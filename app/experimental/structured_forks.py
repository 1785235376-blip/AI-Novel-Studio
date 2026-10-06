"""B09 selected original knowledge records, with mapping and recoverable CAS journals.

Snapshots are immutable review/checkpoint evidence. All editable records stay in
NovelService's original characters/locations/relationships authorities. Local
project copies are neither collaboration branches nor story-route/Git IDs.
"""
from __future__ import annotations
from copy import deepcopy
from collections import Counter
import re
from typing import Literal
from uuid import uuid4

from pydantic import Field
from ..privacy import merge_privacy
from .common import StaleSourceError, check_version, new_row
from .planning import StrictModel, digest
from .project_forks import ProjectForksService, VersionIn, ConfirmIn, CompareIn, ApplyIn, advance
from .store import canonical

KINDS = ('locations', 'characters', 'relationships')
FIELDS = {
    'characters': {'id', 'name', 'age', 'role', 'personality', 'goal', 'current_location', 'status', 'privacy_level', 'privacy_status'},
    'locations': {'id', 'name', 'location_type', 'description', 'rules', 'atmosphere', 'status', 'privacy_level', 'privacy_status'},
    'relationships': {'id', 'source_character_id', 'target_character_id', 'relationship_type', 'description', 'status', 'valid_from_event_id', 'valid_to_event_id', 'certainty', 'privacy_level', 'privacy_status'},
}
METADATA = {'id', 'privacy_level', 'privacy_status'}
LIMITS = ['ORIGINAL_LOCAL_KNOWLEDGE_AUTHORITIES', 'SELECTED_CHARACTERS_LOCATIONS_RELATIONSHIPS',
          'NO_COLLABORATION_BRANCH_OR_STORY_ROUTE_ID_REUSE', 'EXPLICIT_COMPLETE_REFERENCE_MAPPING',
          'NO_CANON_EVENTS_WORKFLOWS_OR_UNKNOWN_EMBEDDED_FIELDS', 'NO_PERMISSION_OR_CLOUD_GRANT_COPY',
          'AUTHOR_LICENSE_DECLARATION_NOT_LEGAL_VERIFICATION', 'RECOVERABLE_ARCHIVE_NOT_PHYSICAL_DELETE',
          'CROSS_STORE_JOURNAL_NOT_GLOBAL_ATOMICITY']


class Selection(StrictModel):
    kind: Literal['characters', 'locations', 'relationships']
    record_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$')
    source_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    license: str = Field(min_length=1, max_length=240)
    allow_local_copy: Literal[True]


class ManuscriptForkLink(StrictModel):
    fork_id: str = Field(min_length=1, max_length=120)
    expected_version: int = Field(ge=1)


class StructuredForkIn(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    records: list[Selection] = Field(min_length=1, max_length=60)
    manuscript_fork: ManuscriptForkLink | None = None


def split(key):
    kind, rid = key.split(':', 1)
    if kind not in KINDS or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}', rid):
        raise ValueError('FORK_RECORD_ID_INVALID')
    return kind, rid


def supported(kind, row):
    if not isinstance(row, dict) or set(row) - FIELDS[kind]:
        raise ValueError('FORK_UNSUPPORTED_STRUCTURED_FIELDS')
    required = ('name',) if kind in {'characters', 'locations'} else ('source_character_id', 'target_character_id', 'relationship_type')
    if any(not isinstance(row.get(k), str) or not row[k].strip() for k in required):
        raise ValueError('FORK_STRUCTURED_REQUIRED_FIELD_INVALID')
    if len(canonical(row).encode()) > 64 * 1024:
        raise ValueError('FORK_STRUCTURED_RECORD_SIZE_LIMIT')
    if kind == 'relationships' and (row.get('valid_from_event_id') or row.get('valid_to_event_id')):
        raise ValueError('FORK_EVENT_REFERENCE_REQUIRES_EVENT_OWNER')
    if any(isinstance(v, (dict, list)) for v in row.values()):
        raise ValueError('FORK_UNSUPPORTED_EMBEDDED_STRUCTURE')
    return deepcopy(row)


def references(kind, row):
    if not row: return []
    if kind == 'characters':
        return [('current_location', 'locations', row['current_location'])] if row.get('current_location') else []
    if kind == 'relationships':
        return [(f, 'characters', row.get(f)) for f in ('source_character_id', 'target_character_id')]
    return []


def mapped(kind, row, mapping):
    if row is None: return None
    result = supported(kind, row)
    for field, target_kind, rid in references(kind, row):
        key = f'{target_kind}:{rid}'
        if key not in mapping: raise ValueError('FORK_REFERENCE_NOT_SELECTED_OR_UNMAPPED')
        result[field] = split(mapping[key])[1]
    return result


def content(row):
    return {k: deepcopy(v) for k, v in row.items() if k not in METADATA} if row else None


def live(row): return row is not None and row.get('status') != 'ARCHIVED'


class StructuredForksService(ProjectForksService):
    FORKS = 'project_structured_forks_v1'
    MERGES = 'project_structured_merges_v1'

    def _read(self, ctx, key):
        self._local(ctx); kind, rid = split(key)
        rows = [r for r in self.novels.data_set(ctx.novel_id, kind) if str(r.get('id')) == rid]
        if len(rows) > 1: raise ValueError('FORK_DUPLICATE_ORIGINAL_RECORD_ID')
        if not rows: return None
        row = rows[0]
        if row.get('branch_id') or row.get('hidden') or row.get('secret') or str(row.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'}:
            raise FileNotFoundError('structured record unavailable')
        return deepcopy(row)

    @staticmethod
    def _summary(row):
        keys = ('id', 'version', 'status', 'title', 'target_id', 'preview_digest', 'id_map', 'error_code', 'active_merge', 'created_at', 'fork_id', 'kind', 'checkpoint_id', 'journal', 'restored_by', 'provenance', 'manuscript_fork')
        return {**{k: deepcopy(row[k]) for k in keys if k in row}, 'record_count': len(row.get('baseline', row.get('checkpoint', {}))), 'limitations': LIMITS}

    def catalog(self, ctx):
        if ctx.scope.get('mode') != 'local': return {'records': [], 'available': False, 'limitations': LIMITS}
        self._local(ctx); self.novels.get(ctx.novel_id); result = []; truncated = False
        for kind in KINDS:
            rows = self.novels.data_set(ctx.novel_id, kind); counts = Counter(str(r.get('id')) for r in rows); truncated = truncated or len(rows) > 1000
            for row in rows[:1000]:
                key = f"{kind}:{row.get('id', '')}"
                try:
                    split(key); raw = deepcopy(row)
                    if counts[str(raw.get('id'))] != 1 or not live(raw): continue
                    if raw.get('branch_id') or raw.get('hidden') or raw.get('secret') or str(raw.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'}: continue
                except (ValueError, FileNotFoundError): continue
                reason = None
                try: supported(kind, raw)
                except ValueError as exc: reason = str(exc)
                result.append({'key': key, 'kind': kind, 'record_id': raw['id'], 'title': raw.get('name', raw.get('relationship_type', raw['id'])),
                    'source_digest': digest(raw), 'references': [{'field': f, 'key': f'{k}:{rid}'} for f, k, rid in references(kind, raw)],
                    'supported': reason is None, 'reason': reason})
        return {'records': result, 'available': True, 'truncated': truncated, 'limitations': LIMITS}

    def records(self, ctx, target_authorize=lambda nid: None):
        self._local(ctx); result = []
        for row in self.list(ctx.novel_id, ctx.scope, self.FORKS):
            if row['created_by'] != ctx.actor: continue
            try:
                for key in row['baseline']: self._read(ctx, key)
            except FileNotFoundError: continue
            item = self._summary(row)
            # Target manuscript stays behind its current authorization check.
            item['target_available'] = True
            if row['status'] != 'PREFLIGHT':
                try: target_authorize(row['target_id']); self.novels.get(row['target_id'])
                except (FileNotFoundError, PermissionError): item['target_available'] = False
                except Exception as exc:
                    if getattr(exc, 'status_code', None) not in {403, 404}: raise
                    item['target_available'] = False
            result.append(item)
        ids = {r['id'] for r in result}
        return {'items': result[-100:], 'merges': [self._summary(r) for r in self.list(ctx.novel_id, ctx.scope, self.MERGES) if r['created_by'] == ctx.actor and r['fork_id'] in ids][-100:]}

    def preflight(self, ctx, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        self._local(ctx); value = StructuredForkIn.model_validate(body); baseline = {}; provenance = {}; mapping = {}
        for item in value.records:
            key = f'{item.kind}:{item.record_id}'
            if key in baseline: raise ValueError('FORK_DUPLICATE_STRUCTURED_SELECTION')
            current = self._read(ctx, key)
            if not live(current): raise FileNotFoundError('selected structured record unavailable')
            supported(item.kind, current)
            if digest(current) != item.source_digest: raise StaleSourceError('FORK_STRUCTURED_SOURCE_CHANGED')
            if item.license.strip().upper() in {'UNKNOWN', 'UNSPECIFIED', 'NONE'}: raise ValueError('FORK_EXPLICIT_RECORD_LICENSE_REQUIRED')
            baseline[key] = current; mapping[key] = item.kind + ':fork-' + uuid4().hex
            provenance[key] = {'source_project_id': ctx.novel_id, 'source_record_id': item.record_id, 'source_kind': item.kind,
                'source_digest': item.source_digest, 'license': item.license, 'license_verification': 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION'}
        for key, current in baseline.items(): mapped(split(key)[0], current, mapping)
        if len(canonical(baseline).encode()) > 2 * 1024 * 1024: raise ValueError('FORK_STRUCTURED_SNAPSHOT_LIMIT')
        link = self._capture_manuscript_fork(ctx, value.manuscript_fork, target_authorize) if value.manuscript_fork else None
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'status': 'PREFLIGHT', 'title': value.title, 'target_id': link['target_id'] if link else 'fork-' + uuid4().hex, 'manuscript_fork': link,
            'baseline': baseline, 'provenance': provenance, 'id_map': mapping, 'journal': []})
        row['preview_digest'] = digest([row['target_id'], baseline, provenance, mapping, value.title, link]); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            if len(state['collections'].get(self.FORKS, {})) >= 100: raise ValueError('FORK_RECORD_LIMIT')
            self._assert_baseline(ctx, row); self._verify_manuscript_fork(ctx, row, target_authorize, exact=True); reauthorize(); state['collections'].setdefault(self.FORKS, {})[row['id']] = row
        return self._summary(row)

    def _capture_manuscript_fork(self, ctx, selection, target_authorize):
        manuscript = self._owned(ctx, ProjectForksService.FORKS, selection.fork_id)
        check_version(manuscript, selection.expected_version)
        if manuscript['status'] != 'FORKED': raise ValueError('FORK_MANUSCRIPT_TARGET_NOT_READY')
        if manuscript.get('active_merge'):
            merge = self._owned(ctx, ProjectForksService.MERGES, manuscript['active_merge'])
            if merge['status'] not in {'COMPLETED', 'RESTORED'}: raise ValueError('FORK_MANUSCRIPT_TARGET_RECOVERY_REQUIRED')
        original, fork = ProjectForksService._current(self, ctx, manuscript, target_authorize)
        return {'fork_id': manuscript['id'], 'expected_version': manuscript['version'], 'target_id': manuscript['target_id'],
                'manuscript_source_digest': digest([original, fork, manuscript['id_map']]), 'mode': 'ATTACH_SELECTED_STRUCTURES'}

    def _verify_manuscript_fork(self, ctx, row, target_authorize, *, exact=False):
        link = row.get('manuscript_fork')
        if not link: return
        manuscript = self._owned(ctx, ProjectForksService.FORKS, link['fork_id'])
        if manuscript['target_id'] != row['target_id'] or manuscript['target_id'] != link['target_id'] or manuscript['status'] != 'FORKED':
            raise StaleSourceError('FORK_MANUSCRIPT_TARGET_IDENTITY_CHANGED')
        target_authorize(row['target_id'])
        if exact:
            current = self._capture_manuscript_fork(ctx, ManuscriptForkLink(fork_id=link['fork_id'], expected_version=link['expected_version']), target_authorize)
            if current != link: raise StaleSourceError('FORK_MANUSCRIPT_BINDING_CHANGED')

    def _assert_baseline(self, ctx, row):
        if any(self._read(ctx, key) != before for key, before in row['baseline'].items()):
            raise StaleSourceError('FORK_STRUCTURED_SOURCE_CHANGED')

    def _write(self, ctx, key, desired, expected):
        kind, rid = split(key)
        if desired is None: raise ValueError('FORK_STRUCTURED_PHYSICAL_DELETE_UNSUPPORTED')
        payload = supported(kind, desired); payload.pop('id', None); payload.pop('privacy_status', None)
        return self.novels.compare_and_swap_record(ctx.novel_id, kind, rid, payload, digest(expected) if expected is not None else None)

    def create_fork(self, ctx, rid, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = ConfirmIn.model_validate(body); row = self._owned(ctx, self.FORKS, rid); check_version(row, value.expected_version)
        if row['status'] != 'PREFLIGHT' or row['preview_digest'] != value.preview_digest: raise ValueError('FORK_CONFIRMATION_CHANGED')
        self._assert_baseline(ctx, row); self._verify_manuscript_fork(ctx, row, target_authorize, exact=True); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.FORKS][rid]
            advance(current, ctx.actor, value.expected_version, lambda r: r.update(status='CLAIMED'))
        expected_target = {}
        def guard():
            reauthorize(); self._assert_baseline(ctx, row); self._verify_manuscript_fork(ctx, row, target_authorize, exact=True)
            if expected_target:
                target_authorize(row['target_id']); target_ctx = self._target_ctx(ctx, row)
                if any(self._read(target_ctx, key) != value for key, value in expected_target.items()):
                    raise StaleSourceError('FORK_TARGET_RECORD_CHANGED_DURING_COPY')
        try:
            if row.get('manuscript_fork'):
                self._step(ctx, self.FORKS, rid, 'VERIFY_OWNED_MANUSCRIPT_FORK', row['target_id'], lambda: self.novels.get(row['target_id']), guard)
            else:
                self._step(ctx, self.FORKS, rid, 'CREATE_PROJECT', row['target_id'], lambda: self.novels.create({'id': row['target_id'], 'title': row['title'], 'genre': 'Reviewed structured project fork'}), guard)
            target_ctx = self._target_ctx(ctx, row)
            for key in sorted(row['baseline'], key=lambda k: (KINDS.index(split(k)[0]), k)):
                desired = mapped(split(key)[0], row['baseline'][key], row['id_map']); target_key = row['id_map'][key]
                desired.update(id=split(target_key)[1], privacy_level='LOCAL_ONLY'); desired.pop('privacy_status', None)
                self._step(ctx, self.FORKS, rid, 'COPY_ORIGINAL_RECORD', target_key,
                    lambda: self._write(target_ctx, target_key, desired, None), lambda: (guard(), target_authorize(row['target_id'])))
                actual = self._read(target_ctx, target_key)
                if content(actual) != content(desired) or actual.get('privacy_level') != 'LOCAL_ONLY':
                    raise StaleSourceError('FORK_RECORD_COPY_RECEIPT_UNCERTAIN')
                expected_target[target_key] = actual
            guard(); target_authorize(row['target_id'])
            self._change(ctx, self.FORKS, rid, lambda r: r.update(status='FORKED'))
            return self._summary(self._owned(ctx, self.FORKS, rid))
        except Exception:
            self._change(ctx, self.FORKS, rid, lambda r: r.update(status='RECOVERY_REQUIRED', error_code='FORK_PARTIAL_NEW_PROJECT_NO_AUTOMATIC_RETRY'))
            raise

    def _current(self, ctx, row, target_authorize):
        self._verify_manuscript_fork(ctx, row, target_authorize)
        target_authorize(row['target_id']); target_ctx = self._target_ctx(ctx, row); self.novels.get(row['target_id'])
        original = {k: self._read(ctx, k) for k in row['baseline']}
        fork = {k: self._read(target_ctx, mapped_key) for k, mapped_key in row['id_map'].items()}
        reverse = {v: k for k, v in row['id_map'].items()}
        for key, item in fork.items():
            if item:
                item = mapped(split(key)[0], item, reverse); item['id'] = split(key)[1]; fork[key] = item
        for key, item in original.items():
            if item: supported(split(key)[0], item)
        return original, fork

    def _dependencies(self, ctx, selected):
        result = {}
        for kind in KINDS:
            for row in self.novels.data_set(ctx.novel_id, kind):
                key = f"{kind}:{row.get('id', '')}"
                if key in selected or not live(row): continue
                if any(f'{k}:{rid}' in selected for _, k, rid in references(kind, row)):
                    result[key] = self._read(ctx, key)
        return result

    @staticmethod
    def _dependency_blocks(dependencies, desired):
        blocked = []
        for key, row in dependencies.items():
            for _, kind, rid in references(split(key)[0], row):
                target = f'{kind}:{rid}'
                if target in desired and not live(desired[target]):
                    blocked.append({'key': target, 'code': 'FORK_UNSELECTED_DEPENDENT_REQUIRES_REVIEW'})
        return blocked

    def _comparison(self, row, original, fork, choices):
        used = set(); records = []; desired = {}; conflicts = 0
        for key, base in row['baseline'].items():
            left, right = original[key], fork[key]; changes = []; result = deepcopy(left)
            if not live(left) or not live(right):
                cid = digest([key, 'ARCHIVE_DELETE', base, left, right]); choice = choices.get(cid); used.add(cid)
                changes.append({'id': cid, 'field': 'record', 'kind': 'CONFLICT', 'reason': 'DELETE_OR_ARCHIVE_MODIFY', 'base': content(base), 'ORIGINAL': content(left), 'FORK': content(right), 'choice': choice})
                if not choice: conflicts += 1
                if choice == 'FORK':
                    if left is None: raise ValueError('FORK_MISSING_ORIGINAL_REQUIRES_OWNER_RESTORE')
                    result = {**deepcopy(left), **(content(right) or {}), 'status': right.get('status', 'ACTIVE') if live(right) else 'ARCHIVED'}
            else:
                for field in sorted(set(content(base)) | set(content(left)) | set(content(right))):
                    b, l, r = base.get(field), left.get(field), right.get(field)
                    if l == r == b: continue
                    kind = 'BOTH_SAME' if l == r else 'FORK_ONLY' if l == b else 'ORIGINAL_ONLY' if r == b else 'CONFLICT'
                    cid = digest([key, field, b, l, r]); choice = choices.get(cid) if kind == 'CONFLICT' else None
                    if kind == 'CONFLICT':
                        used.add(cid)
                        if not choice: conflicts += 1
                    chosen = r if kind in {'FORK_ONLY', 'BOTH_SAME'} or choice == 'FORK' else l
                    result[field] = deepcopy(chosen)
                    changes.append({'id': cid, 'field': field, 'kind': kind, 'reason': 'RENAME' if field == 'name' else 'FIELD_EDIT', 'base': b, 'ORIGINAL': l, 'FORK': r, 'choice': choice})
            if result is not None and content(result) != content(left):
                result['privacy_level'] = merge_privacy((left or {}).get('privacy_level'), (right or {}).get('privacy_level'), base.get('privacy_level'))
                result.pop('privacy_status', None)
            desired[key] = result
            records.append({'key': key, 'kind': split(key)[0], 'title': (left or base).get('name', (left or base).get('relationship_type', key)),
                'original_digest': digest(left), 'fork_digest': digest(right), 'changes': changes})
        if set(choices) - used: raise ValueError('FORK_UNKNOWN_OR_STALE_CONFLICT_CHOICE')
        blocked = []
        for key, result in desired.items():
            if not live(result): continue
            for field, kind, rid in references(split(key)[0], result):
                target = f'{kind}:{rid}'
                if target not in desired or not live(desired[target]):
                    blocked.append({'key': key, 'field': field, 'code': 'FORK_CROSS_REFERENCE_MISSING_OR_ARCHIVED'})
        return records, desired, conflicts, blocked

    def compare(self, ctx, rid, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = CompareIn.model_validate(body); row = self._owned(ctx, self.FORKS, rid); check_version(row, value.expected_version)
        if row['status'] != 'FORKED': raise ValueError('FORK_NOT_READY_OR_RECOVERY_REQUIRED')
        if row.get('active_merge') and self._owned(ctx, self.MERGES, row['active_merge'])['status'] not in {'COMPLETED', 'RESTORED'}:
            raise ValueError('FORK_MERGE_RECOVERY_REQUIRED')
        original, fork = self._current(ctx, row, target_authorize)
        records, desired, conflicts, blocked = self._comparison(row, original, fork, value.choices)
        dependencies = self._dependencies(ctx, desired); blocked.extend(self._dependency_blocks(dependencies, desired))
        reauthorize(); target_authorize(row['target_id'])
        return {'fork_id': rid, 'expected_version': row['version'], 'preview_digest': digest([rid, row['version'], original, fork, value.choices, desired, dependencies]),
            'records': records, 'unresolved': conflicts, 'blocked': blocked, 'can_apply': not conflicts and not blocked,
            'write_count': sum(v != original[k] for k, v in desired.items()), 'limitations': LIMITS}

    def _execute_records(self, ctx, row, plan, reauthorize, target_authorize):
        pid = plan['id']
        def guard():
            reauthorize(); current = self._owned(ctx, self.MERGES, pid)
            if self._owned(ctx, self.FORKS, row['id']).get('active_merge') != pid or current['status'] not in {'CLAIMED', 'APPLYING'}:
                raise ValueError('FORK_WRITER_SUPERSEDED_BY_RECOVERY')
            if any(self._read(ctx, k) != v for k, v in current['expected'].items()): raise StaleSourceError('FORK_ORIGINAL_RECORD_CHANGED_DURING_APPLY')
            if plan['kind'] == 'MERGE':
                _, source = self._current(ctx, row, target_authorize)
                if source != plan['fork_snapshot']: raise StaleSourceError('FORK_SOURCE_RECORD_CHANGED_DURING_APPLY')
                if self._dependencies(ctx, plan['desired']) != plan.get('dependencies', {}): raise StaleSourceError('FORK_DEPENDENT_RECORD_CHANGED_DURING_APPLY')
        try:
            for key, desired in plan['desired'].items():
                before = self._owned(ctx, self.MERGES, pid)['expected'][key]
                if desired == before: continue
                if before is None: raise ValueError('FORK_MISSING_ORIGINAL_REQUIRES_OWNER_RESTORE')
                self._step(ctx, self.MERGES, pid, 'ORIGINAL_RECORD_CAS', key, lambda: self._write(ctx, key, desired, before), guard)
                actual = self._read(ctx, key)
                if content(actual) != content(desired) or actual.get('privacy_level') != desired.get('privacy_level'):
                    raise StaleSourceError('FORK_RECORD_WRITE_RECEIPT_UNCERTAIN')
                self._change(ctx, self.MERGES, pid, lambda r: (r['expected'].update({key: actual}), r['journal'][-1].update(status='DONE', result_digest=digest(actual))))
            guard(); self._change(ctx, self.MERGES, pid, lambda r: r.update(status='COMPLETED' if plan['kind'] == 'MERGE' else 'RESTORED'))
            if plan.get('checkpoint_id'): self._change(ctx, self.MERGES, plan['checkpoint_id'], lambda r: r.update(status='RESTORED', restored_by=pid))
            return self._summary(self._owned(ctx, self.MERGES, pid))
        except Exception:
            if self._owned(ctx, self.MERGES, pid)['status'] in {'CLAIMED', 'APPLYING'}:
                self._change(ctx, self.MERGES, pid, lambda r: r.update(status='RECOVERY_REQUIRED', error_code='FORK_PARTIAL_OR_UNKNOWN_NO_AUTOMATIC_RETRY'))
            raise

    def apply(self, ctx, rid, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = ApplyIn.model_validate(body); review = self.compare(ctx, rid, value.model_dump(include={'expected_version', 'choices'}), reauthorize, target_authorize)
        if review['preview_digest'] != value.preview_digest: raise StaleSourceError('FORK_PREVIEW_CHANGED')
        if not review['can_apply']: raise ValueError('FORK_CONFLICTS_OR_REFERENCES_UNRESOLVED')
        row = self._owned(ctx, self.FORKS, rid); original, fork = self._current(ctx, row, target_authorize)
        _, desired, _, _ = self._comparison(row, original, fork, value.choices)
        dependencies = self._dependencies(ctx, desired)
        if digest([rid, row['version'], original, fork, value.choices, desired, dependencies]) != value.preview_digest: raise StaleSourceError('FORK_PREVIEW_CHANGED')
        plan = self._plan(ctx, row, original, desired, 'MERGE', fork)
        plan['dependencies'] = dependencies
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.FORKS][rid]; check_version(current, value.expected_version); reauthorize(); target_authorize(row['target_id'])
            state['collections'].setdefault(self.MERGES, {})[plan['id']] = plan
            advance(current, ctx.actor, value.expected_version, lambda r: r.update(active_merge=plan['id']))
        return self._execute_records(ctx, row, plan, reauthorize, target_authorize)

    def recovery(self, ctx, mid, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = VersionIn.model_validate(body); plan = self._owned(ctx, self.MERGES, mid); check_version(plan, value.expected_version)
        current = {k: self._read(ctx, k) for k in plan['checkpoint']}; blocked = [k for k, v in current.items() if v is None]
        # Recovering an archived reference graph is reviewed as a complete set.
        for key, row in plan['checkpoint'].items():
            if row: supported(split(key)[0], row)
        reauthorize()
        return {'id': mid, 'expected_version': plan['version'], 'status': plan['status'], 'checkpoint': deepcopy(plan['checkpoint']), 'current': current,
            'journal': deepcopy(plan['journal']), 'preview_digest': digest([mid, plan['version'], current, plan['checkpoint']]),
            'can_restore': not blocked and plan['status'] != 'RESTORED', 'blocked': blocked, 'no_automatic_retry': True}

    def restore_checkpoint(self, ctx, mid, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = ConfirmIn.model_validate(body); review = self.recovery(ctx, mid, {'expected_version': value.expected_version}, reauthorize)
        if value.preview_digest != review['preview_digest']: raise StaleSourceError('FORK_RECOVERY_PREVIEW_CHANGED')
        if not review['can_restore']: raise ValueError('FORK_CHECKPOINT_CANNOT_RESTORE')
        previous = self._owned(ctx, self.MERGES, mid); row = self._owned(ctx, self.FORKS, previous['fork_id'])
        desired = deepcopy(previous['checkpoint'])
        for key, before in desired.items():
            before['privacy_level'] = merge_privacy(before.get('privacy_level'), review['current'][key].get('privacy_level')); before.pop('privacy_status', None)
        plan = self._plan(ctx, row, review['current'], desired, 'CHECKPOINT_RESTORE', checkpoint_id=mid)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.FORKS][row['id']]; check_version(state['collections'][self.MERGES][mid], value.expected_version)
            if current.get('active_merge') != mid: raise ValueError('FORK_CHECKPOINT_SUPERSEDED')
            reauthorize(); state['collections'][self.MERGES][plan['id']] = plan
            advance(current, ctx.actor, current['version'], lambda r: r.update(active_merge=plan['id']))
        return self._execute_records(ctx, row, plan, reauthorize, target_authorize)
