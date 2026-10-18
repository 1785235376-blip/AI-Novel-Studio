"""Unmounted IMAGE V3 coordinator over original owners; adoption unavailable."""
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from .director_image_source import DirectorImageSources, MAX_IMAGE_BYTES
from .director_image_binding import ImageBinding, ImageTarget
from .director_image_execution import _DirectorImageCapability, _SEAL
from .director_terminal_evidence import digest
from .director_image_terminal import FIELD, validate, parse_advice
from ..experimental.common import new_row, change_row, check_version
from ..director_vision_wire import VisionWireParameters

COLLECTION = 'creative_director_proposals_v2'
CONTRACT = 'DIRECTOR_IMAGE_PROPOSAL_V3'
_owner = ContextVar('director_image_owner_phase', default=None)

class DirectorImageCoordinator:
    def __init__(self, workspace, manager, broker, runtime):
        self.workspace,self.documents,self.store = workspace,workspace.creative,workspace.store
        self.sources = DirectorImageSources(workspace)
        self.manager,self.broker = manager,broker
        self.node = runtime.generation_runtime.vision_analysis_node

    def basic(self, guard, host):
        from ..model_center.discovery_authority import DiscoveryAuthority
        from ..experimental.flags import require_flag
        if type(host) is not DiscoveryAuthority or not callable(guard): raise ValueError('DIRECTOR_IMAGE_HOST_REQUIRED')
        for flag in ('ai_execution_v2','narrative_production_v2','asset_lineage_v2','model_broker_v2','author_context_inspector_v2'):
            require_flag(flag)
        host.guard(); guard()

    def target(self, source, target):
        document = self.documents.get(source.project_id,source.scope.model_dump(),target.document_id)
        if (document['mode'] != 'DIRECTOR' or document['status'] != 'DRAFT'
                or document['version'] != target.version or self.documents.document_digest(document) != target.digest
                or target.scene_id not in {scene['id'] for scene in document['scenes']}):
            raise ValueError('DIRECTOR_IMAGE_TARGET_CHANGED')
        return document

    def check(self, binding, guard, host):
        self.basic(guard,host)
        source = binding.source
        if _owner.get() == (id(self),digest(binding.model_dump())):
            if self.store.incarnation(source.project_id) != source.project_incarnation:
                raise ValueError('DIRECTOR_IMAGE_OWNER_CHANGED')
            row,content = self.workspace.pinned_content(source.project_id,source.scope.model_dump(),
                {'id':source.asset.asset_id,'version':source.asset.version,'digest':source.asset.sha256,'asset_kind':'image'},
                max_bytes=MAX_IMAGE_BYTES,guard=lambda:self.basic(guard,host))
            if sha256(content).hexdigest() != source.asset.sha256 or len(content) != source.byte_count or row['media_type'] != source.media_type:
                raise ValueError('DIRECTOR_IMAGE_SOURCE_CHANGED')
            self.target(source,binding.target)
        else:
            with self.sources.read(source.project_id,source.scope.model_dump(),source.actor_id,source.asset.model_dump(),
                    guard=lambda:self.basic(guard,host),expected=source.model_dump()):
                self.target(source,binding.target)
        self.basic(guard,host)

    def owner_lease(self, binding):
        @contextmanager
        def lease():
            source = binding.source
            key = self.store.key(source.project_id,source.scope.model_dump())
            if key not in getattr(self.store.store._local,'active',{}):
                raise ValueError('DIRECTOR_IMAGE_SCOPE_LEASE_REQUIRED')
            with self.store.existing_owner_only(), self.workspace._asset_scope(source.project_id,source.scope.model_dump()):
                if self.store.incarnation(source.project_id) != source.project_incarnation:
                    raise ValueError('DIRECTOR_IMAGE_OWNER_CHANGED')
                token = _owner.set((id(self),digest(binding.model_dump())))
                try: yield
                finally: _owner.reset(token)
        return lease

    @contextmanager
    def transaction(self, binding, guard, host):
        source = binding.source
        with ExitStack() as leases:
            with self.store.store.transaction(source.project_id,source.scope.model_dump()) as raw:
                leases.enter_context(self.owner_lease(binding)())
                self.check(binding,guard,host)
                yield raw
                self.check(binding,guard,host)
                self.documents.proposals._capacity(self.store._view(raw,source.project_incarnation))

    def preview(self, nid, scope, actor, *, asset, target, provider_id, model_id, instruction, host, guard):
        self.basic(guard,host)
        if not isinstance(instruction,str) or not instruction.strip() or len(instruction.encode()) > 8000:
            raise ValueError('DIRECTOR_IMAGE_INSTRUCTION_INVALID')
        source = self.sources.capture(nid,scope,actor,asset,guard=lambda:self.basic(guard,host))
        route = self.node.binding(provider_id,model_id)
        parameters = VisionWireParameters()
        prompt = ('Return only JSON with contract DIRECTOR_IMAGE_ADVICE_V3, observations (1-8 strings), '
            'suggestions (1-8 strings), uncertainty (string). Each string <=2000 characters. '
            'Observations are uncertain model descriptions of the supplied image, not verified facts. '
            'Suggestions are hypothetical directing choices, not measurements. No identification of people.\n'+instruction)
        payload = {'source':source,'target':ImageTarget.model_validate(target).model_dump(),
            'provider_id':provider_id,'model_id':model_id,'route_digest':route['route_digest'],
            'prompt':prompt,'parameters':parameters.model_dump()}
        binding = ImageBinding(source=source,target=payload['target'],route_digest=route['route_digest'],preview_digest=digest(payload))
        self.check(binding,guard,host)
        with self.transaction(binding,guard,host) as state:
            row = new_row(nid,scope,actor,{'contract':CONTRACT,'project_incarnation':binding.source.project_incarnation,
                'status':'PREVIEW','binding':binding.model_dump(),'preview':payload,'job_id':None,
                'adoption_available':False,'adoption_blocker':'DIRECTOR_IMAGE_ADOPTION_NOT_INTEGRATED'})
            state['collections'].setdefault(COLLECTION,{})[row['id']] = row
        return deepcopy(row)

    def _row(self, nid, scope, actor, rid):
        row = self.store.read(nid,scope)['collections'].get(COLLECTION,{}).get(rid)
        if not row or row.get('contract') != CONTRACT or row.get('created_by') != actor or row.get('scope') != scope:
            raise FileNotFoundError(rid)
        return row

    def dispatch(self,nid,scope,actor,rid,*,expected_version,reviewed_preview_digest,host,guard):
        row = self._row(nid,scope,actor,rid); check_version(row,expected_version)
        binding = ImageBinding.model_validate(row['binding']); preview = row['preview']
        if (row['status'] != 'PREVIEW' or row.get('job_id') is not None
                or reviewed_preview_digest != binding.preview_digest or digest(preview) != binding.preview_digest):
            raise ValueError('DIRECTOR_IMAGE_EXACT_PREVIEW_REQUIRED')
        cap = _DirectorImageCapability(_SEAL,self,binding,host,guard,preview['provider_id'],preview['model_id'],
            preview['prompt'],VisionWireParameters.model_validate(preview['parameters']),
            (datetime.now(timezone.utc)+timedelta(seconds=120)).isoformat())
        job = self.manager._prepare_director_image_job(cap)
        from ..experimental.local_vision_broker import _issue_authority
        cap.broker_authority = _issue_authority(self.broker,nid,scope,actor,binding.source.project_incarnation,
            job.expected_request_digest,cap.current,provider_id=cap.provider_id,model_id=cap.model_id,route_digest=binding.route_digest)
        decision = self.broker.preview(nid,scope,actor,{'capability':'VISION','profile':'LOCAL_ONLY','task_type':'FRAME_ANALYSIS',
            'policy':'CUSTOM','preferred_route':digest(['local-vision-v3',cap.provider_id,cap.model_id])},
            guard=cap.current,local_vision_only=True,vision_authority=cap.broker_authority,owner_lease=self.owner_lease(binding))
        if decision.get('status') != 'PREVIEW': raise ValueError('DIRECTOR_IMAGE_BROKER_ADMISSION_BLOCKED')
        cap.reservation = self.broker.reserve(nid,scope,actor,decision['id'],decision['version'],rid,job.id,
            guard=cap.current,authorization_digest=job.expected_request_digest,owner_lease=self.owner_lease(binding),vision_authority=cap.broker_authority)
        cap.proposal_id = rid
        try:
            with self.transaction(binding,guard,host) as state:
                current = state['collections'][COLLECTION][rid]; check_version(current,expected_version)
                if current['status'] != 'PREVIEW' or current.get('job_id'): raise ValueError('DIRECTOR_IMAGE_ALREADY_DISPATCHED')
                change_row(current,actor,expected_version,lambda value:value.update(status='DISPATCHED',job_id=job.id,
                    request_digest=job.expected_request_digest,reservation_id=cap.reservation['id']))
            self.manager._start_director_image_job(job)
        except Exception:
            if job.id not in self.manager.jobs:
                job.status = 'FAILED'; cap.terminal(job)
            raise
        return job

    def prepare_pending(self,nid,scope,actor,rid,*,expected_version,host,guard):
        row = self._row(nid,scope,actor,rid)
        binding = ImageBinding.model_validate(row['binding'])
        with self.transaction(binding,guard,host) as state:
            current = state['collections'][COLLECTION][rid]; check_version(current,expected_version)
            if current['status'] not in {'DISPATCHED','PENDING_REVIEW'}: raise ValueError('DIRECTOR_IMAGE_PENDING_UNAVAILABLE')
            saved = self.manager.persistence.get(current['job_id']); evidence = validate(saved,saved.get(FIELD))
            if saved['expected_request_digest'] != current['request_digest'] or saved['director_image_binding'] != binding.model_dump():
                raise ValueError('DIRECTOR_IMAGE_TERMINAL_CHANGED')
            ledger = self.broker.get(nid,scope,self.broker.LEDGER,current['reservation_id'])
            if ledger != evidence['accounting']: raise ValueError('DIRECTOR_IMAGE_ACCOUNTING_CHANGED')
            pending = {'contract':'DIRECTOR_IMAGE_PENDING_V3','terminal_digest':digest(evidence),
                'source':binding.source.model_dump(),'target':binding.target.model_dump(),
                'advice':parse_advice(saved['output']),'accounting_status':ledger['status'],
                'adoption_available':False,'adoption_blocker':'DIRECTOR_IMAGE_ADOPTION_NOT_INTEGRATED',
                'observations_verified':False,'quality_verification':'HUMAN_REVIEW_REQUIRED'}
            if current['status'] == 'PENDING_REVIEW':
                if current.get('pending') != pending: raise ValueError('DIRECTOR_IMAGE_PENDING_CHANGED')
            else:
                change_row(current,actor,expected_version,lambda value:value.update(status='PENDING_REVIEW',pending=pending))
            return deepcopy(current)

    def cancel(self,nid,scope,actor,rid,*,host,guard):
        row = self._row(nid,scope,actor,rid); binding = ImageBinding.model_validate(row['binding'])
        self.check(binding,guard,host)
        job = self.manager.get(row['job_id'])
        cap = job.director_image_authority
        from .director_image_execution import require_capability
        require_capability(self.manager,job,started=True)
        if job.status in self.manager.terminal: raise ValueError('DIRECTOR_IMAGE_NOT_RUNNING')
        job.cancelled.set()
        return {'job_id':job.id,'state':'CANCELLATION_REQUESTED','upstream_stopped':False}

    def adopt(self,*args,**kwargs):
        raise ValueError('DIRECTOR_IMAGE_ADOPTION_NOT_INTEGRATED')
