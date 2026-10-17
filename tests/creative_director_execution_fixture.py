"""Original File owners and a mocked wire for internal Director lifecycle tests.

The LocalTextAdapter is real; no probe, process, GPU, network or model is used.
The fixture does not mint an execution capability or fabricate Graph bindings.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
import os
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

FLAGS = "ai_execution_v2,narrative_production_v2,model_broker_v2,author_context_inspector_v2"
CONTRACT = "CREATIVE_DIRECTOR_INTERNAL_EXECUTION_V1"
TEXT = "Internal fixture result; never public content or adoption."


class ForbiddenOwner:
    def __getattr__(self, name):
        raise AssertionError("Independent Director touched forbidden chapter/context/canon/workflow owner: " + name)

    def __call__(self, *args, **kwargs):
        raise AssertionError("Independent Director invoked forbidden owner")


def wait(e, job):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with job.condition:
            if job.status in e.manager.terminal and job.terminal_hook_status is not None:
                return job
        time.sleep(.005)
    pytest.fail("Original worker did not finish within existing five-second boundary: " + repr(job.public()))


def preview(e, **changes):
    body = dict(expected_version=e.row["version"], route_id=e.route["route_id"],
                allow_synthetic=False, max_output_tokens=512, temperature=0.0)
    body.update(changes)
    return e.coordinator._preview_independent(e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)


def dispatch(e, row, **changes):
    body = dict(expected_version=row["version"], reviewed_preview_digest=row["model_preview"]["preview_digest"])
    body.update(changes)
    return e.coordinator._dispatch_independent(e.ctx, row["id"], body, e.guard, host_authority=e.authority)


def result(e):
    return e.coordinator._read_independent_result(e.ctx, e.row["id"], e.guard, host_authority=e.authority)


def raw_proposal(e):
    return e.raw.read(e.nid, e.scope)["collections"][e.documents.proposals.COLLECTION][e.row["id"]]


def run(e):
    prepared = preview(e)
    try:
        receipt = dispatch(e, prepared)
    except (ValueError, HTTPException, PermissionError, FileNotFoundError, KeyError):
        # A fast original worker can revoke authority before the dispatch
        # response checkpoint. Still await that already registered worker.
        if len(e.manager.jobs) != 1:
            raise
        receipt = raw_proposal(e)
    job = e.manager.get(receipt["model_execution"]["job_id"])
    return prepared, receipt, wait(e, job)


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    from app import jobs as jobs_module
    from app.actor_context import SessionContext
    from app.config import settings
    from app.creative.generation import DirectorModelCoordinator
    from app.creative.service import CreativeService
    from app.experimental.model_broker import ModelBrokerService
    from app.experimental.store import ExperimentalStore
    from app.jobs import JobManager
    from app.model_center.discovery_authority import resolve_discovery_authority
    from app.model_center.discovery_bridge import LocalTextAdapter
    from app.model_runtime import Modality, ModelDescriptor, ProviderDescriptor
    from app.repository import FileRepository
    from app.repositories.file.generation import FileGenerationRepository
    from app.repositories.file.novel import FileNovelRepository
    from app.runtime import Runtime
    from app.services.generation_service import GenerationService
    from app.stable_identity import StableIdentityStore
    from app.trusted_sessions import TrustedSessionResolver

    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ["PROJECT_ROOT"]).resolve() == root
    assert tmp_path.resolve().is_relative_to(root / ".runtime")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    assert not settings.enable_packaged_runtime
    forbidden = ForbiddenOwner()
    nid, actor = "independent-director", "director-host-actor"
    scope = {"mode": "local", "novel_id": nid}
    backend = FileRepository(tmp_path)
    novels = FileNovelRepository(backend)
    novels.create({"id": nid, "title": "Independent Director lifecycle"})
    raw = ExperimentalStore(tmp_path, "file", "")
    documents = CreativeService(raw, novels, forbidden)
    source = documents.create(nid, scope, actor, {
        "mode": "STORYBOARD", "source_independent": True, "title": "Saved independent storyboard",
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "INT. ROOM", "action": "A visitor waits."}],
        "shots": [{"id": "shot-1", "number": 1, "scene_id": "scene-1", "action": "The visitor turns."}],
    })
    row = documents.proposals.create(nid, scope, actor,
        {"source_document_id": source["id"], "expected_source_version": source["version"]})
    runtime = Runtime(StableIdentityStore(tmp_path / "identity.json"))
    runtime.providers["mock"].delay_ms = 0
    monkeypatch.setattr(jobs_module, "runtime", runtime)
    persistence = GenerationService(FileGenerationRepository(tmp_path))
    manager = JobManager(persistence, forbidden, forbidden, forbidden,
        memory_extractor=forbidden, snapshot_required=True, collaboration_updates=forbidden)
    sessions = TrustedSessionResolver()
    token = "fixture-current-host-token"
    session = SessionContext("fixture-session", "fixture-client", actor, "fixture-workspace")
    sessions.register(token, session)
    host_settings = SimpleNamespace(enable_packaged_runtime=False, enable_collaboration_runtime=False,
                                    frontend_origin="http://127.0.0.1:5173")
    request = Request({"type": "http", "method": "POST", "scheme": "http", "path": "/internal-fixture",
        "headers": [], "client": ("127.0.0.1", 41000), "server": ("127.0.0.1", 8000), "query_string": b""})
    authority = resolve_discovery_authority(request, token, settings_getter=lambda: host_settings,
        resolver_getter=lambda: sessions, bootstrap_getter=lambda: None)
    assert authority.principal and callable(authority.guard)
    e = SimpleNamespace(root=tmp_path, nid=nid, actor=actor, scope=scope, novels=novels,
        raw=raw, documents=documents, source=source, row=row, runtime=runtime, manager=manager,
        persistence=persistence, sessions=sessions, token=token, session=session, authority=authority,
        host_settings=host_settings, active=True, calls=[], requests=[], wire_hook=None,
        wire_text=TEXT, wire_finish="stop", caller=get_ident(), forbidden=forbidden)
    e.ctx = SimpleNamespace(novel_id=nid, scope=scope, actor=actor, token=token, branch=None)
    def guard():
        if not e.active:
            raise HTTPException(403, {"code": "FIXTURE_SCOPE_REVOKED"})
    e.guard = guard
    candidate = {"id": "fixture-local-text", "provider_id": "fixture-local-provider", "model_name": "explicit-fixture-model",
        "source_locality": "LOCAL_VERIFIED", "model_evidence_fingerprint": "fixture-model-evidence",
        "runtime_fingerprint": "fixture-runtime-evidence", "enabled_at": "fixture-enable-receipt", "license_confirmed": True,
        "runtime_config": {"management": "EXTERNAL", "type": "LLAMA_CPP", "endpoint": "http://127.0.0.1:8999"}}
    def candidate_guard(identifier):
        assert identifier == candidate["id"]
        return candidate
    bridge = SimpleNamespace(guard=candidate_guard, service=SimpleNamespace(check_model_dispatch=lambda value: None),
                             launch_on_demand=forbidden)
    adapter = LocalTextAdapter(bridge, candidate)
    def wire(endpoint, path, body):
        assert get_ident() != e.caller, "Original worker must own provider execution"
        assert not getattr(raw._local, "active", {}), "Provider I/O under raw scope lock"
        assert not getattr(documents.store._local, "active", {}), "Provider I/O under Creative scope lock"
        assert not getattr(documents.store._local, "owners", {}), "Provider I/O under project owner lease"
        assert endpoint == "http://127.0.0.1:8999" and path == "/v1/chat/completions"
        e.calls.append(("wire", get_ident()))
        e.requests.append(deepcopy(body))
        if e.wire_hook:
            e.wire_hook()
        return {"choices": [{"message": {"content": e.wire_text}, "finish_reason": e.wire_finish}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}
    adapter.client = SimpleNamespace(json=wire)
    monkeypatch.setattr(adapter, "health_check", forbidden)
    runtime.provider_registry.register(ProviderDescriptor(candidate["provider_id"], "Fixture external local", "local",
        frozenset({Modality.TEXT}), True, True), adapter)
    runtime.model_registry.register(ModelDescriptor(candidate["id"], candidate["provider_id"], "Fixture local text", Modality.TEXT,
        frozenset({"generate", "stream", "buffered_stream"}), streaming=True))
    broker = ModelBrokerService(raw, novels, forbidden, runtime=runtime)
    coordinator = DirectorModelCoordinator(documents.proposals, broker, forbidden, manager)
    documents.proposals.generation = coordinator
    route = next(item for item in broker.candidates(local_text_only=True) if item["model_id"] == candidate["id"])
    assert route["available"] and not route["synthetic"] and not route["cloud"]
    now = datetime.now(timezone.utc)
    broker.configure_price(nid, scope, actor, {"route_id": route["route_id"], "route_fingerprint": route["fingerprint"],
        "reserve_microusd": 0, "input_per_million_microusd": 0, "output_per_million_microusd": 0,
        "source": "Fixture explicit zero local fee", "as_of": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(), "expected_version": 0})
    e.broker, e.coordinator, e.route, e.adapter, e.candidate = broker, coordinator, route, adapter, candidate
    yield e
    for job in tuple(manager.jobs.values()):
        if job.status not in manager.terminal:
            manager.cancel(job.id)
    deadline = time.monotonic() + 5
    while any(job.status not in manager.terminal or (job.dispatch_hooks_required and job.terminal_hook_status is None)
              for job in manager.jobs.values()) and time.monotonic() < deadline:
        time.sleep(.01)
    assert all(job.status in manager.terminal for job in manager.jobs.values()), "Fixture leaked original worker"
