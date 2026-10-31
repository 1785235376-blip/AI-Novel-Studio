"""Guarded IMAGE_UNDERSTANDING seam over original host registries.

No Job preparation/admission or durable terminal publication is provided. This
host-only callable is not dispatch authority; a later original Job integration
must supply the live guard. No public Director route uses this node.
"""
from dataclasses import dataclass, field, replace
from hashlib import sha256
import time
from threading import Event
from typing import Callable, Protocol

from .model_runtime import Modality
from .stable_identity import canonical_model_identity_key
from .creative.director_binding import Digest, Identifier, _Frozen
from .creative.director_image_source import DirectorImageSource, decode_image
from .director_vision_wire import VisionWireParameters, MAX_PROMPT_BYTES, MAX_RESPONSE_BYTES
from .creative.director_image_preview import digest


class _RequestIdentity(_Frozen):
    provider_id: Identifier
    model_id: Identifier
    job_id: Identifier
    route_digest: Digest


@dataclass(frozen=True, slots=True)
class VisionAnalysisRequest:
    provider_id: str
    model_id: str
    job_id: str
    route_digest: str
    source: DirectorImageSource
    content: bytes = field(repr=False)
    prompt: str = field(repr=False)
    parameters: VisionWireParameters
    deadline: float
    dispatch_guard: Callable[[], None] = field(repr=False, compare=False)
    cancellation: Event = field(repr=False, compare=False)

    def __post_init__(self):
        _RequestIdentity(provider_id=self.provider_id, model_id=self.model_id,
                         job_id=self.job_id, route_digest=self.route_digest)
        if (type(self.source) is not DirectorImageSource or type(self.parameters) is not VisionWireParameters
                or not callable(self.dispatch_guard) or not isinstance(self.cancellation, Event)
                or type(self.deadline) not in (int, float) or not 0 < self.deadline - time.monotonic() <= 180
                or type(self.prompt) is not str or not self.prompt.strip() or '\x00' in self.prompt
                or len(self.prompt.encode()) > MAX_PROMPT_BYTES):
            raise ValueError('VISION_ANALYSIS_REQUEST_INVALID')
        self.current()
        shape = decode_image(self.content, self.source.media_type, guard=self.current)
        if (shape != (self.source.width, self.source.height) or len(self.content) != self.source.byte_count
                or sha256(self.content).hexdigest() != self.source.asset.sha256):
            raise ValueError('VISION_ANALYSIS_SOURCE_CHANGED')

    def current(self):
        if self.cancellation.is_set(): raise ValueError('VISION_ANALYSIS_CANCELLED')
        if time.monotonic() >= self.deadline: raise ValueError('VISION_ANALYSIS_TIMEOUT')
        self.dispatch_guard()
        if self.cancellation.is_set(): raise ValueError('VISION_ANALYSIS_CANCELLED')
        if time.monotonic() >= self.deadline: raise ValueError('VISION_ANALYSIS_TIMEOUT')


@dataclass(frozen=True, slots=True)
class VisionAnalysisResponse:
    provider_id: str
    model_id: str
    source_digest: str
    route_digest: str
    text: str = field(repr=False)
    output_digest: str
    quality_verification: str = 'NOT_RUN'


class VisionAnalysisProvider(Protocol):
    def route_snapshot(self) -> dict: ...
    def analyze_image(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse: ...


class VisionAnalysisModelNode:
    type_id = 'builtin.vision_image_understanding_model'
    contract_version = 3

    def __init__(self, providers, models):
        self.providers, self.models = providers, models

    def binding(self, provider_id, model_id):
        from .local_ollama_vision import LocalOllamaVisionProvider
        from .experimental.model_broker import implementation_hash
        provider = self.providers.resolve(provider_id)
        model = self.models.resolve(provider_id, model_id, Modality.VISION)
        descriptor = next(row for row in self.providers.descriptors() if row.provider_id == provider_id)
        if (type(provider) is not LocalOllamaVisionProvider or descriptor.provider_type != 'local'
                or Modality.VISION not in descriptor.supported_modalities
                or 'IMAGE_UNDERSTANDING' not in model.capabilities):
            raise ValueError('VISION_ANALYSIS_ADAPTER_UNSUPPORTED')
        identities = self.providers.identity_store
        if (identities is None or self.models.identity_store is None or identities.path != self.models.identity_store.path
                or descriptor.identity_id is None or model.identity_id is None
                or identities.get('provider', provider_id) != descriptor.identity_id
                or identities.get('model', canonical_model_identity_key(provider_id, model_id)) != model.identity_id
                or identities.get('execution_node', 'local') is None):
            raise ValueError('VISION_ANALYSIS_IDENTITY_REQUIRED')
        route = provider.route_snapshot()
        if (route['provider_id'], route['model_id']) != (provider_id, model_id):
            raise ValueError('VISION_ANALYSIS_ROUTE_MISMATCH')
        value = {'contract': 'VISION_IMAGE_UNDERSTANDING_BINDING_V3', 'provider_id': provider_id,
            'model_id': model_id, 'provider_uuid': str(descriptor.identity_id), 'model_uuid': str(model.identity_id),
            'execution_node_uuid': str(identities.get('execution_node', 'local')),
            'adapter_hash': implementation_hash(LocalOllamaVisionProvider), 'route': route}
        value['route_digest'] = digest(value)
        return value

    def execute(self, request):
        from .creative.ai_execution import require_execution
        require_execution()
        if type(request) is not VisionAnalysisRequest:
            raise ValueError('VISION_ANALYSIS_TYPED_REQUEST_REQUIRED')
        request.current()
        captured = self.binding(request.provider_id, request.model_id)
        provider = self.providers.resolve(request.provider_id)
        if captured['route_digest'] != request.route_digest:
            raise ValueError('VISION_ANALYSIS_ROUTE_CHANGED')
        def current():
            require_execution(); request.current()
            if (self.providers.resolve(request.provider_id) is not provider
                    or self.binding(request.provider_id, request.model_id) != captured):
                raise ValueError('VISION_ANALYSIS_ROUTE_CHANGED')
        current()
        response = provider.analyze_image(replace(request, dispatch_guard=current))
        current()
        if (type(response) is not VisionAnalysisResponse
                or (response.provider_id, response.model_id, response.source_digest, response.route_digest) !=
                    (request.provider_id, request.model_id, request.source.asset.sha256, request.route_digest)
                or type(response.text) is not str or not response.text.strip()
                or len(response.text.encode()) > MAX_RESPONSE_BYTES or '\x00' in response.text
                or sha256(response.text.encode()).hexdigest() != response.output_digest
                or response.quality_verification != 'NOT_RUN'):
            raise ValueError('VISION_ANALYSIS_OUTPUT_INVALID')
        return response
