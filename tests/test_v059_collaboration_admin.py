from types import SimpleNamespace
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.collaboration import Branch, Storyline, Workspace
from app.collaboration_admin import CollaborationAdminService, create_collaboration_admin_router
from app.identity import User, WorkspaceMembership
from app.repositories.file.identity import FileIdentityRepository
from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.identity_service import IdentityService
from app.trusted_sessions import TrustedSessionResolver


class Novels:
    def get(self, value): return {"id": value}


def make_client(tmp_path, workspace_mutations=None):
    scopes=CollaborationScopeService(FileScopeRepository(tmp_path),Novels())
    scopes.create_workspace(Workspace("w","Workspace"))
    identity=IdentityService(FileIdentityRepository(tmp_path),scopes)
    for user in (User("admin","Admin"),User("lead","Lead"),User("member","Member")):
        identity.create_user(user);identity.add_membership(WorkspaceMembership(f"m:{user.id}",user.id,"w"))
    authorization=AuthorizationService(FileAuthorizationRepository(tmp_path),scopes)
    ws=AuthorizationScope(ScopeKind.WORKSPACE,"w")
    authorization.assign_role(DomainRoleAssignment("admin-role","admin",DomainRole.ADMIN,ModalityDomain.NOVEL,ws,"bootstrap"))
    authorization.assign_role(DomainRoleAssignment("lead-role","lead",DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,ws,"admin"))
    sessions=TrustedSessionResolver()
    for user in ("admin","lead","member"):
        sessions.register(user,SessionContext(f"s:{user}",f"c:{user}",user,"w"))
    service=CollaborationAdminService(sessions=sessions,identity=identity,authorization=authorization,scopes=scopes,workspace_mutations=workspace_mutations)
    app=FastAPI();app.state.scopes=scopes;app.include_router(create_collaboration_admin_router(service))
    return TestClient(app),authorization


def h(user):return {"X-Session-Token":user}


class WorkspaceMutations:
    def __init__(self): self.calls=[]
    def create_workspace(self,workspace_id,name,actor_id):
        self.calls.append(("create",workspace_id,name,actor_id));return {"id":workspace_id,"name":name}
    def rename_workspace(self,workspace_id,name,actor_id):
        self.calls.append(("rename",workspace_id,name,actor_id));return {"id":workspace_id,"name":name}


def test_trusted_actor_admin_boundary_and_workspace_discovery(tmp_path):
    api,_=make_client(tmp_path)
    assert api.get("/api/collaboration/admin/workspaces",headers=h("admin")).json()["items"][0]["id"]=="w"
    assert api.get("/api/collaboration/admin/workspaces/w/members",headers=h("member")).status_code==403
    assert api.get("/api/collaboration/admin/workspaces/w/members").status_code==401


def test_workspace_navigation_is_validated_named_and_has_deterministic_default(tmp_path):
    api,_=make_client(tmp_path)
    # Build scope through the same validated service used by the production route.
    scopes=api.app.state.scopes
    scopes.link_project("w","project")
    scopes.create_storyline(Storyline("storyline","w","project","Storyline"))
    scopes.create_branch(Branch("branch","w","project","storyline","Branch"))
    scopes.link_project("w","incomplete-project")
    scopes.create_workspace(Workspace("other","Other Workspace"))
    scopes.link_project("other","other-project")
    scopes.create_storyline(Storyline("other-storyline","other","other-project","Other Storyline"))
    scopes.create_branch(Branch("other-branch","other","other-project","other-storyline","Other Branch"))

    response=api.get("/api/collaboration/admin/workspaces/w/navigation",headers=h("admin"))

    assert response.status_code==200
    path={"workspace_id":"w","project_id":"project","storyline_id":"storyline","branch_id":"branch",
          "project_name":"\u672a\u547d\u540d\u5c0f\u8bf4","storyline_name":"Storyline","branch_name":"Branch"}
    assert response.json()=={
        "workspace_id":"w",
        "eligible_paths":[path],
        "default_path":path,
    }


def test_empty_workspace_navigation_is_explicitly_empty(tmp_path):
    api,_=make_client(tmp_path)
    response=api.get("/api/collaboration/admin/workspaces/w/navigation",headers=h("admin"))
    assert response.status_code==200
    assert response.json()=={"workspace_id":"w","eligible_paths":[],"default_path":None}


def test_domain_lead_is_domain_scoped_and_cannot_grant_admin(tmp_path):
    api,_=make_client(tmp_path)
    body={"id":"permission","principal_id":"member","permission":"domain.write","domain":"NOVEL","scope":{"kind":"WORKSPACE","workspace_id":"w"}}
    assert api.post("/api/collaboration/admin/workspaces/w/permissions",json=body,headers=h("lead")).status_code==200
    body={"id":"video-permission","principal_id":"member","permission":"domain.write","domain":"VIDEO","scope":{"kind":"WORKSPACE","workspace_id":"w"}}
    assert api.post("/api/collaboration/admin/workspaces/w/permissions",json=body,headers=h("lead")).status_code==403
    role={"id":"forged-admin","principal_id":"member","role":"ADMIN","domain":"NOVEL","scope":{"kind":"WORKSPACE","workspace_id":"w"}}
    assert api.post("/api/collaboration/admin/workspaces/w/roles",json=role,headers=h("lead")).status_code==403


def test_last_active_admin_and_explanation_and_content_free_audit(tmp_path):
    api,authorization=make_client(tmp_path)
    assert api.delete("/api/collaboration/admin/workspaces/w/roles/admin-role",headers=h("admin")).json()["detail"]["code"]=="LAST_ACTIVE_ADMIN"
    explained=api.get("/api/collaboration/admin/workspaces/w/explain",params={"principal_id":"lead","permission":"domain.write","domain":"NOVEL"},headers=h("admin"))
    assert explained.status_code==200 and explained.json()["sources"][0]["source_type"]=="DOMAIN_ROLE"
    events=authorization.repository.list_audit_events()
    assert all("content" not in str(x.get("metadata",{})).lower() for x in events)


def test_assignment_scope_spoofing_is_rejected(tmp_path):
    api,_=make_client(tmp_path)
    body={"id":"escape","principal_id":"member","permission":"domain.read","domain":"NOVEL","scope":{"kind":"WORKSPACE","workspace_id":"other"}}
    response=api.post("/api/collaboration/admin/workspaces/w/permissions",json=body,headers=h("admin"))
    assert response.status_code==403 and response.json()["detail"]["code"]=="SCOPE_WORKSPACE_MISMATCH"


def test_member_add_rolls_back_when_audit_append_fails(tmp_path, monkeypatch):
    api, _ = make_client(tmp_path)
    identity = api.app.state.scopes.repository.path.with_name("identity.json")
    from app.repositories.file.identity import FileIdentityRepository
    repo = FileIdentityRepository(tmp_path)
    repo.save_user({"id":"new-user","display_name":"New User","status":"ACTIVE","created_at":"t","updated_at":"t","metadata":None})
    before = identity.read_bytes()

    def fail_audit(self, item):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(FileAuthorizationRepository, "append_audit_event", fail_audit)
    with pytest.raises(RuntimeError, match="injected audit failure"):
        repo.save_membership_with_audit({"id":"membership:w:new-user","user_id":"new-user","workspace_id":"w","status":"ACTIVE","created_at":"t","updated_at":"t","metadata":None}, {"id":"audit-fail","scope":{"kind":"WORKSPACE","workspace_id":"w"}})
    assert identity.read_bytes() == before


def test_member_status_rolls_back_when_audit_append_fails(tmp_path, monkeypatch):
    api, _ = make_client(tmp_path)
    identity = api.app.state.scopes.repository.path.with_name("identity.json")
    before = identity.read_bytes()

    def fail_audit(self, item):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(FileAuthorizationRepository, "append_audit_event", fail_audit)
    try:
        api.patch("/api/collaboration/admin/workspaces/w/members/member/status", json={"status": "INACTIVE"}, headers=h("admin"))
    except RuntimeError as exc:
        assert str(exc) == "injected audit failure"
    else:
        raise AssertionError("injected audit failure was not propagated")
    assert identity.read_bytes() == before


def test_workspace_create_uses_trusted_admin_actor_and_one_atomic_call(tmp_path):
    mutations=WorkspaceMutations();api,_=make_client(tmp_path,mutations)
    assert api.post("/api/collaboration/admin/workspaces",json={"id":"new","name":"New"}).status_code==401
    assert api.post("/api/collaboration/admin/workspaces",json={"id":"new","name":"New"},headers=h("lead")).status_code==403
    spoofed=api.post("/api/collaboration/admin/workspaces",json={"id":"new","name":"New","actor_id":"lead"},headers=h("admin"))
    assert spoofed.status_code==422 and mutations.calls==[]
    created=api.post("/api/collaboration/admin/workspaces",json={"id":"new","name":"New"},headers=h("admin"))
    assert created.status_code==201 and created.json()=={"id":"new","name":"New"}
    assert mutations.calls==[("create","new","New","admin")]


def test_workspace_rename_requires_target_admin_and_one_atomic_call(tmp_path):
    mutations=WorkspaceMutations();api,_=make_client(tmp_path,mutations)
    assert api.patch("/api/collaboration/admin/workspaces/w",json={"name":"Renamed"},headers=h("lead")).status_code==403
    renamed=api.patch("/api/collaboration/admin/workspaces/w",json={"name":"Renamed"},headers=h("admin"))
    assert renamed.status_code==200 and renamed.json()=={"id":"w","name":"Renamed"}
    assert mutations.calls==[("rename","w","Renamed","admin")]


def test_real_file_workspace_create_is_atomic_and_establishes_creator_admin(tmp_path):
    mutations=FileScopeRepository(tmp_path);api,_=make_client(tmp_path,mutations)
    created=api.post("/api/collaboration/admin/workspaces",json={"id":"new","name":"New"},headers=h("admin"))
    assert created.status_code==201 and mutations.get("workspaces","new")["name"]=="New"
    identity=FileIdentityRepository(tmp_path)
    membership=identity.get_membership("admin","new")
    assert membership["status"]=="ACTIVE"
    authorization=FileAuthorizationRepository(tmp_path)
    roles=[row for row in authorization.list_role_assignments("admin") if row["scope"]["workspace_id"]=="new"]
    assert [(row["role"],row["domain"]) for row in roles]==[("ADMIN","NOVEL")]
    events=[row for row in authorization.list_audit_events() if row["target_id"]=="new"]
    assert events[-1]["action"]=="WORKSPACE_CREATED" and events[-1]["actor_id"]=="admin"


def test_real_file_workspace_create_rolls_back_all_files_on_audit_failure(tmp_path,monkeypatch):
    mutations=FileScopeRepository(tmp_path);api,_=make_client(tmp_path,mutations)
    paths=[tmp_path/name for name in ("collaboration_scope.json","identity.json","authorization.json")]
    before={path:path.read_bytes() for path in paths}
    monkeypatch.setattr(FileAuthorizationRepository,"save_role_assignment_with_audit",lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError("audit failed")))
    with pytest.raises(RuntimeError,match="audit failed"):
        api.post("/api/collaboration/admin/workspaces",json={"id":"new","name":"New"},headers=h("admin"))
    assert {path:path.read_bytes() for path in paths}==before


def test_real_file_workspace_rename_is_authorized_and_audit_atomic(tmp_path,monkeypatch):
    mutations=FileScopeRepository(tmp_path);api,_=make_client(tmp_path,mutations)
    assert api.patch("/api/collaboration/admin/workspaces/w",json={"name":"No"},headers=h("lead")).status_code==403
    renamed=api.patch("/api/collaboration/admin/workspaces/w",json={"name":"Renamed"},headers=h("admin"))
    assert renamed.status_code==200 and mutations.get("workspaces","w")["name"]=="Renamed"
    assert any(row["action"]=="WORKSPACE_RENAMED" and row["actor_id"]=="admin" for row in FileAuthorizationRepository(tmp_path).list_audit_events())
    scope_before=(tmp_path/"collaboration_scope.json").read_bytes();auth_before=(tmp_path/"authorization.json").read_bytes()
    monkeypatch.setattr(FileAuthorizationRepository,"append_audit_event",lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError("audit failed")))
    with pytest.raises(RuntimeError,match="audit failed"):
        api.patch("/api/collaboration/admin/workspaces/w",json={"name":"Broken"},headers=h("admin"))
    assert (tmp_path/"collaboration_scope.json").read_bytes()==scope_before
    assert (tmp_path/"authorization.json").read_bytes()==auth_before
