"""Bounded, restart-safe review jobs inside their existing domain's scope store.

Adapters are trusted host dependencies. This helper grants no network, plugin,
Canon or manuscript authority. Source readers and dispatch guards stay with the
owning Research or Embedding service.
"""
from __future__ import annotations

import copy
from uuid import uuid4

from .common import new_row, change_row, check_version, StaleSourceError
from .planning import collection, digest


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

    def _source(self, nid, scope, actor, row):
        source, inputs = self.source_reader(nid, scope, actor, row['request'])
        if source != row['source_snapshot']:
            raise StaleSourceError('ADAPTER_SOURCE_CHANGED')
        return inputs

    def public(self, row):
        value = copy.deepcopy({key: item for key, item in row.items() if key not in {'history', 'execution_token'}})
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
            rows[row['id']] = row
            guard()
            return self.public(row)

    def action(self, nid, scope, actor, rid, action, version, guard):
        if action == 'run': return self.run(nid, scope, actor, rid, version, guard)
        if action not in {'cancel', 'recover', 'review', 'invalidate'}: raise ValueError('ADAPTER_ACTION_INVALID')
        with self.service.store.transaction(nid, scope) as state:
            guard(); row = self._row(nid, scope, actor, rid, state); check_version(row, version)
            if len(row.get('history', [])) >= 100: raise ValueError('ADAPTER_REVISION_LIMIT')
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
            change_row(row, actor, version, lambda target: target.update(values))
            guard(); return self.public(row)

    def run(self, nid, scope, actor, rid, version, guard):
        guard(); original = self._row(nid, scope, actor, rid); check_version(original, version)
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
            guard(); row = self._row(nid, scope, actor, rid, state); check_version(row, version)
            if row['status'] not in {'DRAFT', 'NOT_CONFIGURED', 'FAILED'}: raise ValueError('ADAPTER_RECOVER_OR_REVIEW_REQUIRED')
            if len(row.get('history', [])) >= 100: raise ValueError('ADAPTER_REVISION_LIMIT')
            self._source(nid, scope, actor, row)
            change_row(row, actor, version, lambda target: target.update(status='RUNNING', execution_token=token, error_code=None, result=None))
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
                    return self.public(row)
                self._source(nid, scope, actor, claimed)
                if self.provider_reader() is not provider or provider.capability.model_dump() != capability:
                    raise StaleSourceError('ADAPTER_PROVIDER_CHANGED')
                # Prevent adapter-controlled unbounded storage or non-JSON values.
                from .store import canonical
                if len(canonical(result).encode()) > 512 * 1024: raise ValueError('ADAPTER_RESULT_LIMIT')
                change_row(row, actor, row['version'], lambda target: target.update(
                    status='REVIEW_REQUIRED', result=result, model=capability, execution_token=None,
                    result_digest=digest(result)))
                guard(); return self.public(row)
        except Exception:
            # Persist a sanitized failure, but never override cancel/replacement.
            with self.service.store.transaction(nid, scope) as state:
                row = self._row(nid, scope, actor, rid, state)
                if row.get('execution_token') == token:
                    change_row(row, actor, row['version'], lambda target: target.update(
                        status='FAILED', execution_token=None, result=None, error_code='ADAPTER_EXECUTION_FAILED'))
            raise
