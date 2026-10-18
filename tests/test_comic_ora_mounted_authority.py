"""Production mount, genuine original authority and original File/PG owners."""
import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_comic_ora_api import body

@pytest.fixture
def ora(mounted,monkeypatch):
    e=scoped(mounted,monkeypatch)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_production_v2,asset_lineage_v2,comic_layouts_v2,ai_director_v2')
    from app.creative.project_store import CreativeProjectStore
    owner=CreativeProjectStore(e.store)
    owner.incarnation(e.nid)  # explicit existing project setup, outside HTTP reads
    comic=e.experimental.comic_layouts_service
    monkeypatch.setattr(comic,'independent_store',owner)
    workspace=e.experimental.independent_workspace_service
    for key,value in {'store':owner,'assets':e.assets,'novels':e.novels}.items(): monkeypatch.setattr(workspace,key,value)
    service=e.experimental.comic_ora_staging_service
    for key,value in {'comic':comic,'workspace':workspace,'store':e.store,'owner':owner,'assets':e.assets}.items(): monkeypatch.setattr(service,key,value)
    monkeypatch.setattr(e.api,'authorization_service',e.authorization)
    e.ora=e.base+'/comic-layouts/ora-imports'
    e.ora_service=service
    yield e
    if e.backend == 'postgres':
        # Only this fixture's generated workspace/users/project. The enclosing
        # mounted fixture deletes its novel and content after this teardown.
        with e.store._connect() as connection:
            for table in ('domain_role_assignments','permission_assignments','authorization_audit_events'):
                connection.execute(f"DELETE FROM {table} WHERE payload->'scope'->>'workspace_id'=%s", (e.workspace,))
            connection.execute("DELETE FROM workspace_memberships WHERE workspace_id=%s AND user_id IN (%s,%s)", (e.workspace,e.lead,e.viewer))
            for table in ('storyline_branches','storylines'):
                connection.execute(f"DELETE FROM {table} WHERE payload->>'workspace_id'=%s AND payload->>'project_id'=%s", (e.workspace,e.nid))
            connection.execute("DELETE FROM project_workspaces WHERE project_id=%s AND workspace_id=%s", (e.nid,e.workspace))
            connection.execute("UPDATE novels SET workspace_id='default-workspace' WHERE slug=%s AND workspace_id=%s", (e.nid,e.workspace))
            connection.execute("DELETE FROM workspaces WHERE id=%s", (e.workspace,))
            connection.execute("DELETE FROM users WHERE id IN (%s,%s)", (e.lead,e.viewer))


def test_production_alias_session_role_scope_and_flags(ora,monkeypatch):
    e=ora;c=e.client;root=e.ora
    assert c.get(root).status_code==401
    assert c.get(root,headers=e.headers).status_code==200
    row=checked(c.post(root,headers=e.headers,json=body(request_key='production')))
    assert c.get(root,headers=e.viewer_headers).json()=={'receipts':[]}
    assert c.get(root+'/'+row['id'],headers=e.viewer_headers).status_code==404
    assert c.post(root,headers=e.viewer_headers,json=body(request_key='viewer')).status_code==403
    assert c.get(root,headers={**e.headers,'X-Branch-ID':e.other_branch}).status_code==403
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_production_v2,asset_lineage_v2,comic_layouts_v2')
    response=c.get(root,headers=e.headers)
    assert response.status_code==404 and response.headers['cache-control']=='no-store'


def test_production_session_revocation_blocks_resume(ora):
    e=ora
    row=checked(e.client.post(e.ora,headers=e.headers,json=body(request_key='revoke')))
    e.sessions.revoke(e.lead)
    response=e.client.post(e.ora+'/'+row['id']+'/stage',headers=e.headers,json=body())
    assert response.status_code==401
    assert not list(e.assets.root.glob('*.bin'))
