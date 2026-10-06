"""B05 selected-segment composition of original Author/Broker/JobManager.

One durable admission per preview. No provider, scheduler, model-quality claim,
source write, automatic replay or segment approval is implemented here.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pydantic import Field

from ..author_request import request_digest, request_payload
from ..jobs import mark_generation_origin
from .author_context_api import AuthorPreviewInput
from .common import StaleSourceError, change_row, new_row, now
from .model_broker import BrokerRequest
from .multilingual_editions import VersionIn, MAX_TARGET_TEXT, valid_text
from .planning import collection, digest, require_row
from .store import canonical

MAX_OUTPUT_BYTES = 20_000
TIMEOUT_SECONDS = 300


class TranslationPreviewIn(VersionIn):
    route_id: str = Field(min_length=1, max_length=160)
    allow_synthetic: bool = False


class TranslationDispatchIn(VersionIn):
    reviewed_preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class TranslationAdoptIn(VersionIn):
    expected_edition_version: int = Field(ge=1)
    candidate_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class MultilingualTranslationCoordinator:
    RUNS = 'language_translation_runs_v2'

    def __init__(self, service, preparer, broker, manager):
        self.service, self.preparer, self.broker, self.manager = service, preparer, broker, manager

    def _owned(self, ctx, eid, rid, state=None):
        row = require_row(state, self.RUNS, rid) if state is not None else self.service.get(ctx.novel_id, ctx.scope, self.RUNS, rid)
        if row['created_by'] != ctx.actor or row['edition_id'] != eid: raise FileNotFoundError(rid)
        return row

    def _edition(self, ctx, eid, expected, state=None):
        row = require_row(state, self.service.COLLECTION, eid) if state is not None else self.service._owned(ctx.novel_id, ctx.scope, ctx.actor, eid)
        if row['created_by'] != ctx.actor: raise FileNotFoundError(eid)
        self.service._version(row, expected)
        return row, self.service._current(ctx.novel_id, ctx.scope, row)

    def _bound(self, ctx, row, guard, state=None):
        guard()
        edition, texts = self._edition(ctx, row['edition_id'], row['edition_version'], state)
        segment = self.service._segment(edition, row['segment_id'])
        if digest([edition['sources'], segment, edition['rules'], edition['style_note'], edition['target_language'], edition['source_language']]) != row['binding_digest']:
            raise StaleSourceError('TRANSLATION_EDITION_OR_SOURCE_CHANGED')
        return edition, texts

    def _route_current(self, ctx, row):
        decision = self.broker.get(ctx.novel_id, ctx.scope, self.broker.DECISIONS, row['preview']['broker']['id'])
        self.broker._assert_preview(ctx.novel_id, ctx.scope, ctx.actor, decision)
        return decision

    def routes(self, ctx, guard):
        guard()
        rows = [{k: deepcopy(r[k]) for k in ('route_id', 'provider_id', 'model_id', 'display_name', 'available', 'reasons', 'synthetic', 'verification')}
                for r in self.broker.candidates() if r['capability'] == 'TEXT' and not r['cloud']]
        guard()
        return {'items': rows, 'profile': 'LOCAL_ONLY', 'max_cost_microusd': 0, 'quality_verification': 'NOT_RUN'}

    def _public(self, ctx, row, guard):
        guard()
        safe = {k: deepcopy(row.get(k)) for k in ('id', 'version', 'status', 'edition_id', 'edition_version', 'segment_id', 'created_at', 'execution', 'adopted_edition_version')}
        safe.update(automatic_retry=False, quality_verification='NOT_RUN', source_applied=False,
                    stale=False, content_withheld=False, candidate=None, preview=None)
        # After adoption the original edition CAS intentionally changed. Retain
        # only receipts, never expose stored plaintext under a stale authority.
        if row['status'] == 'ADOPTED': return safe
        try:
            self._bound(ctx, row, guard)
            if row.get('execution'): self._route_current(ctx, row)
        except (ValueError, FileNotFoundError, HTTPException):
            safe.update(stale=True, content_withheld=True)
            return safe
        safe['preview'] = deepcopy(row['preview'])
        if row['status'] == 'CANDIDATE':
            try:
                job = self._trusted_job(ctx, row, guard)
                if job.output != row['candidate']['text']: raise ValueError('TRANSLATION_OUTPUT_CHANGED')
                safe['candidate'] = deepcopy(row['candidate'])
            except (ValueError, KeyError, FileNotFoundError, HTTPException):
                safe.update(content_withheld=True, stale=True)
        guard()
        return safe

    def list(self, ctx, eid, guard):
        self.service._owned(ctx.novel_id, ctx.scope, ctx.actor, eid); guard()
        rows = [r for r in self.service.list(ctx.novel_id, ctx.scope, self.RUNS) if r['created_by'] == ctx.actor and r['edition_id'] == eid]
        return {'items': [self._public(ctx, r, guard) for r in rows[-50:]], 'truncated': len(rows) > 50}

    def preview(self, ctx, eid, sid, value, guard):
        body = TranslationPreviewIn.model_validate(value)
        edition, texts = self._edition(ctx, eid, body.expected_version)
        segment = self.service._segment(edition, sid); guard()
        decision = self.broker.preview(ctx.novel_id, ctx.scope, ctx.actor,
            BrokerRequest(chapter_ids=[segment['chapter_id']], policy='CUSTOM', preferred_route=body.route_id,
                          profile='LOCAL_ONLY', max_cost_microusd=0, allow_synthetic=body.allow_synthetic), guard)
        preview = {'broker': decision, 'author': None, 'request': None, 'execution_available': False,
                   'source_strategy': 'EXACT_SAVED_SEGMENT', 'max_output_bytes': MAX_OUTPUT_BYTES,
                   'timeout_seconds': TIMEOUT_SECONDS, 'quality_verification': 'NOT_RUN', 'model_called': False,
                   'automatic_retry': False, 'excluded': ['OTHER_SEGMENTS', 'AUTOMATIC_CONTEXT', 'UNAPPROVED_RULES', 'EXTERNAL_REFERENCES']}
        route = decision['chosen']
        if route:
            price = route.get('price') or {}
            known_zero = price.get('actual_known_zero') or all(price.get(k) == 0 for k in ('input_per_million_microusd', 'output_per_million_microusd'))
            if not known_zero:
                preview['blocked_reason'] = 'TRANSLATION_KNOWN_ZERO_PRICE_REQUIRED'
                route = None
        if route:
            if route['cloud'] or route['price']['reserve_microusd'] != 0: raise ValueError('TRANSLATION_LOCAL_KNOWN_ZERO_ONLY')
            instructions = {'task': 'Translate only the selected saved segment. Return only the translated text; no commentary or tool calls.',
                            'source_language': edition['source_language'], 'target_language': edition['target_language'],
                            'style_note': edition['style_note'],
                            'approved_terminology': [r for r in edition['rules'] if r['status'] == 'APPROVED']}
            author = AuthorPreviewInput(novel_id=ctx.novel_id, chapter_id=segment['chapter_id'], chapter_version=segment['source_version'],
                operation='rewrite', instruction=canonical(instructions), profile='LOCAL_ONLY',
                provider_id=route['provider_id'], model_id=route['model_id'], source=texts[sid],
                request_scope={'source_mode': 'SELECTION_ONLY', 'include_automatic_context': False,
                               'include_style_reference': False, 'include_plan_reference': False})
            prepared = self.preparer.prepare_preview(ctx.novel_id, author, ctx.token, ctx.branch)
            author = author.model_copy(update={'preview_digest': request_digest(prepared.request, prepared.job, False)})
            preview.update(author=author.model_dump(mode='json'), request=request_payload(prepared.request), execution_available=True)
        preview['preview_digest'] = digest(preview)
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'edition_id': eid, 'edition_version': edition['version'], 'segment_id': sid,
            'binding_digest': digest([edition['sources'], segment, edition['rules'], edition['style_note'], edition['target_language'], edition['source_language']]),
            'preview': preview, 'status': 'PREVIEW' if route else 'BLOCKED', 'execution': None, 'candidate': None})
        with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
            self._bound(ctx, row, guard, state)
            rows = collection(state, self.RUNS)
            if sum(r['edition_id'] == eid for r in rows.values()) >= 200: raise ValueError('TRANSLATION_PREVIEW_LIMIT')
            rows[row['id']] = row; guard()
        return self._public(ctx, row, guard)

    def dispatch(self, ctx, eid, rid, value, guard):
        body = TranslationDispatchIn.model_validate(value); row = self._owned(ctx, eid, rid)
        guard()
        if body.reviewed_preview_digest != row['preview']['preview_digest']: raise ValueError('TRANSLATION_EXACT_PREVIEW_REQUIRED')
        # An exact retry recovers the original identity, including uncertain,
        # cancelled and stale admissions. It never builds a replacement job.
        if row['execution']: return self._public(ctx, row, guard)
        self.service._version(row, body.expected_version); self._bound(ctx, row, guard)
        if not row['preview']['execution_available'] or row['status'] != 'PREVIEW': raise ValueError('TRANSLATION_LEGAL_PREVIEW_REQUIRED')
        self._route_current(ctx, row)
        job = self.preparer.prepare_author(ctx.novel_id, AuthorPreviewInput.model_validate(row['preview']['author']), ctx.token, ctx.branch)
        mark_generation_origin(job, 'multilingual_translation')
        job.generation_max_output_bytes = MAX_OUTPUT_BYTES
        job.generation_deadline = (datetime.now(timezone.utc) + timedelta(seconds=TIMEOUT_SECONDS)).isoformat()
        bounds = (job.generation_max_output_bytes, job.generation_deadline)
        original_authority = job.request_authorization
        def current():
            active = self._owned(ctx, eid, rid)
            self._bound(ctx, active, guard)
            if (not active['execution'] or active['execution']['job_id'] != job.id or
                active['status'] not in {'ADMISSION_PENDING', 'QUEUED', 'RUNNING', 'GENERATING', 'SETTLING', 'CANDIDATE'}):
                raise ValueError('TRANSLATION_ADMISSION_INACTIVE')
            if (job.generation_max_output_bytes, job.generation_deadline) != bounds or (active['execution']['max_output_bytes'], active['execution']['deadline']) != bounds: raise ValueError('TRANSLATION_BOUNDS_CHANGED')
            if job.status != 'COMPLETED' and active['status'] != 'CANDIDATE' and datetime.now(timezone.utc) >= datetime.fromisoformat(bounds[1]): raise ValueError('TRANSLATION_DEADLINE_EXCEEDED')
            self._route_current(ctx, active)
            original_authority()
        job.request_authorization = current
        execution = {'job_id': job.id, 'reservation_id': None, 'receipt_state': 'UNKNOWN_NO_AUTOMATIC_REPLAY',
                     'deadline': job.generation_deadline, 'max_output_bytes': MAX_OUTPUT_BYTES,
                     'model_called': False, 'usage_state': 'UNKNOWN', 'accounting': None}
        with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
            stored = self._owned(ctx, eid, rid, state)
            self.service._version(stored, body.expected_version); self._bound(ctx, stored, guard, state)
            if stored['execution']: raise ValueError('TRANSLATION_ADMISSION_CHANGED')
            for previous in collection(state, self.RUNS).values():
                if previous['id'] != rid and previous['edition_id'] == eid and previous['segment_id'] == row['segment_id'] and previous.get('execution') and previous['status'] in {'ADMISSION_PENDING', 'QUEUED', 'RUNNING', 'GENERATING', 'SETTLING', 'UNKNOWN'}:
                    raise ValueError('TRANSLATION_ORIGINAL_ADMISSION_REQUIRES_RECOVERY')
            change_row(stored, ctx.actor, body.expected_version, lambda r: r.update(status='ADMISSION_PENDING', execution=deepcopy(execution)))
            guard()
        try:
            reservation = self.broker.reserve(ctx.novel_id, ctx.scope, ctx.actor,
                row['preview']['broker']['id'], row['preview']['broker']['version'], 'translation:' + rid, job.id, current, row['preview']['preview_digest'])
            if reservation['job_id'] != job.id or reservation['reserve_microusd'] != 0: raise ValueError('TRANSLATION_ADMISSION_UNKNOWN')
            execution.update(reservation_id=reservation['id'], receipt_state='RECORDED')
            with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
                stored = self._owned(ctx, eid, rid, state); current()
                change_row(stored, ctx.actor, stored['version'], lambda r: r.update(status='QUEUED', execution=deepcopy(execution))); guard()
            job.before_dispatch = lambda: self.broker.guard_dispatch(ctx.novel_id, ctx.scope, ctx.actor, reservation['id'], job.id, current)
            job.on_terminal = lambda: self.broker.finalize(ctx.novel_id, ctx.scope, ctx.actor, reservation['id'], job.id, job.execution_outcome or 'UNKNOWN', job.usage)
            self.manager.start_prepared(job)
        except Exception:
            with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
                stored = self._owned(ctx, eid, rid, state)
                execution['receipt_state'] = 'UNKNOWN_NO_AUTOMATIC_REPLAY'
                # A concurrent cancellation remains irrevocable.
                change_row(stored, ctx.actor, stored['version'], lambda r: r.update(status='CANCELLED' if r['status'] == 'CANCELLED' else 'UNKNOWN', execution=deepcopy(execution), candidate=None))
            raise
        return self._public(ctx, self._owned(ctx, eid, rid), guard)

    def _trusted_job(self, ctx, row, guard):
        self._bound(ctx, row, guard); self._route_current(ctx, row)
        execution = row['execution']
        if not execution or not execution['reservation_id']: raise ValueError('TRANSLATION_RECEIPT_UNKNOWN')
        job = self.manager.get(execution['job_id'])
        ledger = self.broker.get(ctx.novel_id, ctx.scope, self.broker.LEDGER, execution['reservation_id'])
        if (ledger['created_by'] != ctx.actor or ledger['job_id'] != job.id or ledger['preview_id'] != row['preview']['broker']['id'] or ledger['status'] != 'SETTLED' or not ledger['dispatched'] or
            job.experimental_origin != 'multilingual_translation' or job.expected_request_digest != row['preview']['author']['preview_digest'] or
            job.status != 'COMPLETED' or job.cancelled.is_set() or job.terminal_hook_status != 'COMPLETED' or not callable(job.request_authorization)):
            raise ValueError('TRANSLATION_RESULT_NOT_TRUSTED')
        job.request_authorization()
        valid_text(job.output)
        if not job.output.strip() or len(job.output.encode()) > MAX_OUTPUT_BYTES: raise ValueError('TRANSLATION_OUTPUT_INVALID')
        return job

    def refresh(self, ctx, eid, rid, value, guard):
        body = VersionIn.model_validate(value); row = self._owned(ctx, eid, rid)
        self.service._version(row, body.expected_version); guard()
        execution = deepcopy(row['execution'])
        if not execution: raise ValueError('TRANSLATION_EXECUTION_REQUIRED')
        try: job = self.manager.get(execution['job_id'])
        except KeyError: job = None
        ledger = self.broker.get(ctx.novel_id, ctx.scope, self.broker.LEDGER, execution['reservation_id']) if execution['reservation_id'] else None
        if ledger and (ledger['created_by'] != ctx.actor or ledger['job_id'] != execution['job_id']): raise ValueError('TRANSLATION_RECEIPT_AUTHORITY_CHANGED')
        known = bool(job and callable(job.request_authorization) and (job.status not in self.manager.terminal or
            job.terminal_hook_status == 'COMPLETED' or job.public()['status'] == 'SETTLING'))
        execution.update(receipt_state='RECORDED' if known else 'UNKNOWN_NO_AUTOMATIC_REPLAY',
            model_called=bool(ledger and ledger['dispatched']), usage_state=job.usage_status if job else 'UNKNOWN', failure_code=job.error_code if job else None,
            accounting={k: ledger.get(k) for k in ('id', 'version', 'status', 'cost_state', 'actual_microusd', 'accounted_microusd')} if ledger else None)
        status, candidate = row['status'], None
        if status not in {'CANCELLED', 'ADOPTED'}:
            status = job.public()['status'] if known else 'UNKNOWN'
            if ledger and ledger['status'] == 'UNKNOWN_UPSTREAM': status = 'UNKNOWN'
            if status == 'COMPLETED':
                try:
                    trusted = self._trusted_job(ctx, row, guard)
                    candidate = {'text': trusted.output, 'digest': digest([rid, trusted.id, trusted.expected_request_digest, trusted.output]),
                                 'job_id': trusted.id, 'request_digest': trusted.expected_request_digest, 'quality_verification': 'NOT_RUN', 'applied': False}
                    status = 'CANDIDATE'
                except (ValueError, FileNotFoundError, KeyError, HTTPException): status = 'FAILED' if known else 'UNKNOWN'
        with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
            stored = self._owned(ctx, eid, rid, state); self.service._version(stored, body.expected_version); guard()
            if candidate: self._trusted_job(ctx, stored, guard)
            change_row(stored, ctx.actor, body.expected_version, lambda r: r.update(status=status, execution=execution, candidate=candidate)); guard()
        return self._public(ctx, stored, guard)

    def cancel(self, ctx, eid, rid, value, guard):
        body = VersionIn.model_validate(value)
        with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._owned(ctx, eid, rid, state); self.service._version(row, body.expected_version); guard()
            if row['status'] == 'ADOPTED': raise ValueError('TRANSLATION_ALREADY_ADOPTED')
            change_row(row, ctx.actor, body.expected_version, lambda r: r.update(status='CANCELLED', candidate=None)); guard()
        if row['execution']:
            try: self.manager.cancel(row['execution']['job_id'])
            except KeyError: pass
        return self._public(ctx, row, guard)

    def adopt(self, ctx, eid, rid, value, guard):
        body = TranslationAdoptIn.model_validate(value)
        with self.service.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._owned(ctx, eid, rid, state); self.service._version(row, body.expected_version)
            edition, _ = self._bound(ctx, row, guard, state)
            self.service._version(edition, body.expected_edition_version)
            if row['status'] != 'CANDIDATE' or not row['candidate'] or row['candidate']['digest'] != body.candidate_digest: raise ValueError('TRANSLATION_CANDIDATE_REVIEW_REQUIRED')
            job = self._trusted_job(ctx, row, guard)
            if job.output != row['candidate']['text']: raise ValueError('TRANSLATION_OUTPUT_CHANGED')
            segment = self.service._segment(edition, row['segment_id'])
            if sum(len(s['target_text']) for s in edition['segments'] if s['id'] != segment['id']) + len(job.output) > MAX_TARGET_TEXT: raise ValueError('edition target character limit exceeded')
            def update(current):
                segment.update(target_text=job.output, status='DRAFT', accepted_term_revision=None,
                    translation_provenance={'job_id': job.id, 'run_id': rid, 'request_digest': job.expected_request_digest,
                        'candidate_digest': body.candidate_digest, 'adopted_by': ctx.actor, 'adopted_at': now()})
                segment.pop('reviewed_by', None); segment.pop('reviewed_at', None)
                current['status'] = 'DRAFT'
            change_row(edition, ctx.actor, body.expected_edition_version, update)
            change_row(row, ctx.actor, body.expected_version, lambda r: r.update(status='ADOPTED', candidate=None, adopted_edition_version=edition['version']))
            self.service._current(ctx.novel_id, ctx.scope, edition); guard()
            result = deepcopy(edition)
        return self.service._view(ctx.novel_id, ctx.scope, result)
