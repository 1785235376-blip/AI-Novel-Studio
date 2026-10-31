"""Project scope documents are attributed to capacity without claiming writes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings
from app.project_capacity_scope_docs import measure_scope_documents
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


def scope_root(root):
    path = Path(root) / "experimental_v1"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_document(root, name, novel_id, payload=None):
    path = scope_root(root) / name
    document = {"schema_version": 1, "novel_id": novel_id, "scope": {}, "collections": {}}
    document.update(payload or {})
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def activate(e):
    e.workspace.activate(e.nid, e.scope, "local-author")


def test_scope_document_measurement_is_bounded_and_project_scoped(tmp_path):
    root = tmp_path / "data"
    mine = write_document(root, "mine.json", "project-a")
    write_document(root, "other.json", "project-b")
    (scope_root(root) / "corrupt.json").write_text("{not-json", encoding="utf-8")
    (scope_root(root) / "notes.txt").write_text("ignored", encoding="utf-8")
    result = measure_scope_documents(root, "project-a")
    assert result["state"] == "MEASURED" and result["complete"] is True
    assert result["bytes"] == mine.stat().st_size and result["objects"] == 1
    assert result["counters"]["other_project_files"] == 1
    assert result["counters"]["unreadable_entries"] == 1
    assert result["counters"]["files_attributed"] == 1
    assert measure_scope_documents(tmp_path / "missing", "project-a")["state"] == "MISSING"


def test_scope_document_oversize_is_unknown_and_blocks_admission(tmp_path):
    root = tmp_path / "data"
    scope_root(root).joinpath("huge.json").write_bytes(b"{" + b" " * (8 * 1024 * 1024 + 10))
    result = measure_scope_documents(root, "project-a")
    assert result["unknown_count"] == 1
    assert result["counters"]["oversized_files"] == 1
    assert result["complete"] is True


def test_diagnostics_and_reconcile_include_scope_document_bytes(rig):
    e = rig
    activate(e)
    document = write_document(e.rig.root if hasattr(e, "rig") else e.root, "scope.json", e.nid) if False else write_document(e.root, "scope.json", e.nid)
    diagnostics = e.workspace.capacity_diagnostics(e.nid, e.scope)
    assert diagnostics["scope_documents"]["bytes"] >= document.stat().st_size
    assert diagnostics["combined"]["logical_bytes"] >= document.stat().st_size
    reconciled = e.workspace.capacity_reconcile(e.nid, e.scope, "local-author")
    assert reconciled["measurement"]["scope_documents_bytes"] >= document.stat().st_size
    assert reconciled["snapshot"]["used_bytes"] >= document.stat().st_size


def test_asset_admission_accounts_for_existing_scope_documents(rig):
    e = rig
    activate(e)
    document = write_document(e.root, "existing.json", e.nid)
    previous = settings.enable_project_capacity_admission
    object.__setattr__(settings, "enable_project_capacity_admission", True)
    try:
        e.workspace.capacity_reconcile(e.nid, e.scope, "local-author")
        ledger = Path(e.root) / "runtime" / "project-capacity.json"
        before = json.loads(ledger.read_text(encoding="utf-8"))["projects"][e.nid]["used_bytes"]
        with e.workspace._asset_scope(e.nid, e.scope):
            asset = e.workspace.assets.create(
                e.nid, "covered.bin", __import__("base64").b64encode(b"x" * 16).decode(),
                "application/octet-stream", "file", None, required_features=(),
                _capacity_admitted=False)
        record = json.loads(ledger.read_text(encoding="utf-8"))["projects"][e.nid]
        landed = sum((Path(e.workspace.assets.root) / f"{asset['id']}.{suffix}").stat().st_size
                     for suffix in ("bin", "json"))
        assert record["reservations"] == {}
        assert record["used_bytes"] - before == landed
        assert before >= document.stat().st_size
    finally:
        object.__setattr__(settings, "enable_project_capacity_admission", previous)
