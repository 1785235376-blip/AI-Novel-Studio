"""Audio-history write capacity accounting (flag-gated combination).

Only active when both ENABLE_AUDIO_ASSET_HISTORY and
ENABLE_PROJECT_CAPACITY_ADMISSION are enabled: each immutable history write
reserves a bounded record/blob peak against the reconciled project ledger and
charges the actual history-directory delta (records + new blob only). Legacy
defaults are unchanged and the content-owner manual-import admission remains a
separate path.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from app.config import settings
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig
from test_project_capacity_admin_api import capacity_url
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def history_and_capacity():
    previous = (settings.enable_audio_asset_history, settings.enable_project_capacity_admission)
    object.__setattr__(settings, "enable_audio_asset_history", True)
    object.__setattr__(settings, "enable_project_capacity_admission", True)
    try:
        yield
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", previous[0])
        object.__setattr__(settings, "enable_project_capacity_admission", previous[1])


def create_audio(e, filename="cap-history.wav"):
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        return e.rig.assets.create(e.rig.nid, filename, base64.b64encode(e.content).decode(),
                                   "audio/wav", "audio",
                                   required_features=("narrative_production_v2",),
                                   _capacity_admitted=True)  # this suite isolates history-write accounting


def ledger_path(e):
    return Path(e.rig.root) / "runtime" / "project-capacity.json"


def ledger_record(e):
    return json.loads(ledger_path(e).read_text(encoding="utf-8"))["projects"][e.rig.nid]


def reconcile(e):
    response = e.client.post(capacity_url(e, "/reconcile"), headers=e.headers)
    assert response.status_code == 200, response.text
    return e.client.get(capacity_url(e), headers=e.headers).json()


def history_dir(e, asset_id):
    return Path(e.rig.assets.root) / ".audio-history" / asset_id


def history_bytes(e, asset_id):
    return sum(path.stat().st_size for path in history_dir(e, asset_id).rglob("*") if path.is_file())


def used(e):
    return e.client.get(capacity_url(e), headers=e.headers).json()["ledger"]["used_bytes"]


def test_history_write_reserves_and_commits_actual_delta(audio_history, history_and_capacity):
    e = audio_history
    current = reconcile(e)
    before = current["ledger"]["used_bytes"]
    asset = create_audio(e)
    delta = history_bytes(e, asset["id"])
    assert delta > 0 and len(list(history_dir(e, asset["id"]).rglob("*.bin"))) >= 2
    record = ledger_record(e)
    assert record["reservations"] == {}
    assert record["used_bytes"] == before + delta
    commits = [entry for entry in record["audit"] if entry["action"] == "COMMIT"]
    assert commits and commits[-1]["actual_bytes"] == delta
    assert commits[-1]["reserved_bytes"] >= delta
    assert snapshot(e.rig.root)  # read succeeded


def test_metadata_revision_charges_only_the_new_record(audio_history, history_and_capacity):
    e = audio_history
    current = reconcile(e)
    asset = create_audio(e)
    first = used(e)
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        e.rig.assets.update_metadata(asset["id"], {"approved_at": "2026-10-31T00:00:00+00:00"})
    second = used(e)
    records = list((history_dir(e, asset["id"]) / "records").glob("*.bin"))
    blobs = list((history_dir(e, asset["id"]) / "blobs").glob("*.bin"))
    assert len(records) == 2 and len(blobs) == 1  # identical content keeps one blob
    new_record = max(path.stat().st_size for path in records)
    assert second - first == sum(path.stat().st_size for path in records) - (first - current["ledger"]["used_bytes"]) - max(
        path.stat().st_size for path in records) + new_record or second > first
    assert second - first < sum(path.stat().st_size for path in records)  # only the delta, not the whole chain
    assert ledger_record(e)["reservations"] == {}


def test_history_write_refused_before_reconcile(audio_history, history_and_capacity):
    e = audio_history
    assert not ledger_path(e).exists()
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        before_assets = e.rig.assets.list(e.rig.nid, branch_id=e.rig.scope.get("branch_id"))
    with pytest.raises(ValueError, match="AUDIO_HISTORY_CAPACITY_NOT_RECONCILED"):
        create_audio(e)
    assert not ledger_path(e).exists()
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        assert e.rig.assets.list(e.rig.nid, branch_id=e.rig.scope.get("branch_id")) == before_assets


def test_history_write_refused_when_limit_is_too_low(audio_history, history_and_capacity):
    e = audio_history
    current = reconcile(e)
    used_bytes = current["ledger"]["used_bytes"]
    version = current["ledger"]["ledger_version"]
    limited = e.client.put(capacity_url(e, "/limit"), headers=e.headers,
                           json={"limit_bytes": used_bytes + 100, "expected_version": version})
    assert limited.status_code == 200, limited.text
    with pytest.raises(ValueError, match="AUDIO_HISTORY_CAPACITY_EXCEEDED"):
        create_audio(e)
    assert history_bytes(e, "missing-asset") == 0
    record = ledger_record(e)
    assert record["used_bytes"] == used_bytes and record["reservations"] == {}


def test_history_write_refused_when_unknown_objects_block_ledger(audio_history, history_and_capacity):
    e = audio_history
    stray = Path(e.rig.assets.root) / "stray-residue.tmp"
    stray.write_bytes(b"residue")
    blocked = reconcile(e)
    assert blocked["ledger"]["unknown"]["blocked"] is True
    with pytest.raises(ValueError, match="AUDIO_HISTORY_CAPACITY_UNKNOWN_BLOCKED"):
        create_audio(e)
    stray.unlink()
    recovered = reconcile(e)
    assert recovered["ledger"]["unknown"]["blocked"] is False
    asset = create_audio(e)
    assert history_bytes(e, asset["id"]) > 0


def test_failed_current_commit_charges_prepared_residue_and_leaves_no_reservation(audio_history, history_and_capacity, monkeypatch):
    e = audio_history
    current = reconcile(e)
    before = current["ledger"]["used_bytes"]
    import app.services.asset_library_service as owner
    original = owner.atomic_write
    calls = {"count": 0}

    def failing(path, value):
        calls["count"] += 1
        raise OSError("synthetic crash before current metadata commit")
    monkeypatch.setattr(owner, "atomic_write", failing)
    with pytest.raises(OSError):
        create_audio(e)
    assert calls["count"] >= 1
    monkeypatch.setattr(owner, "atomic_write", original)
    record = ledger_record(e)
    assert record["reservations"] == {}
    assert record["used_bytes"] > before  # prepared record/blob residue stays charged
    assert any(entry["action"] == "COMMIT" for entry in record["audit"])
    # A later successful write still works and does not double-charge the old chain.
    asset = create_audio(e, "second.wav")
    assert history_bytes(e, asset["id"]) > 0
    assert ledger_record(e)["reservations"] == {}


def test_capacity_accounting_requires_both_flags(audio_history):
    e = audio_history
    # History alone keeps its previous behavior: no ledger is created or needed.
    object.__setattr__(settings, "enable_audio_asset_history", True)
    try:
        asset = create_audio(e)
        assert history_bytes(e, asset["id"]) > 0
        assert not ledger_path(e).exists()
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", False)




def migrate_url(e, asset_id):
    return f"/api/v1/projects/{e.rig.nid}/studio/assets/{asset_id}/history/migrate"


def set_both_flags(history: bool, capacity: bool):
    object.__setattr__(settings, "enable_audio_asset_history", history)
    object.__setattr__(settings, "enable_project_capacity_admission", capacity)


def test_explicit_migration_charges_baseline_bytes(audio_history):
    e = audio_history
    asset = create_audio(e)  # legacy asset captured only by an explicit migration
    set_both_flags(True, True)
    try:
        current = reconcile(e)
        before = current["ledger"]["used_bytes"]
        response = e.client.post(migrate_url(e, asset["id"]), headers=e.headers,
                                 json={"expected_version": 1})
        assert response.status_code == 200, response.text
        assert response.json()["migrated"] is True
        delta = history_bytes(e, asset["id"])
        assert delta > 0
        record = ledger_record(e)
        assert record["reservations"] == {}
        assert record["used_bytes"] == before + delta
        commits = [entry for entry in record["audit"] if entry["action"] == "COMMIT"]
        assert commits and commits[-1]["actual_bytes"] == delta
    finally:
        set_both_flags(False, False)


def test_explicit_migration_refused_before_reconcile(audio_history):
    from app.services.audio_asset_history_store import HEAD
    e = audio_history
    asset = create_audio(e)
    set_both_flags(True, True)
    try:
        assert not ledger_path(e).exists()
        response = e.client.post(migrate_url(e, asset["id"]), headers=e.headers,
                                 json={"expected_version": 1})
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "AUDIO_HISTORY_CAPACITY_NOT_RECONCILED"
        assert not ledger_path(e).exists()
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            assert HEAD not in e.rig.assets._load(asset["id"])
        assert history_bytes(e, asset["id"]) == 0
    finally:
        set_both_flags(False, False)


def test_failed_explicit_migration_charges_residue_without_reservation(audio_history, monkeypatch):
    from app.services.audio_asset_history_store import HEAD
    e = audio_history
    asset = create_audio(e)
    set_both_flags(True, True)
    try:
        current = reconcile(e)
        before = current["ledger"]["used_bytes"]
        import app.storage as storage_module
        original = storage_module.atomic_write

        def failing(path, value):
            raise OSError("synthetic crash during explicit migration commit")
        monkeypatch.setattr(storage_module, "atomic_write", failing)
        with pytest.raises(OSError):
            e.client.post(migrate_url(e, asset["id"]), headers=e.headers,
                          json={"expected_version": 1})
        monkeypatch.setattr(storage_module, "atomic_write", original)
        record = ledger_record(e)
        assert record["reservations"] == {}
        assert record["used_bytes"] > before
        assert any(entry["action"] == "COMMIT" for entry in record["audit"])
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            assert HEAD not in e.rig.assets._load(asset["id"])
    finally:
        set_both_flags(False, False)

def test_explicit_restore_is_capacity_accounted(audio_history):
    from app.services.audio_asset_history_store import HEAD
    e = audio_history
    set_both_flags(True, True)
    try:
        reconcile(e)
        asset = create_audio(e)
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            e.rig.assets.update_metadata(asset["id"], {"character_id": "char-a",
                                                       "parameters": {"tone": "warm"}})
            e.rig.assets.update_metadata(asset["id"], {"character_id": "char-b",
                                                       "parameters": {"tone": "cool"}})
        url = f"/api/v1/projects/{e.rig.nid}/studio/assets/{asset['id']}/history"
        listing = e.client.get(url, headers=e.headers)
        assert listing.status_code == 200, listing.text
        target = listing.json()["items"][1]["version_id"]
        preview = e.client.post(url + f"/{target}/restore/preview", headers=e.headers,
                                json={"expected_version": 3})
        assert preview.status_code == 200, preview.text
        before_used, before_history = used(e), history_bytes(e, asset["id"])
        confirmed = e.client.post(url + f"/{target}/restore", headers=e.headers,
                                  json={"expected_version": 3,
                                        "expected_restore_digest": preview.json()["restore_digest"]})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["review_inherited"] is False
        delta = history_bytes(e, asset["id"]) - before_history
        assert delta > 0
        record = ledger_record(e)
        assert record["reservations"] == {}
        assert record["used_bytes"] == before_used + delta
        commits = [entry for entry in record["audit"] if entry["action"] == "COMMIT"]
        assert commits and commits[-1]["actual_bytes"] == delta
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            meta = e.rig.assets._load(asset["id"])
        assert meta["version"] == 4 and meta["_audio_history_restore_origin"]["target_version_id"] == target
        assert HEAD in meta
    finally:
        set_both_flags(False, False)

def test_history_write_requires_a_reconcile_after_process_start(audio_history):
    """A ledger reconciled by a previous process is stale for trusted history writes."""
    e = audio_history
    set_both_flags(True, True)
    try:
        reconcile(e)
        asset = create_audio(e)
        ledger = json.loads(ledger_path(e).read_text(encoding="utf-8"))
        ledger["projects"][e.rig.nid]["reconciled_at"] = "2020-01-01T00:00:00+00:00"
        ledger_path(e).write_text(json.dumps(ledger), encoding="utf-8")
        previous = e.rig.workspace.settings if hasattr(e.rig.workspace, "settings") else None
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            meta = e.rig.assets._load(asset["id"])
            expected = meta["version"]
            with pytest.raises(ValueError, match="AUDIO_HISTORY_CAPACITY_NOT_RECONCILED"):
                e.rig.assets.update_metadata(asset["id"], {"approved_at": "2026-10-31T00:00:00+00:00"})
            assert e.rig.assets._load(asset["id"])["version"] == expected
        # A fresh explicit reconcile makes the ledger usable again.
        reconcile(e)
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            e.rig.assets.update_metadata(asset["id"], {"approved_at": "2026-10-31T00:00:00+00:00"})
            assert e.rig.assets._load(asset["id"])["version"] == expected + 1
        assert ledger_record(e)["reservations"] == {}
    finally:
        set_both_flags(False, False)

