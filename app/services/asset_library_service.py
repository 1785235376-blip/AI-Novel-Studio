from __future__ import annotations
import base64, hashlib, mimetypes, re, uuid
from pathlib import Path
import threading
from ..repository import atomic_write, read_json, now

class AssetLibraryService:
    MAX_BYTES = 25 * 1024 * 1024

    def __init__(self, root: Path):
        self.root = root / "assets"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _meta_path(self, asset_id: str) -> Path: return self.root / f"{asset_id}.json"
    def _bin_path(self, asset_id: str) -> Path: return self.root / f"{asset_id}.bin"

    def create(self, novel_id: str, filename: str, content_base64: str, media_type: str | None = None, kind: str = "image", idempotency_key: str | None = None):
        with self._lock:
            return self._create_locked(novel_id, filename, content_base64, media_type, kind, idempotency_key)
    def _create_locked(self, novel_id, filename, content_base64, media_type, kind, idempotency_key):
        if idempotency_key:
            for existing in self.list(novel_id):
                if existing.get("idempotency_key") == idempotency_key: return existing
        try: data = base64.b64decode(content_base64, validate=True)
        except Exception as exc: raise ValueError("content_base64 is invalid") from exc
        if not data: raise ValueError("asset content is empty")
        if len(data) > self.MAX_BYTES: raise ValueError("asset exceeds the 25 MiB limit")
        safe_name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        safe_name = re.sub(r"[\x00-\x1f\x7f]", "", safe_name).strip()
        if not safe_name: raise ValueError("asset filename is empty")
        asset_id = str(uuid.uuid4()); digest = hashlib.sha256(data).hexdigest()
        media_type = str(media_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream").strip()
        if not re.fullmatch(r"[A-Za-z0-9!#$&^_.+*-]+/[A-Za-z0-9!#$&^_.+*-]+", media_type):
            raise ValueError("asset media_type is invalid")
        meta = {"id": asset_id, "novel_id": novel_id, "filename": safe_name[:255], "kind": str(kind or "file")[:40],
                "media_type": media_type, "size": len(data), "sha256": digest,
                "created_at": now(), "updated_at": now(), "idempotency_key": idempotency_key}
        self._bin_path(asset_id).write_bytes(data)
        atomic_write(self._meta_path(asset_id), __import__('json').dumps(meta, ensure_ascii=False, indent=2))
        return meta

    def list(self, novel_id: str):
        return [read_json(p, {}) for p in self.root.glob("*.json") if read_json(p, {}).get("novel_id") == novel_id]
    def get(self, asset_id: str):
        meta = read_json(self._meta_path(asset_id), None)
        if not meta: raise FileNotFoundError(asset_id)
        return meta
    def content(self, asset_id: str):
        self.get(asset_id)
        return self._bin_path(asset_id).read_bytes()

    def delete(self, asset_id: str):
        meta = self.get(asset_id)
        self._meta_path(asset_id).unlink(missing_ok=True)
        self._bin_path(asset_id).unlink(missing_ok=True)
        return {"id": asset_id, "deleted": True, "sha256": meta.get("sha256")}
