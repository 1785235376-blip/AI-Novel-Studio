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
from typing import Annotated, Iterable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

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
    execution_receipt_contract: Literal["creative-graph-text-execution/1"] | None = None
    execution_receipt_source_version: int | None = Field(default=None, ge=1, le=2**53 - 1)

    @model_validator(mode="after")
    def _receipt_pair(self):
        if (self.execution_receipt_contract is None) != (self.execution_receipt_source_version is None):
            raise ValueError("GRAPH_EXECUTION_RECEIPT_BINDING_INVALID")
        return self

    @model_serializer(mode="wrap")
    def _omit_legacy_receipt_marker(self, handler):
        result = handler(self)
        # Existing request digests predate this marker. Missing consent must
        # retain exactly the old canonical binding, never an injected null.
        if self.execution_receipt_contract is None:
            result.pop("execution_receipt_contract", None)
            result.pop("execution_receipt_source_version", None)
        return result


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


def graph_request_payload_digest(job, payload, synthetic_allowed):
    """Hash passive request data for verification; never recreate an invocation."""
    value = {"request": payload, "job_id": job.id, "project_id": job.novel_id,
        "actor_id": job.actor_id, "scope": job.scope, "graph_binding": job.graph_binding,
        "profile": job.profile, "operation": job.operation, "chapter_id": job.chapter_id,
        "provider_id": job.requested_provider, "model_id": job.requested_model,
        "max_output_bytes": job.generation_max_output_bytes, "deadline": job.generation_deadline,
        "synthetic_allowed": synthetic_allowed}
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _binding_digest(job, request, synthetic_allowed):
    return graph_request_payload_digest(job, _payload(request), synthetic_allowed)


def creative_director_request_payload_digest(job, payload, synthetic_allowed, *, route_fingerprint):
    """Domain-separated passive data hash; never prepares or authorizes a call."""
    import re
    from .creative.director_binding import creative_director_job_binding
    if (type(synthetic_allowed) is not bool or not isinstance(route_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", route_fingerprint) is None
            or type(payload) is not dict):
        raise ValueError("CREATIVE_DIRECTOR_REQUEST_INVALID")
    fields = ("id", "novel_id", "actor_id", "scope", "operation", "experimental_origin",
              "chapter_id", "profile", "creative_director_binding", "graph_binding", "adaptation_binding")
    binding = creative_director_job_binding({key: getattr(job, key, None) for key in fields},
                                           require_request_digest=False)
    if (payload.get("provider_id") != job.requested_provider
            or payload.get("model_id") != job.requested_model):
        raise ValueError("CREATIVE_DIRECTOR_REQUEST_ROUTE_MISMATCH")
    value = {"domain": "creative-director-request/1", "request": payload,
        "job_id": job.id, "project_id": job.novel_id, "actor_id": job.actor_id,
        "scope": job.scope, "creative_director_binding": binding,
        "operation": job.operation, "origin": job.experimental_origin,
        "profile": job.profile, "chapter_id": job.chapter_id,
        "provider_id": job.requested_provider, "model_id": job.requested_model,
        "route_fingerprint": route_fingerprint, "synthetic_allowed": synthetic_allowed,
        "max_output_bytes": job.generation_max_output_bytes, "deadline": job.generation_deadline}
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _require_graph_only_invocation(job):
    from .creative.director_binding import is_creative_director_job
    if is_creative_director_job(job):
        raise ValueError("GRAPH_PREPARED_DOMAIN_INVALID")


_CREATIVE_SEAL = object()


class _CreativeDirectorCapability:
    """Transient supported-caller boundary, not a sandbox for hostile Python.

    Only the original Director coordinator issues this private object. JSON,
    passive Jobs, copied invocations and arbitrary callbacks cannot restore it.
    Python code with arbitrary in-process introspection is outside this boundary.
    """
    __slots__ = ("_seal", "manager", "host", "preparation", "authorization", "route_fingerprint",
                 "job", "job_id", "cancellation", "invocation", "adapter", "started", "before_dispatch", "on_terminal", "worker_claimed",
                 "terminal_publication", "publication_state", "publication_thread", "_publication_binding")

    def __init__(self, seal, manager, host, preparation, authorization, route_fingerprint):
        from .model_center.discovery_authority import DiscoveryAuthority
        if (seal is not _CREATIVE_SEAL or type(host) is not DiscoveryAuthority
                or not isinstance(host.principal, str) or not host.principal
                or not callable(host.guard) or not callable(preparation) or not callable(authorization)):
            raise ValueError("CREATIVE_DIRECTOR_LIVE_AUTHORITY_REQUIRED")
        self._seal, self.manager, self.host = seal, manager, host
        self.preparation, self.authorization = preparation, authorization
        self.route_fingerprint = route_fingerprint
        self.job_id = None
        self.job = self.cancellation = self.invocation = self.adapter = None
        self.started = False
        self.worker_claimed = False
        self.before_dispatch = self.on_terminal = None
        self.terminal_publication = None
        self.publication_state = None
        self.publication_thread = None
        self._publication_binding = None
        host.guard()

    @classmethod
    def _issue(cls, manager, host, preparation, authorization, route_fingerprint):
        return cls(_CREATIVE_SEAL, manager, host, preparation, authorization, route_fingerprint)

    def _attach(self, job):
        if self._seal is not _CREATIVE_SEAL or self.job is not None:
            raise ValueError("CREATIVE_DIRECTOR_CAPABILITY_ALREADY_BOUND")
        self.job, self.job_id, self.cancellation = job, job.id, job.cancelled

    def _bind_hooks(self, job, before_dispatch, on_terminal):
        self._check(job)
        if self.before_dispatch is not None or self.on_terminal is not None or not callable(before_dispatch) or not callable(on_terminal):
            raise ValueError("CREATIVE_DIRECTOR_BROKER_HOOKS_REQUIRED")
        self.before_dispatch, self.on_terminal = before_dispatch, on_terminal
        job.before_dispatch, job.on_terminal = before_dispatch, on_terminal

    def _bind_terminal_publication(self, job, publisher, repository):
        self._check(job)
        if (self.started or self._publication_binding is not None or not callable(publisher)
                or repository is not getattr(self.manager.persistence, "repository", self.manager.persistence)):
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_OWNER_REQUIRED")
        self._publication_binding = (publisher, repository, job.expected_request_digest)
        self.terminal_publication = publisher
        self.publication_state = "PENDING"

    def _check(self, job, *, manager=None, started=False):
        from .model_center.discovery_authority import DiscoveryAuthority
        if (self._seal is not _CREATIVE_SEAL or self.job is not job or self.job_id != job.id
                or (manager is not None and self.manager is not manager)
                or job.creative_execution_authority is not self
                or self.cancellation is not job.cancelled
                or type(self.host) is not DiscoveryAuthority or not self.host.principal
                or not callable(self.host.guard) or (started and not self.started)):
            raise ValueError("CREATIVE_DIRECTOR_LIVE_AUTHORITY_REQUIRED")

    def _current(self, job):
        self._check(job)
        if self._publication_binding is not None and (
                self.terminal_publication is not self._publication_binding[0]
                or job.expected_request_digest != self._publication_binding[2]):
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_OWNER_CHANGED")
        if (self.before_dispatch is not None and (job.before_dispatch is not self.before_dispatch
                or job.on_terminal is not self.on_terminal)):
            raise ValueError("CREATIVE_DIRECTOR_BROKER_HOOKS_CHANGED")
        self.host.guard()
        self.authorization()
        self.host.guard()
        self._check(job)
        if self._publication_binding is not None and (
                self.terminal_publication is not self._publication_binding[0]
                or job.expected_request_digest != self._publication_binding[2]):
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_OWNER_CHANGED")


@dataclass(frozen=True, slots=True)
class PreparedTextInvocation:
    request: TextGenerationRequest
    adapter: ModelProviderAdapter
    binding_digest: str
    synthetic_allowed: bool
    _creative_capability: object = None

    @classmethod
    def bind(cls, job, request, adapter, synthetic_allowed):
        _require_graph_only_invocation(job)
        return cls(request, adapter, _binding_digest(job, request, synthetic_allowed), synthetic_allowed)

    def validate_job(self, job):
        _require_graph_only_invocation(job)
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

    @classmethod
    def _bind_creative(cls, job, request, adapter, synthetic_allowed, capability):
        if type(capability) is not _CreativeDirectorCapability:
            raise ValueError("CREATIVE_DIRECTOR_LIVE_AUTHORITY_REQUIRED")
        capability._check(job)
        if capability.invocation is not None or type(adapter) is not LocalModelInvocation:
            raise ValueError("CREATIVE_DIRECTOR_PREPARED_REQUEST_INVALID")
        value = creative_director_request_payload_digest(job, _payload(request), synthetic_allowed,
            route_fingerprint=capability.route_fingerprint)
        invocation = cls(request, adapter, value, synthetic_allowed, capability)
        capability.invocation, capability.adapter = invocation, adapter
        return invocation

    def _validate_creative(self, job, *, manager=None, started=False):
        capability = self._creative_capability
        if type(capability) is not _CreativeDirectorCapability:
            raise ValueError("CREATIVE_DIRECTOR_LIVE_AUTHORITY_REQUIRED")
        capability._check(job, manager=manager, started=started)
        if (capability.invocation is not self or job.prepared_text_invocation is not self
                or capability.adapter is not self.adapter or type(self.adapter) is not LocalModelInvocation
                or self.request.job_id != job.id or self.request.cancellation is not job.cancelled
                or self.request.dispatch_guard is not None or self.request.preparation_guard is not None
                or self.adapter.synthetic_allowed is not self.synthetic_allowed
                or (self.adapter.provider_id, self.adapter.model_id) != (job.requested_provider, job.requested_model)
                or creative_director_request_payload_digest(job, _payload(self.request), self.synthetic_allowed,
                    route_fingerprint=capability.route_fingerprint) != self.binding_digest
                or job.expected_request_digest != self.binding_digest):
            raise ValueError("CREATIVE_DIRECTOR_PREPARED_REQUEST_CHANGED")
        self.adapter.validate()

    def _creative_request_for_dispatch(self, job, dispatch_guard, preparation_guard):
        self._validate_creative(job, started=True)
        from .model_center.discovery_bridge import LocalTextAdapter
        prepare = preparation_guard if type(self.adapter._provider) is LocalTextAdapter else None
        return replace(self.request, dispatch_guard=dispatch_guard, preparation_guard=prepare)
