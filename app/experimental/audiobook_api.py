from fastapi import APIRouter, Header
from pydantic import Field
from .common import api_call
from .media import StrictModel
from .audiobook import (VoiceProfileIn, VoiceMappingIn, AudiobookPlanIn, SegmentUpdateIn, SegmentAudioIn, AudioTrackIn)


class AudioActionIn(StrictModel):
    expected_version: int = Field(ge=1)


def create_audiobook_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/audiobook", tags=["Experimental audiobook"])

    def access(nid, token, branch, permission="domain.read"):
        require_flag("audiobook_v2")
        return authorize(nid, token, branch, permission)

    @router.get("/capabilities")
    def capabilities(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        return service.capabilities()

    @router.get("/profiles")
    def profiles(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.list, nid, scope, service.PROFILES)}

    @router.post("/profiles", status_code=201)
    def profile(nid: str, body: VoiceProfileIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_profile, nid, scope, actor, body)

    @router.get("/mappings")
    def mappings(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.list, nid, scope, service.MAPPINGS)}

    @router.post("/mappings")
    def mapping(nid: str, body: VoiceMappingIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.map_voice, nid, scope, actor, body)

    @router.get("/plans")
    def plans(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.plans, nid, scope)}

    @router.post("/plans", status_code=201)
    def plan(nid: str, body: AudiobookPlanIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_plan, nid, scope, actor, body)

    @router.put("/plans/{rid}/segments/{sid}")
    def segment(nid: str, rid: str, sid: str, body: SegmentUpdateIn,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.update_segment, nid, scope, actor, rid, sid, body)

    @router.put("/plans/{rid}/segments/{sid}/audio")
    def audio(nid: str, rid: str, sid: str, body: SegmentAudioIn,
              x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.bind_audio, nid, scope, actor, rid, sid, body)

    @router.post("/plans/{rid}/tracks")
    def track(nid: str, rid: str, body: AudioTrackIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.add_track, nid, scope, actor, rid, body)

    @router.delete("/plans/{rid}/tracks/{tid}")
    def remove_track(nid: str, rid: str, tid: str, expected_version: int,
                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.remove_track, nid, scope, actor, rid, tid, expected_version)

    @router.get("/plans/{rid}/duration-manifest")
    def duration(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.duration_manifest, nid, scope, rid)

    @router.get("/plans/{rid}/subtitles")
    def subtitles(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.subtitles, nid, scope, rid)

    @router.post("/plans/{rid}/{action}")
    def action(nid: str, rid: str, action: str, body: AudioActionIn,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        permission = "domain.write" if action == "mix" else "domain.review"
        actor, scope = access(nid, x_session_token, x_branch_id, permission)
        if action == "mix":
            def reauthorize():
                if access(nid, x_session_token, x_branch_id, permission) != (actor, scope):
                    raise ValueError("AUDIO_SCOPE_CHANGED")
            return api_call(service.mix, nid, scope, actor, rid, body.expected_version, reauthorize)
        return api_call(service.review, nid, scope, actor, rid, action, body.expected_version)

    @router.get("/mixes")
    def mixes(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": [{k: v for k, v in row.items() if k != "content_base64"}
                          for row in api_call(service.list, nid, scope, service.MIXES)]}

    @router.post("/mixes/{rid}/{action}")
    def mix_review(nid: str, rid: str, action: str, body: AudioActionIn,
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.review")
        return api_call(service.review, nid, scope, actor, rid, action, body.expected_version)

    return router
