from __future__ import annotations
import hashlib,json,threading,uuid
from datetime import datetime,timezone
from typing import Any
from pydantic import BaseModel,Field,model_validator
from app.agents import AgentRunner
from app.document import document_to_markdown
from app.lore.enums import ProposalType

NAMESPACE=uuid.UUID("93e54f54-f779-5d9f-a354-fdfcc48bc146")
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
class AgentEvidence(BaseModel):
 chapter_id:str=Field(min_length=1);chapter_version:int=Field(ge=1);excerpt:str=Field(min_length=1);locator:dict[str,Any]
 @model_validator(mode="after")
 def locator_required(self):
  if not self.locator:raise ValueError("evidence locator is required")
  return self
class AgentProposal(BaseModel):
 proposal_type:ProposalType;payload:dict[str,Any];confidence:float=Field(ge=0,le=1);evidence:list[AgentEvidence]=Field(min_length=1)
 @model_validator(mode="after")
 def extraction_types_only(self):
  if self.proposal_type not in {ProposalType.CHARACTER_MEMORY,ProposalType.RELATIONSHIP,ProposalType.EVENT,ProposalType.SECRET_CHANGE}:raise ValueError("unsupported memory extraction proposal_type")
  return self
class MemoryAgentOutput(BaseModel):proposals:list[AgentProposal]

class MemoryAgentRunner:
 def __init__(self,novels,chapters,lore,generations,agent_runner:AgentRunner,runtime):self.novels=novels;self.chapters=chapters;self.lore=lore;self.generations=generations;self.agent_runner=agent_runner;self.runtime=runtime
 def _input(self,novel_id,chapter_id,version):
  chapter=self.chapters.get(chapter_id);versions=self.chapters.history(chapter_id);match={"version":chapter["version"],"document":chapter["document"]} if chapter["version"]==version else next((x for x in versions if x["version"]==version),None)
  if not match:raise FileNotFoundError(f"chapter version {chapter_id}@{version}")
  document=match["document"];text=document_to_markdown(document);sources=self.novels.get_context_sources(novel_id)
  chars=[x for x in sources.get("characters",[]) if (x.get("id") and x.get("id") in text) or (x.get("name") and x.get("name") in text)]
  keys=[x.get("id") for x in chars]+[x.get("name") for x in chars];related=lambda items:[x for x in items if any(k and k in canonical(x) for k in keys) or str(chapter["number"]) in canonical(x)]
  snapshot=self.lore.repository.get_latest_snapshot(novel_id,"NOVEL","novel")
  return {"accepted_chapter":{"chapter_id":chapter_id,"version":version,"document":document,"content":text},"characters":chars,"canon":related(self.novels.get_data_set(novel_id,"canon")),"timeline":related(self.novels.get_data_set(novel_id,"timeline")),"secrets":[x for x in sources.get("secrets",[]) if (x.get("id") and x.get("id") in text) or (x.get("title") and x.get("title") in text)],"memory_snapshot":snapshot}
 def extract(self,novel_id,chapter_id,version,profile="LOCAL_ONLY",job_id=None):
  jid=job_id or str(uuid.uuid4());base={"id":jid,"operation":"MEMORY_EXTRACTION","novel_id":novel_id,"chapter_id":chapter_id,"status":"GENERATING","request":{"chapter_version":version},"created_at":datetime.now(timezone.utc).isoformat()};self.generations.save(base)
  try:
   data=self._input(novel_id,chapter_id,version);prompt=self.agent_runner.build_prompt("memory_agent",data,"Extract only durable evidence-backed changes.")
   router=self.runtime.router(profile,"memory_agent");result=router.generate("memory_agent",prompt);parsed=MemoryAgentOutput.model_validate_json(result.text);ids=[]
   for index,item in enumerate(parsed.proposals):
    seed=f"{novel_id}:{chapter_id}:{version}:{index}:{canonical(item.payload)}";pid=str(uuid.uuid5(NAMESPACE,"proposal:"+seed));relations=[]
    for eindex,evidence in enumerate(item.evidence):
     if evidence.chapter_id!=chapter_id or evidence.chapter_version!=version:raise ValueError("evidence must reference the accepted chapter version")
     eid=str(uuid.uuid5(NAMESPACE,f"evidence:{seed}:{eindex}:{canonical(evidence.model_dump())}"));ev={"id":eid,"novel_id":novel_id,"source_type":"CHAPTER_VERSION","source_id":f"{chapter_id}:v{version}","chapter_id":chapter_id,"chapter_version":version,"excerpt":evidence.excerpt,"locator":evidence.locator,"content_hash":hashlib.sha256((evidence.excerpt+canonical(evidence.locator)).encode()).hexdigest(),"privacy":"LOCAL_ONLY","status":"ACTIVE"}
     try:self.lore.create_evidence(ev)
     except FileExistsError:self.lore.repository.get_evidence(eid)
     relations.append({"evidence_id":eid,"relevance":"PRIMARY" if eindex==0 else "SUPPORTING"})
    proposal={"id":pid,"novel_id":novel_id,"proposal_type":item.proposal_type,"payload":item.payload,"status":"PENDING","confidence":item.confidence,"agent_name":"memory_agent","generation_job_id":jid,"source_chapter_id":chapter_id,"source_version":version}
    try:self.lore.create_proposal(proposal,relations)
    except FileExistsError:self.lore.repository.get_proposal(pid)
    ids.append(pid)
   self.generations.save({**base,"status":"COMPLETED","provider":result.provider,"model":result.model,"result":{"proposal_ids":ids}});return ids
  except Exception as exc:
   self.generations.save({**base,"status":"FAILED","error":f"{type(exc).__name__}: {exc}"});raise
 def enqueue(self,novel_id,chapter_id,version,profile="LOCAL_ONLY"):
  jid=str(uuid.uuid5(NAMESPACE,f"job:{novel_id}:{chapter_id}:{version}"))
  try:
   existing=self.generations.get(jid)
   if existing.get("status") in {"QUEUED","GENERATING","COMPLETED"}:return jid
  except KeyError:pass
  self.generations.save({"id":jid,"operation":"MEMORY_EXTRACTION","novel_id":novel_id,"chapter_id":chapter_id,"status":"QUEUED","request":{"chapter_version":version}})
  threading.Thread(target=lambda:self._quiet_extract(novel_id,chapter_id,version,profile,jid),daemon=True).start();return jid
 def _quiet_extract(self,*args):
  try:self.extract(*args)
  except Exception:pass
