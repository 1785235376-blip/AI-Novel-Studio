import json
import pytest
from test_studio_asset_query import rig, shared_scope
from test_studio_workspace_identity_history_contract import audio_history
from test_audio_history_status_readonly import snapshot

@pytest.mark.parametrize('alias',['','/v1'])
@pytest.mark.parametrize('params,expected', [({'limit':'0'},422),({'limit':'51'},422),({'cursor':'forged'},409),({'cursor':''},409)])
@pytest.mark.parametrize('marked',[False,True])
def test_invalid_paging_never_returns_empty_history(audio_history,alias,params,expected,marked):
    e=audio_history
    if marked:
        path=e.rig.assets._meta_path(e.asset['id'])
        row=json.loads(path.read_text(encoding='utf-8'));row['_audio_history_head']='a'*64
        path.write_text(json.dumps(row),encoding='utf-8')
    before=snapshot(e.rig.root)
    response=e.client.get(f'/api{alias}/projects/{e.rig.nid}/studio/assets/{e.asset["id"]}/history',headers=e.headers,params=params)
    assert response.status_code==expected,response.text
    assert 'UNCAPTURED' not in response.text and 'items' not in response.json()
    assert snapshot(e.rig.root)==before

def test_invalid_paging_does_not_preempt_collaboration_authorization(rig):
    scope,headers=shared_scope(rig)
    asset=rig.seed('query.wav','audio',scope_value=scope)
    url=f'/api/projects/{rig.nid}/studio/assets/{asset["id"]}/history'
    denied=rig.client.get(url,params={'limit':'0'},headers={**headers,'X-Session-Token':'token-no-grants'})
    assert denied.status_code==403,denied.text

@pytest.mark.parametrize('alias',['','/v1'])
@pytest.mark.parametrize('limit',['1','20','50','001','+1','1.0',' 1'])
def test_valid_limit_retains_uncaptured_status(audio_history,alias,limit):
    e=audio_history
    before=snapshot(e.rig.root)
    response=e.client.get(f'/api{alias}/projects/{e.rig.nid}/studio/assets/{e.asset["id"]}/history',headers=e.headers,params={'limit':limit})
    assert response.status_code==200,response.text
    assert response.json()['coverage']=='UNCAPTURED'
    assert snapshot(e.rig.root)==before

@pytest.mark.parametrize('params',[[('limit','1'),('limit','2')],[('limit','x')],[('limit','-1')]])
def test_invalid_or_ambiguous_limit_is_rejected(audio_history,params):
    e=audio_history
    before=snapshot(e.rig.root)
    response=e.client.get(f'/api/projects/{e.rig.nid}/studio/assets/{e.asset["id"]}/history',headers=e.headers,params=params)
    assert response.status_code==422,response.text
    assert response.json()['detail']['code']=='AUDIO_HISTORY_QUERY_INVALID'
    assert snapshot(e.rig.root)==before

