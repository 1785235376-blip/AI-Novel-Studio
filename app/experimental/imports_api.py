"""Authenticated, feature-gated entrypoints for semantic import V2."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .common import api_call
from ..services.import_apply_service import ImportApplyInterrupted


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportJobIn(StrictInput):
    chapter_ids: list[str] = Field(min_length=1, max_length=2000)
    chunk_size: int = Field(default=8000, ge=256, le=32000)
    overlap: int = Field(default=256, ge=0, le=1024)
    adapter_id: str = Field(default="local-semantic-rules-v2", min_length=1, max_length=120)


class VersionIn(StrictInput):
    expected_version: int = Field(ge=1)


class ProcessIn(VersionIn):
    max_chunks: int = Field(default=1, ge=1, le=100)


class ReviewIn(VersionIn):
    action: Literal["approve", "reject", "reopen"]


class ReviewEntry(ReviewIn):
    id: str = Field(min_length=1, max_length=120)


class BatchReviewIn(StrictInput):
    items: list[ReviewEntry] = Field(min_length=1, max_length=200)


class CommitIn(VersionIn):
    candidate_ids: list[str] | None = Field(default=None, max_length=1000)


def create_import_router(service, authorize, require_flag):
    router = APIRouter()
    prefix = "/novels/{nid}/experimental/imports"

    def access(nid, token, branch, permission="domain.read"):
        require_flag("semantic_import_v2")
        return authorize(nid, token, branch, permission)

    @router.get(prefix + "/jobs")
    def jobs(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        rows = api_call(service.jobs, nid, scope)
        return {"items": rows, "total": len(rows)}

    @router.post(prefix + "/jobs", status_code=201)
    def create(nid: str, body: ImportJobIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_job, nid, scope, actor, **body.model_dump())

    @router.get(prefix + "/jobs/{job_id}")
    def job(nid: str, job_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.job, nid, scope, job_id)

    @router.get(prefix + "/jobs/{job_id}/chunks")
    def chunks(nid: str, job_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        rows = api_call(service.chunks, nid, scope, job_id)
        return {"items": rows, "total": len(rows)}

    @router.post(prefix + "/jobs/{job_id}/process")
    def process(nid: str, job_id: str, body: ProcessIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")

        def check_authority():
            current_actor, current_scope = access(nid, x_session_token, x_branch_id, "domain.write")
            if current_actor != actor or current_scope != scope:
                raise HTTPException(403, {"code": "IMPORT_PROCESS_SCOPE_CHANGED"})

        return api_call(service.process, nid, scope, actor, job_id, **body.model_dump(), check_authority=check_authority)

    @router.post(prefix + "/jobs/{job_id}/review-batch")
    def batch(nid: str, job_id: str, body: BatchReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.review")
        rows = api_call(service.review_batch, nid, scope, actor, body.model_dump()["items"], job_id)
        return {"items": rows, "total": len(rows)}

    @router.post(prefix + "/jobs/{job_id}/commit")
    def commit(nid: str, job_id: str, body: CommitIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        access(nid, x_session_token, x_branch_id, "domain.review")

        def reauthorize():
            current_actor, current_scope = access(nid, x_session_token, x_branch_id, "domain.write")
            access(nid, x_session_token, x_branch_id, "domain.review")
            if current_actor != actor or current_scope != scope:
                raise HTTPException(403, {"code": "IMPORT_COMMIT_SCOPE_CHANGED"})

        try:
            return api_call(service.commit, nid, scope, actor, job_id, **body.model_dump(), reauthorize=reauthorize)
        except ImportApplyInterrupted as exc:
            raise HTTPException(409, exc.detail) from exc

    @router.post(prefix + "/jobs/{job_id}/{action}")
    def transition(nid: str, job_id: str, action: Literal["pause", "resume", "cancel", "retry", "recover"], body: VersionIn,
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.transition, nid, scope, actor, job_id, action, body.expected_version)

    @router.get(prefix + "/candidates")
    def candidates(nid: str, job_id: str | None = Query(None), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        rows = api_call(service.candidates, nid, scope, job_id)
        return {"items": rows, "total": len(rows)}

    @router.post(prefix + "/candidates/{candidate_id}/review")
    def review(nid: str, candidate_id: str, body: ReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.review")
        return api_call(service.review, nid, scope, actor, candidate_id, body.action, body.expected_version)

    return router
