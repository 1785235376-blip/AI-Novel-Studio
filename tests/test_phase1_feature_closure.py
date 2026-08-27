from uuid import uuid4

from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.asset_providers import DeterministicVideoProvider, VideoGenerationRequest
from app.dependencies import trusted_session_resolver, v1_capability_service
from app.main import app
from app.services.screenplay_service import is_traceable_frame, require_motion_frames


def agent_headers():
    token = f"phase1-feature-{uuid4()}"
    trusted_session_resolver.register(
        token,
        SessionContext(actor_id="phase1-feature", workspace_id="workspace-a", session_id="session", client_id="test"),
    )
    return {"X-Session-Token": token}


def test_overview_exposes_real_counts_and_writing_goal():
    client = TestClient(app)
    novel = client.post("/api/novels", json={"title": f"Overview {uuid4()}"}).json()
    nid = novel["id"]
    client.post(f"/api/novels/{nid}/chapters", json={"title": "第一章", "content": "迷雾封锁港口。" * 20})
    client.put(f"/api/novels/{nid}/writing-goal", json={"target_words": 1000, "target_chapters": 10})
    created = client.post(
        f"/api/novels/{nid}/research",
        json={"title": "Phase1 Desktop 验收资料", "source_type": "NOTE", "status": "ACTIVE", "tags": ["phase1-desktop"]},
    )
    assert created.status_code == 201
    overview = client.get(f"/api/novels/{nid}/overview").json()
    assert overview["placeholder"] is False
    assert overview["storage"] == "durable_sidecar"
    for key in ("chapters", "characters", "locations", "timeline", "foreshadowing", "world_rules", "research"):
        assert key in overview["counts"]
    assert overview["counts"]["chapters"] == 1
    assert overview["counts"]["research"] == 1
    assert overview["content"]["word_count"] > 0
    assert overview["writing_goal"]["target_words"] == 1000
    assert "pending_items" in overview and "recent_activity" in overview


def test_research_filter_edit_conflict_delete_and_novel_isolation(tmp_path=None):
    client = TestClient(app)
    a = client.post("/api/novels", json={"title": f"Research A {uuid4()}"}).json()["id"]
    b = client.post("/api/novels", json={"title": f"Research B {uuid4()}"}).json()["id"]
    created = client.post(
        f"/api/novels/{a}/research",
        json={"title": "Phase1 Desktop 验收资料", "source_type": "NOTE", "status": "ACTIVE", "tags": ["phase1-desktop"], "excerpt": "初稿"},
    ).json()
    listed = client.get(f"/api/novels/{a}/research", params={"tag": "phase1-desktop"}).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == created["id"]
    updated = client.put(
        f"/api/novels/{a}/research/{created['id']}",
        params={"expected_version": created["version"]},
        json={"title": "Phase1 Desktop 验收资料-修订", "source_type": "NOTE", "status": "ACTIVE", "tags": ["phase1-desktop"], "excerpt": "修订摘要"},
    )
    assert updated.status_code == 200 and updated.json()["version"] == created["version"] + 1
    conflict = client.put(
        f"/api/novels/{a}/research/{created['id']}",
        params={"expected_version": created["version"]},
        json={"title": "stale", "source_type": "NOTE", "status": "ACTIVE", "tags": ["phase1-desktop"]},
    )
    assert conflict.status_code == 409
    assert client.get(f"/api/novels/{b}/research").json()["total"] == 0
    assert client.delete(f"/api/novels/{b}/research/{created['id']}").status_code == 404
    temp = client.post(
        f"/api/novels/{a}/research",
        json={"title": "临时删除", "source_type": "NOTE", "status": "ACTIVE", "tags": ["temp"]},
    ).json()
    deleted = client.delete(f"/api/novels/{a}/research/{temp['id']}", params={"expected_version": temp["version"]})
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    titles = [item["title"] for item in client.get(f"/api/novels/{a}/research").json()["items"]]
    assert "临时删除" not in titles
    sidecar = v1_capability_service._path("research")
    assert sidecar.name == "research.json"
    assert created["id"] in sidecar.read_text(encoding="utf-8")


def test_deterministic_agent_job_is_validated_without_review_apply():
    client = TestClient(app)
    client.headers.update(agent_headers())
    novel = client.post("/api/novels", json={"title": f"Agent {uuid4()}"}).json()
    nid = novel["id"]
    client.post(f"/api/novels/{nid}/chapters", json={"title": "第一章", "content": "雾港封锁。"})
    created = client.post("/api/agent-jobs", json={"agent_id": "planner", "novel_id": nid, "chapter": 1, "execution_mode": "deterministic"}).json()
    executed = client.post(f"/api/agent-jobs/{created['id']}/execute").json()
    assert executed["status"] == "VALIDATED"
    assert executed["execution_label"] == "契约校验，未调用模型"
    assert executed["result"]["structured_output"]["proposals"] == []
    assert client.post(f"/api/agent-jobs/{created['id']}/review", json={"decision": "ACCEPTED", "reviewed_by": "author"}).status_code == 400
    assert client.post(f"/api/agent-jobs/{created['id']}/apply", json={"applied_by": "author"}).status_code == 400


def test_motion_task_stays_pending_without_provider_and_rejects_placeholder():
    client = TestClient(app)
    nid = client.post("/api/novels", json={"title": f"Video {uuid4()}"}).json()["id"]
    client.post(f"/api/novels/{nid}/chapters", json={"title": "第一章", "content": "港口夜色。"})
    client.post(f"/api/novels/{nid}/chapters", json={"title": "第二章", "content": "灯塔亮起。"})
    screenplay = client.post(f"/api/novels/{nid}/screenplays", json={"title": "验收剧本"}).json()
    sid = screenplay["id"]
    client.post(f"/api/novels/{nid}/screenplays/{sid}/approve")
    client.post(f"/api/novels/{nid}/screenplays/{sid}/shots")
    client.post(f"/api/novels/{nid}/screenplays/{sid}/shots/approve")
    client.post(f"/api/novels/{nid}/screenplays/{sid}/storyboard")
    client.post(f"/api/novels/{nid}/screenplays/{sid}/storyboard/approve")
    client.post(f"/api/novels/{nid}/screenplays/{sid}/transitions")
    screenplay = client.get(f"/api/novels/{nid}/screenplays").json()[0]
    transition = screenplay["transitions"][0]
    client.put(
        f"/api/novels/{nid}/screenplays/{sid}/transitions/{transition['id']}/motion-prompt",
        json={"motion_prompt": "镜头缓慢前推，保持人物轮廓稳定。"},
    )
    created = client.post(f"/api/novels/{nid}/screenplays/{sid}/motion-tasks")
    assert created.status_code == 201
    tasks = created.json()["motion_tasks"]
    assert tasks and tasks[0]["status"] == "PENDING"
    assert tasks[0]["error"] == "VIDEO_PROVIDER_NOT_CONFIGURED"
    assert is_traceable_frame(tasks[0]["start_frame"]) and is_traceable_frame(tasks[0]["end_frame"])
    assert str(tasks[0]["start_frame"]).startswith(("shot:", "asset:", "http://", "https://", "storyboard:"))
    assert str(tasks[0]["end_frame"]).startswith(("shot:", "asset:", "http://", "https://", "storyboard:"))
    executed = client.post(f"/api/novels/{nid}/screenplays/{sid}/motion-tasks/{tasks[0]['id']}/execute")
    body = executed.json() if executed.headers.get("content-type", "").startswith("application/json") else {}
    if executed.status_code == 200:
        task = next(item for item in executed.json()["motion_tasks"] if item["id"] == tasks[0]["id"])
        assert task["status"] == "PENDING"
        assert task["error"] == "VIDEO_PROVIDER_NOT_CONFIGURED"
        assert not str((task.get("result") or {}).get("url") or "").startswith("placeholder://")
    else:
        assert executed.status_code >= 400
    require_motion_frames({"start_frame": "shot:from", "end_frame": "shot:to"})
    try:
        DeterministicVideoProvider().generate(VideoGenerationRequest("deterministic", "none", "p", "shot:a", "shot:b", "t1"))
        raise AssertionError("placeholder success must not be produced")
    except ValueError as exc:
        assert "VIDEO_PROVIDER_NOT_CONFIGURED" in str(exc)
