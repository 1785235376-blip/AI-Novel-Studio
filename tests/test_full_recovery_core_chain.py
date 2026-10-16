"""Synthetic adapter outputs exercise real original stores, CAS and prompts.

These tests are implementation evidence, not live model quality acceptance.
"""
import copy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents import AgentRunner
from app.context import build_context_from_sources
from app.agent_catalog import public_agent_catalog, resolve_agent
from app.model_runtime import TextGenerationResponse, TextModelNodeOutput, GenerationEvent
from app.repositories.factory import create_repository_bundle
from app.repositories.structured_cas import record_digest
from app.repositories.chapter_repository import VersionConflict
from app.review import deterministic_review
from app.services import NovelService, ChapterService, ContextService, LoreService, GenerationService
from app.services.agent_context_service import AgentContextService
from app.services.agent_job_service import AgentJobService
from app.services.ai_planning_service import AIPlanningService, PlanningRunIn
from app.services.creation_workbench_service import CreationWorkbenchService
from app.services.v1_capability_service import V1CapabilityService, CapabilityVersionConflict


PREMISE = "一个失忆者在废弃城市寻找过去身份，最终发现自己曾经毁灭城市。"


@pytest.fixture
def core(tmp_path):
    bundle = create_repository_bundle(data_root=tmp_path)
    novels, chapters, lore = NovelService(bundle.novels,bundle.chapters), ChapterService(bundle.chapters), LoreService(bundle.lore)
    nid = novels.create({"id":"recovery-core-"+uuid4().hex[:12],"title":"废城之忆"})["id"]
    store = V1CapabilityService(tmp_path,novels,chapters,None)
    workbench = CreationWorkbenchService(store,chapters,novels)
    runtime = SimpleNamespace(output="",calls=[],cloud=False,execution_mode="real")
    runtime.is_remote_text_provider = lambda _:runtime.cloud
    def execute(value):
        value.request.dispatch_guard()
        runtime.calls.append(value.request)
        response = TextGenerationResponse(runtime.output,"completed",value.request.provider_id,value.request.model_id,execution_mode=runtime.execution_mode)
        return TextModelNodeOutput(response.text,response,value.request.job_id)
    runtime.prepare_text_route = lambda *_:SimpleNamespace(execute=execute)
    service = AIPlanningService(workbench,runtime,lore)
    return SimpleNamespace(nid=nid,bundle=bundle,novels=novels,chapters=chapters,lore=lore,store=store,workbench=workbench,
                           runtime=runtime,planning=service,scope=workbench.local_scope(nid),root=tmp_path)


def record(kind):
    common = {"kind":kind,"title":"合成测试候选","description":"仅用于结构化回归的合成测试输入。"}
    if kind == "WORLD":
        return {**common,"world_summary":"废弃城市保留灾难档案，记忆可以被封存。",
            "world_rules":[{"statement":"没有无代价的时间逆行","forbidden_terms":["无代价时间逆行"]}],
            "locations":[{"name":"废城档案馆","description":"保留毁城事件证据。"}]}
    if kind == "CHARACTERS":
        return {**common,"characters":[{"name":"失忆者","role":"主人公","personality":"谨慎","goal":"寻找身份","age":29}]}
    return {**common,"outline":{"theme":"责任","premise":PREMISE,"structure":"THREE_ACT",
        "beginning":"失忆者醒来","middle":"追查档案","ending":"承担毁城责任","main_conflict":"寻找身份与面对罪责","climax":"发现自己毁灭城市"}}


def queued(env,kind):
    return env.planning.create(env.nid,env.scope,"author",PlanningRunIn(kind=kind,premise=PREMISE,provider_id="synthetic-adapter",model_id="synthetic-model",candidate_count=1),start=False)


def ready(env,kind):
    env.runtime.output=json.dumps({"candidates":[{"record":record(kind)}]},ensure_ascii=False)
    row=queued(env,kind)
    result=env.planning.execute(env.nid,env.scope,row["id"])
    assert result["status"]=="READY",result
    return result


def apply(env,row):
    return env.planning.apply_candidate(env.nid,env.scope,"author",row["id"],row["candidates"][0]["id"],row["version"])


def test_seed_world_characters_outline_use_original_owners_and_context(core):
    env=core
    env.novels.upsert_character(env.nid,"manual-person",{"name":"手工角色","privacy_level":"LOCAL_ONLY"})
    world=ready(env,"WORLD")
    assert not env.novels.get(env.nid).get("world_summary")
    applied=apply(env,world)
    assert applied["run"]["candidates"][0]["status"]=="APPLIED"
    assert env.novels.get(env.nid)["world_summary"]==record("WORLD")["world_summary"]
    assert len(applied["applied"]["world_rule_ids"])==1
    rule=env.lore.repository.get_proposal(applied["applied"]["world_rule_ids"][0])
    assert rule["status"]=="APPROVED" and rule["reviewed_by"]=="author"
    assert env.lore.repository.list_proposal_evidence(rule["id"])
    characters=ready(env,"CHARACTERS")
    assert "废弃城市" in env.runtime.calls[-1].prompt
    assert env.runtime.calls[-1].context["world_rules"][0]["payload"]["statement"]==rule["approved_payload"]["statement"]
    applied_chars=apply(env,characters)["applied"]
    assert len(applied_chars["character_ids"])==1
    assert {x["name"] for x in env.novels.data_set(env.nid,"characters")}=={"手工角色","失忆者"}
    story=env.novels.story_record(env.nid,"characters",applied_chars["character_ids"][0])
    assert story["version"]==1 and story["actor_id"]=="author"
    outline=ready(env,"OUTLINE")
    assert "失忆者" in env.runtime.calls[-1].prompt
    assert "all outline fields belong inside record.outline" in env.runtime.calls[-1].prompt
    assert '"outline": {"theme": "<theme>"' in env.runtime.calls[-1].prompt
    result=apply(env,outline)
    assert result["applied"]["outline"]["climax"]=="发现自己毁灭城市"
    assert env.novels.outline(env.nid)["privacy_level"]=="LOCAL_ONLY"
    chapter=env.chapters.create(env.nid,{"title":"醒来","content":"失忆者望向档案馆。"})
    context=ContextService(env.bundle.novels,env.bundle.chapters,env.lore).for_chapter(chapter["id"])
    assert context["world"]["summary"] and context["outline"]["climax"]
    assert len(context["characters"])==2 and context["world_rules"][0]["status"]=="APPROVED"


def test_startup_schema_requires_seed_and_does_not_replace_old_source_requirements():
    with pytest.raises(ValueError):PlanningRunIn(kind="WORLD",provider_id="p",model_id="m")
    with pytest.raises(ValueError):PlanningRunIn(kind="STYLE",provider_id="p",model_id="m")
    with pytest.raises(ValueError):PlanningRunIn(kind="CHARACTERS",premise=PREMISE,mode="LOCAL_EXPLICIT")


def test_startup_context_drift_before_dispatch_prevents_model_call(core):
    env=core;row=queued(env,"OUTLINE")
    env.novels.upsert_character(env.nid,"changed",{"name":"已修改角色"})
    result=env.planning.execute(env.nid,env.scope,row["id"])
    assert result["status"]=="FAILED" and not env.runtime.calls


def test_startup_context_drift_after_review_blocks_application(core):
    env=core;row=ready(env,"OUTLINE")
    env.novels.update_outline(env.nid,{"theme":"作者的修改"})
    with pytest.raises(ValueError,match="context changed"):apply(env,row)
    assert env.novels.outline(env.nid)=={"theme":"作者的修改"}


def test_startup_model_schema_failure_and_mock_cannot_apply(core):
    env=core;env.runtime.output='{"candidates":[{"record":{"kind":"WORLD","title":"bad","description":"bad"}}]}'
    row=queued(env,"WORLD")
    result=env.planning.execute(env.nid,env.scope,row["id"])
    assert result["status"]=="FAILED" and not env.novels.data_set(env.nid,"locations")
    env.runtime.execution_mode="mock_standin"
    row=ready(env,"WORLD")
    with pytest.raises(ValueError,match="real model"):apply(env,row)
    assert not env.novels.get(env.nid).get("world_summary")


def test_partial_application_retains_receipts_and_explicit_retry_does_not_duplicate(core,monkeypatch):
    env=core;row=ready(env,"WORLD")
    original=env.novels.save_story_record
    monkeypatch.setattr(env.novels,"save_story_record",lambda *_a,**_kw:(_ for _ in ()).throw(RuntimeError("synthetic storage failure")))
    with pytest.raises(RuntimeError):apply(env,row)
    failed=env.planning.get(env.nid,env.scope,row["id"])
    assert failed["application"]["status"]=="FAILED" and "world_summary" in failed["application"]["receipts"]
    assert env.novels.get(env.nid)["world_summary"]==record("WORLD")["world_summary"]
    monkeypatch.setattr(env.novels,"save_story_record",original)
    result=apply(env,failed)
    assert result["run"]["application"]["status"]=="APPLIED"
    assert len(env.novels.data_set(env.nid,"locations"))==1
    assert len(env.lore.repository.list_proposals(env.nid,"APPROVED"))==1
    with pytest.raises(ValueError,match="already been applied"):apply(env,result["run"])


def test_native_outline_digest_cas_and_run_version_cas_reject_stale_write(core):
    env=core;old=record_digest(env.novels.outline(env.nid))
    env.novels.update_outline(env.nid,{"theme":"new"})
    with pytest.raises(VersionConflict):env.novels.update_outline(env.nid,{"theme":"lost"},expected_digest=old)
    row=ready(env,"CHARACTERS")
    with pytest.raises(CapabilityVersionConflict):env.planning.apply_candidate(env.nid,env.scope,"author",row["id"],row["candidates"][0]["id"],1)


def test_cloud_startup_context_does_not_send_unapproved_original_domain_data(core):
    env=core;env.runtime.cloud=True
    env.novels.upsert_character(env.nid,"private",{"name":"PRIVATE_TEST_PERSON","privacy_level":"LOCAL_ONLY"})
    env.novels.update_outline(env.nid,{"theme":"PRIVATE_TEST_THEME","privacy_level":"LOCAL_ONLY"})
    ready(env,"WORLD")
    prompt=env.runtime.calls[-1].prompt
    assert "PRIVATE_TEST" not in prompt
    assert PREMISE in prompt


def test_cloud_startup_project_policy_revocation_after_capture_blocks_dispatch(core,monkeypatch):
    env=core;env.runtime.cloud=True
    policy={"privacy_level":"CLOUD_ALLOWED"}
    original_get=env.novels.get
    monkeypatch.setattr(env.novels,"get",lambda nid:{**original_get(nid),**policy})
    row=queued(env,"WORLD")
    assert row["project_context_snapshot"]["project"]["privacy_level"]=="CLOUD_ALLOWED"
    original_prepare=env.runtime.prepare_text_route
    def prepare(*args):
        policy["privacy_level"]="LOCAL_ONLY"
        return original_prepare(*args)
    monkeypatch.setattr(env.runtime,"prepare_text_route",prepare)
    env.runtime.output=json.dumps({"candidates":[{"record":record("WORLD")}]},ensure_ascii=False)
    result=env.planning.execute(env.nid,env.scope,row["id"])
    assert result["status"]=="FAILED" and not env.runtime.calls
    assert not env.novels.get(env.nid).get("world_summary")


def test_reviewer_verifier_are_executable_and_receive_source_bound_prose(core):
    env=core;chapter=env.chapters.create(env.nid,{"title":"章一","content":"失忆者醒来。"})
    context=ContextService(env.bundle.novels,env.bundle.chapters,env.lore)
    contexts=AgentContextService(env.bundle.novels,env.bundle.chapters,context)
    generations=GenerationService(env.bundle.generations)
    runner=AgentRunner(SimpleNamespace(prompt=lambda name:name))
    runtime=SimpleNamespace(is_remote_text_provider=lambda _:False,providers={"p":object()})
    service=AgentJobService(generations,contexts,env.bundle.novels,runtime,runner)
    for agent in ("planner","writer","editor","reviewer","verifier"):
        created=service.create(agent,env.nid,1,provider="p",model="m",execution_mode="model",chapter_id=chapter["id"])
        def execute(value,agent=agent,created=created):
            value.request.dispatch_guard()
            assert value.request.context["sections"]["chapter_source"]["content"]==env.chapters.get(chapter["id"])["content"]
            assert '"schema": "'+resolve_agent(agent)["output_schema"]+'"' in value.request.prompt
            assert '"agent_id": "'+agent+'"' in value.request.prompt
            assert '"context_hash": "'+created["context_hash"]+'"' in value.request.prompt
            assert "final response must match this JSON schema" in value.request.prompt
            output={"schema":resolve_agent(agent)["output_schema"],"agent_id":agent,"summary":"synthetic verification","proposals":[],"findings":[],"context_hash":created["context_hash"]}
            response=TextGenerationResponse(json.dumps(output),"completed","p","m",execution_mode="mock_standin")
            return TextModelNodeOutput(response.text,response,created["id"])
        runtime.prepare_text_route=lambda *_:SimpleNamespace(execute=execute)
        result=service.execute(created["id"])
        assert result["status"]=="COMPLETED" and result["model_called"] is False,result
        assert result["provider_execution_mode"]=="mock_standin"
    assert [a["id"] for a in public_agent_catalog()["additional_agents"]]==["reviewer","verifier"]


def test_non_writer_preserves_approved_continuity_without_exposing_legacy_raw_contract():
    runner=AgentRunner(SimpleNamespace(prompt=lambda _:"edit"))
    prompt=runner.build_prompt("editor",{"novel_id":"n","chapter":1,"lore_memory":{"short_memory":[{"id":"m","content":{"event":"已承认毁城"}}]}},"preserve continuity")
    assert "continuity_memory" in prompt and "已承认毁城" in prompt and "lore_memory" not in prompt


def test_generation_review_includes_character_world_and_timeline_conflicts():
    issues=deterministic_review("死亡角色无代价时间逆行。",{"novel_id":"n","chapter":1,
        "characters":[{"name":"死亡角色","status":"DEAD"}],
        "world_rules":[{"id":"r","payload":{"statement":"时间旅行有代价","forbidden_terms":["无代价时间逆行"]}}],
        "timeline":[{"id":"e","title":"倒置时间","start_time":"2026-10-07T12:00:00","end_time":"2026-10-07T11:00:00"}]})
    assert {x["code"] for x in issues}=={"DEAD_CHARACTER","WORLD_RULE_VIOLATION","TIMELINE_ORDER_VIOLATION"}
    assert not deterministic_review("nothing",{"timeline":[{"time":"晚唐","end_time":"三天后"}]})


@pytest.mark.file_backend_only
def test_empty_new_relationship_collection_preserves_existing_legacy_state(core):
    from app.storage import atomic_write
    env=core
    old={"source_character_id":"hero","target_character_id":"witness","relationship_type":"FRIEND"}
    atomic_write(env.root/"novels"/env.nid/"story_state.json",json.dumps({"volume":1,"relationships":[old],"privacy_level":"CLOUD_ALLOWED"}))
    sources=env.bundle.novels.get_context_sources(env.nid)
    assert sources["relationships"]==[]
    assert build_context_from_sources(sources,env.nid,1,"")["relationships"]==[old]
    assert build_context_from_sources(sources,env.nid,1,"",cloud=True)["relationships"]==[old]
    sources["story_state"]["privacy_level"]="LOCAL_ONLY"
    assert build_context_from_sources(sources,env.nid,1,"",cloud=True)["relationships"]==[]


def test_completed_generation_persists_the_actual_three_domain_checks(core,monkeypatch):
    import app.jobs as module
    from app.jobs import JobManager
    from app.services import CanonService
    env=core;applied=apply(env,ready(env,"WORLD"))
    env.novels.upsert_character(env.nid,"dead",{"name":"死亡角色","status":"DEAD"})
    env.novels.upsert_timeline_event(env.nid,"inverted",{"title":"倒置时间","sequence":1,"start_time":"2026-10-07T12:00:00","end_time":"2026-10-07T11:00:00"})
    chapter=env.chapters.create(env.nid,{"title":"章一","content":"原正文"})
    output="死亡角色无代价时间逆行。"
    def stream(value):
        value.request.dispatch_guard()
        assert value.request.context["world_rules"][0]["id"]==applied["applied"]["world_rule_ids"][0]
        yield GenerationEvent("generation.delta",value.request.job_id,delta=output)
        yield GenerationEvent("generation.completed",value.request.job_id,response=TextGenerationResponse(output,"completed","p","m",execution_mode="mock_standin"))
    monkeypatch.setattr(module,"runtime",SimpleNamespace(is_remote_text_provider=lambda _:False,
        packaged_author_route_ready=lambda _:True,prepare_text_route=lambda *_:SimpleNamespace(stream=stream),
        router=lambda *_:SimpleNamespace(routes={"writer":[]})))
    manager=JobManager(generations=GenerationService(env.bundle.generations),chapters=env.chapters,
        contexts=ContextService(env.bundle.novels,env.bundle.chapters,env.lore),canon=CanonService(env.bundle.canon),
        memory_extractor=False,snapshot_required=False)
    job=manager.prepare_job("continue",{"novel_id":env.nid,"chapter_id":chapter["id"],"instruction":"创作","provider_id":"p","model_id":"m"})
    manager.jobs[job.id]=job
    manager._run(job)
    assert job.status=="COMPLETED",job.public()
    assert {x["code"] for x in job.issues}=={"DEAD_CHARACTER","WORLD_RULE_VIOLATION","TIMELINE_ORDER_VIOLATION"}
    assert {x["code"] for x in env.bundle.generations.get(job.id)["issues"]}=={x["code"] for x in job.issues}


def test_accepting_generated_next_chapter_enqueues_its_actual_version(core):
    from app.jobs import Job,JobManager
    from app.services import CanonService
    env=core;chapter=env.chapters.create(env.nid,{"title":"章一","content":"过去的版本"})
    calls=[]
    manager=JobManager(generations=GenerationService(env.bundle.generations),chapters=env.chapters,contexts=object(),
        canon=CanonService(env.bundle.canon),memory_extractor=SimpleNamespace(enqueue=lambda *args:calls.append(args)),snapshot_required=False)
    job=Job("synthetic-continue-accept-"+env.nid,"continue",env.nid,chapter["id"],"", "LOCAL_ONLY",status="COMPLETED",output="接受的新章节")
    manager.jobs[job.id]=job
    result=manager.accept(job.id)
    assert result["chapter"]["id"]!=chapter["id"]
    saved=env.chapters.get(result["chapter"]["id"])
    assert calls==[(env.nid,saved["id"],saved["version"],"LOCAL_ONLY")]


def test_memory_rejects_fabricated_quote_before_any_proposal_is_written(core,monkeypatch):
    from app.lore.memory_agent import MemoryAgentRunner
    env=core;chapter=env.chapters.create(env.nid,{"title":"章一","content":"失忆者在档案馆发现姓名。"})
    chapter=env.chapters.get(chapter["id"])
    output={"proposals":[{"proposal_type":"EVENT","payload":{"event":"找到了姓名"},"confidence":0.9,
        "evidence":[{"chapter_id":chapter["id"],"chapter_version":chapter["version"],"excerpt":quote,"locator":{"kind":"DOCUMENT_RANGE"}}]}
        for quote in ("失忆者在档案馆发现姓名。","正文中从未出现的证据") ]}
    service=MemoryAgentRunner(env.bundle.novels,env.bundle.chapters,env.lore,GenerationService(env.bundle.generations),
        AgentRunner(SimpleNamespace(prompt=lambda _:"memory")),object())
    def generate(prompt, _job_id, output_schema=None):
        assert "Produce an INSTANCE of the output schema" in prompt
        assert 'The top-level response MUST be {"proposals":[...]}' in prompt
        evidence=output_schema['$defs']['AgentEvidence']['properties']
        assert evidence['chapter_id']['const']==chapter['id']
        assert evidence['chapter_version']['const']==chapter['version']
        assert all(quote in chapter['content'] for quote in evidence['excerpt']['enum'])
        assert "正文中从未出现的证据" not in evidence['excerpt']['enum']
        return TextGenerationResponse(json.dumps(output),"completed","synthetic","synthetic",execution_mode="mock_standin")
    monkeypatch.setattr(service,"_local_generation",generate)
    job_id="synthetic-fabrication-"+env.nid
    with pytest.raises(ValueError,match="quote does not occur"):service.extract(env.nid,chapter["id"],chapter["version"],job_id=job_id)
    assert not env.lore.repository.list_proposals(env.nid)
    assert not env.lore.repository.list_evidence(env.nid)
    assert env.bundle.generations.get(job_id)["status"]=="FAILED"
