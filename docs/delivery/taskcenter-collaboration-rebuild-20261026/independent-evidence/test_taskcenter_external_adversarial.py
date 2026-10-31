"""Independent original-owner/HTTP counterexamples, written before implementation freeze."""
from copy import deepcopy
from types import SimpleNamespace
import hashlib
import pytest
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only

def snap(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '.workspace-mutation-locks' not in p.parts}

@pytest.fixture
def env(rig, monkeypatch):
    from app import api as legacy
    from app.experimental import api
    from app.experimental.store import ExperimentalStore
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    rig.seed('marker-fixture', required_features=())
    scope, headers = shared_scope(rig)
    store = ExperimentalStore(rig.root, 'file', '')
    chapters = rig.workspace.creative.chapters
    monkeypatch.setattr(legacy, 'chapter_service', chapters)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','workspace_tools_v2,agent_team_recipes')
    for service in (api.workspace_tools_service, api.team_service):
        monkeypatch.setattr(service, 'store', store)
        monkeypatch.setattr(service, 'novels', rig.novels)
        monkeypatch.setattr(service, 'chapters', chapters)
    rig.grants.assign_permission(PermissionAssignment('query-write', 'reader', 'domain.write',
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.PROJECT,'query-workspace',rig.nid), 'fixture'))
    rows=[]
    for n in range(3):
        response=rig.client.post(f'/api/novels/{rig.nid}/experimental/teams/runs',headers=headers,
            json={'recipe_id':'outline_chapter_editor','source_text':f'private-manuscript-{n}'})
        assert response.status_code==201,response.text
        rows.append(response.json())
    return SimpleNamespace(r=rig, scope=scope, headers=headers, store=store, source=api.team_service,
                           api=api, legacy=legacy, rows=rows, mp=monkeypatch)

def read(e, token=None, prefix='/api', **query):
    params={'page_mode':'cursor','authority':'agent_team','limit':1, **query}
    if token is not None: params['cursor']=token
    return e.r.client.get(f'{prefix}/novels/{e.r.nid}/experimental/workspace/tasks', params=params, headers=e.headers)

def first(e):
    r=read(e); assert r.status_code==200,r.text
    assert r.json()['next_cursor']; return r.json()['next_cursor']

def restart(response):
    assert response.status_code==409,response.text
    assert response.json()['detail']['code']=='TASKCENTER_CURSOR_RESTART_REQUIRED'
    assert response.headers['cache-control']=='no-store'

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_real_post_and_repeated_pages_are_private_zero_write(env,prefix):
    e=env; before=snap(e.r.root); seen=[]; token=None
    for page in range(3):
        r=read(e,token,prefix); assert r.status_code==200,r.text
        b=r.json(); seen.extend(x['id'] for x in b['items'])
        assert b['observed_total']==3 and r.headers['cache-control']=='no-store'
        assert 'private-manuscript' not in r.text and str(e.r.root) not in r.text
        assert 'row_lifecycles' not in r.text and 'token-reader' not in r.text
        replay=read(e,token,prefix); assert replay.status_code==200,replay.text
        if token is None:
            assert {k:v for k,v in replay.json().items() if k!='next_cursor'}=={k:v for k,v in b.items() if k!='next_cursor'}
        else:
            assert replay.json()==b
        token=b['next_cursor']
    assert token is None and len(seen)==len(set(seen))==3
    assert snap(e.r.root)==before

def test_same_token_same_session_revoke_register_invalidates(env):
    e=env; token=first(e); session=e.r.sessions.resolve('token-reader').session
    e.r.sessions.revoke('token-reader');e.r.sessions.register('token-reader',session)
    restart(read(e,token))

def test_resolver_replacement_equal_first_generation_rejected(env):
    from app.trusted_sessions import TrustedSessionResolver
    from app import main
    e=env; token=first(e); replacement=TrustedSessionResolver()
    replacement.register('token-reader',e.r.sessions.resolve('token-reader').session)
    e.mp.setattr(e.legacy,'trusted_session_resolver',replacement)
    e.mp.setattr(main,'trusted_session_resolver',replacement)
    restart(read(e,token))

def test_membership_inactive_active_direct_service_invalidates(env):
    from app.identity import IdentityStatus
    e=env; token=first(e)
    for status in (IdentityStatus.INACTIVE, IdentityStatus.ACTIVE):
        e.r.identities.set_membership_status('reader','query-workspace',status)
    restart(read(e,token))

def test_grant_exact_payload_restore_via_repository_invalidates(env):
    e=env; token=first(e); repo=e.r.grants.repository
    original=deepcopy(next(x for x in repo.list_permission_assignments('reader') if x['id']=='query-read'))
    e.r.grants.revoke_permission('query-read','reader');repo.save_permission_assignment(original)
    restart(read(e,token))

def test_unrelated_membership_and_irrelevant_grant_preserve_cursor(env):
    from app.identity import IdentityStatus
    from app.authorization import AuthorizationScope,ModalityDomain,PermissionAssignment,ScopeKind
    e=env;token=first(e)
    for status in (IdentityStatus.INACTIVE,IdentityStatus.ACTIVE):
        e.r.identities.set_membership_status('no-grants','query-workspace',status)
    e.r.grants.assign_permission(PermissionAssignment('irrelevant','reader','domain.write',ModalityDomain.IMAGE,
        AuthorizationScope(ScopeKind.PROJECT,'query-workspace',e.r.nid),'fixture'))
    r=read(e,token);assert r.status_code==200,r.text

@pytest.mark.parametrize('restore',[False,True])
def test_revocation_inside_original_source_reader_rejects_whole_response(env,restore):
    from app.identity import IdentityStatus
    e=env; original=e.source.list_runs
    def intercepted(*a,**kw):
        result=original(*a,**kw)
        e.r.identities.set_membership_status('reader','query-workspace',IdentityStatus.INACTIVE)
        if restore: e.r.identities.set_membership_status('reader','query-workspace',IdentityStatus.ACTIVE)
        return result
    e.mp.setattr(e.source,'list_runs',intercepted)
    r=read(e)
    if restore:
        assert r.status_code in (409, 501), r.text
        assert r.headers['cache-control']=='no-store'
    else:
        assert r.status_code==403,r.text
        assert r.headers['cache-control']=='no-store'
    assert 'private-manuscript' not in r.text

def test_scope_retire_and_same_topology_recreation_invalidates(env):
    e=env;token=first(e); repo=e.r.scopes.repository
    story=deepcopy(repo.get('storylines','query-story'))
    branches=[deepcopy(repo.get('branches',bid)) for bid in ('query-branch-a','query-branch-b')]
    repo.retire_project(e.r.nid);repo.link_project(e.r.nid,'query-workspace')
    repo.create('storylines',story)
    for b in branches: repo.create('branches',b)
    restart(read(e,token))

def test_observed_private_field_aba_invalidates_even_unchanged_projection(env):
    e=env;token=first(e)
    row=e.rows[0];rid=row['id']
    original=deepcopy(e.store.read(e.r.nid,e.scope)['collections']['team_runs'][rid])
    with e.store.transaction(e.r.nid,e.scope) as d: d['collections']['team_runs'][rid]['instruction']='private-change'
    with e.store.transaction(e.r.nid,e.scope) as d: d['collections']['team_runs'][rid]=original
    restart(read(e,token))

def test_other_collection_changes_preserve_cursor(env):
    e=env;token=first(e)
    with e.store.transaction(e.r.nid,e.scope) as d: d['collections']['unselected_secret']={'x':{'private':'activity'}}
    r=read(e,token);assert r.status_code==200,r.text

def test_recreated_project_never_claims_old_source_document(env):
    e=env;token=first(e);e.r.novels.delete(e.r.nid);e.r.project(e.r.nid)
    from app.collaboration import Storyline,Branch
    e.r.scopes.link_project('query-workspace',e.r.nid)
    e.r.scopes.create_storyline(Storyline('query-story','query-workspace',e.r.nid,'Story'))
    e.r.scopes.create_branch(Branch('query-branch-a','query-workspace',e.r.nid,'query-story','Branch'))
    from app.authorization import AuthorizationScope,ModalityDomain,PermissionAssignment,ScopeKind
    e.r.grants.assign_permission(PermissionAssignment('query-read','reader','domain.read',ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT,'query-workspace',e.r.nid),'fixture'))
    before=snap(e.r.root)
    assert read(e,token).status_code in (409,501)
    assert read(e).status_code==501
    assert snap(e.r.root)==before

def test_admin_cross_domain_grant_semantics_and_direct_recreation(env):
    from app.authorization import AuthorizationScope,ModalityDomain,DomainRoleAssignment,DomainRole,ScopeKind
    e=env
    e.r.grants.revoke_permission('query-read','reader')
    e.r.grants.assign_role(DomainRoleAssignment('admin-other-domain','reader',DomainRole.ADMIN,ModalityDomain.IMAGE,
        AuthorizationScope(ScopeKind.PROJECT,'query-workspace',e.r.nid),'fixture'))
    token=first(e);repo=e.r.grants.repository
    row=deepcopy(next(x for x in repo.list_role_assignments('reader') if x['id']=='admin-other-domain'))
    # Add a second admin to preserve original last-admin safety when removing this one.
    e.r.grants.assign_role(DomainRoleAssignment('backup-admin','no-grants',DomainRole.ADMIN,ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT,'query-workspace',e.r.nid),'fixture'))
    e.r.grants.revoke_role('admin-other-domain','reader');repo.save_role_assignment(row)
    restart(read(e,token))

def test_other_actor_cannot_reuse_token_even_with_same_permissions(env):
    from app.authorization import AuthorizationScope,ModalityDomain,PermissionAssignment,ScopeKind
    e=env;token=first(e)
    e.r.grants.assign_permission(PermissionAssignment('other-read','no-grants','domain.read',ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT,'query-workspace',e.r.nid),'fixture'))
    e.headers={**e.headers,'X-Session-Token':'token-no-grants'}
    restart(read(e,token))

def test_branch_revision_and_presentation_changes_do_not_create_global_epoch(env):
    from app.collaboration import CollaborationScope
    e=env;token=first(e);repo=e.r.scopes.repository
    scope=CollaborationScope('query-workspace',e.r.nid,'query-story','query-branch-a')
    repo.compare_and_increment(scope,0)
    document=repo._read()
    for row in document['branches']:
        if row['id']=='query-branch-a':row['name']='renamed display only'
    repo._write(document)
    r=read(e,token);assert r.status_code==200,r.text

@pytest.mark.parametrize('owner_name,key',[
    ('identity','_identity_lifecycle_v1'),('scope','_scope_lifecycle_v1'),('grants','_grant_lifecycle_v1')])
@pytest.mark.parametrize('legacy',[False,True])
def test_reserved_null_is_not_accepted_for_fresh_or_legacy_owner(tmp_path,owner_name,key,legacy):
    import json
    from app.repositories.file.identity import FileIdentityRepository
    from app.repositories.file.scope import FileScopeRepository,FileAuthorizationRepository
    factory={'identity':FileIdentityRepository,'scope':FileScopeRepository,'grants':FileAuthorizationRepository}[owner_name]
    repo=factory(tmp_path)
    empty=repo._read()
    if legacy:repo.path.write_text(json.dumps(empty))
    before=repo.path.read_bytes() if repo.path.exists() else None
    with pytest.raises(ValueError):repo._write({**empty,key:None})
    after=repo.path.read_bytes() if repo.path.exists() else None
    assert after==before
