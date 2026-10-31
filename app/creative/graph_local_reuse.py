"""Narrow historical receipt proof, never execution authority or a second cache.

All lookups occur inside the original scope/project transaction. Exact admitted
keys and current-run fences remain owned by CreativeGraphExecutor.
"""
from copy import deepcopy
from datetime import datetime

from .project_store import BINDING
from .graph_models import MAX_HISTORY, MAX_RUNS, NODE_TIMEOUT_SECONDS
from .graph_execution import ADAPTER_VERSION, digest

FORMAT = "creative-local-dependencies/1"
LOCAL = {"text_input", "text_reference", "draft_prepare", "manual_transform", "director_note"}


def eligible(definition):
    return (definition.get("schema_version") == 1
            and all(node.get("definition_id") in LOCAL | {"human_review"} for node in definition.get("nodes", [])))


def signature(row, actor, node_id, outputs, memo=None):
    memo = {} if memo is None else memo
    if node_id in memo:
        return memo[node_id]
    node = next(node for node in row["typed_nodes"] if node["id"] == node_id)
    incoming = sorted((edge["source_node_id"], edge["source_port"], edge["target_port"])
                      for edge in row["typed_edges"] if edge["target_node_id"] == node_id)
    dependencies = [[source, port, target, signature(row, actor, source, outputs, memo)]
                    for source, port, target in incoming]
    inputs = {target: outputs[source][port] for source, port, target in incoming}
    value = digest([FORMAT, row["novel_id"], row[BINDING], row["scope"], actor, row["graph_id"], 1,
                    ADAPTER_VERSION, {key: node[key] for key in
                    ("id", "definition_id", "definition_version", "enabled", "parameters")},
                    dependencies, digest(inputs), digest(outputs[node_id])])
    memo[node_id] = value
    return value


def _timestamp(value):
    return isinstance(value, str) and datetime.fromisoformat(value).utcoffset() is not None


def _proof(executor, target, source, actor, state, guard):
    service = executor.service
    if (source.get("id") == target["id"] or source.get("status") != "SUCCEEDED"
            or source.get("reviewed") is not True or source.get("adapter_version") != ADAPTER_VERSION
            or any(source.get(key) != target.get(key) for key in
                   ("novel_id", "scope", BINDING, "graph_id", "created_by"))
            or source.get("created_by") != actor or source.get("model_execution_contract")
            or source.get("media_execution_contract") or source.get("external_calls") != 0
            or source.get("model_called") is not False or source.get("external_ai_calls") is not False):
        return None
    service._owned(target["novel_id"], target["scope"], actor, service.RUNS, source["id"], state)
    graph = service._owned(target["novel_id"], target["scope"], actor, service.GRAPHS, target["graph_id"], state)
    if not eligible(graph["definition"]) or len(graph["history"]) > MAX_HISTORY:
        return None
    matches = [item for item in [graph, *graph["history"]] if item.get("version") == source.get("graph_version")]
    if len(matches) != 1:
        return None
    historical = deepcopy(matches[0])
    # Snapshots intentionally omit history. Only this private proof document
    # receives an empty list; no stored graph/run authority is changed.
    historical.setdefault("history", [])
    if (not eligible(historical["definition"]) or any(historical.get(key) != graph.get(key)
            for key in ("id", "novel_id", "scope", BINDING, "created_by"))
            or source.get("execution_digest") != historical.get("execution_digest")
            or source.get("graph_schema_version", 1) != 1):
        return None
    proof_state = {**state, "collections": {**state["collections"], service.GRAPHS:
        {**state["collections"][service.GRAPHS], graph["id"]: historical}}}
    # Reuse exact original validation against the proven historical definition.
    # This return value is ONLY cache candidacy; never passed to action/view.
    executor._current(target["novel_id"], target["scope"], actor, source, guard, proof_state)
    nodes = {node["id"]: node for node in source["typed_nodes"]}
    local = {key for key, node in nodes.items() if node["definition_id"] in LOCAL}
    reviews = set(nodes) - local
    if (not reviews or set(source["typed_outputs"]) != local
            or any(item.get("status") != "SUCCEEDED" for item in source["node_states"].values())
            or not isinstance(source.get("history"), list) or len(source["history"]) > MAX_HISTORY):
        return None
    for node_id in local:
        node = nodes[node_id]
        result = source["node_states"][node_id]["output"]["result"]
        provenance = result.get("provenance", {})
        if (result.get("model_called") is not False or result.get("applied") is not False
                or provenance.get("method") != "LOCAL_RULES" or provenance.get("adapter") != ADAPTER_VERSION):
            return None
        inputs = executor._inputs(source, node_id, source["typed_outputs"])
        from ..experimental.declarative_adapter_sdk import AdapterRequest, run_trusted_local
        output = run_trusted_local(executor.adapter, AdapterRequest(node["definition_id"],
            {"parameters": deepcopy(node["parameters"]), "ports": inputs},
            source["id"] + ":" + node_id, digest([source[BINDING], source["scope"], actor]),
            timeout_seconds=NODE_TIMEOUT_SECONDS), authorize=guard).output
        if output != source["typed_outputs"][node_id]:
            return None
    reviewed = set(reviews)
    for review in reviews:
        evidence = source["node_states"][review].get("output") or {}
        if evidence.get("approved_by") != actor.strip() or not _timestamp(evidence.get("approved_at")):
            return None
        waiting = [item for item in source["history"] if item.get("status") == "WAITING_APPROVAL"
                   and item.get("current_node_id") == review]
        waiting_proven = False
        for item in waiting:
            if (any(item.get(key) != source.get(key) for key in
                    ("id", "novel_id", "scope", BINDING, "created_by", "created_at", "graph_id",
                     "graph_version", "graph_digest", "execution_digest", "adapter_version", "request_digest"))
                    or type(item.get("version")) is not int or not 1 <= item["version"] < source["version"]
                    or item.get("updated_by") != actor
                    or item.get("node_states", {}).get(review, {}).get("status") != "WAITING_APPROVAL"
                    or source["trace"][:len(item.get("trace", []))] != item.get("trace")
                    or executor._inputs(item, review, item["typed_outputs"]) !=
                        executor._inputs(source, review, source["typed_outputs"])):
                continue
            prefix = item.get("trace", [])
            transitions = source.get("trace", [])
            if not prefix or len(prefix) >= len(transitions):
                continue
            before, after = prefix[-1], transitions[len(prefix)]
            old, new = before.get("node_statuses", {}), after.get("node_statuses", {})
            if (old != {key: value["status"] for key, value in item["node_states"].items()}
                    or before.get("status") != "WAITING_APPROVAL"
                    or set(old) != set(nodes) or set(new) != set(nodes)
                    or old[review] != "WAITING_APPROVAL" or new[review] != "SUCCEEDED"
                    or after.get("action") != "WORKFLOW_NODE_APPROVED" or after.get("status") != "RUNNING"
                    or not _timestamp(after.get("at"))
                    or any(old[key] != new[key] for key in nodes if key != review)):
                continue
            executor._current(target["novel_id"], target["scope"], actor, item, guard, proof_state)
            waiting_proven = True
            break
        if not waiting_proven:
            return None
    queue = list(reviews)
    while queue:
        node_id = queue.pop()
        for edge in source["typed_edges"]:
            if edge["target_node_id"] == node_id and edge["source_node_id"] not in reviewed:
                reviewed.add(edge["source_node_id"])
                queue.append(edge["source_node_id"])
    return reviewed


class _GuardFailure(Exception):
    def __init__(self, original):
        self.original = original


def cached(executor, row, actor, node_id, state, outputs, guard):
    def proof_guard():
        try:
            guard()
        except Exception as exc:
            raise _GuardFailure(exc) from exc
    guard()
    sources = state["collections"].get(executor.service.RUNS, {})
    if len(sources) > MAX_RUNS:
        return None
    for source in sources.values():
        guard()
        try:
            reviewed = _proof(executor, row, source, actor, state, proof_guard)
            if not reviewed or node_id not in reviewed or node_id not in source["typed_outputs"]:
                continue
            output = source["typed_outputs"][node_id]
            if signature(source, actor, node_id, source["typed_outputs"]) != signature(
                    row, actor, node_id, {**outputs, node_id: output}):
                continue
            proof_guard()
            return deepcopy(output)
        except _GuardFailure as exc:
            raise exc.original
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError, StopIteration, FileNotFoundError, RecursionError, TimeoutError):
            # Missing, legacy, or corrupt evidence never grants reuse. Authority
            # exceptions are deliberately not swallowed.
            guard()
    guard()
    return None
