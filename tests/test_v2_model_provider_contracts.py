"""M4-B pure contracts and original local protocol mocks. Real inference NOT_RUN."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Event
from types import SimpleNamespace

import pytest

from app.model_execution import APIProvider
from app.model_provider_contracts import (ComfyUIProvider, LMStudioProvider, LlamaCppProvider,
    LocalOllamaProvider, ProviderExecutionRequest, ProviderExecutionResult, ReservedAPIProvider, TaskRequirement,
    match_task_requirement, normalize_text_result, provider_catalog)
from app.model_runtime import (ModelDescriptor, ModelRegistry, ModelRuntimeError, Modality,
    ProviderDescriptor, ProviderRegistry, TextGenerationParameters, TextGenerationRequest,
    TextGenerationResponse, TextModelNode)


def request(**values):
    defaults = dict(provider_id="registered-local", model_id="registered-model", prompt="A short proposal",
        parameters=TextGenerationParameters(temperature=0.0, max_output_tokens=128),
        job_id="original-job", cancellation=Event(), preparation_guard=lambda: None, dispatch_guard=lambda: None)
    defaults.update(values)
    return TextGenerationRequest(**defaults)


def route(**values):
    defaults = {"route_id": "a" * 64, "capability": "TEXT", "cloud": False, "available": True,
        "synthetic": False, "reasons": [], "identity": {"source_locality": "LOCAL_VERIFIED",
            "model_version": "existing-evidence", "adapter_hash": "existing-implementation"}}
    defaults.update(values)
    return defaults


def runtime(kind, calls):
    from app.model_center.discovery_bridge import LocalTextAdapter
    candidate = {"id": "registered-model", "provider_id": "registered-local", "model_name": "approved-model",
        "enabled_at": "original-enable-receipt", "source_locality": "LOCAL_VERIFIED",
        "model_evidence_fingerprint": "original-evidence", "runtime_config": {"type": kind,
            "management": "EXTERNAL", "endpoint": "http://127.0.0.1:9999"}}
    service = SimpleNamespace(check_model_dispatch=lambda row: calls.append("metadata"))
    bridge = SimpleNamespace(guard=lambda _: candidate, service=service,
        launch_on_demand=lambda *_: pytest.fail("process launch forbidden"))
    adapter = LocalTextAdapter(bridge, candidate)
    def wire(endpoint, path, body=None):
        calls.append((endpoint, path, deepcopy(body)))
        if kind == "OLLAMA":
            return {"done": True, "response": "Mocked protocol proposal", "prompt_eval_count": 2, "eval_count": 3}
        return {"choices": [{"finish_reason": "stop", "message": {"content": "Mocked protocol proposal"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}}
    adapter.client = SimpleNamespace(json=wire)
    providers, models = ProviderRegistry(), ModelRegistry()
    providers.register(ProviderDescriptor("registered-local", "Fixture", "local", frozenset({Modality.TEXT}), True, True), adapter)
    models.register(ModelDescriptor("registered-model", "registered-local", "Fixture", Modality.TEXT,
        frozenset({"generate", "stream"}), streaming=True))
    host = SimpleNamespace(provider_registry=providers, model_registry=models,
        is_remote_text_provider=lambda _: False, prepare_text_route=lambda *_: TextModelNode(providers, models))
    return host, candidate, adapter


def test_static_catalog_has_five_unavailable_families_without_any_host():
    rows = provider_catalog()
    assert [row["family"] for row in rows] == ["LOCAL_OLLAMA", "LM_STUDIO", "COMFYUI", "LLAMA_CPP", "API"]
    assert all(not row["availability"]["adapter_available"] and not row["availability"]["execution_available"] for row in rows)
    assert all(not row["capability"]["verified"] and row["real_model_verification"] == "NOT_RUN" for row in rows)
    assert rows[1]["availability"]["reasons"] == ["LMSTUDIO_LOCALITY_UNVERIFIED"]
    assert rows[2]["capability"]["advertised"] == ["IMAGE_GENERATION", "VIDEO_GENERATION"]


@pytest.mark.parametrize("provider,kind", [(LocalOllamaProvider, "OLLAMA"), (LlamaCppProvider, "LLAMA_CPP")])
def test_facades_use_only_original_registry_adapter_node_and_guarded_protocol(provider, kind):
    calls = []; host, _, _ = runtime(kind, calls)
    facade = provider(host, "registered-local", "registered-model")
    assert facade.availability().adapter_available
    assert facade.capabilities().verified == ("TEXT_GENERATION",)
    rows = provider_catalog(host)
    assert sum(row["availability"]["adapter_available"] for row in rows) == 1
    assert calls == []  # Listing never probes or executes.
    envelope = ProviderExecutionRequest("TEXT_GENERATION", request(
        preparation_guard=lambda: calls.append("prepare"), dispatch_guard=lambda: calls.append("dispatch")))
    events = list(facade.execute(envelope))
    assert [event.event_type for event in events] == ["generation.started", "generation.delta", "generation.completed"]
    assert calls[:4] == ["prepare", "prepare", "metadata", "dispatch"]
    assert len(calls) == 5 and calls[-1][0] == "http://127.0.0.1:9999"
    assert calls[-1][1] == ("/api/generate" if kind == "OLLAMA" else "/v1/chat/completions")
    result = facade.result(envelope, events[-1].response)
    assert result.text == "Mocked protocol proposal" and result.quality_verification == "NOT_RUN"
    assert result.parameters.max_output_tokens == 128 and result.provider_id == "registered-local"
    assert result.output_digest == sha256(result.text.encode()).hexdigest()
    assert result.request_digest == envelope.request_digest and result.proposal_only
    assert result.request_created_at <= result.result_recorded_at


@pytest.mark.parametrize("field", ["dispatch_guard", "preparation_guard", "cancellation", "job_id"])
def test_new_facade_cannot_bypass_prepared_request_guards(field):
    calls = []; host, _, _ = runtime("OLLAMA", calls)
    facade = LocalOllamaProvider(host, "registered-local", "registered-model")
    with pytest.raises(ValueError, match="PREPARED_GUARDS"):
        facade.execute(ProviderExecutionRequest("TEXT_GENERATION", request(**{field: None})))
    assert calls == []


@pytest.mark.parametrize("mutation", ["managed", "remote", "missing_evidence", "wrong_family", "disabled"])
def test_registered_label_never_grants_unsupported_authority(mutation):
    calls = []; host, candidate, _ = runtime("OLLAMA", calls)
    if mutation == "managed": candidate["runtime_config"]["management"] = "MANAGED"
    elif mutation == "remote": candidate["source_locality"] = "REMOTE"
    elif mutation == "missing_evidence": candidate["model_evidence_fingerprint"] = None
    elif mutation == "wrong_family": candidate["runtime_config"]["type"] = "LLAMA_CPP"
    else:
        descriptor = host.provider_registry.descriptors()[0]
        host.provider_registry.register(replace(descriptor, available=False), host.provider_registry._providers[descriptor.provider_id], replace=True)
    facade = LocalOllamaProvider(host, "registered-local", "registered-model")
    assert not facade.availability().adapter_available and not facade.capabilities().verified
    with pytest.raises((ValueError, ModelRuntimeError)):
        list(facade.execute(ProviderExecutionRequest("TEXT_GENERATION", request())))
    assert calls == []


def test_family_and_registration_replacement_between_prepare_and_iteration_blocks_transport():
    calls = []; host, candidate, _ = runtime("OLLAMA", calls)
    facade = LocalOllamaProvider(host, "registered-local", "registered-model")
    events = facade.execute(ProviderExecutionRequest("TEXT_GENERATION", request()))
    candidate["source_locality"] = "REMOTE"
    with pytest.raises(ValueError): list(events)
    assert calls == []


@pytest.mark.parametrize("moment", ["before_execute", "before_iteration", "after_metadata"])
def test_mutable_request_payload_is_rechecked_at_original_final_hop(moment):
    calls = []; host, _, adapter = runtime("OLLAMA", calls)
    value = request(context={"source": "original"})
    envelope = ProviderExecutionRequest("TEXT_GENERATION", value)
    if moment == "before_execute": value.context["source"] = "changed"
    if moment == "after_metadata":
        adapter.bridge.service.check_model_dispatch = lambda row: value.context.update(source="changed")
    facade = LocalOllamaProvider(host, "registered-local", "registered-model")
    with pytest.raises(ValueError, match="REQUEST_CHANGED"):
        events = facade.execute(envelope)
        if moment == "before_iteration": value.context["source"] = "changed"
        list(events)
    assert calls == []


@pytest.mark.parametrize("cls", [LMStudioProvider, ComfyUIProvider, ReservedAPIProvider, APIProvider])
def test_reserved_families_reject_before_transport_even_if_host_claims_local(cls):
    calls = []; host, candidate, adapter = runtime("OPENAI_COMPATIBLE_LOCAL", calls)
    candidate["evidence"] = {"model_listed": True, "size_bytes": 12345,
        "loaded_instances": [{"id": "loaded-local-looking", "config": {"context_length": 4096}}]}
    adapter.client.json = lambda *_args, **_kw: pytest.fail("reserved provider cannot contact LocalProbeClient")
    provider = cls(host, "registered-local", "registered-model")
    assert not provider.availability().adapter_available
    assert not provider.capabilities().verified
    with pytest.raises(ModelRuntimeError): provider.execute(ProviderExecutionRequest("TEXT_GENERATION", request()))
    assert calls == []


@pytest.mark.parametrize("values", [{"endpoint": "http://127.0.0.1:9000"}, {"min_host_vram_mib": True},
    {"min_host_ram_mib": 0}, {"allow_synthetic": "true"}, {"local_only": False},
    {"task_type": "AUDIO_GENERATION"}, {"preferred_route": "model-name"}, {"api_available": 1}, {"local_only": 1}])
def test_task_requirement_is_strict_and_cannot_include_execution_inputs(values):
    with pytest.raises(ValueError): TaskRequirement.model_validate(values)


def test_task_match_is_pure_advisory_and_requires_verified_capability():
    source = route(); original = deepcopy(source)
    result = match_task_requirement(TaskRequirement(), source)
    assert result.eligible and not result.execution_authority and not result.automatic_fallback
    assert result.hardware_state == "NOT_REQUESTED" and not result.gpu_fit_verified
    assert source == original
    advertised = route(identity={"source_locality": "LOCAL_VERIFIED"})
    result = match_task_requirement({}, advertised)
    assert not result.eligible and "VERIFIED_MODEL_CAPABILITY_REQUIRED" in result.reasons


@pytest.mark.parametrize("task,capability", [("IMAGE_GENERATION", "IMAGE"), ("VIDEO_GENERATION", "VIDEO")])
def test_task_advertisement_cannot_enable_image_or_video(task, capability):
    result = match_task_requirement({"task_type": task}, route(capability=capability))
    assert not result.eligible and "GRAPH_" + capability + "_EXECUTION_NOT_ENABLED" in result.reasons


@pytest.mark.parametrize("available", [False, True])
def test_api_availability_never_authorizes_cloud_or_fallback(available):
    result = match_task_requirement({"api_available": available}, route(cloud=True))
    assert not result.eligible and "API_PROVIDER_EXECUTION_NOT_ENABLED" in result.reasons
    assert "LOCAL_ONLY_REQUIRED" in result.reasons and not result.automatic_fallback


def test_exact_user_preference_and_synthetic_permission_are_never_implicit():
    assert match_task_requirement({"preferred_route": "a" * 64}, route()).preferred
    wrong = match_task_requirement({"preferred_route": "b" * 64}, route())
    assert not wrong.eligible and "EXACT_PREFERRED_ROUTE_REQUIRED" in wrong.reasons
    assert not match_task_requirement({}, route(synthetic=True)).eligible
    assert match_task_requirement({"allow_synthetic": True}, route(synthetic=True)).eligible


@pytest.mark.parametrize("hardware,state,eligible", [({}, "UNKNOWN", False),
    ({"state": "UNAVAILABLE", "vram_mib": 9999}, "UNKNOWN", False),
    ({"state": "HOST_TOTAL_CAPACITY", "vram_mib": True}, "UNKNOWN", False),
    ({"state": "HOST_TOTAL_CAPACITY", "vram_mib": -1}, "UNKNOWN", False),
    ({"state": "HOST_TOTAL_CAPACITY", "vram_mib": 4096}, "INSUFFICIENT", False),
    ({"state": "HOST_TOTAL_CAPACITY", "vram_mib": 8192}, "TOTAL_CAPACITY_ONLY", True)])
def test_vram_requirement_fails_closed_and_never_promises_gpu_fit(hardware, state, eligible):
    result = match_task_requirement({"min_host_vram_mib": 8192}, route(), hardware)
    assert result.eligible is eligible and result.hardware_state == state and not result.gpu_fit_verified


def test_ram_and_vram_are_independent_constraints():
    result = match_task_requirement({"min_host_ram_mib": 16000, "min_host_vram_mib": 8000}, route(),
        {"state": "HOST_TOTAL_CAPACITY", "ram_mib": 15000, "vram_mib": 9000})
    assert not result.eligible and result.reasons == ("HOST_RAM_INSUFFICIENT",)


def completion():
    return {"object": "chat.completion", "model": "exact-loaded-instance", "choices": [
        {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Protocol-only fixture"}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}}


def test_lmstudio_pure_wire_contract_uses_exact_instance_and_bounded_original_parameters():
    value = request(system_instruction="Reviewable instruction",
        parameters=TextGenerationParameters(temperature=0.25, max_output_tokens=123, stop_sequences=("END",)))
    payload = LMStudioProvider.wire_request(value, loaded_instance_id="exact-loaded-instance")
    assert payload == {"model": "exact-loaded-instance", "messages": [
        {"role": "system", "content": "Reviewable instruction"}, {"role": "user", "content": value.prompt}],
        "stream": False, "temperature": 0.25, "max_tokens": 123, "stop": ["END"]}
    decoded = LMStudioProvider.wire_response(value, completion(), loaded_instance_id="exact-loaded-instance")
    assert decoded.provider_id == value.provider_id and decoded.model_id == value.model_id
    assert decoded.usage.total_tokens == 5 and decoded.finish_reason == "completed"
    result = normalize_text_result(ProviderExecutionRequest("TEXT_GENERATION", value), decoded)
    assert result.quality_verification == "NOT_RUN" and result.proposal_only
    assert not LMStudioProvider().availability().adapter_available


@pytest.mark.parametrize("mutation", ["wrong_model", "no_choices", "multiple_choices", "bad_index", "length", "tool", "refusal",
    "wrong_role", "empty", "oversized", "usage_bool", "usage_negative", "usage_inconsistent", "object", "error"])
def test_lmstudio_decoder_rejects_malformed_or_nontext_response(mutation):
    data = completion(); choice = data["choices"][0]; message = choice["message"]
    if mutation == "wrong_model": data["model"] = "other-model"
    elif mutation == "no_choices": data["choices"] = []
    elif mutation == "multiple_choices": data["choices"] *= 2
    elif mutation == "bad_index": choice["index"] = False
    elif mutation == "length": choice["finish_reason"] = "length"
    elif mutation == "tool": message["tool_calls"] = []
    elif mutation == "refusal": message["refusal"] = "no"
    elif mutation == "wrong_role": message["role"] = "user"
    elif mutation == "empty": message["content"] = " "
    elif mutation == "oversized": message["content"] = "x" * 32001
    elif mutation == "usage_bool": data["usage"]["total_tokens"] = True
    elif mutation == "usage_negative": data["usage"]["prompt_tokens"] = -1
    elif mutation == "usage_inconsistent": data["usage"]["total_tokens"] = 6
    elif mutation == "object": data["object"] = "chat.completion.chunk"
    else: data["error"] = {"message": "failure"}
    with pytest.raises(ValueError): LMStudioProvider.wire_response(request(), data, loaded_instance_id="exact-loaded-instance")


@pytest.mark.parametrize("values", [{"parameters": TextGenerationParameters(max_output_tokens=2049)},
    {"prompt": "x" * 32001}, {"system_instruction": "x" * 32001},
    {"structured_output_schema": {"type": "object"}}, {"parameters": TextGenerationParameters(temperature=True, max_output_tokens=128)}])
def test_lmstudio_wire_encoder_enforces_bounded_plain_text(values):
    with pytest.raises(ValueError): LMStudioProvider.wire_request(request(**values), loaded_instance_id="exact-loaded-instance")


@pytest.mark.parametrize("changes", [{"provider_id": "wrong"}, {"model_id": "wrong"}, {"finish_reason": "length"},
    {"text": ""}, {"text": "x" * 32001}, {"execution_mode": "quality_verified"}, {"latency_ms": -1}])
def test_normalized_result_rejects_wrong_route_incomplete_and_unbounded_output(changes):
    value = request(); response = TextGenerationResponse("Draft", "completed", value.provider_id, value.model_id)
    with pytest.raises(ValueError): normalize_text_result(ProviderExecutionRequest("TEXT_GENERATION", value), replace(response, **changes))


def test_result_rejects_mutated_transient_request_and_keeps_system_input_in_digest():
    value = request(context={"source": "original"}); envelope = ProviderExecutionRequest("TEXT_GENERATION", value)
    response = TextGenerationResponse("Draft", "completed", value.provider_id, value.model_id)
    value.context["source"] = "changed"
    with pytest.raises(ValueError, match="REQUEST_CHANGED"): normalize_text_result(envelope, response)
    assert ProviderExecutionRequest("TEXT_GENERATION", request()).request_digest != ProviderExecutionRequest(
        "TEXT_GENERATION", request(system_instruction="changed")).request_digest


@pytest.mark.parametrize("stamp", ["not-a-timestamp", "2026-01-01T00:00:00", None,
    pytest.param((datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), id="future_utc")])
def test_normalized_result_rejects_invalid_naive_or_future_request_timestamps(stamp):
    value = request(); envelope = ProviderExecutionRequest("TEXT_GENERATION", value, created_at=stamp)
    response = TextGenerationResponse("Draft", "completed", value.provider_id, value.model_id)
    with pytest.raises(ValueError): normalize_text_result(envelope, response)


def test_result_json_shape_roundtrips_without_guards_or_invented_quality_and_rejects_reversed_time():
    value = request(); envelope = ProviderExecutionRequest("TEXT_GENERATION", value)
    response = TextGenerationResponse("Draft", "completed", value.provider_id, value.model_id)
    result = normalize_text_result(envelope, response)
    saved = result.model_dump(mode="json")
    assert saved["parameters"] == {"temperature": 0.0, "max_output_tokens": 128, "stop_sequences": []}
    assert saved["contract"] == "model-provider-result/1" and saved["quality_verification"] == "NOT_RUN"
    assert "guard" not in str(saved) and "cancellation" not in str(saved)
    assert ProviderExecutionResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValueError):
        ProviderExecutionResult.model_validate({**result.model_dump(), "result_recorded_at": "2020-01-01T00:00:00+00:00"})
