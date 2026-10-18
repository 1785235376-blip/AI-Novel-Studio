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
from .common import now, check_version, change_row
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
    def _transaction(self, nid, scope, actor, guard, *, bound_assets=True):
        self._authority(nid, scope, actor, guard)
        if not bound_assets:
            with self.comic._independent_transaction(nid, scope) as state:
                self._authority(nid, scope, actor, guard)
                yield state, self.owner.incarnation(nid)
                self._authority(nid, scope, actor, guard)
            return
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
                or not 1 <= row['version'] <= 515
                or any(not isinstance(s, dict) or s.get('state') not in {'PENDING', 'STAGED', 'REVIEWED'} for s in row['steps'])
                or len({s.get('asset_id') for s in row['steps']}) != len(row['steps'])):
            raise ValueError('COMIC_ORA_RECEIPT_CORRUPT')
        return row

    @staticmethod
    def _public(row):
        value = {k: copy.deepcopy(row[k]) for k in ('id', 'version', 'archive_sha256', 'status', 'steps', 'losses')}
        if row.get('review'):
            value['losses'] = [loss for loss in value['losses'] if loss != 'NO_ASSET_STAGING_REVIEW_OR_PAGE_ATTACHMENT'] + [
                'ASSET_REVIEW_DOES_NOT_RECOVER_OR_VERIFY_ORIGINAL_GENERATION_PROVENANCE']
            value['review_digest'] = row['review']['review_digest']
            value['manifest_digest'] = row['review']['manifest_digest']
        if row.get('attachment'): value['attachment'] = copy.deepcopy(row['attachment'])
        return value

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
        if (record(meta) != self._origin(row, step, index) or meta['version'] not in (1, 2)
                or meta.get('idempotency_key') != 'comic-ora:' + row['id'] + ':' + str(index)):
            raise ValueError('COMIC_ORA_STAGED_ASSET_CHANGED')
        if meta.get('_comic_ora_review') is not None:
            if not row.get('review') or meta['_comic_ora_review'] != self._review_proof(row, step) or meta['version'] != 2:
                raise ValueError('COMIC_ORA_REVIEW_CHANGED')
        elif step['state'] == 'REVIEWED' or meta['version'] != 1:
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
                if step['state'] in {'STAGED', 'REVIEWED'}:
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
                    meta = self._verify(row, step, index, guard)
                    result['steps'][index]['observed_state'] = ('REVIEWED' if step['state'] == 'REVIEWED' else 'REVIEW_COMMITTED_AWAITING_RECEIPT_RESUME') if meta.get('_comic_ora_review') else 'STAGED' if step['state'] == 'STAGED' else 'COMMITTED_AWAITING_RECEIPT_RESUME'
                except FileNotFoundError:
                    result['steps'][index]['observed_state'] = ('MISSING_OR_UNAVAILABLE' if step['state'] in {'STAGED', 'REVIEWED'}
                        else 'ORPHAN_BINARY_REQUIRES_ARCHIVE_RESUME' if self.assets._bin_path(step['asset_id']).exists()
                        else 'AWAITING_ARCHIVE_STAGE')
            self._authority(nid, scope, actor, guard)
            return result

    @staticmethod
    def _digest(value):
        from .store import canonical
        import hashlib
        return hashlib.sha256(canonical(value).encode()).hexdigest()

    def _manifest(self, row, parsed, guard):
        if row['archive_sha256'] != parsed.report['archive_sha256'] or len(row['steps']) != len(parsed.layers):
            raise ValueError('COMIC_ORA_PREVIEW_CHANGED')
        pins = []
        for index, step in enumerate(row['steps']):
            if step['state'] not in {'STAGED', 'REVIEWED'}: raise ValueError('COMIC_ORA_STAGING_INCOMPLETE')
            if any(step.get(k) != v for k, v in parsed.report['layers'][index].items()):
                raise ValueError('COMIC_ORA_RECEIPT_CHANGED')
            self._verify(row, step, index, guard)
            pins.append({k: copy.deepcopy(v) for k, v in step.items() if k not in {'state', 'asset_version'}} |
                        {'staged_version': 1})
        return {'receipt_id': row['id'], 'scope_key': self.store.key(row['novel_id'], row['scope']),
                'incarnation': row['incarnation'], 'actor': row['actor'], 'archive_sha256': row['archive_sha256'],
                'page': {'width': parsed.report['width'], 'height': parsed.report['height']}, 'layers': pins,
                'origin_classification': 'UNVERIFIED_RASTER', 'native_text_recovered': False}

    def review_manifest(self, nid, scope, actor, rid, raw, *, guard):
        self._authority(nid, scope, actor, guard)
        parsed = preview_ora(raw)
        state = self.store.read(nid, scope)
        with self.owner.existing_owner_only(), self.assets.project_scope(nid, scope.get('branch_id'),
                lambda: self.owner.owner_lease(nid), scope_key=self.store.key(nid, scope)):
            row = self._receipt(state, rid, nid, scope, actor, self.owner.incarnation(nid))
            manifest = self._manifest(row, parsed, guard)
            self._authority(nid, scope, actor, guard)
            return {'manifest': manifest, 'manifest_digest': self._digest(manifest)}

    @staticmethod
    def _review_proof(row, step):
        review = row['review']
        return {'contract': 'comic-ora-reviewed-raster/1', 'receipt_id': row['id'], 'actor': row['actor'],
                'manifest_digest': review['manifest_digest'], 'review_digest': review['review_digest'],
                'archive_sha256': row['archive_sha256'], 'png_sha256': step['png_sha256'],
                'origin_classification': 'UNVERIFIED_RASTER', 'license_note': review['license_note'],
                'native_text_recovered': False}

    def review(self, nid, scope, actor, rid, raw, *, manifest_digest, license_note,
               acknowledge_raster_text, max_steps=1, guard):
        """Explicit original Asset review; each promotion survives receipt rollback."""
        from ..services.comic_ora_origin import reviewed, seal_review
        self._authority(nid, scope, actor, guard)
        if acknowledge_raster_text is not True: raise ValueError('COMIC_ORA_RASTER_LOSS_ACK_REQUIRED')
        if type(max_steps) is not int or not 1 <= max_steps <= MAX_BATCH: raise ValueError('COMIC_ORA_BATCH_LIMIT')
        parsed = preview_ora(raw)
        # Persist immutable review intent before the first separate Asset commit.
        with self._transaction(nid, scope, actor, guard) as (state, incarnation):
            row = self._receipt(state, rid, nid, scope, actor, incarnation)
            manifest = self._manifest(row, parsed, guard)
            if self._digest(manifest) != manifest_digest: raise ValueError('COMIC_ORA_REVIEW_MANIFEST_CHANGED')
            review = {'manifest': manifest, 'manifest_digest': manifest_digest, 'license_note': license_note}
            review['review_digest'] = self._digest(review)
            # Same validator used by the original Asset hook, before receipt writes.
            reviewed(self._review_proof({**row, 'review': review}, row['steps'][0]), self._origin(row, row['steps'][0], 0))
            if row.get('review') is not None and row['review'] != review: raise ValueError('COMIC_ORA_REVIEW_INTENT_IMMUTABLE')
            if not row.get('review'):
                row['review'] = review; row['version'] += 1; row['status'] = 'REVIEW_IN_PROGRESS'
        completed = 0
        for index in range(len(parsed.layers)):
            with self._transaction(nid, scope, actor, guard) as (state, incarnation):
                row = self._receipt(state, rid, nid, scope, actor, incarnation)
                step = row['steps'][index]
                meta = self._verify(row, step, index, guard)
                if step['state'] == 'REVIEWED': continue
                proof = self._review_proof(row, step)
                def before_commit(): self._authority(nid, scope, actor, guard)
                self.assets.promote_owned(step['asset_id'], actor_id=actor, branch_id=scope.get('branch_id'),
                    expected_version=1, provenance=proof, guard=before_commit,
                    _comic_ora_review=seal_review(self._origin(row, step, index), proof))
                self._authority(nid, scope, actor, guard)
                step.update(state='REVIEWED', asset_version=2)
                row['version'] += 1
                row['status'] = 'REVIEWED_READY_FOR_ATTACHMENT' if all(s['state'] == 'REVIEWED' for s in row['steps']) else 'REVIEW_IN_PROGRESS'
                completed += 1
            if completed >= max_steps: break
        return self.status(nid, scope, actor, rid, guard=guard)

    def attach(self, nid, scope, actor, rid, page_id, *, expected_page_version, review_digest, guard):
        """Only receipt + existing independent page CAS commit atomically together."""
        from .comic_layouts import LayoutIn
        from .comic_layers import ora_decode_budget
        with ora_decode_budget(), self._transaction(nid, scope, actor, guard, bound_assets=False) as (state, incarnation):
            row = self._receipt(state, rid, nid, scope, actor, incarnation)
            if not row.get('review') or row['review']['review_digest'] != review_digest:
                raise ValueError('COMIC_ORA_REVIEW_CHANGED')
            if any(s['state'] != 'REVIEWED' for s in row['steps']): raise ValueError('COMIC_ORA_REVIEW_INCOMPLETE')
            page = state['collections'].get(self.comic.RECORDS, {}).get(page_id)
            if (not isinstance(page, dict) or page.get('created_by') != actor or page.get('novel_id') != nid
                    or page.get('scope') != scope or page.get('project_incarnation') != incarnation
                    or not self.comic._independent(page)):
                raise FileNotFoundError(page_id)
            with self.workspace._asset_scope(nid, scope):
                for index, step in enumerate(row['steps']): self._verify(row, step, index, guard)
            self.comic._current(nid, scope, actor, page)
            existing = row.get('attachment')
            if existing:
                if (existing['page_id'] != page_id or existing['expected_page_version'] != expected_page_version
                        or existing['page_version'] != page['version']
                        or existing['document_digest'] != self._digest(page['document'])):
                    raise ValueError('COMIC_ORA_ATTACHMENT_REPLAY_CHANGED')
                return {'receipt': self._public(row), 'page': self.comic._view(nid, scope, actor, page)}
            check_version(page, expected_page_version)
            if len(page['history']) >= 100: raise ValueError('COMIC_REVISION_LIMIT_CREATE_NEW_LAYOUT')
            document = copy.deepcopy(page['document'])
            if {k: document[k] for k in ('width', 'height')} != row['review']['manifest']['page']:
                raise ValueError('COMIC_ORA_PAGE_DIMENSIONS_MISMATCH')
            if 'layer_stack' not in document:
                items = []
                for panel in sorted(document['panels'], key=lambda p: p['order']):
                    refs = [(k, panel['id']) for k in ('PANEL_ART', 'PANEL_FRAME')]
                    refs += [(k, b['id']) for b in panel['bubbles'] for k in ('BUBBLE_SHAPE', 'BUBBLE_TEXT')]
                    items += [{'id': 'layer_' + str(uuid4()), 'kind': k, 'target_id': target,
                               'name': k, 'visible': True, 'opacity_percent': 100} for k, target in refs]
                document['layer_stack'] = {'schema_version': 1, 'items': items}
            additions = [{'id': 'layer_' + str(uuid4()), 'kind': 'RASTER', 'target_id': s['asset_id'],
                          'pin': {'version': 2, 'sha256': s['png_sha256'], 'review_digest': review_digest},
                          **{k: s[k] for k in ('name', 'visible', 'opacity_percent', 'x', 'y', 'width', 'height')}}
                         for s in row['steps']]
            # Imported raster sits below existing native text/art; no native content is discarded.
            document['layer_stack']['items'] = additions + document['layer_stack']['items']
            document = LayoutIn.model_validate(document).model_dump()
            payload = self.comic._payload(nid, scope, actor, document)
            self.comic._current(nid, scope, actor, payload)
            change_row(page, actor, expected_page_version, lambda current: current.update(payload))
            row['version'] += 1; row['status'] = 'ATTACHED'
            row['attachment'] = {'page_id': page_id, 'expected_page_version': expected_page_version,
                'page_version': page['version'], 'document_digest': self._digest(page['document']),
                'layer_ids': [i['id'] for i in additions]}
            self._authority(nid, scope, actor, guard)
            return {'receipt': self._public(row), 'page': self.comic._view(nid, scope, actor, page)}
