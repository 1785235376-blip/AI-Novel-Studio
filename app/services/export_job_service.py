from __future__ import annotations

import base64
import binascii
import hashlib
import json
import inspect
import os
import stat
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import contextmanager
from copy import deepcopy

from ..repositories.file.mutation_coordinator import workspace_mutation

from ..industry_export_formats import IndustryExportError
from ..pdf_export import PDFExportError
from ..storage import atomic_write
from .export_execution_claim import try_execution_claim


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

    SUPPORTED = {"json", "txt", "text", "markdown", "md", "docx", "word", "pdf", "epub", "screenplay", "shot-list", "storyboard", "screenplay-fountain", "screenplay-standard", "screenplay-docx"}
    SUPPORTED |= {"screenplay-package", "shot-list-package", "storyboard-package"}
    STATUSES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
    MEDIA_TYPES = {
        "json": "application/json",
        "txt": "text/plain",
        "markdown": "text/markdown",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "epub": "application/epub+zip",
        "screenplay": "text/markdown",
        "screenplay-fountain": "text/x-fountain",
        "screenplay-docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "shot-list": "text/csv",
        "storyboard": "text/markdown",
        "screenplay-package": "application/zip",
        "shot-list-package": "application/zip",
        "storyboard-package": "application/zip",
    }
    EXTENSIONS = {
        "json": "json",
        "txt": "txt",
        "markdown": "md",
        "docx": "docx",
        "pdf": "pdf",
        "epub": "epub",
        "screenplay": "md",
        "screenplay-fountain": "fountain",
        "screenplay-docx": "docx",
        "shot-list": "csv",
        "storyboard": "md",
        "screenplay-package": "zip",
        "shot-list-package": "zip",
        "storyboard-package": "zip",
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

    _LIFECYCLE = "_export_lifecycle_v1"

    @contextmanager
    def _mutation(self):
        # The original queue owns serialization, including its existing workers.
        # This is the shared File coordinator, not a TaskCenter/query authority.
        with workspace_mutation(self.path.parent, "export-jobs"), self._lock:
            yield

    @staticmethod
    def _nonce(value):
        try:
            return isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).version == 4
        except (ValueError, TypeError, AttributeError):
            return False

    def _validate_lifecycle(self, document):
        if self._LIFECYCLE not in document:
            return
        meta = document[self._LIFECYCLE]
        rows = {k for k in document if k != self._LIFECYCLE}
        if (not isinstance(meta, dict) or set(meta) != {"schema_version", "incarnation", "rows"}
                or type(meta["schema_version"]) is not int or meta["schema_version"] != 1
                or not self._nonce(meta["incarnation"]) or not isinstance(meta["rows"], dict)
                or set(meta["rows"]) != rows or not all(self._nonce(v) for v in meta["rows"].values())):
            raise ValueError("EXPORT_BINDING_UNSUPPORTED")

    def _read_document(self) -> dict:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate export key")
                result[key] = value
            return result
        from ..creative.asset_usage_budget import current_usage_budget
        budget = current_usage_budget()
        try:
            value = json.loads(budget.read(self.path) if budget is not None
                               else self.path.read_text(encoding="utf-8"), object_pairs_hook=unique)
            if not isinstance(value, dict):
                return {}
            self._validate_lifecycle(value)
            return value
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _read(self) -> dict:
        # Existing consumers retain the exact top-level job-map contract.
        return {k: v for k, v in self._read_document().items() if k != self._LIFECYCLE}

    def binding_observation(self, job_ids):
        """Private selected committed-row evidence, never an authorization grant.

        No migration or provisioning occurs here. A caller still needs the
        original actor/scope/per-record authorization and public projection.
        """
        if (type(job_ids) not in (list, tuple) or not 1 <= len(job_ids) <= 200
                or any(type(jid) is not str or not jid or jid == self._LIFECYCLE for jid in job_ids)
                or len(set(job_ids)) != len(job_ids)):
            raise ValueError("EXPORT_BINDING_UNSUPPORTED")
        # atomic_write gives a single committed document; a read needs no
        # writable coordinator directory or new lockfile.
        with self._lock:
            document = self._read_document()
            meta = document.get(self._LIFECYCLE)
            if not isinstance(meta, dict) or any(not isinstance(document.get(jid), dict) for jid in job_ids):
                raise ValueError("EXPORT_BINDING_UNSUPPORTED")
            return {"document_incarnation": meta["incarnation"],
                    "rows": {jid: meta["rows"][jid] for jid in job_ids}}

    def revalidate_binding(self, job_ids, observation):
        return self.binding_observation(job_ids) == observation

    @classmethod
    def _is_idempotency_fresh(cls, item: dict) -> bool:
        try:
            created = datetime.fromisoformat(str(item.get("created_at", "")))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - created <= cls.IDEMPOTENCY_TTL
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _committed_row(row):
        # Match the original JSON serializer's coercions (for example numeric
        # object keys and tuples), then compare the committed JSON semantics.
        return json.dumps(json.loads(json.dumps(row, ensure_ascii=False)),
                          sort_keys=True, separators=(",", ":"))

    def _write(self, value: dict) -> None:
        if not isinstance(value, dict) or self._LIFECYCLE in value:
            raise ValueError("export lifecycle metadata is owner-managed")
        with self._mutation():
            fresh = not self.path.exists()
            before = self._read_document()
            old = before.get(self._LIFECYCLE)
            result = deepcopy(value)
            # Existing legacy/corrupt documents remain unbound on ordinary writes.
            if old is not None or fresh:
                meta = deepcopy(old) if old is not None else {
                    "schema_version": 1, "incarnation": str(uuid.uuid4()), "rows": {}}
                meta["rows"] = {jid: (meta["rows"][jid] if jid in before and self._committed_row(before[jid])
                                      == self._committed_row(row)
                                      else str(uuid.uuid4())) for jid, row in value.items()}
                result[self._LIFECYCLE] = meta
                self._validate_lifecycle(result)
            atomic_write(self.path, json.dumps(result, ensure_ascii=False, indent=2))

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
        """Recover only candidates for which no current executor holds a claim."""
        candidates = [str(jid) for jid, raw in self._read().items()
                      if isinstance(raw, dict) and str(raw.get("status") or "").lower() in {"queued", "running"}]
        for job_id in candidates:
            self._submit(job_id, recovery=True)

    def _prepare_recovery(self, job_id: str) -> bool:
        # Caller owns the per-job execution claim. Re-read under the original
        # short writer coordinator; no whole-queue lock spans exporter work.
        with self._mutation():
            jobs = self._read()
            raw = jobs.get(job_id)
            if not isinstance(raw, dict) or str(raw.get("status") or "").lower() not in {"queued", "running"}:
                return False
            if raw.get("cancel_requested"):
                raw.update(status="cancelled", progress_message="已取消",
                           error={"code": "EXPORT_CANCELLED", "message": "export cancelled"},
                           finished_at=_now(), updated_at=_now())
            else:
                try:
                    previous_progress = int(raw.get("progress", 0) or 0)
                except (TypeError, ValueError):
                    previous_progress = 0
                try:
                    previous_recoveries = int(raw.get("recovery_count", 0) or 0)
                except (TypeError, ValueError):
                    previous_recoveries = 0
                raw.update(status="queued", progress=max(0, min(5, previous_progress)),
                           progress_message="等待恢复", recovery_count=previous_recoveries + 1,
                           recovered_at=_now(), updated_at=_now())
            self._write(jobs)
            return raw["status"] == "queued"

    def _submit(self, job_id: str, *, recovery=False, preserve_queued_on_pool_failure=False) -> None:
        claim = try_execution_claim(self.path.parent, job_id)
        if claim is None:
            return
        submitted = False
        try:
            if recovery and not self._prepare_recovery(job_id):
                return
            if preserve_queued_on_pool_failure:
                # The original creator may have finished or cancelled after
                # the idempotency snapshot, before this claim was acquired.
                with self._mutation():
                    current = self._read().get(job_id)
                    if not isinstance(current, dict) or str(current.get("status") or "").lower() != "queued":
                        return
            try:
                future = self._pool.submit(self._run, job_id, claim)
            except RuntimeError as exc:
                if preserve_queued_on_pool_failure:
                    # Another creator may still be about to acquire the claim.
                    # A retry's closed pool has no authority to fail its row.
                    raise RuntimeError("EXPORT_QUEUE_UNAVAILABLE") from exc
                # We still own this job: a failed local executor cannot poison
                # another process's queued/running task.
                with self._mutation():
                    jobs = self._read()
                    job = jobs.get(job_id)
                    if isinstance(job, dict) and str(job.get("status", "")).lower() == "queued":
                        job.update(status="failed", progress_message="队列不可用",
                                   error={"code": "EXPORT_QUEUE_UNAVAILABLE", "message": str(exc)},
                                   finished_at=_now(), updated_at=_now())
                        self._write(jobs)
                return
            submitted = True
            # A cancelled queued Future never enters _run; its done callback
            # must release the exact claim. release() is idempotent.
            future.add_done_callback(lambda _future: claim.release())
            with self._mutation():
                if future.done():
                    self._futures.pop(job_id, None)
                else:
                    self._futures[job_id] = future
        finally:
            if not submitted:
                claim.release()

    @staticmethod
    def _canonical_format(value: object) -> str:
        fmt = str(value or "json").lower().strip()
        return {"md": "markdown", "text": "txt", "word": "docx",
                "screenplay-standard": "screenplay-fountain"}.get(fmt, fmt)

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
        fmt = self._canonical_format(fmt)
        existing = None
        with self._mutation():
            jobs = self._read()
            if idempotency_key:
                for item in jobs.values():
                    if isinstance(item, dict) and item.get("novel_id") == novel_id and item.get("idempotency_key") == idempotency_key and item.get("permission_context") == permission_context and self._is_idempotency_fresh(item):
                        if self._canonical_format(item.get("format")) != fmt:
                            raise ValueError("EXPORT_IDEMPOTENCY_FORMAT_CONFLICT")
                        existing = self._normalise_job(item)
                        break
            if existing is None:
                attempt = 1
                if retry_of:
                    source = jobs.get(retry_of)
                    if isinstance(source, dict):
                        try:
                            attempt = max(1, int(source.get("attempt", 1) or 1) + 1)
                        except (TypeError, ValueError):
                            attempt = 2
                snapshot = self._capture_snapshot(novel_id, fmt, permission_context=permission_context)
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
        if existing is not None:
            # A prior attempt may have persisted the queue row before claim
            # acquisition failed. A live executor retains its nonblocking claim;
            # terminal/running rows are never replayed by an idempotent create.
            if existing["status"] == "queued":
                self._submit(existing["id"], preserve_queued_on_pool_failure=True)
                return self.get(existing["id"])
            return existing
        self._submit(job["id"])
        return self._normalise_job(job)

    def _capture_snapshot(self, novel_id: str, format: str, *, permission_context: dict | None = None):
        """Call an optional snapshot provider while preserving old adapters."""
        if self.snapshotter is None:
            return None
        try:
            parameters = inspect.signature(self.snapshotter).parameters
        except (TypeError, ValueError):
            parameters = {}
        kwargs = {}
        accepts_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())
        if "permission_context" in parameters or accepts_kwargs:
            kwargs["permission_context"] = permission_context
        if "format" in parameters or accepts_kwargs:
            snapshot = self.snapshotter(novel_id, format=format, **kwargs)
        elif len(parameters) >= 2:
            snapshot = self.snapshotter(novel_id, format, **kwargs)
        else:
            snapshot = self.snapshotter(novel_id, **kwargs)
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

    @staticmethod
    def public(job: dict) -> dict:
        """Lifecycle/provenance only; snapshots and binary bodies stay local."""
        item = {key: value for key, value in job.items() if key not in {"snapshot", "idempotency_key", "artifact"}}
        snapshot = job.get("snapshot")
        if isinstance(snapshot, dict):
            item["source_versions"] = snapshot.get("source_versions", {})
            item["captured_at"] = snapshot.get("captured_at")
        result = item.get("result")
        if isinstance(result, dict):
            item["result"] = {key: value for key, value in result.items() if key not in {"content", "content_base64"}}
        return item

    @classmethod
    def _scope_rows(cls, jobs, novel_id, permission_context, status=None):
        """The original exact-context filter, shared by list and observation."""
        keys = ("mode", "novel_id", "workspace_id", "storyline_id", "branch_id", "actor_id")
        rows = []
        for raw in jobs.values():
            if not isinstance(raw, dict) or raw.get("novel_id") != novel_id:
                continue
            context = raw.get("permission_context")
            if not isinstance(context, dict) or any(context.get(key) != permission_context.get(key) for key in keys):
                continue
            if status and raw.get("status") != status:
                continue
            rows.append(cls._normalise_job(raw))
        return rows

    def local_task_observation(self, novel_id):
        """Atomic original local 100-row window; not a permission grant.

        There is deliberately no collaboration shortcut here: those records
        still require their independent original per-record authorization.
        """
        if type(novel_id) is not str or not novel_id:
            raise ValueError("EXPORT_BINDING_UNSUPPORTED")
        with self._lock:
            document = self._read_document()
            meta = document.get(self._LIFECYCLE)
            if not isinstance(meta, dict):
                raise ValueError("EXPORT_BINDING_UNSUPPORTED")
            jobs = {key: value for key, value in document.items() if key != self._LIFECYCLE}
            rows = self._scope_rows(jobs, novel_id, {"mode": "local", "novel_id": novel_id})
            rows.sort(key=lambda row: (str(row.get("created_at", "")), str(row.get("id", ""))), reverse=True)
            selected = rows[:100]
            ids = [row.get("id") for row in selected]
            if (any(type(jid) is not str or not jid or jid not in jobs for jid in ids)
                    or len(set(ids)) != len(ids)
                    or any(self._committed_row(self._normalise_job(jobs[jid])) != self._committed_row(row)
                           for jid, row in zip(ids, selected))):
                raise ValueError("EXPORT_BINDING_UNSUPPORTED")
            return {"rows": [self.public(row) for row in selected],
                    "row_lifecycles": {jid: meta["rows"][jid] for jid in ids},
                    "document_incarnation": meta["incarnation"], "source_more": len(rows) > 100}

    def list(self, novel_id: str, *, permission_context: dict, status: str | None = None,
             limit: int = 50, offset: int = 0, authorize=None) -> dict:
        """Exact owner/scope history, with no secret session identifier saved."""
        if status is not None and status not in self.STATUSES:
            raise ValueError("invalid export status filter")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("invalid export history page")
        with self._lock:
            rows = self._scope_rows(self._read(), novel_id, permission_context, status)
        # Source ownership can be stricter than a historical permission label.
        # Filter before pagination so denied records contribute no count/hint.
        if authorize is not None:
            rows = [row for row in rows if authorize(row)]
        rows.sort(key=lambda row: (str(row.get("created_at", "")), str(row.get("id", ""))), reverse=True)
        page = rows[offset:offset + limit]
        return {"items": [self.public(row) for row in page], "next_offset": offset + limit if len(rows) > offset + limit else None}

    def _set_progress(self, job_id: str, progress: object, message: str | None = None) -> bool:
        try:
            value = int(float(progress))
        except (TypeError, ValueError):
            return False
        value = max(0, min(100, value))
        with self._mutation():
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
        with self._mutation():
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
                content_bytes = self._read_artifact_file(target)
            except FileNotFoundError:
                content_bytes = None
            except OSError:
                raise ExportJobResultInvalid("export artifact is unavailable") from None
        if content_bytes is None:
            content_bytes = self._result_bytes(result)
        if isinstance(artifact, dict) and artifact.get("path"):
            # A recovered inline copy remains bound to its original receipt.
            # Legacy jobs without artifact receipts retain their inline contract.
            expected_hash = str(artifact.get("sha256") or "")
            if expected_hash and hashlib.sha256(content_bytes).hexdigest() != expected_hash:
                raise ExportJobResultInvalid("export artifact checksum mismatch")
            if artifact.get("size") is not None and artifact["size"] != len(content_bytes):
                raise ExportJobResultInvalid("export artifact size mismatch")

        format = str(job.get("format") or result.get("format") or "bin").lower().strip()
        format = "markdown" if format == "md" else ("txt" if format == "text" else ("docx" if format == "word" else format))
        return {
            "content": content_bytes,
            "filename": self._safe_filename(result.get("filename"), job_id, format),
            "media_type": self._media_type(result.get("media_type"), format),
            "format": format,
        }

    def _read_artifact_file(self, target: Path) -> bytes:
        """Read bounded regular bytes; prevent blocking POSIX FIFO swaps.

        This is not a general ancestor-path or cross-platform security boundary.
        """
        planned = target.stat()
        if not stat.S_ISREG(planned.st_mode):
            raise ExportJobResultInvalid("export artifact is not a regular file")
        if planned.st_size > self.MAX_RESULT_BYTES:
            raise ExportJobResultInvalid("export artifact exceeds the 64 MiB limit")
        if os.name == "posix" and not getattr(os, "O_NONBLOCK", 0):
            raise ExportJobResultInvalid("export artifact nonblocking read is unavailable")
        flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0)
                 | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(target, flags)
        try:
            opened = os.fstat(descriptor)
            if (not stat.S_ISREG(opened.st_mode)
                    or (opened.st_dev, opened.st_ino) != (planned.st_dev, planned.st_ino)):
                raise ExportJobResultInvalid("export artifact file changed")
            if opened.st_size > self.MAX_RESULT_BYTES:
                raise ExportJobResultInvalid("export artifact exceeds the 64 MiB limit")
            stream = os.fdopen(descriptor, "rb")
            descriptor = None  # The stream owns the descriptor after fdopen.
            with stream:
                content = stream.read(self.MAX_RESULT_BYTES + 1)
            if len(content) > self.MAX_RESULT_BYTES:
                raise ExportJobResultInvalid("export artifact exceeds the 64 MiB limit")
            return content
        finally:
            if descriptor is not None:
                os.close(descriptor)

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
        # The signature decides compatibility before invocation. A renderer's
        # TypeError is a real failure; retrying without snapshot could silently
        # export subsequently edited live data instead of the captured body.
        return self.exporter(job["novel_id"], job["format"], **kwargs)

    @staticmethod
    def _result_bytes(result: dict) -> bytes:
        """Decode a bounded exporter payload for artifact persistence/download."""
        if not isinstance(result, dict):
            raise ExportJobResultInvalid("export result is missing")
        encoded = result.get("content_base64")
        if encoded is not None:
            if not isinstance(encoded, str) or result.get("content_encoding", "base64") != "base64":
                raise ExportJobResultInvalid("export result encoding is invalid")
            if len(encoded) > ((ExportJobService.MAX_RESULT_BYTES + 2) // 3) * 4:
                raise ExportJobResultInvalid("export result exceeds the 64 MiB limit")
            try:
                content_bytes = base64.b64decode(encoded.encode("ascii"), validate=True)
            except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
                raise ExportJobResultInvalid("export result content is invalid") from exc
        else:
            content = result.get("content")
            if result.get("content_encoding") == "base64" and isinstance(content, str):
                if len(content) > ((ExportJobService.MAX_RESULT_BYTES + 2) // 3) * 4:
                    raise ExportJobResultInvalid("export result exceeds the 64 MiB limit")
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
        with self._mutation():
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
        elif isinstance(content, str):
            if item.get("content_encoding") == "base64":
                # The limit describes decoded artifact bytes, regardless of
                # which supported binary representation the exporter uses.
                try:
                    ExportJobService._result_bytes({"content": content, "content_encoding": "base64"})
                except ExportJobResultInvalid as exc:
                    raise ValueError(str(exc)) from exc
            elif len(content.encode("utf-8")) > ExportJobService.MAX_RESULT_BYTES:
                raise ValueError("export result exceeds the 64 MiB limit")
        encoded = item.get("content_base64")
        if encoded is not None:
            if not isinstance(encoded, str) or item.get("content_encoding", "base64") != "base64":
                raise ValueError("export result content encoding is invalid")
            if len(encoded) > ((ExportJobService.MAX_RESULT_BYTES + 2) // 3) * 4:
                raise ValueError("export result exceeds the 64 MiB limit")
            try:
                raw_encoded = base64.b64decode(encoded, validate=True)
            except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
                raise ValueError("export result content encoding is invalid") from exc
            if len(raw_encoded) > ExportJobService.MAX_RESULT_BYTES:
                raise ValueError("export result exceeds the 64 MiB limit")
        return item

    def _run(self, job_id: str, claim=None) -> None:
        # _submit transfers a live claim. Direct internal execution also claims
        # before reading or changing a queued job.
        claim = claim if claim is not None else try_execution_claim(self.path.parent, job_id)
        if claim is None:
            return
        try:
            self._run_owned(job_id)
        finally:
            # Every terminal path, including cooperative cancellation or an
            # unexpected worker error, releases only this instance's state.
            with self._lock:
                self._futures.pop(job_id, None)
                self._cancel_events.pop(job_id, None)
            claim.release()

    def _run_owned(self, job_id: str) -> None:
        with self._mutation():
            jobs = self._read()
            job = jobs.get(job_id)
            if not isinstance(job, dict) or str(job.get("status") or "").lower() != "queued":
                with self._mutation():
                    self._futures.pop(job_id, None)
                    self._cancel_events.pop(job_id, None)
                return
            cancel_event = self._cancel_events.setdefault(job_id, threading.Event())
            if cancel_event.is_set() or job.get("cancel_requested"):
                with self._mutation():
                    self._futures.pop(job_id, None)
                    self._cancel_events.pop(job_id, None)
                return
            try:
                previous_progress = int(job.get("progress", 0) or 0)
            except (TypeError, ValueError):
                previous_progress = 0
            job.update(status="running", progress=max(5, previous_progress), progress_message="处理中", started_at=_now(), updated_at=_now())
            self._write(jobs)

        def check_cancelled():
            if cancel_event.is_set():
                raise _ExportCancelled()
            # Another same-host service/process can cancel this durable job
            # without sharing the execution owner's in-memory Event.
            with self._lock:
                current = self._read().get(job_id)
            if isinstance(current, dict) and (current.get("cancel_requested")
                    or str(current.get("status", "")).lower() == "cancelled"):
                cancel_event.set()
                raise _ExportCancelled()

        def report(progress: object, message: str | None = None):
            check_cancelled()
            self._set_progress(job_id, progress, message)

        try:
            report(10, "准备导出")
            result = self._serialise_result(self._invoke_exporter(job, report))
            # Never publish a success state for a renderer with no usable file.
            self._result_bytes(result)
            check_cancelled()
            artifact = self._persist_artifact(job_id, result)
            report(95, "整理导出结果")
            update = {"status": "succeeded", "result": result, "artifact": artifact, "error": None, "progress": 100, "progress_message": "已完成", "finished_at": _now(), "updated_at": _now()}
        except _ExportCancelled:
            self._mark_cancelled_from_worker(job_id)
            return
        except Exception as exc:
            with self._mutation():
                current = self._read().get(job_id)
                if isinstance(current, dict) and (cancel_event.is_set() or str(current.get("status", "")).lower() == "cancelled"):
                    self._mark_cancelled_from_worker(job_id)
                    return
            error = {"code": "EXPORT_FAILED", "message": str(exc)}
            if isinstance(exc, (IndustryExportError, PDFExportError)):
                error.update(code=exc.code, details=exc.details)
            update = {"status": "failed", "result": None, "error": error, "progress_message": "失败", "finished_at": _now(), "updated_at": _now()}
        with self._mutation():
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
