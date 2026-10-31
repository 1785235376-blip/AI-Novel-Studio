"""Bounded convergence over the original Creative, Job, Broker and Asset owners.

No model is called or replayed here. A final durable executor publication and
fresh read authority are both required; passive receipts never grant access.
"""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from threading import Lock
from uuid import UUID
import time

from ..author_request import request_payload_digest
from ..experimental.common import StaleSourceError, check_version
from ..experimental.store import canonical
from ..experimental.ux import ReadContext
from .proposals import digest
from .adaptation_models import AdaptationArchiveBinding, AdaptationJobBinding, terminal_publication
from .adaptation_receipt import (ASSET_CONTRACT, CONTRACT, PUBLICATION_CONTRACT, REVIEW_CONTRACT,
    FEATURES, MAX_OUTPUT_BYTES, MAX_PROMPT_BYTES, MAX_REQUEST_BYTES, MAX_BYTES, MAX_METADATA_BYTES,
    asset_parameters, receipt_payload, validate_receipt, public_receipt, validate_ordered_sources, validate_request)

_phase = ContextVar("adaptation_asset_authority", default=None)


def zero_settlement_state(price, usage):
    """Original Broker zero-cost branches, without inventing reported usage."""
    if not isinstance(price, dict): raise StaleSourceError("ADAPTATION_ZERO_PRICE_REQUIRED")
    if price.get("actual_known_zero") is True:
        return "KNOWN_SYNTHETIC_ZERO"
    if (any(type(price.get(key)) is not int or price[key] != 0 for key in
            ("input_per_million_microusd", "output_per_million_microusd"))
            or not isinstance(usage, dict)
            or any(type(usage.get(key)) is not int or usage[key] < 0 for key in ("input_tokens", "output_tokens"))):
        raise StaleSourceError("ADAPTATION_REPORTED_ZERO_SETTLEMENT_REQUIRED")
    return "CALCULATED_FROM_REPORTED_USAGE"


class AdaptationAssets:
    def __init__(self, proposals, workspace):
        self.proposals, self.workspace = proposals, workspace
        self._cooldowns, self._lock = OrderedDict(), Lock()

    @property
    def runtime(self): return self.proposals.generation
    @property
    def store(self): return self.proposals.documents.store
    @property
    def assets(self): return self.workspace.assets

    def enabled(self, row):
        # A stripped tag is corruption, never a downgrade to the old callback
        # proof. Check both durable owners and retained admission history.
        if any(key in row for key in ("model_asset_intent", "asset_archive", "asset_review_decision")):
            return True
        if any("model_asset_intent" in item for item in row.get("history", [])):
            return True
        execution = row.get("model_execution")
        if isinstance(execution, dict):
            if row.get("result_archive_contract") == ASSET_CONTRACT: return True
            try: return bool((self.runtime.manager.get(execution["job_id"]).adaptation_binding or {}).get("archive"))
            except KeyError: pass
        return False

    @staticmethod
    def binding(source_version):
        return AdaptationArchiveBinding(contract=ASSET_CONTRACT, execution_receipt_contract=CONTRACT,
            final_publication_contract=PUBLICATION_CONTRACT, source_proposal_version=source_version).model_dump()

    @staticmethod
    def limits():
        return {"contract": ASSET_CONTRACT, "mandatory": True, "actor_private": True,
            "raw_output_bytes": MAX_OUTPUT_BYTES, "prompt_bytes": MAX_PROMPT_BYTES,
            "request_bytes": MAX_REQUEST_BYTES, "receipt_bytes": MAX_BYTES,
            "metadata_bytes": MAX_METADATA_BYTES, "automatic_model_retry": False}

    def configured(self):
        if (self.workspace.creative is not self.proposals.documents or self.workspace.store is not self.store
                or self.runtime.broker.store is not self.store.store):
            raise ValueError("ADAPTATION_SHARED_ASSET_OWNER_REQUIRED")

    def intent(self, row):
        intent = row.get("model_asset_intent")
        keys = {"contract", "execution_receipt_contract", "final_publication_contract", "source_proposal_version",
                "job_id", "preview_digest"}
        if (not isinstance(intent, dict) or set(intent) != keys
                or intent["job_id"] != (row.get("model_execution") or {}).get("job_id")
                or intent["preview_digest"] != (row.get("model_preview") or {}).get("preview_digest")
                or type(intent["source_proposal_version"]) is not int
                or not 1 <= intent["source_proposal_version"] <= row["version"]):
            raise StaleSourceError("ADAPTATION_ARCHIVE_INTENT_CHANGED")
        binding = self.binding(intent["source_proposal_version"])
        if any(intent[key] != value for key, value in binding.items()):
            raise StaleSourceError("ADAPTATION_ARCHIVE_INTENT_CHANGED")
        return binding

    def source(self, ctx, rid, guard, state=None):
        self.configured(); guard(); self.runtime._flags()
        row = self.proposals._owned(ctx.novel_id, ctx.scope, ctx.actor, rid, state)
        self.proposals._current(ctx.novel_id, ctx.scope, row)
        self.intent(row)
        preview = row["model_preview"]
        ordered = row.get("source_mode") == "ORDERED_CHAPTERS"
        if ordered:
            sources = validate_ordered_sources(row["sources"], row["ordered_sources_digest"])
            if any(row[key] != sources[0][key] for key in
                    ("chapter_id", "source_version", "source_digest", "selection_digest", "selected_text")):
                raise StaleSourceError("ADAPTATION_ARCHIVE_SELECTION_CHANGED")
            validate_request(preview["request"], provider_id=preview["request"]["provider_id"],
                model_id=preview["request"]["model_id"], source={"schema_version": 2,
                    "sources": sources, "ordered_sources_digest": row["ordered_sources_digest"]})
        if (preview.get("preview_digest") != digest({key: value for key, value in preview.items() if key != "preview_digest"})
                or row["selection_digest"] != digest(row["selected_text"])
                or preview.get("selection_digest") != row["selection_digest"]
                or preview.get("input_digest") != (row["ordered_sources_digest"] if ordered else row["source_digest"])
                or preview.get("author", {}).get("source") != ("" if ordered else row["selected_text"])):
            raise StaleSourceError("ADAPTATION_ARCHIVE_SELECTION_CHANGED")
        if row["status"] == "CANCELLED" or (row.get("model_execution") or {}).get("status") in {"CANCELLED", "UNKNOWN"}:
            raise StaleSourceError("ADAPTATION_ARCHIVE_NO_VERIFIED_RESULT")
        return row

    def _key(self, row):
        return "adaptation-text:" + sha256(canonical([ASSET_CONTRACT, row["project_incarnation"], row["scope"],
            row["created_by"], row["id"], row["model_asset_intent"]]).encode()).hexdigest()

    def _origin_payload(self, row, version, job_id, output_digest, produced_at):
        ordered = row.get("source_mode") == "ORDERED_CHAPTERS"
        return {"schema_version": 2 if ordered else 1, "contract": ASSET_CONTRACT, "proposal_id": row["id"],
            "source_proposal_version": version, "chapter_id": row["chapter_id"], "source_version": row["source_version"],
            "source_digest": row["source_digest"], "selection_digest": row["selection_digest"],
            "job_id": job_id, "output_digest": output_digest,
            "preview_digest": row["model_preview"]["preview_digest"], "produced_at": produced_at,
            **({"sources": deepcopy(row["sources"]), "ordered_sources_digest": row["ordered_sources_digest"]} if ordered else {})}

    def parameters(self, row):
        return asset_parameters(row["model_preview"]["request"], row["model_preview"]["broker"]["chosen"])

    def validate_admission(self, row, source_version, deadline):
        self.configured()
        preview, sample = row["model_preview"], b"x"
        job_id, raw_digest = str(UUID(int=0)), sha256(sample).hexdigest()
        origin = self._origin_payload(row, source_version, job_id, raw_digest,
            datetime.max.replace(tzinfo=timezone.utc).isoformat())
        publication = {"schema_version": 1, "contract": PUBLICATION_CONTRACT,
            "job_id": job_id, "request_digest": "f" * 64, "output_digest": raw_digest}
        receipt = receipt_payload(preview["request"], preview["broker"]["chosen"], origin,
            execution_mode="mock_standin" if preview["allow_synthetic"] and preview["broker"]["chosen"]["synthetic"] else "real",
            request_digest="f" * 64, settlement_id="f" * 64, settlement_version=2**53 - 1,
            generation_bounds={"max_output_bytes": MAX_OUTPUT_BYTES, "deadline": deadline}, final_publication=publication)
        initial = self.assets.text_result_metadata(source_receipt=origin, provider_id=preview["request"]["provider_id"],
            model_id=preview["request"]["model_id"], source_job_id=job_id,
            parameters=self.parameters(row), execution_receipt=receipt)
        self.assets._text_initial(initial, sample)
        return receipt

    def job(self, row):
        try: job = self.runtime.manager.get(row["model_execution"]["job_id"])
        except KeyError: raise StaleSourceError("ADAPTATION_ORIGINAL_JOB_REQUIRED") from None
        from .adaptation_generation import AdaptationPublicationPending
        if not job.condition.acquire(blocking=False):
            raise AdaptationPublicationPending("ADAPTATION_TERMINAL_PUBLICATION_PENDING")
        try: return self._job_locked(row, job)
        finally: job.condition.release()

    def _job_locked(self, row, job):
        from ..repositories.generation_repository import graph_job_binding
        saved = self.runtime.manager.persistence.get(job.id)
        binding = AdaptationJobBinding(proposal_id=row["id"], project_id=row["novel_id"], actor_id=row["created_by"],
            scope=row["scope"], project_incarnation=row["project_incarnation"], chapter_id=row["chapter_id"],
            source_version=row["source_version"], source_digest=row["source_digest"],
            preview_digest=row["model_preview"]["preview_digest"], archive=self.intent(row),
            **({"sources": row["sources"], "ordered_sources_digest": row["ordered_sources_digest"]}
                if row.get("source_mode") == "ORDERED_CHAPTERS" else {})).model_dump(exclude_none=True)
        fields = ("id", "novel_id", "chapter_id", "actor_id", "session_id", "workspace_id", "scope", "operation",
            "experimental_origin", "required_experimental_features", "adaptation_binding", "adaptation_publication",
            "graph_binding", "expected_request_digest", "requested_provider", "requested_model", "provider", "model",
            "output", "status", "execution_outcome", "terminal_hook_status", "created_at", "updated_at", "execution_mode",
            "generation_max_output_bytes", "generation_deadline", "profile", "creation_records", "base_chapter_version",
            "base_chapter_digest", "author_input_digest", "request_scope", "source", "instruction", "style")
        if (not isinstance(saved, dict) or any(saved.get(key) != getattr(job, key, None) for key in fields)
                or graph_job_binding(saved) != binding or job.adaptation_binding != binding
                or any(getattr(job, key) != "COMPLETED" for key in ("status", "execution_outcome", "terminal_hook_status"))
                or job.adaptation_publication != terminal_publication(job)
                or job.profile != "LOCAL_ONLY" or job.generation_max_output_bytes != MAX_OUTPUT_BYTES
                or job.generation_deadline != row["model_execution"]["deadline"]
                or job.base_chapter_version != row["source_version"] or job.base_chapter_digest != row["source_digest"]
                or job.source != ("" if row.get("source_mode") == "ORDERED_CHAPTERS" else row["selected_text"])
                or job.cancelled.is_set()):
            raise StaleSourceError("ADAPTATION_DURABLE_PUBLICATION_REQUIRED")
        preview = row["model_preview"]
        from ..experimental.author_context_api import AuthorPreviewInput
        author = AuthorPreviewInput.model_validate(preview["author"])
        author_payload = author.model_dump(exclude={"preview_digest", "generation_request_id"})
        if (job.author_input_digest != digest([author_payload, (row["created_by"], row["scope"])])
                or job.instruction != author.instruction or job.style != author.style
                or (job.requested_provider, job.requested_model) != (author.provider_id, author.model_id)
                or job.request_scope != author.request_scope.model_dump(exclude_none=True)
                or job.dispatch_hooks_required is not True or job.generation_bound_failure is not None
                or set(job.required_experimental_features) != FEATURES):
            raise StaleSourceError("ADAPTATION_PASSIVE_AUTHOR_CHANGED")
        if (request_payload_digest(preview["request"], job, False) != job.expected_request_digest
                or (job.provider, job.model) != (preview["request"]["provider_id"], preview["request"]["model_id"])):
            raise StaleSourceError("ADAPTATION_PASSIVE_REQUEST_CHANGED")
        return job

    def ledger(self, row, job):
        preview, broker = row["model_preview"], self.runtime.broker
        decision = broker.get(row["novel_id"], row["scope"], broker.DECISIONS, preview["broker_preview_id"])
        check_version(decision, preview["broker_preview_version"])
        chosen = decision.get("chosen") or {}
        ledger = broker.get(row["novel_id"], row["scope"], broker.LEDGER, row["model_execution"]["reservation_id"])
        if (decision != preview["broker"] or decision.get("created_by") != row["created_by"]
                or decision.get("scope") != row["scope"] or decision.get("novel_id") != row["novel_id"]
                or decision.get("status") != "PREVIEW" or decision["request"]["allow_cloud_fallback"]
                or decision["request"]["profile"] != "LOCAL_ONLY"
                or ledger.get("created_by") != row["created_by"] or ledger.get("job_id") != job.id
                or ledger.get("scope") != row["scope"] or ledger.get("novel_id") != row["novel_id"]
                or ledger.get("status") != "SETTLED" or ledger.get("job_status") != "COMPLETED"
                or type(ledger.get("actual_microusd")) is not int or type(ledger.get("accounted_microusd")) is not int
                or type(ledger.get("version")) is not int or ledger["version"] < 1
                or ledger.get("price") != chosen.get("price")
                or ledger.get("cost_state") != zero_settlement_state(chosen.get("price"), job.usage)
                or ledger.get("actual_microusd") != 0 or ledger.get("accounted_microusd") != 0
                or ledger.get("dispatched") is not True or ledger.get("overrun") is not False
                or ledger.get("preview_id") != decision["id"]
                or ledger.get("authorization_digest") != preview["preview_digest"]
                or ledger.get("route_fingerprint") != chosen.get("fingerprint")
                or any(ledger.get(key) != chosen.get(key) for key in ("route_id", "provider_id", "model_id"))):
            raise StaleSourceError("ADAPTATION_SETTLED_RECEIPT_CHANGED")
        accounting = row["model_execution"].get("accounting")
        if accounting is not None and accounting != {key: ledger.get(key) for key in
                ("id", "version", "status", "cost_state", "actual_microusd", "accounted_microusd")}:
            raise StaleSourceError("ADAPTATION_ARCHIVE_ACCOUNTING_CHANGED")
        return ledger

    def evidence(self, row, job):
        ledger = self.ledger(row, job)
        origin = self._origin_payload(row, self.intent(row)["source_proposal_version"], job.id,
            sha256(job.output.encode()).hexdigest(), ledger["updated_at"])
        receipt = receipt_payload(row["model_preview"]["request"], row["model_preview"]["broker"]["chosen"], origin,
            execution_mode=job.execution_mode, request_digest=job.expected_request_digest, settlement_id=ledger["id"], settlement_version=ledger["version"],
            generation_bounds={"max_output_bytes": job.generation_max_output_bytes, "deadline": job.generation_deadline},
            final_publication=job.adaptation_publication)
        return origin, validate_receipt(receipt, source=origin, provider_id=job.provider,
            model_id=job.model, parameters=self.parameters(row))

    def route_guard(self, row):
        preview = row["model_preview"]
        decision = self.runtime.broker.get(row["novel_id"], row["scope"], self.runtime.broker.DECISIONS,
            preview["broker_preview_id"])
        # Completed archive recovery validates durable identity, not the old
        # process's adapter address. Live dispatch keeps Broker._assert_preview.
        chosen = decision["chosen"]
        route = self.runtime.broker.current_route(chosen["route_id"], local_text_only=True)
        if (decision != preview["broker"] or decision["created_by"] != row["created_by"]
                or decision["status"] != "PREVIEW"
                or decision["sources"] != self.runtime.broker._sources(row["novel_id"], row["scope"], decision["request"]["chapter_ids"])
                or not route["available"] or route["cloud"]
                or any(route.get(key) != chosen.get(key) for key in
                    ("route_id", "provider_id", "model_id", "fingerprint", "identity"))
                or not route["synthetic"] and not route.get("identity", {}).get("license_confirmed")):
            raise StaleSourceError("ADAPTATION_ARCHIVE_ROUTE_CHANGED")
        self.runtime.router.guard_route(route, synthetic_allowed=preview["allow_synthetic"])
        from ..model_execution import LocalModelInvocation
        from ..model_center.discovery_bridge import LocalTextAdapter
        invocation = LocalModelInvocation(self.runtime.broker.runtime, route["provider_id"], route["model_id"],
            synthetic_allowed=preview["allow_synthetic"])
        provider = invocation._provider
        registration = deepcopy(provider.bridge.guard(provider.candidate["id"])) if type(provider) is LocalTextAdapter else None
        config = None if registration is not None else (getattr(provider.provider, "delay_ms", None), getattr(provider.provider, "failure", None))
        def fresh():
            invocation.validate()
            if registration is not None:
                if provider.bridge.guard(provider.candidate["id"]) != registration:
                    raise StaleSourceError("ADAPTATION_ARCHIVE_ROUTE_CHANGED")
            elif config != (getattr(provider.provider, "delay_ms", None), getattr(provider.provider, "failure", None)):
                raise StaleSourceError("ADAPTATION_ARCHIVE_ROUTE_CHANGED")
        fresh()
        return fresh

    @contextmanager
    def lease(self, ctx, rid, guard):
        self.configured()
        with self.store.source_lease(ctx.novel_id, ctx.scope) as state:
            with self.workspace._asset_scope(ctx.novel_id, ctx.scope):
                yield self.source(ctx, rid, guard, state)
                guard()

    def ensure(self, ctx, rid, guard, *, create):
        row = self.source(ctx, rid, guard)
        route_guard = self.route_guard(row)
        with self.lease(ctx, rid, guard) as current:
            if row != current: raise StaleSourceError("ADAPTATION_ARCHIVE_SOURCE_CHANGED")
            job = self.job(current)
            origin, receipt = self.evidence(current, job)
            def fresh():
                guard(); route_guard()
                live = self.source(ctx, rid, guard)
                if live != current or self.evidence(live, self.job(live)) != (origin, receipt):
                    raise StaleSourceError("ADAPTATION_ARCHIVE_SOURCE_CHANGED")
            pointer = current.get("asset_archive")
            if pointer is not None:
                try:
                    asset = self.assets.get(pointer["asset_id"], branch_id=ctx.scope.get("branch_id"),
                        actor_id=ctx.actor, include_deleted=True)
                except FileNotFoundError:
                    # The proposal has already been authorized. Its unavailable
                    # private archive is a conflict, not a generic asset URL.
                    raise StaleSourceError("ADAPTATION_ARCHIVE_INCOMPLETE_OR_CHANGED") from None
                if asset.get("idempotency_key") != self._key(current):
                    raise StaleSourceError("ADAPTATION_ARCHIVE_IDENTITY_CHANGED")
            else:
                asset = self.assets.find_text_result(ctx.novel_id, self._key(current),
                    branch_id=ctx.scope.get("branch_id"), owner_actor_id=ctx.actor, proposal_id=rid)
            if asset is None and create:
                usage = self.assets.project_usage(ctx.novel_id, branch_id=ctx.scope.get("branch_id"))
                if usage["count"] >= self.workspace.MAX_ASSETS or usage["bytes"] + len(job.output.encode()) > self.workspace.MAX_PROJECT_BYTES:
                    raise ValueError("CREATIVE_PROJECT_ASSET_QUOTA")
                self.workspace.storage_admission.require(len(job.output.encode()))
                def before_commit():
                    fresh(); self.workspace.storage_admission.require(1)
                asset = self.assets.create_text_result(ctx.novel_id, "adaptation-" + rid + ".txt", job.output,
                    source_receipt=origin, provider_id=job.provider, model_id=job.model, source_job_id=job.id,
                    parameters=self.parameters(current), execution_receipt=receipt, idempotency_key=self._key(current),
                    branch_id=ctx.scope.get("branch_id"), owner_actor_id=ctx.actor, required_features=FEATURES, guard=before_commit)
            if (asset is None or asset.get("deleted_at") or asset.get("_text_result_origin") != origin
                    or asset.get("_text_execution_receipt") != receipt or asset.get("kind") != "text"
                    or asset.get("media_type") != "text/plain" or asset.get("source_job_id") != job.id
                    or asset.get("provider_id") != job.provider or asset.get("model_id") != job.model
                    or asset.get("parameters") != self.parameters(current)
                    or self.assets.content(asset["id"], branch_id=ctx.scope.get("branch_id"), actor_id=ctx.actor) != job.output.encode()):
                raise StaleSourceError("ADAPTATION_ARCHIVE_INCOMPLETE_OR_CHANGED")
            if (asset.get("_owner_actor_id") != ctx.actor
                    or set(asset.get("_required_features", [])) != FEATURES
                    or type(asset.get("version")) is not int):
                raise StaleSourceError("ADAPTATION_ARCHIVE_OWNER_CHANGED")
            review = asset.get("_text_result_review")
            if not isinstance(review, dict) or set(review) != {"status", "receipt", "history"}:
                raise StaleSourceError("ADAPTATION_ARCHIVE_REVIEW_CHANGED")
            if review["status"] == "DRAFT":
                if asset.get("version") != 1 or review != {"status": "DRAFT", "receipt": None, "history": []}:
                    raise StaleSourceError("ADAPTATION_ARCHIVE_REVIEW_CHANGED")
            elif review["status"] == "APPROVED":
                if (current["status"] != "APPROVED" or asset.get("version") != 2
                        or review["receipt"] != current.get("asset_review_decision")
                        or review["history"] != [{"status": "DRAFT", "asset_version": 1}]):
                    raise StaleSourceError("ADAPTATION_ARCHIVE_REVIEW_CHANGED")
            else:
                raise StaleSourceError("ADAPTATION_ARCHIVE_REVIEW_CHANGED")
            pointer = current.get("asset_archive")
            if pointer is not None and pointer != {"asset_id": asset["id"], "version": 1,
                    "receipt_digest": digest(receipt), "output_digest": origin["output_digest"]}:
                raise StaleSourceError("ADAPTATION_ARCHIVE_POINTER_CHANGED")
            if current["status"] in {"NEEDS_REVIEW", "APPROVED"} and pointer is None:
                raise StaleSourceError("ADAPTATION_ARCHIVE_POINTER_REQUIRED")
            fresh()
            return deepcopy(asset), deepcopy(current), origin, receipt, route_guard

    @contextmanager
    def phase(self, ctx, rid, guard, *, create=True):
        asset, row, origin, receipt, route_guard = self.ensure(ctx, rid, guard, create=create)
        proof = {"owner": self, "ctx": ctx, "id": rid, "incarnation": row["project_incarnation"],
            "origin": origin, "receipt": receipt, "guard": guard, "route_guard": route_guard, "asset": asset}
        token = _phase.set(proof)
        try: yield asset
        finally: _phase.reset(token)

    def authority(self, row):
        proof = _phase.get()
        if (not proof or proof["owner"] is not self or proof["id"] != row["id"]
                or proof["ctx"].actor != row["created_by"] or proof["ctx"].scope != row["scope"]
                or proof["incarnation"] != row["project_incarnation"]):
            raise StaleSourceError("ADAPTATION_ARCHIVE_AUTHORITY_REQUIRED")
        proof["guard"](); proof["route_guard"]()
        self.proposals._current(row["novel_id"], row["scope"], row)
        job = self.job(row)
        if self.evidence(row, job) != (proof["origin"], proof["receipt"]):
            raise StaleSourceError("ADAPTATION_ARCHIVE_RECEIPT_CHANGED")
        return proof

    def decision(self, row, document, reviewed_digest, reviewed_at):
        proof = self.authority(row)
        return {"contract": REVIEW_CONTRACT, "proposal_id": row["id"], "proposal_version": row["version"] + 1,
            "output_digest": proof["origin"]["output_digest"], "generated_output_digest": row["output_digest"],
            "reviewed_output_digest": reviewed_digest, "document_id": document["id"], "document_version": 1,
            "reviewed_by": row["created_by"], "reviewed_at": reviewed_at}

    def project(self, ctx, rid, guard, *, reconcile=True):
        asset, row, origin, receipt, route_guard = self.ensure(ctx, rid, guard, create=False)
        decision = row.get("asset_review_decision")
        if row["status"] == "APPROVED":
            if (not isinstance(decision, dict) or decision.get("document_id") != row.get("document_id")
                    or decision.get("proposal_version") != row["version"]
                    or decision.get("generated_output_digest") != row.get("output_digest")
                    or decision.get("reviewed_by") != row.get("reviewed_by")
                    or decision.get("reviewed_at") != row.get("reviewed_at")):
                raise StaleSourceError("ADAPTATION_ARCHIVE_REVIEW_CHANGED")
            if reconcile:
                with self.lease(ctx, rid, guard) as current:
                    if current != row: raise StaleSourceError("ADAPTATION_ARCHIVE_REVIEW_CHANGED")
                    def fresh():
                        guard(); route_guard()
                        live = self.source(ctx, rid, guard)
                        if live != current or self.evidence(live, self.job(live)) != (origin, receipt):
                            raise StaleSourceError("ADAPTATION_ARCHIVE_REVIEW_CHANGED")
                    asset = self.assets.review_text_result(asset["id"], actor_id=ctx.actor,
                        branch_id=ctx.scope.get("branch_id"), expected_version=asset["version"],
                        output_digest=origin["output_digest"], status="APPROVED", review_receipt=decision,
                        execution_receipt=receipt, guard=fresh)
        review = asset.get("_text_result_review", {})
        if row["status"] == "APPROVED" and (review.get("status") != "APPROVED" or review.get("receipt") != decision):
            raise StaleSourceError("ADAPTATION_ARCHIVE_REVIEW_PENDING")
        guard()
        return {"contract": ASSET_CONTRACT, "state": review.get("status"), "asset_id": asset["id"],
            "version": asset["version"], "sha256": asset["sha256"], "size": asset["size"],
            "created_at": asset["created_at"], "source": origin, "execution_receipt": public_receipt(receipt),
            "actor_private": True, "quality_verification": "NOT_RUN", "automatic_model_retry": False}

    @staticmethod
    def pending(state="PENDING", reason=None):
        return {"contract": ASSET_CONTRACT, "state": state, "asset_id": None, "version": None,
            "actor_private": True, "quality_verification": "NOT_RUN", "automatic_model_retry": False,
            **({"reason": reason} if reason else {})}

    def masked(self, row, reason="ADAPTATION_ARCHIVE_RECONCILIATION_REQUIRED"):
        result = self.proposals._public(row)
        result.update(output=None, output_digest=None, model_preview=None, provenance=None,
            asset_output=self.pending("INCOMPLETE", reason), unavailable_reason=reason)
        if row["status"] != "APPROVED": result["status"] = "MODEL_UNAVAILABLE"
        return result

    def pending_projection(self, row, state="PENDING"):
        result = self.masked(row, "ADAPTATION_TERMINAL_PUBLICATION_PENDING")
        if row["status"] == "GENERATING" and not row.get("output") and not row.get("asset_archive"):
            result["status"] = "GENERATING"
        result["asset_output"] = self.pending(state)
        return result

    def remember_failure(self, ctx, row):
        key = (ctx.novel_id, self.store.key(ctx.novel_id, ctx.scope), ctx.actor, row["project_incarnation"], row["id"])
        with self._lock:
            self._cooldowns[key] = time.monotonic() + 2
            self._cooldowns.move_to_end(key)
            while len(self._cooldowns) > 100: self._cooldowns.popitem(last=False)

    def can_reconcile(self, ctx, row):
        try:
            if self.runtime.manager.get(row["model_execution"]["job_id"]).status != "COMPLETED": return False
        except (KeyError, TypeError): return False
        key = (ctx.novel_id, self.store.key(ctx.novel_id, ctx.scope), ctx.actor, row["project_incarnation"], row["id"])
        with self._lock: return self._cooldowns.get(key, 0) <= time.monotonic()

    def forget_failure(self, ctx, row):
        key = (ctx.novel_id, self.store.key(ctx.novel_id, ctx.scope), ctx.actor, row["project_incarnation"], row["id"])
        with self._lock: self._cooldowns.pop(key, None)

    def read(self, ctx, rid, guard, *, reconcile=True, force=False):
        from .adaptation_generation import AdaptationPublicationPending
        row = self.proposals._owned(ctx.novel_id, ctx.scope, ctx.actor, rid)
        self.proposals._current(ctx.novel_id, ctx.scope, row); guard()
        result = self.proposals._public(row)
        if row["status"] == "CANCELLED":
            result.update(provenance=None, asset_output=self.pending("NO_ACCEPTED_RESULT"))
            return result
        key = (ctx.novel_id, self.store.key(ctx.novel_id, ctx.scope), ctx.actor, row["project_incarnation"], rid)
        try:
            self.source(ctx, rid, guard)
            job = self.runtime.manager.get(row["model_execution"]["job_id"])
            if job.status not in self.runtime.manager.terminal:
                if not callable(job.request_authorization): raise StaleSourceError("ADAPTATION_LIVE_AUTHORITY_REQUIRED")
                job.request_authorization()
                return self.pending_projection(row)
            if job.status != "COMPLETED":
                return self.pending_projection(row, "NO_ACCEPTED_RESULT")
            with self._lock:
                if not force and self._cooldowns.get(key, 0) > time.monotonic(): return self.masked(row)
            if row["status"] == "GENERATING":
                if not reconcile:
                    result["asset_output"] = self.pending()
                    return result
                result = self.runtime.refresh(ctx, rid, {"expected_version": row["version"]}, guard)
            else:
                with self.phase(ctx, rid, guard, create=False):
                    self.authority(row)
                    if row["status"] == "NEEDS_REVIEW": self.runtime.validate_result(ctx, row)
                result["asset_output"] = self.project(ctx, rid, guard, reconcile=reconcile)
            if (result.get("asset_output") or {}).get("state") == "INCOMPLETE":
                self.remember_failure(ctx, row)
            else:
                with self._lock: self._cooldowns.pop(key, None)
            guard()
            return result
        except AdaptationPublicationPending:
            guard()
            return self.pending_projection(row)
        except (ValueError, OSError, KeyError):
            guard()
            if reconcile: self.remember_failure(ctx, row)
            return self.masked(row)
