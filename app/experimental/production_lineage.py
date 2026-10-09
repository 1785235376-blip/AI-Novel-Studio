"""Asset DAG projections and immutable production evidence over existing owners.

AssetLibraryService owns assets/edges; MediaService owns execution and review.
This module stores manifests and replay pointers, never another asset library,
executor, approval flow, or budget. Export is a closed allowlist.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Literal

from pydantic import Field, model_validator

from ..source_privacy import source_privacy_status
from ..services.v1_capability_service import CapabilityVersionConflict
from .common import DomainService, StaleSourceError, check_version, new_row, now
from .media import StrictModel, RegisteredLocalImageWorkflowAdapter, digest, production_environment


class LicenseDeclaration(StrictModel):
    label: str = Field(default="UNSPECIFIED", min_length=1, max_length=160)
    source: str = Field(default="", max_length=2000)
    note: str = Field(default="", max_length=2000)


class LineageInput(StrictModel):
    expected_version: int = Field(ge=1)
    origin: Literal["ORIGINAL_INPUT", "GENERATED_RESULT", "DERIVED_PROCESSING", "EXTERNAL_IMPORT", "MANUAL_EDIT"]
    parent_asset_ids: list[str] = Field(default_factory=list, max_length=100)
    chapter_ids: list[str] = Field(default_factory=list, max_length=100)
    license: LicenseDeclaration = Field(default_factory=LicenseDeclaration)
    operation: str = Field(default="", max_length=160)

    @model_validator(mode="after")
    def lineage_kind(self):
        if self.origin in {"ORIGINAL_INPUT", "EXTERNAL_IMPORT"} and self.parent_asset_ids:
            raise ValueError("LINEAGE_ORIGINAL_CANNOT_HIDE_DERIVATION")
        if self.origin == "DERIVED_PROCESSING" and not self.parent_asset_ids:
            raise ValueError("LINEAGE_DERIVED_PARENT_REQUIRED")
        return self


class ManifestInput(StrictModel):
    task_id: str = Field(min_length=1, max_length=240)
    expected_task_version: int = Field(ge=1)


class ReplayInput(StrictModel):
    expected_version: int = Field(ge=1)
    preflight_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=120)
    broker_decision_id: str | None = Field(default=None, max_length=160)
    broker_decision_version: int | None = Field(default=None, ge=1)


class ProductionLineageService(DomainService):
    MANIFESTS = "production_manifests_v2"
    REPLAYS = "production_replays_v2"

    def __init__(self, store, novels, chapters, assets, media, *, broker=None, broker_enabled=None):
        super().__init__(store, novels, chapters)
        self.assets, self.media = assets, media
        self.change_impact = None
        self.broker, self.broker_enabled = broker, broker_enabled or (lambda: False)

    def _asset(self, nid, scope, aid, deleted=False):
        row = self.assets.get(aid, branch_id=scope.get("branch_id"), include_deleted=deleted)
        # The legacy local asset getter's None branch is a wildcard; this
        # projection always demands the exact authorized branch, including None.
        if row.get("novel_id") != nid or row.get("branch_id") != scope.get("branch_id"):
            raise FileNotFoundError(aid)
        return row

    def _asset_rows(self, nid, scope):
        self.novels.get(nid)
        return [r for r in self.assets.list(nid, branch_id=scope.get("branch_id"), include_deleted=True)
                if r.get("branch_id") == scope.get("branch_id")]

    def _chapters(self, nid, scope, ids):
        result = {}
        for cid in dict.fromkeys(ids):
            chapter = self.chapters_for(scope).get(cid)
            if chapter.get("novel_id") != nid or chapter.get("branch_id") != scope.get("branch_id"):
                raise FileNotFoundError(cid)
            result.update(self.sources(nid, [cid], scope))
        return result

    def annotate(self, nid, scope, actor, aid, value, guard=lambda: None, *, include_impact=True):
        body = LineageInput.model_validate(value)
        current = self._asset(nid, scope, aid)
        if current["version"] != body.expected_version:
            raise CapabilityVersionConflict(self._project_asset(nid, scope, current))
        sources = self._chapters(nid, scope, body.chapter_ids)
        for pid in body.parent_asset_ids:
            self._asset(nid, scope, pid)
        # Existing relationships may not be silently erased and relabelled as
        # original. A missing/deleted parent remains an explicit tombstone.
        if set(current.get("source_asset_ids", [])) - set(body.parent_asset_ids):
            raise ValueError("LINEAGE_EXISTING_PARENT_REMOVAL_NOT_SUPPORTED")
        guard()
        self._chapters(nid, scope, body.chapter_ids)
        self.assert_sources(nid, sources, scope)
        declaration = {"schema": "asset-lineage-v2", "origin": body.origin, "license": body.license.model_dump(),
                       "license_verification": "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION", "operation": body.operation,
                       "declared_by": actor, "declared_at": now(), "sources": sources}
        def before_commit():
            guard()
            self._asset(nid, scope, aid)
            self._chapters(nid, scope, body.chapter_ids)
            self.assert_sources(nid, sources, scope)
        try:
            self.assets.annotate_lineage(aid, declaration, body.parent_asset_ids, branch_id=scope.get("branch_id"),
                                        expected_version=body.expected_version, guard=before_commit)
        except CapabilityVersionConflict:
            raise CapabilityVersionConflict(self._project_asset(nid, scope, self._asset(nid, scope, aid))) from None
        guard()
        return self.asset(nid, scope, aid, include_impact=include_impact)

    def _project_asset(self, nid, scope, row):
        evidence = row.get("parameters", {}).get("asset_lineage_v2", {})
        if not isinstance(evidence, dict): evidence = {}
        legacy = row.get("parameters", {}).get("experimental_media_lineage", {})
        generation = None
        if self._visible_task(nid, scope, row.get("source_job_id")):
            task = self._task(nid, scope, row["source_job_id"])
            # Inherit existing R3 provenance only when the approved proposal
            # actually links this asset, not merely from a caller-supplied ID.
            try:
                proposal = self.media.get(nid, scope, self.media.PROPOSALS, legacy.get("proposal_id", ""))
                linked = (proposal["task_id"] == task["id"] and row["id"] in {proposal.get("asset_id"), proposal.get("promotion_asset_id")}
                          and legacy.get("source_digest") == task["source_digest"])
            except (FileNotFoundError, ValueError): linked = False
            if linked:
                generation = {"task_id": task["id"], "adapter_id": task["adapter_id"], "operation": task["operation"],
                              "candidate_count": task["candidate_count"], "input_digest": task["source_digest"],
                              "model_id": task["adapter_definition"].get("model_id"), "adapter_version": task["adapter_definition"].get("adapter_version"),
                              "workflow_version": (task.get("observed_environment") or {}).get("workflow_version"),
                              "seed": task.get("parameters", {}).get("seed"), "produced_at": proposal.get("created_at"),
                              "prompt_digest": digest(task["brief_snapshot"].get("prompt", "")),
                              "screenplay_id": task["brief_snapshot"].get("screenplay_id"), "shot_id": task["brief_snapshot"].get("shot_id"),
                              "scene_id": task["brief_snapshot"].get("shot_snapshot", {}).get("scene_id"),
                              "model_quality": "NOT_RUN"}
                if not evidence:
                    evidence = {"origin": "GENERATED_RESULT", "sources": task["sources"],
                                "parents": task["brief_snapshot"].get("asset_sources", {}), "operation": task["operation"]}
        parents = []
        for pid in row.get("source_asset_ids", []):
            try:
                parent = self._asset(nid, scope, pid, deleted=True)
            except (FileNotFoundError, ValueError):
                parents.append({"state": "UNAVAILABLE", "label": "来源不可用或无权访问"})
                continue
            expected = evidence.get("parents", {}).get(pid)
            state = "DELETED" if parent.get("deleted_at") else "UNVERIFIED" if expected is None else "CURRENT"
            if state == "CURRENT" and expected != {"version": parent["version"], "digest": parent["sha256"]}:
                state = "STALE"
            parents.append({"id": pid, "label": parent["filename"], "version": parent["version"],
                            "digest": parent["sha256"], "state": state})
        sources = []
        for cid, binding in evidence.get("sources", {}).items():
            try:
                actual = self._chapters(nid, scope, [cid])[cid]
                sources.append({"id": cid, **binding, "state": "CURRENT" if actual == binding else "STALE"})
            except (FileNotFoundError, ValueError):
                sources.append({"state": "UNAVAILABLE"})
        integrity = "DELETED" if row.get("deleted_at") else "VERIFIED"
        if integrity != "DELETED":
            try: self.assets.content(row["id"], branch_id=scope.get("branch_id"))
            except (FileNotFoundError, ValueError): integrity = "CONTENT_UNAVAILABLE"
        return {"id": row["id"], "label": row["filename"], "kind": row["kind"], "version": row["version"],
                "digest": row["sha256"], "deleted": bool(row.get("deleted_at")), "integrity": integrity,
                "origin": evidence.get("origin", "DERIVATION_UNDECLARED" if parents else "UNDECLARED"),
                "license": evidence.get("license", {"label": "UNSPECIFIED", "source": "", "note": ""}),
                "license_verification": "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION",
                "operation": evidence.get("operation", ""), "parents": parents, "sources": sources,
                "producer": {"declared_by": evidence.get("declared_by"), "provider_id": row.get("provider_id"),
                             "model_id": row.get("model_id")},
                "generation": generation,
                "declaration_history_versions": [r["asset_version"] for r in evidence.get("history", []) if isinstance(r, dict) and "asset_version" in r],
                "stale": integrity not in {"VERIFIED"} or any(p["state"] != "CURRENT" for p in parents + sources),
                "source_task_id": row.get("source_job_id") if self._visible_task(nid, scope, row.get("source_job_id")) else None}

    def _visible_task(self, nid, scope, task_id):
        if not task_id: return False
        try: self.media.get(nid, scope, self.media.TASKS, task_id); return True
        except (FileNotFoundError, ValueError): return False

    def assets_view(self, nid, scope):
        return {"items": [self._project_asset(nid, scope, r) for r in self._asset_rows(nid, scope)],
                "coverage": "EXISTING_ASSET_DAG_AND_MEDIA_REFERENCES", "inferred_dependencies": False}

    def asset(self, nid, scope, aid, *, include_impact=True):
        row = self._project_asset(nid, scope, self._asset(nid, scope, aid, deleted=True))
        if include_impact:
            row["impact"] = self.impact(nid, scope, aid)
        return row

    def impact(self, nid, scope, aid):
        self._asset(nid, scope, aid, deleted=True)
        rows = self._asset_rows(nid, scope)
        descendants, frontier = set(), {aid}
        while frontier:
            children = {r["id"] for r in rows if set(r.get("source_asset_ids", [])).intersection(frontier)} - descendants - {aid}
            descendants.update(children); frontier = children
        affected = descendants | {aid}
        briefs = [r for r in self.media.list(nid, scope, self.media.BRIEFS)
                  if set(r.get("asset_sources", {})).intersection(affected)]
        brief_ids = {r["id"] for r in briefs}
        tasks = [r for r in self.media.tasks(nid, scope) if r.get("brief_id") in brief_ids
                 or set(r.get("brief_snapshot", {}).get("asset_sources", {})).intersection(affected)]
        extra = []
        if self.media.screenplays is not None:
            for screenplay in self.media.screenplays.list(nid, branch_id=scope.get("branch_id")):
                if screenplay.get("branch_id") != scope.get("branch_id"): continue
                for collection in ("shots", "storyboard"):
                    for item in screenplay.get(collection, []):
                        if {item.get("asset_id"), item.get("frame_asset_id")}.intersection(affected):
                            extra.append({"kind": "SHOT_REFERENCE", "id": item["id"], "label": screenplay["id"],
                                          "version": screenplay.get("edit_version", 0)})
                for task in screenplay.get("motion_tasks", []):
                    refs = {str(task.get(key) or "").removeprefix("asset:") for key in ("start_frame", "end_frame")}
                    refs.add((task.get("result") or {}).get("asset_id"))
                    if refs.intersection(affected):
                        extra.append({"kind": "MOTION_TASK", "id": task["id"], "label": task.get("status", "UNKNOWN"),
                                      "version": screenplay.get("motion_task_revision", 0)})
        return {"assets": [{"id": r["id"], "label": r["filename"], "version": r["version"], "deleted": bool(r.get("deleted_at"))}
                           for r in rows if r["id"] in descendants],
                "usages": [{"kind": "MEDIA_BRIEF", "id": r["id"], "label": r.get("kind", "MEDIA"), "version": r["version"]} for r in briefs]
                          + [{"kind": "MEDIA_TASK", "id": r["id"], "label": r["status"], "version": r["version"]} for r in tasks] + extra,
                "coverage": "EXACT_RECORDED_ASSET_AND_MEDIA_DEPENDENCIES_ONLY", "other_dependencies": "UNKNOWN",
                "automatic_regeneration": False, "replacement_policy": "NEW_ASSET_AND_EXPLICIT_REVIEW_REQUIRED"}

    def _task(self, nid, scope, tid):
        return self.media.get(nid, scope, self.media.TASKS, tid)

    def _privacy(self, nid, scope, task):
        result = {"brief": task["brief_snapshot"].get("privacy_level", "LOCAL_ONLY"), "chapters": {}}
        for cid in task.get("sources", {}):
            self._chapters(nid, scope, [cid])
            state = source_privacy_status(self.chapters_for(scope).get(cid), scope.get("branch_id"), self.store.root)
            result["chapters"][cid] = {k: state[k] for k in ("privacy_level", "reviewed", "stale")}
        return result

    def _origin(self, nid, scope, task, guard=lambda: None):
        if task.get('benchmark_run_id'): raise ValueError('PRODUCTION_BENCHMARK_CAPTURE_NOT_SUPPORTED')
        if task.get('production_origin_refresh_id'):
            original = self._task(nid, scope, task['origin_media_task_id'])
        else: original = task
        if not original.get('change_impact_refresh_id'): return None
        if self.change_impact is None: raise ValueError('PRODUCTION_CHANGE_IMPACT_AUTHORITY_REQUIRED')
        return self.change_impact.manifest_origin(nid, scope, original, guard)

    def _visible_origin(self, nid, scope, row):
        if not row.get('origin'): return True
        try:
            self._task(nid, scope, row['task_id'])
            return True
        except (FileNotFoundError, ValueError): return False

    def get(self, nid, scope, collection, rid):
        row = super().get(nid, scope, collection, rid)
        if collection == self.MANIFESTS and not self._visible_origin(nid, scope, row): raise FileNotFoundError(rid)
        return row

    def list(self, nid, scope, collection):
        rows = super().list(nid, scope, collection)
        return [r for r in rows if self._visible_origin(nid, scope, r)] if collection == self.MANIFESTS else rows

    def capture(self, nid, scope, actor, value, guard=lambda: None):
        body = ManifestInput.model_validate(value)
        task = self._task(nid, scope, body.task_id)
        origin = self._origin(nid, scope, task, guard)
        if origin and task['created_by'] != actor: raise ValueError('PRODUCTION_CHANGE_IMPACT_OWNER_REQUIRED')
        check_version(task, body.expected_task_version)
        if task["status"] != "SUCCEEDED": raise ValueError("PRODUCTION_COMPLETED_TASK_REQUIRED")
        outputs = []
        for pid in task["proposal_ids"]:
            proposal = self.media.get(nid, scope, self.media.PROPOSALS, pid)
            content, _ = self.media.preview(nid, scope, pid)
            outputs.append({"proposal_id": pid, "candidate_index": proposal["candidate_index"],
                            "digest": hashlib.sha256(content).hexdigest(), "media_type": proposal["media"]["media_type"]})
        payload = {"schema": "production-manifest-v2", "status": "RECORDED", "task_id": task["id"],
                   "task_version": task["version"], "operation": task["operation"], "adapter": task["adapter_definition"],
                   "environment": task.get("observed_environment"), "input_digest": task["source_digest"],
                   "brief_id": task["brief_id"], "brief_version": task["brief_version"],
                   "sources": task["sources"], "asset_sources": task["brief_snapshot"].get("asset_sources", {}),
                   "seed": {"state": "RECORDED" if "seed" in task.get("parameters", {}) else "NOT_RECORDED", "value": task.get("parameters", {}).get("seed")},
                   "parameters": {"candidate_count": task["candidate_count"], **{k: v for k, v in task.get("parameters", {}).items() if k != "negative_prompt"},
                       **({"negative_prompt_digest": digest(task["parameters"]["negative_prompt"])} if "negative_prompt" in task.get("parameters", {}) else {})},
                   "parameter_digest": digest(task.get("parameters", {})), "configuration_diff": {},
                   **({"origin": origin} if origin else {}),
                   "outputs": outputs, "privacy_at_capture": self._privacy(nid, scope, task),
                   "prompt_storage": "EXISTING_PRIVATE_MEDIA_BRIEF_ONLY", "quality_verification": "NOT_EVALUATED"}
        payload["manifest_digest"] = digest(payload)
        guard()
        with self.store.transaction(nid, scope) as doc:
            guard()
            check_version(self._task(nid, scope, body.task_id), body.expected_task_version)
            if self._origin(nid, scope, task, guard) != origin: raise ValueError('PRODUCTION_ORIGIN_CHANGED')
            rows = doc["collections"].setdefault(self.MANIFESTS, {})
            old = next((r for r in rows.values() if r["manifest_digest"] == payload["manifest_digest"]), None)
            if old: return self._manifest_view(nid, scope, old)
            row = new_row(nid, scope, actor, payload); rows[row["id"]] = row
            return self._manifest_view(nid, scope, row)

    @staticmethod
    def assurance(row, replayable=None):
        """Evidence labels are independent; a seed is never a guarantee."""
        environment = row.get("environment") or {}
        synthetic = environment.get("deterministic") is True and environment.get("verification") == "SYNTHETIC_PROTOCOL_ONLY"
        return {"traceable": "RECORDED_INPUTS_AND_OUTPUT_DIGESTS",
                "replayable": "NOT_CHECKED" if replayable is None else "CURRENT_PREFLIGHT_PASSED" if replayable else "BLOCKED",
                "approximately_reproducible": "NOT_EVALUATED",
                "deterministically_reproducible": "SYNTHETIC_PROTOCOL_ONLY" if synthetic else "NOT_VERIFIED",
                "byte_equality": "REQUIRES_COMPLETED_REPLAY_COMPARISON",
                "seed_guarantees_identical_bytes": False, "model_quality": "NOT_EVALUATED"}

    def _manifest_view(self, nid, scope, row):
        # No prompt copy, private reference titles, local paths or arbitrary
        # adapter metadata are included in this API projection.
        return {k: copy.deepcopy(row[k]) for k in ("id", "version", "status", "created_at", "task_id", "task_version",
                "schema", "operation", "manifest_digest", "input_digest", "parameters", "seed", "outputs",
                "quality_verification")} | {"environment": copy.deepcopy(row.get("environment")),
                "adapter_id": row["adapter"]["adapter_id"], "model_id": row["adapter"].get("model_id"),
                "assurance": self.assurance(row), "verification": row["adapter"]["state"], "input_versions": self._input_versions(nid, scope, row)}

    def _input_versions(self, nid, scope, row):
        result = []
        for kind, sources in (("CHAPTER", row["sources"]), ("ASSET", row["asset_sources"])):
            for rid, binding in sources.items():
                try:
                    if kind == "CHAPTER": self._chapters(nid, scope, [rid])
                    else: self._asset(nid, scope, rid, deleted=True)
                    result.append({"kind": kind, "id": rid, **binding})
                except (FileNotFoundError, ValueError): result.append({"kind": kind, "state": "UNAVAILABLE"})
        return result

    def manifests(self, nid, scope):
        return {"items": [self._manifest_view(nid, scope, r) for r in self.list(nid, scope, self.MANIFESTS)]}

    def _dependencies(self, nid, scope, row):
        reasons, task, current_env, privacy = [], None, None, None
        try:
            task = self._task(nid, scope, row["task_id"])
            if (task["status"] != "SUCCEEDED" or task["source_digest"] != row["input_digest"]
                    or (row.get("parameter_digest") and digest(task.get("parameters", {})) != row["parameter_digest"])):
                reasons.append("SOURCE_TASK_CHANGED")
            self.media._current_brief(nid, scope, task)
            if self._origin(nid, scope, task) != row.get('origin'): reasons.append('ORIGIN_AUTHORITY_CHANGED')
            for aid in row["asset_sources"]:
                self._asset(nid, scope, aid)
                self.assets.content(aid, branch_id=scope.get("branch_id"))
            privacy = self._privacy(nid, scope, task)
            if privacy != row["privacy_at_capture"]: reasons.append("CURRENT_PRIVACY_CHANGED")
        except (FileNotFoundError, ValueError): reasons.append("SOURCE_CHANGED_OR_UNAVAILABLE")
        try:
            adapter = self.media.registry.resolve(row["adapter"]["adapter_id"], row["operation"])
            if adapter.definition.model_dump() != row["adapter"]: reasons.append("ADAPTER_OR_MODEL_CHANGED")
            current_env = production_environment(adapter)
            if not adapter.definition.local: reasons.append("FRESH_CLOUD_AUTHORIZATION_NOT_INTEGRATED")
            if type(adapter) is RegisteredLocalImageWorkflowAdapter and not self.broker_enabled():
                reasons.append("MODEL_BROKER_FEATURE_REQUIRED")
        except ValueError: reasons.append("CONFIGURED_ADAPTER_REQUIRED")
        if not row.get("environment"): reasons.append("ORIGINAL_RUNTIME_EVIDENCE_MISSING")
        elif row["environment"] != current_env: reasons.append("RUNTIME_OR_IMPLEMENTATION_CHANGED")
        if current_env and not current_env.get("model_digest"): reasons.append("EXACT_MODEL_IDENTITY_REQUIRED")
        # These manifests currently support the bounded existing image pipeline.
        # No arbitrary imported workflow can become executable through replay.
        try:
            for output in row["outputs"]:
                content, _ = self.media.preview(nid, scope, output["proposal_id"])
                if hashlib.sha256(content).hexdigest() != output["digest"]:
                    reasons.append("ORIGINAL_OUTPUT_CHANGED")
        except (FileNotFoundError, ValueError): reasons.append("ORIGINAL_OUTPUT_UNAVAILABLE")
        reasons = list(dict.fromkeys(reasons))
        state = {"manifest_digest": row["manifest_digest"], "environment": current_env, "privacy": privacy,
                 "input_digest": task["source_digest"] if task else None, "reasons": reasons,
                 "broker_required": bool(self.broker_enabled())}
        return reasons, state

    def _preflight_digest(self, actor, scope, state, broker_id, broker_version):
        return digest([actor, scope, state, broker_id, broker_version])

    def preflight(self, nid, scope, actor, rid, expected_version, guard=lambda: None):
        row = self.get(nid, scope, self.MANIFESTS, rid); check_version(row, expected_version); guard()
        reasons, state = self._dependencies(nid, scope, row)
        broker_id, broker_version, cost = None, None, {"state": "KNOWN_SYNTHETIC_ZERO" if not reasons else "UNAVAILABLE", "currency": "USD", "estimate_microusd": 0 if not reasons else None}
        if self.broker_enabled():
            if self.broker is None: reasons.append("MODEL_BROKER_NOT_CONFIGURED")
            elif not reasons:
                decision = self.broker.preview(nid, scope, actor, {"capability": "IMAGE", "policy": "CUSTOM", "profile": "LOCAL_ONLY",
                    "preferred_route": digest(["media", row["adapter"]["adapter_id"], row["adapter"].get("model_id")]),
                    "chapter_ids": list(row["sources"]), "allow_synthetic": bool(row.get("environment", {}).get("deterministic"))}, guard)
                broker_id, broker_version = decision["id"], decision["version"]
                if not decision.get("chosen"): reasons.append("MODEL_BROKER_NO_LEGAL_ROUTE")
                else:
                    chosen = decision["chosen"]
                    cost = {"state": chosen["cost_state"], "currency": "USD", "estimate_microusd": (chosen.get("price") or {}).get("reserve_microusd")}
        guard()
        _, after_state = self._dependencies(nid, scope, row)
        if after_state != state: raise StaleSourceError("PRODUCTION_PREFLIGHT_CHANGED_DURING_CHECK")
        return {"manifest_id": rid, "manifest_version": row["version"], "ready": not reasons, "blockers": reasons,
                "assurance": self.assurance(row, not reasons), "preflight_digest": self._preflight_digest(actor, scope, state, broker_id, broker_version),
                "broker_decision_id": broker_id, "broker_decision_version": broker_version, "cost": cost,
                "states": {"traceable": not any(r in reasons for r in ("SOURCE_CHANGED_OR_UNAVAILABLE", "SOURCE_TASK_CHANGED")),
                    "rebuildable": bool(row.get("environment")) and bool(row["environment"].get("deterministic") or (row["environment"].get("registration") or {}).get("runtime_version")) and not any(r in reasons for r in ("RUNTIME_OR_IMPLEMENTATION_CHANGED", "EXACT_MODEL_IDENTITY_REQUIRED", "CONFIGURED_ADAPTER_REQUIRED")),
                    "replayable": not reasons, "deterministic": bool(row.get("environment", {}).get("deterministic")) if row.get("environment") else False,
                    "byte_equal": None},
                "authorization": "CURRENT_REQUEST_ONLY_NEW_TASK_REQUIRES_EXPLICIT_ACTION", "automatic_retry": False,
                "verification": row.get("environment", {}).get("verification", "HISTORICAL_EVIDENCE_INCOMPLETE") if row.get("environment") else "HISTORICAL_EVIDENCE_INCOMPLETE"}

    def _assert_replay(self, nid, scope, actor, row, value, guard):
        guard()
        reasons, state = self._dependencies(nid, scope, row)
        if reasons: raise StaleSourceError("PRODUCTION_REPLAY_BLOCKED:" + ",".join(reasons))
        expected = self._preflight_digest(actor, scope, state, value.broker_decision_id, value.broker_decision_version)
        if expected != value.preflight_digest: raise StaleSourceError("PRODUCTION_PREFLIGHT_CHANGED")
        if self.broker_enabled() and (not self.broker or not value.broker_decision_id):
            raise ValueError("PRODUCTION_FRESH_BROKER_PREFLIGHT_REQUIRED")
        if self.broker_enabled():
            decision = self.broker.get(nid, scope, self.broker.DECISIONS, value.broker_decision_id)
            check_version(decision, value.broker_decision_version)
            current = self.broker._assert_preview(nid, scope, actor, decision)
            if current.get("adapter_id") != row["adapter"]["adapter_id"] or current.get("model_id") != row["adapter"].get("model_id"):
                raise ValueError("PRODUCTION_BROKER_ROUTE_MISMATCH")

    def replay(self, nid, scope, actor, rid, value, guard=lambda: None):
        body = ReplayInput.model_validate(value)
        row = self.get(nid, scope, self.MANIFESTS, rid); check_version(row, body.expected_version)
        self._assert_replay(nid, scope, actor, row, body, guard)
        key = digest([actor, body.idempotency_key]); fingerprint = digest([rid, body.model_dump()])
        with self.store.transaction(nid, scope) as doc:
            self._assert_replay(nid, scope, actor, row, body, guard)
            rows = doc["collections"].setdefault(self.REPLAYS, {})
            old = next((r for r in rows.values() if r["idempotency_digest"] == key), None)
            if old:
                if old["request_digest"] != fingerprint: raise ValueError("PRODUCTION_IDEMPOTENCY_CONFLICT")
                return self._replay_view(nid, scope, old)
            replay = new_row(nid, scope, actor, {"manifest_id": rid, "idempotency_digest": key, "request_digest": fingerprint,
                "request": body.model_dump(), "status": "LINKED", "broker_required": bool(self.broker_enabled()), "reservation_id": None})
            task = self.media.prepare_task(nid, scope, actor, {"brief_id": row["brief_id"], "expected_brief_version": row["brief_version"],
                "adapter_id": row["adapter"]["adapter_id"], "candidate_count": row["parameters"]["candidate_count"],
                "parameters": copy.deepcopy(self._task(nid, scope, row["task_id"]).get("parameters", {}))},
                origin_guard=(lambda brief: self._assert_replay(nid, scope, actor, row, body, guard)) if row.get('origin') else None)
            if row.get('origin'):
                original = self._task(nid, scope, row['task_id'])
                task.update(production_origin_refresh_id=row['origin']['refresh_id'],
                    origin_media_task_id=original.get('origin_media_task_id', original['id']))
            task.update(production_replay_id=replay["id"], production_manifest_id=rid)
            replay["task_id"] = task["id"]
            doc["collections"].setdefault(self.media.TASKS, {})[task["id"]] = task; rows[replay["id"]] = replay
        # No dispatch here. The new task is durable and discoverable even if a
        # process exits before budget reservation; explicit execute can recover.
        return self._replay_view(nid, scope, replay)

    def _replay_view(self, nid, scope, row):
        task = self._task(nid, scope, row["task_id"])
        manifest = self.get(nid, scope, self.MANIFESTS, row["manifest_id"])
        outputs = []
        for pid in task.get("proposal_ids", []):
            p = self.media.get(nid, scope, self.media.PROPOSALS, pid)
            try:
                content, _ = self.media.preview(nid, scope, pid)
                verified = hashlib.sha256(content).hexdigest() == p["content_sha256"]
            except (FileNotFoundError, ValueError): verified = False
            outputs.append({"proposal_id": pid, "candidate_index": p["candidate_index"], "digest": p["content_sha256"],
                            "status": p["status"], "integrity": "VERIFIED" if verified else "CONTENT_UNAVAILABLE"})
        same = None
        if task["status"] == "SUCCEEDED" and outputs and all(r["integrity"] == "VERIFIED" for r in outputs):
            same = [(r["candidate_index"], r["digest"]) for r in outputs] == [(r["candidate_index"], r["digest"]) for r in manifest["outputs"]]
        recoverable = next((r.get("recoverable", False) for r in self.media.tasks(nid, scope) if r["id"] == task["id"]), False)
        return {"id": row["id"], "version": row["version"], "manifest_id": row["manifest_id"], "task_id": task["id"],
                "task_version": task["version"], "status": task["status"], "created_at": row["created_at"],
                "byte_equal": same, "outputs": outputs, "recoverable": recoverable,
                "recovery": "NEW_PREFLIGHT_AND_NEW_TASK_REQUIRED" if recoverable or task["status"] == "FAILED"
                    or any(r["integrity"] != "VERIFIED" for r in outputs) else None,
                "reservation_id": row.get("reservation_id"), "broker_required": row["broker_required"],
                "review_feature": "cover_storyboard_generation", "automatic_approval": False,
                "synthetic": bool((manifest.get("environment") or {}).get("deterministic"))}

    def replays(self, nid, scope, actor):
        result = []
        for row in self.list(nid, scope, self.REPLAYS):
            if row['created_by'] != actor: continue
            try: result.append(self._replay_view(nid, scope, row))
            except (FileNotFoundError, ValueError): continue
        return {'items': result}

    def execute_replay(self, nid, scope, actor, rid, expected_task_version, guard=lambda: None):
        replay = self.get(nid, scope, self.REPLAYS, rid)
        if replay["created_by"] != actor: raise FileNotFoundError(rid)
        manifest = self.get(nid, scope, self.MANIFESTS, replay["manifest_id"])
        request = ReplayInput.model_validate(replay["request"])
        def current():
            self._assert_replay(nid, scope, actor, manifest, request, guard)
        current()
        task = self._task(nid, scope, replay["task_id"]); check_version(task, expected_task_version)
        if task["status"] != "QUEUED": raise ValueError("PRODUCTION_REPLAY_NOT_QUEUED")
        reservation_id = replay.get("reservation_id")
        if replay["broker_required"]:
            reservation = self.broker.reserve(nid, scope, actor, request.broker_decision_id, request.broker_decision_version,
                "production:" + replay["id"], task["id"], current)
            reservation_id = reservation["id"]
            with self.store.transaction(nid, scope) as doc:
                current()
                doc["collections"][self.REPLAYS][rid]["reservation_id"] = reservation_id
        def dispatch(actual_task, adapter):
            current()
            if actual_task["id"] != task["id"]: raise ValueError("PRODUCTION_TASK_BINDING_CHANGED")
            if reservation_id:
                self.broker.guard_dispatch(nid, scope, actor, reservation_id, task["id"], current)
            latest = self._task(nid, scope, task["id"])
            if (latest["status"] != "RUNNING" or latest["version"] != actual_task["version"]
                    or latest.get("execution_token") != actual_task.get("execution_token")):
                raise ValueError("PRODUCTION_REPLAY_CANCELLED_OR_CHANGED")
        try:
            self.media.execute(nid, scope, actor, task["id"], expected_task_version, current, production_guard=dispatch)
        finally:
            if reservation_id:
                status = self._task(nid, scope, task["id"])["status"]
                # A concurrent click that loses the media task claim must not
                # close the winning invocation's budget while it is running.
                if status not in {"QUEUED", "RUNNING"}:
                    self.broker.finalize(nid, scope, actor, reservation_id, task["id"],
                        {"SUCCEEDED": "COMPLETED", "FAILED": "FAILED", "CANCELLED": "CANCELLED"}.get(status, "UNKNOWN"))
        guard()
        return self._replay_view(nid, scope, self.get(nid, scope, self.REPLAYS, rid))

    def cancel_replay(self, nid, scope, actor, rid, version, guard=lambda: None):
        row = self.get(nid, scope, self.REPLAYS, rid)
        if row["created_by"] != actor: raise FileNotFoundError(rid)
        guard()
        self.media.transition(nid, scope, actor, row["task_id"], "cancel", version)
        reservation_id = row.get("reservation_id")
        if not reservation_id and row["broker_required"] and self.broker:
            # A process may exit after the shared ledger commits but before
            # our pointer checkpoint. Explicit cancellation still releases a
            # never-dispatched hold instead of orphaning the project budget.
            candidate = digest([actor, "production:" + row["id"]])
            try:
                entry = self.broker.get(nid, scope, self.broker.LEDGER, candidate)
                if entry.get("job_id") == row["task_id"] and entry.get("created_by") == actor:
                    reservation_id = candidate
            except FileNotFoundError:
                pass
        if reservation_id:
            self.broker.finalize(nid, scope, actor, reservation_id, row["task_id"], "CANCELLED")
        return self._replay_view(nid, scope, row)

    def export(self, nid, scope, rid):
        row = self.get(nid, scope, self.MANIFESTS, rid)
        # No free-form strings from user/model/runtime configuration cross this
        # boundary. Identities become digests; fields/enum values are fixed.
        env = row.get("environment") or {}
        return {"schema": "production-public-manifest-v2", "manifest_digest": row["manifest_digest"],
                "input_digest": row["input_digest"], "app_version_digest": digest(env.get("app_version")),
                "runtime_digest": digest(env.get("runtime")), "adapter_identity_digest": digest(row["adapter"]),
                "model_identity_digest": digest(env.get("model_id")), "model_digest": env.get("model_digest"),
                "adapter_digest": env.get("adapter_digest"), "workflow_digest": env.get("workflow_digest"),
                "workflow_version_digest": digest(env.get("workflow_version")),
                "input_versions": [{"version": binding["version"], "digest": binding["digest"]} for group in (row["sources"], row["asset_sources"]) for binding in group.values()],
                "seed": {"state": "RECORDED" if type((row.get('seed') or {}).get('value')) is int else "NOT_RECORDED",
                         "value": row['seed']['value'] if type((row.get('seed') or {}).get('value')) is int else None},
                "parameters": {k: row['parameters'][k] for k in ('candidate_count', 'width', 'height', 'steps', 'seed') if type(row['parameters'].get(k)) is int},
                "parameters_digest": digest(row['parameters']), "configuration_diff_digest": digest(row["configuration_diff"]),
                "outputs": [{"candidate_index": r["candidate_index"], "digest": r["digest"]} for r in row["outputs"]],
                "deterministic": bool(env.get("deterministic")), "byte_equal": None,
                "redaction": {"raw_prompts": False, "source_text": False, "credentials": False, "paths": False, "asset_ids": False},
                "assurance": self.assurance(row), "quality_verified": False, "license_verified": False}
