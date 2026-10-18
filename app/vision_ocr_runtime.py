"""Bounded OCR model seam over the original host registries.

No provider is registered, installed, discovered, launched or called on creation.
This seam does not admit Research jobs: their existing synthetic-only dispatch
fence remains closed until an original JobManager integration supplies authority.
Input validation here is a byte envelope, not image decoding or OCR quality proof.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
import hashlib
import re
from threading import Event
from typing import Callable, Protocol

from .audio_processing_runtime import _identity, audio_digest
from .model_runtime import ModelRuntimeError, Modality, RuntimeErrorCode
from .model_center.discovery_types import local_endpoint
from .stable_identity import canonical_model_identity_key

HASH = re.compile(r'^[a-f0-9]{64}$')


def _hash(value):
    return isinstance(value, str) and HASH.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class VisionOCRRequest:
    provider_id: str
    model_id: str
    content: bytes
    media_type: str
    language: str
    source_digest: str
    route_digest: str
    request_id: str
    dispatch_guard: Callable[[], None] = field(repr=False, compare=False)
    cancellation: Event | None = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        _identity(self.provider_id); _identity(self.model_id); _identity(self.request_id)
        if (not isinstance(self.content, bytes) or not 0 < len(self.content) <= 4 * 1024 * 1024
                or not isinstance(self.media_type, str) or self.media_type not in {'image/png', 'image/jpeg'}
                or not isinstance(self.language, str) or not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z]{2,8})?', self.language)
                or not _hash(self.source_digest) or not _hash(self.route_digest)
                or hashlib.sha256(self.content).hexdigest() != self.source_digest
                or not callable(self.dispatch_guard)
                or self.cancellation is not None and not isinstance(self.cancellation, Event)):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'OCR 请求须绑定明确的图片字节、语言、来源与准入')


@dataclass(frozen=True, slots=True)
class VisionOCRResponse:
    provider_id: str
    model_id: str
    text: str
    receipt: dict


class VisionOCRProvider(Protocol):
    supports_dispatch_guard: bool
    def route_snapshot(self) -> dict: ...
    def recognize_image(self, request: VisionOCRRequest) -> VisionOCRResponse: ...


class VisionOCRModelNode:
    type_id = 'builtin.vision_ocr_model'
    contract_version = 1

    def __init__(self, providers, models):
        self.providers, self.models = providers, models

    def binding(self, provider_id, model_id):
        _identity(provider_id); _identity(model_id)
        provider = self.providers.resolve(provider_id)
        model = self.models.resolve(provider_id, model_id, Modality.VISION)
        descriptor = next((row for row in self.providers.descriptors() if row.provider_id == provider_id), None)
        if (descriptor is None or descriptor.provider_type != 'local' or Modality.VISION not in descriptor.supported_modalities
                or 'OCR' not in model.capabilities or getattr(provider, 'supports_dispatch_guard', False) is not True
                or not callable(getattr(provider, 'route_snapshot', None)) or not callable(getattr(provider, 'recognize_image', None))):
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, '须使用原注册表内明确支持 OCR 的本地视觉模型')
        identities = self.providers.identity_store
        if (identities is None or self.models.identity_store is None or identities.path != self.models.identity_store.path
                or descriptor.identity_id is None or model.identity_id is None
                or identities.get('provider', provider_id) != descriptor.identity_id
                or identities.get('model', canonical_model_identity_key(provider_id, model_id)) != model.identity_id):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'OCR 模型须具有原主机持久身份')
        execution_id = identities.get('execution_node', 'local')
        if execution_id is None:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, '原主机执行节点尚未注册')
        route = provider.route_snapshot()
        fields = {'schema', 'provider_id', 'model_id', 'endpoint', 'model_sha256', 'admission_digest', 'languages', 'adapter_version'}
        if (not isinstance(route, dict) or set(route) != fields or route.get('schema') != 'local-vision-ocr-admission/1'
                or route.get('provider_id') != provider_id or route.get('model_id') != model_id
                or not isinstance(route.get('languages'), list) or not 1 <= len(route['languages']) <= 32
                or any(not isinstance(x, str) or not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z]{2,8})?', x) for x in route['languages'])
                or len(set(route['languages'])) != len(route['languages'])
                or not isinstance(route.get('adapter_version'), str) or not 1 <= len(route['adapter_version']) <= 160
                or not _hash(route.get('model_sha256')) or not _hash(route.get('admission_digest'))):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'OCR 模型缺少当前可信准入回执')
        try:
            local = isinstance(route['endpoint'], str) and local_endpoint(route['endpoint']) == route['endpoint']
        except (ValueError, TypeError):
            local = False
        if not local:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, 'OCR 运行时必须使用明确的主机本地地址')
        value = {'schema': 'original-vision-ocr-binding/1', 'provider_id': provider_id, 'model_id': model_id,
            'provider_uuid': str(descriptor.identity_id), 'model_uuid': str(model.identity_id), 'execution_node_uuid': str(execution_id),
            'route': copy.deepcopy(route), 'model_capabilities': sorted(model.capabilities),
            'provider_state': {'configured': descriptor.configured, 'available': descriptor.available, 'health_status': descriptor.health_status}}
        value['route_digest'] = audio_digest(value)
        return value

    def execute(self, request: VisionOCRRequest) -> VisionOCRResponse:
        from .creative.ai_execution import require_execution
        require_execution()
        if not isinstance(request, VisionOCRRequest):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, 'OCR 请求类型无效')
        captured = self.binding(request.provider_id, request.model_id)
        if captured['route_digest'] != request.route_digest or request.language not in captured['route']['languages']:
            raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, 'OCR 路由或语言准入已变化，请重新核对')
        provider = self.providers.resolve(request.provider_id)
        def guard():
            require_execution()
            if request.cancellation is not None and request.cancellation.is_set():
                raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, '已停止 OCR')
            request.dispatch_guard()
            if self.binding(request.provider_id, request.model_id) != captured or self.providers.resolve(request.provider_id) is not provider:
                raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, 'OCR 模型或准入变化，输出已丢弃')
            require_execution()
        guard()
        response = provider.recognize_image(replace(request, dispatch_guard=guard))
        guard()
        fields = {'model_called', 'source_digest', 'input_sha256', 'route_digest', 'language', 'text_sha256'}
        valid = isinstance(response, VisionOCRResponse) and response.provider_id == request.provider_id and response.model_id == request.model_id and isinstance(response.text, str)
        if valid:
            try:
                raw = response.text.encode('utf-8') if isinstance(response.text, str) else b''
                valid = (bool(response.text.strip()) and len(raw) <= 256 * 1024 and '\x00' not in response.text
                    and isinstance(response.receipt, dict) and set(response.receipt) == fields
                    and response.receipt['model_called'] is True and response.receipt['source_digest'] == request.source_digest
                    and response.receipt['input_sha256'] == request.source_digest and response.receipt['route_digest'] == request.route_digest
                    and response.receipt['language'] == request.language
                    and response.receipt['text_sha256'] == hashlib.sha256(raw).hexdigest())
            except (UnicodeError, AttributeError):
                valid = False
        if not valid:
            raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, 'OCR 结果缺少当前来源绑定的有界完成回执')
        receipt = copy.deepcopy(response.receipt)
        receipt.update(provider_uuid=captured['provider_uuid'], model_uuid=captured['model_uuid'], execution_node_uuid=captured['execution_node_uuid'],
            model_sha256=captured['route']['model_sha256'], admission_digest=captured['route']['admission_digest'],
            automatic_canon=False, review_required=True, model_quality='NOT_RUN')
        return VisionOCRResponse(request.provider_id, request.model_id, response.text, receipt)
