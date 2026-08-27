from app import audio_provider_config
from app.audio_providers import provider_catalog
from app.main import app
from fastapi.testclient import TestClient


def test_custom_audio_provider_is_persisted_without_secret(monkeypatch, tmp_path):
    path = tmp_path / "audio-providers.json"
    monkeypatch.setenv("AUDIO_PROVIDER_CONFIG_PATH", str(path))
    saved = audio_provider_config.save("studio-audio", endpoint="https://audio.example/v1", default_model="voice-pro", display_name="Studio Audio", local=False, enabled=True, requires_credential=True, capabilities=["TTS", "MUSIC"])
    assert saved["capabilities"] == ["TTS", "MUSIC"]
    assert "secret" not in path.read_text(encoding="utf-8")
    row = next(item for item in provider_catalog() if item["provider_id"] == "studio-audio")
    assert row["endpoint"] == "https://audio.example/v1"


def test_audio_provider_rejects_unknown_capability(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIO_PROVIDER_CONFIG_PATH", str(tmp_path / "audio-providers.json"))
    try:
        audio_provider_config.save("bad", endpoint="https://audio.example/v1", default_model="x", display_name="Bad", local=False, enabled=True, requires_credential=True, capabilities=["UNKNOWN"])
    except ValueError as exc:
        assert "capabilities" in str(exc)
    else:
        raise AssertionError("unknown capability accepted")


def test_audio_provider_api_exposes_custom_provider_without_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIO_PROVIDER_CONFIG_PATH", str(tmp_path / "audio-providers.json"))
    client = TestClient(app)
    response = client.put("/api/audio/providers/cloud-voice", json={"endpoint":"https://voice.example/v1","default_model":"voice-v2","display_name":"Cloud Voice","local":False,"enabled":True,"requires_credential":True,"capabilities":["TTS"]})
    assert response.status_code == 200
    assert response.json()["secret"] is None
    rows = {item["provider_id"]: item for item in client.get("/api/audio/providers").json()["items"]}
    assert rows["cloud-voice"]["display_name"] == "Cloud Voice"
    assert rows["cloud-voice"]["configured"] is False
    assert rows["cloud-voice"]["secret"] is None
