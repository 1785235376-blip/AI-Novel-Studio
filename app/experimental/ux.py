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
from threading import RLock
from typing import Callable, Literal

from fastapi import HTTPException
from pydantic import Field

from .common import DomainService, StaleSourceError, change_row, new_row
from .planning import StrictModel, digest
from ..services.v1_capability_service import CapabilityVersionConflict

FEATURES = frozenset({'editor', 'creation', 'story', 'history', 'workflow', 'screenplay', 'assets',
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
    search_kind: Literal['', 'chapter', 'character', 'location', 'foreshadowing'] = ''
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
    kind: Literal['chapter', 'character', 'location', 'foreshadowing']
    id: str = Field(min_length=1, max_length=160)
    revision: str = Field(min_length=1, max_length=80)
    offset: int = Field(default=0, ge=0, le=2_000_000)
    open_current: bool = False


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


STAGES = {'QUEUED': '排队', 'PENDING': '等待', 'DRAFT': '草稿', 'READY': '就绪',
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
    if (reader.name == 'author_generation' and isinstance(row.get('chapter_id'), str)
            and row['chapter_id'] and type(row.get('base_chapter_version')) is int
            and row['base_chapter_version'] > 0):
        source = {'source': {'kind': 'generation', 'id': str(row['id']),
                  'chapter_id': row['chapter_id'], 'version': row['base_chapter_version']}}
    return {**source, 'id': str(row['id']), 'authority': reader.name, 'label': reader.label,
            'status': status, 'stage_label': STAGES[status], 'version': row.get('version'),
            'feature': reader.feature, 'progress': progress, 'history': history,
            'stale': bool(row.get('stale')), 'cost': {'estimate': None, 'actual': None, 'state': 'UNKNOWN'},
            'error_code': safe_code(error) if error else None,
            'actions': ['open_source'], 'retry_policy': 'SOURCE_AUTHORITY_ONLY',
            'lifecycle': '面板关闭不取消任务；继续执行和重启恢复取决于原任务服务。'}


class WorkspaceToolsService(DomainService):
    RESUMES = 'workspace_resumes_v2'

    def __init__(self, store, novels, chapters, *, chapter_reader=None, entity_readers=None, task_readers=None, focus_reader=None):
        super().__init__(store, novels, chapters)
        self.chapter_reader = chapter_reader
        self.entity_readers = entity_readers or {}
        self.task_readers = tuple(task_readers or ())
        self.focus_reader = focus_reader
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

    def _documents(self, ctx):
        for row in self.chapter_rows(ctx):
            yield {'kind': 'chapter', 'id': str(row['id']), 'title': str(row.get('title', '章节')),
                         'text': chapter_text(row), 'version': row['version'], 'revision': digest(row),
                         'feature': 'editor', 'aliases': [], 'tags': [], 'updated_at': row.get('updated_at', ''), 'coordinate': COORDINATE}
        # Legacy entities do not have member/character-level visibility adapters;
        # expose names/aliases only in local author mode, never secrets or body.
        for kind, dataset in (('character', 'characters'), ('location', 'locations'), ('foreshadowing', 'foreshadowing')):
            if kind in self.entity_readers:
                rows = self.entity_readers[kind](ctx)
            elif ctx.scope.get('mode') == 'local':
                rows = self.novels.data_set(ctx.novel_id, dataset)
            else:
                rows = []
            for row in rows:
                if not row.get('id') or row.get('hidden') or row.get('secret') or str(row.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'}:
                    continue
                if row.get('branch_id') and row['branch_id'] != ctx.scope.get('branch_id'):
                    continue
                aliases = row.get('aliases', [])
                aliases = [v for v in aliases[:20] if isinstance(v, str)] if isinstance(aliases, list) else []
                title = str(row.get('name') or row.get('title') or {'character': '人物', 'location': '地点', 'foreshadowing': '伏笔'}[kind])
                yield {'kind': kind, 'id': str(row['id']), 'title': title, 'text': '', 'version': row.get('version'),
                             'revision': digest(row), 'feature': 'story', 'aliases': aliases, 'tags': [], 'updated_at': row.get('updated_at', ''), 'coordinate': COORDINATE}

    def search(self, ctx, query='', kind='', chapter_id=None, rebuild=False):
        if len(query) > 160 or kind not in {'', 'chapter', 'character', 'location', 'foreshadowing'}:
            raise ValueError('invalid search filter')
        query = query.strip().casefold()
        documents = self._documents(ctx)
        key = digest([ctx.novel_id, ctx.scope, ctx.actor])
        with self._index_lock:
            old = {} if rebuild else self._indexes.get(key, {})
            current, size, changed, truncated = {}, 0, 0, False
            for doc in documents:
                size += len(doc['text']) + len(doc['title'])
                if len(current) >= MAX_RECORDS or size > MAX_CHARACTERS:
                    truncated = True
                    break
                sid = f"{doc['kind']}:{doc['id']}"
                cached = old.get(sid)
                if not cached or cached['revision'] != doc['revision']:
                    doc['_search'] = '\n'.join([doc['title'], *doc['aliases'], doc['text']]).casefold()
                    changed += 1
                    current[sid] = doc
                else:
                    current[sid] = cached
            # Drop removed/unauthorized sources before querying, including counts.
            self._indexes[key] = current
            self._indexes.move_to_end(key)
            while len(self._indexes) > 8:
                self._indexes.popitem(last=False)
            results = []
            for doc in current.values():
                if kind and doc['kind'] != kind or chapter_id and (doc['kind'] != 'chapter' or doc['id'] != chapter_id):
                    continue
                if query and query not in doc['_search']:
                    continue
                offset = literal_offset(doc['text'], query) if query else 0
                results.append({k: deepcopy(v) for k, v in doc.items() if k not in {'text', '_search'}} |
                               {'offset': offset, 'snippet': doc['text'][max(0, offset - 35):offset + 125]})
                if len(results) >= 50:
                    truncated = True
                    break
        return {'items': results, 'mode': 'LITERAL_LEXICAL', 'model_called': False,
                'truncated': truncated, 'updated_documents': changed, 'limit': 50,
                'branch_sources_available': ctx.scope.get('mode') == 'local' or self.chapter_reader is not None}

    def resolve(self, ctx, body):
        value = ResolveIn.model_validate(body)
        doc = next((d for d in self._documents(ctx) if d['kind'] == value.kind and d['id'] == value.id), None)
        if doc is None:
            raise FileNotFoundError(value.id)
        stale = doc['revision'] != value.revision
        if stale and not value.open_current:
            raise StaleSourceError('search target changed; explicitly open its current version')
        return {'kind': 'chapter' if doc['kind'] == 'chapter' else 'feature', 'id': doc['id'],
                'feature': doc['feature'], 'version': doc['version'],
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

    def tasks(self, ctx, require_flag, query='', failed_only=False):
        items, unavailable, truncated = [], [], False
        for reader in self.task_readers:
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
        return {'items': items[:500], 'unavailable': unavailable, 'truncated': truncated or len(items) > 500,
                'executor': False, 'refresh': 'MANUAL', 'automatic_retries': False}

    def diagnostics(self, ctx, body, require_flag):
        options = DiagnosticIn.model_validate(body)
        result = {'schema': 'workspace-diagnostics-v1', 'contains_manuscript': False,
                  'contains_credentials': False, 'uploaded': False, 'sections': {}}
        if options.include_environment:
            result['sections']['environment'] = {'component': 'workspace_tools_v2', 'storage': self.store.storage_mode,
                'scope_mode': ctx.scope['mode'], 'diagnostic_contract': 1}
        if options.include_task_states or options.include_error_codes:
            tasks = self.tasks(ctx, require_flag)
            if options.include_task_states:
                # No titles, IDs, timestamps, paths, prompts, host IDs or raw logs.
                result['sections']['task_states'] = [{'authority': t['authority'], 'status': t['status'],
                    'cost_state': 'UNKNOWN'} for t in tasks['items']]
            if options.include_error_codes:
                result['sections']['error_codes'] = sorted(set(t['error_code'] for t in tasks['items'] if t['error_code']))
            result['sections']['coverage'] = {'truncated': tasks['truncated'], 'raw_logs_included': False}
        result['preview_digest'] = digest(result)
        return result

    def export_diagnostics(self, ctx, body, require_flag):
        value = DiagnosticExportIn.model_validate(body)
        result = self.diagnostics(ctx, value.model_dump(exclude={'preview_digest'}), require_flag)
        if result['preview_digest'] != value.preview_digest:
            raise StaleSourceError('diagnostic state changed; create a fresh preview before exporting')
        return result
