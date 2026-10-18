"""Explicit private staging through the original Asset and Comic owners.

Scope receipt commits and Asset commits are separate. A planned exact Asset ID
is durable before create; retries reconcile that ID, never a broad file scan.
No review, promotion, page attachment, upload route or automatic generation.
"""
from contextlib import contextmanager, ExitStack
import base64
import copy
import re
import errno
import stat
from uuid import uuid4

from .comic_ora_import import preview_ora
from .common import now
from ..services.comic_ora_origin import FIELD, CONTRACT, FEATURES, record

COLLECTION = 'comic_ora_staging_v1'
MAX_RECEIPTS = 32
MAX_BATCH = 8


class ComicOraStaging:
    def __init__(self, comic, workspace):
        if (comic.assets is not workspace.assets or comic.store is not workspace.store.store
                or comic._independent_owner() is not workspace.store):
            raise ValueError('COMIC_ORA_ORIGINAL_OWNERS_REQUIRED')
        self.comic, self.workspace = comic, workspace
        self.store, self.owner, self.assets = comic.store, workspace.store, comic.assets

    def _authority(self, nid, scope, actor, guard):
        guard()
        self.store.key(nid, scope)
        if not isinstance(actor, str) or not 1 <= len(actor) <= 240 or any(ord(c) < 32 or ord(c) == 127 for c in actor):
            raise ValueError('COMIC_ORA_ACTOR_INVALID')
        from .flags import enabled_flags
        if not FEATURES.issubset(enabled_flags()): raise ValueError('COMIC_ORA_FEATURES_REQUIRED')
        self.comic.novels.get(nid)

    @contextmanager
    def _transaction(self, nid, scope, actor, guard):
        self._authority(nid, scope, actor, guard)
        # Raw scope -> original Asset -> original project owner. Project lease
        # outlives scope commit. Never use wrapped CreativeProjectStore.transaction.
        with self.owner.existing_owner_only(), ExitStack() as leases:
            with self.store.transaction(nid, scope) as state:
                leases.enter_context(self.assets.project_scope(nid, scope.get('branch_id'),
                    lambda: self.owner.owner_lease(nid), scope_key=self.store.key(nid, scope)))
                self._authority(nid, scope, actor, guard)
                yield state, self.owner.incarnation(nid)
                self._authority(nid, scope, actor, guard)

    @staticmethod
    def _receipt(state, rid, nid, scope, actor, incarnation):
        row = state['collections'].get(COLLECTION, {}).get(rid)
        if (not isinstance(row, dict) or row.get('novel_id') != nid or row.get('scope') != scope
                or row.get('actor') != actor or row.get('incarnation') != incarnation):
            raise FileNotFoundError(rid)
        if (row.get('id') != rid or row.get('contract') != CONTRACT or not isinstance(row.get('steps'), list)
                or not 1 <= len(row['steps']) <= 256 or type(row.get('version')) is not int
                or not 1 <= row['version'] <= 257
                or any(not isinstance(s, dict) or s.get('state') not in {'PENDING', 'STAGED'} for s in row['steps'])
                or len({s.get('asset_id') for s in row['steps']}) != len(row['steps'])):
            raise ValueError('COMIC_ORA_RECEIPT_CORRUPT')
        return row

    @staticmethod
    def _public(row):
        return {k: copy.deepcopy(row[k]) for k in ('id', 'version', 'archive_sha256', 'status', 'steps', 'losses')}

    def prepare(self, nid, scope, actor, raw, *, archive_sha256, request_key, guard):
        """Explicit staging intent AFTER a separate no-write preview/hash acceptance."""
        self._authority(nid, scope, actor, guard)
        if not isinstance(request_key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', request_key):
            raise ValueError('COMIC_ORA_REQUEST_KEY_INVALID')
        parsed = preview_ora(raw)
        if parsed.report['archive_sha256'] != archive_sha256: raise ValueError('COMIC_ORA_PREVIEW_CHANGED')
        with self._transaction(nid, scope, actor, guard) as (state, incarnation):
            rows = state['collections'].setdefault(COLLECTION, {})
            relevant = [r for r in rows.values() if r.get('incarnation') == incarnation]
            for row in relevant:
                if row.get('actor') == actor and row.get('request_key') == request_key:
                    row = self._receipt(state, row['id'], nid, scope, actor, incarnation)
                    if row['archive_sha256'] != archive_sha256: raise ValueError('COMIC_ORA_IDEMPOTENCY_CONFLICT')
                    return self._public(row)
            if len(relevant) >= MAX_RECEIPTS: raise ValueError('COMIC_ORA_RECEIPT_LIMIT')
            rid = str(uuid4())
            steps = [{**copy.deepcopy(layer), 'asset_id': str(uuid4()), 'state': 'PENDING', 'asset_version': None}
                     for layer in parsed.report['layers']]
            row = dict(id=rid, contract=CONTRACT, novel_id=nid, scope=copy.deepcopy(scope), actor=actor,
                       incarnation=incarnation, request_key=request_key, archive_sha256=archive_sha256,
                       version=1, status='AWAITING_EXPLICIT_STAGE', created_at=now(), steps=steps,
                       losses=parsed.report['losses'])
            rows[rid] = row
            return self._public(row)

    def _origin(self, row, step, index):
        return dict(contract=CONTRACT, actor=row['actor'], scope_key=self.store.key(row['novel_id'], row['scope']),
                    incarnation=row['incarnation'], receipt_id=row['id'], asset_id=step['asset_id'],
                    archive_sha256=row['archive_sha256'], member_sha256=step['member_sha256'],
                    png_sha256=step['png_sha256'], index=index, origin_status='UNVERIFIED_EXTERNAL_RASTER')

    def _verify(self, row, step, index, guard):
        meta = self.assets.get(step['asset_id'], branch_id=row['scope'].get('branch_id'), actor_id=row['actor'])
        if (record(meta) != self._origin(row, step, index) or meta['version'] != 1
                or meta.get('idempotency_key') != 'comic-ora:' + row['id'] + ':' + str(index)):
            raise ValueError('COMIC_ORA_STAGED_ASSET_CHANGED')
        self.assets._verified_content(meta, max_bytes=self.assets.MAX_BYTES, guard=guard)
        return meta

    def _usage_with_planned_orphans(self, state, nid, scope, incarnation):
        # Original quota counts committed metadata, including private/deleted rows.
        # Add ONLY exact IDs durably planned by this original scope/incarnation.
        # Binary-before-metadata crashes must not create invisible retained usage.
        usage = self.assets.project_usage(nid, branch_id=scope.get('branch_id'))
        orphans = {}; seen = set()
        rows = [r for r in state['collections'].get(COLLECTION, {}).values()
                if r.get('incarnation') == incarnation]
        if len(rows) > MAX_RECEIPTS: raise ValueError('COMIC_ORA_RECEIPT_LIMIT')
        for candidate in rows:
            row = self._receipt(state, candidate['id'], nid, scope, candidate['actor'], incarnation)
            for step in row['steps']:
                aid = step['asset_id']
                if aid in seen: raise ValueError('COMIC_ORA_RECEIPT_CORRUPT')
                seen.add(aid)
                if self.assets._meta_path(aid).exists():
                    meta = self.assets._load(aid)
                    if (meta.get('novel_id') != nid or meta.get('_project_binding') != self.assets._scope.binding):
                        raise ValueError('COMIC_ORA_PLANNED_ASSET_CONFLICT')
                    continue  # already counted by original project_usage
                try: info = self.assets._bin_path(aid).lstat()
                except FileNotFoundError: continue
                if (not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= self.assets.MAX_BYTES
                        or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
                    raise ValueError('COMIC_ORA_ORPHAN_CONTENT_INVALID')
                orphans[aid] = info.st_size
        return {'count': usage['count'] + len(orphans), 'bytes': usage['bytes'] + sum(orphans.values())}, orphans

    def stage(self, nid, scope, actor, rid, raw, *, max_steps=1, guard):
        """Explicit bounded stage/resume. Reselect identical archive after restart."""
        self._authority(nid, scope, actor, guard)
        if type(max_steps) is not int or not 1 <= max_steps <= MAX_BATCH: raise ValueError('COMIC_ORA_BATCH_LIMIT')
        parsed = preview_ora(raw)
        completed = 0
        for index, layer in enumerate(parsed.layers):
            with self._transaction(nid, scope, actor, guard) as (state, incarnation):
                row = self._receipt(state, rid, nid, scope, actor, incarnation)
                if (row['archive_sha256'] != parsed.report['archive_sha256']
                        or len(row['steps']) != len(parsed.layers)): raise ValueError('COMIC_ORA_PREVIEW_CHANGED')
                step = row['steps'][index]
                if any(step.get(k) != v for k, v in parsed.report['layers'][index].items()):
                    raise ValueError('COMIC_ORA_RECEIPT_CHANGED')
                if step['state'] == 'STAGED':
                    self._verify(row, step, index, guard)
                    continue
                if step['state'] != 'PENDING': raise ValueError('COMIC_ORA_STEP_INVALID')
                exists = self.assets._meta_path(step['asset_id']).exists()
                if exists:
                    meta = self._verify(row, step, index, guard)
                else:
                    usage, orphans = self._usage_with_planned_orphans(state, nid, scope, incarnation)
                    # Resuming the same orphan converts retained bytes into an
                    # indexed Asset; it does not consume another slot or copy.
                    if (usage['count'] + (0 if step['asset_id'] in orphans else 1) > self.workspace.MAX_ASSETS
                            or usage['bytes'] - orphans.get(step['asset_id'], 0) + len(layer.png) > self.workspace.MAX_PROJECT_BYTES):
                        raise ValueError('CREATIVE_PROJECT_ASSET_QUOTA')
                    self.workspace.storage_admission.require(len(layer.png))
                    def before_commit():
                        self._authority(nid, scope, actor, guard)
                        self.workspace.storage_admission.require(1)
                    try:
                        meta = self.assets.create(nid, 'ora-layer-' + str(index) + '.png',
                            base64.b64encode(layer.png).decode('ascii'), 'image/png', 'image',
                            'comic-ora:' + rid + ':' + str(index), branch_id=scope.get('branch_id'),
                            required_features=tuple(sorted(FEATURES)), owner_actor_id=actor, guard=before_commit,
                            _initial_comic_ora=self._origin(row, step, index))
                    except OSError as exc:
                        if exc.errno == errno.ENOSPC:
                            from ..creative.storage_admission import StudioStorageCapacityError
                            raise StudioStorageCapacityError("CREATIVE_STORAGE_LOW_SPACE") from None
                        raise
                guard()
                step.update(state='STAGED', asset_version=meta['version'])
                row['version'] += 1
                row['status'] = 'STAGED_PRIVATE_REVIEW_PENDING' if all(s['state'] == 'STAGED' for s in row['steps']) else 'PARTIALLY_STAGED'
                completed += 1
            if completed >= max_steps: break
        return self.status(nid, scope, actor, rid, guard=guard)

    def status(self, nid, scope, actor, rid, *, guard):
        self._authority(nid, scope, actor, guard)
        state = self.store.read(nid, scope)
        with self.owner.existing_owner_only(), self.assets.project_scope(nid, scope.get('branch_id'),
                lambda: self.owner.owner_lease(nid), scope_key=self.store.key(nid, scope)):
            row = self._receipt(state, rid, nid, scope, actor, self.owner.incarnation(nid))
            result = self._public(row)
            for index, step in enumerate(row['steps']):
                try:
                    self._verify(row, step, index, guard)
                    result['steps'][index]['observed_state'] = 'STAGED' if step['state'] == 'STAGED' else 'COMMITTED_AWAITING_RECEIPT_RESUME'
                except FileNotFoundError:
                    result['steps'][index]['observed_state'] = ('MISSING_OR_UNAVAILABLE' if step['state'] == 'STAGED'
                        else 'ORPHAN_BINARY_REQUIRES_ARCHIVE_RESUME' if self.assets._bin_path(step['asset_id']).exists()
                        else 'AWAITING_ARCHIVE_STAGE')
            self._authority(nid, scope, actor, guard)
            return result
