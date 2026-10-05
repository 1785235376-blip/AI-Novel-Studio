from __future__ import annotations
import json,time
import pytest
from pydantic import ValidationError
from app.agents import AgentRegistry,AgentRunner
from app.lore.memory_agent import MemoryAgentOutput,MemoryAgentRunner
from app.repositories.factory import create_repository_bundle
from app.repository import FileRepository
from app.services import ChapterService,GenerationService,LoreService,NovelService
from app.storage import atomic_write
from app.providers import Generation,MockProvider
from app.model_runtime import (GenerationRuntime,LegacyTextProviderAdapter,ModelDescriptor,ModelRegistry,
 Modality,ProviderDescriptor,ProviderRegistry)
from app.jobs import Job,JobManager

class MemoryFixtureProvider(MockProvider):
 def __init__(self,text):self.text=text;self.requests=[]
 def generate(self,prompt,model,**kwargs):
  self.requests.append(prompt)
  return Generation(self.text,"mock",model,metadata={"mock":True})
class Runtime:
 """Explicit in-process fixture through the real normalized node; never network."""
 def __init__(self,text):
  from app.config import settings
  object.__setattr__(settings,"mock_provider",True)  # Explicit development fixture, restored by conftest.
  self.provider=MemoryFixtureProvider(text);self.provider_registry=ProviderRegistry();self.model_registry=ModelRegistry()
  self.provider_registry.register(ProviderDescriptor("mock","Synthetic memory fixture","development",frozenset({Modality.TEXT}),True,True),LegacyTextProviderAdapter("mock",self.provider))
  self.model_registry.register(ModelDescriptor("memory-test","mock","Synthetic memory fixture",Modality.TEXT,frozenset({"generate"})))
  self.generation_runtime=GenerationRuntime(self.provider_registry,self.model_registry)
 def prepare_text_route(self,*args):return self.generation_runtime.text_node
 def router(self,*args):raise AssertionError("memory extraction must not use legacy routing")
def runner(tmp_path,output):
 bundle=create_repository_bundle(data_root=tmp_path);novels=NovelService(bundle.novels,bundle.chapters);chapters=ChapterService(bundle.chapters);nid=novels.create({"id":"agent-test","title":"Agent"})["id"];chapter=chapters.create(nid,{"title":"One","content":"Lin learned the harbor secret."});saved=chapters.save(chapter["id"],{"content":"Lin learned the harbor secret.","version":1,"source":"AI_ACCEPT"})
 atomic_write(tmp_path/"novels"/nid/"characters"/"characters.json",json.dumps([{"id":"lin","name":"Lin"}]))
 service=LoreService(bundle.lore);return MemoryAgentRunner(bundle.novels,bundle.chapters,service,GenerationService(bundle.generations),AgentRunner(AgentRegistry()),Runtime(json.dumps(output))),bundle,nid,chapter["id"],saved["version"]
def valid_output():return {"proposals":[{"proposal_type":"CHARACTER_MEMORY","payload":{"character_id":"lin","memory_type":"KNOWLEDGE_CHANGE","content":{"fact":"harbor secret"}},"confidence":0.9,"evidence":[{"chapter_id":"agent-test:1","chapter_version":2,"excerpt":"Lin learned the harbor secret.","locator":{"kind":"DOCUMENT_RANGE","from":1,"to":31}}]}]}
def test_json_output_and_evidence_contract():
 assert MemoryAgentOutput.model_validate(valid_output()).proposals[0].confidence==0.9
 with pytest.raises(ValidationError):MemoryAgentOutput.model_validate({"proposals":[{"proposal_type":"EVENT","payload":{},"confidence":.5,"evidence":[]}]})
 with pytest.raises(ValidationError):MemoryAgentOutput.model_validate({"proposals":[{"proposal_type":"CANON_SUGGESTION","payload":{},"confidence":.5,"evidence":[{"chapter_id":"n:1","chapter_version":1,"excerpt":"x","locator":{"kind":"DOCUMENT_RANGE"}}]}]})
@pytest.mark.file_backend_only
def test_extract_creates_pending_proposal_with_evidence_and_is_idempotent(tmp_path):
 agent,bundle,nid,cid,version=runner(tmp_path,valid_output());first=agent.extract(nid,cid,version,job_id="memory-job-1");second=agent.extract(nid,cid,version,job_id="memory-job-2")
 assert first==second and len(bundle.lore.list_proposals(nid))==1
 assert bundle.generations.get("memory-job-1")["execution_mode"]=="mock_standin"
 proposal=bundle.lore.get_proposal(first[0]);relations=bundle.lore.list_proposal_evidence(first[0]);assert proposal["status"]=="PENDING" and relations and bundle.lore.get_evidence(relations[0]["evidence_id"])["chapter_version"]==version
 assert bundle.lore.list_memories(nid)==[]
@pytest.mark.file_backend_only
def test_invalid_json_marks_independent_job_failed(tmp_path):
 agent,bundle,nid,cid,version=runner(tmp_path,{"wrong":[]})
 with pytest.raises(ValidationError):agent.extract(nid,cid,version,job_id="memory-failed")
 assert bundle.generations.get("memory-failed")["status"]=="FAILED"
def test_accept_survives_memory_enqueue_failure():
 class Store:
  def __init__(self):self.items={}
  def save(self,x):self.items[x["id"]]=x
  def load_all(self):return []
 class Chapters:
  def __init__(self):self.item={"id":"n:1","novel_id":"n","number":1,"content":"old","version":1}
  def get(self,c):return dict(self.item)
  def save(self,c,p):self.item.update(content=p["content"],version=self.item["version"]+1);return dict(self.item)
  def save_summary(self,*a):pass
 class Canon:
  def save_pending(self,x):return x
 class Failing:
  def enqueue(self,*a):raise RuntimeError("agent unavailable")
 store=Store();chapters=Chapters();manager=JobManager(generations=store,chapters=chapters,contexts=object(),canon=Canon(),memory_extractor=Failing());job=Job("j","continue","n","n:1","","LOCAL_ONLY",status="COMPLETED",output="new");manager.jobs[job.id]=job
 result=manager.accept(job.id);assert result["chapter"]["content"]=="old\n\nnew" and job.status=="ACCEPTED"
