"""M2-A pure local orchestration through the original WorkflowRun state owner.

There is no worker, scheduler, provider, chapter anchor or alternate JobManager.
All claims/completions/review decisions are original engine transitions. Asset
inputs are rejected before admission until an atomic original-owner seam exists.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib

from ..experimental.common import StaleSourceError, change_row, check_version, new_row, now
from ..experimental.declarative_agents import _ScopedOriginalWorkflowHost
from ..experimental.declarative_adapter_sdk import AdapterCapabilities, AdapterRequest, run_trusted_local
from ..experimental.store import canonical
from ..workflow_recipes import execute_local_recipe_node
from .graph_models import (GraphAction, GraphPreflight, MAX_OUTPUT_BYTES, MAX_NODES, MAX_HISTORY,
                          RUN_TIMEOUT_SECONDS, NODE_TIMEOUT_SECONDS, validate_output_ports)
from .project_store import BINDING

ADAPTER_VERSION = "creative-graph-local/1"
CACHE_MODE = "SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY"


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class _LocalGraphAdapter:
    capabilities = AdapterCapabilities("builtin.creative-graph-local", ADAPTER_VERSION,
        ("text_input", "text_reference", "draft_prepare", "manual_transform", "director_note"),
        max_input_bytes=32_000, max_output_bytes=MAX_OUTPUT_BYTES)

    def execute(self, request):
        parameters, ports = request.input["parameters"], request.input["ports"]
        if request.node_type == "text_input":
            return {"text": parameters["text"]}
        if request.node_type == "text_reference":
            return {"text": ports["text"]}
        if request.node_type == "director_note":
            return {"direction": {"note": parameters["note"]}}
        if request.node_type == "draft_prepare":
            result = execute_local_recipe_node("draft_prepare", {"source_text": ports["text"]}, {}, {})
            draft = {"text": result["draft"], "origin": "USER_SUPPLIED", "plan": result["plan"]}
        elif request.node_type == "manual_transform":
            draft = {"text": parameters["result"], "origin": "MANUAL"}
        else:
            raise ValueError("CREATIVE_GRAPH_LOCAL_ADAPTER_REQUIRED")
        if "direction" in ports:
            # Carry author notes as explicit reference material. Local rules do
            # not claim to interpret directions or generate different prose.
            draft["direction"] = deepcopy(ports["direction"])
        return {"draft": draft}


class CreativeGraphExecutor:
    def __init__(self, service):
        self.service = service
        self.adapter = _LocalGraphAdapter()

    @staticmethod
    def _timing(row):
        timeout, started = row.get("timeout_seconds"), row.get("started_at")
        if (type(timeout) is not int or timeout != RUN_TIMEOUT_SECONDS or not 1 <= timeout <= 86_400
                or not isinstance(started, str) or not 1 <= len(started) <= 64):
            raise ValueError("CREATIVE_GRAPH_RUNTIME_TIMING_INVALID")
        try:
            stamp = datetime.fromisoformat(started)
            if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
                raise ValueError("UTC admission timestamp required")
            return (stamp + timedelta(seconds=timeout)).isoformat()
        except (ValueError, OverflowError):
            raise ValueError("CREATIVE_GRAPH_RUNTIME_TIMING_INVALID") from None

    def _current(self, nid, scope, actor, row, guard, state=None):
        guard()
        self._timing(row)
        graph = self.service._owned(nid, scope, actor, self.service.GRAPHS, row["graph_id"], state)
        if (graph["version"] != row["graph_version"] or graph["definition_digest"] != row["graph_digest"]
                or row.get(BINDING) != graph[BINDING]):
            raise StaleSourceError("CREATIVE_GRAPH_RUN_DEFINITION_CHANGED")
        if row.get("adapter_version") != ADAPTER_VERSION:
            raise StaleSourceError("CREATIVE_GRAPH_ADAPTER_CHANGED")
        selected = row["selected_closure"]
        expected = [node for node in graph["definition"]["nodes"] if node["id"] in selected]
        if (row.get("typed_nodes") != expected or any(node["definition_id"] == "asset_reference" for node in expected)
                or row.get("typed_edges") != [edge for edge in graph["definition"]["edges"]
                    if edge["source_node_id"] in selected and edge["target_node_id"] in selected]):
            raise StaleSourceError("CREATIVE_GRAPH_RUN_BINDING_CHANGED")
        preflight = self.service._preflight(graph, GraphPreflight(expected_version=graph["version"],
            target_node_ids=selected), actor)
        pairs = list(dict.fromkeys((edge["source_node_id"], edge["target_node_id"]) for edge in row["typed_edges"]))
        snapshot = {"title": graph["definition"]["title"],
            "nodes": [{"id": node["id"], "name": node["id"], "config": {},
                "type": "manual_approval" if node["definition_id"] == "human_review" else "agent_task"}
                for node in expected],
            "edges": [{"source": source, "target": target} for source, target in pairs],
            "topological_order": preflight["execution_order"]}
        statuses = {"PENDING", "WAITING_APPROVAL", "QUEUED", "WORKING", "SUCCEEDED", "FAILED", "SKIPPED", "REJECTED"}
        if (not preflight["executable"] or len(set(selected)) != len(selected)
                or row.get("definition_snapshot") != snapshot or set(row.get("node_states", {})) != set(selected)
                or any(not isinstance(value, dict) or value.get("status") not in statuses for value in row["node_states"].values())):
            raise StaleSourceError("CREATIVE_GRAPH_RUN_ENGINE_BINDING_CHANGED")
        by_id = {node["id"]: node for node in expected}
        if not isinstance(row.get("typed_outputs"), dict) or set(row["typed_outputs"]) - set(by_id):
            raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
        for node_id, output in row["typed_outputs"].items():
            if row["node_states"][node_id]["status"] != "SUCCEEDED":
                raise ValueError("CREATIVE_GRAPH_OUTPUT_STATE_INVALID")
            validate_output_ports(by_id[node_id]["definition_id"], output)
            receipt = row.get("cache_keys", {}).get(node_id, {})
            engine_output = (row["node_states"][node_id].get("output") or {}).get("result") or {}
            if (engine_output.get("ports") != output or receipt.get("output_digest") != digest(output)
                    or receipt.get("key") != self._key(row, actor, by_id[node_id], self._inputs(row, node_id, row["typed_outputs"]))):
                raise ValueError("CREATIVE_GRAPH_OUTPUT_RECEIPT_INVALID")
        if any(node["definition_id"] == "text_generate" for node in expected):
            if self.service.model_runtime is None:
                raise StaleSourceError("CREATIVE_MODEL_RUNTIME_UNAVAILABLE")
            self.service.model_runtime.validate_snapshot(row)
        guard()
        return graph

    def create(self, nid, scope, actor, rid, body, guard):
        incarnation, current = self.service._context(nid, scope, actor, guard)
        with self.service.store.transaction(nid, scope) as state:
            graph = self.service._owned(nid, scope, actor, self.service.GRAPHS, rid, state)
            check_version(graph, body.expected_graph_version)
            preflight = self.service._preflight(graph, GraphPreflight(expected_version=body.expected_graph_version,
                target_node_ids=body.target_node_ids), actor)
            if not preflight["executable"]:
                raise ValueError("CREATIVE_GRAPH_EXECUTION_BLOCKED")
            if preflight["preflight_digest"] != body.reviewed_preflight_digest:
                raise StaleSourceError("CREATIVE_GRAPH_EXACT_PREFLIGHT_REQUIRED")
            current()
            request_digest = digest([rid, body.model_dump(), incarnation, scope, actor])
            rows = state["collections"].setdefault(self.service.RUNS, {})
            found = next((row for row in rows.values() if row.get("created_by") == actor and row.get("request_id") == body.request_id), None)
            if found:
                if found.get("request_digest") != request_digest:
                    raise ValueError("CREATIVE_GRAPH_REQUEST_ID_REUSED")
                result = self.view(nid, scope, actor, found, current, state)
                current(); return result
            selected = preflight["selected_closure"]
            typed_nodes = [deepcopy(node) for node in graph["definition"]["nodes"] if node["id"] in selected]
            typed_edges = [deepcopy(edge) for edge in graph["definition"]["edges"]
                           if edge["source_node_id"] in selected and edge["target_node_id"] in selected]
            pairs = list(dict.fromkeys((edge["source_node_id"], edge["target_node_id"]) for edge in typed_edges))
            engine_nodes = [{"id": node["id"], "name": node["id"], "config": {},
                "type": "manual_approval" if node["definition_id"] == "human_review" else "agent_task"}
                for node in typed_nodes]
            payload = {BINDING: incarnation, "graph_id": rid, "graph_version": graph["version"],
                "graph_digest": graph["definition_digest"], "execution_digest": graph["execution_digest"],
                "request_id": body.request_id, "request_digest": request_digest,
                "adapter_version": ADAPTER_VERSION, "selected_closure": selected,
                "typed_nodes": typed_nodes, "typed_edges": typed_edges,
                "definition_snapshot": {"title": graph["definition"]["title"], "nodes": engine_nodes,
                    "edges": [{"source": source, "target": target} for source, target in pairs],
                    "topological_order": preflight["execution_order"]},
                "node_states": {node["id"]: {"status": "PENDING", "output": None, "error": None} for node in typed_nodes},
                "typed_outputs": {}, "cache_keys": {}, "cache": {"hits": 0, "misses": 0, "mode": CACHE_MODE},
                "input": {}, "status": "QUEUED", "initiated_by": actor, "current_node_id": None,
                "started_at": now(), "timeout_seconds": RUN_TIMEOUT_SECONDS,
                "max_output_bytes": MAX_OUTPUT_BYTES, "step_limit": MAX_NODES,
                "steps_completed": 0, "attempt": 1, "retry_of": None, "trace": [], "dispatch_trace": [],
                "reviewed": False, "reviewed_nodes": [], "external_ai_calls": False, "external_calls": 0, "model_called": False,
                "applied": False, "execution_mode": "ORIGINAL_WORKFLOW_LOCAL_RULES"}
            if any(node["definition_id"] == "text_generate" for node in typed_nodes):
                from .ai_execution import CONTRACT
                payload.update(model_execution_contract=CONTRACT, model_preview=None, model_execution=None)
            row = new_row(nid, scope, actor, payload)
            rows[row["id"]] = row
            self.service._capacity(state); current()
            return self.view(nid, scope, actor, row, current, state)

    @staticmethod
    def _inputs(row, node_id, outputs):
        result = {}
        for edge in row["typed_edges"]:
            if edge["target_node_id"] != node_id:
                continue
            value = outputs.get(edge["source_node_id"], {})
            if edge["source_port"] not in value:
                raise ValueError("CREATIVE_GRAPH_UPSTREAM_OUTPUT_MISSING")
            result[edge["target_port"]] = deepcopy(value[edge["source_port"]])
        return result

    def _review(self, row):
        node_id = row.get("current_node_id")
        node = next((node for node in row["typed_nodes"] if node["id"] == node_id), None)
        if row["status"] != "WAITING_APPROVAL" or not node or node["definition_id"] != "human_review":
            return None
        draft = self._inputs(row, node_id, row["typed_outputs"])["draft"]
        return {"node_id": node_id, "draft": draft,
                "output_digest": digest([row["id"], node_id, row["graph_version"], draft])}

    def view(self, nid, scope, actor, row, guard, state=None):
        # Validate ownership even when a caller supplies a transaction's row.
        self.service._owned(nid, scope, actor, self.service.RUNS, row["id"], state)
        try:
            self._current(nid, scope, actor, row, guard, state)
            stale = False
            if row.get("model_execution_contract"):
                if self.service.model_runtime is None:
                    raise StaleSourceError("CREATIVE_MODEL_RUNTIME_UNAVAILABLE")
                self.service.model_runtime.output_authority(row)
        except (StaleSourceError, FileNotFoundError):
            guard(); stale = True
        result = {key: deepcopy(row[key]) for key in ("id", "version", "graph_id", "graph_version", "status",
            "current_node_id", "cache", "created_at", "updated_at", "reviewed")}
        result.update(project_id=nid, scope=deepcopy(scope), stale=stale,
            timeout_seconds=row["timeout_seconds"], deadline_at=self._timing(row),
            node_states={node_id: {"status": value["status"],
                "reviewed": node_id in row.get("reviewed_nodes", []),
                "output": None if stale or row["status"] in {"CANCELLED", "REJECTED", "FAILED"} else deepcopy(row["typed_outputs"].get(node_id)),
                "error": {"code": "CREATIVE_GRAPH_NODE_FAILED"} if value.get("error") else None}
                for node_id, value in row["node_states"].items()},
            review=None if stale else self._review(row), model_called=False, external_calls=0, applied=False)
        if any(node["definition_id"] == "text_generate" for node in row["typed_nodes"]):
            if self.service.model_runtime is None:
                raise ValueError("CREATIVE_MODEL_RUNTIME_UNAVAILABLE")
            result["model_runtime"] = self.service.model_runtime.public(row, stale=stale)
            result["model_called"] = bool(row.get("model_execution", {}).get("model_called")) if row.get("model_execution") else False
            if not stale:
                try:
                    self.service.model_runtime.output_authority(row)
                except (StaleSourceError, FileNotFoundError):
                    result["stale"] = True
                    result["review"] = None
                    result["model_runtime"]["preview"] = None
                    for value in result["node_states"].values():
                        value["output"] = None
        guard(); return result

    def _key(self, row, actor, node, inputs):
        return digest([row[BINDING], row["scope"], actor, row["graph_id"], row["graph_version"],
            row["execution_digest"], ADAPTER_VERSION, node["id"], node["definition_id"],
            node["definition_version"], node["parameters"], inputs])

    def _cached(self, row, actor, node_id, key, state):
        if any(item["id"] == node_id and item["definition_id"] == "text_generate" for item in row["typed_nodes"]):
            return None
        for source in state["collections"].get(self.service.RUNS, {}).values():
            if (source["id"] == row["id"] or source.get("created_by") != actor or source.get("scope") != row["scope"]
                    or source.get(BINDING) != row[BINDING] or source.get("graph_id") != row["graph_id"]
                    or source.get("graph_version") != row["graph_version"] or source.get("status") != "SUCCEEDED"
                    or not source.get("reviewed") or node_id not in source.get("reviewed_nodes", [])
                    or source.get("adapter_version") != ADAPTER_VERSION):
                continue
            receipt = source.get("cache_keys", {}).get(node_id)
            output = source.get("typed_outputs", {}).get(node_id)
            if receipt and receipt.get("key") == key and output is not None and receipt.get("output_digest") == digest(output):
                return deepcopy(output)
        return None

    def _drive(self, host, row, actor, state, guard):
        outputs = deepcopy(row["typed_outputs"])
        cache_keys = deepcopy(row["cache_keys"])
        cache = deepcopy(row["cache"])
        nodes = {node["id"]: node for node in row["typed_nodes"]}
        for _ in range(MAX_NODES + 1):
            current = host.get_workflow_run(row["id"])
            node_id = current.get("current_node_id")
            if current["status"] != "WAITING_APPROVAL" or node_id is None:
                break
            node = nodes[node_id]
            if node["definition_id"] in {"human_review", "text_generate"}:
                break
            guard()
            host.trigger_agent_node(row["id"], node_id, actor)
            host.claim_agent_task(row["id"], node_id, actor)
            inputs = self._inputs(row, node_id, outputs)
            key = self._key(row, actor, node, inputs)
            output = self._cached(row, actor, node_id, key, state)
            hit = output is not None
            try:
                if output is None:
                    receipt = run_trusted_local(self.adapter, AdapterRequest(node["definition_id"],
                        {"parameters": deepcopy(node["parameters"]), "ports": inputs},
                        row["id"] + ":" + node_id, digest([row[BINDING], row["scope"], actor]),
                        timeout_seconds=NODE_TIMEOUT_SECONDS), authorize=guard)
                    output = receipt.output
                output = validate_output_ports(node["definition_id"], output)
            except (ValueError, TimeoutError):
                guard()
                host.complete_agent_task(row["id"], node_id, "FAILED", error="CREATIVE_GRAPH_LOCAL_NODE_FAILED")
                break
            guard()
            if host.get_workflow_run(row["id"])["status"] == "FAILED":
                break
            outputs[node_id] = deepcopy(output)
            cache_keys[node_id] = {"key": key, "output_digest": digest(output)}
            cache["hits" if hit else "misses"] += 1
            host.complete_agent_task(row["id"], node_id, "SUCCEEDED", output={"ports": output,
                "provenance": {"method": "LOCAL_RULES", "adapter": ADAPTER_VERSION, "cache_hit": hit},
                "model_called": False, "applied": False})
        else:
            raise ValueError("CREATIVE_GRAPH_STEP_LIMIT")
        result = deepcopy(host.row)
        result.update(typed_outputs=outputs, cache_keys=cache_keys, cache=cache)
        reviews = [node["id"] for node in row["typed_nodes"] if node["definition_id"] == "human_review"]
        result["reviewed"] = bool(reviews) and all(result["node_states"][node_id]["status"] == "SUCCEEDED" for node_id in reviews)
        reviewed = {node_id for node_id in reviews if result["node_states"][node_id]["status"] == "SUCCEEDED"}
        queue = list(reviewed)
        while queue:
            node_id = queue.pop()
            for edge in row["typed_edges"]:
                if edge["target_node_id"] == node_id and edge["source_node_id"] not in reviewed:
                    reviewed.add(edge["source_node_id"])
                    queue.append(edge["source_node_id"])
        result["reviewed_nodes"] = sorted(reviewed)
        return result

    def action(self, nid, scope, actor, rid, action, value, guard):
        body = GraphAction.model_validate(value)
        if action not in {"execute", "approve", "reject", "cancel", "pause", "resume"}:
            raise ValueError("CREATIVE_GRAPH_ACTION_INVALID")
        if action not in {"approve", "reject"} and (body.node_id is not None or body.reviewed_output_digest is not None):
            raise ValueError("CREATIVE_GRAPH_ACTION_BINDING_INVALID")
        _, current = self.service._context(nid, scope, actor, guard)
        with self.service.store.transaction(nid, scope) as state:
            row = self.service._owned(nid, scope, actor, self.service.RUNS, rid, state)
            check_version(row, body.expected_version)
            self._timing(row)
            if row.get("model_execution_contract") and action not in {"cancel", "reject"} and len(row["history"]) >= MAX_HISTORY - 2:
                raise ValueError("CREATIVE_MODEL_ACTION_HISTORY_CAPACITY")
            if action in {"pause", "resume"} and row.get("model_execution") and row["node_states"][row["model_execution"]["node_id"]]["status"] == "WORKING":
                raise ValueError("CREATIVE_MODEL_INFLIGHT_PAUSE_UNAVAILABLE")
            def fresh():
                current()
                if action not in {"cancel", "reject"}:
                    self._current(nid, scope, actor, row, current, state)
                if action == "approve" and row.get("model_execution_contract"):
                    self.service.model_runtime.output_authority(row)
            fresh()
            engine_row = deepcopy(row)
            if action == "execute":
                if row["status"] != "QUEUED":
                    raise ValueError("CREATIVE_GRAPH_EXECUTE_REQUIRES_QUEUED")
            host = _ScopedOriginalWorkflowHost(engine_row, fresh)
            timed = host.get_workflow_run(rid)
            if timed["status"] == "FAILED" and timed.get("error", {}).get("code") == "WORKFLOW_TIMEOUT":
                result = timed
            else:
                if action in {"approve", "reject"}:
                    if action == "approve" and row.get("model_execution_contract"):
                        self.service.model_runtime.output_authority(row)
                    review = self._review(row)
                    if (not review or body.node_id != review["node_id"]
                            or body.reviewed_output_digest != review["output_digest"]):
                        raise StaleSourceError("CREATIVE_GRAPH_EXACT_REVIEW_REQUIRED")
                    if action == "approve":
                        host.approve_workflow_node(rid, body.node_id, actor, body.note)
                    else:
                        host.reject_workflow_node(rid, body.node_id, actor, body.note)
                elif action == "execute":
                    host._advance_workflow_run(rid)
                else:
                    host.set_workflow_run_state(rid, action)
                result = self._drive(host, row, actor, state, fresh) if action in {"execute", "approve", "resume"} else deepcopy(host.row)
            payload = {key: item for key, item in result.items() if key not in {"history", "version"}}
            payload.update(trace=row["trace"] + host.transitions, dispatch_trace=row["dispatch_trace"] + host.dispatches)
            change_row(row, actor, body.expected_version, lambda item: item.update(payload))
            self.service._capacity(state); fresh()
            return self.view(nid, scope, actor, row, current, state)
