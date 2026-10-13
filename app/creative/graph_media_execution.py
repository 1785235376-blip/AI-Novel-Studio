"""Explicit Graph media composition over WorkflowRun and original job owners.

No queue, worker, transport or credential owner lives here. Original runs first
reserve exact requests; uncertain replies are looked up without admission/send
replay. Only media_review promotes a candidate and emits a usable ASSET_REF.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import hashlib

from pydantic import Field

from ..experimental.common import StaleSourceError, change_row, check_version
from ..experimental.declarative_agents import _ScopedOriginalWorkflowHost
from .graph_execution import ADAPTER_VERSION, digest
from .graph_models import (Digest, Id, Strict, history_limit, validate_output_ports,
    MAX_NODES, MAX_RECORD_BYTES, MAX_SCOPE_BYTES, MAX_OUTPUT_BYTES, parse_graph)
from .graph_media_binding import make_graph_binding_digest
from .production_execution_models import MediaCommand, MediaCreate, MediaJobAction, MediaReview
from .graph_timeline_execution import GraphTimelineCommand
from .project_store import BINDING

CONTRACT = "creative-graph-media/1"
UNKNOWN = "UNKNOWN_NO_AUTOMATIC_REPLAY"
TERMINAL_RUNS = {"FAILED", "CANCELLED", "REJECTED"}
RECEIPT_FIELDS = ("id", "version", "status", "request_digest", "receipt_digest", "output_candidate",
    "approved_asset_version", "error_code", "needs_reconciliation", "execution_state",
    "cancellation_mode", "remote_compute_may_continue")
OWNER_STATUSES = {"QUEUED", "RUNNING", "SEND_RESERVED", "REMOTE_RUNNING", "RESULT_READY",
    "UNKNOWN", "AWAITING_REVIEW", "SUCCEEDED", "REVIEWING", "APPROVED", "FAILED", "CANCELLED"}
EXECUTION_STATUSES = OWNER_STATUSES | {"ADMISSION_RESERVED", "ADMISSION_UNKNOWN", "JOB_NOT_FOUND"}


class MediaNodeRequest(Strict):
    expected_version: int = Field(ge=1)
    node_id: Id


class MediaDispatch(MediaNodeRequest):
    reviewed_preview_digest: Digest


class MediaJobRequest(MediaNodeRequest):
    expected_job_version: int = Field(ge=1)
    expected_request_digest: Digest


class MediaGraphReview(MediaJobRequest):
    reviewed_output_digest: Digest


class CreativeGraphMediaRuntime:
    """All durable previews, claims and receipts belong to original graph runs."""

    def __init__(self, service, production):
        self.service, self.production = service, production

    @staticmethod
    def nodes(row):
        return {node["id"]: node for node in row["typed_nodes"] if node["definition_id"] in {"media_generate", "timeline_export"}}

    def _node(self, row, node_id):
        node = self.nodes(row).get(node_id)
        if node is None or row.get("media_execution_contract") != CONTRACT:
            raise ValueError("CREATIVE_GRAPH_MEDIA_NODE_REQUIRED")
        return node

    def _row(self, nid, scope, actor, rid, guard, state=None):
        guard()
        row = self.service._owned(nid, scope, actor, self.service.RUNS, rid, state)
        if row.get("media_execution_contract") != CONTRACT:
            raise ValueError("CREATIVE_GRAPH_MEDIA_CONTRACT_REQUIRED")
        self.service.executor._current(nid, scope, actor, row, guard, state)
        return row

    def _text_assets(self, row):
        runtime = self.service.model_runtime
        return runtime.text_assets if runtime and runtime.text_assets.enabled(row) else None

    @contextmanager
    def _phase(self, nid, scope, actor, rid, guard, *, writable=False, expected_version=None):
        """Prepare text routes outside leases; share original leased proofs.

        Original owner queue reads stay outside this context. It never creates
        or reviews text assets: archival convergence belongs to GraphTextAssets.
        """
        captured = self.service._owned(nid, scope, actor, self.service.RUNS, rid)
        if expected_version is not None:
            check_version(captured, expected_version)
        archival = self._text_assets(captured)
        prepared = (archival.prepare_projection(captured, guard)
            if archival and captured["status"] not in TERMINAL_RUNS else None)
        phase = (self.service.asset_inputs.transaction(nid, scope, actor, guard)
            if writable else self.service.asset_inputs.phase(nid, scope, actor, guard))
        with phase as state:
            current = self.service._owned(nid, scope, actor, self.service.RUNS, rid, state)
            check_version(current, captured["version"])
            projection = (archival.projection(nid, scope, actor, rid, guard, prepared)
                if archival and prepared is not None else nullcontext())
            with projection:
                yield state

    def _view(self, nid, scope, actor, row, guard, state):
        result = self.service.executor.view(nid, scope, actor, row, guard, state)
        archival = self._text_assets(row)
        if archival and not result["stale"] and row["node_states"][archival.runtime.node(row)["id"]]["status"] == "SUCCEEDED":
            try:
                result["asset_output"] = archival.public_current(row)
            except (StaleSourceError, FileNotFoundError):
                return archival.masked(result)
        return result

    @staticmethod
    def _deadline(row):
        from .graph_execution import CreativeGraphExecutor
        if datetime.now(timezone.utc) >= datetime.fromisoformat(CreativeGraphExecutor._timing(row)):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_WORKFLOW_DEADLINE_EXCEEDED")

    @staticmethod
    def _capacity(row, reserve=3):
        if len(row["history"]) >= history_limit(row) - reserve:
            raise ValueError("CREATIVE_GRAPH_MEDIA_HISTORY_CAPACITY")

    def _admission_capacity(self, state, row, updates=6):
        """Reserve byte headroom before original admission/send/promotion.

        This is only a bound calculation, not a fabricated output or reservation
        ledger. Every actual commit remains checked by the original scope owner.
        Later independent edits can still invalidate admission; publication then
        fails closed under the same raw source lease.
        """
        from ..experimental.store import canonical
        snapshot = {key: value for key, value in row.items() if key != "history"}
        # Original WorkflowRun limits a whole node-state update to 256000 bytes.
        # Bound only still-pending local outputs; modality references/receipts and
        # original transition traces receive an additional finite 16 KiB margin.
        pending_local = sum(MAX_OUTPUT_BYTES for node in row["typed_nodes"]
            if node["definition_id"] not in {"media_generate", "media_review", "timeline_export"}
            and row["node_states"][node["id"]]["status"] != "SUCCEEDED")
        future = min(256000, pending_local) + 16384
        addition = updates * (len(canonical(snapshot).encode("utf-8")) + future)
        current_size = len(canonical(row).encode("utf-8"))
        collections = {name: state["collections"].get(name, {}) for name in (self.service.GRAPHS, self.service.RUNS)}
        if current_size + addition > MAX_RECORD_BYTES or len(canonical(collections).encode("utf-8")) + addition > MAX_SCOPE_BYTES:
            raise ValueError("CREATIVE_GRAPH_MEDIA_RECEIPT_BYTE_HEADROOM_REQUIRED")

    def _inputs(self, row, node):
        ports = self.service.executor._inputs(row, node["id"], row["typed_outputs"])
        command = deepcopy(node["parameters"])
        if node["definition_id"] == "timeline_export":
            expected = {binding["port"] for binding in command["source_bindings"]}
            if set(ports) != expected:
                raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_RESOLVED_INPUT_REQUIRED")
            command["source_bindings"] = [{**binding, "asset": deepcopy(ports[binding["port"]])}
                for binding in command["source_bindings"]]
            command.update(operation_id="m9.timeline.multitrack", request_id="graph-media-" + digest([
                CONTRACT, row[BINDING], row["scope"], row["created_by"], row["id"], row["graph_id"],
                row["graph_version"], row["request_digest"], node["id"]]))
            body = GraphTimelineCommand.model_validate(command)
            return ports, body, digest([row[BINDING], row["scope"], row["created_by"], row["graph_digest"], node, ports])
        if "text" in ports and "draft" in ports:
            raise ValueError("CREATIVE_GRAPH_MEDIA_TEXT_DRAFT_EXCLUSIVE")
        text = ports.get("text", "")
        if text:
            command["prompt"] = command.get("prompt", "") + ("\n\n" if command.get("prompt") else "") + "GRAPH_SOURCE_TEXT\n" + text
        if "draft" in ports:
            draft = ports["draft"]
            edge = next((edge for edge in row["typed_edges"]
                if edge["target_node_id"] == node["id"] and edge["target_port"] == "draft"), None)
            reviewer = next((source for source in row["typed_nodes"]
                if edge and source["id"] == edge["source_node_id"]), None)
            original = next((source for source in row["typed_edges"] if reviewer
                and source["target_node_id"] == reviewer["id"] and source["target_port"] == "draft"), None)
            archival = self._text_assets(row)
            if (row.get("graph_schema_version") != 3 or not archival or not reviewer or not original
                    or reviewer["definition_id"] != "human_review" or edge["source_port"] != "reviewed_draft"
                    or row["node_states"][reviewer["id"]]["status"] != "SUCCEEDED"
                    or reviewer["id"] not in row.get("reviewed_nodes", [])
                    or original["source_node_id"] != archival.runtime.node(row)["id"] or original["source_port"] != "draft"
                    or draft != row["typed_outputs"].get(reviewer["id"], {}).get("reviewed_draft")
                    or draft != row["typed_outputs"].get(original["source_node_id"], {}).get("draft")
                    or archival._decision(row, hashlib.sha256(draft["text"].encode()).hexdigest())[0] != "APPROVED"):
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_APPROVED_MODEL_DRAFT_REQUIRED")
            # Metadata checks here are pure: _current calls this before proof
            # establishment. Every write/send/publication/promotion additionally
            # verifies the same APPROVED private archive and original bytes in
            # its source/asset phase; a node status alone grants no authority.
            command["prompt"] = command.get("prompt", "") + ("\n\n" if command.get("prompt") else "") + "GRAPH_SOURCE_DRAFT\n" + draft["text"]
        sources = []
        if "source" in ports:
            asset = ports["source"]
            sources.append({"kind": "ASSET", "id": asset["asset_id"], "version": asset["version"],
                "digest": asset["digest"], "asset_kind": asset["kind"]})
        command.update(request_id="graph-media-" + digest([CONTRACT, row[BINDING], row["scope"], row["created_by"],
            row["id"], row["graph_id"], row["graph_version"], row["request_digest"], node["id"]]), source_snapshots=sources)
        body = MediaCommand.model_validate(command)
        return ports, body, digest([row[BINDING], row["scope"], row["created_by"], row["graph_digest"], node, ports])

    def _binding(self, row, node, command, input_digest, run_version):
        context = {"actor": row["created_by"], "scope_key": self.service.store.key(row["novel_id"], row["scope"]),
            "incarnation": row[BINDING]}
        binding = {"contract": "creative-graph-media-binding/1", "run_id": row["id"], "node_id": node["id"],
            "graph_id": row["graph_id"], "graph_version": row["graph_version"], "graph_digest": row["graph_digest"],
            "run_request_digest": row["request_digest"], "input_digest": input_digest,
            "preview_run_version": run_version, "command_digest": digest(command.model_dump())}
        binding["attempt_digest"] = make_graph_binding_digest(binding, context)
        return binding

    @staticmethod
    def _owner(operation):
        return "timeline" if operation == "m9.timeline.multitrack" else "image" if operation.startswith("m5.") else "video" if operation.startswith("m7.") else "audio"

    def validate_snapshot(self, row):
        nodes = self.nodes(row)
        previews, executions = row.get("media_previews"), row.get("media_executions")
        if (row.get("media_execution_contract") != CONTRACT or not 1 <= len(nodes) <= 4
                or not isinstance(previews, dict) or not isinstance(executions, dict)
                or set(previews) - set(nodes) or set(executions) - set(previews)):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_SNAPSHOT_INVALID")
        for node_id, preview in previews.items():
            _, command, input_digest = self._inputs(row, nodes[node_id])
            expected = {"node_id", "source_run_version", "input_digest", "graph_binding", "command",
                "production_preview", "preview_digest"}
            if (not isinstance(preview, dict) or set(preview) != expected or preview["node_id"] != node_id
                    or type(preview["source_run_version"]) is not int or preview["source_run_version"] < 1
                    or preview["input_digest"] != input_digest or preview["command"] != command.model_dump(exclude_none=True)
                    or preview["preview_digest"] != digest([CONTRACT, row[BINDING], row["scope"], row["created_by"],
                        row["graph_digest"], {key: value for key, value in preview.items() if key != "preview_digest"}])
                    or preview["graph_binding"] != self._binding(row, nodes[node_id], command, input_digest, preview["source_run_version"])):
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_PREVIEW_CHANGED")
            if nodes[node_id]["definition_id"] == "timeline_export":
                self.production.graph_timeline.context(row["novel_id"], row["scope"], row["created_by"],
                    preview["production_preview"], preview["graph_binding"], row[BINDING])
            execution = executions.get(node_id)
            if execution:
                expected_execution = {"node_id", "owner", "job_id", "request_id", "request_digest", "graph_binding",
                    "status", "receipt_state", "send_reserved", "job", "review_state"}
                if (not isinstance(execution, dict) or set(execution) != expected_execution
                        or execution["node_id"] != node_id or execution["owner"] != self._owner(command.operation_id)
                        or execution["graph_binding"] != preview["graph_binding"] or execution["request_id"] != command.request_id
                        or execution["request_digest"] != preview["production_preview"]["request_digest"]
                        or execution["status"] not in EXECUTION_STATUSES
                        or execution["receipt_state"] not in {"RECORDED", UNKNOWN}
                        or type(execution["send_reserved"]) is not bool
                        or execution["review_state"] not in {"NONE", "REVIEW_RESERVED", "APPROVED"}):
                    raise StaleSourceError("CREATIVE_GRAPH_MEDIA_EXECUTION_CHANGED")
                if execution["job"] is not None:
                    self._validate_job(row, node_id, execution, execution["job"], small=True)

    def _validate_job(self, row, node_id, execution, job, *, small=False):
        if (not isinstance(job, dict) or job.get("id") != execution["job_id"]
                or job.get("request_digest") != execution["request_digest"]
                or type(job.get("version")) is not int or job["version"] < 1
                or job.get("status") not in OWNER_STATUSES or (small and set(job) != set(RECEIPT_FIELDS))):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_OWNER_RECEIPT_CHANGED")
        if not small and (job.get("owner") != execution["owner"]
                or job.get("novel_id") != row["novel_id"] or job.get("branch_id") != row["scope"].get("branch_id")
                or job.get("request_id") != execution["request_id"]
                or job.get("operation_id") != row["media_previews"][node_id]["command"]["operation_id"]):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_OWNER_BINDING_CHANGED")
        if not small and execution["owner"] == "timeline":
            preview = row["media_previews"][node_id]["production_preview"]
            if (job.get("timeline_snapshot") != preview["timeline_snapshot"]
                    or job.get("sources") != [source["snapshot"] for source in preview["sources"]]
                    or job.get("execution_recipe") != preview["execution_recipe"] or job.get("command") is not None):
                raise StaleSourceError("CREATIVE_GRAPH_TIMELINE_OWNER_INPUT_CHANGED")
        recorded = execution.get("job")
        if not small and recorded:
            if job["version"] < recorded["version"]:
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_OWNER_VERSION_REGRESSED")
            # Read-only orphan projections may change advisory reconciliation
            # fields. Immutable original receipts may not change at the same
            # owner version, especially the candidate bytes/digest.
            immutable = ("id", "version", "status", "request_digest", "receipt_digest", "output_candidate",
                "approved_asset_version", "error_code", "cancellation_mode")
            if job["version"] == recorded["version"] and any(job.get(key) != recorded.get(key) for key in immutable):
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_OWNER_SAME_VERSION_CHANGED")
        if job.get("output_candidate"):
            self._candidate_port(execution, job)

    @staticmethod
    def _candidate_port(execution, job):
        candidate = job["output_candidate"]
        return validate_output_ports("timeline_export" if execution["owner"] == "timeline" else "media_generate", {"candidate": {"owner": execution["owner"],
            "job_id": job["id"], "job_version": job["version"], "request_digest": job["request_digest"],
            "asset": {"asset_id": candidate["id"], "version": candidate["version"],
                "digest": candidate["digest"], "kind": candidate["kind"]}}}, schema_version=3)["candidate"]

    def _metadata_authority(self, document, captured, node_id, current):
        row = self.service.asset_inputs.validate_document(captured["novel_id"], captured["scope"],
            captured["created_by"], captured, document, current)
        # Publication already owns the raw source scope. Revalidate original
        # node/cache/approval receipts without entering an asset phase here.
        self.service.executor._current(captured["novel_id"], captured["scope"],
            captured["created_by"], row, current, document, check_assets=False)
        expected = captured["media_executions"].get(node_id)
        live = row.get("media_executions", {}).get(node_id)
        if (row.get("status") in TERMINAL_RUNS or row.get("status") == "PAUSED"
                or row.get("media_previews", {}).get(node_id) != captured["media_previews"][node_id]
                or not expected or not live or any(live.get(key) != expected.get(key)
                    for key in ("node_id", "owner", "job_id", "request_id", "request_digest", "graph_binding", "send_reserved", "review_state"))):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_ATTEMPT_CHANGED")
        node_state = row.get("node_states", {}).get(node_id, {})
        if expected["review_state"] == "REVIEW_RESERVED":
            review_id = row.get("current_node_id")
            review_node = next((node for node in row["typed_nodes"] if node["id"] == review_id), None)
            candidate = row.get("typed_outputs", {}).get(node_id, {}).get("candidate")
            if (row["status"] != "WAITING_APPROVAL" or node_state.get("status") != "SUCCEEDED"
                    or not review_node or review_node["definition_id"] != "media_review"
                    or row["node_states"][review_id]["status"] != "WAITING_APPROVAL"
                    or not any(edge["source_node_id"] == node_id and edge["source_port"] == "candidate"
                        and edge["target_node_id"] == review_id and edge["target_port"] == "candidate" for edge in row["typed_edges"])
                    or not candidate or candidate["job_id"] != expected["job_id"]
                    or candidate["request_digest"] != expected["request_digest"]):
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_ACTIVE_REVIEW_REQUIRED")
        elif (expected["review_state"] != "NONE" or not expected["send_reserved"]
                or row["status"] != "RUNNING" or row.get("current_node_id") != node_id
                or node_state.get("status") != "WORKING"):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_ACTIVE_GENERATE_REQUIRED")
        self.validate_snapshot(row); self._deadline(row)
        self.timeline_current(row, document, current)
        return row

    def timeline_current(self, row, document, current, *, assets=False):
        """Check edited snapshots, not the now-historical node base snapshot."""
        for node_id, node in self.nodes(row).items():
            if node["definition_id"] != "timeline_export" or node_id in row.get("media_executions", {}):
                continue
            # Before admission an independent edit invalidates the captured
            # base and any displayed preview. This is a pure document check,
            # including when called before publication's asset phase.
            snapshot = node["parameters"]["timeline_snapshot"]
            original = self.production._owned_timeline(row["novel_id"], row["scope"], row["created_by"], snapshot["id"],
                {"incarnation": row[BINDING]}, document)
            if (original["version"], original["timeline_digest"]) != (snapshot["version"], snapshot["digest"]):
                raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        for node_id, execution in row.get("media_executions", {}).items():
            if execution["owner"] != "timeline": continue
            preview = row["media_previews"][node_id]
            context = self.production.graph_timeline.context(row["novel_id"], row["scope"], row["created_by"],
                preview["production_preview"], preview["graph_binding"], row[BINDING])
            self.production.graph_timeline.current(row["novel_id"], row["scope"], row["created_by"],
                context, document, current, assets=assets)

    def _guards(self, nid, scope, actor, row, node_id, current):
        archival = self._text_assets(row)
        prepared = archival.prepare_projection(row, current) if archival else None
        def source_guard(document):
            live = self._metadata_authority(document, row, node_id, current)
            self._admission_capacity(document, live, 2)
            # Production calls this after taking its existing asset lease while
            # the same raw source lease remains held. Never reopen scope here.
            def asset_guard():
                self.service.asset_inputs.current_under_asset_lease(nid, scope, actor, live, current)
                self.timeline_current(live, document, current, assets=True)
                if archival:
                    archival.current_under_asset_lease(nid, scope, actor, live, current, prepared)
            return asset_guard
        def last_mile():
            with self._phase(nid, scope, actor, row["id"], current) as document:
                live = self._metadata_authority(document, row, node_id, current)
                self.service.asset_inputs.current(nid, scope, actor, live, current, document)
                self.timeline_current(live, document, current, assets=True)
                if archival and prepared is not None:
                    archival.output_authority(live)
        return last_mile, source_guard

    def _job(self, nid, scope, actor, row, node_id, current):
        execution = row["media_executions"].get(node_id)
        if not execution or not execution["job_id"]:
            raise ValueError("CREATIVE_GRAPH_MEDIA_OWNER_JOB_REQUIRED")
        job = self.production.get(nid, scope, actor, execution["owner"], execution["job_id"], current,
            graph_binding=execution["graph_binding"])
        self._validate_job(row, node_id, execution, job)
        return job

    @staticmethod
    def _job_action(body):
        return MediaJobAction(expected_version=body.expected_job_version, expected_request_digest=body.expected_request_digest)

    def _checked_action(self, nid, scope, actor, rid, value, guard, *, review=False):
        body = (MediaGraphReview if review else MediaJobRequest).model_validate(value)
        _, current = self.service._context(nid, scope, actor, guard)
        row = self._row(nid, scope, actor, rid, current)
        check_version(row, body.expected_version)
        node_id = body.node_id
        if review:
            if not any(node["id"] == node_id and node["definition_id"] == "media_review" for node in row["typed_nodes"]):
                raise ValueError("CREATIVE_GRAPH_MEDIA_REVIEW_NODE_REQUIRED")
            edge = next((edge for edge in row["typed_edges"] if edge["target_node_id"] == node_id and edge["target_port"] == "candidate"), None)
            if edge is None: raise ValueError("CREATIVE_GRAPH_MEDIA_REVIEW_BINDING_REQUIRED")
            node_id = edge["source_node_id"]
        self._node(row, node_id); self._deadline(row)
        job = self._job(nid, scope, actor, row, node_id, current)
        if (job["version"], job["request_digest"]) != (body.expected_job_version, body.expected_request_digest):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_EXACT_OWNER_VERSION_REQUIRED")
        return body, current, row, node_id, job

    def _commit_host(self, row, actor, host, **extra):
        payload = {key: deepcopy(value) for key, value in host.row.items() if key not in {"version", "history"}}
        payload.update(trace=row["trace"] + host.transitions, dispatch_trace=row["dispatch_trace"] + host.dispatches, **extra)
        change_row(row, actor, row["version"], lambda item: item.update(payload))

    def preview(self, nid, scope, actor, rid, value, guard):
        body = MediaNodeRequest.model_validate(value)
        _, current = self.service._context(nid, scope, actor, guard)
        row = self._row(nid, scope, actor, rid, current)
        check_version(row, body.expected_version)
        node = self._node(row, body.node_id)
        self._deadline(row); self._capacity(row, 8)
        if (row["status"] != "WAITING_APPROVAL" or row["current_node_id"] != node["id"]
                or node["id"] in row["media_executions"]):
            raise ValueError("CREATIVE_GRAPH_MEDIA_NODE_NOT_AWAITING_PREVIEW")
        _, command, input_digest = self._inputs(row, node)
        binding = self._binding(row, node, command, input_digest, body.expected_version)
        if node["definition_id"] == "timeline_export":
            with self._phase(nid, scope, actor, rid, current) as document:
                self._row(nid, scope, actor, rid, current, document)
                production_preview, _, _ = self.production.graph_timeline.prepare(nid, scope, actor,
                    command, current, document=document, graph_binding=binding)
        else:
            production_preview, _, _ = self.production.preview(nid, scope, actor, command, current, graph_binding=binding)
        preview = {"node_id": node["id"], "source_run_version": body.expected_version, "input_digest": input_digest,
            "graph_binding": binding, "command": command.model_dump(exclude_none=True), "production_preview": production_preview}
        preview["preview_digest"] = digest([CONTRACT, row[BINDING], scope, actor, row["graph_digest"], preview])
        with self._phase(nid, scope, actor, rid, current, writable=True) as state:
            stored = self._row(nid, scope, actor, rid, current, state)
            check_version(stored, body.expected_version)
            if node["definition_id"] == "timeline_export":
                fresh, _, _ = self.production.graph_timeline.prepare(nid, scope, actor,
                    command, current, document=state, graph_binding=binding)
                if fresh != production_preview:
                    raise StaleSourceError("STUDIO_PRODUCTION_PREVIEW_CHANGED")
            projected = deepcopy(stored)
            projected["media_previews"][node["id"]] = preview
            self._admission_capacity(state, projected)
            change_row(stored, actor, body.expected_version, lambda item: item["media_previews"].update({node["id"]: deepcopy(preview)}))
            self.service._capacity(state); current()
            return self._view(nid, scope, actor, stored, current, state)

    def dispatch(self, nid, scope, actor, rid, value, guard):
        """Claim the original node and queue once. This method never sends."""
        body = MediaDispatch.model_validate(value)
        _, current = self.service._context(nid, scope, actor, guard)
        row = self._row(nid, scope, actor, rid, current)
        check_version(row, body.expected_version)
        node = self._node(row, body.node_id)
        preview = row["media_previews"].get(node["id"])
        self._deadline(row); self._capacity(row, 6)
        if (not preview or preview["preview_digest"] != body.reviewed_preview_digest
                or row["status"] != "WAITING_APPROVAL" or row["current_node_id"] != node["id"]
                or node["id"] in row["media_executions"]):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_EXACT_PREVIEW_REQUIRED")
        execution = {"node_id": node["id"], "owner": self._owner(preview["command"]["operation_id"]), "job_id": None,
            "request_id": preview["command"]["request_id"], "request_digest": preview["production_preview"]["request_digest"],
            "graph_binding": deepcopy(preview["graph_binding"]), "status": "ADMISSION_RESERVED", "receipt_state": UNKNOWN,
            "send_reserved": False, "job": None, "review_state": "NONE"}
        with self._phase(nid, scope, actor, rid, current, writable=True) as state:
            stored = self._row(nid, scope, actor, rid, current, state)
            check_version(stored, body.expected_version)
            self._admission_capacity(state, stored)
            if node["definition_id"] == "timeline_export":
                self.production.graph_timeline.commit(nid, scope, actor, preview["production_preview"],
                    preview["graph_binding"], current, document=state)
            host = _ScopedOriginalWorkflowHost(stored, current)
            host.trigger_agent_node(rid, node["id"], actor); host.claim_agent_task(rid, node["id"], actor)
            host.row["media_executions"][node["id"]] = deepcopy(execution)
            self._commit_host(stored, actor, host); self.service._capacity(state); current()
            captured = deepcopy(stored)
        try:
            if execution["owner"] == "timeline":
                job = self.production.graph_timeline_queue(nid, scope, actor, preview["production_preview"],
                    execution["graph_binding"], captured[BINDING], current)
            else:
                job = self.production.create(nid, scope, actor, MediaCreate(command=MediaCommand.model_validate(preview["command"]),
                    reviewed_preview_digest=preview["production_preview"]["preview_digest"]), current, graph_binding=execution["graph_binding"])
            execution["job_id"] = job["id"]
            return self._synchronize(nid, scope, actor, captured, node["id"], execution, job, current)
        except Exception:
            self._unknown(nid, scope, actor, rid, node["id"], execution, current, "ADMISSION_UNKNOWN")
            # Cancellation can commit while original admission is in flight.
            # Its first lookup may see no job yet. Recheck the durable fence
            # after admission/reply failure and cancel only the original bound
            # receipt; never create or execute a replacement. Keep any failed
            # cancellation evidence/receipt for later original-owner inspection.
            try:
                latest = self.service._owned(nid, scope, actor, self.service.RUNS, rid)
                if latest["status"] in TERMINAL_RUNS:
                    self.cancel(nid, scope, actor, latest, current)
            except (FileNotFoundError, ValueError, StaleSourceError):
                pass
            raise

    def _unknown(self, nid, scope, actor, rid, node_id, execution, current, status="UNKNOWN"):
        # The preceding reservation already survives failed reporting/revocation.
        try:
            with self.service.asset_inputs.transaction(nid, scope, actor, current) as state:
                row = self.service._owned(nid, scope, actor, self.service.RUNS, rid, state)
                live = row.get("media_executions", {}).get(node_id)
                if not live or live["graph_binding"] != execution["graph_binding"] or row["status"] in TERMINAL_RUNS or live["status"] == "APPROVED": return
                changed = {**deepcopy(live), "status": status, "receipt_state": UNKNOWN}
                if changed != live:
                    change_row(row, actor, row["version"], lambda item: item["media_executions"].update({node_id: changed}))
                    self.service._capacity(state); current()
        except Exception:
            return

    def _synchronize(self, nid, scope, actor, captured, node_id, execution, job, current):
        self._validate_job(captured, node_id, execution, job)
        updated = {**deepcopy(execution), "status": job["status"],
            "receipt_state": UNKNOWN if job["status"] in {"UNKNOWN", "RUNNING", "SEND_RESERVED"} else "RECORDED",
            "job": {key: deepcopy(job.get(key)) for key in RECEIPT_FIELDS}}
        with self._phase(nid, scope, actor, captured["id"], current, writable=True) as state:
            row = self._row(nid, scope, actor, captured["id"], current, state)
            check_version(row, captured["version"])
            self.timeline_current(row, state, current, assets=True)
            if row["media_executions"].get(node_id, {}).get("graph_binding") != updated["graph_binding"]:
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_ATTEMPT_CHANGED")
            host = _ScopedOriginalWorkflowHost(row, current)
            if host.get_workflow_run(row["id"])["status"] in TERMINAL_RUNS:
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RUN_NO_LONGER_ACCEPTS_RESULT")
            if row["node_states"][node_id]["status"] == "WORKING":
                if job["status"] in {"AWAITING_REVIEW", "SUCCEEDED", "REVIEWING", "APPROVED"}:
                    if job["status"] == "APPROVED":
                        raise StaleSourceError("CREATIVE_GRAPH_MEDIA_OWNER_APPROVED_WITHOUT_GRAPH_REVIEW")
                    candidate = self._candidate_port(updated, job)
                    self.service.asset_inputs.read_candidate(nid, scope, actor, candidate, current, graph_binding=updated["graph_binding"])
                    output = {"candidate": candidate}
                    host.complete_agent_task(row["id"], node_id, "SUCCEEDED", output={"ports": output,
                        "provenance": {"method": "ORIGINAL_MEDIA_OWNER", "contract": CONTRACT,
                            "owner": updated["owner"], "job_id": job["id"], "request_digest": job["request_digest"]},
                        "model_called": False, "applied": False})
                    host.row["typed_outputs"][node_id] = output
                    node = self._node(row, node_id)
                    ports = self.service.executor._inputs(row, node_id, row["typed_outputs"])
                    host.row["cache_keys"][node_id] = {"key": self.service.executor._key(row, actor, node, ports),
                        "output_digest": digest(output), "cacheable": False}
                elif job["status"] in {"FAILED", "CANCELLED"}:
                    host.complete_agent_task(row["id"], node_id, "FAILED", error="CREATIVE_GRAPH_MEDIA_RESULT_DISCARDED")
            host.row["media_executions"][node_id] = updated
            # Original completion may advance to an unrelated ready local
            # text/reference node before the media review gate. Drive only
            # those trusted local nodes; the original executor stops at every
            # media/model/human confirmation boundary.
            host.row = self.service.executor._drive(host, host.row, actor, state, current)
            if host.row != row:
                self._commit_host(row, actor, host); self.service._capacity(state); current()
            return self._view(nid, scope, actor, row, current, state)

    def execute_job(self, nid, scope, actor, rid, value, guard):
        body, current, row, node_id, job = self._checked_action(nid, scope, actor, rid, value, guard)
        execution = deepcopy(row["media_executions"][node_id])
        self._capacity(row, 4)
        if (execution["send_reserved"] or job["status"] != "QUEUED" or row["status"] != "RUNNING"
                or row["node_states"][node_id]["status"] != "WORKING"):
            raise ValueError("CREATIVE_GRAPH_MEDIA_SEND_ONCE_REQUIRES_UNSENT_QUEUED_JOB")
        execution.update(send_reserved=True, status="SEND_RESERVED", receipt_state=UNKNOWN)
        with self._phase(nid, scope, actor, rid, current, writable=True) as state:
            stored = self._row(nid, scope, actor, rid, current, state)
            check_version(stored, body.expected_version)
            self._admission_capacity(state, stored, 4)
            change_row(stored, actor, body.expected_version, lambda item: item["media_executions"].update({node_id: deepcopy(execution)}))
            self.service._capacity(state); current()
            captured = deepcopy(stored)
        graph_guard, source_guard = self._guards(nid, scope, actor, captured, node_id, current)
        try:
            job = self.production.execute(nid, scope, actor, execution["owner"], execution["job_id"], self._job_action(body), current,
                graph_binding=execution["graph_binding"], graph_guard=graph_guard, graph_source_guard=source_guard)
            return self._synchronize(nid, scope, actor, captured, node_id, execution, job, current)
        except Exception:
            self._unknown(nid, scope, actor, rid, node_id, execution, current)
            raise

    def refresh(self, nid, scope, actor, rid, value, guard):
        """Query an unknown admission, or explicitly poll the same video job."""
        unbound = (isinstance(value, dict) and "expected_job_version" not in value
            or isinstance(value, MediaNodeRequest) and not isinstance(value, MediaJobRequest))
        if unbound:
            body = MediaNodeRequest.model_validate(value)
            _, current = self.service._context(nid, scope, actor, guard)
            row = self._row(nid, scope, actor, rid, current)
            check_version(row, body.expected_version)
            self._node(row, body.node_id); self._deadline(row)
            execution = deepcopy(row["media_executions"].get(body.node_id))
            if not execution: raise ValueError("CREATIVE_GRAPH_MEDIA_ADMISSION_REQUIRED")
            if execution["job_id"]: raise ValueError("CREATIVE_GRAPH_MEDIA_EXACT_OWNER_VERSION_REQUIRED")
            jobs = self.production.list(nid, scope, actor, current, graph_binding=execution["graph_binding"])["items"]
            jobs = [job for job in jobs if job["request_id"] == execution["request_id"]
                and job["request_digest"] == execution["request_digest"] and job["owner"] == execution["owner"]]
            if len(jobs) > 1: raise StaleSourceError("CREATIVE_GRAPH_MEDIA_ADMISSION_AMBIGUOUS")
            if not jobs:
                self._unknown(nid, scope, actor, rid, body.node_id, execution, current, "JOB_NOT_FOUND")
                return self.service.get_run(nid, scope, actor, rid, current, reconcile=False)
            execution["job_id"] = jobs[0]["id"]
            return self._synchronize(nid, scope, actor, row, body.node_id, execution, jobs[0], current)
        body, current, row, node_id, job = self._checked_action(nid, scope, actor, rid, value, guard)
        execution = deepcopy(row["media_executions"][node_id])
        if execution["owner"] == "video" and execution["send_reserved"] and job["status"] in {"REMOTE_RUNNING", "RESULT_READY", "UNKNOWN"}:
            graph_guard, source_guard = self._guards(nid, scope, actor, row, node_id, current)
            try:
                job = self.production.refresh_video(nid, scope, actor, execution["job_id"], self._job_action(body), current,
                    graph_binding=execution["graph_binding"], graph_guard=graph_guard, graph_source_guard=source_guard)
            except Exception:
                self._unknown(nid, scope, actor, rid, node_id, execution, current)
                raise
        return self._synchronize(nid, scope, actor, row, node_id, execution, job, current)

    def reconcile(self, nid, scope, actor, rid, value, guard):
        body = MediaJobRequest.model_validate(value)
        _, current = self.service._context(nid, scope, actor, guard)
        with self.service.asset_inputs.phase(nid, scope, actor, current) as state:
            captured = deepcopy(self._bookkeeping_row(nid, scope, actor, rid, current, state))
            check_version(captured, body.expected_version)
            self._node(captured, body.node_id)
        job = self._job(nid, scope, actor, captured, body.node_id, current)
        if (job["version"], job["request_digest"]) != (body.expected_job_version, body.expected_request_digest):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_EXACT_OWNER_VERSION_REQUIRED")
        if job["status"] == "REVIEWING":
            return self._reconcile_review(nid, scope, actor, captured, body, job, current)
        # Ordinary execution reconciliation retains every original source,
        # timeline, route, deadline and workflow transition gate.
        body, current, row, node_id, job = self._checked_action(nid, scope, actor, rid, value, guard)
        execution = deepcopy(row["media_executions"][node_id])
        graph_guard, source_guard = self._guards(nid, scope, actor, row, node_id, current)
        job = self.production.reconcile(nid, scope, actor, execution["owner"], execution["job_id"], self._job_action(body), current,
            graph_binding=execution["graph_binding"], graph_guard=graph_guard, graph_source_guard=source_guard)
        return self._synchronize(nid, scope, actor, row, node_id, execution, job, current)

    def _bookkeeping_row(self, nid, scope, actor, rid, current, state):
        """Validate original metadata without granting current source authority.

        This is limited to stopped-review bookkeeping/read receipts. It is never
        used by preview, dispatch, execution, refresh, candidate or approval.
        """
        current()
        row = self.service._owned(nid, scope, actor, self.service.RUNS, rid, state)
        if row.get("graph_schema_version") != 3 or row.get("media_execution_contract") != CONTRACT:
            raise ValueError("CREATIVE_GRAPH_MEDIA_CONTRACT_REQUIRED")
        # The current Graph can have been edited/deleted after reservation.
        # Validate the durable original run snapshot; never revive that Graph
        # or let this metadata proof authorize a source, send or transition.
        snapshot = row.get("definition_snapshot")
        selected = row.get("selected_closure")
        if (not isinstance(snapshot, dict) or not isinstance(selected, list)
                or any(not isinstance(node_id, str) for node_id in selected)
                or len(set(selected)) != len(selected) or not selected
                or type(row.get("graph_version")) is not int or row["graph_version"] < 1
                or row.get("adapter_version") != ADAPTER_VERSION
                or any(not isinstance(row.get(key), str) or len(row[key]) != 64
                    or any(character not in "0123456789abcdef" for character in row[key])
                    for key in ("graph_digest", "execution_digest", "request_digest"))):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_BINDING_CHANGED")
        definition = parse_graph({"schema_version": 3, "title": snapshot.get("title"),
            "nodes": row.get("typed_nodes"), "edges": row.get("typed_edges")}).model_dump()
        nodes, edges = definition["nodes"], definition["edges"]
        if nodes != row["typed_nodes"] or edges != row["typed_edges"] or set(selected) != {node["id"] for node in nodes}:
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_BINDING_CHANGED")
        # check_assets=False uses only schema/topology and feature authority;
        # it does not look up current assets/timeline/model routes or jobs.
        preflight = self.service._preflight({"id": row["graph_id"], "novel_id": nid, "scope": scope,
            BINDING: row[BINDING], "version": row["graph_version"], "definition_digest": row["graph_digest"],
            "definition": definition}, {"expected_version": row["graph_version"], "target_node_ids": selected},
            actor, check_assets=False)
        pairs = list(dict.fromkeys((edge["source_node_id"], edge["target_node_id"]) for edge in edges))
        expected_snapshot = {"title": definition["title"],
            "nodes": [{"id": node["id"], "name": node["id"], "config": {},
                "type": "manual_approval" if node["definition_id"] in {"human_review", "media_review"} else "agent_task"}
                for node in nodes],
            "edges": [{"source": source, "target": target} for source, target in pairs],
            "topological_order": preflight["execution_order"]}
        statuses = {"PENDING", "WAITING_APPROVAL", "QUEUED", "WORKING", "SUCCEEDED", "FAILED", "SKIPPED", "REJECTED"}
        states = row.get("node_states")
        if (not preflight["executable"] or preflight["selected_closure"] != selected or snapshot != expected_snapshot
                or row.get("step_limit") != max(MAX_NODES, len(nodes)) or not isinstance(states, dict)
                or set(states) != set(selected) or any(not isinstance(value, dict) or value.get("status") not in statuses
                    for value in states.values())
                or row.get("status") not in {"QUEUED", "RUNNING", "WAITING_APPROVAL", "PAUSED", "SUCCEEDED", "FAILED", "CANCELLED", "REJECTED"}):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_ENGINE_CHANGED")
        by_id = {node["id"]: node for node in nodes}
        outputs = row.get("typed_outputs")
        if not isinstance(outputs, dict) or set(outputs) - set(by_id):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_OUTPUT_CHANGED")
        for node_id, output in outputs.items():
            if states[node_id]["status"] != "SUCCEEDED":
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_OUTPUT_CHANGED")
            validate_output_ports(by_id[node_id]["definition_id"], output, schema_version=3)
            receipt = row.get("cache_keys", {}).get(node_id, {})
            engine_output = (states[node_id].get("output") or {}).get("result") or {}
            if (engine_output.get("ports") != output or receipt.get("output_digest") != digest(output)
                    or receipt.get("key") != self.service.executor._key(row, actor, by_id[node_id],
                        self.service.executor._inputs(row, node_id, outputs))):
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_OUTPUT_CHANGED")
            if by_id[node_id]["definition_id"] == "human_review":
                approved = states[node_id].get("output") or {}
                if (output.get("reviewed_draft") != self.service.executor._inputs(row, node_id, outputs)["draft"]
                        or approved.get("approved_by") != actor.strip() or not approved.get("approved_at")
                        or engine_output.get("provenance") != {"method": "ORIGINAL_HUMAN_REVIEW", "review_node_id": node_id,
                            "reviewed_output_digest": digest([row["id"], node_id, row["graph_version"], output["reviewed_draft"]])}):
                    raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_OUTPUT_CHANGED")
        if any(node["definition_id"] == "text_generate" for node in nodes):
            if self.service.model_runtime is None:
                raise StaleSourceError("CREATIVE_MODEL_RUNTIME_UNAVAILABLE")
            self.service.model_runtime.validate_snapshot(row)
        self.service.executor._timing(row)
        self.validate_snapshot(row)
        current()
        return row

    def _review_recovery_binding(self, row, node_id, job):
        execution = row["media_executions"].get(node_id)
        candidate = row.get("typed_outputs", {}).get(node_id, {}).get("candidate")
        if not execution:
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_EXACT_REVIEW_RECOVERY_REQUIRED")
        self._validate_job(row, node_id, execution, job)
        if (execution["review_state"] != "REVIEW_RESERVED" or not candidate
                or not job.get("output_candidate") or candidate["owner"] != execution["owner"]
                or candidate["job_id"] != execution["job_id"] or candidate["request_digest"] != execution["request_digest"]
                or candidate["job_version"] > job["version"]
                or candidate["asset"] != {"asset_id": job["output_candidate"]["id"], "version": job["output_candidate"]["version"],
                    "digest": job["output_candidate"]["digest"], "kind": job["output_candidate"]["kind"]}):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_EXACT_REVIEW_RECOVERY_REQUIRED")
        validate_output_ports("timeline_export" if execution["owner"] == "timeline" else "media_generate",
            {"candidate": candidate}, schema_version=3)
        return execution

    def _bookkeeping_view(self, row, jobs):
        """Masked original GraphRun DTO; unverified sources remain unusable."""
        result = {key: deepcopy(row[key]) for key in ("id", "version", "graph_id", "graph_version", "status",
            "current_node_id", "cache", "created_at", "updated_at", "reviewed")}
        result.update(project_id=row["novel_id"], scope=deepcopy(row["scope"]), stale=True,
            timeout_seconds=row["timeout_seconds"], deadline_at=self.service.executor._timing(row),
            node_states={node_id: {"status": value["status"], "reviewed": node_id in row.get("reviewed_nodes", []),
                "output": None, "error": {"code": "CREATIVE_GRAPH_NODE_FAILED"} if value.get("error") else None}
                for node_id, value in row["node_states"].items()},
            review=None, model_called=False, external_calls=0, applied=False)
        if any(node["definition_id"] == "text_generate" for node in row["typed_nodes"]):
            if self.service.model_runtime is None:
                raise ValueError("CREATIVE_MODEL_RUNTIME_UNAVAILABLE")
            # public(stale=True) projects stored metadata only; no route/source
            # admission, text archival convergence or runtime owner is invoked.
            result["model_runtime"] = self.service.model_runtime.public(row, stale=True)
            result["model_called"] = bool(row.get("model_execution", {}).get("model_called")) if row.get("model_execution") else False
        result["media_runtime"] = self.public(row, stale=True)
        for node in result["media_runtime"]["nodes"]:
            job = jobs.get(node["node_id"])
            if job and job["status"] == "REVIEWING":
                node["execution"]["status"] = "REVIEWING"
                node["execution"]["review_recovery"] = {"contract": "creative-graph-review-recovery/1",
                    "job_version": job["version"], "request_digest": job["request_digest"]}
        return result

    def _reconcile_review(self, nid, scope, actor, captured, body, original_job, current):
        node_id = body.node_id
        execution = deepcopy(self._review_recovery_binding(captured, node_id, original_job))
        self._capacity(captured, 1)
        # Host/actor/incarnation and original binding remain required. No route,
        # current source grant or workflow advancement is needed to release an
        # exact stopped private reservation through its original job owner.
        job = self.production.reconcile(nid, scope, actor, execution["owner"], execution["job_id"], self._job_action(body), current,
            graph_binding=execution["graph_binding"])
        self._validate_job(captured, node_id, execution, job)
        if job["status"] not in {"REVIEWING", "AWAITING_REVIEW"} or job.get("output_candidate") != original_job.get("output_candidate"):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_REVIEW_RECOVERY_OUTCOME_CHANGED")
        updated = {**deepcopy(execution), "status": job["status"], "receipt_state": "RECORDED",
            "job": {key: deepcopy(job.get(key)) for key in RECEIPT_FIELDS}}
        with self.service.asset_inputs.transaction(nid, scope, actor, current) as state:
            row = self._bookkeeping_row(nid, scope, actor, captured["id"], current, state)
            check_version(row, captured["version"])
            if row["media_executions"] != captured["media_executions"]:
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_RECEIPT_CHANGED")
            if updated != execution:
                change_row(row, actor, row["version"], lambda item: item["media_executions"].update({node_id: deepcopy(updated)}))
                self.service._capacity(state)
            result = self._bookkeeping_view(row, {node_id: job})
            current()
        return result

    def review_recovery_read(self, nid, scope, actor, rid, guard, *, expected_version=None, fallback=None):
        """Host GET only: exact owner lookup outside all scope/asset leases.

        No candidate, prompt, source or route is exposed. The three-field action
        evidence grants only an explicit original-owner REVIEWING reconciliation.
        """
        _, current = self.service._context(nid, scope, actor, guard)
        with self.service.asset_inputs.phase(nid, scope, actor, current) as state:
            captured = deepcopy(self._bookkeeping_row(nid, scope, actor, rid, current, state))
            if expected_version is not None: check_version(captured, expected_version)
        jobs = {}
        for node_id, execution in captured["media_executions"].items():
            if not execution["job_id"] or execution["review_state"] != "REVIEW_RESERVED": continue
            try:
                job = self._job(nid, scope, actor, captured, node_id, current)
                if job["status"] != "REVIEWING": continue
                self._review_recovery_binding(captured, node_id, job)
                jobs[node_id] = job
            except FileNotFoundError:
                continue
        if not jobs:
            current()
            return fallback
        with self.service.asset_inputs.phase(nid, scope, actor, current) as state:
            latest = self._bookkeeping_row(nid, scope, actor, rid, current, state)
            check_version(latest, captured["version"])
            if latest["media_executions"] != captured["media_executions"]:
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_RECOVERY_RECEIPT_CHANGED")
            result = self._bookkeeping_view(latest, jobs)
            current()
        return result

    def review(self, nid, scope, actor, rid, value, guard):
        body, current, row, node_id, job = self._checked_action(nid, scope, actor, rid, value, guard, review=True)
        execution = deepcopy(row["media_executions"][node_id])
        candidate = row["typed_outputs"].get(node_id, {}).get("candidate")
        self._capacity(row, 3)
        if (row["status"] != "WAITING_APPROVAL" or row["current_node_id"] != body.node_id
                or row["node_states"][node_id]["status"] != "SUCCEEDED" or not candidate
                or candidate["asset"]["digest"] != body.reviewed_output_digest
                or (job.get("output_candidate") or {}).get("digest") != body.reviewed_output_digest
                or job["status"] not in {"AWAITING_REVIEW", "SUCCEEDED", "REVIEWING", "APPROVED"}):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_EXACT_CANDIDATE_REVIEW_REQUIRED")
        if execution["review_state"] != "REVIEW_RESERVED":
            execution["review_state"] = "REVIEW_RESERVED"
            with self._phase(nid, scope, actor, rid, current, writable=True) as state:
                stored = self._row(nid, scope, actor, rid, current, state)
                check_version(stored, body.expected_version)
                self._admission_capacity(state, stored, 2)
                self.service.asset_inputs.read_candidate(nid, scope, actor, candidate, current, graph_binding=execution["graph_binding"])
                change_row(stored, actor, body.expected_version, lambda item: item["media_executions"].update({node_id: deepcopy(execution)}))
                self.service._capacity(state); current()
                row = deepcopy(stored)
        _, source_guard = self._guards(nid, scope, actor, row, node_id, current)
        try:
            reviewed = self.production.review(nid, scope, actor, execution["owner"], execution["job_id"],
                MediaReview(expected_version=body.expected_job_version, expected_request_digest=body.expected_request_digest,
                    reviewed_output_digest=body.reviewed_output_digest), current,
                graph_binding=execution["graph_binding"], graph_source_guard=source_guard)
            self._validate_job(row, node_id, execution, reviewed)
            if reviewed["status"] != "APPROVED" or type(reviewed.get("approved_asset_version")) is not int:
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_OWNER_APPROVAL_RECEIPT_REQUIRED")
            updated = {**execution, "status": "APPROVED", "receipt_state": "RECORDED", "review_state": "APPROVED",
                "job": {key: deepcopy(reviewed.get(key)) for key in RECEIPT_FIELDS}}
            asset = {**candidate["asset"], "version": reviewed["approved_asset_version"]}
            with self._phase(nid, scope, actor, rid, current, writable=True) as state:
                stored = self._row(nid, scope, actor, rid, current, state)
                check_version(stored, row["version"])
                if stored["media_executions"][node_id]["review_state"] != "REVIEW_RESERVED":
                    raise StaleSourceError("CREATIVE_GRAPH_MEDIA_APPROVAL_INTENT_CHANGED")
                self.service.asset_inputs.read(nid, scope, actor, asset, current)
                host = _ScopedOriginalWorkflowHost(stored, current)
                host.approve_workflow_node(rid, body.node_id, actor, "EXPLICIT_ORIGINAL_MEDIA_OWNER_REVIEW")
                output = validate_output_ports("media_review", {"asset": asset}, schema_version=3)
                host.row["typed_outputs"][body.node_id] = output
                host.row["node_states"][body.node_id]["output"] = {"result": {"ports": output,
                    "provenance": {"method": "ORIGINAL_MEDIA_OWNER_REVIEW", "contract": CONTRACT,
                        "owner": execution["owner"], "job_id": execution["job_id"], "output_digest": body.reviewed_output_digest},
                    "model_called": False, "applied": False}}
                review_node = next(node for node in stored["typed_nodes"] if node["id"] == body.node_id)
                ports = self.service.executor._inputs(stored, body.node_id, stored["typed_outputs"])
                host.row["cache_keys"][body.node_id] = {"key": self.service.executor._key(stored, actor, review_node, ports),
                    "output_digest": digest(output), "cacheable": False}
                host.row["media_executions"][node_id] = updated
                host.row = self.service.executor._drive(host, host.row, actor, state, current)
                self._commit_host(stored, actor, host); self.service._capacity(state); current()
                return self._view(nid, scope, actor, stored, current, state)
        except Exception:
            self._unknown(nid, scope, actor, rid, node_id, execution, current)
            raise

    def candidate(self, nid, scope, actor, rid, node_id, guard):
        _, current = self.service._context(nid, scope, actor, guard)
        row = self._row(nid, scope, actor, rid, current)
        self._node(row, node_id)
        if row["status"] in TERMINAL_RUNS: raise FileNotFoundError(node_id)
        job = self._job(nid, scope, actor, row, node_id, current)
        execution = row["media_executions"][node_id]
        if not job.get("output_candidate"): raise FileNotFoundError(node_id)
        meta, data = self.production.candidate(nid, scope, actor, execution["owner"], execution["job_id"], current,
            graph_binding=execution["graph_binding"])
        if hashlib.sha256(data).hexdigest() != job["output_candidate"]["digest"]:
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_CANDIDATE_BYTES_CHANGED")
        # Do not read an owner queue while holding this final source/asset phase.
        # Recheck its original asset directly and reject a late stale private
        # response after source edits, cancellation, promotion or replacement.
        with self._phase(nid, scope, actor, rid, current) as state:
            latest = self._row(nid, scope, actor, rid, current, state)
            check_version(latest, row["version"])
            self.timeline_current(latest, state, current, assets=True)
            if latest["media_executions"][node_id] != execution or latest["status"] in TERMINAL_RUNS:
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_CANDIDATE_AUTHORITY_CHANGED")
            asset = self.service.workspace.assets.get(meta["id"], branch_id=scope.get("branch_id"), actor_id=actor)
            origin = asset.get("_studio_result_origin", {})
            if ((asset["version"], asset["sha256"], asset["kind"]) != (meta["version"], meta["sha256"], meta["kind"])
                    or origin.get("graph_binding") != execution["graph_binding"]
                    or origin.get("job_id") != execution["job_id"] or origin.get("request_digest") != execution["request_digest"]):
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_CANDIDATE_FINAL_RECEIPT_CHANGED")
            self.service.workspace.assets.content(asset["id"], branch_id=scope.get("branch_id"), actor_id=actor)
            current()
        return meta, data

    def output_authority(self, row):
        """Pure receipt checks, safe within the original leased scope."""
        self.validate_snapshot(row)
        for node_id, execution in row["media_executions"].items():
            candidate = row["typed_outputs"].get(node_id, {}).get("candidate")
            if candidate:
                job = execution.get("job")
                if (not job or candidate["job_id"] != execution["job_id"] or candidate["request_digest"] != execution["request_digest"]
                        or not job.get("output_candidate") or candidate["asset"]["asset_id"] != job["output_candidate"]["id"]
                        or candidate["asset"]["digest"] != job["output_candidate"]["digest"]):
                    raise StaleSourceError("CREATIVE_GRAPH_MEDIA_OUTPUT_RECEIPT_REQUIRED")
            for edge in row["typed_edges"]:
                if edge["source_node_id"] != node_id or edge["source_port"] != "candidate": continue
                asset = row["typed_outputs"].get(edge["target_node_id"], {}).get("asset")
                if asset and (not candidate or execution["review_state"] != "APPROVED" or execution["status"] != "APPROVED"
                        or asset["asset_id"] != candidate["asset"]["asset_id"] or asset["digest"] != candidate["asset"]["digest"]
                        or asset["version"] != execution["job"]["approved_asset_version"]):
                    raise StaleSourceError("CREATIVE_GRAPH_MEDIA_UNREVIEWED_OUTPUT_DENIED")

    def cancel(self, nid, scope, actor, row, guard):
        """After the original durable run fence; never claim remote abort."""
        if row["status"] not in TERMINAL_RUNS: return
        _, current = self.service._context(nid, scope, actor, guard)
        for execution in row.get("media_executions", {}).values():
            try:
                if execution["job_id"]:
                    jobs = [self.production.get(nid, scope, actor, execution["owner"], execution["job_id"], current,
                        graph_binding=execution["graph_binding"])]
                else:
                    # Admission may have committed after its Graph reply was
                    # lost. Query the same binding; never create a successor.
                    jobs = self.production.list(nid, scope, actor, current, graph_binding=execution["graph_binding"])["items"]
                    jobs = [job for job in jobs if job["request_id"] == execution["request_id"]
                        and job["request_digest"] == execution["request_digest"] and job["owner"] == execution["owner"]]
                    if len(jobs) > 1: continue
                if not jobs: continue
                job = jobs[0]
                if job["status"] not in {"APPROVED", "FAILED", "CANCELLED", "REVIEWING"}:
                    self.production.cancel(nid, scope, actor, execution["owner"], job["id"],
                        MediaJobAction(expected_version=job["version"], expected_request_digest=job["request_digest"]), current,
                        graph_binding=execution["graph_binding"])
            except (FileNotFoundError, ValueError, StaleSourceError):
                # Run invalidation already discards late results. Keep uncertain
                # original receipts and candidates for inspection.
                continue

    def read(self, nid, scope, actor, rid, guard, *, expected_version=None):
        try:
            result = self._read_current(nid, scope, actor, rid, guard, expected_version=expected_version)
        except (StaleSourceError, FileNotFoundError):
            result = self.review_recovery_read(nid, scope, actor, rid, guard, expected_version=expected_version)
            if result is None: raise
            return result
        if result["stale"] or result["status"] in TERMINAL_RUNS:
            return self.review_recovery_read(nid, scope, actor, rid, guard, expected_version=result["version"], fallback=result)
        return result

    def _read_current(self, nid, scope, actor, rid, guard, *, expected_version=None):
        """Read-only current owner receipts; no polling, reconciliation or write.

        Current job versions are needed after an unknown owner reply, including
        a committed promotion whose Graph completion still needs explicit review.
        Queue reads happen after releasing the scope/asset phase.
        """
        _, current = self.service._context(nid, scope, actor, guard)
        with self._phase(nid, scope, actor, rid, current, expected_version=expected_version) as state:
            row = self.service._owned(nid, scope, actor, self.service.RUNS, rid, state)
            result = self._view(nid, scope, actor, row, current, state)
            captured = deepcopy(row)
        if result["stale"] or captured["status"] in TERMINAL_RUNS:
            return result
        by_id = {entry["node_id"]: entry for entry in result["media_runtime"]["nodes"]}
        for node_id, execution in captured["media_executions"].items():
            if not execution["job_id"]: continue
            try:
                job = self._job(nid, scope, actor, captured, node_id, current)
            except FileNotFoundError:
                public = by_id[node_id]["execution"]
                public.update(status="UNKNOWN", receipt_state=UNKNOWN, job=None)
                by_id[node_id]["status"] = "UNKNOWN"
                continue
            public = by_id[node_id]["execution"]
            public["job"] = {key: deepcopy(job.get(key)) for key in RECEIPT_FIELDS}
            # Preserve Graph review/admission consent, rather than implying that
            # an owner's approval already completed the Graph review node.
            if execution["review_state"] != "REVIEW_RESERVED":
                public["status"] = job["status"]
                by_id[node_id]["status"] = job["status"]
            elif job["status"] == "REVIEWING":
                self._review_recovery_binding(captured, node_id, job)
                public["status"] = "REVIEWING"
                by_id[node_id]["status"] = "REVIEWING"
                public["review_recovery"] = {"contract": "creative-graph-review-recovery/1",
                    "job_version": job["version"], "request_digest": job["request_digest"]}
            public["receipt_state"] = UNKNOWN if job["status"] in {"UNKNOWN", "RUNNING", "SEND_RESERVED"} else "RECORDED"
        with self._phase(nid, scope, actor, rid, current) as state:
            latest = self.service._owned(nid, scope, actor, self.service.RUNS, rid, state)
            check_version(latest, captured["version"])
            if latest["media_executions"] != captured["media_executions"]:
                raise StaleSourceError("CREATIVE_GRAPH_MEDIA_READ_RECEIPT_CHANGED")
            final = self._view(nid, scope, actor, latest, current, state)
            if not final["stale"]:
                final["media_runtime"] = result["media_runtime"]
            current()
        return final

    def public(self, row, *, stale=False):
        masked = stale or row["status"] in TERMINAL_RUNS
        result = []
        for node_id in self.nodes(row):
            preview = row.get("media_previews", {}).get(node_id)
            execution = row.get("media_executions", {}).get(node_id)
            public_preview = ({key: deepcopy(preview[key]) for key in ("node_id", "input_digest", "preview_digest",
                "command", "production_preview")} if preview and not masked else None)
            public_execution = ({key: deepcopy(execution[key]) for key in ("node_id", "owner", "job_id", "status",
                "receipt_state", "send_reserved", "job", "review_state")} if execution else None)
            if public_execution and masked: public_execution["job"] = None
            status = execution["status"] if execution else "AWAITING_PREVIEW" if row["current_node_id"] == node_id else "PENDING"
            result.append({"node_id": node_id, "status": "STALE" if stale else status,
                "preview": public_preview, "execution": public_execution})
        return {"schema_version": 1, "contract": CONTRACT, "nodes": result, "product_acceptance": "LOCAL_REQUIRED",
            "automatic_retry": False, "automatic_poll": False, "applied": False}
