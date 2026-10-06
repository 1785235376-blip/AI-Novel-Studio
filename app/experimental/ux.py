"""Scoped, local-only workspace metadata and read-only navigation projections.

This is not a job executor, editor or permission authority. Readers are injected
by the composition root, re-authorized on every request, and never persisted as
another domain database. Bounded lexical indexes are private to actor + scope.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from threading import RLock, Event
from datetime import datetime, timezone
from uuid import uuid4
from typing import Callable, Literal

from fastapi import HTTPException
from pydantic import Field

from .common import DomainService, StaleSourceError, change_row, new_row
from .planning import StrictModel, digest
from .search_sources import SearchSource, chapter_manifest, project_ids
from ..services.v1_capability_service import CapabilityVersionConflict

FEATURES = frozenset({'overview', 'editor', 'creation', 'story', 'history', 'workflow', 'screenplay', 'assets',
                      'exports', 'knowledge', 'research', 'agents', 'diagnostics', 'settings',
                      'semantic_import_v2', 'audiobook_v2', 'cover_storyboard_generation'})
MAX_RECORDS = 2000
MAX_CHARACTERS = 2_000_000


class Anchor(StrictModel):
    offset: int = Field(default=0, ge=0, le=2_000_000)
    scroll: int = Field(default=0, ge=0, le=10_000_000)


class Layout(StrictModel):
    density: Literal['normal', 'advanced'] = 'normal'
    section: Literal['resume', 'search', 'tasks', 'diagnostics', 'guide'] = 'resume'
    show_failed_only: bool = False
    search_query: str = Field(default='', max_length=160)
    search_kind: Literal['', 'novel', 'chapter', 'volume', 'scene', 'character', 'location', 'timeline', 'foreshadowing', 'finding', 'organization', 'rule', 'story_graph', 'asset', 'workflow', 'review', 'task'] = ''
    search_scope: Literal['project', 'authorized'] = 'project'
    search_tag: str = Field(default='', max_length=80)
    search_recent_days: int = Field(default=0, ge=0, le=3650)
    search_unresolved: bool = False
    search_fulltext: bool = False
    search_current_chapter: bool = False
    task_query: str = Field(default='', max_length=160)


class WorkspaceView(StrictModel):
    focus_active: bool = False
    references_visible: bool = True


class ResumeIn(StrictModel):
    expected_version: int = Field(default=0, ge=0)
    chapter_id: str | None = Field(default=None, max_length=160)
    chapter_version: int | None = Field(default=None, ge=1)
    anchor: Anchor = Field(default_factory=Anchor)
    layout: Layout = Field(default_factory=Layout)
    view: WorkspaceView = Field(default_factory=WorkspaceView)
    stopping_note: str = Field(default='', max_length=2000)
    pinned_chapter_ids: list[str] = Field(default_factory=list, max_length=8)
    recent_commands: list[str] = Field(default_factory=list, max_length=12)
    guide_dismissed: bool = False


class VersionIn(StrictModel):
    expected_version: int = Field(ge=0)


class ResumeResolveIn(VersionIn):
    open_current: bool = False


class ResolveIn(StrictModel):
    kind: Literal['novel', 'chapter', 'volume', 'scene', 'character', 'location', 'timeline', 'foreshadowing', 'finding', 'organization', 'rule', 'story_graph', 'asset', 'workflow', 'review', 'task']
    novel_id: str | None = Field(default=None, max_length=160)
    branch_id: str | None = Field(default=None, max_length=160)
    id: str = Field(min_length=1, max_length=160)
    revision: str = Field(min_length=1, max_length=80)
    offset: int = Field(default=0, ge=0, le=2_000_000)
    open_current: bool = False


class TaskCancelIn(StrictModel):
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')


class DiagnosticIn(StrictModel):
    include_environment: bool = True
    include_task_states: bool = True
    include_error_codes: bool = True


class DiagnosticExportIn(DiagnosticIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


@dataclass(frozen=True)
class ReadContext:
    novel_id: str
    scope: dict
    actor: str
    # Captured request authority; credentials never enter the index/metadata.
    token: str | None = None
    branch: str | None = None


@dataclass(frozen=True)
class TaskReader:
    name: str
    label: str
    feature: str
    read: Callable[[ReadContext], object]
    flag: str | None = None
    cancel: Callable[..., object] | None = None
    cancel_states: frozenset[str] = frozenset({'QUEUED', 'PENDING', 'RUNNING', 'WORKING', 'PROCESSING', 'GENERATING'})


STAGES = {'ANALYZING': '分析中', 'NEEDS_REVIEW': '需要审核', 'QUEUED': '排队', 'PENDING': '等待', 'DRAFT': '草稿', 'READY': '就绪',
          'RUNNING': '运行中', 'WORKING': '运行中', 'PROCESSING': '处理中',
          'PREPARED': '准备就绪', 'GENERATING': '生成中', 'SETTLING': '结算确认中',
          'ACCEPTING': '接受处理中', 'ACCEPTANCE_UNCERTAIN': '接受结果未知',
          'VALIDATED': '待审核', 'REVIEW': '待审核', 'AWAITING_REVIEW': '待审核',
          'COMPLETED': '已完成', 'SUCCEEDED': '已完成', 'COMMITTED': '已应用', 'ACCEPTED': '已接受',
          'APPROVED': '已批准', 'REJECTED': '已拒绝', 'FAILED': '失败', 'CANCELLED': '已取消',
          'CANCELLING': '取消中', 'PAUSED': '已暂停', 'UNKNOWN': '结果未知',
          'WAITING_APPROVAL': '等待批准', 'PENDING_REVIEW': '待审核', 'REVIEW_REQUIRED': '需要审核',
          'RESULT_READY': '结果就绪', 'PROPOSED': '建议待审', 'PLANNED': '已规划',
          'PARTIAL': '部分完成', 'STALE': '来源过期', 'APPLYING': '应用中', 'APPROVING': '批准处理中'}
SAFE_CODES = frozenset({'TIMEOUT', 'CANCELLED', 'PERMISSION_DENIED', 'VERSION_CONFLICT',
    'SOURCE_STALE', 'ADAPTER_REQUIRED', 'PROVIDER_UNAVAILABLE', 'NETWORK_ERROR',
    'EXPERIMENTAL_SOURCE_STALE', 'EXPERIMENTAL_VERSION_CONFLICT', 'MEDIA_TASK_TRANSITION_INVALID'})



COORDINATE = 'EDITOR_TEXT_CODEPOINT'


def chapter_text(row):
    """Match editor textBetween/getText with one newline per text block.

    Offsets are Unicode codepoints, not Markdown bytes or ProseMirror positions.
    Nested list/quote textblocks retain their order; marks add no characters.
    """
    document = row.get('document')
    if not isinstance(document, dict) or document.get('type') != 'doc':
        return str(row.get('content', ''))
    def inline(node):
        if node.get('type') == 'text':
            return str(node.get('text', ''))
        if node.get('type') == 'hardBreak':
            return '\n'
        return ''.join(inline(child) for child in node.get('content', []) if isinstance(child, dict))
    def blocks(node):
        if node.get('type') in {'paragraph', 'heading', 'codeBlock'}:
            yield inline(node)
        else:
            for child in node.get('content', []):
                if isinstance(child, dict):
                    yield from blocks(child)
    return '\n'.join(blocks(document))


def literal_offset(text, folded_query):
    """Case folding may expand a character (ß → ss); keep source coordinates."""
    folded = text.casefold()
    index = folded.find(folded_query)
    if index < 0:
        return 0
    if len(folded) == len(text):
        return index
    consumed = 0
    for position, character in enumerate(text):
        if consumed >= index:
            return position
        consumed += len(character.casefold())
    return len(text)


def safe_code(value):
    # Codes are enums, not regex-approved arbitrary strings. A credential can
    # consist entirely of valid code characters and must still never be copied.
    return value if isinstance(value, str) and value in SAFE_CODES else 'UNCLASSIFIED'


FEATURE_OWNED_GENERATION = {
    "declarative_agent": ("declarative_agents_v2", "声明式工作流候选"),
    "story_simulator_model": ("story_simulator_v2", "剧情模拟候选"),
    "multilingual_translation": ("multilingual_editions_v2", "语言版本译文候选"),
    "narrative_judge_model": ("narrative_quality_judge_v2", "叙事评审意见"),
    "style_analysis_model": ("style_dna_v2", "文风模型意见"),
    "revision_comparison_model": ("revision_intelligence_v2", "版本语义比较"),
}


def task_identifier(value):
    """Bounded provider/model identities only; never echo URLs or credentials."""
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+ -]{0,159}', value):
        return None
    if '://' in value or value.lower().startswith(('sk-', 'bearer ', 'token ', 'password', 'secret')):
        return None
    return value


def projected_task(reader, row):
    error = row.get('error_code') or (row.get('error', {}).get('code') if isinstance(row.get('error'), dict) else None)
    status = str(row.get('status', 'UNKNOWN')).upper()
    if row.get('recovery_required') or row.get('recoverable'):
        status = 'UNKNOWN'
    if status not in STAGES:
        status = 'UNKNOWN'
    progress = None
    total, completed = row.get('total_chunks'), row.get('completed_chunks')
    if type(total) is int and type(completed) is int and 0 <= completed <= total and total > 0:
        progress = {'completed': completed, 'total': total, 'unit': '分块'}
    history = [{'version': item.get('version'), 'status': str(item.get('status', 'UNKNOWN')).upper()}
               for item in row.get('history', [])[-10:] if isinstance(item, dict)
               and str(item.get('status', '')).upper() in STAGES]
    source = {}
    owner = FEATURE_OWNED_GENERATION.get(row.get('experimental_origin')) if reader.name == 'author_generation' else None
    if owner:
        source = {'source': {'kind': 'feature', 'id': str(row['id']), 'feature': owner[0]}}
        if row.get('experimental_origin') in {'style_analysis_model', 'revision_comparison_model'}:
            source['source'].update(task_authority='style_model_job' if row['experimental_origin'] == 'style_analysis_model' else 'revision_model_job',
                                    chapter_id=row.get('chapter_id'), version=row.get('base_chapter_version'))
    if (not owner and reader.name == 'author_generation' and isinstance(row.get('chapter_id'), str)
            and row['chapter_id'] and type(row.get('base_chapter_version')) is int
            and row['base_chapter_version'] > 0):
        source = {'source': {'kind': 'generation', 'id': str(row['id']),
                  'chapter_id': row['chapter_id'], 'version': row['base_chapter_version']}}
    provider = task_identifier(row.get('provider'))
    model = task_identifier(row.get('model'))
    requested_provider = task_identifier(row.get('requested_provider') or row.get('provider_id'))
    requested_model = task_identifier(row.get('requested_model') or row.get('model_id'))
    if not source:
        source = {'source': {'kind': 'feature', 'id': str(row['id']), 'feature': reader.feature, 'task_authority': reader.name}}
        if reader.name == 'review_inbox': source['source'].update(id=row['review_id'], parent_id=row['review_domain'])
        if reader.name == 'workflows' and isinstance(row.get('workflow_id'), str): source['source']['parent_id'] = row['workflow_id']
        if reader.name == 'motion' and isinstance(row.get('screenplay_id'), str): source['source']['parent_id'] = row['screenplay_id']
    cancel_allowed = bool(reader.cancel and str(row.get('status', '')).upper() in reader.cancel_states and not row.get('safe_batch_id'))
    result = {**source, 'id': str(row['id']), 'authority': reader.name, 'label': owner[1] if owner else reader.label,
            'status': status, 'stage_label': STAGES[status], 'version': row.get('version'),
            'feature': owner[0] if owner else reader.feature, 'progress': progress, 'history': history,
            'stale': bool(row.get('stale')), 'cost': {'estimate': None, 'actual': None, 'state': 'UNKNOWN'},
            'error_code': safe_code(error) if error else None,
            'provider_id': provider or requested_provider, 'model_id': model or requested_model,
            'route_state': 'OBSERVED' if reader.name == 'author_generation' and provider and model else 'REQUESTED' if (provider or requested_provider) and (model or requested_model) else 'UNKNOWN',
            'actions': ['open_source'] + (['cancel'] if cancel_allowed else []),
            'action_limits': {'cancel': None if cancel_allowed else 'ORIGIN_COORDINATOR_REQUIRED' if row.get('safe_batch_id') else 'TERMINAL_OR_UNSUPPORTED' if reader.cancel else 'SOURCE_AUTHORITY_ONLY',
                              'retry': 'SOURCE_PREFLIGHT_REQUIRED', 'resume': 'SOURCE_RECOVERY_REQUIRED', 'review': 'SOURCE_REVIEW_REQUIRED'},
            'retry_policy': 'SOURCE_AUTHORITY_ONLY',
            'lifecycle': '面板关闭不取消任务；继续执行和重启恢复取决于原任务服务。'}
    result['revision'] = digest(result)
    return result


class WorkspaceToolsService(DomainService):
    RESUMES = 'workspace_resumes_v2'

    def __init__(self, store, novels, chapters, *, chapter_reader=None, entity_readers=None, task_readers=None, focus_reader=None, search_candidates=None, finding_reader=None):
        super().__init__(store, novels, chapters)
        self.chapter_reader = chapter_reader
        self.entity_readers = entity_readers or {}
        self.task_readers = tuple(task_readers or ())
        self.focus_reader = focus_reader
        self.search_candidates = search_candidates
        self.finding_reader = finding_reader
        self._search_operations = OrderedDict()
        self._indexes = OrderedDict()
        self._index_lock = RLock()

    @staticmethod
    def _owner(actor):
        if not isinstance(actor, str) or not actor:
            raise ValueError('trusted actor required')
        return hashlib.sha256(actor.encode()).hexdigest()

    def chapter_rows(self, ctx):
        self.novels.get(ctx.novel_id)
        if self.chapter_reader:
            rows = self.chapter_reader(ctx)
        elif ctx.scope.get('mode') == 'local':
            rows = self.chapters.list(ctx.novel_id)
        else:
            # Never replace missing branch evidence with the base manuscript.
            return []
        return [row for row in rows if row.get('novel_id') == ctx.novel_id
                and not row.get('is_archived')
                and (ctx.scope.get('mode') == 'local' and not row.get('branch_id')
                     or row.get('branch_id') == ctx.scope.get('branch_id'))]

    def _chapter(self, ctx, cid):
        row = next((r for r in self.chapter_rows(ctx) if r.get('id') == cid), None)
        if row is None:
            raise FileNotFoundError(cid)
        return row

    def _resume_row(self, ctx, doc=None):
        doc = doc if doc is not None else self.store.read(ctx.novel_id, ctx.scope)
        row = doc['collections'].get(self.RESUMES, {}).get(self._owner(ctx.actor))
        if row and (row.get('novel_id') != ctx.novel_id or row.get('scope') != ctx.scope or row.get('created_by') != ctx.actor):
            raise ValueError('invalid workspace metadata owner')
        return row

    def _focus(self, ctx, require_flag):
        # U04 remains the only preferences/reference authority. This projection
        # never writes it or persists a duplicate pin list/reference body.
        if not self.focus_reader:
            return None
        try:
            require_flag('writing_focus_v2')
            value = self.focus_reader(ctx)
            if value['preferences'].get('recovery_required'):
                return None
            return value
        except Exception:
            return None

    @staticmethod
    def _pending(task):
        if task['status'] in {'ACCEPTED', 'APPROVED', 'COMMITTED', 'REJECTED', 'CANCELLED', 'SUCCEEDED'}:
            return False
        return task['status'] != 'COMPLETED' or task['authority'] == 'author_generation'

    def resume(self, ctx, require_flag=lambda flag: None, reauthorize=lambda: None):
        row = deepcopy(self._resume_row(ctx))
        if not row:
            return {'item': None, 'availability': 'EMPTY'}
        row.pop('history', None)
        state = 'READY'
        if row.get('chapter_id'):
            try:
                chapter = self._chapter(ctx, row['chapter_id'])
                state = 'READY' if digest(chapter) == row.get('chapter_digest') else 'STALE'
                row['chapter_title'] = chapter.get('title', '')
                row['current_chapter_version'] = chapter['version']
            except FileNotFoundError:
                state = 'UNAVAILABLE'
        # Corrupt layout is isolated from writing metadata and can be reset.
        try:
            row['layout'] = Layout.model_validate(row.get('layout')).model_dump()
            row['layout_recovery_required'] = False
        except ValueError:
            row['layout'] = Layout().model_dump()
            row['layout_recovery_required'] = True
        try:
            row['view'] = WorkspaceView.model_validate(row.get('view', {})).model_dump()
        except ValueError:
            row['view'] = WorkspaceView().model_dump()
            row['layout_recovery_required'] = True
        focus = self._focus(ctx, require_flag)
        captured_version = row.pop('focus_preferences_version', None)
        row['focus_state'] = ('UNAVAILABLE' if focus is None else 'NOT_CAPTURED' if captured_version is None
                              else 'READY' if captured_version == focus['preferences']['version'] else 'CHANGED')
        row['reference_recovery_required'] = bool(focus and any(pin['state'] != 'READY' for pin in focus['pins']['items']))
        # Re-read original services before disclosing remembered IDs or status.
        references = row.pop('pending_task_refs', [])
        current = self.tasks(ctx, require_flag) if references else {'items': [], 'unavailable': [], 'truncated': False}
        by_id = {(task['authority'], task['id']): task for task in current['items']}
        row['pending_tasks'] = [by_id[(ref['authority'], ref['id'])] for ref in references
                                if (ref['authority'], ref['id']) in by_id]
        row['tasks_recovery_required'] = len(row['pending_tasks']) != len(references) or bool(current['unavailable'])
        row['tasks_capture_partial'] = bool(row.get('tasks_capture_partial')) or current['truncated']
        row.pop('chapter_digest', None)
        reauthorize()
        return {'item': row, 'availability': state}

    def save_resume(self, ctx, body, require_flag=lambda flag: None, reauthorize=lambda: None):
        data = ResumeIn.model_validate(body).model_dump()
        version = data.pop('expected_version')
        if any(command not in FEATURES for command in data['recent_commands']):
            raise ValueError('unsupported navigation command')
        if data['chapter_id']:
            chapter = self._chapter(ctx, data['chapter_id'])
            if chapter['version'] != data['chapter_version']:
                raise StaleSourceError('chapter version changed; save the current workspace explicitly')
            if data['anchor']['offset'] > len(chapter_text(chapter)):
                raise ValueError('anchor lies outside chapter')
            data['chapter_digest'] = digest(chapter)
        elif data['chapter_version'] is not None or data['anchor']['offset'] or data['anchor']['scroll']:
            raise ValueError('anchor requires a chapter')
        for cid in data['pinned_chapter_ids']:
            self._chapter(ctx, cid)
        focus = self._focus(ctx, require_flag)
        data['focus_preferences_version'] = focus['preferences']['version'] if focus else None
        tasks = self.tasks(ctx, require_flag)
        pending = [task for task in tasks['items'] if self._pending(task)]
        data['pending_task_refs'] = [{'authority': task['authority'], 'id': task['id']} for task in pending[:50]]
        data['tasks_capture_partial'] = len(pending) > 50 or tasks['truncated'] or bool(tasks['unavailable'])
        reauthorize()
        if data['chapter_id'] and digest(self._chapter(ctx, data['chapter_id'])) != data['chapter_digest']:
            raise StaleSourceError('chapter changed during workspace capture')
        with self.store.transaction(ctx.novel_id, ctx.scope) as doc:
            row = self._resume_row(ctx, doc)
            reauthorize()
            if row:
                change_row(row, ctx.actor, version, lambda value: value.update(data))
                row['history'] = row['history'][-20:]
            else:
                if version != 0:
                    raise CapabilityVersionConflict({'version': 0})
                row = new_row(ctx.novel_id, ctx.scope, ctx.actor, data)
                doc['collections'].setdefault(self.RESUMES, {})[self._owner(ctx.actor)] = row
        return self.resume(ctx, require_flag, reauthorize)

    def reset_layout(self, ctx, expected_version, require_flag=lambda flag: None, reauthorize=lambda: None):
        with self.store.transaction(ctx.novel_id, ctx.scope) as doc:
            row = self._resume_row(ctx, doc)
            if not row:
                raise FileNotFoundError('resume')
            reauthorize()
            change_row(row, ctx.actor, expected_version, lambda value: value.update(layout=Layout().model_dump(), view=WorkspaceView().model_dump()))
            row['history'] = row['history'][-20:]
        return self.resume(ctx, require_flag, reauthorize)

    def resolve_resume(self, ctx, body, require_flag=lambda flag: None, reauthorize=lambda: None):
        value = ResumeResolveIn.model_validate(body)
        row = self._resume_row(ctx)
        if not row or not row.get('chapter_id'):
            raise FileNotFoundError('resume chapter')
        if row['version'] != value.expected_version:
            raise CapabilityVersionConflict({'version': row['version']})
        chapter = self._chapter(ctx, row['chapter_id'])
        stale = digest(chapter) != row.get('chapter_digest')
        if stale and not value.open_current:
            raise StaleSourceError('saved chapter changed; explicitly open its current version')
        snapshot = self.resume(ctx, require_flag)['item']
        if not snapshot or snapshot['version'] != value.expected_version:
            raise CapabilityVersionConflict({'version': snapshot['version'] if snapshot else 0})
        # Return only a current U04 projection when the saved authority version
        # still matches. Changed pins/preferences require an explicit fresh save.
        focus = self._focus(ctx, require_flag)
        workspace = {key: deepcopy(snapshot[key]) for key in ('layout', 'view', 'focus_state', 'reference_recovery_required')}
        if focus and row.get('focus_preferences_version') == focus['preferences']['version']:
            workspace['focus_preferences'] = focus['preferences']['preferences']
        else:
            workspace['focus_state'] = 'CHANGED' if focus else 'UNAVAILABLE'
        reauthorize()
        return {'kind': 'chapter', 'id': chapter['id'], 'feature': 'editor', 'version': chapter['version'],
                'anchor': {'offset': 0, 'scroll': 0} if stale else deepcopy(row['anchor']), 'stale': stale, 'coordinate': COORDINATE,
                'workspace': workspace}

    def resume_history(self, ctx):
        row = self._resume_row(ctx)
        return {'items': [{k: deepcopy(r.get(k)) for k in ('version', 'updated_at', 'chapter_id', 'chapter_version', 'stopping_note')}
                          for r in (row or {}).get('history', [])]}

    @staticmethod
    def _visible_search_row(ctx, row):
        return (isinstance(row, dict) and bool(row.get('id')) and not row.get('is_archived')
                and str(row.get('status', '')).upper() != 'ARCHIVED'
                and not row.get('hidden') and not row.get('secret')
                and str(row.get('visibility', '')).upper() not in {'PRIVATE', 'SECRET', 'DENIED'}
                and (not row.get('branch_id') if ctx.scope.get('mode') == 'local'
                     else row.get('branch_id') == ctx.scope.get('branch_id')))

    @staticmethod
    def _search_document(ctx, kind, row):
        strings = lambda name: [v[:160] for v in row.get(name, [])[:20] if isinstance(v, str)] if isinstance(row.get(name), list) else []
        doc = {'kind': kind, 'id': str(row['id']), 'novel_id': ctx.novel_id, 'branch_id': ctx.branch,
               'title': str(row.get('name') or row.get('title') or row.get('label') or row.get('message') or kind)[:500],
               'text': chapter_text(row) if kind == 'chapter' else '', 'version': row.get('version'),
               'feature': 'editor' if kind == 'chapter' else row.get('feature', 'story'),
               'aliases': strings('aliases'), 'tags': strings('tags'), 'updated_at': str(row.get('updated_at') or ''),
               'status': str(row.get('status', '')), 'coordinate': COORDINATE}
        if kind in {'organization', 'rule', 'story_graph', 'asset', 'workflow'}:
            doc['source'] = deepcopy(row['source_navigation'])
        if kind == 'novel':
            doc['source'] = {'kind': 'feature', 'id': row['id'], 'feature': 'overview'}
        elif kind in {'volume', 'scene', 'character', 'location', 'timeline', 'foreshadowing'}:
            doc['source'] = {'kind': 'feature', 'id': row['id'], 'feature': 'story', 'record_kind': kind}
        if kind == 'task':
            doc['source'] = deepcopy(row.get('source') or {'kind': 'feature', 'id': row['id'], 'feature': row['feature']})
        # The digest and cache contain only this allowlisted searchable projection.
        # A chapter document/style change remains version fenced by the authority.
        doc['revision'] = digest({'projection': doc, 'source_digest': digest(row)})
        return doc

    def _search_manifest(self, ctx, check, require_flag):
        novel = self.novels.get(ctx.novel_id)
        sources = chapter_manifest(self, ctx, check)
        projected_rows = 0
        incremental = sources is not None
        if sources is None:
            sources = []
            for row in self.chapter_rows(ctx):
                check()
                if self._visible_search_row(ctx, row):
                    projected_rows += 1
                    doc = self._search_document(ctx, 'chapter', row)
                    sources.append(SearchSource('chapter:' + doc['id'], doc['revision'], lambda doc=doc: doc))
        if ctx.scope.get('mode') == 'local' and self._visible_search_row(ctx, novel):
            doc = self._search_document(ctx, 'novel', novel)
            sources.append(SearchSource('novel:' + doc['id'], doc['revision'], lambda doc=doc: doc))
            projected_rows += 1
        for kind, dataset in (('character', 'characters'), ('location', 'locations'), ('foreshadowing', 'foreshadowing')):
            rows = (self.entity_readers[kind](ctx) if kind in self.entity_readers else
                    self.novels.data_set(ctx.novel_id, dataset) if ctx.scope.get('mode') == 'local' else [])
            for row in rows:
                check()
                if not self._visible_search_row(ctx, row): continue
                projected_rows += 1
                doc = self._search_document(ctx, kind, row)
                sources.append(SearchSource(kind + ':' + doc['id'], doc['revision'], lambda doc=doc: doc))
        for kind, dataset in (('volume', 'volumes'), ('scene', 'scenes'), ('timeline', 'timeline')):
            if kind in self.entity_readers:
                rows = self.entity_readers[kind](ctx)
            elif ctx.scope.get('mode') == 'local' and hasattr(self.novels, 'novels'):
                rows = self.novels.data_set(ctx.novel_id, dataset)
            else:
                rows = []
            for row in rows:
                check()
                if not self._visible_search_row(ctx, row): continue
                projected_rows += 1
                doc = self._search_document(ctx, kind, row)
                sources.append(SearchSource(kind + ':' + doc['id'], doc['revision'], lambda doc=doc: doc))
        for kind in ('organization', 'rule', 'story_graph', 'asset', 'workflow'):
            reader = self.entity_readers.get(kind)
            if reader is None: continue
            try:
                rows = reader(ctx)
            except HTTPException as exc:
                if exc.status_code in {401, 403, 404}: continue
                raise
            for row in rows:
                check()
                if not self._visible_search_row(ctx, row): continue
                projected_rows += 1
                doc = self._search_document(ctx, kind, row)
                sources.append(SearchSource(kind + ':' + doc['id'], doc['revision'], lambda doc=doc: doc))
        if self.finding_reader:
            for row in self.finding_reader(ctx):
                check()
                if row.get('project_id') != ctx.novel_id or not self._visible_search_row(ctx, row): continue
                projected_rows += 1
                doc = self._search_document(ctx, 'finding', {**row, 'feature': 'story',
                    'title': row.get('description') or row.get('message') or row.get('finding_type') or '连续性发现',
                    'updated_at': row.get('resolved_at') or row.get('created_at') or ''})
                sources.append(SearchSource('finding:' + doc['id'], doc['revision'], lambda doc=doc: doc))
        if self.task_readers:
            for row in self.tasks(ctx, require_flag)['items']:
                check()
                projected_rows += 1
                kind = 'review' if row['authority'] == 'review_inbox' else 'task'
                doc = self._search_document(ctx, kind, {**row, 'id': row['authority'] + ':' + row['id']})
                # Source navigation must retain the original ID, not the index key.
                doc['source'] = deepcopy(row.get('source') or {'kind': 'feature', 'id': row['id'], 'feature': row['feature']})
                doc['revision'] = digest({k: v for k, v in doc.items() if k != 'revision'})
                sources.append(SearchSource(kind + ':' + doc['id'], doc['revision'], lambda doc=doc: doc))
        return sources, incremental, projected_rows

    def candidates(self, ctx):
        return (self.search_candidates(ctx, self) if self.search_candidates else
                [(nid, None) for nid in project_ids(self)] if ctx.scope.get('mode') == 'local' else [])

    @staticmethod
    def _index_key(ctx):
        return digest([ctx.novel_id, ctx.scope, ctx.actor])

    def discard_search(self, ctx):
        with self._index_lock:
            self._indexes.pop(self._index_key(ctx), None)

    def cancel_search(self, ctx, request_id):
        # Bounded pre-start tombstones close the HTTP start/cancel race. No token
        # is retained; a different actor/branch cannot cancel this operation.
        key = (self._index_key(ctx), request_id)
        with self._index_lock:
            event = self._search_operations.setdefault(key, Event()); event.set()
            self._search_operations.move_to_end(key)
            while len(self._search_operations) > 256:
                self._search_operations.popitem(last=False)
        return {'state': 'CANCELLED', 'request_id': request_id}

    def search_cancelled(self, ctx, request_id):
        with self._index_lock:
            event = self._search_operations.get((self._index_key(ctx), request_id))
            return bool(event and event.is_set())

    def search(self, ctx, query='', kind='', chapter_id=None, rebuild=False, *, tag='', recent_days=0,
               unresolved=False, fulltext=False, offset=0, request_id=None, reauthorize=lambda: None,
               require_flag=lambda flag: None, cancelled=lambda: False, limit=50):
        if (len(query) > 160 or len(tag) > 80 or kind not in {'', 'novel', 'chapter', 'volume', 'scene', 'character', 'location', 'timeline', 'foreshadowing', 'finding', 'organization', 'rule', 'story_graph', 'asset', 'workflow', 'review', 'task'}
            or not 0 <= recent_days <= 3650 or not 0 <= offset <= MAX_RECORDS):
            raise ValueError('invalid search filter')
        key = self._index_key(ctx); operation = (key, request_id or str(uuid4()))
        with self._index_lock:
            event = self._search_operations.setdefault(operation, Event())
            old = {} if rebuild else dict(self._indexes.get(key, {}))
        def check():
            if event.is_set() or cancelled():
                raise HTTPException(409, {'code': 'SEARCH_CANCELLED'})
        check(); reauthorize()
        try:
            sources, incremental, projected_rows = self._search_manifest(ctx, check, require_flag)
            current, size, changed, reads, chapter_reads, truncated = {}, 0, 0, 0, 0, False
            for source in sources:
                check()
                if len(current) >= MAX_RECORDS:
                    truncated = True; break
                cached = old.get(source.key)
                if cached and cached['_stamp'] == source.stamp:
                    doc = cached
                else:
                    row = source.read()
                    # Project title is already read by the mandatory project
                    # access/manifest lookup; count it in projection_rows_scanned,
                    # not as an additional source-body read.
                    reads += int(not source.key.startswith('novel:'))
                    if source.key.startswith('chapter:') and 'kind' not in row:
                        chapter_reads += 1
                        if row.get('novel_id') != ctx.novel_id or not self._visible_search_row(ctx, row): continue
                        doc = self._search_document(ctx, 'chapter', row)
                    else: doc = row
                    doc = {**doc, '_stamp': source.stamp,
                           '_search': '\n'.join([doc['title'], *doc['aliases'], doc['id'], doc['text']]).casefold()}
                    changed += 1
                size += len(doc['text']) + len(doc['title']) + sum(map(len, doc['aliases']))
                if size > MAX_CHARACTERS:
                    truncated = True; break
                current[source.key] = doc
            # Validate metadata again before committing a replacement. On cancel,
            # source races or revoked permissions the prior cache is untouched.
            latest, _, latest_projected = self._search_manifest(ctx, check, require_flag)
            if [(r.key, r.stamp) for r in latest] != [(r.key, r.stamp) for r in sources]:
                raise StaleSourceError('sources changed while indexing; retry the current search')
            reauthorize(); check()
            query, tag = query.strip().casefold(), tag.strip().casefold()
            cutoff = datetime.now(timezone.utc).timestamp() - recent_days * 86400
            results = []
            for doc in current.values():
                check()
                if kind and doc['kind'] != kind or chapter_id and (doc['kind'] != 'chapter' or doc['id'] != chapter_id): continue
                if tag and tag not in [value.casefold() for value in doc['tags']]: continue
                if unresolved and doc['status'].upper() not in {'OPEN', 'UNRESOLVED', 'PENDING', 'FAILED', 'UNKNOWN', 'WAITING_APPROVAL', 'PENDING_REVIEW', 'REVIEW_REQUIRED'}: continue
                if recent_days:
                    try: stamp = datetime.fromisoformat(doc['updated_at'].replace('Z', '+00:00'))
                    except (ValueError, TypeError): continue
                    if stamp.tzinfo is None or stamp.timestamp() < cutoff: continue
                if query and query not in (doc['text'].casefold() if fulltext else doc['_search']): continue
                title = doc['title'].casefold(); aliases = [value.casefold() for value in doc['aliases']]
                rank = 0 if query == title else 1 if query in aliases else 2 if title.startswith(query) else 3 if any(query in name for name in aliases) else 4
                position = literal_offset(doc['text'], query) if query else 0
                results.append((rank, {k: deepcopy(v) for k, v in doc.items() if k not in {'text', '_search', '_stamp', 'source'}} |
                                {'offset': position, 'snippet': doc['text'][max(0, position - 35):position + 125]}))
            results.sort(key=lambda pair: (pair[0], pair[1]['title'], pair[1]['kind'], pair[1]['id']))
            reauthorize(); check()
            with self._index_lock:
                check()
                self._indexes[key] = current; self._indexes.move_to_end(key)
                while len(self._indexes) > 8: self._indexes.popitem(last=False)
            return {'items': [row for _, row in results[offset:offset + limit]], 'mode': 'LITERAL_LEXICAL', 'model_called': False,
                    'truncated': truncated or len(results) > offset + limit, 'index_truncated': truncated,
                    'match_count': len(results), 'next_offset': offset + limit if len(results) > offset + limit else None,
                    'updated_documents': changed, 'source_rows_read': reads, 'chapter_bodies_read': chapter_reads,
                    'projection_rows_scanned': projected_rows + latest_projected, 'metadata_checks': len(sources) + len(latest),
                    'incremental_chapters': incremental, 'limit': limit,
                    'branch_sources_available': ctx.scope.get('mode') == 'local' or self.chapter_reader is not None}
        except HTTPException as exc:
            if exc.status_code in {401, 403, 404}: self.discard_search(ctx)
            raise
        finally:
            with self._index_lock:
                if request_id is None: self._search_operations.pop(operation, None)
                while len(self._search_operations) > 256: self._search_operations.popitem(last=False)

    def resolve(self, ctx, body, *, reauthorize=lambda: None, require_flag=lambda flag: None):
        value = ResolveIn.model_validate(body)
        reauthorize()
        sources, _, _ = self._search_manifest(ctx, lambda: None, require_flag)
        source = next((s for s in sources if s.key == value.kind + ':' + value.id), None)
        if source is None: raise FileNotFoundError(value.id)
        row = source.read()
        if value.kind == 'chapter' and 'kind' not in row:
            if row.get('novel_id') != ctx.novel_id or not self._visible_search_row(ctx, row): raise FileNotFoundError(value.id)
            doc = self._search_document(ctx, value.kind, row)
        else: doc = row
        stale = doc['revision'] != value.revision
        if stale and not value.open_current:
            raise StaleSourceError('search target changed; explicitly open its current version')
        latest, _, latest_projected = self._search_manifest(ctx, lambda: None, require_flag)
        if next((s.stamp for s in latest if s.key == source.key), None) != source.stamp:
            raise StaleSourceError('search target changed while resolving; retry')
        reauthorize()
        navigation = doc.get('source', {'kind': 'chapter' if doc['kind'] == 'chapter' else 'feature', 'id': doc['id'], 'feature': doc['feature']})
        return {**navigation,
                'novel_id': ctx.novel_id, 'branch_id': ctx.branch, 'version': navigation.get('version', doc['version']),
                'anchor': {'offset': 0 if stale else min(value.offset, len(doc['text'])), 'scroll': 0},
                'stale': stale, 'revision': doc['revision'], 'coordinate': COORDINATE}

    @staticmethod
    def _task_in_scope(ctx, reader, row):
        if not isinstance(row, dict) or row.get('novel_id') != ctx.novel_id:
            return False
        if row.get('scope') is not None and row['scope'] != ctx.scope:
            return False
        if row.get('branch_id') and row['branch_id'] != ctx.scope.get('branch_id'):
            return False
        if reader.name == 'exports':
            # ExportJobService.public preserves its original permission_context
            # envelope. Recognize exactly this authority; never turn arbitrary
            # nested dictionaries into a second authorization mechanism.
            envelope = row.get('permission_context')
            if not isinstance(envelope, dict):
                return False
            expected = {**ctx.scope, 'actor_id': ctx.actor if ctx.scope.get('mode') == 'collaboration' else None}
            keys = ('mode', 'novel_id', 'workspace_id', 'storyline_id', 'branch_id', 'actor_id')
            return all(envelope.get(key) == expected.get(key) for key in keys)
        if ctx.scope.get('mode') == 'collaboration':
            return row.get('scope') == ctx.scope or row.get('branch_id') == ctx.scope.get('branch_id')
        return not row.get('branch_id')

    def tasks(self, ctx, require_flag, query='', failed_only=False, reauthorize=lambda: None):
        reauthorize()
        items, unavailable, truncated = [], [], False
        for reader in self.task_readers:
            reauthorize()
            try:
                if reader.flag:
                    require_flag(reader.flag)
                payload = reader.read(ctx)
                rows = payload.get('items', []) if isinstance(payload, dict) else payload
                source_more = (bool(payload.get('has_more')) or payload.get('next_offset') is not None) if isinstance(payload, dict) else False
                source_visible = False
                for row in rows[:200]:
                    # Readers provide authorized records; still fence all returned scopes.
                    if not self._task_in_scope(ctx, reader, row):
                        continue
                    source_visible = True
                    task = projected_task(reader, row)
                    if failed_only and task['status'] not in {'FAILED', 'UNKNOWN'}:
                        continue
                    if query.casefold() not in (task['id'] + task['label'] + task['stage_label']).casefold():
                        continue
                    items.append(task)
                # Never expose pagination hints solely from rejected records.
                truncated |= source_visible and (source_more or len(rows) > 200)
            except HTTPException as exc:
                if exc.status_code not in {403, 404}:
                    unavailable.append({'authority': reader.name, 'label': reader.label, 'reason': 'SOURCE_UNAVAILABLE'})
                # A denied source has no task identifiers, counts or titles.
            except Exception:
                unavailable.append({'authority': reader.name, 'label': reader.label, 'reason': 'SOURCE_UNAVAILABLE'})
        reauthorize()
        return {'items': items[:500], 'unavailable': unavailable, 'truncated': truncated or len(items) > 500,
                'executor': False, 'refresh': 'MANUAL', 'automatic_retries': False}

    def cancel_task(self, ctx, authority, task_id, body, require_flag, reauthorize=lambda: None):
        value = TaskCancelIn.model_validate(body)
        reauthorize()
        reader = next((item for item in self.task_readers if item.name == authority), None)
        if reader is None or reader.cancel is None:
            raise FileNotFoundError('task cancellation authority')
        if reader.flag:
            require_flag(reader.flag)
        def original():
            payload = reader.read(ctx)
            rows = payload.get('items', []) if isinstance(payload, dict) else payload
            row = next((row for row in rows[:200] if self._task_in_scope(ctx, reader, row)
                        and row.get('id') == task_id), None)
            if row is None:
                raise FileNotFoundError('task')
            return projected_task(reader, row)
        before = original()
        if before['revision'] != value.expected_revision:
            raise StaleSourceError('task changed; refresh before requesting cancellation')
        if 'cancel' not in before['actions']:
            raise ValueError('source task does not permit cancellation')
        reauthorize()
        # The original executor owns the terminal race and cancellation signal.
        # Its possibly prose-bearing response is never forwarded or persisted.
        try:
            reader.cancel(ctx, task_id, before['version'])
        except CapabilityVersionConflict as exc:
            # A source CAS failure may carry full prompt/lease fields. The task
            # center only returns its authoritative version, never that payload.
            raise CapabilityVersionConflict({'version': exc.current.get('version')}) from None
        reauthorize()
        after = original()
        reauthorize()
        return {'item': after, 'cancellation_requested': True, 'executor': False}

    def diagnostics(self, ctx, body, require_flag, reauthorize=lambda: None):
        reauthorize()
        options = DiagnosticIn.model_validate(body)
        result = {'schema': 'workspace-diagnostics-v1', 'contains_manuscript': False,
                  'contains_credentials': False, 'uploaded': False, 'sections': {}}
        if options.include_environment:
            result['sections']['environment'] = {'component': 'workspace_tools_v2', 'storage': self.store.storage_mode,
                'scope_mode': ctx.scope['mode'], 'diagnostic_contract': 1}
        if options.include_task_states or options.include_error_codes:
            tasks = self.tasks(ctx, require_flag, reauthorize=reauthorize)
            if options.include_task_states:
                # No titles, IDs, timestamps, paths, prompts, host IDs or raw logs.
                result['sections']['task_states'] = [{'authority': t['authority'], 'status': t['status'],
                    'cost_state': 'UNKNOWN'} for t in tasks['items']]
            if options.include_error_codes:
                result['sections']['error_codes'] = sorted(set(t['error_code'] for t in tasks['items'] if t['error_code']))
            result['sections']['coverage'] = {'truncated': tasks['truncated'], 'raw_logs_included': False}
        reauthorize()
        result['preview_digest'] = digest(result)
        return result

    def export_diagnostics(self, ctx, body, require_flag, reauthorize=lambda: None):
        value = DiagnosticExportIn.model_validate(body)
        result = self.diagnostics(ctx, value.model_dump(exclude={'preview_digest'}), require_flag, reauthorize)
        if result['preview_digest'] != value.preview_digest:
            raise StaleSourceError('diagnostic state changed; create a fresh preview before exporting')
        return result
