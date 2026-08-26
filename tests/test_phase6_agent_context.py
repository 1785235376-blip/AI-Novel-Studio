from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def setup_novel(client):
    novel=client.post('/api/novels',json={'title':f'Agent Context {uuid4()}'}).json();nid=novel['id'];client.post(f'/api/novels/{nid}/chapters',json={'title':'第一章','content':'林海抵达雾港。'});client.put(f'/api/novels/{nid}/outline',json={'theme':'信任','premise':'调查雾港'});client.put(f'/api/novels/{nid}/characters/lin-hai',json={'name':'林海'});client.put(f'/api/novels/{nid}/locations/mist-port',json={'name':'雾港'});client.put(f'/api/novels/{nid}/volumes/fog',json={'title':'迷雾卷'});client.put(f'/api/novels/{nid}/scenes/arrival',json={'title':'抵达雾港','chapter_id':f'{nid}:1'});return nid


def test_agent_context_is_role_scoped_and_versioned():
    client=TestClient(app);nid=setup_novel(client)
    planner=client.get('/api/agents/planner/context-preview',params={'novel_id':nid,'chapter':1}).json();artist=client.get('/api/agents/artist/context-preview',params={'novel_id':nid,'chapter':1}).json()
    assert planner['chapter_version']==1 and len(planner['context_hash'])==64
    assert 'outline' in planner['sections'] and 'story_routes' in planner['sections']
    assert set(artist['sections'])=={'characters','locations','scenes'}
    assert 'writing_context' not in artist['sections']


def test_cloud_agent_context_preserves_privacy_decisions():
    client=TestClient(app);nid=setup_novel(client)
    result=client.get('/api/agents/writer/context-preview',params={'novel_id':nid,'chapter':1,'target':'cloud'}).json()
    assert result['target']=='cloud' and result['sections']['writing_context']['privacy_omissions'] is not None
    assert result['agent_id']=='writer' and result['source_manifest']


def test_unknown_agent_is_rejected():
    client=TestClient(app);nid=setup_novel(client)
    assert client.get('/api/agents/unknown/context-preview',params={'novel_id':nid,'chapter':1}).status_code==400
