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
from .common import DomainService, StaleSourceError, change_row, check_version, new_row, now
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
    kind: Literal['PROOF', 'EXPORT', 'SYNTHETIC_MEDIA', 'REGISTERED_MEDIA', 'VOICE_REDO']
    chapter_ids: list[str] = Field(default_factory=list, max_length=100)
    start: int = Field(default=0, ge=0, le=2_000_000)
    end: int | None = Field(default=None, ge=1, le=2_000_000)
    format: Literal['txt', 'markdown', 'docx', 'epub', 'pdf'] = 'txt'
    brief_id: str | None = Field(default=None, max_length=240)
    expected_brief_version: int | None = Field(default=None, ge=1)
    adapter_id: str = Field(default='mock-image-v1', max_length=240)

    voice_job_id: str | None = Field(default=None, max_length=240)
    expected_voice_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    broker_preview_id: str | None = Field(default=None, max_length=240)
    expected_broker_version: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def valid_selection(self):
        if len(set(self.chapter_ids)) != len(self.chapter_ids): raise ValueError('BATCH_DUPLICATE_CHAPTER')
        if self.kind not in {'SYNTHETIC_MEDIA', 'REGISTERED_MEDIA', 'VOICE_REDO'} and not self.chapter_ids: raise ValueError('BATCH_CHAPTER_SELECTION_REQUIRED')
        if self.kind in {'SYNTHETIC_MEDIA', 'REGISTERED_MEDIA'} and (not self.brief_id or self.expected_brief_version is None): raise ValueError('BATCH_BRIEF_REQUIRED')
        if self.kind in {'REGISTERED_MEDIA', 'VOICE_REDO'} and (not self.broker_preview_id or self.expected_broker_version is None): raise ValueError('BATCH_ORIGINAL_BROKER_PREVIEW_REQUIRED')
        if self.kind == 'VOICE_REDO' and (not self.voice_job_id or not self.expected_voice_digest): raise ValueError('BATCH_ORIGINAL_APPROVED_VOICE_JOB_REQUIRED')
        if (self.start or self.end is not None) and (self.kind != 'PROOF' or len(self.chapter_ids) != 1): raise ValueError('BATCH_RANGE_REQUIRES_ONE_PROOF_CHAPTER')
        if self.end is not None and self.end <= self.start: raise ValueError('BATCH_RANGE_INVALID')
        return self


class BatchIn(StrictModel):
    items: list[BatchItemIn] = Field(min_length=1, max_length=20)
    concurrency: Literal[1] = 1
    budget_microusd: Literal[0] = 0
    skip_satisfied: bool = True
    preset_id: str | None = Field(default=None, max_length=240)
    expected_preset_version: int | None = Field(default=None, ge=1)


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1)


class ConfirmIn(VersionIn):
    snapshot_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    budget_microusd: Literal[0] = 0
    confirmed: Literal[True]


class ReviewIn(ConfirmIn):
    proposal_id: str = Field(min_length=1, max_length=240)
    proposal_version: int = Field(ge=1)


class VoiceReviewIn(ConfirmIn):
    item_index: int = Field(ge=0, le=19)
    expected_asset_version: int = Field(ge=1)


class SafeBatchesService(DomainService):
    BATCHES = 'safe_batches_v2'

    def __init__(self, store, novels, chapters, *, sources, reader, media, broker=None, templates=None, voice=None, flag_check=None):
        super().__init__(store, novels, chapters)
        self.sources, self.reader, self.media, self.broker, self.templates = sources, reader, media, broker, templates
        self.voice = voice
        if flag_check is None:
            from .flags import require_flag
            flag_check = require_flag
        self.flag_check = flag_check

    def _rows(self, ctx):
        rows = authorized_chapter_rows(ctx, self.sources, self.chapters)
        if len(rows) > 200 or sum(len(chapter_text(r)) for r in rows) > 2_000_000: raise ValueError('BATCH_SOURCE_LIMIT')
        return [{**r, "batch_source_privacy": source_privacy_status(r, ctx.scope.get("branch_id"), self.store.root)} for r in rows]

    def _brief(self, ctx, rid, rows, current=True):
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
        if current: self.media._assert_brief(ctx.novel_id, ctx.scope, brief)
        if current and brief.get('kind') == 'STORYBOARD':
            screenplay, shot = self.media._shot(ctx.novel_id, ctx.scope, brief['screenplay_id'], brief['shot_id'])
            if any(r.get('hidden') or r.get('secret') for r in (screenplay, shot)): raise FileNotFoundError('shot unavailable')
            if screenplay.get('shot_status') != 'APPROVED': raise ValueError('BATCH_APPROVED_SHOT_PLAN_REQUIRED')
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

    def _preset(self, ctx, value):
        if value.preset_id is None:
            if value.expected_preset_version is not None: raise ValueError('BATCH_PRESET_ID_REQUIRED')
            return None
        self.flag_check('template_library_v2')
        if self.templates is None: raise ValueError('BATCH_TEMPLATE_LIBRARY_AUTHORITY_REQUIRED')
        if value.expected_preset_version is None: raise ValueError('BATCH_PRESET_VERSION_REQUIRED')
        from .safe_batch_contracts import BatchPreset
        row = self.templates._owned(ctx, self.templates.INSTANCES, value.preset_id)
        check_version(row, value.expected_preset_version)
        if row['manifest']['type'] != 'safe_batch': raise ValueError('BATCH_PRESET_TYPE_REQUIRED')
        preset = BatchPreset.model_validate(row['content'])
        proof = any(i.kind == 'PROOF' for i in value.items)
        exports = [i for i in value.items if i.kind == 'EXPORT']
        if proof != preset.proof or bool(exports) != bool(preset.export_format) or any(i.format != preset.export_format for i in exports) or value.skip_satisfied != preset.skip_satisfied:
            raise ValueError('BATCH_PRESET_PARAMETERS_CHANGED')
        return {'id': row['id'], 'version': row['version'], 'package_id': row['package_id'], 'package_version': row['package_version'], 'content': preset.model_dump()}

    def _media_admission(self, ctx, item, voice=None):
        self.flag_check('model_broker_v2')
        if self.broker is None: raise ValueError('BATCH_ORIGINAL_BROKER_AUTHORITY_REQUIRED')
        decision = self.broker.get(ctx.novel_id, ctx.scope, self.broker.DECISIONS, item.broker_preview_id)
        if decision['created_by'] != ctx.actor: raise FileNotFoundError('broker preview unavailable')
        check_version(decision, item.expected_broker_version)
        route = self.broker._assert_preview(ctx.novel_id, ctx.scope, ctx.actor, decision)
        chosen = decision['chosen']
        if voice:
            if route.get('audio_provider_id') != voice['provider_id'] or route['model_id'] != voice['model_id'] or route['capability'] != 'AUDIO' or route['cloud']: raise ValueError('BATCH_EXACT_LOCAL_AUDIO_BROKER_ROUTE_REQUIRED')
        elif route.get('adapter_id') != item.adapter_id or route['capability'] != 'IMAGE' or route['cloud']:
            raise ValueError('BATCH_LOCAL_IMAGE_BROKER_ROUTE_REQUIRED')
        current_price = self.broker._price(route, self.store.read(ctx.novel_id, ctx.scope)['collections'].get(self.broker.PRICES, {}))
        if current_price != chosen.get('price'): raise StaleSourceError('BATCH_BROKER_PRICE_CHANGED')
        if not current_price or current_price.get('reserve_microusd') != 0:
            raise ValueError('BATCH_KNOWN_ZERO_ESTIMATE_REQUIRED')
        if decision['request'].get('max_cost_microusd') != 0 or decision['request'].get('profile') != 'LOCAL_ONLY':
            raise ValueError('BATCH_EXACT_ZERO_LOCAL_BROKER_APPROVAL_REQUIRED')
        if decision['budget_version'] != self.broker.budget(ctx.novel_id, ctx.scope)['version']:
            raise StaleSourceError('BATCH_BROKER_BUDGET_CHANGED')
        return {'preview_id': decision['id'], 'version': decision['version'], 'source_ids': list(decision['sources']),
                'route_id': route['route_id'], 'fingerprint': route['fingerprint'], 'binding_hash': route['binding_hash'],
                'price': deepcopy(current_price), 'cost_state': 'KNOWN_SYNTHETIC_ZERO' if route['synthetic'] else 'ZERO_ESTIMATE_NOT_INVOICE'}

    @staticmethod
    def _receipt(item, **values):
        receipts = item.setdefault('receipts', [])
        if not receipts or receipts[-1]['attempt'] != item['attempts']:
            receipts.append({'attempt': item['attempts'], 'at': now(), 'status': 'CLAIMED'})
        event = {k: deepcopy(v) for k, v in values.items() if k in {'status', 'cost_state', 'actual_microusd', 'task_id', 'reservation_id', 'reconciliation'} and receipts[-1].get(k) != v}
        if event: receipts[-1].setdefault('events', []).append({'at': now(), **event})
        receipts[-1].update(values)

    def _media_result(self, ctx, task):
        if task['status'] != 'SUCCEEDED': raise ValueError('BATCH_ORIGINAL_TASK_NOT_SUCCESSFUL')
        proposals = [self.media.get(ctx.novel_id, ctx.scope, self.media.PROPOSALS, pid) for pid in task['proposal_ids']]
        return {'task_id': task['id'], 'proposals': [{k: p[k] for k in ('id', 'version', 'status', 'media', 'verification', 'asset_id') if k in p} for p in proposals]}

    def _snapshot(self, ctx, value, batch_id=None):
        self.flag_check(FEATURE)
        rows = {r['id']: r for r in self._rows(ctx)}; steps = []
        for item in value.items:
            if set(item.chapter_ids) - set(rows): raise FileNotFoundError('source unavailable')
            source_ids = item.chapter_ids; media_snapshot = None; resources = []
            if item.kind in {'SYNTHETIC_MEDIA', 'REGISTERED_MEDIA'}:
                self.flag_check('cover_storyboard_generation'); self.flag_check('media_adapter_registry')
                brief = self._brief(ctx, item.brief_id, rows)
                operation = 'cover_generation' if brief['kind'] == 'COVER' else 'storyboard_card_generation'
                adapter = self.media.registry.resolve(item.adapter_id, operation)
                # A declaration of local/mock is not a sandbox. Only the exact
                # registered host-owned deterministic implementation is allowed.
                if item.kind == 'SYNTHETIC_MEDIA' and type(adapter) is not MockImageWorkflowAdapter: raise ValueError('BATCH_REAL_MEDIA_REQUIRES_ORIGINAL_BROKER_AND_WORKFLOW_ADMISSION')
                admission = self._media_admission(ctx, item) if item.kind == 'REGISTERED_MEDIA' else None
                prepared = self.media.prepare_task(ctx.novel_id, ctx.scope, ctx.actor, {'brief_id': item.brief_id, 'expected_brief_version': item.expected_brief_version, 'adapter_id': item.adapter_id, 'candidate_count': 1})
                media_snapshot = {k: prepared[k] for k in ('brief_version', 'brief_snapshot', 'source_digest', 'sources', 'operation', 'adapter_definition')}
                if 'queued_environment' in prepared: media_snapshot['queued_environment'] = prepared['queued_environment']
                if admission:
                    if set(admission['source_ids']) != set(brief.get('sources', {})): raise ValueError('BATCH_BROKER_SOURCE_SELECTION_MISMATCH')
                    media_snapshot['broker_admission'] = admission
                    resources = [{'kind': 'ORIGINAL_REGISTERED_LOCAL_RUNTIME', 'gpu_vram': 'UNKNOWN', 'external_occupancy': 'WARNING_NOT_CONTROLLED'}]
                source_ids = list(brief.get('sources', {}))
            if item.kind == 'VOICE_REDO':
                self.flag_check('voice_direction_v2'); self.flag_check('audiobook_v2')
                if self.voice is None: raise ValueError('BATCH_ORIGINAL_VOICE_AUTHORITY_REQUIRED')
                media_snapshot = self.voice.snapshot(ctx, item, batch_id)
                if not batch_id:
                    original_job = self.voice.job(ctx, item.voice_job_id)
                    if original_job['status'] == 'SUCCEEDED' and (not value.skip_satisfied or original_job['approval_status'] != 'APPROVED'): raise ValueError('BATCH_VOICE_EXISTING_RESULT_REVIEW_OR_SKIP_REQUIRED')
                admission = self._media_admission(ctx, item, media_snapshot)
                source_ids = [media_snapshot['chapter_id']]
                if set(admission['source_ids']) != set(source_ids): raise ValueError('BATCH_BROKER_SOURCE_SELECTION_MISMATCH')
                media_snapshot['broker_admission'] = admission
                resources = [{'kind': 'ORIGINAL_LOCAL_TTS_EXECUTOR', 'gpu_vram': 'UNKNOWN', 'external_occupancy': 'WARNING_NOT_CONTROLLED'}]
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
            if set(source_ids) - set(rows): raise FileNotFoundError('source unavailable')
            config = self.reader.settings(ctx) if item.kind == 'PROOF' else {'format': item.format} if item.kind == 'EXPORT' else media_snapshot
            frozen = {'input': item.model_dump(), 'sources': {cid: digest(rows[cid]) for cid in source_ids}, 'source_versions': {cid: rows[cid]['version'] for cid in source_ids}, 'configuration': config,
                'resource_requirements': resources or [{'kind': 'CPU_LOCAL', 'gpu_vram': 'NOT_REQUESTED'}], 'known_cost_microusd': 0,
                'permission': 'domain.write', 'network': item.kind in {'REGISTERED_MEDIA', 'VOICE_REDO'}, 'model': 'SYNTHETIC_FIXTURE' if item.kind == 'SYNTHETIC_MEDIA' else 'REGISTERED_ADAPTER_UNVERIFIED_QUALITY' if item.kind == 'REGISTERED_MEDIA' else 'ORIGINAL_TTS_ADAPTER_UNVERIFIED_QUALITY' if item.kind == 'VOICE_REDO' else 'NONE'}
            steps.append({**frozen, 'fingerprint': digest(frozen)})
        identities = []
        for step in steps:
            item = step['input']
            if item['kind'] == 'VOICE_REDO': key = ['VOICE', item['voice_job_id']]
            elif item['kind'] in {'SYNTHETIC_MEDIA', 'REGISTERED_MEDIA'}: key = ['MEDIA', item['brief_id'], item['adapter_id']]
            elif item['kind'] == 'PROOF': key = ['PROOF', item['chapter_ids'], item['start'], item['end']]
            else: key = ['EXPORT', item['chapter_ids'], item['format']]
            identities.append(digest(key))
        if len(set(identities)) != len(identities): raise ValueError('BATCH_DUPLICATE_ITEM')
        meta = self.novels.get(ctx.novel_id)
        return {'steps': steps, 'project_digest': digest({k: meta.get(k) for k in ('title', 'privacy_level', 'privacy')}), 'budget': self._budget(ctx), 'concurrency': 1, 'budget_microusd': 0, 'preset': self._preset(ctx, value)}

    def _owned(self, ctx, rid):
        row = self.get(ctx.novel_id, ctx.scope, self.BATCHES, rid)
        if row['created_by'] != ctx.actor: raise FileNotFoundError('batch unavailable')
        # Any hidden/deleted source conceals the whole row, including counts.
        rows = {r['id']: r for r in self._rows(ctx)}
        for step in row['snapshot']['steps']:
            if set(step['sources']) - set(rows): raise FileNotFoundError('batch unavailable')
            if step['input']['kind'] in {'SYNTHETIC_MEDIA', 'REGISTERED_MEDIA'}:
                self.flag_check('cover_storyboard_generation'); self.flag_check('media_adapter_registry')
                self._brief(ctx, step['input']['brief_id'], rows, current=False)
            if step['input']['kind'] == 'VOICE_REDO':
                self.flag_check('voice_direction_v2'); self.flag_check('audiobook_v2')
                if self.voice is None: raise FileNotFoundError('voice authority unavailable')
                self.voice.job(ctx, step['input']['voice_job_id'], row['id'], current=False)
        return row

    def _assert(self, ctx, row, reauthorize):
        reauthorize(); fresh = self._snapshot(ctx, BatchIn.model_validate(row['input']), row['id'])
        if digest(fresh) != row['snapshot_digest']: raise StaleSourceError('BATCH_INPUT_CONFIGURATION_OR_BUDGET_CHANGED')
        reauthorize()

    def _public(self, row):
        result = {k: deepcopy(row[k]) for k in ('id', 'version', 'status', 'snapshot_digest', 'created_at', 'confirmed', 'error_code') if k in row}
        result['budget'] = deepcopy(row['snapshot']['budget']); result['concurrency'] = 1
        result['approvals'] = deepcopy(row.get('approvals', [])); result['preset'] = deepcopy(row['snapshot'].get('preset'))
        result['items'] = []
        for step, item in zip(row['snapshot']['steps'], row['items']):
            public = {k: deepcopy(v) for k, v in item.items() if k not in {'result', 'claim'}}
            public.update(kind=step['input']['kind'], chapter_ids=list(step['sources']), source_versions_digest=digest(step['sources']),
                source_versions=deepcopy(step['source_versions']), configuration_summary={'format': step['input']['format']} if step['input']['kind'] == 'EXPORT' else {'rules_version': step['configuration']['version'], 'start': step['input']['start'], 'end': step['input']['end']} if step['input']['kind'] == 'PROOF' else {'job_id': step['input']['voice_job_id'], 'broker_preview_id': step['input']['broker_preview_id']} if step['input']['kind'] == 'VOICE_REDO' else {'brief_id': step['input']['brief_id'], 'brief_version': step['input']['expected_brief_version'], 'adapter_id': step['input']['adapter_id'], 'candidate_count': 1},
                known_cost_microusd=0, cost_state=step['configuration'].get('broker_admission', {}).get('cost_state', 'KNOWN_ZERO_LOCAL'), resource_requirements=step['resource_requirements'], permission=step['permission'])
            if item['status'] == 'RUNNING' and item.get('claim') not in ACTIVE:
                public['status'] = 'UNKNOWN'; public['error_code'] = 'BATCH_INTERRUPTED_RECONCILIATION_REQUIRED_NO_REPLAY'
            if item.get('result'):
                payload = item['result']
                if payload.get('satisfied_asset_ids'): public['satisfied_asset_ids'] = deepcopy(payload['satisfied_asset_ids'])
                if step['input']['kind'] == 'PROOF': public['findings'] = payload['items']
                elif step['input']['kind'] == 'EXPORT': public['download_available'] = True; public['format'] = step['input']['format']
                elif step['input']['kind'] == 'VOICE_REDO': public['voice_result'] = deepcopy(payload)
                else: public['proposals'] = deepcopy(payload['proposals']); public['verification'] = 'SYNTHETIC_PROTOCOL_ONLY' if step['input']['kind'] == 'SYNTHETIC_MEDIA' else 'REGISTERED_ADAPTER_CONTRACT_ONLY'
            result['items'].append(public)
        if row['status'] != 'CANCELLED' and any(r['status'] == 'UNKNOWN' for r in result['items']): result['status'] = 'UNKNOWN'
        result['limitations'] = ['EXPLICIT_ONE_STAGE_PER_REQUEST', 'NO_CLOUD_OR_POSITIVE_COST_ADMISSION', 'MEDIA_REQUIRES_SEPARATE_REVIEW', 'UNKNOWN_RESULT_MUST_RECONCILE_IN_ORIGINAL_EXECUTOR']
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
        broker_previews, presets, voice_jobs = [], [], []
        try:
            self.flag_check('model_broker_v2')
            if self.broker:
                for row in self.broker.decisions(ctx.novel_id, ctx.scope, ctx.actor):
                    chosen = row.get('chosen') or {}
                    if chosen.get('capability') not in {'IMAGE', 'AUDIO'} or chosen.get('cloud') or set(row.get('sources', {})) - set(rows): continue
                    item = BatchItemIn(kind='REGISTERED_MEDIA', brief_id='catalog-only', expected_brief_version=1, adapter_id=chosen.get('adapter_id', 'audio'), broker_preview_id=row['id'], expected_broker_version=row['version'])
                    try: admission = self._media_admission(ctx, item, {'provider_id': chosen['audio_provider_id'], 'model_id': chosen['model_id']} if chosen.get('capability') == 'AUDIO' else None)
                    except (FileNotFoundError, ValueError): continue
                    broker_previews.append({'id': row['id'], 'version': row['version'], 'adapter_id': chosen.get('adapter_id'), 'audio_provider_id': chosen.get('audio_provider_id'), 'model_id': chosen['model_id'], 'capability': chosen['capability'], 'source_ids': admission['source_ids'], 'cost_state': admission['cost_state']})
        except HTTPException as exc:
            if exc.status_code != 404: raise
        try:
            self.flag_check('template_library_v2')
            if self.templates:
                presets = [{'id': r['id'], 'version': r['version'], 'title': r['manifest']['title'], 'content': r['content']} for r in self.templates.instances(ctx)['items'] if r['manifest']['type'] == 'safe_batch']
        except HTTPException as exc:
            if exc.status_code != 404: raise
        try:
            self.flag_check('voice_direction_v2'); self.flag_check('audiobook_v2')
            if self.voice: voice_jobs = [job for job in self.voice.catalog(ctx) if job['chapter_id'] in rows]
        except HTTPException as exc:
            if exc.status_code != 404: raise
        return {'chapters': [{'id': r['id'], 'title': r['title'], 'version': r['version']} for r in rows.values()], 'briefs': briefs, 'broker_previews': broker_previews, 'presets': presets, 'voice_jobs': voice_jobs,
            'formats': ['txt', 'markdown', 'docx', 'epub', 'pdf'], 'concurrency': 1, 'known_cost_microusd': 0,
            'unsupported': ['VOICE_REDO_REQUIRES_ORIGINAL_APPROVED_JOB_AND_AUDIO_BROKER_ZERO_ESTIMATE', 'REMOTE_MEDIA_REQUIRES_ORIGINAL_BROKER_EGRESS_ADMISSION', 'VIDEO_EXECUTOR_NOT_SUPPORTED_BY_ORIGINAL_BRIEF_MEDIA_SERVICE', 'NO_OWNED_GPU_RUNTIME_TELEMETRY_NO_GPU_SCHEDULING'],
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
            except HTTPException as exc:
                if exc.status_code != 404: raise
            public = self._public(row)
            try: self._assert(ctx, row, lambda: None); public['stale'] = False
            except (ValueError, FileNotFoundError, HTTPException) as exc:
                if isinstance(exc, HTTPException) and exc.status_code != 404: raise
                receipts = [{'index': i['index'], 'status': i['status'], 'attempts': i['attempts'], 'receipts': deepcopy(i.get('receipts', []))} for i in public['items']]
                public = {k: public[k] for k in ('id', 'version', 'status', 'snapshot_digest', 'created_at', 'approvals')}; public['stale'] = True; public['retained_receipts'] = receipts
            result.append(public)
        return {'items': result[-100:]}

    def preflight(self, ctx, body, reauthorize=lambda: None):
        value = BatchIn.model_validate(body); frozen = self._snapshot(ctx, value); reauthorize()
        completed = {}
        if value.skip_satisfied:
            for row in self.list(ctx.novel_id, ctx.scope, self.BATCHES):
                if row['created_by'] != ctx.actor: continue
                try: self._owned(ctx, row['id']); self._assert(ctx, row, reauthorize)
                except (FileNotFoundError, ValueError): continue
                except HTTPException as exc:
                    if exc.status_code == 404: continue
                    raise
                for step, item in zip(row['snapshot']['steps'], row['items']):
                    if item['status'] in {'COMPLETED', 'SKIPPED'} and item.get('result'):
                        if step['input']['kind'] in {'PROOF', 'EXPORT'}:
                            completed[step['fingerprint']] = item['result']
                        elif step['input']['kind'] in {'SYNTHETIC_MEDIA', 'REGISTERED_MEDIA'}:
                            try:
                                with self._media_context(ctx, row['id'], lambda: self._assert(ctx, row, reauthorize)):
                                    ids = list(item['result'].get('satisfied_asset_ids', []))
                                    for proposal in item['result'].get('proposals', []):
                                        current = self.media.get(ctx.novel_id, ctx.scope, self.media.PROPOSALS, proposal['id'])
                                        if current['status'] != 'APPROVED' or not current.get('asset_id'): raise ValueError('BATCH_MEDIA_NOT_SATISFIED')
                                        ids.append(current['asset_id'])
                                    if not ids: raise ValueError('BATCH_MEDIA_NOT_SATISFIED')
                                    for aid in ids:
                                        asset = self.media.assets.get(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
                                        if asset.get('novel_id') != ctx.novel_id or asset.get('branch_id') != ctx.scope.get('branch_id') or asset.get('hidden') or asset.get('secret'): raise FileNotFoundError('asset unavailable')
                                        self.media.assets.content(aid, branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
                                    completed[step['fingerprint']] = {'proposals': [], 'satisfied_asset_ids': ids, 'original_batch_id': row['id']}
                            except (FileNotFoundError, ValueError): pass
        if value.skip_satisfied and self.voice:
            for step in frozen['steps']:
                if step['input']['kind'] != 'VOICE_REDO': continue
                job = self.voice.job(ctx, step['input']['voice_job_id'])
                if job['status'] == 'SUCCEEDED' and job['approval_status'] == 'APPROVED': completed[step['fingerprint']] = self.voice.result(ctx, job)
        items = []
        for index, step in enumerate(frozen['steps']):
            result = completed.get(step['fingerprint']); items.append({'index': index, 'status': 'SKIPPED' if result else 'PENDING', 'attempts': 0, 'result': deepcopy(result), 'claim': None, 'receipts': []})
        row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'input': value.model_dump(), 'snapshot': frozen, 'snapshot_digest': digest(frozen), 'items': items, 'status': 'PREFLIGHT', 'confirmed': False})
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            self._assert(ctx, row, reauthorize); state['collections'].setdefault(self.BATCHES, {})[row['id']] = row
        return self._public(row)

    def confirm(self, ctx, rid, body, reauthorize=lambda: None):
        value = ConfirmIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version); self._assert(ctx, row, reauthorize)
        if row['status'] != 'PREFLIGHT' or value.snapshot_digest != row['snapshot_digest']: raise ValueError('BATCH_CONFIRMATION_CHANGED')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.BATCHES][rid]
            change_row(current, ctx.actor, value.expected_version, lambda r: (r.setdefault('approvals', []).append({'actor': ctx.actor, 'snapshot_digest': r['snapshot_digest'], 'budget_microusd': 0, 'approved_version': r['version'], 'at': now()}), r.update(confirmed=True, status='READY' if any(i['status'] == 'PENDING' for i in r['items']) else 'COMPLETED')))
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
                    self._receipt(r['items'][index], snapshot_digest=r['snapshot_digest'], approval_version=(r.get('approvals') or [{}])[-1].get('approved_version'), known_cost_microusd=0)
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
                elif item['kind'] == 'VOICE_REDO':
                    voice_item = BatchItemIn.model_validate(item)
                    reservation_key = f"batch:{rid}:{index}:{row['items'][index]['attempts'] + 1}"
                    reservation_id = digest([ctx.actor, reservation_key]); job_id = item['voice_job_id']
                    with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                        guard(); stage = state['collections'][self.BATCHES][rid]['items'][index]
                        stage.update(voice_job_id=job_id, reservation_id=reservation_id)
                        self._receipt(stage, task_id=job_id, reservation_id=reservation_id)
                    self.broker.reserve(ctx.novel_id, ctx.scope, ctx.actor, item['broker_preview_id'], item['expected_broker_version'], reservation_key, job_id, guard, authorization_digest=row['snapshot_digest'])
                    def voice_admission(job, provider_id, model_id, provider):
                        guard()
                        expected = step['configuration']['broker_admission']
                        current = self.broker.audio_identity(provider_id, model_id, provider)
                        if digest(current) != expected['fingerprint']: raise StaleSourceError('BATCH_VOICE_PROVIDER_CHANGED')
                        self.broker.guard_dispatch(ctx.novel_id, ctx.scope, ctx.actor, reservation_id, job_id, guard)
                    try:
                        done = self.voice.dispatch(ctx, rid, index, voice_item, guard, voice_admission)
                        result = self.voice.result(ctx, done)
                        self.broker.finalize(ctx.novel_id, ctx.scope, ctx.actor, reservation_id, job_id, 'COMPLETED')
                    except Exception:
                        self.broker.finalize(ctx.novel_id, ctx.scope, ctx.actor, reservation_id, job_id, 'UNKNOWN')
                        raise
                else:
                    with self._media_context(ctx, rid, guard):
                        task = self.media.prepare_task(ctx.novel_id, ctx.scope, ctx.actor, {'brief_id': item['brief_id'], 'expected_brief_version': item['expected_brief_version'], 'adapter_id': item['adapter_id'], 'candidate_count': 1})
                        task['safe_batch_id'] = rid; task['safe_batch_index'] = index
                        reservation_key = f"batch:{rid}:{index}:{row['items'][index]['attempts'] + 1}"
                        reservation_id = digest([ctx.actor, reservation_key]) if item['kind'] == 'REGISTERED_MEDIA' else None
                        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                            guard(); current = state['collections'][self.BATCHES][rid]
                            current['items'][index].update(task_id=task['id'], reservation_id=reservation_id)
                            self._receipt(current['items'][index], task_id=task['id'], reservation_id=reservation_id)
                            state['collections'].setdefault(self.media.TASKS, {})[task['id']] = task
                        if reservation_id:
                            self.broker.reserve(ctx.novel_id, ctx.scope, ctx.actor, item['broker_preview_id'], item['expected_broker_version'], reservation_key, task['id'], guard, authorization_digest=row['snapshot_digest'])
                        admitted = False
                        def admission(*_):
                            nonlocal admitted
                            guard()
                            if reservation_id and not admitted:
                                self.broker.guard_dispatch(ctx.novel_id, ctx.scope, ctx.actor, reservation_id, task['id'], guard)
                                admitted = True
                        try:
                            guard(); done = self.media.execute(ctx.novel_id, ctx.scope, ctx.actor, task['id'], task['version'], check_authority=guard, safe_batch_guard=admission)
                            result = self._media_result(ctx, done)
                            if reservation_id: self.broker.finalize(ctx.novel_id, ctx.scope, ctx.actor, reservation_id, task['id'], 'COMPLETED')
                        except Exception:
                            if reservation_id:
                                self.broker.finalize(ctx.novel_id, ctx.scope, ctx.actor, reservation_id, task['id'], 'UNKNOWN')
                            raise
                if len(canonical(result).encode()) > MAX_RESULT: raise ValueError("BATCH_RESULT_LIMIT")
                guard()
                with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                    guard(); current = state['collections'][self.BATCHES][rid]
                    if sum(len(canonical(i.get("result")).encode()) for i in current["items"]) + len(canonical(result).encode()) > 4 * 1024 * 1024:
                        raise ValueError("BATCH_TOTAL_RESULT_LIMIT")
                    def finish(r):
                        r['items'][index].update(status='COMPLETED', result=result, claim=None)
                        self._receipt(r['items'][index], status='COMPLETED', result_digest=digest(result))
                        if r['items'][index].get('reservation_id'):
                            ledger = state['collections'][self.broker.LEDGER][r['items'][index]['reservation_id']]
                            self._receipt(r['items'][index], cost_state=ledger['cost_state'], actual_microusd=ledger['actual_microusd'])
                            if ledger['status'] == 'UNKNOWN_UPSTREAM': r['items'][index].update(status='UNKNOWN', error_code='BATCH_ORIGINAL_COST_RECONCILIATION_REQUIRED')
                        r['status'] = 'UNKNOWN' if any(i['status'] == 'UNKNOWN' for i in r['items']) else 'READY' if any(i['status'] == 'PENDING' for i in r['items']) else 'PARTIAL' if any(i['status'] == 'FAILED' for i in r['items']) else 'COMPLETED'
                    change_row(current, ctx.actor, current['version'], finish)
                    return self._public(current)
            except Exception:
                with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                    current = state['collections'][self.BATCHES][rid]
                    stage = current['items'][index]
                    original = state['collections'].get(self.media.TASKS, {}).get(stage.get('task_id'), {})
                    ledger = state['collections'].get(self.broker.LEDGER, {}).get(stage.get('reservation_id'), {}) if self.broker else {}
                    unknown = original.get('status') in {'RUNNING', 'SUCCEEDED'} or ledger.get('status') in {'DISPATCHED', 'UNKNOWN_UPSTREAM'}
                    self._receipt(stage, status='UNKNOWN' if unknown else 'FAILED', original_task_status=original.get('status'), cost_state=ledger.get('cost_state', 'KNOWN_ZERO_LOCAL'))
                    if current['status'] == 'RUNNING' and stage.get('claim') == claim:
                        def fail(r):
                            r['items'][index].update(status='UNKNOWN' if unknown else 'FAILED', error_code='BATCH_ORIGINAL_RECEIPT_RECONCILIATION_REQUIRED' if unknown else 'BATCH_DOMAIN_FAILED_RECHECK_BEFORE_RETRY', claim=None)
                            r['status'] = 'UNKNOWN' if unknown else 'PARTIAL'
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
        if row['status'] != 'PARTIAL' or any(i['status'] in {'RUNNING', 'UNKNOWN'} for i in row['items']) or not any(i['status'] == 'FAILED' for i in row['items']): raise ValueError('BATCH_ONLY_FAILED_RETRY_UNKNOWN_MUST_RECONCILE')
        for step, item in zip(row['snapshot']['steps'], row['items']):
            if item['status'] == 'FAILED' and step['input']['kind'] == 'VOICE_REDO': self.voice.retry(ctx, rid, step['input'])
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.BATCHES][rid]
            def reset(r):
                r.update(status='PREFLIGHT', confirmed=False)
                for item in r['items']:
                    if item['status'] == 'FAILED':
                        # The prior attempt and original approval remain in receipts.
                        # Unknown outcomes cannot enter this failed-only branch.
                        item.update(status='PENDING', claim=None); item.pop('error_code', None); item.pop('task_id', None); item.pop('reservation_id', None)
            change_row(current, ctx.actor, value.expected_version, reset); self._assert(ctx, current, reauthorize)
            return self._public(current)

    def reconcile(self, ctx, rid, body, reauthorize=lambda: None):
        value = VersionIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version)
        self._assert(ctx, row, reauthorize)
        changed = []
        with self._media_context(ctx, rid, lambda: self._assert(ctx, row, reauthorize)):
            for index, item in enumerate(row['items']):
                if item['status'] not in {'RUNNING', 'UNKNOWN'}: continue
                if item.get('claim') in ACTIVE: raise ValueError('BATCH_ORIGINAL_EXECUTOR_STILL_ACTIVE')
                if item.get('voice_job_id'):
                    task = self.voice.job(ctx, item['voice_job_id'], rid)
                elif item.get('task_id'):
                    task = self.media.get(ctx.novel_id, ctx.scope, self.media.TASKS, item['task_id'])
                else: continue
                if not item.get('voice_job_id') and (task.get('safe_batch_id') != rid or task.get('safe_batch_index') != index): raise ValueError('BATCH_ORIGINAL_TASK_BINDING_CHANGED')
                ledger = None
                if item.get('reservation_id'):
                    self.flag_check('model_broker_v2')
                    ledger = self.broker.get(ctx.novel_id, ctx.scope, self.broker.LEDGER, item['reservation_id'])
                    if ledger['created_by'] != ctx.actor or ledger['job_id'] != task['id'] or ledger.get('authorization_digest') != row['snapshot_digest']:
                        raise ValueError('BATCH_ORIGINAL_RESERVATION_BINDING_CHANGED')
                    if ledger['status'] not in {'SETTLED', 'RELEASED', 'RECONCILED'}: continue
                    if ledger.get('actual_microusd') != 0 or ledger.get('overrun'): raise ValueError('BATCH_ZERO_BUDGET_OVERRUN_REVIEW_REQUIRED')
                if task['status'] == 'SUCCEEDED': changed.append((index, 'COMPLETED', self.voice.result(ctx, task) if item.get('voice_job_id') else self._media_result(ctx, task), ledger))
                elif task['status'] in {'FAILED', 'CANCELLED'}: changed.append((index, 'FAILED', None, ledger))
                elif task['status'] == 'QUEUED' and ledger and ledger['status'] == 'RECONCILED' and not ledger['dispatched'] and ledger.get('original_executor_stopped_confirmed'):
                    # Original manual recovery proves this admitted request was
                    # not sent and its executor is stopped; a new retry still
                    # requires a fresh explicit batch confirmation.
                    changed.append((index, 'FAILED', None, ledger))
        if not changed: raise ValueError('BATCH_NO_TERMINAL_ORIGINAL_RECEIPT_RECONCILE_ORIGINAL_EXECUTOR_FIRST')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.BATCHES][rid]
            def update(r):
                for index, status, result, ledger in changed:
                    item = r['items'][index]
                    item.update(status=status, result=result, claim=None)
                    item.pop('error_code', None)
                    self._receipt(item, status=status, reconciled_at=now(), reconciliation='ORIGINAL_EXECUTOR_RECEIPT', cost_state=ledger['cost_state'] if ledger else 'KNOWN_ZERO_LOCAL')
                r['status'] = 'CANCELLED' if r['status'] == 'CANCELLED' else 'UNKNOWN' if any(i['status'] in {'RUNNING', 'UNKNOWN'} for i in r['items']) else 'READY' if any(i['status'] == 'PENDING' for i in r['items']) else 'PARTIAL' if any(i['status'] == 'FAILED' for i in r['items']) else 'COMPLETED'
            change_row(current, ctx.actor, value.expected_version, update); self._assert(ctx, current, reauthorize)
            return self._public(current)

    def download(self, ctx, rid, index, reauthorize=lambda: None):
        row = self._owned(ctx, rid); self._assert(ctx, row, reauthorize)
        if not 0 <= index < len(row['items']): raise FileNotFoundError('item unavailable')
        step, item = row['snapshot']['steps'][index], row['items'][index]
        if step['input']['kind'] != 'EXPORT' or item['status'] not in {'COMPLETED', 'SKIPPED'}: raise ValueError('BATCH_RESULT_UNAVAILABLE')
        result = item['result']; raw = ExportJobService._result_bytes(result); reauthorize()
        return raw, step['input']['format'], ExportJobService.MEDIA_TYPES[step['input']['format']]

    def preview_voice(self, ctx, rid, index, reauthorize=lambda: None):
        row = self._owned(ctx, rid); self._assert(ctx, row, reauthorize)
        if row['status'] == 'CANCELLED' or not 0 <= index < len(row['items']): raise FileNotFoundError('voice result unavailable')
        step, item = row['snapshot']['steps'][index], row['items'][index]
        if step['input']['kind'] != 'VOICE_REDO' or not item.get('result'): raise FileNotFoundError('voice result unavailable')
        job = self.voice.job(ctx, step['input']['voice_job_id'], rid)
        result = self.voice.result(ctx, job)
        raw = self.voice.voice.assets.content(result['asset_id'], branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
        reauthorize(); return raw, result['media_type']

    def approve_voice(self, ctx, rid, body, reauthorize=lambda: None):
        value = VoiceReviewIn.model_validate(body); row = self._owned(ctx, rid); check_version(row, value.expected_version)
        if not row['confirmed'] or row['status'] not in {'READY', 'PARTIAL', 'COMPLETED'} or value.snapshot_digest != row['snapshot_digest']: raise ValueError('BATCH_REVIEW_CONFIRMATION_CHANGED')
        if not 0 <= value.item_index < len(row['items']): raise FileNotFoundError('voice result unavailable')
        step, item = row['snapshot']['steps'][value.item_index], row['items'][value.item_index]
        if step['input']['kind'] != 'VOICE_REDO' or item['status'] != 'COMPLETED': raise FileNotFoundError('voice result unavailable')
        def guard():
            current = self._owned(ctx, rid)
            if current['status'] == 'CANCELLED' or not current['confirmed']: raise ValueError('BATCH_STOPPED')
            self._assert(ctx, current, reauthorize)
        guard(); result = self.voice.approve(ctx, rid, step['input']['voice_job_id'], value.expected_asset_version, guard)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            current = state['collections'][self.BATCHES][rid]
            change_row(current, ctx.actor, value.expected_version, lambda r: r['items'][value.item_index].update(result=result)); guard()
            return self._public(current)

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
