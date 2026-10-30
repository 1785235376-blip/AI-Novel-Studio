"""Mounted capacity administration: explicit reconcile and limit adjustment.

These are File-only synthetic tests. Reconcile measures the original owners and
persists the ledger; limit changes require the original project-management
lease, the ledger CAS version and a persistent audit. Content write admission
stays closed in both routes (``admission`` is still UNAVAILABLE).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.creative.project_quota_management_authority import project_management_lease
from app.project_capacity import ProjectCapacityLedger
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig
from test_project_quota_management_authority import shared_project
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only


def capacity_url(e, suffix="", alias=False):
    prefix = f"/api{'/v1' if alias else ''}"
    return f"{prefix}/projects/{e.rig.nid}/studio/capacity{suffix}"


@pytest.mark.parametrize("alias", [False, True])
def test_explicit_reconcile_initializes_ledger_from_measurement(audio_history, alias):
    e = audio_history
    before = e.client.get(capacity_url(e, alias=alias), headers=e.headers)
    assert before.status_code == 200, before.text
    assert before.json()["ledger_state"] == "NOT_INITIALIZED"
    response = e.client.post(capacity_url(e, "/reconcile", alias), headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["contract"] == "project-capacity-reconcile/1"
    assert result["admission"] == "UNAVAILABLE"
    assert result["write_gate"] == "PROJECT_CAPACITY_WRITE_UNAVAILABLE"
    assert result["measurement"]["unknown_objects"] == 0
    current = e.client.get(capacity_url(e, alias=alias), headers=e.headers).json()
    assert current["ledger_state"] == "AVAILABLE"
    assert result["snapshot"]["used_bytes"] == current["combined"]["logical_bytes"]
    assert result["snapshot"]["state"] == "OK"
    ledger_path = e.rig.root / "runtime" / "project-capacity.json"
    assert ledger_path.is_file()
    audit = json.loads(ledger_path.read_text(encoding="utf-8"))["projects"][e.rig.nid]["audit"]
    assert any(entry["action"] == "RECONCILE" for entry in audit)


def test_reconcile_records_unknown_then_recovers(audio_history):
    e = audio_history
    corrupt = Path(e.rig.assets.root) / "corrupt-capacity-metadata.json"
    corrupt.write_bytes(b"{broken")
    blocked = e.client.post(capacity_url(e, "/reconcile"), headers=e.headers)
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["snapshot"]["unknown"]["blocked"] is True
    assert blocked.json()["snapshot"]["state"] == "UNKNOWN_BLOCKED"
    corrupt.unlink()
    recovered = e.client.post(capacity_url(e, "/reconcile"), headers=e.headers)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["snapshot"]["unknown"] == {"objects": 0, "blocked": False}
    assert recovered.json()["snapshot"]["state"] == "OK"


def test_limit_change_requires_reconciled_ledger(audio_history):
    e = audio_history
    response = e.client.put(capacity_url(e, "/limit"), headers=e.headers,
                            json={"limit_bytes": 1024, "expected_version": 0})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "PROJECT_CAPACITY_NOT_RECONCILED"


@pytest.mark.parametrize("alias", [False, True])
def test_limit_change_cas_version_and_audit(audio_history, alias):
    e = audio_history
    assert e.client.post(capacity_url(e, "/reconcile", alias), headers=e.headers).status_code == 200
    current = e.client.get(capacity_url(e, alias=alias), headers=e.headers).json()
    version = current["ledger"]["ledger_version"]
    increased = current["ledger"]["used_bytes"] + 4096
    changed = e.client.put(capacity_url(e, "/limit", alias), headers=e.headers,
                           json={"limit_bytes": increased, "expected_version": version})
    assert changed.status_code == 200, changed.text
    assert changed.json()["snapshot"]["limit_bytes"] == increased
    assert changed.json()["snapshot"]["state"] == "OK"
    stale = e.client.put(capacity_url(e, "/limit", alias), headers=e.headers,
                         json={"limit_bytes": increased + 4096, "expected_version": version})
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "PROJECT_CAPACITY_VERSION_CONFLICT"
    current = e.client.get(capacity_url(e, alias=alias), headers=e.headers).json()
    assert current["ledger"]["limit_bytes"] == increased
    audit = json.loads((e.rig.root / "runtime" / "project-capacity.json").read_text(encoding="utf-8"))
    entries = audit["projects"][e.rig.nid]["audit"]
    last_change = [entry for entry in entries if entry["action"] == "LIMIT_CHANGE"][-1]
    assert last_change["previous_limit_bytes"] == 512 * 1024 * 1024
    assert last_change["limit_bytes"] == increased


def test_lowering_limit_marks_over_limit_but_keeps_content(audio_history):
    e = audio_history
    assert e.client.post(capacity_url(e, "/reconcile"), headers=e.headers).status_code == 200
    current = e.client.get(capacity_url(e), headers=e.headers).json()
    used = current["ledger"]["used_bytes"]
    assert used > 0
    response = e.client.put(capacity_url(e, "/limit"), headers=e.headers,
                            json={"limit_bytes": max(1, used - 1),
                                  "expected_version": current["ledger"]["ledger_version"]})
    assert response.status_code == 200, response.text
    assert response.json()["snapshot"]["state"] == "OVER_LIMIT"
    assert response.json()["snapshot"]["used_bytes"] == used


def test_limit_change_rejects_invalid_body(audio_history):
    e = audio_history
    assert e.client.post(capacity_url(e, "/reconcile"), headers=e.headers).status_code == 200
    version = e.client.get(capacity_url(e), headers=e.headers).json()["ledger"]["ledger_version"]
    for body in ({"limit_bytes": 0, "expected_version": version},
                 {"limit_bytes": 1024, "expected_version": -1},
                 {"limit_bytes": "1024", "expected_version": version}):
        response = e.client.put(capacity_url(e, "/limit"), headers=e.headers, json=body)
        assert response.status_code == 422, (body, response.text)


def test_capacity_admin_requires_existing_project_owner(rig):
    e = rig
    response = e.client.post(f"/api/projects/{e.nid}/studio/capacity/reconcile")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "STUDIO_STORAGE_READ_ONLY_UNAVAILABLE"


def test_limit_change_rejects_non_management_token(shared_project):
    e = shared_project
    ledger = ProjectCapacityLedger(e.root / "runtime" / "project-capacity.json",
                                   default_limit_bytes=1024)
    incarnation = e.workspace.store.incarnation(e.nid)
    ledger.reconcile(e.nid, measured_bytes=10, unknown_objects=0,
                     incarnation=incarnation, actor_id="fixture")
    version = ledger.peek(e.nid)["ledger_version"]
    # Direct service call with a token that has no original project authority
    # must fail before the ledger CAS is touched.
    with pytest.raises(HTTPException) as denied:
        e.workspace.capacity_adjust_limit(
            e.nid, {"mode": "collaboration", "novel_id": e.nid, "workspace_id": "ws"},
            "manager", "other-token",
            SimpleNamespace(limit_bytes=1024, expected_version=version))
    assert denied.value.status_code in {401, 403, 409}
    assert ledger.peek(e.nid)["limit_bytes"] == 1024


def test_capacity_routes_are_exactly_allowlisted():
    from app.creative.workspace_api import is_independent_studio_route
    root = "/api/projects/example/studio"
    assert is_independent_studio_route("POST", root + "/capacity/reconcile")
    assert is_independent_studio_route("PUT", root + "/capacity/limit")
    assert not is_independent_studio_route("POST", root + "/capacity/reconcile/extra")
    assert not is_independent_studio_route("PUT", root + "/capacity")
    assert not is_independent_studio_route("DELETE", root + "/capacity/limit")




