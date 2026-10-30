"""Export jobs stay bound to their creating actor, project and branch context.

Uses the synthetic Studio rig (real mounted routes, real sessions/membership/
grants) plus a temporary ``ExportJobService`` with a deterministic synthetic
exporter, so no repository data or real renderer is touched. Pins the read,
download, concealment and post-deletion behavior of the legacy export consumer.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from test_studio_asset_query import rig, shared_scope  # noqa: F401 - pytest fixture/helper

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def export_rig(rig, tmp_path, monkeypatch):
    from app import api
    from app.actor_context import SessionContext
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.identity import User, WorkspaceMembership
    from app.services.export_job_service import ExportJobService

    scope, headers = shared_scope(rig)
    rig.grants.assign_permission(PermissionAssignment(
        "query-write", "reader", "domain.write", ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid), "fixture"))
    service = ExportJobService(
        tmp_path / "export-owner",
        lambda novel_id, fmt: {"content": b"synthetic-export", "filename": "synthetic.txt",
                               "media_type": "text/plain"},
    )
    monkeypatch.setattr(api, "export_job_service", service)
    # An unrelated member with a real project read grant but a different actor id.
    rig.identities.create_user(User("other-reader", "Other Reader"))
    rig.identities.add_membership(WorkspaceMembership("member-other-reader", "other-reader",
                                                      "query-workspace"))
    rig.sessions.register("token-other-reader",
                          SessionContext("session-other-reader", "client", "other-reader",
                                         "query-workspace"))
    rig.grants.assign_permission(PermissionAssignment(
        "other-read", "other-reader", "domain.read", ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid), "fixture"))
    yield SimpleNamespace(rig=rig, service=service, scope=scope, headers=headers, tmp=tmp_path)
    service._pool.shutdown(wait=False)


def _create(export_rig):
    rig = export_rig.rig
    created = rig.client.post(f"/api/exports?novel_id={rig.nid}", json={"format": "json"},
                              headers=export_rig.headers)
    assert created.status_code == 202, created.text
    job_id = created.json()["id"]
    for _ in range(200):
        job = rig.client.get(f"/api/exports/{job_id}", headers=export_rig.headers)
        if job.status_code == 200 and job.json().get("status") == "succeeded":
            return job_id
        time.sleep(.02)
    raise AssertionError("synthetic export did not finish: " + str(job.text[:200]))


def test_export_read_download_are_actor_project_and_branch_bound(export_rig):
    rig = export_rig.rig
    job_id = _create(export_rig)
    creator = rig.client.get(f"/api/exports/{job_id}", headers=export_rig.headers)
    assert creator.status_code == 200 and creator.json()["status"] == "succeeded"
    downloaded = rig.client.get(f"/api/exports/{job_id}/download", headers=export_rig.headers)
    assert downloaded.status_code == 200
    assert downloaded.content == b"synthetic-export"

    # No token -> session boundary still applies.
    anonymous = rig.client.get(f"/api/exports/{job_id}")
    assert anonymous.status_code == 401
    # A valid workspace member with no grant cannot even confirm existence.
    outsider = rig.client.get(f"/api/exports/{job_id}",
                              headers={"X-Session-Token": "token-no-grants"})
    assert outsider.status_code == 404
    assert job_id not in outsider.text
    # A different actor with a real project read grant must not read another
    # actor's job; the persisted permission context binds the creator.
    other = rig.client.get(f"/api/exports/{job_id}",
                           headers={"X-Session-Token": "token-other-reader",
                                    "X-Branch-Id": "query-branch-a"})
    assert other.status_code == 404
    # The requested branch must match the branch captured at creation.
    wrong_branch = rig.client.get(f"/api/exports/{job_id}",
                                  headers={**export_rig.headers, "X-Branch-Id": "query-branch-b"})
    assert wrong_branch.status_code == 404
    # Download paths share the same concealment.
    for headers in ({"X-Session-Token": "token-no-grants"},
                    {"X-Session-Token": "token-other-reader", "X-Branch-Id": "query-branch-a"}):
        denied = rig.client.get(f"/api/exports/{job_id}/download", headers=headers)
        assert denied.status_code == 404


def test_export_access_is_refused_after_grant_revocation_and_project_rebuild(export_rig):
    rig = export_rig.rig
    job_id = _create(export_rig)
    # Fresh authorization is required on every read: revoking the grant conceals
    # the persisted job even for the original session.
    rig.grants.revoke_permission("query-read", "fixture")
    revoked = rig.client.get(f"/api/exports/{job_id}", headers=export_rig.headers)
    assert revoked.status_code == 404, revoked.text
    assert job_id not in revoked.text
    denied_download = rig.client.get(f"/api/exports/{job_id}/download", headers=export_rig.headers)
    assert denied_download.status_code == 404

    # Deleting and recreating the same project identifier does not resurrect the
    # old job's authority or disclose its existence.
    rig.novels.delete(rig.nid)
    rig.novels.create({"id": rig.nid, "title": "Synthetic recreated project"})
    rebuilt = rig.client.get(f"/api/exports/{job_id}", headers=export_rig.headers)
    assert rebuilt.status_code in (403, 404), rebuilt.text
    assert job_id not in rebuilt.text
