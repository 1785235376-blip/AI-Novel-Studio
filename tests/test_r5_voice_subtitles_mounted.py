"""B03/B04 actual /api and /api/v1 composition with real membership authority."""
import copy
import json
import base64
import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_r3_media_support import wav_bytes
from app.experimental.flags import FLAGS
from app.experimental.voice_direction_api import voice_task_projection, create_runtime_executor


def prepare(e):
    voice=checked(e.client.post(e.base+'/audiobook/profiles',json={'display_name':'Synthetic voice','provider_id':'unconfigured-local','model_id':'synthetic-only','voice_id':'fixture','license_note':'Original synthetic fixture, no real voice'}),201)
    checked(e.client.post(e.base+'/audiobook/mappings',json={'character_id':'__narrator__','profile_id':voice['id']}))
    p=checked(e.client.post(e.base+'/audiobook/plans',json={'chapter_id':e.chapter['id']}),201)
    for s in p['segments']:
        p=checked(e.client.put(e.base+f'/voice-direction/plans/{p["id"]}/segments/{s["id"]}',json={
            'expected_version':p['version'],'kind':'NARRATION','profile_id':voice['id'],'reviewed_text':s['text'],
            'text_reviewed':True,'attribution_reviewed':True,'voice_authorized':True}))
    return p


def test_mounted_directed_original_inbox_review_local_and_source_invalidation(mounted):
    e=mounted;p=prepare(e)
    listed=checked(e.client.get(e.base+'/review-inbox',params={'domain':'audiobook'}))
    assert listed['total']==1 and listed['items'][0]['id']==p['id']
    approved=checked(e.client.post(e.base+f'/review-inbox/audiobook/{p["id"]}/approve',json={'expected_version':p['version']}))
    assert approved['status']=='APPROVED'
    job=checked(e.client.post(e.base+f'/voice-direction/plans/{p["id"]}/queue',json={'expected_version':approved['version'],'segment_ids':[p['segments'][0]['id']],'approve_selected':True}),202)['items'][0]
    result=voice_task_projection(e.experimental.audiobook_service,e.nid,e.scope,'local-author')
    assert result['items'][0]['id']==job['id'] and result['has_more'] is False
    assert set(result['items'][0])=={'id','status','chapter_id','version','stale','experimental_origin'}
    # The legacy root namespace never gains actor-private local audio jobs.
    original=checked(e.client.get(e.prefix+f'/novels/{e.nid}/audiobook/jobs'))
    assert original['total']==0
    current=e.chapters.get(e.chapter['id']);e.chapters.save(current['id'],{'version':current['version'],'content':'Edited source'})
    assert e.client.post(e.base+f'/voice-direction/jobs/{job["id"]}/execute').status_code==409
    stale=voice_task_projection(e.experimental.audiobook_service,e.nid,e.scope,'local-author')['items'][0]
    assert stale['stale'] and stale['chapter_id'] is None


def test_mounted_directed_disabled_feature_and_v1_cannot_use_generic_reads_reviews(mounted,monkeypatch):
    e=mounted;p=prepare(e)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,unified_review_inbox')
    assert checked(e.client.get(e.base+'/audiobook/plans'))['items']==[]
    assert checked(e.client.get(e.base+'/review-inbox',params={'domain':'audiobook'}))['total']==0
    for path in (f'/audiobook/plans/{p["id"]}/approve',f'/review-inbox/audiobook/{p["id"]}/approve'):
        assert e.client.post(e.base+path,json={'expected_version':p['version']}).status_code==404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(FLAGS));monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    for path in ('/voice-direction/catalog','/voice-direction/jobs','/subtitle-timeline/records','/audiobook/plans','/review-inbox'):
        assert e.client.get(e.base+path).status_code==404
    assert voice_task_projection(e.experimental.audiobook_service,e.nid,e.scope,'local-author')=={'items':[],'has_more':False}


def test_mounted_real_trusted_actor_membership_branch_inbox_origin_fences(mounted,monkeypatch):
    e=mounted;p=prepare(e);e=scoped(e,monkeypatch)
    assert checked(e.client.get(e.base+'/voice-direction/catalog',headers=e.headers))['plans']==[]
    assert e.client.get(e.base+'/voice-direction/catalog').status_code in (400,401,403)
    # Existing R3 deliberately has no branch manuscript adapter. Verify the
    # production route rejects base text instead of fabricating branch content.
    response=e.client.post(e.base+'/audiobook/plans',headers=e.headers,json={'chapter_id':e.chapter['id']})
    assert response.status_code==409 and 'BRANCH_SOURCE_ADAPTER_REQUIRED' in response.text
    # Persist a synthetic old branch record to exercise real read/review origin
    # fencing. It is correctly stale; approval must not bypass source fencing.
    payload={k:v for k,v in p.items() if k not in {'id','novel_id','scope','version','created_by','created_at','updated_by','updated_at','history'}}
    legacy=e.experimental.audiobook_service.create(e.nid,e.scope,e.lead,e.experimental.audiobook_service.PLANS,payload)
    own=checked(e.client.get(e.base+'/review-inbox',headers=e.headers,params={'domain':'audiobook'}))
    assert own['total']==1 and own['items'][0]['stale']
    for endpoint in ('/audiobook/plans','/review-inbox?domain=audiobook'):
        other=checked(e.client.get(e.base+endpoint,headers=e.viewer_headers));assert other['items']==[]
    assert e.client.post(e.base+f'/review-inbox/audiobook/{legacy["id"]}/approve',headers=e.viewer_headers,json={'expected_version':1}).status_code==403
    assert e.client.post(e.base+f'/review-inbox/audiobook/{legacy["id"]}/approve',headers=e.headers,json={'expected_version':1}).status_code==409
    rejected=checked(e.client.post(e.base+f'/review-inbox/audiobook/{legacy["id"]}/reject',headers=e.headers,json={'expected_version':1}))
    assert rejected['status']=='REJECTED'
    e.authorization.revoke_role(e.role,e.lead)
    assert e.client.get(e.base+'/review-inbox',headers=e.headers).status_code==403
    assert e.client.get(e.base+'/voice-direction/catalog',headers=e.headers).status_code==403


def test_mounted_measured_caption_file_current_asset_and_source_snapshots(mounted):
    e=mounted;p=prepare(e)
    asset=checked(e.client.post(e.prefix+f'/novels/{e.nid}/assets',json={'novel_id':e.nid,'filename':'measured.wav','kind':'audio','media_type':'audio/wav','content_base64':base64.b64encode(wav_bytes(2000)).decode()}))
    row=checked(e.client.post(e.base+'/subtitle-timeline/records',json={'asset_id':asset['id'],'plan_id':p['id'],'expected_plan_version':p['version'],'cues':[{'id':'c','start_tick':0,'end_tick':1500,'text':'Synthetic 中文🌙','segment_id':p['segments'][0]['id']}]}),201)
    assert row['media']['waveform']['status']=='MEASURED_PCM16_PEAKS'
    response=e.client.get(e.base+f'/subtitle-timeline/records/{row["id"]}/file.vtt?expected_version=1')
    assert response.status_code==200 and response.text.startswith('WEBVTT') and response.headers['cache-control']=='no-store'
    e.assets.update_metadata(asset['id'],{'model_id':'changed-source'})
    stale=checked(e.client.get(e.base+'/subtitle-timeline/records'))['items'][0]
    assert stale['stale'] and 'cues' not in stale
    assert e.client.get(e.base+f'/subtitle-timeline/records/{row["id"]}/file.srt?expected_version=1').status_code==409


def test_mounted_bounded_safe_task_projection(mounted):
    e=mounted;p=prepare(e);p=checked(e.client.post(e.base+f'/audiobook/plans/{p["id"]}/approve',json={'expected_version':p['version']}))
    job=checked(e.client.post(e.base+f'/voice-direction/plans/{p["id"]}/queue',json={'expected_version':p['version'],'segment_ids':[p['segments'][0]['id']],'approve_selected':True}),202)['items'][0]
    executor=create_runtime_executor(e.scope,'local-author')
    def multiply(state):state['jobs']=[{**copy.deepcopy(job),'id':f'bounded-{n}'} for n in range(110)]
    executor.store.mutate(e.nid,multiply)
    result=voice_task_projection(e.experimental.audiobook_service,e.nid,e.scope,'local-author')
    assert len(result['items'])==100 and result['has_more']
    encoded=json.dumps(result);assert 'source_text' not in encoded and 'direction_binding' not in encoded and 'pronunciation' not in encoded
    assert voice_task_projection(e.experimental.audiobook_service,e.nid,e.scope,'other')['items']==[]


def test_mounted_source_privacy_revocation_and_remote_provider_never_send(mounted,monkeypatch):
    """Synthetic resolver protocol only; no external model/provider call."""
    from app.source_privacy import content_digest
    import app.audio_providers as providers
    e=mounted;p=prepare(e);source=e.chapters.get(e.chapter['id'])
    path=e.prefix+f'/novels/{e.nid}/chapters/{source["id"]}/privacy'
    checked(e.client.put(path,json={'privacy_level':'CLOUD_ALLOWED','expected_version':source['version'],'content_sha256':content_digest(source)}))
    p=checked(e.client.post(e.base+f'/audiobook/plans/{p["id"]}/approve',json={'expected_version':p['version']}))
    job=checked(e.client.post(e.base+f'/voice-direction/plans/{p["id"]}/queue',json={'expected_version':p['version'],'segment_ids':[p['segments'][0]['id']],'approve_selected':True}),202)['items'][0]
    assert job['privacy_level']=='CLOUD_ALLOWED'
    checked(e.client.put(path,json={'privacy_level':'LOCAL_ONLY','expected_version':source['version'],'content_sha256':content_digest(source)}))
    calls=[]
    class SyntheticRemote:
        local=False
        def generate(self,request):calls.append(request);raise AssertionError('must never transmit')
    monkeypatch.setattr(providers,'resolve_provider',lambda *args,**kwargs:('synthetic-remote','fixture',SyntheticRemote()))
    response=e.client.post(e.base+f'/voice-direction/jobs/{job["id"]}/execute')
    assert response.status_code==403 and response.json()['detail']['code']=='VOICE_REMOTE_BUDGET_NOT_INTEGRATED'
    assert not calls and not e.assets.list(e.nid)


def test_mounted_workspace_tasks_project_directed_owner_and_hide_other_actor_off_v1(mounted,monkeypatch):
    e=mounted;p=prepare(e)
    p=checked(e.client.post(e.base+f'/audiobook/plans/{p["id"]}/approve',json={'expected_version':p['version']}))
    job=checked(e.client.post(e.base+f'/voice-direction/plans/{p["id"]}/queue',json={'expected_version':p['version'],'segment_ids':[p['segments'][0]['id']],'approve_selected':True}),202)['items'][0]
    tasks=checked(e.client.get(e.base+'/workspace/tasks'))
    row=next(r for r in tasks['items'] if r['id']==job['id'])
    assert row['authority']=='voice_direction' and row['status']=='QUEUED' and row['feature']=='voice_direction_v2'
    assert 'direction_binding' not in json.dumps(tasks) and 'source_text' not in json.dumps(tasks)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','workspace_tools_v2,audiobook_v2,unified_review_inbox')
    off=checked(e.client.get(e.base+'/workspace/tasks'))
    assert job['id'] not in json.dumps(off) and not any(r['authority']=='voice_direction' for r in off['items'])
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(FLAGS));monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert e.client.get(e.base+'/workspace/tasks').status_code==404
    monkeypatch.delenv('V1_ACCEPTANCE_MODE');e=scoped(e,monkeypatch)
    other=checked(e.client.get(e.base+'/workspace/tasks',headers=e.viewer_headers))
    assert job['id'] not in json.dumps(other) and not any(r['authority']=='voice_direction' for r in other['items'])


def test_mounted_production_pcm_mixer_preview_export_and_review(mounted, monkeypatch):
    """Production composer and /api aliases, synthetic PCM only, no provider."""
    e = mounted; p = prepare(e)
    capability = checked(e.client.get(e.base+'/audiobook/capabilities'))
    assert capability['mixer'] == 'local-pcm16-wav-v1'
    source = e.chapters.get(e.chapter['id'])
    for index, segment in enumerate(p['segments']):
        asset = checked(e.client.post(e.prefix+f'/novels/{e.nid}/assets', json={
            'novel_id':e.nid,'filename':f'mix-{index}.wav','kind':'audio','media_type':'audio/wav',
            'content_base64':base64.b64encode(wav_bytes(100, sample=100+index)).decode()}))
        p = checked(e.client.put(e.base+f'/audiobook/plans/{p["id"]}/segments/{segment["id"]}/audio', json={'expected_version':p['version'],'asset_id':asset['id']}))
    p = checked(e.client.post(e.base+f'/audiobook/plans/{p["id"]}/approve', json={'expected_version':p['version']}))
    mixed = checked(e.client.post(e.base+f'/voice-direction/plans/{p["id"]}/mix', json={'expected_version':p['version']}))
    catalog = checked(e.client.get(e.base+'/voice-direction/catalog'))
    assert catalog['mixes'][0]['id'] == mixed['id'] and 'content_base64' not in json.dumps(catalog)
    url = e.base+f'/voice-direction/mixes/{mixed["id"]}/audio?expected_version={mixed["version"]}'
    audio = e.client.get(url)
    assert audio.status_code == 200 and audio.content.startswith(b'RIFF')
    approved = checked(e.client.post(e.base+f'/review-inbox/audiobook/{mixed["id"]}/approve', json={'expected_version':mixed['version']}))
    assert e.assets.content(approved['asset_id']) == audio.content
    assert e.chapters.get(source['id']) == source
    current_url = e.base+f'/voice-direction/mixes/{mixed["id"]}/audio?expected_version={approved["version"]}'
    assert e.client.get(current_url).content == audio.content
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,unified_review_inbox')
    assert checked(e.client.get(e.base+'/audiobook/mixes'))['items'] == []
    assert e.client.get(current_url).status_code == 404
    with pytest.raises(FileNotFoundError): e.assets.content(approved['asset_id'])
