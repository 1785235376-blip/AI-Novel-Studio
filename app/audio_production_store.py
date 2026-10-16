from __future__ import annotations

import copy
from contextlib import contextmanager
import json
import os
import re
import threading
from pathlib import Path
from typing import Callable, TypeVar

from .config import settings
from .repositories.file.mutation_coordinator import workspace_mutation
from .storage import atomic_write

T = TypeVar("T")
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class AudioStateVersionConflict(RuntimeError):
    """The callback ran once, but another process changed its input snapshot."""
    code = "AUDIO_STATE_VERSION_CONFLICT"
    status = 409

    def __init__(self):
        super().__init__("原音频队列已被另一进程更新；请读取当前回执，不要自动重放操作")


class AudioProductionStore:
    """Original durable audio store with short cross-process snapshot CAS writes.

    Corrupt state fails closed instead of replacing a user's queue with emptiness.
    Completed history and active jobs are never silently truncated.
    Callbacks retain the original process RLock, without the new file fence.
    A CAS conflict never replays source/provider/asset effects in a callback.
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

    @contextmanager
    def _file_fence(self, novel_id: str):
        path = self._path(novel_id)
        # All save/mutate writers to this actor/branch's same original file use
        # one existing coordinator key. Windows path aliases share that key.
        root = Path(os.path.normcase(str(self.root.resolve())))
        with workspace_mutation(root, "audio-production-file:" + os.path.normcase(path.name)):
            yield

    @staticmethod
    def _snapshot(state: dict) -> str:
        # Retain the legacy JSON value semantics; this is a whole-state CAS
        # token, never a user-visible receipt or an execution proof.
        return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

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

    def load(self, novel_id: str, *, include_studio: bool = False) -> dict:
        data = self._load(novel_id)
        for key in ("jobs", "generations"):
            # Studio rows require their scope/incarnation owner, even when the
            # experimental feature is enabled. Legacy readers keep their view.
            data[key] = [row for row in data[key] if self.visible(row) and
                         (include_studio or row.get("studio_origin") != "studio-audio-execution/1")]
        return data

    def save(self, novel_id: str, data: dict, *, include_studio: bool = False) -> dict:
        payload = {key: list(data.get(key, [])) for key in ("voice_bindings", "pronunciation_dictionary", "jobs", "generations")}
        with self._lock, self._file_fence(novel_id):
            if not include_studio:
                # A legacy load -> save receives a filtered view. Preserve the
                # original Studio rows verbatim; it cannot replace, inject or
                # shadow their job identities through that view.
                current = self._load(novel_id)
                studio_jobs = [row for row in current["jobs"] if isinstance(row, dict) and row.get("studio_origin") == "studio-audio-execution/1"]
                job_ids = {row["id"] for row in studio_jobs}
                for key in ("jobs", "generations"):
                    identifier = "id" if key == "jobs" else "job_id"
                    preserved = [row for row in current[key] if isinstance(row, dict) and row.get("studio_origin") == "studio-audio-execution/1"]
                    payload[key] = [row for row in payload[key] if not isinstance(row, dict) or
                                    (row.get("studio_origin") != "studio-audio-execution/1" and row.get(identifier) not in job_ids)] + preserved
            path = self._path(novel_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        if include_studio: return payload
        return {key: [row for row in rows if not isinstance(row, dict) or row.get("studio_origin") != "studio-audio-execution/1"]
                if key in {"jobs", "generations"} else rows for key, rows in payload.items()}

    def mutate(self, novel_id: str, operation: Callable[[dict], T]) -> T:
        with self._lock:
            with self._file_fence(novel_id):
                state = self._load(novel_id)
                before = self._snapshot(state)
            # Existing V1 callbacks can call original source/asset owners. The
            # new cross-process fence must not span those callbacks. Studio
            # callbacks are pure row CAS changes; their effects occur outside.
            result = operation(state)
            with self._file_fence(novel_id):
                if self._snapshot(self._load(novel_id)) != before:
                    raise AudioStateVersionConflict()
                # save() reacquires this same original RLock/coordinator key;
                # both are reentrant. No callback is invoked during the write.
                self.save(novel_id, state, include_studio=True)
            return copy.deepcopy(result)


audio_production_store = AudioProductionStore()
