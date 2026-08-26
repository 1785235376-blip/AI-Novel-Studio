"""Provider-neutral model runtime foundation for built-in model nodes."""

from __future__ import annotations

import time
from threading import Event
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Protocol

from .providers import Generation, LLMProvider, ProviderError


class Modality(str, Enum):
    TEXT = "TEXT"
    EMBEDDING = "EMBEDDING"
    IMAGE = "IMAGE"
    VISION = "VISION"
    VIDEO = "VIDEO"


class RuntimeErrorCode(str, Enum):
    PROVIDER_NOT_FOUND = "PROVIDER_NOT_FOUND"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_DISABLED = "MODEL_DISABLED"
    CAPABILITY_NOT_SUPPORTED = "CAPABILITY_NOT_SUPPORTED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    INVALID_REQUEST = "INVALID_REQUEST"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    GENERATION_FAILED = "GENERATION_FAILED"
    CANCELLED = "CANCELLED"


class ModelRuntimeError(RuntimeError):
    def __init__(self, code: RuntimeErrorCode, message: str, *, retryable: bool = False,
                 provider_id: str | None = None, model_id: str | None = None,
                 metadata: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable
        self.provider_id = provider_id
        self.model_id = model_id
        self.metadata = dict(metadata or {})


@dataclass(frozen=True, slots=True)
class TextGenerationParameters:
    temperature: float | None = None
    max_output_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "temperature must be between 0 and 2")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "max_output_tokens must be positive")


@dataclass(frozen=True, slots=True)
class TextGenerationRequest:
    provider_id: str
    model_id: str
    prompt: str
    system_instruction: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)
    parameters: TextGenerationParameters = field(default_factory=TextGenerationParameters)
    structured_output_schema: Mapping[str, Any] | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    job_id: str | None = None
    cancellation: Event | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.provider_id or not self.model_id or not self.prompt.strip():
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "provider, model and prompt are required")


@dataclass(frozen=True, slots=True)
class GenerationUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class TextGenerationResponse:
    text: str
    finish_reason: str
    provider_id: str
    model_id: str
    usage: GenerationUsage | None = None
    latency_ms: int = 0
    provider_reference_id: str | None = None
    structured_output: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class GenerationEvent:
    event_type: str
    job_id: str | None
    delta: str = ""
    response: TextGenerationResponse | None = None
    error_code: RuntimeErrorCode | None = None


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    provider_id: str
    display_name: str
    provider_type: str
    supported_modalities: frozenset[Modality]
    configured: bool
    available: bool
    health_status: str = "available"


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    model_id: str
    provider_id: str
    display_name: str
    modality: Modality
    capabilities: frozenset[str]
    context_window: int | None = None
    structured_output: bool = False
    streaming: bool = False
    enabled: bool = True


class TextProvider(Protocol):
    provider_id: str
    def generate_text(self, request: TextGenerationRequest) -> TextGenerationResponse: ...
    def stream_text(self, request: TextGenerationRequest) -> Iterable[GenerationEvent]: ...


class LegacyTextProviderAdapter:
    """Moves existing providers onto the normalized contract without vendor leakage."""

    def __init__(self, provider_id: str, provider: LLMProvider):
        self.provider_id = provider_id
        self.provider = provider

    @staticmethod
    def _kwargs(request: TextGenerationRequest) -> dict[str, Any]:
        values: dict[str, Any] = {}
        if request.parameters.temperature is not None:
            values["temperature"] = request.parameters.temperature
        if request.parameters.max_output_tokens is not None:
            values["max_tokens"] = request.parameters.max_output_tokens
        if request.parameters.stop_sequences:
            values["stop"] = list(request.parameters.stop_sequences)
        return values

    def _response(self, request: TextGenerationRequest, value: Generation) -> TextGenerationResponse:
        return TextGenerationResponse(
            text=value.text,
            finish_reason="completed",
            provider_id=self.provider_id,
            model_id=request.model_id,
            usage=GenerationUsage(value.input_tokens, value.output_tokens, value.input_tokens + value.output_tokens),
            latency_ms=value.latency_ms,
            provider_reference_id=str(value.metadata.get("request_id")) if value.metadata.get("request_id") else None,
        )

    def generate_text(self, request: TextGenerationRequest) -> TextGenerationResponse:
        try:
            return self._response(request, self.provider.generate(request.prompt, request.model_id, **self._kwargs(request)))
        except ProviderError as exc:
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, "模型服务暂时不可用", retryable=True) from exc

    def stream_text(self, request: TextGenerationRequest) -> Iterable[GenerationEvent]:
        started = time.monotonic()
        yield GenerationEvent("generation.started", request.job_id)
        chunks: list[str] = []
        try:
            for chunk in self.provider.stream(request.prompt, request.model_id, **self._kwargs(request)):
                if request.cancellation is not None and request.cancellation.is_set():
                    raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, "已停止生成")
                chunks.append(chunk)
                yield GenerationEvent("generation.delta", request.job_id, delta=chunk)
            text = "".join(chunks)
            response = TextGenerationResponse(
                text=text,
                finish_reason="completed",
                provider_id=self.provider_id,
                model_id=request.model_id,
                usage=None,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            yield GenerationEvent("generation.completed", request.job_id, response=response)
        except ProviderError as exc:
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, "模型服务暂时不可用", retryable=True) from exc


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, TextProvider] = {}
        self._descriptors: dict[str, ProviderDescriptor] = {}

    def register(self, descriptor: ProviderDescriptor, provider: TextProvider, *, replace: bool = False) -> None:
        if descriptor.provider_id in self._providers and not replace:
            raise ValueError(f"provider already registered: {descriptor.provider_id}")
        self._providers[descriptor.provider_id] = provider
        self._descriptors[descriptor.provider_id] = descriptor

    def resolve(self, provider_id: str) -> TextProvider:
        try:
            descriptor, provider = self._descriptors[provider_id], self._providers[provider_id]
        except KeyError as exc:
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_NOT_FOUND, "未找到指定的模型服务") from exc
        if not descriptor.configured or not descriptor.available:
            raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, "模型服务当前不可用", retryable=True)
        return provider

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(self._descriptors[key] for key in sorted(self._descriptors))

    def is_configured(self, provider_id: str) -> bool:
        descriptor = self._descriptors.get(provider_id)
        return bool(descriptor and descriptor.configured and descriptor.available)


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[tuple[str, str], ModelDescriptor] = {}

    def register(self, model: ModelDescriptor, *, replace: bool = False) -> None:
        key = (model.provider_id, model.model_id)
        if key in self._models and not replace:
            raise ValueError(f"model already registered: {key}")
        self._models[key] = model

    def resolve(self, provider_id: str, model_id: str, modality: Modality) -> ModelDescriptor:
        try:
            model = self._models[(provider_id, model_id)]
        except KeyError as exc:
            raise ModelRuntimeError(RuntimeErrorCode.MODEL_NOT_FOUND, "未找到指定模型") from exc
        if not model.enabled:
            raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, "该模型当前已停用")
        if model.modality is not modality:
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, "该模型不支持文本生成")
        return model

    def descriptors(self) -> tuple[ModelDescriptor, ...]:
        return tuple(self._models[key] for key in sorted(self._models))


@dataclass(frozen=True, slots=True)
class TextModelNodeInput:
    request: TextGenerationRequest


@dataclass(frozen=True, slots=True)
class TextModelNodeOutput:
    generated_text: str
    response: TextGenerationResponse
    job_reference: str | None


class TextModelNode:
    type_id = "builtin.text_model"
    contract_version = 1

    def __init__(self, providers: ProviderRegistry, models: ModelRegistry):
        self.providers = providers
        self.models = models

    def execute(self, value: TextModelNodeInput) -> TextModelNodeOutput:
        request = value.request
        provider = self.providers.resolve(request.provider_id)
        model = self.models.resolve(request.provider_id, request.model_id, Modality.TEXT)
        if request.structured_output_schema is not None and not model.structured_output:
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, "当前模型不支持结构化输出")
        response = provider.generate_text(request)
        return TextModelNodeOutput(response.text, response, request.job_id)

    def stream(self, value: TextModelNodeInput) -> Iterable[GenerationEvent]:
        request = value.request
        provider = self.providers.resolve(request.provider_id)
        model = self.models.resolve(request.provider_id, request.model_id, Modality.TEXT)
        if not model.streaming:
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, "当前模型不支持流式生成")
        terminal = False
        try:
            for event in provider.stream_text(request):
                if event.event_type in {"generation.completed", "generation.failed", "generation.cancelled"}:
                    if terminal:
                        continue
                    terminal = True
                yield event
            if not terminal:
                yield GenerationEvent("generation.completed", request.job_id)
        except ModelRuntimeError as exc:
            event_type = "generation.cancelled" if exc.code is RuntimeErrorCode.CANCELLED else "generation.failed"
            yield GenerationEvent(event_type, request.job_id, error_code=exc.code)


class GenerationRuntime:
    def __init__(self, providers: ProviderRegistry, models: ModelRegistry):
        self.providers = providers
        self.models = models
        self.text_node = TextModelNode(providers, models)
