from __future__ import annotations
import hashlib,json,threading,uuid
from datetime import datetime,timezone
from typing import Any
from contextlib import contextmanager
from pathlib import Path
from .memory_project_binding import FIELD as MEMORY_FIELD, create_binding
from pydantic import BaseModel,Field,model_validator
from app.agents import AgentRunner
from app.document import document_to_markdown
from app.lore.enums import ProposalType
from app.config import settings
from app.model_runtime import (LegacyTextProviderAdapter, ModelRuntimeError, Modality,
 RuntimeErrorCode, TextGenerationParameters, TextGenerationRequest, TextModelNodeInput)
from app.model_center.discovery_bridge import LocalTextAdapter
from app.model_center.discovery_types import local_endpoint
from app.providers import MockProvider

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

def source_bound_memory_schema(data):
 """Constrain quoted evidence to actual accepted source before generation."""
 source=data['accepted_chapter'];schema=MemoryAgentOutput.model_json_schema()
 excerpts=[]
 for line in source['content'].splitlines():
  line=line.strip()
  for start in range(0,len(line),800):
   quote=line[start:start+800]
   if quote and quote not in excerpts:excerpts.append(quote)
 evidence=schema['$defs']['AgentEvidence']['properties']
 evidence['chapter_id']['const']=source['chapter_id']
 evidence['chapter_version']['const']=source['version']
 # Empty chapters have no evidence and therefore only the empty proposals list.
 if excerpts:evidence['excerpt']['enum']=excerpts
 else:schema['properties']['proposals']['maxItems']=0
 schema['$defs']['AgentProposal']['properties']['proposal_type']={'type':'string','enum':['CHARACTER_MEMORY','RELATIONSHIP','EVENT','SECRET_CHANGE']}
 return schema

class MemoryAgentRunner:
 def __init__(self,novels,chapters,lore,generations,agent_runner:AgentRunner,runtime):
  self.novels=novels;self.chapters=chapters;self.lore=lore;self.generations=generations;self.agent_runner=agent_runner;self.runtime=runtime
  self._bound_ports=(novels,chapters,lore,generations,getattr(lore,"repository",None),getattr(generations,"repository",None))
  self._bound_backends=tuple(getattr(port,"backend",None) for port in (novels,chapters,self._bound_ports[4]))
  root=getattr(self._bound_ports[-1],"root",None)
  self._bound_data=Path(root).resolve().parent.parent if root is not None else None
 @contextmanager
 def _bound_owner(self,binding):
  if binding is None:
   yield
   return
  from app.repositories.file import FileNovelRepository,FileChapterRepository,FileLoreRepository,FileGenerationRepository
  from app.repositories.generation_repository import GenerationRepository,GenerationProjectIdentityError
  from app.services import LoreService,GenerationService
  from app.creative.project_store import CreativeProjectStore
  from types import SimpleNamespace
  ports=(self.novels,self.chapters,self.lore,self.generations,getattr(self.lore,"repository",None),getattr(self.generations,"repository",None))
  if (any(current is not original for current,original in zip(ports,self._bound_ports))
      or type(self.novels) is not FileNovelRepository or type(self.chapters) is not FileChapterRepository
      or type(self.lore) is not LoreService or type(self.generations) is not GenerationService
      or type(ports[4]) is not FileLoreRepository or type(ports[5]) not in (FileGenerationRepository,GenerationRepository)
      or self._bound_data is None or Path(ports[5].root).resolve()!=self._bound_data/'runtime/jobs'
      or any(port.backend is not backend for port,backend in zip((self.novels,self.chapters,ports[4]),self._bound_backends))
      or any(Path(port.backend.data).resolve()!=self._bound_data or Path(port.backend.novels).resolve()!=self._bound_data/'novels' for port in (self.novels,self.chapters,ports[4]))):
   raise GenerationProjectIdentityError("MEMORY_BOUND_FILE_STORE_MISMATCH")
  owner=CreativeProjectStore(SimpleNamespace(backend="file",root=self._bound_data))
  from app.runtime_events import runtime_events
  # File mutation decorators publish observer callbacks. Flush only after the
  # project lease exits; callbacks may acquire authorization/scope locks.
  with runtime_events.transaction(),owner.existing_owner_only(),owner.owner_lease(binding["project_id"]) as incarnation:
   if incarnation!=binding["project_incarnation"]:
    raise GenerationProjectIdentityError("MEMORY_PROJECT_OWNER_CHANGED")
   yield
 def _bound_check(self,binding):
  with self._bound_owner(binding):pass
 @staticmethod
 def _same_written_fields(existing,expected):
  if any(existing.get(key)!=value for key,value in expected.items()):
   raise ValueError("MEMORY_BOUND_WRITE_IDENTITY_MISMATCH")
 def _bound_proposal(self,proposal,relations,expected):
  owner={"_file_memory":expected}
  # Original LoreService owns validation and first creation. A prior attempt
  # may have created the proposal but stopped before linking all evidence.
  try:self.lore.create_proposal(proposal,relations,**owner)
  except FileExistsError:
   self._same_written_fields(self.lore.repository.get_proposal(proposal["id"],**owner),proposal)
   for relation in relations:
    row={**relation,"proposal_id":proposal["id"]}
    try:self.lore.repository.link_evidence(row,**owner)
    except FileExistsError:
     existing=next((item for item in self.lore.repository.list_proposal_evidence(proposal["id"],**owner)
                    if item["evidence_id"]==row["evidence_id"]),None)
     if existing is None:raise ValueError("MEMORY_BOUND_RELATION_MISSING")
     self._same_written_fields(existing,row)

 def _input(self,novel_id,chapter_id,version,expected=None):
  owner={"_file_memory":expected} if expected is not None else {}
  chapter=self.chapters.get(chapter_id,**owner);versions=self.chapters.history(chapter_id,**owner);match={"version":chapter["version"],"document":chapter["document"]} if chapter["version"]==version else next((x for x in versions if x["version"]==version),None)
  if not match:raise FileNotFoundError(f"chapter version {chapter_id}@{version}")
  if chapter.get("novel_id")!=novel_id:raise ValueError("memory chapter belongs to another project")
  document=match["document"];text=document_to_markdown(document);sources=self.novels.get_context_sources(novel_id,**owner)
  chars=[x for x in sources.get("characters",[]) if (x.get("id") and x.get("id") in text) or (x.get("name") and x.get("name") in text)]
  keys=[x.get("id") for x in chars]+[x.get("name") for x in chars];related=lambda items:[x for x in items if any(k and k in canonical(x) for k in keys) or str(chapter["number"]) in canonical(x)]
  snapshot=self.lore.repository.get_latest_snapshot(novel_id,"NOVEL","novel",**owner)
  return {"accepted_chapter":{"chapter_id":chapter_id,"version":version,"document":document,"content":text},"characters":chars,"canon":related(self.novels.get_data_set(novel_id,"canon",**owner)),"timeline":related(self.novels.get_data_set(novel_id,"timeline",**owner)),"secrets":[x for x in sources.get("secrets",[]) if (x.get("id") and x.get("id") in text) or (x.get("title") and x.get("title") in text)],"memory_snapshot":snapshot}
 def _verified_local_adapter(self,provider_id,model_id):
  registry=getattr(self.runtime,"provider_registry",None)
  if registry is None:raise ModelRuntimeError(RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED,"MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED")
  descriptor=next((row for row in registry.descriptors() if row.provider_id==provider_id),None)
  if descriptor is None or descriptor.provider_type not in {"local","development"}:
   raise ModelRuntimeError(RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED,"MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED")
  adapter=registry.resolve(provider_id)
  if isinstance(adapter,LocalTextAdapter):
   candidate=adapter.bridge.guard(adapter.candidate["id"])
   local_endpoint(candidate["runtime_config"]["endpoint"])
   if candidate.get("provider_id")!=provider_id or candidate.get("id")!=model_id:
    raise ModelRuntimeError(RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED,"MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED")
  elif not (isinstance(adapter,LegacyTextProviderAdapter) and isinstance(adapter.provider,MockProvider)
            and settings.mock_provider and not settings.enable_packaged_runtime):
   # A local-looking registry label or an Ollama brand does not prove egress is
   # confined. Only the guarded, no-proxy/no-redirect local adapter is admitted.
   raise ModelRuntimeError(RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED,"MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED")
  return adapter
 def _local_generation(self,prompt,jid,output_schema=None,owner_check=None):
  registry=getattr(self.runtime,"model_registry",None)
  if registry is not None:
   for model in registry.descriptors():
    if model.modality is not Modality.TEXT or not model.enabled:continue
    try:adapter=self._verified_local_adapter(model.provider_id,model.model_id)
    except (ModelRuntimeError,ValueError,KeyError):continue
    node=self.runtime.prepare_text_route(model.provider_id,model.model_id)
    def dispatch_guard():
     if self._verified_local_adapter(model.provider_id,model.model_id) is not adapter:
      raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION,"memory local route changed before dispatch")
     if owner_check is not None:owner_check()
    if owner_check is not None:owner_check()
    request=TextGenerationRequest(model.provider_id,model.model_id,prompt,job_id=jid,
     parameters=TextGenerationParameters(temperature=0.2,max_output_tokens=4000),
     structured_output_schema=(output_schema or MemoryAgentOutput.model_json_schema()) if getattr(model,'structured_output',False) else None,
     metadata={"purpose":"memory_extraction","privacy_level":"LOCAL_ONLY"},dispatch_guard=dispatch_guard)
    # Never fall back after an attempted generation, including to cloud routes.
    return node.execute(TextModelNodeInput(request)).response
  raise ModelRuntimeError(RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED,"MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED")
 def extract(self,novel_id,chapter_id,version,profile="LOCAL_ONLY",job_id=None,*,project_incarnation=None):
  binding=create_binding(novel_id,chapter_id,version,project_incarnation) if project_incarnation is not None else None
  from .file_memory_ports import _FileMemoryPorts
  expected=_FileMemoryPorts(self,binding) if binding is not None else None
  owner={"_file_memory":expected} if expected is not None else {}
  if binding is not None and job_id not in (None,binding["job_id"]):raise ValueError("MEMORY_BOUND_JOB_ID_MISMATCH")
  jid=binding["job_id"] if binding is not None else (job_id or str(uuid.uuid4()));base={"id":jid,"operation":"MEMORY_EXTRACTION","novel_id":novel_id,"chapter_id":chapter_id,"status":"GENERATING","request":{"chapter_version":version,"profile":"LOCAL_ONLY"},"created_at":datetime.now(timezone.utc).isoformat()}
  if binding is not None:base[MEMORY_FIELD]=binding
  with self._bound_owner(binding):self.generations.save(base,**owner)
  try:
   with self._bound_owner(binding):data=self._input(novel_id,chapter_id,version,expected) if expected is not None else self._input(novel_id,chapter_id,version)
   output_schema=source_bound_memory_schema(data)
   task="Extract durable evidence-backed changes from the accepted chapter. Produce an INSTANCE of the output schema, never repeat the schema itself. Return ONLY JSON, without Markdown fences or commentary, matching this JSON schema: "+json.dumps(output_schema,ensure_ascii=False)
   task+="\nEvery evidence reference must use chapter_id="+json.dumps(chapter_id)+" and chapter_version="+str(version)+". Copy an exact contiguous excerpt from accepted_chapter.content. Never cite paraphrases as evidence."
   task+="\nFor CHARACTER_MEMORY payloads, use an existing supplied character_id, memory_type EXPERIENCE|STATE_CHANGE|KNOWLEDGE_CHANGE|RELATIONSHIP_CHANGE and content as a JSON object. Extract at most three important changes with concise payloads and short exact excerpts. Return {\"proposals\":[]} if no durable change can be proven."
   prompt=self.agent_runner.build_prompt("memory_agent",data,task)
   prompt+='\n\nOUTPUT TASK: Read the accepted_chapter above and extract its durable changes. The top-level response MUST be {"proposals":[...]}, never {"$defs":...} or {"properties":...}. Each item needs proposal_type, payload, confidence and evidence. Evidence must quote the accepted chapter verbatim, with its provided chapter_id and version. Use only known character IDs for CHARACTER_MEMORY. Return {"proposals":[]} only when no durable change is supported.'
   result=(self._local_generation(prompt,jid,output_schema,owner_check=lambda:self._bound_check(binding))
           if binding is not None else self._local_generation(prompt,jid,output_schema));parsed=MemoryAgentOutput.model_validate_json(result.text);ids=[]
   # Validate every reference before the first durable proposal/evidence write.
   # An LLM's valid JSON is not evidence that a quoted event happened.
   text=data["accepted_chapter"]["content"]
   for item in parsed.proposals:
    for evidence in item.evidence:
     if evidence.chapter_id!=chapter_id or evidence.chapter_version!=version:raise ValueError("evidence must reference the accepted chapter version")
     if evidence.excerpt not in text:raise ValueError("memory evidence quote does not occur in the accepted chapter version")
   with self._bound_owner(binding):
    if canonical(self._input(novel_id,chapter_id,version,expected) if expected is not None else self._input(novel_id,chapter_id,version))!=canonical(data):raise ValueError("memory extraction sources changed during inference")
    for index,item in enumerate(parsed.proposals):
     seed=f"{novel_id}:{chapter_id}:{version}:{index}:{canonical(item.payload)}"
     if binding is not None:seed="bound-memory-v1:"+binding["job_id"]+":"+seed
     pid=str(uuid.uuid5(NAMESPACE,"proposal:"+seed));relations=[]
     for eindex,evidence in enumerate(item.evidence):
      if evidence.chapter_id!=chapter_id or evidence.chapter_version!=version:raise ValueError("evidence must reference the accepted chapter version")
      eid=str(uuid.uuid5(NAMESPACE,f"evidence:{seed}:{eindex}:{canonical(evidence.model_dump())}"));ev={"id":eid,"novel_id":novel_id,"source_type":"CHAPTER_VERSION","source_id":f"{chapter_id}:v{version}","chapter_id":chapter_id,"chapter_version":version,"excerpt":evidence.excerpt,"locator":evidence.locator,"content_hash":hashlib.sha256((evidence.excerpt+canonical(evidence.locator)).encode()).hexdigest(),"privacy":"LOCAL_ONLY","status":"ACTIVE"}
      try:self.lore.create_evidence(ev,**owner)
      except FileExistsError:
       existing=self.lore.repository.get_evidence(eid,**owner)
       if binding is not None:self._same_written_fields(existing,ev)
      relations.append({"evidence_id":eid,"relevance":"PRIMARY" if eindex==0 else "SUPPORTING"})
     proposal={"id":pid,"novel_id":novel_id,"proposal_type":item.proposal_type,"payload":item.payload,"status":"PENDING","confidence":item.confidence,"agent_name":"memory_agent","generation_job_id":jid,"source_chapter_id":chapter_id,"source_version":version}
     if binding is not None:self._bound_proposal(proposal,relations,expected)
     else:
      try:self.lore.create_proposal(proposal,relations)
      except FileExistsError:self.lore.repository.get_proposal(pid)
     ids.append(pid)
    self.generations.save({**base,"status":"COMPLETED","provider":result.provider_id,"model":result.model_id,"execution_mode":result.execution_mode,"result":{"proposal_ids":ids}},**owner);return ids
  except Exception as exc:
   code=exc.code.value if isinstance(exc,ModelRuntimeError) else "MEMORY_EXTRACTION_FAILED"
   with self._bound_owner(binding):self.generations.save({**base,"status":"NOT_CONFIGURED" if code=="TEXT_PROVIDER_NOT_CONFIGURED" else "FAILED","error_code":code,"error":f"{type(exc).__name__}: {exc}"},**owner);raise
 def enqueue(self,novel_id,chapter_id,version,profile="LOCAL_ONLY",*,project_incarnation=None):
  binding=create_binding(novel_id,chapter_id,version,project_incarnation) if project_incarnation is not None else None
  from .file_memory_ports import _FileMemoryPorts
  expected=_FileMemoryPorts(self,binding) if binding is not None else None
  owner={"_file_memory":expected} if expected is not None else {}
  jid=binding["job_id"] if binding is not None else str(uuid.uuid5(NAMESPACE,f"job:{novel_id}:{chapter_id}:{version}"))
  with self._bound_owner(binding):
   try:
    existing=self.generations.get(jid,**owner)
    if binding is not None and existing.get(MEMORY_FIELD)!=binding:raise ValueError("MEMORY_BOUND_RECEIPT_MISMATCH")
    if existing.get("status") in {"QUEUED","GENERATING","COMPLETED"}:return jid
   except KeyError:pass
   queued={"id":jid,"operation":"MEMORY_EXTRACTION","novel_id":novel_id,"chapter_id":chapter_id,"status":"QUEUED","request":{"chapter_version":version}}
   if binding is not None:queued[MEMORY_FIELD]=binding
   self.generations.save(queued,**owner)
  kwargs={"project_incarnation":project_incarnation} if binding is not None else {}
  threading.Thread(target=lambda:self._quiet_extract(novel_id,chapter_id,version,profile,jid,**kwargs),daemon=True).start();return jid
 def _quiet_extract(self,*args,**kwargs):
  try:self.extract(*args,**kwargs)
  except Exception:pass
