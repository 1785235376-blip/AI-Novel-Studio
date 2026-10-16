"""Original adaptation routes, with one proposal authority and explicit recovery."""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from .authorization import AuthorizationScope, ScopeKind, ModalityDomain, DomainRole, DomainRoleAssignment
from .repositories.chapter_repository import VersionConflict
from .services.adaptation_service import FEATURE, enabled
from .experimental.flags import require_flag

class ProposalIn(BaseModel):
    target: str
    title: str = Field(default="",max_length=200)
    instruction: str = Field(default="",max_length=8000)
class RevisionIn(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0, strict=True)
class BlueprintIn(RevisionIn):
    focus: str
    pacing: str
    format: str
    constraints: list[str] = []
    chapter_map: list[dict] = []
class GenerateIn(RevisionIn):
    mode: str = "deterministic"
    provider_id: str | None = None
    model_id: str | None = None
class ReviewIn(RevisionIn):
    decision: str
    note: str = ""


def create_adaptation_router(service, host):
    router = APIRouter()
    def context(nid, branch, token, permission):
        if branch and callable(service.branch_authority):require_flag("branch_manuscript_v1")
        if not branch and host['collaboration_scope_service'].repository.project_workspace(nid):
            return host['_authorize_novel_project'](nid,token,permission)
        return host['_adaptation_context'](nid,branch,token,permission)
    def authority(nid,branch,token,permission):
        actor,scope=context(nid,branch,token,permission)
        lifecycle_enabled=enabled()
        def check():
            if lifecycle_enabled:require_flag(FEATURE)
            if context(nid,branch,token,permission)!=(actor,scope):raise HTTPException(403,{'code':'ADAPTATION_AUTHORITY_CHANGED'})
        return actor,scope,check
    def revision(value):
        if enabled() and value is None:raise HTTPException(428,{'code':'ADAPTATION_REVISION_REQUIRED'})
        return value
    def call(fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except VersionConflict as exc:raise HTTPException(409,{'code':'VERSION_CONFLICT','conflict':exc.as_dict()}) from exc
        except (FileNotFoundError,KeyError) as exc:raise HTTPException(404,{'code':'ADAPTATION_SOURCE_OR_RECORD_MISSING'}) from exc
        except PermissionError as exc:raise HTTPException(403,{'code':'ADAPTATION_FORBIDDEN'}) from exc
        except ValueError as exc:
            text=str(exc);status=409 if any(word in text for word in ('RECOVERY','RECONCILIATION','CLAIM','CHANGED','CAPACITY')) else 400
            raise HTTPException(status,{'code':text if text.isupper() else 'ADAPTATION_INVALID','message':text}) from exc
    def audit(actor,scope,action,row):
        if actor:host['audit_service'].append(host['audit_service'].build(actor,action,'AdaptationProposal',row['id'],scope,{'novel_id':row['novel_id'],'branch_id':row.get('branch_id'),'status':row['status'],'result_version':row.get('revision')}))
    def target_scope(item):
        target=item.get('adapted_scope')
        if not target:raise ValueError('ADAPTATION_TARGET_SCOPE_MISSING')
        return AuthorizationScope(ScopeKind.BRANCH,target['workspace_id'],target['project_id'],target['storyline_id'],target['branch_id'])
    def check_target(actor,item,permission='domain.write'):
        if actor:host['membership_authorization_service'].require(actor,permission,ModalityDomain.NOVEL,target_scope(item))
    def team_callbacks(actor,check):
        def create(item):
            check();reserved=item['materialization']
            created=host['collaboration_admin_service'].path_mutations.create_project(actor.workspace_id,item['title'],f"Adaptation:{item['target']}",actor,**{key:reserved[key] for key in ('project_id','storyline_id','branch_id')})
            scopes=host['collaboration_scope_service'].repository
            story=scopes.list('storylines',workspace_id=actor.workspace_id,project_id=created['id'])[0]
            branch=scopes.list('branches',workspace_id=actor.workspace_id,project_id=created['id'],storyline_id=story['id'])[0]
            target={'workspace_id':actor.workspace_id,'project_id':created['id'],'storyline_id':story['id'],'branch_id':branch['id']}
            from uuid import uuid4
            check();host['authorization_service'].assign_role(DomainRoleAssignment(str(uuid4()),actor.actor_id,DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.PROJECT,actor.workspace_id,created['id']),actor.actor_id))
            return {**created,'scope':target}
        def chapter(item,snapshot):
            check();check_target(actor,item)
            return host['collaboration_application_service'].create_chapter(actor=actor,scope=target_scope(item),title=snapshot['title'])
        def save(item,cid,document,version):
            check();check_target(actor,item)
            return host['collaboration_application_service'].update_chapter(actor=actor,scope=target_scope(item),chapter_id=cid,document=document,expected_version=version,reason='AI_ACCEPT')
        return create,chapter,save

    @router.get('/novels/{nid}/adaptations/catalog')
    def catalog(nid:str,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        _,_,check=authority(nid,branch_id,x_session_token,'domain.read')
        allowed={}
        for capability,permission in [('can_write','domain.write'),('can_review','domain.review')]:
            try:context(nid,branch_id,x_session_token,permission);allowed[capability]=True
            except HTTPException:allowed[capability]=False
        check()
        from .repositories import adaptation_versions as limits
        capacity={'proposals_per_project':limits.MAX_PROPOSALS,'source_chapters':limits.MAX_SOURCE_CHAPTERS,'source_bytes':limits.MAX_SOURCE_BYTES,'history_entries':limits.MAX_REVISIONS,'reserved_finalization_entries':limits.FINALIZATION_RESERVE,'proposal_bytes':limits.MAX_PROPOSAL_BYTES,'reserved_finalization_bytes':limits.FINALIZATION_BYTES,'manifest_draft_bytes':limits.MAX_MANIFEST_DRAFT_BYTES,'attempts_per_task':limits.MAX_ATTEMPTS,'automatic_eviction':False}
        return {'limits':capacity,'feature':FEATURE,'enabled':enabled(),'owner':'NovelRepository.adaptation_proposals','scope':'branch' if branch_id else 'project','revision_field':'revision','model_runtime':'NOT_CONFIGURED','mock_runtime':'MOCK_ONLY','automatic_resume':False,'states':['DRAFT','APPROVED','MATERIALIZING','MATERIALIZED','PENDING_REWRITE','RUNNING','AWAITING_REVIEW','ACCEPTED','REJECTED','APPLYING','APPLIED','CANCELLED','FAILED','RECOVERY_REQUIRED','NOT_CONFIGURED'],**allowed}

    @router.get('/novels/{nid}/adaptations')
    def listing(nid:str,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        _,_,check=authority(nid,branch_id,x_session_token,'domain.read');rows=call(service.list,nid,branch_id);check()
        return [row for row in rows if not row.get('lifecycle_version') or enabled()]

    @router.post('/novels/{nid}/adaptations',status_code=201)
    def create(nid:str,body:ProposalIn,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        actor,scope,check=authority(nid,branch_id,x_session_token,'domain.write')
        raw={'kind':scope.kind.value,**{key:getattr(scope,key) for key in ('workspace_id','project_id','storyline_id','branch_id')}} if scope else None
        result=call(service.create,nid,body.target,body.title,body.instruction,branch_id,raw,check);audit(actor,scope,'ADAPTATION_PROPOSAL_CREATED',result);return result

    @router.put('/novels/{nid}/adaptations/{proposal_id}/blueprint')
    def blueprint(nid:str,proposal_id:str,body:BlueprintIn,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        actor,scope,check=authority(nid,branch_id,x_session_token,'domain.write')
        result=call(service.update_blueprint,nid,proposal_id,body.model_dump(),branch_id,revision(body.expected_revision),check);audit(actor,scope,'ADAPTATION_BLUEPRINT_UPDATED',result);return result

    @router.post('/novels/{nid}/adaptations/{proposal_id}/approve')
    def approve(nid:str,proposal_id:str,body:RevisionIn|None=None,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        actor,scope,check=authority(nid,branch_id,x_session_token,'domain.review')
        result=call(service.approve,nid,proposal_id,branch_id,revision(body.expected_revision if body else None),check);audit(actor,scope,'ADAPTATION_PROPOSAL_APPROVED',result);return result

    @router.post('/novels/{nid}/adaptations/{proposal_id}/materialize',status_code=201)
    def materialize(nid:str,proposal_id:str,body:RevisionIn|None=None,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        actor,scope,check=authority(nid,branch_id,x_session_token,'domain.write')
        expected=revision(body.expected_revision if body else None)
        current=call(service.get,nid,proposal_id,branch_id)
        if current.get('adapted_scope'):call(check_target,actor,current)
        options={}
        if actor:
            if callable(service.branch_authority):require_flag('branch_manuscript_v1')
            create,chapter,save=team_callbacks(actor,check);options={'create_project':create,'create_chapter':chapter,'save_chapter':save}
        result=call(service.materialize,nid,proposal_id,branch_id,expected,check,**options)
        audit(actor,scope,'ADAPTATION_MATERIALIZED',service.get(nid,proposal_id,branch_id));return result

    @router.post('/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/generate')
    def generate(nid:str,proposal_id:str,task_id:str,body:GenerateIn,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        actor,_,check=authority(nid,branch_id,x_session_token,'domain.write')
        item=call(service.get,nid,proposal_id,branch_id)
        def both():check();check_target(actor,item)
        result=call(service.generate_draft,nid,proposal_id,task_id,body.mode,body.provider_id,body.model_id,branch_id,both,revision(body.expected_revision));check();return result

    @router.post('/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/review')
    def review(nid:str,proposal_id:str,task_id:str,body:ReviewIn,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        actor,_,check=authority(nid,branch_id,x_session_token,'domain.review');item=call(service.get,nid,proposal_id,branch_id)
        def both():check();check_target(actor,item,'domain.review')
        return call(service.review_draft,nid,proposal_id,task_id,body.decision,body.note,branch_id,revision(body.expected_revision),both)

    @router.post('/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/apply')
    def apply(nid:str,proposal_id:str,task_id:str,body:RevisionIn|None=None,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        actor,scope,check=authority(nid,branch_id,x_session_token,'domain.write');item=call(service.get,nid,proposal_id,branch_id)
        def both():check();check_target(actor,item)
        options={'save_chapter':team_callbacks(actor,check)[2]} if actor else {}
        result=call(service.apply_draft,nid,proposal_id,task_id,branch_id,revision(body.expected_revision if body else None),both,**options)
        audit(actor,scope,'ADAPTATION_DRAFT_APPLIED',service.get(nid,proposal_id,branch_id));return result

    @router.get('/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}')
    def task_detail(nid:str,proposal_id:str,task_id:str,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        require_flag(FEATURE);actor,_,check=authority(nid,branch_id,x_session_token,'domain.read')
        item=call(service.get,nid,proposal_id,branch_id);call(check_target,actor,item,'domain.read')
        _,_,task=call(service._task,item,task_id);stale=False
        try:service._source(item,{'chapter_id':task['source_chapter_id'],'version':task['source_version']},current_required=True)
        except VersionConflict:stale=True
        except (FileNotFoundError,KeyError):raise HTTPException(404,{'code':'ADAPTATION_SOURCE_OR_RECORD_MISSING'}) from None
        from .services.adaptation_service import digest
        current=call(service._chapters(item,True).get,task['target_chapter_id'])
        target_version=task.get('result_version') if task['status']=='APPLIED' else task.get('target_version')
        target_digest=task.get('result_digest') if task['status']=='APPLIED' else task.get('target_digest')
        if target_version is not None and (current['version']!=target_version or digest(current['document'])!=target_digest):stale=True
        check();call(check_target,actor,item,'domain.read')
        return {'proposal_id':proposal_id,'proposal_revision':item['revision'],'task':task,'stale':stale,'automatic_resume':False}

    @router.get('/novels/{nid}/adaptations/{proposal_id}/history')
    def history(nid:str,proposal_id:str,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        require_flag(FEATURE);_,_,check=authority(nid,branch_id,x_session_token,'domain.read');item=call(service.get,nid,proposal_id,branch_id);check()
        return {'revision':item['revision'],'items':item.get('revision_history',[]),'materialization':item.get('materialization'),'automatic_resume':False}

    @router.post('/novels/{nid}/adaptations/{proposal_id}/actions/{action}')
    def action(nid:str,proposal_id:str,action:str,body:RevisionIn,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        require_flag(FEATURE);_,_,check=authority(nid,branch_id,x_session_token,'domain.write')
        return call(service.action,nid,proposal_id,action,branch_id,revision(body.expected_revision),check=check)

    @router.post('/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/actions/{action}')
    def task_action(nid:str,proposal_id:str,task_id:str,action:str,body:RevisionIn,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        require_flag(FEATURE);actor,_,check=authority(nid,branch_id,x_session_token,'domain.write');item=call(service.get,nid,proposal_id,branch_id)
        def both():check();check_target(actor,item)
        return call(service.action,nid,proposal_id,action,branch_id,revision(body.expected_revision),task_id,both)
    return router
