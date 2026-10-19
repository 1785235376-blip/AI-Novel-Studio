"""Independent AN-AUDIT-01/02/03 checks using synthetic canaries only."""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.context import build_context_from_sources
from app.privacy import cloud_safe_context, merge_privacy
from app.repositories.file.novel import FileNovelRepository
from app.repositories.postgres import novel as pg
from app.repositories.postgres.serialization import serialize_canon, serialize_foreshadowing, serialize_timeline
from app.repository import FileRepository


@pytest.mark.parametrize("policy", ["LOCAL_ONLY", "REDACT_BEFORE_CLOUD"])
def test_timeline_strict_policy_is_always_serialized(policy):
    record = SimpleNamespace(id="event", sequence=1, event_time="now", title="PRIVATE_CANARY", privacy=policy, details={})
    serialized = serialize_timeline(record)
    assert serialized["privacy_level"] == policy
    assert "PRIVATE_CANARY" not in json.dumps(cloud_safe_context([serialized])[0])


@pytest.mark.parametrize("policy", ["LOCAL_ONLY", "REDACT_BEFORE_CLOUD"])
def test_foreshadowing_details_are_persistent_policy_authority(policy):
    record = SimpleNamespace(id="hint", title="PRIVATE_CANARY", status="OPEN", planted_chapter=1, target_chapter=None, details={"privacy_level": policy})
    serialized = serialize_foreshadowing(record)
    assert serialized["privacy_level"] == policy
    assert "PRIVATE_CANARY" not in json.dumps(cloud_safe_context([serialized])[0])


@pytest.mark.parametrize("column,json_policy,expected", [
    ("LOCAL_ONLY", "CLOUD_ALLOWED", "LOCAL_ONLY"),
    ("REDACT_BEFORE_CLOUD", "CLOUD_ALLOWED", "REDACT_BEFORE_CLOUD"),
    ("CLOUD_ALLOWED", "LOCAL_ONLY", "LOCAL_ONLY"),
    ("CLOUD_ALLOWED", "invalid", "LOCAL_ONLY"),
])
def test_canon_policy_conflict_is_stricter_wins(column, json_policy, expected):
    record = SimpleNamespace(id="fact", source="test", privacy=column, fact_value={"fact":"PRIVATE_CANARY", "privacy_level": json_policy})
    serialized = serialize_canon(record)
    assert serialized["privacy_level"] == expected
    assert "PRIVATE_CANARY" not in json.dumps(cloud_safe_context([serialized])[0])


@pytest.mark.parametrize("policy", [None, "", "cloud_allowed", "UNKNOWN", {}, []])
def test_unknown_or_invalid_policy_cannot_send(policy):
    assert cloud_safe_context([{"id":"unknown", "text":"PRIVATE_CANARY", "privacy_level":policy}]) == ([], ["unknown"])
    assert merge_privacy("CLOUD_ALLOWED", policy) == "LOCAL_ONLY"


def test_legacy_foreshadowing_marks_unknown_for_review():
    record = SimpleNamespace(id="hint", title="PRIVATE_CANARY", status="OPEN", planted_chapter=1, target_chapter=None, details={})
    result = serialize_foreshadowing(record)
    assert result["privacy_level"] == "LOCAL_ONLY"
    assert result["privacy_status"] == "UNKNOWN"


@pytest.mark.parametrize("method,title", [("upsert_character", {"name":"Item"}), ("upsert_location", {"name":"Item"}), ("upsert_timeline_event", {"title":"Item"}), ("upsert_foreshadowing", {"title":"Item"})])
@pytest.mark.parametrize("policy", ["LOCAL_ONLY", "REDACT_BEFORE_CLOUD"])
def test_file_update_omitting_policy_preserves_it_across_reopen(tmp_path, method, title, policy):
    repo = FileNovelRepository(FileRepository(tmp_path))
    repo.create({"id":"privacy", "title":"Privacy test"})
    getattr(repo, method)("privacy", "item", {**title, "privacy_level":policy})
    reopened = FileNovelRepository(FileRepository(tmp_path))
    assert getattr(reopened, method)("privacy", "item", title)["privacy_level"] == policy


@pytest.mark.parametrize("method,title", [("upsert_timeline_event", {"title":"PRIVATE_CANARY"}), ("upsert_foreshadowing", {"title":"PRIVATE_CANARY"})])
@pytest.mark.parametrize("policy", ["LOCAL_ONLY", "REDACT_BEFORE_CLOUD"])
def test_postgres_write_then_fresh_serialization_and_omitted_update(monkeypatch, method, title, policy):
    rows = {}
    class Session:
        def get(self, kind, key): return rows.get((kind, key))
        def scalar(self, _query): return None
        def add(self, record): rows[(type(record), record.id)] = record
        def flush(self): pass
    class Database:
        @contextmanager
        def session(self): yield Session()
    monkeypatch.setattr(pg, "novel_or_raise", lambda *_: SimpleNamespace(id=uuid.UUID(int=1), slug="privacy"))
    repo = pg.PostgresNovelRepository(Database())
    result = getattr(repo, method)("privacy", "item", {**title,"privacy_level":policy})
    assert result["privacy_level"] == policy
    result = getattr(pg.PostgresNovelRepository(Database()), method)("privacy", "item", title)
    assert result["privacy_level"] == policy
    record = next(iter(rows.values()))
    serialized = (serialize_timeline if method == "upsert_timeline_event" else serialize_foreshadowing)(record)
    assert "PRIVATE_CANARY" not in json.dumps(cloud_safe_context([serialized])[0])


def test_legacy_cloud_context_filters_every_private_dataset():
    secret = {"id":"hidden", "name":"Hero", "title":"PRIVATE_CANARY", "description":"PRIVATE_CANARY", "privacy_level":"LOCAL_ONLY", "status":"OPEN"}
    sources = {"novel":{"title":"test", "long_term_summary":"PRIVATE_CANARY"}, "characters":[secret], "locations":[secret],
               "secrets":[secret], "foreshadowing":[secret], "story_state":{"active_characters":["hidden"], "prose":"PRIVATE_CANARY"},
               "summaries":[{"summary":"PRIVATE_CANARY"}], "style_profile":{"sample":"PRIVATE_CANARY"}}
    assert "PRIVATE_CANARY" in json.dumps(build_context_from_sources(sources,"n",1,"Write",False))
    assert "PRIVATE_CANARY" not in json.dumps(build_context_from_sources(sources,"n",1,"Write",True))


def test_redaction_cannot_echo_arbitrary_extra_fields_or_identifiers():
    result, _ = cloud_safe_context([{"id":"PRIVATE_CANARY", "type":"PRIVATE_CANARY", "name":"PRIVATE_CANARY", "nested":{"text":"PRIVATE_CANARY"}, "privacy_level":"REDACT_BEFORE_CLOUD"}])
    assert "PRIVATE_CANARY" not in json.dumps(result)


def test_allowed_parent_cannot_unmask_nested_private_or_redacted_records():
    entry={"id":"public","privacy_level":"CLOUD_ALLOWED", "text":"approved", "children":[
        {"privacy_level":"LOCAL_ONLY","text":"PRIVATE_CANARY"},
        {"privacy_level":"REDACT_BEFORE_CLOUD","text":"PRIVATE_CANARY"},
        {"privacy_level":"UNKNOWN","text":"PRIVATE_CANARY"},
    ]}
    safe,_=cloud_safe_context([entry])
    assert safe[0]["text"]=="approved"
    assert "PRIVATE_CANARY" not in json.dumps(safe)
    assert entry["children"][0]["text"]=="PRIVATE_CANARY"


def test_file_unknown_historical_foreshadowing_is_explicitly_reviewable(tmp_path):
    backend=FileRepository(tmp_path);backend.create_novel({"id":"legacy","title":"Legacy"})
    (backend.novels/"legacy/foreshadowing.json").write_text('[{"id":"hint","title":"old"}]')
    result=FileNovelRepository(backend).get_data_set("legacy","foreshadowing")[0]
    assert result["privacy_level"]=="LOCAL_ONLY" and result["privacy_status"]=="UNKNOWN"


@pytest.mark.parametrize("policy", ["LOCAL_ONLY", "REDACT_BEFORE_CLOUD", None, "INVALID"])
def test_lore_derived_memory_with_restricted_evidence_never_reaches_cloud(policy):
    from app.lore.context_view import LoreContextBuilder
    memory={"id":"memory","character_id":"hero","proposal_id":"proposal","content":{"text":"PRIVATE_CANARY"},"valid_from_chapter":1,"memory_type":"EXPERIENCE"}
    evidence={"id":"evidence","privacy":policy,"source_type":"CHAPTER_VERSION"}
    repo=SimpleNamespace(list_memories=lambda *_:[memory],get_proposal=lambda *_:{},list_proposal_evidence=lambda *_:[{"evidence_id":"evidence"}],get_evidence=lambda *_:evidence,get_latest_snapshot=lambda *_:None)
    result=LoreContextBuilder(SimpleNamespace(repository=repo)).build({"novel_id":"n","characters":[{"id":"hero","name":"Hero"}]},1,True)
    assert "PRIVATE_CANARY" not in result.lore_memory.model_dump_json()
    assert result.privacy_decisions[0]["memory_id"]=="memory"
    assert result.privacy_decisions[0]["decision"].startswith("OMITTED_")


@pytest.mark.parametrize("privacy", ["LOCAL_ONLY", "REDACT_BEFORE_CLOUD", "UNKNOWN", None])
def test_narrative_projection_filters_sources_before_losing_policy(privacy):
    from app.narrative_context import NarrativeContextBuilder
    records={"threads":[{"id":"thread","title":"PRIVATE_CANARY","status":"OPEN","privacy_level":privacy}],
             "events":[{"id":"event","subject_id":"public","event_type":"ADVANCED","chapter_version_id":"n:1:v1","payload":{"summary":"PRIVATE_CANARY"},"privacy_level":privacy}],
             "findings":[{"id":"finding","finding_type":"OVERDUE","status":"OPEN","description":"PRIVATE_CANARY","privacy_level":privacy}]}
    records["threads"].append({"id":"public","title":"Approved public title","status":"OPEN","privacy_level":"CLOUD_ALLOWED"})
    builder=NarrativeContextBuilder(SimpleNamespace(list=lambda _,kind:records.get(kind,[])))
    assert "PRIVATE_CANARY" in builder.build("n","n:1",1).model_dump_json()
    cloud=builder.build("n","n:1",1,cloud=True).model_dump_json()
    assert "PRIVATE_CANARY" not in cloud
    assert "Approved public title" in cloud


def test_narrative_cannot_leak_via_actual_author_prompt(monkeypatch):
    from app.services.context_service import ContextService
    from app.jobs import Job, JobManager
    from app.router import Route
    import app.jobs as module
    narratives=SimpleNamespace(list=lambda _,kind:[{"id":"private","title":"PRIVATE_CANARY","status":"OPEN","privacy_level":"LOCAL_ONLY"}] if kind=="threads" else [])
    novels=SimpleNamespace(get_context_sources=lambda _:{"novel":{"id":"n","title":"Test"}})
    chapters=SimpleNamespace(get=lambda _:{"id":"n:1","version":1,"number":1,"novel_id":"n","content":"Approved source","privacy_level":"CLOUD_ALLOWED"})
    context=ContextService(novels,chapters,narrative_repository=narratives,enable_narrative_context=True,enable_lore_context=False)
    dispatched=[]
    class Node:
        def stream(self, item):
            dispatched.append(item.request.prompt)
            return iter(())
    fake_runtime=SimpleNamespace(is_remote_text_provider=lambda _:True,router=lambda *_:SimpleNamespace(routes={"writer":[Route("external","test")]}),packaged_author_route_ready=lambda _:True,prepare_text_route=lambda *_:Node())
    monkeypatch.setattr(module,"runtime",fake_runtime)
    monkeypatch.setattr(module,"runtime_log",SimpleNamespace(write=lambda **_:None))
    manager=JobManager.__new__(JobManager)
    manager.chapters=chapters;manager.contexts=context;manager.snapshot_required=False;manager._emit=lambda *_:None
    from app.source_privacy import review_source_privacy, content_digest
    approved=chapters.get("n:1")
    review_source_privacy(approved,None,"synthetic-test","CLOUD_ALLOWED",1,content_digest(approved))
    job=Job("audit","continue","n","n:1","Continue","QUALITY",requested_provider="external",requested_model="test")
    manager._run(job)
    assert len(dispatched)==1,job.error
    assert "PRIVATE_CANARY" not in dispatched[0]


def test_alternate_postgres_canon_repository_read_uses_stricter_policy():
    from app.repositories.postgres.canon import PostgresCanonRepository
    row=SimpleNamespace(id=uuid.uuid4(),source="test",privacy="CLOUD_ALLOWED",fact_value={"fact":"PRIVATE_CANARY","privacy_level":"LOCAL_ONLY"})
    class Session:
        def scalar(self,_):return SimpleNamespace(id=uuid.uuid4())
        def scalars(self,_):return SimpleNamespace(all=lambda:[row])
    class Database:
        @contextmanager
        def session(self):yield Session()
    result=PostgresCanonRepository(Database()).list("n")
    assert result[0]["privacy_level"]=="LOCAL_ONLY"
    assert "PRIVATE_CANARY" not in json.dumps(cloud_safe_context(result)[0])


def test_file_canon_approval_without_policy_is_local_and_reviewable(tmp_path):
    from app.repositories.file.canon import FileCanonRepository
    backend=FileRepository(tmp_path);backend.create_novel({"id":"n","title":"Test"})
    canon=FileCanonRepository(backend)
    canon.save_pending({"id":"pending","novel_id":"n","proposals":[{"fact":"PRIVATE_CANARY"}]})
    canon.approve("pending")
    result=canon.list("n")
    assert result[0]["privacy_level"]=="LOCAL_ONLY" and result[0]["privacy_status"]=="UNKNOWN"
