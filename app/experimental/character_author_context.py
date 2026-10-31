"""Fail-closed character authoring binding; no model/provider calls or manuscript writes.

The coordinator supplies the current ReadContext, the existing graph service,
and the *original user instruction*, before style/plan enrichment. This helper
owns a transient resolver, not another job executor or a durable credential.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import Field

from .common import StaleSourceError
from .flags import require_flag
from .planning import StrictModel, digest
from .ux import ReadContext


@dataclass(frozen=True)
class CharacterContextSource(ReadContext):
    service: Any = None
    # Must come from the original request body, never enriched job.instruction.
    user_instruction: str = ''


class SourceVersion(StrictModel):
    version: int = Field(ge=1)
    digest: str = Field(pattern=r'^[0-9a-f]{64}$')


class CharacterEvidence(StrictModel):
    record_id: str = Field(min_length=1, max_length=160)
    record_version: int = Field(ge=1)
    chapter_id: str = Field(min_length=1, max_length=160)
    source_versions: dict[str, SourceVersion]


class CharacterEntry(StrictModel):
    text: str = Field(max_length=8000)
    epistemic_status: Literal['KNOWN_FACT', 'BELIEF', 'FALSE_BELIEF', 'SECRET', 'GOAL', 'FEAR', 'VALUE', 'EMOTION', 'INTENT', 'RELATIONSHIP_STATE']
    evidence_status: Literal['EXPLICIT', 'HYPOTHESIS']
    evidence: CharacterEvidence
    relation_version: int | None = Field(default=None, ge=1)


class SceneBoundary(StrictModel):
    id: str
    chapter_id: str
    parent_id: str
    position: int = Field(ge=0)
    version: int = Field(ge=1)
    digest: str = Field(pattern=r'^[0-9a-f]{64}$')


class CharacterProjection(StrictModel):
    contract: Literal['CHARACTER_KNOWLEDGE_V1']
    character_id: str = Field(min_length=1, max_length=160)
    chapter_id: str = Field(min_length=1, max_length=160)
    world_time: int | None
    calendar: str = Field(min_length=1, max_length=80)
    known_facts: list[CharacterEntry]
    beliefs: list[CharacterEntry]
    false_beliefs: list[CharacterEntry]
    secrets: list[CharacterEntry]
    goals: list[CharacterEntry]
    fears: list[CharacterEntry]
    values: list[CharacterEntry]
    emotion: list[CharacterEntry]
    intent: list[CharacterEntry]
    relationships: list[CharacterEntry] = Field(default_factory=list)
    scene_id: str | None = None
    scene_boundary: SceneBoundary | None = None
    verification: Literal['DETERMINISTIC_REVIEWED_EVENTS']
    context_digest: str = Field(pattern=r'^[0-9a-f]{64}$')


class CharacterViewpoint(StrictModel):
    schema_version: Literal[1] = 1
    scene_id: str | None = Field(default=None, min_length=1, max_length=160)
    character_id: str = Field(min_length=1, max_length=160)
    chapter_id: str = Field(min_length=1, max_length=160)
    world_time: int | None = None
    calendar: str = Field(default='story', min_length=1, max_length=80)
    context_digest: str = Field(pattern=r'^[0-9a-f]{64}$')


def is_character_job(job) -> bool:
    # A malformed/empty descriptor or orphaned resolver must not opt back into
    # omniscient mode by truthiness. Explicit exit creates a fresh unbound job.
    return (getattr(job, 'character_viewpoint', None) is not None
            or getattr(job, 'character_context_resolver', None) is not None)


def _flags():
    require_flag('temporal_story_graph_v2')
    require_flag('character_mind_v2')


def _identity(job):
    return deepcopy({key: getattr(job, key, None) for key in
                     ('novel_id', 'chapter_id', 'scope', 'actor_id', 'session_id', 'client_id', 'workspace_id', 'operation')})


def _snapshot(ctx, character_id, chapter_id, world_time, calendar, scene_id=None):
    raw = ctx.service.character_context(ctx.novel_id, ctx.scope, character_id, chapter_id, world_time, calendar, scene_id=scene_id)
    value = CharacterProjection.model_validate(raw).model_dump(exclude_unset=True)
    if value.get('scene_id') != scene_id: raise ValueError('CHARACTER_CONTEXT_SCENE_MISMATCH')
    if (value['character_id'], value['chapter_id'], value['world_time'], value['calendar']) != (character_id, chapter_id, world_time, calendar):
        raise ValueError('CHARACTER_CONTEXT_VIEWPOINT_MISMATCH')
    if value['context_digest'] != digest({key: item for key, item in value.items() if key != 'context_digest'}):
        raise ValueError('CHARACTER_CONTEXT_DIGEST_INVALID')
    expected = {'known_facts': 'KNOWN_FACT', 'beliefs': 'BELIEF', 'false_beliefs': 'FALSE_BELIEF', 'secrets': 'SECRET',
                'goals': 'GOAL', 'fears': 'FEAR', 'values': 'VALUE', 'emotion': 'EMOTION', 'intent': 'INTENT', 'relationships': 'RELATIONSHIP_STATE'}
    if any(item['epistemic_status'] != category for section, category in expected.items() for item in value.get(section, [])):
        raise ValueError('CHARACTER_CONTEXT_EPISTEMIC_MISMATCH')
    return value


def configure_character_job(job, ctx: CharacterContextSource, character_id: str, chapter_id: str,
                            world_time: int | None = None, calendar: str = 'story', *,
                            authorize: Callable[[], object], scene_id: str | None = None):
    """Bind one user-selected viewpoint before preview/request construction.

    Returns the safe persistent descriptor. The resolver is transient and must
    never be serialized. Calling again on the same job is not an opt-out or a
    retry: create and authorize a fresh job instead.
    """
    _flags()
    if is_character_job(job): raise ValueError('CHARACTER_CONTEXT_ALREADY_BOUND')
    if not callable(authorize) or ctx.service is None: raise ValueError('CHARACTER_CONTEXT_AUTHORIZATION_REQUIRED')
    if job.operation not in {'continue', 'brainstorm'}: raise ValueError('CHARACTER_CONTEXT_OPERATION_UNSUPPORTED')
    if job.profile != 'LOCAL_ONLY': raise ValueError('CHARACTER_CONTEXT_LOCAL_ONLY')
    if job.novel_id != ctx.novel_id or job.chapter_id != chapter_id or ctx.scope.get('novel_id') != ctx.novel_id:
        raise ValueError('CHARACTER_CONTEXT_SCOPE_MISMATCH')
    if ctx.scope.get('mode') == 'collaboration':
        expected = {key: ctx.scope.get(key) for key in ('workspace_id', 'storyline_id', 'branch_id')}
        actual = {key: (job.scope or {}).get(key) for key in expected}
        if expected != actual or ctx.branch != expected['branch_id'] or ctx.actor != job.actor_id:
            raise ValueError('CHARACTER_CONTEXT_SCOPE_MISMATCH')
    elif ctx.scope.get('mode') != 'local' or job.scope:
        raise ValueError('CHARACTER_CONTEXT_SCOPE_MISMATCH')
    if not isinstance(ctx.user_instruction, str) or len(ctx.user_instruction) > 20000:
        raise ValueError('CHARACTER_CONTEXT_INSTRUCTION_INVALID')
    # Capture copies, never a caller-owned mutable scope or user instruction.
    captured = CharacterContextSource(novel_id=ctx.novel_id, scope=deepcopy(ctx.scope), actor=ctx.actor,
        token=ctx.token, branch=ctx.branch, service=ctx.service, user_instruction=ctx.user_instruction)
    authority = deepcopy(authorize())
    if authority is False: raise ValueError('CHARACTER_CONTEXT_AUTHORIZATION_REQUIRED')
    initial = _snapshot(captured, character_id, chapter_id, world_time, calendar, scene_id)
    descriptor = CharacterViewpoint(character_id=character_id, chapter_id=chapter_id,
        world_time=world_time, calendar=calendar, scene_id=scene_id, context_digest=initial['context_digest']).model_dump()
    identity = _identity(job)

    def resolve(*, cloud: bool):
        _flags()
        if cloud is not False or job.profile != 'LOCAL_ONLY': raise ValueError('CHARACTER_CONTEXT_LOCAL_ONLY')
        if _identity(job) != identity or getattr(job, 'character_viewpoint', None) != descriptor:
            raise ValueError('CHARACTER_CONTEXT_SCOPE_CHANGED')
        if callable(getattr(getattr(job, 'cancelled', None), 'is_set', None)) and job.cancelled.is_set():
            raise ValueError('CHARACTER_CONTEXT_CANCELLED')
        if job.source or job.style or job.creation_records or job.instruction != captured.user_instruction:
            raise ValueError('CHARACTER_CONTEXT_UNSAFE_ENRICHMENT')
        if authorize() != authority: raise ValueError('CHARACTER_CONTEXT_AUTHORITY_CHANGED')
        current = _snapshot(captured, character_id, chapter_id, world_time, calendar, scene_id)
        if authorize() != authority: raise ValueError('CHARACTER_CONTEXT_AUTHORITY_CHANGED')
        if current['context_digest'] != descriptor['context_digest']:
            raise StaleSourceError('CHARACTER_CONTEXT_SOURCE_CHANGED')
        return {'character_viewpoint': current}

    # No previous snapshot or enriched instruction survives into the actual job.
    job.source = ''
    job.style = ''
    job.creation_records = []
    job.instruction = captured.user_instruction
    job.character_viewpoint = deepcopy(descriptor)
    job.character_context_resolver = resolve
    return deepcopy(descriptor)


def resolve_character_author_context(job, *, cloud: bool):
    """Call before assembly and again from the last-hop dispatch guard."""
    _flags()
    if not is_character_job(job): raise ValueError('CHARACTER_CONTEXT_NOT_BOUND')
    resolver = getattr(job, 'character_context_resolver', None)
    if not callable(resolver): raise ValueError('CHARACTER_CONTEXT_SESSION_REQUIRED')
    # Never fall back to ordinary context after restart or an invalid binding.
    return resolver(cloud=cloud)
