"""Host-bound, chapter-independent text contracts over the existing runtime.

No registry, scheduler, transport or credential owner is introduced. The local
invocation is transient and cannot be reconstructed from a persisted Job. API
providers are reserved and deliberately nonexecuting in this M4 slice.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from typing import Annotated, Iterable, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .model_runtime import (GenerationEvent, LegacyTextProviderAdapter, Modality,
    ModelRuntimeError, RuntimeErrorCode, TextGenerationRequest, TextModelNodeInput)
from .model_provider_contracts import ReservedAPIProvider

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=240)]


class GraphRequestBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    graph_id: Identifier
    graph_version: int = Field(ge=1)
    run_id: Identifier
    node_id: Identifier
    project_incarnation: Identifier
    input_digest: Digest
    reviewed_preview_digest: Digest
    route_fingerprint: Digest


class ModelProviderAdapter(Protocol):
    """A consumer of host-owned registration, never a provider registry."""
    def validate(self) -> None: ...
    def stream_text(self, request: TextGenerationRequest) -> Iterable[GenerationEvent]: ...


class APIProvider(ReservedAPIProvider):
    """Reserved interface only; existing paid/API adapters are not activated."""
    available = False
    reason = "GRAPH_API_PROVIDER_RESERVED"

    def validate(self):
        raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, self.reason)

    def stream_text(self, request):
        self.validate()


class LocalModelInvocation:
    """One exact registered local route, delegated to the original TextModelNode."""
    def __init__(self, runtime, provider_id, model_id, *, synthetic_allowed=False):
        if type(synthetic_allowed) is not bool:
            raise ValueError("GRAPH_SYNTHETIC_PERMISSION_INVALID")
        self.runtime, self.provider_id, self.model_id = runtime, provider_id, model_id
        self.synthetic_allowed = synthetic_allowed
        self._provider = runtime.provider_registry.resolve(provider_id)
        self._model = runtime.model_registry.resolve(provider_id, model_id, Modality.TEXT)
        self.validate()

    def validate(self):
        from .model_center.discovery_bridge import LocalTextAdapter
        from .providers import MockProvider
        from .config import settings
        current = self.runtime.provider_registry.resolve(self.provider_id)
        model = self.runtime.model_registry.resolve(self.provider_id, self.model_id, Modality.TEXT)
        if current is not self._provider or model != self._model:
            raise ValueError("GRAPH_LOCAL_ROUTE_CHANGED")
        if self.runtime.is_remote_text_provider(self.provider_id):
            raise ValueError("GRAPH_LOCAL_ONLY")
        synthetic = type(current) is LegacyTextProviderAdapter and type(current.provider) is MockProvider
        if synthetic:
            if not self.synthetic_allowed or settings.enable_packaged_runtime:
                raise ValueError("GRAPH_SYNTHETIC_NOT_AUTHORIZED")
        elif type(current) is LocalTextAdapter:
            candidate = current.bridge.guard(current.candidate["id"])
            if (candidate["id"] != self.model_id or candidate.get("source_locality") != "LOCAL_VERIFIED"
                    or not candidate.get("model_evidence_fingerprint")):
                raise ValueError("GRAPH_VERIFIED_LOCAL_MODEL_REQUIRED")
            config = candidate.get("runtime_config", {})
            if config.get("management") != "EXTERNAL" or config.get("type") not in {"OLLAMA", "LLAMA_CPP"}:
                raise ValueError("GRAPH_EXTERNAL_LOCAL_RUNTIME_REQUIRED")
        else:
            # A local descriptor or loopback URL alone cannot authorize egress.
            raise ValueError("GRAPH_VERIFIED_LOCAL_ADAPTER_REQUIRED")
        if "generate" not in model.capabilities or not model.streaming:
            raise ValueError("GRAPH_TEXT_CAPABILITY_REQUIRED")

    def stream_text(self, request):
        self.validate()
        if (request.provider_id, request.model_id) != (self.provider_id, self.model_id):
            raise ValueError("GRAPH_LOCAL_ROUTE_MISMATCH")
        # This is the only invocation path. There is no fallback or new transport.
        node = self.runtime.prepare_text_route(self.provider_id, self.model_id)
        yield from node.stream(TextModelNodeInput(request))


def guard_local_provider(runtime, provider_id, model_id, synthetic_allowed=False):
    """Read existing registration only; never probe, launch or inspect credentials."""
    from .model_center.discovery_bridge import LocalTextAdapter
    invocation = LocalModelInvocation(runtime, provider_id, model_id, synthetic_allowed=synthetic_allowed)
    return {"synthetic": type(invocation._provider) is LegacyTextProviderAdapter,
            "streaming": "BUFFERED" if type(invocation._provider) is LocalTextAdapter else "ADAPTER_PROTOCOL"}


def graph_prompt_digest(prompt, *, max_output_tokens=512, temperature=0.0, binding=None):
    """Deterministic preview data fingerprint, not an execution permission."""
    from .model_runtime import TextGenerationParameters
    if type(temperature) not in {int, float} or not math.isfinite(temperature):
        raise ValueError("GRAPH_MODEL_TEMPERATURE_INVALID")
    params = TextGenerationParameters(temperature=temperature, max_output_tokens=max_output_tokens)
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > 32_000:
        raise ValueError("GRAPH_MODEL_PROMPT_INVALID")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 2048:
        raise ValueError("GRAPH_MODEL_TOKEN_BOUND_INVALID")
    value = {"prompt": prompt, "max_output_tokens": params.max_output_tokens,
             "temperature": params.temperature, "binding": binding}
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _payload(request):
    from .author_request import request_payload
    return request_payload(request)


def _binding_digest(job, request, synthetic_allowed):
    value = {"request": _payload(request), "job_id": job.id, "project_id": job.novel_id,
        "actor_id": job.actor_id, "scope": job.scope, "graph_binding": job.graph_binding,
        "profile": job.profile, "operation": job.operation, "chapter_id": job.chapter_id,
        "provider_id": job.requested_provider, "model_id": job.requested_model,
        "max_output_bytes": job.generation_max_output_bytes, "deadline": job.generation_deadline,
        "synthetic_allowed": synthetic_allowed}
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class PreparedTextInvocation:
    request: TextGenerationRequest
    adapter: ModelProviderAdapter
    binding_digest: str
    synthetic_allowed: bool

    @classmethod
    def bind(cls, job, request, adapter, synthetic_allowed):
        return cls(request, adapter, _binding_digest(job, request, synthetic_allowed), synthetic_allowed)

    def validate_job(self, job):
        GraphRequestBinding.model_validate(job.graph_binding)
        if (job.operation != "graph_text" or job.chapter_id is not None or job.profile != "LOCAL_ONLY"
                or self.request.job_id != job.id or self.request.cancellation is not job.cancelled
                or _binding_digest(job, self.request, self.synthetic_allowed) != self.binding_digest
                or job.expected_request_digest != self.binding_digest):
            raise ValueError("GRAPH_PREPARED_REQUEST_CHANGED")
        self.adapter.validate()

    def request_for_dispatch(self, job, dispatch_guard, preparation_guard=None):
        self.validate_job(job)
        # Only the exact external-local adapter has a separate preparation
        # phase and final-hop callback. Synthetic legacy Mock dispatches at the
        # original TextModelNode boundary and must not lose that callback.
        from .model_center.discovery_bridge import LocalTextAdapter
        prepare = preparation_guard if type(self.adapter._provider) is LocalTextAdapter else None
        return replace(self.request, dispatch_guard=dispatch_guard, preparation_guard=prepare)
