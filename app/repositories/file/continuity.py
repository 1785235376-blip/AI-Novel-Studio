from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from copy import deepcopy
from ...storage import atomic_write
from .finding_lock import continuity_write


class FileContinuityRepository:
    """Small append-only JSON repository for typed continuity records."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, kind: str) -> Path:
        return self.root / f"continuity_{kind}.json"

    def _read(self, kind: str) -> list[dict[str, Any]]:
        path = self._path(kind)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, kind: str, rows: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write(self._path(kind), json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2))

    @continuity_write
    def create(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._read(kind)
        for row in rows:
            if row.get("id") == payload.get("id"):
                return row
        rows.append(dict(payload))
        self._write(kind, rows)
        return dict(payload)

    def get_by_id(self, kind: str, record_id: str) -> dict[str, Any]:
        for row in self._read(kind):
            if row.get("id") == record_id:
                return row
        raise KeyError(record_id)

    def list_by_project(self, kind: str, project_id: str) -> list[dict[str, Any]]:
        return sorted([row for row in self._read(kind) if row.get("project_id") == project_id], key=lambda row: row.get("id", ""))

    def list_by_character(self, kind: str, character_id: str) -> list[dict[str, Any]]:
        return sorted([row for row in self._read(kind) if row.get("character_id") == character_id or row.get("source_character_id") == character_id or row.get("target_character_id") == character_id], key=lambda row: row.get("id", ""))

    def list_by_evidence(self, kind: str, evidence_id: str) -> list[dict[str, Any]]:
        return sorted([row for row in self._read(kind) if evidence_id in row.get("evidence_ids", [])], key=lambda row: row.get("id", ""))

    @continuity_write
    def set_finding_status(self, finding_id: str, status: str) -> dict[str, Any]:
        rows=self._read("findings")
        for row in rows:
            if row.get("id")==finding_id:
                row["status"]=status; self._write("findings",rows); return row
        raise KeyError(finding_id)

    @continuity_write
    def mutate_finding(self, project, finding_id, callback):
        rows = self._read("findings")
        index = next((i for i, row in enumerate(rows) if row["id"] == finding_id), None)
        old = rows[index] if index is not None else None
        if old is not None and old.get("project_id") != project: raise FileNotFoundError(finding_id)
        result = callback(deepcopy(old))
        if result.get("project_id") != project or result.get("id") != finding_id: raise ValueError("FINDING_SCOPE_MISMATCH")
        if index is None: rows.append(result)
        else: rows[index] = result
        self._write("findings", rows)
        return deepcopy(result)
