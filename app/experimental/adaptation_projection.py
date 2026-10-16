"""Read-through task/review views of original adaptation execution manifests.

No executor, task store or alternate approval route. Opening an exact proposal
and task returns to the original source/target-bound human review surface.
"""
from copy import deepcopy
from fastapi import HTTPException
from ..authorization import AuthorizationScope, ScopeKind, ModalityDomain
from ..repositories.chapter_repository import VersionConflict
from ..services.adaptation_service import FEATURE
from .inbox import ReviewBinding
from .ux import TaskReader


def adaptation_reader(service, legacy, require_flag):
    def read(ctx):
        def authority():
            require_flag(FEATURE)
            if ctx.branch and callable(service.branch_authority):require_flag('branch_manuscript_v1')
            if not ctx.branch and legacy.collaboration_scope_service.repository.project_workspace(ctx.novel_id):
                actor,scope=legacy._authorize_novel_project(ctx.novel_id,ctx.token,'domain.read')
            else:actor,scope=legacy._adaptation_context(ctx.novel_id,ctx.branch,ctx.token,'domain.read')
            if actor:
                if ctx.actor!=actor.actor_id or ctx.scope.get('novel_id')!=ctx.novel_id or ctx.scope.get('branch_id')!=ctx.branch or ctx.scope.get('workspace_id')!=scope.workspace_id:
                    raise HTTPException(403,{'code':'ADAPTATION_PROJECTION_SCOPE_CHANGED'})
                if ctx.branch and ctx.scope.get('storyline_id')!=scope.storyline_id:raise HTTPException(403,{'code':'ADAPTATION_PROJECTION_SCOPE_CHANGED'})
            elif ctx.actor!='local-author' or ctx.scope!={'mode':'local','novel_id':ctx.novel_id}:
                raise HTTPException(403,{'code':'ADAPTATION_PROJECTION_SCOPE_CHANGED'})
            return actor
        actor=authority();output=[];target_scopes=[]
        for proposal in service.list(ctx.novel_id,ctx.branch)[-200:]:
            authority()
            target=proposal.get('adapted_scope')
            if actor and target:
                target_scope=AuthorizationScope(ScopeKind.BRANCH,target['workspace_id'],target['project_id'],target['storyline_id'],target['branch_id'])
                try:legacy.membership_authorization_service.require(actor,'domain.read',ModalityDomain.NOVEL,target_scope)
                except PermissionError:continue
                target_scopes.append(target_scope)
            for task in proposal.get('execution_manifest',[]):
                stale=False;reasons=[]
                try:service._source(proposal,{'chapter_id':task['source_chapter_id'],'version':task['source_version']},current_required=True)
                except (VersionConflict,FileNotFoundError,KeyError,ValueError):stale=True;reasons.append('SOURCE_CHANGED_OR_MISSING')
                if task.get('target_version') is not None and task['status']!='APPLIED':
                    try:service._check_target(proposal,task)
                    except (VersionConflict,FileNotFoundError,KeyError):stale=True;reasons.append('TARGET_CHANGED_OR_MISSING')
                navigation={'kind':'feature','feature':FEATURE,'task_authority':'adaptation','id':task['id'],'parent_id':proposal['id'],'novel_id':ctx.novel_id,'branch_id':ctx.branch,'chapter_id':task['source_chapter_id'],'version':proposal['revision'],'proposal_revision':proposal['revision'],'source_version':task['source_version'],'source_digest':task.get('source_digest'),'target_chapter_id':task['target_chapter_id'],'target_version':task.get('target_version'),'target_digest':task.get('target_digest')}
                output.append({'id':task['id'],'novel_id':ctx.novel_id,'scope':deepcopy(ctx.scope),'branch_id':ctx.branch,
                    'proposal_id':proposal['id'],'proposal_revision':proposal['revision'],'version':proposal['revision'],
                    'status':task['status'],'recovery_required':task['status'] in {'RUNNING','APPLYING','RECOVERY_REQUIRED'},
                    'stale':stale,'stale_reasons':reasons,'source_navigation':navigation,'target':navigation,
                    'source_versions':{'source_chapter_id':task['source_chapter_id'],'source_version':task['source_version'],'source_digest':task.get('source_digest'),'target_chapter_id':task['target_chapter_id'],'target_version':task.get('target_version'),'target_digest':task.get('target_digest'),'proposal_revision':proposal['revision']},
                    'preview':f"{proposal['title']} · {task['unit']}",'allowed_actions':[],'batch_safe':False,
                    'risk':'SOURCE_TARGET_BOUND_REVIEW','error_code':task.get('error_code'),'history':[],
                    'created_at':task.get('generation_started_at',proposal['created_at'])})
                if len(output)>=200:break
            if len(output)>=200:break
        authority()
        for target_scope in target_scopes:
            try:legacy.membership_authorization_service.require(actor,'domain.read',ModalityDomain.NOVEL,target_scope)
            except PermissionError as exc:raise HTTPException(403,{'code':'ADAPTATION_PROJECTION_TARGET_REVOKED'}) from exc
        return output
    return read


def mount_adaptation_projections(workspace, inbox, service, legacy, require_flag):
    read=adaptation_reader(service,legacy,require_flag)
    workspace.task_readers += (TaskReader(name='adaptation',label='改编原任务',feature=FEATURE,read=read,flag=FEATURE),)
    inbox.register(ReviewBinding('adaptation',read,feature=FEATURE))
