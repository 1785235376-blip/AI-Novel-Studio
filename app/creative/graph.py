"""Actor-private typed drafts over the existing incarnation-fenced scope owner.

Schemas 1 and 2 retain their nonexecuting asset reference contract. Schema 3
uses an explicit original scope -> asset -> project phase for atomic inputs.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import hashlib

from ..experimental.common import StaleSourceError, change_row, check_version, new_row
from ..experimental.store import canonical
from ..services.v1_capability_service import V1CapabilityService
from .project_store import CreativeProjectStore, BINDING
from .graph_models import (
    DEFINITIONS, GraphInput, GraphCreate, GraphSave, GraphPreflight, GraphRunCreate,
    MAX_NODES, MAX_EDGES, MAX_DEFINITION_BYTES, MAX_OUTPUT_BYTES, MAX_GRAPHS,
    MAX_RUNS, MAX_HISTORY, MAX_RECORD_BYTES, MAX_SCOPE_BYTES, catalog_definitions, parse_graph,
    RUN_TIMEOUT_SECONDS, NODE_TIMEOUT_SECONDS,
    MAX_MEDIA_NODES, MAX_MEDIA_GENERATORS, MAX_MEDIA_HISTORY, history_limit,
)

GRAPHS = "creative_graph_definitions_v2"
RUNS = "creative_graph_runs_v2"


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def execution_definition(value):
    return {"schema_version": value["schema_version"],
        "nodes": [{key: deepcopy(item[key]) for key in ("id", "definition_id", "definition_version", "enabled", "parameters")}
                  for item in value["nodes"]], "edges": deepcopy(value["edges"])}


class CreativeGraphService:
    GRAPHS = GRAPHS
    RUNS = RUNS

    def __init__(self, store, workspace):
        self.store = store if isinstance(store, CreativeProjectStore) else CreativeProjectStore(store)
        self.workspace = workspace
        from .graph_execution import CreativeGraphExecutor
        self.executor = CreativeGraphExecutor(self)
        self.model_runtime = None
        self.media_runtime = None
        from .graph_asset_inputs import GraphAssetInputs
        self.asset_inputs = GraphAssetInputs(self)

    def configure_models(self, broker, manager):
        from .ai_execution import CreativeGraphNodeRuntime
        self.model_runtime = CreativeGraphNodeRuntime(self, broker, manager)

    def configure_media(self, production):
        from .graph_media_execution import CreativeGraphMediaRuntime
        self.media_runtime = CreativeGraphMediaRuntime(self, production)

    @staticmethod
    def _model_authority(definition):
        if (definition.get("schema_version") == 2
                or any(node["definition_id"] == "text_generate" or
                    (node["definition_id"] == "media_generate" and node["parameters"]["operation_id"] != "m8.audio.trim")
                    for node in definition["nodes"])):
            from .ai_execution import require_execution
            require_execution()

    def _context(self, nid, scope, actor, guard):
        self.store.key(nid, scope)
        if not isinstance(actor, str) or not 1 <= len(actor) <= 240:
            raise ValueError("CREATIVE_GRAPH_ACTOR_REQUIRED")
        self.workspace.novels.get(nid)
        guard()
        incarnation = self.store.incarnation(nid)
        captured_scope = deepcopy(scope)
        def current():
            guard()
            self.workspace.novels.get(nid)
            if scope != captured_scope or self.store.incarnation(nid) != incarnation:
                raise StaleSourceError("CREATIVE_GRAPH_AUTHORITY_CHANGED")
        current()
        return incarnation, current

    def _owned(self, nid, scope, actor, name, rid, state=None):
        document = self.store.read(nid, scope) if state is None else state
        row = document["collections"].get(name, {}).get(rid)
        if (not isinstance(row, dict) or row.get("novel_id") != nid or row.get("scope") != scope
                or row.get("created_by") != actor or row.get(BINDING) != self.store.incarnation(nid)):
            raise FileNotFoundError(rid)
        if type(row.get("version")) is not int or row["version"] < 1 or not isinstance(row.get("history"), list):
            raise ValueError("CREATIVE_GRAPH_RECORD_CORRUPT")
        if name == GRAPHS:
            value = parse_graph(row.get("definition")).model_dump()
            self._model_authority(value)
            if (value != row["definition"] or digest(value) != row.get("definition_digest")
                    or digest(execution_definition(value)) != row.get("execution_digest")):
                raise ValueError("CREATIVE_GRAPH_RECORD_CORRUPT")
        if name == RUNS and any(node.get("definition_id") == "text_generate" or
                (node.get("definition_id") == "media_generate" and node.get("parameters", {}).get("operation_id") != "m8.audio.trim")
                for node in row.get("typed_nodes", [])):
            from .ai_execution import require_execution
            require_execution()
        return row

    @staticmethod
    def _capacity(state):
        collections = {name: state["collections"].get(name, {}) for name in (GRAPHS, RUNS)}
        if len(collections[GRAPHS]) > MAX_GRAPHS or len(collections[RUNS]) > MAX_RUNS:
            raise ValueError("CREATIVE_GRAPH_COLLECTION_CAPACITY")
        for rows in collections.values():
            for row in rows.values():
                if len(row.get("history", [])) > history_limit(row) or len(canonical(row).encode()) > MAX_RECORD_BYTES:
                    raise ValueError("CREATIVE_GRAPH_HISTORY_CAPACITY")
        if len(canonical(collections).encode()) > MAX_SCOPE_BYTES:
            raise ValueError("CREATIVE_GRAPH_SCOPE_CAPACITY")

    @staticmethod
    def _asset_bindings(definition):
        return {node["id"]: deepcopy(node["parameters"]) for node in definition["nodes"]
                if node["definition_id"] == "asset_reference"}

    def _reference_states(self, nid, scope, definition, guard, actor=None):
        """Legacy reads stay outside transactions; schema 3 uses its asset phase."""
        if definition.get("schema_version") == 3:
            if not isinstance(actor, str):
                raise ValueError("CREATIVE_GRAPH_ACTOR_REQUIRED")
            return self.asset_inputs.states(nid, scope, actor, definition, guard)
        if self.store.key(nid, scope) in getattr(self.store._local, "active", {}):
            raise ValueError("CREATIVE_GRAPH_ASSET_READ_INSIDE_SCOPE_DENIED")
        result = []
        bindings = self._asset_bindings(definition)
        if not bindings:
            return result
        guard()
        with self.workspace._asset_scope(nid, scope):
            for node_id, expected in bindings.items():
                guard()
                try:
                    row = self.workspace._row(nid, scope, expected["asset_id"], deleted=True)
                    if row.get("deleted_at"):
                        state = "UNAVAILABLE"
                    else:
                        state = "CURRENT" if (row["version"] == expected["version"]
                            and row["sha256"] == expected["digest"] and row["kind"] == expected["kind"]) else "STALE"
                except (FileNotFoundError, ValueError, KeyError):
                    state = "UNAVAILABLE"
                result.append({"node_id": node_id, "state": state})
            guard()
        guard()
        return result

    def _view(self, nid, scope, row, guard):
        public = {key: deepcopy(row[key]) for key in ("id", "version", "definition", "definition_digest",
                  "execution_digest", "created_at", "updated_at")}
        states = self._reference_states(nid, scope, row["definition"], guard, row["created_by"])
        denied = {item["node_id"] for item in states if item["state"] == "UNAVAILABLE"}
        for node in public["definition"]["nodes"]:
            if node["id"] in denied:
                node["parameters"] = {}
        public.update(can_edit=not denied, reference_states=states)
        public.update(project_id=nid, scope=deepcopy(scope))
        guard()
        return public

    def catalog(self, nid, scope, actor, guard=lambda: None):
        _, current = self._context(nid, scope, actor, guard)
        from .ai_execution import execution_enabled, CONTRACT
        models = self.model_runtime is not None and execution_enabled()
        media = self.media_runtime is not None
        result = {"definitions": catalog_definitions(include_model=models, include_media=media), "limits": {"nodes": MAX_NODES, "edges": MAX_EDGES,
            "definition_bytes": MAX_DEFINITION_BYTES, "output_bytes": MAX_OUTPUT_BYTES,
            "graphs": MAX_GRAPHS, "runs": MAX_RUNS, "history": MAX_HISTORY,
            "runtime_timeout_seconds": RUN_TIMEOUT_SECONDS, "node_timeout_seconds": NODE_TIMEOUT_SECONDS},
            "capabilities": {"local_execution": True, "chapter_required": False, "model_execution": False,
                "external_reference_execution": False, "external_reference_detach": False,
                "binary_cache": False, "parallel_execution": False, "automatic_retry": False,
                "actor_private": True, "cache_mode": "SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY"}}
        if models:
            result["capabilities"].update(model_execution=True, model_execution_contract=CONTRACT)
        if media:
            from .graph_media_execution import CONTRACT as MEDIA_CONTRACT
            result["media_limits"] = {"nodes": MAX_MEDIA_NODES, "generators": MAX_MEDIA_GENERATORS, "history": MAX_MEDIA_HISTORY}
            result["capabilities"].update(media_execution=True, media_execution_contract=MEDIA_CONTRACT,
                external_reference_execution=True, media_evidence="LOCAL_REQUIRED",
                media_cache=False, media_parallel_execution=False, automatic_media_dispatch=False)
        current(); return result

    @contextmanager
    def _definition_transaction(self, nid, scope, actor, definition, guard):
        if definition.get("schema_version") == 3:
            with self.asset_inputs.transaction(nid, scope, actor, guard) as state:
                yield state
        else:
            with self.store.transaction(nid, scope) as state:
                yield state

    def list(self, nid, scope, actor, guard=lambda: None):
        _, current = self._context(nid, scope, actor, guard)
        state = self.store.read(nid, scope)
        result = []
        for rid, row in state["collections"].get(GRAPHS, {}).items():
            if isinstance(row, dict) and row.get("created_by") == actor:
                result.append(self._view(nid, scope, self._owned(nid, scope, actor, GRAPHS, rid, state), current))
        current(); return {"items": sorted(result, key=lambda row: (row["created_at"], row["id"]))}

    def get(self, nid, scope, actor, rid, guard=lambda: None):
        _, current = self._context(nid, scope, actor, guard)
        result = self._view(nid, scope, self._owned(nid, scope, actor, GRAPHS, rid), current)
        current(); return result

    def create(self, nid, scope, actor, value, guard=lambda: None):
        body = GraphCreate.model_validate(value)
        incarnation, current = self._context(nid, scope, actor, guard)
        definition = body.definition.model_dump()
        self._model_authority(definition)
        if any(row["state"] != "CURRENT" for row in self._reference_states(nid, scope, definition, current, actor)):
            raise StaleSourceError("CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED")
        request_digest = digest(body.model_dump())
        with self._definition_transaction(nid, scope, actor, definition, current) as state:
            current()
            if definition.get("schema_version") == 3 and any(
                    row["state"] != "CURRENT" for row in self.asset_inputs.states(nid, scope, actor, definition, current)):
                raise StaleSourceError("CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED")
            rows = state["collections"].setdefault(GRAPHS, {})
            found = next((row for row in rows.values() if row.get("created_by") == actor and row.get("request_id") == body.request_id), None)
            if found:
                if found.get("request_digest") != request_digest:
                    raise ValueError("CREATIVE_GRAPH_REQUEST_ID_REUSED")
                row = self._owned(nid, scope, actor, GRAPHS, found["id"], state)
            else:
                row = new_row(nid, scope, actor, {BINDING: incarnation, "definition": definition,
                    "definition_digest": digest(definition), "execution_digest": digest(execution_definition(definition)),
                    "request_id": body.request_id, "request_digest": request_digest})
                rows[row["id"]] = row
            self._capacity(state); current(); saved = deepcopy(row)
        return self._view(nid, scope, saved, current)

    def save(self, nid, scope, actor, rid, value, guard=lambda: None):
        body = GraphSave.model_validate(value)
        _, current = self._context(nid, scope, actor, guard)
        old = self._owned(nid, scope, actor, GRAPHS, rid)
        check_version(old, body.expected_version)
        if any(row["state"] == "UNAVAILABLE" for row in self._reference_states(nid, scope, old["definition"], current, actor)):
            raise ValueError("CREATIVE_GRAPH_EXTERNAL_BINDING_READ_ONLY")
        definition = body.definition.model_dump()
        self._model_authority(definition)
        previous, replacement = self._asset_bindings(old["definition"]), self._asset_bindings(definition)
        if any(replacement.get(node_id) != binding for node_id, binding in previous.items()):
            raise ValueError("CREATIVE_GRAPH_EXTERNAL_DETACH_UNAVAILABLE")
        added = {node_id for node_id in replacement if node_id not in previous}
        states = self._reference_states(nid, scope, definition, current, actor)
        if any(item["node_id"] in added and item["state"] != "CURRENT" for item in states):
            raise StaleSourceError("CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED")
        with self._definition_transaction(nid, scope, actor, definition, current) as state:
            row = self._owned(nid, scope, actor, GRAPHS, rid, state)
            check_version(row, body.expected_version); current()
            if definition.get("schema_version") == 3 and any(
                    item["node_id"] in added and item["state"] != "CURRENT"
                    for item in self.asset_inputs.states(nid, scope, actor, definition, current)):
                raise StaleSourceError("CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED")
            change_row(row, actor, body.expected_version, lambda item: item.update(definition=definition,
                definition_digest=digest(definition), execution_digest=digest(execution_definition(definition))))
            self._capacity(state); current(); saved = deepcopy(row)
        return self._view(nid, scope, saved, current)

    def _preflight(self, row, body, actor, *, check_assets=True):
        definition = row["definition"]
        nodes = {node["id"]: node for node in definition["nodes"]}
        targets = body.target_node_ids or [node["id"] for node in definition["nodes"] if node["enabled"]]
        if len(set(targets)) != len(targets) or any(target not in nodes for target in targets):
            raise ValueError("CREATIVE_GRAPH_TARGET_INVALID")
        incoming = {key: [] for key in nodes}
        for edge in definition["edges"]:
            incoming[edge["target_node_id"]].append(edge)
        closure = set(targets)
        queue = list(targets)
        while queue:
            for edge in incoming[queue.pop()]:
                if edge["source_node_id"] not in closure:
                    closure.add(edge["source_node_id"]); queue.append(edge["source_node_id"])
        issues = []
        if not closure:
            issues.append({"code": "CREATIVE_GRAPH_EMPTY_SELECTION"})
        order = V1CapabilityService._workflow_order([{"id": node["id"]} for node in definition["nodes"]],
            [{"source": edge["source_node_id"], "target": edge["target_node_id"]} for edge in definition["edges"]])
        order = [node_id for node_id in order if node_id in closure]
        for node_id in order:
            node = nodes[node_id]
            if not node["enabled"]:
                issues.append({"code": "CREATIVE_GRAPH_DISABLED_DEPENDENCY", "node_id": node_id})
            if node["definition_id"] == "asset_reference" and definition["schema_version"] != 3:
                issues.append({"code": "CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED", "node_id": node_id})
            for port in DEFINITIONS[node["definition_id"]]["inputs"]:
                if port["required"] and not any(edge["target_port"] == port["id"] for edge in incoming[node_id]):
                    issues.append({"code": "CREATIVE_GRAPH_REQUIRED_INPUT_MISSING", "node_id": node_id})
            if node["definition_id"] in {"text_input", "manual_transform"}:
                key = "text" if node["definition_id"] == "text_input" else "result"
                if not node["parameters"][key].strip():
                    issues.append({"code": "CREATIVE_GRAPH_TEXT_REQUIRED", "node_id": node_id})
        models = [key for key in order if nodes[key]["definition_id"] == "text_generate"]
        if models:
            self._model_authority(definition)
            if self.model_runtime is None:
                issues.append({"code": "CREATIVE_MODEL_RUNTIME_UNAVAILABLE"})
            if len(models) != 1:
                issues.append({"code": "CREATIVE_MODEL_SINGLE_NODE_REQUIRED"})
            for model in models:
                downstream = [edge for edge in definition["edges"] if edge["source_node_id"] == model]
                if not downstream or any(edge["target_node_id"] not in closure or
                        nodes[edge["target_node_id"]]["definition_id"] != "human_review" for edge in downstream):
                    issues.append({"code": "CREATIVE_MODEL_HUMAN_REVIEW_REQUIRED", "node_id": model})
        reference_states = []
        if definition["schema_version"] == 3:
            selected_definition = {"nodes": [nodes[key] for key in order]}
            if check_assets:
                reference_states = self.asset_inputs.states(row["novel_id"], row["scope"], actor,
                    selected_definition, lambda: None)
            for item in reference_states:
                if item["state"] != "CURRENT":
                    issues.append({"code": "CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED", "node_id": item["node_id"]})
            generators = [key for key in order if nodes[key]["definition_id"] == "media_generate"]
            reviews = [key for key in order if nodes[key]["definition_id"] == "media_review"]
            if generators and self.media_runtime is None:
                issues.append({"code": "CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE"})
            if len(generators) > MAX_MEDIA_GENERATORS:
                issues.append({"code": "CREATIVE_GRAPH_MEDIA_NODE_CAPACITY"})
            for generator in generators:
                node = nodes[generator]
                operation = node["parameters"]["operation_id"]
                outgoing = [edge for edge in definition["edges"] if edge["source_node_id"] == generator]
                if (len(outgoing) != 1 or outgoing[0]["target_node_id"] not in closure
                        or nodes[outgoing[0]["target_node_id"]]["definition_id"] != "media_review"):
                    issues.append({"code": "CREATIVE_GRAPH_MEDIA_REVIEW_REQUIRED", "node_id": generator})
                source = next((edge for edge in incoming[generator] if edge["target_port"] == "source"), None)
                text = next((edge for edge in incoming[generator] if edge["target_port"] == "text"), None)
                draft = next((edge for edge in incoming[generator] if edge["target_port"] == "draft"), None)
                if text is not None and draft is not None:
                    issues.append({"code": "CREATIVE_GRAPH_MEDIA_TEXT_DRAFT_EXCLUSIVE", "node_id": generator})
                if draft is not None:
                    reviewer = nodes[draft["source_node_id"]]
                    original = next((edge for edge in incoming[reviewer["id"]] if edge["target_port"] == "draft"), None)
                    if (reviewer["definition_id"] != "human_review" or draft["source_port"] != "reviewed_draft"
                            or original is None or original["source_port"] != "draft"
                            or nodes[original["source_node_id"]]["definition_id"] != "text_generate"):
                        issues.append({"code": "CREATIVE_GRAPH_MEDIA_APPROVED_MODEL_DRAFT_REQUIRED", "node_id": generator})
                required_kind = {"m5.image.i2i": "image", "m7.video.i2v": "image",
                    "m7.video.v2v": "video", "m8.audio.trim": "audio"}.get(operation)
                if required_kind and source is None:
                    issues.append({"code": "CREATIVE_GRAPH_MEDIA_SOURCE_REQUIRED", "node_id": generator})
                if source is not None:
                    source_node = nodes[source["source_node_id"]]
                    source_kind = source_node["parameters"]["kind"] if source_node["definition_id"] == "asset_reference" else None
                    if source_node["definition_id"] == "media_review":
                        parent = next((edge for edge in incoming[source_node["id"]] if edge["target_port"] == "candidate"), None)
                        if parent is not None:
                            parent_node = nodes[parent["source_node_id"]]
                            if parent_node["definition_id"] == "media_generate":
                                parent_operation = parent_node["parameters"]["operation_id"]
                                source_kind = "image" if parent_operation.startswith("m5.") else "video" if parent_operation.startswith("m7.") else "audio"
                    if required_kind is None or source_kind != required_kind:
                        issues.append({"code": "CREATIVE_GRAPH_MEDIA_SOURCE_KIND_INVALID", "node_id": generator})
                if operation == "m8.audio.trim":
                    if text is not None or draft is not None:
                        issues.append({"code": "STUDIO_AUDIO_TRIM_LOCAL_ONLY", "node_id": generator})
                elif not node["parameters"]["prompt"].strip() and text is None and draft is None:
                    issues.append({"code": "CREATIVE_GRAPH_MEDIA_PROMPT_REQUIRED", "node_id": generator})
            for review in reviews:
                sources = [edge for edge in incoming[review] if edge["target_port"] == "candidate"]
                if len(sources) != 1 or sources[0]["source_node_id"] not in generators:
                    issues.append({"code": "CREATIVE_GRAPH_MEDIA_REVIEW_BINDING_INVALID", "node_id": review})
        result = {"project_id": row["novel_id"], "scope": deepcopy(row["scope"]), "graph_id": row["id"],
            "valid": True, "executable": not issues, "issues": issues, "execution_order": order,
            "selected_closure": order, "definition_digest": row["definition_digest"],
            "expected_version": row["version"], "target_node_ids": list(targets),
            "model_called": False, "external_calls": 0}
        if definition["schema_version"] == 3:
            result.update(graph_schema_version=3, reference_states=reference_states,
                media_execution="EXPLICIT_PREVIEW_DISPATCH_REVIEW", media_evidence="LOCAL_REQUIRED")
            if not check_assets:
                result["source_check"] = "DEFERRED_TO_LEASED_OWNER"
        result["preflight_digest"] = digest([row["id"], row[BINDING], row["scope"], actor, result])
        return result

    def preflight(self, nid, scope, actor, rid, value, guard=lambda: None):
        body = GraphPreflight.model_validate(value)
        _, current = self._context(nid, scope, actor, guard)
        row = self._owned(nid, scope, actor, GRAPHS, rid)
        check_version(row, body.expected_version)
        if row["definition"]["schema_version"] == 3:
            with self.asset_inputs.phase(nid, scope, actor, current) as state:
                row = self._owned(nid, scope, actor, GRAPHS, rid, state)
                check_version(row, body.expected_version)
                result = self._preflight(row, body, actor)
        else:
            result = self._preflight(row, body, actor)
        current(); return result

    def create_run(self, nid, scope, actor, rid, value, guard=lambda: None):
        return self.executor.create(nid, scope, actor, rid, GraphRunCreate.model_validate(value), guard)

    def runs(self, nid, scope, actor, rid, guard=lambda: None):
        _, current = self._context(nid, scope, actor, guard)
        self._owned(nid, scope, actor, GRAPHS, rid)
        state = self.store.read(nid, scope)
        rows = [row for row in state["collections"].get(RUNS, {}).values()
                if row.get("created_by") == actor and row.get("graph_id") == rid]
        result = {"items": [self.get_run(nid, scope, actor, row["id"], current, reconcile=False)
            if (self.model_runtime and self.model_runtime.text_assets.enabled(row))
                or (row.get("graph_schema_version") == 3 and row.get("media_execution_contract"))
            else self.executor.view(nid, scope, actor, row, current, state) for row in rows]}
        current(); return result

    def get_run(self, nid, scope, actor, rid, guard=lambda: None, *, reconcile=True):
        _, current = self._context(nid, scope, actor, guard)
        row = self._owned(nid, scope, actor, RUNS, rid)
        archival = self.model_runtime is not None and self.model_runtime.text_assets.enabled(row)
        if archival:
            result = self.model_runtime.text_assets.read(nid, scope, actor, rid, current, reconcile=reconcile)
            if (result["stale"] or result["status"] in {"FAILED", "CANCELLED", "REJECTED"}
                    or row.get("graph_schema_version") != 3 or not row.get("media_execution_contract")):
                return result
            if self.media_runtime is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE")
            # Text convergence/decision projection is complete before original
            # media queues are read outside leases. The same run version must
            # still own both projections; stale text cannot become media success.
            media = self.media_runtime.read(nid, scope, actor, rid, current, expected_version=result["version"])
            if media["stale"]:
                return self.model_runtime.text_assets.masked(media)
            if "asset_output" not in media:
                media["asset_output"] = deepcopy(result["asset_output"])
            return media
        if row.get("graph_schema_version") == 3 and row.get("media_execution_contract"):
            if self.media_runtime is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE")
            return self.media_runtime.read(nid, scope, actor, rid, current)
        result = self.executor.view(nid, scope, actor, row, current)
        current(); return result

    def action(self, nid, scope, actor, rid, action, value, guard=lambda: None):
        row = self._owned(nid, scope, actor, RUNS, rid)
        archival = self.model_runtime is not None and self.model_runtime.text_assets.enabled(row)
        if archival and action in {"approve", "reject"}:
            with self.model_runtime.text_assets.phase(nid, scope, actor, rid, guard, create=False):
                result = self.executor.action(nid, scope, actor, rid, action, value, guard)
            result = self.model_runtime.text_assets.decorate(nid, scope, actor, rid, guard, result)
        else:
            result = self.executor.action(nid, scope, actor, rid, action, value, guard)
        if action == "cancel" and self.model_runtime is not None:
            # Cancel the original worker only after the durable workflow fence.
            self.model_runtime.cancel(self._owned(nid, scope, actor, RUNS, rid))
        if action in {"cancel", "reject"} and row.get("graph_schema_version") == 3 and row.get("media_execution_contract"):
            if self.media_runtime is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE")
            # The workflow cancellation is durable before discarding its
            # original provider candidates. No remote abort/resubmit is implied.
            self.media_runtime.cancel(nid, scope, actor, self._owned(nid, scope, actor, RUNS, rid), guard)
            return self.get_run(nid, scope, actor, rid, guard, reconcile=False)
        if archival and action == "cancel":
            result["asset_output"] = self.model_runtime.text_assets.pending("NO_ACCEPTED_RESULT")
        if (archival and row.get("graph_schema_version") == 3 and row.get("media_execution_contract")
                and action == "approve" and not result["stale"] and result["status"] not in {"FAILED", "CANCELLED", "REJECTED"}):
            if self.media_runtime is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE")
            projected = self.media_runtime.read(nid, scope, actor, rid, guard, expected_version=result["version"])
            return self.model_runtime.text_assets.masked(projected) if projected["stale"] else projected
        return result
