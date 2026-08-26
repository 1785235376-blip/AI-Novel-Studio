from __future__ import annotations

import base64
import binascii
import hashlib
import json
import inspect
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..storage import atomic_write


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExportJobUnavailable(RuntimeError):
    """Raised when an export has not produced a downloadable result yet."""

    def __init__(self, status: str):
        self.status = status
        super().__init__(f"export job is not ready (status: {status})")


class ExportJobResultInvalid(RuntimeError):
    """Raised when a succeeded job does not contain a safe export payload."""


class ExportJobNotCancellable(RuntimeError):
    """Raised when a terminal export cannot be cancelled."""

    def __init__(self, status: str):
        self.status = status
        super().__init__(f"export job cannot be cancelled (status: {status})")


class ExportJobNotRetryable(RuntimeError):
    """Raised when an export is not in a failed/cancelled state."""

    def __init__(self, status: str):
        self.status = status
        super().__init__(f"export job cannot be retried (status: {status})")


class _ExportCancelled(RuntimeError):
    """Internal cooperative cancellation signal for exporters that report progress."""


class ExportJobService:
    """Durable, local-first export queue with bounded background workers."""

    SUPPORTED = {"json", "txt", "text", "markdown", "md", "docx", "word", "pdf", "epub", "screenplay", "shot-list", "storyboard"}
    STATUSES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
    MEDIA_TYPES = {
        "json": "application/json",
        "txt": "text/plain",
        "markdown": "text/markdown",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "epub": "application/epub+zip",
        "screenplay": "text/markdown",
        "shot-list": "text/csv",
        "storyboard": "text/markdown",
    }
    EXTENSIONS = {
        "json": "json",
        "txt": "txt",
        "markdown": "md",
        "docx": "docx",
        "pdf": "pdf",
        "epub": "epub",
        "screenplay": "md",
        "shot-list": "csv",
        "storyboard": "md",
    }
    IDEMPOTENCY_TTL = timedelta(hours=24)
    MAX_RESULT_BYTES = 64 * 1024 * 1024

    def __init__(self, data_path: Path, exporter, snapshotter=None):
        self.path = data_path / "export_jobs.json"
        self.exporter = exporter
        self.snapshotter = snapshotter
        self.artifact_root = data_path / "export_artifacts"
        try:
            self.artifact_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            # The queue remains usable in read-only/legacy profiles; inline
            # bounded payloads are still retained as a compatibility fallback.
            pass
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="export")
        self._futures = {}
        self._cancel_events = {}
        # A desktop process can be closed while a task is writing its result.
        # Requeue interrupted work on the next process start instead of leaving
        # a permanently-running item in the local queue.
        self._recover_on_startup()

    def _read(self) -> dict:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @classmethod
    def _is_idempotency_fresh(cls, item: dict) -> bool:
        try:
            created = datetime.fromisoformat(str(item.get("created_at", "")))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - created <= cls.IDEMPOTENCY_TTL
        except (TypeError, ValueError):
            return False

    def _write(self, value: dict) -> None:
        atomic_write(self.path, json.dumps(value, ensure_ascii=False, indent=2))

    @staticmethod
    def _normalise_job(job: dict) -> dict:
        """Fill lifecycle fields for jobs written by older builds.

        The returned dictionary is a copy so reading an old record does not
        unexpectedly mutate the durable queue.  New records persist all of
        these fields, while this compatibility path keeps pre-lifecycle jobs
        readable during a desktop upgrade.
        """
        item = dict(job)
        status = str(item.get("status") or "queued").lower()
        item["status"] = status
        try:
            progress = int(item.get("progress", 100 if status == "succeeded" else 0))
        except (TypeError, ValueError):
            progress = 0
        item["progress"] = max(0, min(100, progress))
        item.setdefault("progress_message", {
            "queued": "排队中",
            "running": "处理中",
            "succeeded": "已完成",
            "failed": "失败",
            "cancelled": "已取消",
        }.get(status, status))
        item.setdefault("retry_of", None)
        item.setdefault("attempt", 1)
        item.setdefault("cancel_requested", False)
        item.setdefault("recovery_count", 0)
        item.setdefault("snapshot_id", None)
        item.setdefault("snapshot", None)
        item.setdefault("resource_manifest", {"referenced": [], "available": [], "missing": [], "missing_count": 0})
        item.setdefault("missing_resources", item.get("resource_manifest", {}).get("missing", []) if isinstance(item.get("resource_manifest"), dict) else [])
        item.setdefault("permission_context", None)
        item.setdefault("artifact", None)
        return item

    def _recover_on_startup(self) -> None:
        """Requeue queued/running jobs left by a previous process.

        ``running`` is converted to ``queued`` before submission.  Exporters
        only read project state and write the job record, so replaying an
        interrupted export is safe and deterministic.  A job explicitly marked
        ``cancel_requested`` is finalised as cancelled instead.
        """
        pending = []
        changed = False
        with self._lock:
            jobs = self._read()
            for job_id, raw in list(jobs.items()):
                if not isinstance(raw, dict):
                    continue
                status = str(raw.get("status") or "").lower()
                if status not in {"queued", "running"}:
                    continue
                if raw.get("cancel_requested"):
                    raw.update(
                        status="cancelled",
                        progress_message="已取消",
                        error={"code": "EXPORT_CANCELLED", "message": "export cancelled"},
                        finished_at=_now(),
                        updated_at=_now(),
                    )
                else:
                    try:
                        previous_progress = int(raw.get("progress", 0) or 0)
                    except (TypeError, ValueError):
                        previous_progress = 0
                    try:
                        previous_recoveries = int(raw.get("recovery_count", 0) or 0)
                    except (TypeError, ValueError):
                        previous_recoveries = 0
                    raw.update(
                        status="queued",
                        progress=max(0, min(5, previous_progress)),
                        progress_message="等待恢复",
                        recovery_count=previous_recoveries + 1,
                        recovered_at=_now(),
                        updated_at=_now(),
                    )
                    pending.append(str(job_id))
                changed = True
            if changed:
                self._write(jobs)
        for job_id in pending:
            self._submit(job_id)

    def _submit(self, job_id: str) -> None:
        try:
            future = self._pool.submit(self._run, job_id)
        except RuntimeError as exc:
            # A service being shut down should not leave a forever-queued job.
            with self._lock:
                jobs = self._read()
                job = jobs.get(job_id)
                if isinstance(job, dict) and str(job.get("status", "")).lower() == "queued":
                    job.update(
                        status="failed",
                        progress_message="队列不可用",
                        error={"code": "EXPORT_QUEUE_UNAVAILABLE", "message": str(exc)},
                        finished_at=_now(),
                        updated_at=_now(),
                    )
                    self._write(jobs)
            return
        with self._lock:
            if future.done():
                self._futures.pop(job_id, None)
            else:
                self._futures[job_id] = future

    def create(
        self,
        novel_id: str,
        format: str,
        idempotency_key: str | None = None,
        *,
        retry_of: str | None = None,
        permission_context: dict | None = None,
    ) -> dict:
        fmt = str(format or "json").lower().strip()
        if fmt not in self.SUPPORTED:
            raise ValueError("unsupported export format")
        fmt = "markdown" if fmt == "md" else ("txt" if fmt == "text" else ("docx" if fmt == "word" else fmt))
        with self._lock:
            jobs = self._read()
            if idempotency_key:
                for item in jobs.values():
                    if isinstance(item, dict) and item.get("novel_id") == novel_id and item.get("idempotency_key") == idempotency_key and self._is_idempotency_fresh(item):
                        return self._normalise_job(item)
            attempt = 1
            if retry_of:
                source = jobs.get(retry_of)
                if isinstance(source, dict):
                    try:
                        attempt = max(1, int(source.get("attempt", 1) or 1) + 1)
                    except (TypeError, ValueError):
                        attempt = 2
            snapshot = self._capture_snapshot(novel_id, fmt)
            resource_manifest = snapshot.get("resource_manifest", {}) if isinstance(snapshot, dict) else {}
            job = {
                "id": str(uuid.uuid4()), "novel_id": novel_id, "format": fmt,
                "status": "queued", "created_at": _now(), "updated_at": _now(),
                "idempotency_key": idempotency_key, "result": None, "error": None,
                "progress": 0, "progress_message": "排队中", "retry_of": retry_of,
                "attempt": attempt, "cancel_requested": False, "recovery_count": 0,
                "snapshot_id": snapshot.get("snapshot_id") if isinstance(snapshot, dict) else None,
                "snapshot": snapshot,
                "resource_manifest": resource_manifest,
                "missing_resources": resource_manifest.get("missing", []) if isinstance(resource_manifest, dict) else [],
                "permission_context": permission_context,
                "artifact": None,
            }
            jobs[job["id"]] = job
            self._write(jobs)
        self._submit(job["id"])
        return self._normalise_job(job)

    def _capture_snapshot(self, novel_id: str, format: str):
        """Call an optional snapshot provider while preserving old adapters."""
        if self.snapshotter is None:
            return None
        try:
            parameters = inspect.signature(self.snapshotter).parameters
        except (TypeError, ValueError):
            parameters = {}
        try:
            if "format" in parameters or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
                snapshot = self.snapshotter(novel_id, format=format)
            elif len(parameters) >= 2:
                snapshot = self.snapshotter(novel_id, format)
            else:
                snapshot = self.snapshotter(novel_id)
        except TypeError:
            # A legacy test adapter may reject keyword arguments despite a
            # broad signature; retry only with positional arguments.
            snapshot = self.snapshotter(novel_id, format)
        if snapshot is None:
            return None
        if not isinstance(snapshot, dict):
            raise ValueError("export snapshot is invalid")
        return snapshot

    def get(self, job_id: str) -> dict:
        with self._lock:
            job = self._read().get(job_id)
            if not job:
                raise FileNotFoundError(job_id)
            if not isinstance(job, dict):
                raise ExportJobResultInvalid("export job record is invalid")
            return self._normalise_job(job)

    def _set_progress(self, job_id: str, progress: object, message: str | None = None) -> bool:
        try:
            value = int(float(progress))
        except (TypeError, ValueError):
            return False
        value = max(0, min(100, value))
        with self._lock:
            jobs = self._read()
            job = jobs.get(job_id)
            if not isinstance(job, dict) or str(job.get("status", "")).lower() in {"succeeded", "failed", "cancelled"}:
                return False
            try:
                current_progress = int(job.get("progress", 0) or 0)
            except (TypeError, ValueError):
                current_progress = 0
            if current_progress == value and (message is None or job.get("progress_message") == message):
                return True
            job["progress"] = value
            if message:
                job["progress_message"] = str(message)[:200]
            job["updated_at"] = _now()
            self._write(jobs)
            return True

    def cancel(self, job_id: str) -> dict:
        """Request cooperative cancellation and return the final queue record."""
        with self._lock:
            jobs = self._read()
            job = jobs.get(job_id)
            if not isinstance(job, dict):
                raise FileNotFoundError(job_id)
            status = str(job.get("status") or "queued").lower()
            if status not in {"queued", "running"}:
                raise ExportJobNotCancellable(status)
            self._cancel_events.setdefault(job_id, threading.Event()).set()
            future = self._futures.get(job_id)
            if future is not None and status == "queued":
                if future.cancel():
                    self._futures.pop(job_id, None)
            job.update(
                status="cancelled",
                progress_message="已取消",
                error={"code": "EXPORT_CANCELLED", "message": "export cancelled"},
                cancel_requested=True,
                finished_at=_now(),
                updated_at=_now(),
            )
            self._write(jobs)
            self._cancel_events.pop(job_id, None)
            return self._normalise_job(job)

    def retry(self, job_id: str) -> dict:
        """Create a fresh attempt for a failed or cancelled export."""
        job = self.get(job_id)
        status = str(job.get("status") or "").lower()
        if status not in {"failed", "cancelled"}:
            raise ExportJobNotRetryable(status)
        return self.create(
            job["novel_id"],
            job["format"],
            retry_of=job_id,
            permission_context=job.get("permission_context"),
        )

    @staticmethod
    def _safe_filename(filename: object, job_id: str, format: str) -> str:
        """Return a filename suitable for a Content-Disposition header.

        Exporters are local code, but filenames are still treated as untrusted
        data because persisted jobs can outlive a process upgrade.  Keep only
        the final path component and remove header control characters/quotes so
        a result can never inject a response header or escape a download name.
        """
        raw = str(filename or "").replace("\r", "").replace("\n", "")
        raw = raw.replace("\\", "/").rsplit("/", 1)[-1]
        raw = re.sub(r"[\x00-\x1f\x7f]", "", raw).replace('"', "_").strip()
        if not raw:
            extension = ExportJobService.EXTENSIONS.get(format, "bin")
            safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(job_id))[:64] or "job"
            raw = f"export-{safe_id}.{extension}"
        return raw[:255]

    @classmethod
    def _media_type(cls, value: object, format: str) -> str:
        """Allow only a single MIME type token; otherwise use a known default."""
        candidate = str(value or "").strip()
        if re.fullmatch(r"[A-Za-z0-9!#$&^_.+*-]+/[A-Za-z0-9!#$&^_.+*-]+", candidate):
            return candidate
        return cls.MEDIA_TYPES.get(format, "application/octet-stream")

    def download(self, job_id: str) -> dict:
        """Build a safe download payload for a completed export job.

        The queue stores export results as metadata plus text or bounded
        base64-encoded binary content. This method deliberately does not read
        arbitrary paths from persisted data; future binary exporters must use
        the same service-owned payload boundary before they can be downloaded.
        """
        job = self.get(job_id)
        if not isinstance(job, dict):
            raise ExportJobResultInvalid("export job record is invalid")
        status = str(job.get("status") or "").lower()
        if status not in self.STATUSES:
            raise ExportJobResultInvalid("invalid export job status")
        if status != "succeeded":
            raise ExportJobUnavailable(status)

        result = job.get("result")
        if not isinstance(result, dict):
            raise ExportJobResultInvalid("export result is missing")
        content_bytes = None
        artifact = job.get("artifact")
        if isinstance(artifact, dict) and artifact.get("path"):
            try:
                root = self.artifact_root.resolve()
                target = (self.artifact_root / str(artifact["path"])).resolve()
                if target.parent != root:
                    raise ExportJobResultInvalid("export artifact path is invalid")
                content_bytes = target.read_bytes()
                if len(content_bytes) > self.MAX_RESULT_BYTES:
                    raise ExportJobResultInvalid("export artifact exceeds the 64 MiB limit")
                expected_hash = str(artifact.get("sha256") or "")
                if expected_hash and hashlib.sha256(content_bytes).hexdigest() != expected_hash:
                    raise ExportJobResultInvalid("export artifact checksum mismatch")
            except FileNotFoundError:
                content_bytes = None
        if content_bytes is None:
            content_bytes = self._result_bytes(result)

        format = str(job.get("format") or result.get("format") or "bin").lower().strip()
        format = "markdown" if format == "md" else ("txt" if format == "text" else ("docx" if format == "word" else format))
        return {
            "content": content_bytes,
            "filename": self._safe_filename(result.get("filename"), job_id, format),
            "media_type": self._media_type(result.get("media_type"), format),
            "format": format,
        }

    # Explicit alias for callers that prefer a descriptive method name.
    def download_payload(self, job_id: str) -> dict:
        return self.download(job_id)

    def _invoke_exporter(self, job: dict, progress_callback) -> dict:
        """Invoke legacy two-argument exporters, with optional progress hooks."""
        try:
            parameters = inspect.signature(self.exporter).parameters
        except (TypeError, ValueError):
            parameters = {}
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
        )
        kwargs = {}
        if "snapshot" in parameters or accepts_kwargs:
            kwargs["snapshot"] = job.get("snapshot")
        if "progress_callback" in parameters or accepts_kwargs:
            kwargs["progress_callback"] = progress_callback
        elif "progress" in parameters:
            kwargs["progress"] = progress_callback
        if kwargs:
            try:
                return self.exporter(job["novel_id"], job["format"], **kwargs)
            except TypeError:
                # Preserve compatibility with adapters that expose a broad
                # signature but reject one optional keyword internally.
                kwargs.pop("snapshot", None)
                if kwargs:
                    try:
                        return self.exporter(job["novel_id"], job["format"], **kwargs)
                    except TypeError:
                        pass
        return self.exporter(job["novel_id"], job["format"])

    @staticmethod
    def _result_bytes(result: dict) -> bytes:
        """Decode a bounded exporter payload for artifact persistence/download."""
        if not isinstance(result, dict):
            raise ExportJobResultInvalid("export result is missing")
        encoded = result.get("content_base64")
        if encoded is not None:
            if not isinstance(encoded, str) or result.get("content_encoding", "base64") != "base64":
                raise ExportJobResultInvalid("export result encoding is invalid")
            try:
                content_bytes = base64.b64decode(encoded.encode("ascii"), validate=True)
            except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
                raise ExportJobResultInvalid("export result content is invalid") from exc
        else:
            content = result.get("content")
            if result.get("content_encoding") == "base64" and isinstance(content, str):
                try:
                    content_bytes = base64.b64decode(content.encode("ascii"), validate=True)
                except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
                    raise ExportJobResultInvalid("export result content encoding is invalid") from exc
            elif isinstance(content, str):
                content_bytes = content.encode("utf-8")
            elif isinstance(content, (bytes, bytearray, memoryview)):
                content_bytes = bytes(content)
            else:
                raise ExportJobResultInvalid("export result content is invalid")
        if len(content_bytes) > ExportJobService.MAX_RESULT_BYTES:
            raise ExportJobResultInvalid("export result exceeds the 64 MiB limit")
        return content_bytes

    def _persist_artifact(self, job_id: str, result: dict) -> dict | None:
        """Write a service-owned immutable artifact and return safe metadata."""
        try:
            content = self._result_bytes(result)
        except ExportJobResultInvalid:
            return None
        try:
            self.artifact_root.mkdir(parents=True, exist_ok=True)
            filename = f"{re.sub(r'[^A-Za-z0-9_-]', '', str(job_id))[:80] or 'job'}.artifact"
            target = self.artifact_root / filename
            target.write_bytes(content)
        except OSError:
            return None
        return {
            "path": filename,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "media_type": self._media_type(result.get("media_type"), str(result.get("format") or "bin")),
            "filename": self._safe_filename(result.get("filename"), job_id, str(result.get("format") or "bin")),
            "created_at": _now(),
        }

    def _mark_cancelled_from_worker(self, job_id: str) -> None:
        with self._lock:
            jobs = self._read()
            job = jobs.get(job_id)
            if not isinstance(job, dict) or str(job.get("status", "")).lower() in {"succeeded", "failed", "cancelled"}:
                return
            job.update(
                status="cancelled",
                progress_message="已取消",
                error={"code": "EXPORT_CANCELLED", "message": "export cancelled"},
                cancel_requested=True,
                finished_at=_now(),
                updated_at=_now(),
            )
            self._write(jobs)
            self._cancel_events.pop(job_id, None)

    @staticmethod
    def _serialise_result(result):
        """Keep byte payloads JSON-safe for future binary exporters."""
        if not isinstance(result, dict):
            return result
        item = dict(result)
        content = item.get("content")
        if isinstance(content, (bytes, bytearray, memoryview)):
            raw = bytes(content)
            if len(raw) > ExportJobService.MAX_RESULT_BYTES:
                raise ValueError("export result exceeds the 64 MiB limit")
            item["content"] = base64.b64encode(raw).decode("ascii")
            item["content_encoding"] = "base64"
        elif isinstance(content, str) and len(content.encode("utf-8")) > ExportJobService.MAX_RESULT_BYTES:
            raise ValueError("export result exceeds the 64 MiB limit")
        encoded = item.get("content_base64")
        if encoded is not None:
            if not isinstance(encoded, str) or item.get("content_encoding", "base64") != "base64":
                raise ValueError("export result content encoding is invalid")
            try:
                raw_encoded = base64.b64decode(encoded, validate=True)
            except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
                raise ValueError("export result content encoding is invalid") from exc
            if len(raw_encoded) > ExportJobService.MAX_RESULT_BYTES:
                raise ValueError("export result exceeds the 64 MiB limit")
        return item

    def _run(self, job_id: str) -> None:
        with self._lock:
            jobs = self._read()
            job = jobs.get(job_id)
            if not isinstance(job, dict) or str(job.get("status") or "").lower() != "queued":
                with self._lock:
                    self._futures.pop(job_id, None)
                    self._cancel_events.pop(job_id, None)
                return
            cancel_event = self._cancel_events.setdefault(job_id, threading.Event())
            if cancel_event.is_set() or job.get("cancel_requested"):
                with self._lock:
                    self._futures.pop(job_id, None)
                    self._cancel_events.pop(job_id, None)
                return
            try:
                previous_progress = int(job.get("progress", 0) or 0)
            except (TypeError, ValueError):
                previous_progress = 0
            job.update(status="running", progress=max(5, previous_progress), progress_message="处理中", started_at=_now(), updated_at=_now())
            self._write(jobs)

        def report(progress: object, message: str | None = None):
            if cancel_event.is_set():
                raise _ExportCancelled()
            self._set_progress(job_id, progress, message)

        try:
            report(10, "准备导出")
            result = self._serialise_result(self._invoke_exporter(job, report))
            if cancel_event.is_set():
                self._mark_cancelled_from_worker(job_id)
                return
            artifact = self._persist_artifact(job_id, result)
            report(95, "整理导出结果")
            update = {"status": "succeeded", "result": result, "artifact": artifact, "error": None, "progress": 100, "progress_message": "已完成", "finished_at": _now(), "updated_at": _now()}
        except _ExportCancelled:
            self._mark_cancelled_from_worker(job_id)
            return
        except Exception as exc:
            with self._lock:
                current = self._read().get(job_id)
                if isinstance(current, dict) and (cancel_event.is_set() or str(current.get("status", "")).lower() == "cancelled"):
                    self._mark_cancelled_from_worker(job_id)
                    return
            update = {"status": "failed", "result": None, "error": {"code": "EXPORT_FAILED", "message": str(exc)}, "progress_message": "失败", "finished_at": _now(), "updated_at": _now()}
        with self._lock:
            jobs = self._read()
            job = jobs.get(job_id)
            if job:
                # A cancellation request wins a race with exporter completion;
                # never resurrect a cancelled task as succeeded.
                if str(job.get("status", "")).lower() == "cancelled" or cancel_event.is_set():
                    self._mark_cancelled_from_worker(job_id)
                else:
                    job.update(update)
                    self._write(jobs)
            self._futures.pop(job_id, None)
            self._cancel_events.pop(job_id, None)
