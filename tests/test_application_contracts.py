from types import SimpleNamespace

import pytest

from app.application.contracts import Progress, TaskStatus
from app.application.events import DocumentSaved, TaskCompleted, TaskFailed, TaskStarted
from app.application.task_service import TaskService


class Manager:
    def __init__(self):
        self.job = SimpleNamespace(
            id="job-1", operation="review", status="QUEUED", output="", error=None,
            provider=None, model=None, issues=[], created_at="now", updated_at="now",
            cancelled=SimpleNamespace(is_set=lambda: False),
        )

    def create(self, operation, payload):
        self.job.operation = operation
        return self.job

    def get(self, job_id):
        assert job_id == self.job.id
        return self.job

    def cancel(self, job_id):
        self.job.status = "CANCELLED"
        self.job.cancelled = SimpleNamespace(is_set=lambda: True)
        return self.job


def test_task_service_adapts_existing_manager_without_owning_execution():
    manager = Manager()
    service = TaskService(manager)
    assert service.start("review", {"novel_id": "n"}).id == "job-1"
    assert service.get("job-1").status is TaskStatus.QUEUED
    cancelled = service.cancel("job-1")
    assert cancelled.status is TaskStatus.CANCELLED
    assert cancelled.cancellation_requested


def test_completed_and_failed_result_contracts():
    manager = Manager()
    service = TaskService(manager)
    manager.job.status = "COMPLETED"
    manager.job.output = "done"
    assert service.get("job-1").result.output == "done"
    manager.job.status = "FAILED"
    manager.job.error = "boom"
    failed = service.get("job-1")
    assert failed.failure.code == "JOB_FAILED" and failed.result is None


def test_progress_validation_and_terminal_semantics():
    assert Progress(1, 2).current == 1
    assert TaskStatus.COMPLETED.terminal and not TaskStatus.RUNNING.terminal
    with pytest.raises(ValueError):
        Progress(3, 2)


def test_application_events_are_typed_and_timezone_aware():
    events = [
        DocumentSaved(document_id="chapter-1", version=2),
        TaskStarted(task_id="t", operation="review"),
        TaskCompleted(task_id="t", operation="review", result="ok"),
        TaskFailed(task_id="t", operation="review", code="X", message="bad"),
    ]
    assert all(event.occurred_at.tzinfo is not None for event in events)
