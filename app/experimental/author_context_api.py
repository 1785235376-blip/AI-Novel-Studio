"""One version/digest-bound coordinator for author preview, direct and broker jobs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..author_request import request_digest, request_payload, saved_source_matches, author_source, automatic_context_allowed
from ..model_runtime import ModelRuntimeError
from ..router import Route
from ..runtime import runtime

from .revision_intelligence import SelectionIn
from .planning import digest

FEATURE = 'author_context_inspector_v2'


class AuthorRequestScope(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source_mode: Literal['AUTO', 'SELECTION_ONLY', 'NONE'] = 'AUTO'
    include_automatic_context: bool = True
    include_style_reference: bool = True
    include_plan_reference: bool = True


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
    request_scope: AuthorRequestScope | None = None
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


class VariantReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    variant_index: int = Field(ge=1, le=3)
    preview_digest: str = Field(pattern=r'^[0-9a-f]{64}$')


class AuthorVariantsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    author: AuthorPreviewInput
    count: int = Field(ge=2, le=3, strict=True)
    group_id: str = Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    receipts: list[VariantReceipt] = Field(default_factory=list, max_length=3)

    @model_validator(mode='after')
    def bounded(self):
        if (self.author.character_id or self.author.revision_selection or self.author.operation == 'review'
            or self.author.preview_digest or self.author.generation_request_id):
            raise ValueError('unsupported author batch mode')
        if self.receipts and [row.variant_index for row in self.receipts] != list(range(1, self.count + 1)):
            raise ValueError('each ordered variant requires exactly one receipt')
        return self

    def variants(self):
        fingerprint = digest(self.model_dump(exclude={'receipts'}))
        for index in range(1, self.count + 1):
            instruction = (self.author.instruction + f"\n候选方案 {index}：请提供与其他候选明显不同但同样符合要求的方向。").strip()
            body = self.author.model_copy(update={'instruction': instruction,
                'preview_digest': self.receipts[index - 1].preview_digest if self.receipts else None})
            binding = {'group_id': self.group_id, 'variant_index': index, 'count': self.count,
                'job_id': str(uuid.uuid5(uuid.UUID(self.group_id), str(index))), 'batch_input_digest': fingerprint}
            yield body, binding


@dataclass(frozen=True)
class PreparedAuthor:
    job: Any
    request: Any


class AuthorPreparer:
    """Shared by router and broker; never starts/persists/probes a model."""
    def __init__(self, manager, authorize, require_flag, generation_context, generation_payload, *, story_graph=None, revision_selection_validator=None, variant_policy_guard=None):
        self.manager, self.authorize, self.require_flag = manager, authorize, require_flag
        self.generation_context, self.generation_payload = generation_context, generation_payload
        self.variant_policy_guard = variant_policy_guard
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

    def _prepare(self, nid, body, token, branch, permission, variant=None):
        from ..api import GenerateIn
        self.require_flag(FEATURE)
        authorization = self.authorize(nid, token, branch, permission)
        if body.novel_id != nid: raise HTTPException(404, {'code': 'CHAPTER_OUTSIDE_PROJECT'})
        character = body.character_id is not None
        requested_scope = body.request_scope.model_dump() if body.request_scope else None
        if character and requested_scope is not None:
            raise HTTPException(422, {'code': 'CHARACTER_CONTEXT_SCOPE_UNSUPPORTED'})
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
            if body.request_scope and body.request_scope.source_mode == 'NONE':
                source = ''
            if body.request_scope and body.request_scope.source_mode == 'SELECTION_ONLY' and not source:
                raise HTTPException(422, {'code': 'AUTHOR_SELECTION_REQUIRED'})
            if body.operation == 'rewrite' and not source:
                raise HTTPException(422, {'code': 'AUTHOR_SELECTION_REQUIRED'})
        variant_policy = None
        if variant is not None:
            if not callable(self.variant_policy_guard):
                raise HTTPException(409, {'code': 'AUTHOR_VARIANT_POLICY_GUARD_UNAVAILABLE'})
            try:
                variant_policy = deepcopy(self.variant_policy_guard(nid, authorization[1], authorization[0], body.provider_id, body.model_id, variant['count']))
            except HTTPException: raise
            except Exception: raise HTTPException(409, {'code': 'AUTHOR_VARIANT_POLICY_UNAVAILABLE'}) from None
            if not isinstance(variant_policy, dict): raise HTTPException(409, {'code': 'AUTHOR_VARIANT_POLICY_UNAVAILABLE'})
        revision_binding = revision_fingerprint = None
        if body.revision_selection is not None:
            try: revision_binding, revision_fingerprint = self._revision_receipt(nid, authorization[1], body, source)
            except (ValueError, FileNotFoundError, KeyError):
                raise HTTPException(409, {'code': 'REVISION_SELECTION_UNAVAILABLE_OR_STALE'}) from None
        raw = body.model_dump(exclude={'operation', 'chapter_version', 'preview_digest', 'generation_request_id', 'character_id', 'world_time', 'calendar', 'revision_selection', 'revision_selection_digest', 'request_scope'})
        raw.update(source=source, selected_text=source)
        if body.request_scope:
            reduced = body.request_scope.source_mode != 'AUTO'
            # Approved references can derive from excluded manuscript, too. Their
            # dependency metadata cannot prove substring-level noninterference.
            if reduced or not body.request_scope.include_style_reference: raw['style_profile_id'] = None
            if reduced or not body.request_scope.include_plan_reference: raw['plot_plan_id'] = None
        if character:
            # Do not even resolve approved style/plan records in this mode. The
            # original request instruction is the sole retained author input.
            raw.update(style='', style_profile_id=None, plot_plan_id=None, instruction=body.instruction)
        try: value = GenerateIn.model_validate(raw)
        except ValidationError: raise HTTPException(422, {'code': 'AUTHOR_PREVIEW_INPUT_INVALID'}) from None
        actor, scope = self.generation_context(value, token, branch)
        payload = value.model_dump(exclude={'count'}) if character else self.generation_payload(value, token, branch)
        job = self.manager.prepare_job(body.operation, payload, actor, scope)
        if variant is not None:
            job.reviewed_variant_policy = deepcopy(variant_policy)
            job.reviewed_variant = deepcopy(variant)
            job.id = variant['job_id']; job.variant_group_id = variant['group_id']; job.variant_index = variant['variant_index']
        job.request_scope = deepcopy(requested_scope)
        job.author_input_digest = digest([body.model_dump(exclude={"preview_digest", "generation_request_id"}), authorization])
        if job.base_chapter_version != body.chapter_version:
            raise HTTPException(409, {'code': 'AUTHOR_CHAPTER_CHANGED'})
        chapter = self.manager.chapters.get(job.chapter_id)
        if source and not saved_source_matches(chapter, source):
            raise HTTPException(409, {'code': 'AUTHOR_SELECTION_NOT_SAVED'})

        def reauthorize():
            self.require_flag(FEATURE)
            if job.reviewed_variant != variant: raise ValueError('AUTHOR_VARIANT_CHANGED')
            if variant is not None:
                current_policy = self.variant_policy_guard(nid, authorization[1], authorization[0], body.provider_id, body.model_id, variant['count'])
                if current_policy != variant_policy or job.reviewed_variant_policy != variant_policy:
                    raise ValueError('AUTHOR_VARIANT_POLICY_CHANGED')
            if variant is not None and (job.id != variant['job_id'] or job.variant_group_id != variant['group_id'] or job.variant_index != variant['variant_index']):
                raise ValueError('AUTHOR_VARIANT_CHANGED')
            if job.request_scope != requested_scope: raise ValueError('AUTHOR_REQUEST_SCOPE_CHANGED')
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

    def prepare_preview(self, nid, body: AuthorPreviewInput, token=None, branch=None, *, variant=None):
        return self._prepare(nid, body, token, branch, 'domain.read', variant)

    def prepare_author(self, nid, body: AuthorPreviewInput, token=None, branch=None, *, variant=None):
        self.require_flag(FEATURE)
        if not body.preview_digest: raise HTTPException(409, {'code': 'AUTHOR_PREVIEW_REQUIRED'})
        prepared = self._prepare(nid, body, token, branch, 'domain.write', variant)
        if request_digest(prepared.request, prepared.job, runtime.is_remote_text_provider(prepared.request.provider_id)) != body.preview_digest:
            raise HTTPException(409, {'code': 'AUTHOR_PREVIEW_STALE'})
        prepared.job.expected_request_digest = body.preview_digest
        # Exactly this object, including transient authority and viewpoint
        # resolvers, must be passed to start_prepared. No second prepare_job.
        return prepared.job

    __call__ = prepare_author


def create_author_preparer(manager, authorize, require_flag, generation_context, generation_payload, *, story_graph=None, revision_selection_validator=None, variant_policy_guard=None):
    return AuthorPreparer(manager, authorize, require_flag, generation_context, generation_payload,
        story_graph=story_graph, revision_selection_validator=revision_selection_validator, variant_policy_guard=variant_policy_guard)


def create_author_context_router(manager, authorize, require_flag, generation_context, generation_payload, *, preparer=None, variant_policy_guard=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/author-context', tags=['Experimental author context'])
    preparer = preparer or create_author_preparer(manager, authorize, require_flag, generation_context, generation_payload, variant_policy_guard=variant_policy_guard)

    async def read_body(request, model=AuthorPreviewInput):
        require_flag(FEATURE)
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 2 * 1024 * 1024: raise HTTPException(413, {'code': 'AUTHOR_PREVIEW_INPUT_TOO_LARGE'})
        try: return model.model_validate_json(bytes(raw))
        except (ValidationError, ValueError): raise HTTPException(422, {'code': 'AUTHOR_PREVIEW_INPUT_INVALID'}) from None

    @router.post('/preview')
    async def preview(nid: str, request: Request, response: Response,
                      x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        body = await read_body(request)
        prepared = preparer.prepare_preview(nid, body, x_session_token, x_branch_id)
        response.headers['Cache-Control'] = 'no-store'
        return preview_result(prepared)

    def preview_result(prepared):
        job, assembled = prepared.job, prepared.request
        payload = request_payload(assembled); context = payload['context']
        character = job.character_viewpoint is not None
        result = {'contract': 'AUTHOR_REQUEST_V1', 'preview_digest': request_digest(assembled, job, runtime.is_remote_text_provider(assembled.provider_id)),
            'chapter_id': job.chapter_id, 'chapter_version': job.base_chapter_version,
            'target': 'cloud' if runtime.is_remote_text_provider(assembled.provider_id) else 'local',
            'provider_id': assembled.provider_id, 'model_id': assembled.model_id,
            'request': payload, 'prompt_characters': len(assembled.prompt), 'token_count': None, 'token_count_state': 'UNKNOWN',
            'source_characters': 0 if character else len(author_source(job, manager.chapters.get(job.chapter_id))),
            'source_strategy': 'CHARACTER_KNOWLEDGE_ONLY' if character else 'NO_MANUSCRIPT' if (job.request_scope or {}).get('source_mode') == 'NONE' else 'EXACT_SAVED_SELECTION' if job.source else 'LAST_2000_SAVED_CHARACTERS',
            'truncation': 'NONE' if character or job.source or (job.request_scope or {}).get('source_mode') == 'NONE' else 'SOURCE_TAIL_2000',
            'privacy_omissions': [{'reason': 'CHARACTER_VIEWPOINT_BOUNDARY'}] if character else [{'reason': 'SOURCE_PRIVACY_POLICY'}] if context.get('privacy_omissions') else [],
            'context_sections': [{'name': key, 'characters': len(json.dumps(value, ensure_ascii=False)), 'included_in_adapter_request': True} for key, value in context.items()],
            'creation_records': [{'id': row['id'], 'version': row['version']} for row in job.creation_records],
            'scope_changes_supported': not character, 'request_scope': job.request_scope,
            'scope_effects': {'automatic_context_included': not character and automatic_context_allowed(job),
                'references_omitted_for_source_isolation': not character and (job.request_scope or {}).get('source_mode', 'AUTO') != 'AUTO',
                'granularity': 'WHOLE_AUTOMATIC_BUNDLE',
                'reason': 'DERIVED_SOURCE_ISOLATION_UNPROVEN' if not character and (job.request_scope or {}).get('source_mode', 'AUTO') != 'AUTO' else None}, 'verification': 'ACTUAL_REQUEST_BUILDER', 'model_called': False,
            'boundary': 'Adapter-facing payload; provider-specific protocol encoding is performed by the selected adapter.'}
        if job.reviewed_variant is not None:
            result.update(variant=job.reviewed_variant, variant_policy=job.reviewed_variant_policy)
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

    def check_batch(nid, body, token, branch, permission):
        require_flag(FEATURE)
        authority = authorize(nid, token, branch, permission)
        if body.author.novel_id != nid: raise HTTPException(404, {'code': 'CHAPTER_OUTSIDE_PROJECT'})
        # Cloud batches need an A06 group reservation coordinator, not this
        # direct local path. Explicit route selection never permits fallback.
        if body.author.profile != 'LOCAL_ONLY' or runtime.is_remote_text_provider(body.author.provider_id):
            raise HTTPException(409, {'code': 'AUTHOR_VARIANTS_LOCAL_ONLY_BUDGET_REQUIRED'})
        return authority

    @router.post('/preview-variants')
    async def preview_variants(nid: str, request: Request, response: Response,
                               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        body = await read_body(request, AuthorVariantsInput)
        check_batch(nid, body, x_session_token, x_branch_id, 'domain.read')
        if body.receipts: raise HTTPException(422, {'code': 'AUTHOR_VARIANT_PREVIEW_INPUT_INVALID'})
        values = [preview_result(preparer.prepare_preview(nid, author, x_session_token, x_branch_id, variant=binding))
                  for author, binding in body.variants()]
        response.headers['Cache-Control'] = 'no-store'
        return {'group_id': body.group_id, 'count': body.count, 'variants': values, 'model_called': False,
                'execution_policy': 'LOCAL_ONLY_EXACTLY_REVIEWED_REQUESTS_NO_RETRY'}

    def batch_result(body):
        rows = []
        for author, binding in body.variants():
            try: job = manager.get(binding['job_id'])
            except KeyError: job = None
            status = job.public()['status'] if job else 'UNKNOWN'
            rows.append({'job_id': binding['job_id'], 'variant_index': binding['variant_index'],
                'status': status, 'preview_digest': author.preview_digest,
                'base_chapter_version': job.base_chapter_version if job else body.author.chapter_version,
                'events_url': f"/api/generation/{binding['job_id']}/events",
                'receipt_state': (job.reviewed_variant_receipt_state or 'PERSISTENCE_UNCERTAIN') if job else 'UNKNOWN_NO_AUTOMATIC_REPLAY'})
        statuses = {row['status'] for row in rows}
        state = 'UNKNOWN' if any(row['receipt_state'] != 'RECORDED' for row in rows) or 'UNKNOWN' in statuses else 'COMPLETED' if statuses <= {'COMPLETED', 'ACCEPTED', 'REJECTED'} else 'PARTIAL' if statuses & {'FAILED', 'CANCELLED'} else 'RUNNING'
        return {'group_id': body.group_id, 'count': body.count, 'variants': rows, 'batch_state': state,
                'automatic_retry': False, 'usage_state': 'PER_JOB_REPORTED_OR_UNKNOWN'}

    @router.post('/generate-variants', status_code=202)
    async def generate_variants(nid: str, request: Request, response: Response,
                                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        body = await read_body(request, AuthorVariantsInput)
        authority = check_batch(nid, body, x_session_token, x_branch_id, 'domain.write')
        if not body.receipts: raise HTTPException(409, {'code': 'AUTHOR_VARIANT_PREVIEWS_REQUIRED'})
        response.headers['Cache-Control'] = 'no-store'
        # One original executor group is the durable once-only receipt, including
        # PREPARED rows. Restart never resumes these authorization closures.
        from .. import api as legacy
        with legacy._idempotency_execution_lock:
            existing = manager.variants(body.group_id)
            if existing:
                expected = {binding['job_id']: (author, binding) for author, binding in body.variants()}
                for job in existing:
                    pair = expected.get(job.id)
                    if (pair is None or job.novel_id != nid or job.reviewed_variant != pair[1]
                        or job.expected_request_digest != pair[0].preview_digest
                        or job.author_input_digest != digest([pair[0].model_dump(exclude={'preview_digest', 'generation_request_id'}), authority])):
                        raise HTTPException(409, {'code': 'AUTHOR_VARIANT_IDEMPOTENCY_MISMATCH'})
                # Validate current actor/scope without retrieving or exposing
                # another actor's group, even when text/digests are identical.
                actor, scope = preparer.generation_context(body.author, x_session_token, x_branch_id)
                if any(job.actor_id != (actor.actor_id if actor else None) or job.session_id != (actor.session_id if actor else None)
                       or (job.scope or {}).get('branch_id') != (scope.branch_id if scope else None) for job in existing):
                    raise HTTPException(404, {'code': 'AUTHOR_VARIANT_GROUP_NOT_FOUND'})
                return batch_result(body)
            jobs = [preparer.prepare_author(nid, author, x_session_token, x_branch_id, variant=binding)
                    for author, binding in body.variants()]
            try:
                for job in jobs: job.request_authorization()
            except ValueError:
                raise HTTPException(409, {'code': 'AUTHOR_SCOPE_OR_SOURCE_CHANGED'}) from None
            try:
                manager.stage_reviewed_variants(jobs)
                for job in jobs:
                    # Cancellation of a staged member stops it without starting
                    # another request. All siblings retain their original IDs.
                    if job.cancelled.is_set() or job.status != 'PREPARED': continue
                    manager.start_prepared(job)
            except Exception:
                # A start/persistence exception cannot authorize a replay or
                # silently create the remaining candidates on a later retry.
                for job in jobs:
                    if job.status == 'PREPARED':
                        job.cancelled.set(); job.status = 'CANCELLED'; job.execution_outcome = 'CANCELLED'
                        job.reviewed_variant_receipt_state = 'RECORDED'
                        try: manager._persist(job)
                        except Exception: job.reviewed_variant_receipt_state = 'PERSISTENCE_UNCERTAIN'
            return batch_result(body)

    return router
