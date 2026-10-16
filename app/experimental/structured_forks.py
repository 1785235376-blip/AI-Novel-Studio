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
from ..services.v1_capability_service import CapabilityVersionConflict
from .common import StaleSourceError, check_version, new_row, now
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


# Shared Universe is an immutable sharing extension of these original owners.
# It is not another Canon, project registry, manuscript, permission or task store.
UNIVERSE_KINDS = {'HISTORY': 'timeline', 'CIVILIZATION': 'organization', 'ABILITY': 'rule', 'GEOGRAPHY': 'geography'}


class UniverseSelection(StrictModel):
    key: str = Field(min_length=1, max_length=240)
    source_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class UniverseSnapshotIn(StrictModel):
    universe_key: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
    title: str = Field(min_length=1, max_length=160)
    records: list[UniverseSelection] = Field(min_length=1, max_length=60)
    license: str = Field(min_length=1, max_length=240)
    allow_local_copy: Literal[True]


class UniverseSnapshotConfirm(UniverseSnapshotIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')


class UniversePinIn(StrictModel):
    snapshot_id: str = Field(min_length=1, max_length=160)
    target_project_id: str = Field(min_length=1, max_length=160)
    role: Literal['MAIN_NOVEL', 'SEQUEL', 'PREQUEL', 'SIDE_STORY']
    expected_version: int = Field(ge=0)


class UniversePinConfirm(UniversePinIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirmed: Literal[True]


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

    # These metadata collections live beside the original fork receipts. Only
    # snapshot creation and explicit pin transitions write them.
    UNIVERSE_SNAPSHOTS = 'structured_universe_snapshots_v1'
    UNIVERSE_PINS = 'structured_universe_pins_v1'

    @staticmethod
    def _universe_visibility(row):
        if row is None or row.get('status') == 'ARCHIVED' or row.get('hidden') or row.get('secret') or str(row.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'}:
            raise FileNotFoundError('universe source unavailable')
        return {k: deepcopy(row.get(k)) for k in ('branch_id', 'visibility', 'privacy_level', 'privacy_state', 'privacy_status', 'hidden', 'secret')}

    def _universe_read(self, ctx, key, *, fresh=False, _seen=None):
        from .world import WorldService
        from .planning import require_row
        self._local(ctx); self.novels.get(ctx.novel_id)
        if key.startswith('world:'):
            rid = key[len('world:'):]
            world = WorldService(self.store, self.novels, self.chapters)
            state = self.store.read(ctx.novel_id, ctx.scope)
            row = require_row(state, world.RECORDS, rid)
            if row.get('research_sources') or row.get('kind') not in UNIVERSE_KINDS or row.get('status') != 'APPROVED':
                raise FileNotFoundError('approved original world record unavailable')
            if fresh: world._assert_fresh(ctx.novel_id, ctx.scope, row, state)
            result = {k: deepcopy(v) for k, v in row.items() if k != 'history'}
        else:
            result = self._read(ctx, key)
            if result is None: raise FileNotFoundError('original structured record unavailable')
            supported(split(key)[0], result)
        self._universe_visibility(result)
        if fresh:
            seen = set(_seen or ())
            if key in seen or len(seen) >= 128: raise ValueError('UNIVERSE_SOURCE_REFERENCE_CYCLE_OR_LIMIT')
            seen.add(key)
            for ref in self._universe_refs(key, result): self._universe_read(ctx, ref, fresh=True, _seen=seen)
            for cid in result.get('sources', {}): self._universe_chapter_policy(ctx, cid)
        return result

    def _universe_refs(self, key, row):
        if key.startswith('world:'):
            return sorted(set(row.get('entity_sources', {})) | {'world:' + rid for rid in row.get('semantic_sources', {})})
        return sorted({kind + ':' + rid for _, kind, rid in references(split(key)[0], row)})

    def _universe_chapter_policy(self, ctx, cid):
        from ..source_privacy import source_privacy_status
        chapter = self.chapters.get(cid)
        if chapter.get('novel_id') != ctx.novel_id or chapter.get('branch_id') != ctx.scope.get('branch_id'):
            raise FileNotFoundError('universe source chapter unavailable')
        if cid not in {c['id'] for c in self.chapters.list(ctx.novel_id)}: raise FileNotFoundError('universe source chapter archived')
        visible = self._universe_visibility(chapter)
        policy = source_privacy_status(chapter, ctx.branch, self.store.root)
        return {'visibility': visible, 'privacy_level': policy['privacy_level'],
                'reviewed_by': policy.get('reviewed_by'), 'reviewed_at': policy.get('reviewed_at')}

    def universe_catalog(self, ctx, target_authorize=lambda nid: None):
        from .world import WorldService
        self._local(ctx); catalog = self.catalog(ctx); rows = []
        for item in catalog['records']:
            if not item['supported']: continue
            try: raw = self._universe_read(ctx, item['key'], fresh=True)
            except (ValueError, FileNotFoundError): continue
            rows.append({**item, 'references': self._universe_refs(item['key'], raw)})
        world = WorldService(self.store, self.novels, self.chapters)
        for raw in world.records(ctx.novel_id, ctx.scope):
            if raw.get('kind') not in UNIVERSE_KINDS: continue
            key = 'world:' + raw['id']
            try: record = self._universe_read(ctx, key, fresh=True)
            except (ValueError, FileNotFoundError): continue
            rows.append({'key': key, 'kind': UNIVERSE_KINDS[raw['kind']], 'record_id': raw['id'], 'title': raw['title'],
                         'source_digest': digest(record), 'version': raw['version'], 'references': self._universe_refs(key, record), 'supported': True})
        projects = []
        for project in self.novels.list()[:100]:
            try: target_authorize(project['id']); current = self.novels.get(project['id'])
            except Exception as exc:
                if isinstance(exc, (FileNotFoundError, PermissionError)) or getattr(exc, 'status_code', None) in {403, 404}: continue
                raise
            projects.append({'id': current['id'], 'title': current.get('title', current['id'])})
        return {'records': rows[:1000], 'projects': projects, 'truncated': len(rows) > 1000 or len(self.novels.list()) > 100,
                'storage': 'IMMUTABLE_ORIGINAL_OWNER_SNAPSHOTS', 'automatic_repin': False, 'canon_write': False}

    def _universe_capture(self, ctx, value):
        baseline = {}; policies = {}; chapters = {}
        if value.license.strip().upper() in {'UNKNOWN', 'UNSPECIFIED', 'NONE'}: raise ValueError('UNIVERSE_EXPLICIT_LOCAL_COPY_LICENSE_REQUIRED')
        for selected in value.records:
            if selected.key in baseline: raise ValueError('UNIVERSE_DUPLICATE_SOURCE')
            raw = self._universe_read(ctx, selected.key, fresh=True)
            if digest(raw) != selected.source_digest: raise StaleSourceError('UNIVERSE_SELECTED_SOURCE_CHANGED')
            baseline[selected.key] = raw
            policies[selected.key] = self._universe_visibility(raw)
            for cid in raw.get('sources', {}): chapters[cid] = self._universe_chapter_policy(ctx, cid)
        missing = sorted({ref for key, row in baseline.items() for ref in self._universe_refs(key, row) if ref not in baseline})
        if missing: raise ValueError('UNIVERSE_SELECT_REFERENCED_RECORDS: ' + ', '.join(missing))
        if len(canonical(baseline).encode()) > 2 * 1024 * 1024: raise ValueError('UNIVERSE_SNAPSHOT_SIZE_LIMIT')
        return {'baseline': baseline, 'source_policies': policies, 'chapter_policies': chapters,
                'project_policy': self._universe_visibility(self.novels.get(ctx.novel_id))}

    def universe_preview(self, ctx, body, reauthorize=lambda: None):
        value = UniverseSnapshotIn.model_validate(body); captured = self._universe_capture(ctx, value); reauthorize()
        return {'preview_digest': digest([ctx.novel_id, ctx.scope, ctx.actor, value.model_dump(), captured]),
                'universe_key': value.universe_key, 'title': value.title, 'record_count': len(captured['baseline']),
                'source_records': [{'key': key, 'source_digest': digest(row), 'version': row.get('version')} for key, row in captured['baseline'].items()],
                'writes': 'IMMUTABLE_SNAPSHOT_ONLY', 'automatic_repin': False, 'canon_write': False}

    def create_universe_snapshot(self, ctx, body, reauthorize=lambda: None):
        from .planning import collection
        value = UniverseSnapshotConfirm.model_validate(body); request = UniverseSnapshotIn.model_validate(value.model_dump(exclude={'preview_digest', 'request_id'}))
        self._local(ctx); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            rows = collection(state, self.UNIVERSE_SNAPSHOTS)
            previous = next((r for r in rows.values() if r['created_by'] == ctx.actor and r['request_id'] == value.request_id), None)
            if previous:
                if previous['request_digest'] != digest(value.model_dump()): raise ValueError('UNIVERSE_REQUEST_ID_REUSED')
                result = self._universe_snapshot_view(ctx, previous); reauthorize(); return result
            if len(rows) >= 200: raise ValueError('UNIVERSE_SNAPSHOT_LIMIT')
            captured = self._universe_capture(ctx, request)
            receipt = digest([ctx.novel_id, ctx.scope, ctx.actor, request.model_dump(), captured])
            if receipt != value.preview_digest: raise StaleSourceError('UNIVERSE_SNAPSHOT_PREVIEW_CHANGED')
            revision = max([r['snapshot_revision'] for r in rows.values() if r['created_by'] == ctx.actor and r['universe_key'] == value.universe_key] or [0]) + 1
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'universe_key': value.universe_key, 'title': value.title,
                'snapshot_revision': revision, 'snapshot_digest': digest(captured), 'license': value.license,
                'license_verification': 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', 'request_id': value.request_id,
                'request_digest': digest(value.model_dump()), 'status': 'IMMUTABLE', **captured})
            if self._universe_capture(ctx, request) != captured: raise StaleSourceError('UNIVERSE_SOURCE_CHANGED_DURING_SNAPSHOT')
            reauthorize(); rows[row['id']] = row
            result = self._universe_snapshot_view(ctx, row)
            if result['content_withheld']: raise FileNotFoundError('universe snapshot source authority changed')
            reauthorize(); return result

    def _universe_snapshot_view(self, ctx, row):
        safe = {k: deepcopy(row[k]) for k in ('id', 'version', 'status', 'snapshot_revision', 'snapshot_digest', 'created_at')}
        try:
            if digest({k: row[k] for k in ('baseline', 'source_policies', 'chapter_policies', 'project_policy')}) != row['snapshot_digest']:
                raise ValueError('UNIVERSE_SNAPSHOT_DIGEST_MISMATCH')
            if self._universe_visibility(self.novels.get(ctx.novel_id)) != row.get('project_policy', {}):
                raise FileNotFoundError('universe source project privacy changed')
            current = {}
            for key, before in row['source_policies'].items():
                raw = self._universe_read(ctx, key)
                if self._universe_visibility(raw) != before: raise FileNotFoundError('universe source privacy changed')
                current[key] = raw
            for cid, before in row['chapter_policies'].items():
                if self._universe_chapter_policy(ctx, cid) != before: raise FileNotFoundError('universe source chapter privacy changed')
        except (ValueError, FileNotFoundError):
            return {**safe, 'content_withheld': True, 'source_changes': [], 'recovery': 'RESTORE_CURRENT_SOURCE_AUTHORITY_OR_CREATE_NEW_SNAPSHOT'}
        return {**safe, 'universe_key': row['universe_key'], 'title': row['title'], 'license': row['license'],
            'content_withheld': False, 'records': deepcopy(row['baseline']),
            'source_changes': [key for key in row['baseline'] if digest(current[key]) != digest(row['baseline'][key])],
            'automatic_repin': False, 'canon_write': False}

    def universe_snapshots(self, ctx, reauthorize=lambda: None):
        self._local(ctx); rows = [self._universe_snapshot_view(ctx, r) for r in self.list(ctx.novel_id, ctx.scope, self.UNIVERSE_SNAPSHOTS) if r['created_by'] == ctx.actor]
        reauthorize(); return {'items': rows}

    def _universe_pin(self, ctx, key, target, state=None):
        rows = (state or self.store.read(ctx.novel_id, ctx.scope))['collections'].get(self.UNIVERSE_PINS, {}).values()
        return next((r for r in rows if r['created_by'] == ctx.actor and r['universe_key'] == key and r['target_project_id'] == target), None)

    def _universe_pin_preview(self, ctx, value, target_authorize, state=None):
        snapshot = self._owned(ctx, self.UNIVERSE_SNAPSHOTS, value.snapshot_id)
        view = self._universe_snapshot_view(ctx, snapshot)
        if view['content_withheld']: raise FileNotFoundError('universe snapshot authority unavailable')
        target_authorize(value.target_project_id); project = self.novels.get(value.target_project_id)
        self._universe_visibility(project)
        existing = self._universe_pin(ctx, snapshot['universe_key'], value.target_project_id, state)
        version = existing['version'] if existing else 0
        if version != value.expected_version: raise CapabilityVersionConflict({'id': existing['id'] if existing else None, 'version': version})
        target_receipt = digest(project)
        return {'preview_digest': digest([ctx.novel_id, ctx.scope, ctx.actor, value.model_dump(), snapshot['snapshot_digest'], target_receipt, existing]),
            'snapshot_id': snapshot['id'], 'snapshot_revision': snapshot['snapshot_revision'], 'snapshot_digest': snapshot['snapshot_digest'],
            'universe_key': snapshot['universe_key'], 'target_project_id': project['id'], 'target_title': project.get('title', project['id']),
            'target_digest': target_receipt, 'role': value.role, 'expected_version': version, 'previous_snapshot_id': existing['snapshot_id'] if existing else None,
            'source_changes': view['source_changes'], 'will_modify_target_content': False, 'automatic_repin': False}

    def universe_pin_preview(self, ctx, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        value = UniversePinIn.model_validate(body); result = self._universe_pin_preview(ctx, value, target_authorize); reauthorize(); return result

    def pin_universe(self, ctx, body, reauthorize=lambda: None, target_authorize=lambda nid: None):
        from .common import change_row
        from .planning import collection
        value = UniversePinConfirm.model_validate(body); request = UniversePinIn.model_validate(value.model_dump(exclude={'preview_digest', 'confirmed'})); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            preview = self._universe_pin_preview(ctx, request, target_authorize, state)
            if value.preview_digest != preview['preview_digest']: raise StaleSourceError('UNIVERSE_PIN_PREVIEW_CHANGED')
            row = self._universe_pin(ctx, preview['universe_key'], value.target_project_id, state)
            payload = {'universe_key': preview['universe_key'], 'snapshot_id': value.snapshot_id, 'snapshot_digest': preview['snapshot_digest'],
                'snapshot_revision': preview['snapshot_revision'], 'target_project_id': value.target_project_id, 'role': value.role,
                'status': 'PINNED', 'approved_by': ctx.actor, 'approved_at': now()}
            if row: change_row(row, ctx.actor, value.expected_version, lambda r: r.update(payload))
            else:
                if len(collection(state, self.UNIVERSE_PINS)) >= 500: raise ValueError('UNIVERSE_PIN_LIMIT')
                row = new_row(ctx.novel_id, ctx.scope, ctx.actor, payload); collection(state, self.UNIVERSE_PINS)[row['id']] = row
            if self._universe_snapshot_view(ctx, self._owned(ctx, self.UNIVERSE_SNAPSHOTS, value.snapshot_id))['content_withheld']:
                raise FileNotFoundError('universe snapshot authority changed')
            target_authorize(value.target_project_id); reauthorize()
            if digest(self.novels.get(value.target_project_id)) != preview['target_digest']: raise StaleSourceError('UNIVERSE_TARGET_CHANGED')
            result = self._universe_pin_view(ctx, row, target_authorize)
            if result['content_withheld']: raise FileNotFoundError('universe pin authority changed')
            reauthorize(); return result

    def _universe_pin_view(self, ctx, row, target_authorize):
        safe = {k: deepcopy(row[k]) for k in ('id', 'version', 'status', 'created_at')}
        try:
            target_authorize(row['target_project_id']); project = self.novels.get(row['target_project_id']); self._universe_visibility(project)
            snap = self._owned(ctx, self.UNIVERSE_SNAPSHOTS, row['snapshot_id']); view = self._universe_snapshot_view(ctx, snap)
            if view['content_withheld']: raise FileNotFoundError('universe snapshot unavailable')
        except Exception as exc:
            if not isinstance(exc, (ValueError, FileNotFoundError, PermissionError)) and getattr(exc, 'status_code', None) not in {403, 404}: raise
            return {**safe, 'content_withheld': True}
        return {**{k: deepcopy(v) for k, v in row.items() if k != 'history'}, 'target_title': project.get('title', project['id']),
                'content_withheld': False, 'history_versions': [h['version'] for h in row.get('history', [])], 'source_changes': view['source_changes'], 'automatic_repin': False}

    def universe_pins(self, ctx, reauthorize=lambda: None, target_authorize=lambda nid: None):
        self._local(ctx); result = [self._universe_pin_view(ctx, row, target_authorize) for row in self.list(ctx.novel_id, ctx.scope, self.UNIVERSE_PINS) if row['created_by'] == ctx.actor]
        reauthorize(); return {'items': result}

    def release_universe_pin(self, ctx, rid, body, reauthorize=lambda: None):
        from .common import change_row
        from .planning import require_row
        value = VersionIn.model_validate(body); self._local(ctx); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = require_row(state, self.UNIVERSE_PINS, rid)
            if row['created_by'] != ctx.actor: raise FileNotFoundError(rid)
            if row['version'] != value.expected_version: raise CapabilityVersionConflict({'id': rid, 'version': row['version']})
            if row['status'] != 'PINNED': raise ValueError('UNIVERSE_PIN_ALREADY_RELEASED')
            change_row(row, ctx.actor, value.expected_version, lambda r: r.update(status='RELEASED'))
            reauthorize(); return {k: deepcopy(row[k]) for k in ('id', 'version', 'status')}

    def universe_pin_history(self, ctx, rid, reauthorize=lambda: None, target_authorize=lambda nid: None):
        row = self._owned(ctx, self.UNIVERSE_PINS, rid)
        items = [self._universe_pin_view(ctx, old, target_authorize) for old in row.get('history', [])]
        reauthorize(); return {'items': items, 'restore': 'EXPLICIT_SNAPSHOT_REPIN_ONLY'}

    def _universe_source_ctx(self, ctx, source_project_id, authorize_project):
        from dataclasses import replace
        self._local(ctx); authorize_project(source_project_id)
        self.novels.get(ctx.novel_id); self.novels.get(source_project_id)
        return replace(ctx, novel_id=source_project_id, scope={'mode': 'local', 'novel_id': source_project_id})

    def universe_incoming(self, ctx, reauthorize=lambda: None, authorize_project=lambda nid: None):
        """Bounded authorized pointer scan, not a second project/universe index."""
        self._local(ctx); projects = self.novels.list(); items = []; truncated = len(projects) > 100
        for project in projects[:100]:
            try:
                source_ctx = self._universe_source_ctx(ctx, project['id'], authorize_project)
                for row in self.list(project['id'], source_ctx.scope, self.UNIVERSE_PINS):
                    if row['created_by'] != ctx.actor or row['target_project_id'] != ctx.novel_id or row['status'] != 'PINNED': continue
                    view = self._universe_pin_view(source_ctx, row, authorize_project)
                    if view['content_withheld']: continue
                    if len(items) >= 30: truncated = True; break
                    items.append({'source_project_id': project['id'], 'source_project_title': project.get('title', project['id']),
                        'pin_id': row['id'], 'pin_version': row['version'], 'universe_key': view['universe_key'],
                        'snapshot_id': row['snapshot_id'], 'snapshot_revision': row['snapshot_revision'],
                        'snapshot_digest': row['snapshot_digest'], 'role': row['role'], 'source_changes': view['source_changes']})
            except Exception as exc:
                if not isinstance(exc, (FileNotFoundError, PermissionError)) and getattr(exc, 'status_code', None) not in {403, 404}: raise
        # A source revoked during the scan is removed rather than leaking its title.
        safe = []
        for item in items:
            try:
                source_ctx = self._universe_source_ctx(ctx, item['source_project_id'], authorize_project)
                current = self._owned(source_ctx, self.UNIVERSE_PINS, item['pin_id'])
                if current['version'] != item['pin_version'] or current['status'] != 'PINNED': continue
                if self._universe_pin_view(source_ctx, current, authorize_project)['content_withheld']: continue
            except Exception as exc:
                if isinstance(exc, (FileNotFoundError, PermissionError)) or getattr(exc, 'status_code', None) in {403, 404}: continue
                raise
            safe.append(item)
        reauthorize(); return {'items': safe, 'truncated': truncated, 'project_scan_limit': 100,
                              'mode': 'READ_ONLY_ORIGINAL_OWNER_REFERENCES', 'automatic_context_injection': False}

    def read_universe_incoming(self, ctx, source_project_id, pin_id, reauthorize=lambda: None, authorize_project=lambda nid: None):
        source_ctx = self._universe_source_ctx(ctx, source_project_id, authorize_project)
        pin = self._owned(source_ctx, self.UNIVERSE_PINS, pin_id)
        if pin['target_project_id'] != ctx.novel_id or pin['status'] != 'PINNED': raise FileNotFoundError('universe pin unavailable')
        row = self._owned(source_ctx, self.UNIVERSE_SNAPSHOTS, pin['snapshot_id'])
        view = self._universe_snapshot_view(source_ctx, row)
        if view['content_withheld']: raise FileNotFoundError('universe snapshot unavailable')
        authorize_project(source_project_id); authorize_project(ctx.novel_id); reauthorize()
        current = self._owned(source_ctx, self.UNIVERSE_PINS, pin_id)
        if current['version'] != pin['version']: raise StaleSourceError('UNIVERSE_PIN_CHANGED_DURING_READ')
        view = self._universe_snapshot_view(source_ctx, row)
        if view['content_withheld']: raise FileNotFoundError('universe snapshot authority changed')
        authorize_project(source_project_id); reauthorize()
        return {'source_project_id': source_project_id, 'pin_id': pin_id, 'pin_version': pin['version'],
                'snapshot': view, 'mode': 'READ_ONLY', 'canon_write': False, 'automatic_context_injection': False}
