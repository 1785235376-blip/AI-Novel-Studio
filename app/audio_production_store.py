from __future__ import annotations

import copy
import json
import re
import threading
from pathlib import Path
from typing import Callable, TypeVar

from .config import settings
from .storage import atomic_write

T = TypeVar("T")
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class AudioProductionStore:
    """Single-process durable store; mutations serialize a full read/modify/write.

    Corrupt state fails closed instead of replacing a user's queue with emptiness.
    Completed history and active jobs are never silently truncated.
    """
    def __init__(self, root: Path | None = None):
        self.root = root or settings.data_path() / "audio-production"
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(str(self.root.resolve()), threading.RLock())

    def for_actor(self, actor_id: str):
        import hashlib
        if not actor_id: raise ValueError("actor id is required")
        scoped=AudioProductionStore(self.root / "actors" / hashlib.sha256(actor_id.encode()).hexdigest())
        scoped.owner_actor_id=actor_id
        return scoped

    def for_branch(self, branch_id: str | None):
        if branch_id is None: return self
        if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,199}", branch_id) or branch_id in {".", ".."}:
            raise ValueError("invalid branch id")
        return AudioProductionStore(self.root / "branches" / branch_id)

    def _path(self, novel_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,199}", novel_id) or novel_id in {".", ".."}:
            raise ValueError("invalid novel id")
        return self.root / f"{novel_id}.json"

    def _load(self, novel_id: str) -> dict:
        path = self._path(novel_id)
        with self._lock:
            if not path.exists():
                return {"voice_bindings": [], "pronunciation_dictionary": [], "jobs": [], "generations": []}
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or any(not isinstance(data.get(key, []), list) for key in ("voice_bindings", "pronunciation_dictionary", "jobs", "generations")):
                raise ValueError("AUDIO_STATE_INVALID: restore the audio production backup")
            return {key: list(data.get(key, [])) for key in ("voice_bindings", "pronunciation_dictionary", "jobs", "generations")}

    @staticmethod
    def visible(row):
        from .experimental.flags import enabled_flags
        if row.get("safe_batch_binding"):
            from .experimental.safe_batch_voice import batch_voice_visible
            if not batch_voice_visible(row): return False
        return not row.get("experimental_origin") or row["experimental_origin"] in enabled_flags()

    def load(self, novel_id: str) -> dict:
        data = self._load(novel_id)
        for key in ("jobs", "generations"):
            data[key] = [row for row in data[key] if self.visible(row)]
        return data

    def save(self, novel_id: str, data: dict) -> dict:
        payload = {key: list(data.get(key, [])) for key in ("voice_bindings", "pronunciation_dictionary", "jobs", "generations")}
        with self._lock:
            path = self._path(novel_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    def mutate(self, novel_id: str, operation: Callable[[dict], T]) -> T:
        with self._lock:
            state = self._load(novel_id)
            result = operation(state)
            self.save(novel_id, state)
            return copy.deepcopy(result)


audio_production_store = AudioProductionStore()
