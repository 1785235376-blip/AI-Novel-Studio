"""Private IMAGE invocation inside the existing JobManager worker."""
from copy import deepcopy
from datetime import datetime, timezone
import time
from uuid import uuid4
from .director_image_binding import ImageBinding, OPERATION, ORIGIN
from .director_terminal_evidence import digest

_SEAL = object()
IDENTITY = ('id','operation','novel_id','chapter_id','profile','actor_id','scope','experimental_origin',
    'director_image_binding','expected_request_digest','requested_provider','requested_model',
    'generation_deadline','generation_max_output_bytes','instruction','source',
    'creative_director_binding','graph_binding','adaptation_binding','research_ocr_binding')

class _DirectorImageCapability:
    def __init__(self, seal, coordinator, binding, host, guard, provider_id, model_id, prompt, parameters, deadline):
        from ..model_center.discovery_authority import DiscoveryAuthority
        if seal is not _SEAL or type(host) is not DiscoveryAuthority or not callable(guard):
            raise ValueError('DIRECTOR_IMAGE_HOST_REQUIRED')
        self.coordinator, self.binding, self.host, self.guard = coordinator, binding, host, guard
        self.provider_id, self.model_id, self.prompt, self.parameters = provider_id, model_id, prompt, parameters
        self.deadline = deadline
        self.manager, self.node = coordinator.manager, coordinator.node
        self.provider = self.node.providers.resolve(provider_id)
        self.persistence = self.manager.persistence
        self.job = None
        self.started = self.worker_claimed = False
        self.publication_state = 'PENDING'
        self.identity = None
        self.reservation = self.accounting = self.broker_authority = None
        self.proposal_id = None
        self._host_identity = (id(host),id(guard),id(coordinator))
        self._payload_identity = self.payload_identity()
        self.current()

    def payload_identity(self):
        return digest({'binding':self.binding.model_dump(),'provider':self.provider_id,'model':self.model_id,
            'prompt':self.prompt,'parameters':self.parameters.model_dump(),'deadline':self.deadline})

    def current(self):
        if self._host_identity != (id(self.host),id(self.guard),id(self.coordinator)) or self.payload_identity() != self._payload_identity:
            raise ValueError('DIRECTOR_IMAGE_INVOCATION_CHANGED')
        from .ai_execution import require_execution
        require_execution(); self.host.guard(); self.guard()
        if datetime.now(timezone.utc) >= datetime.fromisoformat(self.deadline):
            raise ValueError('DIRECTOR_IMAGE_DEADLINE')
        if (self.manager is not self.coordinator.manager or self.persistence is not self.manager.persistence
                or self.node.providers.resolve(self.provider_id) is not self.provider
                or self.node.binding(self.provider_id,self.model_id)['route_digest'] != self.binding.route_digest):
            raise ValueError('DIRECTOR_IMAGE_ROUTE_CHANGED')
        self.coordinator.check(self.binding, self.guard, self.host)
        if self.job is not None:
            job = self.job
            if (job.creative_execution_authority is not None or job.research_ocr_execution_authority is not None
                    or job.prepared_text_invocation is not None or job.director_image_authority is not self or job.cancelled is not self.cancellation
                    or job.request_authorization is not self.authorizer or job.before_dispatch is not self.before_hook
                    or job.on_terminal is not self.terminal_hook
                    or any(getattr(job,k) != v for k,v in self.identity.items())):
                raise ValueError('DIRECTOR_IMAGE_JOB_CHANGED')
            if job.cancelled.is_set(): raise ValueError('DIRECTOR_IMAGE_CANCELLED')

    def before_dispatch(self):
        self.current()
        s = self.binding.source
        self.coordinator.broker.guard_dispatch(s.project_id,s.scope.model_dump(),s.actor_id,
            self.reservation['id'],self.job.id,guard=self.current,
            owner_lease=self.coordinator.owner_lease(self.binding),vision_authority=self.broker_authority)
        self.current()

    def terminal(self, job=None):
        job = self.job if job is None else job
        if job is not self.job: raise ValueError('DIRECTOR_IMAGE_JOB_CHANGED')
        s = self.binding.source
        self.accounting = self.coordinator.broker.finalize(s.project_id,s.scope.model_dump(),s.actor_id,
            self.reservation['id'],job.id,job.status,owner_lease=self.coordinator.owner_lease(self.binding),
            vision_authority=self.broker_authority)


def prepare(manager, capability):
    from ..jobs import Job
    if type(capability) is not _DirectorImageCapability or capability.manager is not manager or capability.job is not None:
        raise ValueError('DIRECTOR_IMAGE_PRIVATE_OWNER_REQUIRED')
    capability.current(); source = capability.binding.source
    job = Job(str(uuid4()),OPERATION,source.project_id,None,'','LOCAL_ONLY',
        requested_provider=capability.provider_id,requested_model=capability.model_id,status='PREPARED',
        actor_id=source.actor_id,scope=source.scope.model_dump(),experimental_origin=ORIGIN,
        director_image_binding=capability.binding.model_dump(),generation_max_output_bytes=128000,
        generation_deadline=capability.deadline)
    job.expected_request_digest = digest({'binding':job.director_image_binding,
        'provider':capability.provider_id,'model':capability.model_id,'prompt':capability.prompt,
        'parameters':capability.parameters.model_dump(),'deadline':capability.deadline})
    capability.job = job
    capability.before_hook, capability.terminal_hook, capability.authorizer = capability.before_dispatch, capability.terminal, capability.current
    job.before_dispatch,job.on_terminal,job.request_authorization = capability.before_hook,capability.terminal_hook,capability.authorizer
    job.dispatch_hooks_required = True
    capability.cancellation = job.cancelled
    job.director_image_authority = capability
    capability.identity = {k:deepcopy(getattr(job,k)) for k in IDENTITY}
    capability.current()
    return job


def require_capability(manager, job, *, started):
    cap = job.director_image_authority
    if type(cap) is not _DirectorImageCapability or cap.manager is not manager or cap.job is not job or cap.started is not started:
        raise ValueError('DIRECTOR_IMAGE_PRIVATE_OWNER_REQUIRED')
    cap.current()
    return cap


def run(manager, job):
    from ..vision_analysis_runtime import VisionAnalysisRequest
    from .director_image_terminal import parse_advice, publish
    cap = job.director_image_authority
    if type(cap) is not _DirectorImageCapability or cap.manager is not manager or cap.job is not job or not cap.started:
        raise ValueError('DIRECTOR_IMAGE_PRIVATE_OWNER_REQUIRED')
    with job.condition:
        if cap.worker_claimed: raise ValueError('DIRECTOR_IMAGE_ALREADY_STARTED')
        cap.worker_claimed = True
    try:
        cap.current(); job.status = 'GENERATING'; manager._persist(job)
        s = cap.binding.source
        with cap.coordinator.sources.read(s.project_id,s.scope.model_dump(),s.actor_id,s.asset.model_dump(),
                guard=lambda:(cap.host.guard(),cap.guard()),expected=s.model_dump()) as (_, content):
            raw = content
        cap.current()
        remaining = (datetime.fromisoformat(cap.deadline)-datetime.now(timezone.utc)).total_seconds()
        request = VisionAnalysisRequest(cap.provider_id,cap.model_id,job.id,cap.binding.route_digest,s,raw,
            cap.prompt,cap.parameters,time.monotonic()+remaining,cap.current,job.cancelled)
        cap.before_dispatch()
        result = cap.node.execute(request)
        cap.current(); parse_advice(result.text)
        job.output,job.provider,job.model = result.text,result.provider_id,result.model_id
        job.status = job.execution_outcome = 'COMPLETED'
    except Exception:
        job.output = ''
        job.status = job.execution_outcome = 'CANCELLED' if job.cancelled.is_set() else 'FAILED'
        job.error_code = 'DIRECTOR_IMAGE_EXECUTION_FAILED'
        job.error = 'Image analysis unavailable; no automatic replay.'
    manager._finish_terminal_hook(job)
    try:
        if job.status == 'COMPLETED':
            cap.current()
            if job.terminal_hook_status != 'COMPLETED': raise ValueError('DIRECTOR_IMAGE_ACCOUNTING_UNCONFIRMED')
            publish(manager,job,cap,cap.accounting)
        else: manager._persist(job)
    except Exception:
        # A successful write followed by lost acknowledgement is not overwritten.
        cap.publication_state = 'UNKNOWN'
        job.output = ''; job.status = 'FAILED'; job.error_code = 'DIRECTOR_IMAGE_TERMINAL_UNKNOWN'
    with job.condition: job.condition.notify_all()
