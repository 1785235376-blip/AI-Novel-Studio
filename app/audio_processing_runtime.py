"""Source-bound local audio processing through the original model registries.

There is no route discovery, fallback, queue, credential store or process launch
here. The host must explicitly register and admit an installed local provider
and model. Caption tasks remain owned by SubtitleTimelineService.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
import re
from threading import Event
from typing import Callable, Literal, Protocol

from .model_runtime import ModelRuntimeError, Modality, RuntimeErrorCode
from .model_center.discovery_types import local_endpoint
from .stable_identity import canonical_model_identity_key

CAPABILITIES = {'ASR': 'TRANSCRIBE', 'FORCED_ALIGNMENT': 'FORCED_ALIGNMENT'}


def audio_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _identity(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 240 or value != value.strip() or any(ord(c) < 32 for c in value):
        raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, '音频模型标识无效')
    return value


@dataclass(frozen=True, slots=True)
class AudioProcessingRequest:
    provider_id: str
    model_id: str
    operation: Literal['ASR', 'FORCED_ALIGNMENT']
    media: bytes
    media_type: str
    language: str
    duration_ms: int
    source_digest: str
    route_digest: str
    request_id: str
    transcript: str = ''
    dispatch_guard: Callable[[], None] | None = field(default=None, repr=False, compare=False)
    cancellation: Event | None = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        _identity(self.provider_id); _identity(self.model_id); _identity(self.request_id)
        if (self.operation not in CAPABILITIES or not isinstance(self.media, bytes)
                or not 0 < len(self.media) <= 8 * 1024 * 1024
                or type(self.duration_ms) is not int or not 1 <= self.duration_ms <= 600_000
                or not isinstance(self.language, str) or not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z]{2,8})?|auto', self.language)
                or not isinstance(self.source_digest, str) or not re.fullmatch(r'[a-f0-9]{64}', self.source_digest)
                or not isinstance(self.route_digest, str) or not re.fullmatch(r'[a-f0-9]{64}', self.route_digest)
                or not callable(self.dispatch_guard) or not isinstance(self.transcript, str) or len(self.transcript) > 100_000
                or self.operation == 'ASR' and self.transcript
                or self.operation == 'FORCED_ALIGNMENT' and not self.transcript.strip()):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, '音频处理请求须具有明确的来源、准入和操作边界')


@dataclass(frozen=True, slots=True)
class AudioProcessingResponse:
    provider_id: str
    model_id: str
    segments: tuple[dict, ...]
    receipt: dict


class AudioProcessingProvider(Protocol):
    supports_dispatch_guard: bool
    def route_snapshot(self) -> dict: ...
    def process_audio(self, request: AudioProcessingRequest) -> AudioProcessingResponse: ...


class AudioProcessingModelNode:
    type_id = 'builtin.audio_processing_model'
    contract_version = 1

    def __init__(self, providers, models):
        self.providers, self.models = providers, models

    def binding(self, provider_id, model_id, operation):
        _identity(provider_id); _identity(model_id)
        if operation not in CAPABILITIES:
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, '音频处理操作不受支持')
        provider = self.providers.resolve(provider_id)
        model = self.models.resolve(provider_id, model_id, Modality.AUDIO)
        descriptor = next((row for row in self.providers.descriptors() if row.provider_id == provider_id), None)
        capability = CAPABILITIES[operation]
        if (descriptor is None or descriptor.provider_type != 'local' or Modality.AUDIO not in descriptor.supported_modalities
                or capability not in model.capabilities or getattr(provider, 'supports_dispatch_guard', False) is not True
                or not callable(getattr(provider, 'route_snapshot', None)) or not callable(getattr(provider, 'process_audio', None))):
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, '须使用原注册表中明确支持该操作的本地音频模型')
        identities = self.providers.identity_store
        if (identities is None or self.models.identity_store is None
                or identities.path != self.models.identity_store.path or descriptor.identity_id is None or model.identity_id is None
                or identities.get('provider', provider_id) != descriptor.identity_id
                or identities.get('model', canonical_model_identity_key(provider_id, model_id)) != model.identity_id):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, '音频模型须完成原主机持久身份注册')
        execution_identity = identities.get('execution_node', 'local')
        if execution_identity is None:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, '须使用已注册的原主机执行节点')
        route = provider.route_snapshot()
        fields = {'schema', 'provider_id', 'model_id', 'endpoint', 'model_sha256', 'admission_digest', 'operations', 'adapter_version'}
        if (not isinstance(route, dict) or set(route) != fields or route.get('schema') != 'local-audio-admission/1'
                or route.get('provider_id') != provider_id or route.get('model_id') != model_id
                or not isinstance(route.get('operations'), list) or not 1 <= len(route['operations']) <= 2
                or any(not isinstance(item, str) for item in route['operations']) or operation not in route['operations']
                or set(route['operations']) - set(CAPABILITIES)
                or not isinstance(route.get('adapter_version'), str) or not 1 <= len(route['adapter_version']) <= 160
                or any(not isinstance(route.get(key), str) or not re.fullmatch(r'[a-f0-9]{64}', route[key])
                       for key in ('model_sha256', 'admission_digest'))):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, '音频模型尚无当前可信本地准入回执')
        if local_endpoint(route['endpoint']) != route['endpoint']:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, '音频处理只允许明确的主机本地运行时')
        value = {'schema': 'original-audio-model-binding/1', 'provider_id': provider_id, 'model_id': model_id,
            'provider_uuid': str(descriptor.identity_id), 'model_uuid': str(model.identity_id),
            'execution_node_uuid': str(execution_identity), 'capability': capability, 'local': True,
            'route': copy.deepcopy(route), 'provider_state': {'configured': descriptor.configured, 'available': descriptor.available,
                'health_status': descriptor.health_status}, 'model_capabilities': sorted(model.capabilities)}
        value['route_digest'] = audio_digest(value)
        return value

    def execute(self, request: AudioProcessingRequest) -> AudioProcessingResponse:
        from .creative.ai_execution import require_execution
        require_execution()
        if not isinstance(request, AudioProcessingRequest):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, '音频处理请求无效')
        captured = self.binding(request.provider_id, request.model_id, request.operation)
        if captured['route_digest'] != request.route_digest:
            raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, '音频模型或准入已经变化，请重新提交任务')
        provider = self.providers.resolve(request.provider_id)
        def guard():
            require_execution()
            if request.cancellation is not None and request.cancellation.is_set():
                raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, '已停止音频处理')
            request.dispatch_guard()
            current = self.binding(request.provider_id, request.model_id, request.operation)
            if current != captured or self.providers.resolve(request.provider_id) is not provider:
                raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, '音频模型或准入已经变化，输出已丢弃')
            require_execution()
        from dataclasses import replace
        guard()
        response = provider.process_audio(replace(request, dispatch_guard=guard))
        guard()
        if (not isinstance(response, AudioProcessingResponse) or response.provider_id != request.provider_id
                or response.model_id != request.model_id or not isinstance(response.segments, tuple)
                or not 1 <= len(response.segments) <= 2000 or not isinstance(response.receipt, dict)
                or response.receipt.get('model_called') is not True
                or response.receipt.get('source_digest') != request.source_digest
                or response.receipt.get('input_sha256') != hashlib.sha256(request.media).hexdigest()
                or response.receipt.get('route_digest') != request.route_digest):
            raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '音频模型没有返回当前来源绑定的真实完成回执')
        receipt = copy.deepcopy(response.receipt)
        receipt.update(provider_uuid=captured['provider_uuid'], model_uuid=captured['model_uuid'],
            execution_node_uuid=captured['execution_node_uuid'], model_sha256=captured['route']['model_sha256'],
            admission_digest=captured['route']['admission_digest'])
        return AudioProcessingResponse(request.provider_id, request.model_id, copy.deepcopy(response.segments), receipt)
