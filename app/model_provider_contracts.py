"""M4-B provider contracts, not a provider registry or execution authority.

Static family facades read the original host registrations. Only exact external
Ollama/llama.cpp text invocations delegate to the original TextModelNode. Catalog
records and task matches are advisory; JobManager/Broker/WorkflowRun still own
consent, admission, dispatch, accounting and publication. No transport is added.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Annotated, Iterable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .model_runtime import (GenerationEvent, GenerationUsage, ModelRuntimeError, RuntimeErrorCode,
    TextGenerationRequest, TextGenerationResponse)

TaskType = Literal["TEXT_GENERATION", "IMAGE_GENERATION", "VIDEO_GENERATION"]
ProviderFamily = Literal["LOCAL_OLLAMA", "LM_STUDIO", "COMFYUI", "LLAMA_CPP", "API"]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
TASK_CAPABILITY = {"TEXT_GENERATION": "TEXT", "IMAGE_GENERATION": "IMAGE", "VIDEO_GENERATION": "VIDEO"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TaskRequirement(Strict):
    """An additional bounded filter; never permissions or a routing recipe."""
    task_type: TaskType = "TEXT_GENERATION"
    preferred_route: Digest | None = None
    min_host_ram_mib: int | None = Field(default=None, ge=1, le=10**7)
    min_host_vram_mib: int | None = Field(default=None, ge=1, le=10**7)
    local_only: Literal[True] = True
    api_available: bool = False  # Advisory host fact; API execution stays reserved.
    allow_synthetic: bool = False

    @field_validator("local_only", mode="before")
    @classmethod
    def literal_local_only(cls, value):
        if value is not True:
            raise ValueError("TASK_LOCAL_ONLY_REQUIRED")
        return value


class TaskMatch(Strict):
    task_type: TaskType
    eligible: bool
    reasons: tuple[str, ...]
    preferred: bool
    hardware_state: Literal["NOT_REQUESTED", "UNKNOWN", "INSUFFICIENT", "TOTAL_CAPACITY_ONLY"]
    api_available: bool
    execution_authority: Literal[False] = False
    automatic_fallback: Literal[False] = False
    gpu_fit_verified: Literal[False] = False


def match_task_requirement(requirement, route, hardware=None) -> TaskMatch:
    """Match original broker facts without probes, ranking or state mutation.

    ``route`` and ``hardware`` are host-owned broker observations, never positive
    evidence from an HTTP body. Even an eligible match requires the unchanged
    current-route guard and original preview/admission flow.
    """
    requirement = TaskRequirement.model_validate(requirement)
    reasons = list(route.get("reasons", ()))
    if route.get("available") is not True:
        reasons.append("CURRENT_ROUTE_UNAVAILABLE")
    if route.get("capability") != TASK_CAPABILITY[requirement.task_type]:
        reasons.append("TASK_CAPABILITY_MISMATCH")
    if requirement.task_type != "TEXT_GENERATION":
        reasons.append("GRAPH_" + TASK_CAPABILITY[requirement.task_type] + "_EXECUTION_NOT_ENABLED")
    if route.get("cloud") is not False:
        reasons.extend(("LOCAL_ONLY_REQUIRED", "API_PROVIDER_EXECUTION_NOT_ENABLED"))
        if not requirement.api_available:
            reasons.append("API_AVAILABILITY_NOT_CONFIRMED")
    identity = route.get("identity") or {}
    if (identity.get("source_locality") != "LOCAL_VERIFIED" or not identity.get("model_version")
            or not identity.get("adapter_hash")):
        reasons.append("VERIFIED_MODEL_CAPABILITY_REQUIRED")
    if route.get("synthetic") is True and not requirement.allow_synthetic:
        reasons.append("SYNTHETIC_NOT_AUTHORIZED")
    preferred = requirement.preferred_route is not None and requirement.preferred_route == route.get("route_id")
    if requirement.preferred_route is not None and not preferred:
        reasons.append("EXACT_PREFERRED_ROUTE_REQUIRED")
    states = []
    hardware = hardware or {}
    for kind, required in (("RAM", requirement.min_host_ram_mib), ("VRAM", requirement.min_host_vram_mib)):
        if required is None:
            continue
        available = hardware.get(kind.lower() + "_mib")
        if (hardware.get("state") != "HOST_TOTAL_CAPACITY" or type(available) is not int or available < 0):
            states.append("UNKNOWN")
            reasons.append("HOST_" + kind + "_UNKNOWN")
        elif available < required:
            states.append("INSUFFICIENT")
            reasons.append("HOST_" + kind + "_INSUFFICIENT")
        else:
            states.append("TOTAL_CAPACITY_ONLY")
    hardware_state = next((state for state in ("INSUFFICIENT", "UNKNOWN", "TOTAL_CAPACITY_ONLY") if state in states), "NOT_REQUESTED")
    return TaskMatch(task_type=requirement.task_type, eligible=not reasons,
        reasons=tuple(dict.fromkeys(reasons)), preferred=preferred, hardware_state=hardware_state,
        api_available=requirement.api_available)


class ProviderCapability(Strict):
    family: ProviderFamily
    advertised: tuple[TaskType, ...]
    verified: tuple[TaskType, ...] = ()
    verification: Literal["NOT_VERIFIED", "REGISTERED_ADAPTER_CONTRACT_ONLY"] = "NOT_VERIFIED"
    inference_verification: Literal["NOT_RUN"] = "NOT_RUN"


class ProviderAvailability(Strict):
    family: ProviderFamily
    adapter_available: bool
    status: Literal["REGISTERED", "UNAVAILABLE", "RESERVED"]
    reasons: tuple[str, ...]
    # Availability of an adapter does not authorize a graph to dispatch it.
    execution_available: Literal[False] = False
    execution_authority: Literal["ORIGINAL_REVIEWED_REQUEST_REQUIRED"] = "ORIGINAL_REVIEWED_REQUEST_REQUIRED"


def _now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ProviderExecutionRequest:
    """Transient host envelope. It is never deserialized as dispatch authority."""
    task_type: TaskType
    request: TextGenerationRequest
    created_at: str = field(default_factory=_now)
    request_digest: str = field(init=False)

    def __post_init__(self):
        if self.task_type not in TASK_CAPABILITY or type(self.request) is not TextGenerationRequest:
            raise ValueError("MODEL_PROVIDER_ORIGINAL_REQUEST_REQUIRED")
        object.__setattr__(self, "request_digest", _request_digest(self.request))


def _request_digest(request):
    from .author_request import request_payload
    return sha256(json.dumps(request_payload(request), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class ProviderResultParameters(Strict):
    temperature: float | None
    max_output_tokens: int | None
    stop_sequences: tuple[str, ...]


class ProviderExecutionResult(Strict):
    contract: Literal["model-provider-result/1"] = "model-provider-result/1"
    task_type: Literal["TEXT_GENERATION"] = "TEXT_GENERATION"
    provider_id: str
    model_id: str
    parameters: ProviderResultParameters
    request_created_at: str
    result_recorded_at: str
    latency_ms: int = Field(ge=0)
    request_digest: Digest
    output_digest: Digest
    text: str
    execution_mode: Literal["real", "mock_standin"]
    proposal_only: Literal[True] = True
    quality_verification: Literal["NOT_RUN"] = "NOT_RUN"
    acceptance_authority: Literal["ORIGINAL_JOB_RECEIPT_AND_HUMAN_REVIEW"] = "ORIGINAL_JOB_RECEIPT_AND_HUMAN_REVIEW"

    @field_validator("request_created_at", "result_recorded_at")
    @classmethod
    def aware_timestamp(cls, value):
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed > datetime.now(timezone.utc):
            raise ValueError("MODEL_PROVIDER_TIMESTAMP_INVALID")
        return value

    @model_validator(mode="after")
    def ordered_timestamps(self):
        if datetime.fromisoformat(self.request_created_at) > datetime.fromisoformat(self.result_recorded_at):
            raise ValueError("MODEL_PROVIDER_TIMESTAMP_INVALID")
        return self


def normalize_text_result(execution: ProviderExecutionRequest, response: TextGenerationResponse) -> ProviderExecutionResult:
    """Host-only representation of an original response, never an acceptance API.

    The response is not proof of settlement, job completion or model quality.
    The original worker remains responsible for validating its event stream.
    """
    if type(execution) is not ProviderExecutionRequest or execution.task_type != "TEXT_GENERATION":
        raise ValueError("MODEL_PROVIDER_TEXT_RESULT_REQUIRED")
    request = execution.request
    if type(request) is not TextGenerationRequest or type(response) is not TextGenerationResponse:
        raise ValueError("MODEL_PROVIDER_ORIGINAL_RESULT_REQUIRED")
    if _request_digest(request) != execution.request_digest:
        raise ValueError("MODEL_PROVIDER_REQUEST_CHANGED")
    if ((response.provider_id, response.model_id) != (request.provider_id, request.model_id)
            or response.finish_reason != "completed" or not isinstance(response.text, str)
            or not response.text.strip() or len(response.text.encode("utf-8")) > 32_000):
        raise ValueError("MODEL_PROVIDER_RESULT_BINDING_INVALID")
    if not isinstance(execution.created_at, str):
        raise ValueError("MODEL_PROVIDER_TIMESTAMP_INVALID")
    created = datetime.fromisoformat(execution.created_at)
    if created.tzinfo is None or created > datetime.now(timezone.utc):
        raise ValueError("MODEL_PROVIDER_TIMESTAMP_INVALID")
    return ProviderExecutionResult(provider_id=response.provider_id, model_id=response.model_id,
        parameters=ProviderResultParameters(temperature=request.parameters.temperature,
            max_output_tokens=request.parameters.max_output_tokens, stop_sequences=request.parameters.stop_sequences),
        request_created_at=execution.created_at, result_recorded_at=_now(), latency_ms=response.latency_ms,
        request_digest=execution.request_digest,
        output_digest=sha256(response.text.encode()).hexdigest(), text=response.text, execution_mode=response.execution_mode)


class ModelProvider(Protocol):
    """Uniform host-facing contract; families may truthfully remain reserved."""
    def capabilities(self) -> ProviderCapability: ...
    def availability(self) -> ProviderAvailability: ...
    def execute(self, request: ProviderExecutionRequest) -> Iterable[GenerationEvent]: ...
    def result(self, request: ProviderExecutionRequest, response: TextGenerationResponse) -> ProviderExecutionResult: ...


class _ProviderFacade:
    family: ProviderFamily
    runtime_type: str | None = None
    advertised: tuple[TaskType, ...] = ("TEXT_GENERATION",)
    reserved_reason: str | None = None

    def __init__(self, runtime=None, provider_id=None, model_id=None):
        self.runtime, self.provider_id, self.model_id = runtime, provider_id, model_id

    def _invocation(self):
        if self.reserved_reason:
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED, self.reserved_reason)
        if self.runtime is None or not self.provider_id or not self.model_id:
            raise ValueError("EXPLICIT_REGISTERED_LOCAL_ROUTE_REQUIRED")
        from .model_execution import LocalModelInvocation
        from .model_center.discovery_bridge import LocalTextAdapter
        invocation = LocalModelInvocation(self.runtime, self.provider_id, self.model_id)
        if (type(invocation._provider) is not LocalTextAdapter
                or invocation._provider.bridge.guard(self.model_id).get("runtime_config", {}).get("type") != self.runtime_type):
            raise ValueError("MODEL_PROVIDER_FAMILY_MISMATCH")
        return invocation

    def availability(self):
        reasons = []
        try:
            self._invocation()
        except (ModelRuntimeError, ValueError, KeyError):
            # Never disclose exception text, endpoint, path or model evidence.
            reasons.append(self.reserved_reason or "EXPLICIT_VERIFIED_LOCAL_ROUTE_UNAVAILABLE")
        return ProviderAvailability(family=self.family, adapter_available=not reasons,
            status="RESERVED" if self.reserved_reason else "UNAVAILABLE" if reasons else "REGISTERED", reasons=tuple(reasons))

    def capabilities(self):
        available = self.availability().adapter_available
        return ProviderCapability(family=self.family, advertised=self.advertised,
            verified=("TEXT_GENERATION",) if available else (),
            verification="REGISTERED_ADAPTER_CONTRACT_ONLY" if available else "NOT_VERIFIED")

    def execute(self, request):
        invocation = self._invocation()
        if type(request) is not ProviderExecutionRequest or request.task_type != "TEXT_GENERATION":
            raise ValueError("MODEL_PROVIDER_TEXT_EXECUTION_REQUIRED")
        # Original callbacks are compulsory on this new facade. Their owners
        # still validate current consent, scope, limits and accounting.
        if (not callable(request.request.dispatch_guard) or not callable(request.request.preparation_guard)
                or not request.request.job_id or request.request.cancellation is None):
            raise ValueError("MODEL_PROVIDER_PREPARED_GUARDS_REQUIRED")
        def guard(original):
            def current():
                if _request_digest(request.request) != request.request_digest:
                    raise ValueError("MODEL_PROVIDER_REQUEST_CHANGED")
                original()
            return current
        if _request_digest(request.request) != request.request_digest:
            raise ValueError("MODEL_PROVIDER_REQUEST_CHANGED")
        return invocation.stream_text(replace(request.request,
            dispatch_guard=guard(request.request.dispatch_guard),
            preparation_guard=guard(request.request.preparation_guard)))

    def result(self, request, response):
        self._invocation()
        if (request.request.provider_id, request.request.model_id) != (self.provider_id, self.model_id):
            raise ValueError("MODEL_PROVIDER_RESULT_ROUTE_MISMATCH")
        return normalize_text_result(request, response)


class LocalOllamaProvider(_ProviderFacade):
    family = "LOCAL_OLLAMA"
    runtime_type = "OLLAMA"


class LlamaCppProvider(_ProviderFacade):
    family = "LLAMA_CPP"
    runtime_type = "LLAMA_CPP"


class LMStudioProvider(_ProviderFacade):
    family = "LM_STUDIO"
    runtime_type = "OPENAI_COMPATIBLE_LOCAL"
    reserved_reason = "LMSTUDIO_LOCALITY_UNVERIFIED"

    @staticmethod
    def wire_request(request: TextGenerationRequest, *, loaded_instance_id: str):
        """Pure OpenAI-compatible payload contract, not loaded/local authority.

        A future trusted owner must supply the exact loaded instance and prove
        locality/no-JIT before the original LocalProbeClient can send it. The
        current execute path deliberately fails before any transport call.
        """
        from .model_execution import graph_prompt_digest
        if type(request) is not TextGenerationRequest or request.structured_output_schema is not None:
            raise ValueError("LMSTUDIO_TEXT_REQUEST_REQUIRED")
        if (not isinstance(loaded_instance_id, str) or not loaded_instance_id.strip()
                or len(loaded_instance_id) > 256 or any(ord(c) < 32 for c in loaded_instance_id)):
            raise ValueError("LMSTUDIO_LOADED_INSTANCE_REQUIRED")
        params = request.parameters
        graph_prompt_digest(request.prompt, max_output_tokens=params.max_output_tokens,
                            temperature=params.temperature)
        if (request.system_instruction is not None and (not isinstance(request.system_instruction, str)
                or len(request.system_instruction.encode()) + len(request.prompt.encode()) > 32_000)):
            raise ValueError("LMSTUDIO_PROMPT_BOUND_REQUIRED")
        if (type(params.stop_sequences) is not tuple or len(params.stop_sequences) > 4
                or any(not isinstance(item, str) or not item or len(item) > 200 for item in params.stop_sequences)):
            raise ValueError("LMSTUDIO_STOP_BOUND_REQUIRED")
        messages = [{"role": "user", "content": request.prompt}]
        if request.system_instruction:
            messages.insert(0, {"role": "system", "content": request.system_instruction})
        value = {"model": loaded_instance_id, "messages": messages, "stream": False,
                 "temperature": params.temperature, "max_tokens": params.max_output_tokens}
        if params.stop_sequences:
            value["stop"] = list(params.stop_sequences)
        return value

    @staticmethod
    def wire_response(request: TextGenerationRequest, data, *, loaded_instance_id: str, latency_ms=0):
        """Strict pure decoder; successful decoding never confers execution authority."""
        LMStudioProvider.wire_request(request, loaded_instance_id=loaded_instance_id)
        if (not isinstance(data, dict) or data.get("error") or data.get("object") != "chat.completion"
                or data.get("model") != loaded_instance_id or type(latency_ms) is not int or latency_ms < 0):
            raise ValueError("LMSTUDIO_RESPONSE_INVALID")
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("LMSTUDIO_RESPONSE_INVALID")
        choice = choices[0]
        message = choice.get("message")
        if (type(choice.get("index")) is not int or choice["index"] != 0 or choice.get("finish_reason") != "stop"
                or not isinstance(message, dict) or message.get("role") != "assistant"
                or message.get("tool_calls") is not None or message.get("function_call") is not None
                or message.get("refusal") is not None):
            raise ValueError("LMSTUDIO_RESPONSE_INVALID")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip() or len(text.encode()) > 32_000:
            raise ValueError("LMSTUDIO_RESPONSE_INVALID")
        usage = None
        if data.get("usage") is not None:
            measured = data["usage"]
            if not isinstance(measured, dict):
                raise ValueError("LMSTUDIO_USAGE_INVALID")
            counts = tuple(measured.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
            if any(value is not None and (type(value) is not int or not 0 <= value <= 10**7) for value in counts):
                raise ValueError("LMSTUDIO_USAGE_INVALID")
            if all(value is not None for value in counts) and counts[0] + counts[1] != counts[2]:
                raise ValueError("LMSTUDIO_USAGE_INVALID")
            if any(value is not None for value in counts):
                usage = GenerationUsage(*counts)
        return TextGenerationResponse(text, "completed", request.provider_id, request.model_id,
            usage=usage, latency_ms=latency_ms, execution_mode="real")


class ComfyUIProvider(_ProviderFacade):
    family = "COMFYUI"
    runtime_type = "COMFYUI"
    advertised = ("IMAGE_GENERATION", "VIDEO_GENERATION")
    reserved_reason = "COMFYUI_GRAPH_EXECUTION_NOT_ENABLED"


class ReservedAPIProvider(_ProviderFacade):
    family = "API"
    advertised = ("TEXT_GENERATION", "IMAGE_GENERATION", "VIDEO_GENERATION")
    reserved_reason = "API_PROVIDER_EXECUTION_NOT_ENABLED"


def provider_catalog(runtime=None):
    """Five static advisory family records, not discovered/registered models.

    Reads descriptor snapshots only. No credentials, health checks, discovery,
    hardware collection, inference, install, enable or process launch occurs.
    Catalog execution_available is always false; exact route controls live in
    the original graph model catalog and review flow.
    """
    classes = (LocalOllamaProvider, LMStudioProvider, ComfyUIProvider, LlamaCppProvider, ReservedAPIProvider)
    bindings = []
    if runtime is not None:
        from .model_runtime import Modality
        for model in runtime.model_registry.descriptors():
            if model.modality is Modality.TEXT:
                bindings.append((model.provider_id, model.model_id))
    rows = []
    for cls in classes:
        facade = cls()
        registered = []
        if not facade.reserved_reason:
            for provider_id, model_id in bindings:
                bound = cls(runtime, provider_id, model_id)
                if bound.availability().adapter_available:
                    registered.append({"provider_id": provider_id, "model_id": model_id})
                    facade = bound
        rows.append({"family": facade.family, "capability": facade.capabilities().model_dump(mode="json"),
            "availability": facade.availability().model_dump(mode="json"), "registered_routes": registered,
            "advisory_only": True, "automatic_fallback": False, "real_model_verification": "NOT_RUN"})
    return rows


# More explicit spelling for integrations that also expose model route rows.
provider_contract_catalog = provider_catalog
