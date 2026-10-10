"""U15 bounded author sessions and notices over existing goal/history/tasks.

This stores session metadata, never a second manuscript, project goal or task
executor. Reminder preferences are inert data; the UI owns optional timers.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import Field
from .common import DomainService, change_row, new_row, now
from .planning import StrictModel, digest
from .ux import chapter_text
from .reader_sources import authorized_chapter_rows
from ..services.v1_capability_service import CapabilityVersionConflict


class ChecklistItem(StrictModel):
    id: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    text: str = Field(min_length=1, max_length=300)
    done: bool = False


class StartIn(StrictModel):
    capture_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    goal: str = Field(default='', max_length=1000)
    target_characters: int | None = Field(default=None, ge=1, le=1000000)
    tasks: list[ChecklistItem] = Field(default_factory=list, max_length=30)


class SessionIn(StrictModel):
    expected_version: int = Field(ge=1)
    tasks: list[ChecklistItem] = Field(default_factory=list, max_length=30)
    stopping_note: str = Field(default='', max_length=2000)
    complete: bool = False


class Reminder(StrictModel):
    enabled: bool = False
    time: str = Field(default='18:00', pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    timezone: str = Field(default='UTC', min_length=1, max_length=80)


class NoticePreferencesIn(StrictModel):
    expected_version: int = Field(ge=0)
    reminder: Reminder = Field(default_factory=Reminder)
    completion_priority: Literal['normal', 'low'] = 'normal'
    review_priority: Literal['normal', 'low'] = 'normal'
    failure_priority: Literal['urgent', 'normal'] = 'urgent'


class AcknowledgeIn(StrictModel):
    expected_version: int = Field(ge=0)
    event_id: str = Field(pattern=r'^[a-f0-9]{64}$')


class WritingSessionsService(DomainService):
    SESSIONS = 'writing_sessions_v2'
    NOTICES = 'writing_notice_preferences_v2'

    def __init__(self, store, novels, chapters, *, sources, task_reader=None, history_reader=None):
        super().__init__(store, novels, chapters)
        self.sources, self.task_reader, self.history_reader = sources, task_reader, history_reader

    def _rows(self, ctx):
        rows = authorized_chapter_rows(ctx, self.sources, self.chapters)
        if len(rows) > 200 or sum(len(chapter_text(r)) for r in rows) > 2_000_000:
            raise ValueError('session limit: 200 chapters / 2,000,000 characters')
        return rows

    def _owned(self, ctx, collection, state=None):
        self.novels.get(ctx.novel_id)
        state = state if state is not None else self.store.read(ctx.novel_id, ctx.scope)
        return [r for r in state['collections'].get(collection, {}).values()
                if r.get('created_by') == ctx.actor and r.get('scope') == ctx.scope and r.get('novel_id') == ctx.novel_id]

    @staticmethod
    def _count(row): return sum(not c.isspace() for c in chapter_text(row))

    def overview(self, ctx):
        sessions = sorted(self._owned(ctx, self.SESSIONS), key=lambda r: r['created_at'], reverse=True)
        # Do not call the legacy global-totals route under branch scope.
        goal = (self.novels.get(ctx.novel_id).get('writing_goal') or {'target_words': 0, 'target_chapters': 0}) if ctx.scope['mode'] == 'local' else None
        if goal is not None:
            rows = self._rows(ctx)
            goal = {k: goal[k] for k in ('target_words', 'target_chapters', 'deadline') if k in goal}
            goal.update(current_words=sum(self._count(r) for r in rows), current_chapters=len(rows))
        return {'items': [self._public(r, ctx) for r in sessions[:50]], 'truncated': len(sessions) > 50,
                'project_goal': goal, 'goal_authority': 'ORIGINAL_NOVEL_GOAL' if goal is not None else 'BRANCH_PROJECTION_UNAVAILABLE',
                'statistics': 'PERSISTED_NON_WHITESPACE_CHARACTERS_AND_HISTORY', 'model_execution': False}

    def _public(self, row, ctx=None):
        result = {key: deepcopy(row.get(key)) for key in ('id', 'version', 'status', 'goal', 'target_characters', 'tasks', 'stopping_note', 'created_at', 'completed_at', 'recap')}
        if ctx and row.get('recap') and not set(row.get('recap_sources', [])).issubset({r['id'] for r in self._rows(ctx)}):
            result['recap'] = {**result['recap'], 'net_characters': None, 'persisted_revision_events': None, 'history_available': False, 'statistics_scope': 'SOURCE_ACCESS_CHANGED'}
        return result

    def start(self, ctx, body, reauthorize=lambda: None):
        value = StartIn.model_validate(body); data = value.model_dump()
        if len({t.id for t in value.tasks}) != len(value.tasks): raise ValueError('duplicate checklist item')
        rows = self._rows(ctx)
        from ..manuscript_sources import reader_available
        if not reader_available(self.sources.chapter_reader, ctx): raise ValueError('authorized branch chapter reader unavailable')
        baseline = {r['id']: {'version': r['version'], 'characters': self._count(r)} for r in rows}
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            owned = self._owned(ctx, self.SESSIONS, state)
            old = next((r for r in owned if r['capture_id'] == value.capture_id), None)
            if old:
                if old['capture_digest'] != digest(data): raise ValueError('capture identity reused with different data')
                reauthorize(); return self._public(old)
            if any(r['status'] == 'ACTIVE' for r in owned): raise ValueError('finish the current session before starting another')
            if len(owned) >= 500: raise ValueError('session history limit reached')
            reauthorize()
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**data, 'capture_digest': digest(data), 'baseline': baseline,
                          'stopping_note': '', 'status': 'ACTIVE', 'recap': None})
            state['collections'].setdefault(self.SESSIONS, {})[row['id']] = row
            return self._public(row)

    def _recap(self, ctx, session):
        current = {r['id']: r for r in self._rows(ctx)}; baseline = session['baseline']
        revisions = set(); history_available = True
        for cid, row in current.items():
            minimum = baseline.get(cid, {}).get('version', 0)
            if row['version'] <= minimum: continue
            if self.history_reader:
                history = self.history_reader(ctx, cid)
            elif ctx.scope['mode'] == 'local': history = self.chapters.history(cid)
            else: history_available = False; continue
            if len(history) > 10000: raise ValueError('history recap limit reached')
            for entry in history:
                version = entry.get('version')
                if type(version) is not int or not minimum <= version < row['version']: continue
                if ctx.scope['mode'] != 'local' and entry.get('scope_id') != ctx.scope.get('branch_id'): continue
                revisions.add((cid, version))
        # A removed or now-hidden chapter is not enumerated or counted. The
        # recap is explicitly limited to currently authorized surviving data.
        comparable = set(current).intersection(baseline)
        return {'persisted_revision_events': len(revisions) if history_available else None,
                'net_characters': sum(self._count(current[c]) - baseline[c]['characters'] for c in comparable)
                    + sum(self._count(current[c]) for c in set(current) - set(baseline)),
                'completed_checklist_items': sum(t['done'] for t in session['tasks']),
                'statistics_scope': 'CURRENTLY_AUTHORIZED_CHAPTERS', 'history_available': history_available,
                'attribution': 'PROJECT_WRITES_DURING_SESSION_NOT_PERSONAL_TYPING', 'captured_at': now(), '_source_ids': list(current)}

    def update(self, ctx, sid, body, reauthorize=lambda: None):
        value = SessionIn.model_validate(body)
        if len({t.id for t in value.tasks}) != len(value.tasks): raise ValueError('duplicate checklist item')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = next((r for r in self._owned(ctx, self.SESSIONS, state) if r['id'] == sid), None)
            if row is None: raise FileNotFoundError(sid)
            if row['status'] != 'ACTIVE': raise ValueError('completed session is immutable')
            def update(target):
                target.update(tasks=[t.model_dump() for t in value.tasks], stopping_note=value.stopping_note)
                if value.complete:
                    recap = self._recap(ctx, target)
                    target.update(status='COMPLETED', completed_at=now(), recap_sources=recap.pop('_source_ids'), recap=recap)
            change_row(row, ctx.actor, value.expected_version, update); reauthorize(); return self._public(row)

    def _preferences_row(self, ctx, state=None):
        return next(iter(self._owned(ctx, self.NOTICES, state)), None)

    def preferences(self, ctx):
        row = self._preferences_row(ctx)
        data = NoticePreferencesIn.model_validate({'expected_version': row['version'] if row else 0,
            **{k: row[k] for k in ('reminder', 'completion_priority', 'review_priority', 'failure_priority') if row and k in row}}).model_dump()
        data['version'] = data.pop('expected_version')
        return {**data, 'delivery': 'IN_APP_TASK_CENTER_ONLY', 'restart': 'MISSED_REMINDERS_NOT_REPLAYED',
                'requires_open': 'TASK_CENTER', 'network_push': False, 'email': False, 'tracking': False, 'model_execution': False}

    def _change_preferences(self, ctx, version, update, reauthorize):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._preferences_row(ctx, state)
            if (row['version'] if row else 0) != version: raise CapabilityVersionConflict(self.preferences(ctx))
            if row: change_row(row, ctx.actor, version, update)
            else:
                row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'status': 'ACTIVE', 'acknowledged': []}); update(row)
                state['collections'].setdefault(self.NOTICES, {})[self.sources._owner(ctx.actor)] = row
            reauthorize(); return self.preferences(ctx)

    def save_preferences(self, ctx, body, reauthorize=lambda: None):
        value = NoticePreferencesIn.model_validate(body)
        try: ZoneInfo(value.reminder.timezone)
        except (ZoneInfoNotFoundError, ValueError): raise ValueError('valid IANA timezone required') from None
        data = value.model_dump(); version = data.pop('expected_version')
        return self._change_preferences(ctx, version, lambda row: row.update(data), reauthorize)

    def notices(self, ctx, focus=False):
        settings = self.preferences(ctx); ack = set((self._preferences_row(ctx) or {}).get('acknowledged', []))
        source = self.task_reader(ctx) if self.task_reader else {'items': [], 'unavailable': [{'reason': 'NOT_CONFIGURED'}]}
        seen, visible, deferred = set(), [], 0
        for task in source.get('items', []):
            status = task.get('status')
            kind = 'failure' if status in {'FAILED', 'UNKNOWN'} else 'completion' if status in {'COMPLETED', 'SUCCEEDED', 'COMMITTED', 'ACCEPTED'} else 'review' if status in {'REVIEW', 'AWAITING_REVIEW', 'PENDING_REVIEW', 'REVIEW_REQUIRED', 'RESULT_READY', 'PROPOSED'} else None
            if not kind: continue
            event = digest([task['authority'], task['id'], task.get('version'), status])
            if event in seen or event in ack: continue
            seen.add(event); priority = settings[kind + '_priority']
            if focus and priority != 'urgent': deferred += 1; continue
            visible.append({'event_id': event, 'kind': kind, 'priority': priority, 'label': task['label'],
                'status': status, 'feature': task['feature'], 'task_id': task['id'], 'authority': task['authority']})
        visible.sort(key=lambda item: {'urgent': 0, 'normal': 1, 'low': 2}[item['priority']])
        return {'items': visible, 'deferred_count': deferred, 'truncated': bool(source.get('truncated')), 'unavailable': source.get('unavailable', []),
                'save_failures_always_visible': True, 'refresh': 'MANUAL', 'executor': False}

    def acknowledge(self, ctx, body, reauthorize=lambda: None):
        value = AcknowledgeIn.model_validate(body)
        def update(row):
            if value.event_id not in {x['event_id'] for x in self.notices(ctx)['items']}:
                raise ValueError('notice is no longer available; refresh task center')
            row['acknowledged'] = (row.get('acknowledged', []) + [value.event_id])[-1000:]
        return self._change_preferences(ctx, value.expected_version, update, reauthorize)
