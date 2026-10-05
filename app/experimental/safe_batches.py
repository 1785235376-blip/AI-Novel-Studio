"""U16 explicit, serial, snapshot-bound orchestration of existing domain tools.

No timer, automatic restart, cloud fallback or independent model executor.
A persisted claim precedes each effect; an orphaned claim is UNKNOWN and cannot
be retried. Each request runs at most one stage, so stopping is unambiguous.
"""
from __future__ import annotations
import base64
from contextlib import contextmanager
from copy import deepcopy
import threading
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator
from fastapi import HTTPException
from .common import DomainService, StaleSourceError, change_row, check_version, new_row
from .planning import StrictModel, digest
from .reader_sources import authorized_chapter_rows
from .ux import chapter_text
from .media import MockImageWorkflowAdapter, batch_media_context
from .store import canonical
from ..services.export_job_service import ExportJobService
from ..services.novel_service import NovelService
from ..source_privacy import source_privacy_status

FEATURE = 'safe_batches_v2'
ACTIVE = set()
ACTIVE_LOCK = threading.RLock()
MAX_RESULT = 2 * 1024 * 1024


class BatchItemIn(StrictModel):
    kind: Literal['PROOF', 'EXPORT', 'SYNTHETIC_MEDIA']
    chapter_ids: list[str] = Field(default_factory=list, max_length=100)
    start: int = Field(default=0, ge=0, le=2_000_000)
    end: int | None = Field(default=None, ge=1, le=2_000_000)
    format: Literal['txt', 'markdown', 'docx', 'epub', 'pdf'] = 'txt'
    brief_id: str | None = Field(default=None, max_length=240)
    expected_brief_version: int | None = Field(default=None, ge=1)
    adapter_id: str = Field(default='mock-image-v1', max_length=240)

    @model_validator(mode='after')
    def valid_selection(self):
        if len(set(self.chapter_ids)) != len(self.chapter_ids): raise ValueError('BATCH_DUPLICATE_CHAPTER')
        if self.kind != 'SYNTHETIC_MEDIA' and not self.chapter_ids: raise ValueError('BATCH_CHAPTER_SELECTION_REQUIRED')
        if self.kind == 'SYNTHETIC_MEDIA' and (not self.brief_id or self.expected_brief_version is None): raise ValueError('BATCH_BRIEF_REQUIRED')
        if (self.start or self.end is not None) and (self.kind != 'PROOF' or len(self.chapter_ids) != 1): raise ValueError('BATCH_RANGE_REQUIRES_ONE_PROOF_CHAPTER')
        if self.end is not None and self.end <= self.start: raise ValueError('BATCH_RANGE_INVALID')
        return self


class BatchIn(StrictModel):
    items: list[BatchItemIn] = Field(min_length=1, max_length=20)
    concurrency: Literal[1] = 1
    budget_microusd: Literal[0] = 0
    skip_satisfied: bool = True


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1)


class ConfirmIn(VersionIn):
    snapshot_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    budget_microusd: Literal[0] = 0
    confirmed: Literal[True]


class ReviewIn(ConfirmIn):
    proposal_id: str = Field(min_length=1, max_length=240)
    proposal_version: int = Field(ge=1)


class SafeBatchesService(DomainService):
    BATCHES = 'safe_batches_v2'

    def __init__(self, store, novels, chapters, *, sources, reader, media, broker=None, flag_check=None):
        super().__init__(store, novels, chapters)
        self.sources, self.reader, self.media, self.broker = sources, reader, media, broker
        if flag_check is None:
            from .flags import require_flag
            flag_check = require_flag
        self.flag_check = flag_check

    def _rows(self, ctx):
        rows = authorized_chapter_rows(ctx, self.sources, self.chapters)
        if len(rows) > 200 or sum(len(chapter_text(r)) for r in rows) > 2_000_000: raise ValueError('BATCH_SOURCE_LIMIT')
        return [{**r, "batch_source_privacy": source_privacy_status(r, ctx.scope.get("branch_id"), self.store.root)} for r in rows]

    def _brief(self, ctx, rid, rows):
        brief = self.media.get(ctx.novel_id, ctx.scope, self.media.BRIEFS, rid)
        if brief.get('created_by') != ctx.actor or brief.get('hidden') or brief.get('secret') or brief.get('safe_batch_id') or brief.get('change_impact_refresh_id'):
            raise FileNotFoundError('brief unavailable')
        if set(brief.get('sources', {})) - set(rows): raise FileNotFoundError('brief unavailable')
        characters = {r['id']: r for r in self.novels.data_set(ctx.novel_id, 'characters')
            if not r.get('hidden') and not r.get('secret') and str(r.get('visibility', '')).upper() not in {'PRIVATE', 'SECRET', 'DENIED'} and r.get('branch_id') == ctx.scope.get('branch_id')}
        if set(brief.get('character_ids', [])) - set(characters): raise FileNotFoundError('brief unavailable')
        reference_bytes = 0
        for aid in brief.get('reference_asset_ids', []):
            asset = self.media.assets.get(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
            if asset.get('novel_id') != ctx.novel_id or asset.get('branch_id') != ctx.scope.get('branch_id') or asset.get('hidden') or asset.get('secret'): raise FileNotFoundError('brief unavailable')
            if type(asset.get('size')) is not int or asset['size'] < 0: raise ValueError('BATCH_RESOURCE_INVALID')
            reference_bytes += asset['size']
            if reference_bytes > 32 * 1024 * 1024: raise ValueError('BATCH_RESOURCE_LIMIT')
            self.media.assets.content(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
        self.media._assert_brief(ctx.novel_id, ctx.scope, brief)
        return brief

    def _budget(self, ctx):
        if self.broker is None: return {'state': 'NOT_CONFIGURED', 'known_cost_microusd': 0, 'currency': 'USD'}
        try: self.flag_check('model_broker_v2')
        except Exception as exc:
            from fastapi import HTTPException
            if isinstance(exc, HTTPException) and exc.status_code == 404: return {'state': 'DISABLED', 'known_cost_microusd': 0, 'currency': 'USD'}
            raise
        budget = self.broker.budget(ctx.novel_id, ctx.scope)
        # No aggregate counts of other actors' reservations in a batch preview.
        return {'state': 'ORIGINAL_BROKER_CONFIG', 'version': budget['version'], 'limit_microusd': budget['limit_microusd'],
                'max_inflight': budget['max_inflight'], 'require_known_estimate': budget['require_known_estimate'], 'known_cost_microusd': 0, 'currency': 'USD'}

    def _snapshot(self, ctx, value):
        self.flag_check(FEATURE)
        rows = {r['id']: r for r in self._rows(ctx)}; steps = []
        for item in value.items:
            if set(item.chapter_ids) - set(rows): raise FileNotFoundError('source unavailable')
            source_ids = item.chapter_ids; media_snapshot = None; resources = []
            if item.kind == 'SYNTHETIC_MEDIA':
                self.flag_check('cover_storyboard_generation'); self.flag_check('media_adapter_registry')
                brief = self._brief(ctx, item.brief_id, rows)
                operation = 'cover_generation' if brief['kind'] == 'COVER' else 'storyboard_card_generation'
                adapter = self.media.registry.resolve(item.adapter_id, operation)
                # A declaration of local/mock is not a sandbox. Only the exact
                # registered host-owned deterministic implementation is allowed.
                if type(adapter) is not MockImageWorkflowAdapter: raise ValueError('BATCH_REAL_MEDIA_REQUIRES_ORIGINAL_BROKER_AND_WORKFLOW_ADMISSION')
                prepared = self.media.prepare_task(ctx.novel_id, ctx.scope, ctx.actor, {'brief_id': item.brief_id, 'expected_brief_version': item.expected_brief_version, 'adapter_id': item.adapter_id, 'candidate_count': 1})
                media_snapshot = {k: prepared[k] for k in ('brief_version', 'brief_snapshot', 'source_digest', 'sources', 'operation', 'adapter_definition')}
                if 'queued_environment' in prepared: media_snapshot['queued_environment'] = prepared['queued_environment']
                source_ids = list(brief.get('sources', {}))
            if item.kind == 'PROOF':
                self.flag_check('reader_preflight_v2')
                if item.start or item.end is not None:
                    length = len(chapter_text(rows[source_ids[0]]))
                    if item.start >= length or (item.end is not None and item.end > length): raise ValueError('BATCH_RANGE_OUT_OF_BOUNDS')
            if item.kind == 'EXPORT':
                # Reuse original exporter only for its actual supported prose
                # formats. Embedded media requires its resource-package flow.
                if NovelService._asset_references([rows[cid] for cid in source_ids]): raise ValueError('BATCH_EMBEDDED_MEDIA_USE_ORIGINAL_RESOURCE_PACKAGE_EXPORT')
                if item.format == 'pdf':
                    from ..pdf_export import pdf_font_status
                    if not pdf_font_status().get('available'): raise ValueError('BATCH_PDF_FONT_UNAVAILABLE')
                resources = [{'kind': 'CPU_LOCAL', 'gpu_vram': 'NOT_REQUESTED'}]
            config = self.reader.settings(ctx) if item.kind == 'PROOF' else {'format': item.format} if item.kind == 'EXPORT' else media_snapshot
            frozen = {'input': item.model_dump(), 'sources': {cid: digest(rows[cid]) for cid in source_ids}, 'source_versions': {cid: rows[cid]['version'] for cid in source_ids}, 'configuration': config,
                'resource_requirements': resources or [{'kind': 'CPU_LOCAL', 'gpu_vram': 'NOT_REQUESTED'}], 'known_cost_microusd': 0,
                'permission': 'domain.write', 'network': False, 'model': 'SYNTHETIC_FIXTURE' if item.kind == 'SYNTHETIC_MEDIA' else 'NONE'}
            steps.append({**frozen, 'fingerprint': digest(frozen)})
        if len({s['fingerprint'] for s in steps}) != len(steps): raise ValueError('BATCH_DUPLICATE_ITEM')
        meta = self.novels.get(ctx.novel_id)
        return {'steps': steps, 'project_digest': digest({k: meta.get(k) for k in ('title', 'privacy_level', 'privacy')}), 'budget': self._budget(ctx), 'concurrency': 1, 'budget_microusd': 0}

    def _owned(self, ctx, rid):
        row = self.get(ctx.novel_id, ctx.scope, self.BATCHES, rid)
        if row['created_by'] != ctx.actor: raise FileNotFoundError('batch unavailable')
        # Any hidden/deleted source conceals the whole row, including counts.
        rows = {r['id']: r for r in self._rows(ctx)}
        for step in row['snapshot']['steps']:
            if set(step['sources']) - set(rows): raise FileNotFoundError('batch unavailable')
            if step['input']['kind'] == 'SYNTHETIC_MEDIA':
                self.flag_check('cover_storyboard_generation'); self.flag_check('media_adapter_registry')
                self._brief(ctx, step['input']['brief_id'], rows)
        return row

    def _assert(self, ctx, row, reauthorize):
        reauthorize(); fresh = self._snapshot(ctx, BatchIn.model_validate(row['input']))
        if digest(fresh) != row['snapshot_digest']: raise StaleSourceError('BATCH_INPUT_CONFIGURATION_OR_BUDGET_CHANGED')
        reauthorize()

    def _public(self, row):
        result = {k: deepcopy(row[k]) for k in ('id', 'version', 'status', 'snapshot_digest', 'created_at', 'confirmed', 'error_code') if k in row}
        result['budget'] = deepcopy(row['snapshot']['budget']); result['concurrency'] = 1
        result['items'] = []
        for step, item in zip(row['snapshot']['steps'], row['items']):
            public = {k: deepcopy(v) for k, v in item.items() if k not in {'result', 'claim'}}
            public.update(kind=step['input']['kind'], chapter_ids=list(step['sources']), source_versions_digest=digest(step['sources']),
                source_versions=deepcopy(step['source_versions']), configuration_summary={'format': step['input']['format']} if step['input']['kind'] == 'EXPORT' else {'rules_version': step['configuration']['version'], 'start': step['input']['start'], 'end': step['input']['end']} if step['input']['kind'] == 'PROOF' else {'brief_id': step['input']['brief_id'], 'brief_version': step['input']['expected_brief_version'], 'adapter_id': step['input']['adapter_id'], 'candidate_count': 1},
                known_cost_microusd=0, resource_requirements=step['resource_requirements'], permission=step['permission'])
            if item['status'] == 'RUNNING' and item.get('claim') not in ACTIVE:
                public['status'] = 'UNKNOWN'; public['error_code'] = 'BATCH_INTERRUPTED_RECONCILIATION_REQUIRED_NO_REPLAY'
            if item.get('result'):
                payload = item['result']
                if step['input']['kind'] == 'PROOF': public['findings'] = payload['items']
                elif step['input']['kind'] == 'EXPORT': public['download_available'] = True; public['format'] = step['input']['format']
                else: public['proposals'] = deepcopy(payload['proposals']); public['verification'] = 'SYNTHETIC_PROTOCOL_ONLY'
            result['items'].append(public)
        if any(r['status'] == 'UNKNOWN' for r in result['items']): result['status'] = 'UNKNOWN'
        result['limitations'] = ['EXPLICIT_ONE_STAGE_PER_REQUEST', 'NO_REAL_MODEL_OR_CLOUD_CALLS', 'MEDIA_REQUIRES_SEPARATE_REVIEW', 'UNKNOWN_RESULT_MUST_RECONCILE_IN_ORIGINAL_EXECUTOR']
        return result

    def catalog(self, ctx):
        rows = {r['id']: r for r in self._rows(ctx)}; briefs = []
        try:
            self.flag_check('cover_storyboard_generation'); self.flag_check('media_adapter_registry')
            for brief in self.media.list(ctx.novel_id, ctx.scope, self.media.BRIEFS):
                try: self._brief(ctx, brief['id'], rows)
                except (FileNotFoundError, ValueError): continue
                briefs.append({'id': brief['id'], 'title': brief.get('title') or brief['kind'], 'version': brief['version'], 'kind': brief['kind']})
        except Exception as exc:
            from fastapi import HTTPException
            if not isinstance(exc, HTTPException) or exc.status_code != 404: raise
        return {'chapters': [{'id': r['id'], 'title': r['title'], 'version': r['version']} for r in rows.values()], 'briefs': briefs,
            'formats': ['txt', 'markdown', 'docx', 'epub', 'pdf'], 'concurrency': 1, 'known_cost_microusd': 0,
            'unsupported': ['REAL_AUDIO_REDO_REQUIRES_VOICE_WORKFLOW_ADMISSION', 'REAL_IMAGE_VIDEO_REQUIRE_REGISTERED_WORKFLOW_AND_BROKER', 'NO_OWNED_GPU_RUNTIME_TELEMETRY_NO_GPU_SCHEDULING'],
            'budget': self._budget(ctx)}

    def list_batches(self, ctx):
        result = []
        for row in self.list(ctx.novel_id, ctx.scope, self.BATCHES):
            if row['created_by'] != ctx.actor: continue
            try: row = self._owned(ctx, row['id'])
            except (FileNotFoundError, ValueError): continue
            except HTTPException as exc:
                if exc.status_code == 404: continue
                raise
            try:
                self._assert(ctx, row, lambda: None)
                if row['status'] != 'CANCELLED':
                    with self._media_context(ctx, row['id'], lambda: self._assert(ctx, row, lambda: None)):
                        for item in row['items']:
                            for proposal in (item.get('result') or {}).get('proposals', []):
                                current = self.media.get(ctx.novel_id, ctx.scope, self.media.PROPOSALS, proposal['id'])
                                proposal.update({key: current[key] for key in ('version', 'status', 'asset_id') if key in current})
            except (FileNotFoundError, ValueError):
                pass
            public = self._public(row)
            try: self._assert(ctx, row, lambda: None); public['stale'] = False
            except (ValueError, FileNotFoundError):
                public = {k: public[k] for k in ('id', 'version', 'status', 'snapshot_digest', 'created_at')}; public['stale'] = True
            result.append(public)
        return {'items': result[-100:]}

    def preflight(self, ctx, body, reauthorize=lambda: None):
        value = BatchIn.model_validate(body); frozen = self._snapshot(ctx, value); reauthorize()
        completed = {}
        if value.skip_satisfied:
            for row in self.list(ctx.novel_id, ctx.scope, self.BATCHES):
                if row['created_by'] != ctx.actor or row['status'] not in {'COMPLETED', 'PARTIAL'}: continue
                try: self._owned(ctx, row['id']); self._assert(ctx, row, reauthorize)
                except (FileNotFoundError, ValueError): continue
                except HTTPException as exc:
                    if exc.status_code == 404: continue
                    raise
                for step, item in zip(row['snapshot']['steps'], row['items']):
                    if item['status'] in {'COMPLETED', 'SKIPPED'} and item.get('result') and step['input']['kind'] != 'SYNTHETIC_MEDIA':
                        completed[step['fingerprint']] = item['result']
        items = []
        for index, step in enumerate(frozen['steps']):
            result = completed.get(step['fingerprint']); items.append({'index': index, 'status': 'SKIPPED' if result else 'PENDING', 'attempts': 0, 'result': deepcopy(result), 'claim': None})
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'input': value.model_dump(), 'snapshot': frozen, 'snapshot_digest': digest(frozen), 'items': items, 'status': 'PREFLIGHT', 'confirmed': False})
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            self._assert(ctx, row, reauthorize); state['collections'].setdefault(self.BATCHES, {})[row['id']] = row
        return self._public(row)

    def confirm(self, ctx, rid, body, reauthorize=lambda: None):
        value = ConfirmIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version); self._assert(ctx, row, reauthorize)
        if row['status'] != 'PREFLIGHT' or value.snapshot_digest != row['snapshot_digest']: raise ValueError('BATCH_CONFIRMATION_CHANGED')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.BATCHES][rid]
            change_row(current, ctx.actor, value.expected_version, lambda r: r.update(confirmed=True, status='READY' if any(i['status'] == 'PENDING' for i in r['items']) else 'COMPLETED'))
            self._assert(ctx, current, reauthorize)
            return self._public(current)

    @contextmanager
    def _media_context(self, ctx, rid, guard):
        token = batch_media_context.set({'id': rid, 'actor': ctx.actor, 'novel_id': ctx.novel_id, 'scope': deepcopy(ctx.scope), 'guard': guard})
        try: yield
        finally: batch_media_context.reset(token)

    def dispatch(self, ctx, rid, body, reauthorize=lambda: None):
        value = VersionIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version); self._assert(ctx, row, reauthorize)
        if row['status'] not in {'READY', 'PARTIAL'} or not row['confirmed']: raise ValueError('BATCH_CONFIRM_BEFORE_EXECUTION')
        index = next((i for i, item in enumerate(row['items']) if item['status'] == 'PENDING'), None)
        if index is None: raise ValueError('BATCH_NO_PENDING_ITEM')
        claim = uuid4().hex
        with ACTIVE_LOCK: ACTIVE.add(claim)
        try:
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                current = state['collections'][self.BATCHES][rid]
                def start(r):
                    r.update(status='RUNNING'); r['items'][index].update(status='RUNNING', claim=claim, attempts=r['items'][index]['attempts'] + 1)
                change_row(current, ctx.actor, value.expected_version, start); self._assert(ctx, current, reauthorize)
            def guard():
                fresh = self._owned(ctx, rid)
                if fresh['status'] != 'RUNNING' or fresh['items'][index].get('claim') != claim or fresh['items'][index]['status'] != 'RUNNING': raise ValueError('BATCH_STOPPED')
                self._assert(ctx, fresh, reauthorize)
            step = row['snapshot']['steps'][index]; item = step['input']; guard()
            try:
                if item['kind'] == 'PROOF':
                    proof = self.reader.proof(ctx)
                    result = {'items': [finding for finding in proof['items'] if finding['chapter_id'] in item['chapter_ids'] and finding['offset'] >= item['start'] and (item['end'] is None or finding['offset'] + len(finding['quote']) <= item['end'])], 'method': proof['method'], 'automatic_edits': False}
                elif item['kind'] == 'EXPORT':
                    rows = {r['id']: r for r in self._rows(ctx)}
                    snapshot = {'novel_id': ctx.novel_id, 'source': {'novel': {'title': self.novels.get(ctx.novel_id)['title']}, 'chapters': [deepcopy(rows[cid]) for cid in item['chapter_ids']], 'screenplays': [], 'datasets': {}}}
                    guard(); result = self.novels.export_snapshot_result(snapshot, item['format'], progress_callback=lambda *_: guard())
                    raw = ExportJobService._result_bytes(result)
                    if len(raw) > MAX_RESULT: raise ValueError('BATCH_RESULT_LIMIT')
                else:
                    with self._media_context(ctx, rid, guard):
                        task = self.media.prepare_task(ctx.novel_id, ctx.scope, ctx.actor, {'brief_id': item['brief_id'], 'expected_brief_version': item['expected_brief_version'], 'adapter_id': item['adapter_id'], 'candidate_count': 1})
                        task['safe_batch_id'] = rid; task['safe_batch_index'] = index
                        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                            guard(); current = state['collections'][self.BATCHES][rid]
                            current['items'][index]['task_id'] = task['id']; state['collections'].setdefault(self.media.TASKS, {})[task['id']] = task
                        guard(); done = self.media.execute(ctx.novel_id, ctx.scope, ctx.actor, task['id'], task['version'], check_authority=guard, safe_batch_guard=lambda *_: guard())
                        proposals = [self.media.get(ctx.novel_id, ctx.scope, self.media.PROPOSALS, pid) for pid in done['proposal_ids']]
                        result = {'task_id': task['id'], 'proposals': [{k: p[k] for k in ('id', 'version', 'status', 'media', 'verification')} for p in proposals]}
                if len(canonical(result).encode()) > MAX_RESULT: raise ValueError("BATCH_RESULT_LIMIT")
                guard()
                with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                    guard(); current = state['collections'][self.BATCHES][rid]
                    if sum(len(canonical(i.get("result")).encode()) for i in current["items"]) + len(canonical(result).encode()) > 4 * 1024 * 1024:
                        raise ValueError("BATCH_TOTAL_RESULT_LIMIT")
                    def finish(r):
                        r['items'][index].update(status='COMPLETED', result=result, claim=None)
                        r['status'] = 'READY' if any(i['status'] == 'PENDING' for i in r['items']) else 'PARTIAL' if any(i['status'] == 'FAILED' for i in r['items']) else 'COMPLETED'
                    change_row(current, ctx.actor, current['version'], finish)
                    return self._public(current)
            except Exception:
                with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                    current = state['collections'][self.BATCHES][rid]
                    if current['status'] == 'RUNNING' and current['items'][index].get('claim') == claim:
                        def fail(r):
                            r['items'][index].update(status='FAILED', error_code='BATCH_DOMAIN_FAILED_RECHECK_BEFORE_RETRY', claim=None)
                            r['status'] = 'PARTIAL'
                        change_row(current, ctx.actor, current['version'], fail)
                raise
        finally:
            with ACTIVE_LOCK: ACTIVE.discard(claim)

    def stop(self, ctx, rid, body, reauthorize=lambda: None):
        value = VersionIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version)
        if row['status'] in {'COMPLETED', 'CANCELLED'}: raise ValueError('BATCH_ALREADY_TERMINAL')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.BATCHES][rid]
            def stop(r):
                r.update(status='CANCELLED', confirmed=False)
                for item in r['items']:
                    if item['status'] in {'PENDING', 'RUNNING'}: item.update(status='CANCELLED', claim=None)
            change_row(current, ctx.actor, value.expected_version, stop); reauthorize(); return self._public(current)

    def retry_failed(self, ctx, rid, body, reauthorize=lambda: None):
        value = VersionIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version); self._assert(ctx, row, reauthorize)
        if row['status'] != 'PARTIAL' or any(i['status'] == 'RUNNING' for i in row['items']) or not any(i['status'] == 'FAILED' for i in row['items']): raise ValueError('BATCH_ONLY_FAILED_RETRY_UNKNOWN_MUST_RECONCILE')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.BATCHES][rid]
            def reset(r):
                r.update(status='PREFLIGHT', confirmed=False)
                for item in r['items']:
                    if item['status'] == 'FAILED':
                        # Unknown paid/model outcomes are not supported by this
                        # zero-cost executor. An orphan RUNNING claim never enters.
                        item.update(status='PENDING', claim=None); item.pop('error_code', None)
            change_row(current, ctx.actor, value.expected_version, reset); self._assert(ctx, current, reauthorize)
            return self._public(current)

    def download(self, ctx, rid, index, reauthorize=lambda: None):
        row = self._owned(ctx, rid); self._assert(ctx, row, reauthorize)
        if not 0 <= index < len(row['items']): raise FileNotFoundError('item unavailable')
        step, item = row['snapshot']['steps'][index], row['items'][index]
        if step['input']['kind'] != 'EXPORT' or item['status'] not in {'COMPLETED', 'SKIPPED'}: raise ValueError('BATCH_RESULT_UNAVAILABLE')
        result = item['result']; raw = ExportJobService._result_bytes(result); reauthorize()
        return raw, step['input']['format'], ExportJobService.MEDIA_TYPES[step['input']['format']]

    def preview_media(self, ctx, rid, proposal_id, reauthorize=lambda: None):
        row = self._owned(ctx, rid); self._assert(ctx, row, reauthorize)
        if row['status'] == 'CANCELLED': raise FileNotFoundError('proposal unavailable')
        if not any(proposal_id == p['id'] for i in row['items'] for p in (i.get('result') or {}).get('proposals', [])): raise FileNotFoundError('proposal unavailable')
        with self._media_context(ctx, rid, lambda: self._assert(ctx, self._owned(ctx, rid), reauthorize)):
            raw, mime = self.media.preview(ctx.novel_id, ctx.scope, proposal_id); reauthorize(); return raw, mime

    def approve_media(self, ctx, rid, body, reauthorize=lambda: None):
        value = ReviewIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version)
        if not row['confirmed'] or row['status'] not in {'READY', 'PARTIAL', 'COMPLETED'} or value.snapshot_digest != row['snapshot_digest']:
            raise ValueError('BATCH_REVIEW_CONFIRMATION_CHANGED')
        index = next((i for i, item in enumerate(row['items']) if item['status'] == 'COMPLETED' and any(p['id'] == value.proposal_id for p in (item.get('result') or {}).get('proposals', []))), None)
        if index is None: raise FileNotFoundError('proposal unavailable')
        def guard():
            current = self._owned(ctx, rid)
            if current['status'] == 'CANCELLED' or not current['confirmed']: raise ValueError('BATCH_STOPPED')
            self._assert(ctx, current, reauthorize)
        guard()
        with self._media_context(ctx, rid, guard):
            candidate = self.media.get(ctx.novel_id, ctx.scope, self.media.PROPOSALS, value.proposal_id)
            if candidate['status'] == 'APPROVED':
                check_version(candidate, value.proposal_version)
                approved = candidate
            else:
                approved = self.media.review(ctx.novel_id, ctx.scope, ctx.actor, value.proposal_id, 'approve', value.proposal_version, safe_batch_guard=guard)
            guard()
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                current = state['collections'][self.BATCHES][rid]
                def update(r):
                    proposals = r['items'][index]['result']['proposals']
                    target = next(p for p in proposals if p['id'] == value.proposal_id)
                    target.update({k: approved[k] for k in ('version', 'status', 'asset_id')})
                change_row(current, ctx.actor, value.expected_version, update); guard()
                return self._public(current)
