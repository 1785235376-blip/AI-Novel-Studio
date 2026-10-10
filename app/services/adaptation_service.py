"""Revisioned adaptation proposals on the original NovelRepository authority.

Creation/apply intents are persisted before touching manuscript owners. Unknown
outcomes are never replayed. Real model admission is deliberately unavailable
until this workflow can bind the original JobManager/broker preview contract.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import hashlib
import json
import re
from ..document import document_to_markdown, markdown_to_document
from ..repositories.adaptation_versions import check_revision, reserve_transitions, MAX_SOURCE_CHAPTERS, MAX_ATTEMPTS
from ..repositories.chapter_repository import VersionConflict
from ..model_runtime import TextGenerationParameters, TextGenerationRequest, TextModelNodeInput, ModelRuntimeError

FEATURE = "adaptation_lifecycle_v1"

def now(): return datetime.now(timezone.utc).isoformat()
def digest(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
def body_text(document): return re.sub(r"^#{1,6}\s+[^\n]+\n+", "", document_to_markdown(document).strip(), count=1).strip()
def approval_binding(item):
    return digest({key:item.get(key) for key in ("blueprint","source_digest","target","instruction")})

def review_binding(item,task):
    return digest({"proposal_id":item["id"],"blueprint_revision":item.get("blueprint_revision"),
        "approved_binding":item.get("approved_binding"),"source_scope":item.get("source_scope"),
        "target_scope":item.get("adapted_scope"),"task":{key:task.get(key) for key in
        ("source_chapter_id","source_version","source_digest","target_chapter_id","target_version","target_digest")}})

def enabled():
    from ..experimental.flags import enabled_flags
    return FEATURE in enabled_flags()

TARGETS={"COMMERCIAL","LITERARY","SCREEN","CUSTOM"}
PROFILES={
    "COMMERCIAL":{"focus":"强化冲突、悬念与章节钩子","pacing":"加快关键事件推进","format":"长篇商业小说","constraints":["保留核心人物关系","每章建立明确目标与转折"]},
    "LITERARY":{"focus":"深化人物心理、主题与语言质感","pacing":"允许内省与意象形成节奏","format":"文学小说","constraints":["保留主题核心","避免用情节压缩替代人物变化"]},
    "SCREEN":{"focus":"将叙述转换为可见行动、场景与对白","pacing":"按场景冲突和幕结构重组","format":"影视改编蓝图","constraints":["不可拍摄的内心叙述需外化","保留关键因果链"]},
    "CUSTOM":{"focus":"遵循用户指定的风格与结构要求","pacing":"由改编要求决定","format":"自定义版本","constraints":["未明确要求的核心事实保持不变"]},
}

class AdaptationService:
    def __init__(self, novels, chapters, runtime=None, agent_runner=None):
        self.novels, self.chapters, self.runtime, self.agent_runner = novels, chapters, runtime, agent_runner
        self.branch_authority = None

    def list(self, novel_id, branch_id=None):
        return [row for row in self.novels.list_adaptation_proposals(novel_id) if row.get("branch_id") == branch_id]

    def get(self, novel_id, proposal_id, branch_id=None):
        item = next((row for row in self.list(novel_id, branch_id) if row["id"] == proposal_id), None)
        if item is None: raise FileNotFoundError(proposal_id)
        return item

    def _save(self, item, changes, check=None, *, finalize=False):
        if check: check()
        return self.novels.save_adaptation_proposal(item["novel_id"], {**item, **changes, "updated_at": now()},
            expected_revision=item.get("revision", 0), check=check, finalize=finalize)

    def _read(self, nid, pid, branch_id, expected_revision):
        item = self.get(nid, pid, branch_id)
        check_revision(item, expected_revision)
        if item.get("lifecycle_version") and not enabled():
            from ..experimental.flags import require_flag
            require_flag(FEATURE)
        return item

    def _chapters(self, item, target=False):
        scope = item.get("adapted_scope" if target else "source_scope")
        if scope and scope.get("branch_id") and (item.get("branch_authority") or target and callable(self.branch_authority)):
            from ..experimental.flags import require_flag
            require_flag("branch_manuscript_v1")
            if not callable(self.branch_authority): raise ValueError("BRANCH_MANUSCRIPT_NOT_CONFIGURED")
            view = self.branch_authority(scope)
            return getattr(view, "repository", view)
        return self.chapters

    def _source(self, item, source, *, current_required=False):
        owner = self._chapters(item)
        current = owner.get(source["chapter_id"])
        if current.get("novel_id") != item["novel_id"]: raise FileNotFoundError(source["chapter_id"])
        snapshot = next((row for row in item.get("source_snapshots", []) if row["chapter_id"] == source["chapter_id"]), None)
        if snapshot is None:
            document = current["document"] if current["version"] == source["version"] else next((row["document"] for row in owner.history(source["chapter_id"]) if row["version"] == source["version"]), None)
            if document is None: raise ValueError("SOURCE_SNAPSHOT_UNAVAILABLE")
            snapshot = {"chapter_id": source["chapter_id"], "title": current["title"], "version": source["version"], "document": document, "digest": digest(document)}
        if digest(snapshot["document"]) != snapshot["digest"]: raise ValueError("SOURCE_DIGEST_CHANGED")
        if current_required and (current["version"] != source["version"] or digest(current["document"]) != snapshot["digest"]):
            raise VersionConflict({"id": source["chapter_id"], "version": current["version"]}, expected_version=source["version"])
        return deepcopy(snapshot)

    def create(self, novel_id, target, title="", instruction="", branch_id=None, source_scope=None, check=None):
        target = target.upper()
        if target not in TARGETS: raise ValueError("unsupported adaptation target")
        if check: check()
        novel = self.novels.get(novel_id)
        shell = {"novel_id": novel_id, "source_scope": source_scope, "branch_authority": bool(branch_id and callable(self.branch_authority))}
        chapters = self._chapters(shell).list(novel_id)
        if len(chapters)>MAX_SOURCE_CHAPTERS:raise ValueError("ADAPTATION_CAPACITY_SOURCE_LIMIT")
        if len(title)>200 or len(instruction)>8000:raise ValueError("ADAPTATION_INPUT_LIMIT")
        snapshots = []
        for listed in chapters:
            row = self._chapters(shell).get(listed["id"])
            snapshots.append({"chapter_id":row["id"], "version":row["version"], "title":row["title"], "document":deepcopy(row["document"]), "digest":digest(row["document"])})
        profile = PROFILES[target]
        action = {"COMMERCIAL":"强化本章冲突与结尾钩子", "LITERARY":"深化本章视角人物与主题意象", "SCREEN":"拆分为可拍摄场景并外化人物行动", "CUSTOM":"按自定义要求改写并保持事实连续"}[target]
        blueprint = {**profile, "chapter_map":[{"source_chapter_id":c["chapter_id"], "source_title":c["title"], "sequence":i, "action":action, "unit":f"第{((i-1)//3)+1}集" if target == "SCREEN" else f"第{i}章"} for i,c in enumerate(snapshots,1)]}
        item = {**shell,"id":str(uuid4()),"branch_id":branch_id,"source_title":novel["title"],"source_chapter_count":len(snapshots),"source_versions":[{"chapter_id":c["chapter_id"],"version":c["version"]} for c in snapshots],"source_snapshots":snapshots,"source_digest":digest(snapshots),"target":target,"title":title.strip() or f"{novel['title']} 改编方案","instruction":instruction.strip(),"blueprint":blueprint,"blueprint_revision":1,"blueprint_history":[],"status":"DRAFT","created_at":now(),"updated_at":now(),"lifecycle_version":1 if enabled() else None,"model_runtime":"NOT_CONFIGURED","automatic_resume":False}
        return self.novels.save_adaptation_proposal(novel_id,item,expected_revision=0,check=check)

    def update_blueprint(self,nid,pid,payload,branch_id=None,expected_revision=None,check=None):
        item = self._read(nid,pid,branch_id,expected_revision)
        if item["status"] != "DRAFT": raise ValueError("approved adaptation blueprint is frozen")
        current=item["blueprint"]; incoming={row.get("source_chapter_id"):row for row in payload.get("chapter_map",[]) if row.get("source_chapter_id")}
        chapter_map=[{**row,"unit":str(incoming.get(row["source_chapter_id"],{}).get("unit",row["unit"]))[:120],"action":str(incoming.get(row["source_chapter_id"],{}).get("action",row["action"]))[:1000]} for row in current["chapter_map"]]
        blueprint={"focus":payload["focus"].strip()[:1000],"pacing":payload["pacing"].strip()[:1000],"format":payload["format"].strip()[:200],"constraints":[str(value).strip()[:500] for value in payload.get("constraints",[]) if str(value).strip()][:50],"chapter_map":chapter_map}
        return self._save(item,{"blueprint":blueprint,"blueprint_revision":item.get("blueprint_revision",1)+1,"blueprint_history":[*item.get("blueprint_history",[]),{"revision":item.get("blueprint_revision",1),"blueprint":current,"saved_at":item["updated_at"]}]},check)

    def approve(self,nid,pid,branch_id=None,expected_revision=None,check=None):
        item=self._read(nid,pid,branch_id,expected_revision)
        if item["status"] != "DRAFT": raise ValueError("adaptation proposal is already decided")
        for source in item["source_versions"]: self._source(item,source,current_required=True)
        return self._save(item,{"status":"APPROVED","approved_binding":approval_binding(item),"approved_at":now()},check)

    def snapshot_chapters(self,nid,pid,branch_id=None):
        item=self.get(nid,pid,branch_id)
        if item["status"] not in {"APPROVED","MATERIALIZING","MATERIALIZED"}: raise ValueError("adaptation proposal must be approved")
        return [self._source(item,source) for source in item["source_versions"]]

    def _claim(self,nid,pid,branch_id,token):
        item=self.get(nid,pid,branch_id)
        if item.get("operation_token") != token or item["status"] != "MATERIALIZING": raise ValueError("ADAPTATION_CLAIM_LOST")
        return item

    def materialize(self,nid,pid,branch_id=None,expected_revision=None,check=None,create_project=None,create_chapter=None,save_chapter=None):
        item=self._read(nid,pid,branch_id,expected_revision)
        if item["status"] == "MATERIALIZED":
            if check:check()
            target=self.novels.get(item["adapted_novel_id"])
            return {**target,**({"scope":item["adapted_scope"]} if item.get("adapted_scope") else {})}
        if item["status"] != "APPROVED": raise ValueError("ADAPTATION_RECOVERY_REQUIRED" if item["status"] in {"MATERIALIZING","RECOVERY_REQUIRED"} else "adaptation proposal must be approved")
        snapshots=self.snapshot_chapters(nid,pid,branch_id)
        binding=approval_binding(item)
        if item.get("approved_binding") and binding != item["approved_binding"]: raise ValueError("ADAPTATION_APPROVAL_CHANGED")
        reserve_transitions(item,3*len(snapshots)+5)
        token=str(uuid4());checkpoint=deepcopy(item.get("materialization") or {"operation_id":str(uuid4()),"project_id":str(uuid4()),"storyline_id":str(uuid4()),"branch_id":str(uuid4()),"phase":"PLANNED","chapters":[]})
        item=self._save(item,{"status":"MATERIALIZING","operation_token":token,"materialization":checkpoint},check)
        try:
            if not item.get("adapted_novel_id"):
                checkpoint.update(phase="PROJECT_WRITE_INTENT")
                item=self._save(item,{"materialization":checkpoint},check)
                if check:check()
                target=create_project(item) if create_project else self.novels.create({"id":checkpoint["project_id"],"title":item["title"],"genre":f"Adaptation:{item['target']}"})
                item=self._claim(nid,pid,branch_id,token);checkpoint.update(phase="PROJECT_COMMITTED",project_id=target["id"])
                item=self._save(item,{"adapted_novel_id":target["id"],"adapted_scope":target.get("scope"),"materialization":checkpoint},check)
            for index,snapshot in enumerate(snapshots):
                if index < len(checkpoint["chapters"]) and checkpoint["chapters"][index].get("phase") == "COMMITTED": continue
                item=self._claim(nid,pid,branch_id,token)
                checkpoint.update(phase="CHAPTER_WRITE_INTENT",source_chapter_id=snapshot["chapter_id"])
                item=self._save(item,{"materialization":checkpoint},check)
                if check:check()
                target=create_chapter(item,snapshot) if create_chapter else self.chapters.create(item["adapted_novel_id"],{"title":snapshot["title"],"content":"","number":index+1})
                target=self._chapters(item,True).get(target["id"])
                item=self._claim(nid,pid,branch_id,token)
                receipt={"source_chapter_id":snapshot["chapter_id"],"target_chapter_id":target["id"],"version":target["version"],"phase":"DOCUMENT_WRITE_INTENT"}
                checkpoint["chapters"].append(receipt);checkpoint["phase"]="DOCUMENT_WRITE_INTENT"
                item=self._save(item,{"materialization":checkpoint},check)
                if check:check()
                saved=save_chapter(item,target["id"],snapshot["document"],target["version"]) if save_chapter else self.chapters.save(target["id"],snapshot["document"],target["version"],"ADAPTATION_SNAPSHOT")
                item=self._claim(nid,pid,branch_id,token);receipt.update(phase="COMMITTED",version=saved["version"],digest=digest(saved["document"]));checkpoint["phase"]="CHAPTER_COMMITTED"
                item=self._save(item,{"materialization":checkpoint},check)
            manifest=[]
            for index,(source,receipt) in enumerate(zip(item["source_versions"],checkpoint["chapters"])):
                mapping=item["blueprint"]["chapter_map"][index]
                manifest.append({"id":str(uuid4()),"source_chapter_id":source["chapter_id"],"source_version":source["version"],"source_digest":snapshots[index]["digest"],"target_chapter_id":receipt["target_chapter_id"],"target_version":receipt["version"],"target_digest":receipt["digest"],"unit":mapping["unit"],"action":mapping["action"],"status":"PENDING_REWRITE"})
            checkpoint["phase"]="COMPLETED"
            item=self._save(item,{"status":"MATERIALIZED","operation_token":None,"materialization":checkpoint,"execution_manifest":manifest,"execution_status":"PENDING_REWRITE","materialized_at":now()},check,finalize=True)
            target=self.novels.get(item["adapted_novel_id"])
            return {**target,**({"scope":item["adapted_scope"]} if item.get("adapted_scope") else {})}
        except Exception:
            latest=self.get(nid,pid,branch_id)
            if latest.get("operation_token") == token:
                self._save(latest,{"status":"RECOVERY_REQUIRED","operation_token":None,"error_code":"MATERIALIZATION_OUTCOME_UNCERTAIN"},finalize=True)
            raise

    def _task(self,item,tid):
        tasks=deepcopy(item.get("execution_manifest",[]));index=next((i for i,row in enumerate(tasks) if row["id"]==tid),None)
        if index is None: raise FileNotFoundError(tid)
        return tasks,index,tasks[index]

    def _save_task(self,item,tasks,index,changes,check=None):
        finalize=tasks[index]["status"] in {"RUNNING","APPLYING"} or changes.get("status") in {"CANCELLED","RECOVERY_REQUIRED","APPLIED"}
        tasks[index]={**tasks[index],**changes}
        statuses={row["status"] for row in tasks}
        overall=next(iter(statuses)) if len(statuses)==1 else "IN_PROGRESS"
        saved=self._save(item,{"execution_manifest":tasks,"execution_status":overall},check,finalize=finalize)
        return {**saved["execution_manifest"][index],"proposal_revision":saved["revision"]}

    def _task_claim(self,nid,pid,tid,branch_id,token,status="RUNNING"):
        item=self.get(nid,pid,branch_id);tasks,index,task=self._task(item,tid)
        if task.get("execution_token")!=token or task["status"]!=status: raise ValueError("ADAPTATION_CLAIM_LOST")
        return item,tasks,index,task

    def generate_draft(self,nid,pid,tid,mode="deterministic",provider=None,model=None,branch_id=None,reauthorize=None,expected_revision=None):
        item=self._read(nid,pid,branch_id,expected_revision);tasks,index,task=self._task(item,tid)
        if task["status"] not in {"PENDING_REWRITE","REJECTED","FAILED","NOT_CONFIGURED"}: raise ValueError("adaptation task is not ready for generation")
        if int(task.get("generation_attempts",0))>=MAX_ATTEMPTS:raise ValueError("ADAPTATION_CAPACITY_ATTEMPT_LIMIT")
        reserve_transitions(item,3)
        if reauthorize:reauthorize()
        source=self._source(item,{"chapter_id":task["source_chapter_id"],"version":task["source_version"]},current_required=True)
        target=self._chapters(item,True).get(task["target_chapter_id"])
        token=str(uuid4())
        self._save_task(item,tasks,index,{"status":"RUNNING","generation_attempts":int(task.get("generation_attempts",0))+1,"execution_token":token,"draft":None,"error_code":None,"target_version":target["version"],"target_digest":digest(target["document"]),"source_digest":source["digest"],"generation_started_at":now()},reauthorize)
        try:
            def dispatch_guard():
                if reauthorize:reauthorize()
                current,_,_,_=self._task_claim(nid,pid,tid,branch_id,token)
                self._source(current,{"chapter_id":task["source_chapter_id"],"version":task["source_version"]},current_required=True)
            dispatch_guard()
            if mode=="model":
                from ..config import settings
                from ..providers import MockProvider
                # This is a host-owned synthetic contract test, never an alternative
                # real model executor or implicit cloud/privacy approval.
                adapter=(getattr(getattr(self.runtime,"_deepseek_provider_adapter",None),"provider",None) if provider=="deepseek" else getattr(self.runtime,"providers",{}).get(provider))
                synthetic=bool(settings.mock_provider and not settings.enable_packaged_runtime and isinstance(adapter,MockProvider) and not self.runtime.is_remote_text_provider(provider))
                if not synthetic:
                    current,rows,i,_=self._task_claim(nid,pid,tid,branch_id,token)
                    return self._save_task(current,rows,i,{"status":"NOT_CONFIGURED","execution_token":None,"error_code":"ADAPTATION_MODEL_ADMISSION_NOT_CONFIGURED","runtime_status":"NOT_CONFIGURED","error":"真实模型改写尚未接入任务准入与预算预检。"},reauthorize)
                if not model: raise ValueError("model generation requires provider and model")
                context={"adaptation_target":item["target"],"blueprint":item["blueprint"],"unit":task["unit"],"action":task["action"],"source_chapter_id":task["source_chapter_id"],"source_version":task["source_version"]}
                prompt=self.agent_runner.build_prompt("writer",context,"Return JSON with schema adaptation_chapter_draft, content, source_chapter_id, source_version.",body_text(source["document"]))
                request=TextGenerationRequest(provider_id=provider,model_id=model,prompt=prompt,context=context,parameters=TextGenerationParameters(temperature=0.4),metadata={"purpose":"adaptation_rewrite","verification":"MOCK_ONLY"},job_id=tid,dispatch_guard=dispatch_guard)
                node=self.runtime.prepare_text_route(provider,model,adapter);dispatch_guard();response=node.execute(TextModelNodeInput(request)).response
                parsed=json.loads(response.text)
                if parsed.get("schema")!="adaptation_chapter_draft" or parsed.get("source_chapter_id")!=task["source_chapter_id"] or parsed.get("source_version")!=task["source_version"] or not str(parsed.get("content","")).strip():raise ValueError("adaptation draft contract mismatch")
                draft={**parsed,"target_chapter_id":task["target_chapter_id"],"unit":task["unit"],"action":task["action"],"generation_mode":"model","provider":response.provider_id,"model":response.model_id,"verification":"MOCK_ONLY"}
            elif mode=="deterministic":
                draft={"schema":"adaptation_chapter_draft","source_chapter_id":task["source_chapter_id"],"source_version":task["source_version"],"target_chapter_id":task["target_chapter_id"],"unit":task["unit"],"action":task["action"],"content":body_text(source["document"]),"document":deepcopy(source["document"]),"generation_mode":"deterministic-preparation","verification":"CONTRACT_VERIFIED","note":"当前草稿保留锁定原文，等待 Writer/Editor 模型按改编动作完成实质改写。"}
            else:raise ValueError("unsupported adaptation generation mode")
            dispatch_guard();current,rows,i,_=self._task_claim(nid,pid,tid,branch_id,token)
            return self._save_task(current,rows,i,{"status":"AWAITING_REVIEW","draft":draft,"execution_token":None,"generated_at":now()},reauthorize)
        except Exception as exc:
            current=self.get(nid,pid,branch_id);rows,i,latest=self._task(current,tid)
            if latest.get("execution_token")!=token or latest["status"]!="RUNNING":return {**latest,"proposal_revision":current["revision"]}
            code=str(exc) if isinstance(exc,ValueError) and str(exc).startswith("ADAPTATION_CAPACITY_") else exc.code.value if isinstance(exc,ModelRuntimeError) else "INVALID_ADAPTATION_DRAFT" if isinstance(exc,(ValueError,json.JSONDecodeError)) else "ADAPTATION_GENERATION_FAILED"
            return self._save_task(current,rows,i,{"status":"FAILED","execution_token":None,"error_code":code,"error":"改编生成失败；来源权限、隐私或模型输出未通过检查。","generated_at":now()})

    def _check_target(self,item,task):
        current=self._chapters(item,True).get(task["target_chapter_id"])
        expected=task.get("target_version")
        if expected is None or current["version"]!=expected or digest(current["document"])!=task.get("target_digest"):
            raise VersionConflict({"id":current["id"],"version":current["version"]},expected_version=expected)
        return current

    def review_draft(self,nid,pid,tid,decision,note="",branch_id=None,expected_revision=None,check=None):
        if decision not in {"ACCEPTED","REJECTED"}:raise ValueError("invalid adaptation review decision")
        item=self._read(nid,pid,branch_id,expected_revision);tasks,index,task=self._task(item,tid)
        if task["status"]!="AWAITING_REVIEW":raise ValueError("adaptation task is not awaiting review")
        self._source(item,{"chapter_id":task["source_chapter_id"],"version":task["source_version"]},current_required=True);self._check_target(item,task)
        return self._save_task(item,tasks,index,{"status":decision,"review_note":note.strip(),"reviewed_at":now(),"reviewed_draft_hash":digest(task["draft"]),"reviewed_binding":review_binding(item,task),"applied":False},check)

    def prepare_apply(self,nid,pid,tid,branch_id=None,expected_revision=None):
        item=self._read(nid,pid,branch_id,expected_revision);tasks,index,task=self._task(item,tid)
        if task["status"]!="ACCEPTED" or task.get("applied"):raise ValueError("adaptation draft is not ready to apply")
        if digest(task["draft"])!=task.get("reviewed_draft_hash") or review_binding(item,task)!=task.get("reviewed_binding"):raise ValueError("adaptation draft changed after review")
        self._source(item,{"chapter_id":task["source_chapter_id"],"version":task["source_version"]},current_required=True);self._check_target(item,task)
        return item,tasks,index,task

    def apply_draft(self,nid,pid,tid,branch_id=None,expected_revision=None,check=None,save_chapter=None):
        item,tasks,index,task=self.prepare_apply(nid,pid,tid,branch_id,expected_revision)
        reserve_transitions(item,3)
        target=self._check_target(item,task);draft=task["draft"]
        document=deepcopy(draft["document"]) if draft.get("document") else markdown_to_document(f"# {target['title']}\n\n{draft['content'].strip()}")
        token=str(uuid4());self._save_task(item,tasks,index,{"status":"APPLYING","execution_token":token,"apply_intent":{"expected_version":task["target_version"],"document_digest":digest(document),"created_at":now()}},check)
        try:
            if check:check()
            self._task_claim(nid,pid,tid,branch_id,token,"APPLYING")
            saved=save_chapter(item,target["id"],document,task["target_version"]) if save_chapter else self._chapters(item,True).save(target["id"],document,task["target_version"],"ADAPTATION_ACCEPT")
            current,rows,i,_=self._task_claim(nid,pid,tid,branch_id,token,"APPLYING")
            return self._save_task(current,rows,i,{"status":"APPLIED","applied":True,"execution_token":None,"applied_at":now(),"result_version":saved["version"],"result_digest":digest(saved["document"])},check)
        except Exception:
            current=self.get(nid,pid,branch_id);rows,i,latest=self._task(current,tid)
            if latest.get("execution_token")==token:
                self._save_task(current,rows,i,{"status":"RECOVERY_REQUIRED","execution_token":None,"error_code":"APPLY_OUTCOME_UNCERTAIN"})
            raise

    def action(self,nid,pid,action,branch_id=None,expected_revision=None,task_id=None,check=None):
        item=self._read(nid,pid,branch_id,expected_revision)
        if action not in {"cancel","recover"}:raise ValueError("ADAPTATION_ACTION_INVALID")
        if task_id:
            tasks,index,task=self._task(item,task_id)
            if task["status"]=="APPLIED":raise ValueError("ADAPTATION_ALREADY_APPLIED")
            if action=="cancel":
                uncertain=bool(task.get("apply_intent"))
                return self._save_task(item,tasks,index,{"status":"RECOVERY_REQUIRED" if uncertain else "CANCELLED","execution_token":None,"cancelled_at":now(),"error_code":"CANCEL_DURING_WRITE_UNCERTAIN" if uncertain else None},check)
            if task.get("apply_intent"):
                target=self._chapters(item,True).get(task["target_chapter_id"]);intent=task["apply_intent"]
                if target["version"]==intent["expected_version"]+1 and digest(target["document"])==intent["document_digest"]:
                    return self._save_task(item,tasks,index,{"status":"APPLIED","applied":True,"execution_token":None,"result_version":target["version"],"result_digest":digest(target["document"]),"recovered_at":now()},check)
                raise ValueError("ADAPTATION_WRITE_RECONCILIATION_REQUIRED")
            if task["status"] not in {"RUNNING","FAILED","CANCELLED","NOT_CONFIGURED","RECOVERY_REQUIRED"}:raise ValueError("ADAPTATION_RECOVERY_NOT_REQUIRED")
            return self._save_task(item,tasks,index,{"status":"PENDING_REWRITE","execution_token":None,"draft":None,"error_code":None,"recovered_at":now()},check)
        if item["status"]=="MATERIALIZED":raise ValueError("ADAPTATION_ALREADY_MATERIALIZED")
        checkpoint=item.get("materialization",{})
        if action=="cancel":
            uncertain=checkpoint.get("phase","").endswith("WRITE_INTENT")
            return self._save(item,{"status":"RECOVERY_REQUIRED" if uncertain else "CANCELLED","operation_token":None,"error_code":"CANCEL_DURING_WRITE_UNCERTAIN" if uncertain else None},check,finalize=True)
        if checkpoint.get("phase","").endswith("WRITE_INTENT"):raise ValueError("ADAPTATION_WRITE_RECONCILIATION_REQUIRED")
        if item["status"] not in {"CANCELLED","MATERIALIZING","RECOVERY_REQUIRED"}:raise ValueError("ADAPTATION_RECOVERY_NOT_REQUIRED")
        return self._save(item,{"status":"APPROVED" if item.get("approved_binding") else "DRAFT","operation_token":None,"error_code":None,"recovered_at":now()},check)
