from __future__ import annotations

import pytest
from threading import Event

from app.model_runtime import (
    GenerationRuntime,
    LegacyTextProviderAdapter,
    ModelDescriptor,
    ModelRegistry,
    ModelRuntimeError,
    Modality,
    ProviderDescriptor,
    ProviderRegistry,
    RuntimeErrorCode,
    TextGenerationParameters,
    TextGenerationRequest,
    TextModelNodeInput,
)
from app.providers import MockProvider


def runtime(*, enabled=True, modality=Modality.TEXT, streaming=True, failure="", available=True):
    providers = ProviderRegistry()
    models = ModelRegistry()
    provider = MockProvider(0, failure)
    providers.register(
        ProviderDescriptor("mock", "内置测试服务", "development", frozenset({Modality.TEXT}), True, available),
        LegacyTextProviderAdapter("mock", provider),
    )
    models.register(
        ModelDescriptor(
            "mock-writer",
            "mock",
            "内置测试写作模型",
            modality,
            frozenset({"generate", "stream"}),
            8192,
            streaming=streaming,
            enabled=enabled,
        )
    )
    return GenerationRuntime(providers, models)


def request(**changes):
    values = {"provider_id": "mock", "model_id": "mock-writer", "prompt": "继续这一章", "job_id": "job-1"}
    values.update(changes)
    return TextGenerationRequest(**values)


def test_provider_and_model_registries_use_stable_ids():
    value = runtime()
    assert value.providers.descriptors()[0].provider_id == "mock"
    assert value.models.descriptors()[0].model_id == "mock-writer"
    assert value.models.descriptors()[0].display_name == "内置测试写作模型"


def test_text_model_node_executes_normalized_request():
    output = runtime().text_node.execute(TextModelNodeInput(request()))
    assert output.generated_text
    assert output.response.provider_id == "mock"
    assert output.response.model_id == "mock-writer"
    assert output.job_reference == "job-1"


def test_text_model_node_stream_has_normalized_events():
    events = list(runtime().text_node.stream(TextModelNodeInput(request())))
    assert events[0].event_type == "generation.started"
    assert events[-1].event_type == "generation.completed"
    assert "".join(item.delta for item in events if item.event_type == "generation.delta")


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ({"provider_id": "missing"}, RuntimeErrorCode.PROVIDER_NOT_FOUND),
        ({"model_id": "missing"}, RuntimeErrorCode.MODEL_NOT_FOUND),
    ],
)
def test_unknown_runtime_selection_fails_safely(value, code):
    with pytest.raises(ModelRuntimeError) as caught:
        runtime().text_node.execute(TextModelNodeInput(request(**value)))
    assert caught.value.code == code


def test_disabled_model_cannot_execute():
    with pytest.raises(ModelRuntimeError) as caught:
        runtime(enabled=False).text_node.execute(TextModelNodeInput(request()))
    assert caught.value.code is RuntimeErrorCode.MODEL_DISABLED


def test_non_text_model_rejects_text_generation():
    with pytest.raises(ModelRuntimeError) as caught:
        runtime(modality=Modality.IMAGE).text_node.execute(TextModelNodeInput(request()))
    assert caught.value.code is RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED


def test_unsupported_streaming_fails_before_provider_call():
    with pytest.raises(ModelRuntimeError) as caught:
        list(runtime(streaming=False).text_node.stream(TextModelNodeInput(request())))
    assert caught.value.code is RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED


def test_unavailable_provider_fails_before_execution():
    with pytest.raises(ModelRuntimeError) as caught:
        runtime(available=False).text_node.execute(TextModelNodeInput(request()))
    assert caught.value.code is RuntimeErrorCode.PROVIDER_UNAVAILABLE


def test_unsupported_structured_output_fails_before_provider_call():
    with pytest.raises(ModelRuntimeError) as caught:
        runtime().text_node.execute(TextModelNodeInput(request(structured_output_schema={"type": "object"})))
    assert caught.value.code is RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED


def test_model_descriptor_exposes_stable_text_capabilities():
    descriptor = runtime().models.descriptors()[0]
    assert descriptor.modality is Modality.TEXT
    assert descriptor.capabilities == frozenset({"generate", "stream"})
    assert descriptor.streaming is True
    assert descriptor.structured_output is False


def test_parameters_are_validated():
    with pytest.raises(ModelRuntimeError) as caught:
        TextGenerationParameters(temperature=3)
    assert caught.value.code is RuntimeErrorCode.INVALID_REQUEST


def test_provider_error_is_normalized_without_secret_or_raw_exception():
    secret = "sk-phase1-secret"
    with pytest.raises(ModelRuntimeError) as caught:
        runtime(failure=secret).text_node.execute(TextModelNodeInput(request()))
    assert caught.value.code is RuntimeErrorCode.PROVIDER_UNAVAILABLE
    assert secret not in caught.value.safe_message
    assert "Mock failure" not in caught.value.safe_message


def test_contracts_do_not_contain_credentials():
    secret = "phase1-private-credential"
    dumped = repr(request(metadata={"purpose": "rewrite"}))
    assert secret not in dumped
    assert "authorization" not in dumped.casefold()


def test_generic_error_contract_has_real_provider_categories_and_safe_metadata():
    error = ModelRuntimeError(
        RuntimeErrorCode.RATE_LIMITED, "请求过于频繁", retryable=True,
        provider_id="provider", model_id="model", metadata={"retry_after": 2},
    )
    assert RuntimeErrorCode.AUTHENTICATION_FAILED.value == "AUTHENTICATION_FAILED"
    assert RuntimeErrorCode.TIMEOUT.value == "TIMEOUT"
    assert error.provider_id == "provider" and error.model_id == "model"
    assert error.metadata == {"retry_after": 2}


def test_cancel_signal_produces_one_cancelled_terminal_event():
    signal = Event(); signal.set()
    events = list(runtime().text_node.stream(TextModelNodeInput(request(cancellation=signal))))
    terminal = [event for event in events if event.event_type in {"generation.completed", "generation.failed", "generation.cancelled"}]
    assert [(event.event_type, event.error_code) for event in terminal] == [
        ("generation.cancelled", RuntimeErrorCode.CANCELLED)
    ]


def test_provider_failure_produces_one_failed_terminal_event():
    events = list(runtime(failure="private-provider-detail").text_node.stream(TextModelNodeInput(request())))
    terminal = [event for event in events if event.event_type in {"generation.completed", "generation.failed", "generation.cancelled"}]
    assert [(event.event_type, event.error_code) for event in terminal] == [
        ("generation.failed", RuntimeErrorCode.PROVIDER_UNAVAILABLE)
    ]


def test_streaming_usage_is_truthfully_unavailable_for_legacy_chunks():
    completed = list(runtime().text_node.stream(TextModelNodeInput(request())))[-1]
    assert completed.response is not None
    assert completed.response.usage is None


def test_provider_health_descriptor_distinguishes_not_configured():
    providers = ProviderRegistry()
    providers.register(
        ProviderDescriptor("off", "未配置服务", "remote", frozenset({Modality.TEXT}), False, False, "not_configured"),
        LegacyTextProviderAdapter("off", MockProvider()),
    )
    assert providers.descriptors()[0].health_status == "not_configured"
    assert providers.is_configured("off") is False
