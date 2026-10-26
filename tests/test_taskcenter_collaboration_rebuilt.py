"""Fresh mounted HTTP collaboration tests after unrecoverable local snapshot loss."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and not p.name.endswith('.lock')}


@pytest.fixture
def collaboration_rig(rig, monkeypatch):
    from app import api
    from app.experimental import api as experimental
    from app.authorization import AuthorizationScope, ScopeKind, PermissionAssignment, ModalityDomain
    scope, headers = shared_scope(rig)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2,agent_team_recipes')
    monkeypatch.setattr(api, 'chapter_service', rig.workspace.creative.chapters)
    # Explicit original project owner provisioning belongs to fixture creation, never GET.
    rig.workspace.creative.store.incarnation(rig.nid)
    from app.experimental.store import ExperimentalStore
    raw_store = ExperimentalStore(rig.root)
    for target in (experimental.team_service, experimental.workspace_tools_service):
        monkeypatch.setattr(target, 'store', raw_store)
        monkeypatch.setattr(target, 'novels', rig.novels)
        monkeypatch.setattr(target, 'chapters', rig.workspace.creative.chapters)
    reader = next(r for r in experimental.workspace_tools_service.task_readers if r.name == 'agent_team')
    monkeypatch.setattr(experimental.workspace_tools_service, 'task_readers', (reader,))
    rig.grants.assign_permission(PermissionAssignment('query-write','reader','domain.write',ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT,'query-workspace',rig.nid),'fixture'))
    ids=[]
    for i in range(3):
        r=rig.client.post(f'/api/novels/{rig.nid}/experimental/teams/runs',headers=headers,
            json={'recipe_id':'outline_chapter_editor','source_text':f'private-source-{i}'})
        assert r.status_code==201,r.text
        ids.append(r.json()['id'])
    return SimpleNamespace(rig=rig, scope=scope, headers=headers, ids=ids, store=raw_store,
                           team=experimental.team_service, adapter=experimental.taskcenter_cursor_adapter.collaboration_adapter)


def get(e, params=None, prefix='/api', headers=None):
    return e.rig.client.get(f'{prefix}/novels/{e.rig.nid}/experimental/workspace/tasks',
        params={'authority':'agent_team','page_mode':'cursor','limit':1,**(params or {})},
        headers=headers or e.headers)


@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_first_next_replay_final_readonly(collaboration_rig,prefix):
    e=collaboration_rig;before=snapshot(e.rig.root)
    first=get(e,prefix=prefix);assert first.status_code==200,first.text
    second=get(e,{'cursor':first.json()['next_cursor']},prefix)
    assert second.status_code==200,second.text
    assert get(e,{'cursor':first.json()['next_cursor']},prefix).json()==second.json()
    third=get(e,{'cursor':second.json()['next_cursor']},prefix)
    assert third.status_code==200,third.text
    assert third.json()['next_cursor'] is None
    assert len({r.json()['items'][0]['id'] for r in (first,second,third)})==3
    for r in (first,second,third):
        assert r.headers['cache-control']=='no-store'
        assert 'private-source' not in r.text and 'row_lifecycles' not in r.text and 'file:' not in r.text
    assert snapshot(e.rig.root)==before


@pytest.mark.parametrize('kind',['session','membership','grant','task','project'])
def test_observed_aba_restart(collaboration_rig,kind):
    e=collaboration_rig;first=get(e);assert first.status_code==200,first.text
    token=first.json()['next_cursor']
    if kind=='session':
        session=e.rig.sessions._sessions['token-reader']
        e.rig.sessions.revoke('token-reader');e.rig.sessions.register('token-reader',session)
    elif kind=='membership':
        repo=e.rig.identities.repository
        row=repo.get_membership('reader','query-workspace')
        repo.update_membership_status('reader','query-workspace','INACTIVE','changed',False)
        repo.update_membership_status('reader','query-workspace','ACTIVE',row['updated_at'],False)
    elif kind=='grant':
        repo=e.rig.grants.repository;row=next(x for x in repo.list_permission_assignments() if x['id']=='query-read')
        e.rig.grants.revoke_permission('query-read','fixture');repo.save_permission_assignment(row)
    elif kind=='project':
        marker=e.rig.root/'novels'/e.rig.nid/'creative_project_v2.json'
        marker.unlink();e.rig.workspace.creative.store.incarnation(e.rig.nid)
    else:
        original=e.store.read(e.rig.nid,e.scope)['collections']['team_runs'][e.ids[0]]
        with e.store.transaction(e.rig.nid,e.scope) as d:d['collections']['team_runs'][e.ids[0]]['instruction']='private-change'
        with e.store.transaction(e.rig.nid,e.scope) as d:d['collections']['team_runs'][e.ids[0]]=original
    response=get(e,{'cursor':token});assert response.status_code==409,response.text


def test_read_mid_revocation_rejects(collaboration_rig,monkeypatch):
    e=collaboration_rig;original=e.team.list_runs
    def changed(*a,**kw):
        result=original(*a,**kw);e.rig.grants.revoke_permission('query-read','fixture');return result
    monkeypatch.setattr(e.team,'list_runs',changed)
    r=get(e);assert r.status_code==403,r.text


def test_unrelated_member_does_not_invalidate(collaboration_rig):
    e=collaboration_rig;first=get(e);assert first.status_code==200,first.text
    e.rig.identities.repository.update_membership_status('no-grants','query-workspace','INACTIVE','changed',False)
    assert get(e,{'cursor':first.json()['next_cursor']}).status_code==200


def test_legacy_source_is_zero_write_unsupported(collaboration_rig):
    e=collaboration_rig;p=e.store.path(e.rig.nid,e.scope);d=json.loads(p.read_text());d.pop('_taskcenter_team_lifecycle_v1');p.write_text(json.dumps(d))
    before=snapshot(e.rig.root);r=get(e);assert r.status_code==501,r.text;assert snapshot(e.rig.root)==before

@pytest.mark.parametrize('params',[{'authority':['agent_team','semantic_import']},{'authority':'media'}])
def test_unsupported_authorities_stay_closed(collaboration_rig,params):
    r=get(collaboration_rig,params);assert r.status_code==501,r.text

@pytest.mark.parametrize('params',[{'cursor':'private-invalid'},{'failed_only':'private-invalid'},{'limit':'999'}])
def test_invalid_queries_sanitized(collaboration_rig,params):
    r=get(collaboration_rig,params);assert r.status_code==422,r.text
    assert 'private-invalid' not in r.text
    assert r.headers['cache-control']=='no-store'


def test_resolver_replacement_invalidates(collaboration_rig,monkeypatch):
    e=collaboration_rig;first=get(e);assert first.status_code==200,first.text
    from app.trusted_sessions import TrustedSessionResolver
    from app import api,main
    resolver=TrustedSessionResolver();resolver.register('token-reader',e.rig.sessions._sessions['token-reader'])
    monkeypatch.setattr(api,'trusted_session_resolver',resolver);monkeypatch.setattr(main,'trusted_session_resolver',resolver)
    r=get(e,{'cursor':first.json()['next_cursor']});assert r.status_code==409,r.text
