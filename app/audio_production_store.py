from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from .config import settings
from .storage import atomic_write


class AudioProductionStore:
    def __init__(self, root: Path | None = None):
        self.root = root or settings.data_path() / "audio-production"
        self._lock = threading.RLock()

    def _path(self, novel_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", novel_id):
            raise ValueError("invalid novel id")
        return self.root / f"{novel_id}.json"

    def load(self, novel_id: str) -> dict:
        path = self._path(novel_id)
        with self._lock:
            if not path.exists():
                return {"voice_bindings": [], "pronunciation_dictionary": [], "jobs": [], "generations": []}
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            return {
                "voice_bindings": list(data.get("voice_bindings", [])),
                "pronunciation_dictionary": list(data.get("pronunciation_dictionary", [])),
                "jobs": list(data.get("jobs", [])),
                "generations": list(data.get("generations", [])),
            }

    def save(self, novel_id: str, data: dict) -> dict:
        payload = {
            "voice_bindings": list(data.get("voice_bindings", [])),
            "pronunciation_dictionary": list(data.get("pronunciation_dictionary", [])),
            "jobs": list(data.get("jobs", []))[-200:],
            "generations": list(data.get("generations", []))[-50:],
        }
        with self._lock:
            path = self._path(novel_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        return payload


audio_production_store = AudioProductionStore()
