"""Mounted read-only project capacity diagnostics.

The capacity ledger exists, but the write admission chain is intentionally not
wired yet, so the diagnostics route must:
- expose the logical measurement and any persisted ledger snapshot;
- never initialize the ledger/locks, reserve bytes or claim admission;
- keep the write gate explicitly ``PROJECT_CAPACITY_WRITE_UNAVAILABLE``;
- be read-only and identical under both API aliases.
"""
from __future__ import annotations

import hashlib

import pytest

from test_studio_asset_query import rig, shared_scope
from test_studio_workspace_identity_history_contract import audio_history
from test_audio_history_status_readonly import snapshot

pytestmark = pytest.mark.file_backend_only


def url(e, alias):
    return f"/api{'/v1' if alias else ''}/projects/{e.rig.nid}/studio/capacity"


@pytest.mark.parametrize("alias", [False, True])
def test_capacity_diagnostics_is_read_only_and_never_initializes(audio_history, alias):
    e = audio_history
    before = snapshot(e.rig.root)
    response = e.client.get(url(e, alias), headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["contract"] == "project-capacity-diagnostics/1"
    assert result["project_id"] == e.rig.nid
    assert result["measurement"]["measurement"] == "LOGICAL_FILE_LENGTH_NOT_ALLOCATED"
    assert result["measurement"]["logical_bytes"] >= 1
    assert result["measurement"]["allocated_storage_bytes"] == "UNKNOWN"
    assert result["measurement_scope"] == "PROJECT_OWNED_ROOT_ONLY"
    assert result["ledger_state"] == "NOT_INITIALIZED" and result["ledger"] is None
    assert result["admission"] == "UNAVAILABLE"
    assert result["write_gate"] == "PROJECT_CAPACITY_WRITE_UNAVAILABLE"
    assert result["write"] is False and result["initialized"] is False
    assert snapshot(e.rig.root) == before
    assert not (e.rig.root / "runtime" / "project-capacity.json").exists()
    assert not (e.rig.root / ".workspace-mutation-locks" / (
        hashlib.sha256(b"project-capacity").hexdigest() + ".lock")).exists()


def test_capacity_diagnostics_reads_persisted_ledger_without_writes(audio_history):
    from app.project_capacity import ProjectCapacityLedger

    e = audio_history
    ledger_path = e.rig.root / "runtime" / "project-capacity.json"
    ProjectCapacityLedger(ledger_path, default_limit_bytes=1024).reconcile(
        e.rig.nid, measured_bytes=64, unknown_objects=0, incarnation="fixture-incarnation",
        actor_id="reconciler")
    before = snapshot(e.rig.root)
    response = e.client.get(url(e, True), headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["ledger_state"] == "AVAILABLE"
    assert result["ledger"]["used_bytes"] == 64
    assert result["ledger"]["limit_bytes"] == 1024
    assert result["limits"]["applied_limit_bytes"] == 1024
    assert result["admission"] == "UNAVAILABLE"
    assert snapshot(e.rig.root) == before


def test_capacity_diagnostics_corrupt_ledger_fails_closed(audio_history):
    e = audio_history
    ledger_path = e.rig.root / "runtime" / "project-capacity.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_bytes(b"{broken")
    response = e.client.get(f"/api/projects/{e.rig.nid}/studio/capacity")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["ledger_state"] == "UNAVAILABLE" and result["ledger"] is None
    assert result["admission"] == "UNAVAILABLE"
    assert ledger_path.read_bytes() == b"{broken"


def test_capacity_diagnostics_requires_original_project_authority(rig):
    scope, headers = shared_scope(rig)
    e = rig
    other = e.project()
    response = e.client.get(f"/api/projects/{other}/studio/capacity", headers=headers)
    assert response.status_code == 403
    assert "project-capacity-diagnostics/1" not in response.text


def test_capacity_route_is_on_the_exact_admission_allowlist():
    from app.creative.workspace_api import is_independent_studio_route
    root = "/api/projects/example/studio"
    assert is_independent_studio_route("GET", root + "/capacity")
    assert not is_independent_studio_route("GET", root + "/capacity/extra")
    assert not is_independent_studio_route("POST", root + "/capacity")

