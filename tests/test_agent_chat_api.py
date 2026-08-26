from fastapi.testclient import TestClient

from app.main import app
from app.model_runtime import (
    ModelRuntimeError,
    RuntimeErrorCode,
    TextGenerationResponse,
    TextModelNodeOutput,
)
from app.runtime import runtime
from app.dependencies import user_preference_service


def test_agent_chat_uses_selected_model_and_read_only_instruction(monkeypatch):
    captured = {}

    def execute(value):
        captured["request"] = value.request
        response = TextGenerationResponse(
            text="这是只读建议。",
            finish_reason="completed",
            provider_id=value.request.provider_id,
            model_id=value.request.model_id,
        )
        return TextModelNodeOutput(response.text, response, None)

    monkeypatch.setattr(runtime.generation_runtime.text_node, "execute", execute)
    result = TestClient(app).post("/api/agent/chat", json={
        "message": "下一步怎么做？",
        "provider_id": "deepseek",
        "model_id": "deepseek-chat",
        "context": {"novel_id": "novel-1", "secret": "must-not-forward"},
    })

    assert result.status_code == 200
    assert result.json() == {"message": "这是只读建议。", "provider_id": "deepseek", "model_id": "deepseek-chat", "read_only": True, "preferences_used": False}
    request = captured["request"]
    assert "不得声称已经执行" in request.system_instruction
    assert "novel-1" in request.prompt
    assert "must-not-forward" not in request.prompt


def test_agent_chat_returns_safe_runtime_error(monkeypatch):
    def execute(_value):
        raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, "模型服务当前不可用", retryable=True)

    monkeypatch.setattr(runtime.generation_runtime.text_node, "execute", execute)
    result = TestClient(app).post("/api/agent/chat", json={"message": "你好"})

    assert result.status_code == 503
    assert result.json()["detail"] == {"code": "PROVIDER_UNAVAILABLE", "message": "模型服务当前不可用", "retryable": True}


def test_agent_chat_rejects_empty_message():
    result = TestClient(app).post("/api/agent/chat", json={"message": ""})
    assert result.status_code == 422

def test_agent_chat_only_includes_preferences_after_explicit_consent(monkeypatch, tmp_path):
    service = user_preference_service
    original_path = service.path
    service.path = tmp_path / "prefs.json"
    service.upsert("style", "克制")
    captured = {}
    def execute(value):
        captured["prompt"] = value.request.prompt
        response = TextGenerationResponse("ok", "completed", value.request.provider_id, value.request.model_id)
        return TextModelNodeOutput("ok", response, None)
    monkeypatch.setattr(runtime.generation_runtime.text_node, "execute", execute)
    client = TestClient(app)
    denied = client.post("/api/agent/chat", json={"message":"你好"}).json()
    assert denied["preferences_used"] is False and "克制" not in captured["prompt"]
    service.set_share_enabled(True)
    allowed = client.post("/api/agent/chat", json={"message":"你好"}).json()
    assert allowed["preferences_used"] is True and "克制" in captured["prompt"]
    service.path = original_path
