"""Independent studio adapters over the original project, asset and lineage owners.

No project, asset, version, queue or model registry is introduced here. The
scope document stores only presentation preferences. Binary metadata and its
versions remain exclusively owned by AssetLibraryService.
"""
from __future__ import annotations

import base64
import copy
from contextlib import contextmanager
import shutil
import errno

from ..experimental.common import change_row, new_row
from ..media_files import inspect_image, inspect_media
from ..services.v1_capability_service import CapabilityVersionConflict
from .project_store import BINDING
from .workspace_models import ManualAssetImport, StudioLineageInput, WorkspacePreferences, WorkspacePreferencesUpdate

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

    @staticmethod
    def _preference_view(row):
        fields = WorkspacePreferences.model_fields
        return {"version": row["version"], **{key: copy.deepcopy(row[key]) for key in fields}} if row else {
            "version": 0, **WorkspacePreferences().model_dump()}

    def project(self, nid, scope):
        self.store.key(nid, scope)
        project = self.novels.get(nid)
        row = self._preferences(self.store.read(nid, scope))
        return {"project": {"id": project["id"], "title": project["title"],
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

    def _row(self, nid, scope, aid, *, deleted=False):
        row = self.assets.get(aid, branch_id=scope.get("branch_id"), include_deleted=deleted)
        if row["novel_id"] != nid or row.get("branch_id") != scope.get("branch_id"):
            raise FileNotFoundError(aid)
        # Legacy metadata is permissive; the new CAS surface must never adopt
        # a corrupted/coerced counter as an authoritative asset revision.
        if type(row.get("version")) is not int or row["version"] < 1:
            raise ValueError("CREATIVE_ASSET_VERSION_INVALID")
        # M1 only accepts manual uploads. Do not read a media task/scope store
        # under an asset-owner lease if an unsupported record reaches here.
        if row.get("source_job_id"):
            raise ValueError("CREATIVE_ASSET_ADAPTER_REQUIRED")
        return row

    def _view(self, nid, scope, row):
        public = self.assets.public(row)
        if isinstance(public.get("parameters"), dict):
            # Only current scoped projections disclose source/relationship IDs.
            public["parameters"].pop("asset_lineage_v2", None)
        return {**public,
                "provenance": self.lineage.asset(nid, scope, row["id"], include_impact=False),
                "relationships": self.relationships.project(nid, scope, row)}

    def list_assets(self, nid, scope, *, include_deleted=False):
        with self._asset_scope(nid, scope):
            rows = self.assets.list(nid, branch_id=scope.get("branch_id"), include_deleted=include_deleted)
            return {"items": [self._view(nid, scope, self._row(nid, scope, row["id"], deleted=include_deleted)) for row in rows]}

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
        measured = inspect_image(data) if body.kind == "image" else inspect_media(data, body.kind)
        guard()
        with self._asset_scope(nid, scope):
            rows = self.assets.list(nid, branch_id=scope.get("branch_id"), include_deleted=True)
            retry = any(row.get("idempotency_key") == body.idempotency_key for row in rows)
            if not retry and (len(rows) >= self.MAX_ASSETS or sum(row["size"] for row in rows) + len(data) > self.MAX_PROJECT_BYTES):
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
                row = self.assets.create(nid, body.filename, body.content_base64, measured["media_type"], body.kind,
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
            self._row(nid, scope, aid)
            self.lineage.annotate(nid, scope, actor, aid, body, guard, include_impact=False)
            guard()
            return self._view(nid, scope, self._row(nid, scope, aid))

    def download(self, nid, scope, aid, guard=lambda: None):
        with self._asset_scope(nid, scope):
            row = self._row(nid, scope, aid)
            data = self.assets.content(aid, branch_id=scope.get("branch_id"))
            guard()
            return self.assets.public(row), data

    def lifecycle(self, nid, scope, aid, expected_version, *, restore=False, guard=lambda: None):
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("CREATIVE_EXPECTED_VERSION_INVALID")
        with self._asset_scope(nid, scope):
            row = self._row(nid, scope, aid, deleted=True)
            if row["version"] != expected_version:
                raise CapabilityVersionConflict({"version": row["version"]})
            if not restore:
                children = [other for other in self.assets.list(nid, branch_id=scope.get("branch_id"))
                            if aid in other.get("source_asset_ids", []) or any(
                                not relation.get("removed_at") and relation["target"]["kind"] == "ASSET"
                                and relation["target"]["id"] == aid for relation in self.relationships.records(other))]
                if children:
                    raise ValueError("CREATIVE_ASSET_IN_USE")
            guard()
            if restore:
                self.assets.restore(aid, branch_id=scope.get("branch_id"), guard=guard)
            else:
                self.assets.delete(aid, branch_id=scope.get("branch_id"), guard=guard)
            guard()
            return self._view(nid, scope, self._row(nid, scope, aid, deleted=True))

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
