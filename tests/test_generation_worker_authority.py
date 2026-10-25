"""Live ordinary-author authority through real File/API/JobManager workers.

Scheduling gates and a MockProvider observe the original worker and node; they
never replace source reads, authorization decisions, or worker dispatch logic.
"""
import copy
import json
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import api, jobs as jobs_module
from app.author_request import request_digest
from app.experimental import author_context_api
from app.experimental.author_context_api import AuthorPreparer, AuthorPreviewInput
from app.experimental.flags import require_flag
from app.services.generation_idempotency_authority import GenerationIdempotencyAuthority
from app.config import Settings
from app.idempotency import IdempotencyStore
from app.jobs import Job, JobManager
from app.providers import MockProvider
from app.repositories.factory import create_repository_bundle
from app.router import Route
from app.runtime import Runtime
from app.services import CanonService, ChapterService, ContextService, GenerationService, LoreService, NovelService
from app.stable_identity import StableIdentityStore


@pytest.fixture
def source(tmp_path, monkeypatch):
    import app.main as main_module
    from app.main import app

    config = Settings(storage_backend="file", novel_data=tmp_path, mock_provider=True,
                      enable_collaboration_runtime=False, enable_packaged_runtime=False)
    bundle = create_repository_bundle(config, tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    novel = novels.create({"id": "worker-book", "title": "Original owner"})
    chapter = chapters.create(novel["id"], {"title": "One", "content": "ORIGINAL_SOURCE"})
    chapter = chapters.get(chapter["id"])
    contexts = ContextService(bundle.novels, bundle.chapters, LoreService(bundle.lore))
    manager = JobManager(generations=GenerationService(bundle.generations), chapters=chapters,
        contexts=contexts, canon=CanonService(bundle.canon), snapshot_required=False,
        memory_extractor=SimpleNamespace(enqueue=lambda *_: "synthetic-memory-job"))
    runtime = Runtime(StableIdentityStore(tmp_path / "runtime" / "identities.json"))
    counts = {key: 0 for key in ("callback", "context", "snapshot", "adapter", "stream", "dispatch_guard", "outbound")}
    hooks = SimpleNamespace(after_context=None, after_stream=None)

    class ObservedMock(MockProvider):
        def stream(self, *args, **kwargs):
            counts["stream"] += 1
            yield from super().stream(*args, **kwargs)
            if hooks.after_stream is not None:
                hooks.after_stream()

    runtime.providers["mock"] = ObservedMock(delay_ms=0)
    runtime._sync_model("mock", "mock-writer")
    adapter = runtime.provider_registry.resolve("mock")
    original_adapter = adapter.stream_text
    def adapter_stream(request):
        counts["adapter"] += 1
        return original_adapter(request)
    monkeypatch.setattr(adapter, "stream_text", adapter_stream)
    for module in (api, jobs_module, main_module):
        monkeypatch.setattr(module, "settings", config)
    monkeypatch.setattr(api, "runtime", runtime)
    monkeypatch.setattr(jobs_module, "runtime", runtime)
    monkeypatch.setattr(api, "novel_service", novels)
    monkeypatch.setattr(api, "chapter_service", chapters)
    monkeypatch.setattr(api, "jobs", manager)
    monkeypatch.setattr(api, "_idempotency_store", IdempotencyStore(tmp_path / "idempotency.json"))
    entered, release, finished = Event(), Event(), Event()
    dispatch_entered, dispatch_release = Event(), Event()
    original_run = manager._run
    def worker(job):
        entered.set()
        assert release.wait(10), "worker release timed out"
        try:
            original_run(job)
        finally:
            finished.set()
    monkeypatch.setattr(manager, "_run", worker)
    original_prepare = manager.prepare_job
    authority = []
    def prepare(operation, payload, actor=None, scope=None, request_authorization=None):
        authority.append(request_authorization)
        def counted():
            counts["callback"] += 1
            return request_authorization()
        return original_prepare(operation, payload, actor, scope,
            counted if request_authorization is not None else None)
    monkeypatch.setattr(manager, "prepare_job", prepare)
    original_context = contexts.for_chapter
    def context(*args, **kwargs):
        counts["context"] += 1
        result = original_context(*args, **kwargs)
        if hooks.after_context is not None:
            hooks.after_context()
        return result
    monkeypatch.setattr(contexts, "for_chapter", context)
    original_snapshot = contexts.save_snapshot
    def snapshot(*args, **kwargs):
        counts["snapshot"] += 1
        return original_snapshot(*args, **kwargs)
    monkeypatch.setattr(contexts, "save_snapshot", snapshot)
    original_outbound = manager._validate_outbound_sources
    def outbound(*args, **kwargs):
        counts["outbound"] += 1
        return original_outbound(*args, **kwargs)
    monkeypatch.setattr(manager, "_validate_outbound_sources", outbound)
    original_guard = manager._guard_author_request
    def guard(*args, **kwargs):
        counts["dispatch_guard"] += int(kwargs.get("dispatch", False))
        return original_guard(*args, **kwargs)
    monkeypatch.setattr(manager, "_guard_author_request", guard)
    def gate_dispatch():
        node = runtime.generation_runtime.text_node
        original_stream = node.stream
        def stream(value):
            dispatch_entered.set()
            assert dispatch_release.wait(10), "dispatch release timed out"
            yield from original_stream(value)
        monkeypatch.setattr(node, "stream", stream)
    payload = {"novel_id": novel["id"], "chapter_id": chapter["id"], "instruction": "Continue",
               "profile": "LOCAL_ONLY", "provider_id": "mock", "model_id": "mock-writer"}
    fixture = SimpleNamespace(root=tmp_path, bundle=bundle, novels=novels, chapters=chapters,
        chapter=chapter, contexts=contexts, manager=manager, runtime=runtime, counts=counts,
        hooks=hooks, entered=entered, release=release, finished=finished,
        dispatch_entered=dispatch_entered, dispatch_release=dispatch_release,
        gate_dispatch=gate_dispatch, payload=payload, authority=authority,
        client=TestClient(app, raise_server_exceptions=False))
    yield fixture
    release.set()
    dispatch_release.set()
    if entered.is_set():
        assert finished.wait(10), "worker did not finish during cleanup"


def _post(source, *, keyed=True, automatic_route=False):
    payload = dict(source.payload)
    if automatic_route:
        payload.pop("provider_id")
        payload.pop("model_id")
    response = source.client.post("/api/generate/continue", json=payload,
        headers={"Idempotency-Key": "worker-key"} if keyed else {})
    assert response.status_code == 202, response.text
    assert source.entered.wait(10)
    job = source.manager.jobs[response.json()["job_id"]]
    assert response.json()["status"] == "QUEUED"
    assert source.counts["context"] == source.counts["adapter"] == 0
    return job


def _mutate(source, change):
    if change == "archive":
        source.chapters.archive(source.chapter["id"], source.chapter["version"])
        assert source.chapters.get(source.chapter["id"])["is_archived"]
    else:
        marker = source.root / "novels" / source.chapter["novel_id"] / "creative_project_v2.json"
        old_owner = json.loads(marker.read_text())["project_incarnation"]
        source.novels.delete(source.chapter["novel_id"])
        source.novels.create({"id": source.chapter["novel_id"], "title": "Replacement owner"})
        new_chapter = source.chapters.create(source.chapter["novel_id"],
            {"title": "Replacement", "content": "REPLACEMENT_OWNER_SOURCE"})
        assert new_chapter["id"] == source.chapter["id"]
        from app.services.generation_idempotency_authority import GenerationIdempotencyAuthority
        assert GenerationIdempotencyAuthority(source.novels, source.chapters).capture_new(
            source.chapter["novel_id"]) != "file:" + old_owner
    assert source.chapters.get(source.chapter["id"])["version"] == source.chapter["version"]


def _finish(source):
    source.release.set()
    source.dispatch_release.set()
    assert source.finished.wait(10)


@pytest.mark.parametrize("snapshot_required", [False, True])
@pytest.mark.parametrize("moment", ["before_context", "before_adapter"])
@pytest.mark.parametrize("change", ["archive", "replace_owner"])
def test_live_keyed_authority_fences_initial_context_and_adapter(source, snapshot_required, moment, change):
    source.manager.snapshot_required = snapshot_required
    if moment == "before_adapter":
        source.gate_dispatch()
    job = _post(source)
    assert callable(job.request_authorization) and job.expected_request_digest is None and job.scope is None
    if moment == "before_adapter":
        source.release.set()
        assert source.dispatch_entered.wait(10), (job.status, job.error)
    _mutate(source, change)
    # Original production closure, not a patched permission result.
    with pytest.raises(Exception) as denied:
        source.authority[0]()
    assert getattr(denied.value, "status_code", None) == (404 if change == "archive" else 409)
    _finish(source)
    assert job.status == "FAILED"
    assert source.counts["callback"] >= 1
    assert source.counts["adapter"] == source.counts["stream"] == 0
    if moment == "before_context":
        assert source.counts["context"] == source.counts["snapshot"] == 0
        assert source.counts["outbound"] == 0
        assert job.context_snapshot_id is None
    else:
        assert source.counts["context"] == 1
        assert source.counts["dispatch_guard"] == 1
        assert source.counts["snapshot"] == int(snapshot_required)


@pytest.mark.parametrize("change", ["archive", "replace_owner"])
def test_authority_change_during_context_stops_before_snapshot(source, change):
    source.manager.snapshot_required = True
    job = _post(source)
    source.hooks.after_context = lambda: _mutate(source, change)
    _finish(source)
    assert job.status == "FAILED"
    assert source.counts["context"] == 1
    assert source.counts["snapshot"] == source.counts["adapter"] == 0
    assert job.context_snapshot_id is None


@pytest.mark.parametrize("change", ["archive", "replace_owner"])
def test_authority_change_during_mock_stream_cannot_write_deferred_snapshot(source, change):
    job = _post(source)
    source.hooks.after_stream = lambda: _mutate(source, change)
    _finish(source)
    assert job.status == "FAILED"
    assert source.counts["adapter"] == 1
    assert source.counts["snapshot"] == 0


@pytest.mark.parametrize("keyed", [False, True])
def test_valid_live_callback_and_no_callback_legacy_complete(source, keyed):
    job = _post(source, keyed=keyed)
    _finish(source)
    assert job.status == "COMPLETED", job.error
    assert source.counts["context"] == source.counts["snapshot"] == 1
    assert source.counts["adapter"] == source.counts["stream"] == 1
    if keyed:
        assert source.counts["callback"] >= 2
    else:
        assert source.counts["callback"] == 0
    saved = source.manager.persistence.get(job.id)
    assert "request_authorization" not in saved


@pytest.mark.parametrize("deny_at", [1, 2])
def test_authorization_rejection_is_safe_and_never_tries_fallback(source, monkeypatch, deny_at):
    original_router = source.runtime.router
    def router(profile, role):
        value = original_router(profile, role)
        value.routes[role] = [Route("mock", "mock-writer"), Route("mock", "mock-writer")]
        return value
    monkeypatch.setattr(source.runtime, "router", router)
    job = _post(source, automatic_route=True)
    calls = []
    def deny_checkpoint():
        calls.append(None)
        if len(calls) == deny_at:
            raise RuntimeError("secret-token /private/source/root")
    job.request_authorization = deny_checkpoint
    _finish(source)
    assert job.status == "FAILED"
    assert len(calls) == deny_at
    assert len(job.route_decisions) == 1
    assert source.counts["context"] == deny_at - 1
    assert source.counts["snapshot"] == source.counts["adapter"] == 0
    assert "secret-token" not in json.dumps(job.public())
    assert "/private/source/root" not in json.dumps(job.public())


def test_valid_callback_does_not_disable_existing_provider_preflight_fallback(source, monkeypatch):
    original_router = source.runtime.router
    def router(profile, role):
        value = original_router(profile, role)
        value.routes[role] = [Route("mock", "mock-writer"), Route("mock", "mock-writer")]
        return value
    monkeypatch.setattr(source.runtime, "router", router)
    checks = []
    def ready(_provider):
        checks.append(None)
        return len(checks) > 1
    monkeypatch.setattr(source.runtime, "packaged_author_route_ready", ready)
    job = _post(source, automatic_route=True)
    _finish(source)
    assert job.status == "COMPLETED", job.error
    assert len(checks) == 2
    assert [row["status"] for row in job.route_decisions] == ["FAILED", "COMPLETED"]
    assert source.counts["context"] == source.counts["adapter"] == 1


def test_transient_callback_is_not_reconstructed_by_existing_restart_recovery(source):
    job = source.manager.prepare_job("continue", source.payload, request_authorization=lambda: None)
    job.status = "QUEUED"
    source.manager.persistence.save(job.public())
    reopened = JobManager(generations=source.manager.persistence, chapters=source.chapters,
        contexts=source.contexts, canon=source.manager.canon, snapshot_required=False,
        memory_extractor=SimpleNamespace(enqueue=lambda *_: "synthetic-memory-job"))
    recovered = reopened.get(job.id)
    assert recovered.status == "FAILED"
    assert recovered.request_authorization is None
    assert "request_authorization" not in reopened.persistence.get(job.id)
    assert source.counts["context"] == source.counts["adapter"] == 0


@pytest.mark.parametrize("deny", [False, True])
def test_ordinary_authorization_checks_do_not_duplicate_dispatch_or_terminal_hooks(source, monkeypatch, deny):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "author_context_inspector_v2,model_broker_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    callbacks, dispatches, terminals = [], [], []
    def authorize():
        callbacks.append(None)
        if deny:
            raise ValueError("revoked")
    job = source.manager.prepare_job("continue", source.payload, request_authorization=authorize)
    job.before_dispatch = lambda: dispatches.append(None)
    job.on_terminal = lambda: terminals.append(None)
    source.manager.start_prepared(job)
    assert source.entered.wait(10)
    _finish(source)
    assert job.status == ("FAILED" if deny else "COMPLETED")
    assert len(dispatches) == (0 if deny else 1)
    assert len(terminals) == 1
    if deny:
        assert len(callbacks) == 1
    else:
        assert len(callbacks) >= 3


# Reuse the existing real File collaboration owners, never its dispatcher.
from test_generation_idempotency_contracts import generation, collaboration_generation


@pytest.mark.parametrize("live_callback", [False, True])
def test_registered_branch_keeps_original_required_callback_contract(collaboration_generation, monkeypatch, live_callback):
    import app.dependencies as dependencies

    fixture = collaboration_generation
    runtime = Runtime(StableIdentityStore(fixture.root / "runtime" / "branch-identities.json"))
    runtime.providers["mock"] = MockProvider(delay_ms=0)
    runtime._sync_model("mock", "mock-writer")
    monkeypatch.setattr(jobs_module, "runtime", runtime)
    monkeypatch.setattr(jobs_module, "settings", api.settings)
    monkeypatch.setattr(dependencies, "membership_authorization_service", api.membership_authorization_service)
    manager = JobManager(generations=GenerationService(fixture.bundle.generations),
        chapters=fixture.chapters,
        contexts=ContextService(fixture.bundle.novels, fixture.bundle.chapters, LoreService(fixture.bundle.lore)),
        canon=CanonService(fixture.bundle.canon), snapshot_required=False,
        memory_extractor=SimpleNamespace(enqueue=lambda *_: "synthetic-memory-job"))
    body = api.GenerateIn(**fixture.payload, provider_id="mock", model_id="mock-writer")
    actor, scope = api._generation_request_context(body, "opaque-alice", "branch-a")
    original = api._registered_branch_generation_authorization(
        body, "opaque-alice", "branch-a", actor, scope)["request_authorization"]
    calls = []
    def authorize():
        calls.append(None)
        return original()
    job = manager.prepare_job("continue", body.model_dump(), actor, scope,
        authorize if live_callback else None)
    adapter = runtime.provider_registry.resolve("mock")
    original_stream = adapter.stream_text
    dispatched = []
    def stream(request):
        dispatched.append(None)
        return original_stream(request)
    monkeypatch.setattr(adapter, "stream_text", stream)
    manager._run(job)
    assert job.status == ("COMPLETED" if live_callback else "FAILED"), job.error
    assert len(dispatched) == int(live_callback)
    # Existing non-preview branch checkpoints are unchanged: post-assembly and
    # the actual TextModelNode dispatch guard, not the ordinary helper.
    assert len(calls) == (2 if live_callback else 0)


@pytest.mark.parametrize("operation,code", [
    ("creative_director_text", "CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE"),
    ("creative_director_image_v3", "DIRECTOR_IMAGE_PRIVATE_OWNER_REQUIRED"),
    ("research_ocr", "RESEARCH_OCR_EXECUTION_UNAVAILABLE"),
])
def test_specialized_worker_domains_still_require_their_private_capability(source, monkeypatch, operation, code):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("specialized worker entered ordinary authorization")
    monkeypatch.setattr(source.manager, "_guard_ordinary_request_authorization", forbidden)
    job = Job("inert-specialized-job", operation, source.chapter["novel_id"], None, "", "LOCAL_ONLY")
    job.request_authorization = forbidden
    with pytest.raises(ValueError, match=code):
        JobManager._run(source.manager, job)
    assert source.counts["context"] == source.counts["snapshot"] == source.counts["adapter"] == 0


@pytest.mark.parametrize("callback_state", ["live", "absent_at_start", "absent_at_worker"])
def test_reviewed_author_keeps_original_preview_and_required_callback_contract(
        source, monkeypatch, callback_state):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "author_context_inspector_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    monkeypatch.setattr(author_context_api, "runtime", source.runtime)
    preparer = AuthorPreparer(source.manager, api._workbench_authorize, require_flag,
                             api._generation_request_context, api._generation_payload)
    ordinary_entries = []
    ordinary_active = [False]
    original_ordinary = source.manager._guard_ordinary_request_authorization

    def ordinary(job):
        ordinary_entries.append(job.id)
        ordinary_active[0] = True
        try:
            return original_ordinary(job)
        finally:
            ordinary_active[0] = False

    monkeypatch.setattr(source.manager, "_guard_ordinary_request_authorization", ordinary)
    body = AuthorPreviewInput(**source.payload, operation="continue",
                              chapter_version=source.chapter["version"])
    preview = preparer.prepare_preview(source.chapter["novel_id"], body)
    reviewed_body = body.model_copy(update={
        "preview_digest": request_digest(preview.request, preview.job, False),
    })
    job = preparer.prepare_author(source.chapter["novel_id"], reviewed_body)
    assert job.expected_request_digest == reviewed_body.preview_digest
    assert callable(job.request_authorization)
    assert ordinary_entries == []  # Preview assembly never enters the new helper.
    assert source.counts["context"] == 2
    assert source.counts["adapter"] == source.counts["snapshot"] == 0
    authorization_calls = []
    original_authorization = job.request_authorization

    def authorize():
        assert not ordinary_active[0], "reviewed Author callback used the ordinary path"
        authorization_calls.append(None)
        return original_authorization()

    job.request_authorization = authorize
    if callback_state == "absent_at_start":
        job.request_authorization = None
        with pytest.raises(ValueError, match="AUTHOR_PREVIEW_SESSION_REQUIRED"):
            source.manager.start_prepared(job)
        assert not source.entered.is_set()
        assert source.counts["context"] == 2
        assert source.counts["adapter"] == source.counts["snapshot"] == 0
        return

    source.manager.start_prepared(job)
    assert source.entered.wait(10)
    if callback_state == "absent_at_worker":
        job.request_authorization = None
    _finish(source)
    if callback_state == "live":
        assert job.status == "COMPLETED", job.error
        # The three original expected-digest checkpoints each authorize once:
        # initial guard, post-assembly guard, and real TextModelNode dispatch.
        assert len(authorization_calls) == 3
        assert source.counts["context"] == 6
        assert source.counts["adapter"] == source.counts["stream"] == 1
        assert source.counts["snapshot"] == 1
        assert ordinary_entries
    else:
        assert job.status == "FAILED", job.error
        assert job.error_code == "INVALID_REQUEST"
        assert authorization_calls == []
        assert source.counts["context"] == 2
        assert source.counts["adapter"] == source.counts["snapshot"] == 0


@pytest.mark.parametrize("callback_state", [
    "live", "absent_at_prepare", "absent_at_start", "absent_at_worker",
])
def test_real_graph_worker_keeps_disjoint_path_and_required_callback_contract(
        source, monkeypatch, callback_state):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join((
        "ai_execution_v2", "narrative_production_v2",
        "author_context_inspector_v2", "model_broker_v2",
    )))
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    owner = GenerationIdempotencyAuthority(source.novels, source.chapters)
    project_id = source.chapter["novel_id"]
    incarnation = owner.capture_new(project_id)
    authorization_calls = []

    def authorize():
        authorization_calls.append(None)
        with owner.verify_existing(project_id, incarnation):
            pass

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Graph entered an ordinary Author/source/context path")

    monkeypatch.setattr(source.manager, "_guard_ordinary_request_authorization", forbidden)
    monkeypatch.setattr(source.manager, "prepare_author_request", forbidden)
    monkeypatch.setattr(source.manager, "chapters_for_job", forbidden)
    monkeypatch.setattr(source.manager, "_save_context_snapshot", forbidden)
    monkeypatch.setattr(source.contexts, "for_chapter", forbidden)
    # Graph's synthetic seam intentionally permits only exact MockProvider.
    provider = MockProvider(delay_ms=0)
    original_stream = provider.stream

    def stream(*args, **kwargs):
        source.counts["stream"] += 1
        yield from original_stream(*args, **kwargs)

    monkeypatch.setattr(provider, "stream", stream)
    source.runtime.providers["mock"] = provider
    source.runtime._sync_model("mock", "mock-writer")
    assert type(provider) is MockProvider
    adapter = source.runtime.provider_registry.resolve("mock")
    original_adapter = adapter.stream_text

    def adapter_stream(request):
        source.counts["adapter"] += 1
        return original_adapter(request)

    monkeypatch.setattr(adapter, "stream_text", adapter_stream)
    arguments = dict(
        project_id=project_id, provider_id="mock", model_id="mock-writer",
        prompt="Write one short synthetic graph proposal.", actor_id="local-author",
        scope={"mode": "local", "novel_id": project_id},
        request_binding={
            "graph_id": "compat-graph", "graph_version": 1, "run_id": "compat-run",
            "node_id": "compat-node", "project_incarnation": incarnation,
            "input_digest": "a" * 64, "reviewed_preview_digest": "b" * 64,
            "route_fingerprint": "c" * 64,
        },
        request_authorization=None if callback_state == "absent_at_prepare" else authorize,
        max_output_bytes=4096,
        deadline=(datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(),
        synthetic_allowed=True,
    )
    if callback_state == "absent_at_prepare":
        with pytest.raises(ValueError, match="GRAPH_MODEL_AUTHORITY_REQUIRED"):
            source.manager.prepare_graph_job(**arguments)
        assert authorization_calls == []
        assert source.counts["adapter"] == source.counts["stream"] == 0
        return

    job = source.manager.prepare_graph_job(**arguments)
    assert len(authorization_calls) == 2
    assert job.chapter_id is None and job.expected_request_digest
    before_dispatch, on_terminal = [], []
    job.before_dispatch = lambda: before_dispatch.append(None)
    job.on_terminal = lambda: on_terminal.append(None)
    if callback_state == "absent_at_start":
        job.request_authorization = None
        with pytest.raises(ValueError, match="GENERATION_AUTHORITY_REVOKED"):
            source.manager.start_prepared(job)
        assert not source.entered.is_set()
        assert source.counts["adapter"] == source.counts["stream"] == 0
        assert before_dispatch == on_terminal == []
        return

    source.manager.start_prepared(job)
    assert source.entered.wait(10)
    if callback_state == "absent_at_worker":
        job.request_authorization = None
    _finish(source)
    assert source.counts["context"] == source.counts["snapshot"] == 0
    assert len(on_terminal) == 1
    if callback_state == "live":
        assert job.status == "COMPLETED", job.error
        assert job.terminal_hook_status == "COMPLETED"
        assert len(authorization_calls) > 2
        assert source.counts["adapter"] == source.counts["stream"] == 1
        assert len(before_dispatch) == 1
        assert job.output
    else:
        assert job.status == "FAILED", job.error
        assert job.error_code == "GENERATION_AUTHORITY_REVOKED"
        assert source.counts["adapter"] == source.counts["stream"] == 0
        assert before_dispatch == []
        assert job.output == ""


@pytest.fixture
def broker_features(monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "author_context_inspector_v2,model_broker_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)


def post_operation(source, operation):
    response = source.client.post('/api/generate/' + operation, json=dict(source.payload),
        headers={'Idempotency-Key': 'review-publication-key'})
    assert response.status_code == 202, response.text
    assert source.entered.wait(10)
    job = source.manager.jobs[response.json()['job_id']]
    assert job.status == 'QUEUED'
    return job


def watch(source, monkeypatch):
    revoked, emissions, saves, dispatches, terminals = [], [], [], [], []
    original_emit = source.manager._emit
    def emit(job, chunk=''):
        emissions.append((bool(revoked), chunk, job.status))
        return original_emit(job, chunk)
    monkeypatch.setattr(source.manager, '_emit', emit)
    original_save = source.manager.persistence.save
    def save(payload):
        saves.append((bool(revoked), copy.deepcopy(payload)))
        return original_save(payload)
    monkeypatch.setattr(source.manager.persistence, 'save', save)
    return revoked, emissions, saves, dispatches, terminals


@pytest.mark.parametrize('operation', ['continue', 'polish'])
@pytest.mark.parametrize('snapshot_required', [False, True])
@pytest.mark.parametrize('moment', ['midstream', 'before_completed_event'])
@pytest.mark.parametrize('change', ['archive', 'replace_owner'])
@pytest.mark.usefixtures("broker_features")
def test_revoked_live_source_stops_new_output_and_terminal_publish(source, monkeypatch, operation, snapshot_required, moment, change):
    source.manager.snapshot_required = snapshot_required
    revoked, emissions, saves, dispatches, terminals = watch(source, monkeypatch)
    def revoke():
        _mutate(source, change)
        revoked.append(True)
    if moment == 'before_completed_event':
        source.hooks.after_stream = revoke
    else:
        provider = source.runtime.providers['mock']
        original_stream = provider.stream
        def stream(*args, **kwargs):
            first = True
            for chunk in original_stream(*args, **kwargs):
                yield chunk
                if first:
                    first = False
                    revoke()
        monkeypatch.setattr(provider, 'stream', stream)
    job = post_operation(source, operation)
    job.dispatch_hooks_required = True
    job.before_dispatch = lambda: dispatches.append(None)
    job.on_terminal = lambda: terminals.append(None)
    _finish(source)
    assert revoked
    assert job.status == 'FAILED'
    assert job.output == ''
    assert source.manager.persistence.get(job.id)['output'] == ''
    assert source.counts['adapter'] == 1
    assert len(dispatches) == len(terminals) == 1
    assert job.terminal_hook_status == 'COMPLETED'
    assert not any(chunk for after, chunk, _ in emissions if after)
    assert not any(after and row['status'] == 'COMPLETED' for after, row in saves)
    assert source.counts['snapshot'] == int(snapshot_required)
    if moment == 'midstream':
        assert sum(len(chunk) for after, chunk, _ in emissions if not after) == 8
    assert job.route_decisions[0]['status'] in {'DISPATCHED', 'FAILED', 'COMPLETED'}


@pytest.mark.parametrize('operation', ['continue', 'polish'])
@pytest.mark.parametrize('snapshot_required', [False, True])
@pytest.mark.parametrize('moment', ['final_review', 'terminal_hook'])
@pytest.mark.usefixtures("broker_features")
def test_final_publication_rechecks_after_review_or_settlement_without_losing_execution_receipts(source, monkeypatch, operation, snapshot_required, moment):
    source.manager.snapshot_required = snapshot_required
    revoked, emissions, saves, dispatches, terminals = watch(source, monkeypatch)
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    monkeypatch.setattr(provider, 'supports_stream_usage', True, raising=False)
    def stream(*args, **kwargs):
        kwargs['usage_callback']({'input_tokens': 13, 'output_tokens': 21})
        yield from original_stream(*args, **kwargs)
    monkeypatch.setattr(provider, 'stream', stream)
    def revoke():
        _mutate(source, 'archive')
        revoked.append(True)
    if moment == 'final_review':
        original_review = jobs_module.deterministic_review
        def review(*args, **kwargs):
            result = original_review(*args, **kwargs)
            revoke()
            return result
        monkeypatch.setattr(jobs_module, 'deterministic_review', review)
    job = post_operation(source, operation)
    job.dispatch_hooks_required = True
    job.before_dispatch = lambda: dispatches.append(None)
    def settle():
        terminals.append(None)
        if moment == 'terminal_hook':
            revoke()
    job.on_terminal = settle
    _finish(source)
    assert revoked
    assert job.status == 'FAILED'
    assert job.output == ''
    assert job.usage == {'input_tokens': 13, 'output_tokens': 21, 'total_tokens': 34}
    assert job.usage_status == 'REPORTED'
    assert job.execution_mode == 'mock_standin'
    assert job.provider == 'mock' and job.model == 'mock-writer'
    assert job.route_decisions[0]['status'] == 'COMPLETED'
    assert job.execution_outcome == 'COMPLETED', 'provider execution completed before authority was revoked'
    assert len(dispatches) == len(terminals) == 1
    assert job.terminal_hook_status == 'COMPLETED'
    assert job.error_code != 'GENERATION_TERMINAL_PERSISTENCE_UNCERTAIN'
    assert job.error_code != 'TERMINAL_RECONCILIATION_REQUIRED'
    assert source.counts['snapshot'] == int(snapshot_required or operation == 'continue')
    assert not any(after and row['status'] == 'COMPLETED' for after, row in saves)
    saved = source.manager.persistence.get(job.id)
    assert saved['status'] == 'FAILED' and saved['output'] == ''
    assert saved['usage'] == job.usage


@pytest.mark.parametrize('terminal', ['CANCELLED', 'ACCEPTED', 'REJECTED'])
def test_late_worker_event_does_not_reauthorize_or_rewrite_existing_terminal(source, monkeypatch, terminal):
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    job = post_operation(source, 'continue')
    baseline = []
    original_authorize = job.request_authorization
    def authorize():
        assert not baseline, 'late callback checked after already published terminal'
        return original_authorize()
    job.request_authorization = authorize
    def stream(*args, **kwargs):
        first = True
        for chunk in original_stream(*args, **kwargs):
            yield chunk
            if first:
                first = False
                # Controlled persisted terminal fixture. This does not claim a
                # running task is adoptable through the actual accept API.
                with job.condition:
                    if terminal == 'CANCELLED':
                        source.manager.cancel(job.id)
                    else:
                        job.status = terminal
                        source.manager._persist(job)
                    baseline.append(copy.deepcopy(source.manager.persistence.get(job.id)))
                _mutate(source, 'archive')
    monkeypatch.setattr(provider, 'stream', stream)
    _finish(source)
    assert baseline
    assert job.status == terminal
    assert source.manager.persistence.get(job.id) == baseline[0]


@pytest.mark.parametrize('also_revoke', [False, True])
@pytest.mark.usefixtures("broker_features")
def test_terminal_hook_cancel_preserves_completed_execution_fact_and_cannot_publish(source, monkeypatch, also_revoke):
    revoked, emissions, saves, dispatches, terminals = watch(source, monkeypatch)
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    monkeypatch.setattr(provider, 'supports_stream_usage', True, raising=False)
    def stream(*args, **kwargs):
        kwargs['usage_callback']({'input_tokens': 13, 'output_tokens': 21})
        yield from original_stream(*args, **kwargs)
    monkeypatch.setattr(provider, 'stream', stream)
    job = post_operation(source, 'continue')
    job.dispatch_hooks_required = True
    job.before_dispatch = lambda: dispatches.append(None)
    at_hook = []
    def settle():
        terminals.append(None)
        at_hook.append((job.status, job.execution_outcome))
        source.manager.cancel(job.id)
        if also_revoke:
            _mutate(source, 'archive')
            revoked.append(True)
    job.on_terminal = settle
    _finish(source)
    assert at_hook == [('SETTLING', 'COMPLETED')]
    assert job.status == 'CANCELLED'
    assert job.execution_outcome == 'COMPLETED'
    assert job.usage == {'input_tokens': 13, 'output_tokens': 21, 'total_tokens': 34}
    assert len(dispatches) == len(terminals) == 1
    assert job.terminal_hook_status == 'COMPLETED'
    assert not any(row['status'] == 'COMPLETED' for _, row in saves)
    assert source.manager.persistence.get(job.id)['status'] == 'CANCELLED'


@pytest.mark.parametrize('snapshot_required', [False, True])
def test_late_adapter_guard_refusal_cannot_leave_partial_buffer_reviewable(source, monkeypatch, snapshot_required):
    source.manager.snapshot_required = snapshot_required
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    monkeypatch.setattr(provider, 'supports_dispatch_guard', True, raising=False)
    refused = []
    def stream(*args, **kwargs):
        first = True
        for chunk in original_stream(*args, **kwargs):
            yield chunk
            if first:
                first = False
                _mutate(source, 'archive')
                refused.append(True)
                kwargs['dispatch_guard']()
    monkeypatch.setattr(provider, 'stream', stream)
    job = post_operation(source, 'continue')
    _finish(source)
    assert refused
    assert job.status == 'FAILED'
    assert job.output == ''
    assert source.manager.persistence.get(job.id)['output'] == ''


def test_one_time_late_adapter_refusal_survives_normalized_failure_event(source, monkeypatch):
    provider = source.runtime.providers["mock"]
    original_stream = provider.stream
    monkeypatch.setattr(provider, "supports_dispatch_guard", True, raising=False)
    job = _post(source)
    original_authority = job.request_authorization
    armed, refusals = [], []
    def authorize():
        if armed and not refusals:
            refusals.append(None)
            raise RuntimeError("secret-once /private/refusal-root")
        return original_authority()
    job.request_authorization = authorize
    def stream(*args, **kwargs):
        for chunk in original_stream(*args, **kwargs):
            yield chunk
            armed.append(None)
            kwargs["dispatch_guard"]()
    monkeypatch.setattr(provider, "stream", stream)
    _finish(source)
    assert len(refusals) == 1
    assert job.status == "FAILED" and job.output == ""
    assert source.counts["adapter"] == 1
    saved = source.manager.persistence.get(job.id)
    assert saved["status"] == "FAILED" and saved["output"] == ""
    assert "_ordinary_authorization_refused" not in saved
    assert "secret-once" not in json.dumps(saved)
    assert "/private/refusal-root" not in json.dumps(saved)


def test_no_hook_live_publication_does_not_persist_settlement_recovery_state(source, monkeypatch):
    rows = []
    original_save = source.manager.persistence.save
    def save(value):
        rows.append(copy.deepcopy(value))
        return original_save(value)
    monkeypatch.setattr(source.manager.persistence, "save", save)
    job = _post(source)
    _finish(source)
    assert job.status == "COMPLETED"
    assert not any(row["status"] == "SETTLING" or row.get("dispatch_hooks_required") for row in rows)


@pytest.mark.usefixtures("broker_features")
def test_failed_settlement_keeps_its_receipt_but_discards_revoked_output(source):
    job = _post(source)
    job.dispatch_hooks_required = True
    dispatches, settlements = [], []
    job.before_dispatch = lambda: dispatches.append(None)
    def settle():
        settlements.append(None)
        _mutate(source, "archive")
        raise RuntimeError("synthetic settlement failure")
    job.on_terminal = settle
    _finish(source)
    assert job.status == "FAILED" and job.output == ""
    assert job.execution_outcome == "COMPLETED"
    assert job.terminal_hook_status == "FAILED_RECONCILIATION_REQUIRED"
    assert job.error_code == "TERMINAL_RECONCILIATION_REQUIRED"
    assert len(dispatches) == len(settlements) == 1
    assert source.manager.persistence.get(job.id)["output"] == ""


@pytest.mark.usefixtures("broker_features")
def test_settlement_persistence_failure_cannot_publish_completed(source, monkeypatch):
    job = _post(source)
    job.dispatch_hooks_required = True
    dispatches, settlements, successful_saves, failures = [], [], [], []
    job.before_dispatch = lambda: dispatches.append(None)
    job.on_terminal = lambda: settlements.append(None)
    original_save = source.manager.persistence.save
    def save(value):
        if value["status"] == "SETTLING" and value.get("terminal_hook_status") == "COMPLETED" and not failures:
            failures.append(None)
            raise OSError("synthetic settlement persistence failure")
        result = original_save(value)
        successful_saves.append(copy.deepcopy(value))
        return result
    monkeypatch.setattr(source.manager.persistence, "save", save)
    _finish(source)
    assert len(failures) == len(dispatches) == len(settlements) == 1
    assert job.status == "FAILED"
    assert job.execution_outcome == "COMPLETED"
    assert job.terminal_hook_status == "PERSISTENCE_UNCERTAIN_RECONCILIATION_REQUIRED"
    assert not any(row["status"] == "COMPLETED" for row in successful_saves)
    assert source.manager.persistence.get(job.id)["status"] == "FAILED"


def test_no_hook_final_cancel_preserves_observed_execution(source, monkeypatch):
    job = _post(source)
    after_review = []
    original_review = jobs_module.deterministic_review
    def review(*args, **kwargs):
        result = original_review(*args, **kwargs)
        after_review.append(None)
        return result
    monkeypatch.setattr(jobs_module, "deterministic_review", review)
    original_authority = job.request_authorization
    def authorize():
        if after_review:
            source.manager.cancel(job.id)
        return original_authority()
    job.request_authorization = authorize
    _finish(source)
    assert after_review
    assert job.status == "CANCELLED"
    assert job.execution_outcome == "COMPLETED"
    assert job.route_decisions[0]["status"] == "COMPLETED"
    assert source.manager.persistence.get(job.id)["status"] == "CANCELLED"


def test_late_adapter_refusal_does_not_clear_already_persisted_accepted_result(source, monkeypatch):
    provider = source.runtime.providers["mock"]
    original_stream = provider.stream
    monkeypatch.setattr(provider, "supports_dispatch_guard", True, raising=False)
    job = _post(source)
    accepted = []
    def stream(*args, **kwargs):
        for chunk in original_stream(*args, **kwargs):
            yield chunk
            with job.condition:
                job.status = "ACCEPTED"  # Controlled terminal fixture, not an accept-API claim.
                source.manager._persist(job)
                accepted.append(copy.deepcopy(source.manager.persistence.get(job.id)))
            _mutate(source, "archive")
            kwargs["dispatch_guard"]()
    monkeypatch.setattr(provider, "stream", stream)
    _finish(source)
    assert len(accepted) == 1
    assert job.status == "ACCEPTED" and len(job.output) == 8
    assert source.manager.persistence.get(job.id) == accepted[0]
    assert not getattr(job, "_ordinary_authorization_refused", False)
