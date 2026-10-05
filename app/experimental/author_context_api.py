"""Version/digest-bound preview of the real author request, never a second context."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal
import hashlib
import json

from ..author_request import request_digest, request_payload, saved_source_matches
from ..model_runtime import ModelRuntimeError
from ..router import Route
from ..runtime import runtime

FEATURE = "author_context_inspector_v2"


class AuthorPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    novel_id: str = Field(min_length=1, max_length=240)
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)
    operation: Literal["continue", "rewrite", "polish", "brainstorm", "review"]
    instruction: str = Field(default="", max_length=20000)
    profile: Literal["LOCAL_ONLY", "HYBRID", "QUALITY"] = "LOCAL_ONLY"
    provider_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    source: str = Field(default="", max_length=200000)
    selected_text: str = Field(default="", max_length=200000)
    style: str = Field(default="", max_length=120)
    style_profile_id: str | None = Field(default=None, max_length=240)
    plot_plan_id: str | None = Field(default=None, max_length=240)
    preview_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    generation_request_id: str | None = Field(default=None, min_length=1, max_length=160)


def create_author_context_router(manager, authorize, require_flag, generation_context, generation_payload):
    router = APIRouter(prefix="/novels/{nid}/experimental/author-context", tags=["Experimental author context"])

    def prepare(nid, body, token, branch, permission):
        from ..api import GenerateIn
        require_flag(FEATURE)
        authorization = authorize(nid, token, branch, permission)
        if body.novel_id != nid: raise HTTPException(404, {"code": "CHAPTER_OUTSIDE_PROJECT"})
        source = body.source or body.selected_text
        if body.source and body.selected_text and body.source != body.selected_text:
            raise HTTPException(422, {"code": "AUTHOR_SELECTION_MISMATCH"})
        if body.operation == "rewrite" and not source:
            raise HTTPException(422, {"code": "AUTHOR_SELECTION_REQUIRED"})
        try:
            value = GenerateIn.model_validate({**body.model_dump(exclude={"operation", "chapter_version", "preview_digest", "generation_request_id"}), "source": source, "selected_text": source})
        except ValidationError:
            raise HTTPException(422, {"code": "AUTHOR_PREVIEW_INPUT_INVALID"}) from None
        actor, scope = generation_context(value, token, branch)
        payload = generation_payload(value, token, branch)
        job = manager.prepare_job(body.operation, payload, actor, scope)
        if job.base_chapter_version != body.chapter_version:
            raise HTTPException(409, {"code": "AUTHOR_CHAPTER_CHANGED"})
        chapter = manager.chapters.get(job.chapter_id)
        if source and not saved_source_matches(chapter, source):
            raise HTTPException(409, {"code": "AUTHOR_SELECTION_NOT_SAVED"})
        route = Route(body.provider_id, body.model_id)
        try:
            _, _, request = manager.prepare_author_request(job, route)
        except (ModelRuntimeError, ValueError):
            raise HTTPException(409, {"code": "AUTHOR_CONTEXT_OR_PRIVACY_BLOCKED"}) from None
        if authorize(nid, token, branch, permission) != authorization:
            raise HTTPException(409, {"code": "AUTHOR_SCOPE_CHANGED"})
        return value, payload, job, request, authorization, actor, scope

    async def read_body(request):
        require_flag(FEATURE)
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 2 * 1024 * 1024:
                raise HTTPException(413, {"code": "AUTHOR_PREVIEW_INPUT_TOO_LARGE"})
        try:
            return AuthorPreviewInput.model_validate_json(bytes(raw))
        except (ValidationError, ValueError):
            raise HTTPException(422, {"code": "AUTHOR_PREVIEW_INPUT_INVALID"}) from None

    @router.post("/preview")
    async def preview(nid: str, request: Request, response: Response,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        body = await read_body(request)
        _, _, job, request, _, _, _ = prepare(nid, body, x_session_token, x_branch_id, "domain.read")
        response.headers["Cache-Control"] = "no-store"
        payload = request_payload(request)
        context = payload["context"]
        return {"contract": "AUTHOR_REQUEST_V1", "preview_digest": request_digest(request, job, runtime.is_remote_text_provider(request.provider_id)),
                "chapter_id": job.chapter_id, "chapter_version": job.base_chapter_version,
                "target": "cloud" if runtime.is_remote_text_provider(request.provider_id) else "local",
                "provider_id": request.provider_id, "model_id": request.model_id,
                "request": payload, "prompt_characters": len(request.prompt), "token_count": None,
                "token_count_state": "UNKNOWN", "source_characters": len(job.source or manager.chapters.get(job.chapter_id)["content"][-2000:]),
                "source_strategy": "EXACT_SAVED_SELECTION" if job.source else "LAST_2000_SAVED_CHARACTERS",
                "truncation": "SOURCE_TAIL_2000" if not job.source else "NONE",
                "privacy_omissions": [{"reason": "SOURCE_PRIVACY_POLICY"}] if context.get("privacy_omissions") else [],
                "context_sections": [{"name": key, "characters": len(__import__("json").dumps(value, ensure_ascii=False)), "included_in_adapter_request": True} for key, value in context.items()],
                "creation_records": [{"id": row["id"], "version": row["version"]} for row in job.creation_records],
                "scope_changes_supported": False, "verification": "ACTUAL_REQUEST_BUILDER", "model_called": False,
                "boundary": "Adapter-facing payload; provider-specific protocol encoding is performed by the selected adapter."}

    @router.post("/generate", status_code=202)
    async def generate(nid: str, request: Request, response: Response,
                 x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None),
                 idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=160)):
        body = await read_body(request)
        if not body.preview_digest:
            require_flag(FEATURE)
            raise HTTPException(409, {"code": "AUTHOR_PREVIEW_REQUIRED"})
        value, payload, preview_job, request, authorization, actor, scope = prepare(nid, body, x_session_token, x_branch_id, "domain.write")
        if request_digest(request, preview_job, runtime.is_remote_text_provider(request.provider_id)) != body.preview_digest:
            raise HTTPException(409, {"code": "AUTHOR_PREVIEW_STALE"})
        def reauthorize():
            require_flag(FEATURE)
            if authorize(nid, x_session_token, x_branch_id, "domain.write") != authorization:
                raise ValueError("AUTHOR_SCOPE_CHANGED")
            fresh_actor, fresh_scope = generation_context(value, x_session_token, x_branch_id)
            if (fresh_actor, fresh_scope) != (actor, scope): raise ValueError("AUTHOR_SESSION_CHANGED")
            # Approved style/plan payloads can be revoked or edited independently.
            if generation_payload(value, x_session_token, x_branch_id) != payload_without_receipt:
                raise ValueError("AUTHOR_APPROVAL_CHANGED")
        payload_without_receipt = dict(payload)
        payload["expected_request_digest"] = body.preview_digest
        def create():
            job = manager.create(body.operation, payload, actor, scope, request_authorization=reauthorize)
            return {"job_id": job.id, "status": job.status, "events_url": f"/api/generation/{job.id}/events",
                    "base_chapter_version": job.base_chapter_version, "preview_digest": body.preview_digest}
        response.headers["Cache-Control"] = "no-store"
        if idempotency_key:
            from .. import api as legacy
            authority = [nid, body.chapter_id, getattr(actor, "actor_id", "local-author"),
                         getattr(actor, "workspace_id", "local"), getattr(scope, "branch_id", None)]
            cache_scope = "author-preview:" + body.operation + ":" + hashlib.sha256(json.dumps(authority).encode()).hexdigest()
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            with legacy._idempotency_execution_lock:
                cached = legacy._cached_idempotent(idempotency_key, cache_scope)
                if cached:
                    if cached.get("request_digest") != digest:
                        raise HTTPException(409, {"code": "IDEMPOTENCY_REQUEST_MISMATCH"})
                    return cached["result"]
                result = create()
                legacy._store_idempotent(idempotency_key, cache_scope, {"request_digest": digest, "result": result})
                return result
        return create()

    return router
