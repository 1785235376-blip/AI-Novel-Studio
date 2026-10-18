"""Local, author-entered reader comparisons in the original narrative review owners.

No simulated opinions, model execution, new queue, or manuscript mutations.
Age group describes the intended content audience, never an actual person.
"""
from copy import deepcopy
from contextlib import contextmanager, ExitStack
from typing import Literal
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import Field, field_validator

from .common import new_row, now, StaleSourceError
from .planning import StrictModel, collection, digest
from .narrative_judge import JudgeEvidence, validate_evidence
from .style_analysis import paragraphs
from ..repositories.file.mutation_coordinator import workspace_mutation
from ..creative.project_store import CreativeProjectStore


class ReaderProfile(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    genre_experience: Literal['NOVICE', 'FAMILIAR', 'EXPERIENCED']
    target_age_group: Literal['GENERAL', 'CHILDREN', 'TEENS', 'ADULTS']
    language_habit: str = Field(min_length=1, max_length=240)
    reading_speed: int = Field(ge=1, le=10000, strict=True)

    @field_validator('name', 'language_habit')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('nonblank profile parameter required')
        return value.strip()


class AuthorObservation(StrictModel):
    profile_index: Literal[0, 1]
    evidence: JudgeEvidence
    observation: str = Field(min_length=1, max_length=2000)
    suggestion: str = Field(min_length=1, max_length=2000)

    @field_validator('observation', 'suggestion')
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError('nonblank author observation required')
        return value.strip()


class AudienceComparisonIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    expected_version: int = Field(ge=1)
    expected_source_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    profiles: list[ReaderProfile] = Field(min_length=2, max_length=2)
    observations: list[AuthorObservation] = Field(default_factory=list, max_length=20)
    comparison: Literal['DIFFERENT_ADVICE', 'AGREEMENT', 'NOT_ASSESSED'] = 'NOT_ASSESSED'


BOUNDARY = ('作者按阅读目标录入的观察，不是模型模拟意见或真实读者测试。'
            '阅读时间仅按非空白 Unicode 字符数与自填速度估算，不评价理解、文学质量、市场表现或成功率。'
            '年龄层仅是作品目标分类，不记录真实未成年人资料。')


class AudienceReview:
    """Small composition, borrowing the exact judge receipt and review authorities."""
    def __init__(self, judge): self.judge = judge

    def prepare_source(self, nid, scope, chapter_id, expected_version, guard=lambda: None):
        # Explicit author action initializes only the original owner marker.
        _, chapters = self.judge.capture(nid, scope, [chapter_id], {chapter_id: expected_version})
        chapter = chapters[chapter_id]
        if chapter.get('hidden') or chapter.get('secret') or chapter.get('archived_at') or chapter.get('is_archived'):
            raise FileNotFoundError('source unavailable')
        guard()
        owner = CreativeProjectStore(self.judge.store)
        with ExitStack() as lifecycle:
            with self.judge.store.transaction(nid, scope):
                lifecycle.enter_context(owner.owner_lease(nid))
                self.judge.novels.get(nid); guard()
        return self.source(nid, scope, chapter_id, expected_version, guard)

    def source(self, nid, scope, chapter_id, expected_version, guard=lambda: None):
        owner = CreativeProjectStore(self.judge.store)
        with owner.existing_owner_only():
            identity = owner.incarnation(nid)
        result = self._source(nid, scope, chapter_id, expected_version, identity, guard)
        with owner.existing_owner_only():
            if owner.incarnation(nid) != identity: raise StaleSourceError('AUDIENCE_PROJECT_CHANGED')
        return result

    def _source(self, nid, scope, chapter_id, expected_version, identity, guard):
        sources, chapters = self.judge.capture(nid, scope, [chapter_id], {chapter_id: expected_version})
        chapter = chapters[chapter_id]
        if chapter.get('hidden') or chapter.get('secret') or chapter.get('archived_at') or chapter.get('is_archived'):
            raise FileNotFoundError('source unavailable')
        rows = paragraphs(chapter.get('content', ''))
        # Evidence has the original 2,000-character limit; do not truncate quotes
        # and pretend they represent an entire long paragraph.
        result = {'chapter_id': chapter_id, 'chapter_version': expected_version,
                  'paragraphs': [p for p in rows if len(p['quote']) <= 2000],
                  'unsupported_paragraphs': sum(len(p['quote']) > 2000 for p in rows),
                  'coordinate': 'RAW_MARKDOWN_UNICODE_CODEPOINT',
                  'source_digest': digest([identity, sources])}
        guard()
        self.judge.assert_capture(nid, scope, sources)
        latest_sources, latest = self.judge.capture(nid, scope, [chapter_id], {chapter_id: expected_version})
        if latest_sources != sources: raise StaleSourceError('AUDIENCE_SOURCE_PREVIEW_CHANGED')
        current = latest[chapter_id]
        if current.get('hidden') or current.get('secret') or current.get('archived_at') or current.get('is_archived'):
            raise StaleSourceError('source unavailable')
        return result

    def catalog(self, nid, scope):
        rows = []
        for row in self.judge.chapter_catalog(nid, scope):
            chapter = self.judge.chapters_for(scope).get(row['id'])
            if not chapter.get('hidden') and not chapter.get('secret') and not chapter.get('archived_at') and not chapter.get('is_archived'):
                rows.append(row)
        return {'chapters': rows, 'profiles': [], 'boundary': BOUNDARY, 'model_called': False}

    def comparisons(self, nid, scope):
        j = self.judge
        return [j._public(nid, scope, row) for row in j.list(nid, scope, j.RUNS) if row.get('audience')]

    def create(self, nid, scope, actor, value, guard=lambda: None):
        data = AudienceComparisonIn.model_validate(value.model_dump() if hasattr(value, 'model_dump') else value)
        j = self.judge
        owner = CreativeProjectStore(j.store)
        with owner.existing_owner_only():
            identity = owner.incarnation(nid)
        sources, chapters = j.capture(nid, scope, [data.chapter_id], {data.chapter_id: data.expected_version})
        if digest([identity, sources]) != data.expected_source_digest:
            raise StaleSourceError('AUDIENCE_SOURCE_PREVIEW_CHANGED')
        chapter = chapters[data.chapter_id]
        if chapter.get('hidden') or chapter.get('secret') or chapter.get('archived_at') or chapter.get('is_archived'):
            raise FileNotFoundError('source unavailable')
        if data.comparison != 'NOT_ASSESSED' and {o.profile_index for o in data.observations} != {0, 1}:
            raise ValueError('comparison requires an author observation for both profiles')
        profiles = []
        for profile in data.profiles:
            snapshot = {'schema_version': 1, **profile.model_dump(), 'speed_unit': 'NONSPACE_UNICODE_CODEPOINTS_PER_MINUTE'}
            profiles.append({**snapshot, 'digest': digest(snapshot)})
        if profiles[0]['digest'] == profiles[1]['digest']:
            raise ValueError('select two distinct explicit reader profiles')
        findings = []
        for observation in data.observations:
            evidence = validate_evidence([observation.evidence.model_dump()], chapters)
            findings.append({'code': 'AUTHOR_READER_OBSERVATION', 'category': 'READABILITY', 'severity': 'INFO',
                'origin': 'AUTHOR_ENTERED', 'audience_profile_index': observation.profile_index,
                'explanation': observation.observation, 'suggestion': observation.suggestion,
                'boundary': BOUNDARY, 'evidence': evidence, 'decision': 'PENDING',
                # Exact source AND profile identity: never cross-reader or cross-version suppression.
                'issue_key': digest(['audience-author-v1', identity, sources, profiles[observation.profile_index], observation.model_dump()])})
        run_id = str(uuid5(NAMESPACE_URL, digest(['audience-author-v1', nid, scope, actor, sources, data.model_dump()])))
        units = sum(not c.isspace() for c in chapter.get('content', ''))
        audience = {'schema_version': 1, 'profiles': profiles, 'chapter_id': data.chapter_id,
            'chapter_version': data.expected_version, 'source_digest': sources[data.chapter_id]['digest'],
            'comparison': data.comparison, 'comparison_origin': 'AUTHOR_ENTERED',
            'measurements': [{'profile_index': i, 'nonspace_characters': units,
                'estimated_seconds': units * 60 / p.reading_speed} for i, p in enumerate(data.profiles)],
            'boundary': BOUNDARY, 'coverage': 'CHAPTER_ONLY_PARTIAL_DIF11'}
        receipt = new_row(nid, scope, actor, {'status': 'COMPLETED', 'sources': sources,
            'context_digest': None, 'audience_project_incarnation': identity, 'finding_ids': [], 'request': data.model_dump(), 'audience': audience,
            'privacy_level': 'LOCAL_ONLY', 'model_called': False, 'verification': 'AUTHOR_ENTERED_AND_LOCAL_ARITHMETIC',
            'abstentions': ['未生成模拟读者意见；题材经验、年龄层与语言习惯只记录作者参数，不推断理解能力。'],
            'review_storage': j.creation.store.storage_mode, 'receipt_storage': j.store.storage_mode})
        receipt['id'] = run_id
        with j.creation.store._lock, workspace_mutation(j.creation.store.root, 'creation-workbench'), owner.existing_owner_only(), ExitStack() as lifecycle:
            with j.store.transaction(nid, scope) as state:
                lifecycle.enter_context(owner.owner_lease(nid))
                if owner.incarnation(nid) != identity: raise StaleSourceError('AUDIENCE_PROJECT_CHANGED')
                j._fresh(nid, scope, receipt); guard()
                existing = collection(state, j.RUNS).get(run_id)
                if existing: return j._public(nid, scope, existing)
                if len(collection(state, j.RUNS)) >= 200: raise ValueError('judge receipt limit reached')
                rows = j.creation._rows('review_threads')
                for index, finding in enumerate(findings):
                    rid = str(uuid5(UUID(run_id), str(index)))
                    receipt['finding_ids'].append(rid)
                    existing = next((row for row in rows if row['id'] == rid), None)
                    if existing:
                        if not j.creation._match(existing, nid, scope): raise ValueError('review thread scope conflict')
                        continue
                    proof = finding['evidence'][0]
                    rows.append({'id': rid, 'novel_id': nid, 'scope': deepcopy(scope),
                        'anchor': {'chapter_id': proof['chapter_id'], 'chapter_version': proof['chapter_version'],
                                   'quote': proof['quote'], 'content_sha256': sources[data.chapter_id]['digest']},
                        'status': 'OPEN', 'version': 1, 'created_at': now(), 'updated_at': now(),
                        'messages': [{'id': str(uuid5(UUID(rid), 'author')), 'actor_id': actor, 'text': finding['explanation'], 'at': now()}],
                        'history': [{'action': 'AUDIENCE_AUTHOR_CREATED', 'actor_id': actor, 'at': now()}],
                        'narrative_judge': {**finding, 'run_id': run_id, 'privacy_level': 'LOCAL_ONLY'}})
                j._fresh(nid, scope, receipt); guard()
                j.creation.store._write('review_threads', rows)
                collection(state, j.RUNS)[run_id] = receipt
        return j._public(nid, scope, receipt)


@contextmanager
def audience_review_lease(judge, nid, scope, rid):
    """Hold original lifecycle through audience disposition; leave legacy unchanged."""
    row = judge.creation._find(judge._threads(nid, scope), nid, scope, rid)
    run_id = row.get('narrative_judge', {}).get('run_id')
    receipt = judge.store.read(nid, scope)['collections'].get(judge.RUNS, {}).get(run_id, {})
    if not receipt.get('audience'):
        yield
        return
    owner = CreativeProjectStore(judge.store)
    with owner.existing_owner_only(), ExitStack() as lifecycle:
        with judge.store.transaction(nid, scope):
            identity = lifecycle.enter_context(owner.owner_lease(nid))
            if receipt.get('audience_project_incarnation') != identity:
                raise StaleSourceError('AUDIENCE_PROJECT_CHANGED')
            yield
