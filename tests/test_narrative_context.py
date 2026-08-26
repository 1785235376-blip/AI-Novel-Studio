import json

import pytest

from app.agents import AgentRunner
from app.narrative_context import NarrativeContextBuilder
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService,ContextService,NovelService
from app.services import LoreService
from app.config import Settings
from app.storage import atomic_write


def fixture(repository,project="p"):
    rows={
        "threads":[{"id":"t","project_id":project,"title":"Thread","status":"OPEN","event_ids":[]}],
        "foreshadowing":[{"id":"f","project_id":project,"title":"Clue","status":"DEVELOPING"}],
        "mysteries":[{"id":"m","project_id":project,"title":"Who?","status":"OPEN"}],
        "character_goals":[{"id":"g","project_id":project,"character_id":"hero","title":"Escape","status":"ACTIVE"}],
        "events":[{"id":"event","project_id":project,"subject_id":"g","event_type":"CHARACTER_GOAL:ADVANCED","chapter_version_id":f"{project}:1:v1","payload":{"summary":"Moved"},"evidence_ids":["ev"]}],
        "chapter_links":[{"id":"link","project_id":project,"chapter_id":f"{project}:1","chapter_version":1,"entity_type":"MYSTERY","entity_id":"m","progress_type":"DEVELOPED","event_id":"other"}],
        "expectations":[{"id":"expect","project_id":project,"subject_id":"m","expectation_type":"MYSTERY_ANSWER_BY","deadline_chapter":2,"active":True,"evidence_ids":[]}],
        "findings":[{"id":"open","project_id":project,"finding_type":"MYSTERY_OVERDUE","subject_id":"m","description":"Overdue","severity":"MEDIUM","status":"OPEN","evidence_ids":[]},{"id":"resolved","project_id":project,"finding_type":"THREAD_STALE","subject_id":"t","description":"Old","status":"RESOLVED"}],
    }
    for kind,items in rows.items():
        for item in items:repository.create(project,kind,item)


@pytest.mark.file_backend_only
def test_narrative_context_is_deterministic_read_only_and_structured(tmp_path):
    repository=create_repository_bundle(data_root=tmp_path).narrative;fixture(repository);before=repository._read("p")
    builder=NarrativeContextBuilder(repository,800);views=[builder.build("p","p:1",1,["hero"]).model_dump(mode="json") for _ in range(3)]
    assert views[0]==views[1]==views[2]
    view=views[0];assert view["mysteries"][0]["selection_reason"]=="CURRENT_CHAPTER_LINK"
    assert view["character_goals"][0]["selection_reason"]=="CURRENT_CHARACTER_GOAL"
    assert view["character_goals"][0]["latest_progress"]["event_id"]=="event"
    assert [x["finding_id"] for x in view["findings"]]==["open"] and view["findings"][0]["advisory_only"] is True
    assert repository._read("p")==before


@pytest.mark.file_backend_only
def test_narrative_context_budget_truncation_is_deterministic(tmp_path):
    repository=create_repository_bundle(data_root=tmp_path).narrative;fixture(repository);builder=NarrativeContextBuilder(repository,45)
    first=builder.build("p","p:1",1,["hero"]).model_dump(mode="json");second=builder.build("p","p:1",1,["hero"]).model_dump(mode="json")
    assert first==second and first["truncated"] is True and first["estimated_tokens"]<=45


@pytest.mark.file_backend_only
def test_context_flag_disabled_is_exact_baseline_and_enabled_adds_projection(tmp_path):
    bundle=create_repository_bundle(data_root=tmp_path);novels=NovelService(bundle.novels,bundle.chapters);chapters=ChapterService(bundle.chapters);project=novels.create({"id":"context-project","title":"Context"})["id"];chapters.create(project,{"title":"One","content":"Text"});fixture(bundle.narrative,project)
    atomic_write(tmp_path/"novels"/project/"story_state.json",json.dumps({"volume":1,"chapter":1,"active_characters":["hero"]}))
    plain=ContextService(bundle.novels,bundle.chapters).build(project,1);disabled=ContextService(bundle.novels,bundle.chapters,narrative_repository=bundle.narrative,enable_narrative_context=False).build(project,1)
    assert disabled==plain and "narrative_context" not in disabled
    enabled=ContextService(bundle.novels,bundle.chapters,narrative_repository=bundle.narrative,enable_narrative_context=True).build(project,1)
    assert enabled["narrative_context"]["project_id"]==project


def test_narrative_context_is_writer_only():
    class Registry:
        def prompt(self,name):return name
    runner=AgentRunner(Registry());context={"chapter":1,"narrative_context":{"mysteries":[{"id":"m"}]}}
    assert "narrative_context" in runner.build_prompt("writer",context,"write")
    assert "narrative_context" not in runner.build_prompt("reviewer",context,"review")


@pytest.mark.file_backend_only
def test_narrative_context_flag_matrix_and_default(tmp_path):
    assert Settings().enable_narrative_context is False
    bundle=create_repository_bundle(data_root=tmp_path);project=NovelService(bundle.novels,bundle.chapters).create({"id":"matrix","title":"Matrix"})["id"];ChapterService(bundle.chapters).create(project,{"title":"One","content":"Text"});fixture(bundle.narrative,project);lore=LoreService(bundle.lore)
    off_off=ContextService(bundle.novels,bundle.chapters,None,False,bundle.narrative,False).build(project,1)
    on_off=ContextService(bundle.novels,bundle.chapters,lore,True,bundle.narrative,False).build(project,1)
    off_on=ContextService(bundle.novels,bundle.chapters,None,False,bundle.narrative,True).build(project,1)
    on_on=ContextService(bundle.novels,bundle.chapters,lore,True,bundle.narrative,True).build(project,1)
    assert "lore_memory" not in off_off and "narrative_context" not in off_off
    assert "lore_memory" in on_off and "narrative_context" not in on_off
    assert "lore_memory" not in off_on and "narrative_context" in off_on
    assert "lore_memory" in on_on and "narrative_context" in on_on


@pytest.mark.file_backend_only
def test_disabled_narrative_context_does_not_query_repository(tmp_path):
    bundle=create_repository_bundle(data_root=tmp_path);project=NovelService(bundle.novels,bundle.chapters).create({"id":"no-query","title":"No Query"})["id"];ChapterService(bundle.chapters).create(project,{"title":"One","content":"Text"})
    class FailingRepository:
        def list(self,*_):raise AssertionError("disabled narrative context queried repository")
    context=ContextService(bundle.novels,bundle.chapters,narrative_repository=FailingRepository(),enable_narrative_context=False).build(project,1)
    assert "narrative_context" not in context
