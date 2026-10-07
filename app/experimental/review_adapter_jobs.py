"""Bounded, restart-safe review jobs inside their existing domain's scope store.

Adapters are trusted host dependencies. This helper grants no network, plugin,
Canon or manuscript authority. Source readers and dispatch guards stay with the
owning Research or Embedding service.
"""
from __future__ import annotations

import copy
from uuid import uuid4

from .common import new_row, change_row, check_version, snapshot, StaleSourceError
from .store import canonical
from .planning import collection, digest
from ..services.v1_capability_service import CapabilityVersionConflict


MAX_HISTORY = 100
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 768 * 1024
MAX_RESULT_BYTES = 512 * 1024
# Claim -> terminal -> review -> cancel -> recover -> source invalidation.
# These are reserved slots, not extra history or permission to evict old rows.
HEADROOM = {'RUNNING': 5, 'REVIEW_REQUIRED': 4, 'REVIEWED': 3,
            'FAILED': 3, 'CANCELLED': 2, 'DRAFT': 1, 'NOT_CONFIGURED': 1,
            'INVALIDATED': 0}


def preflight(row, reserve=0):
    if len(row.get('history', [])) + reserve > MAX_HISTORY:
        raise ValueError('ADAPTER_REVISION_LIMIT')
    if len(canonical(snapshot(row)).encode()) > MAX_SNAPSHOT_BYTES:
        raise ValueError('ADAPTER_SNAPSHOT_LIMIT')
    # Worst-case snapshots and growth of the current result are reserved before
    # dispatch. A late oversized/non-JSON result is rejected, then safely failed.
    if len(canonical(row).encode()) + (reserve + bool(reserve)) * MAX_SNAPSHOT_BYTES > MAX_RECEIPT_BYTES:
        raise ValueError('ADAPTER_RECEIPT_BYTE_LIMIT')


def bounded_change(row, actor, version, values, *, reserve=None):
    check_version(row, version)
    candidate = copy.deepcopy(row)
    change_row(candidate, actor, version, lambda target: target.update(values))
    preflight(candidate, HEADROOM.get(candidate['status'], 0) if reserve is None else reserve)
    row.clear(); row.update(candidate)
    return row


def invalidate_receipt(row):
    if row['status'] == 'INVALIDATED' and row.get('execution_token') is None and row.get('result') is None:
        return row
    return bounded_change(row, 'research-source-invalidation', row['version'], {
        'status': 'INVALIDATED', 'execution_token': None, 'result': None,
        'error_code': 'RESEARCH_SOURCE_CHANGED'}, reserve=0)


class ReviewAdapterJobs:
    def __init__(self, service, name, source_reader, provider_reader, execute):
        self.service, self.name = service, name
        self.source_reader, self.provider_reader, self.execute = source_reader, provider_reader, execute

    def _row(self, nid, scope, actor, rid, state=None):
        row = (collection(state, self.name).get(rid) if state is not None
               else self.service.get(nid, scope, self.name, rid))
        if not row or row.get('novel_id') != nid or row.get('scope') != scope or row.get('created_by') != actor:
            raise FileNotFoundError(rid)
        return row

    @staticmethod
    def _version(row, expected):
        if row['version'] != expected:
            # Conflict receipts must not redisclose a revoked source either.
            raise CapabilityVersionConflict({key: row[key] for key in ('id', 'version', 'status')})

    def _source(self, nid, scope, actor, row):
        source, inputs = self.source_reader(nid, scope, actor, row['request'])
        if source != row['source_snapshot']:
            raise StaleSourceError('ADAPTER_SOURCE_CHANGED')
        return inputs

    def public(self, row, *, minimal=False):
        hidden = {'history', 'execution_token'}
        # Reserved cancellation does not redisclose a revoked source.
        # Keep the recovery receipt useful, but never return old lineage/results.
        if minimal or row['status'] in {'CANCELLED', 'INVALIDATED', 'STALE'}:
            hidden |= {'request', 'source_snapshot', 'model', 'result_digest'}
        value = copy.deepcopy({key: item for key, item in row.items() if key not in hidden})
        if minimal:
            value['result'] = None
        cancel_available = row['status'] not in {'CANCELLED', 'INVALIDATED'}
        if cancel_available:
            try:
                candidate = dict(row)
                change_row(candidate, row['updated_by'], row['version'], lambda target: target.update(
                    status='CANCELLED', execution_token=None, result=None))
                preflight(candidate, HEADROOM['CANCELLED'])
            except ValueError:
                cancel_available = False
        value['capacity'] = {'cancel_available': cancel_available, 'history_limit': MAX_HISTORY, 'history_used': len(row.get('history', [])),
            'remaining_revisions': max(0, MAX_HISTORY - len(row.get('history', []))),
            'receipt_byte_limit': MAX_RECEIPT_BYTES, 'result_byte_limit': MAX_RESULT_BYTES,
            'run_requires_free_revisions': 1 + HEADROOM['RUNNING'],
            'exhaustion_recovery': 'CREATE_NEW_RECEIPT_NO_AUTOMATIC_REPLAY'}
        value.update(recovery_required=row['status'] == 'RUNNING', automatic_resume=False,
                     automatic_canon=False, model_quality='NOT_RUN',
                     executor='SYNTHETIC_IN_PROCESS', durable_worker=False, runtime_admission='NOT_CONFIGURED')
        return value

    def get(self, nid, scope, actor, rid):
        row = self._row(nid, scope, actor, rid)
        try:
            self._source(nid, scope, actor, row)
        except StaleSourceError:
            row = {**row, 'status': 'STALE', 'result': None}
        return self.public(row)

    def list(self, nid, scope, actor):
        rows = []
        for row in self.service.list(nid, scope, self.name):
            if row.get('created_by') != actor: continue
            try: rows.append(self.get(nid, scope, actor, row['id']))
            except FileNotFoundError: continue
        return {'items': rows, 'total': len(rows), 'automatic_resume': False}

    def create(self, nid, scope, actor, request, guard):
        guard()
        source, _ = self.source_reader(nid, scope, actor, request)
        provider = self.provider_reader()
        configured = provider is not None and provider.capability.verification == 'MOCK_ONLY' and provider.capability.local
        with self.service.store.transaction(nid, scope) as state:
            guard()
            current, _ = self.source_reader(nid, scope, actor, request)
            if current != source: raise StaleSourceError('ADAPTER_SOURCE_CHANGED')
            rows = collection(state, self.name)
            if len(rows) >= 200: raise ValueError('ADAPTER_JOB_LIMIT')
            row = new_row(nid, scope, actor, {'request': request, 'source_snapshot': source,
                'status': 'DRAFT' if configured else 'NOT_CONFIGURED', 'result': None,
                'model': None, 'execution_token': None, 'error_code': None})
            preflight(row, 1 + HEADROOM['RUNNING'])
            rows[row['id']] = row
            guard()
            return self.public(row)

    def action(self, nid, scope, actor, rid, action, version, guard):
        if action == 'run': return self.run(nid, scope, actor, rid, version, guard)
        if action not in {'cancel', 'recover', 'review', 'invalidate'}: raise ValueError('ADAPTER_ACTION_INVALID')
        with self.service.store.transaction(nid, scope) as state:
            guard(); row = self._row(nid, scope, actor, rid, state); self._version(row, version)
            if action in {'cancel', 'invalidate'} and row['status'] == ('CANCELLED' if action == 'cancel' else 'INVALIDATED'):
                guard(); return self.public(row)
            if action == 'review':
                if row['status'] != 'REVIEW_REQUIRED': raise ValueError('ADAPTER_REVIEW_REQUIRED')
                self._source(nid, scope, actor, row)
                values = {'status': 'REVIEWED', 'reviewed_by': actor}
            elif action == 'recover':
                if row['status'] not in {'RUNNING', 'FAILED', 'CANCELLED', 'NOT_CONFIGURED'}:
                    raise ValueError('ADAPTER_RECOVERY_NOT_REQUIRED')
                self._source(nid, scope, actor, row)
                values = {'status': 'DRAFT', 'result': None, 'error_code': None}
            else:
                values = {'status': 'CANCELLED' if action == 'cancel' else 'INVALIDATED', 'result': None}
            values['execution_token'] = None
            bounded_change(row, actor, version, values)
            guard(); return self.public(row)

    def run(self, nid, scope, actor, rid, version, guard):
        guard(); original = self._row(nid, scope, actor, rid); self._version(original, version)
        provider = self.provider_reader()
        if provider is None: raise ValueError('ADAPTER_NOT_CONFIGURED')
        capability = copy.deepcopy(provider.capability.model_dump())
        # No implicit remote egress. A future remote implementation needs a
        # domain-specific authorization adapter, not a client-supplied switch.
        if capability.get('local') is not True: raise ValueError('ADAPTER_LOCAL_PROVIDER_REQUIRED')
        # These receipts exercise synchronous synthetic contracts, not a second
        # model runtime. Real adapters must enter the original JobManager and
        # admission pipeline before a future integration can enable dispatch.
        if capability.get('verification') != 'MOCK_ONLY':
            raise ValueError('ADAPTER_MODEL_ADMISSION_NOT_CONFIGURED')
        token = str(uuid4())
        with self.service.store.transaction(nid, scope) as state:
            guard(); row = self._row(nid, scope, actor, rid, state); self._version(row, version)
            if row['status'] not in {'DRAFT', 'NOT_CONFIGURED', 'FAILED'}: raise ValueError('ADAPTER_RECOVER_OR_REVIEW_REQUIRED')
            self._source(nid, scope, actor, row)
            bounded_change(row, actor, version, dict(status='RUNNING', execution_token=token, error_code=None, result=None))
            claimed = copy.deepcopy(row)
            guard()
        try:
            def dispatch_guard():
                guard()
                current = self._row(nid, scope, actor, rid)
                if current.get('execution_token') != token or current['version'] != claimed['version']:
                    raise StaleSourceError('ADAPTER_EXECUTION_CANCELLED')
                if self.provider_reader() is not provider or provider.capability.model_dump() != capability:
                    raise StaleSourceError('ADAPTER_PROVIDER_CHANGED')
                self._source(nid, scope, actor, claimed)
            dispatch_guard()
            inputs = self._source(nid, scope, actor, claimed)
            result = self.execute(provider, inputs, claimed['request'], dispatch_guard)
            # Provider cancellation may have won while outside the transaction.
            guard()
            with self.service.store.transaction(nid, scope) as state:
                guard(); row = self._row(nid, scope, actor, rid, state)
                if row.get('execution_token') != token or row['version'] != claimed['version']:
                    return self.public(row, minimal=True)
                self._source(nid, scope, actor, claimed)
                if self.provider_reader() is not provider or provider.capability.model_dump() != capability:
                    raise StaleSourceError('ADAPTER_PROVIDER_CHANGED')
                # Prevent adapter-controlled unbounded storage or non-JSON values.
                if len(canonical(result).encode()) > MAX_RESULT_BYTES: raise ValueError('ADAPTER_RESULT_LIMIT')
                bounded_change(row, actor, row['version'], dict(
                    status='REVIEW_REQUIRED', result=result, model=capability, execution_token=None,
                    result_digest=digest(result)))
                guard(); return self.public(row)
        except Exception:
            # Persist a sanitized failure, but never override cancel/replacement.
            with self.service.store.transaction(nid, scope) as state:
                row = self._row(nid, scope, actor, rid, state)
                if row.get('execution_token') == token:
                    bounded_change(row, actor, row['version'], dict(
                        status='FAILED', execution_token=None, result=None, error_code='ADAPTER_EXECUTION_FAILED'))
            raise
