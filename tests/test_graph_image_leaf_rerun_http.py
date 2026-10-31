from copy import deepcopy
import pytest

from app.creative.workspace_api import is_independent_studio_route
from app.experimental import api
from test_studio_backend_integration_v2 import studio
from test_studio_asset_query import rig
from test_graph_image_leaf_rerun import setup_graph, request

pytestmark = pytest.mark.file_backend_only


def mount_graph(monkeypatch, graph):
    for key, value in graph.__dict__.items():
        monkeypatch.setattr(api.creative_graph_service, key, value, raising=False)


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_mounted_rerun_routes_and_revoked_session(studio, monkeypatch, prefix):
    e=studio; graph,saved,source=setup_graph(e); mount_graph(monkeypatch,graph)
    base=f'{prefix}/projects/{e.nid}/studio/graph-runs/{source["id"]}/image-leaf-rerun'
    body=request(saved,source)
    assert e.client.post(base+'/preview',json=body).status_code==401
    preview=e.client.post(base+'/preview',headers=e.headers,json=body)
    assert preview.status_code==200,preview.text
    payload={**body,'request_id':'mounted-http','reviewed_impact_digest':preview.json()['impact_digest']}
    before=len(e.calls)
    created=e.client.post(base,headers=e.headers,json=payload)
    assert created.status_code==201,created.text
    assert created.json()['status']=='QUEUED' and len(e.calls)==before
    e.rig.sessions.revoke('studio-integration-host')
    denied=e.client.post(base,headers=e.headers,json={**payload,'request_id':'revoked-http'})
    assert denied.status_code in (401,403),denied.text
    denied_preview=e.client.post(base+'/preview',headers=e.headers,json=body)
    assert denied_preview.status_code in (401,403),denied_preview.text
    assert len(e.calls)==before


def test_mounted_revoke_before_create_commit_rolls_back(studio,monkeypatch):
    from app.creative import graph_media_rerun as rerun
    e=studio;graph,saved,source=setup_graph(e);mount_graph(monkeypatch,graph)
    base=f'/api/projects/{e.nid}/studio/graph-runs/{source["id"]}/image-leaf-rerun'
    body=request(saved,source)
    preview=e.client.post(base+'/preview',headers=e.headers,json=body)
    assert preview.status_code==200,preview.text
    before=deepcopy(e.workspace.store.read(e.nid,e.scope)); calls=len(e.calls)
    real_plan=rerun.plan
    def revoke_after_plan(*args,**kwargs):
        result=real_plan(*args,**kwargs)
        e.rig.sessions.revoke('studio-integration-host')
        return result
    monkeypatch.setattr(rerun,'plan',revoke_after_plan)
    denied=e.client.post(base,headers=e.headers,json={**body,'request_id':'revoked-during-commit',
        'reviewed_impact_digest':preview.json()['impact_digest']})
    assert denied.status_code in (401,403),denied.text
    assert e.workspace.store.read(e.nid,e.scope)==before and len(e.calls)==calls


def test_route_admission_is_exact():
    base='/api/projects/synthetic/studio/graph-runs/run/image-leaf-rerun'
    for suffix in ('','/preview'):
        assert is_independent_studio_route('POST',base+suffix)
        assert not is_independent_studio_route('GET',base+suffix)
        assert not is_independent_studio_route('DELETE',base+suffix)
    for suffix in ('/other','/preview/extra','-extra','/execute'):
        assert not is_independent_studio_route('POST',base+suffix)


def test_unhosted_collaboration_fails_closed(studio,monkeypatch):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from test_studio_asset_query import shared_scope
    e=studio
    scope,headers=shared_scope(e.rig)
    project=AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', e.nid)
    e.rig.grants.assign_permission(PermissionAssignment('query-write','reader','domain.write',ModalityDomain.NOVEL,project,'fixture'))
    e.scope=scope; e.actor='reader'; e.headers=headers
    activated=e.client.post(f'/api/projects/{e.nid}/studio/activate',headers=headers)
    assert activated.status_code==200,activated.text
    graph,saved,source=setup_graph(e); mount_graph(monkeypatch,graph)
    base=f'/api/projects/{e.nid}/studio/graph-runs/{source["id"]}/image-leaf-rerun'
    body=request(saved,source)
    preview=e.client.post(base+'/preview',headers=headers,json=body)
    assert preview.status_code==403,preview.text
    assert preview.json()['code']=='LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE'
