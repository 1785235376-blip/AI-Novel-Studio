"""Closed schema7 admission/projection over the original WorkflowRun owner."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os

from ..experimental.common import StaleSourceError
from ..experimental.declarative_agents import _ScopedOriginalWorkflowHost
from ..experimental.flags import enabled_flags
from ..experimental.store import canonical
from ..services.v1_capability_service import V1CapabilityService

CONTRACT = "creative-graph-local-conditions/1"
CACHE_MODE = "DISABLED_LOCAL_CONDITIONS_V1"
NODE_IDS = frozenset({"text_input", "local_condition", "text_reference", "draft_prepare", "manual_transform", "human_review"})
SKIP_ERROR = {"code": "CREATIVE_GRAPH_BRANCH_NOT_SELECTED"}


def require_conditions():
    if os.getenv("CREATIVE_GRAPH_CONDITIONS_V1") != "1" or "narrative_production_v2" not in enabled_flags():
        raise ValueError("CREATIVE_GRAPH_CONDITIONS_DISABLED")


def selected_port(parameters):
    predicate = parameters["predicate"]
    matched = predicate["value"] if predicate["kind"] == "boolean" else predicate["value"] == predicate["equals"]
    return "when_true" if matched else "when_false"


def evaluate(parameters, inputs):
    return {selected_port(parameters): inputs["text"]}


def compile_plan(definition):
    """One inline source, one fixed condition, two disjoint linear reviewed arms."""
    def invalid():
        raise ValueError("CREATIVE_GRAPH_CONDITION_TOPOLOGY_INVALID")
    nodes = {n["id"]: n for n in definition["nodes"]}
    if any(n["definition_id"] not in NODE_IDS or not n["enabled"] for n in nodes.values()): invalid()
    conditions = [n for n in nodes.values() if n["definition_id"] == "local_condition"]
    sources = [n for n in nodes.values() if n["definition_id"] == "text_input"]
    if len(conditions) != 1 or len(sources) != 1: invalid()
    condition, source = conditions[0], sources[0]
    incoming, outgoing = {k: [] for k in nodes}, {k: [] for k in nodes}
    for edge in definition["edges"]:
        outgoing[edge["source_node_id"]].append(edge)
        incoming[edge["target_node_id"]].append(edge)
    if incoming[source["id"]] or len(outgoing[source["id"]]) != 1: invalid()
    link = outgoing[source["id"]][0]
    if (link["target_node_id"] != condition["id"] or link["source_port"] != "text"
            or link["target_port"] != "text" or len(incoming[condition["id"]]) != 1): invalid()
    roots = outgoing[condition["id"]]
    if len(roots) != 2 or {e["source_port"] for e in roots} != {"when_true", "when_false"}: invalid()
    seen = {source["id"], condition["id"]}
    arms = {}
    for root in sorted(roots, key=lambda e: e["source_port"]):
        path, edge = [], root
        while True:
            key = edge["target_node_id"]
            if key in seen or len(incoming[key]) != 1: invalid()
            seen.add(key); path.append(key)
            node = nodes[key]
            if node["definition_id"] == "human_review":
                if outgoing[key] or edge["target_port"] != "draft": invalid()
                break
            if node["definition_id"] not in {"text_reference", "draft_prepare", "manual_transform"}: invalid()
            if edge["target_port"] != "text" or len(outgoing[key]) != 1: invalid()
            edge = outgoing[key][0]
        arms[root["source_port"]] = path
    if seen != set(nodes): invalid()
    order = V1CapabilityService._workflow_order(list(nodes.values()), [
        {"source": e["source_node_id"], "target": e["target_node_id"]} for e in definition["edges"]])
    chosen = selected_port(condition["parameters"])
    active = {source["id"], condition["id"], *arms[chosen]}
    plan = {"contract": CONTRACT, "condition_node_id": condition["id"], "selected_port": chosen,
        "active_node_ids": [key for key in order if key in active],
        "skipped_node_ids": [key for key in order if key not in active]}
    plan["plan_digest"] = hashlib.sha256(canonical([definition, plan]).encode()).hexdigest()
    return plan


def validate_run(row, plan):
    """Reject forged skips, hidden dispatch, stale decisions and cache receipts."""
    if (row.get("conditional_plan") != plan or row.get("cache", {}).get("mode") != CACHE_MODE
            or row.get("cache", {}).get("hits") != 0 or row.get("reuse_reviewed_local_dependencies", False)):
        raise StaleSourceError("CREATIVE_GRAPH_CONDITION_RUN_BINDING_CHANGED")
    skipped = set(plan["skipped_node_ids"])
    active = set(plan["active_node_ids"])
    if (row.get("current_node_id") is not None and row["current_node_id"] not in active
            or any(item.get("node_id") not in active for item in row.get("dispatch_trace", []))
            or any(any(item.get("node_statuses", {}).get(key) != "SKIPPED" for key in skipped)
                for item in row.get("trace", []))):
        raise StaleSourceError("CREATIVE_GRAPH_CONDITION_SKIP_PROOF_CHANGED")
    states = row.get("node_states", {})
    for key in skipped:
        if states.get(key) != {"status": "SKIPPED", "output": None, "error": SKIP_ERROR}:
            raise StaleSourceError("CREATIVE_GRAPH_CONDITION_SKIP_PROOF_CHANGED")
    if (skipped.intersection(row.get("typed_outputs", {})) or skipped.intersection(row.get("cache_keys", {}))
            or any(item.get("node_id") in skipped for item in row.get("dispatch_trace", []))):
        raise StaleSourceError("CREATIVE_GRAPH_CONDITION_SKIP_PROOF_CHANGED")
    reviews = [n["id"] for n in row["typed_nodes"] if n["id"] in active and n["definition_id"] == "human_review"]
    reviewed = all(states.get(key, {}).get("status") == "SUCCEEDED" for key in reviews)
    if type(row.get("reviewed")) is not bool or row["reviewed"] != reviewed:
        raise StaleSourceError("CREATIVE_GRAPH_CONDITION_REVIEW_RECEIPT_CHANGED")
    if reviewed:
        for key in reviews:
            receipt = states[key].get("output") or {}
            if receipt.get("approved_by") != row["created_by"].strip() or not receipt.get("approved_at"):
                raise StaleSourceError("CREATIVE_GRAPH_CONDITION_REVIEW_RECEIPT_CHANGED")
    if row.get("reviewed_nodes") != (sorted(active) if reviewed else []):
        raise StaleSourceError("CREATIVE_GRAPH_CONDITION_REVIEW_RECEIPT_CHANGED")
    successful = {key for key in plan["active_node_ids"] if states.get(key, {}).get("status") == "SUCCEEDED"
        and next(n for n in row["typed_nodes"] if n["id"] == key)["definition_id"] != "human_review"}
    if set(row.get("typed_outputs", {})) != successful or set(row.get("cache_keys", {})) != successful:
        raise StaleSourceError("CREATIVE_GRAPH_CONDITION_OUTPUT_RECEIPT_CHANGED")


class ConditionalWorkflowHost(_ScopedOriginalWorkflowHost):
    """Storage projection only: advance/claim/complete/review stay original methods."""
    def _project(self, row):
        result = deepcopy(row)
        active = set(self.row["conditional_plan"]["active_node_ids"])
        snapshot = result["definition_snapshot"]
        snapshot["nodes"] = [n for n in snapshot["nodes"] if n["id"] in active]
        snapshot["edges"] = [e for e in snapshot["edges"] if e["source"] in active and e["target"] in active]
        snapshot["topological_order"] = [key for key in snapshot["topological_order"] if key in active]
        result["node_states"] = {key: value for key, value in result["node_states"].items() if key in active}
        return result

    def _get(self, name, rid):
        return self._project(super()._get(name, rid))

    def _update(self, name, rid, payload, **kwargs):
        payload = deepcopy(payload)
        if "definition_snapshot" in payload:
            raise ValueError("CREATIVE_GRAPH_CONDITION_SNAPSHOT_WRITE_DENIED")
        if "node_states" in payload:
            active = set(self.row["conditional_plan"]["active_node_ids"])
            if set(payload["node_states"]) != active:
                raise ValueError("CREATIVE_GRAPH_CONDITION_ENGINE_PROJECTION_INVALID")
            payload["node_states"] = {**deepcopy(self.row["node_states"]), **payload["node_states"]}
        return self._project(super()._update(name, rid, payload, **kwargs))

    def workflow_dispatch_guard(self, run, node):
        if node["id"] not in self.row["conditional_plan"]["active_node_ids"]:
            raise ValueError("CREATIVE_GRAPH_CONDITION_UNSELECTED_DISPATCH_DENIED")
        return super().workflow_dispatch_guard(run, node)
