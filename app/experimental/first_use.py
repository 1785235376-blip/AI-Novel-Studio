"""U10 orchestration receipts; all manuscript writes use original authorities.

One bounded receipt per actor/workspace. This metadata is not a project store.
A committed intent precedes every non-idempotent create. An interrupted create
is never repeated, even when a client retries or a different process recovers.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from uuid import uuid4

from fastapi import HTTPException
from pydantic import Field

from ..document import markdown_to_document
from .planning import StrictModel
from .flags import require_flag

SAMPLE_TITLE = '灯塔来信 · 独立练习'
CHAPTER_TITLE = '第一章 灯亮之前'
SAMPLE_TEXT = ('# 第一章 灯亮之前\n\n傍晚，林青在旧灯塔的台阶上找到一封没有署名的信。'
               '信纸只写着一句话：今晚请留一盏灯。\n\n她把信夹进笔记本，推开门。'
               '海风穿过空荡的楼梯，楼顶传来一声轻轻的敲击。\n\n'
               '这是原创合成练习。请在这里写下接下来发生的事，再保存自己的版本。')
SAMPLE_DOCUMENT = markdown_to_document(SAMPLE_TEXT)
EMPTY_DOCUMENT = markdown_to_document(f'# {CHAPTER_TITLE}\n\n')
COLLECTION = 'first_use_receipts_v1'


class FirstUseIn(StrictModel):
    workspace_id: str | None = Field(default=None, min_length=1, max_length=160)


@dataclass(frozen=True)
class FirstUseContext:
    actor: str
    workspace_id: str | None
    token: str | None = None


class OriginalFirstUseAuthorities:
    """Thin adapter over the existing local and collaboration write boundaries."""
    def __init__(self, api, collaboration_read_service):
        self.api = api
        self.collaboration = collaboration_read_service

    def context(self, workspace_id, token, *, create=False):
        require_flag('workspace_tools_v2')
        api = self.api
        if workspace_id:
            admin = api.collaboration_admin_service
            actor = admin.actor(token, workspace_id)
            if create:
                admin.require_admin(actor, workspace_id)
            return FirstUseContext(actor.actor_id, workspace_id, token)
        # Never downgrade a scoped/packaged session into the local authority.
        if api.settings.enable_collaboration_runtime or api.settings.enable_packaged_runtime or token:
            raise HTTPException(400, {'code': 'FIRST_USE_WORKSPACE_REQUIRED'})
        return FirstUseContext('local-author', None)

    def current(self, ctx, *, create=False):
        current = self.context(ctx.workspace_id, ctx.token, create=create)
        if current.actor != ctx.actor:
            raise HTTPException(403, {'code': 'FIRST_USE_AUTHORITY_CHANGED'})
        return current

    def target(self, ctx, row, *, write=False):
        self.current(ctx)
        nid = row['project_id']
        if ctx.workspace_id:
            path = row.get('path')
            if not path:
                # Navigation is resolved only for the project returned by the
                # original create, never a client-supplied or name-matched ID.
                scopes = self.api.collaboration_scope_service
                stories = scopes.list_storylines(ctx.workspace_id, nid)
                if len(stories) != 1:
                    raise HTTPException(404, {'code': 'FIRST_USE_TARGET_UNAVAILABLE'})
                branches = scopes.list_branches(ctx.workspace_id, nid, stories[0]['id'])
                if len(branches) != 1:
                    raise HTTPException(404, {'code': 'FIRST_USE_TARGET_UNAVAILABLE'})
                path = {'workspace_id': ctx.workspace_id, 'project_id': nid,
                        'storyline_id': stories[0]['id'], 'branch_id': branches[0]['id'],
                        'project_name': SAMPLE_TITLE, 'storyline_name': stories[0]['name'], 'branch_name': branches[0]['name']}
            self.collaboration.context(ctx.token, ctx.workspace_id, nid,
                path['storyline_id'], path['branch_id'], 'domain.write' if write else 'domain.read')
            return deepcopy(path)
        self.api.novel_service.get(nid)
        return None

    def create_project(self, ctx, row):
        self.current(ctx, create=True)
        if ctx.workspace_id:
            admin = self.api.collaboration_admin_service
            actor = admin.actor(ctx.token, ctx.workspace_id)
            admin.require_admin(actor, ctx.workspace_id)
            if admin.path_mutations is None:
                raise HTTPException(501, {'code': 'PATH_MUTATION_NOT_SUPPORTED'})
            return admin.path_mutations.create_project(ctx.workspace_id, SAMPLE_TITLE, '原创合成练习', actor)
        return self.api.create_novel(self.api.NovelIn(id=row['reserved_project_id'], title=SAMPLE_TITLE, genre='原创合成练习'))

    def create_chapter(self, ctx, row):
        path = self.target(ctx, row, write=True)
        if ctx.workspace_id:
            actor, scope = self.collaboration.context(ctx.token, ctx.workspace_id, row['project_id'],
                path['storyline_id'], path['branch_id'], 'domain.write')
            return self.collaboration.create_chapter(actor, scope, CHAPTER_TITLE)
        return self.api.create_chapter(row['project_id'], self.api.ChapterIn(title=CHAPTER_TITLE))

    def read_chapter(self, ctx, row):
        self.target(ctx, row)
        chapter = self.api.chapter_service.get(row['chapter_id'])
        if chapter.get('novel_id') != row['project_id'] or chapter.get('is_archived'):
            raise HTTPException(404, {'code': 'FIRST_USE_CHAPTER_UNAVAILABLE'})
        return chapter

    def save_chapter(self, ctx, row):
        path = self.target(ctx, row, write=True)
        if ctx.workspace_id:
            actor, scope = self.collaboration.context(ctx.token, ctx.workspace_id, row['project_id'],
                path['storyline_id'], path['branch_id'], 'domain.write')
            return self.api.collaboration_application_service.update_chapter(actor=actor, scope=scope,
                chapter_id=row['chapter_id'], document=deepcopy(SAMPLE_DOCUMENT),
                expected_version=row['chapter_version'], reason='MANUAL_SAVE')
        return self.api.update_chapter(row['chapter_id'], self.api.ChapterUpdate(
            document=deepcopy(SAMPLE_DOCUMENT), content=SAMPLE_TEXT, version=row['chapter_version'], source='MANUAL_SAVE'),
            x_session_token=None, x_branch_id=None)


class FirstUseService:
    def __init__(self, store, authority):
        self.store, self.authority = store, authority

    @staticmethod
    def journal(ctx):
        # Private synthetic metadata key, not an original manuscript/project ID.
        owner = hashlib.sha256(f'{ctx.actor}\0{ctx.workspace_id or "local"}'.encode()).hexdigest()
        nid = 'first-use-' + owner
        return nid, {'mode': 'local', 'novel_id': nid}

    def _read(self, ctx):
        nid, scope = self.journal(ctx)
        return deepcopy(self.store.read(nid, scope)['collections'].get(COLLECTION, {}).get('sample'))

    def _update(self, ctx, expected, **changes):
        nid, scope = self.journal(ctx)
        with self.store.transaction(nid, scope) as doc:
            rows = doc['collections'].setdefault(COLLECTION, {})
            row = rows.get('sample')
            if not row or row['version'] != expected:
                raise HTTPException(409, {'code': 'FIRST_USE_RECEIPT_CHANGED'})
            row.update(deepcopy(changes), version=expected + 1)
            return deepcopy(row)

    def inspect(self, ctx, row=None):
        self.authority.current(ctx)
        row = row or self._read(ctx)
        if not row:
            return {'item': None, 'model_calls': 0}
        result = deepcopy(row)
        result.pop('reserved_project_id', None)
        result.pop('initial_document', None)
        if row.get('project_id'):
            try:
                result['path'] = self.authority.target(ctx, row)
            except (FileNotFoundError, KeyError):
                result.update(availability='UNAVAILABLE', path=None)
                return {'item': result, 'model_calls': 0}
            except HTTPException as exc:
                if exc.status_code == 404:
                    result.update(availability='UNAVAILABLE', path=None)
                    return {'item': result, 'model_calls': 0}
                raise
            result['availability'] = 'AVAILABLE'
        else:
            result['availability'] = 'NOT_CREATED' if row['stage'] == 'REQUESTED' else 'UNKNOWN'
        # A project opened after interruption can be completed manually. Only
        # confirmed IDs are exposed; the local reservation is never called saved.
        result['can_open'] = bool(row.get('project_id')) and result['availability'] == 'AVAILABLE'
        result['can_recover'] = row['stage'] in {'PROJECT_READY', 'CHAPTER_CREATED', 'CHAPTER_READY', 'SAVING_SAMPLE'} and result['availability'] == 'AVAILABLE'
        return {'item': result, 'model_calls': 0}

    def start(self, ctx):
        self.authority.current(ctx, create=True)
        nid, scope = self.journal(ctx)
        with self.store.transaction(nid, scope) as doc:
            rows = doc['collections'].setdefault(COLLECTION, {})
            existing = rows.get('sample')
            if existing:
                row, fresh = deepcopy(existing), False
            else:
                row = {'id': str(uuid4()), 'version': 1, 'stage': 'CREATING_PROJECT',
                       'project_id': None, 'chapter_id': None, 'path': None,
                       'reserved_project_id': 'first-use-sample-' + uuid4().hex if not ctx.workspace_id else None,
                       'synthetic': True, 'sample_version': 1}
                rows['sample'] = deepcopy(row)
                fresh = True
        if not fresh:
            return self.inspect(ctx, row)
        try:
            project = self.authority.create_project(ctx, row)
            # Persist the returned project immediately, before navigation or any
            # chapter call. A navigation failure must not lose the owned ID.
            row = self._update(ctx, row['version'], stage='PROJECT_READY', project_id=project['id'])
        except Exception:
            # Intent remains durable. Retrying start never creates again.
            return self.inspect(ctx)
        return self._continue(ctx, row)

    def recover(self, ctx):
        self.authority.current(ctx)
        row = self._read(ctx)
        if not row:
            return self.inspect(ctx)
        # No automatic/name-based reconciliation of an unknown project or
        # chapter create. Existing authority lacks a create-idempotency receipt.
        if row['stage'] in {'CREATING_PROJECT', 'CREATING_CHAPTER', 'READY', 'SOURCE_CHANGED'}:
            return self.inspect(ctx, row)
        return self._continue(ctx, row)

    def _continue(self, ctx, row):
        if row['stage'] == 'PROJECT_READY':
            path = self.authority.target(ctx, row, write=True)
            row = self._update(ctx, row['version'], stage='CREATING_CHAPTER', path=path)
            try:
                chapter = self.authority.create_chapter(ctx, row)
                row = self._update(ctx, row['version'], stage='CHAPTER_CREATED', chapter_id=chapter['id'])
            except Exception:
                return self.inspect(ctx)
        if row['stage'] == 'CHAPTER_CREATED':
            current = self.authority.read_chapter(ctx, row)
            if current['version'] != 1 or current['document'] != EMPTY_DOCUMENT:
                row = self._update(ctx, row['version'], stage='SOURCE_CHANGED')
            else:
                row = self._update(ctx, row['version'], stage='CHAPTER_READY', chapter_version=1, initial_document=EMPTY_DOCUMENT)
        if row['stage'] in {'CHAPTER_READY', 'SAVING_SAMPLE'}:
            current = self.authority.read_chapter(ctx, row)
            if (current['version'] == row['chapter_version'] + 1 and current['document'] == SAMPLE_DOCUMENT):
                row = self._update(ctx, row['version'], stage='READY', seed_version=current['version'])
            elif current['version'] != row['chapter_version'] or current['document'] != row['initial_document']:
                row = self._update(ctx, row['version'], stage='SOURCE_CHANGED')
            else:
                self.authority.target(ctx, row, write=True)
                row = self._update(ctx, row['version'], stage='SAVING_SAMPLE')
                try:
                    saved = self.authority.save_chapter(ctx, row)
                    row = self._update(ctx, row['version'], stage='READY', seed_version=saved['version'])
                except Exception:
                    return self.inspect(ctx)
        return self.inspect(ctx, row)
