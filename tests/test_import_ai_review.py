import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import import_review_service
from app.model_runtime import TextGenerationResponse, TextModelNodeOutput
from app.runtime import runtime


def _import_pending(client: TestClient):
    title = f"AI审查测试-{uuid4()}"
    response = client.post("/api/novels/import", json={
        "format": "txt",
        "content": f"{title}\n第一章 起点\n林默在云港遇见沈舟。\n第二章 回声\n林默返回云港。",
        "confirm": True,
    })
    assert response.status_code == 200
    payload = response.json()
    return payload["novel"], payload["knowledge_review"]


def test_import_ai_review_replaces_draft_but_does_not_accept_entities(monkeypatch, tmp_path):
    original_path = import_review_service.path
    import_review_service.path = tmp_path / "import_reviews.json"
    captured = {}

    def execute(value):
        captured["request"] = value.request
        text = json.dumps({"candidates": {
            "characters": [{"name": "林默", "role": "主角", "evidence": "两章均出现", "confidence": 0.96}],
            "locations": [{"name": "云港", "evidence": "人物到访和返回", "confidence": 0.9}],
            "timeline_events": [], "foreshadowing": [],
        }}, ensure_ascii=False)
        response = TextGenerationResponse(text, "completed", value.request.provider_id, value.request.model_id)
        return TextModelNodeOutput(text, response, None)

    monkeypatch.setattr(runtime.generation_runtime.text_node, "execute", execute)
    try:
        client = TestClient(app)
        novel, review = _import_pending(client)
        result = client.post(
            f"/api/novels/{novel['id']}/import/knowledge-base/review/{review['id']}/ai-analyze",
            json={"provider_id": "deepseek", "model_id": "deepseek-chat"},
        )
        assert result.status_code == 200
        saved = result.json()["review"]
        assert saved["status"] == "PENDING"
        assert saved["candidates"]["characters"][0]["name"] == "林默"
        assert saved["candidates"]["characters"][0]["analysis_source"] == "AI_REVIEW"
        assert saved["selected"]["characters"] == [False]
        assert saved["analysis"]["model_id"] == "deepseek-chat"
        assert "章节节选" in captured["request"].prompt
        assert captured["request"].metadata["mode"] == "author_approval_required"
    finally:
        import_review_service.path = original_path


def test_import_ai_review_keeps_local_draft_when_model_output_is_invalid(monkeypatch, tmp_path):
    original_path = import_review_service.path
    import_review_service.path = tmp_path / "import_reviews.json"

    def execute(value):
        response = TextGenerationResponse("这不是 JSON", "completed", value.request.provider_id, value.request.model_id)
        return TextModelNodeOutput(response.text, response, None)

    monkeypatch.setattr(runtime.generation_runtime.text_node, "execute", execute)
    try:
        client = TestClient(app)
        novel, review = _import_pending(client)
        before = review["candidates"]
        result = client.post(f"/api/novels/{novel['id']}/import/knowledge-base/review/{review['id']}/ai-analyze", json={})
        assert result.status_code == 422
        persisted = client.get(f"/api/novels/{novel['id']}/import/knowledge-base/review/{review['id']}").json()
        assert persisted["candidates"] == before
        assert persisted.get("analysis") is None
    finally:
        import_review_service.path = original_path


def test_manual_chapter_can_create_scoped_ai_knowledge_review(monkeypatch, tmp_path):
    original_path = import_review_service.path
    import_review_service.path = tmp_path / "import_reviews.json"
    captured = {}

    def execute(value):
        captured["prompt"] = value.request.prompt
        text = json.dumps({"candidates": {"characters": [{"name": "手写人物"}]}}, ensure_ascii=False)
        response = TextGenerationResponse(text, "completed", value.request.provider_id, value.request.model_id)
        return TextModelNodeOutput(text, response, None)

    monkeypatch.setattr(runtime.generation_runtime.text_node, "execute", execute)
    try:
        client = TestClient(app)
        novel = client.post("/api/novels", json={"title": f"手写审查-{uuid4()}"}).json()
        first = client.post(f"/api/novels/{novel['id']}/chapters", json={"title": "手写章", "content": "手写人物走进旧车站。"}).json()
        client.post(f"/api/novels/{novel['id']}/chapters", json={"title": "不应读取", "content": "另一个人物在远方。"})
        prepared = client.post(f"/api/novels/{novel['id']}/chapters/{first['id']}/knowledge-base/review")
        assert prepared.status_code == 201
        review = prepared.json()
        assert review["source_format"] == "chapter"
        result = client.post(f"/api/novels/{novel['id']}/import/knowledge-base/review/{review['id']}/ai-analyze", json={})
        assert result.status_code == 200
        assert result.json()["analysis"]["chapter_count"] == 1
        assert "手写人物走进旧车站" in captured["prompt"]
        assert "另一个人物在远方" not in captured["prompt"]
    finally:
        import_review_service.path = original_path
