"""Private original Broker inventory for admitted local image understanding.

Runtime readiness is not durable Job availability. No price, measured latency,
hardware fit, quality, reservation or dispatch permission is fabricated here.
"""
from dataclasses import dataclass
import re
from weakref import WeakSet

from ..model_runtime import Modality
from ..vision_analysis_runtime import VisionAnalysisModelNode
from ..local_ollama_vision import LocalOllamaVisionProvider
from .planning import digest

PROFILE = 'LOCAL_VISION_IMAGE_UNDERSTANDING_V3'


# In-process host authority only. Persisted identities are evidence, never a way
# to recreate this capability after restart. The caller seals this inside the
# original Director IMAGE preparation capability after checking Host authority.
_issued = WeakSet()


@dataclass(frozen=True, eq=False)
class _VisionBrokerAuthority:
    broker: object
    nid: str
    scope_digest: str
    actor: str
    incarnation: str
    binding_digest: str
    guard: object
    provider_id: str
    model_id: str
    route_digest: str

    def __copy__(self):
        raise TypeError('BROKER_IMAGE_AUTHORITY_NOT_COPYABLE')

    def __deepcopy__(self, memo):
        raise TypeError('BROKER_IMAGE_AUTHORITY_NOT_COPYABLE')

    def __reduce__(self):
        raise TypeError('BROKER_IMAGE_AUTHORITY_NOT_SERIALIZABLE')


def _issue_authority(broker, nid, scope, actor, incarnation, binding_digest, guard,
                     *, provider_id, model_id, route_digest):
    if (not callable(guard) or not all(isinstance(v, str) and v for v in
            (nid, actor, incarnation, provider_id, model_id))
            or not all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v)
                       for v in (binding_digest, route_digest))
            or broker._native_ocr_owner(nid) != incarnation):
        raise ValueError('BROKER_IMAGE_AUTHORITY_REQUIRED')
    guard()
    authority = _VisionBrokerAuthority(broker, nid, digest(scope), actor, incarnation,
        binding_digest, guard, provider_id, model_id, route_digest)
    _issued.add(authority)
    return authority


def assert_authority(broker, authority, *, nid=None, scope=None, actor=None,
                     row=None, current=True):
    if (type(authority) is not _VisionBrokerAuthority or authority not in _issued
            or authority.broker is not broker
            or nid is not None and authority.nid != nid
            or scope is not None and authority.scope_digest != digest(scope)
            or actor is not None and authority.actor != actor
            or broker._native_ocr_owner(authority.nid) != authority.incarnation):
        raise ValueError('BROKER_IMAGE_AUTHORITY_REQUIRED')
    if row is not None and (row.get('candidate_profile') != PROFILE
            or row.get('director_image_incarnation') != authority.incarnation
            or row.get('director_image_binding_digest') != authority.binding_digest):
        raise ValueError('BROKER_IMAGE_AUTHORITY_MISMATCH')
    if row is not None:
        route = row.get('chosen') if 'chosen' in row else row
        # NO_LEGAL_ROUTE is allowed only at preview creation, not consumption.
        if (not isinstance(route, dict) or route.get('provider_id') != authority.provider_id
                or route.get('model_id') != authority.model_id
                or route.get('route_id') != digest(['local-vision-v3', authority.provider_id, authority.model_id])):
            raise ValueError('BROKER_IMAGE_AUTHORITY_MISMATCH')
    if current:
        authority.guard()
    return authority


def candidates(runtime, *, broker=None, authority=None):
    admitted = assert_authority(broker, authority) if authority is not None else None
    node = runtime.generation_runtime.vision_analysis_node
    if (type(node) is not VisionAnalysisModelNode or node.providers is not runtime.provider_registry
            or node.models is not runtime.model_registry):
        return []
    result = []
    for model in runtime.model_registry.descriptors():
        if model.modality is not Modality.VISION or 'IMAGE_UNDERSTANDING' not in model.capabilities:
            continue
        try:
            provider = runtime.provider_registry.resolve(model.provider_id)
            if type(provider) is not LocalOllamaVisionProvider: continue
            binding = node.binding(model.provider_id, model.model_id)
            route = binding['route']
            permitted = admitted is not None and (
                model.provider_id == admitted.provider_id and model.model_id == admitted.model_id
                and binding['route_digest'] == admitted.route_digest)
            if admitted is not None and not permitted:
                continue
            # Public candidate data never contains local endpoints/configuration.
            identity = {'vision_binding_digest': binding['route_digest'], 'adapter_hash': binding['adapter_hash'],
                'provider_uuid': binding['provider_uuid'], 'model_uuid': binding['model_uuid'],
                'execution_node_uuid': binding['execution_node_uuid'], 'model_version': route['model_sha256'],
                'model_sha256': route['model_sha256'], 'admission_digest': route['admission_digest'],
                'source_locality': 'LOCAL_VERIFIED', 'license_confirmed': True,
                'license_state': 'HOST_CONFIRMED', 'capability': {'operations': ['IMAGE_UNDERSTANDING']}}
            result.append({'route_id': digest(['local-vision-v3', model.provider_id, model.model_id]),
                'provider_id': model.provider_id, 'model_id': model.model_id, 'display_name': model.display_name,
                'capability': 'VISION', 'context_window': model.context_window,
                'cloud': False, 'synthetic': False, 'available': permitted,
                'runtime_available': True, 'execution_available': permitted,
                'reasons': [] if permitted else ['DIRECTOR_IMAGE_JOB_NOT_INTEGRATED'],
                'fingerprint': digest(identity), 'binding_hash': digest([id(provider), digest(identity)]),
                'identity': identity, 'verification': 'HOST_LOCAL_CAPABILITY_ADMITTED_INFERENCE_NOT_RUN',
                'executor': 'original.job_manager.director_image_v3' if permitted else 'original.job_manager.director_image_not_integrated',
                'candidate_profile': PROFILE, 'quality_verification': 'NOT_RUN'})
        except (ValueError, RuntimeError, TypeError, KeyError, AttributeError):
            continue
    if admitted is not None:
        assert_authority(broker, admitted)
    return result
