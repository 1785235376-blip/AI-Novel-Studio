"""Flag-gated capacity admission for the original Studio manual import owner.

Default-off must keep the historical closed behavior. With
``ENABLE_PROJECT_CAPACITY_ADMISSION`` enabled the original asset owner still
performs the write, but the capacity ledger must reconcile first, refuse UNKNOWN
residue, reserve the content+metadata peak and commit only the landed bytes.
These are File-only synthetic tests; no real model/PG is involved.
"""
from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path

import pytest

from app.config import settings
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only

SYNTHETIC_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8A"
    "AwMCAO+a9skAAAAASUVORK5CYII="
)


def payload(key="capacity-admission-1"):
    return {"filename": "synthetic.png", "kind": "image",
            "content_base64": SYNTHETIC_PNG_B64, "idempotency_key": key}


def capacity_url(e, suffix="", alias=True):
    prefix = "/api/v1" if alias else "/api"
    return f"{prefix}/projects/{e.rig.nid}/studio/capacity{suffix}"


def upload_url(e, alias=True):
    prefix = "/api/v1" if alias else "/api"
    return f"{prefix}/projects/{e.rig.nid}/studio/assets"


def ledger_path(e):
    return Path(e.rig.root) / "runtime" / "project-capacity.json"


def ledger_doc(e):
    return json.loads(ledger_path(e).read_text(encoding="utf-8"))


@pytest.fixture
def capacity_admission_enabled():
    previous = settings.enable_project_capacity_admission
    object.__setattr__(settings, "enable_project_capacity_admission", True)
    try:
        yield
    finally:
        object.__setattr__(settings, "enable_project_capacity_admission", previous)


def reconcile(e):
    response = e.client.post(capacity_url(e, "/reconcile"), headers=e.headers)
    assert response.status_code == 200, response.text
    return e.client.get(capacity_url(e), headers=e.headers).json()


def test_flag_off_keeps_manual_upload_closed(audio_history):
    e = audio_history
    before = snapshot(e.rig.root)
    response = e.client.post(upload_url(e), headers=e.headers, json=payload())
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "PROJECT_CAPACITY_WRITE_UNAVAILABLE"
    assert snapshot(e.rig.root) == before
    assert not ledger_path(e).exists()


def test_flag_on_imports_and_charges_only_landed_bytes(audio_history, capacity_admission_enabled):
    e = audio_history
    current = reconcile(e)
    used_before = current["ledger"]["used_bytes"]
    response = e.client.post(upload_url(e), headers=e.headers, json=payload())
    assert response.status_code == 201, response.text
    asset_id = response.json()["id"]
    content = Path(e.rig.assets.root) / f"{asset_id}.bin"
    metadata = Path(e.rig.assets.root) / f"{asset_id}.json"
    landed = content.stat().st_size + metadata.stat().st_size
    current = e.client.get(capacity_url(e), headers=e.headers).json()
    assert current["ledger_state"] == "AVAILABLE"
    assert current["ledger"]["used_bytes"] == used_before + landed
    assert current["ledger"]["reserved_bytes"] == 0
    audit = ledger_doc(e)["projects"][e.rig.nid]["audit"]
    commit = [entry for entry in audit if entry["action"] == "COMMIT"][-1]
    assert commit["actual_bytes"] == landed
    assert commit["reserved_bytes"] >= landed


def test_idempotent_retry_does_not_charge_twice(audio_history, capacity_admission_enabled):
    e = audio_history
    reconcile(e)
    first = e.client.post(upload_url(e), headers=e.headers, json=payload("retry-key"))
    assert first.status_code == 201, first.text
    used = e.client.get(capacity_url(e), headers=e.headers).json()["ledger"]["used_bytes"]
    second = e.client.post(upload_url(e), headers=e.headers, json=payload("retry-key"))
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    after = e.client.get(capacity_url(e), headers=e.headers).json()["ledger"]["used_bytes"]
    assert after == used


def test_over_quota_is_refused_before_any_asset_write(audio_history, capacity_admission_enabled):
    e = audio_history
    current = reconcile(e)
    used = current["ledger"]["used_bytes"]
    version = current["ledger"]["ledger_version"]
    limited = e.client.put(capacity_url(e, "/limit"), headers=e.headers,
                           json={"limit_bytes": used + 1024, "expected_version": version})
    assert limited.status_code == 200, limited.text
    before_bins = {path.name for path in Path(e.rig.assets.root).glob("*.bin")}
    response = e.client.post(upload_url(e), headers=e.headers, json=payload("quota-key"))
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "PROJECT_CAPACITY_EXCEEDED"
    ledger = ledger_doc(e)["projects"][e.rig.nid]
    assert ledger["used_bytes"] == used and ledger["reservations"] == {}
    assert {path.name for path in Path(e.rig.assets.root).glob("*.bin")} == before_bins


def test_unknown_root_residue_blocks_import_until_cleared(audio_history, capacity_admission_enabled):
    e = audio_history
    stray = Path(e.rig.assets.root) / "crashed-write-residue.tmp"
    stray.write_bytes(b"x" * 32)
    blocked = e.client.post(upload_url(e), headers=e.headers, json=payload("unknown-key"))
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "PROJECT_CAPACITY_UNKNOWN_BLOCKED"
    assert stray.exists()
    stray.unlink()
    allowed = e.client.post(upload_url(e), headers=e.headers, json=payload("unknown-key"))
    assert allowed.status_code == 201, allowed.text


def test_corrupt_ledger_fails_closed_without_write(audio_history, capacity_admission_enabled):
    e = audio_history
    ledger_path(e).parent.mkdir(parents=True, exist_ok=True)
    ledger_path(e).write_bytes(b"{broken")
    before_bins = {path.name for path in Path(e.rig.assets.root).glob("*.bin")}
    response = e.client.post(upload_url(e), headers=e.headers, json=payload("corrupt-key"))
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "PROJECT_CAPACITY_LEDGER_UNAVAILABLE"
    assert ledger_path(e).read_bytes() == b"{broken"
    assert {path.name for path in Path(e.rig.assets.root).glob("*.bin")} == before_bins


def test_disabled_flag_and_missing_marker_keeps_closed(rig):
    e = rig
    response = e.client.post(f"/api/projects/{e.nid}/studio/assets", json=payload())
    assert response.status_code == 503


def test_concurrent_admissions_only_one_lands_when_limit_is_tight(audio_history, capacity_admission_enabled):
    e = audio_history
    current = reconcile(e)
    used = current["ledger"]["used_bytes"]
    version = current["ledger"]["ledger_version"]
    # Room for one reservation (~1 MiB metadata peak + small content), not two.
    limited = e.client.put(capacity_url(e, "/limit"), headers=e.headers,
                           json={"limit_bytes": used + 1024 * 1024 + 256,
                                 "expected_version": version})
    assert limited.status_code == 200, limited.text
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(e.client.post, upload_url(e), json=payload(f"concurrent-{index}"))
                   for index in range(2)]
        responses = [future.result() for future in futures]
    codes = sorted(item.status_code for item in responses)
    assert codes == [201, 409], [(item.status_code, item.text) for item in responses]
    ledger = ledger_doc(e)["projects"][e.rig.nid]
    assert ledger["reservations"] == {}
    assert ledger["used_bytes"] > used




