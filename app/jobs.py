from __future__ import annotations
import difflib,json,threading,uuid,time
from dataclasses import dataclass,field
from datetime import datetime,timezone
from .agents import agent_runner
from .review import deterministic_review
from .runtime import runtime
from .structured_log import runtime_log
from .dependencies import chapter_service,context_service,canon_service,generation_service,repositories,memory_agent_service,collaboration_application_service
from .repositories.factory import create_repository_bundle
from .services import ChapterService,ContextService,CanonService,GenerationService,LoreService
from .config import settings
from .actor_context import ActorContext,SessionContext
from .authorization import AuthorizationScope,ScopeKind
from .model_runtime import TextGenerationRequest,TextModelNodeInput,TextGenerationParameters,ModelRuntimeError,RuntimeErrorCode
from .router import Route

# Compatibility facade for V0.3 tests and extensions that patched app.jobs.repo.
# Job business logic never reads it directly; it is only a File-mode composition root.
repo=getattr(repositories.novels,"backend",None)

def utc():return datetime.now(timezone.utc).isoformat()
@dataclass
class Job:
    id:str;operation:str;novel_id:str;chapter_id:str;instruction:str;profile:str;source:str="";requested_provider:str|None=None;requested_model:str|None=None;style:str="";status:str="QUEUED";output:str="";error:str|None=None;provider:str|None=None;model:str|None=None;issues:list=field(default_factory=list);latency_ms:int=0;base_chapter_version:int|None=None;variant_group_id:str|None=None;variant_index:int|None=None;actor_id:str|None=None;session_id:str|None=None;client_id:str|None=None;workspace_id:str|None=None;scope:dict|None=None;scope_type:str|None=None;scope_id:str|None=None;correlation_id:str|None=None;context_snapshot_id:str|None=None;created_at:str=field(default_factory=utc);updated_at:str=field(default_factory=utc);cancelled:threading.Event=field(default_factory=threading.Event,repr=False);condition:threading.Condition=field(default_factory=threading.Condition,repr=False)
    def public(self):return {k:getattr(self,k) for k in ("id","operation","novel_id","chapter_id","instruction","profile","source","requested_provider","requested_model","style","status","output","error","provider","model","issues","latency_ms","base_chapter_version","variant_group_id","variant_index","actor_id","session_id","client_id","workspace_id","scope","scope_type","scope_id","correlation_id","context_snapshot_id","created_at","updated_at")}
class JobManager:
    terminal={"COMPLETED","FAILED","CANCELLED","ACCEPTED","REJECTED"}
    def __init__(self,generations=None,chapters=None,contexts=None,canon=None,memory_extractor=None,snapshot_required=None,collaboration_updates=None):
        if generations is None and repo is not None:
            bundle=create_repository_bundle(data_root=repo.data);generations=GenerationService(bundle.generations);chapters=ChapterService(bundle.chapters);contexts=ContextService(bundle.novels,bundle.chapters,LoreService(bundle.lore));canon=CanonService(bundle.canon)
        self.jobs={};self.lock=threading.Lock();self.persistence=generations or generation_service;self.chapters=chapters or chapter_service;self.contexts=contexts or context_service;self.canon=canon or canon_service;self.memory_extractor=memory_extractor if memory_extractor is not None else memory_agent_service;self.snapshot_required=settings.enable_collaboration_runtime if snapshot_required is None else snapshot_required;self.collaboration_updates=collaboration_application_service if collaboration_updates is None else collaboration_updates
        for item in self.persistence.load_all():
            if item.get("status") in {"RUNNING","GENERATING","QUEUED"}:item["status"]="FAILED";item["error"]="服务重启导致生成中断，请重新生成。"
            try:self.jobs[item["id"]]=Job(**{k:v for k,v in item.items() if k in Job.__dataclass_fields__ and k not in {"cancelled","condition"}})
            except Exception:continue
    def _persist(self,job):self.persistence.save(job.public())
    def create(self,operation,payload,actor=None,scope=None):
        requested_provider=payload.get("provider_id");requested_model=payload.get("model_id")
        if bool(requested_provider)!=bool(requested_model):raise ValueError("provider_id and model_id must be selected together")
        job=Job(str(uuid.uuid4()),operation,payload["novel_id"],payload["chapter_id"],payload.get("instruction",""),payload.get("profile","LOCAL_ONLY"),payload.get("source",payload.get("selected_text","")),requested_provider,requested_model,payload.get("style",""))
        job.variant_group_id = payload.get("variant_group_id")
        job.variant_index = payload.get("variant_index")
        # Capture the generation base before dispatch so the response, snapshot
        # and later AI_ACCEPT all refer to the same optimistic version.
        job.base_chapter_version=self.chapters.get(job.chapter_id).get("version")
        if actor is not None:
            job.actor_id=actor.actor_id;job.session_id=actor.session_id;job.client_id=actor.client_id;job.workspace_id=actor.workspace_id;job.correlation_id=actor.effective_correlation_id
            if scope is not None:
                job.scope={"kind":scope.kind.value,"workspace_id":scope.workspace_id,"project_id":scope.project_id,"storyline_id":scope.storyline_id,"branch_id":scope.branch_id}
                job.scope_type=scope.kind.value;job.scope_id={"WORKSPACE":scope.workspace_id,"PROJECT":scope.project_id,"STORYLINE":scope.storyline_id,"BRANCH":scope.branch_id}[scope.kind.value]
        with self.lock:self.jobs[job.id]=job
        self._persist(job);threading.Thread(target=self._run,args=(job,),daemon=True).start();return job
    def _emit(self,job,chunk=""):
        with job.condition:
            if chunk:job.output+=chunk
            job.updated_at=utc();job.condition.notify_all()
        self._persist(job)
    def _run(self,job):
        started = time.monotonic()
        try:
            if job.cancelled.is_set():
                job.status="CANCELLED";self._emit(job);return
            job.status="GENERATING";self._emit(job)
            if job.cancelled.is_set():
                job.status="CANCELLED";self._emit(job);return
            ch=self.chapters.get(job.chapter_id);cloud=job.profile!="LOCAL_ONLY" or runtime.is_remote_text_provider(job.requested_provider);context=self.contexts.for_chapter(job.chapter_id,job.instruction,cloud,job.operation)
            mapping={"continue":"writer","rewrite":"writer","polish":"editor","brainstorm":"plot_planner","review":"continuity_reviewer"};role=mapping[job.operation];task={"continue":"Continue the chapter without repeating it.","rewrite":"Rewrite only the supplied selection.","polish":"Polish the supplied text without changing facts.","brainstorm":"Return concise story options.","review":"Review the chapter and list actionable issues."}[job.operation]
            style_instruction=f"\n写作风格要求：{job.style}" if job.style else ""
            prompt=agent_runner.build_prompt(role,context,task+" "+job.instruction+style_instruction,job.source or ch["content"][-2000:]);router=runtime.router(job.profile,role);last=None
            if job.requested_provider and job.requested_model:router.routes[role]=[Route(job.requested_provider,job.requested_model)]
            for route in router.routes[role]:
                if not runtime.packaged_author_route_ready(route.provider):
                    last=ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION,"TEXT_PROVIDER_NOT_CONFIGURED",provider_id=route.provider)
                    continue
                try:
                    if self.snapshot_required:
                        snapshot=self.contexts.save_snapshot(job.chapter_id,ch.get("version",0),context,f"{role}:v1",route.model,actor_id=job.actor_id,session_id=job.session_id,scope_type=job.scope_type,scope_id=job.scope_id,generation_id=job.id,cloud=cloud)
                        if not snapshot:raise RuntimeError("Context snapshot persistence is required")
                        job.context_snapshot_id=snapshot["id"];self._persist(job)
                    node=runtime.prepare_text_route(route.provider,route.model,router.providers.get(route.provider))
                    request=TextGenerationRequest(provider_id=route.provider,model_id=route.model,prompt=prompt,context=context,parameters=TextGenerationParameters(),metadata={"purpose":job.operation},job_id=job.id,cancellation=job.cancelled)
                    for event in node.stream(TextModelNodeInput(request)):
                        if event.event_type=="generation.cancelled" or job.cancelled.is_set():job.status="CANCELLED";self._emit(job);return
                        if event.event_type=="generation.failed":raise ModelRuntimeError(event.error_code or RuntimeErrorCode.GENERATION_FAILED,"生成失败，请稍后重试")
                        if event.event_type=="generation.delta" and event.delta:self._emit(job,event.delta)
                    job.provider=route.provider;job.model=route.model;break
                except Exception as exc:last=exc
            else:raise last or RuntimeError("No provider route")
            if role=="writer" and not self.snapshot_required:self.contexts.save_snapshot(job.chapter_id,ch.get("version",0),context,"writer:v1",job.model or "unknown")
            job.issues=deterministic_review(job.output,context);job.latency_ms=int((time.monotonic()-started)*1000);job.status="COMPLETED";self._emit(job);runtime_log.write(generation_id=job.id,novel_id=job.novel_id,chapter_id=job.chapter_id,agent=role,provider=job.provider,model=job.model,status=job.status,latency_ms=job.latency_ms)
        except Exception as exc:
            if isinstance(exc,ModelRuntimeError):safe_error=exc.safe_message;error_code=exc.code.value
            elif isinstance(exc,RuntimeError) and "snapshot" in str(exc).casefold():safe_error=f"Context snapshot persistence failed: {exc}";error_code="CONTEXT_SNAPSHOT_FAILED"
            else:safe_error="生成失败，请稍后重试";error_code=type(exc).__name__
            job.latency_ms=int((time.monotonic()-started)*1000);job.status="FAILED";job.error=safe_error;self._emit(job);runtime_log.write(generation_id=job.id,novel_id=job.novel_id,chapter_id=job.chapter_id,status=job.status,error=error_code,latency_ms=job.latency_ms)
    def get(self,jid):
        if jid not in self.jobs:raise KeyError(jid)
        return self.jobs[jid]
    def variants(self, group_id):
        return sorted((job for job in self.jobs.values() if job.variant_group_id == group_id), key=lambda job: job.variant_index or 0)
    def cancel(self,jid):
        job=self.get(jid)
        job.cancelled.set()
        if job.status not in self.terminal:
            job.status="CANCELLED"
            self._emit(job)
        return job
    def events(self,jid):
        job=self.get(jid);sent=0
        while True:
            with job.condition:
                if len(job.output)==sent and job.status not in self.terminal:job.condition.wait(timeout=10)
                chunk=job.output[sent:];sent=len(job.output);status=job.status
            yield "data: "+json.dumps({"job_id":jid,"status":status,"chunk":chunk,"provider":job.provider,"model":job.model,"error":job.error},ensure_ascii=False)+"\n\n"
            if status in self.terminal:return
    def accept(self,jid,accepted_output=None,actor=None,scope=None,expected_version=None):
        job=self.get(jid)
        if job.status!="COMPLETED":raise ValueError("Only completed drafts can be accepted")
        chapter=self.chapters.get(job.chapter_id);original=chapter["content"];output=accepted_output if accepted_output is not None else job.output;content=(original+"\n\n"+output) if job.operation=="continue" else (original.replace(job.source,output,1) if job.operation=="rewrite" and job.source in original else output)
        if job.operation == "continue":
            title = f"第{chapter['number'] + 1}章"
            if actor is not None and scope is not None:
                created = self.collaboration_updates.create_chapter(actor=actor, scope=scope, title=title)
                saved = self.collaboration_updates.update_chapter(
                    actor=actor, scope=scope, chapter_id=created["id"],
                    document=__import__("app.document",fromlist=["markdown_to_document"]).markdown_to_document(f"# {title}\n\n{output}"),
                    expected_version=created["version"], reason="AI_ACCEPT",
                )
            elif job.actor_id and job.scope:
                session=SessionContext(job.session_id or "",job.client_id or "",job.actor_id,job.workspace_id or "",job.correlation_id)
                stored_actor=ActorContext(job.actor_id,job.workspace_id or "",session,job.correlation_id);raw=job.scope;stored_scope=AuthorizationScope(ScopeKind(raw["kind"]),raw["workspace_id"],raw.get("project_id"),raw.get("storyline_id"),raw.get("branch_id"))
                created = self.collaboration_updates.create_chapter(actor=stored_actor, scope=stored_scope, title=title)
                saved = self.collaboration_updates.update_chapter(actor=stored_actor, scope=stored_scope, chapter_id=created["id"], document=__import__("app.document",fromlist=["markdown_to_document"]).markdown_to_document(f"# {title}\n\n{output}"), expected_version=created["version"], reason="AI_ACCEPT")
            else:
                create_chapter = getattr(self.chapters, "create", None)
                if callable(create_chapter):
                    saved = create_chapter(job.novel_id, {"title": title, "content": output})
                else:
                    # Keep the V0.3 compatibility facade usable with minimal
                    # chapter doubles while the real repository creates the
                    # next chapter through ChapterService.create().
                    saved = self.chapters.save(
                        job.chapter_id,
                        {"title": title, "content": f"{original}\n\n{output}", "version": chapter["version"], "source": "AI_ACCEPT"},
                    )
            self.chapters.save_summary(job.novel_id, saved.get("number", chapter["number"] + 1), output[:240])
            pending_canon={"id":str(uuid.uuid4()),"novel_id":job.novel_id,"chapter":saved.get("number", chapter["number"] + 1),"status":"PENDING","proposals":[{"fact":"AI draft introduced a possible lasting story fact","source_job":jid}],"source":"archivist"}
            self.canon.save_pending(pending_canon)
            job.status="ACCEPTED";self._emit(job)
            return {"chapter": saved, "pending_canon": pending_canon}
        current=self.chapters.get(job.chapter_id);target_version=expected_version if expected_version is not None else (job.base_chapter_version if job.base_chapter_version is not None else current["version"])
        if actor is not None and scope is not None:
            saved=self.collaboration_updates.update_chapter(actor=actor,scope=scope,chapter_id=job.chapter_id,document=__import__("app.document",fromlist=["markdown_to_document"]).markdown_to_document(content),expected_version=target_version,reason="AI_ACCEPT")
        elif job.actor_id and job.scope:
            session=SessionContext(job.session_id or "",job.client_id or "",job.actor_id,job.workspace_id or "",job.correlation_id)
            stored_actor=ActorContext(job.actor_id,job.workspace_id or "",session,job.correlation_id);raw=job.scope;stored_scope=AuthorizationScope(ScopeKind(raw["kind"]),raw["workspace_id"],raw.get("project_id"),raw.get("storyline_id"),raw.get("branch_id"))
            saved=self.collaboration_updates.update_chapter(actor=stored_actor,scope=stored_scope,chapter_id=job.chapter_id,document=__import__("app.document",fromlist=["markdown_to_document"]).markdown_to_document(content),expected_version=target_version,reason="AI_ACCEPT")
        else:saved=self.chapters.save(job.chapter_id,{"content":content,"version":current["version"],"source":"AI_ACCEPT"})
        self.chapters.save_summary(job.novel_id,chapter["number"],content[:240]);pending={"id":str(uuid.uuid4()),"novel_id":job.novel_id,"chapter":chapter["number"],"status":"PENDING","proposals":[{"fact":"AI draft introduced a possible lasting story fact","source_job":jid}],"source":"archivist"};self.canon.save_pending(pending);job.status="ACCEPTED";self._emit(job)
        try:self.memory_extractor.enqueue(job.novel_id,job.chapter_id,saved["version"],job.profile)
        except Exception:pass
        return {"chapter":self.chapters.get(job.chapter_id),"pending_canon":pending}
    def reject(self,jid):job=self.get(jid);job.status="REJECTED";self._emit(job);return job
    def diff(self,jid):job=self.get(jid);original=job.source or self.chapters.get(job.chapter_id)["content"];return "\n".join(difflib.unified_diff(original.splitlines(),job.output.splitlines(),fromfile="original",tofile="generated",lineterm=""))
jobs=JobManager()
