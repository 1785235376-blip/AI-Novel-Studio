from __future__ import annotations
import difflib,json,threading,uuid,time
from dataclasses import dataclass,field,asdict
from datetime import datetime,timezone
from .agents import agent_runner
from .author_request import AUTHOR_ROLES, build_author_request, request_digest, saved_source_matches, chapter_digest, automatic_context_allowed
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
from .privacy import normalize_privacy

# Compatibility facade for V0.3 tests and extensions that patched app.jobs.repo.
# Job business logic never reads it directly; it is only a File-mode composition root.
repo=getattr(repositories.novels,"backend",None)

def utc():return datetime.now(timezone.utc).isoformat()
@dataclass
class Job:
    id:str;operation:str;novel_id:str;chapter_id:str;instruction:str;profile:str;source:str="";requested_provider:str|None=None;requested_model:str|None=None;style:str="";status:str="QUEUED";output:str="";error:str|None=None;error_code:str|None=None;provider:str|None=None;model:str|None=None;issues:list=field(default_factory=list);latency_ms:int=0;base_chapter_version:int|None=None;variant_group_id:str|None=None;variant_index:int|None=None;actor_id:str|None=None;session_id:str|None=None;client_id:str|None=None;workspace_id:str|None=None;scope:dict|None=None;scope_type:str|None=None;scope_id:str|None=None;correlation_id:str|None=None;context_snapshot_id:str|None=None;created_at:str=field(default_factory=utc);updated_at:str=field(default_factory=utc);cancelled:threading.Event=field(default_factory=threading.Event,repr=False);condition:threading.Condition=field(default_factory=threading.Condition,repr=False)
    creation_records:list=field(default_factory=list)
    expected_request_digest:str|None=None
    base_chapter_digest:str|None=None
    generation_max_output_bytes:int|None=None
    generation_deadline:str|None=None
    generation_bound_failure:str|None=None
    author_input_digest:str|None=None
    request_scope:dict|None=None
    reviewed_variant:dict|None=None
    reviewed_variant_receipt_state:str|None=None
    reviewed_variant_policy:dict|None=None
    request_authorization:object=field(default=None,repr=False)
    experimental_origin:str|None=None
    required_experimental_features:list=field(default_factory=list)
    execution_outcome:str|None=None
    partial_revision_only:bool=False
    revision_selection_binding:dict|None=None
    character_viewpoint:dict|None=None
    character_context_resolver:object=field(default=None,repr=False)
    before_dispatch:object=field(default=None,repr=False)
    on_terminal:object=field(default=None,repr=False)
    dispatch_hooks_required:bool=False
    terminal_hook_status:str|None=None
    _terminal_hook_called:bool=field(default=False,repr=False)
    usage:dict|None=None
    usage_status:str="UNKNOWN"
    execution_mode:str|None=None
    provider_reference_id:str|None=None
    route_decisions:list=field(default_factory=list)
    def public(self):
        result = {k:getattr(self,k) for k in ("id","operation","novel_id","chapter_id","instruction","profile","source","requested_provider","requested_model","style","status","output","error","error_code","provider","model","issues","latency_ms","base_chapter_version","variant_group_id","variant_index","actor_id","session_id","client_id","workspace_id","scope","scope_type","scope_id","correlation_id","context_snapshot_id","created_at","updated_at","creation_records","usage","usage_status","execution_mode","provider_reference_id","route_decisions")}
        if self.generation_max_output_bytes is not None or self.generation_deadline is not None:
            result.update(generation_max_output_bytes=self.generation_max_output_bytes, generation_deadline=self.generation_deadline)
        if self.generation_bound_failure is not None: result["generation_bound_failure"] = self.generation_bound_failure
        if self.author_input_digest is not None: result["author_input_digest"] = self.author_input_digest
        if self.request_scope is not None: result["request_scope"] = self.request_scope
        if self.reviewed_variant is not None:
            result.update(reviewed_variant=self.reviewed_variant, reviewed_variant_receipt_state=self.reviewed_variant_receipt_state, reviewed_variant_policy=self.reviewed_variant_policy)
        if self.expected_request_digest:
            result.update(expected_request_digest=self.expected_request_digest, base_chapter_digest=self.base_chapter_digest)
        if self.experimental_origin is not None:
            result.update(experimental_origin=self.experimental_origin,
                          required_experimental_features=list(self.required_experimental_features))
        if self.execution_outcome is not None and (self.experimental_origin is not None or self.dispatch_hooks_required):
            result["execution_outcome"] = self.execution_outcome
        if self.status == "COMPLETED" and (self.dispatch_hooks_required or callable(self.on_terminal)) and self.terminal_hook_status is None:
            result["status"] = "SETTLING"
        if self.partial_revision_only or self.revision_selection_binding is not None:
            result.update(partial_revision_only=True, revision_selection_binding=self.revision_selection_binding)
        if self.character_viewpoint is not None:
            result["character_viewpoint"] = self.character_viewpoint
        if self.dispatch_hooks_required:
            result["dispatch_hooks_required"] = True
        if self.terminal_hook_status is not None:
            result["terminal_hook_status"] = self.terminal_hook_status
        return result
# These stamps are set by trusted server coordinators, never from GenerateIn or
# an unvalidated payload. Intrinsic receipt fields retain older-job fencing.
GENERATION_ORIGINS = {
    "story_simulator_model": frozenset({"author_context_inspector_v2", "model_broker_v2", "story_simulator_v2"}),
    "multilingual_translation": frozenset({"author_context_inspector_v2", "model_broker_v2", "multilingual_editions_v2"}),
    "narrative_judge_model": frozenset({"author_context_inspector_v2", "model_broker_v2", "narrative_quality_judge_v2"}),
    "declarative_agent": frozenset({"author_context_inspector_v2", "model_broker_v2", "declarative_agents_v2"}),
    "author_context": frozenset({"author_context_inspector_v2"}),
    "character_author": frozenset({"author_context_inspector_v2", "world_character_engines_v2", "temporal_story_graph_v2", "character_mind_v2"}),
    "model_broker": frozenset({"author_context_inspector_v2", "model_broker_v2"}),
    "selection_assistant": frozenset({"author_context_inspector_v2", "revision_intelligence_v2", "selection_assistant_v2"}),
}


def generation_required_features(job):
    required = set()
    origin = getattr(job, "experimental_origin", None)
    stored = getattr(job, "required_experimental_features", [])
    allowed = set().union(*GENERATION_ORIGINS.values())
    if origin is not None:
        if origin not in GENERATION_ORIGINS or not isinstance(stored, list) or any(not isinstance(value, str) or value not in allowed for value in stored):
            raise ValueError("GENERATION_ORIGIN_INVALID")
        required.update(GENERATION_ORIGINS[origin]); required.update(stored)
    elif stored:
        raise ValueError("GENERATION_ORIGIN_INVALID")
    if getattr(job, "expected_request_digest", None): required.update(GENERATION_ORIGINS["author_context"])
    if getattr(job, "character_viewpoint", None) is not None or getattr(job, "character_context_resolver", None) is not None:
        required.update(GENERATION_ORIGINS["character_author"])
    if getattr(job, "dispatch_hooks_required", False): required.update(GENERATION_ORIGINS["model_broker"])
    if getattr(job, "partial_revision_only", False) or getattr(job, "revision_selection_binding", None) is not None:
        required.update(GENERATION_ORIGINS["selection_assistant"])
    return frozenset(required)


def mark_generation_origin(job, origin):
    if origin not in GENERATION_ORIGINS: raise ValueError("GENERATION_ORIGIN_INVALID")
    required = generation_required_features(job) | GENERATION_ORIGINS[origin]
    job.experimental_origin = origin
    job.required_experimental_features = sorted(required)


def generation_content_available(job):
    try: required = generation_required_features(job)
    except ValueError: return False
    if not required: return True
    from .experimental.flags import enabled_flags
    return required.issubset(enabled_flags())


def require_generation_content(job):
    if not generation_content_available(job):
        from fastapi import HTTPException
        raise HTTPException(404, {"code": "GENERATION_FEATURE_DISABLED"})


def require_whole_generation_acceptance(job):
    required = generation_required_features(job)
    for feature, code in (("story_simulator_v2", "SIMULATOR_DRAFT_ONLY"), ("multilingual_editions_v2", "TRANSLATION_DRAFT_ONLY"), ("narrative_quality_judge_v2", "JUDGE_DRAFT_ONLY")):
        if feature in required:
            from fastapi import HTTPException
            raise HTTPException(409, {"code": code})
    if "declarative_agents_v2" in generation_required_features(job):
        from fastapi import HTTPException
        raise HTTPException(409, {"code": "DECLARATIVE_DRAFT_ONLY"})
    if (getattr(job, "partial_revision_only", False) or getattr(job, "revision_selection_binding", None) is not None
        or "selection_assistant_v2" in generation_required_features(job)):
        from fastapi import HTTPException
        raise HTTPException(409, {"code": "REVISION_REVIEW_REQUIRED"})


def require_generation_accounting(job):
    if (job.dispatch_hooks_required or callable(job.on_terminal)) and job.terminal_hook_status != "COMPLETED":
        from fastapi import HTTPException
        raise HTTPException(409, {"code": "GENERATION_ACCOUNTING_NOT_TERMINAL"})


def validate_generation_bounds(job):
    """Trusted-host-only optional bounds. Ordinary input payloads cannot set them."""
    size, deadline = job.generation_max_output_bytes, job.generation_deadline
    if size is None and deadline is None: return None
    if type(size) is not int or not 256 <= size <= 128000 or not isinstance(deadline, str):
        raise ValueError("GENERATION_BOUNDS_INVALID")
    try: parsed = datetime.fromisoformat(deadline)
    except ValueError: raise ValueError("GENERATION_BOUNDS_INVALID") from None
    if parsed.tzinfo is None or (parsed - datetime.now(timezone.utc)).total_seconds() > 301:
        raise ValueError("GENERATION_BOUNDS_INVALID")
    return parsed


def check_generation_bounds(job, *, delta="", completion_text=None):
    expected = getattr(job, "_generation_bounds", None)
    changed = expected is not None and expected != (job.generation_max_output_bytes, job.generation_deadline)
    if changed:
        job.generation_bound_failure = "GENERATION_BOUNDS_CHANGED"; job.output = ""; job.cancelled.set()
        raise ValueError("GENERATION_BOUNDS_CHANGED")
    deadline = validate_generation_bounds(job)
    if deadline is None: return
    code = None
    if datetime.now(timezone.utc) >= deadline: code = "GENERATION_DEADLINE_EXCEEDED"
    elif len(job.output.encode("utf-8")) + len(delta.encode("utf-8")) > job.generation_max_output_bytes:
        code = "GENERATION_OUTPUT_LIMIT"
    elif completion_text is not None and len(completion_text.encode("utf-8")) > job.generation_max_output_bytes:
        # Completion is often the same text already streamed; never add it twice.
        code = "GENERATION_OUTPUT_LIMIT"
    if code:
        job.generation_bound_failure = code
        job.output = ""
        job.cancelled.set()  # Cooperative signal, not forced upstream preemption.
        raise ValueError(code)


class JobManager:
    transient_fields={"cancelled", "condition", "request_authorization", "character_context_resolver", "before_dispatch", "on_terminal", "_terminal_hook_called"}
    terminal={"COMPLETED","FAILED","CANCELLED","ACCEPTED","REJECTED","ACCEPTING","ACCEPTANCE_UNCERTAIN"}
    def __init__(self,generations=None,chapters=None,contexts=None,canon=None,memory_extractor=None,snapshot_required=None,collaboration_updates=None):
        if generations is None and repo is not None:
            bundle=create_repository_bundle(data_root=repo.data);generations=GenerationService(bundle.generations);chapters=ChapterService(bundle.chapters);contexts=ContextService(bundle.novels,bundle.chapters,LoreService(bundle.lore));canon=CanonService(bundle.canon)
        self.jobs={};self.lock=threading.Lock();self.persistence=generations or generation_service;self.chapters=chapters or chapter_service;self.contexts=contexts or context_service;self.canon=canon or canon_service;self.memory_extractor=memory_extractor if memory_extractor is not None else memory_agent_service;self.snapshot_required=settings.enable_collaboration_runtime if snapshot_required is None else snapshot_required;self.collaboration_updates=collaboration_application_service if collaboration_updates is None else collaboration_updates
        for item in self.persistence.load_all():
            if item.get("status") == "SETTLING":
                item.update(status="FAILED", error_code="GENERATION_SETTLEMENT_RECOVERY_REQUIRED",
                    error="服务重启中断了结算确认。已保留草稿与费用占用，请核对调度记录，不会自动重放。",
                    dispatch_hooks_required=True, terminal_hook_status="MISSING_RECONCILIATION_REQUIRED")
            elif item.get("status") in {"RUNNING","GENERATING","QUEUED","PREPARED"}:item["status"]="FAILED";item["error"]="服务重启导致生成中断，请重新生成。"
            try:self.jobs[item["id"]]=Job(**{k:v for k,v in item.items() if k in Job.__dataclass_fields__ and k not in self.transient_fields})
            except Exception:continue
    def _persist(self,job):self.persistence.save(job.public())
    def prepare_job(self,operation,payload,actor=None,scope=None,request_authorization=None):
        requested_provider=payload.get("provider_id");requested_model=payload.get("model_id")
        if bool(requested_provider)!=bool(requested_model):raise ValueError("provider_id and model_id must be selected together")
        job=Job(str(uuid.uuid4()),operation,payload["novel_id"],payload["chapter_id"],payload.get("instruction",""),payload.get("profile","LOCAL_ONLY"),payload.get("source",payload.get("selected_text","")),requested_provider,requested_model,payload.get("style",""))
        job.creation_records = [dict(row) for row in payload.get("creation_records", [])]
        job.expected_request_digest = payload.get("expected_request_digest")
        job.request_authorization = request_authorization
        job.status = "PREPARED"
        job.variant_group_id = payload.get("variant_group_id")
        job.variant_index = payload.get("variant_index")
        # Capture the generation base before dispatch so the response, snapshot
        # and later AI_ACCEPT all refer to the same optimistic version.
        captured_chapter=self.chapters.get(job.chapter_id)
        job.base_chapter_version=captured_chapter.get("version")
        job.base_chapter_digest=chapter_digest(captured_chapter)
        if actor is not None:
            job.actor_id=actor.actor_id;job.session_id=actor.session_id;job.client_id=actor.client_id;job.workspace_id=actor.workspace_id;job.correlation_id=actor.effective_correlation_id
            if scope is not None:
                job.scope={"kind":scope.kind.value,"workspace_id":scope.workspace_id,"project_id":scope.project_id,"storyline_id":scope.storyline_id,"branch_id":scope.branch_id}
                job.scope_type=scope.kind.value;job.scope_id={"WORKSPACE":scope.workspace_id,"PROJECT":scope.project_id,"STORYLINE":scope.storyline_id,"BRANCH":scope.branch_id}[scope.kind.value]
        return job
    def create(self,operation,payload,actor=None,scope=None,request_authorization=None):
        job=self.prepare_job(operation,payload,actor,scope,request_authorization)
        return self.start_prepared(job)
    def stage_reviewed_variants(self, jobs):
        """Record the entire bounded review before the first adapter can run.

        Keep partial persistence evidence on failure. The batch coordinator will
        never fill missing members by replay after an uncertain staging/start.
        """
        if not 2 <= len(jobs) <= 3 or any(not job.reviewed_variant or not job.expected_request_digest
                or not callable(job.request_authorization) or job.status != "PREPARED" for job in jobs):
            raise ValueError("AUTHOR_VARIANT_REVIEW_REQUIRED")
        with self.lock:
            if any(job.id in self.jobs for job in jobs): raise ValueError("AUTHOR_VARIANT_ALREADY_RECORDED")
            for job in jobs:
                job.reviewed_variant_receipt_state = "NOT_RECORDED"
                self.jobs[job.id] = job
            for job in jobs:
                job.reviewed_variant_receipt_state = "RECORDED"
                try: self._persist(job)
                except Exception:
                    job.reviewed_variant_receipt_state = "PERSISTENCE_UNCERTAIN"
                    raise

    def start_prepared(self, job):
        """Start the exact validated instance once, never rebuild its payload."""
        from .experimental.character_author_context import is_character_job
        if job.status != "PREPARED": raise ValueError("GENERATION_JOB_NOT_PREPARED")
        validate_generation_bounds(job)
        job._generation_bounds = (job.generation_max_output_bytes, job.generation_deadline)
        if job.expected_request_digest and not callable(job.request_authorization):
            raise ValueError("AUTHOR_PREVIEW_SESSION_REQUIRED")
        if (job.partial_revision_only or job.revision_selection_binding is not None) and not callable(job.request_authorization):
            raise ValueError("REVISION_SELECTION_AUTHORITY_REQUIRED")
        if is_character_job(job) and not callable(job.character_context_resolver):
            raise ValueError("CHARACTER_CONTEXT_SESSION_REQUIRED")
        if job.before_dispatch is not None or job.on_terminal is not None:
            if not callable(job.before_dispatch) or not callable(job.on_terminal):
                raise ValueError("GENERATION_DISPATCH_HOOK_PAIR_REQUIRED")
            job.dispatch_hooks_required = True
        if job.dispatch_hooks_required and (not callable(job.before_dispatch) or not callable(job.on_terminal)):
            raise ValueError("GENERATION_DISPATCH_SESSION_REQUIRED")
        with self.lock:
            if job.id in self.jobs and not (job.reviewed_variant and self.jobs[job.id] is job):
                raise ValueError("GENERATION_JOB_ALREADY_STARTED")
            job.status = "QUEUED"
            self.jobs[job.id] = job
            try: self._persist(job)
            except Exception:
                if not job.reviewed_variant: self.jobs.pop(job.id, None)
                job.status = "PREPARED"
                raise
        try: threading.Thread(target=self._run,args=(job,),daemon=True).start()
        except Exception:
            job.status = "FAILED"; job.execution_outcome = "FAILED"; job.error_code = "GENERATION_START_FAILED"
            job.error = "生成未启动，请检查任务记录。"
            self._finish_terminal_hook(job)
            self._persist(job)
            raise
        return job
    def _emit(self,job,chunk=""):
        with job.condition:
            if chunk and not job.cancelled.is_set() and job.status not in self.terminal:job.output+=chunk
            job.updated_at=utc();job.condition.notify_all()
        self._persist(job)
    def _validate_outbound_sources(self, job, cloud):
        """Last-hop authority; queued copies never override current source policy."""
        from .source_privacy import effective_source_privacy, assert_project_source_policies
        require_generation_content(job)
        branch_id=(job.scope or {}).get("branch_id")
        chapter = self.chapters.get(job.chapter_id)
        if chapter.get("novel_id", job.novel_id) != job.novel_id:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "章节不属于当前项目")
        if job.base_chapter_version is not None and chapter.get("version") != job.base_chapter_version:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "章节已改变，请重新生成")
        if job.expected_request_digest and chapter_digest(chapter) != job.base_chapter_digest:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "正文内容已改变，请重新检查。")
        if cloud and job.profile == "LOCAL_ONLY":
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "仅本地创作模式不允许云模型，请明确切换创作模式后重试。")
        if cloud and job.source and not saved_source_matches(chapter, job.source):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "所选文本不属于已审核正文，请重新选择。")
        if cloud and effective_source_privacy(chapter,branch_id) != "CLOUD_ALLOWED":
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "正文尚未明确允许云端使用，请选择本地模型或先审核正文隐私。")
        if cloud:
            try:
                assert_project_source_policies(getattr(self.contexts, "novels", None), job.novel_id)
            except ValueError as exc:
                raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, str(exc)) from exc
        if job.actor_id and job.scope:
            from .dependencies import membership_authorization_service
            from .authorization import ModalityDomain
            session=SessionContext(job.session_id or "",job.client_id or "",job.actor_id,job.workspace_id or "",job.correlation_id)
            actor=ActorContext(job.actor_id,job.workspace_id or "",session,job.correlation_id)
            raw=job.scope
            scope=AuthorizationScope(ScopeKind(raw["kind"]),raw["workspace_id"],raw.get("project_id"),raw.get("storyline_id"),raw.get("branch_id"))
            membership_authorization_service.require(actor,"domain.read",ModalityDomain.NOVEL,scope)
        if job.creation_records:
            from .api import creation_workbench_service
            if job.scope:
                record_scope={"mode":"collaboration","novel_id":job.novel_id,"workspace_id":job.scope["workspace_id"],"storyline_id":job.scope.get("storyline_id"),"branch_id":job.scope.get("branch_id")}
            else:
                record_scope=creation_workbench_service.local_scope(job.novel_id)
            for approved in job.creation_records:
                current=creation_workbench_service.get_record(job.novel_id,record_scope,approved["id"])
                if current.get("version") != approved.get("version") or current.get("status") != "APPROVED":
                    raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST,"创作方案已改变或撤销审核，请重新选择。")
                if cloud and normalize_privacy(current.get("privacy_level")) != "CLOUD_ALLOWED":
                    raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST,"创作方案限制云端使用。")
                for chapter_id,version in current.get("source_versions",{}).items():
                    source=self.chapters.get(chapter_id)
                    if source.get("version") != version or (cloud and effective_source_privacy(source,branch_id) != "CLOUD_ALLOWED"):
                        raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST,"创作方案引用的正文版本或隐私已改变。")
        if cloud:
            from .source_privacy import assert_current_manuscript_egress
            assert_current_manuscript_egress(self.chapters, getattr(self.contexts,"novels",None), job.novel_id, chapter, branch_id)
        return chapter

    def prepare_author_request(self, job, route):
        cloud = runtime.is_remote_text_provider(route.provider)
        chapter = self._validate_outbound_sources(job, cloud)
        from .experimental.character_author_context import is_character_job, resolve_character_author_context
        if is_character_job(job):
            context = resolve_character_author_context(job, cloud=cloud)
        elif automatic_context_allowed(job):
            context = self.contexts.for_chapter(job.chapter_id, job.instruction, cloud, job.operation)
        else:
            context = {}
        if job.request_scope is not None and not is_character_job(job):
            from .author_context_sources import apply_source_controls
            context, job.author_source_manifest = apply_source_controls(context, job.novel_id,
                (job.request_scope or {}).get("source_items") if automatic_context_allowed(job) else None,
                omit_dependents=automatic_context_allowed(job) and (not job.request_scope.get("include_style_reference", True)
                    or not job.request_scope.get("include_plan_reference", True)))
        request = build_author_request(job, route, chapter, context,
            dispatch_guard=lambda: self._guard_author_request(job, route, dispatch=True))
        if job.expected_request_digest and request_digest(request, job, cloud) != job.expected_request_digest:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "预检内容、来源或授权已改变，请重新检查后生成。")
        return chapter, dict(request.context), request

    def _guard_author_request(self, job, route, *, dispatch=False):
        check_generation_bounds(job)
        cloud = runtime.is_remote_text_provider(route.provider)
        self._validate_outbound_sources(job, cloud)
        from .experimental.character_author_context import is_character_job, resolve_character_author_context
        if is_character_job(job): resolve_character_author_context(job, cloud=cloud)
        if job.cancelled.is_set():
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "生成已取消，请重新检查。")
        if job.dispatch_hooks_required and (not callable(job.before_dispatch) or not callable(job.on_terminal)):
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "调度会话不可恢复，请重新预检。")
        if job.expected_request_digest:
            from .experimental.flags import require_flag
            require_flag("author_context_inspector_v2")
            if not callable(job.request_authorization):
                raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "预检会话不可恢复，请重新检查。")
            job.request_authorization()
            if job.cancelled.is_set():
                raise ModelRuntimeError(RuntimeErrorCode.INVALID_REQUEST, "生成已取消，请重新检查。")
            # Late context/prompt/approval changes cannot ride an earlier receipt.
            self.prepare_author_request(job, route)
        # Only the actual adapter-facing guard marks budget dispatch. Ordinary
        # preflight and request assembly never invoke this side-effect hook.
        if dispatch and callable(job.before_dispatch): job.before_dispatch()

    def _finish_terminal_hook(self, job):
        if job._terminal_hook_called: return
        if not callable(job.on_terminal):
            if job.dispatch_hooks_required:
                job.terminal_hook_status = "MISSING_RECONCILIATION_REQUIRED"
                try: self._persist(job)
                except Exception: job.terminal_hook_status = "PERSISTENCE_UNCERTAIN_RECONCILIATION_REQUIRED"
            return
        job._terminal_hook_called = True
        if job.execution_outcome is None:
            job.execution_outcome = job.status if job.status in {"COMPLETED", "CANCELLED", "FAILED"} else "UNKNOWN"
        try:
            job.on_terminal()
            job.terminal_hook_status = "COMPLETED"
        except Exception:
            # A lost settlement never releases a reservation or triggers replay.
            # Retain output for review while surfacing the accounting blocker.
            job.terminal_hook_status = "FAILED_RECONCILIATION_REQUIRED"
            if job.status not in {"ACCEPTING", "ACCEPTED", "ACCEPTANCE_UNCERTAIN", "REJECTED"}:
                job.status = "FAILED"
            job.error_code = "TERMINAL_RECONCILIATION_REQUIRED"
            job.error = "模型任务已结束，但用量结算未确认。请核对调度记录，不要自动重试。"
        try: self._persist(job)
        except Exception:
            job.terminal_hook_status = "PERSISTENCE_UNCERTAIN_RECONCILIATION_REQUIRED"

    def _run(self,job):
        started=time.monotonic()
        try:
            if job.cancelled.is_set():job.status="CANCELLED";job.execution_outcome="CANCELLED";self._emit(job);return
            job.status="GENERATING";self._emit(job)
            role=AUTHOR_ROLES[job.operation]
            router=runtime.router(job.profile,role)
            if job.requested_provider and job.requested_model:router.routes[role]=[Route(job.requested_provider,job.requested_model)]
            last=None
            for route in router.routes[role]:
                dispatched=False
                cloud=runtime.is_remote_text_provider(route.provider)
                decision={"provider":route.provider,"model":route.model,"cloud":cloud,"status":"PREFLIGHT"}
                job.route_decisions.append(decision)
                try:
                    if job.cancelled.is_set():job.status="CANCELLED";job.execution_outcome="CANCELLED";self._emit(job);return
                    if job.expected_request_digest:
                        self._guard_author_request(job, route)
                    if not runtime.packaged_author_route_ready(route.provider):
                        raise ModelRuntimeError(RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED,"未配置可用文本模型，请先在设置中配置文本 Provider。",provider_id=route.provider)
                    node=runtime.prepare_text_route(route.provider,route.model)
                    ch, context, request = self.prepare_author_request(job, route)
                    if self.snapshot_required:
                        snapshot=self.contexts.save_snapshot(job.chapter_id,ch.get("version",0),context,f"{role}:v1",route.model,actor_id=job.actor_id,session_id=job.session_id,scope_type=job.scope_type,scope_id=job.scope_id,generation_id=job.id,cloud=cloud)
                        if not snapshot:raise RuntimeError("Context snapshot persistence is required")
                        job.context_snapshot_id=snapshot["id"];self._persist(job)
                    # Recheck after potentially slow context/snapshot assembly.
                    self._guard_author_request(job, route)
                    completed=False;dispatched=True;decision["status"]="DISPATCHED"
                    for event in node.stream(TextModelNodeInput(request)):
                        if event.event_type=="generation.cancelled" or job.cancelled.is_set():job.status="CANCELLED";job.execution_outcome="CANCELLED";self._emit(job);return
                        if event.event_type=="generation.failed":raise ModelRuntimeError(event.error_code or RuntimeErrorCode.GENERATION_FAILED,"生成失败，请审核已有输出后重试")
                        if event.event_type=="generation.delta" and event.delta:
                            check_generation_bounds(job, delta=event.delta)
                            self._emit(job,event.delta)
                        if event.event_type=="generation.completed":
                            check_generation_bounds(job, completion_text=event.response.text if event.response else None)
                            completed=True
                            if event.response:
                                job.usage=asdict(event.response.usage) if event.response.usage else None
                                job.usage_status="REPORTED" if event.response.usage else "UNKNOWN"
                                job.execution_mode=event.response.execution_mode
                                job.provider_reference_id=event.response.provider_reference_id
                    if not completed:raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED,"模型连接中断，草稿未完成")
                    job.provider=route.provider;job.model=route.model;decision["status"]="COMPLETED";break
                except Exception as exc:
                    decision["status"]="FAILED";decision["error_code"]=exc.code.value if isinstance(exc,ModelRuntimeError) else "PREFLIGHT_FAILED"
                    last=exc
                    # Never combine partial drafts or silently replay a request
                    # whose remote billing/result is ambiguous.
                    if dispatched or job.output or job.requested_provider or cloud:raise
            else:raise last or RuntimeError("No provider route")
            if job.cancelled.is_set():job.status="CANCELLED";job.execution_outcome="CANCELLED";self._emit(job);return
            if role=="writer" and not self.snapshot_required:self.contexts.save_snapshot(job.chapter_id,ch.get("version",0),context,"writer:v1",job.model or "unknown")
            check_generation_bounds(job)
            job.issues=deterministic_review(job.output,context);job.latency_ms=int((time.monotonic()-started)*1000)
            if job.cancelled.is_set():job.status="CANCELLED";job.execution_outcome="CANCELLED";self._emit(job);return
            with job.condition:
                job.status="COMPLETED";job.execution_outcome="COMPLETED"
                # Settle and persist under the same in-process transition lock
                # that acceptance uses. Readers see SETTLING until this ends.
                self._finish_terminal_hook(job)
                self._emit(job)
            runtime_log.write(generation_id=job.id,novel_id=job.novel_id,chapter_id=job.chapter_id,agent=role,provider=job.provider,model=job.model,status=job.status,latency_ms=job.latency_ms)
        except Exception as exc:
            if job.status in {"ACCEPTING", "ACCEPTED", "ACCEPTANCE_UNCERTAIN", "REJECTED"}:
                return  # A late logging/accounting failure cannot undo review.
            if job.generation_bound_failure:
                job.output="";job.status="FAILED";job.execution_outcome="FAILED";job.error_code=job.generation_bound_failure
                job.error="生成超出已审核的时间或输出限额，未完成内容已丢弃。"
                self._emit(job);return
            if job.cancelled.is_set():job.status="CANCELLED";job.execution_outcome="CANCELLED";self._emit(job);return
            if isinstance(exc,ModelRuntimeError):safe_error=exc.safe_message;error_code=exc.code.value
            elif isinstance(exc,RuntimeError) and "snapshot" in str(exc).casefold():safe_error="Context snapshot failed";error_code="CONTEXT_SNAPSHOT_FAILED"
            else:safe_error="生成失败，请稍后重试";error_code=RuntimeErrorCode.GENERATION_FAILED.value
            job.latency_ms=int((time.monotonic()-started)*1000);job.status="FAILED";job.execution_outcome=job.execution_outcome or "FAILED";job.error=safe_error;job.error_code=error_code;self._emit(job)
            runtime_log.write(generation_id=job.id,novel_id=job.novel_id,chapter_id=job.chapter_id,status=job.status,error=error_code,latency_ms=job.latency_ms)
        finally:
            self._finish_terminal_hook(job)
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
            if not generation_content_available(job): return
            with job.condition:
                if len(job.output)==sent and job.public()["status"] not in self.terminal:job.condition.wait(timeout=10)
                if not generation_content_available(job): return
                chunk=job.output[sent:];sent=len(job.output);status=job.public()["status"]
            yield "data: "+json.dumps({"job_id":jid,"status":status,"chunk":chunk,"provider":job.provider,"model":job.model,"error":job.error,"error_code":job.error_code},ensure_ascii=False)+"\n\n"
            if status in self.terminal:return
    def accept(self,jid,accepted_output=None,actor=None,scope=None,expected_version=None):
        from .repositories.file.mutation_coordinator import workspace_mutation
        from .repositories.chapter_repository import VersionConflict
        from pathlib import Path

        # The shared coordinator combines a process lock with an OS file lock.
        # All managers on this host use the same persisted-job namespace, not a
        # manager-local threading lock. Re-read durable state inside that lock.
        persistence_repository = getattr(self.persistence, "repository", self.persistence)
        lock_root = getattr(persistence_repository, "root", None) or Path(settings.novel_data) / "runtime/jobs"
        with workspace_mutation(Path(lock_root), f"generation-accept:{jid}"):
            job = self.get(jid)
            with job.condition:
                require_generation_content(job)
                require_whole_generation_acceptance(job)
                require_generation_accounting(job)
                read = getattr(self.persistence, "get", None)
                try:
                    stored = read(jid) if callable(read) else None
                except KeyError:
                    stored = None  # Compatibility with explicitly injected drafts.
                if stored is not None:
                    for key, value in stored.items():
                        if key in Job.__dataclass_fields__ and key not in self.transient_fields:
                            setattr(job, key, value)
                require_generation_content(job)
                require_whole_generation_acceptance(job)
                require_generation_accounting(job)
                if job.status != "COMPLETED":
                    raise ValueError("Only completed drafts can be accepted; an interrupted acceptance requires manual review")
                chapter = self.chapters.get(job.chapter_id)
                # Caller-supplied versions may narrow the precondition, never rebase
                # an old generation onto a newer manuscript. Legacy continuations
                # create a new chapter; legacy replacements without a base fail shut.
                target_version = job.base_chapter_version
                if target_version is None:
                    if job.operation != "continue":
                        raise ValueError("Draft generation base is missing; regenerate before accepting")
                    target_version = chapter["version"]
                if chapter["version"] != target_version or (expected_version is not None and expected_version != target_version):
                    raise VersionConflict(chapter, resource_id=job.chapter_id, expected_version=target_version)
                # Persist before the first side effect. If the process dies, ACCEPTING
                # is deliberately not replayable: a chapter may already exist. A
                # subsequent manager must reconcile it rather than write it twice.
                job.status = "ACCEPTING"
                self._persist(job)
                try:
                    return self._accept_claimed(job, chapter, target_version, accepted_output, actor, scope)
                except Exception:
                    job.status = "ACCEPTANCE_UNCERTAIN"
                    job.error_code = "ACCEPTANCE_REVIEW_REQUIRED"
                    job.error = "采用操作未能完整确认，正文可能已保存。请检查正文及待审核 Canon，勿重复采用。"
                    try:
                        self._emit(job)
                    except Exception:
                        pass  # The durable ACCEPTING claim still prevents replay.
                    raise

    def _accept_claimed(self,job,chapter,target_version,accepted_output=None,actor=None,scope=None):
        require_generation_content(job)
        require_whole_generation_acceptance(job)
        jid = job.id
        original=chapter["content"];output=accepted_output if accepted_output is not None else job.output;content=(original+"\n\n"+output) if job.operation=="continue" else (original.replace(job.source,output,1) if job.operation=="rewrite" and job.source in original else output)
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
                        {"title": title, "content": f"{original}\n\n{output}", "version": target_version, "source": "AI_ACCEPT"},
                    )
            self.chapters.save_summary(job.novel_id, saved.get("number", chapter["number"] + 1), output[:240])
            pending_canon={"id":str(uuid.uuid5(uuid.NAMESPACE_URL, f"novel-generation-accept:{jid}")),"novel_id":job.novel_id,"chapter":saved.get("number", chapter["number"] + 1),"status":"PENDING","proposals":[{"fact":"AI draft introduced a possible lasting story fact","source_job":jid}],"source":"archivist"}
            self.canon.save_pending(pending_canon)
            job.status="ACCEPTED";self._emit(job)
            return {"chapter": saved, "pending_canon": pending_canon}
        if actor is not None and scope is not None:
            saved=self.collaboration_updates.update_chapter(actor=actor,scope=scope,chapter_id=job.chapter_id,document=__import__("app.document",fromlist=["markdown_to_document"]).markdown_to_document(content),expected_version=target_version,reason="AI_ACCEPT")
        elif job.actor_id and job.scope:
            session=SessionContext(job.session_id or "",job.client_id or "",job.actor_id,job.workspace_id or "",job.correlation_id)
            stored_actor=ActorContext(job.actor_id,job.workspace_id or "",session,job.correlation_id);raw=job.scope;stored_scope=AuthorizationScope(ScopeKind(raw["kind"]),raw["workspace_id"],raw.get("project_id"),raw.get("storyline_id"),raw.get("branch_id"))
            saved=self.collaboration_updates.update_chapter(actor=stored_actor,scope=stored_scope,chapter_id=job.chapter_id,document=__import__("app.document",fromlist=["markdown_to_document"]).markdown_to_document(content),expected_version=target_version,reason="AI_ACCEPT")
        else:saved=self.chapters.save(job.chapter_id,{"content":content,"version":target_version,"source":"AI_ACCEPT"})
        self.chapters.save_summary(job.novel_id,chapter["number"],content[:240]);pending={"id":str(uuid.uuid5(uuid.NAMESPACE_URL, f"novel-generation-accept:{jid}")),"novel_id":job.novel_id,"chapter":chapter["number"],"status":"PENDING","proposals":[{"fact":"AI draft introduced a possible lasting story fact","source_job":jid}],"source":"archivist"};self.canon.save_pending(pending);job.status="ACCEPTED";self._emit(job)
        try:self.memory_extractor.enqueue(job.novel_id,job.chapter_id,saved["version"],job.profile)
        except Exception:pass
        return {"chapter":self.chapters.get(job.chapter_id),"pending_canon":pending}
    def reject(self,jid):
        from .repositories.file.mutation_coordinator import workspace_mutation
        from pathlib import Path
        persistence_repository = getattr(self.persistence, "repository", self.persistence)
        lock_root = getattr(persistence_repository, "root", None) or Path(settings.novel_data) / "runtime/jobs"
        with workspace_mutation(Path(lock_root), f"generation-accept:{jid}"):
            job = self.get(jid)
            with job.condition:
                require_generation_content(job)
                read = getattr(self.persistence, "get", None)
                try:
                    stored = read(jid) if callable(read) else None
                except KeyError:
                    stored = None
                if stored is not None and stored.get("status") in {"ACCEPTING", "ACCEPTED", "ACCEPTANCE_UNCERTAIN"}:
                    raise ValueError("An accepted or uncertain draft cannot be rejected")
                if job.status in {"ACCEPTING", "ACCEPTED", "ACCEPTANCE_UNCERTAIN"}:
                    raise ValueError("An accepted or uncertain draft cannot be rejected")
                job.status="REJECTED";self._emit(job);return job
    def diff(self,jid):job=self.get(jid);require_generation_content(job);original=job.source or self.chapters.get(job.chapter_id)["content"];return "\n".join(difflib.unified_diff(original.splitlines(),job.output.splitlines(),fromfile="original",tofile="generated",lineterm=""))
jobs=JobManager()
