"""Processing adapters owned by SubtitleTimelineService, never a plugin runtime.

The host may inject an already trusted local implementation. HTTP accepts only
adapter IDs, never URLs, model paths, shell arguments, packages or executable
code. No implementations are configured by default. Synthetic fixtures belong
in tests and cannot establish ASR, alignment or rendering quality.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import asdict, dataclass
import hashlib
from typing import Callable, Literal, Protocol
from uuid import uuid4

from pydantic import Field, model_validator
from starlette.exceptions import HTTPException
from ..services.v1_capability_service import CapabilityVersionConflict

from .common import StaleSourceError, change_row, check_version, new_row
from .flags import require_flag
from .media import StrictModel, digest
from ..media_files import inspect_media

OPERATIONS = ('ASR', 'FORCED_ALIGNMENT', 'BURN_IN')
FLAGS = ('subtitle_timeline_v2', 'voice_direction_v2', 'audiobook_v2')
MAX_MEDIA_BYTES = 8 * 1024 * 1024
MAX_SCOPE_RENDER_BYTES = 32 * 1024 * 1024
MAX_TASKS = 200
MAX_ATTEMPTS = 50


class ProcessingCreateIn(StrictModel):
    caption_id: str = Field(min_length=1, max_length=240)
    expected_caption_version: int = Field(ge=1, strict=True)
    adapter_id: str = Field(min_length=1, max_length=160)
    operation: Literal['ASR', 'FORCED_ALIGNMENT', 'BURN_IN']
    transcript: str = Field(default='', max_length=100000)

    @model_validator(mode='after')
    def shape(self):
        if self.operation == 'FORCED_ALIGNMENT' and not self.transcript.strip():
            raise ValueError('PROCESSING_TRANSCRIPT_REQUIRED')
        if self.operation != 'FORCED_ALIGNMENT' and self.transcript:
            raise ValueError('PROCESSING_TRANSCRIPT_NOT_APPLICABLE')
        return self


class ProcessingActionIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    preview_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


@dataclass(frozen=True)
class ProcessingDefinition:
    adapter_id: str
    version: str
    operations: tuple[str, ...]
    local: bool = True
    verification: str = 'CONTRACT_VERIFIED'
    model_verification: str = 'NOT_RUN'


@dataclass(frozen=True)
class ProcessingRequest:
    request_id: str
    operation: str
    media: bytes
    media_type: str
    caption: dict
    transcript: str
    source_digest: str
    guard: Callable[[], None]


@dataclass(frozen=True)
class ProcessingResult:
    cues: tuple[dict, ...] = ()
    content: bytes = b''
    media_type: str = ''


class SubtitleProcessingAdapter(Protocol):
    definition: ProcessingDefinition
    def process(self, request: ProcessingRequest) -> ProcessingResult: ...


class ProcessingFenceError(ValueError):
    """Fixed host-generated error; never populated from provider text."""


class ProcessingResultError(ValueError):
    """Fixed result-validation code; no transcript or provider details."""


class SubtitleProcessingMixin:
    """Task and review state is stored atomically alongside the caption owner."""
    PROCESSING = 'subtitle_processing_tasks'

    def _initialize_processing(self, adapters):
        self._processing_boot = uuid4().hex
        self._processing_adapters = {}
        for adapter in adapters:
            definition = adapter.definition
            if (not isinstance(definition, ProcessingDefinition) or definition.local is not True
                or definition.verification not in {'CONTRACT_VERIFIED', 'MOCK_ONLY'}
                or definition.model_verification != 'NOT_RUN'
                or not definition.adapter_id or len(definition.adapter_id) > 160
                or not definition.version or not definition.operations
                or set(definition.operations) - set(OPERATIONS)
                or definition.adapter_id in self._processing_adapters
                or not callable(getattr(adapter, 'process', None))):
                raise ValueError('PROCESSING_TRUSTED_LOCAL_ADAPTER_REQUIRED')
            self._processing_adapters[definition.adapter_id] = adapter

    @staticmethod
    def _processing_flags():
        for flag in FLAGS: require_flag(flag)

    @staticmethod
    def _processing_ready(adapter, operation):
        # ASR/alignment models need the existing model admission coordinator.
        # The current in-process seam executes synthetic fixtures only.
        return bool(adapter and operation in adapter.definition.operations and
                    (adapter.definition.verification == 'MOCK_ONLY' or operation == 'BURN_IN'))

    def processing_catalog(self):
        self._processing_flags()
        configured = [asdict(a.definition) for a in self._processing_adapters.values()]
        return {'schema': 'ai-novel-subtitle-processing/1', 'owner': 'subtitle_timeline_v2',
            'operations': [{'operation': operation, 'status': ('CONTRACT_VERIFIED' if operation == 'BURN_IN' and any(operation in a['operations'] and a['verification'] == 'CONTRACT_VERIFIED' for a in configured) else 'MOCK_ONLY') if any(self._processing_ready(a, operation) for a in self._processing_adapters.values()) else 'NOT_CONFIGURED',
                            'runtime_verification': 'NOT_RUN'} for operation in OPERATIONS],
            'adapters': configured, 'input_schema': ProcessingCreateIn.model_json_schema(),
            'model_runtime_admission': 'NOT_CONFIGURED_ORIGINAL_MEDIA_RUNTIME_REQUIRED',
            'synthetic_execution': 'TRUSTED_HOST_FIXTURES_ONLY_NOT_A_MODEL_RUNTIME',
            'third_party_execution': 'DENY_ALL', 'privacy': 'LOCAL_ONLY',
            'max_media_bytes': MAX_MEDIA_BYTES, 'max_scope_render_bytes': MAX_SCOPE_RENDER_BYTES,
            'max_tasks_per_scope': MAX_TASKS, 'max_attempts_per_task': MAX_ATTEMPTS, 'timing': 'VALIDATED_CUE_TICKS_NOT_PHONEME_OR_LIP_SYNC',
            'cancel': 'COOPERATIVE_AND_LATE_OUTPUT_DISCARD', 'recovery': 'EXPLICIT_RECOVER_THEN_RESUME_NO_AUTOMATIC_REPLAY',
            'surface': {'workspace': 'Production', 'page': 'subtitle_timeline_v2',
                'states': ['LOADING', 'EMPTY', 'ERROR', 'UNAUTHORIZED', 'NOT_CONFIGURED', 'DISABLED', 'CONFLICT', 'REVIEW', 'RECOVERY'],
                'actions': ['queue', 'execute', 'cancel', 'recover', 'resume', 'approve', 'reject', 'download'],
                'permissions': {'read': 'domain.read', 'write': 'domain.write', 'review': 'domain.review'},
                'feature_flags': list(FLAGS)}}

    @staticmethod
    def _processing_change(row, actor, version, callback):
        change_row(row, actor, version, callback)
        previous = row['history'][-1]
        # Immutable transcript/source and large output bytes need no duplicate
        # storage for every claim transition. Keep exact digest audit receipts;
        # adopted caption text has its own original caption revision history.
        transcript = previous.pop('transcript', None)
        if transcript is not None: previous['transcript_digest'] = digest(transcript)
        result = previous.pop('result', None)
        if result is not None: previous['result_digest'] = digest(result)
        previous.pop('claim', None); previous.pop('boot', None)

    def _processing_owned(self, nid, scope, actor, rid, doc=None):
        self._processing_flags()
        row = self.get(nid, scope, self.PROCESSING, rid) if doc is None else doc['collections'].get(self.PROCESSING, {}).get(rid)
        if not row or row.get('novel_id') != nid or row.get('scope') != scope or row.get('created_by') != actor:
            raise FileNotFoundError('subtitle processing task')
        return row

    def _processing_current(self, nid, scope, actor, row):
        caption = self._current(nid, scope, actor, row['caption_id'])
        expected = row.get('applied_caption_version', row['caption_version'])
        if caption['version'] != expected or caption['asset_snapshot'] != row['asset_snapshot']:
            raise StaleSourceError('PROCESSING_CAPTION_SOURCE_CHANGED')
        return caption

    @staticmethod
    def _processing_public(row):
        result = copy.deepcopy({k: v for k, v in row.items() if k not in {'history', 'claim', 'boot', 'transcript', 'result'}})
        if row.get('result'):
            result['result'] = {k: v for k, v in row['result'].items() if k != 'content_base64'}
        result['review_required'] = row['status'] == 'NEEDS_REVIEW'
        result['resume_required'] = row['status'] in {'INTERRUPTED', 'FAILED', 'CANCELLED', 'NOT_CONFIGURED'}
        return result

    def processing_tasks(self, nid, scope, actor):
        self._processing_flags(); result = []
        for row in self.list(nid, scope, self.PROCESSING):
            if row.get('created_by') != actor: continue
            try:
                self._processing_current(nid, scope, actor, row)
                view = self._processing_public(row); view['stale'] = False
            except FileNotFoundError:
                continue
            except StaleSourceError:
                view = {k: row[k] for k in ('id', 'version', 'status', 'novel_id', 'scope', 'created_at')}
                view.update(stale=True, content_withheld=True)
            if row['status'] == 'RUNNING' and row.get('boot') != self._processing_boot:
                view['recovery_required'] = True
            result.append(view)
        return {'items': result}

    def queue_processing(self, nid, scope, actor, value, reauthorize=lambda: None):
        self._processing_flags(); data = ProcessingCreateIn.model_validate(value); reauthorize()
        with self.store.transaction(nid, scope) as doc:
            if len(doc['collections'].get(self.PROCESSING, {})) >= MAX_TASKS:
                raise ValueError('PROCESSING_TASK_LIMIT')
            caption = self._current(nid, scope, actor, data.caption_id)
            check_version(caption, data.expected_caption_version)
            asset, _ = self.media(nid, scope, caption['asset_id'])
            if data.operation == 'BURN_IN' and (asset['kind'] != 'video' or not caption['cues']):
                raise ValueError('PROCESSING_VIDEO_AND_CAPTIONS_REQUIRED')
            adapter = self._processing_adapters.get(data.adapter_id)
            if adapter and data.operation not in adapter.definition.operations:
                raise ValueError('PROCESSING_OPERATION_UNSUPPORTED')
            row = new_row(nid, scope, actor, {'caption_id': caption['id'], 'caption_version': caption['version'],
                'asset_snapshot': copy.deepcopy(caption['asset_snapshot']), 'adapter_id': data.adapter_id,
                'adapter_identity': digest(asdict(adapter.definition)) if adapter else None,
                'operation': data.operation, 'transcript': data.transcript, 'attempt': 0,
                'status': 'QUEUED' if self._processing_ready(adapter, data.operation) else 'NOT_CONFIGURED', 'runtime_verification': 'NOT_RUN',
                'verification': adapter.definition.verification if adapter else 'CONTRACT_VERIFIED',
                'privacy_level': 'LOCAL_ONLY', 'result': None, 'error_code': None})
            doc['collections'].setdefault(self.PROCESSING, {})[row['id']] = row
            reauthorize(); self._processing_current(nid, scope, actor, row)
            return self._processing_public(row)

    def _processing_result(self, caption, row, output):
        from .subtitle_timeline import Cue
        if not isinstance(output, ProcessingResult): raise ProcessingResultError('PROCESSING_RESULT_INVALID')
        if row['operation'] == 'BURN_IN':
            if output.cues or not isinstance(output.content, bytes) or not output.content or len(output.content) > MAX_MEDIA_BYTES:
                raise ProcessingResultError('PROCESSING_RESULT_INVALID')
            info = inspect_media(output.content, 'video')
            from fractions import Fraction
            original_ms = Fraction(**caption['media']['duration_seconds']) * 1000
            if not info.get('duration_ms') or abs(Fraction(str(info['duration_ms'])) - original_ms) > 1:
                raise ProcessingResultError('PROCESSING_RENDER_DURATION_CHANGED')
            if output.media_type != info['media_type']: raise ProcessingResultError('PROCESSING_RESULT_MIME_MISMATCH')
            return {'content_base64': base64.b64encode(output.content).decode(), 'media_type': info['media_type'],
                'sha256': hashlib.sha256(output.content).hexdigest(), 'bytes': len(output.content),
                'render_verification': 'MOCK_ONLY' if row['verification'] == 'MOCK_ONLY' else 'NOT_RUN'}
        if output.content or output.media_type or not 1 <= len(output.cues) <= 2000:
            raise ProcessingResultError('PROCESSING_RESULT_INVALID')
        if any(not isinstance(c, dict) or any(type(c.get(k)) is not int for k in ('start_tick', 'end_tick')) for c in output.cues):
            raise ProcessingResultError('PROCESSING_INTEGER_TICKS_REQUIRED')
        cues = [Cue.model_validate(c).model_dump() for c in output.cues]
        if any(c['segment_id'] is not None for c in cues): raise ProcessingResultError('PROCESSING_SPEAKER_ATTRIBUTION_REVIEW_REQUIRED')
        candidate = {**caption, 'cues': cues}; warnings = self._validate(candidate)
        if row['operation'] == 'FORCED_ALIGNMENT' and ' '.join(' '.join(c['text'].split()) for c in cues) != ' '.join(row['transcript'].split()):
            raise ProcessingResultError('PROCESSING_ALIGNMENT_TRANSCRIPT_CHANGED')
        if sum(len(c['text']) for c in cues) > 100000: raise ProcessingResultError('PROCESSING_RESULT_TOO_LARGE')
        return {'cues': cues, 'warnings': warnings, 'timing_origin': 'SYNTHETIC_FIXTURE' if row['verification'] == 'MOCK_ONLY' else 'ADAPTER_CUE_ALIGNMENT',
            'alignment_quality': 'NOT_RUN'}

    def execute_processing(self, nid, scope, actor, rid, value, reauthorize=lambda: None):
        data = ProcessingActionIn.model_validate(value); reauthorize()
        with self.store.transaction(nid, scope) as doc:
            row = self._processing_owned(nid, scope, actor, rid, doc); check_version(row, data.expected_version)
            caption = self._processing_current(nid, scope, actor, row)
            if row['status'] != 'QUEUED': raise ValueError('PROCESSING_QUEUED_REQUIRED')
            adapter = self._processing_adapters.get(row['adapter_id'])
            if not self._processing_ready(adapter, row['operation']) or digest(asdict(adapter.definition)) != row['adapter_identity']:
                raise ValueError('PROCESSING_ADAPTER_NOT_CONFIGURED_OR_CHANGED')
            content = self.assets.content(caption['asset_id'], branch_id=scope.get('branch_id'))
            if len(content) > MAX_MEDIA_BYTES: raise ValueError('PROCESSING_INPUT_TOO_LARGE')
            asset = self.assets.get(caption['asset_id'], branch_id=scope.get('branch_id'))
            info = inspect_media(content, asset['kind'])
            claim = uuid4().hex
            self._processing_change(row, actor, row['version'], lambda r: r.update(status='RUNNING', claim=claim,
                boot=self._processing_boot, attempt=r['attempt'] + 1, result=None, error_code=None))
            running = copy.deepcopy(row); reauthorize()
        def guard():
            reauthorize(); current = self._processing_owned(nid, scope, actor, rid)
            if current['status'] != 'RUNNING' or current.get('claim') != claim:
                raise ProcessingFenceError('PROCESSING_CANCELLED_OR_CLAIM_CHANGED')
            self._processing_current(nid, scope, actor, current)
            if self._processing_adapters.get(current['adapter_id']) is not adapter or digest(asdict(adapter.definition)) != current['adapter_identity']:
                raise ProcessingFenceError('PROCESSING_ADAPTER_CHANGED')
        try:
            guard()
            adapter_guard_errors = []
            def adapter_guard():
                try: guard()
                except Exception as failure:
                    adapter_guard_errors.append(failure)
                    raise
            try:
                output = adapter.process(ProcessingRequest(rid + ':' + str(running['attempt']), running['operation'], content,
                    info['media_type'], copy.deepcopy(caption), running['transcript'], digest([caption['version'], caption['asset_snapshot']]), adapter_guard))
            except Exception as failure:
                # Only an exception from our actual dispatch guard may retain
                # its public authority/conflict classification. An adapter's
                # HTTPException or ValueError is still untrusted error text.
                if any(failure is observed for observed in adapter_guard_errors): raise
                raise ValueError('PROCESSING_ADAPTER_FAILED') from None
            guard(); result = self._processing_result(caption, running, output)
            with self.store.transaction(nid, scope) as doc:
                guard(); current = self._processing_owned(nid, scope, actor, rid, doc)
                if sum((item.get('result') or {}).get('bytes', 0) for item in doc['collections'].get(self.PROCESSING, {}).values()) + result.get('bytes', 0) > MAX_SCOPE_RENDER_BYTES:
                    raise ProcessingResultError('PROCESSING_SCOPE_RENDER_LIMIT')
                self._processing_change(current, actor, running['version'], lambda r: r.update(status='NEEDS_REVIEW', result=result, claim=None))
                current['preview_digest'] = digest([current['id'], current['version'], current['caption_version'], current['asset_snapshot'], result])
                reauthorize(); self._processing_current(nid, scope, actor, current)
                return self._processing_public(current)
        except Exception as exc:
            # Preserve a concurrent cancellation/recovery. Never persist raw
            # provider errors (which can contain paths, prompts or credentials).
            with self.store.transaction(nid, scope) as doc:
                current = doc['collections'].get(self.PROCESSING, {}).get(rid)
                if current and current['status'] == 'RUNNING' and current.get('claim') == claim:
                    self._processing_change(current, actor, current['version'], lambda r: r.update(status='FAILED', claim=None, result=None, error_code='PROCESSING_OUTPUT_DISCARDED'))
            if isinstance(exc, (HTTPException, CapabilityVersionConflict, StaleSourceError, FileNotFoundError, ProcessingFenceError, ProcessingResultError)):
                raise
            raise ValueError('PROCESSING_OUTPUT_DISCARDED') from None

    def processing_action(self, nid, scope, actor, rid, action, value, reauthorize=lambda: None):
        if action == 'execute': return self.execute_processing(nid, scope, actor, rid, value, reauthorize)
        data = ProcessingActionIn.model_validate(value); reauthorize()
        with self.store.transaction(nid, scope) as doc:
            row = self._processing_owned(nid, scope, actor, rid, doc); check_version(row, data.expected_version)
            if action == 'cancel':
                if row['status'] not in {'QUEUED', 'RUNNING', 'NOT_CONFIGURED', 'NEEDS_REVIEW', 'INTERRUPTED', 'FAILED'}:
                    raise ValueError('PROCESSING_CANCEL_INVALID_STATE')
                self._processing_change(row, actor, row['version'], lambda r: r.update(status='CANCELLED', result=None, claim=None))
            elif action == 'recover':
                if row['status'] != 'RUNNING' or row.get('boot') == self._processing_boot:
                    raise ValueError('PROCESSING_INTERRUPTED_RESTART_REQUIRED')
                self._processing_change(row, actor, row['version'], lambda r: r.update(status='INTERRUPTED', result=None, claim=None))
            elif action == 'resume':
                if row['status'] not in {'CANCELLED', 'FAILED', 'INTERRUPTED', 'NOT_CONFIGURED'}:
                    raise ValueError('PROCESSING_RESUME_INVALID_STATE')
                self._processing_current(nid, scope, actor, row)
                if row['attempt'] >= MAX_ATTEMPTS: raise ValueError('PROCESSING_ATTEMPT_LIMIT')
                adapter = self._processing_adapters.get(row['adapter_id'])
                if not self._processing_ready(adapter, row['operation']):
                    raise ValueError('PROCESSING_ADAPTER_NOT_CONFIGURED')
                self._processing_change(row, actor, row['version'], lambda r: r.update(status='QUEUED', adapter_identity=digest(asdict(adapter.definition)),
                    verification=adapter.definition.verification, result=None, error_code=None, claim=None))
            elif action in {'approve', 'reject'}:
                caption = self._processing_current(nid, scope, actor, row)
                if row['status'] != 'NEEDS_REVIEW' or data.preview_digest != row.get('preview_digest'):
                    raise StaleSourceError('PROCESSING_REVIEW_CHANGED')
                if action == 'approve' and row['operation'] != 'BURN_IN':
                    current = doc['collections'][self.COLLECTION][caption['id']]
                    cues = copy.deepcopy(row['result']['cues'])
                    snapshots, speakers, sources = self._snapshot(nid, scope, actor, caption.get('plan_id'), cues)
                    change_row(current, actor, caption['version'], lambda r: r.update(cues=cues,
                        segment_snapshots=snapshots, speakers=speakers, sources=sources, warnings=row['result']['warnings'],
                        status='APPROVED', timing_origin=row['result']['timing_origin'], alignment_model=row['adapter_id'],
                        processing_task_id=rid, alignment_quality='NOT_RUN'))
                    row['applied_caption_version'] = current['version']
                self._processing_change(row, actor, row['version'], lambda r: r.update(status='APPROVED' if action == 'approve' else 'REJECTED'))
            else: raise ValueError('PROCESSING_ACTION_UNKNOWN')
            reauthorize()
            if action in {'approve', 'reject', 'resume'}: self._processing_current(nid, scope, actor, row)
            return self._processing_public(row)

    def processing_download(self, nid, scope, actor, rid, version, reauthorize=lambda: None):
        row = self._processing_owned(nid, scope, actor, rid); check_version(row, version)
        self._processing_current(nid, scope, actor, row)
        if row['status'] != 'APPROVED' or row['operation'] != 'BURN_IN': raise ValueError('PROCESSING_APPROVED_RENDER_REQUIRED')
        content = base64.b64decode(row['result']['content_base64'], validate=True)
        if hashlib.sha256(content).hexdigest() != row['result']['sha256']: raise ValueError('PROCESSING_RENDER_CORRUPT')
        reauthorize(); current = self._processing_owned(nid, scope, actor, rid); check_version(current, version)
        self._processing_current(nid, scope, actor, current)
        return content, row['result']['media_type']


def processing_task_projection(service, ctx):
    """Bounded metadata-only view for the original unified Task Center."""
    rows = service.processing_tasks(ctx.novel_id, ctx.scope, ctx.actor)['items']
    return {'items': [{k: row[k] for k in ('id', 'novel_id', 'scope', 'version', 'status', 'stale',
        'operation', 'caption_id', 'created_at', 'recovery_required') if k in row} for row in rows[:200]],
        'has_more': len(rows) > 200}


def processing_review_projection(service, ctx):
    """Original inbox points to exact-source preview; it cannot skip its digest."""
    rows = service.processing_tasks(ctx.novel_id, ctx.scope, ctx.actor)['items']
    return [{'id': row['id'], 'novel_id': ctx.novel_id, 'scope': ctx.scope, 'version': row['version'],
        'status': row['status'], 'stale': row.get('stale', False), 'created_by': ctx.actor,
        'created_at': row['created_at'], 'privacy_state': 'LOCAL_ONLY', 'risk': 'EXACT_RESULT_REVIEW_REQUIRED',
        'preview': 'Subtitle processing result' if row.get('stale') else row['operation'] + ' subtitle result',
        'target': {'domain': 'subtitle_timeline_v2', 'id': row['id']},
        'allowed_actions': [], 'batch_safe': False} for row in rows if row['status'] == 'NEEDS_REVIEW']
