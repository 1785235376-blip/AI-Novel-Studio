"""Closed, explicit production commands on original Host and scope authority."""
from typing import Literal
from urllib.parse import quote
from fastapi import APIRouter, Header, HTTPException, Request, Response

from ..experimental.production_lineage_api import PrivateProductionRoute
from ..services.v1_capability_service import CapabilityVersionConflict
from ..services.audiobook_service import AudiobookError
from ..audio_production_store import AudioStateVersionConflict
from .production_execution_models import (MediaCommand, MediaCreate, MediaJobAction, MediaReview, TimelineSave, TimelineRender,
    TimelineEdit, TimelineRestore, TimelineExportPreview, TimelineExport,
    TimelineTransferPreview, TimelineTransferImport, TimelineTransferDownload, TimelinePlaybackPreview, TimelinePlaybackBuild, TimelinePlaybackAttestation)

Owner = Literal["image", "audio", "video", "timeline"]


def create_production_execution_router(service, invoke, *, require_host_session, model_host_authority):
    router = APIRouter(tags=["Studio Production Execution V2"], route_class=PrivateProductionRoute)

    def call(request, nid, token, branch, permission, callback, *, model=False):
        def operation(actor, scope, guard):
            if require_host_session is None or model_host_authority is None:
                raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
            authority = model_host_authority(request, token)
            if not authority.principal: raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_BINDING_REQUIRED"})
            def current():
                guard(); require_host_session(token); authority.guard()
                if model:
                    from .ai_execution import require_execution
                    require_execution()
            current()
            try: result = callback(actor, scope, current)
            except AudiobookError as exc:
                current()
                raise HTTPException(exc.status, {"code": exc.code}) from None
            except AudioStateVersionConflict as exc:
                current()
                raise HTTPException(409, {"code": exc.code}) from None
            except CapabilityVersionConflict as exc:
                current()
                # Never echo private owner tokens, prompts, URLs or context from
                # a lower-level job owner's raw CAS exception.
                raise HTTPException(409, {"code": "STUDIO_PRODUCTION_VERSION_CONFLICT", "current_version": exc.current.get("version")}) from None
            except Exception:
                current(); raise
            current()
            return result
        return invoke(nid, token, branch, permission, operation)

    @router.get("/projects/{nid}/studio/production/providers")
    def providers(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.providers(nid, scope, actor, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/playback-preview")
    def playback_preview(nid: str, tid: str, request: Request, body: TimelinePlaybackPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_playback_preview(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/playback-build")
    def playback_build(nid: str, tid: str, request: Request, body: TimelinePlaybackBuild, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_playback_build(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/playback-attestation")
    def playback_attestation(nid: str, tid: str, request: Request, body: TimelinePlaybackAttestation, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_playback_attest(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/preview")
    def preview(nid: str, request: Request, body: MediaCommand, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.preview(nid, scope, actor, body, guard)[0], model=body.operation_id != "m8.audio.trim")

    @router.post("/projects/{nid}/studio/production/jobs", status_code=201)
    def create(nid: str, request: Request, body: MediaCreate, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.create(nid, scope, actor, body, guard), model=body.command.operation_id != "m8.audio.trim")

    @router.get("/projects/{nid}/studio/production/jobs")
    def jobs(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.list(nid, scope, actor, guard))

    @router.get("/projects/{nid}/studio/production/jobs/{owner}/{jid}")
    def job(nid: str, owner: Owner, jid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.get(nid, scope, actor, owner, jid, guard))

    @router.get("/projects/{nid}/studio/production/jobs/{owner}/{jid}/candidate")
    def candidate(nid: str, owner: Owner, jid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        row, data = call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.candidate(nid, scope, actor, owner, jid, guard))
        return Response(data, media_type=row["media_type"], headers={"Cache-Control": "no-store", "X-Asset-SHA256": row["sha256"],
            "X-Asset-Version": str(row["version"]), "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row['filename'], safe='')}"})

    @router.post("/projects/{nid}/studio/production/jobs/{owner}/{jid}/execute")
    def execute(nid: str, owner: Owner, jid: str, request: Request, body: MediaJobAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.execute(nid, scope, actor, owner, jid, body, guard))

    @router.post("/projects/{nid}/studio/production/jobs/video/{jid}/refresh")
    def refresh(nid: str, jid: str, request: Request, body: MediaJobAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.refresh_video(nid, scope, actor, jid, body, guard), model=True)

    @router.post("/projects/{nid}/studio/production/jobs/{owner}/{jid}/cancel")
    def cancel(nid: str, owner: Owner, jid: str, request: Request, body: MediaJobAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.cancel(nid, scope, actor, owner, jid, body, guard))

    @router.post("/projects/{nid}/studio/production/jobs/{owner}/{jid}/review")
    def review(nid: str, owner: Owner, jid: str, request: Request, body: MediaReview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.review", lambda actor, scope, guard: service.review(nid, scope, actor, owner, jid, body, guard))

    @router.post("/projects/{nid}/studio/production/jobs/{owner}/{jid}/reconcile")
    def reconcile(nid: str, owner: Owner, jid: str, request: Request, body: MediaJobAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.reconcile(nid, scope, actor, owner, jid, body, guard))

    @router.get("/projects/{nid}/studio/production/timelines")
    def timelines(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_list(nid, scope, actor, guard))

    @router.post("/projects/{nid}/studio/production/timelines", status_code=201)
    def create_timeline(nid: str, request: Request, body: TimelineSave, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_save(nid, scope, actor, None, body, guard))

    @router.get("/projects/{nid}/studio/production/timelines/{tid}")
    def timeline(nid: str, tid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_get(nid, scope, actor, tid, guard))

    @router.put("/projects/{nid}/studio/production/timelines/{tid}")
    def save_timeline(nid: str, tid: str, request: Request, body: TimelineSave, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_save(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/render")
    def render(nid: str, tid: str, request: Request, body: TimelineRender, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_render(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/edit")
    def edit(nid: str, tid: str, request: Request, body: TimelineEdit, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_edit(nid, scope, actor, tid, body, guard))

    @router.get("/projects/{nid}/studio/production/timelines/{tid}/history")
    def history(nid: str, tid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_history(nid, scope, actor, tid, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/restore")
    def restore(nid: str, tid: str, request: Request, body: TimelineRestore, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_restore(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/export-preview")
    def export_preview(nid: str, tid: str, request: Request, body: TimelineExportPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_export_preview(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/export")
    def export(nid: str, tid: str, request: Request, body: TimelineExport, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_export(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/transfer-preview")
    def transfer_preview(nid: str, tid: str, request: Request, body: TimelineTransferPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_transfer_preview(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/transfer-import")
    def transfer_import(nid: str, tid: str, request: Request, body: TimelineTransferImport, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_transfer_import(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/transfer-attachment")
    def transfer_attachment(nid: str, tid: str, request: Request, body: TimelineTransferDownload, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data, sha256, format = call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_transfer_attachment(nid, scope, actor, tid, body, guard))
        return Response(data, media_type={"OTIO": "application/vnd.opentimelineio+json", "SRT": "application/x-subrip", "VTT": "text/vtt"}[format],
            headers={"Cache-Control": "no-store", "X-Asset-SHA256": sha256, "Content-Disposition": f'attachment; filename="studio-timeline.{format.lower()}"'})

    return router
