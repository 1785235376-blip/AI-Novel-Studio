"""Transient OCR invocation owned by the original JobManager.

This module exposes no HTTP route and does not admit Research jobs. Its trusted
caller must supply original broker hooks; real Research dispatch remains closed.
Persisted records cannot reconstruct this object or obtain a live result.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import time
from threading import get_ident

from .research_ocr_binding import parse_research_ocr_binding
from .research_vision import PreparedResearchOCRSource
from ..audio_processing_runtime import audio_digest
from ..model_runtime import ModelRuntimeError, RuntimeErrorCode
from ..vision_ocr_runtime import VisionOCRModelNode, VisionOCRRequest, PDFPageOCRRequest

FLAGS = ('research_library_v2', 'ai_execution_v2', 'narrative_production_v2',
         'model_broker_v2', 'author_context_inspector_v2')
IDENTITY = ('id', 'operation', 'novel_id', 'chapter_id', 'profile', 'actor_id', 'scope',
    'experimental_origin', 'research_ocr_binding', 'expected_request_digest',
    'requested_provider', 'requested_model', 'generation_max_output_bytes', 'generation_deadline',
    'source', 'instruction', 'graph_binding', 'adaptation_binding', 'creative_director_binding')


class _ResearchOCRCapability:
    def __init__(self, manager, job, source, node, before_dispatch, on_terminal, on_result=None):
        if (type(source) is not PreparedResearchOCRSource or type(node) is not VisionOCRModelNode
                or not callable(before_dispatch) or not callable(on_terminal)
                or on_result is not None and not callable(on_result)):
            raise ValueError('RESEARCH_OCR_LIVE_OWNER_REQUIRED')
        self.manager, self.job, self.source, self.node = manager, job, source, node
        self.before_dispatch, self.on_terminal = before_dispatch, on_terminal
        self.on_result = on_result
        self.authorizer, self.cancellation = job.request_authorization, job.cancelled
        self.persistence = manager.persistence
        self.provider = node.providers.resolve(job.requested_provider)
        self.identity = {key: deepcopy(getattr(job, key)) for key in IDENTITY}
        self.started = self.worker_claimed = self.finished = False
        self.worker_thread = None
        self._result = None

    def current(self):
        from .flags import require_flag
        from ..jobs import validate_generation_bounds
        for flag in FLAGS: require_flag(flag)
        job = self.job
        if (job.research_ocr_execution_authority is not self or self.manager.persistence is not self.persistence
                or job.creative_execution_authority is not None or job.prepared_text_invocation is not None
                or job.cancelled is not self.cancellation or job.request_authorization is not self.authorizer
                or self.node.providers.resolve(job.requested_provider) is not self.provider
                or any(getattr(job, key) != value for key, value in self.identity.items())
                or job.before_dispatch is not self.before_dispatch or job.on_terminal is not self.on_terminal):
            raise ValueError('RESEARCH_OCR_LIVE_IDENTITY_CHANGED')
        if job.cancelled.is_set():
            raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, '已停止 OCR')
        deadline = validate_generation_bounds(job)
        if deadline is None or datetime.now(timezone.utc) >= deadline:
            raise ModelRuntimeError(RuntimeErrorCode.TIMEOUT, 'OCR 任务已超时')
        binding = parse_research_ocr_binding(job.research_ocr_binding)
        source = self.source.binding
        if any(source.get(key) != getattr(binding, key) for key in
               ('project_id', 'project_incarnation', 'actor_id', 'source_id', 'source_version', 'source_digest', 'media_type')):
            raise ValueError('RESEARCH_OCR_SOURCE_BINDING_CHANGED')
        if binding.source_kind == 'PDF' and (source.get('source_kind') != 'PDF' or source.get('page') != binding.page):
            raise ValueError('RESEARCH_OCR_SOURCE_BINDING_CHANGED')
        if source['scope'] != binding.scope.model_dump():
            raise ValueError('RESEARCH_OCR_SOURCE_BINDING_CHANGED')
        self.source.validate_current()
        route = self.node.binding(job.requested_provider, job.requested_model)
        if (route['route_digest'] != binding.route_digest
                or binding.language not in route['route']['languages']):
            raise ValueError('RESEARCH_OCR_ROUTE_CHANGED')

    def require_job(self, manager, job, *, started):
        if (manager is not self.manager or job is not self.job
                or job.research_ocr_execution_authority is not self or self.started is not started):
            raise ValueError('RESEARCH_OCR_EXECUTION_UNAVAILABLE')
        self.current()

    def result(self):
        if not self.finished and self.worker_thread != get_ident():
            raise ValueError('RESEARCH_OCR_PUBLICATION_PENDING')
        self.current()
        job = self.job
        if (self._result is None or job.status != 'COMPLETED' or job.terminal_hook_status != 'COMPLETED'
                or job.output != self._result.text):
            raise ValueError('RESEARCH_OCR_TERMINAL_RESULT_UNAVAILABLE')
        persisted = self.manager.persistence.get(job.id)
        if any(persisted.get(key) != job.public().get(key) for key in
               ('status', 'output', 'terminal_hook_status', 'research_ocr_binding', 'expected_request_digest', 'research_ocr_output_evidence')):
            raise ValueError('RESEARCH_OCR_TERMINAL_RESULT_UNAVAILABLE')
        self.current()
        return deepcopy(self._result)


def prepare(manager, *, source, node, binding, provider_id, model_id, deadline,
            before_dispatch, on_terminal, max_output_bytes=128000, on_result=None):
    from uuid import uuid4
    from ..jobs import Job
    parsed = parse_research_ocr_binding(binding)
    job = Job(id=str(uuid4()), operation='research_ocr', novel_id=parsed.project_id,
        chapter_id=None, instruction='', profile='LOCAL_ONLY', requested_provider=provider_id,
        requested_model=model_id, status='PREPARED', actor_id=parsed.actor_id, scope=parsed.scope.model_dump(),
        experimental_origin='research_ocr_model', research_ocr_binding=parsed.model_dump(),
        generation_max_output_bytes=max_output_bytes, generation_deadline=deadline,
        before_dispatch=before_dispatch, on_terminal=on_terminal, dispatch_hooks_required=True,
        request_authorization=source.validate_current if type(source) is PreparedResearchOCRSource else None)
    job.expected_request_digest = audio_digest({'binding': parsed.model_dump(), 'provider_id': provider_id,
        'model_id': model_id, 'deadline': deadline, 'max_output_bytes': max_output_bytes})
    job.research_ocr_execution_authority = _ResearchOCRCapability(manager, job, source, node, before_dispatch, on_terminal, on_result)
    job.research_ocr_execution_authority.current()
    return job


def require_capability(manager, job, *, started):
    capability = getattr(job, 'research_ocr_execution_authority', None)
    if type(capability) is not _ResearchOCRCapability:
        raise ValueError('RESEARCH_OCR_EXECUTION_UNAVAILABLE')
    capability.require_job(manager, job, started=started)
    return capability


def run(manager, job):
    capability = getattr(job, 'research_ocr_execution_authority', None)
    if (type(capability) is not _ResearchOCRCapability or capability.manager is not manager
            or capability.job is not job or not capability.started):
        raise ValueError('RESEARCH_OCR_EXECUTION_UNAVAILABLE')
    with job.condition:
        if capability.worker_claimed:
            raise ValueError('RESEARCH_OCR_WORKER_ALREADY_CLAIMED')
        capability.worker_claimed = True
        capability.worker_thread = get_ident()
    started = time.monotonic()
    response = None
    try:
        capability.current()
        job.status = 'GENERATING'
        manager._emit(job)
        raw = capability.source.read_current()
        binding = job.research_ocr_binding
        request_type = PDFPageOCRRequest if binding['source_kind'] == 'PDF' else VisionOCRRequest
        extra = {'page': binding['page']} if binding['source_kind'] == 'PDF' else {}
        request = request_type(job.requested_provider, job.requested_model, raw,
            binding['media_type'], binding['language'], binding['source_digest'], binding['route_digest'],
            job.id, dispatch_guard=capability.current, cancellation=job.cancelled, **extra)
        capability.before_dispatch()
        capability.current()
        response = capability.node.execute(request)
        capability.current()
        if len(response.text.encode('utf-8')) > job.generation_max_output_bytes:
            raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, 'OCR 输出超过本次任务限制')
        if binding['source_kind'] == 'PDF':
            job.research_ocr_output_evidence = deepcopy(response.receipt)
        job.provider, job.model = response.provider_id, response.model_id
        job.output, job.status, job.execution_outcome = response.text, 'COMPLETED', 'COMPLETED'
    except Exception as exc:
        job.output = ''
        cancelled = job.cancelled.is_set() or isinstance(exc, ModelRuntimeError) and exc.code == RuntimeErrorCode.CANCELLED
        job.status = job.execution_outcome = 'CANCELLED' if cancelled else 'FAILED'
        job.error_code = 'CANCELLED' if cancelled else exc.code.value if isinstance(exc, ModelRuntimeError) else 'RESEARCH_OCR_EXECUTION_FAILED'
        job.error = 'OCR 未完成，未发布识别结果。'
    finally:
        job.latency_ms = int((time.monotonic() - started) * 1000)
        manager._finish_terminal_hook(job)
        try:
            if job.status == 'COMPLETED':
                capability.current()
                if response is None or job.output != response.text or job.terminal_hook_status != 'COMPLETED':
                    raise ValueError('RESEARCH_OCR_TERMINAL_RESULT_UNAVAILABLE')
            manager._persist(job)
            if job.status == 'COMPLETED':
                capability.current()
                capability._result = deepcopy(response)
                if capability.on_result is not None:
                    # The original review owner receives only a verified,
                    # detached result after job persistence and settlement.
                    # Its own transaction and receipt validation remain required.
                    capability.on_result(capability.result())
                    capability.result()  # Recheck authority and durable identity after the callback.
        except Exception:
            job.output = ''; job.status = 'CANCELLED' if job.cancelled.is_set() else 'FAILED'; job.execution_outcome = job.status
            job.error_code = 'CANCELLED' if job.cancelled.is_set() else 'RESEARCH_OCR_TERMINAL_UNCONFIRMED'
            job.error = 'OCR 结果未能确认保存，请核对原任务，不能自动重放。'
            capability._result = None
            try: manager._persist(job)
            except Exception: pass  # Original owner may have been deleted; never recreate it.
        with job.condition:
            capability.finished = True
            job.condition.notify_all()
