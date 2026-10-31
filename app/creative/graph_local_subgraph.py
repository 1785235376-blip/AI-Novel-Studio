"""Bounded current-pin pure-local calls inside the original scope/run owner.

No historical snapshots, child jobs, retries, cache, providers or authorization grants.
A real caller guard and the original scope document are mandatory at every entry.
"""
from copy import deepcopy
import hashlib
from time import monotonic

from ..experimental.common import StaleSourceError
from ..experimental.declarative_adapter_sdk import AdapterRequest, run_trusted_local
from ..experimental.store import canonical
from ..services.v1_capability_service import V1CapabilityService
from .graph_models import (DEFINITIONS, LocalSubgraphParameters, LOCAL_SUBGRAPH_CHILD_IDS,
    LOCAL_SUBGRAPH_CONTRACT, MAX_SUBGRAPH_NODES, MAX_SUBGRAPH_TOTAL_NODES,
    MAX_SUBGRAPH_RECEIPT_BYTES, MAX_OUTPUT_BYTES, NODE_TIMEOUT_SECONDS, validate_output_ports)
from .project_store import BINDING


class LocalSubgraphError(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _context(guard, state):
    if not callable(guard) or not isinstance(state, dict) or not isinstance(state.get("collections"), dict):
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_REAL_CONTEXT_REQUIRED")
    guard()


def resolve(service, nid, scope, actor, node, guard, state):
    """Re-read only the current actor-owned row from the supplied real scope state."""
    _context(guard, state)
    parameters = LocalSubgraphParameters.model_validate(node["parameters"]).model_dump()
    try:
        source = service._owned(nid, scope, actor, service.GRAPHS, parameters["graph_id"], state)
    except (ValueError, KeyError, TypeError) as exc:
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_SOURCE_INVALID") from exc
    guard()
    if (source["version"] != parameters["expected_version"]
            or source["definition_digest"] != parameters["definition_digest"]
            or source["execution_digest"] != parameters["execution_digest"]):
        raise StaleSourceError("CREATIVE_GRAPH_SUBGRAPH_SOURCE_CHANGED")
    definition = source["definition"]
    if definition["schema_version"] != 1:
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_SCHEMA1_CHILD_REQUIRED")
    nodes = {item["id"]: item for item in definition["nodes"]}
    if (not nodes or len(nodes) > MAX_SUBGRAPH_NODES
            or any(item["definition_id"] not in LOCAL_SUBGRAPH_CHILD_IDS for item in nodes.values())):
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_PURE_CHILD_REQUIRED")
    if any(not item["enabled"] for item in nodes.values()):
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_DISABLED_DEPENDENCY")
    entry, output = parameters["input_node_id"], parameters["output_node_id"]
    if (entry not in nodes or nodes[entry]["definition_id"] != "text_reference"
            or output not in nodes or nodes[output]["definition_id"] not in {"draft_prepare", "manual_transform"}):
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_INTERFACE_INVALID")
    incoming = {key: [] for key in nodes}
    for edge in definition["edges"]:
        incoming[edge["target_node_id"]].append(edge)
    if incoming[entry]:
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_BOUNDARY_OCCUPIED")
    for key, item in nodes.items():
        for port in DEFINITIONS[item["definition_id"]]["inputs"]:
            if (port["required"] and not (key == entry and port["id"] == "text")
                    and not any(edge["target_port"] == port["id"] for edge in incoming[key])):
                raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_REQUIRED_INPUT_MISSING")
    closure, queue = {output}, [output]
    while queue:
        for edge in incoming[queue.pop()]:
            if edge["source_node_id"] not in closure:
                closure.add(edge["source_node_id"]); queue.append(edge["source_node_id"])
    if entry not in closure or closure != set(nodes):
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_HIDDEN_OR_UNUSED_DEPENDENCY")
    order = V1CapabilityService._workflow_order([{"id": key} for key in nodes],
        [{"source": edge["source_node_id"], "target": edge["target_node_id"]} for edge in definition["edges"]])
    interface = {"input": {"id": "text", "type": "TEXT", "node_id": entry, "port": "text"},
        "output": {"id": "draft", "type": "DRAFT", "node_id": output, "port": "draft"}}
    normalized = {"nodes": [{key: deepcopy(nodes[value][key]) for key in
        ("id", "definition_id", "definition_version", "enabled", "parameters")} for value in order],
        "edges": sorted(deepcopy(definition["edges"]), key=lambda edge: edge["id"]), "interface": interface}
    binding = {"contract": LOCAL_SUBGRAPH_CONTRACT, "project_id": nid,
        BINDING: service.store.incarnation(nid), "scope": deepcopy(scope), "actor": actor,
        "call_node_id": node["id"], "source": {"id": source["id"], "version": source["version"],
            "definition_digest": source["definition_digest"], "execution_digest": source["execution_digest"]},
        "interface": interface, "node_count": len(order), "closure_digest": _digest(normalized)}
    binding["binding_digest"] = _digest(binding)
    if len(canonical(binding).encode()) > MAX_SUBGRAPH_RECEIPT_BYTES:
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_RECEIPT_CAPACITY")
    guard()
    return {"binding": binding, "definition": deepcopy(definition), "order": order}


def resolve_bindings(service, nid, scope, actor, definition, guard, state):
    _context(guard, state)
    calls = [node for node in definition["nodes"] if node["definition_id"] == "local_subgraph"]
    if definition["schema_version"] != 6 or len(calls) > 1:
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_PARENT_INVALID")
    resolved = {node["id"]: resolve(service, nid, scope, actor, node, guard, state) for node in calls}
    if len(definition["nodes"]) + sum(len(plan["definition"]["nodes"]) for plan in resolved.values()) > MAX_SUBGRAPH_TOTAL_NODES:
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_TOTAL_NODE_CAPACITY")
    guard()
    return resolved


def bindings(resolved):
    return {key: deepcopy(plan["binding"]) for key, plan in resolved.items()}


def current_bindings(service, nid, scope, actor, definition, expected, guard, state):
    _context(guard, state)  # Missing caller context is a programming error, never a stale-source mask.
    try:
        result = resolve_bindings(service, nid, scope, actor, definition, guard, state)
    except LocalSubgraphError as exc:
        raise StaleSourceError("CREATIVE_GRAPH_SUBGRAPH_SOURCE_UNAVAILABLE") from exc
    if not isinstance(expected, dict) or bindings(result) != expected:
        raise StaleSourceError("CREATIVE_GRAPH_SUBGRAPH_RESOLUTION_CHANGED")
    guard()
    return result


def reference_states(service, nid, scope, actor, definition, guard, state):
    _context(guard, state)
    result = []
    for node in definition["nodes"]:
        if node["definition_id"] != "local_subgraph":
            continue
        try:
            resolve(service, nid, scope, actor, node, guard, state)
            status = "CURRENT"
        except StaleSourceError:
            guard(); status = "STALE"
        except (FileNotFoundError, LocalSubgraphError):
            guard(); status = "UNAVAILABLE"
        result.append({"node_id": node["id"], "state": status})
    guard()
    return result


def evaluate(service, nid, scope, actor, node, expected, inputs, adapter, guard, state, request_id):
    _context(guard, state)
    if not isinstance(inputs, dict) or set(inputs) != {"text"}:
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_INPUT_INVALID")
    validate_output_ports("text_reference", {"text": inputs["text"]}, schema_version=1)
    deadline = monotonic() + NODE_TIMEOUT_SECONDS
    def check():
        guard()
        if monotonic() >= deadline:
            raise TimeoutError("CREATIVE_GRAPH_SUBGRAPH_NODE_TIMEOUT")
    plan = resolve(service, nid, scope, actor, node, check, state)
    if plan["binding"] != expected:
        raise StaleSourceError("CREATIVE_GRAPH_SUBGRAPH_RESOLUTION_CHANGED")
    child = plan["definition"]; nodes = {item["id"]: item for item in child["nodes"]}
    outputs, used = {}, 0
    for key in plan["order"]:
        check()
        ports = {}
        for edge in child["edges"]:
            if edge["target_node_id"] == key:
                ports[edge["target_port"]] = deepcopy(outputs[edge["source_node_id"]][edge["source_port"]])
        if key == expected["interface"]["input"]["node_id"]:
            ports["text"] = deepcopy(inputs["text"])
        receipt = run_trusted_local(adapter, AdapterRequest(nodes[key]["definition_id"],
            {"parameters": deepcopy(nodes[key]["parameters"]), "ports": ports},
            request_id + ":" + key, expected["binding_digest"], timeout_seconds=NODE_TIMEOUT_SECONDS), authorize=check)
        value = validate_output_ports(nodes[key]["definition_id"], receipt.output, schema_version=1)
        used += len(canonical(value).encode())
        if used > MAX_OUTPUT_BYTES:
            raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_OUTPUT_CAPACITY")
        check(); outputs[key] = value
    value = validate_output_ports("local_subgraph",
        {"draft": outputs[expected["interface"]["output"]["node_id"]]["draft"]}, schema_version=6)
    check()
    result = {"contract": LOCAL_SUBGRAPH_CONTRACT, "binding_digest": expected["binding_digest"],
        "input_digest": _digest(inputs), "output_digest": _digest(value), "steps": len(plan["order"])}
    if len(canonical(result).encode()) > MAX_SUBGRAPH_RECEIPT_BYTES or len(canonical(value).encode()) > MAX_OUTPUT_BYTES:
        raise LocalSubgraphError("CREATIVE_GRAPH_SUBGRAPH_OUTPUT_CAPACITY")
    check()
    return value, result
