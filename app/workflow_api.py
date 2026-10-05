"""Authenticated, owner-bound access to durable local workflow artifacts."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .dependencies import v1_capability_service as service, agent_job_service
from .services.v1_capability_service import WorkflowDefinitionIn, WorkflowRunIn
from .workflow_recipes import RECIPES, recipe_definition

router = APIRouter()


def actor(token):
    from .api import _agent_job_read_actor
    return _agent_job_read_actor(token)


def guard(fn, *args, **kwargs):
    from .api import capability_guard
    return capability_guard(fn, *args, **kwargs)


def owner(current):
    return {"actor_id":current.actor_id, "workspace_id":current.workspace_id}


def check(record, current, permission="domain.read"):
    from .api import _validate_agent_job_branch, collaboration_scope_service
    if record.get("owner") != owner(current):
        raise HTTPException(403, {"code":"WORKFLOW_SCOPE_FORBIDDEN"})
    linked = collaboration_scope_service.repository.project_workspace(record["novel_id"])
    if linked and (linked != current.workspace_id or not record.get("branch_id")):
        raise HTTPException(403, {"code":"WORKFLOW_BRANCH_REQUIRED"})
    _validate_agent_job_branch(current, record["novel_id"], record.get("branch_id"), permission)
    return record


def read_run(run_id, token, permission="domain.read"):
    current = actor(token)
    return current, check(guard(service.get_workflow_run, run_id), current, permission)


def stamp(collection, record, current, branch_id=None):
    return service._update(collection, record["id"], {"owner":owner(current), "branch_id":branch_id}, novel_id=record["novel_id"], expected_version=record["version"], action="WORKFLOW_SCOPE_BOUND", target_type="Workflow")


def idem(current, key, payload):
    if key is None:
        return None
    return hashlib.sha256(json.dumps([owner(current), key, payload], sort_keys=True).encode()).hexdigest()


class ScopedDefinition(WorkflowDefinitionIn):
    branch_id: str | None = None


class RecipeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    novel_id: str
    branch_id: str | None = None


class ExecuteAgentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapter: int = Field(ge=1)
    provider_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    instruction: str = Field(default="", max_length=10000)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


@router.get("/workflows/recipes")
def recipes(x_session_token: str | None = Header(default=None)):
    actor(x_session_token)
    return {"items":RECIPES, "external_ai_calls":False}


@router.post("/workflows/recipes/{recipe_id}", status_code=201)
def create_recipe(recipe_id: str, body: RecipeIn, x_session_token: str | None = Header(default=None)):
    definition = guard(recipe_definition, recipe_id, body.novel_id)
    return create_workflow(ScopedDefinition(**definition, branch_id=body.branch_id), x_session_token, None)


@router.get("/workflows")
def workflows(novel_id: str | None = None, x_session_token: str | None = Header(default=None)):
    current = actor(x_session_token)
    rows = guard(service.list_workflows, novel_id)
    rows["items"] = [row for row in rows["items"] if row.get("owner") == owner(current)]
    # Re-check membership and branch access; revoked access disappears from history.
    visible=[]
    for row in rows["items"]:
        try: visible.append(check(row,current))
        except HTTPException: continue
    return {**rows, "items":visible, "total":len(visible)}


@router.post("/workflows", status_code=201)
def create_workflow(body: ScopedDefinition, x_session_token: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
    current = actor(x_session_token)
    check({"novel_id":body.novel_id,"branch_id":body.branch_id,"owner":owner(current)}, current, "domain.write")
    payload=body.model_dump(exclude={"branch_id"})
    with service._lock:
        record=guard(service.create_workflow, WorkflowDefinitionIn(**payload), idem(current,idempotency_key,body.model_dump()))
        stored=service.get_workflow(record["id"])
        return stored if stored.get("owner") else stamp("workflows",stored,current,body.branch_id)


@router.get("/workflows/{workflow_id}")
def workflow(workflow_id: str, x_session_token: str | None = Header(default=None)):
    return check(guard(service.get_workflow,workflow_id),actor(x_session_token))


@router.get("/workflows/{workflow_id}/runs")
def runs(workflow_id: str, x_session_token: str | None = Header(default=None)):
    workflow(workflow_id,x_session_token)
    rows=guard(service.list_workflow_runs,workflow_id)
    current=actor(x_session_token)
    visible=[check(row,current) for row in rows["items"] if row.get("owner")==owner(current)]
    return {**rows,"items":visible,"total":len(visible)}


@router.post("/workflows/{workflow_id}/runs", status_code=202)
def create_run(workflow_id: str, body: WorkflowRunIn, x_session_token: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
    current=actor(x_session_token)
    definition=check(guard(service.get_workflow,workflow_id),current,"domain.write")
    body=body.model_copy(update={"initiated_by":current.actor_id})
    with service._lock:
        record=guard(service.create_workflow_run,workflow_id,body,idem(current,idempotency_key,[workflow_id,body.model_dump()]))
        stored=service.get_workflow_run(record["id"])
        return stored if stored.get("owner") else stamp("workflow_runs",stored,current,definition.get("branch_id"))


@router.get("/workflow-runs/{run_id}")
def run(run_id: str, x_session_token: str | None = Header(default=None)):
    return read_run(run_id,x_session_token)[1]


@router.post("/workflow-runs/{run_id}/nodes/{node_id}/approve")
def approve(run_id: str, node_id: str, note: str = "", x_session_token: str | None = Header(default=None)):
    current,_=read_run(run_id,x_session_token,"domain.review")
    return guard(service.approve_workflow_node,run_id,node_id,current.actor_id,note)


@router.post("/workflow-runs/{run_id}/nodes/{node_id}/reject")
def reject(run_id: str, node_id: str, note: str = "", x_session_token: str | None = Header(default=None)):
    current,_=read_run(run_id,x_session_token,"domain.review")
    return guard(service.reject_workflow_node,run_id,node_id,current.actor_id,note)


@router.post("/workflow-runs/{run_id}/nodes/{node_id}/trigger-agent")
def trigger(run_id: str, node_id: str, x_session_token: str | None = Header(default=None)):
    current,_=read_run(run_id,x_session_token,"domain.write")
    return guard(service.trigger_agent_node,run_id,node_id,current.actor_id)


@router.get("/agent-queue")
def queue(novel_id: str | None = None, x_session_token: str | None = Header(default=None)):
    current=actor(x_session_token)
    rows=guard(service.list_agent_queue,novel_id)
    visible=[]
    for row in rows["items"]:
        try:
            check(service.get_workflow_run(row["run_id"]),current)
            visible.append(row)
        except HTTPException: continue
    return {"items":visible,"total":len(visible)}


@router.post("/agent-queue/{run_id}/{node_id}/execute", status_code=202)
def execute_agent(run_id: str, node_id: str, body: ExecuteAgentIn, x_session_token: str | None = Header(default=None)):
    current,record=read_run(run_id,x_session_token,"domain.write")
    with service._lock:
        claimed=guard(service.claim_agent_task,run_id,node_id,current.actor_id)
        node=next(n for n in claimed["definition_snapshot"]["nodes"] if n["id"]==node_id)
        try:
            job=agent_job_service.create(node.get("config",{}).get("agent_role","writer"),record["novel_id"],body.chapter,body.instruction,"local",body.provider_id,body.model_id,"model",body.timeout_seconds)
            job={**job,"branch_id":record.get("branch_id"),"owner":owner(current)}
            agent_job_service.generations.save(job)
            state={**claimed["node_states"][node_id]}
            state["output"]={**state["output"],"agent_job_id":job["id"]}
            linked=service._update("workflow_runs",run_id,{"node_states":{**claimed["node_states"],node_id:state},"external_ai_calls":job["target"]=="cloud"},novel_id=record["novel_id"],expected_version=claimed["version"],action="AGENT_JOB_LINKED",target_type="WorkflowRun")
            agent_job_service.start(job["id"])
            return linked
        except Exception:
            service.complete_agent_task(run_id,node_id,"FAILED",error="AGENT_START_FAILED")
            raise HTTPException(400,{"code":"AGENT_START_FAILED"}) from None


@router.post("/agent-queue/{run_id}/{node_id}/sync")
def sync_agent(run_id: str, node_id: str, x_session_token: str | None = Header(default=None)):
    _,record=read_run(run_id,x_session_token,"domain.write")
    state=record["node_states"].get(node_id,{})
    jid=(state.get("output") or {}).get("agent_job_id")
    if not jid:raise HTTPException(400,{"code":"AGENT_JOB_NOT_LINKED"})
    job=guard(agent_job_service.get,jid)
    if job["status"]=="COMPLETED":
        return guard(service.complete_agent_task,run_id,node_id,"SUCCEEDED",{"agent_job_id":jid,"result":job.get("result"),"applied":False})
    if job["status"] in {"FAILED","CANCELLED"}:
        return guard(service.complete_agent_task,run_id,node_id,"FAILED",error=job.get("error_code","AGENT_FAILED"))
    return record


@router.post("/workflow-runs/{run_id}/retry",status_code=202)
def retry(run_id: str, x_session_token: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
    current,source=read_run(run_id,x_session_token,"domain.write")
    with service._lock:
        result=guard(service.retry_workflow_run,run_id,idem(current,idempotency_key,run_id))
        return stamp("workflow_runs",result,current,source.get("branch_id"))


@router.post("/workflow-runs/{run_id}/{action}")
def transition(run_id: str, action: Literal["pause","resume","cancel"], x_session_token: str | None = Header(default=None)):
    _,record=read_run(run_id,x_session_token,"domain.write")
    result=guard(service.set_workflow_run_state,run_id,action)
    if action=="cancel":
        for state in record["node_states"].values():
            jid=(state.get("output") or {}).get("agent_job_id")
            if jid:
                try: agent_job_service.cancel(jid)
                except ValueError: pass
    return result
