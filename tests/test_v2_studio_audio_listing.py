"""Additive original-owner audio listing checks; no provider/model execution."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.audio_production_store import AudioProductionStore
from app.services.audiobook_service import AudiobookError, AudiobookService
from app.services.studio_audio_execution import StudioAudioExecution
from test_v2_independent_workspace import rig


def make_owner(root, actor="author", branch="branch-a", assets=None):
    store = AudioProductionStore(root).for_branch(branch).for_actor(actor)
    return StudioAudioExecution(AudiobookService(store, assets, branch_id=branch))


def binding(actor="author", **changes):
    return {"actor": actor, "scope_key": "a" * 64, "incarnation": "file:" + str(uuid4()),
            "request_id": "request-one", "operation_id": "m8.audio.speech", "request_digest": "b" * 64,
            "sources": [], "rights": {"license_note": "Synthetic local fixture"},
            "provider_binding": {"provider_id": "fixture", "model_id": "fixture-tts", "endpoint": "http://127.0.0.1:9",
                                 "local": True, "capability": "TTS", "route_digest": "c" * 64}, **changes}


def queued(owner, context, nid="project", sources=()):
    context = {**context, "sources": deepcopy(list(sources))}
    return owner.queue(nid, {"operation_id": "m8.audio.speech", "provider_id": "fixture", "model_id": "fixture-tts",
                           "prompt": "Local receipt fixture: 青", "source_snapshots": deepcopy(list(sources))},
                       context, lambda: None, lambda snapshot: snapshot)


@pytest.fixture
def audio(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    owner = make_owner(tmp_path)
    context = binding()
    row = queued(owner, context)
    return SimpleNamespace(owner=owner, context=context, row=row, nid="project")


def save_rows(audio, rows):
    state = audio.owner.store._load(audio.nid)
    state["jobs"] = rows
    audio.owner.store.save(audio.nid, state, include_studio=True)


def history(audio, count):
    rows = [{**deepcopy(audio.row), "id": f"audio-{index:05d}"} for index in range(count)]
    save_rows(audio, rows)
    return rows


def listed(audio, guard=lambda: None):
    return audio.owner.list(audio.nid, audio.context, guard)


def assert_error(code, operation, status=409):
    with pytest.raises(AudiobookError) as caught:
        operation()
    assert (caught.value.code, caught.value.status) == (code, status)


def test_list_reads_one_real_snapshot_with_linear_job_visits(audio, monkeypatch):
    expected = history(audio, 180)
    events = SimpleNamespace(loads=0, visits=0)
    original = audio.owner.store.load

    class ObservedJobs(list):
        def __iter__(self):
            for row in super().__iter__():
                events.visits += 1
                yield row

    def observed(*args, **kwargs):
        events.loads += 1
        state = original(*args, **kwargs)
        state["jobs"] = ObservedJobs(state["jobs"])
        return state

    monkeypatch.setattr(audio.owner.store, "load", observed)
    assert listed(audio) == expected
    assert events.loads == 1
    assert events.visits <= 2 * len(expected), events.visits


def test_complete_history_and_deep_copy_are_preserved(audio):
    expected = history(audio, 601)
    result = listed(audio)
    assert result == expected
    result[-1]["context"]["rights"]["license_note"] = "Changed returned copy"
    assert listed(audio) == expected
    assert audio.owner.store.load(audio.nid)["jobs"] == []
    assert audio.owner.store.load(audio.nid, include_studio=True)["jobs"] == expected


@pytest.mark.parametrize("field,value,code", [
    ("_studio_body", {}, "STUDIO_AUDIO_OPERATION_UNSUPPORTED"),
    ("source_text", "Changed", "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("source_sha256", "d" * 64, "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("request_sha256", "d" * 64, "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("request_digest", "d" * 64, "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("branch_id", "another-branch", "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("chapter_id", "chapter", "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("operation_id", "m8.audio.music", "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("provider_id", "other-provider", "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("model_id", "other-model", "STUDIO_AUDIO_JOB_BINDING_CHANGED"),
    ("version", True, "STUDIO_AUDIO_VERSION_INVALID"),
    ("version", 0, "STUDIO_AUDIO_VERSION_INVALID"),
])
def test_malformed_tail_is_never_truncated_or_returned(audio, field, value, code):
    rows = history(audio, 601)
    rows[-1][field] = value
    save_rows(audio, rows)
    assert_error(code, lambda: listed(audio), 400 if code.endswith(("UNSUPPORTED", "VERSION_INVALID")) else 409)


@pytest.mark.parametrize("field", ["sources", "rights", "provider_binding"])
def test_binding_shape_at_tail_is_validated(audio, field):
    rows = history(audio, 3)
    rows[-1]["context"][field] = None
    save_rows(audio, rows)
    with pytest.raises(AudiobookError):
        listed(audio)


@pytest.mark.parametrize("change,code", [
    ("prompt", "STUDIO_AUDIO_PROMPT_INVALID"),
    ("sources", "STUDIO_AUDIO_SOURCE_INVALID"),
    ("binding_bytes", "STUDIO_AUDIO_BINDING_LIMIT"),
])
def test_original_per_receipt_limits_still_apply_to_tail(audio, change, code):
    rows = history(audio, 3)
    if change == "prompt":
        rows[-1]["_studio_body"]["prompt"] = "x" * 16_001
    elif change == "sources":
        rows[-1]["_studio_body"]["source_snapshots"] = [{}] * 9
    else:
        rows[-1]["context"]["rights"]["license_note"] = "x" * (256 * 1024)
    save_rows(audio, rows)
    assert_error(code, lambda: listed(audio), 400)


def test_graph_binding_at_tail_is_still_validated(audio):
    rows = history(audio, 3)
    rows[-1]["context"]["graph_binding"] = None
    save_rows(audio, rows)
    with pytest.raises(ValueError, match="^CREATIVE_GRAPH_MEDIA_BINDING_INVALID$"):
        listed(audio)


def test_source_snapshot_binding_is_checked_without_refreshing_history(audio):
    source = {"id": "document", "version": 3, "digest": "d" * 64, "kind": "CREATIVE_DOCUMENT"}
    second = queued(audio.owner, {**audio.context, "request_id": "with-source"}, sources=[source])
    assert listed(audio) == [audio.row, second]
    second["context"]["sources"][0]["version"] += 1
    save_rows(audio, [audio.row, second])
    assert_error("STUDIO_AUDIO_SOURCE_BINDING_MISMATCH", lambda: listed(audio))


@pytest.mark.parametrize("field", ["actor", "scope_key", "incarnation"])
def test_other_owner_context_is_filtered_without_validating_private_body(audio, field):
    other = deepcopy(audio.row)
    other["id"] = "other"
    other["context"][field] = "other"
    other["_studio_body"] = {"private_invalid": True}
    save_rows(audio, [other, audio.row, deepcopy(other)])
    assert listed(audio) == [audio.row]


def test_non_studio_and_other_actor_rows_do_not_enter_listing(audio):
    legacy = {"id": "legacy", "status": "QUEUED"}
    foreign = {**deepcopy(audio.row), "id": "foreign", "owner_actor_id": "other", "_studio_body": {}}
    save_rows(audio, [legacy, foreign, audio.row])
    assert listed(audio) == [audio.row]
    assert audio.owner.store.load(audio.nid)["jobs"] == [legacy]


@pytest.mark.parametrize("acceptance", [False, True])
def test_original_feature_off_and_v1_visibility_are_preserved(audio, monkeypatch, acceptance):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2" if acceptance else "")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if acceptance else "")
    assert listed(audio) == []


def test_wrong_actor_cannot_read_store(audio, monkeypatch):
    monkeypatch.setattr(audio.owner.store, "load", lambda *a, **k: pytest.fail("unauthorized read"))
    assert_error("STUDIO_AUDIO_ACTOR_STORE_REQUIRED",
                 lambda: audio.owner.list(audio.nid, {**audio.context, "actor": "other"}, lambda: None), 403)


def test_first_and_final_permission_checks_are_preserved(audio, monkeypatch):
    original = audio.owner.store.load
    events = []

    def read(*args, **kwargs):
        events.append("load")
        return original(*args, **kwargs)

    monkeypatch.setattr(audio.owner.store, "load", read)
    assert listed(audio, lambda: events.append("guard")) == [audio.row]
    assert events == ["guard", "load", "guard"]
    events.clear()

    def deny():
        raise PermissionError("Revoked")

    with pytest.raises(PermissionError, match="Revoked"):
        listed(audio, deny)
    assert events == []
    calls = 0

    def revoked_after_read():
        nonlocal calls
        calls += 1
        if calls == 2:
            deny()

    with pytest.raises(PermissionError, match="Revoked"):
        listed(audio, revoked_after_read)
    assert calls == 2 and events == ["load"]


@pytest.mark.parametrize("malformed", [False, True])
def test_duplicate_studio_ids_fail_closed_instead_of_shadowing_tail(audio, malformed):
    duplicate = deepcopy(audio.row)
    if malformed:
        duplicate["request_sha256"] = "d" * 64
    save_rows(audio, [audio.row, duplicate])
    before = audio.owner.store._path(audio.nid).read_bytes()
    assert_error("STUDIO_AUDIO_JOB_BINDING_CHANGED", lambda: listed(audio))
    assert audio.owner.store._path(audio.nid).read_bytes() == before


@pytest.mark.parametrize("foreign_kind", ["legacy", "actor", "scope"])
def test_foreign_first_duplicate_retains_not_found_denial(audio, foreign_kind):
    foreign = deepcopy(audio.row)
    if foreign_kind == "legacy":
        foreign.pop("studio_origin")
    elif foreign_kind == "actor":
        foreign["owner_actor_id"] = "other"
    else:
        foreign["context"]["scope_key"] = "other"
    save_rows(audio, [foreign, audio.row])
    assert_error("STUDIO_AUDIO_JOB_NOT_FOUND", lambda: listed(audio), 404)


def test_foreign_tail_and_unrelated_duplicates_stay_filtered(audio):
    foreign = {**deepcopy(audio.row), "owner_actor_id": "other", "_studio_body": {}}
    unrelated = {**deepcopy(foreign), "id": "unrelated"}
    save_rows(audio, [audio.row, foreign, unrelated, deepcopy(unrelated)])
    assert listed(audio) == [audio.row]


@pytest.mark.parametrize("job_id", [7, None, [], {"legacy": "id"}])
def test_legacy_non_string_unique_id_behavior_is_unchanged(audio, job_id):
    row = {**deepcopy(audio.row), "id": job_id}
    save_rows(audio, [row])
    assert listed(audio) == [row]


@pytest.mark.parametrize("job_id", [7, []])
def test_legacy_non_string_duplicate_studio_ids_still_fail_closed(audio, job_id):
    row = {**deepcopy(audio.row), "id": job_id}
    save_rows(audio, [row, deepcopy(row)])
    assert_error("STUDIO_AUDIO_JOB_BINDING_CHANGED", lambda: listed(audio))


def test_missing_id_keeps_original_lookup_failure_without_changing_foreign_only_view(audio):
    missing = {"status": "QUEUED"}
    save_rows(audio, [missing])
    assert listed(audio) == []
    save_rows(audio, [audio.row, missing])
    assert listed(audio) == [audio.row]
    save_rows(audio, [missing, audio.row])
    with pytest.raises(KeyError, match="id"):
        listed(audio)
    own_missing = deepcopy(audio.row)
    own_missing.pop("id")
    save_rows(audio, [own_missing])
    with pytest.raises(KeyError, match="id"):
        listed(audio)


def test_single_job_get_and_versioned_cancel_keep_original_contract(audio):
    assert audio.owner.get(audio.nid, audio.row["id"], audio.context, lambda: None) == audio.row
    assert_error("STUDIO_AUDIO_VERSION_CONFLICT", lambda: audio.owner.cancel(
        audio.nid, audio.row["id"], 2, audio.context, lambda: None))
    cancelled = audio.owner.cancel(audio.nid, audio.row["id"], 1, audio.context, lambda: None)
    assert cancelled["status"] == "CANCELLED" and cancelled["version"] == 2
    assert listed(audio) == [cancelled]
    assert_error("AUDIOBOOK_JOB_NOT_FOUND", lambda: audio.owner.get(audio.nid, "absent", audio.context, lambda: None), 404)


def test_reopened_audio_history_uses_real_file_and_postgres_project_incarnation(rig):
    context = binding(actor=rig.actor, scope_key=rig.service.store.key(rig.nid, rig.scope),
                      incarnation=rig.service.store.incarnation(rig.nid))
    assert context["incarnation"].startswith(rig.backend + ":")
    owner = make_owner(rig.root, rig.actor, None, rig.assets)
    row = queued(owner, context, rig.nid)
    reopened = make_owner(rig.root, rig.actor, None, rig.assets)
    assert reopened.list(rig.nid, context, lambda: None) == [row]
    assert reopened.list(rig.nid, {**context, "incarnation": "recreated"}, lambda: None) == []
    assert reopened.list(rig.nid, {**context, "scope_key": "different"}, lambda: None) == []
    assert reopened.list(rig.create_project("Other project"), context, lambda: None) == []
    assert make_owner(rig.root, rig.actor, "other", rig.assets).list(rig.nid, context, lambda: None) == []
    other = make_owner(rig.root, "other", None, rig.assets)
    assert other.list(rig.nid, {**context, "actor": "other"}, lambda: None) == []
    assert reopened.store.load(rig.nid)["jobs"] == []
    cancelled = reopened.cancel(rig.nid, row["id"], 1, context, lambda: None)
    assert reopened.list(rig.nid, context, lambda: None) == [cancelled]
    assert_error("STUDIO_AUDIO_VERSION_CONFLICT", lambda: owner.cancel(rig.nid, row["id"], 1, context, lambda: None))


def test_recreated_project_cannot_adopt_previous_incarnation_audio_receipts(rig):
    context = binding(actor=rig.actor, scope_key=rig.service.store.key(rig.nid, rig.scope),
                      incarnation=rig.service.store.incarnation(rig.nid))
    owner = make_owner(rig.root, rig.actor, None, rig.assets)
    row = queued(owner, context, rig.nid)
    rig.novels.delete(rig.nid)
    rig.create_project("Recreated project", nid=rig.nid)
    current = {**context, "incarnation": rig.service.store.incarnation(rig.nid)}
    assert current["incarnation"] != context["incarnation"]
    assert owner.list(rig.nid, current, lambda: None) == []
    assert owner.store.load(rig.nid, include_studio=True)["jobs"] == [row]
