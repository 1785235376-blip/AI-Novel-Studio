from types import SimpleNamespace
from uuid import uuid4
import base64
import json
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.services.image_job_service import ImageJobService
from app.audio_production_store import AudioProductionStore
from app.asset_providers import AssetGenerationResult, AssetProviderRegistry
from app.services.asset_library_service import AssetLibraryService
from test_r2_media_lifecycle import png_bytes, wav_bytes, FixtureVoice


def project():
    from app.main import app
    client=TestClient(app)
    novel=client.post('/api/novels',json={'title':'Synthetic media '+str(uuid4())}).json()
    chapter=client.post(f"/api/novels/{novel['id']}/chapters",json={'title':'Chapter','content':'第一句。第二句！'}).json()
    return client,novel['id'],chapter['id']


def test_audiobook_batch_produces_ordered_verified_manifest_and_export(monkeypatch):
    client,nid,cid=project();voice=FixtureVoice()
    monkeypatch.setattr('app.audio_providers.resolve_provider',lambda *args:('synthetic','fixture',voice))
    batch=client.post(f'/api/novels/{nid}/audiobook/chapters/{cid}/queue-segments',json={'provider_id':'synthetic','model_id':'fixture','voice':'CC0 silence','license_note':'CC0-1.0 synthetic test silence'}).json()
    assert batch['order']=='SOURCE_ORDER' and len(batch['items'])==2
    # Finish out of order; manifest must retain original segment order.
    for job in reversed(batch['items']):
        response=client.post(f"/api/novels/{nid}/audiobook/jobs/{job['id']}/execute")
        assert response.status_code==200,response.text
        assert response.json()['status']=='SUCCEEDED'
    manifest=client.get(f'/api/novels/{nid}/audiobook/manifest').json()
    assert manifest['ready_chapters']==1
    audio=manifest['chapters'][0]['audio']
    assert [item['segment_index'] for item in audio]==[0,1]
    ids=[job['id'] for job in batch['items']]
    exported=client.post(f'/api/novels/{nid}/audiobook/chapters/{cid}/export',json={'job_ids':ids})
    assert exported.status_code==200 and exported.content.startswith(b'RIFF')
    receipt=client.post(f'/api/novels/{nid}/audiobook/chapters/{cid}/export',json={'job_ids':ids,'manifest_only':True}).json()
    assert receipt['duration_ms']==480 and len(receipt['segments'])==2
    assert [segment['start_ms'] for segment in receipt['segments']]==[0,380]
    assert all(row['voice_authorization']=='CC0-1.0 synthetic test silence' for row in receipt['segments'])


def test_queue_idempotency_rejects_changed_request(monkeypatch):
    client,nid,cid=project();headers={'Idempotency-Key':'same-queue-request'}
    first=client.post(f'/api/novels/{nid}/audiobook/chapters/{cid}/queue',headers=headers,json={'voice':'one'}).json()
    again=client.post(f'/api/novels/{nid}/audiobook/chapters/{cid}/queue',headers=headers,json={'voice':'one'}).json()
    assert first['id']==again['id']
    changed=client.post(f'/api/novels/{nid}/audiobook/chapters/{cid}/queue',headers=headers,json={'voice':'different'})
    assert changed.status_code==409 and changed.json()['detail']['code']=='AUDIOBOOK_IDEMPOTENCY_CONFLICT'


def test_media_api_partitions_branch_actor_and_recovers_same_actor_new_session(tmp_path,monkeypatch):
    _,nid,cid=project()
    import app.api as api
    monkeypatch.setattr(api,'settings',SimpleNamespace(enable_collaboration_runtime=True))
    monkeypatch.setattr(api,'image_job_service',ImageJobService(tmp_path))
    monkeypatch.setattr(api,'audio_production_store',AudioProductionStore(tmp_path/'audio'))
    actors={'session-a':'actor-a','session-a-renewed':'actor-a','session-b':'actor-b'}
    class Sessions:
        def resolve(self,token):
            if token not in actors:raise HTTPException(401,'session invalid')
            return SimpleNamespace(actor_id=actors[token])
    monkeypatch.setattr(api,'trusted_session_resolver',Sessions())
    def authorize(project,token,permission):
        Sessions().resolve(token)
        if project!=nid:raise HTTPException(403,{'code':'PROJECT_SCOPE_FORBIDDEN'})
    monkeypatch.setattr(api,'_authorize_novel_project',authorize)
    monkeypatch.setattr(api,'_adaptation_context',lambda project,branch,token,permission:None)
    application=FastAPI();application.include_router(api.router,prefix='/api');client=TestClient(application)
    first={'X-Session-Token':'session-a','X-Branch-Id':'branch-a'}
    image=client.post(f'/api/novels/{nid}/image-jobs',headers=first,json={'provider_id':'fixture','model_id':'fixture','prompt':'Private pre-review image'}).json()
    audio=client.post(f'/api/novels/{nid}/audiobook/chapters/{cid}/queue',headers=first,json={}).json()
    for headers in ({'X-Session-Token':'session-b','X-Branch-Id':'branch-a'},{'X-Session-Token':'session-a','X-Branch-Id':'branch-b'}):
        assert client.get(f'/api/novels/{nid}/image-jobs',headers=headers).json()['items']==[]
        assert client.get(f'/api/novels/{nid}/audiobook/jobs',headers=headers).json()['items']==[]
        assert client.post(f"/api/novels/{nid}/image-jobs/{image['id']}/cancel",headers=headers).status_code==404
        assert client.post(f"/api/novels/{nid}/audiobook/jobs/{audio['id']}/cancel",headers=headers).status_code==404
    renewed={'X-Session-Token':'session-a-renewed','X-Branch-Id':'branch-a'}
    assert client.get(f'/api/novels/{nid}/image-jobs',headers=renewed).json()['items'][0]['id']==image['id']
    assert client.get(f'/api/novels/{nid}/audiobook/jobs',headers=renewed).json()['items'][0]['id']==audio['id']
    for path in tmp_path.rglob('*.json'):
        assert 'session-a' not in path.read_text() and 'session-b' not in path.read_text()


def test_callback_requires_matching_remote_attempt_and_replay_cannot_replace_output(monkeypatch):
    from test_phase1_video_runtime import Repo,task
    from app.services.screenplay_service import ScreenplayService
    import app.api as api
    repo=Repo(task(status='RUNNING',remote_task_id='remote-a',submission_key='attempt-a'))
    monkeypatch.setattr(api,'screenplay_service',ScreenplayService(repo,object()))
    monkeypatch.setenv('VIDEO_CALLBACK_TOKEN','synthetic-callback-secret')
    application=FastAPI();application.include_router(api.router,prefix='/api');client=TestClient(application)
    path='/api/novels/novel-a/screenplays/screenplay-1/motion-tasks/motion-1/callback'
    headers={'X-Video-Callback-Token':'synthetic-callback-secret'}
    payload={'status':'SUCCEEDED','url':'https://example.test/one.mp4','remote_task_id':'remote-a','submission_key':'attempt-a'}
    assert client.post(path,headers=headers,json={**payload,'submission_key':'older-attempt'}).status_code==409
    assert client.post(path,headers=headers,json=payload).status_code==200
    assert client.post(path,headers=headers,json=payload).status_code==200
    assert client.post(path,headers=headers,json={**payload,'url':'https://example.test/changed.mp4'}).status_code==400
    assert repo.rows[0]['motion_tasks'][0]['result']['url']==payload['url']


def test_direct_binary_speech_can_be_verified_and_imported(monkeypatch):
    client,nid,cid=project()
    uri='data:audio/wav;base64,'+base64.b64encode(wav_bytes()).decode()
    result=client.post(f'/api/novels/{nid}/speech-generations/import',json={'audio_uri':uri})
    assert result.status_code==202,result.text
    assert result.json()['media_type']=='audio/wav' and result.json()['filename'].endswith('.wav')
    bad=client.post(f'/api/novels/{nid}/speech-generations/import',json={'audio_uri':'data:audio/wav;base64,'+base64.b64encode(b'invalid').decode()})
    assert bad.status_code==502
