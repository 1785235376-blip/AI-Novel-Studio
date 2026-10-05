"""Current-actor B03 APIs; synthesis goes through the existing executor."""
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import Field
from .production_lineage_api import api_call, PrivateProductionRoute
from .voice_direction import DirectionEditIn, LockIn, ReorderIn, QueueSegmentsIn, VersionIn, VOICE_FLAG
from .media import StrictModel
from ..services.audiobook_service import AudiobookService, AudiobookError


def create_runtime_executor(scope, actor):
    from ..audio_production_store import audio_production_store
    from .. import api as legacy
    store = audio_production_store.for_branch(scope.get("branch_id")).for_actor(actor)
    return AudiobookService(store, legacy.asset_library_service, branch_id=scope.get("branch_id"))


def resolve_runtime_provider(provider_id):
    from ..audio_providers import resolve_provider
    from ..dependencies import credential_vault
    import httpx
    return resolve_provider(provider_id, "TTS", credential_vault, httpx)


class AssetReviewIn(StrictModel):
    expected_asset_version: int = Field(ge=1)


def create_voice_direction_router(service, authorize, require_flag, executor_factory=None, resolver=None):
    executor_factory = executor_factory or create_runtime_executor
    resolver = resolver or resolve_runtime_provider
    router = APIRouter(prefix="/novels/{nid}/experimental/voice-direction", tags=["Experimental voice direction"], route_class=PrivateProductionRoute)

    def invoke(nid, token, branch, permission, callback):
        def access():
            require_flag(VOICE_FLAG); require_flag("audiobook_v2")
            return authorize(nid, token, branch, permission)
        actor, scope = access()
        def guard():
            if access() != (actor, scope): raise HTTPException(403, {"code": "VOICE_AUTHORITY_CHANGED"})
        def run():
            try: return callback(actor, scope, guard)
            except AudiobookError as exc: raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None
        result = api_call(service.as_actor, actor, run)
        guard(); return result

    @router.get("/catalog")
    def catalog(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read", lambda a,s,g: service.catalog(nid,s,a))

    @router.put("/plans/{rid}/segments/{sid}")
    def edit(nid: str, rid: str, sid: str, body: DirectionEditIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.write",lambda a,s,g: (g(),service.edit_direction(nid,s,a,rid,sid,body))[1])

    @router.post("/plans/{rid}/segments/{sid}/lock")
    def lock(nid: str, rid: str, sid: str, body: LockIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.write",lambda a,s,g: (g(),service.lock(nid,s,a,rid,sid,body))[1])

    @router.post("/plans/{rid}/reorder")
    def reorder(nid: str, rid: str, body: ReorderIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.write",lambda a,s,g: (g(),service.reorder(nid,s,a,rid,body))[1])

    @router.post("/plans/{rid}/queue", status_code=202)
    def queue(nid: str, rid: str, body: QueueSegmentsIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None), idempotency_key: str | None = Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.write",lambda a,s,g: service.queue_selected(nid,s,a,rid,body,executor_factory(s,a),g,idempotency_key))

    @router.get("/jobs")
    def jobs(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def read(a,s,g):
            rows = []
            for job in executor_factory(s,a).store.load(nid)["jobs"]:
                if job.get("experimental_origin") != VOICE_FLAG: continue
                try: service.assert_job(nid,s,a,job)
                except FileNotFoundError: continue
                except ValueError:
                    rows.append({"id":job["id"], "status":job["status"], "stale":True}); continue
                rows.append({k:v for k,v in job.items() if k not in {"source_text", "pronunciation_dictionary", "direction_binding", "execution_token"}})
            return {"items":rows}
        return invoke(nid,x_session_token,x_branch_id,"domain.read",read)

    @router.post("/jobs/{jid}/execute")
    def execute(nid: str, jid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def run(a,s,g):
            result = service.execute_local_job(nid,s,a,jid,executor_factory(s,a),resolver,g)
            return {k:v for k,v in result.items() if k not in {"source_text", "pronunciation_dictionary", "direction_binding", "execution_token"}}
        return invoke(nid,x_session_token,x_branch_id,"domain.write",run)

    @router.post("/jobs/{jid}/cancel")
    def cancel(nid: str, jid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def run(a,s,g):
            executor = executor_factory(s,a); job = executor.find(executor.store.load(nid),jid)
            binding=job.get("direction_binding",{})
            if binding.get("actor") != a or binding.get("scope") != s: raise FileNotFoundError(jid)
            g(); return executor.transition(nid,jid,"CANCELLED")
        return invoke(nid,x_session_token,x_branch_id,"domain.write",run)

    @router.post("/jobs/{jid}/retry")
    def retry(nid: str, jid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def run(a,s,g):
            executor=executor_factory(s,a); job=executor.find(executor.store.load(nid),jid)
            service.assert_job(nid,s,a,job); g(); return executor.transition(nid,jid,"QUEUED")
        return invoke(nid,x_session_token,x_branch_id,"domain.write",run)

    @router.get("/jobs/{jid}/audio")
    def audio(nid: str, jid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def read(a,s,g):
            executor=executor_factory(s,a); job=executor.find(executor.store.load(nid),jid)
            service.assert_job(nid,s,a,job)
            if job["status"] != "SUCCEEDED": raise ValueError("VOICE_AUDIO_NOT_READY")
            asset=service.assets.get(job["asset_id"],branch_id=s.get("branch_id"),actor_id=a)
            data=service.assets.content(asset["id"],branch_id=s.get("branch_id"),actor_id=a);g()
            return Response(data,media_type=asset["media_type"],headers={"Cache-Control":"no-store"})
        return invoke(nid,x_session_token,x_branch_id,"domain.read",read)

    @router.post("/jobs/{jid}/approve")
    def approve(nid: str, jid: str, body: AssetReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def run(a,s,g):
            executor=executor_factory(s,a);job=executor.find(executor.store.load(nid),jid)
            service.assert_job(nid,s,a,job)
            if job["status"] != "SUCCEEDED" or job["approval_status"] != "PENDING": raise ValueError("VOICE_OUTPUT_REVIEW_REQUIRED")
            asset=service.assets.promote_owned(job["asset_id"],actor_id=a,branch_id=s.get("branch_id"),expected_version=body.expected_asset_version,
                provenance={"job_id":jid,"direction_binding":job["direction_binding"],"source_version":job["source_version"],"source_digest":job["source_content_sha256"]},guard=lambda:(g(),service.assert_job(nid,s,a,job)))
            def accept(state):
                current=executor.find(state,jid)
                if current.get("request_sha256") != job["request_sha256"]: raise ValueError("VOICE_JOB_CHANGED")
                current.update(approval_status="APPROVED",asset_version=asset["version"])
                return {"job_id":jid,"asset":asset,"approval_status":"APPROVED"}
            return executor.store.mutate(nid,accept)
        return invoke(nid,x_session_token,x_branch_id,"domain.review",run)
    return router


def voice_task_projection(service, nid, scope, actor, executor_factory=None):
    """Read-only bounded U07 view of the original actor-scoped queue.

    The caller retains current authorization; no task text, binding, path,
    credential, profile or raw provider error is exposed in this projection.
    """
    from .flags import enabled_flags
    from .common import StaleSourceError
    if VOICE_FLAG not in enabled_flags(): return {"items": [], "has_more": False}
    executor = (executor_factory or create_runtime_executor)(scope, actor)
    items = []
    for job in executor.store.load(nid)["jobs"]:
        if job.get("experimental_origin") != VOICE_FLAG: continue
        binding = job.get("direction_binding", {})
        if binding.get("actor") != actor or binding.get("scope") != scope: continue
        stale = False
        try: service.as_actor(actor, service.assert_job, nid, scope, actor, job)
        except FileNotFoundError: continue
        except StaleSourceError: stale = True
        items.append({"id": job["id"], "status": job["status"], "chapter_id": None if stale else job["chapter_id"],
                      "version": job.get("source_version", 1), "stale": stale, "experimental_origin": VOICE_FLAG})
        if len(items) > 100: break
    return {"items": items[:100], "has_more": len(items) > 100}
