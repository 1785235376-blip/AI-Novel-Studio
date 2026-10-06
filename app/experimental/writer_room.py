"""B08 asynchronous collaboration metadata over the original scope/review authorities.

A room is the current authorized scope, not a membership or manuscript store.
No invitations, grants, acceptance proxy, realtime presence or outbound delivery.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import zipfile
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator

from ..authorization import AuthorizationScope, ScopeKind, ModalityDomain
from ..services.creation_workbench_service import CommentIn
from ..services.v1_capability_service import CapabilityVersionConflict
from .common import DomainService, StaleSourceError, change_row, new_row, now, snapshot
from .inbox import ReviewContext
from .planning import StrictModel, digest
from .reader_sources import authorized_chapter_rows, chapter_revision
from .ux import chapter_text

FEATURE = 'writer_room_v2'
COPY_WARNING = '已下载的永久副本无法通过撤销成员权限远程收回。'
MAX_ITEMS = 500
MAX_PACKAGE = 20 * 1024 * 1024


class ChapterRef(StrictModel):
    id: str = Field(min_length=1, max_length=240)
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')


class ReviewRef(StrictModel):
    domain: str = Field(min_length=1, max_length=80)
    id: str = Field(min_length=1, max_length=240)
    version: int = Field(ge=1)


class TaskFields(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=8000)
    assignee: str = Field(min_length=1, max_length=240)
    reviewer: str = Field(min_length=1, max_length=240)


class TaskIn(TaskFields):
    request_id: str = Field(min_length=1, max_length=160)
    chapter: ChapterRef | None = None
    review_target: ReviewRef | None = None


class TaskUpdate(TaskFields):
    expected_version: int = Field(ge=1)
    resolve_conflict_id: str | None = Field(default=None, max_length=160)


class TransitionIn(StrictModel):
    expected_version: int = Field(ge=1)
    action: Literal['start', 'submit', 'request_changes', 'close', 'reopen', 'cancel']
    note: str = Field(default='', max_length=8000)


class ThreadAction(StrictModel):
    expected_version: int = Field(ge=1)
    action: Literal['reply', 'resolve', 'reopen']
    text: str = Field(default='', max_length=8000)


class PackageIn(StrictModel):
    chapters: list[ChapterRef] = Field(default_factory=list, max_length=30)
    asset_ids: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def selection(self):
        if not self.chapters and not self.asset_ids:
            raise ValueError('explicitly select chapters or assets')
        if len({r.id for r in self.chapters}) != len(self.chapters) or len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError('duplicate selected source')
        if any(not value or len(value) > 240 for value in self.asset_ids):
            raise ValueError('invalid asset identifier')
        return self


class PackageConfirm(PackageIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    acknowledge_copy_boundary: bool


class WriterRoomConflict(Exception):
    def __init__(self, row):
        self.record = copy.deepcopy(row)
        super().__init__('Both candidates were preserved. Refresh before resolving.')


class WriterRoomService(DomainService):
    TASKS = 'writer_room_tasks_v2'
    CONFLICTS = 'writer_room_conflicts_v2'

    def __init__(self, store, novels, chapters, *, sources, creation, inbox, assets, membership, asset_authorize=None):
        super().__init__(store, novels, chapters)
        self.sources, self.creation, self.inbox = sources, creation, inbox
        self.assets, self.membership, self.asset_authorize = assets, membership, asset_authorize

    @staticmethod
    def _review_ctx(ctx):
        return ReviewContext(ctx.novel_id, ctx.scope, ctx.actor, ctx.token, ctx.branch)

    def _permission(self, ctx, actor, permission):
        if ctx.scope['mode'] == 'local':
            return actor == ctx.actor == 'local-author'
        services = self.membership()
        scope = AuthorizationScope(ScopeKind.BRANCH, ctx.scope['workspace_id'], ctx.novel_id,
                                   ctx.scope['storyline_id'], ctx.scope['branch_id'])
        try:
            services.identity_service.require_active_membership(actor, scope.workspace_id)
            return services.authorization_service.is_allowed(actor, permission, ModalityDomain.NOVEL, scope)
        except (KeyError, FileNotFoundError, PermissionError):
            return False

    def members(self, ctx):
        if ctx.scope['mode'] == 'local':
            candidates = [{'user_id': ctx.actor}]
        else:
            candidates = self.membership().identity_service.repository.list_memberships(
                workspace_id=ctx.scope['workspace_id'], status='ACTIVE')
        result = []
        for candidate in candidates[:MAX_ITEMS]:
            actor = candidate['user_id']
            if not self._permission(ctx, actor, 'domain.read'):
                continue
            user = self.membership().identity_service.get_user(actor) if ctx.scope['mode'] != 'local' else None
            result.append({'id': actor, 'name': user.display_name if user else '本地作者',
                           'can_write': self._permission(ctx, actor, 'domain.write'),
                           'can_review': self._permission(ctx, actor, 'domain.review')})
        return result

    def _participants(self, ctx, assignee, reviewer):
        if not all((self._permission(ctx, assignee, 'domain.read'), self._permission(ctx, assignee, 'domain.write'), self._permission(ctx, reviewer, 'domain.read'), self._permission(ctx, reviewer, 'domain.review'))):
            raise HTTPException(403, {'code': 'WRITER_ROOM_PARTICIPANT_UNAVAILABLE'})

    def _chapters(self, ctx):
        return authorized_chapter_rows(ctx, self.sources, self.chapters)

    def _chapter(self, ctx, ref):
        row = next((r for r in self._chapters(ctx) if r['id'] == ref.id), None)
        if row is None:
            raise FileNotFoundError(ref.id)
        if chapter_revision(row) != ref.revision:
            raise StaleSourceError('chapter changed; select its current authorized version')
        return row

    def _target(self, ctx, ref):
        reader = getattr(self, 'review_target_readers', {}).get(ref.domain)
        row = reader(ctx, ref.id) if reader else self.inbox.get(self._review_ctx(ctx), ref.domain, ref.id)
        if row['version'] != ref.version or row.get('stale'):
            raise StaleSourceError('domain review target changed; reopen its original review flow')
        return row

    def _source_state(self, ctx, row):
        try:
            if row.get('chapter'): self._chapter(ctx, ChapterRef(**row['chapter']))
            if row.get('review_target'): self._target(ctx, ReviewRef(**row['review_target']))
        except StaleSourceError:
            return 'STALE'
        except FileNotFoundError:
            return 'UNAVAILABLE'
        return 'CURRENT'

    def _public(self, ctx, row):
        result = copy.deepcopy(row)
        result['source_state'] = self._source_state(ctx, row)
        result['participants_current'] = self._permission(ctx, row['assignee'], 'domain.write') and self._permission(ctx, row['reviewer'], 'domain.review')
        result['domain_acceptance'] = 'ORIGINAL_DOMAIN_ONLY'
        return result

    def _rows(self, ctx):
        rows = self.list(ctx.novel_id, ctx.scope, self.TASKS)
        return sorted(rows, key=lambda r: (r['updated_at'], r['id']), reverse=True)

    def overview(self, ctx):
        rows = [r for r in self._rows(ctx) if self._source_state(ctx, r) != 'UNAVAILABLE']
        return {'items': [self._public(ctx, r) for r in rows[:MAX_ITEMS]], 'truncated': len(rows) > MAX_ITEMS,
                'actor': ctx.actor, 'members': self.members(ctx), 'scope': ctx.scope,
                'can_write': self._permission(ctx, ctx.actor, 'domain.write'),
                'can_review': self._permission(ctx, ctx.actor, 'domain.review'),
                'collaboration': 'ASYNC_ONLY', 'presence': 'NOT_IMPLEMENTED',
                'copy_warning': COPY_WARNING, 'approval_authority': 'ORIGINAL_DOMAIN_ONLY'}

    def catalog(self, ctx):
        rows = self._chapters(ctx)
        targets = self.inbox.list(self._review_ctx(ctx))
        assets, asset_state = [], 'AVAILABLE'
        try:
            self._asset_access(ctx)
            assets = self._asset_rows(ctx)
        except HTTPException as exc:
            if exc.status_code not in {401, 403, 404, 501}: raise
            asset_state = 'ORIGINAL_ASSET_AUTHORITY_REQUIRED'
        return {'chapters': [{'id': r['id'], 'title': r.get('title', ''), 'version': r['version'], 'revision': chapter_revision(r)} for r in rows[:MAX_ITEMS]],
                'chapter_state': 'BRANCH_SOURCE_UNAVAILABLE' if ctx.scope['mode'] != 'local' and self.sources.chapter_reader is None else 'AVAILABLE',
                'assets': [{'id': r['id'], 'filename': r['filename'], 'sha256': r['sha256'], 'size': r['size']} for r in assets[:MAX_ITEMS]],
                'asset_state': asset_state,
                'review_targets': [{'domain': r['domain'], 'id': r['id'], 'version': r['version'], 'preview': r['preview'][:200] if isinstance(r.get('preview'), str) else '原领域结构化审核项', 'status': r['status']} for r in targets['items'][:MAX_ITEMS]],
                'unavailable': targets['unavailable'], 'truncated': max(len(rows), len(assets), len(targets['items'])) > MAX_ITEMS}

    def chapter(self, ctx, cid, revision):
        row = self._chapter(ctx, ChapterRef(id=cid, revision=revision))
        # Plain text projection only; there is no manuscript mutation endpoint.
        return {'id': cid, 'version': row['version'], 'revision': chapter_revision(row),
                'title': row.get('title', ''), 'text': chapter_text(row), 'mode': 'READ_ONLY'}

    def create_task(self, ctx, body, check):
        self._participants(ctx, body.assignee, body.reviewer)
        if body.chapter: self._chapter(ctx, body.chapter)
        if body.review_target: self._target(ctx, body.review_target)
        payload = body.model_dump(mode='json')
        with self.store.transaction(ctx.novel_id, ctx.scope) as doc:
            check(); self._participants(ctx, body.assignee, body.reviewer)
            rows = doc['collections'].setdefault(self.TASKS, {})
            previous = next((r for r in rows.values() if r['created_by'] == ctx.actor and r['request_id'] == body.request_id), None)
            if previous:
                if previous['request_digest'] != digest(payload): raise ValueError('request id reused with different content')
                return copy.deepcopy(previous)
            if len(rows) >= MAX_ITEMS: raise ValueError('scope task limit reached')
            if body.chapter: self._chapter(ctx, body.chapter)
            if body.review_target: self._target(ctx, body.review_target)
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**payload, 'request_digest': digest(payload), 'status': 'ASSIGNED', 'events': []})
            rows[row['id']] = row; check()
            return copy.deepcopy(row)

    def _conflict(self, doc, ctx, target, current, submitted):
        rows = doc['collections'].setdefault(self.CONFLICTS, {})
        if len(rows) >= MAX_ITEMS: raise ValueError('conflict limit reached; preserve this input locally')
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'target': target, 'current_candidate': snapshot(current),
                      'submitted_candidate': copy.deepcopy(submitted), 'status': 'OPEN'})
        rows[row['id']] = row
        return copy.deepcopy(row)

    def update_task(self, ctx, rid, body, check):
        conflict = None
        with self.store.transaction(ctx.novel_id, ctx.scope) as doc:
            check()
            row = self.get(ctx.novel_id, ctx.scope, self.TASKS, rid)
            if self._source_state(ctx, row) == 'UNAVAILABLE': raise FileNotFoundError(rid)
            if ctx.actor not in {row['created_by'], row['assignee'], row['reviewer']}:
                raise HTTPException(403, {'code': 'WRITER_ROOM_TASK_ACTOR_REQUIRED'})
            # Source/assignee are immutable in conflict candidates until explicitly
            # saved against a current version. Never last-write-wins.
            self._participants(ctx, body.assignee, body.reviewer)
            if row['version'] != body.expected_version:
                conflict = self._conflict(doc, ctx, {'kind': 'task', 'id': rid}, row, body.model_dump(mode='json'))
            else:
                fields = body.model_dump(include={'title', 'description', 'assignee', 'reviewer'})
                change_row(row, ctx.actor, body.expected_version, lambda value: value.update(fields))
                doc['collections'][self.TASKS][rid] = row
                if body.resolve_conflict_id:
                    saved = doc['collections'].get(self.CONFLICTS, {}).get(body.resolve_conflict_id)
                    if not saved or saved['target'] != {'kind': 'task', 'id': rid} or saved['status'] != 'OPEN':
                        raise ValueError('conflict is unavailable or already resolved')
                    change_row(saved, ctx.actor, saved['version'], lambda value: value.update(status='RESOLVED', resolution_task_version=row['version']))
            check()
        if conflict: raise WriterRoomConflict(conflict)
        return self._public(ctx, row)

    def transition(self, ctx, rid, body, check):
        rules = {'start': ({'ASSIGNED', 'CHANGES_REQUESTED'}, 'IN_PROGRESS', 'assignee'),
                 'submit': ({'IN_PROGRESS', 'CHANGES_REQUESTED'}, 'READY_FOR_REVIEW', 'assignee'),
                 'request_changes': ({'READY_FOR_REVIEW'}, 'CHANGES_REQUESTED', 'reviewer'),
                 'close': ({'READY_FOR_REVIEW'}, 'CLOSED', 'reviewer'),
                 'reopen': ({'CLOSED', 'CANCELLED'}, 'ASSIGNED', 'reviewer'),
                 'cancel': ({'ASSIGNED', 'IN_PROGRESS', 'CHANGES_REQUESTED', 'READY_FOR_REVIEW'}, 'CANCELLED', 'created_by')}
        before, after, responsible = rules[body.action]
        if body.action == 'request_changes' and not body.note.strip(): raise ValueError('change request needs a reason')
        conflict = None
        with self.store.transaction(ctx.novel_id, ctx.scope) as doc:
            check(); row = self.get(ctx.novel_id, ctx.scope, self.TASKS, rid)
            if self._source_state(ctx, row) == 'UNAVAILABLE': raise FileNotFoundError(rid)
            if ctx.actor != row[responsible]: raise HTTPException(403, {'code': 'WRITER_ROOM_RESPONSIBLE_ACTOR_REQUIRED'})
            if responsible == 'reviewer' and not self._permission(ctx, ctx.actor, 'domain.review'):
                raise HTTPException(403, {'code': 'WRITER_ROOM_REVIEW_AUTHORITY_REQUIRED'})
            self._participants(ctx, row['assignee'], row['reviewer'])
            if row['version'] != body.expected_version:
                conflict = self._conflict(doc, ctx, {'kind': 'transition', 'id': rid}, row, body.model_dump(mode='json'))
            else:
                if row['status'] not in before: raise ValueError('transition is unavailable from current status')
                if body.action in {'submit', 'close'} and self._source_state(ctx, row) != 'CURRENT':
                    raise StaleSourceError('task source changed; review it in the original authority and create a new linked task')
                def apply(value):
                    value['status'] = after
                    value['events'].append({'action': body.action, 'actor': ctx.actor, 'at': now(), 'note': body.note})
                change_row(row, ctx.actor, body.expected_version, apply)
                doc['collections'][self.TASKS][rid] = row
            check()
        if conflict: raise WriterRoomConflict(conflict)
        return self._public(ctx, row)

    def conflicts(self, ctx):
        rows = self.list(ctx.novel_id, ctx.scope, self.CONFLICTS)
        tasks = {r['id']: r for r in self._rows(ctx)}
        comment_ids = None
        visible = []
        for row in rows:
            target = row['target']
            if target['kind'] == 'comment':
                if comment_ids is None: comment_ids = {r['id'] for r in self.comments(ctx)['items']}
                if target['id'] not in comment_ids: continue
            else:
                task = tasks.get(target['id'])
                if task is None or self._source_state(ctx, task) == 'UNAVAILABLE': continue
            visible.append(row)
        return {'items': sorted(visible, key=lambda r: r['created_at'], reverse=True)[:MAX_ITEMS]}

    def index(self, ctx, query):
        needle = query.casefold()
        rows = [r for r in self._rows(ctx) if self._source_state(ctx, r) != 'UNAVAILABLE' and needle in (r['title'] + '\n' + r['description']).casefold()]
        return {'items': [self._public(ctx, r) for r in rows[:MAX_ITEMS]], 'total': len(rows), 'cache': 'NONE'}

    def notices(self, ctx):
        rows = [r for r in self._rows(ctx) if self._source_state(ctx, r) != 'UNAVAILABLE' and r['status'] not in {'CLOSED', 'CANCELLED'} and ctx.actor in {r['assignee'], r['reviewer']}]
        return {'items': [{'id': r['id'] + ':' + str(r['version']), 'task_id': r['id'], 'title': r['title'], 'status': r['status'], 'version': r['version']} for r in rows[:MAX_ITEMS]],
                'delivery': 'PULL_CURRENT_AUTHORITY', 'realtime': False}

    def comments(self, ctx):
        allowed = {r['id'] for r in self._chapters(ctx)}
        if not allowed: return {'items': [], 'source_state': 'BRANCH_SOURCE_UNAVAILABLE' if ctx.scope['mode'] != 'local' else 'EMPTY'}
        rows = self.creation.list_comments(ctx.novel_id, ctx.scope)['items']
        return {'items': [r for r in rows if r['anchor']['chapter_id'] in allowed][:MAX_ITEMS], 'source_state': 'AVAILABLE'}

    def create_comment(self, ctx, body, check):
        # Legacy comments validate current versions/quotes themselves. B08 adds
        # the stricter authorized-source fence before invoking that authority.
        row = next((r for r in self._chapters(ctx) if r['id'] == body.chapter_id), None)
        if row is None: raise FileNotFoundError(body.chapter_id)
        if row['version'] != body.chapter_version: raise StaleSourceError('comment source changed')
        ref = ChapterRef(id=row['id'], revision=chapter_revision(row))
        def current():
            check(); self._chapter(ctx, ref)
        current()
        return self.creation.create_comment(ctx.novel_id, ctx.scope, ctx.actor, body, reauthorize=current)

    def comment_action(self, ctx, rid, body, check):
        if not any(r['id'] == rid for r in self.comments(ctx)['items']): raise FileNotFoundError(rid)
        def current():
            check()
            if not any(r['id'] == rid for r in self.comments(ctx)['items']): raise FileNotFoundError(rid)
        current()
        try:
            return self.creation.update_comment(ctx.novel_id, ctx.scope, ctx.actor, rid, body.action, body.expected_version, body.text, reauthorize=current)
        except CapabilityVersionConflict as exc:
            with self.store.transaction(ctx.novel_id, ctx.scope) as doc:
                check()
                conflict = self._conflict(doc, ctx, {'kind': 'comment', 'id': rid}, exc.current, body.model_dump(mode='json'))
            raise WriterRoomConflict(conflict) from None

    def _asset_access(self, ctx):
        if self.asset_authorize: self.asset_authorize(ctx)
        elif ctx.scope['mode'] != 'local': raise HTTPException(403, {'code': 'ORIGINAL_ASSET_AUTHORITY_REQUIRED'})

    def _asset_rows(self, ctx):
        return [r for r in self.assets.list(ctx.novel_id, branch_id=ctx.branch, actor_id=ctx.actor)
                if r.get('branch_id') == ctx.branch]

    def _package(self, ctx, body, with_bytes=False):
        chapter_rows = [self._chapter(ctx, ref) for ref in body.chapters]
        if body.asset_ids: self._asset_access(ctx)
        allowed_assets = {r['id']: r for r in self._asset_rows(ctx)} if body.asset_ids else {}
        selected_assets = []
        for aid in body.asset_ids:
            if aid not in allowed_assets: raise FileNotFoundError(aid)
            selected_assets.append(allowed_assets[aid])
        total = sum(len(chapter_text(r).encode()) for r in chapter_rows) + sum(r['size'] for r in selected_assets)
        if total > MAX_PACKAGE: raise ValueError('selected package exceeds 20 MiB')
        # Selected bytes plus minimal source metadata. No parent assets, prompt,
        # credentials, comments, history, local paths or other project records.
        manifest = {'format': 'ai-novel-restricted-review/1', 'copy_warning': COPY_WARNING,
                    'chapters': [{'id': r['id'], 'title': r.get('title', ''), 'version': r['version'], 'revision': chapter_revision(r), 'file': f'chapters/{i + 1:03d}.txt'} for i, r in enumerate(chapter_rows)],
                    'assets': [{'id': r['id'], 'sha256': r['sha256'], 'size': r['size'], 'media_type': r['media_type'], 'file': f'assets/{i + 1:03d}.bin'} for i, r in enumerate(selected_assets)]}
        preview = {'manifest': manifest, 'preview_digest': digest({'scope': ctx.scope, 'actor': ctx.actor, 'manifest': manifest}), 'selected_bytes': total,
                   'transmission': 'LOCAL_DOWNLOAD_ONLY', 'permission_change': False}
        if not with_bytes: return preview
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode())
            for row, meta in zip(chapter_rows, manifest['chapters']): archive.writestr(meta['file'], chapter_text(row).encode())
            for row, meta in zip(selected_assets, manifest['assets']):
                content = self.assets.content(row['id'], branch_id=ctx.branch, actor_id=ctx.actor)
                if hashlib.sha256(content).hexdigest() != row['sha256']: raise StaleSourceError('selected asset changed')
                archive.writestr(meta['file'], content)
        return preview, out.getvalue()

    def package_preview(self, ctx, body):
        return self._package(ctx, body)

    def package_download(self, ctx, body, check):
        if not body.acknowledge_copy_boundary: raise ValueError('acknowledge downloaded-copy limitation')
        check(); preview, raw = self._package(ctx, body, True)
        if preview['preview_digest'] != body.preview_digest: raise StaleSourceError('selection changed; preview again')
        check()
        return {'filename': 'restricted-review.zip', 'mime': 'application/zip', 'content_base64': base64.b64encode(raw).decode(),
                'sha256': hashlib.sha256(raw).hexdigest(), 'copy_warning': COPY_WARNING}
