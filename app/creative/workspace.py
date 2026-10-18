"""Independent studio adapters over the original project, asset and lineage owners.

No project, asset, version, queue or model registry is introduced here. The
scope document stores only presentation preferences. Binary metadata and its
versions remain exclusively owned by AssetLibraryService.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from contextlib import contextmanager, nullcontext
import shutil
import errno
import re

from ..experimental.common import change_row, new_row, now
from ..experimental.production_lineage import LicenseDeclaration
from ..media_files import inspect_image, inspect_media
from ..services.v1_capability_service import CapabilityVersionConflict
from .project_store import BINDING
from .workspace_models import ManualModelReferenceImport, ManualAssetImport, ManualBinaryMask, StudioLineageInput, WorkspacePreferences, WorkspacePreferencesUpdate

PREFERENCES = "creative_project_preferences_v2"
FLAG = "narrative_production_v2"


class IndependentWorkspaceService:
    MAX_ASSETS = 1000
    MAX_PROJECT_BYTES = 512 * 1024 * 1024
    MAX_PREFERENCE_HISTORY = 200

    def __init__(self, creative, assets, lineage):
        self.creative, self.assets, self.lineage = creative, assets, lineage
        self.store, self.novels = creative.store, creative.novels
        from .workspace_relationships import AssetRelationshipAdapter
        self.relationships = AssetRelationshipAdapter(self)
        from .storage_admission import StudioStorageAdmission
        self.storage_admission = StudioStorageAdmission(self)

    @staticmethod
    def _preferences(document):
        rows = list(document["collections"].get(PREFERENCES, {}).values())
        if len(rows) > 1:
            raise ValueError("CREATIVE_PREFERENCES_CORRUPT")
        if rows:
            row = rows[0]
            if (row.get("novel_id") != document["novel_id"] or row.get("scope") != document["scope"]
                    or type(row.get("version")) is not int or row["version"] < 1
                    or not isinstance(row.get("history"), list)):
                raise ValueError("CREATIVE_PREFERENCES_CORRUPT")
            WorkspacePreferences.model_validate({key: row.get(key) for key in WorkspacePreferences.model_fields})
        return rows[0] if rows else None

    # The preference wire projection stays frozen at the fields every existing client
    # already decodes. CONTENT_POLICY_FRAMEWORK: RESERVED is deliberately NOT on the
    # wire yet (no UI, no filter, no export change); it is read through the typed
    # helpers in `app/creative/content_policy.py`. Freezing the list here is also what
    # keeps a row written before the field existed from raising KeyError.
    PREFERENCE_VIEW_FIELDS = ("intents", "preset", "custom_intent")

    @staticmethod
    def _preference_view(row):
        defaults = WorkspacePreferences().model_dump()
        fields = IndependentWorkspaceService.PREFERENCE_VIEW_FIELDS
        if not row:
            return {"version": 0, **{key: copy.deepcopy(defaults[key]) for key in fields}}
        return {"version": row["version"],
                **{key: copy.deepcopy(row.get(key, defaults[key])) for key in fields}}

    def project(self, nid, scope):
        self.store.key(nid, scope)
        # Scope -> owner is the established lease order. Capture the overview
        # and opaque marker together so durable client drafts cannot rebind a
        # reused public ID to a different project incarnation.
        document = self.store.read(nid, scope)
        with self.store.owner_lease(nid) as incarnation:
            project = self.novels.get(nid)
            row = self._preferences(document)
            if row is not None and row.get(BINDING) != incarnation:
                row = None
        return {"project": {"id": project["id"], "title": project["title"],
                            "incarnation": incarnation,
                            "entry_kind": row.get("entry_kind", "LEGACY") if row else "LEGACY"},
                "preferences": self._preference_view(row),
                "capabilities": {"manual_import": True, "manual_export": True,
                    "model_required": False, "chapter_required": False,
                    "media_validator_configured": bool(shutil.which("ffprobe") and shutil.which("ffmpeg")),
                    "asset_kinds": ["image", "video", "audio"], "intent_is_permission": False}}

    def activate(self, nid, scope, actor, guard=lambda: None):
        """Explicitly open this authorized scope in the neutral studio.

        This saved presentation receipt is independent of intent and does not
        change the original project kind, permissions, manuscript or modules.
        """
        with self.store.transaction(nid, scope) as document:
            row = self._preferences(document)
            guard()
            if row is None:
                row = new_row(nid, scope, actor, {**WorkspacePreferences().model_dump(),
                    "entry_kind": "NEUTRAL_STUDIO", BINDING: self.store.incarnation(nid)})
                document["collections"].setdefault(PREFERENCES, {})[row["id"]] = row
            elif row.get("entry_kind") != "NEUTRAL_STUDIO":
                if len(row["history"]) >= self.MAX_PREFERENCE_HISTORY:
                    raise ValueError("CREATIVE_PREFERENCE_HISTORY_LIMIT")
                change_row(row, actor, row["version"], lambda current: current.update(entry_kind="NEUTRAL_STUDIO"))
            guard()
        return self.project(nid, scope)

    def preferences(self, nid, scope, actor, value, guard=lambda: None):
        body = WorkspacePreferencesUpdate.model_validate(value)
        payload = body.model_dump(exclude={"expected_version"})
        # CONTENT_POLICY_FRAMEWORK: RESERVED — an omitted (null) policy means "unchanged",
        # so an unrelated preference edit can never silently reset a saved policy.
        if payload.get("content_policy") is None:
            payload.pop("content_policy", None)
        self.store.key(nid, scope)
        with self.store.transaction(nid, scope) as document:
            row = self._preferences(document)
            actual = row["version"] if row else 0
            if body.expected_version != actual:
                raise CapabilityVersionConflict({"version": actual})
            if row is not None and len(row["history"]) >= self.MAX_PREFERENCE_HISTORY:
                raise ValueError("CREATIVE_PREFERENCE_HISTORY_LIMIT")
            guard()
            if row is None:
                row = new_row(nid, scope, actor, {**payload, BINDING: self.store.incarnation(nid)})
                document["collections"].setdefault(PREFERENCES, {})[row["id"]] = row
            else:
                change_row(row, actor, actual, lambda current: current.update(payload))
            guard()
            return self._preference_view(row)

    @contextmanager
    def _asset_scope(self, nid, scope):
        key = self.store.key(nid, scope)
        # Never read/write ExperimentalStore under this lease: scope->owner is
        # its established order. Asset lineage callbacks use asset->owner.
        with self.assets.project_scope(nid, scope.get("branch_id"), lambda: self.store.owner_lease(nid), scope_key=key):
            yield

    def _row(self, nid, scope, aid, *, deleted=False, actor_id=None):
        row = self.assets.get(aid, branch_id=scope.get("branch_id"), include_deleted=deleted, actor_id=actor_id)
        if row["novel_id"] != nid or row.get("branch_id") != scope.get("branch_id"):
            raise FileNotFoundError(aid)
        # Legacy metadata is permissive; the new CAS surface must never adopt
        # a corrupted/coerced counter as an authoritative asset revision.
        if type(row.get("version")) is not int or row["version"] < 1:
            raise ValueError("CREATIVE_ASSET_VERSION_INVALID")
        # M1 only accepts manual uploads. Do not read a media task/scope store
        # under an asset-owner lease if an unsupported record reaches here.
        if row.get("source_job_id"):
            origin = row.get("_studio_result_origin")
            if (not isinstance(origin, dict) or origin.get("contract") != "studio-production-result/1"
                    or origin.get("job_id") != row["source_job_id"]
                    or origin.get("scope_key") != self.store.key(nid, scope)
                    or origin.get("incarnation") != row.get("_project_binding", {}).get("incarnation")
                    or not row.get("_origin_provenance")):
                raise ValueError("CREATIVE_ASSET_ADAPTER_REQUIRED")
        return row

    def _view(self, nid, scope, row):
        public = self.assets.public(row)
        if isinstance(public.get("parameters"), dict):
            # Only current scoped projections disclose source/relationship IDs.
            public["parameters"].pop("asset_lineage_v2", None)
        provenance = self._production_provenance(nid, scope, row) if row.get("_studio_result_origin") else self.lineage.asset(nid, scope, row["id"], include_impact=False)
        if "_manual_mask_origin" in row:
            origin = self.assets._manual_record(row)
            public["manual_mask"] = {"contract": origin["contract"],
                "source_asset_id": origin["source"]["id"], "source_version": origin["source"]["version"],
                "source_sha256": origin["source"]["sha256"],
                **{key: origin[key] for key in ("width", "height", "bitplane_sha256", "keep_pixels", "remove_pixels", "mask_sha256")}}
        if "_model_reference_origin" in row:
            origin = self.assets._model_reference_record(row)
            public["model_reference"] = {"contract": origin["contract"], "diagnostic_only": True,
                "source_asset_id": origin["source"]["id"], "source_version": origin["source"]["version"],
                "source_sha256": origin["source"]["sha256"],
                **{key: origin[key] for key in ("width", "height", "yaw", "pitch", "png_sha256", "scene_index")}}
        if "_video_reference_origin" in row:
            from ..services.studio_video_reference_origin import project
            public["video_reference"] = project(self.assets._video_reference_record(row))
        return {**public,
                "provenance": provenance,
                "relationships": self.relationships.project(nid, scope, row)}

    def _production_provenance(self, nid, scope, row):
        """Project the immutable original asset origin without reading a job store
        under the asset/project lease. Document freshness stays unverified here;
        execution and review recheck it through their original source owner.
        """
        origin = row["_studio_result_origin"]
        self._production_asset_ids(origin)
        declaration = self._production_declaration(row)
        parents, sources = [], []
        for source in origin.get("sources", []):
            if source["kind"] != "ASSET":
                sources.append({"id": source["id"], "version": source["version"], "digest": source["digest"], "state": "UNVERIFIED"})
                continue
            try:
                parent = self._row(nid, scope, source["id"], deleted=True)
                state = "DELETED" if parent.get("deleted_at") else "CURRENT" if (parent["version"], parent["sha256"]) == (source["version"], source["digest"]) else "STALE"
                parents.append({"id": parent["id"], "label": parent["filename"], "version": parent["version"], "digest": parent["sha256"], "state": state})
            except (FileNotFoundError, ValueError):
                parents.append({"state": "UNAVAILABLE", "label": "来源不可用或无权访问"})
        integrity = "DELETED" if row.get("deleted_at") else "VERIFIED"
        if integrity != "DELETED":
            try: self.assets._verified_content(row)
            except (FileNotFoundError, ValueError): integrity = "CONTENT_UNAVAILABLE"
        return {"id": row["id"], "label": row["filename"], "kind": row["kind"], "version": row["version"],
                "digest": row["sha256"], "deleted": bool(row.get("deleted_at")), "integrity": integrity,
                "origin": self._production_origin(origin),
                "license": copy.deepcopy(declaration["license"]) if declaration else {"label": "UNSPECIFIED", "source": "", "note": origin.get("license_note", "")},
                "license_verification": "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION",
                "operation": declaration["operation"] if declaration else origin["operation_id"], "parents": parents, "sources": sources,
                "stale": any(p["state"] != "CURRENT" for p in parents + sources),
                "source_task_id": origin["job_id"], "generation": None,
                "reference_only": True, "product_acceptance": "LOCAL_REQUIRED"}

    @staticmethod
    def _production_origin(origin):
        return "DERIVED_PROCESSING" if origin["operation_id"] in {"m5.image.cutout", "m8.audio.trim", "m9.timeline.multitrack"} else "GENERATED_RESULT"

    @staticmethod
    def _production_asset_ids(origin):
        # This is an asset-metadata check, never a source/job owner lookup.
        # A malformed marker must not silently remove deletion protection.
        if (not isinstance(origin, dict) or origin.get("contract") != "studio-production-result/1"
                or not isinstance(origin.get("operation_id"), str) or not origin["operation_id"]
                or not isinstance(origin.get("sources"), list)):
            raise ValueError("CREATIVE_PRODUCTION_ORIGIN_INVALID")
        if any(not isinstance(source, dict) or not isinstance(source.get("kind"), str)
               or source["kind"] not in {"ASSET", "CREATIVE_DOCUMENT", "COMIC_PANEL"}
               or not isinstance(source.get("id"), str) or not source["id"]
               for source in origin["sources"]):
            raise ValueError("CREATIVE_PRODUCTION_ORIGIN_INVALID")
        if any(source["kind"] == "COMIC_PANEL" for source in origin["sources"]):
            from .production_contracts import ProductionSourceSnapshot
            if len(origin["sources"]) != 1 or origin["operation_id"] != "m5.image.t2i" or "graph_binding" in origin:
                raise ValueError("CREATIVE_PRODUCTION_COMIC_ORIGIN_INVALID")
            source = ProductionSourceSnapshot.model_validate(origin["sources"][0])
            if any(getattr(source.comic_panel, key) != origin.get(key) for key in ("actor", "scope_key", "incarnation")):
                raise ValueError("CREATIVE_PRODUCTION_COMIC_ORIGIN_INVALID")
        return list(dict.fromkeys(source["id"] for source in origin["sources"] if source["kind"] == "ASSET"))

    def _production_declaration(self, row):
        """Read only the original owner's compatible author declaration.

        Its parent revisions describe the annotation; execution provenance and
        freshness above remain bound to the immutable production snapshots.
        A legacy annotation cannot relabel this result or mint chapter sources.
        """
        origin = row["_studio_result_origin"]
        parameters = row.get("parameters")
        evidence = parameters.get("asset_lineage_v2") if isinstance(parameters, dict) else None
        parent_ids = self._production_asset_ids(origin)
        if (not isinstance(evidence, dict) or evidence.get("schema") != "asset-lineage-v2"
                or evidence.get("origin") != self._production_origin(origin)
                or evidence.get("output_digest") != row["sha256"] or evidence.get("sources") != {}
                or evidence.get("license_verification") != "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION"
                or not isinstance(evidence.get("parents"), dict) or set(evidence["parents"]) != set(parent_ids)
                or not isinstance(row.get("source_asset_ids"), list)
                or any(not isinstance(parent, str) for parent in row["source_asset_ids"])
                or set(row["source_asset_ids"]) != set(parent_ids)
                or len(row["source_asset_ids"]) != len(parent_ids)
                or not isinstance(evidence.get("operation"), str) or len(evidence["operation"]) > 160
                or not isinstance(evidence.get("license"), dict) or set(evidence["license"]) != set(LicenseDeclaration.model_fields)):
            return None
        if any(not isinstance(binding, dict) or set(binding) != {"version", "digest"}
               or type(binding["version"]) is not int or binding["version"] < 1
               or not isinstance(binding["digest"], str) or not re.fullmatch(r"[a-f0-9]{64}", binding["digest"])
               for binding in evidence["parents"].values()):
            return None
        try:
            license_value = LicenseDeclaration.model_validate(evidence["license"]).model_dump()
        except (ValueError, TypeError):
            return None
        return {"license": license_value, "operation": evidence["operation"]}

    def list_assets(self, nid, scope, *, include_deleted=False):
        with self._asset_scope(nid, scope):
            rows = self.assets.list(nid, branch_id=scope.get("branch_id"), include_deleted=include_deleted)
            return {"items": [self._view(nid, scope, self._row(nid, scope, row["id"], deleted=include_deleted)) for row in rows]}

    def asset_index(self, nid, scope, *, include_deleted=False):
        """Bounded metadata-only asset index under the original asset lease.

        A workflow aggregate must not open one lineage/relationship read per
        asset, so this returns only fields an aggregate may use. Bytes, lineage,
        relationship targets and every per-asset decision stay behind the
        per-asset owners above. Review state is reported only from an owner-stored
        marker (``_text_result_review``); media candidate review is job-level and
        deliberately not invented here.
        """
        with self._asset_scope(nid, scope):
            rows = self.assets.list(nid, branch_id=scope.get("branch_id"), include_deleted=include_deleted)
            return [self._index_row(nid, scope, row) for row in rows]

    @staticmethod
    def _index_row(nid, scope, row):
        if row.get("novel_id") != nid or row.get("branch_id") != scope.get("branch_id"):
            raise FileNotFoundError(row.get("id"))
        review = row.get("_text_result_review")
        status = review.get("status") if isinstance(review, dict) else None
        job = row.get("source_job_id")
        kind = row.get("kind")
        return {"id": row["id"], "kind": kind if isinstance(kind, str) and kind else "other",
                "version": row.get("version"),
                "review_status": status if status in {"DRAFT", "APPROVED", "REJECTED"} else None,
                "source_job_id": job if isinstance(job, str) and job else None,
                "deleted": bool(row.get("deleted_at")), "created_at": row.get("created_at")}

    def asset(self, nid, scope, aid, *, include_deleted=False):
        with self._asset_scope(nid, scope):
            return self._view(nid, scope, self._row(nid, scope, aid, deleted=include_deleted))

    def import_asset(self, nid, scope, actor, value, guard=lambda: None):
        body = ManualAssetImport.model_validate(value)
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (ValueError, TypeError):
            raise ValueError("CREATIVE_ASSET_BASE64_INVALID") from None
        if not data or len(data) > self.assets.MAX_BYTES:
            raise ValueError("CREATIVE_ASSET_SIZE_INVALID")
        # Decode bounded local bytes before acquiring persistence locks. This
        # neither contacts a provider nor loads a model nor trusts MIME labels.
        measured = inspect_image(data) if body.kind == "image" else inspect_media(data, body.kind, guard=guard)
        return self._persist_manual_import(nid, scope, actor, body, data, measured["media_type"], guard)

    def import_model_reference(self, nid, scope, actor, value, guard=lambda: None):
        from .model_reference_glb import inspect_static_glb
        body = ManualModelReferenceImport.model_validate(value)
        if not body.filename.lower().endswith(".glb"):
            raise ValueError("MODEL_REFERENCE_GLB_FILENAME_REQUIRED")
        guard()
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (ValueError, TypeError):
            raise ValueError("MODEL_REFERENCE_GLB_BASE64_INVALID") from None
        inspect_static_glb(data)
        guard()
        return self._persist_manual_import(nid, scope, actor, body, data, "model/gltf-binary", guard)

    def inspect_model_reference(self, nid, scope, aid, guard=lambda: None, *, mesh_preview=False, scene_preview=False, material_inspection=False, camera_inspection=False):
        # Camera observation must never provision a missing File identity. The
        # pre-existing geometry paths keep their original owner admission.
        lease = self.store.existing_owner_only() if camera_inspection is True else nullcontext()
        with lease:
            return self._inspect_model_reference(nid, scope, aid, guard, mesh_preview=mesh_preview,
                scene_preview=scene_preview, material_inspection=material_inspection, camera_inspection=camera_inspection)

    def _inspect_model_reference(self, nid, scope, aid, guard, *, mesh_preview, scene_preview, material_inspection, camera_inspection):
        from .model_reference_glb import MAX_BYTES, inspect_static_glb
        from ..experimental.common import StaleSourceError
        guard()
        with self._asset_scope(nid, scope):
            incarnation = self.store.incarnation(nid)
            row = self._row(nid, scope, aid)
            if row.get("kind") != "model" or row.get("media_type") != "model/gltf-binary":
                raise ValueError("MODEL_REFERENCE_GLB_ASSET_REQUIRED")
            snapshot = {"id": row["id"], "kind": "ASSET", "asset_kind": "model", "version": row["version"], "digest": row["sha256"]}
            _, data = self.pinned_content(nid, scope, snapshot, max_bytes=MAX_BYTES, guard=guard)
        if (any(type(v) is not bool for v in (mesh_preview, scene_preview, material_inspection, camera_inspection))
                or sum((mesh_preview, scene_preview, material_inspection, camera_inspection)) > 1):
            raise ValueError("MODEL_REFERENCE_GLB_PREVIEW_OPTION_INVALID")
        parsed = (inspect_static_glb(data, include_cameras=True) if camera_inspection else
                  inspect_static_glb(data, include_materials=True) if material_inspection else
                  inspect_static_glb(data, include_geometry=True, include_scene=True) if scene_preview else
                  inspect_static_glb(data, include_geometry=True) if mesh_preview else inspect_static_glb(data))
        inspection = parsed["inspection"] if mesh_preview or scene_preview or material_inspection or camera_inspection else parsed
        guard()
        with self._asset_scope(nid, scope):
            current = self._row(nid, scope, aid)
            if (self.store.incarnation(nid) != incarnation or current.get("media_type") != "model/gltf-binary"
                    or (current["version"], current["sha256"], current["kind"]) != (snapshot["version"], snapshot["digest"], "model")):
                raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
            guard()
        return {"asset_snapshot": snapshot, "inspection": inspection,
                **({"mesh_preview": parsed["mesh_preview"]} if mesh_preview else {}),
                **({"scene_preview": parsed["scene_preview"]} if scene_preview else {}),
                **({"material_inspection": parsed["material_inspection"]} if material_inspection else {}),
                **({"camera_inspection": parsed["camera_inspection"]} if camera_inspection else {})}

    def export_model_camera(self, nid, scope, aid, value, guard=lambda: None):
        """Read-only canonical camera exchange from an exact formal GLB source."""
        from .workspace_models import StaticCameraExport
        body = StaticCameraExport.model_validate(value)
        with self.store.existing_owner_only():
            return self._export_model_camera(nid, scope, aid, body, guard)

    def _export_model_camera(self, nid, scope, aid, body, guard):
        from .model_reference_cameras import export_camera
        from ..experimental.common import StaleSourceError
        guard()
        with self._asset_scope(nid, scope):
            incarnation = self.store.incarnation(nid)
            row = self._row(nid, scope, aid)
            if (row["version"], row["sha256"]) != (body.source_version, body.source_sha256):
                raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
        inspected = self.inspect_model_reference(nid, scope, aid, guard, camera_inspection=True)
        pin = inspected["asset_snapshot"]
        if (pin["version"], pin["digest"]) != (body.source_version, body.source_sha256):
            raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
        data, proof = export_camera(inspected["camera_inspection"], pin, scene_index=body.scene_index,
                                   node_index=body.node_index, camera_index=body.camera_index)
        encoded = base64.b64encode(data).decode("ascii")
        guard()
        with self._asset_scope(nid, scope):
            row = self._row(nid, scope, aid)
            if (self.store.incarnation(nid) != incarnation or row.get("kind") != "model"
                    or row.get("media_type") != "model/gltf-binary"
                    or (row["version"], row["sha256"]) != (body.source_version, body.source_sha256)):
                raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
            guard()
        return {"asset_snapshot": pin, "camera_export": proof, "content_base64": encoded}

    def preview_video_reference(self, nid, scope, aid, value, guard):
        from .video_reference import VideoReferencePreparation
        return VideoReferencePreparation(self).preview(nid, scope, aid, value, guard)

    def save_video_reference(self, nid, scope, actor, aid, value, guard):
        from .video_reference import VideoReferencePreparation
        return VideoReferencePreparation(self).save(nid, scope, actor, aid, value, guard)

    def export_model_depth(self, nid, scope, aid, value, guard=lambda: None):
        from .workspace_models import StaticSceneDepthExport
        from .model_reference_depth import render_depth
        body = StaticSceneDepthExport.model_validate(value)
        return self._export_model_diagnostic(nid,scope,aid,body,render_depth,"depth_export",guard)

    def export_model_clay(self, nid, scope, aid, value, guard=lambda: None):
        from .workspace_models import StaticSceneClayExport
        from .model_reference_depth import render_clay
        body = StaticSceneClayExport.model_validate(value)
        return self._export_model_diagnostic(nid,scope,aid,body,render_clay,"clay_export",guard)

    def save_model_clay_reference(self, nid, scope, actor, aid, value, guard):
        """Explicit reviewed clay pixels become one original image Asset."""
        from .workspace_models import StaticSceneClaySave
        from ..services.studio_model_reference_origin import CONTRACT
        from ..services.asset_library_service import AssetIdempotencyConflict
        from ..experimental.common import StaleSourceError
        body = StaticSceneClaySave.model_validate(value)
        if not callable(guard) or not isinstance(actor, str) or not actor:
            raise ValueError("MODEL_REFERENCE_AUTHORITY_REQUIRED")
        guard()
        scope_key = self.store.key(nid, scope)
        key = 'studio-clay-reference:' + hashlib.sha256(json.dumps([scope_key, body.idempotency_key], separators=(',', ':')).encode()).hexdigest()
        with self._asset_scope(nid, scope):
            incarnation = self.store.incarnation(nid)
            observed = self.assets.model_reference_retry(nid, key, branch_id=scope.get("branch_id"))
            observed_id = observed["id"] if observed else None
        exported = self.export_model_clay(nid, scope, aid, {
            "contract":"studio-static-glb-clay-export/1", "source_version":body.source_version,
            "source_sha256":body.source_sha256, "yaw":body.yaw, "pitch":body.pitch}, guard)
        proof = exported["clay_export"]
        if proof["png_sha256"] != body.reviewed_png_sha256:
            raise StaleSourceError("MODEL_REFERENCE_REVIEWED_PIXELS_CHANGED")
        png = base64.b64decode(exported["content_base64"], validate=True)
        origin = {"contract":CONTRACT, "actor":actor, "scope_key":scope_key, "incarnation":incarnation,
            "source":{"id":aid,"version":body.source_version,"sha256":body.source_sha256},
            **{k:proof[k] for k in ("width","height","yaw","pitch","png_sha256","scene_index")}}
        with self._asset_scope(nid, scope):
            if self.store.incarnation(nid) != incarnation:
                raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
            source = self.assets._model_reference_source(origin, nid, scope.get("branch_id"))
            prior = self.assets.model_reference_retry(nid, key, branch_id=scope.get("branch_id"))
            if observed_id is not None and (prior is None or prior["id"] != observed_id):
                raise ValueError("MODEL_REFERENCE_RETRY_CHANGED")
            if prior is not None and prior.get("_model_reference_origin") != origin:
                raise AssetIdempotencyConflict("MODEL_REFERENCE_IDEMPOTENCY_CONFLICT")
            usage = self.assets.project_usage(nid, branch_id=scope.get("branch_id"))
            if prior is None:
                if usage["count"] >= self.MAX_ASSETS or usage["bytes"] + len(png) > self.MAX_PROJECT_BYTES:
                    raise ValueError("CREATIVE_PROJECT_ASSET_QUOTA")
                self.storage_admission.require(len(png))
            def before_commit():
                guard()
                if self.store.incarnation(nid) != incarnation: raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
                self.assets._model_reference_source(origin, nid, scope.get("branch_id"))
                if prior is None: self.storage_admission.require(1)
            features = tuple(sorted({FLAG, "asset_lineage_v2", *source.get("_required_features", [])}))
            try:
                row = self.assets.create(nid, 'model-clay-reference.png', exported["content_base64"], 'image/png', 'image', key,
                    branch_id=scope.get("branch_id"), required_features=features, guard=before_commit,
                    _initial_model_reference=origin, _model_reference_expected_retry_id=prior["id"] if prior else None)
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    from .storage_admission import StudioStorageCapacityError
                    raise StudioStorageCapacityError("CREATIVE_STORAGE_LOW_SPACE") from None
                raise
            before_commit()
            return {"asset":self._view(nid,scope,row), "receipt":{"contract":CONTRACT,
                "source_asset_id":aid, "source_version":body.source_version, "source_sha256":body.source_sha256,
                "png_sha256":proof["png_sha256"], "replayed":prior is not None, "model_called":False,
                "diagnostic_only":True, "asset_created":prior is None}}

    def _export_model_diagnostic(self, nid, scope, aid, body, renderer, proof_key, guard):
        from ..experimental.common import StaleSourceError
        guard()
        with self._asset_scope(nid, scope):
            incarnation = self.store.incarnation(nid)
            row = self._row(nid, scope, aid)
            if (row["version"], row["sha256"]) != (body.source_version, body.source_sha256):
                raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
        inspected = self.inspect_model_reference(nid, scope, aid, guard, scene_preview=True)
        pin = inspected["asset_snapshot"]
        if (pin["version"], pin["digest"]) != (body.source_version, body.source_sha256):
            raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
        count = 0
        def checkpoint():
            nonlocal count
            count += 1
            if count % 32 == 0: guard()
        guard()
        png, proof = renderer(inspected["scene_preview"], body.yaw, body.pitch, checkpoint=checkpoint)
        guard()
        with self._asset_scope(nid, scope):
            row = self._row(nid, scope, aid)
            if (self.store.incarnation(nid) != incarnation
                    or (row["version"], row["sha256"]) != (body.source_version, body.source_sha256)):
                raise StaleSourceError("MODEL_REFERENCE_SOURCE_CHANGED")
            guard()
        return {"asset_snapshot": pin, proof_key: proof, "content_base64": base64.b64encode(png).decode("ascii")}

    def _persist_manual_import(self, nid, scope, actor, body, data, media_type, guard):
        # Shared original asset owner, admission and idempotency for bounded manual imports.
        guard()
        with self._asset_scope(nid, scope):
            rows = self.assets.list(nid, branch_id=scope.get("branch_id"), include_deleted=True)
            retry = any(row.get("idempotency_key") == body.idempotency_key for row in rows)
            usage = self.assets.project_usage(nid, branch_id=scope.get("branch_id"))
            if not retry and (usage["count"] >= self.MAX_ASSETS or usage["bytes"] + len(data) > self.MAX_PROJECT_BYTES):
                raise ValueError("CREATIVE_PROJECT_ASSET_QUOTA")
            guard()
            if not retry:
                self.storage_admission.require(len(data))
            def before_commit():
                guard()
                if not retry:
                    # The staging file already exists now. Preserve the reserve
                    # without pretending its bytes still need allocating twice.
                    self.storage_admission.require(1)
            try:
                row = self.assets.create(nid, body.filename, body.content_base64, media_type, body.kind,
                    body.idempotency_key, branch_id=scope.get("branch_id"), required_features=(FLAG,), guard=before_commit)
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    from .storage_admission import StudioStorageCapacityError
                    raise StudioStorageCapacityError("CREATIVE_STORAGE_LOW_SPACE") from None
                raise
            guard()
            return self._view(nid, scope, row)

    def annotate(self, nid, scope, actor, aid, value, guard=lambda: None):
        body = StudioLineageInput.model_validate(value)
        with self._asset_scope(nid, scope):
            row = self._row(nid, scope, aid)
            if "_manual_mask_origin" in row:
                origin = self.assets._manual_record(row)
                if body.origin != "MANUAL_EDIT" or body.chapter_ids or body.parent_asset_ids != [origin["source"]["id"]]:
                    raise ValueError("IMAGE_MASK_SOURCE_IMMUTABLE")
            if "_model_reference_origin" in row:
                origin = self.assets._model_reference_record(row)
                if body.origin != "MANUAL_EDIT" or body.chapter_ids or body.parent_asset_ids != [origin["source"]["id"]]:
                    raise ValueError("MODEL_REFERENCE_SOURCE_IMMUTABLE")
            if "_video_reference_origin" in row:
                origin = self.assets._video_reference_record(row)
                if body.origin != "MANUAL_EDIT" or body.chapter_ids or body.parent_asset_ids != [origin["source"]["id"]]:
                    raise ValueError("VIDEO_REFERENCE_SOURCE_IMMUTABLE")
            if row.get("_studio_result_origin"):
                origin = copy.deepcopy(row["_studio_result_origin"])
                parent_ids = self._production_asset_ids(origin)
                if (body.origin != self._production_origin(origin) or body.chapter_ids
                        or len(body.parent_asset_ids) != len(parent_ids) or set(body.parent_asset_ids) != set(parent_ids)):
                    raise ValueError("CREATIVE_PRODUCTION_SOURCE_DECLARATION_IMMUTABLE")
                if row["version"] != body.expected_version:
                    raise CapabilityVersionConflict({"version": row["version"]})
                # Keep the original lineage metadata shape. Only license and
                # operation are author declarations; source IDs are fixed by
                # the original job, and document bindings stay in its marker.
                declaration = {"schema": "asset-lineage-v2", "origin": self._production_origin(origin),
                    "license": body.license.model_dump(), "license_verification": "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION",
                    "operation": body.operation, "declared_by": actor, "declared_at": now(), "sources": {}}
                def before_commit():
                    guard()
                    current = self._row(nid, scope, aid)
                    if current["version"] != body.expected_version:
                        raise CapabilityVersionConflict({"version": current["version"]})
                    if current["_studio_result_origin"] != origin or current["sha256"] != row["sha256"]:
                        raise ValueError("CREATIVE_PRODUCTION_ORIGIN_CHANGED")
                    for parent_id in parent_ids: self._row(nid, scope, parent_id)
                self.assets.annotate_lineage(aid, declaration, parent_ids, branch_id=scope.get("branch_id"),
                    expected_version=body.expected_version, guard=before_commit)
            else:
                self.lineage.annotate(nid, scope, actor, aid, body, guard, include_impact=False)
            guard()
            return self._view(nid, scope, self._row(nid, scope, aid))

    def author_mask(self, nid, scope, actor, source_id, value, guard):
        """One original-Asset creation; no job, model or second annotation write."""
        from ..experimental.common import StaleSourceError
        from ..services.studio_image_mask_authoring import CONTRACT, SOURCE_MAX_BYTES, encode_mask, validate_source_png
        from ..services.asset_library_service import AssetIdempotencyConflict
        body = ManualBinaryMask.model_validate(value)
        if not callable(guard) or not isinstance(actor, str) or not actor:
            raise ValueError("IMAGE_MASK_AUTHORITY_REQUIRED")
        guard()
        scope_key = self.store.key(nid, scope)
        key = 'studio-manual-mask:' + hashlib.sha256(json.dumps([scope_key, body.idempotency_key], separators=(',', ':')).encode()).hexdigest()

        def source_current():
            row = self._row(nid, scope, source_id)
            if (row["kind"], row["media_type"], row["version"], row["sha256"]) != ('image', 'image/png', body.source_version, body.source_sha256):
                raise StaleSourceError("IMAGE_MASK_SOURCE_STALE")
            if not 0 < row["size"] <= SOURCE_MAX_BYTES:
                raise ValueError("IMAGE_MASK_SOURCE_LIMIT")
            view = self._view(nid, scope, row)
            if view["provenance"]["integrity"] != "VERIFIED" or view["provenance"]["stale"]:
                raise StaleSourceError("IMAGE_MASK_SOURCE_STALE")
            return row

        with self._asset_scope(nid, scope):
            source = source_current()
            data = self.assets.content(source_id, branch_id=scope.get("branch_id"))
            observed = self.assets.manual_mask_retry(nid, key, branch_id=scope.get("branch_id"))
            observed_id = observed["id"] if observed else None
            incarnation = self.store.incarnation(nid)
            guard(); source_current()
        callbacks = 0
        def sampled_guard():
            nonlocal callbacks
            callbacks += 1
            if callbacks % 64 == 0: guard()
        guard()
        validate_source_png(data, body.width, body.height, checkpoint=sampled_guard)
        guard()
        png, proof = encode_mask(body.width, body.height, body.bitplane_base64, checkpoint=sampled_guard)
        guard()
        origin = {"contract": CONTRACT, "actor": actor, "scope_key": scope_key, "incarnation": incarnation,
                  "source": {"id": source_id, "version": body.source_version, "sha256": body.source_sha256}, **proof}
        with self._asset_scope(nid, scope):
            if self.store.incarnation(nid) != incarnation:
                raise StaleSourceError("IMAGE_MASK_SOURCE_STALE")
            source = source_current()
            prior = self.assets.manual_mask_retry(nid, key, branch_id=scope.get("branch_id"))
            if observed_id is not None and (prior is None or prior["id"] != observed_id):
                raise ValueError("IMAGE_MASK_RETRY_CHANGED")
            if prior is not None and prior.get("_manual_mask_origin") != origin:
                raise AssetIdempotencyConflict("IMAGE_MASK_IDEMPOTENCY_CONFLICT")
            usage = self.assets.project_usage(nid, branch_id=scope.get("branch_id"))
            if prior is None:
                if usage["count"] >= self.MAX_ASSETS or usage["bytes"] + len(png) > self.MAX_PROJECT_BYTES:
                    raise ValueError("CREATIVE_PROJECT_ASSET_QUOTA")
                self.storage_admission.require(len(png))
            def before_commit():
                guard(); source_current()
                if prior is None: self.storage_admission.require(1)
            features = tuple(sorted({FLAG, "asset_lineage_v2", *source.get("_required_features", [])}))
            try:
                row = self.assets.create(nid, "manual-mask.png", base64.b64encode(png).decode('ascii'), 'image/png', 'image', key,
                    branch_id=scope.get("branch_id"), required_features=features, guard=before_commit,
                    _initial_manual_mask=origin, _manual_expected_retry_id=prior["id"] if prior else None)
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    from .storage_admission import StudioStorageCapacityError
                    raise StudioStorageCapacityError("CREATIVE_STORAGE_LOW_SPACE") from None
                raise
            before_commit()
            result = {"asset": self._view(nid, scope, row), "receipt": {"contract": CONTRACT,
                "source_asset_id": source_id, "source_version": body.source_version, "source_sha256": body.source_sha256, **proof}}
            guard(); source_current()
            return result

    def download(self, nid, scope, aid, guard=lambda: None):
        with self._asset_scope(nid, scope):
            row = self._row(nid, scope, aid)
            data = self.assets.content(aid, branch_id=scope.get("branch_id"))
            guard()
            return self.assets.public(row), data

    def pinned_content(self, nid, scope, snapshot, *, max_bytes, guard=lambda: None):
        """Read one formal source inside the caller's original asset phase.

        This deliberately does not acquire another asset scope or inspect media.
        AssetLibraryService enforces the already active incarnation binding.
        """
        from ..experimental.common import StaleSourceError
        binding = getattr(self.assets._scope, "binding", None)
        if (binding is None or binding.get("novel_id") != nid
                or binding.get("branch_id") != scope.get("branch_id")
                or binding.get("scope_key") != self.store.key(nid, scope)):
            raise ValueError("CREATIVE_ASSET_PHASE_REQUIRED")
        guard()
        row = self._row(nid, scope, snapshot["id"])
        if (row.get("_owner_actor_id") or (row["version"], row["sha256"], row["kind"]) !=
                (snapshot["version"], snapshot["digest"], snapshot["asset_kind"])):
            raise StaleSourceError("STUDIO_TIMELINE_SOURCE_CHANGED")
        if type(row.get("size")) is not int or not 0 < row["size"] <= max_bytes:
            raise ValueError("ASSET_BOUNDED_READ_LIMIT")
        data = self.assets.content(row["id"], branch_id=scope.get("branch_id"), max_bytes=max_bytes, guard=guard)
        guard()
        return row, data

    def lifecycle(self, nid, scope, aid, expected_version, *, restore=False, guard=lambda: None, actor_id=None):
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("CREATIVE_EXPECTED_VERSION_INVALID")
        if actor_id is not None and (not isinstance(actor_id, str) or not actor_id):
            raise ValueError("CREATIVE_AUTHORITY_INVALID")
        # This adapter adds private prompt deletion only. The existing restore
        # surface still cannot reopen private revisions or revive their body.
        visibility_actor = actor_id if not restore else None
        with self._asset_scope(nid, scope):
            row = self._row(nid, scope, aid, deleted=True, actor_id=visibility_actor)
            if row.get("_owner_actor_id") and row.get("kind") != "prompt":
                raise FileNotFoundError(aid)
            if row["version"] != expected_version:
                raise CapabilityVersionConflict({"version": row["version"]})
            if not restore:
                rows = {other["id"]: other for other in self.assets.list(nid, branch_id=scope.get("branch_id"))}
                if actor_id is not None:
                    # Private candidates are deliberately absent from ordinary
                    # library discovery. Count the current server actor's active
                    # candidates without exposing them or adopting another actor.
                    rows.update({other["id"]: other for other in self.assets.list(nid, branch_id=scope.get("branch_id"), actor_id=actor_id)})
                children = [other for other in rows.values()
                            if aid in other.get("source_asset_ids", []) or (
                                other.get("_studio_result_origin") is not None
                                and aid in self._production_asset_ids(other["_studio_result_origin"])) or any(
                                not relation.get("removed_at") and relation["target"]["kind"] == "ASSET"
                                and relation["target"]["id"] == aid for relation in self.relationships.records(other))]
                if children:
                    raise ValueError("CREATIVE_ASSET_IN_USE")
            guard()
            if restore:
                self.assets.restore(aid, branch_id=scope.get("branch_id"), guard=guard)
            else:
                self.assets.delete(aid, branch_id=scope.get("branch_id"), guard=guard, actor_id=visibility_actor)
            guard()
            current = self._row(nid, scope, aid, deleted=True, actor_id=visibility_actor)
            if current.get("_owner_actor_id") and current.get("kind") == "prompt":
                # The row has just passed the original owner's actor and
                # incarnation checks. Reuse its lineage projection without an
                # anonymous re-read that would fail after deletion committed.
                public = self.assets.public(current)
                if isinstance(public.get("parameters"), dict):
                    public["parameters"].pop("asset_lineage_v2", None)
                return {**public, "provenance": self.lineage._project_asset(nid, scope, current),
                        "relationships": self.relationships.project(nid, scope, current)}
            return self._view(nid, scope, current)

    def storage(self, nid, scope):
        with self._asset_scope(nid, scope):
            rows = self.assets.list(nid, branch_id=scope.get("branch_id"), include_deleted=True)
            active = [row for row in rows if not row.get("deleted_at")]
            admission = self.storage_admission.view(self.MAX_PROJECT_BYTES - sum(row["size"] for row in rows))
            return {"assets": {"count": len(active), "bytes": sum(row["size"] for row in active)},
                    "trash": {"count": len(rows) - len(active), "bytes": sum(row["size"] for row in rows if row.get("deleted_at"))},
                    "limits": {"asset_bytes": self.assets.MAX_BYTES, "project_asset_bytes": self.MAX_PROJECT_BYTES,
                               "project_assets": self.MAX_ASSETS},
                    "model_storage": "EXTERNAL_READ_ONLY", "cache_storage": "SEPARATE_OWNER",
                    "export_storage": "CLIENT_SELECTED_DOWNLOAD", "physical_cleanup_available": False,
                    "admission": admission}
