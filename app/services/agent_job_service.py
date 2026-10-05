from __future__ import annotations

import uuid
import hashlib
import json
import threading
import csv
import io
from datetime import datetime, timezone
from dataclasses import asdict
from pydantic import BaseModel,Field

from ..agent_catalog import AGENTS
from ..model_runtime import ModelRuntimeError,TextGenerationParameters,TextGenerationRequest,TextModelNodeInput


def utc():return datetime.now(timezone.utc).isoformat()

class StructuredAgentOutput(BaseModel):
    schema_name:str=Field(alias="schema");agent_id:str;summary:str;proposals:list[dict]=[];findings:list[dict]=[];context_hash:str


class AgentJobError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class AgentJobService:
    terminal={"COMPLETED","VALIDATED","FAILED","CANCELLED","ACCEPTED","REJECTED"}
    def __init__(self,generations,contexts,novels,runtime=None,agent_runner=None):self.generations,self.contexts,self.novels,self.runtime,self.agent_runner=generations,contexts,novels,runtime,agent_runner;self.lock=threading.RLock();self.cancellations={};self._timers={}

    def create(self,agent_id,novel_id,chapter_number,instruction="",target="local",provider=None,model=None,execution_mode="deterministic",timeout_seconds=120,retry_of=None):
        agent=next((item for item in AGENTS if item["id"]==agent_id),None)
        if agent is None:raise KeyError(agent_id)
        if target not in {"local", "cloud"}:raise ValueError("invalid execution target")
        if execution_mode == "model":
            if self.runtime is None:raise ValueError("agent model runtime is unavailable")
            # Provider registry, not the request's target label, determines egress.
            target = "cloud" if self.runtime.is_remote_text_provider(provider) else "local"
        context=self.contexts.build(agent_id,novel_id,chapter_number,instruction,target=="cloud");jid=str(uuid.uuid4());now=utc()
        if execution_mode not in {"deterministic","model"}:raise ValueError("invalid agent execution mode")
        if execution_mode=="model" and (not provider or not model):raise ValueError("model execution requires provider and model")
        if timeout_seconds<1 or timeout_seconds>3600:raise ValueError("timeout_seconds must be between 1 and 3600")
        job={"id":jid,"operation":"AGENT_TASK","agent_id":agent_id,"agent_name":agent["name"],"prompt_role":agent["prompt_role"],"novel_id":novel_id,"chapter_id":context["chapter_id"],"chapter_version":context["chapter_version"],"instruction":instruction,"target":target,"execution_mode":execution_mode,"timeout_seconds":timeout_seconds,"retry_of":retry_of,"status":"QUEUED","context_hash":context["context_hash"],"context_contract_version":context["context_contract_version"],"source_manifest":context["source_manifest"],"provider":provider,"model":model,"output_schema":agent["output_schema"],"requires_approval":agent["requires_approval"],"created_at":now,"updated_at":now}
        self.generations.save(job);return job

    def get(self,jid):
        job=self.generations.get(jid)
        if job.get("operation")!="AGENT_TASK":raise KeyError(jid)
        job.setdefault("execution_label", "真实模型执行" if job.get("execution_mode")=="model" else "契约校验，未调用模型")
        return job

    def list(self, novel_id=None, agent_id=None, status=None, page=1, page_size=20, created_after=None, created_before=None, branch_id=None, visibility=None):
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("invalid pagination")
        jobs=[item for item in self.generations.load_all() if item.get("operation")=="AGENT_TASK"]
        if visibility is not None: jobs=[item for item in jobs if visibility(item)]
        for item in jobs: item.setdefault("execution_label", "真实模型执行" if item.get("execution_mode")=="model" else "契约校验，未调用模型")
        if novel_id: jobs=[item for item in jobs if item.get("novel_id")==novel_id]
        if agent_id: jobs=[item for item in jobs if item.get("agent_id")==agent_id]
        if status: jobs=[item for item in jobs if item.get("status")==status]
        if created_after: jobs=[item for item in jobs if (item.get("created_at") or "") >= created_after]
        if created_before: jobs=[item for item in jobs if (item.get("created_at") or "") <= created_before]
        if branch_id: jobs=[item for item in jobs if item.get("branch_id")==branch_id]
        jobs.sort(key=lambda item:item.get("updated_at") or item.get("created_at") or "", reverse=True)
        total=len(jobs); start=(page-1)*page_size
        return {"items":jobs[start:start+page_size],"page":page,"page_size":page_size,"total":total,"has_more":start+page_size<total}

    def export_csv(self, novel_id=None, agent_id=None, status=None, created_after=None, created_before=None, branch_id=None, visibility=None):
        payload=self.list(novel_id,agent_id,status,1,100,created_after,created_before,branch_id,visibility)
        out=io.StringIO(); writer=csv.DictWriter(out,fieldnames=["id","agent_id","agent_name","novel_id","status","execution_mode","provider","model","created_at","updated_at","error_code","retry_of"],extrasaction="ignore"); writer.writeheader(); writer.writerows(payload["items"])
        return out.getvalue()

    def export_summary(self, novel_id=None, agent_id=None, status=None, created_after=None, created_before=None, branch_id=None, visibility=None):
        payload=self.list(novel_id,agent_id,status,1,100,created_after,created_before,branch_id,visibility)
        return {"result_count":payload["total"],"filters":{"novel_id":novel_id,"agent_id":agent_id,"status":status,"created_after":created_after,"created_before":created_before,"branch_id":branch_id}}

    @staticmethod
    def _same_attempt(current, claimed):
        return (current.get("status") == "WORKING"
                and current.get("execution_token") == claimed.get("execution_token")
                and all(current.get(key) == claimed.get(key) for key in (
                    "owner", "branch_id", "novel_id", "chapter_id", "chapter_version",
                    "context_hash", "agent_id", "prompt_role", "instruction", "target",
                    "provider", "model", "execution_mode", "output_schema")))

    def _check_current_attempt(self, job):
        with self.lock:
            current = self.get(job["id"])
            if (not self._same_attempt(current, job)
                    or self.cancellations.setdefault(job["id"], threading.Event()).is_set()):
                raise AgentJobError("AGENT_JOB_CHANGED", "Agent execution claim is no longer current")
            return current

    def _check_authority(self, job, check_authority):
        current = self._check_current_attempt(job)
        if check_authority is None:
            if job.get("owner") or job.get("branch_id"):
                raise AgentJobError("AGENT_AUTHORITY_MISSING", "Agent execution authority is unavailable")
            return
        try:
            check_authority(current)
        except Exception as exc:
            raise AgentJobError("AGENT_PERMISSION_REVOKED", "Agent execution is no longer authorized") from exc

    def _check_dispatch(self, job, check_authority):
        # Rebuild only to validate the reviewed prompt, never silently substitute
        # changed sources. This also catches privacy filtering changes at runtime.
        self._check_authority(job, check_authority)
        actual_target = "cloud" if self.runtime.is_remote_text_provider(job["provider"]) else "local"
        if actual_target != job.get("target"):
            raise AgentJobError("AGENT_ROUTE_CHANGED", "Agent provider egress changed")
        context = self.contexts.build(job["agent_id"], job["novel_id"], int(str(job["chapter_id"]).rsplit(":", 1)[-1]), job.get("instruction", ""), actual_target == "cloud")
        if context["context_hash"] != job["context_hash"] or context["chapter_version"] != job["chapter_version"]:
            raise AgentJobError("AGENT_SOURCE_CHANGED", "Agent sources changed; review a fresh job")
        # Context repositories may themselves be slow. Membership must still
        # hold after they finish, and a callback may have cancelled the attempt.
        self._check_authority(job, check_authority)
        self._check_current_attempt(job)

    def execute(self,jid,check_authority=None):
        with self.lock:
            job=self.get(jid)
            if job["status"]!="QUEUED":raise ValueError("agent job is not queued")
            cancellation=self.cancellations.setdefault(jid,threading.Event());working={**job,"status":"WORKING","execution_token":str(uuid.uuid4()),"attempt":int(job.get("attempt",0))+1,"updated_at":utc()};self.generations.save(working)
        try:
            if job.get("execution_mode","deterministic")=="model":
                output,provider,model,usage,provider_execution_mode=self._execute_model(working,check_authority)
                status="COMPLETED"
                execution_label="模拟测试执行，未调用真实模型" if provider_execution_mode=="mock_standin" else "真实模型执行"
                model_called=provider_execution_mode!="mock_standin"
            else:
                self._check_authority(working,check_authority)
                output={"schema":job["output_schema"],"agent_id":job["agent_id"],"summary":"契约校验通过，未调用模型，未生成可应用正文。","proposals":[],"findings":[],"context_hash":job["context_hash"]}
                provider,model=job.get("provider") or "deterministic-local",job.get("model") or "contract-validator-v1"
                status="VALIDATED"
                execution_label="契约校验，未调用模型"
                model_called=False
                usage=None
                provider_execution_mode="deterministic"
            with self.lock:
                current=self.get(jid)
                if not self._same_attempt(current,working) or cancellation.is_set():return current
                completed={**working,"status":status,"execution_label":execution_label,"model_called":model_called,"result":{"structured_output":output,"empty":not output.get("proposals") and not output.get("findings")},"provider":provider,"model":model,"fallback_used":False,"provider_execution_mode":provider_execution_mode,"usage":usage,"usage_status":"REPORTED" if usage else "UNKNOWN","updated_at":utc()};self.generations.save(completed);return completed
        except Exception as exc:
            code=exc.code.value if isinstance(exc,ModelRuntimeError) else (exc.code if isinstance(exc,AgentJobError) else ("INVALID_STRUCTURED_OUTPUT" if isinstance(exc,(ValueError,json.JSONDecodeError)) else "AGENT_EXECUTION_FAILED"))
            with self.lock:
                current=self.get(jid)
                if not self._same_attempt(current,working):return current
                failed={**working,"status":"FAILED","error_code":code,"error":exc.safe_message if isinstance(exc,ModelRuntimeError) else "Agent execution failed; inspect the safe error code.","fallback_used":False,"updated_at":utc()};self.generations.save(failed);return failed
        finally:
            self._drop_timer(jid)

    def recover_interrupted(self):
        """Reconcile persisted in-flight work after restart without replaying billing."""
        recovered=[]
        with self.lock:
            for job in self.generations.load_all():
                if job.get("operation") != "AGENT_TASK" or job.get("status") != "WORKING" or job["id"] in self.cancellations:
                    continue
                failed={**job,"status":"FAILED","error_code":"INTERRUPTED","error":"Execution interrupted. Review before explicitly retrying; the provider may have processed the request.","replay_safe":False,"updated_at":utc()}
                self.generations.save(failed);recovered.append(job["id"])
        return recovered

    def _drop_timer(self,jid):
        with self.lock:
            timer=self._timers.pop(jid,None)
            if timer is not None:timer.cancel()

    def _run_started(self,jid,check_authority):
        try:
            return self.execute(jid,check_authority)
        except KeyError:
            # A deleted project owns no runnable job or timer.
            return None
        except ValueError:
            current=self.get(jid)
            if current["status"] in self.terminal:
                return current
            raise
        finally:
            self._drop_timer(jid)

    def start(self,jid,check_authority=None):
        with self.lock:
            job=self.get(jid)
            if job["status"]!="QUEUED":raise ValueError("agent job is not queued")
            if jid in self._timers:return job
            timer=threading.Timer(job.get("timeout_seconds",120),self._timeout,args=(jid,));timer.daemon=True
            self._timers[jid]=timer
            thread=threading.Thread(target=self._run_started,args=(jid,check_authority),daemon=True,name=f"agent-job-{jid}")
            # Register the timer before execution can complete and clean it up.
            timer.start();thread.start()
            return self.get(jid)

    def _timeout(self,jid):
        try:
            with self.lock:
                try:
                    job=self.get(jid)
                except KeyError:
                    self.cancellations.pop(jid,None)
                    return
                if job["status"] not in {"QUEUED","WORKING"}:return
                self.cancellations.setdefault(jid,threading.Event()).set();failed={**job,"status":"FAILED","error_code":"TIMEOUT","error":"Agent task timed out","fallback_used":False,"updated_at":utc()};self.generations.save(failed)
        finally:
            self._drop_timer(jid)

    def cancel(self,jid):
        with self.lock:
            job=self.get(jid)
            if job["status"] not in {"QUEUED","WORKING"}:raise ValueError("agent job cannot be cancelled")
            self.cancellations.setdefault(jid,threading.Event()).set();cancelled={**job,"status":"CANCELLED","error_code":"CANCELLED","error":"Agent task cancelled","updated_at":utc()};self.generations.save(cancelled);self._drop_timer(jid);return cancelled

    def retry(self,jid):
        job=self.get(jid)
        if job["status"] not in {"FAILED","CANCELLED"}:raise ValueError("agent job is not retryable")
        retried=self.create(job["agent_id"],job["novel_id"],int(str(job["chapter_id"]).rsplit(":",1)[-1]),job.get("instruction",""),job.get("target","local"),job.get("provider"),job.get("model"),job.get("execution_mode","deterministic"),job.get("timeout_seconds",120),jid)
        # Keep the authorization scope attached to the retry. Without this,
        # a branch-bound job silently became an unscoped legacy job and could
        # then be read or executed without the branch capability.
        retried={**retried,**{key:job[key] for key in ("branch_id","owner") if key in job}}
        self.generations.save(retried)
        return retried

    def _execute_model(self,job,check_authority=None):
        if self.runtime is None or self.agent_runner is None:raise RuntimeError("agent model runtime is unavailable")
        actual_target="cloud" if self.runtime.is_remote_text_provider(job["provider"]) else "local"
        if actual_target != job.get("target"):
            raise ValueError("provider egress changed; create and review a fresh agent job")
        context=self.contexts.build(job["agent_id"],job["novel_id"],int(str(job["chapter_id"]).rsplit(":",1)[-1]),job.get("instruction",""),job.get("target")=="cloud")
        if context["context_hash"] != job["context_hash"] or context["chapter_version"] != job["chapter_version"]:
            raise ValueError("agent source changed; create a fresh job for review")
        prompt=self.agent_runner.build_prompt(job["prompt_role"],context,job.get("instruction") or "Return a structured result.")+"\n\nReturn JSON only with keys: schema, agent_id, summary, proposals, findings, context_hash."
        node=self.runtime.prepare_text_route(job["provider"],job["model"],self.runtime.providers.get(job["provider"]))
        dispatch_guard=lambda:self._check_dispatch(job,check_authority)
        request=TextGenerationRequest(provider_id=job["provider"],model_id=job["model"],prompt=prompt,context=context,parameters=TextGenerationParameters(temperature=0.2),metadata={"purpose":"agent_task"},job_id=job["id"],cancellation=self.cancellations.setdefault(job["id"],threading.Event()),dispatch_guard=dispatch_guard)
        dispatch_guard()
        response=node.execute(TextModelNodeInput(request)).response;parsed=StructuredAgentOutput.model_validate_json(response.text).model_dump(by_alias=True)
        if parsed["schema"]!=job["output_schema"] or parsed["agent_id"]!=job["agent_id"] or parsed["context_hash"]!=job["context_hash"]:raise ValueError("structured agent output contract mismatch")
        return parsed,response.provider_id,response.model_id,asdict(response.usage) if response.usage else None,response.execution_mode

    def review(self,jid,decision,reviewed_by,note="",actions=None):
        job=self.get(jid)
        if job.get("execution_mode","deterministic")!="model" or job["status"]=="VALIDATED":
            raise ValueError("deterministic agent jobs are validated only and have no review or apply path")
        if decision not in {"ACCEPTED","REJECTED"}:raise ValueError("invalid agent review decision")
        if job["status"]!="COMPLETED":raise ValueError("agent job is not awaiting review")
        output=(job.get("result") or {}).get("structured_output")
        if output is None:raise ValueError("agent job has no structured output")
        output_hash=hashlib.sha256(json.dumps(output,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        reviewed_actions=list(actions or []) if decision=="ACCEPTED" else []
        reviewed={**job,"status":decision,"review":{"decision":decision,"reviewed_by":reviewed_by,"note":note,"output_hash":output_hash,"reviewed_actions":reviewed_actions,"reviewed_at":utc(),"applied":False},"updated_at":utc()};self.generations.save(reviewed);return reviewed

    def apply(self,jid,applied_by):
        job=self.get(jid);review=job.get("review") or {}
        if job.get("execution_mode","deterministic")!="model" or job["status"]=="VALIDATED":
            raise ValueError("deterministic agent jobs are validated only and have no review or apply path")
        if job["status"]!="ACCEPTED" or review.get("decision")!="ACCEPTED":raise ValueError("agent job is not accepted")
        if review.get("applied"):raise ValueError("agent job is already applied")
        output=(job.get("result") or {}).get("structured_output");current_hash=hashlib.sha256(json.dumps(output,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if current_hash!=review.get("output_hash"):raise ValueError("agent output changed after review")
        actions = review.get("reviewed_actions", [])
        # Validate the complete action set before the first domain mutation.
        for action in actions:
            if action.get("type") not in {"outline.update", "volume.upsert", "scene.upsert"}:
                raise ValueError("unsupported agent application action")
            if action.get("type") != "outline.update" and not action.get("id"):
                raise ValueError("agent application action requires id")
        snapshots=[]
        for action in review.get("reviewed_actions",[]):
            kind=action.get("type");payload=dict(action.get("payload") or {});target_id=str(action.get("id") or "")
            if kind=="outline.update":before=self.novels.get_outline(job["novel_id"]);after=self.novels.update_outline(job["novel_id"],payload)
            elif kind=="volume.upsert":
                if not target_id:raise ValueError("volume action requires id")
                before=next((x for x in self.novels.get_data_set(job["novel_id"],"volumes") if str(x.get("id"))==target_id),None);after=self.novels.upsert_volume(job["novel_id"],target_id,payload)
            elif kind=="scene.upsert":
                if not target_id:raise ValueError("scene action requires id")
                before=next((x for x in self.novels.get_data_set(job["novel_id"],"scenes") if str(x.get("id"))==target_id),None);after=self.novels.upsert_scene(job["novel_id"],target_id,payload)
            else:raise ValueError(f"unsupported agent application action: {kind}")
            snapshots.append({"type":kind,"id":target_id or None,"before":before,"after":after})
        application={"applied":True,"applied_by":applied_by,"applied_at":utc(),"actions":snapshots,"output_hash":current_hash}
        updated={**job,"review":{**review,"applied":True},"application":application,"updated_at":utc()};self.generations.save(updated);return updated
