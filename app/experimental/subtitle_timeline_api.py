from fastapi import APIRouter, Header, HTTPException, Response
from .production_lineage_api import api_call, PrivateProductionRoute
from .subtitle_timeline import SUBTITLE_FLAG, CaptionCreateIn, CaptionUpdateIn, CaptionSplitIn, CaptionMergeIn


def create_subtitle_timeline_router(service, authorize, require_flag):
    router=APIRouter(prefix="/novels/{nid}/experimental/subtitle-timeline", tags=["Experimental subtitle timeline"], route_class=PrivateProductionRoute)
    def invoke(nid,token,branch,permission,callback):
        def access():
            for flag in (SUBTITLE_FLAG,"voice_direction_v2","audiobook_v2"):require_flag(flag)
            return authorize(nid,token,branch,permission)
        actor,scope=access()
        def guard():
            if access() != (actor,scope):raise HTTPException(403,{"code":"CAPTION_AUTHORITY_CHANGED"})
        result=api_call(service.audiobook.as_actor,actor,callback,actor,scope,guard)
        guard();return result
    @router.get("/catalog")
    def catalog(nid:str,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.read",lambda a,s,g:service.catalog(nid,s,a))
    @router.get("/records")
    def records(nid:str,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.read",lambda a,s,g:service.records(nid,s,a))
    @router.post("/records",status_code=201)
    def create(nid:str,body:CaptionCreateIn,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.write",lambda a,s,g:(g(),service.create_track(nid,s,a,body))[1])
    @router.put("/records/{rid}")
    def update(nid:str,rid:str,body:CaptionUpdateIn,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.write",lambda a,s,g:(g(),service.update(nid,s,a,rid,body))[1])
    @router.post("/records/{rid}/cues/{cid}/split")
    def split(nid:str,rid:str,cid:str,body:CaptionSplitIn,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.write",lambda a,s,g:(g(),service.split(nid,s,a,rid,cid,body))[1])
    @router.post("/records/{rid}/cues/{cid}/merge")
    def merge(nid:str,rid:str,cid:str,body:CaptionMergeIn,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        return invoke(nid,x_session_token,x_branch_id,"domain.write",lambda a,s,g:(g(),service.merge(nid,s,a,rid,cid,body))[1])
    @router.get("/records/{rid}/file.{format}")
    def download(nid:str,rid:str,format:str,expected_version:int,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        content=invoke(nid,x_session_token,x_branch_id,"domain.read",lambda a,s,g:service.download(nid,s,a,rid,expected_version,format,g))
        return Response(content,media_type="text/vtt" if format=="vtt" else "application/x-subrip",headers={"Content-Disposition":f'attachment; filename="captions-{rid}.{format}"',"Cache-Control":"no-store"})
    return router
