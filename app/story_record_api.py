"""Opt-in CAS/history surface for original PROJECT Timeline/Foreshadowing."""
from __future__ import annotations
from typing import Literal
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from .repositories.chapter_repository import VersionConflict

FEATURE = 'story_record_versions_v1'
Kind = Literal['timeline', 'foreshadowing']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)


class VersionIn(StrictModel):
    expected_digest: str | None = Field(pattern=r'^[a-f0-9]{64}$')
    expected_version: int = Field(ge=0)


class SaveIn(VersionIn):
    record: dict
    refresh_sources: bool = False


class RestoreIn(VersionIn):
    restore_version: int = Field(ge=0)
    confirmed: Literal[True]


class FeedbackIn(VersionIn):
    decision: Literal['ACKNOWLEDGED', 'INTENTIONAL', 'NEEDS_REVIEW', 'DISMISSED']
    note: str = Field(default='', max_length=2000)
    evidence: str = Field(default='', max_length=4000)


def create_story_record_router(service, authorize_project, require_flag):
    router=APIRouter(prefix='/novels/{nid}/experimental/story-records', tags=['story-records'])

    def access(nid,token,branch,permission='domain.read'):
        require_flag(FEATURE)
        authorize_project(nid,token,'domain.read',branch)
        identity=authorize_project(nid,token,permission,branch)
        actor=getattr(identity[0],'actor_id','local-user') if identity else 'local-user'
        def again():
            require_flag(FEATURE)
            authorize_project(nid,token,'domain.read',branch)
            if authorize_project(nid,token,permission,branch)!=identity:
                raise HTTPException(403,{'code':'STORY_RECORD_AUTHORITY_CHANGED'})
        return actor,again

    def call(fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except VersionConflict as exc:
            raise HTTPException(409,{'code':'STORY_RECORD_CONFLICT','conflict':exc.as_dict()}) from None
        except (FileNotFoundError,KeyError):raise HTTPException(404,{'code':'STORY_RECORD_NOT_FOUND'}) from None
        except (ValueError,TypeError):raise HTTPException(422,{'code':'STORY_RECORD_INPUT_INVALID'}) from None

    async def body(request,model):
        data=bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data)>128000:raise HTTPException(413,{'code':'STORY_RECORD_INPUT_LIMIT'})
        try:return model.model_validate_json(bytes(data))
        except (ValidationError,ValueError):raise HTTPException(422,{'code':'STORY_RECORD_INPUT_INVALID'}) from None

    @router.get('/catalog')
    def catalog(nid:str,response:Response,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        _,check=access(nid,x_session_token,x_branch_id)
        call(service.get,nid)
        result={'scope':'PROJECT','branch_id':None,'kinds':['timeline','foreshadowing'],'history_limit':20,
                'cancel':'Cancel an unsent local draft; committed writes are recovered by GET and explicit CAS restore.',
                'recovery':'Read current version and bounded history after restart; never retry an uncertain write blindly.'}
        for field,permission in [('can_write','domain.write'),('can_review','domain.review')]:
            try:authorize_project(nid,x_session_token,permission,x_branch_id);result[field]=True
            except HTTPException as exc:
                if exc.status_code not in {401,403,404,409}:raise
                result[field]=False
        check();response.headers['Cache-Control']='no-store';return result

    @router.get('/{kind}/{rid}')
    def get(nid:str,kind:Kind,rid:str,response:Response,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        _,check=access(nid,x_session_token,x_branch_id)
        result=call(service.story_record,nid,kind,rid);check();response.headers['Cache-Control']='no-store';return result

    @router.put('/{kind}/{rid}')
    async def save(nid:str,kind:Kind,rid:str,request:Request,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        actor,check=access(nid,x_session_token,x_branch_id,'domain.write');value=await body(request,SaveIn)
        # Validate with original field types/defaults without accepting unknown
        # metadata/extensions. The repository preserves existing opaque fields.
        from .api import TimelineEventIn,ForeshadowingIn
        from .repositories.structured_cas import FIELDS
        if set(value.record)-(FIELDS[kind]-{'id','privacy_status'}):raise HTTPException(422,{'code':'STORY_RECORD_UNKNOWN_FIELD'})
        try:payload=(TimelineEventIn if kind=='timeline' else ForeshadowingIn).model_validate(value.record).model_dump(exclude_unset=True)
        except ValidationError:raise HTTPException(422,{'code':'STORY_RECORD_INPUT_INVALID'}) from None
        if not str(payload.get('title','')).strip():raise HTTPException(422,{'code':'STORY_RECORD_TITLE_REQUIRED'})
        return await run_in_threadpool(call,service.save_story_record,nid,kind,rid,payload,value.expected_digest,value.expected_version,
                                      actor_id=actor,refresh_sources=value.refresh_sources,check=check)

    @router.post('/{kind}/{rid}/restore')
    async def restore(nid:str,kind:Kind,rid:str,request:Request,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        actor,check=access(nid,x_session_token,x_branch_id,'domain.write');value=await body(request,RestoreIn)
        return await run_in_threadpool(call,service.save_story_record,nid,kind,rid,{},value.expected_digest,value.expected_version,
                                      actor_id=actor,action='RESTORE',restore_version=value.restore_version,check=check)

    @router.post('/{kind}/{rid}/feedback')
    async def feedback(nid:str,kind:Kind,rid:str,request:Request,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
        actor,check=access(nid,x_session_token,x_branch_id,'domain.review');value=await body(request,FeedbackIn)
        return await run_in_threadpool(call,service.save_story_record,nid,kind,rid,{},value.expected_digest,value.expected_version,
                                      actor_id=actor,action='FEEDBACK',feedback=value.model_dump(include={'decision','note','evidence'}),check=check)

    return router
