from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class HarnessAccessAuditService:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path(__file__).resolve().parents[2] / "data" / "harness_access_audit.json")
        self._lock = Lock()

    def _read(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def append(self, *, novel_id: str, chapter: int, agent_id: str, scopes: list[str], outcome: str = "success"):
        event = {"at": datetime.now(timezone.utc).isoformat(), "novel_id": novel_id, "chapter": chapter, "agent_id": agent_id, "scopes": scopes, "outcome": outcome}
        with self._lock:
            entries = self._read()[-99:] + [event]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        return event

    def list(self, limit: int = 20, novel_id: str | None = None, agent_id: str | None = None, outcome: str | None = None):
        with self._lock:
            entries = self._read()
            if novel_id: entries = [item for item in entries if item.get("novel_id") == novel_id]
            if agent_id: entries = [item for item in entries if item.get("agent_id") == agent_id]
            if outcome: entries = [item for item in entries if item.get("outcome") == outcome]
            return entries[-max(1, min(limit, 100)):][::-1]

    def clear(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]", encoding="utf-8")
        return {"cleared": True}


harness_access_audit_service = HarnessAccessAuditService()
