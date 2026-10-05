import copy
from types import SimpleNamespace

import pytest

from test_industry_export_queue import setup_queue
from app.services.screenplay_service import ScreenplayService


@pytest.fixture
def screenplay_client(setup_queue, monkeypatch):
    import app.api as api
    source, _, _, client = setup_queue
    source.screenplays = []
    def save(nid, row, *, expected_version=None):
        rows = source.screenplays
        position = next((i for i, item in enumerate(rows) if item["id"] == row["id"]), None)
        if position is None: rows.append(copy.deepcopy(row))
        else: rows[position] = copy.deepcopy(row)
        return copy.deepcopy(row)
    source.save_screenplay = save
    chapters = SimpleNamespace(list=lambda nid: source.chapters, get=lambda cid: source.chapters[0])
    service = ScreenplayService(source, chapters)
    monkeypatch.setattr(api, "screenplay_service", service)
    return client, source, service


def test_create_list_read_and_edit_screenplays_are_branch_authorized(screenplay_client):
    client, source, service = screenplay_client
    headers = {"X-Session-Token": "owner", "X-Branch-Id": "branch-a"}
    assert client.post("/api/novels/project/screenplays", json={}).status_code == 401
    created = client.post("/api/novels/project/screenplays", json={"title": "Synthetic"}, headers=headers)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["branch_id"] == "branch-a"
    legacy = service.create("project", "Legacy unscoped")
    assert [item["id"] for item in client.get("/api/novels/project/screenplays", headers=headers).json()] == [row["id"]]
    foreign_headers = {**headers, "X-Branch-Id": "branch-b"}
    assert client.get("/api/novels/project/screenplays", headers=foreign_headers).json() == []
    for suffix, method in [("approve", "post"), ("shots", "post"), ("pipeline-status", "get"), ("visual-continuity", "get"), ("revise", "post")]:
        response = getattr(client, method)(f"/api/novels/project/screenplays/{row['id']}/{suffix}", headers=foreign_headers)
        assert response.status_code == 404, response.text
    assert client.post(f"/api/novels/project/screenplays/{legacy['id']}/approve", headers=headers).status_code == 404


def test_approved_revision_fork_retains_source_and_leaves_assets_untouched(screenplay_client):
    client, source, service = screenplay_client
    headers = {"X-Session-Token": "owner", "X-Branch-Id": "branch-a"}
    original = service.create("project", "Original", branch_id="branch-a")
    original["status"] = "APPROVED"
    original["revision"] = 4
    original["shot_revision"] = 3
    original["shots"] = [{"id": "approved-shot", "asset_id": "approved-asset"}]
    original["shot_status"] = "APPROVED"
    original["motion_tasks"] = [{"id": "completed-task", "status": "SUCCEEDED"}]
    source.save_screenplay("project", original)
    response = client.post(f"/api/novels/project/screenplays/{original['id']}/revise", headers=headers,json={"expected_version":0})
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["status"] == "DRAFT" and draft["revision"] == 1
    assert draft["id"] != original["id"]
    assert draft["branch_id"] == "branch-a"
    assert draft["derived_from"]["screenplay_id"] == original["id"]
    assert draft["derived_from"]["revision"] == 4
    assert draft["scenes"][0]["source_version"] == original["scenes"][0]["source_version"]
    assert "shots" not in draft and "motion_tasks" not in draft
    payload = {**draft["scenes"][0], "action": "Revised synthetic scene"}
    edited = service.update_scene("project", draft["id"], draft["scenes"][0]["id"], payload)
    assert edited["scenes"][0]["action"] == "Revised synthetic scene"
    assert next(row for row in service.list("project") if row["id"] == original["id"]) == original
    assert client.post(f"/api/novels/project/screenplays/{draft['id']}/revise", headers=headers,json={"expected_version":0}).status_code == 400
