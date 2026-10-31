"""B02 bounded composition of the original author/broker/Workflow seams.

No model adapter, scheduler, prompt builder, fallback or executable registry is
implemented here. A single explicit local model node has one durable admission.
Admission uncertainty never permits a replay, including after process restart.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from dataclasses import asdict

from pydantic import Field

from ..author_request import request_digest, request_payload
from ..jobs import mark_generation_origin
from .author_context_api import AuthorPreviewInput
from .common import check_version, change_row, now
from .declarative_adapter_sdk import BoundModelReceipt
from .declarative_agents import ActionIn, _ScopedOriginalWorkflowHost, OutputLimitError, validate_object
from .model_broker import BrokerRequest
from .planning import digest
from .store import canonical


class ModelDispatchIn(ActionIn):
    reviewed_preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class DeclarativeModelCoordinator:
    def __init__(self, service, preparer, manager):
        self.service, self.preparer, self.manager = service, preparer, manager

    @property
    def broker(self): return self.service.broker

    def _row(self, ctx, rid, guard, *, active=False):
        guard()
        row = self.service._owned(ctx, self.service.RUNS, rid)
        self.service._assert_current(ctx, row)
        if active and row['status'] != 'RUNNING': raise ValueError('MODEL_RUN_NO_LONGER_ACTIVE')
        if row.get('started_at'):
            deadline = datetime.fromisoformat(row['started_at']) + timedelta(seconds=row['timeout_seconds'])
            if datetime.now(timezone.utc) >= deadline: raise ValueError('WORKFLOW_TIMEOUT')
        return row

    def _node(self, row):
        node = next((n for n in row['definition_snapshot']['nodes'] if n['type'] == 'agent_task'), None)
        if node is None: raise ValueError('BOUND_MODEL_NODE_REQUIRED')
        return node['id']

    def _author(self, ctx, row, route):
        agent = row['definition_snapshot']['agent']
        # These are visible user instructions, never system or tool authority.
        instructions = {'purpose': agent['purpose'], 'role_instructions': agent['role_prompt'],
                        'input': {k: v for k, v in row['input'].items() if k != 'source_text'}}
        if not row['sources']: instructions['input']['source_text'] = row['input']['source_text']
        return AuthorPreviewInput(novel_id=ctx.novel_id, chapter_id=row['anchor']['id'],
            chapter_version=row['anchor']['version'], operation='brainstorm',
            instruction=canonical(instructions), profile='LOCAL_ONLY',
            provider_id=route['provider_id'], model_id=route['model_id'],
            source=row['input']['source_text'] if row['sources'] else '',
            request_scope={'source_mode': 'SELECTION_ONLY' if row['sources'] else 'NONE',
                'include_automatic_context': False, 'include_style_reference': False, 'include_plan_reference': False})

    def preview(self, ctx, rid, value, guard):
        body = ActionIn.model_validate(value)
        row = self._row(ctx, rid, guard); check_version(row, body.expected_version)
        node_id = self._node(row)
        if row['status'] != 'WAITING_APPROVAL' or row.get('current_node_id') != node_id or row.get('model_execution'):
            raise ValueError('MODEL_NODE_NOT_AWAITING_EXPLICIT_DISPATCH')
        route = self.broker.current_route(row['definition_snapshot']['agent']['model_route'])
        if route['cloud']: raise ValueError('DECLARATIVE_MODEL_LOCAL_ONLY')
        author = self._author(ctx, row, route)
        prepared = self.preparer.prepare_preview(ctx.novel_id, author, ctx.token, ctx.branch)
        receipt = request_digest(prepared.request, prepared.job, False)
        author = author.model_copy(update={'preview_digest': receipt})
        def current():
            current_row = self._row(ctx, rid, guard)
            check_version(current_row, row['version'])
        decision = self.broker.preview(ctx.novel_id, ctx.scope, ctx.actor,
            BrokerRequest(chapter_ids=[row['anchor']['id']], policy='CUSTOM', preferred_route=route['route_id'],
                profile='LOCAL_ONLY', max_cost_microusd=0, allow_synthetic=bool(route['synthetic'])), current)
        preview = {'node_id': node_id, 'author': author.model_dump(mode='json'),
            'request': request_payload(prepared.request), 'broker_preview_id': decision['id'],
            'broker_preview_version': decision['version'], 'broker': decision,
            'input_digest': row['input_digest'], 'definition_digest': row['definition_digest'],
            'source_strategy': 'EXACT_SAVED_SELECTION' if row['sources'] else 'NO_MANUSCRIPT',
            'quality_verification': 'NOT_RUN', 'model_called': False, 'automatic_retry': False,
            'execution_available': bool(decision['chosen'])}
        # SDK receipt is an opaque binding, never an executable extension.
        preview['contract'] = asdict(BoundModelReceipt(run_id=rid, node_id=node_id,
            definition_digest=row['definition_digest'], author_request_digest=receipt,
            broker_preview_id=decision['id'], reviewed_preview_digest='',
            source_strategy=preview['source_strategy'], max_output_bytes=row['max_output_bytes'],
            deadline=(datetime.fromisoformat(row['started_at']) + timedelta(seconds=row['timeout_seconds'])).isoformat()))
        preview['preview_digest'] = digest(preview)
        preview['contract']['reviewed_preview_digest'] = preview['preview_digest']
        with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
            stored = self.service._owned(ctx, self.service.RUNS, rid, state)
            current()
            change_row(stored, ctx.actor, body.expected_version, lambda r: r.update(model_preview=preview))
            guard()
            return self.service._public_run(ctx, stored)

    def _commit_host(self, ctx, row, host, result, **extra):
        payload = {k: v for k, v in result.items() if k not in {'history', 'version'}}
        payload.update(extra, trace=row['trace'] + host.transitions,
                       dispatch_trace=row['dispatch_trace'] + host.dispatches)
        change_row(row, ctx.actor, row['version'], lambda r: r.update(payload))

    def dispatch(self, ctx, rid, value, guard):
        body = ModelDispatchIn.model_validate(value)
        row = self._row(ctx, rid, guard)
        preview = row.get('model_preview')
        if (not preview or preview['preview_digest'] != body.reviewed_preview_digest
            or not preview['execution_available']): raise ValueError('MODEL_EXACT_PREVIEW_REQUIRED')
        if row.get('model_execution'):
            # Never start a replacement, even when the original job is absent.
            return self.service._public_run(ctx, row)
        check_version(row, body.expected_version)
        author = AuthorPreviewInput.model_validate(preview['author'])
        job = self.preparer.prepare_author(ctx.novel_id, author, ctx.token, ctx.branch)
        mark_generation_origin(job, 'declarative_agent')
        job.generation_max_output_bytes = row['max_output_bytes']
        job.generation_deadline = (datetime.fromisoformat(row['started_at']) + timedelta(seconds=row['timeout_seconds'])).isoformat()
        expected_bounds = (job.generation_max_output_bytes, job.generation_deadline)
        original_authority = job.request_authorization
        def current():
            if (job.generation_max_output_bytes, job.generation_deadline) != expected_bounds:
                raise ValueError('MODEL_EXECUTION_BOUNDS_CHANGED')
            active = self._row(ctx, rid, guard, active=True)
            if not active.get('model_execution') or active['model_execution']['job_id'] != job.id:
                raise ValueError('MODEL_EXECUTION_BINDING_CHANGED')
            original_authority()
        job.request_authorization = current
        node_id = preview['node_id']
        execution = {'job_id': job.id, 'node_id': node_id, 'reservation_id': None,
            'status': 'ADMISSION_PENDING', 'receipt_state': 'UNKNOWN_NO_AUTOMATIC_REPLAY',
            'quality_verification': 'NOT_RUN', 'usage_state': 'UNKNOWN', 'model_called': False}
        with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
            stored = self.service._owned(ctx, self.service.RUNS, rid, state)
            check_version(stored, body.expected_version)
            self.service._assert_current(ctx, stored); guard()
            if stored.get('model_execution') or stored.get('model_preview') != preview: raise ValueError('MODEL_ADMISSION_CHANGED')
            host = _ScopedOriginalWorkflowHost(stored, lambda: (guard(), self.service._assert_current(ctx, stored, state)))
            host.trigger_agent_node(rid, node_id, ctx.actor)
            result = host.claim_agent_task(rid, node_id, ctx.actor)
            self._commit_host(ctx, stored, host, result, model_execution=execution)
            guard()
        # No network/model side effect is allowed inside the Workflow transaction.
        # The durable claim precedes the broker reservation and executor admission.
        try:
            reservation = self.broker.reserve(ctx.novel_id, ctx.scope, ctx.actor,
                preview['broker_preview_id'], preview['broker_preview_version'],
                'declarative:' + rid, job.id, current, preview['preview_digest'])
            if reservation['job_id'] != job.id: raise ValueError('MODEL_ADMISSION_UNKNOWN')
            execution.update(reservation_id=reservation['id'], status='QUEUED', receipt_state='RECORDED')
            with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
                stored = self.service._owned(ctx, self.service.RUNS, rid, state)
                current()
                change_row(stored, ctx.actor, stored['version'], lambda r: r.update(model_execution=deepcopy(execution)))
                guard()
            job.before_dispatch = lambda: self.broker.guard_dispatch(ctx.novel_id, ctx.scope, ctx.actor,
                reservation['id'], job.id, current)
            job.on_terminal = lambda: self.broker.finalize(ctx.novel_id, ctx.scope, ctx.actor,
                reservation['id'], job.id, job.execution_outcome or 'UNKNOWN', job.usage)
            self.manager.start_prepared(job)
        except Exception:
            # If persistence/start failed, retain the original reservation. Its
            # absence from JobManager is not proof that an upstream never ran.
            # No automatic release/replay or replacement admission follows.
            with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
                stored = self.service._owned(ctx, self.service.RUNS, rid, state)
                execution.update(status='UNKNOWN', receipt_state='UNKNOWN_NO_AUTOMATIC_REPLAY')
                change_row(stored, ctx.actor, stored['version'], lambda r: r.update(model_execution=deepcopy(execution)))
            raise
        return self.service.get_run(ctx, rid)

    def refresh(self, ctx, rid, value, guard):
        body = ActionIn.model_validate(value)
        row = self.service._owned(ctx, self.service.RUNS, rid); check_version(row, body.expected_version)
        guard(); self.service._assert_current(ctx, row)
        execution = deepcopy(row.get('model_execution'))
        if not execution: raise ValueError('MODEL_EXECUTION_REQUIRED')
        try: job = self.manager.get(execution['job_id'])
        except KeyError: job = None
        ledger = self.broker.get(ctx.novel_id, ctx.scope, self.broker.LEDGER, execution['reservation_id']) if execution.get('reservation_id') else None
        if ledger and (ledger['created_by'] != ctx.actor or ledger['job_id'] != execution['job_id']):
            raise ValueError('MODEL_RECEIPT_AUTHORITY_CHANGED')
        execution.update(status=job.public()['status'] if job else 'UNKNOWN',
            receipt_state='RECORDED' if job and callable(job.request_authorization) and (job.status not in self.manager.terminal or job.terminal_hook_status == 'COMPLETED') else 'UNKNOWN_NO_AUTOMATIC_REPLAY',
            usage_state=job.usage_status if job else 'UNKNOWN', failure_code=job.error_code if job else None,
            model_called=bool(ledger and ledger['dispatched']),
            accounting={k: ledger.get(k) for k in ('id', 'version', 'status', 'cost_state', 'actual_microusd', 'accounted_microusd')} if ledger else None)
        with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
            stored = self.service._owned(ctx, self.service.RUNS, rid, state); check_version(stored, body.expected_version)
            def current(): guard(); self.service._assert_current(ctx, stored, state)
            current()
            host = _ScopedOriginalWorkflowHost(stored, current)
            result = host.get_workflow_run(rid)
            if result['status'] == 'RUNNING' and job and job.public()['status'] in {'COMPLETED', 'FAILED', 'CANCELLED'}:
                success = job.status == 'COMPLETED' and job.terminal_hook_status == 'COMPLETED' and bool(job.output.strip())
                output = None
                if success:
                    # Re-run the exact original author/source guard before
                    # admitting text into review. Restart loses that authority.
                    if not callable(job.request_authorization):
                        success = False; execution['receipt_state'] = 'UNKNOWN_NO_AUTOMATIC_REPLAY'
                    else:
                        job.request_authorization()
                        output = {'draft': job.output, 'provenance': {'method': 'ORIGINAL_AUTHOR_EXECUTOR',
                            'job_id': job.id, 'request_digest': job.expected_request_digest},
                            'model_called': True, 'applied': False, 'quality_verification': 'NOT_RUN'}
                        schema = stored['definition_snapshot']['agent']['output_schema']
                        try:
                            validate_object(schema, {f['name']: job.output if f['name'] == 'draft' else 'Model draft; human review required.' for f in schema['fields']})
                            if len(canonical(output).encode()) > stored['max_output_bytes']: raise OutputLimitError('WORKFLOW_OUTPUT_LIMIT')
                        except ValueError:
                            success = False; output = None
                try:
                    result = host.complete_agent_task(rid, execution['node_id'], 'SUCCEEDED' if success else 'FAILED',
                        output=output, error=None if success else 'MODEL_FAILED_OR_OUTPUT_DISCARDED')
                except OutputLimitError:
                    result = deepcopy(stored); result.update(status='FAILED', error={'code': 'WORKFLOW_OUTPUT_LIMIT'}, agent_output=None)
            self._commit_host(ctx, stored, host, result, model_execution=execution,
                model_called=execution['model_called'], external_ai_calls=False)
            current()
            public = self.service._public_run(ctx, stored)
        if public['status'] in {'FAILED', 'CANCELLED', 'REJECTED'} and job:
            self.manager.cancel(job.id)
        return public

    def cancel(self, ctx, rid):
        row = self.service._owned(ctx, self.service.RUNS, rid)
        execution = row.get('model_execution')
        if execution:
            try: self.manager.cancel(execution['job_id'])
            except KeyError: pass  # Durable cancelled run still blocks dispatch.
