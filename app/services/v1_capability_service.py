from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..plugin_contracts import (
    HOST_API_VERSION,
    PLUGIN_CAPABILITIES,
    PLUGIN_MANIFEST_VERSION,
    PLUGIN_PERMISSIONS,
    PluginManifestV1 as PluginManifestIn,
    canonical_manifest_sha256,
)
from ..plugin_discovery import identity_snapshot, sidecar_has_identity
from ..idempotency import IdempotencyStore
from ..storage import atomic_write


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CapabilityVersionConflict(ValueError):
    def __init__(self, current: dict[str, Any]):
        self.current = current
        super().__init__("capability record version conflict")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResearchRecordIn(_StrictModel):
    title: str = Field(min_length=1, max_length=240)
    source_type: Literal["BOOK", "ARTICLE", "WEBSITE", "ARCHIVE", "INTERVIEW", "NOTE", "OTHER"] = "NOTE"
    author: str = Field(default="", max_length=160)
    citation: str = Field(default="", max_length=1000)
    url: str = Field(default="", max_length=2000)
    excerpt: str = Field(default="", max_length=20000)
    notes: str = Field(default="", max_length=50000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    asset_ids: list[str] = Field(default_factory=list, max_length=100)
    status: Literal["ACTIVE", "ARCHIVED"] = "ACTIVE"

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        if value and not re.match(r"^https?://", value, flags=re.IGNORECASE):
            raise ValueError("research URL must use http or https")
        return value

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        output: list[str] = []
        for value in values:
            tag = str(value).strip()
            if not tag or len(tag) > 80:
                raise ValueError("research tags must be 1-80 characters")
            if tag not in output:
                output.append(tag)
        return output


class CharacterEvolutionIn(_StrictModel):
    character_id: str = Field(min_length=1, max_length=160)
    chapter: int | None = Field(default=None, ge=1)
    phase: str = Field(default="", max_length=160)
    event: str = Field(min_length=1, max_length=4000)
    initial_state: str = Field(default="", max_length=4000)
    psychological_change: str = Field(default="", max_length=4000)
    resulting_state: str = Field(default="", max_length=4000)
    relationship_changes: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=200)
    source_version_id: str = Field(default="", max_length=240)
    status: Literal["DRAFT", "CONFIRMED"] = "DRAFT"


class VisualMemoryIn(_StrictModel):
    entity_type: Literal["CHARACTER", "LOCATION", "SCENE", "SHOT", "STYLE", "OTHER"]
    entity_id: str = Field(min_length=1, max_length=240)
    asset_id: str | None = Field(default=None, max_length=240)
    appearance: dict[str, Any] = Field(default_factory=dict)
    clothing: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    scene_features: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=10000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    origin: Literal["USER", "IMPORT", "REVIEWED_AI"] = "USER"
    evidence_ids: list[str] = Field(default_factory=list, max_length=200)
    status: Literal["ACTIVE", "ARCHIVED"] = "ACTIVE"


class AssetDerivativeIn(_StrictModel):
    derivative_asset_id: str = Field(min_length=1, max_length=240)
    derivative_type: Literal["THUMBNAIL", "CROP", "RESIZE", "FORMAT_CONVERSION", "COLOR_VARIANT", "OTHER"]
    parameters: dict[str, Any] = Field(default_factory=dict)
    note: str = Field(default="", max_length=4000)


class PluginPermissionIn(_StrictModel):
    granted_permissions: list[str] = Field(default_factory=list, max_length=30)
    reviewed_by: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=2000)

    @field_validator("granted_permissions")
    @classmethod
    def supported_permissions(cls, values: list[str]) -> list[str]:
        unknown = set(values) - PLUGIN_PERMISSIONS
        if unknown:
            raise ValueError(f"unsupported plugin permissions: {sorted(unknown)}")
        return list(dict.fromkeys(values))


class WorkflowNodeIn(_StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    type: Literal["project_snapshot", "quality_gate", "manual_approval", "checkpoint", "agent_task"]
    name: str = Field(min_length=1, max_length=160)
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdgeIn(_StrictModel):
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)


class WorkflowDefinitionIn(_StrictModel):
    novel_id: str = Field(min_length=1, max_length=240)
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=4000)
    nodes: list[WorkflowNodeIn] = Field(min_length=1, max_length=100)
    edges: list[WorkflowEdgeIn] = Field(default_factory=list, max_length=300)


class WorkflowRunIn(_StrictModel):
    input: dict[str, Any] = Field(default_factory=dict)
    initiated_by: str = Field(default="local-author", min_length=1, max_length=160)


class ReleaseEvidenceIn(_StrictModel):
    status: Literal["PASS", "FAIL"]
    evidence_ref: str = Field(min_length=1, max_length=1000)
    verified_by: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=4000)


class ReleaseGateIn(_StrictModel):
    novel_id: str | None = Field(default=None, max_length=240)
    evidence: dict[str, ReleaseEvidenceIn] = Field(default_factory=dict)


class V1CapabilityService:
    """Local durable closure for V1 surfaces that do not require an AI call.

    The store intentionally contains metadata only.  It never fetches research
    URLs, executes plugin code, starts processes, or persists provider secrets.
    In PostgreSQL profiles this remains a durable sidecar behind the same
    service contract until native migrations are added.
    """

    def __init__(self, root: Path, novels, chapters, assets, exports=None, project_root: Path | None = None):
        self.root = Path(root)
        self.novels = novels
        self.chapters = chapters
        self.assets = assets
        self.exports = exports
        self.project_root = Path(project_root or self.root.parent)
        self._lock = threading.RLock()
        self._idempotency = IdempotencyStore(self.root / "v1_capabilities" / "idempotency.json")

    @property
    def storage_mode(self) -> str:
        return "durable_sidecar"

    def reconfigure_root(self, root: Path) -> None:
        self.root = Path(root)
        self._idempotency = IdempotencyStore(self.root / "v1_capabilities" / "idempotency.json")

    def _path(self, collection: str) -> Path:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", collection):
            raise ValueError("invalid capability collection")
        return self.root / "v1_capabilities" / f"{collection}.json"

    def _read(self, collection: str) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self._path(collection).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        if isinstance(raw, dict):
            raw = raw.get("items", [])
        return [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []

    def _write(self, collection: str, items: list[dict[str, Any]]) -> None:
        atomic_write(
            self._path(collection),
            json.dumps({"schema_version": 1, "items": items}, ensure_ascii=False, indent=2),
        )

    def _require_novel(self, novel_id: str) -> dict[str, Any]:
        if not novel_id or any(char in novel_id for char in ("/", "\\", "\x00")) or novel_id in {".", ".."}:
            raise ValueError("invalid novel_id")
        return self.novels.get(novel_id)

    def _require_character(self, novel_id: str, character_id: str) -> dict[str, Any]:
        self._require_novel(novel_id)
        item = next((row for row in self.novels.data_set(novel_id, "characters") if str(row.get("id")) == character_id), None)
        if item is None:
            raise FileNotFoundError(character_id)
        return item

    def _require_asset(self, asset_id: str, novel_id: str | None = None) -> dict[str, Any]:
        item = self.assets.get(asset_id)
        if novel_id is not None and item.get("novel_id") != novel_id:
            raise FileNotFoundError(asset_id)
        return item

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "idempotency_key"}

    def _audit(self, action: str, target_type: str, target_id: str, novel_id: str | None = None,
               actor: str = "local-author", metadata: dict[str, Any] | None = None) -> None:
        safe_metadata: dict[str, Any] = {}
        for key, value in (metadata or {}).items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe_metadata[str(key)[:80]] = value
        rows = self._read("audit")
        rows.append({
            "id": str(uuid.uuid4()), "novel_id": novel_id, "actor_id": actor,
            "action": action, "target_type": target_type, "target_id": target_id,
            "metadata": safe_metadata, "created_at": _now(),
        })
        self._write("audit", rows[-10000:])

    def list_audit(self, novel_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        rows = self._read("audit")
        if novel_id:
            self._require_novel(novel_id)
            rows = [row for row in rows if row.get("novel_id") == novel_id]
        rows = sorted(rows, key=lambda row: str(row.get("created_at", "")), reverse=True)
        limit = max(1, min(int(limit), 500))
        return {"items": rows[:limit], "total": len(rows), "storage": self.storage_mode}

    def _create(self, collection: str, payload: dict[str, Any], *, novel_id: str | None,
                action: str, target_type: str, idempotency_key: str | None = None,
                item_id: str | None = None) -> dict[str, Any]:
        cache_key = f"{collection}:{novel_id or 'global'}:{idempotency_key}" if idempotency_key else None
        if cache_key:
            cached = self._idempotency.get(cache_key)
            if isinstance(cached, dict):
                return cached
        with self._lock:
            if cache_key:
                cached = self._idempotency.get(cache_key)
                if isinstance(cached, dict):
                    return cached
            rows = self._read(collection)
            identifier = item_id or str(uuid.uuid4())
            if any(row.get("id") == identifier and not row.get("deleted_at") for row in rows):
                raise FileExistsError(identifier)
            now = _now()
            item = {
                "id": identifier, "novel_id": novel_id, **payload,
                "version": 1, "created_at": now, "updated_at": now, "deleted_at": None,
            }
            rows.append(item)
            self._write(collection, rows)
            self._audit(action, target_type, identifier, novel_id)
            public = self._public(item)
            if cache_key:
                self._idempotency.put(cache_key, public)
            return public

    def _get(self, collection: str, item_id: str, novel_id: str | None = None) -> dict[str, Any]:
        row = next((row for row in self._read(collection) if row.get("id") == item_id and not row.get("deleted_at")), None)
        if row is None or (novel_id is not None and row.get("novel_id") != novel_id):
            raise FileNotFoundError(item_id)
        return self._public(row)

    def _update(self, collection: str, item_id: str, changes: dict[str, Any], *, novel_id: str | None,
                expected_version: int | None, action: str, target_type: str) -> dict[str, Any]:
        with self._lock:
            rows = self._read(collection)
            index = next((index for index, row in enumerate(rows) if row.get("id") == item_id and not row.get("deleted_at")), None)
            if index is None or (novel_id is not None and rows[index].get("novel_id") != novel_id):
                raise FileNotFoundError(item_id)
            current = rows[index]
            if expected_version is not None and int(current.get("version", 1)) != int(expected_version):
                raise CapabilityVersionConflict(self._public(current))
            updated = {**current, **changes, "version": int(current.get("version", 1)) + 1, "updated_at": _now()}
            rows[index] = updated
            self._write(collection, rows)
            self._audit(action, target_type, item_id, current.get("novel_id"))
            return self._public(updated)

    def _delete(self, collection: str, item_id: str, *, novel_id: str | None,
                expected_version: int | None, action: str, target_type: str) -> dict[str, Any]:
        return self._update(
            collection, item_id, {"deleted_at": _now(), "status": "DELETED"},
            novel_id=novel_id, expected_version=expected_version, action=action, target_type=target_type,
        )

    # Research Assistant -------------------------------------------------
    def list_research(self, novel_id: str, status: str | None = None, source_type: str | None = None,
                      tag: str | None = None) -> dict[str, Any]:
        self._require_novel(novel_id)
        rows = [self._public(row) for row in self._read("research") if row.get("novel_id") == novel_id and not row.get("deleted_at")]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if source_type:
            rows = [row for row in rows if row.get("source_type") == source_type]
        if tag:
            rows = [row for row in rows if tag in row.get("tags", [])]
        rows.sort(key=lambda row: str(row.get("updated_at", "")), reverse=True)
        return {"items": rows, "total": len(rows), "external_fetch": False, "storage": self.storage_mode}

    def create_research(self, novel_id: str, body: ResearchRecordIn, idempotency_key: str | None = None) -> dict[str, Any]:
        self._require_novel(novel_id)
        for asset_id in body.asset_ids:
            self._require_asset(asset_id, novel_id)
        payload = body.model_dump(mode="json")
        payload["provenance"] = {"mode": "local_user_record", "external_fetch": False}
        return self._create("research", payload, novel_id=novel_id, action="RESEARCH_CREATED",
                            target_type="ResearchRecord", idempotency_key=idempotency_key)

    def update_research(self, novel_id: str, research_id: str, body: ResearchRecordIn,
                        expected_version: int | None = None) -> dict[str, Any]:
        self._require_novel(novel_id)
        for asset_id in body.asset_ids:
            self._require_asset(asset_id, novel_id)
        return self._update("research", research_id, body.model_dump(mode="json"), novel_id=novel_id,
                            expected_version=expected_version, action="RESEARCH_UPDATED", target_type="ResearchRecord")

    def delete_research(self, novel_id: str, research_id: str, expected_version: int | None = None) -> dict[str, Any]:
        self._require_novel(novel_id)
        item = self._delete("research", research_id, novel_id=novel_id, expected_version=expected_version,
                            action="RESEARCH_DELETED", target_type="ResearchRecord")
        return {"id": item["id"], "deleted": True, "version": item["version"]}

    # Character evolution ------------------------------------------------
    def list_character_evolution(self, novel_id: str, character_id: str | None = None,
                                 status: str | None = None) -> dict[str, Any]:
        self._require_novel(novel_id)
        if character_id:
            self._require_character(novel_id, character_id)
        rows = [self._public(row) for row in self._read("character_evolution")
                if row.get("novel_id") == novel_id and not row.get("deleted_at")]
        if character_id:
            rows = [row for row in rows if row.get("character_id") == character_id]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows.sort(key=lambda row: (row.get("chapter") is None, row.get("chapter") or 0, row.get("created_at", "")))
        return {"items": rows, "total": len(rows), "storage": self.storage_mode}

    def create_character_evolution(self, novel_id: str, body: CharacterEvolutionIn,
                                   idempotency_key: str | None = None) -> dict[str, Any]:
        self._require_character(novel_id, body.character_id)
        return self._create("character_evolution", body.model_dump(mode="json"), novel_id=novel_id,
                            action="CHARACTER_EVOLUTION_CREATED", target_type="CharacterEvolution",
                            idempotency_key=idempotency_key)

    def update_character_evolution(self, novel_id: str, evolution_id: str, body: CharacterEvolutionIn,
                                   expected_version: int | None = None) -> dict[str, Any]:
        self._require_character(novel_id, body.character_id)
        return self._update("character_evolution", evolution_id, body.model_dump(mode="json"), novel_id=novel_id,
                            expected_version=expected_version, action="CHARACTER_EVOLUTION_UPDATED",
                            target_type="CharacterEvolution")

    # Visual memory and asset lineage -----------------------------------
    def list_visual_memory(self, novel_id: str, entity_type: str | None = None,
                           entity_id: str | None = None, status: str | None = None) -> dict[str, Any]:
        self._require_novel(novel_id)
        rows = [self._public(row) for row in self._read("visual_memory")
                if row.get("novel_id") == novel_id and not row.get("deleted_at")]
        if entity_type:
            rows = [row for row in rows if row.get("entity_type") == entity_type]
        if entity_id:
            rows = [row for row in rows if row.get("entity_id") == entity_id]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows.sort(key=lambda row: str(row.get("updated_at", "")), reverse=True)
        return {"items": rows, "total": len(rows), "inference_performed": False, "storage": self.storage_mode}

    def create_visual_memory(self, novel_id: str, body: VisualMemoryIn,
                             idempotency_key: str | None = None) -> dict[str, Any]:
        self._require_novel(novel_id)
        if body.entity_type == "CHARACTER":
            self._require_character(novel_id, body.entity_id)
        if body.asset_id:
            self._require_asset(body.asset_id, novel_id)
        return self._create("visual_memory", body.model_dump(mode="json"), novel_id=novel_id,
                            action="VISUAL_MEMORY_CREATED", target_type="VisualMemory",
                            idempotency_key=idempotency_key)

    def update_visual_memory(self, novel_id: str, memory_id: str, body: VisualMemoryIn,
                             expected_version: int | None = None) -> dict[str, Any]:
        self._require_novel(novel_id)
        if body.entity_type == "CHARACTER":
            self._require_character(novel_id, body.entity_id)
        if body.asset_id:
            self._require_asset(body.asset_id, novel_id)
        return self._update("visual_memory", memory_id, body.model_dump(mode="json"), novel_id=novel_id,
                            expected_version=expected_version, action="VISUAL_MEMORY_UPDATED", target_type="VisualMemory")

    def list_asset_derivatives(self, asset_id: str) -> dict[str, Any]:
        source = self._require_asset(asset_id)
        rows = [self._public(row) for row in self._read("asset_derivatives")
                if row.get("source_asset_id") == asset_id and not row.get("deleted_at")]
        return {"source_asset": source, "items": rows, "total": len(rows), "generation_performed": False,
                "storage": self.storage_mode}

    def create_asset_derivative(self, asset_id: str, body: AssetDerivativeIn,
                                idempotency_key: str | None = None) -> dict[str, Any]:
        source = self._require_asset(asset_id)
        derivative = self._require_asset(body.derivative_asset_id, source.get("novel_id"))
        if derivative["id"] == source["id"]:
            raise ValueError("derivative asset must differ from source asset")
        payload = {
            "source_asset_id": source["id"], **body.model_dump(mode="json"),
            "source_sha256": source.get("sha256"), "derivative_sha256": derivative.get("sha256"),
            "status": "AVAILABLE", "generation_performed": False,
        }
        return self._create("asset_derivatives", payload, novel_id=source.get("novel_id"),
                            action="ASSET_DERIVATIVE_LINKED", target_type="AssetDerivative",
                            idempotency_key=idempotency_key)

    # Plugin manifest and permission manager -----------------------------
    def _public_plugin(self, item: dict[str, Any]) -> dict[str, Any]:
        public = self._public(item)
        public["execution_supported"] = False
        try:
            public["version"] = int(public.get("version") or 1)
        except (TypeError, ValueError):
            public["version"] = 1
        if not sidecar_has_identity(public):
            public["status"] = "REVIEW_REQUIRED"
            public["validated"] = False
        return public

    def list_plugins(self) -> dict[str, Any]:
        rows = [self._public_plugin(row) for row in self._read("plugins") if not row.get("deleted_at")]
        rows.sort(key=lambda row: (str(row.get("name", "")).lower(), str(row.get("id", ""))))
        return {"items": rows, "total": len(rows), "default_policy": "DENY",
                "execution_supported": False, "storage": self.storage_mode}

    def get_plugin(self, plugin_id: str) -> dict[str, Any]:
        row = next((row for row in self._read("plugins") if row.get("id") == plugin_id and not row.get("deleted_at")), None)
        if row is None:
            raise FileNotFoundError(plugin_id)
        return self._public_plugin(row)

    def _plugin_payload(self, body: PluginManifestIn) -> dict[str, Any]:
        dump = body.public_dump()
        snapshot = identity_snapshot(body)
        return {
            **{key: value for key, value in dump.items() if key != "version"},
            **snapshot,
            "granted_permissions": [],
            "status": "REGISTERED",
            "default_policy": "DENY",
            "execution_supported": False,
            "publisher_verified": False,
            "publisher_trust": "unverified",
            "permission_review": None,
            "manifest_version": getattr(body, "manifest_version", PLUGIN_MANIFEST_VERSION),
            "host_api_version": getattr(body, "host_api_version", HOST_API_VERSION),
            "manifest_sha256": canonical_manifest_sha256(body),
        }

    def register_plugin(self, body: PluginManifestIn, idempotency_key: str | None = None) -> dict[str, Any]:
        payload = self._plugin_payload(body)
        existing = next((row for row in self._read("plugins") if row.get("id") == body.id and not row.get("deleted_at")), None)
        if existing is None:
            created = self._create("plugins", payload, novel_id=None, action="PLUGIN_REGISTERED",
                                   target_type="Plugin", idempotency_key=idempotency_key, item_id=body.id)
            return self._public_plugin(created)
        public = self._public_plugin(existing)
        if (sidecar_has_identity(existing)
                and existing.get("manifest_sha256") == payload["manifest_sha256"]
                and public.get("status") != "REVIEW_REQUIRED"):
            return public
        return self._public_plugin(self._update(
            "plugins", body.id, payload, novel_id=None, expected_version=None,
            action="PLUGIN_RE_REGISTERED", target_type="Plugin",
        ))

    def set_plugin_permissions(self, plugin_id: str, body: PluginPermissionIn,
                               expected_version: int | None = None) -> dict[str, Any]:
        plugin = self.get_plugin(plugin_id)
        if plugin.get("status") == "REVIEW_REQUIRED" or not sidecar_has_identity(plugin):
            raise ValueError("plugin identity must be re-registered before permission review")
        requested = set(plugin.get("requested_permissions", []))
        granted = set(body.granted_permissions)
        if not granted.issubset(requested):
            raise ValueError("granted permissions must be requested by the plugin manifest")
        review = {"reviewed_by": body.reviewed_by, "note": body.note, "reviewed_at": _now()}
        return self._public_plugin(self._update("plugins", plugin_id, {"granted_permissions": body.granted_permissions,
                            "permission_review": review, "status": "PERMISSIONS_REVIEWED"}, novel_id=None,
                            expected_version=expected_version, action="PLUGIN_PERMISSIONS_REVIEWED", target_type="Plugin"))

    def set_plugin_enabled(self, plugin_id: str, enabled: bool, expected_version: int | None = None) -> dict[str, Any]:
        plugin = self.get_plugin(plugin_id)
        if enabled:
            if plugin.get("status") == "REVIEW_REQUIRED" or not sidecar_has_identity(plugin):
                raise ValueError("plugin identity must be re-registered before activation")
            if set(plugin.get("requested_permissions", [])) != set(plugin.get("granted_permissions", [])):
                raise ValueError("all requested permissions must be reviewed and granted before activation")
            from ..plugin_catalog import assert_activation_identity
            assert_activation_identity(plugin)
        # Activation is manifest activation only.  V1 never executes arbitrary
        # plugin code from this endpoint.
        return self._public_plugin(self._update("plugins", plugin_id, {"status": "MANIFEST_ACTIVE" if enabled else "DISABLED",
                            "execution_supported": False}, novel_id=None, expected_version=expected_version,
                            action="PLUGIN_MANIFEST_ACTIVATED" if enabled else "PLUGIN_DISABLED", target_type="Plugin"))

    # Durable local DAG ---------------------------------------------------
    @staticmethod
    def _workflow_order(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
        ids = [node["id"] for node in nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("workflow node ids must be unique")
        known = set(ids)
        indegree = {node_id: 0 for node_id in ids}
        outgoing = {node_id: [] for node_id in ids}
        seen_edges: set[tuple[str, str]] = set()
        for edge in edges:
            source, target = edge["source"], edge["target"]
            if source not in known or target not in known:
                raise ValueError("workflow edge references an unknown node")
            if source == target:
                raise ValueError("workflow node cannot depend on itself")
            pair = (source, target)
            if pair in seen_edges:
                continue
            seen_edges.add(pair)
            outgoing[source].append(target)
            indegree[target] += 1
        ready = [node_id for node_id in ids if indegree[node_id] == 0]
        order: list[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for target in outgoing[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        if len(order) != len(ids):
            raise ValueError("workflow graph must be acyclic")
        return order

    def list_workflows(self, novel_id: str | None = None) -> dict[str, Any]:
        if novel_id:
            self._require_novel(novel_id)
        rows = [self._public(row) for row in self._read("workflows") if not row.get("deleted_at")]
        if novel_id:
            rows = [row for row in rows if row.get("novel_id") == novel_id]
        return {"items": rows, "total": len(rows), "supported_node_types": [
            "project_snapshot", "quality_gate", "manual_approval", "checkpoint",
        ], "external_ai_calls": False, "storage": self.storage_mode}

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._get("workflows", workflow_id)

    def create_workflow(self, body: WorkflowDefinitionIn, idempotency_key: str | None = None) -> dict[str, Any]:
        self._require_novel(body.novel_id)
        payload = body.model_dump(mode="json")
        payload["topological_order"] = self._workflow_order(payload["nodes"], payload["edges"])
        payload["status"] = "ACTIVE"
        payload["external_ai_calls"] = False
        return self._create("workflows", payload, novel_id=body.novel_id, action="WORKFLOW_CREATED",
                            target_type="Workflow", idempotency_key=idempotency_key)

    def list_workflow_runs(self, workflow_id: str) -> dict[str, Any]:
        self.get_workflow(workflow_id)
        rows = [self._public(row) for row in self._read("workflow_runs")
                if row.get("workflow_id") == workflow_id and not row.get("deleted_at")]
        rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return {"items": rows, "total": len(rows), "storage": self.storage_mode}

    def get_workflow_run(self, run_id: str) -> dict[str, Any]:
        return self._get("workflow_runs", run_id)

    def create_workflow_run(self, workflow_id: str, body: WorkflowRunIn,
                            idempotency_key: str | None = None) -> dict[str, Any]:
        workflow = self.get_workflow(workflow_id)
        node_states = {node["id"]: {"status": "PENDING", "output": None, "error": None}
                       for node in workflow["nodes"]}
        payload = {
            "workflow_id": workflow_id, "workflow_version": workflow["version"],
            "definition_snapshot": {key: workflow[key] for key in ("title", "nodes", "edges", "topological_order")},
            "input": body.input, "initiated_by": body.initiated_by, "status": "QUEUED",
            "node_states": node_states, "attempt": 1, "retry_of": None,
            "external_ai_calls": False,
        }
        run = self._create("workflow_runs", payload, novel_id=workflow["novel_id"], action="WORKFLOW_RUN_CREATED",
                           target_type="WorkflowRun", idempotency_key=idempotency_key)
        return self._advance_workflow_run(run["id"])

    def _advance_workflow_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self.get_workflow_run(run_id)
            if run["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return run
            snapshot = run["definition_snapshot"]
            nodes = {node["id"]: node for node in snapshot["nodes"]}
            incoming: dict[str, list[str]] = {node_id: [] for node_id in nodes}
            for edge in snapshot["edges"]:
                incoming[edge["target"]].append(edge["source"])
            states = dict(run["node_states"])
            status = "RUNNING"
            for node_id in snapshot["topological_order"]:
                state = dict(states[node_id])
                if state["status"] == "SUCCEEDED":
                    continue
                if any(states[source]["status"] != "SUCCEEDED" for source in incoming[node_id]):
                    continue
                node = nodes[node_id]
                if node["type"] == "manual_approval":
                    state.update(status="WAITING_APPROVAL", output=None, error=None)
                    states[node_id] = state
                    status = "WAITING_APPROVAL"
                    break
                if node["type"] == "agent_task":
                    state.update(status="WAITING_APPROVAL", output={"execution":"DEFERRED","agent_role":node.get("config",{}).get("agent_role","writer")}, error=None)
                    states[node_id] = state
                    status = "WAITING_APPROVAL"
                    break
                try:
                    if node["type"] == "project_snapshot":
                        overview = self.overview(run["novel_id"])
                        output = {"counts": overview["counts"], "content": overview["content"]}
                    elif node["type"] == "quality_gate":
                        gate = self.evaluate_release_gate(run["novel_id"], {}, persist=False)
                        output = {"result": gate["result"], "blocking_checks": gate["blocking_checks"]}
                    else:
                        output = {"checkpoint": node_id, "name": node["name"]}
                    state.update(status="SUCCEEDED", output=output, error=None, finished_at=_now())
                    states[node_id] = state
                except Exception as exc:
                    state.update(status="FAILED", output=None, error={"code": "WORKFLOW_NODE_FAILED", "message": str(exc)})
                    states[node_id] = state
                    status = "FAILED"
                    break
            else:
                status = "SUCCEEDED" if all(state["status"] == "SUCCEEDED" for state in states.values()) else status
            return self._update("workflow_runs", run_id, {"node_states": states, "status": status}, novel_id=run["novel_id"],
                                expected_version=run["version"], action="WORKFLOW_RUN_ADVANCED", target_type="WorkflowRun")

    def approve_workflow_node(self, run_id: str, node_id: str, approved_by: str, note: str = "") -> dict[str, Any]:
        if not approved_by.strip():
            raise ValueError("approved_by is required")
        run = self.get_workflow_run(run_id)
        states = dict(run["node_states"])
        state = dict(states.get(node_id) or {})
        node = next((node for node in run["definition_snapshot"]["nodes"] if node["id"] == node_id), None)
        if node is None or node["type"] != "manual_approval" or state.get("status") != "WAITING_APPROVAL":
            raise ValueError("workflow node is not awaiting manual approval")
        state.update(status="SUCCEEDED", output={"approved_by": approved_by.strip(), "note": note, "approved_at": _now()},
                     error=None, finished_at=_now())
        states[node_id] = state
        updated = self._update("workflow_runs", run_id, {"node_states": states, "status": "RUNNING"}, novel_id=run["novel_id"],
                               expected_version=run["version"], action="WORKFLOW_NODE_APPROVED", target_type="WorkflowRun")
        return self._advance_workflow_run(updated["id"])
    def trigger_agent_node(self, run_id: str, node_id: str, triggered_by: str) -> dict[str, Any]:
        run=self.get_workflow_run(run_id); node=next((n for n in run["definition_snapshot"]["nodes"] if n["id"]==node_id),None); state=dict(run["node_states"].get(node_id) or {})
        if not node or node.get("type")!="agent_task" or state.get("status")!="WAITING_APPROVAL": raise ValueError("agent node is not waiting for trigger")
        state.update(status="SUCCEEDED",output={"execution":"QUEUED","triggered_by":str(triggered_by).strip(),"agent_role":node.get("config",{}).get("agent_role","writer"),"queued_at":_now()},finished_at=_now())
        updated=self._update("workflow_runs",run_id,{"node_states":{**run["node_states"],node_id:state},"status":"RUNNING"},novel_id=run["novel_id"],expected_version=run["version"],action="AGENT_NODE_QUEUED",target_type="WorkflowRun")
        return self._advance_workflow_run(updated["id"])
    def list_agent_queue(self, novel_id: str | None = None) -> dict[str, Any]:
        rows=[]
        for run in self._read('workflow_runs'):
            if novel_id and run.get('novel_id')!=novel_id: continue
            for node_id,state in (run.get('node_states') or {}).items():
                if state.get('status')=='SUCCEEDED' and state.get('output',{}).get('execution')=='QUEUED': rows.append({'run_id':run['id'],'novel_id':run.get('novel_id'),'node_id':node_id,'agent_role':state.get('output',{}).get('agent_role'),'status':'QUEUED'})
        return {'items':rows,'total':len(rows)}
    def claim_agent_task(self, run_id: str, node_id: str, claimed_by: str) -> dict[str, Any]:
        run=self.get_workflow_run(run_id); state=dict((run.get('node_states') or {}).get(node_id) or {})
        if state.get('status')!='SUCCEEDED' or state.get('output',{}).get('execution')!='QUEUED': raise ValueError('agent task is not queued')
        output={**state.get('output',{}),'execution':'CLAIMED','claimed_by':str(claimed_by).strip(),'claimed_at':_now()}; state['output']=output
        return self._update('workflow_runs',run_id,{'node_states':{**run['node_states'],node_id:state}},novel_id=run['novel_id'],expected_version=run['version'],action='AGENT_TASK_CLAIMED',target_type='WorkflowRun')
    def complete_agent_task(self, run_id: str, node_id: str, status: str, output: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
        run=self.get_workflow_run(run_id); state=dict((run.get('node_states') or {}).get(node_id) or {})
        if state.get('output',{}).get('execution')!='CLAIMED': raise ValueError('agent task is not claimed')
        if status not in {'SUCCEEDED','FAILED'}: raise ValueError('invalid agent completion status')
        state.update(status=status,output={**state.get('output',{}),'execution':'COMPLETED','result':output} if status=='SUCCEEDED' else {**state.get('output',{}),'execution':'FAILED'},error={'message':error} if error else None,finished_at=_now())
        updated=self._update('workflow_runs',run_id,{'node_states':{**run['node_states'],node_id:state},'status':'RUNNING' if status=='SUCCEEDED' else 'FAILED'},novel_id=run['novel_id'],expected_version=run['version'],action='AGENT_TASK_COMPLETED',target_type='WorkflowRun')
        return self._advance_workflow_run(updated['id']) if status=='SUCCEEDED' else updated

    def set_workflow_run_state(self, run_id: str, action: Literal["pause", "resume", "cancel"]) -> dict[str, Any]:
        run = self.get_workflow_run(run_id)
        if action == "cancel":
            if run["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                raise ValueError("terminal workflow run cannot be cancelled")
            return self._update("workflow_runs", run_id, {"status": "CANCELLED"}, novel_id=run["novel_id"],
                                expected_version=run["version"], action="WORKFLOW_RUN_CANCELLED", target_type="WorkflowRun")
        if action == "pause":
            if run["status"] not in {"QUEUED", "RUNNING", "WAITING_APPROVAL"}:
                raise ValueError("workflow run cannot be paused")
            return self._update("workflow_runs", run_id, {"status": "PAUSED"}, novel_id=run["novel_id"],
                                expected_version=run["version"], action="WORKFLOW_RUN_PAUSED", target_type="WorkflowRun")
        if run["status"] != "PAUSED":
            raise ValueError("only a paused workflow run can be resumed")
        updated = self._update("workflow_runs", run_id, {"status": "RUNNING"}, novel_id=run["novel_id"],
                               expected_version=run["version"], action="WORKFLOW_RUN_RESUMED", target_type="WorkflowRun")
        return self._advance_workflow_run(updated["id"])

    def retry_workflow_run(self, run_id: str, idempotency_key: str | None = None) -> dict[str, Any]:
        source = self.get_workflow_run(run_id)
        if source["status"] not in {"FAILED", "CANCELLED"}:
            raise ValueError("only failed or cancelled workflow runs can be retried")
        workflow = self.get_workflow(source["workflow_id"])
        body = WorkflowRunIn(input=source.get("input", {}), initiated_by=source.get("initiated_by", "local-author"))
        run = self.create_workflow_run(workflow["id"], body, idempotency_key)
        return self._update("workflow_runs", run["id"], {"retry_of": run_id, "attempt": int(source.get("attempt", 1)) + 1},
                            novel_id=run["novel_id"], expected_version=run["version"], action="WORKFLOW_RUN_RETRIED",
                            target_type="WorkflowRun")

    # Overview and release gate -----------------------------------------
    def overview(self, novel_id: str) -> dict[str, Any]:
        novel = self._require_novel(novel_id)
        chapters = self.chapters.list(novel_id)
        datasets: dict[str, list[dict[str, Any]]] = {}
        for name in ("characters", "locations", "timeline", "foreshadowing", "relationships", "volumes", "scenes", "story_routes"):
            try:
                datasets[name] = list(self.novels.data_set(novel_id, name))
            except (KeyError, FileNotFoundError):
                datasets[name] = []
        counts = {name: len(rows) for name, rows in datasets.items()}
        counts.update({
            "chapters": len(chapters), "assets": len(self.assets.list(novel_id)),
            "research": self.list_research(novel_id)["total"],
            "world_rules": self._count_world_rules(novel_id),
            "character_evolution": self.list_character_evolution(novel_id)["total"],
            "visual_memory": self.list_visual_memory(novel_id)["total"],
            "workflows": self.list_workflows(novel_id)["total"],
        })
        word_count = sum(int(chapter.get("word_count", 0) or 0) for chapter in chapters)
        if not word_count:
            word_count = sum(len(str(chapter.get("content") or "").replace(" ", "")) for chapter in chapters)
        missing: list[str] = []
        if not chapters:
            missing.append("chapters")
        if not datasets["characters"]:
            missing.append("characters")
        try:
            outline = self.novels.outline(novel_id)
        except (AttributeError, FileNotFoundError, KeyError):
            outline = {}
        if not outline:
            missing.append("outline")
        writing_goal = self._writing_goal(novel_id, chapters, word_count)
        pending_items = self._pending_items(novel_id, missing, writing_goal)
        recent = self.list_audit(novel_id, 10)["items"]
        return {
            "novel": novel, "counts": counts,
            "content": {"word_count": word_count, "has_chapters": bool(chapters),
                        "latest_chapter": chapters[-1] if chapters else None},
            "writing_goal": writing_goal,
            "pending_items": pending_items,
            "readiness": {"state": "CONTENT_READY" if chapters else "NEEDS_CONTENT", "missing": missing,
                          "release_gate_required": True},
            "recent_activity": recent, "storage": self.storage_mode,
            "placeholder": False,
        }

    def bind_lore(self, lore_service) -> None:
        self._lore = lore_service

    def bind_continuity(self, continuity_finding_service) -> None:
        self._continuity = continuity_finding_service

    def _count_world_rules(self, novel_id: str) -> int:
        lore = getattr(self, "_lore", None)
        if lore is None:
            try:
                rows = list(self.novels.data_set(novel_id, "world_rules"))
            except (AttributeError, KeyError, FileNotFoundError, TypeError):
                rows = []
            return len(rows)
        try:
            rows = lore.repository.list_proposals(novel_id)
        except Exception:
            return 0
        return len([row for row in rows if row.get("proposal_type") == "WORLD_RULE" and not row.get("deleted_at")])

    def _writing_goal(self, novel_id: str, chapters: list[dict[str, Any]], word_count: int) -> dict[str, Any]:
        if hasattr(self.novels, "writing_goal"):
            try:
                return self.novels.writing_goal(novel_id)
            except Exception:
                pass
        novel = self._require_novel(novel_id)
        goal = novel.get("writing_goal") or {"target_words": 0, "target_chapters": 0, "deadline": ""}
        target_words = int(goal.get("target_words") or 0)
        target_chapters = int(goal.get("target_chapters") or 0)
        return {
            "target_words": target_words, "target_chapters": target_chapters,
            "deadline": str(goal.get("deadline") or ""),
            "current_words": word_count, "current_chapters": len(chapters),
            "words_progress": round(min(word_count / target_words, 1), 4) if target_words else 0,
            "chapters_progress": round(min(len(chapters) / target_chapters, 1), 4) if target_chapters else 0,
        }

    def _pending_items(self, novel_id: str, missing: list[str], writing_goal: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = [{"kind": "missing", "label": name} for name in missing]
        if int(writing_goal.get("target_words") or 0) <= 0:
            items.append({"kind": "writing_goal", "label": "未设置写作目标字数"})
        lore = getattr(self, "_lore", None)
        if lore is not None:
            try:
                pending_rules = [
                    row for row in lore.repository.list_proposals(novel_id, "PENDING")
                    if row.get("proposal_type") == "WORLD_RULE"
                ]
                if pending_rules:
                    items.append({"kind": "world_rules", "label": f"{len(pending_rules)} 条待审核世界规则", "count": len(pending_rules)})
            except Exception:
                pass
        continuity = getattr(self, "_continuity", None)
        if continuity is not None:
            try:
                findings = [row for row in continuity.list_findings(novel_id) if str(row.get("status", "")).upper() not in {"RESOLVED", "ACCEPTED"}]
                if findings:
                    items.append({"kind": "continuity", "label": f"{len(findings)} 条未处理一致性问题", "count": len(findings)})
            except Exception:
                pass
        return items

    def _release_checks(self, novel_id: str | None) -> list[dict[str, Any]]:
        version = {"version": "unknown", "channel": "development"}
        version_path = self.project_root / "release" / "version.json"
        try:
            value = json.loads(version_path.read_text(encoding="utf-8"))
            version = {"version": str(value.get("version", "unknown")), "channel": str(value.get("channel", "development"))}
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        supported_exports = set(getattr(self.exports, "SUPPORTED", set()))
        required_exports = {"txt", "docx", "pdf", "epub", "screenplay", "shot-list", "storyboard"}
        export_missing = sorted(required_exports - supported_exports)
        content_status = "NOT_APPLICABLE"
        content_detail = "No project selected"
        if novel_id:
            self._require_novel(novel_id)
            chapters = self.chapters.list(novel_id)
            content_status = "PASS" if chapters else "FAIL"
            content_detail = f"{len(chapters)} chapter(s) present"
        return [
            {"id": "internal_build_guard", "required": True, "status": "PASS",
             "detail": f"{version['version']} {version['channel']}; public_release remains false", "source": "RUNTIME"},
            {"id": "project_content", "required": bool(novel_id), "status": content_status,
             "detail": content_detail, "source": "RUNTIME"},
            {"id": "export_coverage", "required": True, "status": "PASS" if not export_missing else "FAIL",
             "detail": "all required formats registered" if not export_missing else f"missing formats: {', '.join(export_missing)}",
             "source": "RUNTIME"},
            {"id": "desktop_ui_acceptance", "required": True, "status": "NOT_VERIFIED",
             "detail": "clean Windows DesktopHost manual path evidence required", "source": "EXTERNAL_EVIDENCE"},
            {"id": "postgres_parity", "required": True, "status": "NOT_VERIFIED",
             "detail": "clean PostgreSQL regression evidence required", "source": "EXTERNAL_EVIDENCE"},
            {"id": "backup_restore", "required": True, "status": "NOT_VERIFIED",
             "detail": "backup and restore drill evidence required", "source": "EXTERNAL_EVIDENCE"},
            {"id": "security_performance", "required": True, "status": "NOT_VERIFIED",
             "detail": "P0/P1 security review and performance gate evidence required", "source": "EXTERNAL_EVIDENCE"},
        ]

    def evaluate_release_gate(self, novel_id: str | None, evidence: dict[str, ReleaseEvidenceIn] | dict[str, Any],
                              persist: bool = True, idempotency_key: str | None = None) -> dict[str, Any]:
        checks = self._release_checks(novel_id)
        check_map = {check["id"]: check for check in checks}
        for check_id, raw in evidence.items():
            if check_id not in check_map:
                raise ValueError(f"unknown release check: {check_id}")
            item = raw if isinstance(raw, ReleaseEvidenceIn) else ReleaseEvidenceIn.model_validate(raw)
            check_map[check_id].update({
                "status": item.status, "detail": item.note or item.evidence_ref,
                "source": "RECORDED_EVIDENCE", "evidence_ref": item.evidence_ref,
                "verified_by": item.verified_by, "verified_at": _now(),
            })
        blocking = [check["id"] for check in checks if check["required"] and check["status"] != "PASS"]
        result = {
            "result": "READY_FOR_FREEZE" if not blocking else "BLOCKED",
            "public_release": False, "checks": checks, "blocking_checks": blocking,
            "evaluated_at": _now(), "storage": self.storage_mode,
        }
        if not persist:
            return result
        return self._create("release_gates", result, novel_id=novel_id, action="RELEASE_GATE_EVALUATED",
                            target_type="ReleaseGate", idempotency_key=idempotency_key)

    def list_release_gates(self, novel_id: str | None = None) -> dict[str, Any]:
        if novel_id:
            self._require_novel(novel_id)
        rows = [self._public(row) for row in self._read("release_gates") if not row.get("deleted_at")]
        if novel_id:
            rows = [row for row in rows if row.get("novel_id") == novel_id]
        rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return {"items": rows, "total": len(rows), "public_release": False, "storage": self.storage_mode}

    def get_release_gate(self, gate_id: str) -> dict[str, Any]:
        return self._get("release_gates", gate_id)
