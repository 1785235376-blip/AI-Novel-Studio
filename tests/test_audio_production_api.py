from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


def setup_project(content="林海抵达雾港。"):
    client = TestClient(app)
    novel = client.post("/api/novels", json={"title": f"Audio {uuid4()}"}).json()
    chapter = client.post(f"/api/novels/{novel['id']}/chapters", json={"title": "第一章", "content": content}).json()
    return client, novel["id"], chapter["id"]


def test_audio_settings_and_job_configuration_are_persistent():
    client, novel_id, chapter_id = setup_project()
    settings = {
        "voice_bindings": [{"character_id": "lin-hai", "provider_id": "custom", "model_id": "tts-cn", "voice": "narrator", "emotion": "calm"}],
        "pronunciation_dictionary": [{"term": "雾港", "pronunciation": "wu4 gang3"}],
    }
    assert client.put(f"/api/novels/{novel_id}/audio-production/settings", json=settings).status_code == 200
    assert client.get(f"/api/novels/{novel_id}/audio-production/settings").json() == {"novel_id": novel_id, **settings}
    queued = client.post(f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue", json={"provider_id": "openai", "model_id": "ignored", "voice": "ignored", "character_id": "lin-hai"}).json()
    assert queued["status"] == "QUEUED"
    assert queued["provider_id"] == "custom" and queued["model_id"] == "tts-cn" and queued["voice"] == "narrator"
    assert queued["attempt"] == 0 and queued["id"].startswith("audio-")
    assert queued["timing_status"] == "ESTIMATED"
    assert queued["segments"][0]["start_ms"] == 0
    assert queued["segments"][-1]["end_ms"] == queued["estimated_duration_ms"]


def test_audiobook_cancel_and_retry_transitions_are_enforced():
    client, novel_id, chapter_id = setup_project()
    job = client.post(f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue", json={"provider_id": "missing", "model_id": "tts", "voice": "voice"}).json()
    cancelled = client.post(f"/api/novels/{novel_id}/audiobook/jobs/{job['id']}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    execute = client.post(f"/api/novels/{novel_id}/audiobook/jobs/{job['id']}/execute")
    assert execute.status_code == 409 and execute.json()["detail"]["code"] == "AUDIOBOOK_JOB_NOT_EXECUTABLE"
    retried = client.post(f"/api/novels/{novel_id}/audiobook/jobs/{job['id']}/retry")
    assert retried.status_code == 200 and retried.json()["status"] == "QUEUED"


def test_provider_failure_is_persisted_with_stable_error():
    client, novel_id, chapter_id = setup_project()
    job = client.post(f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue", json={"provider_id": "missing", "model_id": "tts", "voice": "voice"}).json()
    response = client.post(f"/api/novels/{novel_id}/audiobook/jobs/{job['id']}/execute")
    assert response.status_code == 503 and response.json()["detail"]["code"] == "SPEECH_PROVIDER_UNAVAILABLE"
    persisted = client.get(f"/api/novels/{novel_id}/audiobook/jobs").json()["items"][-1]
    assert persisted["status"] == "FAILED" and persisted["error_code"] == "SPEECH_PROVIDER_UNAVAILABLE"
    assert persisted["attempt"] == 1 and "audio_uri" not in persisted


@pytest.mark.parametrize(
    "field,value",
    [
        ("speech_rate", 0.49),
        ("speech_rate", 2.01),
        ("pause_ms", -1),
        ("pause_ms", 3001),
    ],
)
def test_audiobook_queue_rejects_invalid_timing_parameters_without_creating_job(field, value):
    client, novel_id, chapter_id = setup_project()
    body = {"provider_id": "openai", "model_id": "tts", "voice": "alloy", field: value}

    response = client.post(f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue", json=body)

    assert response.status_code == 422
    assert client.get(f"/api/novels/{novel_id}/audiobook/jobs").json()["items"] == []


def test_multisentence_subtitle_segments_have_monotonic_timecodes_and_requested_pauses():
    client, novel_id, chapter_id = setup_project("第一句。第二句！\n第三句？最后一句")

    response = client.post(
        f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue",
        json={"provider_id": "openai", "model_id": "tts", "voice": "alloy", "speech_rate": 1.25, "pause_ms": 420},
    )

    assert response.status_code == 202
    job = response.json()
    segments = job["segments"]
    assert [segment["id"] for segment in segments] == ["segment-0001", "segment-0002", "segment-0003", "segment-0004"]
    assert [segment["text"] for segment in segments] == ["第一句。", "第二句！", "第三句？", "最后一句"]
    assert segments[0]["start_ms"] == 0
    assert all(segment["end_ms"] > segment["start_ms"] for segment in segments)
    assert all(current["end_ms"] + 420 == following["start_ms"] for current, following in zip(segments, segments[1:]))
    assert all(current["end_ms"] < following["end_ms"] for current, following in zip(segments, segments[1:]))
    assert job["estimated_duration_ms"] == segments[-1]["end_ms"]
