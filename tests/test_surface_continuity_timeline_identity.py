"""Original Timeline owner contracts on File and the opted-in real PostgreSQL.

No synthetic Session stands in for UUID/FK behavior. PostgreSQL cases use the
unchanged mounted fixture and backend markers, and remain skipped locally.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from uuid import UUID, uuid4

import pytest

from app.lore.continuity import TimelineEvent
from test_r3_mounted_contracts import mounted, prefix


real_postgres = pytest.mark.parametrize("mounted", [
    pytest.param("postgres", marks=pytest.mark.postgres_backend_only),
], indirect=True)


def event(e, identity="time", **extra):
    return {**TimelineEvent(id=identity, project_id=e.nid, event_type="SCENE",
                           title="Clock", start_time="day-3", end_time="day-1",
                           evidence_ids=["clock-" + e.nid]).model_dump(mode="json"), **extra}


def physical_novel(e, slug=None):
    with e.bundle.continuity.session_factory() as conn:
        return conn.execute("SELECT id FROM novels WHERE slug=%s", (slug or e.nid,)).fetchone()[0]


def raw_insert(e, payload, *, storage_id=None, novel_id=None, project_id=None, details=None):
    with e.bundle.continuity.session_factory() as conn:
        conn.execute(
            "INSERT INTO timeline_events (id,novel_id,project_id,payload,event_time,sequence,title,details) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (storage_id or uuid4(), novel_id or physical_novel(e),
             project_id or payload["project_id"], json.dumps(payload), "day-3", 0,
             "Original stored clock", json.dumps(details or {})),
        )
        conn.commit()


@pytest.mark.parametrize("identity", ["time", "opaque:时钟/one", "00000000-0000-0000-0000-000000000123"])
def test_public_identity_slug_fk_append_only_restart_and_list(mounted, identity):
    e = mounted; repo = e.bundle.continuity; payload = event(e, identity)
    assert repo.create("timeline", payload) == payload
    assert repo.get_by_id("timeline", identity) == payload
    assert repo.create("timeline", {**payload, "title": "Must not overwrite", "evidence_ids": []}) == payload
    assert repo.list_by_project("timeline", e.nid) == [payload]
    assert repo.list_by_evidence("timeline", payload["evidence_ids"][0]) == [payload]
    if e.backend == "postgres":
        restarted = type(repo)(repo.session_factory)
        with repo.session_factory() as conn:
            stored = conn.execute("SELECT t.id,t.novel_id,n.slug,t.payload,t.details FROM timeline_events t "
                                  "JOIN novels n ON n.id=t.novel_id WHERE t.project_id=%s", (e.nid,)).fetchone()
        assert isinstance(stored[0], UUID) and stored[1] == physical_novel(e)
        assert stored[2] == e.nid and stored[3] == payload and stored[4]["_source_id"] == identity
        # The original Story Timeline serializer sees the exact public identity.
        assert e.novels.data_set(e.nid, "timeline")[0]["id"] == identity
        if identity.startswith("00000000"):
            assert stored[0] == UUID(identity)
    else:
        restarted = type(repo)(repo.root)
    assert restarted.get_by_id("timeline", identity) == payload
    for other in ["z-last", "a-first"]:
        repo.create("timeline", event(e, other))
    assert [row["id"] for row in restarted.list_by_project("timeline", e.nid)] == sorted([identity, "z-last", "a-first"])
    with pytest.raises(KeyError):
        restarted.get_by_id("timeline", "missing-id")


def test_foreign_project_and_explicit_mismatched_novel_cannot_rebind(mounted):
    e = mounted; repo = e.bundle.continuity; payload = event(e)
    repo.create("timeline", payload)
    other = e.novels.create({"id": "timeline-other-" + uuid4().hex, "title": "Other"})["id"]
    try:
        with pytest.raises(ValueError, match="TIMELINE_PROJECT_MISMATCH"):
            repo.create("timeline", {**payload, "project_id": other, "title": "Foreign"})
        mismatches = [other, "not-a-novel", None]
        if e.backend == "postgres":
            mismatches.append(str(physical_novel(e, other)))
        for explicit in mismatches:
            with pytest.raises(ValueError, match="TIMELINE_PROJECT_MISMATCH"):
                repo.create("timeline", event(e, "foreign-target", novel_id=explicit))
        assert repo.list_by_project("timeline", other) == []
        assert repo.list_by_project("timeline", e.nid) == [payload]
        assert repo.get_by_id("timeline", payload["id"]) == payload
    finally:
        e.novels.delete(other)


def test_missing_project_cannot_create_or_reuse_existing_identity(mounted):
    e = mounted; repo = e.bundle.continuity; payload = event(e)
    repo.create("timeline", payload)
    for identity in [payload["id"], "never-created"]:
        with pytest.raises(FileNotFoundError):
            repo.create("timeline", event(e, identity, project_id="absent-" + uuid4().hex))
    assert repo.list_by_project("timeline", e.nid) == [payload]


def test_matching_explicit_owner_and_concurrent_idempotence(mounted):
    e = mounted; repo = e.bundle.continuity; payload = event(e, novel_id=e.nid)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: repo.create("timeline", deepcopy(payload)), range(2)))
    assert results == [payload, payload]
    assert repo.list_by_project("timeline", e.nid) == [payload]


def test_ambiguous_public_identity_fails_closed_without_rewrite(mounted):
    e = mounted; repo = e.bundle.continuity; payload = event(e)
    repo.create("timeline", payload)
    if e.backend == "postgres":
        raw_insert(e, payload, details={"_source_id": payload["id"]})
    else:
        repo._write("timeline", [payload, {**payload, "title": "Conflicting alias"}])
    for action in [lambda: repo.get_by_id("timeline", payload["id"]),
                   lambda: repo.list_by_project("timeline", e.nid),
                   lambda: repo.list_by_evidence("timeline", payload["evidence_ids"][0]),
                   lambda: repo.create("timeline", payload)]:
        with pytest.raises(ValueError, match="TIMELINE_IDENTITY_CONFLICT"):
            action()
    if e.backend == "postgres":
        with repo.session_factory() as conn:
            assert conn.execute("SELECT count(*) FROM timeline_events WHERE project_id=%s", (e.nid,)).fetchone()[0] == 2
    else:
        assert len(repo._read("timeline")) == 2


@real_postgres
def test_legacy_uuid_rows_and_explicit_physical_owner_remain_addressable(mounted):
    e = mounted; repo = e.bundle.continuity
    payload = event(e, str(uuid4()), novel_id=str(physical_novel(e)))
    raw_insert(e, payload, storage_id=UUID(payload["id"]))
    assert repo.get_by_id("timeline", payload["id"]) == payload
    assert repo.create("timeline", {**payload, "title": "No rewrite"}) == payload
    assert repo.list_by_project("timeline", e.nid) == [payload]
    added = event(e, "explicit-physical", novel_id=str(physical_novel(e)))
    assert repo.create("timeline", added) == added


@real_postgres
def test_storage_uuid_collision_and_source_alias_cannot_rebind(mounted):
    e = mounted; repo = e.bundle.continuity; payload = event(e)
    repo.create("timeline", payload)
    with repo.session_factory() as conn:
        key = conn.execute("SELECT id FROM timeline_events WHERE project_id=%s", (e.nid,)).fetchone()[0]
    for action in [lambda: repo.get_by_id("timeline", str(key)),
                   lambda: repo.create("timeline", event(e, str(key)))]:
        with pytest.raises(ValueError, match="TIMELINE_IDENTITY_CONFLICT"):
            action()
    # An existing original-owner Story row must not be adopted or overwritten.
    e.novels.upsert_timeline_event(e.nid, "story-only", {"title": "Story-owned"})
    with pytest.raises(ValueError, match="TIMELINE_IDENTITY_CONFLICT"):
        repo.create("timeline", event(e, "story-only"))
    assert repo.list_by_project("timeline", e.nid) == [payload]
    assert repo.get_by_id("timeline", payload["id"]) == payload
    # Conversely an opaque ID cannot adopt a UUID-identified legacy row at its key.
    opaque = "collision-" + uuid4().hex
    key = repo._timeline_storage_id(opaque)
    legacy = event(e, str(key))
    raw_insert(e, legacy, storage_id=key)
    with pytest.raises(ValueError, match="TIMELINE_IDENTITY_CONFLICT"):
        repo.create("timeline", event(e, opaque))
    assert repo.get_by_id("timeline", legacy["id"]) == legacy


@real_postgres
def test_mismatched_physical_scope_and_details_alias_are_never_returned(mounted):
    e = mounted; repo = e.bundle.continuity; payload = event(e)
    other = e.novels.create({"id": "timeline-other-" + uuid4().hex, "title": "Other"})["id"]
    try:
        raw_insert(e, payload, novel_id=physical_novel(e, other))
        for action in [lambda: repo.get_by_id("timeline", payload["id"]),
                       lambda: repo.list_by_project("timeline", e.nid),
                       lambda: repo.list_by_project("timeline", other),
                       lambda: repo.list_by_evidence("timeline", payload["evidence_ids"][0]),
                       lambda: repo.create("timeline", payload)]:
            with pytest.raises(ValueError, match="TIMELINE_PROJECT_MISMATCH"):
                action()
    finally:
        e.novels.delete(other)
    raw_insert(e, payload, details={"_source_id": "another-public-id"})
    for identity in [payload["id"], "another-public-id"]:
        with pytest.raises(ValueError, match="TIMELINE_IDENTITY_CONFLICT"):
            repo.get_by_id("timeline", identity)
    with pytest.raises(ValueError, match="TIMELINE_IDENTITY_CONFLICT"):
        repo.create("timeline", payload)


@real_postgres
def test_uuid_shaped_project_slug_is_not_a_physical_owner_alias(mounted):
    e = mounted; repo = e.bundle.continuity
    alias = str(physical_novel(e))
    other = e.novels.create({"id": alias, "title": "UUID-shaped public slug"})["id"]
    try:
        payload = event(e, "uuid-slug-event", project_id=other)
        assert repo.create("timeline", payload) == payload
        with repo.session_factory() as conn:
            actual = conn.execute("SELECT novel_id FROM timeline_events WHERE project_id=%s", (other,)).fetchone()[0]
        assert actual == physical_novel(e, other) and actual != physical_novel(e)
        # The explicit alias simultaneously names two novels. Never guess.
        with pytest.raises(ValueError, match="TIMELINE_PROJECT_MISMATCH"):
            repo.create("timeline", event(e, "ambiguous-novel", novel_id=alias))
        assert repo.list_by_project("timeline", e.nid) == []
        assert repo.list_by_project("timeline", other) == [payload]
    finally:
        e.novels.delete(other)


@real_postgres
def test_uuid_spellings_cannot_claim_an_existing_public_identity(mounted):
    e = mounted; repo = e.bundle.continuity
    identity = "A" + str(uuid4())[1:].upper()
    payload = event(e, identity)
    assert repo.create("timeline", payload) == payload
    for alias in [identity.lower(), "{" + identity + "}"]:
        for action in [lambda: repo.get_by_id("timeline", alias),
                       lambda: repo.create("timeline", event(e, alias))]:
            with pytest.raises(ValueError, match="TIMELINE_IDENTITY_CONFLICT"):
                action()
    assert repo.get_by_id("timeline", identity) == payload
    assert repo.list_by_project("timeline", e.nid) == [payload]


@real_postgres
def test_legacy_physical_uuid_project_metadata_is_not_rebound(mounted):
    e = mounted; repo = e.bundle.continuity; owner = physical_novel(e)
    # The old adapter could persist the FK UUID as project_id. This is not the
    # project's public slug, even though the physical foreign key is valid.
    payload = event(e, str(uuid4()), project_id=str(owner))
    raw_insert(e, payload, storage_id=UUID(payload["id"]), novel_id=owner)
    for action in [lambda: repo.get_by_id("timeline", payload["id"]),
                   lambda: repo.list_by_project("timeline", e.nid),
                   lambda: repo.list_by_project("timeline", str(owner)),
                   lambda: repo.list_by_evidence("timeline", payload["evidence_ids"][0]),
                   lambda: repo.create("timeline", {**payload, "project_id": e.nid})]:
        with pytest.raises(ValueError, match="TIMELINE_PROJECT_MISMATCH"):
            action()
    with pytest.raises(FileNotFoundError):
        repo.create("timeline", payload)
    with repo.session_factory() as conn:
        stored = conn.execute("SELECT novel_id,project_id,payload,details FROM timeline_events WHERE id=%s",
                              (UUID(payload["id"]),)).fetchone()
    assert stored == (owner, str(owner), payload, {})
