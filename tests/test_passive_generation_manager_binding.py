"""Passive ordinary JobManager identities over the original File owner.

These are synthetic local records, not an admission/capture implementation or
live PostgreSQL/provider evidence. Readers and mutations use production owners.
"""
from copy import deepcopy
import json
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import api, jobs as jobs_module
from app.config import Settings
from app.creative.project_store import CreativeProjectStore
from app.jobs import Job, JobManager, generation_content_available, require_generation_content
from app.providers import MockProvider
from app.repositories.factory import create_repository_bundle
from app.runtime import Runtime
from app.services import CanonService, ChapterService, ContextService, GenerationService, LoreService, NovelService
from app.services.generation_project_binding import FIELD, IDENTITY_FIELDS, ordinary_job_binding
from app.stable_identity import StableIdentityStore


pytestmark = pytest.mark.file_backend_only

PUBLIC_FIELDS = {
    "id", "operation", "novel_id", "chapter_id", "instruction", "profile", "source",
    "requested_provider", "requested_model", "style", "status", "output", "error",
    "error_code", "provider", "model", "issues", "latency_ms", "base_chapter_version",
    "variant_group_id", "variant_index", "actor_id", "session_id", "client_id",
    "workspace_id", "scope", "scope_type", "scope_id", "correlation_id",
    "context_snapshot_id", "created_at", "updated_at", "creation_records", "usage",
    "usage_status", "execution_mode", "provider_reference_id", "route_decisions",
}
EXECUTION_HOOKS = {
    "request_authorization", "author_context_resolver", "character_context_resolver",
    "before_dispatch", "on_terminal", "author_preparation_guard",
    "creative_execution_authority", "research_ocr_execution_authority",
    "director_image_authority", "prepared_text_invocation",
}
MUTATION_CODE = "GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED"


@pytest.fixture
def source(tmp_path, monkeypatch):
    import app.main as main_module
    from app.main import app

    config = Settings(storage_backend="file", novel_data=tmp_path, mock_provider=True,
                      enable_collaboration_runtime=False, enable_packaged_runtime=False)
    bundle = create_repository_bundle(config, tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    novel = novels.create({"id": "passive-manager-book", "title": "Original owner"})
    created = chapters.create(novel["id"], {"title": "One", "content": "ORIGINAL_SOURCE"})
    chapter = chapters.get(created["id"])
    contexts = ContextService(bundle.novels, bundle.chapters, LoreService(bundle.lore))
    canon = CanonService(bundle.canon)
    persistence = GenerationService(bundle.generations)
    owner = CreativeProjectStore(SimpleNamespace(backend="file", root=tmp_path))
    incarnation = owner.incarnation(novel["id"])
    counts = dict(worker=0, adapter=0, stream=0, memory=0)
    finished = Event()

    def memory(*_args):
        counts["memory"] += 1
        return "synthetic-memory-job"

    def reopen():
        return JobManager(generations=GenerationService(type(bundle.generations)(tmp_path)),
            chapters=chapters, contexts=contexts, canon=canon, snapshot_required=False,
            memory_extractor=SimpleNamespace(enqueue=memory))

    runtime = Runtime(StableIdentityStore(tmp_path / "runtime" / "passive-identities.json"))

    class ObservedMock(MockProvider):
        def stream(self, *args, **kwargs):
            counts["stream"] += 1
            yield from super().stream(*args, **kwargs)

    runtime.providers["mock"] = ObservedMock(delay_ms=0)
    runtime._sync_model("mock", "mock-writer")
    adapter = runtime.provider_registry.resolve("mock")
    original_adapter = adapter.stream_text

    def stream(request):
        counts["adapter"] += 1
        return original_adapter(request)

    monkeypatch.setattr(adapter, "stream_text", stream)
    original_run = JobManager._run

    def run(manager, job):
        counts["worker"] += 1
        try:
            return original_run(manager, job)
        finally:
            finished.set()

    monkeypatch.setattr(JobManager, "_run", run)
    for module in (api, jobs_module, main_module):
        monkeypatch.setattr(module, "settings", config)
    monkeypatch.setattr(api, "runtime", runtime)
    monkeypatch.setattr(jobs_module, "runtime", runtime)
    monkeypatch.setattr(api, "novel_service", novels)
    monkeypatch.setattr(api, "chapter_service", chapters)
    manager = reopen()
    monkeypatch.setattr(api, "jobs", manager)
    fixture = SimpleNamespace(root=tmp_path, config=config, bundle=bundle, novels=novels,
        chapters=chapters, chapter=chapter, contexts=contexts, canon=canon,
        persistence=persistence, owner=owner, incarnation=incarnation, counts=counts,
        finished=finished, manager=manager, reopen=reopen, monkeypatch=monkeypatch,
        runtime=runtime, original_run=original_run,
        client=TestClient(app, raise_server_exceptions=False))
    yield fixture
    if counts["worker"]:
        assert finished.wait(10), "original worker did not finish"


def _record(source, *, status="COMPLETED", bound=True, group="ordinary-variants", index=1):
    job = Job(str(uuid4()), "continue", source.chapter["novel_id"], source.chapter["id"],
        "Continue", "LOCAL_ONLY", source="ORIGINAL_SOURCE", status=status,
        output="RETAINED_DRAFT", requested_provider="mock", requested_model="mock-writer",
        base_chapter_version=source.chapter["version"], variant_group_id=group,
        variant_index=index)
    row = job.public()
    if bound:
        row["experimental_origin"] = None
        row[FIELD] = dict(schema_version=1, project_incarnation=source.incarnation,
            job_id=job.id, project_id=job.novel_id,
            **{key: deepcopy(row[key]) for key in IDENTITY_FIELDS})
    return row


def _load(source, **kwargs):
    row = _record(source, **kwargs)
    source.persistence.save(row)
    manager = source.reopen()
    source.monkeypatch.setattr(api, "jobs", manager)
    return row, manager, manager.get(row["id"])


def _replace_owner(source):
    nid = source.chapter["novel_id"]
    source.novels.delete(nid)
    source.novels.create({"id": nid, "title": "Replacement owner"})
    replacement = source.chapters.create(nid, {"title": "One", "content": "REPLACEMENT_SOURCE"})
    assert replacement["id"] == source.chapter["id"]
    assert source.owner.incarnation(nid) != source.incarnation


def _corrupt(source, row, change):
    path = source.bundle.generations._job_path(row["id"])
    if change == "replace_owner":
        _replace_owner(source)
    elif change == "missing_marker":
        (source.root / "novels" / row["novel_id"] / "creative_project_v2.json").unlink()
    elif change == "missing_record":
        path.unlink()
    elif change == "malformed_json":
        path.write_text("{not-json", encoding="utf-8")
    else:
        changed = deepcopy(row)
        if change == "binding_removed":
            del changed[FIELD]
        elif change == "binding_null":
            changed[FIELD] = None
        elif change == "binding_unknown_version":
            changed[FIELD]["schema_version"] = 2
        elif change == "outer_identity_missing":
            del changed["actor_id"]
        elif change == "identity_changed":
            changed["chapter_id"] = changed[FIELD]["chapter_id"] = row["novel_id"] + ":2"
        elif change == "owner_changed":
            changed[FIELD]["project_incarnation"] = "file:" + str(uuid4())
        else:
            raise AssertionError(change)
        path.write_text(json.dumps(changed), encoding="utf-8")


def _assert_hidden(call):
    with pytest.raises((KeyError, FileNotFoundError, HTTPException)) as denied:
        call()
    if isinstance(denied.value, HTTPException):
        assert denied.value.status_code == 404


@pytest.mark.parametrize("status", ["COMPLETED", "FAILED", "RUNNING", "GENERATING", "QUEUED", "PREPARED"])
def test_cold_restore_keeps_binding_separate_from_public_and_never_dispatches(source, status):
    row, manager, job = _load(source, status=status)
    expected_status = status if status in {"COMPLETED", "FAILED"} else "FAILED"
    assert job.status == expected_status
    assert getattr(job, FIELD) == row[FIELD]
    assert set(job.public()) == PUBLIC_FIELDS
    assert set(job.record()) == PUBLIC_FIELDS | {FIELD, "experimental_origin"}
    assert ordinary_job_binding(job.record()) == row[FIELD]
    assert all(getattr(job, name) is None for name in EXECUTION_HOOKS)
    assert EXECUTION_HOOKS.isdisjoint(job.public())
    assert EXECUTION_HOOKS.isdisjoint(job.record())
    assert not (manager.transient_fields & set(job.record()))
    assert source.counts == dict(worker=0, adapter=0, stream=0, memory=0)
    assert generation_content_available(job)
    durable = manager.persistence.get(job.id)
    assert durable[FIELD] == row[FIELD] and durable["status"] == expected_status
    # A second cold manager must preserve the same passive identity, too.
    again = source.reopen().get(job.id)
    assert again.record() == job.record()
    detached = job.record()
    detached[FIELD]["chapter_id"] = "mutated-copy"
    assert getattr(job, FIELD)["chapter_id"] == row["chapter_id"]


def test_persistence_projection_retains_binding_on_original_manager_save(source):
    row, manager, job = _load(source)
    job.output = "UPDATED_DRAFT"
    manager._persist(job)
    saved = source.reopen().persistence.get(job.id)
    assert saved[FIELD] == row[FIELD]
    assert saved["experimental_origin"] is None
    assert saved["output"] == "UPDATED_DRAFT"
    assert FIELD not in job.public()


def test_restore_reconstructs_only_read_verifier_and_ignores_persisted_callbacks(source):
    row = _record(source)
    row.update({name: "forged-durable-callback" for name in EXECUTION_HOOKS})
    row["_ordinary_read_verifier"] = "forged-durable-verifier"
    source.persistence.save(row)
    manager = source.reopen()
    job = manager.get(row["id"])
    assert callable(job._ordinary_read_verifier)
    assert job._ordinary_read_verifier.__self__ is manager
    assert all(getattr(job, name) is None for name in EXECUTION_HOOKS)
    assert not (manager.transient_fields & set(job.record()))
    assert generation_content_available(job)
    assert source.counts == dict(worker=0, adapter=0, stream=0, memory=0)


def test_preparation_does_not_capture_or_consume_client_supplied_binding(source):
    supplied = _record(source)[FIELD]
    job = source.manager.prepare_job("continue", {
        "novel_id": source.chapter["novel_id"], "chapter_id": source.chapter["id"],
        "instruction": "Continue", "profile": "LOCAL_ONLY", FIELD: supplied,
    })
    assert FIELD not in api.GenerateIn.model_fields
    assert FIELD not in job.record() and FIELD not in job.public()
    assert job._ordinary_read_verifier is None
    assert source.counts["worker"] == source.counts["adapter"] == 0


@pytest.mark.parametrize("status", ["COMPLETED", "RUNNING"])
def test_bound_restore_refuses_same_slug_chapters_from_another_file_root(source, status):
    row = _record(source, status=status)
    source.persistence.save(row)
    before = source.bundle.generations._job_path(row["id"]).read_bytes()
    other_root = source.root / "other-root"
    config = Settings(storage_backend="file", novel_data=other_root, mock_provider=True)
    other = create_repository_bundle(config, other_root)
    novels = NovelService(other.novels, other.chapters)
    chapters = ChapterService(other.chapters)
    novels.create({"id": row["novel_id"], "title": "Unrelated same slug"})
    created = chapters.create(row["novel_id"], {"title": "One", "content": "FOREIGN_SOURCE"})
    assert created["id"] == row["chapter_id"]
    manager = JobManager(generations=source.persistence, chapters=chapters,
        contexts=source.contexts, canon=source.canon, memory_extractor=object(),
        snapshot_required=False)
    assert row["id"] not in manager.jobs
    _assert_hidden(lambda: manager.get(row["id"]))
    assert source.bundle.generations._job_path(row["id"]).read_bytes() == before
    assert source.counts["worker"] == 0


@pytest.mark.parametrize("invalid", [None, [], {}, {"schema_version": True}])
def test_present_invalid_binding_never_serializes_as_legacy(source, invalid):
    job = Job(str(uuid4()), "continue", source.chapter["novel_id"], source.chapter["id"], "", "LOCAL_ONLY")
    setattr(job, FIELD, invalid)
    with pytest.raises(ValueError):
        job.record()
    with pytest.raises(ValueError):
        source.manager._persist(job)
    assert not source.bundle.generations._job_path(job.id).exists()


def test_unbound_public_and_record_are_exact_original_projection(source):
    row, manager, job = _load(source, bound=False)
    assert job.public() == row
    assert job.record() == row
    assert set(row) == PUBLIC_FIELDS
    assert FIELD not in job.record()
    assert generation_content_available(job)
    manager._persist(job)
    assert manager.persistence.get(job.id) == row


CHANGES = ["replace_owner", "missing_marker", "missing_record", "malformed_json",
           "binding_removed", "binding_null", "binding_unknown_version",
           "outer_identity_missing", "identity_changed", "owner_changed"]


@pytest.mark.parametrize("change", CHANGES)
def test_cached_reads_content_variants_and_diff_recheck_original_durable_owner(source, change):
    row, manager, job = _load(source)
    assert manager.variants(row["variant_group_id"]) == [job]
    assert "RETAINED_DRAFT" in manager.diff(job.id)
    _corrupt(source, row, change)
    _assert_hidden(lambda: manager.get(job.id))
    assert not generation_content_available(job)
    _assert_hidden(lambda: require_generation_content(job))
    _assert_hidden(lambda: manager.diff(job.id))
    assert manager.variants(row["variant_group_id"]) == []
    assert source.counts == dict(worker=0, adapter=0, stream=0, memory=0)
    if change == "missing_marker":
        assert not (source.root / "novels" / row["novel_id"] / "creative_project_v2.json").exists()


@pytest.mark.parametrize("change", CHANGES)
def test_held_event_iterator_stops_before_next_chunk_when_durable_identity_changes(source, change):
    row, manager, job = _load(source)
    # The held iterator is a live observer, without starting or authorizing work.
    job.status = "RUNNING"
    events = manager.events(job.id)
    first = next(events)
    assert json.loads(first.removeprefix("data: "))["chunk"] == "RETAINED_DRAFT"
    _corrupt(source, row, change)
    job.output += "\nMUST_NOT_ESCAPE"
    job.status = "COMPLETED"
    assert list(events) == []
    assert source.counts["worker"] == source.counts["adapter"] == 0


def test_bound_events_never_hold_condition_during_original_repository_read(source):
    _, manager, job = _load(source)
    job.status = "RUNNING"
    repository = manager.persistence.repository
    original = repository.get
    observed = []

    def get(jid):
        observed.append(job.condition._is_owned())
        return original(jid)

    source.monkeypatch.setattr(repository, "get", get)
    events = manager.events(job.id)
    assert "RETAINED_DRAFT" in next(events)
    job.status = "COMPLETED"
    assert len(list(events)) == 1
    assert len(observed) >= 4
    assert not any(observed), "repository owner read ran under job.condition"


def test_variant_filter_preserves_unbound_legacy_compatibility(source):
    bound = _record(source)
    legacy = _record(source, bound=False, index=2)
    source.persistence.save(bound)
    source.persistence.save(legacy)
    manager = source.reopen()
    assert [job.id for job in manager.variants(bound["variant_group_id"])] == [bound["id"], legacy["id"]]
    _replace_owner(source)
    assert [job.id for job in manager.variants(bound["variant_group_id"])] == [legacy["id"]]
    assert manager.get(legacy["id"]).record() == legacy


@pytest.mark.parametrize("operation", ["accept", "reject", "cancel", "start_prepared"])
def test_passive_bound_mutations_fail_before_side_effects(source, operation):
    row, manager, job = _load(source)
    original = source.bundle.generations._job_path(job.id).read_bytes()
    chapter = source.chapters.get(row["chapter_id"])
    pending = deepcopy(source.canon.list_pending(row["novel_id"]))
    with pytest.raises(HTTPException) as denied:
        if operation == "start_prepared":
            manager.start_prepared(job)
        else:
            getattr(manager, operation)(job.id)
    assert denied.value.status_code == 409
    assert denied.value.detail["code"] == MUTATION_CODE
    assert job.status == "COMPLETED" and not job.cancelled.is_set()
    assert source.bundle.generations._job_path(job.id).read_bytes() == original
    assert source.chapters.get(row["chapter_id"]) == chapter
    assert len(source.chapters.list(row["novel_id"])) == 1
    assert source.canon.list_pending(row["novel_id"]) == pending
    assert source.counts == dict(worker=0, adapter=0, stream=0, memory=0)


@pytest.mark.parametrize("operation", ["_run", "_cancel_execution", "_start_prepared_validated",
                                       "stage_reviewed_variants"])
def test_direct_passive_execution_and_variant_staging_have_zero_side_effects(source, operation):
    row, manager, job = _load(source)
    before = source.bundle.generations._job_path(job.id).read_bytes()
    chapter = source.chapters.get(row["chapter_id"])
    pending = deepcopy(source.canon.list_pending(row["novel_id"]))
    callbacks = []
    job.status = "PREPARED"
    job.request_authorization = lambda: callbacks.append("authorize")
    job.before_dispatch = lambda: callbacks.append("dispatch")
    job.on_terminal = lambda: callbacks.append("terminal")
    job.reviewed_variant = {"variant_index": 2}
    job.expected_request_digest = "a" * 64
    jobs = [job]
    if operation == "stage_reviewed_variants":
        manager.jobs.pop(job.id)
        legacy = manager.prepare_job("continue", {"novel_id": row["novel_id"],
            "chapter_id": row["chapter_id"], "instruction": "Continue"})
        legacy.reviewed_variant = {"variant_index": 1}
        legacy.expected_request_digest = "a" * 64
        legacy.request_authorization = lambda: callbacks.append("legacy-authorize")
        jobs = [legacy, job]
    identifiers = set(manager.jobs)
    states = [item.public() for item in jobs]
    with pytest.raises(HTTPException) as denied:
        if operation == "_run":
            source.original_run(manager, job)
        elif operation == "stage_reviewed_variants":
            manager.stage_reviewed_variants(jobs)
        else:
            getattr(manager, operation)(job)
    assert denied.value.status_code == 409 and denied.value.detail["code"] == MUTATION_CODE
    assert [item.public() for item in jobs] == states
    assert set(manager.jobs) == identifiers
    assert not callbacks and not job.cancelled.is_set()
    assert source.bundle.generations._job_path(job.id).read_bytes() == before
    if operation == "stage_reviewed_variants":
        assert not source.bundle.generations._job_path(jobs[0].id).exists()
    assert source.chapters.get(row["chapter_id"]) == chapter
    assert source.canon.list_pending(row["novel_id"]) == pending
    assert source.counts == dict(worker=0, adapter=0, stream=0, memory=0)


@pytest.mark.parametrize("action,status", [("retry", "FAILED"), ("cancel", "COMPLETED"),
                                           ("accept", "COMPLETED"), ("reject", "COMPLETED")])
def test_mounted_bound_mutations_are_explicit_409_and_never_dispatch(source, action, status):
    row, manager, job = _load(source, status=status)
    before = source.bundle.generations._job_path(job.id).read_bytes()
    response = source.client.post(f"/api/generation/{job.id}/{action}")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == MUTATION_CODE
    assert source.bundle.generations._job_path(job.id).read_bytes() == before
    assert set(manager.jobs) == {job.id}
    assert source.counts == dict(worker=0, adapter=0, stream=0, memory=0)


def test_mounted_bound_read_has_original_public_shape_without_internal_identity(source):
    row, _, job = _load(source)
    response = source.client.get(f"/api/generation/{job.id}")
    assert response.status_code == 200, response.text
    assert set(response.json()) == PUBLIC_FIELDS | {"diff"}
    assert row[FIELD]["project_incarnation"] not in response.text
    group = source.client.get(f"/api/generation-groups/{row['variant_group_id']}")
    assert group.status_code == 200, group.text
    assert group.json()["variants"] == [job.public()]
    assert FIELD not in group.text
    events = source.client.get(f"/api/generation/{job.id}/events")
    assert events.status_code == 200, events.text
    assert "RETAINED_DRAFT" in events.text and FIELD not in events.text


def test_mounted_cached_reads_and_original_taskcenter_hide_replaced_owner(source):
    from app.experimental.author_task_projection import create_author_task_reader
    from app.experimental.ux import ReadContext

    row, manager, job = _load(source)
    ctx = ReadContext(job.novel_id, {"mode": "local", "novel_id": job.novel_id}, "local-author")
    reader = create_author_task_reader(manager, lambda *_: (ctx.actor, ctx.scope),
        lambda _flag: None, api.generation)
    assert [item["id"] for item in reader(ctx)["items"]] == [job.id]
    _replace_owner(source)
    assert reader(ctx) == {"items": [], "has_more": False}
    for route in (f"/api/generation/{job.id}", f"/api/generation/{job.id}/events",
                  f"/api/generation-groups/{row['variant_group_id']}"):
        response = source.client.get(route)
        assert response.status_code in {400, 404}, response.text
        assert "RETAINED_DRAFT" not in response.text and "ORIGINAL_SOURCE" not in response.text


def test_unbound_retry_runs_original_mock_worker_and_accepts_without_binding(source):
    row, manager, _ = _load(source, bound=False, status="FAILED")
    response = source.client.post(f"/api/generation/{row['id']}/retry")
    assert response.status_code == 202, response.text
    assert response.json()["retry_of"] == row["id"]
    assert source.finished.wait(10), "original retry worker did not finish"
    job = manager.get(response.json()["job_id"])
    assert job.status == "COMPLETED", (job.error, job.error_code)
    assert source.counts["worker"] == source.counts["adapter"] == source.counts["stream"] == 1
    assert FIELD not in job.public() and FIELD not in job.record()
    assert FIELD not in manager.persistence.get(job.id)
    accepted = source.client.post(f"/api/generation/{job.id}/accept")
    assert accepted.status_code == 200, accepted.text
    assert manager.get(job.id).status == "ACCEPTED"
    saved = source.chapters.get(accepted.json()["chapter"]["id"])
    assert saved["id"] != source.chapter["id"] and job.output in saved["content"]
    assert len(source.chapters.list(job.novel_id)) == 2
    assert source.counts["memory"] == 1
    assert FIELD not in manager.persistence.get(job.id)


# These fixtures provide original File membership, trusted sessions and branch
# manuscript owners. Their counting dispatcher is replaced by the real manager.
from test_generation_idempotency_contracts import generation, collaboration_generation


def _collaborative_record(source, monkeypatch, *, bound):
    monkeypatch.setattr(jobs_module, "settings", api.settings)
    persistence = GenerationService(source.bundle.generations)
    manager = JobManager(generations=persistence, chapters=source.chapters,
        contexts=ContextService(source.bundle.novels, source.bundle.chapters, LoreService(source.bundle.lore)),
        canon=CanonService(source.bundle.canon), snapshot_required=False,
        memory_extractor=object())
    body = api.GenerateIn(**source.payload)
    actor, scope = api._generation_request_context(body, "opaque-alice", "branch-a")
    job = manager.prepare_job("continue", body.model_dump(), actor, scope)
    job.status = "FAILED"
    row = job.public()
    if bound:
        owner = CreativeProjectStore(SimpleNamespace(backend="file", root=source.root))
        row[FIELD] = dict(schema_version=1, project_incarnation=owner.incarnation(job.novel_id),
            job_id=job.id, project_id=job.novel_id,
            **{key: deepcopy(row[key]) for key in IDENTITY_FIELDS})
    persistence.save(row)
    reopened = JobManager(generations=persistence, chapters=source.chapters,
        contexts=manager.contexts, canon=manager.canon, memory_extractor=object(),
        snapshot_required=False)
    monkeypatch.setattr(api, "jobs", reopened)
    return row, reopened, reopened.get(job.id)


@pytest.mark.parametrize("bound", [False, True])
def test_collaborative_retry_keeps_original_preview_guard_before_passive_guard(
        collaboration_generation, monkeypatch, bound):
    source = collaboration_generation
    row, reopened, job = _collaborative_record(source, monkeypatch, bound=bound)
    attempts = []

    def forbidden_worker(_job):
        attempts.append(True)
        pytest.fail("preview-required retry dispatched a worker")

    monkeypatch.setattr(reopened, "_run", forbidden_worker)
    response = source.client.post(f"/api/generation/{job.id}/retry")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "AUTHOR_PREVIEW_REQUIRED"
    assert not attempts and set(reopened.jobs) == {job.id}
    assert reopened.persistence.get(job.id) == row


@pytest.mark.parametrize("change", ["unregistered", "foreign_store", "foreign_mainline"])
def test_registered_branch_passive_reads_require_the_original_registered_owner(
        collaboration_generation, monkeypatch, change):
    from app.experimental.store import ExperimentalStore
    from app.services.branch_manuscript_service import BranchManuscriptService

    source = collaboration_generation
    row, manager, job = _collaborative_record(source, monkeypatch, bound=True)
    assert manager.get(job.id) is job
    assert generation_content_available(job)
    assert manager.chapters_for_job(job).get(job.chapter_id)["id"] == job.chapter_id
    response = source.client.get(f"/api/generation/{job.id}")
    assert response.status_code == 200, response.text
    assert FIELD not in response.text
    original = source.branches
    if change == "unregistered":
        monkeypatch.setattr(source.chapters, "branch_authority", None)
    else:
        store = (ExperimentalStore(source.root / "foreign-branch-root", "file")
                 if change == "foreign_store" else original.store)
        mainline = (ChapterService(source.bundle.chapters)
                    if change == "foreign_mainline" else source.chapters)
        replacement = BranchManuscriptService(store, source.novels, mainline, original.scopes)
        monkeypatch.setattr(source.chapters, "branch_authority", replacement.for_scope)
    _assert_hidden(lambda: manager.get(job.id))
    assert not generation_content_available(job)
    assert manager.variants(row["variant_group_id"]) == []
    cold = JobManager(generations=manager.persistence, chapters=source.chapters,
        contexts=manager.contexts, canon=manager.canon, memory_extractor=object(),
        snapshot_required=False)
    assert job.id not in cold.jobs
    assert manager.persistence.get(job.id) == row
