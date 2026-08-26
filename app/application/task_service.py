"""Application-facing adapter for the existing ``JobManager``."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .contracts import Failure, TaskRef, TaskResult, TaskSnapshot, TaskStatus


class JobManagerPort(Protocol):
    def create(self, operation: str, payload: Mapping[str, Any]) -> Any: ...
    def get(self, job_id: str) -> Any: ...
    def cancel(self, job_id: str) -> Any: ...


class TaskService:
    """Thin boundary: orchestration remains owned by the injected manager."""

    def __init__(self, manager: JobManagerPort):
        self._manager = manager

    def start(self, operation: str, payload: Mapping[str, Any]) -> TaskRef:
        job = self._manager.create(operation, dict(payload))
        return TaskRef(id=str(job.id), operation=str(job.operation))

    def get(self, task_id: str) -> TaskSnapshot:
        return snapshot_from_job(self._manager.get(task_id))

    def cancel(self, task_id: str) -> TaskSnapshot:
        return snapshot_from_job(self._manager.cancel(task_id))


def snapshot_from_job(job: Any) -> TaskSnapshot:
    raw_status = str(getattr(job.status, "value", job.status)).upper()
    try:
        status = TaskStatus(raw_status)
    except ValueError as exc:
        raise ValueError(f"unsupported job status: {raw_status}") from exc
    error = getattr(job, "error", None)
    failure = Failure(code="JOB_FAILED", message=str(error)) if error else None
    has_result = status in {TaskStatus.COMPLETED, TaskStatus.ACCEPTED, TaskStatus.REJECTED}
    result = None
    if has_result:
        result = TaskResult(
            output=str(getattr(job, "output", "")),
            provider=getattr(job, "provider", None),
            model=getattr(job, "model", None),
            issues=tuple(getattr(job, "issues", ()) or ()),
        )
    cancelled = bool(getattr(getattr(job, "cancelled", None), "is_set", lambda: False)())
    return TaskSnapshot(
        id=str(job.id),
        operation=str(job.operation),
        status=status,
        created_at=getattr(job, "created_at", None),
        updated_at=getattr(job, "updated_at", None),
        result=result,
        failure=failure,
        cancellation_requested=cancelled,
    )
