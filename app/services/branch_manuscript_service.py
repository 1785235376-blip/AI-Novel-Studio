"""Branch writing, explicit fork and human merge on the existing authorities."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

from ..collaboration import CollaborationScope
from ..document import markdown_to_document
from ..experimental.common import StaleSourceError, new_row, now
from ..experimental.project_forks import block_merge
from ..repositories.branch_manuscript import BranchManuscriptRepository, branch_scope, document_digest, validated_document
from ..repositories.chapter_repository import VersionConflict
from .chapter_service import ChapterService

FEATURE = 'branch_manuscript_v1'
FORKS = 'branch_manuscript_forks'
MERGES = 'branch_manuscript_merges'
SNAPSHOTS = 'branch_manuscript_context_snapshots'
MAX_REVIEW_BYTES = 64 * 1024 * 1024
MAX_REVIEW_RECORDS = {FORKS: 200, MERGES: 500, SNAPSHOTS: 1000}
MAX_CONTEXT_SNAPSHOT_BYTES = 1_000_000


def check_version(row, expected):
    if row['version'] != expected:
        from .v1_capability_service import CapabilityVersionConflict
        # Review receipts may hold counterpart snapshots. A stale token must
        # never disclose that content through generic inbox conflict handling.
        raise CapabilityVersionConflict({key: deepcopy(row[key]) for key in ('id', 'version', 'status', 'scope', 'novel_id') if key in row})


def experimental_scope(scope):
    if isinstance(scope, dict):
        if scope.get('mode'): return deepcopy(scope)
        return {'mode': 'collaboration', 'novel_id': scope['project_id'],
                **{k: scope[k] for k in ('workspace_id', 'storyline_id', 'branch_id')}}
    return {'mode': 'collaboration', 'novel_id': scope.project_id,
            **{k: getattr(scope, k) for k in ('workspace_id', 'storyline_id', 'branch_id')}}


def reference(row):
    return {'id': row['id'], 'version': row['version'], 'document_digest': document_digest(row['document']),
            'is_archived': bool(row.get('is_archived')), 'branch_id': row.get('branch_id')}


class BranchReader:
    mainline_passthrough = True
    def __init__(self, service, source_service=None):
        self.service, self.source_service = service, source_service
    def _owner(self):
        if self.source_service is None: return self.service
        source = self.source_service
        return BranchManuscriptService(source.store, source.novels, source.chapters)
    def __call__(self, ctx):
        if ctx.scope.get('mode') == 'local': return self._owner().mainline.list(ctx.novel_id)
        if not self.available(ctx): return []
        return self._owner().for_scope(ctx.scope).list(ctx.novel_id)
    def available(self, ctx):
        if ctx.scope.get('mode') == 'local': return True
        from ..experimental.flags import enabled_flags
        if FEATURE not in enabled_flags(): return False
        return self._owner().repository(ctx.scope).manifest()['initialized']


class BranchManuscriptService:
    """Manuscript authority; other modules consume views and never copy content."""
    def __init__(self, store, novels, mainline, scopes=None):
        self.store, self.novels, self.mainline, self.scopes = store, novels, mainline, scopes
        self.reader = BranchReader(self)
        self.chapter_reader = self.reader

    def bind_reader(self, source_service): return BranchReader(self, source_service)

    def is_initialized(self, scope):
        return BranchManuscriptRepository(self.store, experimental_scope(scope)).manifest()['initialized']

    def repository(self, scope):
        scope = branch_scope(experimental_scope(scope))
        self.novels.get(scope['novel_id'])
        if self.scopes is not None:
            self.scopes.validate_scope(CollaborationScope(scope['workspace_id'], scope['novel_id'], scope['storyline_id'], scope['branch_id']))
        return BranchManuscriptRepository(self.store, scope)

    def for_scope(self, scope):
        scope = experimental_scope(scope)
        if scope.get('mode') == 'local':
            if set(scope) != {'mode', 'novel_id'}: raise ValueError('MAINLINE_SCOPE_INVALID')
            return self.mainline
        return ChapterService(self.repository(scope))

    def manifest(self, ctx): return self.repository(ctx.scope).manifest()
    def chapters(self, ctx): return self.for_scope(ctx.scope).list(ctx.novel_id)
    def read(self, ctx, cid): return self.for_scope(ctx.scope).get(cid)

    def create(self, ctx, payload, check=lambda: None):
        return self.repository(ctx.scope).create(ctx.novel_id, payload, ctx.actor, check=check)

    def commit(self, ctx, chapter_id, expected_version, document, operation_id, check=lambda: None, state=None, source='MANUAL_SAVE'):
        return self.repository(ctx.scope).save(chapter_id, document, expected_version, source, ctx.actor,
                                               operation_id=operation_id, check=check, state=state)

    def save(self, ctx, cid, document, version, check=lambda: None, source='MANUAL_SAVE'):
        return self.repository(ctx.scope).save(cid, document, version, source, ctx.actor, check=check)

    def restore(self, ctx, cid, version, expected_version, check=lambda: None):
        return self.repository(ctx.scope).restore(cid, version, expected_version, ctx.actor, check=check)

    def archive(self, ctx, cid, archived, version, check=lambda: None):
        return self.repository(ctx.scope).set_archived(cid, archived, version, ctx.actor, check=check)

    def delete(self, ctx, cid, version, check=lambda: None):
        return self.repository(ctx.scope).delete(cid, version, ctx.actor, check=check)

    def _row(self, ctx, collection, rid, state=None):
        self.repository(ctx.scope)
        doc = state if state is not None else self.store.read(ctx.novel_id, ctx.scope)
        row = doc['collections'].get(collection, {}).get(rid)
        if row is None or row.get('scope') != ctx.scope or row.get('novel_id') != ctx.novel_id:
            raise FileNotFoundError(rid)
        return row

    @staticmethod
    def _check_capacity(state, *, finalize=False):
        from ..experimental.store import canonical
        owned = {key: state['collections'].get(key, {}) for key in MAX_REVIEW_RECORDS}
        if any(len(owned[key]) > limit for key, limit in MAX_REVIEW_RECORDS.items()) or len(canonical(owned).encode()) > MAX_REVIEW_BYTES - (0 if finalize else 4 * 1024 * 1024):
            raise ValueError('BRANCH_CAPACITY_REVIEW_JOURNAL_REQUIRED')

    def records(self, ctx):
        self.repository(ctx.scope)
        state = self.store.read(ctx.novel_id, ctx.scope)
        return {key: [self._summary(row) for row in state['collections'].get(collection, {}).values()]
                for key, collection in (('forks', FORKS), ('merges', MERGES))}

    @staticmethod
    def _summary(row):
        return deepcopy({k: v for k, v in row.items() if k not in {'snapshots', 'desired_document', 'checkpoint', 'history', 'segments', 'conflicts'}})

    def _source(self, nid, scope, cid):
        if scope.get('novel_id') != nid: raise ValueError('BRANCH_CROSS_PROJECT_SOURCE_DENIED')
        chapter = self.for_scope(scope).get(cid)
        if (chapter.get('novel_id') != nid or chapter.get('is_archived')
                or chapter.get('branch_id') != scope.get('branch_id')):
            raise FileNotFoundError(cid)
        validated_document(chapter['document'])
        return chapter

    def preview_fork(self, ctx, source_scope, chapter_ids, check=lambda: None):
        self.repository(ctx.scope); check()
        if source_scope == ctx.scope: raise ValueError('BRANCH_SELF_FORK_DENIED')
        if not 1 <= len(chapter_ids) <= 40 or len(set(chapter_ids)) != len(chapter_ids):
            raise ValueError('BRANCH_FORK_SELECTION_LIMIT')
        snapshots = {cid: self._source(ctx.novel_id, source_scope, cid) for cid in chapter_ids}
        from ..experimental.store import canonical
        if len(canonical(snapshots).encode()) > 8_000_000: raise ValueError('BRANCH_FORK_SNAPSHOT_LIMIT')
        payload = {'status': 'REVIEW', 'source_scope': deepcopy(source_scope),
                   'sources': {cid: reference(row) for cid, row in snapshots.items()},
                   'snapshots': snapshots, 'target_revision': self.manifest(ctx)['revision']}
        payload['preview_digest'] = document_digest(payload)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            check(); row = new_row(ctx.novel_id, ctx.scope, ctx.actor, payload)
            state['collections'].setdefault(FORKS, {})[row['id']] = row
            self._check_capacity(state)
            check(); return self._summary(row)

    def apply_fork(self, ctx, rid, expected_version, preview_digest, confirmed, check=lambda: None):
        if confirmed is not True: raise ValueError('BRANCH_HUMAN_CONFIRMATION_REQUIRED')
        reviewed = deepcopy(self._row(ctx, FORKS, rid)); check()
        check_version(reviewed, expected_version)
        for cid, expected in reviewed['sources'].items():
            if reference(self._source(ctx.novel_id, reviewed['source_scope'], cid)) != expected:
                raise StaleSourceError('BRANCH_FORK_SOURCE_CHANGED')
        # The reviewed source snapshot is immutable. Never acquire another
        # branch lock while holding this target scope transaction.
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            check(); row = self._row(ctx, FORKS, rid, state)
            check_version(row, expected_version)
            if row['status'] != 'REVIEW': raise ValueError('BRANCH_FORK_NOT_REVIEWABLE')
            if row['preview_digest'] != preview_digest: raise StaleSourceError('BRANCH_FORK_REVIEW_CHANGED')
            repository = self.repository(ctx.scope)
            if repository.manifest()['revision'] != row['target_revision']:
                raise StaleSourceError('BRANCH_FORK_TARGET_CHANGED')
            if row['sources'] != reviewed['sources'] or row['source_scope'] != reviewed['source_scope']:
                raise StaleSourceError('BRANCH_FORK_REVIEW_CHANGED')
            mapping = {}
            for cid, source in row['snapshots'].items():
                check()
                origin = {'scope': row['source_scope'], 'chapter_id': cid, 'version': source['version'],
                          'document_digest': document_digest(source['document']), 'document': source['document']}
                created = repository.create(ctx.novel_id, {'title': source['title'], 'document': source['document']},
                                            ctx.actor, check=check, state=state, origin=origin)
                mapping[cid] = created['id']
            row.update(status='APPLIED', version=row['version'] + 1, updated_at=now(), updated_by=ctx.actor, id_map=mapping)
            self._check_capacity(state, finalize=True)
            check(); return self._summary(row)

    def cancel(self, ctx, kind, rid, expected_version, check=lambda: None):
        collection = {'fork': FORKS, 'merge': MERGES}.get(kind)
        if collection is None: raise ValueError('BRANCH_REVIEW_KIND_INVALID')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            check(); row = self._row(ctx, collection, rid, state); check_version(row, expected_version)
            if row['status'] != 'REVIEW': raise ValueError('BRANCH_REVIEW_TERMINAL_OR_EXECUTING')
            row.update(status='CANCELLED', version=row['version'] + 1, updated_at=now(), updated_by=ctx.actor)
            self._check_capacity(state, finalize=True)
            check(); return self._summary(row)

    def compare(self, ctx, cid, target_scope, target_cid, choices=None, check=lambda: None):
        """Rich block diff3. Only explicit choices resolve competing changes."""
        check(); source = self._source(ctx.novel_id, ctx.scope, cid)
        target = self._source(ctx.novel_id, target_scope, target_cid)
        lineage = self.repository(ctx.scope).lineage(cid)
        origin = lineage['origin']
        if not origin or origin['scope'] != target_scope or origin['chapter_id'] != target_cid:
            raise ValueError('BRANCH_MERGE_ORIGIN_MISMATCH')
        base, original, fork = lineage['base_document'], target['document'], source['document']
        choices = choices or {}; used = set(); merged = []; conflicts = []
        root = [{k: v for k, v in doc.items() if k != 'content'} for doc in (base, original, fork)]
        segments = block_merge(base.get('content', []), original.get('content', []), fork.get('content', []))
        for index, segment in enumerate(segments):
            key = str(index)
            if segment['kind'] == 'CONFLICT':
                choice = choices.get(key)
                if choice not in {'ORIGINAL', 'FORK'}: conflicts.append({'id': key, **segment})
                else: used.add(key); merged.extend(deepcopy(segment[choice]))
            elif segment['kind'] == 'UNCHANGED': merged.extend(segment['nodes'])
            elif segment['kind'] == 'ORIGINAL_ONLY': merged.extend(segment['ORIGINAL'])
            else: merged.extend(segment['FORK'])
        if len({document_digest(item) for item in root}) > 1:
            # Unknown root attributes are never guessed or silently discarded.
            choice = choices.get('root')
            if choice not in {'ORIGINAL', 'FORK'}: conflicts.append({'id': 'root', 'kind': 'CONFLICT', 'reason': 'DOCUMENT_ATTRIBUTES_CHANGED'})
            else: used.add('root')
            selected_root = root[1 if choice == 'ORIGINAL' else 2]
        else: selected_root = root[0]
        if set(choices) != used: raise ValueError('BRANCH_MERGE_UNKNOWN_CHOICE')
        desired = validated_document({**selected_root, 'content': merged}) if not conflicts else None
        if desired:
            from ..revision_constraints import assert_ai_locks
            assert_ai_locks(target['document'], desired)
        result = {'chapter_id': cid, 'target_chapter_id': target_cid, 'target_scope': deepcopy(target_scope),
                  'source': reference(source), 'target': reference(target), 'choices': deepcopy(choices),
                  'conflicts': conflicts, 'segments': segments, 'can_apply': not conflicts,
                  'desired_document': desired, 'checkpoint': deepcopy(target['document'])}
        result['preview_digest'] = document_digest(result)
        check(); return result

    def propose_merge(self, ctx, cid, target_scope, target_cid, choices=None, check=lambda: None, *, expected_digest=None):
        comparison = self.compare(ctx, cid, target_scope, target_cid, choices, check)
        if expected_digest is not None and comparison['preview_digest'] != expected_digest:
            raise StaleSourceError('BRANCH_MERGE_REVIEW_CHANGED')
        if not comparison['can_apply']: return comparison
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            check(); row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'status': 'REVIEW', **comparison})
            state['collections'].setdefault(MERGES, {})[row['id']] = row
            self._check_capacity(state)
            check(); return self._summary(row)

    def _change_merge(self, ctx, rid, callback, check):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            check(); row = self._row(ctx, MERGES, rid, state); callback(row)
            row.update(version=row['version'] + 1, updated_at=now(), updated_by=ctx.actor)
            self._check_capacity(state, finalize=True)
            check(); return deepcopy(row)

    def apply_merge(self, ctx, rid, expected_version, preview_digest, confirmed, check=lambda: None, *, mainline_writer=None):
        if confirmed is not True: raise ValueError('BRANCH_HUMAN_CONFIRMATION_REQUIRED')
        reviewed = deepcopy(self._row(ctx, MERGES, rid)); check_version(reviewed, expected_version)
        current = self.compare(ctx, reviewed['chapter_id'], reviewed['target_scope'], reviewed['target_chapter_id'], reviewed['choices'], check)
        def claim(row):
            check_version(row, expected_version)
            if row['status'] != 'REVIEW': raise ValueError('BRANCH_MERGE_NOT_REVIEWABLE')
            if (current['preview_digest'] != row['preview_digest'] or preview_digest != row['preview_digest']
                    or reference(self._source(ctx.novel_id, ctx.scope, row['chapter_id'])) != row['source']):
                raise StaleSourceError('BRANCH_MERGE_REVIEW_CHANGED')
            if row['target_scope']['mode'] == 'local' and mainline_writer is None:
                raise ValueError('BRANCH_MAINLINE_WRITER_REQUIRED')
            row['status'] = 'APPLYING'; row['operation_id'] = 'branch-merge:' + row['id']
        row = self._change_merge(ctx, rid, claim, check)
        try:
            check()
            if row['target_scope']['mode'] == 'local':
                saved = mainline_writer(row['target_chapter_id'], deepcopy(row['desired_document']), row['target']['version'], 'BRANCH_HUMAN_MERGE')
                receipt = {'chapter_id': saved['id'], 'after_version': saved['version'], 'document_digest': document_digest(saved['document'])}
            else:
                target = replace(ctx, scope=row['target_scope'], branch=row['target_scope']['branch_id'])
                receipt = self.commit(target, row['target_chapter_id'], row['target']['version'], row['desired_document'], row['operation_id'], check, source='BRANCH_HUMAN_MERGE')
            check()
            def complete(current):
                if current['status'] != 'APPLYING': raise ValueError('BRANCH_MERGE_CLAIM_CHANGED')
                current.update(status='APPLIED', receipt={k: deepcopy(v) for k, v in receipt.items() if k != 'chapter'})
            return self._summary(self._change_merge(ctx, rid, complete, check))
        except Exception:
            # Never replay an unknown external write. The durable APPLYING claim
            # is sufficient after revoke/OFF/restart when finalization is denied.
            try: self._change_merge(ctx, rid, lambda current: current.update(status='RECOVERY_REQUIRED'), check)
            except Exception: pass
            raise

    def recover_merge(self, ctx, rid, expected_version, check=lambda: None):
        row = self._row(ctx, MERGES, rid); check_version(row, expected_version); check()
        if row['status'] not in {'APPLYING', 'RECOVERY_REQUIRED'}: raise ValueError('BRANCH_RECOVERY_NOT_REQUIRED')
        current = self._source(ctx.novel_id, row['target_scope'], row['target_chapter_id'])
        proven = False
        if row['target_scope']['mode'] == 'collaboration':
            try:
                receipt = self.repository(row['target_scope']).receipt(row['operation_id'])
                proven = receipt['document_digest'] == document_digest(row['desired_document'])
            except FileNotFoundError: pass
        # Mainline has no cross-store operation receipt. Matching content is
        # evidence for the author, never proof that this attempt performed it.
        evidence = {'current': reference(current), 'matches_desired': document_digest(current['document']) == document_digest(row['desired_document']),
                    'matches_checkpoint': reference(current) == row['target'], 'automatic_replay': False,
                    'operation_receipt_verified': proven}
        def record(current_row):
            check_version(current_row, expected_version)
            current_row.update(status='APPLIED' if proven else 'RECOVERY_REQUIRED', recovery=evidence)
        return self._summary(self._change_merge(ctx, rid, record, check))

    def review_items(self, ctx):
        from urllib.parse import quote
        rows = self.records(ctx)
        base = '/novels/' + quote(ctx.novel_id, safe='') + '/experimental/branch-manuscript'
        return [{**row, 'preview': 'Branch fork' if kind == 'forks' else 'Branch human merge',
                 'allowed_actions': [], 'review_mode': 'ORIGINAL_DOMAIN_REQUIRED',
                 'target': {'module': 'collaboration', 'surface': 'branch-manuscript', 'feature': FEATURE,
                            'panel': 'BranchManuscriptPanel', 'kind': kind, 'id': row['id'], 'version': row['version'],
                            'novel_id': ctx.novel_id, 'scope': deepcopy(ctx.scope), 'branch_id': ctx.branch,
                            'api': {'mounts': ['/api', '/api/v1'], 'records': base + '/records',
                                    'review': base + '/merges/' + quote(row['id'], safe='') + '/review' if kind == 'merges' else None,
                                    'cancel': base + '/' + ('fork' if kind == 'forks' else 'merge') + '/' + quote(row['id'], safe='') + '/cancel',
                                    'cancel_method': 'POST', 'cancel_body': {'expected_version': row['version']},
                                    'cancel_permissions': ['domain.read', 'domain.review'],
                                    'scope_headers': {'X-Branch-Id': ctx.branch}, 'session_required': True}}}
                for kind, items in rows.items() for row in items]

    def snapshot(self, scope, cid, chapter_version, context, prompt_version, model, **metadata):
        scope = experimental_scope(scope); chapter = self._source(scope['novel_id'], scope, cid)
        if chapter['version'] != chapter_version: raise StaleSourceError('BRANCH_CONTEXT_SOURCE_CHANGED')
        row = {'id': str(uuid4()), 'chapter_version_id': f'{cid}:v{chapter_version}', 'chapter_id': cid,
               'chapter_version': chapter_version, 'novel_id': scope['novel_id'], 'scope': scope,
               'context': deepcopy(context), 'context_pack_hash': document_digest(context), 'prompt_version': prompt_version,
               'model': model, 'created_at': now(), **metadata}
        from ..experimental.store import canonical
        if len(canonical(row).encode()) > MAX_CONTEXT_SNAPSHOT_BYTES: raise ValueError('BRANCH_CONTEXT_SNAPSHOT_LIMIT')
        with self.store.transaction(scope['novel_id'], scope) as state:
            state['collections'].setdefault(SNAPSHOTS, {})[row['id']] = row
            self._check_capacity(state)
        return deepcopy(row)

    def snapshots(self, scope, cid):
        scope = experimental_scope(scope); self.for_scope(scope).get(cid)
        return [deepcopy(row) for row in self.store.read(scope['novel_id'], scope)['collections'].get(SNAPSHOTS, {}).values() if row['chapter_id'] == cid]
