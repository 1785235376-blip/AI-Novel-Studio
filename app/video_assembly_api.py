from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

class VideoClipIn(BaseModel):
    asset_id:str=Field(min_length=1,max_length=240)
    start_ms:int=Field(default=0,ge=0)
    end_ms:int|None=Field(default=None,gt=0)

class VideoAssemblyIn(BaseModel):
    clips:list[VideoClipIn]=Field(min_length=1,max_length=30)

def create_video_assembly_router(service):
    router=APIRouter()
    def scope(nid,screenplay_id,token,branch,permission):
        from .api import _authorize_motion,settings,trusted_session_resolver
        _authorize_motion(nid,screenplay_id,token,permission,branch)
        return (branch,trusted_session_resolver.resolve(token).actor_id) if settings.enable_collaboration_runtime else (None,'local-author')
    @router.get('/novels/{nid}/screenplays/{screenplay_id}/video-assemblies')
    def listing(nid:str,screenplay_id:str,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        branch,actor=scope(nid,screenplay_id,x_session_token,x_branch_id,'domain.read')
        return {'items':[row for row in service.list(nid,branch,actor) if row['screenplay_id']==screenplay_id]}
    @router.post('/novels/{nid}/screenplays/{screenplay_id}/video-assemblies',status_code=202)
    def create(nid:str,screenplay_id:str,body:VideoAssemblyIn,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        branch,actor=scope(nid,screenplay_id,x_session_token,x_branch_id,'domain.write')
        try:return service.create(nid,branch,actor,screenplay_id,[clip.model_dump() for clip in body.clips])
        except FileNotFoundError:raise HTTPException(404,{'code':'VIDEO_ASSET_NOT_FOUND'})
        except ValueError as exc:raise HTTPException(400,{'code':'VIDEO_ASSEMBLY_INVALID','message':str(exc)})
    return router
