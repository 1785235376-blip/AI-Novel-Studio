from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from .authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, PermissionAssignment, ScopeKind
from .collaboration_admin_contracts import BranchAdminView, BranchCreateRequest, MemberAdminView, MemberStatusRequest, PermissionExplanationView, PermissionGrantRequest, ProjectAdminView, ProjectCreateRequest, RoleGrantRequest, StorylineAdminView, StorylineCreateRequest, WorkspaceAdminList, WorkspaceAdminView, WorkspaceCreateRequest, WorkspaceNavigationContext, WorkspaceRenameRequest
from .identity import IdentityStatus, WorkspaceMembership


def _error(status: int, code: str, detail: str | None = None) -> HTTPException:
    return HTTPException(status, {"code": code, "detail": detail})


def _scope(value: dict) -> AuthorizationScope:
    try:
        return AuthorizationScope(ScopeKind(value["kind"]), value["workspace_id"], value.get("project_id"), value.get("storyline_id"), value.get("branch_id"))
    except (KeyError, ValueError, TypeError) as exc:
        raise _error(422, "INVALID_SCOPE", str(exc)) from exc


class CollaborationAdminService:
    """Actor-authorized administration boundary. Actor identity is session-owned."""

    def __init__(self, *, sessions, identity, authorization, scopes, workspace_mutations=None, path_mutations=None):
        self.sessions, self.identity, self.authorization, self.scopes = sessions, identity, authorization, scopes
        self.workspace_mutations = workspace_mutations
        self.path_mutations = path_mutations

    def trusted_actor(self, token: str | None):
        if not token: raise _error(401, "SESSION_REQUIRED")
        try: return self.sessions.resolve(token)
        except KeyError as exc: raise _error(401, "INVALID_SESSION") from exc

    def actor(self, token: str | None, workspace_id: str):
        actor = self.trusted_actor(token)
        try: self.identity.require_active_membership(actor.actor_id, workspace_id)
        except KeyError as exc: raise _error(404, "WORKSPACE_NOT_FOUND") from exc
        except PermissionError as exc: raise _error(403, "INACTIVE_MEMBERSHIP", str(exc)) from exc
        return actor

    def create_workspace(self, token: str | None, workspace_id: str, name: str):
        actor = self.trusted_actor(token)
        try: self.identity.require_active_membership(actor.actor_id, actor.workspace_id)
        except KeyError as exc: raise _error(404, "WORKSPACE_NOT_FOUND") from exc
        except PermissionError as exc: raise _error(403, "INACTIVE_MEMBERSHIP", str(exc)) from exc
        self.require_admin(actor, actor.workspace_id)
        if self.workspace_mutations is None: raise _error(501, "WORKSPACE_MUTATION_NOT_SUPPORTED")
        try: return self.workspace_mutations.create_workspace(workspace_id, name, actor.actor_id)
        except FileExistsError as exc: raise _error(409, "WORKSPACE_ALREADY_EXISTS", str(exc)) from exc

    def rename_workspace(self, token: str | None, workspace_id: str, name: str):
        actor = self.actor(token, workspace_id)
        self.require_admin(actor, workspace_id)
        if self.workspace_mutations is None: raise _error(501, "WORKSPACE_MUTATION_NOT_SUPPORTED")
        try: return self.workspace_mutations.rename_workspace(workspace_id, name, actor.actor_id)
        except KeyError as exc: raise _error(404, "WORKSPACE_NOT_FOUND") from exc

    @staticmethod
    def workspace_scope(workspace_id: str) -> AuthorizationScope:
        return AuthorizationScope(ScopeKind.WORKSPACE, workspace_id)

    def require_admin(self, actor, workspace_id: str):
        try: self.authorization.require(actor.actor_id, "workspace.admin", ModalityDomain.NOVEL, self.workspace_scope(workspace_id))
        except PermissionError as exc: raise _error(403, "ADMIN_REQUIRED", str(exc)) from exc

    def require_domain_manager(self, actor, domain: ModalityDomain, scope: AuthorizationScope):
        if self.authorization.is_allowed(actor.actor_id, "workspace.admin", domain, self.workspace_scope(scope.workspace_id)): return
        try: self.authorization.require(actor.actor_id, "domain.write", domain, scope)
        except PermissionError as exc: raise _error(403, "DOMAIN_MANAGER_REQUIRED", str(exc)) from exc

    def validate_target(self, workspace_id: str, principal_id: str, scope: AuthorizationScope):
        if scope.workspace_id != workspace_id: raise _error(403, "SCOPE_WORKSPACE_MISMATCH")
        try:
            self.identity.require_active_membership(principal_id, workspace_id)
            self.authorization._validate_scope(scope)
        except KeyError as exc: raise _error(404, "TARGET_NOT_FOUND") from exc
        except ValueError as exc: raise _error(422, "INVALID_SCOPE", str(exc)) from exc
        except PermissionError as exc: raise _error(409, "TARGET_NOT_ACTIVE", str(exc)) from exc


def create_collaboration_admin_router(
    service: CollaborationAdminService, *, prefix: str = "/api/collaboration/admin",
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["collaboration-admin"])

    @router.get("/workspaces", response_model=WorkspaceAdminList)
    def workspaces(x_session_token: str | None = Header(None)):
        if not x_session_token: raise _error(401, "SESSION_REQUIRED")
        try: actor = service.sessions.resolve(x_session_token)
        except KeyError as exc: raise _error(401, "INVALID_SESSION") from exc
        rows=[]
        for membership in service.identity.repository.list_memberships(user_id=actor.actor_id, status="ACTIVE"):
            workspace=service.scopes.get_workspace(membership["workspace_id"])
            rows.append(WorkspaceAdminView(id=workspace["id"], name=workspace["name"]))
        return WorkspaceAdminList(items=rows)

    @router.post("/workspaces", response_model=WorkspaceAdminView, status_code=201)
    def create_workspace(body: WorkspaceCreateRequest, x_session_token: str | None = Header(None)):
        return service.create_workspace(x_session_token, body.id, body.name)

    @router.patch("/workspaces/{w}", response_model=WorkspaceAdminView)
    def rename_workspace(w: str, body: WorkspaceRenameRequest, x_session_token: str | None = Header(None)):
        return service.rename_workspace(x_session_token, w, body.name)

    @router.get("/workspaces/{w}/navigation", response_model=WorkspaceNavigationContext)
    def workspace_navigation(w: str, x_session_token: str | None = Header(None)):
        service.actor(x_session_token, w)
        try:
            paths = service.scopes.navigation_paths(w)
        except (KeyError, ValueError) as exc:
            raise _error(404, "WORKSPACE_NOT_FOUND") from exc
        return WorkspaceNavigationContext(workspace_id=w, eligible_paths=paths, default_path=paths[0] if paths else None)

    @router.get("/workspaces/{w}/projects", response_model=list[ProjectAdminView])
    def projects(w: str, x_session_token: str | None = Header(None)):
        service.actor(x_session_token, w)
        return [service.scopes.novels.get(row["id"]) for row in service.scopes.repository.list("project_workspaces", workspace_id=w)]

    @router.post("/workspaces/{w}/projects", response_model=ProjectAdminView, status_code=201)
    def create_project(w: str, body: ProjectCreateRequest, x_session_token: str | None = Header(None)):
        actor=service.actor(x_session_token,w);service.require_admin(actor,w)
        if service.path_mutations is None: raise _error(501,"PATH_MUTATION_NOT_SUPPORTED")
        return service.path_mutations.create_project(w,body.title,body.genre,actor)

    @router.get("/workspaces/{w}/projects/{p}/storylines", response_model=list[StorylineAdminView])
    def storylines(w:str,p:str,x_session_token:str|None=Header(None)):
        service.actor(x_session_token,w)
        try:return service.scopes.list_storylines(w,p)
        except (KeyError,ValueError) as exc:raise _error(404,"PROJECT_NOT_FOUND") from exc

    @router.post("/workspaces/{w}/projects/{p}/storylines", response_model=StorylineAdminView, status_code=201)
    def create_storyline(w:str,p:str,body:StorylineCreateRequest,x_session_token:str|None=Header(None)):
        actor=service.actor(x_session_token,w);scope=AuthorizationScope(ScopeKind.PROJECT,w,p);service.require_domain_manager(actor,ModalityDomain.NOVEL,scope)
        if service.path_mutations is None:raise _error(501,"PATH_MUTATION_NOT_SUPPORTED")
        try:return service.path_mutations.create_storyline(w,p,body.name,actor)
        except KeyError as exc:raise _error(404,"PROJECT_NOT_FOUND") from exc

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches", response_model=list[BranchAdminView])
    def branches(w:str,p:str,s:str,x_session_token:str|None=Header(None)):
        service.actor(x_session_token,w)
        try:return service.scopes.list_branches(w,p,s)
        except (KeyError,ValueError) as exc:raise _error(404,"STORYLINE_NOT_FOUND") from exc

    @router.post("/workspaces/{w}/projects/{p}/storylines/{s}/branches", response_model=BranchAdminView, status_code=201)
    def create_branch(w:str,p:str,s:str,body:BranchCreateRequest,x_session_token:str|None=Header(None)):
        actor=service.actor(x_session_token,w);scope=AuthorizationScope(ScopeKind.STORYLINE,w,p,s);service.require_domain_manager(actor,ModalityDomain.NOVEL,scope)
        if service.path_mutations is None:raise _error(501,"PATH_MUTATION_NOT_SUPPORTED")
        try:return service.path_mutations.create_branch(w,p,s,body.name,actor)
        except KeyError as exc:raise _error(404,"STORYLINE_NOT_FOUND") from exc

    @router.get("/workspaces/{w}/members", response_model=list[MemberAdminView])
    def members(w: str, x_session_token: str | None = Header(None)):
        actor=service.actor(x_session_token,w);service.require_admin(actor,w)
        values=[]
        for membership in service.identity.repository.list_memberships(workspace_id=w):
            user=service.identity.get_user(membership["user_id"])
            roles=[x for x in service.authorization.repository.list_role_assignments(user.id) if x["scope"]["workspace_id"]==w]
            permissions=[x for x in service.authorization.repository.list_permission_assignments(user.id) if x["scope"]["workspace_id"]==w]
            values.append(MemberAdminView(user_id=user.id,display_name=user.display_name,membership_id=membership["id"],status=membership["status"],roles=roles,permissions=permissions))
        return values

    @router.post("/workspaces/{w}/members/{user_id}", response_model=MemberAdminView)
    def add_member(w: str,user_id: str,x_session_token: str|None=Header(None)):
        actor=service.actor(x_session_token,w);service.require_admin(actor,w)
        try:
            user=service.identity.get_user(user_id)
            membership=service.identity.add_membership_with_audit(WorkspaceMembership(f"membership:{w}:{user_id}",user_id,w), service.authorization._audit_event(actor.actor_id,"MEMBER_ADDED","WorkspaceMembership",f"membership:{w}:{user_id}",service.workspace_scope(w),{"user_id":user_id,"status":"ACTIVE"}))
        except KeyError as exc: raise _error(404,"USER_NOT_FOUND") from exc
        except ValueError as exc: raise _error(409,"MEMBER_ALREADY_EXISTS",str(exc)) from exc
        return MemberAdminView(user_id=user.id,display_name=user.display_name,membership_id=membership.id,status=membership.status.value)

    @router.patch("/workspaces/{w}/members/{user_id}/status")
    def member_status(w:str,user_id:str,body:MemberStatusRequest,x_session_token:str|None=Header(None)):
        actor=service.actor(x_session_token,w);service.require_admin(actor,w)
        try: status=IdentityStatus(body.status)
        except ValueError as exc: raise _error(422,"INVALID_MEMBER_STATUS") from exc
        try:
            result=service.identity.set_membership_status_with_audit(user_id,w,status, service.authorization._audit_event(actor.actor_id,"MEMBERSHIP_STATUS_CHANGED","WorkspaceMembership",f"membership:{w}:{user_id}",service.workspace_scope(w),{"user_id":user_id,"status":status.value}))
            return result
        except ValueError as exc:
            if str(exc)=="LAST_ACTIVE_ADMIN":raise _error(409,"LAST_ACTIVE_ADMIN") from exc
            raise

    @router.post("/workspaces/{w}/roles")
    def grant_role(w:str,body:RoleGrantRequest,x_session_token:str|None=Header(None)):
        actor=service.actor(x_session_token,w);scope=_scope(body.scope)
        try: role,domain=DomainRole(body.role),ModalityDomain(body.domain)
        except ValueError as exc: raise _error(422,"INVALID_ASSIGNMENT") from exc
        service.validate_target(w,body.principal_id,scope)
        if role is DomainRole.ADMIN: service.require_admin(actor,w)
        else: service.require_domain_manager(actor,domain,scope)
        return service.authorization.assign_role(DomainRoleAssignment(body.id,body.principal_id,role,domain,scope,actor.actor_id))

    @router.delete("/workspaces/{w}/roles/{assignment_id}")
    def revoke_role(w:str,assignment_id:str,x_session_token:str|None=Header(None)):
        actor=service.actor(x_session_token,w)
        row=next((x for x in service.authorization.repository.list_role_assignments() if x["id"]==assignment_id),None)
        if not row or row["scope"]["workspace_id"]!=w: raise _error(404,"ASSIGNMENT_NOT_FOUND")
        domain=ModalityDomain(row["domain"]);scope=_scope(row["scope"])
        if row["role"]=="ADMIN":service.require_admin(actor,w)
        else:service.require_domain_manager(actor,domain,scope)
        try:return service.authorization.revoke_role(assignment_id,actor.actor_id)
        except ValueError as exc:
            if str(exc)=="LAST_ACTIVE_ADMIN":raise _error(409,"LAST_ACTIVE_ADMIN") from exc
            raise

    @router.post("/workspaces/{w}/permissions")
    def grant_permission(w:str,body:PermissionGrantRequest,x_session_token:str|None=Header(None)):
        actor=service.actor(x_session_token,w);scope=_scope(body.scope)
        try:domain=ModalityDomain(body.domain)
        except ValueError as exc:raise _error(422,"INVALID_ASSIGNMENT") from exc
        service.validate_target(w,body.principal_id,scope);service.require_domain_manager(actor,domain,scope)
        if body.permission in {"*","workspace.admin"}:
            service.require_admin(actor,w)
        return service.authorization.assign_permission(PermissionAssignment(body.id,body.principal_id,body.permission,domain,scope,actor.actor_id))

    @router.delete("/workspaces/{w}/permissions/{assignment_id}")
    def revoke_permission(w:str,assignment_id:str,x_session_token:str|None=Header(None)):
        actor=service.actor(x_session_token,w)
        row=next((x for x in service.authorization.repository.list_permission_assignments() if x["id"]==assignment_id),None)
        if not row or row["scope"]["workspace_id"]!=w:raise _error(404,"ASSIGNMENT_NOT_FOUND")
        service.require_domain_manager(actor,ModalityDomain(row["domain"]),_scope(row["scope"]))
        if row["permission"] in {"*","workspace.admin"}:service.require_admin(actor,w)
        return service.authorization.revoke_permission(assignment_id,actor.actor_id)

    @router.get("/workspaces/{w}/explain",response_model=PermissionExplanationView)
    def explain(w:str,principal_id:str=Query(...),permission:str=Query(...),domain:str=Query(...),kind:str=Query("WORKSPACE"),project_id:str|None=None,storyline_id:str|None=None,branch_id:str|None=None,x_session_token:str|None=Header(None)):
        actor=service.actor(x_session_token,w);service.require_admin(actor,w)
        try:d=ModalityDomain(domain)
        except ValueError as exc:raise _error(422,"INVALID_DOMAIN") from exc
        scope=_scope({"kind":kind,"workspace_id":w,"project_id":project_id,"storyline_id":storyline_id,"branch_id":branch_id})
        return service.authorization.explain(principal_id,permission,d,scope)

    return router
