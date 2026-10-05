"""One version/digest-bound coordinator for author preview, direct and broker jobs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..author_request import request_digest, request_payload, saved_source_matches
from ..model_runtime import ModelRuntimeError
from ..router import Route
from ..runtime import runtime

from .revision_intelligence import SelectionIn
from .planning import digest

FEATURE = 'author_context_inspector_v2'


class AuthorPreviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    novel_id: str = Field(min_length=1, max_length=240)
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)
    operation: Literal['continue', 'rewrite', 'polish', 'brainstorm', 'review']
    instruction: str = Field(default='', max_length=20000)
    profile: Literal['LOCAL_ONLY', 'HYBRID', 'QUALITY'] = 'LOCAL_ONLY'
    provider_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    source: str = Field(default='', max_length=200000)
    selected_text: str = Field(default='', max_length=200000)
    style: str = Field(default='', max_length=120)
    style_profile_id: str | None = Field(default=None, max_length=240)
    plot_plan_id: str | None = Field(default=None, max_length=240)
    revision_selection: SelectionIn | None = None
    revision_selection_digest: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    character_id: str | None = Field(default=None, min_length=1, max_length=160)
    world_time: int | None = None
    calendar: str = Field(default='story', min_length=1, max_length=80)
    preview_digest: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    generation_request_id: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode='after')
    def viewpoint(self):
        if (self.revision_selection is None) != (self.revision_selection_digest is None):
            raise ValueError('revision selection and receipt are required together')
        if self.revision_selection is not None and (self.operation != 'rewrite' or self.character_id is not None):
            raise ValueError('selection generation requires rewrite without character mode')
        if self.character_id is None and (self.world_time is not None or self.calendar != 'story'):
            raise ValueError('world-time viewpoint requires a character')
        return self


@dataclass(frozen=True)
class PreparedAuthor:
    job: Any
    request: Any


class AuthorPreparer:
    """Shared by router and broker; never starts/persists/probes a model."""
    def __init__(self, manager, authorize, require_flag, generation_context, generation_payload, *, story_graph=None, revision_selection_validator=None):
        self.manager, self.authorize, self.require_flag = manager, authorize, require_flag
        self.generation_context, self.generation_payload = generation_context, generation_payload
        self.story_graph = story_graph
        self.revision_selection_validator = revision_selection_validator

    def _revision_receipt(self, nid, scope, body, source):
        self.require_flag('revision_intelligence_v2'); self.require_flag('selection_assistant_v2')
        if not callable(self.revision_selection_validator):
            raise ValueError('REVISION_SELECTION_VALIDATOR_UNAVAILABLE')
        captured = self.revision_selection_validator(nid, scope, body.revision_selection)
        selected = SelectionIn.model_validate(captured['selection']).model_dump()
        if (selected != body.revision_selection.model_dump() or captured['selection_digest'] != body.revision_selection_digest
            or selected['chapter_id'] != body.chapter_id or selected['chapter_version'] != body.chapter_version
            or selected['text'] != source):
            raise ValueError('REVISION_SELECTION_MISMATCH')
        return {'selection': selected, 'selection_digest': captured['selection_digest']}, digest(captured)

    def _prepare(self, nid, body, token, branch, permission):
        from ..api import GenerateIn
        self.require_flag(FEATURE)
        authorization = self.authorize(nid, token, branch, permission)
        if body.novel_id != nid: raise HTTPException(404, {'code': 'CHAPTER_OUTSIDE_PROJECT'})
        character = body.character_id is not None
        if character:
            self.require_flag('temporal_story_graph_v2'); self.require_flag('character_mind_v2')
            if self.story_graph is None: raise HTTPException(409, {'code': 'CHARACTER_CONTEXT_UNAVAILABLE'})
            if body.operation not in {'continue', 'brainstorm'}:
                raise HTTPException(422, {'code': 'CHARACTER_CONTEXT_OPERATION_UNSUPPORTED'})
            if body.profile != 'LOCAL_ONLY' or runtime.is_remote_text_provider(body.provider_id):
                raise HTTPException(403, {'code': 'CHARACTER_CONTEXT_LOCAL_ONLY'})
            source = ''
        else:
            source = body.source or body.selected_text
            if body.source and body.selected_text and body.source != body.selected_text:
                raise HTTPException(422, {'code': 'AUTHOR_SELECTION_MISMATCH'})
            if body.operation == 'rewrite' and not source:
                raise HTTPException(422, {'code': 'AUTHOR_SELECTION_REQUIRED'})
        revision_binding = revision_fingerprint = None
        if body.revision_selection is not None:
            try: revision_binding, revision_fingerprint = self._revision_receipt(nid, authorization[1], body, source)
            except (ValueError, FileNotFoundError, KeyError):
                raise HTTPException(409, {'code': 'REVISION_SELECTION_UNAVAILABLE_OR_STALE'}) from None
        raw = body.model_dump(exclude={'operation', 'chapter_version', 'preview_digest', 'generation_request_id', 'character_id', 'world_time', 'calendar', 'revision_selection', 'revision_selection_digest'})
        raw.update(source=source, selected_text=source)
        if character:
            # Do not even resolve approved style/plan records in this mode. The
            # original request instruction is the sole retained author input.
            raw.update(style='', style_profile_id=None, plot_plan_id=None, instruction=body.instruction)
        try: value = GenerateIn.model_validate(raw)
        except ValidationError: raise HTTPException(422, {'code': 'AUTHOR_PREVIEW_INPUT_INVALID'}) from None
        actor, scope = self.generation_context(value, token, branch)
        payload = value.model_dump(exclude={'count'}) if character else self.generation_payload(value, token, branch)
        job = self.manager.prepare_job(body.operation, payload, actor, scope)
        if job.base_chapter_version != body.chapter_version:
            raise HTTPException(409, {'code': 'AUTHOR_CHAPTER_CHANGED'})
        chapter = self.manager.chapters.get(job.chapter_id)
        if source and not saved_source_matches(chapter, source):
            raise HTTPException(409, {'code': 'AUTHOR_SELECTION_NOT_SAVED'})

        def reauthorize():
            self.require_flag(FEATURE)
            if self.authorize(nid, token, branch, permission) != authorization:
                raise ValueError('AUTHOR_SCOPE_CHANGED')
            fresh_actor, fresh_scope = self.generation_context(value, token, branch)
            if (fresh_actor, fresh_scope) != (actor, scope): raise ValueError('AUTHOR_SESSION_CHANGED')
            current_payload = value.model_dump(exclude={'count'}) if character else self.generation_payload(value, token, branch)
            if current_payload != payload: raise ValueError('AUTHOR_APPROVAL_CHANGED')
            if revision_binding is not None:
                current_binding, current_fingerprint = self._revision_receipt(nid, authorization[1], body, source)
                if (current_binding != revision_binding or current_fingerprint != revision_fingerprint
                    or not job.partial_revision_only or job.revision_selection_binding != revision_binding):
                    raise ValueError('REVISION_SELECTION_CHANGED')
            return authorization

        job.request_authorization = reauthorize
        if character:
            from .character_author_context import CharacterContextSource, configure_character_job
            ctx = CharacterContextSource(novel_id=nid, scope=authorization[1], actor=authorization[0], token=token,
                branch=branch, service=self.story_graph, user_instruction=body.instruction)
            try:
                configure_character_job(job, ctx, body.character_id, body.chapter_id, body.world_time, body.calendar, authorize=reauthorize)
            except (ValueError, FileNotFoundError):
                raise HTTPException(409, {'code': 'CHARACTER_CONTEXT_UNAVAILABLE_OR_STALE'}) from None
        from ..jobs import mark_generation_origin
        mark_generation_origin(job, 'character_author' if character else 'author_context')
        if revision_binding is not None:
            if job.source != revision_binding['selection']['text'] or job.operation != 'rewrite':
                raise HTTPException(409, {'code': 'REVISION_SELECTION_SOURCE_CHANGED'})
            job.partial_revision_only = True
            job.revision_selection_binding = deepcopy(revision_binding)
            mark_generation_origin(job, 'selection_assistant')
        route = Route(body.provider_id, body.model_id)
        try: _, _, request = self.manager.prepare_author_request(job, route)
        except (ModelRuntimeError, ValueError):
            raise HTTPException(409, {'code': 'AUTHOR_CONTEXT_OR_PRIVACY_BLOCKED'}) from None
        try: reauthorize()
        except ValueError: raise HTTPException(409, {'code': 'AUTHOR_SCOPE_OR_SOURCE_CHANGED'}) from None
        return PreparedAuthor(job, request)

    def prepare_preview(self, nid, body: AuthorPreviewInput, token=None, branch=None):
        return self._prepare(nid, body, token, branch, 'domain.read')

    def prepare_author(self, nid, body: AuthorPreviewInput, token=None, branch=None):
        self.require_flag(FEATURE)
        if not body.preview_digest: raise HTTPException(409, {'code': 'AUTHOR_PREVIEW_REQUIRED'})
        prepared = self._prepare(nid, body, token, branch, 'domain.write')
        if request_digest(prepared.request, prepared.job, runtime.is_remote_text_provider(prepared.request.provider_id)) != body.preview_digest:
            raise HTTPException(409, {'code': 'AUTHOR_PREVIEW_STALE'})
        prepared.job.expected_request_digest = body.preview_digest
        # Exactly this object, including transient authority and viewpoint
        # resolvers, must be passed to start_prepared. No second prepare_job.
        return prepared.job

    __call__ = prepare_author


def create_author_preparer(manager, authorize, require_flag, generation_context, generation_payload, *, story_graph=None, revision_selection_validator=None):
    return AuthorPreparer(manager, authorize, require_flag, generation_context, generation_payload,
        story_graph=story_graph, revision_selection_validator=revision_selection_validator)


def create_author_context_router(manager, authorize, require_flag, generation_context, generation_payload, *, preparer=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/author-context', tags=['Experimental author context'])
    preparer = preparer or create_author_preparer(manager, authorize, require_flag, generation_context, generation_payload)

    async def read_body(request):
        require_flag(FEATURE)
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 2 * 1024 * 1024: raise HTTPException(413, {'code': 'AUTHOR_PREVIEW_INPUT_TOO_LARGE'})
        try: return AuthorPreviewInput.model_validate_json(bytes(raw))
        except (ValidationError, ValueError): raise HTTPException(422, {'code': 'AUTHOR_PREVIEW_INPUT_INVALID'}) from None

    @router.post('/preview')
    async def preview(nid: str, request: Request, response: Response,
                      x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        body = await read_body(request)
        prepared = preparer.prepare_preview(nid, body, x_session_token, x_branch_id)
        job, assembled = prepared.job, prepared.request
        response.headers['Cache-Control'] = 'no-store'
        payload = request_payload(assembled); context = payload['context']
        character = job.character_viewpoint is not None
        result = {'contract': 'AUTHOR_REQUEST_V1', 'preview_digest': request_digest(assembled, job, runtime.is_remote_text_provider(assembled.provider_id)),
            'chapter_id': job.chapter_id, 'chapter_version': job.base_chapter_version,
            'target': 'cloud' if runtime.is_remote_text_provider(assembled.provider_id) else 'local',
            'provider_id': assembled.provider_id, 'model_id': assembled.model_id,
            'request': payload, 'prompt_characters': len(assembled.prompt), 'token_count': None, 'token_count_state': 'UNKNOWN',
            'source_characters': 0 if character else len(job.source or manager.chapters.get(job.chapter_id)['content'][-2000:]),
            'source_strategy': 'CHARACTER_KNOWLEDGE_ONLY' if character else 'EXACT_SAVED_SELECTION' if job.source else 'LAST_2000_SAVED_CHARACTERS',
            'truncation': 'NONE' if character or job.source else 'SOURCE_TAIL_2000',
            'privacy_omissions': [{'reason': 'CHARACTER_VIEWPOINT_BOUNDARY'}] if character else [{'reason': 'SOURCE_PRIVACY_POLICY'}] if context.get('privacy_omissions') else [],
            'context_sections': [{'name': key, 'characters': len(json.dumps(value, ensure_ascii=False)), 'included_in_adapter_request': True} for key, value in context.items()],
            'creation_records': [{'id': row['id'], 'version': row['version']} for row in job.creation_records],
            'scope_changes_supported': False, 'verification': 'ACTUAL_REQUEST_BUILDER', 'model_called': False,
            'boundary': 'Adapter-facing payload; provider-specific protocol encoding is performed by the selected adapter.'}
        if character: result['character_viewpoint'] = job.character_viewpoint
        if job.partial_revision_only:
            result.update(partial_revision_only=True, revision_selection_binding=job.revision_selection_binding)
        return result

    @router.post('/generate', status_code=202)
    async def generate(nid: str, request: Request, response: Response,
                       x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None),
                       idempotency_key: str | None = Header(None, alias='Idempotency-Key', max_length=160)):
        body = await read_body(request)
        job = preparer.prepare_author(nid, body, x_session_token, x_branch_id)
        def create():
            manager.start_prepared(job)
            return {'job_id': job.id, 'status': job.public()['status'], 'events_url': f'/api/generation/{job.id}/events',
                    'base_chapter_version': job.base_chapter_version, 'preview_digest': body.preview_digest}
        response.headers['Cache-Control'] = 'no-store'
        if idempotency_key:
            from .. import api as legacy
            authority = [nid, body.chapter_id, job.actor_id or 'local-author', job.workspace_id or 'local', (job.scope or {}).get('branch_id')]
            cache_scope = 'author-preview:' + body.operation + ':' + hashlib.sha256(json.dumps(authority).encode()).hexdigest()
            fingerprint = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            with legacy._idempotency_execution_lock:
                cached = legacy._cached_idempotent(idempotency_key, cache_scope)
                if cached:
                    if cached.get('request_digest') != fingerprint:
                        raise HTTPException(409, {'code': 'IDEMPOTENCY_REQUEST_MISMATCH'})
                    return cached['result']
                result = create()
                legacy._store_idempotent(idempotency_key, cache_scope, {'request_digest': fingerprint, 'result': result})
                return result
        return create()

    return router
