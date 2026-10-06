"""U04: author-scoped reading preferences, source pins and private inspiration drafts.

No manuscript, Canon, model or research-store writes. Copy is an explicit,
preview-fenced PlanningService proposal in the same experimental transaction.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Literal

from pydantic import Field

from .common import DomainService, StaleSourceError, change_row, check_version, new_row
from .planning import StrictModel, PlanningProposalIn, digest, collection, require_row
from .ux import ReadContext, chapter_text
from ..services.v1_capability_service import CapabilityVersionConflict


class WritingPreferences(StrictModel):
    column_width: Literal['narrow', 'comfortable', 'wide'] = 'comfortable'
    font_size: Literal[16, 18, 20, 24] = 18
    line_height: Literal[1.5, 1.75, 2] = 1.75
    paragraph_focus: bool = False


class Pin(StrictModel):
    kind: Literal['character', 'location', 'chapter']
    id: str = Field(min_length=1, max_length=160)
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')


class BookmarkResolveIn(StrictModel):
    id: str = Field(min_length=1, max_length=160)
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    open_current: bool = False


class PreferencesIn(StrictModel):
    expected_version: int = Field(ge=0)
    preferences: WritingPreferences = Field(default_factory=WritingPreferences)
    pins: list[Pin] = Field(default_factory=list, max_length=6)


class NoteIn(StrictModel):
    capture_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    title: str = Field(default='', max_length=160)
    text: str = Field(min_length=1, max_length=10000)
    chapter_id: str | None = Field(default=None, max_length=160)
    chapter_version: int | None = Field(default=None, ge=1)


class NoteEditIn(NoteIn):
    expected_version: int = Field(ge=1)


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1)


class CopyPreviewIn(VersionIn):
    node_id: str = Field(min_length=1, max_length=160)
    expected_node_version: int = Field(ge=1)
    field: Literal['goal', 'conflict', 'turning_point'] = 'goal'


class CopyIn(CopyPreviewIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class WritingFocusService(DomainService):
    PREFERENCES = 'writing_focus_preferences_v2'
    NOTES = 'writing_inspiration_drafts_v2'

    def __init__(self, store, novels, chapters, *, planning=None, chapter_reader=None, entity_readers=None):
        super().__init__(store, novels, chapters)
        self.planning = planning
        self.chapter_reader = chapter_reader
        self.entity_readers = entity_readers or {}

    @staticmethod
    def _owner(actor):
        if not isinstance(actor, str) or not actor:
            raise ValueError('trusted actor required')
        return hashlib.sha256(actor.encode()).hexdigest()

    def _preference_row(self, ctx, state=None):
        self.novels.get(ctx.novel_id)
        state = state if state is not None else self.store.read(ctx.novel_id, ctx.scope)
        row = state['collections'].get(self.PREFERENCES, {}).get(self._owner(ctx.actor))
        if row and (row.get('novel_id') != ctx.novel_id or row.get('scope') != ctx.scope or row.get('created_by') != ctx.actor):
            raise ValueError('invalid preference owner')
        return row

    def preferences(self, ctx):
        row = self._preference_row(ctx)
        if not row:
            return {'version': 0, 'preferences': WritingPreferences().model_dump(), 'pins': [], 'recovery_required': False}
        try:
            value = WritingPreferences.model_validate(row['preferences']).model_dump()
            pins = [Pin.model_validate(pin).model_dump() for pin in row.get('pins', [])]
            if len(pins) > 6:
                raise ValueError('invalid pin count')
            recovery = False
        except (KeyError, ValueError, TypeError):
            value, pins, recovery = WritingPreferences().model_dump(), [], True
        return {'version': row['version'], 'preferences': value, 'pins': pins, 'recovery_required': recovery}

    def save_preferences(self, ctx, body, reauthorize=lambda: None):
        data = PreferencesIn.model_validate(body).model_dump()
        seen = set()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._preference_row(ctx, state)
            if (row['version'] if row else 0) != data['expected_version']:
                raise CapabilityVersionConflict(self.preferences(ctx))
            # Existing stale pins may remain while typography changes. New or
            # refreshed pins must match the currently authorized source exactly.
            old_pins = (row or {}).get('pins', [])
            for pin in data['pins']:
                key = (pin['kind'], pin['id'])
                if key in seen:
                    raise ValueError('duplicate pin')
                seen.add(key)
                if pin not in old_pins and self._source(ctx, *key)['revision'] != pin['revision']:
                    raise StaleSourceError('reference changed; refresh before pinning')
            reauthorize()
            payload = {'preferences': data['preferences'], 'pins': data['pins'], 'status': 'ACTIVE'}
            if row:
                change_row(row, ctx.actor, data['expected_version'], lambda target: target.update(payload))
            else:
                collection(state, self.PREFERENCES)[self._owner(ctx.actor)] = new_row(ctx.novel_id, ctx.scope, ctx.actor, payload)
            return self.preferences(ctx)

    def _source_rows(self, ctx, kind):
        self.novels.get(ctx.novel_id)
        if kind == 'chapter':
            if self.chapter_reader:
                rows = self.chapter_reader(ctx)
            elif ctx.scope.get('mode') == 'local':
                rows = self.chapters.list(ctx.novel_id)
            else:
                return []
        elif kind in self.entity_readers:
            rows = self.entity_readers[kind](ctx)
        elif ctx.scope.get('mode') == 'local':
            rows = self.novels.data_set(ctx.novel_id, {'character': 'characters', 'location': 'locations', 'scene': 'scenes'}[kind])
        else:
            return []
        return [row for row in rows if row.get('id') and not row.get('is_archived')
                and row.get('status') != 'ARCHIVED' and not row.get('hidden') and not row.get('secret')
                and str(row.get('visibility', '')).upper() not in {'PRIVATE', 'SECRET', 'DENIED'}
                and row.get('novel_id', ctx.novel_id) == ctx.novel_id
                and (ctx.scope.get('mode') == 'local' and not row.get('branch_id')
                     or ctx.scope.get('mode') == 'collaboration' and row.get('branch_id') == ctx.scope.get('branch_id'))]

    @staticmethod
    def _project(kind, row):
        if kind == 'chapter':
            text = chapter_text(row)
        else:
            # Deliberate allowlist: arbitrary secrets, tokens and metadata never
            # become cards. No external HTML or raw entity JSON is rendered.
            fields = ('role', 'personality', 'goal', 'current_location') if kind == 'character' else ('location_type', 'description', 'rules', 'atmosphere')
            labels = {'role': '身份', 'personality': '性格', 'goal': '目标', 'current_location': '位置', 'location_type': '类型', 'description': '描述', 'rules': '规则', 'atmosphere': '氛围'}
            text = '\n'.join(f'{labels[key]}：{row[key]}' for key in fields if isinstance(row.get(key), str) and row[key])
        return {'kind': kind, 'id': str(row['id']), 'title': str(row.get('name') or row.get('title') or '未命名'),
                'revision': digest(row), 'version': row.get('version'), 'text': text[:12000],
                'truncated': len(text) > 12000, 'read_only': True, 'privacy_level': row.get('privacy_level', 'LOCAL_ONLY')}

    def _source(self, ctx, kind, rid):
        row = next((row for row in self._source_rows(ctx, kind) if str(row['id']) == rid), None)
        if row is None:
            raise FileNotFoundError(rid)
        return self._project(kind, row)

    def references(self, ctx, query='', kind=''):
        if len(query) > 160 or kind not in {'', 'chapter', 'character', 'location'}:
            raise ValueError('invalid reference query')
        items, truncated = [], False
        for source_kind in ([kind] if kind else ['character', 'location', 'chapter']):
            for row in self._source_rows(ctx, source_kind):
                title = str(row.get('name') or row.get('title') or '')
                if query.casefold() not in title.casefold():
                    continue
                if len(items) == 50:
                    truncated = True
                    break
                items.append(self._project(source_kind, row))
        return {'items': items, 'truncated': truncated,
                'branch_sources_available': ctx.scope.get('mode') == 'local' or bool(self.chapter_reader or self.entity_readers)}

    def pinned(self, ctx):
        result = []
        for pin in self.preferences(ctx)['pins']:
            try:
                row = self._source(ctx, pin['kind'], pin['id'])
                fresh = row['revision'] == pin['revision']
                result.append({**pin, 'state': 'READY' if fresh else 'STALE',
                               'title': row['title'], 'card': row if fresh else None})
            except FileNotFoundError:
                result.append({**pin, 'state': 'UNAVAILABLE', 'title': '资料不可用', 'card': None})
        return {'items': result}

    def open_bookmark(self, ctx, body):
        data = BookmarkResolveIn.model_validate(body).model_dump()
        source = self._source(ctx, 'chapter', data['id'])
        if not data['open_current'] and source['revision'] != data['revision']:
            raise StaleSourceError('bookmarked chapter changed; review the current version')
        return {'kind': 'chapter', 'id': source['id'], 'version': source['version'],
                'anchor': {'offset': 0, 'scroll': 0}, 'coordinate': 'EDITOR_TEXT_CODEPOINT',
                'stale': source['revision'] != data['revision']}

    def overview(self, ctx, chapter_id=None):
        """Read-only projection of ChapterTree and StoryDatabase's existing IDs."""
        chapters = self._source_rows(ctx, 'chapter')
        if chapter_id:
            chapters = [row for row in chapters if str(row['id']) == chapter_id]
            if not chapters:
                raise FileNotFoundError(chapter_id)
        by_chapter = {str(row['id']): row for row in chapters}
        # Scene records without a reliable current chapter are not borrowed into
        # this overview. They remain editable through the existing StoryDatabase.
        scenes = [row for row in self._source_rows(ctx, 'scene') if row.get('chapter_id') in by_chapter]
        projected = []
        for row in chapters[:100]:
            related = [scene for scene in scenes if scene.get('chapter_id') == row['id']]
            projected.append({'id': str(row['id']), 'title': str(row.get('title', '未命名章节')),
                'version': row['version'], 'revision': digest(row), 'number': row.get('number'),
                'word_count': row.get('word_count') if type(row.get('word_count')) is int else len(chapter_text(row)),
                'scene_count': len(related),
                'scenes': [{'id': str(scene['id']), 'title': str(scene.get('title', '未命名场景')),
                            'chapter_id': str(row['id']), 'sequence': scene.get('sequence'),
                            'status': str(scene.get('status', 'PLANNED')),
                            'details_truncated': any(len(str(scene.get(field, ''))) > 2000 for field in ('purpose', 'conflict', 'outcome')),
                            'purpose': str(scene.get('purpose', ''))[:2000],
                            'conflict': str(scene.get('conflict', ''))[:2000],
                            'outcome': str(scene.get('outcome', ''))[:2000]}
                           for scene in related[:20]], 'scenes_truncated': len(related) > 20})
        return {'items': projected, 'truncated': len(chapters) > 100, 'read_only': True,
                'chapter_sources_available': ctx.scope.get('mode') == 'local' or bool(self.chapter_reader),
                'scene_sources_available': ctx.scope.get('mode') == 'local' or 'scene' in self.entity_readers}

    def _note(self, ctx, note_id, state=None):
        row = require_row(state, self.NOTES, note_id) if state is not None else self.get(ctx.novel_id, ctx.scope, self.NOTES, note_id)
        if row.get('created_by') != ctx.actor:
            raise FileNotFoundError(note_id)
        return row

    def _capture(self, ctx, data):
        if bool(data['chapter_id']) != bool(data['chapter_version']):
            raise ValueError('chapter ID and saved version must be supplied together')
        if not data['chapter_id']:
            return None
        source = self._source(ctx, 'chapter', data['chapter_id'])
        if source['version'] != data['chapter_version']:
            raise StaleSourceError('source chapter changed')
        return {'chapter_id': source['id'], 'version': source['version'], 'revision': source['revision']}

    def _decorate_note(self, ctx, row):
        result = deepcopy({key: value for key, value in row.items() if key != 'history'})
        source = result.get('source')
        result['source_state'] = 'NONE'
        if source:
            try:
                current = self._source(ctx, 'chapter', source['chapter_id'])
                result['source_state'] = 'READY' if current['revision'] == source['revision'] else 'STALE'
            except FileNotFoundError:
                result['source_state'] = 'UNAVAILABLE'
        return result

    def notes(self, ctx, archived=False):
        self._owner(ctx.actor)
        rows = [row for row in self.list(ctx.novel_id, ctx.scope, self.NOTES)
                if row.get('created_by') == ctx.actor and (row['status'] == 'ARCHIVED') == archived]
        rows.sort(key=lambda row: (row['updated_at'], row['id']), reverse=True)
        return {'items': [self._decorate_note(ctx, row) for row in rows[:100]], 'truncated': len(rows) > 100}

    def create_note(self, ctx, body, reauthorize=lambda: None):
        data = NoteIn.model_validate(body).model_dump()
        source = self._capture(ctx, data)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            for previous in collection(state, self.NOTES).values():
                if previous.get('created_by') == ctx.actor and previous.get('capture_id') == data['capture_id']:
                    if any(previous.get(key) != value for key, value in data.items()):
                        raise ValueError('capture ID already used; refresh drafts before retrying')
                    reauthorize()
                    return self._decorate_note(ctx, previous)
            reauthorize()
            # Capture again under the transaction before committing provenance.
            if source != self._capture(ctx, data):
                raise StaleSourceError('chapter changed during capture')
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor,
                          {**data, 'source': source, 'status': 'DRAFT', 'included_in_ai_context': False, 'canon': False, 'copies': []})
            collection(state, self.NOTES)[row['id']] = row
            return self._decorate_note(ctx, row)

    def edit_note(self, ctx, note_id, body, reauthorize=lambda: None):
        data = NoteEditIn.model_validate(body).model_dump()
        version = data.pop('expected_version')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._note(ctx, note_id, state)
            if row['status'] != 'DRAFT':
                raise ValueError('restore archived draft before editing')
            source = self._capture(ctx, data)
            reauthorize()
            change_row(row, ctx.actor, version, lambda target: target.update(data, source=source))
            return self._decorate_note(ctx, row)

    def transition_note(self, ctx, note_id, version, action, reauthorize=lambda: None):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._note(ctx, note_id, state)
            if (action, row['status']) not in {('archive', 'DRAFT'), ('restore', 'ARCHIVED')}:
                raise ValueError('invalid inspiration draft transition')
            reauthorize()
            change_row(row, ctx.actor, version, lambda target: target.update(status='ARCHIVED' if action == 'archive' else 'DRAFT'))
            return self._decorate_note(ctx, row)

    def targets(self, ctx):
        if not self.planning:
            raise ValueError('planning service unavailable')
        graphs = {row['id'] for row in self.planning.list_graphs(ctx.novel_id, ctx.scope) if row['status'] == 'ACTIVE'}
        rows = self.planning.list(ctx.novel_id, ctx.scope, self.planning.NODES)
        return {'items': [{'id': row['id'], 'title': row['title'], 'version': row['version'], 'level': row['level']}
                          for row in rows if row['graph_id'] in graphs and row['status'] != 'ARCHIVED'][:100]}

    def _copy_preview(self, ctx, note_id, body, state):
        if not self.planning:
            raise ValueError('planning service unavailable')
        row = self._note(ctx, note_id, state)
        check_version(row, body['expected_version'])
        if row['status'] != 'DRAFT':
            raise ValueError('restore archived draft before copying')
        if self._decorate_note(ctx, row)['source_state'] in {'STALE', 'UNAVAILABLE'}:
            raise StaleSourceError('note chapter changed; edit and review the source link first')
        node = require_row(state, self.planning.NODES, body['node_id'])
        check_version(node, body['expected_node_version'])
        fields = deepcopy(node['fields'])
        text = '\n\n'.join(value for value in [fields.get(body['field'], ''), row['title'], row['text']] if value)
        fields[body['field']] = text
        payload = PlanningProposalIn(node_id=node['id'], expected_node_version=node['version'],
            title=row['title'] or '灵感规划草稿', fields=fields, links=node['links'],
            rationale='用户逐项核对后从项目灵感复制；仍须在规划工具中审核。').model_dump()
        proposal = self.planning._proposal_row(ctx.novel_id, ctx.scope, ctx.actor, deepcopy(payload), state)
        receipt = digest({'note': {k: v for k, v in row.items() if k != 'history'},
                          'node': {k: v for k, v in node.items() if k != 'history'}, 'payload': payload,
                          'sources': proposal['sources'], 'entities': proposal['entity_sources'], 'ancestors': proposal['ancestor_versions']})
        return {'preview_digest': receipt, 'field': body['field'], 'before': node['fields'].get(body['field'], ''),
                'after': text, 'target_title': node['title'], 'note_version': row['version'],
                'target_version': node['version'], 'status_after_copy': 'REVIEW'}, proposal

    def preview_copy(self, ctx, note_id, body):
        data = CopyPreviewIn.model_validate(body).model_dump()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            return self._copy_preview(ctx, note_id, data, state)[0]

    def copy_to_planning(self, ctx, note_id, body, reauthorize=lambda: None):
        data = CopyIn.model_validate(body).model_dump()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._note(ctx, note_id, state)
            for previous in row.get('copies', []):
                if previous['preview_digest'] == data['preview_digest']:
                    reauthorize()
                    return {**previous, 'replayed': True, 'note': self._decorate_note(ctx, row)}
            preview, proposal = self._copy_preview(ctx, note_id, data, state)
            if preview['preview_digest'] != data['preview_digest']:
                raise StaleSourceError('reviewed copy preview changed')
            reauthorize()
            collection(state, self.planning.PROPOSALS)[proposal['id']] = proposal
            receipt = {'proposal_id': proposal['id'], 'preview_digest': preview['preview_digest'], 'status': 'REVIEW'}
            change_row(row, ctx.actor, data['expected_version'], lambda target: target.update(copies=target.get('copies', []) + [receipt]))
            return {**receipt, 'replayed': False, 'note': self._decorate_note(ctx, row)}
