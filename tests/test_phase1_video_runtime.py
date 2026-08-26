import pytest

from app.asset_providers import HttpVideoProvider, VideoGenerationRequest, VideoGenerationResult
from app.services.screenplay_service import ScreenplayService


class Response:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {}
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class Transport:
    def __init__(self):
        self.posts = []

    def get(self, url, **kwargs):
        if url.endswith("/videos/remote-1"):
            return Response({"status": "completed", "progress": 100, "video_url": "https://cdn.example/final.mp4"})
        return Response()

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if url.endswith("/cancel"):
            return Response({"status": "cancelled"})
        return Response({"id": "remote-1", "status": "queued"})


class Repo:
    def __init__(self, task):
        self.rows = [{"id": "screenplay-1", "motion_tasks": [task], "motion_task_revision": 1}]

    def list_screenplays(self, novel_id):
        return self.rows

    def save_screenplay(self, novel_id, screenplay):
        self.rows = [screenplay]
        return screenplay


def task(**overrides):
    return {
        "id": "motion-1",
        "status": "PENDING",
        "provider_id": "video",
        "model_id": "model",
        "prompt": "camera move",
        "start_frame": "https://cdn.example/start.png",
        "end_frame": "https://cdn.example/end.png",
        **overrides,
    }


def test_http_provider_keeps_remote_id_separate_and_sends_idempotency_key():
    transport = Transport()
    provider = HttpVideoProvider(transport, "https://video.example/v1", "secret", "model")

    result = provider.generate(VideoGenerationRequest("video", "model", "prompt", "start", "end", "motion-1"))

    assert result.video_uri is None
    assert result.remote_task_id == "remote-1"
    assert result.status == "PENDING"
    assert transport.posts[0][1]["headers"]["Idempotency-Key"] == "motion-1"
    assert provider.capabilities()["cancellation"] is True


def test_motion_submit_sync_and_asset_ready_state_are_persistent():
    repo = Repo(task())
    provider = HttpVideoProvider(Transport(), "https://video.example/v1", "secret", "model")
    service = ScreenplayService(repo, object(), video_providers={"video": provider})

    submitted = service.execute_motion_task("novel-1", "screenplay-1", "motion-1")
    submitted_task = submitted["motion_tasks"][0]
    assert submitted_task["status"] == "PENDING"
    assert submitted_task["remote_task_id"] == "remote-1"
    assert submitted_task["attempts"] == 1
    assert submitted_task["submission_key"] == "motion-1"

    synced = service.sync_motion_task("novel-1", "screenplay-1", "motion-1")
    synced_task = synced["motion_tasks"][0]
    assert synced_task["status"] == "SUCCEEDED"
    assert synced_task["result"]["url"] == "https://cdn.example/final.mp4"
    assert synced_task["asset_import"]["import_status"] == "READY_TO_IMPORT"


def test_submit_failure_is_durable_and_retry_preserves_idempotency_key():
    class BrokenProvider:
        def generate(self, request):
            raise RuntimeError("provider unavailable")

    repo = Repo(task())
    service = ScreenplayService(repo, object(), video_providers={"video": BrokenProvider()})

    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.execute_motion_task("novel-1", "screenplay-1", "motion-1")

    failed = repo.rows[0]["motion_tasks"][0]
    assert failed["status"] == "FAILED"
    assert failed["attempts"] == 1
    assert failed["history"][-1]["phase"] == "SUBMITTING"
    retried = service.retry_motion_task("novel-1", "screenplay-1", "motion-1")["motion_tasks"][0]
    assert retried["status"] == "PENDING"
    assert retried["submission_key"] == "motion-1:attempt:2"
    assert retried["remote_task_id"] is None


def test_remote_cancel_must_succeed_before_local_terminal_state():
    transport = Transport()
    provider = HttpVideoProvider(transport, "https://video.example/v1", "secret", "model")
    repo = Repo(task(status="RUNNING", remote_task_id="remote-1"))
    service = ScreenplayService(repo, object(), video_providers={"video": provider})

    cancelled = service.cancel_motion_task("novel-1", "screenplay-1", "motion-1")["motion_tasks"][0]

    assert cancelled["status"] == "CANCELLED"
    assert transport.posts[-1][0].endswith("/videos/remote-1/cancel")


def test_terminal_callback_cannot_regress_or_succeed_without_url():
    repo = Repo(task(status="RUNNING"))
    service = ScreenplayService(repo, object(), video_providers={})

    with pytest.raises(ValueError, match="requires a video URL"):
        service.motion_callback("novel-1", "screenplay-1", "motion-1", "SUCCEEDED", 100)

    service.motion_callback("novel-1", "screenplay-1", "motion-1", "CANCELLED")
    with pytest.raises(ValueError, match="terminal motion task"):
        service.motion_callback("novel-1", "screenplay-1", "motion-1", "RUNNING", 10)
