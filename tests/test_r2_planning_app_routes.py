"""Real mounted /api and /api/v1 planning flow with isolated File persistence."""
from dataclasses import replace
import time

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_real_app_planning_to_draft_then_manual_approval(prefix, tmp_path, monkeypatch):
    import app.api as api
    from app.config import settings
    from app.main import app
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    from app.services.ai_planning_service import AIPlanningService
    from app.services.creation_workbench_service import CreationWorkbenchService
    from app.services.v1_capability_service import V1CapabilityService

    object.__setattr__(settings, "enable_collaboration_runtime", False)
    object.__setattr__(settings, "enable_packaged_runtime", False)
    bundle = create_repository_bundle(config=replace(settings, storage_backend="file"), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    novel = novels.create({"title": "Synthetic planning integration"})
    chapter = chapters.create(novel["id"], {"title": "Marked source", "content": "世界规则：每次施法都须付出代价。\n"})
    chapter = chapters.get(chapter["id"])
    nid = novel["id"]
    store = V1CapabilityService(tmp_path, novels, chapters, None)
    # Patch collaborators of the actual mounted service, not a test-only router.
    monkeypatch.setattr(api, "novel_service", novels)
    workbench = api.creation_workbench_service
    for name, value in (("store", store), ("novels", novels), ("chapters", chapters)):
        monkeypatch.setattr(workbench, name, value)
    planner = api.ai_planning_service
    monkeypatch.setattr(planner, "store", store)
    monkeypatch.setattr(planner, "chapters", chapters)
    monkeypatch.setattr(planner, "workers", set())
    monkeypatch.setattr(planner, "cancellations", {})
    client = TestClient(app)
    endpoint = f"{prefix}/novels/{nid}/planning-runs"
    response = client.post(endpoint, json={"mode": "LOCAL_EXPLICIT", "kind": "ABILITY", "sources": [{"chapter_id": chapter["id"], "expected_version": chapter["version"]}]})
    assert response.status_code == 202, response.text
    rid = response.json()["id"]
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"{endpoint}/{rid}")
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] not in {"QUEUED", "WORKING"}: break
        time.sleep(.01)
    assert run["status"] == "READY", run
    assert run["execution_mode"] == "local_explicit"
    assert len(run["candidates"]) == 1
    assert client.get(endpoint).json()["items"][0]["id"] == rid
    records_endpoint = f"{prefix}/novels/{nid}/creation-records"
    assert client.get(records_endpoint).json()["items"] == []
    saved = client.post(f"{endpoint}/{rid}/candidates/{run['candidates'][0]['id']}/save-draft", json={"expected_version": run["version"]})
    assert saved.status_code == 200, saved.text
    record = saved.json()["record"]
    assert record["status"] == "DRAFT" and record["source"] == "LOCAL_EXPLICIT"
    assert chapters.get(chapter["id"])["content"] == chapter["content"]
    assert novels.data_set(nid, "canon") == []
    approval = client.post(f"{records_endpoint}/{record['id']}/approve", json={"expected_version": record["version"]})
    assert approval.status_code == 200 and approval.json()["status"] == "APPROVED", approval.text
    reopened = CreationWorkbenchService(store, chapters, novels)
    scope = reopened.local_scope(nid)
    assert reopened.get_record(nid, scope, record["id"])["status"] == "APPROVED"
    assert AIPlanningService(reopened, api.runtime).get(nid, scope, rid)["candidates"][0]["record_id"] == record["id"]
    assert client.post(f"{endpoint}/{rid}/cancel", json={"expected_version": saved.json()["run"]["version"]}).status_code == 422
