"""M2-A pure local orchestration through the original WorkflowRun state owner.

There is no worker, scheduler, provider, chapter anchor or alternate JobManager.
All claims/completions/review decisions are original engine transitions. Schema-3/4
assets use the existing scope -> asset -> project atomic source fences.
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
from .graph_models import (GraphAction, GraphRunCreate, GraphMediaRunCreate, parse_graph_run_create,
                          MAX_OUTPUT_BYTES, MAX_NODES, MAX_HISTORY, MAX_MEDIA_HISTORY,
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

    def _current(self, nid, scope, actor, row, guard, state=None, *, check_assets=True):
        if check_assets and row.get("graph_schema_version") in {3, 4} and not self.service.asset_inputs.in_phase(nid, scope, actor):
            with self.service.asset_inputs.phase(nid, scope, actor, guard) as document:
                return self._current(nid, scope, actor, row, guard, document)
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
        schema = graph["definition"]["schema_version"]
        if (row.get("typed_nodes") != expected or (schema not in {3, 4} and any(node["definition_id"] == "asset_reference" for node in expected))
                or (schema in {3, 4} and row.get("graph_schema_version") != schema)
                or row.get("typed_edges") != [edge for edge in graph["definition"]["edges"]
                    if edge["source_node_id"] in selected and edge["target_node_id"] in selected]):
            raise StaleSourceError("CREATIVE_GRAPH_RUN_BINDING_CHANGED")
        # Schema 3's static topology remains reviewed after an explicit timeline
        # edit advances its base. Original asset inputs are checked below; the
        # actual edited timeline snapshot is fenced by its original runtime.
        preflight = self.service._preflight(graph, {"expected_version": graph["version"],
            "target_node_ids": selected}, actor, check_assets=False if schema in {3, 4} else check_assets)
        pairs = list(dict.fromkeys((edge["source_node_id"], edge["target_node_id"]) for edge in row["typed_edges"]))
        snapshot = {"title": graph["definition"]["title"],
            "nodes": [{"id": node["id"], "name": node["id"], "config": {},
                "type": "manual_approval" if node["definition_id"] in {"human_review", "media_review"} else "agent_task"}
                for node in expected],
            "edges": [{"source": source, "target": target} for source, target in pairs],
            "topological_order": preflight["execution_order"]}
        statuses = {"PENDING", "WAITING_APPROVAL", "QUEUED", "WORKING", "SUCCEEDED", "FAILED", "SKIPPED", "REJECTED"}
        if (not preflight["executable"] or len(set(selected)) != len(selected)
                or row.get("step_limit") != max(MAX_NODES, len(expected))
                or row.get("definition_snapshot") != snapshot or set(row.get("node_states", {})) != set(selected)
                or any(not isinstance(value, dict) or value.get("status") not in statuses for value in row["node_states"].values())):
            raise StaleSourceError("CREATIVE_GRAPH_RUN_ENGINE_BINDING_CHANGED")
        by_id = {node["id"]: node for node in expected}
        if not isinstance(row.get("typed_outputs"), dict) or set(row["typed_outputs"]) - set(by_id):
            raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
        for node_id, output in row["typed_outputs"].items():
            if row["node_states"][node_id]["status"] != "SUCCEEDED":
                raise ValueError("CREATIVE_GRAPH_OUTPUT_STATE_INVALID")
            validate_output_ports(by_id[node_id]["definition_id"], output, schema_version=schema)
            if by_id[node_id]["definition_id"] in {"image_reference", "image_prompt", "image_style"}:
                from .graph_image_nodes import execute_image_local
                if output != execute_image_local(by_id[node_id], self._inputs(row, node_id, row["typed_outputs"])):
                    raise StaleSourceError("CREATIVE_GRAPH_IMAGE_TRANSFORM_CHANGED")
            if by_id[node_id]["definition_id"] in {"director_plan", "storyboard_plan", "storyboard_prompt"}:
                from .graph_planning_nodes import execute_planning_local
                if output != execute_planning_local(self.service, nid, scope, by_id[node_id],
                        self._inputs(row, node_id, row["typed_outputs"]), guard, state):
                    raise StaleSourceError("CREATIVE_GRAPH_PLANNING_OUTPUT_CHANGED")
            receipt = row.get("cache_keys", {}).get(node_id, {})
            engine_output = (row["node_states"][node_id].get("output") or {}).get("result") or {}
            if (engine_output.get("ports") != output or receipt.get("output_digest") != digest(output)
                    or receipt.get("key") != self._key(row, actor, by_id[node_id], self._inputs(row, node_id, row["typed_outputs"]))):
                raise ValueError("CREATIVE_GRAPH_OUTPUT_RECEIPT_INVALID")
            if schema == 3 and by_id[node_id]["definition_id"] == "human_review":
                approved = row["node_states"][node_id].get("output") or {}
                if (output.get("reviewed_draft") != self._inputs(row, node_id, row["typed_outputs"])["draft"]
                        or approved.get("approved_by") != actor.strip() or not approved.get("approved_at")
                        or engine_output.get("provenance") != {"method": "ORIGINAL_HUMAN_REVIEW",
                            "review_node_id": node_id, "reviewed_output_digest": digest([row["id"], node_id,
                                row["graph_version"], output["reviewed_draft"]])}):
                    raise StaleSourceError("CREATIVE_GRAPH_REVIEWED_DRAFT_RECEIPT_CHANGED")
        if any(node["definition_id"] == "text_generate" for node in expected):
            if self.service.model_runtime is None:
                raise StaleSourceError("CREATIVE_MODEL_RUNTIME_UNAVAILABLE")
            self.service.model_runtime.validate_snapshot(row)
        if schema in {3, 4}:
            from .graph_planning_nodes import current_documents
            current_documents(self.service, nid, scope, expected, guard, state)
            if check_assets:
                self.service.asset_inputs.current(nid, scope, actor, row, guard, state)
            if any(node["definition_id"] in {"media_generate", "timeline_export", "image_generate", "image_upscale"} for node in expected):
                if self.service.media_runtime is None:
                    raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE")
                self.service.media_runtime.validate_snapshot(row)
                document = state if state is not None else self.service.store.read(nid, scope)
                self.service.media_runtime.timeline_current(row, document, guard)
        guard()
        return graph

    def create(self, nid, scope, actor, rid, body, guard):
        body = GraphMediaRunCreate.model_validate(body.model_dump() if isinstance(body, GraphRunCreate) else body)
        incarnation, current = self.service._context(nid, scope, actor, guard)
        original = self.service._owned(nid, scope, actor, self.service.GRAPHS, rid)
        phase = (self.service.asset_inputs.transaction(nid, scope, actor, current)
            if original["definition"]["schema_version"] in {3, 4} else self.service.store.transaction(nid, scope))
        with phase as state:
            graph = self.service._owned(nid, scope, actor, self.service.GRAPHS, rid, state)
            check_version(graph, body.expected_graph_version)
            body = parse_graph_run_create(body, graph["definition"])
            preflight = self.service._preflight(graph, {"expected_version": body.expected_graph_version,
                "target_node_ids": body.target_node_ids}, actor, guard=current, state=state)
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
                "type": "manual_approval" if node["definition_id"] in {"human_review", "media_review"} else "agent_task"}
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
                "max_output_bytes": MAX_OUTPUT_BYTES, "step_limit": max(MAX_NODES, len(typed_nodes)),
                "steps_completed": 0, "attempt": 1, "retry_of": None, "trace": [], "dispatch_trace": [],
                "reviewed": False, "reviewed_nodes": [], "external_ai_calls": False, "external_calls": 0, "model_called": False,
                "applied": False, "execution_mode": "ORIGINAL_WORKFLOW_LOCAL_RULES"}
            if any(node["definition_id"] == "text_generate" for node in typed_nodes):
                from .ai_execution import CONTRACT
                payload.update(model_execution_contract=CONTRACT, model_preview=None, model_execution=None)
            if graph["definition"]["schema_version"] in {3, 4}:
                payload["graph_schema_version"] = graph["definition"]["schema_version"]
                if any(node["definition_id"] in {"media_generate", "timeline_export", "image_generate", "image_upscale"} for node in typed_nodes):
                    payload.update(media_execution_contract="creative-graph-media/1", media_previews={}, media_executions={})
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
            if row.get("media_execution_contract"):
                if self.service.media_runtime is None:
                    raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE")
                self.service.media_runtime.output_authority(row)
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
        if row.get("media_execution_contract"):
            if self.service.media_runtime is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE")
            result["media_runtime"] = self.service.media_runtime.public(row, stale=result["stale"])
        guard(); return result

    def _key(self, row, actor, node, inputs):
        return digest([row[BINDING], row["scope"], actor, row["graph_id"], row["graph_version"],
            row["execution_digest"], ADAPTER_VERSION, node["id"], node["definition_id"],
            node["definition_version"], node["parameters"], inputs])

    def _cached(self, row, actor, node_id, key, state):
        if row.get("graph_schema_version") in {3, 4}:
            return None
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
        for _ in range(row["step_limit"] + 1):
            current = host.get_workflow_run(row["id"])
            node_id = current.get("current_node_id")
            if current["status"] != "WAITING_APPROVAL" or node_id is None:
                break
            node = nodes[node_id]
            if node["definition_id"] in {"human_review", "text_generate", "media_generate", "media_review", "timeline_export", "image_generate", "image_upscale"}:
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
                    if node["definition_id"] == "asset_reference" and row.get("graph_schema_version") in {3, 4}:
                        output = self.service.asset_inputs.execute_reference(row["novel_id"], row["scope"], actor, node, guard)
                    elif node["definition_id"] in {"image_reference", "image_prompt", "image_style"} and row.get("graph_schema_version") == 4:
                        from .graph_image_nodes import execute_image_local
                        guard()
                        output = execute_image_local(node, inputs)
                        guard()
                    elif node["definition_id"] in {"director_plan", "storyboard_plan", "storyboard_prompt"} and row.get("graph_schema_version") == 4:
                        from .graph_planning_nodes import execute_planning_local
                        output = execute_planning_local(self.service, row["novel_id"], row["scope"], node, inputs, guard, state)
                    else:
                        receipt = run_trusted_local(self.adapter, AdapterRequest(node["definition_id"],
                            {"parameters": deepcopy(node["parameters"]), "ports": inputs},
                            row["id"] + ":" + node_id, digest([row[BINDING], row["scope"], actor]),
                            timeout_seconds=NODE_TIMEOUT_SECONDS), authorize=guard)
                        output = receipt.output
                output = validate_output_ports(node["definition_id"], output, schema_version=row.get("graph_schema_version"))
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
                "provenance": {"method": "ORIGINAL_ASSET_REFERENCE" if node["definition_id"] == "asset_reference" else "LOCAL_RULES",
                    "adapter": ADAPTER_VERSION, "cache_hit": hit},
                "model_called": False, "applied": False})
        else:
            raise ValueError("CREATIVE_GRAPH_STEP_LIMIT")
        result = deepcopy(host.row)
        result.update(typed_outputs=outputs, cache_keys=cache_keys, cache=cache)
        reviews = [node["id"] for node in row["typed_nodes"] if node["definition_id"] in {"human_review", "media_review"}]
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
        original = self.service._owned(nid, scope, actor, self.service.RUNS, rid)
        phase = (self.service.asset_inputs.transaction(nid, scope, actor, current)
            if original.get("graph_schema_version") in {3, 4} else self.service.store.transaction(nid, scope))
        with phase as state:
            row = self.service._owned(nid, scope, actor, self.service.RUNS, rid, state)
            check_version(row, body.expected_version)
            self._timing(row)
            history_limit = MAX_MEDIA_HISTORY if row.get("graph_schema_version") in {3, 4} else MAX_HISTORY
            if (row.get("model_execution_contract") or row.get("media_execution_contract")) and action not in {"cancel", "reject"} and len(row["history"]) >= history_limit - 2:
                raise ValueError("CREATIVE_MODEL_ACTION_HISTORY_CAPACITY")
            if action in {"pause", "resume"} and row.get("model_execution") and row["node_states"][row["model_execution"]["node_id"]]["status"] == "WORKING":
                raise ValueError("CREATIVE_MODEL_INFLIGHT_PAUSE_UNAVAILABLE")
            if action in {"pause", "resume"} and row.get("media_execution_contract") and any(
                    value["status"] == "WORKING" for value in row["node_states"].values()):
                raise ValueError("CREATIVE_GRAPH_MEDIA_INFLIGHT_PAUSE_UNAVAILABLE")
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
            drive_row = row
            timed = host.get_workflow_run(rid)
            if timed["status"] == "FAILED" and timed.get("error", {}).get("code") == "WORKFLOW_TIMEOUT":
                result = timed
            else:
                if action in {"approve", "reject"}:
                    if action == "approve" and row.get("model_execution_contract"):
                        self.service.model_runtime.output_authority(row)
                    review = self._review(row)
                    if action == "reject" and row.get("media_execution_contract") and row["status"] == "WAITING_APPROVAL":
                        media_node = next((node for node in row["typed_nodes"] if node["id"] == row["current_node_id"]
                            and node["definition_id"] == "media_review"), None)
                        if media_node:
                            candidate = self._inputs(row, media_node["id"], row["typed_outputs"])["candidate"]
                            review = {"node_id": media_node["id"], "output_digest": candidate["asset"]["digest"]}
                    if (not review or body.node_id != review["node_id"]
                            or body.reviewed_output_digest != review["output_digest"]):
                        raise StaleSourceError("CREATIVE_GRAPH_EXACT_REVIEW_REQUIRED")
                    if action == "approve":
                        host.approve_workflow_node(rid, body.node_id, actor, body.note)
                        if row.get("graph_schema_version") == 3:
                            # The existing manual-approval owner has completed
                            # this exact node. Add typed projection to that same
                            # original state; no separate approval is created.
                            output = validate_output_ports("human_review",
                                {"reviewed_draft": review["draft"]}, schema_version=3)
                            states = deepcopy(host.row["node_states"])
                            states[body.node_id]["output"]["result"] = {"ports": deepcopy(output),
                                "provenance": {"method": "ORIGINAL_HUMAN_REVIEW", "review_node_id": body.node_id,
                                    "reviewed_output_digest": review["output_digest"]}, "model_called": False, "applied": False}
                            host._update("workflow_runs", rid, {"node_states": states}, novel_id=nid,
                                expected_version=host.row["version"], action="CREATIVE_GRAPH_REVIEWED_DRAFT_RECORDED",
                                target_type="WorkflowRun")
                            host.row["typed_outputs"][body.node_id] = output
                            node = next(node for node in row["typed_nodes"] if node["id"] == body.node_id)
                            ports = self._inputs(row, body.node_id, row["typed_outputs"])
                            host.row["cache_keys"][body.node_id] = {"key": self._key(row, actor, node, ports),
                                "output_digest": digest(output), "cacheable": False}
                            drive_row = host.row
                    else:
                        host.reject_workflow_node(rid, body.node_id, actor, body.note)
                elif action == "execute":
                    host._advance_workflow_run(rid)
                else:
                    host.set_workflow_run_state(rid, action)
                result = self._drive(host, drive_row, actor, state, fresh) if action in {"execute", "approve", "resume"} else deepcopy(host.row)
            payload = {key: item for key, item in result.items() if key not in {"history", "version"}}
            payload.update(trace=row["trace"] + host.transitions, dispatch_trace=row["dispatch_trace"] + host.dispatches)
            change_row(row, actor, body.expected_version, lambda item: item.update(payload))
            self.service._capacity(state); fresh()
            return self.view(nid, scope, actor, row, current, state)
