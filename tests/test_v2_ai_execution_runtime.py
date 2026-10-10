"""M4 composition over real WorkflowRun, ModelBroker and original JobManager.

The shared M1 fixture owns File/PostgreSQL setup and cleanup. All inference is
an exact built-in MockProvider through LegacyTextProviderAdapter on real worker
threads. No model process, paid/live provider, install or network is used.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from threading import Event, get_ident
import time
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import jobs as jobs_module
from app.creative.graph import CreativeGraphService
from app.experimental.common import StaleSourceError
from app.experimental.model_broker import ModelBrokerService
from app.jobs import JobManager, generation_content_available
from app.model_runtime import LegacyTextProviderAdapter
from app.providers import MockProvider
from app.runtime import Runtime
from app.services.generation_service import GenerationService
from app.services.v1_capability_service import CapabilityVersionConflict, V1CapabilityService
from app.stable_identity import StableIdentityStore
from test_v2_independent_workspace import rig, branch_scope

FLAGS = "ai_execution_v2,narrative_production_v2,model_broker_v2,author_context_inspector_v2"
CONTRACT = "creative-graph-model/1"
pytestmark = pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning")


class ForbiddenOwner:
    def __getattr__(self, name):
        raise AssertionError("Graph execution touched chapter/context/canon owner: " + name)


def configure(e, monkeypatch, graphs=None):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    e.runtime = Runtime(StableIdentityStore(e.root / "m4-identities.json"))
    e.runtime.providers["mock"].delay_ms = 0
    adapter = e.runtime.provider_registry.resolve("mock")
    assert type(adapter) is LegacyTextProviderAdapter
    assert type(adapter.provider) is MockProvider
    monkeypatch.setattr(jobs_module, "runtime", e.runtime)
    owner = ForbiddenOwner()
    e.persistence = GenerationService(e.bundle.generations)
    # The original PostgreSQL repository is intentionally shared by the full
    # selection. Earlier original workflow tests may leave unrelated history.
    # Keep exact rows, not a filtered/proxied persistence implementation.
    baseline = e.persistence.load_all()
    e.generation_baseline = {row["id"]: deepcopy(row) for row in baseline}
    assert len(e.generation_baseline) == len(baseline)
    e.manager = JobManager(e.persistence, owner, owner, owner, memory_extractor=owner,
        snapshot_required=True, collaboration_updates=owner)
    e.graphs = graphs or CreativeGraphService(e.store, e.service)
    e.broker = ModelBrokerService(e.graphs.store.store, e.novels, e.chapters, runtime=e.runtime)
    # Router closures retain the existing service: restore its old configuration
    # after each mounted test rather than leaking a fixture runtime into others.
    monkeypatch.setattr(e.graphs, "model_runtime", None)
    e.graphs.configure_models(e.broker, e.manager)
    e.models = e.graphs.model_runtime
    e.route = next(row for row in e.broker.candidates(local_text_only=True) if row["provider_id"] == "mock")
    e.calls, e.releases = [], []
    e.active = True
    def guard():
        if not e.active:
            raise PermissionError("M4 fixture authority revoked")
    e.guard = guard
    return e


def owned_jobs(e):
    """Inspect the actual original manager without adopting foreign history."""
    result = {jid: job for jid, job in e.manager.jobs.items() if jid not in e.generation_baseline}
    assert all(job.novel_id == e.nid and job.experimental_origin == "creative_graph_model"
               for job in result.values()), "M4_UNEXPECTED_JOB_ADDITION"
    return result


def assert_generation_rows(e, rows):
    """Validate an exact global snapshot, then expose only the proven delta."""
    current = {row["id"]: row for row in rows}
    assert len(current) == len(rows), "M4_DUPLICATE_GENERATION_ID"
    assert {jid: current.get(jid) for jid in e.generation_baseline} == e.generation_baseline, \
        "M4_PREEXISTING_GENERATION_CHANGED"
    delta = [row for jid, row in current.items() if jid not in e.generation_baseline]
    assert all(row.get("novel_id") == e.nid and row.get("experimental_origin") == "creative_graph_model"
               for row in delta), "M4_UNEXPECTED_GENERATION_ADDITION"
    assert {row["id"] for row in delta} <= set(owned_jobs(e)), "M4_UNREGISTERED_GENERATION_ADDITION"
    return delta


def generation_delta(e):
    return assert_generation_rows(e, e.persistence.load_all())


def cleanup(e):
    for release in e.releases: release.set()
    for job in list(owned_jobs(e).values()):
        if job.status not in e.manager.terminal: e.manager.cancel(job.id)
    for job in list(owned_jobs(e).values()): wait_job(e, job)
    generation_delta(e)  # Every preexisting foreign row must remain exact.


@pytest.fixture
def model_rig(rig, monkeypatch):
    e = configure(rig, monkeypatch)
    yield e
    cleanup(e)


def definition(*, review=True, text="An author-owned source", instruction="Propose a short draft"):
    nodes = [
        {"id": "Input", "definition_id": "text_input", "parameters": {"text": text}},
        {"id": "Generate", "definition_id": "text_generate", "parameters": {
            "instruction": instruction, "max_output_tokens": 128}},
    ]
    edges = [{"id": "Source", "source_node_id": "Input", "source_port": "text",
              "target_node_id": "Generate", "target_port": "text"}]
    if review:
        nodes.append({"id": "Review", "definition_id": "human_review", "parameters": {}})
        edges.append({"id": "Check", "source_node_id": "Generate", "source_port": "draft",
                      "target_node_id": "Review", "target_port": "draft"})
    return {"schema_version": 2, "title": "Bounded model graph", "nodes": nodes, "edges": edges}


def create_graph(e, value=None):
    return e.graphs.create(e.nid, e.scope, e.actor, {"request_id": "graph-" + uuid4().hex,
        "definition": value or definition()}, e.guard)


def admit(e, graph=None):
    graph = graph or create_graph(e)
    preflight = e.graphs.preflight(e.nid, e.scope, e.actor, graph["id"], {"expected_version": graph["version"]}, e.guard)
    assert preflight["executable"], preflight
    row = e.graphs.create_run(e.nid, e.scope, e.actor, graph["id"], {
        "expected_graph_version": graph["version"], "reviewed_preflight_digest": preflight["preflight_digest"],
        "request_id": "run-" + uuid4().hex}, e.guard)
    return action(e, row, "execute")


def action(e, row, name, **extra):
    return e.graphs.action(e.nid, e.scope, e.actor, row["id"], name,
        {"expected_version": row["version"], **extra}, e.guard)


def preview(e, row, **extra):
    return e.models.preview(e.nid, e.scope, e.actor, row["id"], {
        "expected_version": row["version"], "route_id": e.route["route_id"], "allow_synthetic": True, **extra}, e.guard)


def dispatch(e, row, **extra):
    return e.models.dispatch(e.nid, e.scope, e.actor, row["id"], {"expected_version": row["version"],
        "reviewed_preview_digest": row["model_runtime"]["preview"]["preview_digest"], **extra}, e.guard)


def refresh(e, row):
    return e.models.refresh(e.nid, e.scope, e.actor, row["id"], {"expected_version": row["version"]}, e.guard)


def current(e, row):
    return e.graphs.get_run(e.nid, e.scope, e.actor, row["id"], e.guard)


def raw(e, row):
    return e.graphs.store.read(e.nid, e.scope)["collections"][e.graphs.RUNS][row["id"]]


def wait_job(e, job):
    deadline = time.monotonic() + 8
    while job.status not in e.manager.terminal or job.terminal_hook_status is None:
        if time.monotonic() >= deadline:
            pytest.fail("Original M4 worker did not terminate: " + repr(job.public()))
        time.sleep(.005)
    return job


def spy_transport(e, monkeypatch, *, blocked=False, callback=None):
    provider = e.runtime.providers["mock"]
    original = provider.stream
    entered, release = Event(), Event()
    e.releases.append(release)
    def stream(prompt, model, **kwargs):
        e.calls.append({"prompt": prompt, "model": model, "thread": get_ident()})
        entered.set()
        if blocked: assert release.wait(6), "fixture transport release missing"
        if callback: callback()
        yield from original(prompt, model, **kwargs)
    monkeypatch.setattr(provider, "stream", stream)
    return entered, release


def complete(e, row):
    row = dispatch(e, row)
    job = e.manager.get(row["model_runtime"]["execution"]["job_id"])
    wait_job(e, job)
    return refresh(e, current(e, row)), job


def test_real_original_worker_once_only_exact_review_no_chapter_or_canon(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = admit(e)
    assert row["status"] == "WAITING_APPROVAL" and row["current_node_id"] == "Generate"
    assert row["review"] is None and not owned_jobs(e) and not e.calls
    row = preview(e, row)
    assert row["model_runtime"]["contract"] == CONTRACT
    assert row["model_runtime"]["preview"]["execution_available"]
    assert not e.calls and not generation_delta(e)
    waiting, job = complete(e, row)
    assert job.status == "COMPLETED", job.public()
    assert job.chapter_id is None and job.operation == "graph_text"
    assert waiting["status"] == "WAITING_APPROVAL" and waiting["current_node_id"] == "Review"
    assert waiting["review"]["draft"] == {"text": e.runtime.providers["mock"]._text(""), "origin": "MODEL_PROPOSAL"}
    assert waiting["model_called"] and not waiting["reviewed"] and not waiting["applied"]
    assert len(e.calls) == 1 and e.calls[0]["thread"] != get_ident()
    assert e.calls[0]["prompt"] == row["model_runtime"]["preview"]["prompt"]
    assert e.persistence.get(job.id)["graph_binding"]["run_id"] == row["id"]
    for extra in ({}, {"node_id": "Generate", "reviewed_output_digest": waiting["review"]["output_digest"]},
                  {"node_id": "Review", "reviewed_output_digest": "0" * 64}):
        with pytest.raises(StaleSourceError, match="EXACT_REVIEW"): action(e, waiting, "approve", **extra)
    done = action(e, waiting, "approve", node_id="Review", reviewed_output_digest=waiting["review"]["output_digest"])
    assert done["status"] == "SUCCEEDED" and done["reviewed"] and not done["applied"]
    assert e.chapters.list(e.nid) == []
    assert dispatch(e, row)["id"] == row["id"]
    assert len(e.calls) == len(owned_jobs(e)) == len(generation_delta(e)) == 1
    assert len(e.broker.ledger(e.nid, e.scope, e.actor)) == 1


def test_workflow_claim_precedes_job_persistence_and_slow_io_is_outside_scope(model_rig, monkeypatch):
    e = model_rig
    row = preview(e, admit(e))
    events = []
    original_claim = V1CapabilityService.claim_agent_task
    def claim(host, rid, node, *args, **kwargs):
        result = original_claim(host, rid, node, *args, **kwargs)
        if node == "Generate": events.append("claim")
        return result
    monkeypatch.setattr(V1CapabilityService, "claim_agent_task", claim)
    def outside(name, original):
        def checked(*args, **kwargs):
            assert not getattr(e.graphs.store._local, "active", {}), name
            durable = raw(e, row)
            assert durable["node_states"]["Generate"]["status"] == "WORKING"
            assert durable["model_execution"]["job_id"]
            assert "claim" in events
            events.append(name)
            return original(*args, **kwargs)
        return checked
    monkeypatch.setattr(e.manager, "start_prepared", outside("job_start", e.manager.start_prepared))
    monkeypatch.setattr(e.persistence, "save", outside("job_save", e.persistence.save))
    monkeypatch.setattr(e.runtime.providers["mock"], "stream", outside("provider", e.runtime.providers["mock"].stream))
    waiting, job = complete(e, row)
    assert job.status == "COMPLETED", job.public()
    assert events.index("claim") < events.index("job_start") < events.index("provider")
    assert "job_save" in events and waiting["review"]["node_id"] == "Review"


def test_wrong_preview_and_stale_cas_never_admit_original_job(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e))
    with pytest.raises(StaleSourceError, match="EXACT_PREVIEW"): dispatch(e, row, reviewed_preview_digest="0" * 64)
    with pytest.raises(CapabilityVersionConflict): dispatch(e, row, expected_version=row["version"] - 1)
    assert owned_jobs(e) == {} and generation_delta(e) == [] and not e.calls
    assert not e.broker.ledger(e.nid, e.scope, e.actor)
    assert current(e, row) == row


def test_concurrent_dispatch_claims_one_job_and_never_replays(model_rig, monkeypatch):
    e = model_rig; entered, release = spy_transport(e, monkeypatch, blocked=True)
    row = preview(e, admit(e))
    def attempt():
        try: return dispatch(e, row)
        except (CapabilityVersionConflict, StaleSourceError) as error: return error
    try:
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(lambda _: attempt(), range(2)))
        assert entered.wait(3)
        assert any(isinstance(item, dict) for item in results)
        assert len(e.calls) == len(owned_jobs(e)) == 1
        assert dispatch(e, row)["model_runtime"]["execution"]["job_id"] == next(iter(owned_jobs(e)))
    finally: release.set()
    for job in owned_jobs(e).values(): wait_job(e, job)
    assert len(e.broker.ledger(e.nid, e.scope, e.actor)) == 1


@pytest.mark.parametrize("mutation", ["actor", "scope", "definition", "revoke", "flag"])
def test_preview_authority_changes_block_before_inference(model_rig, monkeypatch, mutation):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e)); actor, scope = e.actor, deepcopy(e.scope)
    if mutation == "actor": e.actor = "different-author"
    elif mutation == "scope": e.scope = branch_scope(e)
    elif mutation == "definition":
        graph = e.graphs.get(e.nid, e.scope, e.actor, row["graph_id"])
        e.graphs.save(e.nid, e.scope, e.actor, graph["id"], {"expected_version": graph["version"], "definition": definition(text="Changed")})
    elif mutation == "revoke": e.active = False
    else: monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS.replace("ai_execution_v2,", ""))
    with pytest.raises((FileNotFoundError, StaleSourceError, PermissionError, HTTPException)):
        dispatch(e, row)
    assert not e.calls and not generation_delta(e) and not owned_jobs(e)
    e.actor, e.scope, e.active = actor, scope, True


@pytest.mark.parametrize("mutation", ["revoke", "flag", "cancel", "timeout", "replace_project"])
def test_late_mock_output_is_discarded_after_authority_or_deadline_change(model_rig, monkeypatch, mutation):
    e = model_rig; entered, release = spy_transport(e, monkeypatch, blocked=True)
    row = dispatch(e, preview(e, admit(e)))
    job = e.manager.get(row["model_runtime"]["execution"]["job_id"])
    try:
        assert entered.wait(3)
        if mutation == "revoke": e.active = False
        elif mutation == "flag": monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS.replace("ai_execution_v2,", ""))
        elif mutation == "cancel":
            row = action(e, current(e, row), "cancel")
            assert job.cancelled.is_set()
        elif mutation == "timeout":
            with e.graphs.store.transaction(e.nid, e.scope) as state:
                state["collections"][e.graphs.RUNS][row["id"]]["started_at"] = "2000-01-01T00:00:00+00:00"
        else:
            e.novels.delete(e.nid)
            e.create_project("Recreated same public slug", e.nid)
    finally: release.set()
    wait_job(e, job)
    assert job.status in {"FAILED", "CANCELLED"}, job.public()
    assert job.output == "" and not generation_content_available(job)
    assert len(e.calls) == 1
    e.active = True
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    if mutation == "replace_project":
        with pytest.raises(FileNotFoundError): current(e, row)
        with pytest.raises(KeyError): e.persistence.get(job.id)
        assert all(saved["id"] != job.id for saved in generation_delta(e))
    else:
        refreshed = refresh(e, current(e, row))
        assert refreshed["review"] is None and refreshed["status"] in {"FAILED", "CANCELLED"}
        assert all(value["output"] is None for value in refreshed["node_states"].values())
    assert e.chapters.list(e.nid) == []


def test_original_job_restart_cannot_promote_output_or_replay(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = dispatch(e, preview(e, admit(e)))
    job = e.manager.get(row["model_runtime"]["execution"]["job_id"]); wait_job(e, job)
    old_manager = e.manager
    owner = ForbiddenOwner()
    e.manager = JobManager(e.persistence, owner, owner, owner, memory_extractor=owner)
    e.graphs = CreativeGraphService(e.store, e.service)
    e.graphs.configure_models(e.broker, e.manager); e.models = e.graphs.model_runtime
    recovered = e.manager.get(job.id)
    assert recovered.prepared_text_invocation is None and recovered.request_authorization is None
    assert not generation_content_available(recovered)
    row = refresh(e, current(e, row))
    assert row["status"] == "FAILED" and row["review"] is None
    assert row["model_runtime"]["execution"]["receipt_state"] == "UNKNOWN_NO_AUTOMATIC_REPLAY"
    assert len(e.calls) == len(generation_delta(e)) == 1
    assert old_manager.jobs[job.id].status == "COMPLETED"


def test_lost_start_receipt_retains_claim_and_never_creates_replacement_job(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e))
    original = e.manager.start_prepared
    def lost(job):
        original(job)
        raise OSError("synthetic caller lost start acknowledgement")
    monkeypatch.setattr(e.manager, "start_prepared", lost)
    with pytest.raises(OSError, match="lost start"): dispatch(e, row)
    admitted = current(e, row)
    assert admitted["model_runtime"]["execution"]["receipt_state"] == "UNKNOWN_NO_AUTOMATIC_REPLAY"
    assert dispatch(e, row)["model_runtime"]["execution"]["job_id"] == admitted["model_runtime"]["execution"]["job_id"]
    for job in owned_jobs(e).values(): wait_job(e, job)
    assert len(owned_jobs(e)) == len(e.calls) == 1


def test_broker_mutations_hold_original_scope_then_project_lease_through_commit(model_rig, monkeypatch):
    from threading import local
    e = model_rig; seen = []; state = local()
    original_transaction = e.broker.store.transaction
    @contextmanager
    def transaction(nid, scope):
        with original_transaction(nid, scope) as document:
            state.scope = True
            try:
                yield document
                if getattr(state, "operation", None):
                    assert nid in getattr(e.graphs.store._local, "owners", {}), state.operation
                    seen.append(state.operation)
            finally: state.scope = False
    monkeypatch.setattr(e.broker.store, "transaction", transaction)
    original_lease = e.models.owner_lease
    def lease(nid, incarnation):
        acquire = original_lease(nid, incarnation)
        @contextmanager
        def wrapped():
            assert getattr(state, "scope", False), "Project lease must follow original scope acquisition"
            with acquire(): yield
        return wrapped
    monkeypatch.setattr(e.models, "owner_lease", lease)
    for name in ("preview", "reserve", "guard_dispatch", "finalize"):
        original = getattr(e.broker, name)
        def tracked(*args, _name=name, _original=original, **kwargs):
            state.operation = _name
            try: return _original(*args, **kwargs)
            finally: state.operation = None
        monkeypatch.setattr(e.broker, name, tracked)
    waiting, job = complete(e, preview(e, admit(e)))
    assert job.status == "COMPLETED" and waiting["review"]["node_id"] == "Review"
    assert set(seen) == {"preview", "reserve", "guard_dispatch", "finalize"}


def test_repeated_unchanged_refresh_preserves_bounded_history_and_cancellation(model_rig, monkeypatch):
    e = model_rig; entered, release = spy_transport(e, monkeypatch, blocked=True)
    row = dispatch(e, preview(e, admit(e)))
    try:
        assert entered.wait(3)
        row = refresh(e, row)
        before = raw(e, row)
        for _ in range(30):
            newer = refresh(e, row)
            assert newer == row
        after = raw(e, row)
        assert after["version"] == before["version"] and after["history"] == before["history"]
        cancelled = action(e, row, "cancel")
        assert cancelled["status"] == "CANCELLED"
    finally: release.set()
    for job in owned_jobs(e).values(): wait_job(e, job)


@pytest.mark.parametrize("status,actual", [("UNKNOWN_UPSTREAM", None), ("SETTLED", 1), ("SETTLED", None), ("DISPATCHED", 0)])
def test_unsettled_or_nonzero_original_ledger_cannot_promote_model_output(model_rig, status, actual):
    e = model_rig
    row = dispatch(e, preview(e, admit(e)))
    job = e.manager.get(row["model_runtime"]["execution"]["job_id"]); wait_job(e, job)
    assert job.status == "COMPLETED" and job.terminal_hook_status == "COMPLETED"
    reservation = raw(e, row)["model_execution"]["reservation_id"]
    with e.broker.store.transaction(e.nid, e.scope) as state:
        ledger = state["collections"][e.broker.LEDGER][reservation]
        ledger.update(status=status, actual_microusd=actual)
    row = refresh(e, current(e, row))
    assert row["status"] == "FAILED" and row["review"] is None
    assert row["model_runtime"]["execution"]["receipt_state"] == "UNKNOWN_NO_AUTOMATIC_REPLAY"
    assert all(value["output"] is None for value in row["node_states"].values())


def test_restarted_published_review_is_masked_and_cannot_be_approved(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    waiting, job = complete(e, preview(e, admit(e)))
    assert waiting["review"]
    owner = ForbiddenOwner()
    e.manager = JobManager(e.persistence, owner, owner, owner, memory_extractor=owner)
    e.graphs = CreativeGraphService(e.store, e.service)
    e.graphs.configure_models(e.broker, e.manager); e.models = e.graphs.model_runtime
    visible = current(e, waiting)
    assert visible["stale"] and visible["review"] is None
    assert all(value["output"] is None for value in visible["node_states"].values())
    with pytest.raises((StaleSourceError, ValueError, HTTPException)):
        action(e, waiting, "approve", node_id="Review", reviewed_output_digest=waiting["review"]["output_digest"])
    assert len(e.calls) == 1 and e.chapters.list(e.nid) == []


def test_reviewed_model_result_never_becomes_automatic_cache_or_new_run_authority(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    graph = create_graph(e)
    first, job = complete(e, preview(e, admit(e, graph)))
    first = action(e, first, "approve", node_id="Review", reviewed_output_digest=first["review"]["output_digest"])
    assert first["status"] == "SUCCEEDED"
    second = admit(e, graph)
    assert second["current_node_id"] == "Generate" and second["review"] is None
    assert second["model_runtime"]["status"] == "AWAITING_PREVIEW"
    assert second["node_states"]["Generate"]["output"] is None
    assert second["model_runtime"]["execution"] is None and len(e.calls) == 1
    second, job2 = complete(e, preview(e, second))
    assert job2.id != job.id and second["status"] == "WAITING_APPROVAL" and not second["reviewed"]
    assert len(e.calls) == len(owned_jobs(e)) == 2


def test_lost_broker_reservation_receipt_keeps_claim_and_unknown_hold_without_retry(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e)); reserve = e.broker.reserve
    def lost(*args, **kwargs):
        reserve(*args, **kwargs)
        raise OSError("Synthetic reservation acknowledgement lost")
    monkeypatch.setattr(e.broker, "reserve", lost)
    with pytest.raises(OSError, match="acknowledgement lost"): dispatch(e, row)
    admitted = current(e, row)
    assert admitted["node_states"]["Generate"]["status"] == "WORKING"
    assert admitted["model_runtime"]["execution"]["receipt_state"] == "UNKNOWN_NO_AUTOMATIC_REPLAY"
    assert dispatch(e, row)["model_runtime"]["execution"]["job_id"] == admitted["model_runtime"]["execution"]["job_id"]
    ledger = e.broker.ledger(e.nid, e.scope, e.actor)
    assert len(ledger) == 1 and ledger[0]["status"] == "RESERVED" and not ledger[0]["dispatched"]
    assert not e.calls and not owned_jobs(e) and not generation_delta(e)


@pytest.mark.parametrize("mutation", ["price", "budget"])
def test_price_or_budget_changes_after_preview_block_before_admission(model_rig, monkeypatch, mutation):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e))
    if mutation == "budget":
        e.broker.configure_budget(e.nid, e.scope, e.actor, {"expected_version": 0, "max_inflight": 2})
    else:
        monkeypatch.setattr(e.broker, "_price", lambda *_: None)
    with pytest.raises(StaleSourceError): dispatch(e, row)
    assert not owned_jobs(e) and not e.calls and not generation_delta(e)


def test_predispatch_cancellation_releases_known_zero_hold_with_recorded_receipt(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    entered, release = Event(), Event(); e.releases.append(release)
    original = e.broker.guard_dispatch
    def waiting(*args, **kwargs):
        entered.set()
        assert release.wait(6), "Predispatch cancellation fixture release missing"
        return original(*args, **kwargs)
    monkeypatch.setattr(e.broker, "guard_dispatch", waiting)
    row = dispatch(e, preview(e, admit(e)))
    job = e.manager.get(row["model_runtime"]["execution"]["job_id"])
    try:
        assert entered.wait(3)
        row = action(e, current(e, row), "cancel")
        assert row["status"] == "CANCELLED" and job.cancelled.is_set()
    finally: release.set()
    wait_job(e, job)
    row = refresh(e, current(e, row))
    ledger = e.broker.ledger(e.nid, e.scope, e.actor)
    assert len(ledger) == 1 and ledger[0]["status"] == "RELEASED" and ledger[0]["actual_microusd"] == 0
    assert row["model_runtime"]["execution"]["receipt_state"] == "RECORDED"
    assert not row["model_called"] and row["review"] is None and not e.calls


def test_preview_and_action_history_limits_leave_room_for_original_cancellation(model_rig):
    from app.creative.graph_models import MAX_HISTORY
    e = model_rig; row = admit(e)
    for _ in range(MAX_HISTORY):
        previous = row
        try: row = preview(e, row)
        except ValueError as error:
            assert str(error) == "CREATIVE_MODEL_PREVIEW_HISTORY_CAPACITY"
            assert current(e, previous) == previous
            break
    else: pytest.fail("Model preview did not reserve terminal transition capacity")
    assert len(raw(e, row)["history"]) <= MAX_HISTORY - 10
    while len(raw(e, row)["history"]) < MAX_HISTORY - 2:
        row = action(e, row, "resume" if row["status"] == "PAUSED" else "pause")
    with pytest.raises(ValueError, match="ACTION_HISTORY_CAPACITY"):
        action(e, row, "resume" if row["status"] == "PAUSED" else "pause")
    cancelled = action(e, row, "cancel")
    assert cancelled["status"] == "CANCELLED"
    assert len(raw(e, cancelled)["history"]) <= MAX_HISTORY
    assert not owned_jobs(e) and not generation_delta(e)


def test_exact_global_generation_baseline_with_unrelated_original_history(rig, monkeypatch):
    # Seed an ordinary original generation in a separate fixture-owned project
    # before configuring M4, just as earlier original shared-PG tests can do.
    foreign_project = rig.create_project("Unrelated original generation history")
    foreign_id = str(uuid4())
    rig.bundle.generations.save({"id": foreign_id, "novel_id": foreign_project,
        "operation": "planner", "chapter_id": None, "instruction": "Original planner history",
        "profile": "LOCAL_ONLY", "status": "COMPLETED", "output": "Preserve exact unrelated output",
        "actor_id": "unrelated-original-author", "scope": {"mode": "local", "novel_id": foreign_project},
        "result": {"original": {"notes": ["deep nested metadata must stay exact"]}}})
    e = configure(rig, monkeypatch)
    try:
        foreign_before = deepcopy(e.persistence.get(foreign_id))
        assert e.generation_baseline[foreign_id] == foreign_before
        assert e.manager.jobs[foreign_id].status == "COMPLETED"
        assert not generation_delta(e) and not owned_jobs(e)
        # Exercise the validator against altered copies only. No foreign row is
        # changed/deleted and production load_all is never mocked or filtered.
        snapshot = e.persistence.load_all()
        changed = deepcopy(snapshot)
        next(row for row in changed if row["id"] == foreign_id)["output"] = "Unwanted mutation"
        with pytest.raises(AssertionError, match="PREEXISTING_GENERATION_CHANGED"):
            assert_generation_rows(e, changed)
        added = deepcopy(snapshot) + [{**deepcopy(foreign_before), "id": str(uuid4())}]
        with pytest.raises(AssertionError, match="UNEXPECTED_GENERATION_ADDITION"):
            assert_generation_rows(e, added)
        spy_transport(e, monkeypatch)
        row = preview(e, admit(e))
        with pytest.raises(StaleSourceError, match="EXACT_PREVIEW"):
            dispatch(e, row, reviewed_preview_digest="0" * 64)
        assert not generation_delta(e) and not owned_jobs(e) and not e.calls
        waiting, job = complete(e, row)
        assert waiting["review"]["draft"]["origin"] == "MODEL_PROPOSAL"
        assert {saved["id"] for saved in generation_delta(e)} == {job.id}
        assert set(owned_jobs(e)) == {job.id} and len(e.calls) == 1
        assert e.persistence.get(foreign_id) == foreign_before
    finally:
        cleanup(e)
