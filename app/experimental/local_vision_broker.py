"""Private original Broker inventory for admitted local image understanding.

Runtime readiness is not durable Job availability. No price, measured latency,
hardware fit, quality, reservation or dispatch permission is fabricated here.
"""
from ..model_runtime import Modality
from ..vision_analysis_runtime import VisionAnalysisModelNode
from ..local_ollama_vision import LocalOllamaVisionProvider
from .planning import digest

PROFILE = 'LOCAL_VISION_IMAGE_UNDERSTANDING_V3'


def candidates(runtime):
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
                'cloud': False, 'synthetic': False, 'available': False,
                'runtime_available': True, 'execution_available': False,
                'reasons': ['DIRECTOR_IMAGE_JOB_NOT_INTEGRATED'],
                'fingerprint': digest(identity), 'binding_hash': digest([id(provider), digest(identity)]),
                'identity': identity, 'verification': 'HOST_LOCAL_CAPABILITY_ADMITTED_INFERENCE_NOT_RUN',
                'executor': 'original.job_manager.director_image_not_integrated',
                'candidate_profile': PROFILE, 'quality_verification': 'NOT_RUN'})
        except (ValueError, RuntimeError, TypeError, KeyError, AttributeError):
            continue
    return result
