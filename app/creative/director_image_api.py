"""Mounted private IMAGE workflow. Browser values are selections, never authority."""
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import Field
from ..experimental.production_lineage_api import PrivateProductionRoute
from ..experimental.director_image_accounting import DirectorImageCostDeclarationInput
from .director_binding import _Frozen, Identifier, Digest
from .director_image_source import ImageAssetSelection
from .director_image_binding import ImageTarget
from .director_image_adoption import ImageAdoptionInput


class Preview(_Frozen):
    asset: ImageAssetSelection
    target: ImageTarget
    provider_id: Identifier
    model_id: Identifier
    instruction: str = Field(min_length=1,max_length=2000)

class Version(_Frozen):
    expected_version: int = Field(ge=1,le=2**53-1)

class Dispatch(Version):
    reviewed_preview_digest: Digest

class Empty(_Frozen):
    pass

class ImageRoute(PrivateProductionRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def bounded(request):
            headers = {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
            try:
                chunks, size = [], 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 32768: raise HTTPException(413,{'code':'DIRECTOR_IMAGE_REQUEST_LIMIT'})
                    chunks.append(chunk)
                request._body = b''.join(chunks)
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422,{'code':'DIRECTOR_IMAGE_REQUEST_INVALID'},headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}),**headers}
                raise
        return bounded


def create_director_image_router(coordinator, invoke, *, require_host_session, model_host_authority):
    router = APIRouter(prefix='/director-image-v3',route_class=ImageRoute)

    def call(request,nid,token,branch,permission,callback,*,recovery=False):
        def operation(actor,scope,guard):
            if require_host_session is None or model_host_authority is None:
                raise HTTPException(403,{'code':'DIRECTOR_IMAGE_HOST_REQUIRED'})
            host = model_host_authority(request,token)
            def current():
                guard(); require_host_session(token); host.guard()
                if not host.principal: raise HTTPException(403,{'code':'DIRECTOR_IMAGE_HOST_REQUIRED'})
            current()
            try:
                result = callback(actor,scope,current,host)
            except HTTPException:
                current(); raise
            except FileNotFoundError:
                current(); raise HTTPException(404,{'code':'DIRECTOR_IMAGE_NOT_FOUND'}) from None
            except Exception as exc:
                current()
                # Only fixed known public codes, never lower-owner exception text.
                code = 'DIRECTOR_IMAGE_ACTION_UNAVAILABLE'
                if type(exc) is ValueError and str(exc) == 'DIRECTOR_IMAGE_BROKER_ADMISSION_BLOCKED':
                    code = str(exc)
                raise HTTPException(409,{'code':code}) from None
            current()
            return result
        with coordinator.store.existing_owner_only():
            return invoke(nid,token,branch,permission,operation,gated=not recovery)

    @router.get('/capabilities')
    def capabilities(nid: str,request: Request,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        def observe(actor,scope,guard,host):
            from ..experimental.flags import enabled_flags
            required = {'ai_execution_v2','narrative_production_v2','asset_lineage_v2','model_broker_v2','author_context_inspector_v2'}
            from ..model_runtime import Modality
            choices = []
            for model in coordinator.node.models.descriptors():
                if model.modality is not Modality.VISION or not model.enabled or 'IMAGE_UNDERSTANDING' not in model.capabilities:
                    continue
                try: coordinator.node.binding(model.provider_id,model.model_id)
                except Exception: continue
                choices.append({'provider_id':model.provider_id,'model_id':model.model_id,'display_name':model.display_name})
            return {'registered_choices':choices[:100], 'contract':'DIRECTOR_IMAGE_CAPABILITIES_V3' ,'enabled':required.issubset(enabled_flags()),
                'local_only':True,'automatic_retry':False,'automatic_fallback':False,
                'measurement_verified':False,'observations_verified':False,
                'recovery_available':True,'vision_registration_required':True}
        return call(request,nid,x_session_token,x_branch_id,'domain.read',observe,recovery=True)

    @router.get('/proposals')
    def listing(nid: str,request: Request,limit: int=Query(30,ge=1,le=50),x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        return call(request,nid,x_session_token,x_branch_id,'domain.read',lambda a,s,g,h:coordinator.list_owned(nid,s,a,host=h,guard=g,limit=limit),recovery=True)

    @router.get('/proposals/{rid}')
    def status(nid: str,rid: str,request: Request,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        return call(request,nid,x_session_token,x_branch_id,'domain.read',lambda a,s,g,h:coordinator.status(nid,s,a,rid,host=h,guard=g),recovery=True)

    @router.post('/preview')
    def preview(nid: str,request: Request,body: Preview,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        def action(a,s,g,h):
            row=coordinator.preview(nid,s,a,**body.model_dump(),host=h,guard=g)
            return {'id':row['id'],'version':row['version'],'status':row['status'],
                'preview_digest':row['binding']['preview_digest'],'preview':row['preview'],
                'model_called':False,'measurement_verified':False,'observations_verified':False}
        return call(request,nid,x_session_token,x_branch_id,'domain.write',action)

    @router.post('/proposals/{rid}/dispatch')
    def dispatch(nid: str,rid: str,request: Request,body: Dispatch,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        def action(a,s,g,h):
            coordinator.dispatch(nid,s,a,rid,**body.model_dump(),host=h,guard=g)
            return coordinator.status(nid,s,a,rid,host=h,guard=g)
        return call(request,nid,x_session_token,x_branch_id,'domain.write',action)

    @router.post('/proposals/{rid}/cancel')
    def cancel(nid: str,rid: str,request: Request,body: Empty,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        return call(request,nid,x_session_token,x_branch_id,'domain.write',lambda a,s,g,h:coordinator.cancel(nid,s,a,rid,host=h,guard=g),recovery=True)

    @router.post('/proposals/{rid}/prepare-review')
    def pending(nid: str,rid: str,request: Request,body: Version,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        def action(a,s,g,h):
            row=coordinator.prepare_pending(nid,s,a,rid,**body.model_dump(),host=h,guard=g)
            ledger=coordinator.broker.get(nid,s,coordinator.broker.LEDGER,row['reservation_id'])
            return {'id':row['id'],'version':row['version'],'status':row['status'],'pending':row['pending'],
                'accounting_version':ledger['version']}
        return call(request,nid,x_session_token,x_branch_id,'domain.write',action)

    @router.post('/proposals/{rid}/declare-cost')
    def declare(nid: str,rid: str,request: Request,body: DirectorImageCostDeclarationInput,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        return call(request,nid,x_session_token,x_branch_id,'domain.write',lambda a,s,g,h:coordinator.declare_cost(nid,s,a,rid,body.model_dump(),host=h,guard=g))

    @router.post('/proposals/{rid}/review')
    def review(nid: str,rid: str,request: Request,body: Empty,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        return call(request,nid,x_session_token,x_branch_id,'domain.read',lambda a,s,g,h:coordinator.review(nid,s,a,rid,host=h,guard=g))

    @router.post('/proposals/{rid}/adopt')
    def adopt(nid: str,rid: str,request: Request,body: ImageAdoptionInput,x_session_token: str | None=Header(None),x_branch_id: str | None=Header(None)):
        return call(request,nid,x_session_token,x_branch_id,'domain.write',lambda a,s,g,h:coordinator.adopt(nid,s,a,rid,body.model_dump(),host=h,guard=g))
    return router
