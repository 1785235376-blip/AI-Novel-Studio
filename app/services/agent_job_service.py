from __future__ import annotations

import uuid
import hashlib
import json
import threading
import csv
import io
from datetime import datetime, timezone
from pydantic import BaseModel,Field

from ..agent_catalog import AGENTS
from ..model_runtime import ModelRuntimeError,TextGenerationParameters,TextGenerationRequest,TextModelNodeInput


def utc():return datetime.now(timezone.utc).isoformat()

class StructuredAgentOutput(BaseModel):
    schema_name:str=Field(alias="schema");agent_id:str;summary:str;proposals:list[dict]=[];findings:list[dict]=[];context_hash:str


class AgentJobService:
    terminal={"COMPLETED","VALIDATED","FAILED","CANCELLED","ACCEPTED","REJECTED"}
    def __init__(self,generations,contexts,novels,runtime=None,agent_runner=None):self.generations,self.contexts,self.novels,self.runtime,self.agent_runner=generations,contexts,novels,runtime,agent_runner;self.lock=threading.RLock();self.cancellations={}

    def create(self,agent_id,novel_id,chapter_number,instruction="",target="local",provider=None,model=None,execution_mode="deterministic",timeout_seconds=120,retry_of=None):
        agent=next((item for item in AGENTS if item["id"]==agent_id),None)
        if agent is None:raise KeyError(agent_id)
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

    def list(self, novel_id=None, agent_id=None, status=None, page=1, page_size=20, created_after=None, created_before=None, branch_id=None):
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("invalid pagination")
        jobs=[item for item in self.generations.load_all() if item.get("operation")=="AGENT_TASK"]
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

    def export_csv(self, novel_id=None, agent_id=None, status=None, created_after=None, created_before=None, branch_id=None):
        payload=self.list(novel_id,agent_id,status,1,100,created_after,created_before,branch_id)
        out=io.StringIO(); writer=csv.DictWriter(out,fieldnames=["id","agent_id","agent_name","novel_id","status","execution_mode","provider","model","created_at","updated_at","error_code","retry_of"],extrasaction="ignore"); writer.writeheader(); writer.writerows(payload["items"])
        return out.getvalue()

    def export_summary(self, novel_id=None, agent_id=None, status=None, created_after=None, created_before=None, branch_id=None):
        payload=self.list(novel_id,agent_id,status,1,100,created_after,created_before,branch_id)
        return {"result_count":payload["total"],"filters":{"novel_id":novel_id,"agent_id":agent_id,"status":status,"created_after":created_after,"created_before":created_before,"branch_id":branch_id}}

    def execute(self,jid):
        with self.lock:
            job=self.get(jid)
            if job["status"]!="QUEUED":raise ValueError("agent job is not queued")
            cancellation=self.cancellations.setdefault(jid,threading.Event());working={**job,"status":"WORKING","updated_at":utc()};self.generations.save(working)
        try:
            if job.get("execution_mode","deterministic")=="model":
                output,provider,model=self._execute_model(job)
                status="COMPLETED"
                execution_label="真实模型执行"
                model_called=True
            else:
                output={"schema":job["output_schema"],"agent_id":job["agent_id"],"summary":"契约校验通过，未调用模型，未生成可应用正文。","proposals":[],"findings":[],"context_hash":job["context_hash"]}
                provider,model=job.get("provider") or "deterministic-local",job.get("model") or "contract-validator-v1"
                status="VALIDATED"
                execution_label="契约校验，未调用模型"
                model_called=False
            with self.lock:
                current=self.get(jid)
                if current["status"] in {"CANCELLED","FAILED"}:return current
                completed={**working,"status":status,"execution_label":execution_label,"model_called":model_called,"result":{"structured_output":output,"empty":not output.get("proposals") and not output.get("findings")},"provider":provider,"model":model,"fallback_used":False,"updated_at":utc()};self.generations.save(completed);return completed
        except Exception as exc:
            code=exc.code.value if isinstance(exc,ModelRuntimeError) else ("INVALID_STRUCTURED_OUTPUT" if isinstance(exc,(ValueError,json.JSONDecodeError)) else "AGENT_EXECUTION_FAILED")
            with self.lock:
                current=self.get(jid)
                if current["status"] in {"CANCELLED","FAILED"}:return current
                failed={**working,"status":"FAILED","error_code":code,"error":str(exc),"fallback_used":False,"updated_at":utc()};self.generations.save(failed);return failed

    def start(self,jid):
        job=self.get(jid)
        if job["status"]!="QUEUED":raise ValueError("agent job is not queued")
        thread=threading.Thread(target=self.execute,args=(jid,),daemon=True,name=f"agent-job-{jid}");thread.start()
        timer=threading.Timer(job.get("timeout_seconds",120),self._timeout,args=(jid,));timer.daemon=True;timer.start()
        return self.get(jid)

    def _timeout(self,jid):
        with self.lock:
            job=self.get(jid)
            if job["status"] not in {"QUEUED","WORKING"}:return
            self.cancellations.setdefault(jid,threading.Event()).set();failed={**job,"status":"FAILED","error_code":"TIMEOUT","error":"Agent task timed out","fallback_used":False,"updated_at":utc()};self.generations.save(failed)

    def cancel(self,jid):
        with self.lock:
            job=self.get(jid)
            if job["status"] not in {"QUEUED","WORKING"}:raise ValueError("agent job cannot be cancelled")
            self.cancellations.setdefault(jid,threading.Event()).set();cancelled={**job,"status":"CANCELLED","error_code":"CANCELLED","error":"Agent task cancelled","updated_at":utc()};self.generations.save(cancelled);return cancelled

    def retry(self,jid):
        job=self.get(jid)
        if job["status"] not in {"FAILED","CANCELLED"}:raise ValueError("agent job is not retryable")
        retried=self.create(job["agent_id"],job["novel_id"],int(str(job["chapter_id"]).rsplit(":",1)[-1]),job.get("instruction",""),job.get("target","local"),job.get("provider"),job.get("model"),job.get("execution_mode","deterministic"),job.get("timeout_seconds",120),jid)
        # Keep the authorization scope attached to the retry. Without this,
        # a branch-bound job silently became an unscoped legacy job and could
        # then be read or executed without the branch capability.
        if job.get("branch_id"):
            retried={**retried,"branch_id":job["branch_id"]}
            self.generations.save(retried)
        return retried

    def _execute_model(self,job):
        if self.runtime is None or self.agent_runner is None:raise RuntimeError("agent model runtime is unavailable")
        context=self.contexts.build(job["agent_id"],job["novel_id"],int(str(job["chapter_id"]).rsplit(":",1)[-1]),job.get("instruction",""),job.get("target")=="cloud")
        prompt=self.agent_runner.build_prompt(job["prompt_role"],context,job.get("instruction") or "Return a structured result.")+"\n\nReturn JSON only with keys: schema, agent_id, summary, proposals, findings, context_hash."
        node=self.runtime.prepare_text_route(job["provider"],job["model"],self.runtime.providers.get(job["provider"]))
        request=TextGenerationRequest(provider_id=job["provider"],model_id=job["model"],prompt=prompt,context=context,parameters=TextGenerationParameters(temperature=0.2),metadata={"purpose":"agent_task"},job_id=job["id"],cancellation=self.cancellations.setdefault(job["id"],threading.Event()))
        response=node.execute(TextModelNodeInput(request)).response;parsed=StructuredAgentOutput.model_validate_json(response.text).model_dump(by_alias=True)
        if parsed["schema"]!=job["output_schema"] or parsed["agent_id"]!=job["agent_id"] or parsed["context_hash"]!=job["context_hash"]:raise ValueError("structured agent output contract mismatch")
        return parsed,response.provider_id,response.model_id

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
