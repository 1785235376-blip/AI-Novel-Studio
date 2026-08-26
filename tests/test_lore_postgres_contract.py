from __future__ import annotations
import hashlib,os
from datetime import datetime,timezone
import pytest
from sqlalchemy import text,select
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.session import Database
from app.services import LoreService,NovelService,ChapterService,GenerationService
from app.services import MemoryService
from app.repositories.postgres.models import CharacterModel,NovelModel
from tests.test_memory_contract import setup as setup_file,prepare as prepare_memory
from app.lore.memory_agent import MemoryAgentRunner
from app.agents import AgentRegistry,AgentRunner
from app.providers import Generation
import json
from app.repository import FileRepository
from app.repositories.file.lore import FileLoreRepository

URL=os.getenv("TEST_POSTGRES_DATABASE_URL","")
pytestmark=[pytest.mark.postgres_backend_only,pytest.mark.skipif(not URL or not Database(URL).health_check(),reason="real PostgreSQL unavailable")]
@pytest.fixture
def bundle():
 b=create_repository_bundle(Settings(storage_backend="postgres",database_url=URL));yield b
 with b.novels.database.session() as s:s.execute(text("TRUNCATE memory_snapshots,character_memories,lore_proposal_evidence,lore_proposals,evidence_records,generation_jobs,pending_canon,canon_entries,chapter_summaries,chapter_versions,chapters,story_states,novels CASCADE"))
def test_real_postgres_lore_contract(bundle,tmp_path):
 novels=NovelService(bundle.novels,bundle.chapters);chapters=ChapterService(bundle.chapters);nid=novels.create({"title":"Lore PG Contract"})["id"];chapter=chapters.create(nid,{"title":"One","content":"Evidence"});service=LoreService(bundle.lore)
 stamp=datetime(2026,8,9,tzinfo=timezone.utc);excerpt="Evidence";eid="evidence-contract";pid="proposal-contract"
 file_backend=FileRepository(tmp_path);file_backend.create_novel({"id":nid,"title":"Lore PG Contract"});file_backend.create_chapter(nid,{"number":1,"title":"One"});file_service=LoreService(FileLoreRepository(file_backend))
 evidence_item={"id":eid,"novel_id":nid,"source_type":"CHAPTER_VERSION","source_id":f"{chapter['id']}:v1","chapter_id":chapter["id"],"chapter_version":1,"excerpt":excerpt,"locator":{"kind":"DOCUMENT_RANGE","from":1,"to":8},"content_hash":hashlib.sha256(excerpt.encode()).hexdigest(),"privacy":"CLOUD_ALLOWED","status":"ACTIVE","created_at":stamp,"updated_at":stamp}
 ev=service.create_evidence(evidence_item);assert ev==file_service.create_evidence(evidence_item)
 assert bundle.lore.get_evidence(eid)==ev and bundle.lore.list_evidence(nid)==[ev]
 proposal_item={"id":pid,"novel_id":nid,"proposal_type":"EVENT","payload":{"title":"Observed"},"status":"PENDING","created_at":stamp,"updated_at":stamp};relations=[{"evidence_id":eid,"relevance":"PRIMARY","created_at":stamp}]
 prop=service.create_proposal(proposal_item,relations);assert prop==file_service.create_proposal(proposal_item,relations)
 assert bundle.lore.get_proposal(pid)==prop and bundle.lore.list_proposal_evidence(pid)[0]["evidence_id"]==eid
 approved=service.approve_proposal(pid,{"title":"Approved"},"tester");assert approved["status"]=="APPROVED"
 with pytest.raises(ValueError):service.approve_proposal(pid,{},"tester")
 ev2=service.create_evidence({**ev,"id":"evidence-reject","source_id":"reject-source","content_hash":hashlib.sha256(b"reject").hexdigest(),"excerpt":"reject"})
 rejected=service.create_proposal({**prop,"id":"proposal-reject","status":"PENDING","approved_payload":None,"reviewed_by":None,"reviewed_at":None,"payload":{"title":"Reject"}},[{"evidence_id":ev2["id"],"relevance":"PRIMARY"}]);assert service.reject_proposal(rejected["id"],"tester")["status"]=="REJECTED"
 assert service.invalidate_evidence(ev2["id"],"obsolete")["status"]=="INVALIDATED"

def test_real_postgres_memory_contract_matches_file(bundle,tmp_path):
 novels=NovelService(bundle.novels,bundle.chapters);chapters=ChapterService(bundle.chapters);nid=novels.create({"title":"Memory Test"})["id"];chapters.create(nid,{"title":"One"})
 with bundle.novels.database.session() as s:
  novel=s.scalar(select(NovelModel).where(NovelModel.slug==nid));s.add(CharacterModel(novel_id=novel.id,slug="hero",name="Hero",facts={}))
 _,pg_memory,pg_prop=prepare_memory(bundle.lore);approved,created=pg_memory.approve_character_memory(pg_prop["id"],{"character_id":"hero","memory_type":"EXPERIENCE","content":{"event":"storm"}},"tester",memory_id="memory-pg",business_id="hero-storm")
 assert approved["status"]=="APPROVED" and created["id"]=="memory-pg" and created["character_id"]=="hero"
 evidence_id=bundle.lore.list_evidence(nid)[0]["id"];failed_prop=LoreService(bundle.lore).create_proposal({"id":"proposal-memory-fail","novel_id":nid,"proposal_type":"CHARACTER_MEMORY","payload":{"candidate":True},"status":"PENDING"},[{"evidence_id":evidence_id,"relevance":"PRIMARY"}])
 with pytest.raises(FileNotFoundError):pg_memory.approve_character_memory(failed_prop["id"],{"character_id":"missing","memory_type":"EXPERIENCE","content":{}},"tester",memory_id="must-not-exist")
 assert bundle.lore.get_proposal(failed_prop["id"])["status"]=="PENDING"
 snap1=pg_memory.create_snapshot(nid,"NOVEL","novel","tester",snapshot_id="snapshot-pg-1");snap2=pg_memory.create_snapshot(nid,"NOVEL","novel","tester",snapshot_id="snapshot-pg-2")
 assert snap2["version"]==2 and snap2["supersedes_id"]=="snapshot-pg-1" and bundle.lore.get_latest_snapshot(nid,"NOVEL","novel")==snap2
 file_repo=setup_file(tmp_path);_,file_memory,file_prop=prepare_memory(file_repo);_,file_created=file_memory.approve_character_memory(file_prop["id"],{"character_id":"hero","memory_type":"EXPERIENCE","content":{"event":"storm"}},"tester",memory_id="memory-pg",business_id="hero-storm")
 for key in ("id","novel_id","character_id","business_id","memory_type","content","status","valid_from_chapter","valid_to_chapter"):assert created[key]==file_created[key]

def test_real_postgres_memory_agent_creates_pending_only(bundle):
 novels=NovelService(bundle.novels,bundle.chapters);chapters=ChapterService(bundle.chapters);nid=novels.create({"title":"Agent PG"})["id"];chapter=chapters.create(nid,{"title":"One","content":"Lin changed."});saved=chapters.save(chapter["id"],{"content":"Lin changed.","version":1,"source":"AI_ACCEPT"})
 with bundle.novels.database.session() as s:
  novel=s.scalar(select(NovelModel).where(NovelModel.slug==nid));s.add(CharacterModel(novel_id=novel.id,slug="lin",name="Lin",facts={}))
 output=json.dumps({"proposals":[{"proposal_type":"CHARACTER_MEMORY","payload":{"character_id":"lin","memory_type":"STATE_CHANGE","content":{"state":"changed"}},"confidence":.8,"evidence":[{"chapter_id":chapter["id"],"chapter_version":saved["version"],"excerpt":"Lin changed.","locator":{"kind":"DOCUMENT_RANGE","from":1,"to":12}}]}]})
 class R:
  def generate(self,*a):return Generation(output,"fake","memory")
 class RT:
  def router(self,*a):return R()
 agent=MemoryAgentRunner(bundle.novels,bundle.chapters,LoreService(bundle.lore),GenerationService(bundle.generations),AgentRunner(AgentRegistry()),RT());ids=agent.extract(nid,chapter["id"],saved["version"],job_id="agent-pg-job")
 assert len(ids)==1 and bundle.lore.get_proposal(ids[0])["status"]=="PENDING" and bundle.lore.list_memories(nid)==[]
