"""Owner- and branch-scoped discovery survives process/session restart."""
from types import SimpleNamespace

import pytest

from test_industry_export_queue import setup_queue, wait
from app.services.export_job_service import ExportJobService


def test_history_recovers_same_job_snapshot_download_after_restart(setup_queue, monkeypatch, tmp_path):
    import app.api as api
    source, novels, queue, client = setup_queue
    monkeypatch.setattr(queue, "_submit", lambda _: None)
    headers = {"X-Session-Token": "owner", "X-Branch-Id": "branch-a"}
    original = client.post("/api/exports?novel_id=project", json={"format": "screenplay-fountain"}, headers=headers).json()
    assert "snapshot" not in original  # No manuscript or binary copies in history/API metadata.
    source.screenplays.clear()
    restarted = ExportJobService(tmp_path, novels.export, snapshotter=novels.export_snapshot)
    monkeypatch.setattr(api, "export_job_service", restarted)
    try:
        wait(restarted, original["id"])
        recovered = client.get("/api/exports?novel_id=project", headers=headers).json()["items"][0]
        assert recovered["id"] == original["id"]
        assert recovered["snapshot_id"] == original["snapshot_id"]
        assert recovered["recovery_count"] == 1
        assert recovered["source_versions"]["screenplays"][0]["version"] == 7
        assert "snapshot" not in recovered and "artifact" not in recovered
        assert "content" not in recovered["result"]
        download = client.get(f"/api/exports/{original['id']}/download", headers=headers)
        assert download.status_code == 200
        assert original["snapshot_id"] in download.text and "Original action" in download.text
    finally:
        restarted._pool.shutdown(wait=True)


def test_history_filters_owner_branch_project_status_and_pages(setup_queue, monkeypatch):
    _, _, queue, client = setup_queue
    monkeypatch.setattr(queue, "_submit", lambda _: None)
    headers = {"X-Session-Token": "owner", "X-Branch-Id": "branch-a"}
    originals = [client.post("/api/exports?novel_id=project", json={"format": "txt"}, headers=headers).json() for _ in range(3)]
    other = client.post("/api/exports?novel_id=project&branch_id=branch-b", json={"format": "txt"}, headers={"X-Session-Token": "other-branch"}).json()
    queue.cancel(originals[0]["id"])
    page = client.get("/api/exports?novel_id=project&limit=2", headers=headers).json()
    assert len(page["items"]) == 2 and page["next_offset"] == 2
    second = client.get("/api/exports?novel_id=project&limit=2&offset=2", headers=headers).json()
    assert len(second["items"]) == 1 and second["next_offset"] is None
    assert {r["id"] for r in page["items"] + second["items"]} == {r["id"] for r in originals}
    filtered = client.get("/api/exports?novel_id=project&status=cancelled", headers=headers).json()
    assert [r["id"] for r in filtered["items"]] == [originals[0]["id"]]
    assert client.get("/api/exports?novel_id=project&status=unknown", headers=headers).status_code == 400
    assert client.get("/api/exports?novel_id=project", headers={**headers, "X-Branch-Id": "branch-b"}).json()["items"] == []
    assert client.get("/api/exports?novel_id=project", headers={"X-Session-Token": "outsider"}).status_code == 403
    assert client.get("/api/exports?novel_id=project").status_code == 401


@pytest.mark.parametrize("suffix,method", [("", "get"), ("/download", "get"), ("/cancel", "post"), ("/retry", "post")])
def test_owner_scope_and_revoked_membership_gate_every_existing_job(setup_queue, monkeypatch, suffix, method):
    import app.api as api
    _, _, queue, client = setup_queue
    monkeypatch.setattr(queue, "_submit", lambda _: None)
    headers = {"X-Session-Token": "owner", "X-Branch-Id": "branch-a"}
    job = client.post("/api/exports?novel_id=project", json={"format": "txt"}, headers=headers).json()
    route = f"/api/exports/{job['id']}{suffix}"
    assert getattr(client, method)(route, headers={**headers, "X-Branch-Id": "branch-b"}).status_code == 404
    # A different authenticated actor with exactly the same membership is still not the owner.
    monkeypatch.setattr(api.trusted_session_resolver, "resolve", lambda _: SimpleNamespace(actor_id="other-user", workspace_id="workspace"))
    assert getattr(client, method)(route, headers=headers).status_code == 404
    monkeypatch.setattr(api.trusted_session_resolver, "resolve", lambda _: SimpleNamespace(actor_id="owner", workspace_id="workspace"))
    def revoked(*args): raise PermissionError("membership revoked")
    monkeypatch.setattr(api.membership_authorization_service, "require", revoked)
    assert getattr(client, method)(route, headers=headers).status_code == 404
    assert client.get("/api/exports?novel_id=project", headers=headers).status_code == 403


def test_collaboration_job_cannot_be_read_by_disabling_runtime(setup_queue, monkeypatch):
    import app.api as api
    _, _, queue, client = setup_queue
    monkeypatch.setattr(queue, "_submit", lambda _: None)
    headers = {"X-Session-Token": "owner", "X-Branch-Id": "branch-a"}
    job = client.post("/api/exports?novel_id=project", json={"format": "txt"}, headers=headers).json()
    monkeypatch.setattr(api, "settings", SimpleNamespace(enable_collaboration_runtime=False))
    assert client.get(f"/api/exports/{job['id']}").status_code == 401
    assert client.get("/api/exports?novel_id=project").json()["items"] == []


def test_legacy_preview_cannot_bypass_project_and_screenplay_branch_gates(setup_queue):
    _, _, _, client = setup_queue
    path = "/api/novels/project/export?format=screenplay"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Session-Token": "outsider"}).status_code == 403
    good = client.get(path, headers={"X-Session-Token": "owner", "X-Branch-Id": "branch-a"})
    assert good.status_code == 200 and "Original action" in good.text
    wrong_branch = client.get(path, headers={"X-Session-Token": "owner", "X-Branch-Id": "branch-b"})
    assert wrong_branch.status_code == 400 and "Original action" not in wrong_branch.text
