"""Inert Creative binding foundation; no model call or execution admission."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.creative.director_binding import (CreativeDirectorBinding,
    CREATIVE_DIRECTOR_OPERATION, CREATIVE_DIRECTOR_ORIGIN, is_creative_director_job,
    validate_creative_director_source)
from app.jobs import (Job, JobManager, generation_content_available,
    require_whole_generation_acceptance, check_generation_bounds)
from app.model_execution import (PreparedTextInvocation, creative_director_request_payload_digest,
    graph_request_payload_digest)
from app.author_request import build_author_request, request_digest, request_payload
from app.model_runtime import TextGenerationRequest, TextGenerationParameters


def binding_values():
    return dict(contract="CREATIVE_DIRECTOR_SOURCE_V1", source_kind="STORYBOARD",
        project_id="independent", project_incarnation="file:22222222-2222-4222-8222-222222222222",
        actor_id="actor", scope={"mode":"local", "novel_id":"independent"},
        source_document_id="saved-board", source_version=1,
        source_digest="a"*64, reviewed_preview_digest="b"*64)


def inert_job(**changes):
    values = dict(id=str(uuid4()), operation=CREATIVE_DIRECTOR_OPERATION, novel_id="independent",
        chapter_id=None, instruction="", profile="LOCAL_ONLY", actor_id="actor",
        scope={"mode":"local", "novel_id":"independent"}, status="PREPARED",
        creative_director_binding=binding_values(), experimental_origin=CREATIVE_DIRECTOR_ORIGIN,
        requested_provider="mock", requested_model="mock-writer", generation_max_output_bytes=32000,
        generation_deadline="2030-01-02T03:04:05+00:00")
    values.update(changes)
    return Job(**values)


class Forbidden:
    def __getattr__(self, name):
        raise AssertionError("Inert foundation accessed forbidden owner: " + name)

    def __call__(self, *args, **kwargs):
        raise AssertionError("Inert foundation invoked authority or provider")


def test_binding_and_nested_scope_are_frozen_and_detached():
    original = binding_values()
    binding = CreativeDirectorBinding.model_validate(original)
    original["scope"]["novel_id"] = "changed"
    assert binding.scope.novel_id == "independent"
    with pytest.raises(ValueError): binding.source_version = 2
    with pytest.raises(ValueError): binding.scope.novel_id = "changed"
    exported = binding.model_dump(); exported["scope"]["novel_id"] = "changed"
    assert binding.scope.novel_id == "independent"
    job = inert_job(); public = job.public(); public["creative_director_binding"]["scope"]["novel_id"] = "changed"
    assert job.creative_director_binding["scope"]["novel_id"] == "independent"
    legacy = Job(str(uuid4()), "brainstorm", "independent", "chapter", "", "LOCAL_ONLY")
    assert "creative_director_binding" not in legacy.public()


@pytest.mark.parametrize("field,value", [
    ("contract", None), ("contract", "creative_director_source_v1"), ("source_kind", "SCREENPLAY"),
    ("source_version", True), ("source_version", "1"), ("source_version", 0),
    ("source_version", 2**53), ("source_digest", "A"*64),
    ("project_incarnation", "22222222-2222-4222-8222-222222222222"),
    ("project_incarnation", "file:22222222222242228222222222222222"),
    ("project_incarnation", "file:22222222-2222-1222-8222-222222222222"),
    ("scope", {"mode":"local", "novel_id":"other"}),
    ("scope", {"mode":"local", "novel_id":"independent", "branch_id":"unexpected"}),
    ("scope", {"mode":"collaboration", "novel_id":"independent"}),
    ("endpoint", "https://unapproved.example"),
])
def test_binding_rejects_coercions_unknown_fields_and_noncanonical_identity(field, value):
    with pytest.raises(ValueError): CreativeDirectorBinding.model_validate(dict(binding_values(), **{field:value}))


@pytest.mark.parametrize("field", ["contract", "source_kind", "scope", "source_digest", "reviewed_preview_digest"])
def test_missing_binding_fields_are_not_repaired(field):
    values = binding_values(); values.pop(field)
    with pytest.raises(ValueError): CreativeDirectorBinding.model_validate(values)


def test_complete_collaboration_scope_is_strict_and_frozen():
    values = binding_values()
    values["scope"] = dict(mode="collaboration", novel_id="independent", workspace_id="w", storyline_id="s", branch_id="b")
    binding = CreativeDirectorBinding.model_validate(values)
    with pytest.raises(ValueError): binding.scope.branch_id = "other"
    values["scope"]["branch_id"] = True
    with pytest.raises(ValueError): CreativeDirectorBinding.model_validate(values)


@pytest.mark.parametrize("discriminator", ["binding", "operation", "origin", "all", "mixed_graph", "mixed_adaptation"])
def test_all_execution_boundaries_deny_every_discriminator_before_side_effects(monkeypatch, discriminator):
    import app.jobs as jobs_module
    job = inert_job(operation="brainstorm", experimental_origin=None, creative_director_binding=None)
    if discriminator in {"binding", "all", "mixed_graph", "mixed_adaptation"}: job.creative_director_binding = binding_values()
    if discriminator in {"operation", "all"}: job.operation = CREATIVE_DIRECTOR_OPERATION
    if discriminator in {"origin", "all"}: job.experimental_origin = CREATIVE_DIRECTOR_ORIGIN
    if discriminator == "mixed_graph":
        job.operation = "graph_text"; job.experimental_origin = "creative_graph_model"; job.graph_binding = {}
    if discriminator == "mixed_adaptation":
        job.experimental_origin = "creative_adaptation_model"; job.adaptation_binding = {}
    blocked = Forbidden()
    job.request_authorization = job.author_preparation_guard = job.before_dispatch = job.on_terminal = blocked
    job.prepared_text_invocation = blocked
    manager = object.__new__(JobManager)
    manager.persistence = manager.chapters = manager.contexts = manager.canon = blocked
    monkeypatch.setattr(jobs_module, "runtime", blocked)
    monkeypatch.setattr(jobs_module.threading, "Thread", blocked)
    assert is_creative_director_job(job) and not generation_content_available(job)
    for action in (lambda: manager.start_prepared(job), lambda: manager._run(job),
            lambda: manager.prepare_author_request(job, blocked), lambda: manager._guard_author_request(job, blocked),
            lambda: manager._guard_graph_request(job), lambda: check_generation_bounds(job)):
        with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE"): action()
    request = TextGenerationRequest("mock", "mock-writer", "passive request")
    with pytest.raises(ValueError, match="GRAPH_PREPARED_DOMAIN_INVALID"):
        PreparedTextInvocation.bind(job, request, blocked, True)
    forged = PreparedTextInvocation(request, blocked, "d"*64, True)
    with pytest.raises(ValueError, match="GRAPH_PREPARED_DOMAIN_INVALID"): forged.validate_job(job)
    with pytest.raises(HTTPException) as caught: require_whole_generation_acceptance(job)
    assert caught.value.status_code == 409 and job.status == "PREPARED"
    job.status = "COMPLETED"; job.output = "forged output"; job.terminal_hook_status = "COMPLETED"
    assert not generation_content_available(job)
    manager.jobs = {job.id:job}
    for action in (lambda: manager.accept(job.id), lambda: manager.reject(job.id), lambda: manager.diff(job.id)):
        with pytest.raises(HTTPException) as caught: action()
        assert caught.value.status_code == 404
    assert list(manager.events(job.id, authorize=blocked)) == []
    assert job.status == "COMPLETED" and job.output == "forged output"


@pytest.mark.parametrize("operation,extra", [
    (CREATIVE_DIRECTOR_OPERATION, {}),
    ("brainstorm", {"operation":CREATIVE_DIRECTOR_OPERATION}),
    ("brainstorm", {"experimental_origin":CREATIVE_DIRECTOR_ORIGIN}),
    ("brainstorm", {"creative_director_binding":None}),
    ("brainstorm", {"creative_director_binding":{}}),
    ("brainstorm", {"creative_director_binding":False}),
    ("brainstorm", {"creative_director_binding":"malformed"}),
])
def test_raw_author_preparation_cannot_strip_reserved_markers(operation, extra):
    manager = object.__new__(JobManager)
    manager.chapters = manager.contexts = manager.canon = manager.persistence = Forbidden()
    payload = dict(novel_id="independent", chapter_id="must-not-read", **extra)
    for action in (lambda: manager.prepare_job(operation, payload), lambda: manager.create(operation, payload)):
        with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE"): action()


def test_new_digest_is_passive_domain_separated_and_covers_exact_inputs():
    job = inert_job()
    payload = request_payload(TextGenerationRequest("mock", "mock-writer", "Exact source prompt"))
    digest = creative_director_request_payload_digest(job, payload, True, route_fingerprint="c"*64)
    assert job.expected_request_digest is None and job.prepared_text_invocation is None
    assert len(digest) == 64
    for changed in (dict(payload, prompt="Different prompt"), dict(payload, context={"explicit":"different"}),
                    dict(payload, parameters={"temperature":0.5, "max_output_tokens":128, "stop_sequences":[]})):
        assert creative_director_request_payload_digest(job, changed, True, route_fingerprint="c"*64) != digest
    assert creative_director_request_payload_digest(job, payload, True, route_fingerprint="d"*64) != digest
    assert creative_director_request_payload_digest(job, payload, False, route_fingerprint="c"*64) != digest
    for field, value in (("generation_max_output_bytes", 16000), ("generation_deadline", "2030-01-02T03:05:00+00:00"),
                         ("id", str(uuid4()))):
        changed = replace(job, **{field:value})
        assert creative_director_request_payload_digest(changed, payload, True, route_fingerprint="c"*64) != digest
    changed = replace(job, creative_director_binding=dict(binding_values(), source_digest="e"*64))
    assert creative_director_request_payload_digest(changed, payload, True, route_fingerprint="c"*64) != digest
    for value in (1, None, "true"):
        with pytest.raises(ValueError): creative_director_request_payload_digest(job, payload, value, route_fingerprint="c"*64)
    with pytest.raises(ValueError): creative_director_request_payload_digest(job, payload, True, route_fingerprint="C"*64)
    with pytest.raises(ValueError): creative_director_request_payload_digest(job, dict(payload, provider_id="other"), True, route_fingerprint="c"*64)
    with pytest.raises(ValueError): creative_director_request_payload_digest(job, dict(payload, context={"number":float("nan")}), True, route_fingerprint="c"*64)


def test_actual_prechange_graph_and_screenplay_payload_hash_goldens_are_unchanged():
    path = Path(__file__).parent / "fixtures/creative_binding_legacy_requests.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac"
    frozen = json.loads(path.read_text())
    graph = frozen["graph"]; job = SimpleNamespace(**graph["job"])
    actual = TextGenerationRequest("mock", "mock-writer", "Golden graph prompt: 夜色。",
        parameters=TextGenerationParameters(temperature=0.0, max_output_tokens=256),
        metadata={"purpose":"creative_graph_model"}, job_id=job.id)
    assert request_payload(actual) == graph["payload"]
    assert graph_request_payload_digest(job, request_payload(actual), True) == graph["expected_digest"] == "c4543d9eb1914c395d38e08088642f407a20fec9c2345d6d01c039972ddf280c"
    screenplay = frozen["screenplay"]; job = SimpleNamespace(**screenplay["job"], cancelled=Event())
    actual = build_author_request(job, SimpleNamespace(provider="mock",model="mock-writer"), {"content":job.source}, {})
    assert request_payload(actual) == screenplay["payload"]
    assert request_digest(actual, job, False) == screenplay["expected_digest"] == "103b4c3fb49325ec39c4dca51e08ecb216e6ee76cdf6407f8715d2a0a9b0fe48"


@pytest.fixture
def source(tmp_path):
    from app.repository import FileRepository
    from app.repositories.file.novel import FileNovelRepository
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    novels = FileNovelRepository(FileRepository(tmp_path))
    novels.create({"id":"independent", "title":"Independent source fixture"})
    raw = ExperimentalStore(tmp_path, "file", "")
    documents = CreativeService(raw, novels, Forbidden())
    scope = {"mode":"local", "novel_id":"independent"}
    value = {"mode":"STORYBOARD", "title":"Saved storyboard", "source_independent":True,
        "scenes":[{"id":"scene-1", "sequence":1, "heading":"INT. ROOM"}],
        "shots":[{"id":"shot-1", "number":1, "scene_id":"scene-1", "action":"A visitor waits."}]}
    row = documents.create("independent", scope, "actor", value)
    binding = dict(binding_values(), project_incarnation=row["project_incarnation"],
        source_document_id=row["id"], source_version=row["version"], source_digest=documents.document_digest(row))
    return SimpleNamespace(root=tmp_path, raw=raw, documents=documents, scope=scope, row=row, binding=binding, value=value)


def validate(e, **changes):
    return validate_creative_director_source(e.documents, changes.pop("binding", e.binding),
        actor_id=changes.pop("actor_id", "actor"), scope=changes.pop("scope", e.scope), **changes)


def test_actual_saved_independent_source_uses_original_validation_without_chapter_reads(source, monkeypatch):
    e = source; before = e.raw.path("independent", e.scope).read_bytes(); calls = []
    original = e.documents.assert_current
    def checked(*args, **kwargs):
        calls.append(True); return original(*args, **kwargs)
    monkeypatch.setattr(e.documents, "assert_current", checked)
    result = validate(e)
    assert result == e.row and calls == [True]
    result["shots"][0]["action"] = "Detached change"
    assert validate(e) == e.row and e.raw.path("independent", e.scope).read_bytes() == before


@pytest.mark.parametrize("changes", [
    {"source_independent":False}, {"source_chapter_ids":["never-read"]},
    {"source_evidence":{"never-read":{}}}, {"source_documents":{"never-read":{}}},
    {"source_privacy":{"never-read":"LOCAL_ONLY"}}, {"source_privacy":None},
    {"mode":"SCREENPLAY"}, {"source_independent":1},
])
def test_ineligible_sources_fail_before_any_chapter_or_ancestry_read(source, changes):
    e = source
    with e.raw.transaction("independent", e.scope) as state:
        state["collections"][e.documents.COLLECTION][e.row["id"]].update(changes)
    before = e.raw.path("independent", e.scope).read_bytes()
    with pytest.raises(ValueError, match="INDEPENDENT_STORYBOARD_REQUIRED"): validate(e)
    assert e.raw.path("independent", e.scope).read_bytes() == before


@pytest.mark.parametrize("field,value", [("source_version",2), ("source_digest","f"*64),
    ("project_incarnation","file:33333333-3333-4333-8333-333333333333")])
def test_saved_source_identity_is_exact(source, field, value):
    with pytest.raises(ValueError): validate(source, binding=dict(source.binding, **{field:value}))


def test_scope_and_actor_mismatch_are_not_source_authority(source):
    with pytest.raises(ValueError): validate(source, actor_id="other")
    with pytest.raises(ValueError): validate(source, scope={"mode":"local", "novel_id":"other"})


def test_missing_marker_and_missing_source_never_provision_or_write(source):
    e = source; path = e.raw.path("independent", e.scope); before = path.read_bytes()
    marker = e.root / "novels/independent/creative_project_v2.json"; marker.unlink()
    with pytest.raises(ValueError, match="SOURCE_OWNER_CHANGED"): validate(e)
    assert not marker.exists() and path.read_bytes() == before
    path.unlink()
    with pytest.raises(ValueError, match="INDEPENDENT_STORYBOARD_REQUIRED"): validate(e)
    assert not path.exists() and not marker.exists()


def test_original_owner_or_scope_nesting_is_rejected(source):
    e = source
    with e.documents.store.owner_lease("independent"):
        with pytest.raises(ValueError, match="LOCK_ORDER_INVALID"): validate(e)
    with e.raw.transaction("independent", e.scope):
        with pytest.raises(ValueError, match="nested experimental transaction"): validate(e)


def test_original_validation_cannot_mutate_the_scope_snapshot(source, monkeypatch):
    e = source; path = e.raw.path("independent", e.scope); before = path.read_bytes()
    original = e.documents.get
    def mutate(*args):
        active = e.raw._local.active[e.raw.key("independent", e.scope)]
        active["collections"][e.documents.COLLECTION][e.row["id"]]["title"] = "Forbidden mutation"
        return original(*args)
    monkeypatch.setattr(e.documents, "get", mutate)
    with pytest.raises(ValueError, match="MUTATION_DENIED"): validate(e)
    assert path.read_bytes() == before


def test_current_source_edit_serializes_on_original_scope_owner(source, monkeypatch):
    e = source; reading, release, editing, edited = Event(), Event(), Event(), Event()
    original = e.documents.get
    def held_get(*args):
        reading.set(); assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(e.documents, "get", held_get)
    def edit():
        editing.set()
        result = e.documents.update("independent", e.scope, "actor", e.row["id"], e.row["version"],
                                    dict(e.value, title="Actual later edit"))
        edited.set(); return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        validation = pool.submit(validate, e)
        try:
            assert reading.wait(5)
            update = pool.submit(edit); assert editing.wait(5)
            assert not edited.wait(.15), "source edit escaped original scope lock"
        finally:
            release.set()
        assert validation.result(timeout=5) == e.row
        assert update.result(timeout=5)["version"] == e.row["version"] + 1
    with pytest.raises(ValueError, match="SOURCE_CHANGED"): validate(e)
