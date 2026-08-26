from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.audio_production_store import audio_production_store


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


def test_media_task_recovery_feed_returns_persisted_audiobook_jobs():
    client, novel_id, chapter_id = setup_project()
    queued = client.post(
        f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue",
        json={"provider_id": "missing", "model_id": "tts", "voice": "voice"},
    ).json()

    response = client.get(f"/api/novels/{novel_id}/media-tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["novel_id"] == novel_id
    assert any(item["id"] == queued["id"] and item["status"] == "QUEUED" for item in payload["audiobook"])
    assert isinstance(payload["motion"], list)


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


def test_subtitle_exports_are_deterministic_and_come_from_persisted_segments():
    client, novel_id, chapter_id = setup_project("第一句。第二句！")
    job = client.post(
        f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue",
        json={"provider_id": "missing", "model_id": "tts", "voice": "alloy", "pause_ms": 300},
    ).json()

    srt = client.get(f"/api/novels/{novel_id}/audiobook/jobs/{job['id']}/subtitles.srt")
    vtt = client.get(f"/api/novels/{novel_id}/audiobook/jobs/{job['id']}/subtitles.vtt")

    assert srt.status_code == 200
    assert "00:00:00,000 --> 00:00:00,720\n第一句。" in srt.text
    assert "00:00:01,020 --> 00:00:01,740\n第二句！" in srt.text
    assert vtt.status_code == 200
    assert vtt.text.startswith("WEBVTT\n\n1\n00:00:00.000 --> 00:00:00.720")
    assert "attachment;" in vtt.headers["content-disposition"]


def test_user_triggered_consumer_recovers_stale_running_jobs_and_reports_real_failures():
    client, novel_id, chapter_id = setup_project()
    first = client.post(
        f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue",
        json={"provider_id": "missing", "model_id": "tts", "voice": "alloy"},
    ).json()
    second = client.post(
        f"/api/novels/{novel_id}/audiobook/chapters/{chapter_id}/queue",
        json={"provider_id": "missing", "model_id": "tts", "voice": "nova"},
    ).json()
    state = audio_production_store.load(novel_id)
    state["jobs"][0] = {**state["jobs"][0], "status": "RUNNING", "updated_at": "2020-01-01T00:00:00+00:00"}
    audio_production_store.save(novel_id, state)

    response = client.post(
        f"/api/novels/{novel_id}/audiobook/jobs/consume",
        json={"limit": 2, "recover_stale": True, "stale_after_seconds": 60},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution"] == "SYNCHRONOUS_USER_TRIGGERED"
    assert payload["recovered"] == [first["id"]]
    assert payload["processed"] == 2 and payload["remaining_queued"] == 0
    assert [item["id"] for item in payload["results"]] == [first["id"], second["id"]]
    assert all(item == {"id": item["id"], "status": "FAILED", "error_code": "SPEECH_PROVIDER_UNAVAILABLE"} for item in payload["results"])
    manifest = client.get(f"/api/novels/{novel_id}/audiobook/manifest").json()
    assert manifest["chapters"][0]["production_status"] == "FAILED"
