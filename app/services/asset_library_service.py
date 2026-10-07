from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import mimetypes
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path

from ..repository import atomic_write, now
from ..repositories.file.mutation_coordinator import workspace_mutation


class AssetIntegrityError(ValueError):
    """Stored content no longer agrees with the recorded digest/length."""


class AssetIdempotencyConflict(ValueError):
    """An idempotency key cannot identify two different uploads."""


class AssetLibraryService:
    """Local assets with verified reads and recoverable deletion.

    MIME is declared metadata, not a media-decoding guarantee. The generic
    upload contract intentionally accepts opaque bytes; generated media uses
    the separate strict media ingestion validator. A supplied branch is a
    trusted server scope, never a client-authorized identity.
    """

    MAX_BYTES = 25 * 1024 * 1024

    @staticmethod
    def public(value):
        """Legacy response projection, retaining all persisted metadata.

        Only the new reserved field is hidden when A09 is off. Ordinary
        parameters and the pre-existing source_asset_ids contract are intact.
        Accepts nested asset response envelopes as well as one asset/list.
        """
        from ..experimental.flags import enabled_flags
        result = copy.deepcopy(value)
        lineage_enabled = "asset_lineage_v2" in enabled_flags()
        def redact(item):
            if isinstance(item, dict):
                for key in ("_required_features", "_owner_actor_id", "_origin_provenance"):
                    item.pop(key, None)
                if not lineage_enabled and isinstance(item.get("parameters"), dict):
                    item["parameters"].pop("asset_lineage_v2", None)
                for child in item.values(): redact(child)
            elif isinstance(item, list):
                for child in item: redact(child)
        redact(result)
        return result

    def __init__(self, root: Path):
        self.root = root / "assets"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @staticmethod
    def _identifier(value: str, field: str = "asset_id") -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", value):
            raise ValueError(f"invalid {field}")
        return value

    def _path(self, asset_id: str, suffix: str) -> Path:
        path = self.root / f"{self._identifier(asset_id)}.{suffix}"
        # Never follow asset symlinks, including symlinks pointing inside root.
        if path.is_symlink():
            raise AssetIntegrityError("asset path is not a regular file")
        return path

    def _meta_path(self, asset_id: str) -> Path:
        return self._path(asset_id, "json")

    def _bin_path(self, asset_id: str) -> Path:
        return self._path(asset_id, "bin")

    def _load(self, asset_id: str) -> dict:
        try:
            meta = json.loads(self._meta_path(asset_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise FileNotFoundError(asset_id) from None
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise AssetIntegrityError("asset metadata is unreadable") from exc
        if (not isinstance(meta, dict) or meta.get("id") != asset_id
                or not isinstance(meta.get("size"), int) or isinstance(meta.get("size"), bool)
                or not 0 < meta["size"] <= self.MAX_BYTES
                or not re.fullmatch(r"[a-f0-9]{64}", str(meta.get("sha256", "")))):
            raise AssetIntegrityError("asset metadata is invalid")
        return meta

    @staticmethod
    def _in_scope(meta: dict, branch_id: str | None, actor_id: str | None = None) -> bool:
        if meta.get("_required_features"):
            from ..experimental.flags import enabled_flags
            if not set(meta["_required_features"]).issubset(enabled_flags()): return False
            if meta.get("branch_id") != branch_id: return False
        if meta.get("_owner_actor_id") and meta["_owner_actor_id"] != actor_id: return False
        return branch_id is None or meta.get("branch_id") == branch_id

    def _write_meta(self, meta: dict) -> None:
        atomic_write(self._meta_path(meta["id"]), json.dumps(meta, ensure_ascii=False, indent=2))

    def create(self, novel_id: str, filename: str, content_base64: str,
               media_type: str | None = None, kind: str = "image",
               idempotency_key: str | None = None, *, branch_id: str | None = None,
               required_features: tuple[str, ...] = (), owner_actor_id: str | None = None):
        from ..experimental.flags import RUNTIME_FLAGS, enabled_flags
        if set(required_features) - set(RUNTIME_FLAGS) or not set(required_features).issubset(enabled_flags()):
            raise ValueError("asset origin feature unavailable")
        if owner_actor_id is not None and (not isinstance(owner_actor_id, str) or not owner_actor_id or len(owner_actor_id) > 240):
            raise ValueError("invalid asset owner")
        self._identifier(novel_id, "novel_id")
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        # Reject before decoding so an attacker cannot allocate arbitrary bytes.
        if not isinstance(content_base64, str):
            raise ValueError("content_base64 is invalid")
        if len(content_base64) > 4 * ((self.MAX_BYTES + 2) // 3):
            raise ValueError("asset exceeds the 25 MiB limit")
        try:
            data = base64.b64decode(content_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("content_base64 is invalid") from exc
        if not data:
            raise ValueError("asset content is empty")
        if len(data) > self.MAX_BYTES:
            raise ValueError("asset exceeds the 25 MiB limit")
        safe_name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        safe_name = re.sub(r"[\x00-\x1f\x7f]", "", safe_name).strip().rstrip(". ")[:255]
        if not safe_name:
            raise ValueError("asset filename is empty")
        media_type = str(media_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream").strip()
        if not re.fullmatch(r"[A-Za-z0-9!#$&^_.+*-]+/[A-Za-z0-9!#$&^_.+*-]+", media_type):
            raise ValueError("asset media_type is invalid")
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 240):
            raise ValueError("invalid asset idempotency key")
        identity = {"filename": safe_name, "kind": str(kind or "file")[:40], "media_type": media_type,
                    "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "branch_id": branch_id}
        if required_features or owner_actor_id:
            identity.update(_required_features=sorted(set(required_features)), _owner_actor_id=owner_actor_id)
        with self._lock, workspace_mutation(self.root, "asset-library"):
            if idempotency_key:
                for existing in self.list(novel_id, branch_id=branch_id, include_deleted=True, actor_id=owner_actor_id):
                    if existing.get("idempotency_key") != idempotency_key:
                        continue
                    if any(existing.get(key) != value for key, value in identity.items()):
                        raise AssetIdempotencyConflict("asset idempotency key was used for a different upload")
                    if existing.get("deleted_at"):
                        raise AssetIdempotencyConflict("asset was deleted; restore it or use a new idempotency key")
                    self.content(existing["id"], branch_id=branch_id, actor_id=owner_actor_id)
                    return existing
            asset_id = str(uuid.uuid4())
            meta = {"id": asset_id, "novel_id": novel_id, **identity, "created_at": now(), "updated_at": now(),
                    "version": 1, "deleted_at": None, "idempotency_key": idempotency_key}
            target = self._bin_path(asset_id)
            fd, temporary = tempfile.mkstemp(dir=self.root, prefix=asset_id + ".", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
                self._write_meta(meta)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return meta

    def list(self, novel_id: str, *, branch_id: str | None = None, include_deleted: bool = False, actor_id: str | None = None):
        self._identifier(novel_id, "novel_id")
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        items = []
        for path in self.root.glob("*.json"):
            try:
                meta = self._load(path.stem)
            except (ValueError, FileNotFoundError):
                # Corrupt entries cannot be treated as active, safe assets.
                continue
            if (meta.get("novel_id") == novel_id and self._in_scope(meta, branch_id, actor_id)
                    and (include_deleted or not meta.get("deleted_at"))):
                items.append(meta)
        return sorted(items, key=lambda item: (item.get("created_at", ""), item["id"]))

    def get(self, asset_id: str, *, branch_id: str | None = None, include_deleted: bool = False, actor_id: str | None = None):
        if branch_id is not None:
            self._identifier(branch_id, "branch_id")
        meta = self._load(asset_id)
        if not self._in_scope(meta, branch_id, actor_id) or (meta.get("deleted_at") and not include_deleted):
            raise FileNotFoundError(asset_id)
        return meta

    def _verified_content(self, meta: dict) -> bytes:
        path = self._bin_path(meta["id"])
        try:
            with path.open("rb") as stream:
                if os.fstat(stream.fileno()).st_size != meta["size"]:
                    raise AssetIntegrityError("asset content size mismatch")
                data = stream.read(self.MAX_BYTES + 1)
        except FileNotFoundError:
            raise FileNotFoundError(meta["id"]) from None
        if len(data) != meta["size"] or not hmac.compare_digest(hashlib.sha256(data).hexdigest(), meta["sha256"]):
            raise AssetIntegrityError("asset content digest mismatch")
        return data

    def content(self, asset_id: str, *, branch_id: str | None = None, actor_id: str | None = None):
        with self._lock, workspace_mutation(self.root, "asset-library"):
            return self._verified_content(self.get(asset_id, branch_id=branch_id, actor_id=actor_id))

    def update_metadata(self, asset_id: str, fields: dict, *, branch_id: str | None = None,
                        expected_version: int | None = None, _lineage_write: bool = False, actor_id: str | None = None):
        allowed = {"source_job_id", "provider_id", "model_id", "parameters", "approved_at",
                   "character_id", "scene_id", "source_asset_ids"}
        if not isinstance(fields, dict) or set(fields) - allowed:
            raise ValueError("unsupported asset metadata fields")
        if len(json.dumps(fields, ensure_ascii=False).encode()) > 64 * 1024:
            raise ValueError("asset metadata exceeds 64 KiB")
        for key, value in fields.items():
            if key == "parameters":
                if not isinstance(value, dict):
                    raise ValueError("asset parameters must be an object")
            elif key == "source_asset_ids":
                if not isinstance(value, list) or len(value) > 100:
                    raise ValueError("source_asset_ids must contain at most 100 assets")
            elif value is not None and (not isinstance(value, str) or len(value) > 240
                                        or any(ord(char) < 32 for char in value)):
                raise ValueError("invalid asset metadata value")
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, actor_id=actor_id)
            if expected_version is not None and meta["version"] != expected_version:
                from .v1_capability_service import CapabilityVersionConflict
                raise CapabilityVersionConflict(self.public(meta))
            if "parameters" in fields and not _lineage_write:
                # Legacy generation parameters are caller-controlled. They
                # cannot manufacture or erase the gated provenance authority.
                protected = meta.get("parameters", {}).get("asset_lineage_v2")
                provided = fields["parameters"].get("asset_lineage_v2")
                if "asset_lineage_v2" in fields["parameters"] and (protected is None or provided != protected):
                    raise ValueError("asset_lineage_v2 requires scoped versioned annotation")
                if protected is not None:
                    fields = {**fields, "parameters": {**fields["parameters"], "asset_lineage_v2": protected}}
            self._verified_content(meta)
            inherited_features = set(meta.get("_required_features", []))
            inherited_owner = meta.get("_owner_actor_id")
            for source_id in fields.get("source_asset_ids", []):
                source = self.get(source_id, branch_id=branch_id, actor_id=actor_id)
                inherited_features.update(source.get("_required_features", []))
                if source.get("_owner_actor_id"):
                    if inherited_owner not in {None, source["_owner_actor_id"]}: raise ValueError("asset source owners differ")
                    inherited_owner = source["_owner_actor_id"]
                if (source_id == asset_id or source.get("novel_id") != meta.get("novel_id")
                        or source.get("branch_id") != meta.get("branch_id")):
                    raise ValueError("source assets must be different assets in the same project and branch")
                self._verified_content(source)
            pending, visited = list(fields.get("source_asset_ids", [])), set()
            while pending:
                source_id = pending.pop()
                if source_id == asset_id:
                    raise ValueError("asset source relationship would create a cycle")
                if source_id in visited:
                    continue
                visited.add(source_id)
                source = self.get(source_id, branch_id=branch_id, include_deleted=True, actor_id=actor_id)
                pending.extend(source.get("source_asset_ids") or [])
            origin_changed = inherited_features != set(meta.get("_required_features", [])) or inherited_owner != meta.get("_owner_actor_id")
            if any(meta.get(key) != value for key, value in fields.items()) or origin_changed:
                meta.update(fields)
                if inherited_features or inherited_owner:
                    meta.update(_required_features=sorted(inherited_features), _owner_actor_id=inherited_owner)
                meta.update(updated_at=now(), version=int(meta.get("version", 1)) + 1)
                self._write_meta(meta)
            return meta

    def promote_owned(self, asset_id: str, *, actor_id: str, branch_id: str | None, expected_version: int, provenance: dict, guard=None):
        """Server-only explicit review: retain origin, identity and bytes."""
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, actor_id=actor_id)
            saved_provenance = {**copy.deepcopy(provenance), "review_actor": actor_id}
            if meta.get("_owner_actor_id") is None and meta.get("_origin_provenance") == saved_provenance and expected_version in {meta["version"], meta["version"] - 1}:
                if guard: guard()
                return self.public(meta)
            if meta.get("_owner_actor_id") != actor_id:
                raise FileNotFoundError(asset_id)
            if meta["version"] != expected_version:
                from .v1_capability_service import CapabilityVersionConflict
                raise CapabilityVersionConflict(self.public(meta))
            self._verified_content(meta)
            if guard: guard()
            meta.update(_owner_actor_id=None, _origin_provenance=saved_provenance,
                        approved_at=now(), updated_at=now(), version=meta["version"] + 1)
            self._write_meta(meta)
            return self.public(meta)

    def annotate_lineage(self, asset_id: str, declaration: dict, parent_ids: list[str], *,
                         branch_id: str | None, expected_version: int, guard=None):
        """Extend the existing DAG in its existing mutation boundary.

        The experimental caller validates the declaration and chapter scope.
        Parent revisions are measured here, under the same lock as cycle
        validation and the write, so callers cannot supply fictional digests.
        """
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id)
            parents = {}
            for parent_id in dict.fromkeys(parent_ids):
                parent = self.get(parent_id, branch_id=branch_id)
                if parent.get("novel_id") != meta.get("novel_id") or parent.get("branch_id") != meta.get("branch_id"):
                    raise FileNotFoundError(parent_id)
                self._verified_content(parent)
                parents[parent_id] = {"version": parent["version"], "digest": parent["sha256"]}
            lineage = {**declaration, "parents": parents, "output_digest": meta["sha256"]}
            previous = meta.get("parameters", {}).get("asset_lineage_v2")
            if isinstance(previous, dict):
                lineage["history"] = list(previous.get("history", [])) + [
                    {**{key: value for key, value in previous.items() if key != "history"}, "asset_version": meta["version"]}]
            parameters = {**meta.get("parameters", {}), "asset_lineage_v2": lineage}
            if guard:
                guard()
            return self.update_metadata(asset_id, {"parameters": parameters, "source_asset_ids": list(parents)},
                                        branch_id=branch_id, expected_version=expected_version, _lineage_write=True)

    def delete(self, asset_id: str, *, branch_id: str | None = None):
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, include_deleted=True)
            if not meta.get("deleted_at"):
                meta.update(deleted_at=now(), updated_at=now(), version=int(meta.get("version", 1)) + 1)
                self._write_meta(meta)
            # Keep original bytes and identity. Existing reads deliberately 404.
            return {"id": asset_id, "deleted": True, "recoverable": True,
                    "sha256": meta["sha256"], "version": meta["version"]}

    def restore(self, asset_id: str, *, branch_id: str | None = None):
        with self._lock, workspace_mutation(self.root, "asset-library"):
            meta = self.get(asset_id, branch_id=branch_id, include_deleted=True)
            self._verified_content(meta)
            if meta.get("deleted_at"):
                meta.update(deleted_at=None, updated_at=now(), version=int(meta.get("version", 1)) + 1)
                self._write_meta(meta)
            return meta
