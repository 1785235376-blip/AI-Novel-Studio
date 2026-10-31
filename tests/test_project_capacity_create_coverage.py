"""Every original AssetLibraryService.create writer is capacity-admitted.

ENABLE_PROJECT_CAPACITY_ADMISSION now makes the shared asset owner reconcile and
reserve before any original create caller writes bytes, not just the manual
import route. Synthetic File backend only; real PostgreSQL/browser/model are not
exercised here.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from app.config import settings
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def capacity_on():
    previous = settings.enable_project_capacity_admission
    object.__setattr__(settings, "enable_project_capacity_admission", True)
    try:
        yield
    finally:
        object.__setattr__(settings, "enable_project_capacity_admission", previous)


def ledger_path(rig) -> Path:
    return Path(rig.root) / "runtime" / "project-capacity.json"


def record(rig) -> dict:
    return json.loads(ledger_path(rig).read_text(encoding="utf-8"))["projects"][rig.nid]


def create(rig, name: str, content: bytes, *, key: str | None = None):
    return rig.assets.create(rig.nid, name, base64.b64encode(content).decode("ascii"),
                             "application/octet-stream", "file", key,
                             required_features=())


def activate(rig):
    rig.workspace.activate(rig.nid, rig.scope, "local-author")


def test_direct_asset_create_reconciles_reserves_and_commits(rig, capacity_on):
    activate(rig)
    assert not ledger_path(rig).exists()
    rig.workspace.capacity_reconcile(rig.nid, rig.scope, "local-author")
    before = record(rig)["used_bytes"]
    asset = create(rig, "cap-cover.bin", b"x" * 40)
    assert (Path(rig.assets.root) / f"{asset['id']}.bin").exists()
    value = record(rig)
    assert value["reservations"] == {}
    landed = sum((Path(rig.assets.root) / f"{asset['id']}.{suffix}").stat().st_size
                 for suffix in ("bin", "json"))
    assert value["used_bytes"] - before == landed
    assert any(entry["action"] == "COMMIT" for entry in value["audit"])


def test_idempotent_replay_is_not_double_charged(rig, capacity_on):
    activate(rig)
    first = create(rig, "cap-replay.bin", b"y" * 20, key="cap-replay-key")
    used = record(rig)["used_bytes"]
    second = create(rig, "cap-replay.bin", b"y" * 20, key="cap-replay-key")
    assert second["id"] == first["id"]
    assert record(rig)["used_bytes"] == used
    assert record(rig)["reservations"] == {}


def test_failed_create_releases_reservation_without_free_residue(rig, capacity_on, monkeypatch):
    activate(rig)
    import app.services.asset_library_service as owner
    original = owner.atomic_write

    def failing(path, value):
        raise OSError("synthetic failure before current metadata commit")
    monkeypatch.setattr(owner, "atomic_write", failing)
    rig.workspace.capacity_reconcile(rig.nid, rig.scope, "local-author")
    baseline = record(rig)["used_bytes"]
    def asset_files():
        return {path.name for pattern in ("*.bin", "*.json")
                for path in Path(rig.assets.root).glob(pattern)}
    before = asset_files()
    with pytest.raises(OSError):
        create(rig, "cap-fail.bin", b"z" * 10)
    monkeypatch.setattr(owner, "atomic_write", original)
    after = asset_files()
    assert after == before  # unindexed binary is cleaned by the original owner
    value = record(rig)
    assert value["reservations"] == {}
    assert value["used_bytes"] == baseline


def test_over_limit_create_is_refused_before_any_asset_bytes(rig, capacity_on):
    activate(rig)
    create(rig, "cap-first.bin", b"a" * 8)
    data = json.loads(ledger_path(rig).read_text(encoding="utf-8"))
    data["projects"][rig.nid]["limit_bytes"] = 100
    ledger_path(rig).write_text(json.dumps(data), encoding="utf-8")
    files = {path.name for path in Path(rig.assets.root).glob("*")}
    with pytest.raises(ValueError, match="PROJECT_CAPACITY_EXCEEDED"):
        create(rig, "cap-over.bin", b"b" * 1024)
    assert {path.name for path in Path(rig.assets.root).glob("*")} == files
    assert record(rig)["reservations"] == {}


def test_default_off_creates_no_ledger(rig):
    activate(rig)
    assert not ledger_path(rig).exists()
    create(rig, "cap-off.bin", b"c" * 8)
    assert not ledger_path(rig).exists()
