"""Project incarnation exposure and bounded deletion tombstone (backend only).

Two previously missing backend capabilities for the client project list:

1. every new project gets a durable ``project_incarnation`` (and the list already
   carries ``created_at``), so a same-id delete/recreate is detectable without
   relying on the server never reusing ids;
2. a bounded, workspace-scoped deletion tombstone journal records projects that
   were deleted while a client was closed, so a later cold start can purge stale
   local view state. This is an auxiliary purge signal, never authority/content.

All fixtures are synthetic temporary File backends; no real project data is used.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import project_tombstones as tombstones
from app.application.persistence import AtomicPathMutationPort
from app.repository import FileRepository
from app.repositories.file.novel import FileNovelRepository
from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
from app.services.novel_service import NovelService


# ---------------------------------------------------------------------------
# 1. Journal primitives
# ---------------------------------------------------------------------------

def _root(tmp_path: Path) -> Path:
    return tmp_path / "data"


def test_tombstones_are_ordered_bounded_and_workspace_scoped(tmp_path):
    root = _root(tmp_path)
    first = tombstones.record(root, "project-a")
    second = tombstones.record(root, "project-b", workspace_id="ws-1", incarnation="inc-1")
    tombstones.record(root, "project-c", workspace_id="ws-2")
    assert first["seq"] == 1 and second["seq"] == 2

    page, cursor, has_more = tombstones.read_page(root, workspace_id=None)
    assert [row["project_id"] for row in page] == ["project-a"]
    assert cursor is None and has_more is False

    page, cursor, has_more = tombstones.read_page(root, workspace_id="ws-1")
    assert [(row["project_id"], row["incarnation"]) for row in page] == [("project-b", "inc-1")]

    everything = tombstones.read_page(root, workspace_id="ws-1", limit=1)[0]
    assert len(everything) == 1
    assert tombstones.read_page(root, workspace_id="ws-2")[0][0]["project_id"] == "project-c"


def test_tombstone_cursor_pages_forward_without_repeating(tmp_path):
    root = _root(tmp_path)
    for index in range(3):
        tombstones.record(root, f"project-{index}")
    page, cursor, has_more = tombstones.read_page(root, workspace_id=None, limit=2)
    assert [row["project_id"] for row in page] == ["project-0", "project-1"]
    assert cursor == 2 and has_more is True
    page, cursor, has_more = tombstones.read_page(root, workspace_id=None, after=cursor, limit=2)
    assert [row["project_id"] for row in page] == ["project-2"]
    assert cursor is None and has_more is False


def test_tombstone_retention_is_bounded_and_keeps_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(tombstones, "MAX_ENTRIES", 3)
    root = _root(tmp_path)
    for index in range(5):
        tombstones.record(root, f"project-{index}")
    page, _, _ = tombstones.read_page(root, workspace_id=None, limit=10)
    assert [row["project_id"] for row in page] == ["project-2", "project-3", "project-4"]
    assert [row["seq"] for row in page] == [3, 4, 5]


def test_corrupt_journal_is_reported_and_never_overwritten(tmp_path):
    root = _root(tmp_path)
    journal = root / tombstones.JOURNAL_RELATIVE
    journal.parent.mkdir(parents=True)
    journal.write_text("{not-json", encoding="utf-8")
    with pytest.raises(tombstones.TombstoneUnavailable):
        tombstones.read_page(root, workspace_id=None)
    with pytest.raises(tombstones.TombstoneUnavailable):
        tombstones.record(root, "project-a")
    assert journal.read_text(encoding="utf-8") == "{not-json"


def test_tombstone_rejects_invalid_ids_and_query_values(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(ValueError):
        tombstones.record(root, "")
    with pytest.raises(ValueError):
        tombstones.record(root, "project\x00id")
    with pytest.raises(ValueError):
        tombstones.read_page(root, workspace_id=None, after=-1)
    with pytest.raises(ValueError):
        tombstones.read_page(root, workspace_id=None, limit=0)
    with pytest.raises(ValueError):
        tombstones.read_page(root, workspace_id=None, limit=tombstones.MAX_PAGE + 1)


def test_journal_root_prefers_the_active_repository_data_root(tmp_path):
    data = tmp_path / "backend-data"
    repository = SimpleNamespace(backend=SimpleNamespace(data=data))
    assert tombstones.journal_root(repository) == data
    from app.config import settings
    assert tombstones.journal_root(None) == settings.data_path()


# ---------------------------------------------------------------------------
# 2. Project incarnation on create/list and delete tombstone through services
# ---------------------------------------------------------------------------

def _file_service(tmp_path: Path) -> tuple[NovelService, Path]:
    data = tmp_path / "data"
    return NovelService(FileNovelRepository(FileRepository(data)), None), data


def test_created_at_and_project_incarnation_are_durable_and_change_on_recreate(tmp_path):
    service, data = _file_service(tmp_path)
    created = service.create({"id": "same-id", "title": "Synthetic Project"})
    assert created["created_at"] and created["project_incarnation"]
    listed = next(row for row in service.list() if row["id"] == "same-id")
    assert listed["created_at"] == created["created_at"]
    assert listed["project_incarnation"] == created["project_incarnation"]

    service.delete("same-id")
    recreated = service.create({"id": "same-id", "title": "Synthetic Project"})
    assert recreated["project_incarnation"] != created["project_incarnation"]
    assert (data / "novels" / "same-id" / "novel.json").is_file()


def test_local_service_delete_records_a_workspace_less_tombstone(tmp_path):
    service, data = _file_service(tmp_path)
    created = service.create({"id": "deleted-local", "title": "Synthetic Project"})
    service.delete("deleted-local")
    page, _, _ = tombstones.read_page(data, workspace_id=None, limit=10)
    entry = next(row for row in page if row["project_id"] == "deleted-local")
    assert entry["workspace_id"] is None
    assert entry["incarnation"] == created["project_incarnation"]
    assert entry["deleted_at"]


def test_collaboration_delete_port_records_a_workspace_scoped_tombstone(tmp_path):
    data = tmp_path / "data"
    novels = FileNovelRepository(FileRepository(data))
    scopes = FileScopeRepository(data)
    authorization = FileAuthorizationRepository(data)
    port = AtomicPathMutationPort(novels, scopes, authorization)
    created = novels.create({"id": "deleted-shared", "title": "Synthetic Project"})
    scopes.link_project("deleted-shared", "ws-1")
    actor = SimpleNamespace(actor_id="actor-1", session_id="session-1", client_id="client-1",
                            effective_correlation_id="corr-1", workspace_id="ws-1")
    port.delete_project("ws-1", "deleted-shared", actor)

    own, _, _ = tombstones.read_page(tombstones.journal_root(novels), workspace_id="ws-1")
    entry = next(row for row in own if row["project_id"] == "deleted-shared")
    assert entry["workspace_id"] == "ws-1"
    assert entry["incarnation"] == created["project_incarnation"]
    other, _, _ = tombstones.read_page(tombstones.journal_root(novels), workspace_id="ws-2")
    assert other == []


# ---------------------------------------------------------------------------
# 3. HTTP route (both API aliases) and delete integration
# ---------------------------------------------------------------------------

def _client(monkeypatch, tmp_path, workspace_id=None):
    from app import api
    service, data = _file_service(tmp_path)
    monkeypatch.setattr(api, "novel_service", service)
    if workspace_id is None:
        monkeypatch.setattr(api, "_shared_runtime_authority_enabled", lambda: False)
    else:
        monkeypatch.setattr(api, "_shared_runtime_authority_enabled", lambda: True)
        monkeypatch.setattr(api, "_shared_actor", lambda token: SimpleNamespace(workspace_id=workspace_id))
    application = FastAPI()
    application.include_router(api.router, prefix="/api")
    application.include_router(api.router, prefix="/api/v1")
    return TestClient(application), data


def test_local_delete_via_http_is_visible_in_the_purge_feed(monkeypatch, tmp_path):
    client, data = _client(monkeypatch, tmp_path)
    from app import api
    created = api.novel_service.create({"id": "http-deleted", "title": "Synthetic Project"})
    assert client.delete("/api/novels/http-deleted").status_code == 204
    response = client.get("/api/projects/deletions")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contract"] == "project-deletions/1"
    assert body["has_more"] is False and body["next_cursor"] is None
    entry = next(row for row in body["items"] if row["project_id"] == "http-deleted")
    assert entry["incarnation"] == created["project_incarnation"]
    assert data.joinpath("runtime").is_dir()
    # The same bounded feed is mounted under the v1 alias with identical data.
    assert client.get("/api/v1/projects/deletions").json() == body


def test_shared_mode_feed_is_workspace_scoped_and_requires_an_actor(monkeypatch, tmp_path):
    client, data = _client(monkeypatch, tmp_path, workspace_id="ws-1")
    tombstones.record(data, "own-project", workspace_id="ws-1", incarnation="inc-1")
    tombstones.record(data, "foreign-project", workspace_id="ws-2")
    body = client.get("/api/projects/deletions").json()
    assert [row["project_id"] for row in body["items"]] == ["own-project"]
    assert all("ws-" not in json.dumps(row) for row in body["items"])
    # A session that resolves without a workspace cannot read the feed.
    from app import api
    monkeypatch.setattr(api, "_shared_actor", lambda token: SimpleNamespace(workspace_id=None))
    denied = client.get("/api/projects/deletions")
    assert denied.status_code == 403
    assert "foreign-project" not in denied.text


def test_corrupt_journal_maps_to_a_fixed_unavailable_error(monkeypatch, tmp_path):
    client, data = _client(monkeypatch, tmp_path)
    journal = data / tombstones.JOURNAL_RELATIVE
    journal.parent.mkdir(parents=True)
    journal.write_text("[]", encoding="utf-8")
    response = client.get("/api/projects/deletions")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PROJECT_DELETIONS_UNAVAILABLE"
