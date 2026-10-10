"""Bounded archival convergence over the original graph and asset owners.

This is not a queue, asset database, dispatch authority or review state machine.
Each authorized read/refresh makes at most one attempt. A durable completed job
may be archived after restart, but its former execution closure is never rebuilt.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
from threading import Lock
import time

from ..experimental.common import StaleSourceError, check_version
from ..experimental.store import canonical
from .graph_models import validate_output_ports
from .project_store import BINDING

CONTRACT = "creative-graph-text-asset/1"
_phase = ContextVar("graph_text_asset_read_authority", default=None)


class GraphTextAssets:
    def __init__(self, runtime):
        self.runtime, self.service = runtime, runtime.service
        self.workspace, self.assets = self.service.workspace, self.service.workspace.assets
        # Bounded, transient retry suppression only. Durable state remains in
        # the original owners; this never schedules or repeats model work.
        self._cooldowns, self._cooldown_lock = OrderedDict(), Lock()

    @staticmethod
    def enabled(row):
        return row.get("model_asset_intent", {}).get("contract") == CONTRACT

    def validate_intent(self, row):
        intent = row.get("model_asset_intent")
        if intent is None:
            return
        execution, preview = row.get("model_execution") or {}, row.get("model_preview") or {}
        if (not isinstance(intent, dict) or set(intent) != {"contract", "job_id", "source_run_version", "preview_digest"}
                or intent["contract"] != CONTRACT or intent["job_id"] != execution.get("job_id")
                or type(intent["source_run_version"]) is not int or not 1 <= intent["source_run_version"] <= row["version"]
                or intent["preview_digest"] != preview.get("preview_digest")):
            raise StaleSourceError("CREATIVE_TEXT_ASSET_INTENT_CHANGED")

    def _key(self, row):
        return "graph-text:" + sha256(canonical([CONTRACT, row[BINDING], row["scope"], row["created_by"],
            row["id"], row["model_asset_intent"]]).encode()).hexdigest()

    def _job(self, row):
        """Require original durable completion, never infer success from text."""
        execution, preview = row["model_execution"], row["model_preview"]
        job = self.runtime.bound_job(row)
        saved = self.runtime.manager.persistence.get(job.id)
        if not isinstance(saved, dict):
            raise StaleSourceError("CREATIVE_TEXT_ASSET_COMPLETION_UNCONFIRMED")
        fields = ("id", "novel_id", "actor_id", "scope", "operation", "experimental_origin", "graph_binding",
            "requested_provider", "requested_model", "provider", "model", "output", "status", "execution_outcome",
            "terminal_hook_status", "expected_request_digest", "created_at", "updated_at")
        if any(saved.get(key) != getattr(job, key, None) for key in fields):
            raise StaleSourceError("CREATIVE_TEXT_ASSET_DURABLE_JOB_CHANGED")
        if (saved.get("status") != "COMPLETED" or saved.get("execution_outcome") != "COMPLETED"
                or saved.get("terminal_hook_status") != "COMPLETED" or saved.get("operation") != "graph_text"
                or saved.get("experimental_origin") != "creative_graph_model"
                or (saved.get("provider"), saved.get("model")) != (preview["route"]["provider_id"], preview["route"]["model_id"])):
            raise StaleSourceError("CREATIVE_TEXT_ASSET_COMPLETION_UNCONFIRMED")
        ledger = self.runtime.broker.get(row["novel_id"], row["scope"], self.runtime.broker.LEDGER, execution["reservation_id"])
        if (ledger.get("created_by") != row["created_by"] or ledger.get("job_id") != job.id
                or ledger.get("status") != "SETTLED" or ledger.get("job_status") != "COMPLETED"
                or ledger.get("actual_microusd") != 0 or not ledger.get("dispatched")):
            raise StaleSourceError("CREATIVE_TEXT_ASSET_SETTLEMENT_UNCONFIRMED")
        validate_output_ports("text_generate", {"draft": {"text": job.output, "origin": "MODEL_PROPOSAL"}})
        return job

    def _route(self, row):
        """Current registered identity, without recreating historical consent."""
        preview = row["model_preview"]
        route = self.runtime.broker.current_route(preview["route"]["route_id"], local_text_only=True)
        self.runtime.router.guard_route(route, synthetic_allowed=preview["allow_synthetic"])
        job = self.runtime.bound_job(row)
        if (route["fingerprint"] != job.graph_binding.get("route_fingerprint")
                or not route["synthetic"] and not route.get("identity", {}).get("license_confirmed")):
            raise StaleSourceError("CREATIVE_TEXT_ASSET_ROUTE_CHANGED")
        from ..model_execution import LocalModelInvocation
        from ..model_center.discovery_bridge import LocalTextAdapter
        invocation = LocalModelInvocation(self.runtime.broker.runtime, route["provider_id"], route["model_id"],
            synthetic_allowed=preview["allow_synthetic"])
        provider = invocation._provider
        registration = deepcopy(provider.bridge.guard(provider.candidate["id"])) if type(provider) is LocalTextAdapter else None
        synthetic_config = None if registration is not None else (
            getattr(provider.provider, "delay_ms", None), getattr(provider.provider, "failure", None))
        def current_registration():
            invocation.validate()
            if registration is not None:
                if provider.bridge.guard(provider.candidate["id"]) != registration:
                    raise StaleSourceError("CREATIVE_TEXT_ASSET_ROUTE_CHANGED")
            elif synthetic_config != (getattr(provider.provider, "delay_ms", None), getattr(provider.provider, "failure", None)):
                raise StaleSourceError("CREATIVE_TEXT_ASSET_ROUTE_CHANGED")
        current_registration()
        return current_registration

    def _source(self, nid, scope, actor, rid, guard, state=None):
        row = self.runtime.row(nid, scope, actor, rid, guard, state)
        self.validate_intent(row)
        if not self.enabled(row):
            raise ValueError("CREATIVE_TEXT_ASSET_CONTRACT_REQUIRED")
        return row

    @contextmanager
    def _lease(self, nid, scope, actor, rid, guard):
        if self.runtime.broker.store is not self.service.store.store:
            raise ValueError("CREATIVE_TEXT_ASSET_SHARED_SCOPE_OWNER_REQUIRED")
        with self.service.store.source_lease(nid, scope) as state:
            with self.workspace._asset_scope(nid, scope):
                row = self._source(nid, scope, actor, rid, guard, state)
                yield row
                guard()

    def _find(self, row):
        matches = [asset for asset in self.assets.list(row["novel_id"], branch_id=row["scope"].get("branch_id"),
            actor_id=row["created_by"], include_deleted=True) if asset.get("idempotency_key") == self._key(row)]
        if len(matches) > 1:
            raise ValueError("CREATIVE_TEXT_ASSET_IDENTITY_AMBIGUOUS")
        return matches[0] if matches else None

    def _origin(self, row, job):
        node = self.runtime.node(row)
        # JobManager's final notification legitimately changes job.updated_at
        # after its durable terminal hook. Use the original once-only completed
        # settlement's time, not that mutable notification timestamp.
        ledger = self.runtime.broker.get(row["novel_id"], row["scope"], self.runtime.broker.LEDGER,
            row["model_execution"]["reservation_id"])
        return {"schema_version": 1, "contract": CONTRACT, "graph_id": row["graph_id"],
            "graph_version": row["graph_version"], "graph_digest": row["graph_digest"], "run_id": row["id"],
            "source_run_version": row["model_asset_intent"]["source_run_version"], "model_node_id": node["id"],
            "job_id": job.id, "input_digest": row["model_preview"]["input_digest"],
            "output_digest": sha256(job.output.encode()).hexdigest(), "preview_digest": row["model_preview"]["preview_digest"],
            "produced_at": ledger["updated_at"]}

    def ensure(self, nid, scope, actor, rid, guard, *, create):
        row = self._source(nid, scope, actor, rid, guard)
        # Slow metadata checks are outside the source/asset persistence lease.
        route_guard = self._route(row)
        incarnation, preview = row[BINDING], deepcopy(row["model_preview"])
        with self._lease(nid, scope, actor, rid, guard) as current:
            if current[BINDING] != incarnation or current["model_preview"] != preview:
                raise StaleSourceError("CREATIVE_TEXT_ASSET_SOURCE_CHANGED")
            job = self._job(current)
            origin = self._origin(current, job)
            def fresh():
                guard()
                live = self._source(nid, scope, actor, rid, guard)
                if live != current:
                    raise StaleSourceError("CREATIVE_TEXT_ASSET_SOURCE_CHANGED")
                # No new probe/IO: exact registration still has its original
                # enablement and model identity. Full observation ran above.
                route_guard()
                if self._origin(live, self._job(live)) != origin:
                    raise StaleSourceError("CREATIVE_TEXT_ASSET_COMPLETION_CHANGED")
            asset = self._find(current)
            if asset is None and create:
                usage = self.assets.project_usage(nid, branch_id=scope.get("branch_id"))
                data = job.output.encode()
                if usage["count"] >= self.workspace.MAX_ASSETS or usage["bytes"] + len(data) > self.workspace.MAX_PROJECT_BYTES:
                    raise ValueError("CREATIVE_PROJECT_ASSET_QUOTA")
                self.workspace.storage_admission.require(len(data))
                from .ai_execution import FLAGS
                def before_commit():
                    fresh(); self.workspace.storage_admission.require(1)
                asset = self.assets.create_text_result(nid, "graph-" + rid + ".txt", job.output,
                    source_receipt=origin, provider_id=preview["route"]["provider_id"], model_id=preview["route"]["model_id"],
                    source_job_id=job.id, parameters={"max_output_tokens": self.runtime.node(current)["parameters"]["max_output_tokens"],
                        "temperature": 0.0, "synthetic": preview["route"]["synthetic"], "quality_verification": "NOT_RUN"},
                    idempotency_key=self._key(current), branch_id=scope.get("branch_id"), owner_actor_id=actor,
                    required_features=FLAGS, guard=before_commit)
            if asset is None:
                raise StaleSourceError("CREATIVE_TEXT_ASSET_ARCHIVE_INCOMPLETE")
            if (asset.get("deleted_at") or asset.get("kind") != "text" or asset.get("media_type") != "text/plain"
                    or asset.get("_text_result_origin") != origin):
                raise StaleSourceError("CREATIVE_TEXT_ASSET_ORIGIN_CHANGED")
            if self.assets.content(asset["id"], branch_id=scope.get("branch_id"), actor_id=actor) != job.output.encode():
                raise StaleSourceError("CREATIVE_TEXT_ASSET_BYTES_CHANGED")
            fresh()
            return deepcopy(asset), deepcopy(current), origin, route_guard

    @contextmanager
    def phase(self, nid, scope, actor, rid, guard, *, create=True):
        asset, row, origin, route_guard = self.ensure(nid, scope, actor, rid, guard, create=create)
        proof = {"runtime": self.runtime, "run_id": rid, "incarnation": row[BINDING], "origin": origin,
            "actor": actor, "scope": deepcopy(scope), "guard": guard, "route_guard": route_guard}
        token = _phase.set(proof)
        try:
            yield asset
        finally:
            _phase.reset(token)

    def output_authority(self, row):
        proof = _phase.get()
        if (not proof or proof["runtime"] is not self.runtime or proof["run_id"] != row["id"]
                or proof["incarnation"] != row[BINDING] or proof["actor"] != row["created_by"] or proof["scope"] != row["scope"]):
            raise StaleSourceError("CREATIVE_TEXT_ASSET_ARCHIVE_INCOMPLETE")
        proof["guard"]()
        proof["route_guard"]()
        job = self._job(row)
        if proof["origin"] != self._origin(row, job):
            raise StaleSourceError("CREATIVE_TEXT_ASSET_OUTPUT_CHANGED")
        output = row.get("typed_outputs", {}).get(self.runtime.node(row)["id"])
        if output is not None and output.get("draft", {}).get("text") != job.output:
            raise StaleSourceError("CREATIVE_TEXT_ASSET_OUTPUT_CHANGED")

    def has_authority(self, row):
        try:
            self.output_authority(row)
            return True
        except (StaleSourceError, FileNotFoundError, KeyError):
            return False

    def _decision(self, row, output_digest):
        snapshots = [*row["history"], row]
        for index, current in enumerate(snapshots):
            if index == 0:
                continue
            approved = current.get("status") == "SUCCEEDED" and current.get("reviewed") is True
            rejected = current.get("status") == "REJECTED"
            if not (approved or rejected):
                continue
            previous = snapshots[index - 1]
            review = self.service.executor._review(previous)
            if not review:
                continue
            return "APPROVED" if approved else "REJECTED", {"run_id": row["id"], "run_version": current["version"],
                "review_node_id": review["node_id"], "output_digest": output_digest,
                "reviewed_output_digest": review["output_digest"], "reviewed_by": current["updated_by"],
                "reviewed_at": current["updated_at"]}
        return "DRAFT", None

    def project(self, nid, scope, actor, rid, guard):
        asset, row, origin, route_guard = self.ensure(nid, scope, actor, rid, guard, create=False)
        status, decision = self._decision(row, origin["output_digest"])
        if decision is not None:
            with self._lease(nid, scope, actor, rid, guard) as current:
                if self._decision(current, origin["output_digest"]) != (status, decision):
                    raise StaleSourceError("CREATIVE_TEXT_ASSET_REVIEW_CHANGED")
                def before_review_commit():
                    guard(); route_guard()
                    live = self._source(nid, scope, actor, rid, guard)
                    if (live != current or self._origin(live, self._job(live)) != origin
                            or self._decision(live, origin["output_digest"]) != (status, decision)):
                        raise StaleSourceError("CREATIVE_TEXT_ASSET_REVIEW_CHANGED")
                asset = self.assets.review_text_result(asset["id"], actor_id=actor, branch_id=scope.get("branch_id"),
                    expected_version=asset["version"], output_digest=origin["output_digest"], status=status,
                    review_receipt=decision, guard=before_review_commit)
        guard()
        return {"contract": CONTRACT, "state": status, "asset_id": asset["id"], "version": asset["version"],
            "sha256": asset["sha256"], "size": asset["size"], "kind": "text", "media_type": "text/plain",
            "created_at": asset["created_at"], "updated_at": asset["updated_at"], "source": origin,
            "provider_id": asset["provider_id"], "model_id": asset["model_id"], "parameters": deepcopy(asset["parameters"]),
            "actor_private": True, "applied": False, "quality_verification": "NOT_RUN", "automatic_model_retry": False}

    @staticmethod
    def pending(state="PENDING", reason=None):
        return {"contract": CONTRACT, "state": state, "asset_id": None, "version": None,
            "actor_private": True, "applied": False, "quality_verification": "NOT_RUN",
            "automatic_model_retry": False, **({"reason": reason} if reason else {})}

    def masked(self, result, reason="ARCHIVE_RECONCILIATION_REQUIRED"):
        result = deepcopy(result)
        result.update(stale=True, review=None, asset_output=self.pending("INCOMPLETE", reason))
        for state in result["node_states"].values():
            state["output"] = None
        if result.get("model_runtime"):
            result["model_runtime"]["preview"] = None
        return result

    def decorate(self, nid, scope, actor, rid, guard, result):
        result["asset_output"] = self.project(nid, scope, actor, rid, guard)
        guard()
        return result

    def read(self, nid, scope, actor, rid, guard, *, reconcile=True):
        """One bounded convergence attempt during an already authorized read.

        Reopen after restart uses only a durable, settled completed result.
        Missing/uncertain execution stays pending, never restarts the worker.
        Failed attempts have a two-second cooldown (at most 100 keys).
        """
        row = self.service._owned(nid, scope, actor, self.service.RUNS, rid)
        result = self.service.executor.view(nid, scope, actor, row, guard)
        if not self.enabled(row):
            return result
        if row["status"] in {"CANCELLED", "FAILED"}:
            result["asset_output"] = self.pending("NO_ACCEPTED_RESULT")
            return result
        try:
            job = self.runtime.bound_job(row)
        except KeyError:
            return self.masked(result)
        if job.status in {"FAILED", "CANCELLED"} and row["status"] == "RUNNING" and reconcile:
            result = self.runtime.refresh(nid, scope, actor, rid, {"expected_version": row["version"]}, guard)
            result["asset_output"] = self.pending("NO_ACCEPTED_RESULT")
            return result
        if job.status == "COMPLETED" and job.terminal_hook_status != "COMPLETED":
            return self.masked(result, "TERMINAL_ACCOUNTING_RECONCILIATION_REQUIRED")
        if job.status != "COMPLETED":
            result["asset_output"] = self.pending()
            return result
        if not reconcile:
            result["asset_output"] = self.pending()
            return result
        key = (nid, self.service.store.key(nid, scope), actor, row[BINDING], rid)
        with self._cooldown_lock:
            if self._cooldowns.get(key, 0) > time.monotonic():
                return self.masked(result)
        try:
            if row["status"] == "RUNNING":
                result = self.runtime.refresh(nid, scope, actor, rid, {"expected_version": row["version"]}, guard)
            else:
                with self.phase(nid, scope, actor, rid, guard, create=False):
                    live = self.service._owned(nid, scope, actor, self.service.RUNS, rid)
                    result = self.service.executor.view(nid, scope, actor, live, guard)
                result = self.decorate(nid, scope, actor, rid, guard, result)
            with self._cooldown_lock:
                self._cooldowns.pop(key, None)
            return result
        except (ValueError, OSError, KeyError):
            guard()
            with self._cooldown_lock:
                self._cooldowns[key] = time.monotonic() + 2
                self._cooldowns.move_to_end(key)
                while len(self._cooldowns) > 100:
                    self._cooldowns.popitem(last=False)
            return self.masked(result)
