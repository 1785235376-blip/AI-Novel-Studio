"""Transient execution of newly admitted original File-local keyed writers.

The durable binding is identity only. This exact live capability is neither
restored nor inferred from a passive record, read verifier or saved callback.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from threading import Lock, Thread, get_ident, current_thread
import time

_SEAL = object()
_INPUT_FIELDS = (
    'id', 'operation', 'novel_id', 'chapter_id', 'instruction', 'profile', 'source',
    'requested_provider', 'requested_model', 'style', 'base_chapter_version',
    'base_chapter_digest', 'actor_id', 'session_id', 'client_id', 'workspace_id',
    'scope', 'scope_type', 'scope_id', 'experimental_origin', 'creation_records',
    'variant_group_id', 'variant_index', 'request_scope', 'expected_request_digest',
    'author_input_digest', 'reviewed_variant', 'revision_selection_binding',
    'partial_revision_only', 'character_viewpoint', 'dispatch_hooks_required',
    'generation_max_output_bytes', 'generation_deadline',
)


class _FileWriterCapability:
    def __init__(self, seal, manager, job, ports, route):
        if seal is not _SEAL:
            raise ValueError('GENERATION_WRITER_LIVE_CAPABILITY_REQUIRED')
        from .. import jobs
        from ..model_execution import LocalModelInvocation
        from .generation_project_binding import ordinary_job_binding
        if not callable(job.request_authorization):
            raise ValueError('GENERATION_WRITER_AUTHORIZATION_REQUIRED')
        self._seal = seal
        self._self = (self,)  # A shallow copy cannot become a newly issued grant.
        self.manager, self.job, self.ports = manager, job, ports
        self._ports = (ports,)
        self.binding = ordinary_job_binding(job.record())
        self.inputs = deepcopy({key: getattr(job, key) for key in _INPUT_FIELDS})
        self.authorization = job.request_authorization
        self.cancellation, self.condition = job.cancelled, job.condition
        self.runtime = jobs.runtime
        self.route = (route.provider, route.model)
        self.invocation = LocalModelInvocation(self.runtime, *self.route, synthetic_allowed=True)
        self.node = self.runtime.prepare_text_route(*self.route)
        self.providers, self.models = self.runtime.provider_registry, self.runtime.model_registry
        self.repository = manager._ordinary_repository
        self._receipt_save = self.repository.save
        self.persistence = manager.persistence
        self.root = manager._ordinary_repository_root
        self.started = self.worker_claimed = self.refused = False
        self.starting = False
        self.start_thread = None
        self.worker_thread = None
        self.worker = None
        self.memory = manager.memory_extractor
        self.memory_ports = self.memory._bound_ports
        self.memory_backends = self.memory._bound_backends
        self.memory_runtime = self.memory.runtime
        self.memory_runner = self.memory.agent_runner
        self.adapter = self.invocation._provider
        self.adapter_provider = getattr(self.adapter, "provider", None)
        self.adapter_bridge = getattr(self.adapter, "bridge", None)
        self.adapter_candidate = deepcopy(getattr(self.adapter, "candidate", None))
        self.adapter_client = getattr(self.adapter, "client", None)
        self._lock = Lock()
        self.active_thread = None
        self.queued = False
        self.durable_status = None

    def __copy__(self):
        raise ValueError('GENERATION_WRITER_CAPABILITY_NOT_COPYABLE')

    def __deepcopy__(self, memo):
        raise ValueError('GENERATION_WRITER_CAPABILITY_NOT_COPYABLE')

    def check(self):
        from .. import jobs
        from .generation_project_binding import ordinary_job_binding
        if (self._seal is not _SEAL or self._self[0] is not self
                or self.ports is not self._ports[0]
                or dict(self.ports.binding) != self.binding
                or self.job._ordinary_execution_capability is not self
                or self.job.request_authorization is not self.authorization
                or self.job.cancelled is not self.cancellation or self.job.condition is not self.condition
                or self.manager.persistence is not self.persistence
                or self.persistence.repository is not self.repository
                or self.manager._ordinary_repository is not self.repository
                or self.manager._ordinary_repository_root != self.root
                or ordinary_job_binding(self.job.record()) != self.binding
                or any(getattr(self.job, key) != value for key, value in self.inputs.items())
                or jobs.runtime is not self.runtime
                or self.runtime.provider_registry is not self.providers
                or self.runtime.model_registry is not self.models
                or self.runtime.generation_runtime.text_node is not self.node
                or self.node.providers is not self.providers or self.node.models is not self.models
                or self.job.before_dispatch is not None or self.job.on_terminal is not None
                or self.job.author_context_resolver is not None
                or self.job.character_context_resolver is not None
                or self.job.author_preparation_guard is not None):
            raise ValueError('GENERATION_WRITER_CAPABILITY_CHANGED')
        self.manager._file_review_pins.validate()
        self._check_memory()
        if (self.providers.resolve(self.route[0]) is not self.adapter
                or self.invocation._provider is not self.adapter
                or getattr(self.adapter, 'provider', None) is not self.adapter_provider
                or getattr(self.adapter, 'bridge', None) is not self.adapter_bridge
                or getattr(self.adapter, 'candidate', None) != self.adapter_candidate
                or getattr(self.adapter, 'client', None) is not self.adapter_client):
            raise ValueError('GENERATION_WRITER_ROUTE_CHANGED')
        self.ports.check()
        if self.queued and self.manager.jobs.get(self.job.id) is not self.job:
            raise ValueError('GENERATION_WRITER_JOB_REPLACED')

    def _check_memory(self):
        from pathlib import Path
        from ..lore.memory_agent import MemoryAgentRunner
        from ..repositories.file import FileNovelRepository, FileChapterRepository, FileLoreRepository
        from ..services import LoreService, GenerationService
        from ..repository import FileRepository
        memory = self.memory
        ports = (memory.novels, memory.chapters, memory.lore, memory.generations,
                 getattr(memory.lore, 'repository', None), getattr(memory.generations, 'repository', None))
        root = self.root.parent.parent
        if (type(memory) is not MemoryAgentRunner or self.manager.memory_extractor is not memory
                or memory._bound_ports is not self.memory_ports
                or memory._bound_backends is not self.memory_backends
                or any(current is not original for current, original in zip(ports, self.memory_ports))
                or tuple(type(value) for value in ports[:5]) !=
                    (FileNovelRepository, FileChapterRepository, LoreService, GenerationService, FileLoreRepository)
                or ports[-1] is not self.repository or memory._bound_data != root
                or memory.runtime is not self.memory_runtime or memory.agent_runner is not self.memory_runner):
            raise ValueError('GENERATION_WRITER_MEMORY_PORT_CHANGED')
        for port, backend in zip((ports[0], ports[1], ports[4]), self.memory_backends):
            if (port.backend is not backend or type(backend) is not FileRepository
                    or Path(backend.data).resolve() != root or Path(backend.novels).resolve() != root/'novels'):
                raise ValueError('GENERATION_WRITER_MEMORY_PORT_CHANGED')

    def authorize(self, route=None, *, dispatch=False):
        from ..jobs import _OrdinaryRequestAuthorizationFailed
        try:
            self.check()
            if self.refused or self.job.cancelled.is_set():
                raise ValueError('GENERATION_WRITER_AUTHORIZATION_REFUSED')
            if route is not None and (route.provider, route.model) != self.route:
                raise ValueError('GENERATION_WRITER_ROUTE_CHANGED')
            # Callbacks and registration guards are intentionally outside all
            # owner/review/condition leases, including the final adapter hop.
            self.authorization()
            self.check()
            self.invocation.validate()
            if self.adapter_bridge is not None:
                current = self.adapter_bridge.guard(self.adapter_candidate['id'])
                if current != self.adapter_candidate:
                    raise ValueError('GENERATION_WRITER_ROUTE_CHANGED')
            if not self.runtime.packaged_author_route_ready(self.route[0]):
                raise ValueError('GENERATION_WRITER_ROUTE_UNAVAILABLE')
            self.ports.source()
            self.check()
            if dispatch:
                if (current_thread() is not self.worker or not self.started or not self.queued
                        or not self.worker_claimed or self.job.status != 'GENERATING'):
                    raise ValueError('GENERATION_WRITER_DISPATCH_CONTEXT_REQUIRED')
                with self.ports.guard():
                    self._check_durable()
                    if self.durable_status != 'GENERATING':
                        raise ValueError('GENERATION_WRITER_DURABLE_QUEUE_REQUIRED')
        except Exception:
            self.refused = True
            raise _OrdinaryRequestAuthorizationFailed() from None

    def source(self, cloud=False):
        self.check()
        if cloud:
            raise ValueError('GENERATION_WRITER_LOCAL_ONLY')
        return self.ports.source()

    @contextmanager
    def mutation(self, *, authorize=True):
        from ..runtime_events import runtime_events
        if authorize:
            self.authorize()
        self.check()
        failure = None
        # Buffer real committed effects even if a later operation throws. Flush
        # only after every original lease and condition has been released.
        with runtime_events.transaction():
            try:
                with self.ports.guard(), self.manager._review_mutation(self.job.id), self.job.condition:
                    self.check()
                    self._check_durable()
                    self.active_thread = get_ident()
                    try:
                        yield
                    finally:
                        self.active_thread = None
            except BaseException as exc:
                failure = (exc, exc.__traceback__)
        if failure is not None:
            raise failure[0].with_traceback(failure[1])

    def _check_durable(self):
        from .generation_project_binding import ordinary_job_binding
        self.check()
        try:
            current = self.repository.get(self.job.id)
        except KeyError:
            if self.durable_status is None:
                return
            raise ValueError('GENERATION_WRITER_DURABLE_RECORD_MISSING') from None
        self.check()
        if (self.durable_status is None or ordinary_job_binding(current) != self.binding
                or current.get('status') != self.durable_status):
            raise ValueError('GENERATION_WRITER_DURABLE_STATE_CHANGED')

    def persist(self):
        from ..jobs import utc
        if self.active_thread != get_ident():
            raise ValueError('GENERATION_WRITER_WRITE_CONTEXT_REQUIRED')
        self.check()
        self._check_durable()
        self.job.updated_at = utc()
        try:
            self.persistence.save(self.job.record(), _file_writer=self.ports)
        except Exception:
            # Suppress adoption from a cached successful-looking terminal state
            # before deferred notifications for a partial write are flushed.
            self.job.status = 'FAILED'; self.job.output = ''; self.job.issues = []
            self.job.error_code = 'GENERATION_TERMINAL_PERSISTENCE_UNCERTAIN'
            self.job.error = '生成记录未能确认保存，不会自动重试或采用。'
            raise
        self.durable_status = self.job.status
        self.job.condition.notify_all()

    def snapshot(self, chapter, context, prompt_version, model, **metadata):
        self.authorize()
        self.check()
        if (chapter.get('id') != self.binding['chapter_id']
                or chapter.get('version') != self.binding['base_chapter_version']):
            raise ValueError('GENERATION_WRITER_SOURCE_CHANGED')
        # The actual original service/repository owns the final write lease.
        # Do not run a facade wrapper under a parent owner's inherited scope.
        result = self.manager.contexts.save_snapshot(self.job.chapter_id,
            self.binding['base_chapter_version'], context, prompt_version, model,
            _file_writer=self.ports, **metadata)
        if not result:
            raise RuntimeError('Context snapshot persistence is required')
        self.check()
        return result


def classify_route(runtime, payload):
    """Select only the original supported local families, without dispatch.

    Other established route families retain their legacy path. A declared Mock
    or registered original LocalTextAdapter is an intended supported family:
    invalid configuration there refuses rather than downgrading to unbound.
    """
    from ..router import Route
    from ..author_request import AUTHOR_ROLES
    from ..model_runtime import LegacyTextProviderAdapter
    from ..model_center.discovery_bridge import LocalTextAdapter
    from ..model_execution import LocalModelInvocation
    from ..providers import MockProvider
    from ..config import settings
    provider, model = payload.get('provider_id'), payload.get('model_id')
    if bool(provider) != bool(model):
        raise ValueError('GENERATION_WRITER_ROUTE_INCOMPLETE')
    if provider:
        route = Route(provider, model)
    else:
        routes = runtime.router('LOCAL_ONLY', 'writer').routes['writer']
        if len(routes) != 1:
            raise ValueError('GENERATION_WRITER_SINGLE_ROUTE_REQUIRED')
        route = routes[0]
    adapter = runtime.provider_registry.resolve(route.provider)
    synthetic = type(adapter) is LegacyTextProviderAdapter and type(adapter.provider) is MockProvider
    if route.provider == 'mock' or synthetic:
        if not synthetic or not settings.mock_provider or settings.enable_packaged_runtime:
            raise ValueError('GENERATION_WRITER_MOCK_ROUTE_UNAVAILABLE')
    elif type(adapter) is not LocalTextAdapter:
        return None
    # This verifies host-owned model locality, not a caller's provider label.
    LocalModelInvocation(runtime, route.provider, route.model, synthetic_allowed=True)
    if not runtime.packaged_author_route_ready(route.provider):
        raise ValueError('GENERATION_WRITER_ROUTE_UNAVAILABLE')
    runtime.prepare_text_route(route.provider, route.model)
    return route


def bind(manager, job, ports, route):
    if getattr(job, '_ordinary_execution_capability', None) is not None or job.status != 'PREPARED':
        raise ValueError('GENERATION_WRITER_ALREADY_BOUND')
    capability = _FileWriterCapability(_SEAL, manager, job, ports, route)
    job._ordinary_execution_capability = capability
    capability.check()
    capability.authorize(route)
    return capability


def require_capability(manager, job, *, started=False):
    capability = getattr(job, '_ordinary_execution_capability', None)
    if (type(capability) is not _FileWriterCapability or capability.manager is not manager
            or capability.job is not job or (started and not capability.started)):
        from fastapi import HTTPException
        raise HTTPException(409, {'code': 'GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED'})
    capability.check()
    return capability


def start(manager, job):
    capability = require_capability(manager, job)
    with capability._lock:
        if capability.started or job.status != 'PREPARED':
            raise ValueError('GENERATION_JOB_ALREADY_STARTED')
        # Consumed before any uncertain write. No automatic second start.
        capability.started = True
        capability.starting = True
        capability.start_thread = get_ident()
    try:
        with capability.mutation():
            with manager.lock:
                if job.id in manager.jobs:
                    raise ValueError('GENERATION_JOB_ALREADY_STARTED')
                manager.jobs[job.id] = job
                capability.queued = True
            job.status = 'QUEUED'
            capability.persist()
        capability.worker = Thread(target=manager._run, args=(job,), daemon=True)
        capability.worker.start()
    except Exception:
        _fail(capability, 'GENERATION_START_UNCONFIRMED', '生成启动记录未能确认，请核对任务记录，不会自动重新派发。')
        raise
    finally:
        capability.starting = False
    return job


def _fail(capability, code, message):
    # Receipt-only authority is restricted to the exact issued worker or its
    # still-active start frame. It does not validate or restore execution.
    if (type(capability) is not _FileWriterCapability or capability._seal is not _SEAL
            or capability._self[0] is not capability
            or capability.job._ordinary_execution_capability is not capability
            or not capability.started
            or not ((current_thread() is capability.worker and capability.worker_claimed)
                or (capability.starting and get_ident() == capability.start_thread
                    and not capability.worker_claimed))):
        raise ValueError('GENERATION_WRITER_FAILURE_RECEIPT_REQUIRED')
    from ..runtime_events import runtime_events
    from .generation_project_binding import ordinary_job_binding
    from ..jobs import utc
    job, manager = capability.job, capability.manager
    def receipt_check():
        if (job._ordinary_execution_capability is not capability
                or manager.persistence is not capability.persistence
                or manager._ordinary_repository is not capability.repository
                or manager._ordinary_repository_root != capability.root
                or capability.persistence.repository is not capability.repository
                or ordinary_job_binding(job.record()) != capability.binding
                or (capability.queued and manager.jobs.get(job.id) is not job)):
            raise ValueError('GENERATION_WRITER_RECEIPT_IDENTITY_CHANGED')
    with runtime_events.transaction():
        try:
            receipt_check()
            ports = capability.ports.for_receipt()
            with ports.guard(), manager._review_mutation(job.id), job.condition:
                receipt_check()
                current = capability.repository.get(job.id)
                if (ordinary_job_binding(current) != capability.binding
                        or current.get('status') not in {'QUEUED', 'GENERATING'}
                        or (capability.durable_status is not None
                            and current.get('status') != capability.durable_status)):
                    raise ValueError('GENERATION_WRITER_DURABLE_STATE_CHANGED')
                # Derive the error receipt from original durable input, not any
                # callback/route/source fields changed on the live object.
                receipt = deepcopy(current)
                receipt.update(status='FAILED', output='', issues=[], error_code=code,
                    error=message, updated_at=utc(),
                    execution_outcome=job.execution_outcome or 'FAILED')
                for key in ('usage', 'usage_status', 'execution_mode', 'provider_reference_id',
                            'provider', 'model', 'route_decisions', 'latency_ms'):
                    receipt[key] = deepcopy(getattr(job, key))
                job.status = 'FAILED'; job.output = ''; job.issues = []
                job.error_code, job.error = code, message
                job.execution_outcome = job.execution_outcome or 'FAILED'
                capability._receipt_save(receipt, _expected_root=capability.root, _file_writer=ports)
                capability.durable_status = 'FAILED'
                job.condition.notify_all()
        except Exception:
            # A missing/retired owner or uncertain receipt gets no late write to
            # a replacement. Flush actual committed effects after leases exit.
            with job.condition:
                job.status = 'FAILED'; job.output = ''; job.issues = []
                job.error_code = 'GENERATION_TERMINAL_PERSISTENCE_UNCERTAIN'
                job.error = '生成记录未能确认保存，不会自动重试或采用。'
                job.execution_outcome = job.execution_outcome or 'FAILED'
                job.condition.notify_all()


def run(manager, job):
    capability = getattr(job, '_ordinary_execution_capability', None)
    # Only the issued worker may consume its claim or publish an error. A
    # direct/forged caller must fail without mutating the queued original job.
    if type(capability) is not _FileWriterCapability:
        manager.require_ordinary_mutation_eligibility(job)
        raise ValueError('GENERATION_WRITER_WORKER_REQUIRED')
    if (capability._seal is not _SEAL
            or capability._self[0] is not capability or capability.manager is not manager
            or capability.job is not job or not capability.started
            or current_thread() is not capability.worker):
        raise ValueError('GENERATION_WRITER_WORKER_REQUIRED')
    with capability._lock:
        if (current_thread() is not capability.worker or capability.worker_claimed
                or not capability.queued or job.status != 'QUEUED'):
            raise ValueError('GENERATION_WRITER_WORKER_ALREADY_CLAIMED')
        capability.worker_claimed = True
        capability.worker_thread = get_ident()
    from ..author_request import AUTHOR_ROLES
    from ..model_runtime import TextModelNodeInput, ModelRuntimeError, RuntimeErrorCode
    from ..review import deterministic_review
    from ..router import Route
    from ..jobs import check_generation_bounds, _OrdinaryRequestAuthorizationFailed
    from ..structured_log import runtime_log
    started = time.monotonic()
    route = Route(*capability.route)
    role = AUTHOR_ROLES[capability.binding['operation']]
    decision = {'provider': route.provider, 'model': route.model, 'cloud': False, 'status': 'PREFLIGHT'}
    completed = False
    try:
        capability.check()
        with capability.mutation():
            job.status = 'GENERATING'
            job.route_decisions.append(decision)
            capability.persist()
        chapter, context, request = manager.prepare_author_request(job, route)
        from ..model_center.discovery_bridge import LocalTextAdapter
        if type(capability.adapter) is LocalTextAdapter:
            request = replace(request, preparation_guard=lambda: capability.authorize(route))
        if manager.snapshot_required:
            snapshot = manager._save_context_snapshot(job, chapter, context, f'{role}:v1', route.model,
                actor_id=job.actor_id, session_id=job.session_id, scope_type=job.scope_type,
                scope_id=job.scope_id, generation_id=job.id, cloud=False)
            with capability.mutation():
                job.context_snapshot_id = snapshot['id']
                capability.persist()
        capability.authorize(route)
        decision['status'] = 'DISPATCHED'
        # The original TextModelNode invokes the original registered adapter.
        # Iteration may block: it never runs under an original owner lease.
        for event in capability.node.stream(TextModelNodeInput(request)):
            if event.job_id != job.id or completed:
                raise ValueError('GENERATION_WRITER_EVENT_BINDING_CHANGED')
            if event.event_type == 'generation.completed':
                if event.response is None:
                    raise ValueError('GENERATION_WRITER_COMPLETION_MISSING')
                # Capture real execution facts before live publication checks.
                with job.condition:
                    job.usage = asdict(event.response.usage) if event.response.usage else None
                    job.usage_status = 'REPORTED' if event.response.usage else 'UNKNOWN'
                    job.execution_mode = event.response.execution_mode
                    job.provider_reference_id = event.response.provider_reference_id
                    job.execution_outcome = 'COMPLETED'
                    job.provider, job.model = route.provider, route.model
                    decision['status'] = 'COMPLETED'
                completed = True
                capability.authorize(route)
                if (event.response.provider_id, event.response.model_id) != capability.route:
                    raise ValueError('GENERATION_WRITER_RESPONSE_ROUTE_CHANGED')
                check_generation_bounds(job, completion_text=event.response.text)
            elif event.event_type == 'generation.failed':
                capability.authorize(route)
                raise ModelRuntimeError(event.error_code or RuntimeErrorCode.GENERATION_FAILED,
                                        '生成失败，请审核任务记录。')
            elif event.event_type == 'generation.cancelled':
                raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, '生成已停止。')
            elif event.event_type == 'generation.delta' and event.delta:
                with capability.mutation():
                    if job.status != 'GENERATING':
                        raise ValueError('GENERATION_WRITER_STATE_CHANGED')
                    check_generation_bounds(job, delta=event.delta)
                    job.output += event.delta
                    capability.persist()
        if not completed:
            raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '模型连接中断，草稿未完成。')
        # Continue/rewrite retain their original deferred snapshot. Never skip
        # this original effect just because collaboration snapshots are off.
        if role == 'writer' and not manager.snapshot_required:
            manager._save_context_snapshot(job, chapter, context, 'writer:v1', route.model)
        check_generation_bounds(job)
        issues = deterministic_review(job.output, context)
        with capability.mutation():
            if job.status != 'GENERATING':
                raise ValueError('GENERATION_WRITER_STATE_CHANGED')
            job.issues = issues
            job.latency_ms = int((time.monotonic() - started) * 1000)
            job.status = 'COMPLETED'
            capability.persist()
        runtime_log.write(generation_id=job.id, novel_id=job.novel_id, chapter_id=job.chapter_id,
            agent=role, provider=job.provider, model=job.model, status=job.status, latency_ms=job.latency_ms)
    except Exception as exc:
        if not completed:
            decision['status'] = 'FAILED'
        if isinstance(exc, ModelRuntimeError):
            code, message = exc.code.value, exc.safe_message
        else:
            code, message = 'GENERATION_WRITER_UNCONFIRMED', '生成未能完成确认，请核对任务记录。'
        if capability.refused or isinstance(exc, _OrdinaryRequestAuthorizationFailed):
            code, message = 'GENERATION_AUTHORITY_REVOKED', '生成授权或来源已改变，未采用生成内容。'
        decision['error_code'] = code
        job.latency_ms = int((time.monotonic() - started) * 1000)
        _fail(capability, code, message)
