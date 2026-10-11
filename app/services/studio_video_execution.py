"""Neutral video generation on the original VideoAssemblyService job owner.

There is no worker or second queue here. Explicit dispatch and refresh use the
original configured VideoProvider; an uncertain submission is never replayed.
"""
from __future__ import annotations

import base64
import copy
import hashlib
from contextlib import contextmanager
from functools import wraps
from uuid import uuid4

from ..asset_providers import VideoGenerationRequest
from ..experimental.store import canonical
from ..media_files import fetch_media_bytes, inspect_media
from ..repository import now
from ..repositories.file.mutation_coordinator import workspace_mutation


def exclusive(method):
    @wraps(method)
    def operation(self, nid, branch, actor, jid, *args, **kwargs):
        with workspace_mutation(self.owner.root, "studio-video-execution:" + jid):
            return method(self, nid, branch, actor, jid, *args, **kwargs)
    return operation


class StudioVideoExecution:
    CONTRACT = "studio-video-execution/1"

    def __init__(self, owner):
        self.owner = owner

    @contextmanager
    def review_phase(self, jid):
        # The same original executor lease serializes review/refresh/recovery;
        # it creates neither a second job nor another lock namespace.
        with workspace_mutation(self.owner.root, "studio-video-execution:" + jid):
            yield

    @staticmethod
    def _receipt(row):
        return hashlib.sha256(canonical({k: row.get(k) for k in
            ("id", "request_digest", "context", "attempt", "remote_task_id", "output_candidate", "status", "publication_ready")}).encode()).hexdigest()

    def get(self, nid, branch, actor, jid, *, context, guard):
        guard()
        row = self.owner._studio_read(nid, branch, actor, jid, context=context)
        if row.get("contract") != self.CONTRACT:
            raise FileNotFoundError(jid)
        guard()
        return row

    def create(self, nid, branch, actor, body, *, context, guard):
        guard()
        jid = hashlib.sha256(canonical([context["scope_key"], context["incarnation"], actor, context["request_id"]]).encode()).hexdigest()
        with workspace_mutation(self.owner.root, "studio-video-execution:" + jid):
            try: existing = self.owner._studio_read(nid, branch, actor, jid, context=context)
            except FileNotFoundError: existing = None
            if existing is not None:
                if existing.get("contract") != self.CONTRACT or existing["request_digest"] != context["request_digest"]:
                    raise ValueError("STUDIO_REQUEST_ID_CONFLICT")
                guard()
                return existing
            if len(self.owner.list_studio(nid, branch, actor, context=context, guard=guard)) >= 100:
                raise ValueError("STUDIO_VIDEO_JOB_LIMIT")
            return self._create(nid, branch, actor, jid, body, context, guard)

    def _create(self, nid, branch, actor, jid, body, context, guard):
        row = {"id": jid, "contract": self.CONTRACT, "type": "STUDIO_VIDEO",
            "kind": "STUDIO_VIDEO", "novel_id": nid, "branch_id": branch, "owner_actor_id": actor,
            "version": 1, "status": "QUEUED", "attempt": 0, "body": copy.deepcopy(body),
            "context": copy.deepcopy(context), "request_digest": context["request_digest"],
            "created_at": now(), "updated_at": now(), "output_candidate": None,
            "remote_task_id": None, "review_state": "HUMAN_REVIEW_REQUIRED"}
        row["receipt_digest"] = self._receipt(row)
        row = self.owner._studio_write(nid, branch, actor, row, context=context)
        guard()
        return row

    def _mutate(self, nid, branch, actor, row, context, **fields):
        def change(current):
            if current["request_digest"] != row["request_digest"] or current.get("execution_token") != row.get("execution_token") or current["status"] != row["status"]:
                raise ValueError("STUDIO_VIDEO_ATTEMPT_CHANGED")
            current.update(fields)
            current["receipt_digest"] = self._receipt(current)
        return self.owner._studio_mutate(nid, branch, actor, row["id"], row["version"], change, context=context)

    @exclusive
    def execute(self, nid, branch, actor, jid, action, *, context, guard, source_guard, resolve, before_send, publish):
        row = self.get(nid, branch, actor, jid, context=context, guard=guard)
        if row["version"] != action.expected_version or row["request_digest"] != action.expected_request_digest or row["status"] != "QUEUED":
            raise ValueError("STUDIO_VIDEO_DISPATCH_VERSION_OR_STATE_CHANGED")
        body = row["body"]
        provider = resolve(row["context"]["provider_binding"])
        if not getattr(provider, "supports_dispatch_guard", False):
            raise ValueError("STUDIO_VIDEO_LAST_MILE_AUTHORITY_UNSUPPORTED")
        operation = body["operation_id"]
        capability = {"m7.video.t2v": "text_to_video", "m7.video.i2v": "image_to_video", "m7.video.v2v": "video_to_video"}[operation]
        if not provider.capabilities().get(capability):
            raise ValueError("STUDIO_VIDEO_CAPABILITY_UNSUPPORTED")
        start_frame, video_uri = "", None
        for snapshot in row["context"]["sources"]:
            result = source_guard(snapshot)
            if snapshot["kind"] == "ASSET":
                uri = "data:" + result["measured"]["media_type"] + ";base64," + base64.b64encode(result["data"]).decode("ascii")
                if operation == "m7.video.i2v": start_frame = uri
                elif operation == "m7.video.v2v": video_uri = uri
        guard()
        row = self._mutate(nid, branch, actor, row, context, status="RUNNING", attempt=row["attempt"] + 1, execution_token=str(uuid4()))
        sent = False
        def last_mile():
            nonlocal row, sent
            guard()
            for snapshot in row["context"]["sources"]: source_guard(snapshot)
            before_send(row, provider)
            if not sent:
                row = self._mutate(nid, branch, actor, row, context, status="SEND_RESERVED", dispatch_reserved_at=now())
                sent = True
            elif self.get(nid, branch, actor, jid, context=context, guard=guard)["version"] != row["version"]:
                raise ValueError("STUDIO_VIDEO_ATTEMPT_CHANGED")
        request = VideoGenerationRequest(body["provider_id"], body["model_id"], body["prompt"],
            start_frame, "", jid, idempotency_key=row["request_digest"], parameters=body["parameters"],
            source_video_uri=video_uri, dispatch_guard=last_mile)
        try:
            result = provider.generate(request)
            if not sent or result.provider_id != body["provider_id"] or result.model_id != body["model_id"]:
                raise ValueError("STUDIO_VIDEO_PROVIDER_RESULT_BINDING_INVALID")
            guard()
            remote = str(result.remote_task_id or "")
            if len(remote) > 240 or any(ord(c) < 32 for c in remote):
                raise ValueError("STUDIO_VIDEO_REMOTE_ID_INVALID")
            if result.status in {"RUNNING", "PENDING", "QUEUED"} and remote:
                return self._mutate(nid, branch, actor, row, context, status="REMOTE_RUNNING", remote_task_id=remote, execution_token=None)
            if result.status != "SUCCEEDED" or not result.video_uri:
                raise ValueError("STUDIO_VIDEO_RESULT_NOT_COMPLETE")
            if not result.video_uri.startswith("data:"):
                if len(result.video_uri) > 4000: raise ValueError("STUDIO_VIDEO_RESULT_URL_LIMIT")
                row = self._mutate(nid, branch, actor, row, context, status="RESULT_READY", result_uri=result.video_uri,
                    remote_task_id=remote or None)
            elif remote:
                row = self._mutate(nid, branch, actor, row, context, remote_task_id=remote)
            before_send(row, provider)
            return self._complete(nid, branch, actor, row, context, result.video_uri, provider, guard, source_guard, publish, remote or None,
                lambda: before_send(row, provider))
        except Exception:
            # Keep a known remote task or private asset if a later local commit
            # fails. The original receipt remains available for explicit reads.
            current = self.get(nid, branch, actor, jid, context=context, guard=lambda: None)
            if current["status"] in {"RUNNING", "SEND_RESERVED"}:
                self._mutate(nid, branch, actor, current, context, status="UNKNOWN" if sent else "FAILED", execution_token=None,
                    error_code="STUDIO_VIDEO_SUBMISSION_UNKNOWN" if sent else "STUDIO_VIDEO_PREPARATION_FAILED")
            raise

    def _complete(self, nid, branch, actor, row, context, uri, provider, guard, source_guard, publish, remote, route_guard):
        guard(); route_guard()
        if uri.startswith("data:video/"):
            if len(uri) > 36 * 1024 * 1024 or ";base64," not in uri:
                raise ValueError("STUDIO_VIDEO_RESULT_SIZE_INVALID")
            data = base64.b64decode(uri.split(";base64,", 1)[1], validate=True)
        else:
            data = fetch_media_bytes(uri, self.owner.assets.MAX_BYTES, configured_provider_endpoint=provider.endpoint)
        if not data or len(data) > self.owner.assets.MAX_BYTES:
            raise ValueError("STUDIO_VIDEO_RESULT_SIZE_INVALID")
        measured = inspect_media(data, "video")
        if measured["duration_ms"] > 600000:
            raise ValueError("STUDIO_VIDEO_DURATION_LIMIT")
        for snapshot in row["context"]["sources"]: source_guard(snapshot)
        guard(); route_guard()
        current = self.get(nid, branch, actor, row["id"], context=context, guard=guard)
        if current["version"] != row["version"] or current["status"] != row["status"]:
            raise ValueError("STUDIO_VIDEO_ATTEMPT_CHANGED")
        # Durable proof before the asset write permits explicit recovery of
        # the same private bytes after process interruption, never another send.
        row = self._mutate(nid, branch, actor, row, context, publication_ready={"kind": "video",
            "output_digest": hashlib.sha256(data).hexdigest(), "output_bytes": len(data), "media_type": measured["media_type"]})
        def job_current():
            current = self.owner._studio_read(nid, branch, actor, row["id"], context=context)
            if current["version"] != row["version"] or current["status"] != row["status"]:
                raise ValueError("STUDIO_VIDEO_ATTEMPT_CHANGED")
        candidate = publish(data, "video", "studio-video." + measured.get("extension", "mp4"), measured, row["id"], job_current)
        origin = candidate.get("_studio_result_origin", {})
        expected_origin = {"contract": "studio-production-result/1", "job_id": row["id"],
            **{k: row["context"][k] for k in ("actor", "scope_key", "incarnation", "request_digest", "operation_id", "sources")},
            "provider_id": row["body"]["provider_id"], "model_id": row["body"]["model_id"],
            "license_note": row["context"].get("license_note", "")}
        if "graph_binding" in row["context"]:
            from ..creative.graph_media_binding import validate_graph_binding
            graph_binding = validate_graph_binding(row["context"]["graph_binding"], row["context"])
            if graph_binding is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
            expected_origin["graph_binding"] = copy.deepcopy(graph_binding)
        expected_binding = {"novel_id": nid, "branch_id": branch,
            "scope_key": row["context"]["scope_key"], "incarnation": row["context"]["incarnation"]}
        if (candidate.get("kind") != "video" or candidate.get("sha256") != hashlib.sha256(data).hexdigest()
                or candidate.get("_owner_actor_id") != actor or candidate.get("source_job_id") != row["id"]
                or candidate.get("_required_features") != ["narrative_production_v2"]
                or candidate.get("_project_binding") != expected_binding or origin != expected_origin
                or candidate.get("size") != len(data) or candidate.get("media_type") != measured["media_type"]):
            raise ValueError("STUDIO_VIDEO_CANDIDATE_RECEIPT_INVALID")
        return self._mutate(nid, branch, actor, row, context, status="AWAITING_REVIEW", execution_token=None,
            remote_task_id=remote, output_candidate={"id": candidate["id"], "version": candidate["version"], "digest": candidate["sha256"], "kind": "video"})

    @exclusive
    def refresh(self, nid, branch, actor, jid, action, *, context, guard, source_guard, resolve, publish):
        row = self.get(nid, branch, actor, jid, context=context, guard=guard)
        if row["version"] != action.expected_version or row["request_digest"] != action.expected_request_digest or row["status"] not in {"REMOTE_RUNNING", "RESULT_READY", "UNKNOWN"}:
            raise ValueError("STUDIO_VIDEO_REFRESH_STATE_CHANGED")
        provider = resolve(row["context"]["provider_binding"])
        def route_guard():
            guard()
            if resolve(row["context"]["provider_binding"]) is not provider:
                raise ValueError("STUDIO_VIDEO_PROVIDER_CHANGED")
        for snapshot in row["context"]["sources"]: source_guard(snapshot)
        guard()
        if row["status"] == "RESULT_READY" and row.get("result_uri"):
            return self._complete(nid, branch, actor, row, context, row["result_uri"], provider, guard, source_guard, publish, row.get("remote_task_id"), route_guard)
        if not row.get("remote_task_id") or not provider.capabilities().get("polling") or not callable(getattr(provider, "get_status", None)):
            raise ValueError("STUDIO_VIDEO_REFRESH_UNSUPPORTED")
        route_guard()
        result = provider.get_status(row["remote_task_id"])
        guard(); route_guard()
        status = str(result.get("status", "UNKNOWN")).upper()
        if status in {"SUCCEEDED", "COMPLETE", "COMPLETED"} and result.get("url"):
            return self._complete(nid, branch, actor, row, context, result["url"], provider, guard, source_guard, publish, row["remote_task_id"], route_guard)
        if status in {"FAILED", "CANCELLED"}:
            return self._mutate(nid, branch, actor, row, context, status=status, error_code="STUDIO_VIDEO_REMOTE_TERMINAL")
        if status not in {"RUNNING", "PENDING", "QUEUED", "IN_PROGRESS"}:
            return self._mutate(nid, branch, actor, row, context, status="UNKNOWN", error_code="STUDIO_VIDEO_REMOTE_STATE_UNKNOWN")
        return row

    @exclusive
    def cancel(self, nid, branch, actor, jid, action, *, context, guard):
        row = self.get(nid, branch, actor, jid, context=context, guard=guard)
        if row["version"] != action.expected_version or row["request_digest"] != action.expected_request_digest:
            raise ValueError("STUDIO_VIDEO_CANCEL_VERSION_CHANGED")
        if row["status"] not in {"QUEUED", "REMOTE_RUNNING", "RESULT_READY", "UNKNOWN", "AWAITING_REVIEW"}:
            raise ValueError("STUDIO_VIDEO_CANCEL_STATE_INVALID")
        # This explicitly discards local publication authority. A provider may
        # continue remotely; cancellation of remote compute is not asserted.
        return self._mutate(nid, branch, actor, row, context, status="CANCELLED", cancellation_mode="LOCAL_RESULT_DISCARD", execution_token=None)

    @exclusive
    def reconcile(self, nid, branch, actor, jid, action, *, context, guard, recover_candidate=None, recover_review=None):
        # Obtaining the original per-job lease proves no new execution of this
        # job is still in progress. This reconciles local state, never submits.
        row = self.get(nid, branch, actor, jid, context=context, guard=guard)
        if row["version"] != action.expected_version or row["request_digest"] != action.expected_request_digest:
            raise ValueError("STUDIO_VIDEO_RECONCILE_VERSION_CHANGED")
        if row["status"] not in {"RUNNING", "SEND_RESERVED", "UNKNOWN", "RESULT_READY", "REVIEWING"}:
            raise ValueError("STUDIO_VIDEO_RECONCILE_STATE_INVALID")
        if row["status"] == "REVIEWING":
            # An explicit stopped-review recovery only clears an exact private
            # reservation. It never reauthorizes stale sources or promotes a
            # candidate, and durable/ambiguous promotion stays REVIEWING.
            candidate = copy.deepcopy(row.get("output_candidate"))
            recovered = None
            def compensate():
                nonlocal recovered
                def change(current):
                    if (current["status"] != "REVIEWING" or current["request_digest"] != row["request_digest"]
                            or current.get("output_candidate") != candidate or current["context"] != row["context"]
                            or current.get("receipt_digest") != row.get("receipt_digest")):
                        raise ValueError("STUDIO_VIDEO_REVIEW_RECOVERY_CHANGED")
                    current.update(status="AWAITING_REVIEW", review_state="HUMAN_REVIEW_REQUIRED",
                        error_code="STUDIO_VIDEO_REVIEW_NOT_PROMOTED", recovery_state="EXACT_PRIVATE_REVIEW_RECOVERED_NO_REPLAY")
                recovered = self.owner._studio_mutate(nid, branch, actor, jid, row["version"], change, context=context)
            if candidate is not None and callable(recover_review):
                recover_review(candidate, compensate)
            guard()
            return recovered if recovered is not None else row
        if row.get("publication_ready") and callable(recover_candidate):
            try:
                candidate = recover_candidate(copy.deepcopy(row))
                guard()
            except Exception:
                guard()
                candidate = None
            if candidate is not None:
                return self._mutate(nid, branch, actor, row, context, status="AWAITING_REVIEW", execution_token=None,
                    output_candidate={"id": candidate["id"], "version": candidate["version"], "digest": candidate["sha256"], "kind": "video"},
                    error_code=None, recovery_state="EXACT_PRIVATE_PUBLICATION_RECOVERED_NO_REPLAY")
        if row["status"] in {"UNKNOWN", "RESULT_READY"}:
            guard()
            return row
        return self._mutate(nid, branch, actor, row, context, status="UNKNOWN", execution_token=None,
            error_code="STUDIO_VIDEO_INTERRUPTED_NO_AUTOMATIC_REPLAY")
