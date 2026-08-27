from uuid import uuid4
import time

from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.asset_providers import DeterministicVideoProvider, VideoGenerationRequest
from app.config import settings
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


def _seed_world_rule(novel_id: str, statement: str, terms: list[str]):
    from app.dependencies import lore_service
    return lore_service.repository.create_proposal({
        "id": f"rule-{uuid4()}",
        "novel_id": novel_id,
        "proposal_type": "WORLD_RULE",
        "payload": {"statement": statement, "forbidden_terms": terms},
        "status": "PENDING",
        "agent_name": "manual",
    })


def test_scan_chapter_uses_persisted_story_data_without_json_and_without_engine_flag():
    client = TestClient(app)
    missing = client.post("/api/novels/missing-novel/continuity/scan-chapter", json={})
    assert missing.status_code == 404
    nid = client.post("/api/novels", json={"title": f"Scan {uuid4()}"}).json()["id"]
    empty = client.post(f"/api/novels/{nid}/continuity/scan-chapter", json={})
    assert empty.status_code == 400
    assert empty.json()["detail"]["code"] == "CHAPTER_REQUIRED"
    chapter = client.post(
        f"/api/novels/{nid}/chapters",
        json={"title": "第一章", "content": "周启走进门。永生仪式开始。"},
    ).json()
    client.put(f"/api/novels/{nid}/characters/zhou", json={"name": "周启", "status": "DEAD"})
    client.put(
        f"/api/novels/{nid}/foreshadowing/old-port",
        json={"title": "旧港事故", "status": "OPEN", "target_chapter": 1, "description": "尚未回收"},
    )
    rule = _seed_world_rule(nid, "角色不能永生", ["永生"])
    other = client.post("/api/novels", json={"title": f"Other {uuid4()}"}).json()["id"]
    client.post(f"/api/novels/{other}/chapters", json={"title": "另一本", "content": "无关正文。"})
    isolated = client.post(f"/api/novels/{other}/continuity/scan-chapter", json={})
    assert isolated.status_code == 200
    assert isolated.json()["findings"] == []
    scanned = client.post(
        f"/api/novels/{nid}/continuity/scan-chapter",
        json={"chapter_id": chapter["id"]},
    )
    assert scanned.status_code == 200
    body = scanned.json()
    assert body["status"] == "COMPLETED"
    assert body["placeholder"] is False
    assert body["model_called"] is False
    assert body["execution_label"] == "契约校验，未调用模型"
    assert body["engine_status"] == "DISABLED"
    assert body["chapter"]["id"] == chapter["id"]
    assert body["scanned"]["characters"] == 1
    assert body["scanned"]["world_rules"] == 1
    types = {item["finding_type"] for item in body["findings"]}
    assert "CHARACTER_CONSISTENCY" in types
    assert "WORLD_RULE_VIOLATION" in types
    assert any(item.get("code") == "DEAD_CHARACTER" for item in body["findings"])
    assert any(item.get("rule_id") == rule["id"] and "永生" in item.get("evidence_ids", []) for item in body["findings"])
    assert body["foreshadowing"]["overdue"]
    assert body["foreshadowing"]["overdue"][0]["title"] == "旧港事故"
    wrong = client.post(
        f"/api/novels/{other}/continuity/scan-chapter",
        json={"chapter_id": chapter["id"]},
    )
    assert wrong.status_code == 404


def test_scan_chapter_reports_engine_status_when_continuity_rules_enabled(monkeypatch):
    from app.config import settings
    from app.dependencies import continuity_finding_service
    object.__setattr__(settings, "enable_continuity_rules", True)
    continuity_finding_service.enabled = True
    try:
        client = TestClient(app)
        nid = client.post("/api/novels", json={"title": f"Engine {uuid4()}"}).json()["id"]
        client.post(f"/api/novels/{nid}/chapters", json={"title": "第一章", "content": "港口未变。"})
        body = client.post(f"/api/novels/{nid}/continuity/scan-chapter", json={}).json()
        assert body["status"] == "COMPLETED"
        assert body["engine_status"] == "COMPLETED"
        assert body["placeholder"] is False
        assert body["model_called"] is False
    finally:
        object.__setattr__(settings, "enable_continuity_rules", False)
        continuity_finding_service.enabled = False


def test_packaged_generation_fails_closed_without_text_provider():
    from app import jobs as jobs_module
    previous_packaged = settings.enable_packaged_runtime
    previous_mock = settings.mock_provider
    client = TestClient(app)
    nid = client.post("/api/novels", json={"title": f"Write {uuid4()}"}).json()["id"]
    chapter = client.post(f"/api/novels/{nid}/chapters", json={"title": "第一章", "content": "港口灯火。"}).json()
    object.__setattr__(settings, "enable_packaged_runtime", True)
    object.__setattr__(settings, "mock_provider", True)
    try:
        job = jobs_module.jobs.create(
            "continue",
            {"novel_id": nid, "chapter_id": chapter["id"], "instruction": "续写", "provider_id": "deepseek", "model_id": "deepseek-chat"},
        )
        for _ in range(160):
            if job.status in jobs_module.JobManager.terminal:
                break
            time.sleep(0.05)
        assert job.status == "FAILED"
        assert job.error == "TEXT_PROVIDER_NOT_CONFIGURED"
        assert "海风裹着雨水" not in (job.output or "")
        try:
            jobs_module.jobs.accept(job.id)
            raise AssertionError("unconfigured text provider must not accept")
        except ValueError as exc:
            assert "completed drafts" in str(exc).casefold()
    finally:
        object.__setattr__(settings, "enable_packaged_runtime", previous_packaged)
        object.__setattr__(settings, "mock_provider", previous_mock)
