"""M4 host-bound graph text through the original JobManager, without a chapter.

Actual worker threads and File generation persistence; synthetic protocol only.
No paid provider, model process, installation, GPU or network request is made.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
import time
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from app import jobs as jobs_module
from app.jobs import JobManager, generation_content_available, require_whole_generation_acceptance
from app.model_execution import (APIProvider, GraphRequestBinding, LocalModelInvocation,
    graph_prompt_digest, guard_local_provider)
from app.model_runtime import (GenerationEvent, GenerationUsage, LegacyTextProviderAdapter,
    ModelDescriptor, ModelRuntimeError, Modality, ProviderDescriptor, TextGenerationResponse)
from app.providers import MockProvider
from app.repositories.file.generation import FileGenerationRepository
from app.runtime import Runtime
from app.services.generation_service import GenerationService
from app.stable_identity import StableIdentityStore

FLAGS = "ai_execution_v2,narrative_production_v2,model_broker_v2,author_context_inspector_v2"


class ForbiddenOwner:
    def __getattr__(self, name):
        raise AssertionError("Graph job must not access chapter/context/canon: " + name)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    from app.config import settings
    assert settings.enable_packaged_runtime is False
    runtime = Runtime(StableIdentityStore(tmp_path / "identity.json"))
    runtime.providers["mock"].delay_ms = 0
    monkeypatch.setattr(jobs_module, "runtime", runtime)
    from app.repository import FileRepository
    from app.experimental.store import ExperimentalStore
    from app.creative.project_store import CreativeProjectStore
    project = FileRepository(tmp_path)
    project.create_novel({"id": "blank-project", "title": "Independent graph fixture"})
    raw_store = ExperimentalStore(tmp_path, "file", "")
    creative_store = CreativeProjectStore(raw_store)
    incarnation = creative_store.incarnation("blank-project")
    owner = ForbiddenOwner()
    persistence = GenerationService(FileGenerationRepository(tmp_path))
    manager = JobManager(persistence, owner, owner, owner, memory_extractor=owner,
                         snapshot_required=True, collaboration_updates=owner)
    e = SimpleNamespace(runtime=runtime, manager=manager, persistence=persistence,
        binding={"graph_id": "graph-a", "graph_version": 1, "run_id": "run-a", "node_id": "model",
                 "project_incarnation": incarnation,
                 "input_digest": "a" * 64, "reviewed_preview_digest": "b" * 64,
                 "route_fingerprint": "c" * 64}, active=True, calls=[], guards=0)
    def authorize():
        e.guards += 1
        if not e.active: raise ValueError("synthetic authority revoked")
    e.authorize = authorize
    yield e
    for job in manager.jobs.values():
        if job.status not in manager.terminal: manager.cancel(job.id)
    deadline = time.monotonic() + 5
    while any(job.dispatch_hooks_required and job.terminal_hook_status is None for job in manager.jobs.values()) and time.monotonic() < deadline:
        time.sleep(.01)


def prepare(e, **changes):
    values = dict(project_id="blank-project", provider_id="mock", model_id="mock-writer",
        prompt="Exact synthetic graph prompt", actor_id="author-a",
        scope={"mode": "local", "novel_id": "blank-project"}, request_binding=deepcopy(e.binding),
        request_authorization=e.authorize, max_output_bytes=32000,
        deadline=(datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(),
        synthetic_allowed=True, max_output_tokens=256, temperature=0.0)
    values.update(changes)
    return e.manager.prepare_graph_job(**values)


def hooks(e, job):
    job.before_dispatch = lambda: e.calls.append(("dispatch", job.id))
    job.on_terminal = lambda: e.calls.append(("terminal", job.id, job.execution_outcome))
    return job


def wait(e, job):
    deadline = time.monotonic() + 5
    while True:
        with job.condition:
            if job.status in e.manager.terminal and job.terminal_hook_status is not None:
                return job
        if time.monotonic() >= deadline: pytest.fail("Original worker did not terminate: " + repr(job.public()))
        time.sleep(.005)


def transport(e, monkeypatch, callback=None, text="Synthetic proposed text"):
    adapter = e.runtime.provider_registry.resolve("mock")
    def stream(request):
        e.calls.append(("invoke", request))
        yield GenerationEvent("generation.started", request.job_id)
        if callback: callback(request)
        yield GenerationEvent("generation.delta", request.job_id, delta=text)
        yield GenerationEvent("generation.completed", request.job_id, response=TextGenerationResponse(
            text, "completed", "mock", "mock-writer", GenerationUsage(3, 4, 7), execution_mode="mock_standin"))
    monkeypatch.setattr(adapter, "stream_text", stream)


def test_original_job_manager_runs_exact_text_without_chapter_and_persists(env, monkeypatch):
    e = env; transport(e, monkeypatch)
    job = hooks(e, prepare(e))
    assert job.chapter_id is None and job.operation == "graph_text"
    assert e.persistence.load_all() == [] and e.calls == []
    assert job.expected_request_digest and len(job.expected_request_digest) == 64
    e.manager.start_prepared(job); wait(e, job)
    assert job.status == "COMPLETED" and job.output == "Synthetic proposed text"
    assert job.usage == {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}
    assert job.context_snapshot_id is None and job.base_chapter_version is None
    assert job.graph_binding == e.binding and job.terminal_hook_status == "COMPLETED"
    request = next(item[1] for item in e.calls if item[0] == "invoke")
    assert request.prompt == "Exact synthetic graph prompt" and request.context == {}
    assert request.parameters.max_output_tokens == 256 and request.job_id == job.id
    assert [item[0] for item in e.calls] == ["dispatch", "invoke", "terminal"]
    assert len(job.route_decisions) == 1
    saved = e.persistence.get(job.id)
    assert saved["chapter_id"] is None and saved["status"] == "COMPLETED"
    assert "prepared_text_invocation" not in saved and "request_authorization" not in saved
    assert "Exact synthetic graph prompt" not in str(saved)
    assert generation_content_available(job)
    with pytest.raises(ValueError, match="NOT_PREPARED"): e.manager.start_prepared(job)


def test_generic_review_and_diff_cannot_apply_or_reject_graph_output(env, monkeypatch):
    e = env; transport(e, monkeypatch)
    job = hooks(e, prepare(e)); e.manager.start_prepared(job); wait(e, job)
    for operation in (lambda: require_whole_generation_acceptance(job), lambda: e.manager.accept(job.id),
                      lambda: e.manager.reject(job.id), lambda: e.manager.diff(job.id)):
        with pytest.raises(HTTPException) as caught: operation()
        assert caught.value.status_code == 409
    assert job.status == "COMPLETED"


@pytest.mark.parametrize("accepted", [False, True])
def test_default_off_and_acceptance_have_no_registration_or_dispatch(env, monkeypatch, accepted):
    e = env
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS if accepted else "")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if accepted else "")
    monkeypatch.setattr(e.runtime, "prepare_text_route", lambda *a: pytest.fail("route invocation forbidden"))
    with pytest.raises(HTTPException): prepare(e)
    assert not e.calls and not e.persistence.load_all()


def test_synthetic_requires_explicit_permission_and_api_is_reserved(env):
    with pytest.raises(ValueError, match="SYNTHETIC_NOT_AUTHORIZED"): prepare(env, synthetic_allowed=False)
    with pytest.raises(ModelRuntimeError): APIProvider().stream_text(None)
    assert APIProvider.available is False
    assert guard_local_provider(env.runtime, "mock", "mock-writer", True)["synthetic"] is True


def test_missing_hooks_and_changed_request_are_denied_before_admission(env):
    e = env; job = prepare(e)
    with pytest.raises(ValueError, match="BROKER_HOOKS"): e.manager.start_prepared(job)
    hooks(e, job); job.graph_binding["graph_version"] = 2
    with pytest.raises((ValueError, HTTPException)): e.manager.start_prepared(job)
    assert not e.calls and not e.persistence.load_all()


@pytest.mark.parametrize("mutation", ["actor", "scope", "prompt", "route", "deadline", "origin"])
def test_exact_host_binding_cannot_be_replaced(env, mutation):
    e = env; job = hooks(e, prepare(e))
    if mutation == "actor": job.actor_id = "other"
    elif mutation == "scope": job.scope["novel_id"] = "other"
    elif mutation == "prompt":
        job.prepared_text_invocation = replace(job.prepared_text_invocation,
            request=replace(job.prepared_text_invocation.request, prompt="changed prompt"))
    elif mutation == "route": job.requested_provider = "ollama"
    elif mutation == "deadline": job.generation_deadline = (datetime.now(timezone.utc) + timedelta(seconds=150)).isoformat()
    else: job.experimental_origin = None
    with pytest.raises((ValueError, HTTPException)): e.manager.start_prepared(job)
    assert not e.calls and not e.persistence.load_all()


def test_late_source_revocation_suppresses_every_chunk_and_settles_once(env, monkeypatch):
    e = env
    transport(e, monkeypatch, lambda request: setattr(e, "active", False))
    job = hooks(e, prepare(e)); e.manager.start_prepared(job); wait(e, job)
    assert job.status == "FAILED" and not job.output
    assert job.error_code == "GENERATION_AUTHORITY_REVOKED"
    assert not generation_content_available(job)
    assert len([call for call in e.calls if call[0] == "terminal"]) == 1
    assert list(e.manager.events(job.id)) == []


def test_cancel_during_synthetic_transport_discards_late_completion(env, monkeypatch):
    e = env; entered = Event(); release = Event()
    def block(request):
        entered.set(); assert release.wait(3)
    transport(e, monkeypatch, block)
    job = hooks(e, prepare(e)); e.manager.start_prepared(job)
    try:
        assert entered.wait(3)
        e.manager.cancel(job.id)
        assert job.status == "CANCELLED" and not job.output
    finally: release.set()
    wait(e, job)
    assert job.status == "CANCELLED" and not job.output
    assert len([call for call in e.calls if call[0] == "terminal"]) == 1


def test_restarted_completed_job_cannot_reconstruct_authority_or_replay(env, monkeypatch):
    e = env; transport(e, monkeypatch)
    job = hooks(e, prepare(e)); e.manager.start_prepared(job); wait(e, job)
    owner = ForbiddenOwner()
    restored = JobManager(e.persistence, owner, owner, owner, memory_extractor=owner)
    found = restored.get(job.id)
    assert found.prepared_text_invocation is None and found.request_authorization is None
    assert not generation_content_available(found)
    with pytest.raises(ValueError): restored.start_prepared(found)
    assert len([call for call in e.calls if call[0] == "invoke"]) == 1


def test_output_and_deadline_bounds_use_original_worker_failure_path(env, monkeypatch):
    e = env; transport(e, monkeypatch, text="x" * 300)
    job = hooks(e, prepare(e, max_output_bytes=256)); e.manager.start_prepared(job); wait(e, job)
    assert job.status == "FAILED" and not job.output and job.error_code == "GENERATION_OUTPUT_LIMIT"
    with pytest.raises(ValueError, match="DEADLINE"): prepare(e, deadline=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())


def test_adapter_replacement_after_preparation_has_no_provider_call(env):
    e = env; job = hooks(e, prepare(e))
    descriptor = next(p for p in e.runtime.provider_registry.descriptors() if p.provider_id == "mock")
    e.runtime.provider_registry.register(descriptor, LegacyTextProviderAdapter("mock", MockProvider(0, "")), replace=True)
    with pytest.raises((ValueError, HTTPException)): e.manager.start_prepared(job)
    assert not e.calls


def test_local_label_cannot_enable_arbitrary_or_legacy_ollama_provider(env):
    with pytest.raises(ValueError, match="VERIFIED_LOCAL_ADAPTER"): guard_local_provider(env.runtime, "ollama", next(m.model_id for m in env.runtime.model_registry.descriptors() if m.provider_id == "ollama"))


@pytest.mark.parametrize("management", ["MANAGED", "REMOTE", None])
def test_managed_runtime_is_rejected_without_launch_or_probe(env, monkeypatch, management):
    from app.model_center.discovery_bridge import LocalTextAdapter
    e = env
    candidate = {"id": "local-text", "provider_id": "local-text-provider", "source_locality": "LOCAL_VERIFIED",
        "model_evidence_fingerprint": "evidence", "runtime_config": {"management": management, "type": "LLAMA_CPP"}}
    bridge = SimpleNamespace(guard=lambda identifier: candidate,
        launch_on_demand=lambda *a: pytest.fail("managed launch forbidden"))
    adapter = LocalTextAdapter(bridge, candidate)
    e.runtime.provider_registry.register(ProviderDescriptor("local-text-provider", "Local", "local", frozenset({Modality.TEXT}), True, True), adapter)
    e.runtime.model_registry.register(ModelDescriptor("local-text", "local-text-provider", "Local", Modality.TEXT, frozenset({"generate", "stream"}), streaming=True))
    with pytest.raises(ValueError, match="EXTERNAL_LOCAL_RUNTIME_REQUIRED"):
        guard_local_provider(e.runtime, "local-text-provider", "local-text")


def test_digest_and_binding_contract_are_strict_and_deterministic(env):
    assert GraphRequestBinding.model_validate(env.binding).project_incarnation.startswith("file:")
    assert graph_prompt_digest("text", binding={"b": 2, "a": 1}) == graph_prompt_digest("text", binding={"a": 1, "b": 2})
    assert graph_prompt_digest("text", max_output_tokens=1) != graph_prompt_digest("text", max_output_tokens=2)
    for values in ({"max_output_tokens": True}, {"max_output_tokens": 2049}, {"temperature": float("nan")}, {"temperature": True}):
        with pytest.raises(ValueError): graph_prompt_digest("text", **values)
    with pytest.raises(ValueError): GraphRequestBinding.model_validate({**env.binding, "graph_version": True})
    with pytest.raises(ValueError): GraphRequestBinding.model_validate({**env.binding, "endpoint": "https://unapproved.example"})


@pytest.mark.parametrize("kind", ["event_job", "completion_text", "no_completion", "finish_reason"])
def test_malformed_completion_cannot_publish_graph_output(env, monkeypatch, kind):
    e = env
    def stream(request):
        yield GenerationEvent("generation.delta", "wrong-job" if kind == "event_job" else request.job_id, delta="draft")
        if kind != "no_completion":
            yield GenerationEvent("generation.completed", request.job_id, response=TextGenerationResponse(
                "other" if kind == "completion_text" else "draft", "length" if kind == "finish_reason" else "completed", "mock", "mock-writer"))
    monkeypatch.setattr(e.runtime.provider_registry.resolve("mock"), "stream_text", stream)
    job = hooks(e, prepare(e)); e.manager.start_prepared(job); wait(e, job)
    assert job.status == "FAILED" and not job.output
    assert len([call for call in e.calls if call[0] == "terminal"]) == 1


def test_revocation_during_terminal_accounting_cannot_publish_completion(env, monkeypatch):
    e = env; transport(e, monkeypatch)
    job = hooks(e, prepare(e))
    def terminal():
        e.calls.append(("terminal", job.id)); e.active = False
    job.on_terminal = terminal
    e.manager.start_prepared(job); wait(e, job)
    assert job.status == "FAILED" and not job.output
    assert job.error_code == "GENERATION_AUTHORITY_REVOKED"
    assert job.execution_outcome == "COMPLETED" and job.terminal_hook_status == "COMPLETED"
    assert not generation_content_available(job)


@pytest.mark.parametrize("runtime_type", ["OLLAMA", "LLAMA_CPP"])
def test_original_external_local_adapter_uses_exact_mocked_transport_only(env, monkeypatch, runtime_type):
    from app.model_center.discovery_bridge import LocalTextAdapter
    e = env
    candidate = {"id": "local-text", "provider_id": "local-text-provider", "model_name": "explicit-model",
        "source_locality": "LOCAL_VERIFIED", "model_evidence_fingerprint": "evidence", "enabled_at": "receipt",
        "runtime_config": {"management": "EXTERNAL", "type": runtime_type, "endpoint": "http://127.0.0.1:8000"}}
    bridge = SimpleNamespace(guard=lambda identifier: candidate,
        service=SimpleNamespace(check_model_dispatch=lambda value: e.calls.append(("metadata", value["id"]))),
        launch_on_demand=lambda *a: pytest.fail("managed launch forbidden"))
    adapter = LocalTextAdapter(bridge, candidate)
    def response(endpoint, path, body):
        assert endpoint == "http://127.0.0.1:8000"
        e.calls.append(("wire", path, deepcopy(body)))
        if runtime_type == "OLLAMA":
            return {"response": "Local adapter contract proposal", "done": True, "prompt_eval_count": 3, "eval_count": 4}
        return {"choices": [{"message": {"content": "Local adapter contract proposal"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}
    adapter.client = SimpleNamespace(json=response)
    monkeypatch.setattr(adapter, "health_check", lambda: pytest.fail("health probe forbidden"))
    e.runtime.provider_registry.register(ProviderDescriptor("local-text-provider", "Local", "local", frozenset({Modality.TEXT}), True, True), adapter)
    e.runtime.model_registry.register(ModelDescriptor("local-text", "local-text-provider", "Local", Modality.TEXT,
        frozenset({"generate", "stream", "buffered_stream"}), streaming=True))
    assert guard_local_provider(e.runtime, "local-text-provider", "local-text") == {"synthetic": False, "streaming": "BUFFERED"}
    assert not e.calls
    job = hooks(e, prepare(e, provider_id="local-text-provider", model_id="local-text", synthetic_allowed=False))
    e.manager.start_prepared(job); wait(e, job)
    assert job.status == "COMPLETED" and job.output == "Local adapter contract proposal"
    wire = [call for call in e.calls if call[0] == "wire"]
    assert len(wire) == 1 and wire[0][2]["model"] == "explicit-model"
    assert [call[0] for call in e.calls] == ["metadata", "dispatch", "wire", "terminal"]
    assert wire[0][1] == ("/api/generate" if runtime_type == "OLLAMA" else "/v1/chat/completions")
    assert len([call for call in e.calls if call[0] == "terminal"]) == 1


def test_settlement_failure_keeps_accounting_blocker_and_hides_graph_text(env, monkeypatch):
    e = env; transport(e, monkeypatch)
    job = hooks(e, prepare(e))
    def failed(): raise OSError("private accounting fixture error")
    job.on_terminal = failed
    e.manager.start_prepared(job); wait(e, job)
    assert job.status == "FAILED" and not job.output
    assert job.terminal_hook_status == "FAILED_RECONCILIATION_REQUIRED"
    assert job.error_code == "TERMINAL_RECONCILIATION_REQUIRED"
    assert not generation_content_available(job)


def test_natural_deadline_during_blocked_adapter_discards_late_result(env, monkeypatch):
    e = env; transport(e, monkeypatch, lambda request: time.sleep(.3))
    job = hooks(e, prepare(e, deadline=(datetime.now(timezone.utc) + timedelta(seconds=.2)).isoformat()))
    e.manager.start_prepared(job); wait(e, job)
    assert job.status == "FAILED" and not job.output
    assert job.error_code == "GENERATION_DEADLINE_EXCEEDED"
    assert len([call for call in e.calls if call[0] == "terminal"]) == 1


def test_queued_local_adapter_cannot_change_external_route_into_managed_launch(env, monkeypatch):
    from app.model_center.discovery_bridge import LocalTextAdapter
    e = env; waiting = Event()
    candidate = {"id": "local-text", "provider_id": "local-text-provider", "model_name": "explicit-model",
        "source_locality": "LOCAL_VERIFIED", "model_evidence_fingerprint": "evidence", "enabled_at": "receipt",
        "runtime_config": {"management": "EXTERNAL", "type": "LLAMA_CPP", "endpoint": "http://127.0.0.1:8000"}}
    bridge = SimpleNamespace(guard=lambda identifier: candidate,
        service=SimpleNamespace(check_model_dispatch=lambda value: e.calls.append(("metadata",))),
        launch_on_demand=lambda *a: e.calls.append(("launch",)))
    adapter = LocalTextAdapter(bridge, candidate)
    adapter.client = SimpleNamespace(json=lambda *a, **kw: pytest.fail("transport forbidden"))
    original = adapter.generate_text
    def queued(request): waiting.set(); return original(request)
    monkeypatch.setattr(adapter, "generate_text", queued)
    e.runtime.provider_registry.register(ProviderDescriptor("local-text-provider", "Local", "local", frozenset({Modality.TEXT}), True, True), adapter)
    e.runtime.model_registry.register(ModelDescriptor("local-text", "local-text-provider", "Local", Modality.TEXT,
        frozenset({"generate", "stream", "buffered_stream"}), streaming=True))
    job = hooks(e, prepare(e, provider_id="local-text-provider", model_id="local-text", synthetic_allowed=False))
    with adapter.execution_lock:
        e.manager.start_prepared(job)
        assert waiting.wait(3)
        candidate["runtime_config"]["management"] = "MANAGED"
    wait(e, job)
    assert job.status == "FAILED" and not job.output
    assert not any(call[0] in {"launch", "metadata", "dispatch"} for call in e.calls)
    assert len([call for call in e.calls if call[0] == "terminal"]) == 1


def test_preparation_guard_cannot_authorize_a_captured_managed_candidate(env):
    from app.model_center.discovery_bridge import LocalTextAdapter
    from app.model_runtime import TextGenerationRequest
    e = env
    candidate = {"id": "local-text", "provider_id": "local-text-provider", "model_name": "explicit-model",
        "runtime_config": {"management": "MANAGED", "type": "LLAMA_CPP"}}
    bridge = SimpleNamespace(guard=lambda identifier: candidate,
        launch_on_demand=lambda *a: pytest.fail("captured managed launch forbidden"))
    adapter = LocalTextAdapter(bridge, candidate)
    def prepare_guard():
        candidate["runtime_config"] = {"management": "EXTERNAL", "type": "LLAMA_CPP"}
    request = TextGenerationRequest("local-text-provider", "local-text", "Test prompt",
        preparation_guard=prepare_guard)
    with pytest.raises(ModelRuntimeError): adapter.generate_text(request)
    assert candidate["runtime_config"]["management"] == "EXTERNAL"


def test_graph_guard_checks_live_authority_once_per_non_dispatch_boundary(env):
    e = env; job = hooks(e, prepare(e)); before = e.guards
    e.manager._guard_graph_request(job)
    assert e.guards == before + 1 and not e.calls
    e.manager._guard_graph_request(job)
    assert e.guards == before + 2  # A new boundary is always fresh.


def test_graph_dispatch_guard_rechecks_live_authority_after_broker_io(env):
    e = env; job = hooks(e, prepare(e)); before = e.guards
    order = []
    original = job.request_authorization
    def authority():
        order.append("authority"); original()
    job.request_authorization = authority
    job.before_dispatch = lambda: order.append("broker")
    e.manager._guard_graph_request(job, dispatch=True)
    assert order == ["authority", "broker", "authority"] and e.guards == before + 2


@pytest.mark.parametrize("change", ["revoke", "origin", "bounds", "cancel", "output", "deadline"])
def test_graph_dispatch_guard_rejects_changes_during_broker_io(env, change):
    e = env
    options = {"deadline": (datetime.now(timezone.utc) + timedelta(seconds=.15)).isoformat()} if change == "deadline" else {}
    job = hooks(e, prepare(e, **options))
    job._generation_bounds = (job.generation_max_output_bytes, job.generation_deadline)
    def broker():
        if change == "revoke": e.active = False
        elif change == "origin": job.experimental_origin = "author_context"
        elif change == "bounds": job.generation_max_output_bytes -= 1
        elif change == "cancel": job.cancelled.set()
        elif change == "output": job.output = "x" * (job.generation_max_output_bytes + 1)
        elif change == "deadline": time.sleep(.2)
    job.before_dispatch = broker
    with pytest.raises((ValueError, ModelRuntimeError)):
        e.manager._guard_graph_request(job, dispatch=True)
    if change == "deadline": assert job.generation_bound_failure == "GENERATION_DEADLINE_EXCEEDED"
    if change == "output": assert job.generation_bound_failure == "GENERATION_OUTPUT_LIMIT" and not job.output


def test_graph_guard_origin_and_preexisting_cancel_cannot_skip_authority(env):
    e = env; job = hooks(e, prepare(e)); before = e.guards
    job.experimental_origin = None
    with pytest.raises(ValueError, match="GRAPH_ORIGIN_REQUIRED"):
        e.manager._guard_graph_request(job)
    job.experimental_origin = "creative_graph_model"; job.cancelled.set()
    with pytest.raises(ModelRuntimeError): e.manager._guard_graph_request(job)
    assert e.guards == before and not e.calls
