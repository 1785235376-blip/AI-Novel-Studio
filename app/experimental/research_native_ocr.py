"""Explicit Research OCR preview/claim/publication over existing owners.

This coordinator creates no registry, queue or workflow store. Host wiring and
public routes are separate; merely importing it never enables or runs OCR.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4
from typing import Literal
from pydantic import Field, model_validator

from .research_library import StrictInput, ResearchLibraryService
from .research_vision import (PreparedResearchOCRSource, ResearchVisionInput,
    ResearchVisionCapability, research_analysis_jobs, bind_research_analysis_result)
from .review_adapter_jobs import bounded_change, preflight, HEADROOM, MAX_RESULT_BYTES
from .planning import digest
from .store import canonical
from .common import StaleSourceError
from .model_broker import ModelBrokerService
from ..creative.project_store import CreativeProjectStore


class NativeOCRPreviewIn(StrictInput):
    expected_version: int = Field(ge=1, strict=True)
    provider_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    language: str = Field(pattern=r'^[A-Za-z]{2,3}(?:-[A-Za-z]{2,8})?$')


class NativeOCRDispatchIn(StrictInput):
    expected_version: int = Field(ge=1, strict=True)
    reviewed_preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    idempotency_key: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$')


class NativeOCRRecoveryIn(StrictInput):
    expected_version: int = Field(ge=1, strict=True)
    reservation_version: int = Field(ge=1, strict=True)
    original_executor_stopped_confirmed: Literal[True]
    evidence_note: str = Field(min_length=1, max_length=500)

    @model_validator(mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if not isinstance(value, dict) or value.get('original_executor_stopped_confirmed') is not True:
            raise ValueError('RESEARCH_OCR_EXECUTOR_STOP_CONFIRMATION_REQUIRED')
        return value


class NativeResearchOCRCoordinator:
    def __init__(self, research, broker, manager):
        from ..jobs import JobManager
        from ..repositories.generation_repository import GenerationRepository
        from ..repositories.postgres.generation import PostgresGenerationRepository
        if (type(research) is not ResearchLibraryService or type(broker) is not ModelBrokerService
                or type(manager) is not JobManager or research.historical_inspection is not True
                or broker.store is not research.store or broker.novels is not research.novels):
            raise ValueError('RESEARCH_OCR_ORIGINAL_OWNERS_REQUIRED')
        repository = getattr(manager.persistence, 'repository', manager.persistence)
        if research.store.backend == 'file':
            matches = isinstance(repository, GenerationRepository) and repository.root.resolve() == (research.store.root / 'runtime/jobs').resolve()
        else:
            matches = type(repository) is PostgresGenerationRepository and repository._matches_director_store(research.store)
        if not matches: raise ValueError('RESEARCH_OCR_ORIGINAL_JOB_STORE_REQUIRED')
        self.research, self.broker, self.manager = research, broker, manager
        self.rows = research_analysis_jobs(research)
        self.owner = CreativeProjectStore(research.store)
        self.node = broker.runtime.generation_runtime.vision_ocr_node
        if getattr(research, 'native_ocr', None) is not None:
            raise ValueError('RESEARCH_OCR_OWNER_ALREADY_CONFIGURED')
        research.native_ocr = self

    def status(self):
        from .flags import enabled_flags
        from .research_ocr_execution import FLAGS
        ready = set(FLAGS).issubset(enabled_flags())
        routes = self.broker.candidates(local_ocr_only=True) if ready else []
        return {'status': 'CONFIGURED' if routes else 'NOT_CONFIGURED',
            'operations': ['OCR'], 'media_types': ['image/png', 'image/jpeg'],
            'review_required': True, 'automatic_canon': False, 'model_quality': 'NOT_RUN',
            'routes': [{'provider_id': row['provider_id'], 'model_id': row['model_id'],
                'display_name': row['display_name'],
                'languages': row['identity']['native_ocr_binding']['route']['languages']}
                for row in routes]}

    @contextmanager
    def lease(self, nid, identity):
        with self.owner.existing_owner_only(), self.owner.owner_lease(nid) as current:
            if current != identity: raise StaleSourceError('RESEARCH_OCR_OWNER_CHANGED')
            yield current

    def _row(self, nid, scope, actor, rid, state=None):
        self.research._analysis_owner(nid, scope, actor, rid)
        row = self.rows._row(nid, scope, actor, rid, state)
        if row['request']['operation'] != 'OCR': raise ValueError('RESEARCH_OCR_OPERATION_REQUIRED')
        return row

    def _source(self, nid, scope, actor, row, guard):
        self.rows._source(nid, scope, actor, row)
        return PreparedResearchOCRSource(self.research, nid, scope, actor,
            row['request']['source_id'], row['request']['source_version'], guard)

    def preview(self, nid, scope, actor, rid, value, *, guard):
        body = NativeOCRPreviewIn.model_validate(value)
        guard(); row = self._row(nid, scope, actor, rid)
        self.rows._version(row, body.expected_version)
        if row['status'] not in {'DRAFT', 'NOT_CONFIGURED', 'FAILED'}:
            raise ValueError('RESEARCH_OCR_RECOVERY_OR_NEW_RECEIPT_REQUIRED')
        previous = row.get('native_ocr_execution')
        if previous:
            ledger = self.broker.get(nid, scope, self.broker.LEDGER, previous['reservation_id'])
            if ledger['status'] in {'RESERVED', 'DISPATCHED', 'UNKNOWN_UPSTREAM'}:
                raise ValueError('RESEARCH_OCR_RECOVERY_REQUIRED')
        preflight(row, 1 + HEADROOM['RUNNING'])
        def current():
            guard()
            latest = self._row(nid, scope, actor, rid)
            self.rows._version(latest, body.expected_version)
        source = self._source(nid, scope, actor, row, current)
        binding = self.node.binding(body.provider_id, body.model_id)
        if body.language not in binding['route']['languages']:
            raise ValueError('RESEARCH_OCR_LANGUAGE_NOT_ADMITTED')
        route = next((item for item in self.broker.candidates(local_ocr_only=True)
            if item['provider_id'] == body.provider_id and item['model_id'] == body.model_id), None)
        if route is None: raise ValueError('RESEARCH_OCR_ROUTE_NOT_ADMITTED')
        identity = source.binding['project_incarnation']
        lease = lambda: self.lease(nid, identity)
        decision = self.broker.preview(nid, scope, actor, {'capability': 'VISION', 'profile': 'LOCAL_ONLY',
            'policy': 'CUSTOM', 'preferred_route': route['route_id'], 'max_cost_microusd': 0},
            guard=current, route_guard=lambda _: source.validate_current(), local_ocr_only=True, owner_lease=lease)
        if not decision['chosen']: raise ValueError('RESEARCH_OCR_NO_ADMITTED_ROUTE')
        proposal = {'schema': 'research-native-ocr-preview/1', 'analysis_id': rid,
            'receipt_version': body.expected_version + 1, 'source_binding': source.binding,
            'provider_id': body.provider_id, 'model_id': body.model_id, 'language': body.language,
            'route_digest': binding['route_digest'], 'broker_preview_id': decision['id'],
            'broker_preview_version': decision['version'], 'max_output_bytes': 128000,
            'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            'external_provider_fee_microusd': 0, 'host_compute_cost_included': False,
            'automatic_canon': False, 'review_required': True, 'model_quality': 'NOT_RUN'}
        proposal['reviewed_preview_digest'] = digest(proposal)
        with self.broker._owned_transaction(nid, scope, lease) as state:
            current(); row = self._row(nid, scope, actor, rid, state)
            bounded_change(row, actor, body.expected_version, {'native_ocr_preview': proposal,
                'native_ocr_execution': None, 'status': 'DRAFT', 'result': None, 'execution_token': None, 'error_code': None},
                reserve=1 + HEADROOM['RUNNING'])
            guard(); self.rows._source(nid, scope, actor, row)
            return self.rows.public(row)

    def _fail(self, nid, scope, actor, rid, token, lease):
        with self.broker._owned_transaction(nid, scope, lease) as state:
            row = self.rows._row(nid, scope, actor, rid, state)
            if row.get('execution_token') == token:
                bounded_change(row, actor, row['version'], {'status': 'FAILED', 'execution_token': None,
                    'result': None, 'error_code': 'RESEARCH_OCR_EXECUTION_FAILED'})

    def dispatch(self, nid, scope, actor, rid, value, *, guard):
        body = NativeOCRDispatchIn.model_validate(value)
        guard(); original = self._row(nid, scope, actor, rid)
        key = digest([rid, body.idempotency_key])
        previous = original.get('native_ocr_execution')
        if previous and previous.get('idempotency_key') == key:
            if (previous['preview_digest'] != body.reviewed_preview_digest
                    or previous['approved_version'] != body.expected_version):
                raise ValueError('RESEARCH_OCR_IDEMPOTENCY_MISMATCH')
            answer = self.rows.get(nid, scope, actor, rid); guard(); return answer
        self.rows._version(original, body.expected_version)
        proposal = deepcopy(original.get('native_ocr_preview'))
        if (original['status'] != 'DRAFT' or not isinstance(proposal, dict)
                or proposal.get('reviewed_preview_digest') != body.reviewed_preview_digest
                or digest({k: v for k, v in proposal.items() if k != 'reviewed_preview_digest'}) != body.reviewed_preview_digest
                or proposal.get('receipt_version') != body.expected_version
                or datetime.now(timezone.utc) >= datetime.fromisoformat(proposal['expires_at'])):
            raise ValueError('RESEARCH_OCR_REVIEWED_PREVIEW_REQUIRED')
        token = str(uuid4()); holder = {'claimed': False, 'published': None}
        def current():
            guard(); latest = self._row(nid, scope, actor, rid)
            if latest['status'] == 'CANCELLED' and holder.get('job') is not None:
                holder['job'].cancelled.set()
            if (latest['request'] != original['request'] or latest['source_snapshot'] != original['source_snapshot']):
                raise StaleSourceError('RESEARCH_OCR_SOURCE_CHANGED')
            if not holder['claimed']:
                self.rows._version(latest, body.expected_version)
            elif holder['published']:
                if latest['status'] not in {'REVIEW_REQUIRED', 'REVIEWED'} or latest.get('result_digest') != holder['published']:
                    raise StaleSourceError('RESEARCH_OCR_PUBLICATION_CHANGED')
            elif latest.get('execution_token') != token or latest['status'] != 'RUNNING':
                if latest['status'] == 'CANCELLED': holder['job'].cancelled.set()
                raise StaleSourceError('RESEARCH_OCR_CANCELLED_OR_CHANGED')
            self.rows._source(nid, scope, actor, latest)
        source = self._source(nid, scope, actor, original, current)
        if source.binding != proposal['source_binding']: raise StaleSourceError('RESEARCH_OCR_SOURCE_CHANGED')
        identity = source.binding['project_incarnation']; lease = lambda: self.lease(nid, identity)
        binding = {k: v for k, v in source.binding.items() if k not in {'contract', 'access', 'page'}}
        binding.update(contract='RESEARCH_OCR_JOB_V1', source_kind='IMAGE', language=proposal['language'],
            route_digest=proposal['route_digest'], reviewed_preview_digest=body.reviewed_preview_digest)
        def before_dispatch():
            if not holder['claimed']: raise ValueError('RESEARCH_OCR_RECEIPT_NOT_CLAIMED')
            if datetime.now(timezone.utc) >= datetime.fromisoformat(proposal['expires_at']):
                raise ValueError('RESEARCH_OCR_PREVIEW_EXPIRED')
            self.broker.guard_dispatch(nid, scope, actor, holder['reservation']['id'], holder['job'].id,
                guard=current, owner_lease=lease)
        def terminal():
            job = holder['job']
            self.broker.finalize(nid, scope, actor, holder['reservation']['id'], job.id,
                job.execution_outcome or 'UNKNOWN', owner_lease=lease)
            if job.status != 'COMPLETED': self._fail(nid, scope, actor, rid, token, lease)
        def publish(response):
            try:
                current()
                capability = ResearchVisionCapability(provider_id=proposal['provider_id'], model_id=proposal['model_id'],
                    model_revision=proposal['route_digest'], local=True, operations=['OCR'], verification='CONTRACT_VERIFIED')
                source_input = ResearchVisionInput(b'', 'IMAGE', (1,), binding['source_id'], binding['source_version'], binding['source_digest'])
                result = bind_research_analysis_result(source_input, {'blocks': [
                    {'kind': 'TEXT', 'page': 1, 'text': response.text[i:i + 8000]}
                    for i in range(0, len(response.text), 8000)], 'warnings': ['LOCAL_NATIVE_OCR_REVIEW_REQUIRED']}, capability)
                if len(canonical(result).encode()) > MAX_RESULT_BYTES: raise ValueError('RESEARCH_OCR_RESULT_LIMIT')
                with self.broker._owned_transaction(nid, scope, lease) as state:
                    current(); row = self._row(nid, scope, actor, rid, state)
                    execution = deepcopy(row['native_ocr_execution'])
                    execution.update(output_sha256=sha256(response.text.encode()).hexdigest(), runtime_receipt=deepcopy(response.receipt))
                    bounded_change(row, actor, row['version'], {'status': 'REVIEW_REQUIRED', 'result': result,
                        'model': capability.model_dump(), 'execution_token': None, 'result_digest': digest(result),
                        'native_ocr_execution': execution})
                    guard(); self.rows._source(nid, scope, actor, row)
                holder['published'] = digest(result)
            except Exception:
                self._fail(nid, scope, actor, rid, token, lease)
                raise
        job = self.manager._prepare_research_ocr_job(source=source, node=self.node, binding=binding,
            provider_id=proposal['provider_id'], model_id=proposal['model_id'],
            deadline=(datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
            max_output_bytes=proposal['max_output_bytes'], before_dispatch=before_dispatch,
            on_terminal=terminal, on_result=publish)
        holder['job'] = job
        holder['reservation'] = self.broker.reserve(nid, scope, actor, proposal['broker_preview_id'],
            proposal['broker_preview_version'], key, job.id, guard=current,
            authorization_digest=job.expected_request_digest, owner_lease=lease)
        try:
            with self.broker._owned_transaction(nid, scope, lease) as state:
                current(); row = self._row(nid, scope, actor, rid, state)
                bounded_change(row, actor, body.expected_version, {'status': 'RUNNING', 'result': None,
                    'execution_token': token, 'error_code': None, 'native_ocr_execution': {
                        'generation_id': job.id, 'reservation_id': holder['reservation']['id'],
                        'idempotency_key': key, 'preview_digest': body.reviewed_preview_digest,
                        'approved_version': body.expected_version, 'binding': binding,
                        'expected_request_digest': job.expected_request_digest}})
                guard(); self.rows._source(nid, scope, actor, row)
            holder['claimed'] = True
            self.manager._start_research_ocr_job(job)
        except Exception:
            self.broker.finalize(nid, scope, actor, holder['reservation']['id'], job.id, 'FAILED', owner_lease=lease)
            self._fail(nid, scope, actor, rid, token, lease)
            raise
        answer = self.rows.get(nid, scope, actor, rid); guard(); return answer

    def recovery_projection(self, nid, scope, actor, row):
        """Read-only interruption feedback; never releases holds or replays jobs."""
        result = deepcopy(row)
        execution = row.get('native_ocr_execution')
        if row.get('status') != 'RUNNING' or not execution:
            return result
        with self.lease(nid, execution['binding']['project_incarnation']):
            self._row(nid, scope, actor, row['id'])
            self.rows._source(nid, scope, actor, row)
            try:
                current = self.manager.get(execution['generation_id'])
            except KeyError:
                current = None
            authority = getattr(current, 'research_ocr_execution_authority', None)
            if authority is not None and not getattr(authority, 'finished', False):
                return result
            ledger = self.broker.get(nid, scope, self.broker.LEDGER, execution['reservation_id'])
            if (ledger.get('created_by') != actor or ledger.get('job_id') != execution['generation_id']
                    or ledger.get('authorization_digest') != execution['expected_request_digest']
                    or ledger.get('native_ocr_incarnation') != execution['binding']['project_incarnation']):
                raise ValueError('RESEARCH_OCR_RECOVERY_IDENTITY_MISMATCH')
            result.update(status='INTERRUPTED', persisted_status=row['status'],
                recovery={'code': 'RESEARCH_OCR_EXECUTOR_NOT_RESUMABLE', 'automatic_resume': False,
                    'budget_hold_retained': ledger['status'] in {'RESERVED', 'DISPATCHED', 'UNKNOWN_UPSTREAM'},
                    'explicit_host_recovery_required': True, 'reservation_version': ledger['version']})
        return result

    def recover(self, nid, scope, actor, rid, value, *, guard):
        from .research_ocr_binding import ResearchOCRJobBinding
        body = NativeOCRRecoveryIn.model_validate(value)
        if not body.evidence_note.strip(): raise ValueError('RESEARCH_OCR_RECOVERY_EVIDENCE_REQUIRED')
        guard(); original = self.rows._row(nid, scope, actor, rid)
        execution = deepcopy(original.get('native_ocr_execution'))
        if not execution: raise ValueError('RESEARCH_OCR_RECOVERY_NOT_REQUIRED')
        binding = ResearchOCRJobBinding.model_validate(execution['binding'])
        if (binding.project_id != nid or binding.actor_id != actor or binding.scope.model_dump() != scope):
            raise ValueError('RESEARCH_OCR_RECOVERY_IDENTITY_MISMATCH')
        lease = lambda: self.lease(nid, binding.project_incarnation)
        recovery_id = digest(['native-ocr-recovery-v1', rid, actor, binding.project_incarnation, execution['generation_id'], execution['expected_request_digest']])
        def response(row):
            return {'id': row['id'], 'version': row['version'], 'status': row['status'],
                'recovery_recorded': True, 'automatic_resume': False, 'automatic_replay': False}
        def inactive():
            guard()
            try: job = self.manager.get(execution['generation_id'])
            except KeyError: job = None
            if job is None:
                try: self.manager.persistence.get(execution['generation_id'])
                except KeyError:
                    ledger = self.broker.get(nid, scope, self.broker.LEDGER, execution['reservation_id'])
                    if ledger.get('dispatched') or ledger['status'] not in {'RESERVED', 'RELEASED', 'RECONCILED'}:
                        raise ValueError('RESEARCH_OCR_RECOVERY_JOB_RECORD_REQUIRED')
                    return
                raise ValueError('RESEARCH_OCR_RECOVERY_REOPEN_OWNER_REQUIRED')
            from .research_ocr_execution import _ResearchOCRCapability
            authority = getattr(job, 'research_ocr_execution_authority', None)
            if authority is not None and (type(authority) is not _ResearchOCRCapability
                    or authority.manager is not self.manager or authority.job is not job or not authority.finished):
                raise ValueError('RESEARCH_OCR_EXECUTOR_STILL_ACTIVE')
            if authority is None and (callable(job.on_terminal) or callable(job.before_dispatch)):
                raise ValueError('RESEARCH_OCR_RECOVERY_REOPEN_OWNER_REQUIRED')
            if (job.id != execution['generation_id'] or job.actor_id != actor
                    or job.novel_id != nid or job.scope != scope or job.operation != 'research_ocr'
                    or job.experimental_origin != 'research_ocr_model'):
                raise ValueError('RESEARCH_OCR_RECOVERY_JOB_MISMATCH')
            try: persisted = self.manager.persistence.get(job.id)
            except KeyError: raise ValueError('RESEARCH_OCR_RECOVERY_JOB_RECORD_REQUIRED') from None
            if (job.status not in {'COMPLETED', 'FAILED', 'CANCELLED'}
                    or persisted.get('status') != job.status or job.research_ocr_binding != execution['binding']
                    or persisted.get('research_ocr_binding') != execution['binding']
                    or job.expected_request_digest != execution['expected_request_digest']
                    or persisted.get('expected_request_digest') != execution['expected_request_digest']):
                raise ValueError('RESEARCH_OCR_RECOVERY_JOB_MISMATCH')
        with self.broker._owned_transaction(nid, scope, lease) as state:
            if self.rows._row(nid, scope, actor, rid, state) != original:
                raise StaleSourceError('RESEARCH_OCR_RECOVERY_CHANGED')
            inactive()
            if execution.get('recovery_id') == recovery_id:
                ledger = self.broker.get(nid, scope, self.broker.LEDGER, execution['reservation_id'])
                if (ledger.get('native_recovery_id') != recovery_id or ledger.get('created_by') != actor
                        or ledger.get('job_id') != execution['generation_id']
                        or ledger.get('authorization_digest') != execution['expected_request_digest']
                        or ledger.get('native_ocr_incarnation') != binding.project_incarnation):
                    raise ValueError('RESEARCH_OCR_RECOVERY_RECEIPT_MISMATCH')
                return response(original)
        self.rows._version(original, body.expected_version)
        if original['status'] not in {'RUNNING', 'FAILED', 'CANCELLED', 'INVALIDATED'}:
            raise ValueError('RESEARCH_OCR_RECOVERY_NOT_REQUIRED')
        execution['recovery_id'] = recovery_id
        values = {'status': original['status'] if original['status'] in {'CANCELLED', 'INVALIDATED'} else 'FAILED',
            'result': None, 'result_digest': None, 'execution_token': None, 'native_ocr_preview': None,
            'error_code': 'RESEARCH_OCR_RECOVERED_NO_REPLAY', 'native_ocr_execution': execution}
        candidate = deepcopy(original)
        bounded_change(candidate, actor, body.expected_version, values)
        def current():
            inactive()
            latest = self.rows._row(nid, scope, actor, rid)
            self.rows._version(latest, body.expected_version)
            if latest != original: raise StaleSourceError('RESEARCH_OCR_RECOVERY_CHANGED')
        self.broker.reconcile_native_ocr(nid, scope, actor, execution['reservation_id'],
            body.reservation_version, execution['generation_id'], execution['expected_request_digest'],
            recovery_id, body.evidence_note, guard=current, owner_lease=lease)
        with self.broker._owned_transaction(nid, scope, lease) as state:
            current(); row = self.rows._row(nid, scope, actor, rid, state)
            bounded_change(row, actor, body.expected_version, values)
            inactive()
            return response(row)

    def export_reviewed(self, nid, scope, actor, rid, expected_version, result_digest):
        row = self._row(nid, scope, actor, rid)
        self.rows._version(row, expected_version)
        if row['status'] != 'REVIEWED' or row.get('result_digest') != result_digest:
            raise ValueError('RESEARCH_OCR_REVIEWED_EXPORT_REQUIRED')
        self.validate_review(nid, scope, actor, row)
        content = ('\n\n'.join(block['text'] for block in row['result']['blocks']) + '\n').encode('utf-8')
        if len(content) > MAX_RESULT_BYTES: raise ValueError('RESEARCH_OCR_RESULT_LIMIT')
        return content

    def validate_review(self, nid, scope, actor, row):
        if self._row(nid, scope, actor, row['id']) != row:
            raise StaleSourceError('RESEARCH_OCR_REVIEW_CHANGED')
        execution = row.get('native_ocr_execution')
        if not execution or row['status'] not in {'REVIEW_REQUIRED', 'REVIEWED'}:
            raise ValueError('RESEARCH_OCR_REVIEW_REQUIRED')
        self.rows._source(nid, scope, actor, row)
        with self.lease(nid, execution['binding']['project_incarnation']):
            job = self.manager.persistence.get(execution['generation_id'])
            ledger = self.broker.get(nid, scope, self.broker.LEDGER, execution['reservation_id'])
            result = row.get('result') or {}
            binding = execution['binding']; text = job.get('output')
            if not isinstance(text, str) or not text:
                raise ValueError('RESEARCH_OCR_DURABLE_RESULT_MISMATCH')
            capability = ResearchVisionCapability(provider_id=job['requested_provider'], model_id=job['requested_model'],
                model_revision=binding['route_digest'], local=True, operations=['OCR'], verification='CONTRACT_VERIFIED')
            source_input = ResearchVisionInput(b'', 'IMAGE', (1,), binding['source_id'], binding['source_version'], binding['source_digest'])
            expected = bind_research_analysis_result(source_input, {'blocks': [
                {'kind': 'TEXT', 'page': 1, 'text': text[i:i + 8000]} for i in range(0, len(text), 8000)],
                'warnings': ['LOCAL_NATIVE_OCR_REVIEW_REQUIRED']}, capability)
            decision = self.broker.get(nid, scope, self.broker.DECISIONS, ledger['preview_id'])
            admitted = (decision.get('chosen') or {}).get('identity', {}).get('native_ocr_binding', {})
            receipt = {'model_called': True, 'source_digest': binding['source_digest'],
                'input_sha256': binding['source_digest'], 'route_digest': binding['route_digest'],
                'language': binding['language'], 'text_sha256': sha256(text.encode()).hexdigest(),
                'provider_uuid': admitted.get('provider_uuid'), 'model_uuid': admitted.get('model_uuid'),
                'execution_node_uuid': admitted.get('execution_node_uuid'),
                'model_sha256': admitted.get('route', {}).get('model_sha256'),
                'admission_digest': admitted.get('route', {}).get('admission_digest'),
                'automatic_canon': False, 'review_required': True, 'model_quality': 'NOT_RUN'}
            if (result != expected or row.get('model') != capability.model_dump()
                    or execution.get('runtime_receipt') != receipt
                    or ledger.get('created_by') != actor or decision.get('created_by') != actor
                    or decision.get('candidate_profile') != 'LOCAL_NATIVE_OCR_ONLY_V1'
                    or admitted.get('route_digest') != binding['route_digest']
                    or ledger.get('cost_state') != 'KNOWN_LOCAL_PROVIDER_ZERO'
                    or job.get('provider') != job['requested_provider'] or job.get('model') != job['requested_model']
                    or job.get('status') != 'COMPLETED' or job.get('terminal_hook_status') != 'COMPLETED'
                    or job.get('research_ocr_binding') != execution['binding']
                    or job.get('expected_request_digest') != execution['expected_request_digest']
                    or job.get('output') != text or sha256(text.encode()).hexdigest() != execution.get('output_sha256')
                    or digest(result) != row.get('result_digest') or result.get('automatic_canon') is not False
                    or ledger.get('status') != 'SETTLED' or ledger.get('job_id') != job['id']
                    or ledger.get('authorization_digest') != job['expected_request_digest']
                    or ledger.get('native_ocr_incarnation') != execution['binding']['project_incarnation']):
                raise ValueError('RESEARCH_OCR_DURABLE_RESULT_MISMATCH')
