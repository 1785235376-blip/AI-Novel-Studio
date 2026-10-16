"""B03/B04 File and opt-in real PostgreSQL contracts; synthetic audio only."""
import base64
import copy
import json
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.audio_production_store import AudioProductionStore
from app.audio_providers import AudioGenerationResult
from app.services.audiobook_service import AudiobookService, AudiobookError
from app.experimental.voice_direction import DirectedAudiobookService, spoken_text
from app.experimental.voice_direction_api import create_voice_direction_router
from app.experimental.subtitle_timeline import SubtitleTimelineService, read_captions
from app.experimental.subtitle_timeline_api import create_subtitle_timeline_router
from app.experimental.audiobook_api import create_audiobook_router
from app.experimental.flags import require_flag
from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig, audio_asset, wav_bytes, branch_scope
from test_r3_audiobook_preparation import mapped_plan


@pytest.fixture
def setup(rig, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2,subtitle_timeline_v2')
    voice=DirectedAudiobookService(rig.store,rig.novels,rig.chapters,assets=rig.assets)
    subtitles=SubtitleTimelineService(rig.store,rig.novels,rig.chapters,voice,rig.assets)
    profile,plan=mapped_plan(rig,voice)
    return SimpleNamespace(voice=voice, subtitles=subtitles, profile=profile, plan=plan)


def directed(rig, setup, approve=False):
    v=setup.voice;p=setup.plan
    for seg in p['segments']:
        p=v.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],seg['id'],edit(p,seg,setup.profile))
    if approve:p=v.as_actor(rig.actor,v.review,rig.nid,rig.scope,rig.actor,p['id'],'approve',p['version'])
    return p


def edit(plan,seg,profile,**updates):
    return {'expected_version':plan['version'],'kind':seg['kind'],'character_id':seg.get('character_id') or 'alice',
            'profile_id':profile['id'],'reviewed_text':seg['text'],'attribution_reviewed':True,'text_reviewed':True,
            'voice_authorized':True,'emotion':'neutral','speech_rate':1.15,'pause_ms':320,'pronunciation_rules':[],**updates}


def test_only_corrected_audio_invalidated_and_source_text_unchanged(rig,setup):
    v=setup.voice;p=setup.plan;asset=audio_asset(rig)
    for seg in p['segments']:p=v.bind_audio(rig.nid,rig.scope,rig.actor,p['id'],seg['id'],{'expected_version':p['version'],'asset_id':asset['id']})
    before=rig.chapters.get(rig.chapter['id'])
    p=v.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],p['segments'][1]['id'],edit(p,p['segments'][1],setup.profile,reviewed_text='Revised spoken text'))
    assert p['segments'][1]['audio_asset_id'] is None
    assert all(s['audio_asset_id']==asset['id'] for i,s in enumerate(p['segments']) if i!=1)
    assert p['segments'][1]['text']!=p['segments'][1]['direction']['reviewed_text']
    assert rig.chapters.get(rig.chapter['id'])==before
    assert v.catalog(rig.nid,rig.scope,rig.actor)['plans'][0]['stale'] is False
    with pytest.raises(CapabilityVersionConflict):v.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],p['segments'][0]['id'],edit(p,p['segments'][0],setup.profile,expected_version=1))


def test_unknown_narration_override_lock_and_reorder(rig,setup):
    v=setup.voice;p=setup.plan;s=p['segments'][1]
    p=v.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],s['id'],edit(p,s,setup.profile,character_id=None,attribution_reviewed=False))
    assert p['segments'][1]['character_id'] is None and p['segments'][1]['attribution_status']=='NEEDS_REVIEW'
    p=v.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],s['id'],edit(p,s,setup.profile,kind='NARRATION'))
    assert p['segments'][1]['character_id']=='__narrator__'
    asset=audio_asset(rig)
    p=v.as_actor(rig.actor,v.bind_audio,rig.nid,rig.scope,rig.actor,p['id'],s['id'],{'expected_version':p['version'],'asset_id':asset['id']})
    p=v.lock(rig.nid,rig.scope,rig.actor,p['id'],s['id'],{'expected_version':p['version'],'locked':True})
    with pytest.raises(ValueError,match='LOCKED'):v.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],s['id'],edit(p,s,setup.profile))
    order=[r['id'] for r in reversed(p['segments'])]
    p=v.reorder(rig.nid,rig.scope,rig.actor,p['id'],{'expected_version':p['version'],'segment_ids':order})
    assert [s['id'] for s in p['segments']]==order


def test_safe_pronunciation_no_cascade_markup_or_regex(rig,setup):
    assert spoken_text('重庆 重庆市', [{'term':'重庆','pronunciation':'chongqing'},{'term':'chongqing','pronunciation':'WRONG'}])=='chongqing chongqing市'
    assert spoken_text('a.b axb',[{'term':'a.b','pronunciation':'literal'}])=='literal axb'
    p=setup.plan;s=p['segments'][0]
    for rules in [[{'term':'x','pronunciation':'<audio src="https://invalid"/>'}],[{'term':'x','pronunciation':'a'},{'term':'x','pronunciation':'b'}]]:
        with pytest.raises(ValueError):setup.voice.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],s['id'],edit(p,s,setup.profile,pronunciation_rules=rules))
    with pytest.raises(ValueError):setup.voice.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],s['id'],{**edit(p,s,setup.profile),'reference_audio_uri':'anything'})


def test_origin_inherited_reads_off_v1_other_actor_and_scope(rig,setup,monkeypatch):
    p=directed(rig,setup);v=setup.voice
    assert v.plans(rig.nid,rig.scope)==[]
    assert v.as_actor('other',v.list_review_items,rig.nid,rig.scope)==[]
    assert v.as_actor(rig.actor,v.plans,rig.nid,rig.scope)[0]['id']==p['id']
    assert v.as_actor(rig.actor,v.plans,rig.nid,branch_scope(rig))==[]
    for key,value in [('EXPERIMENTAL_FEATURES','audiobook_v2'),('V1_ACCEPTANCE_MODE','true')]:
        monkeypatch.setenv(key,value)
        assert v.as_actor(rig.actor,v.plans,rig.nid,rig.scope)==[]
        with pytest.raises(FileNotFoundError):v.as_actor(rig.actor,v.review,rig.nid,rig.scope,rig.actor,p['id'],'approve',p['version'])


def api_client(rig,setup,provider=None):
    app=FastAPI(); authority={'actor':rig.actor,'allowed':True}
    def authorize(nid,token,branch,permission):
        if not authority['allowed']:raise HTTPException(403,{'code':'REVOKED'})
        return authority['actor'],branch_scope(rig,branch) if branch else rig.scope
    def executor(scope,actor):return AudiobookService(AudioProductionStore(rig.root/'audio').for_branch(scope.get('branch_id')).for_actor(actor),rig.assets,scope.get('branch_id'))
    def resolve(pid):
        if not provider:raise ValueError('unavailable')
        return pid,'synthetic',provider
    app.include_router(create_audiobook_router(setup.voice,authorize,require_flag))
    app.include_router(create_voice_direction_router(setup.voice,authorize,require_flag,executor,resolve))
    app.include_router(create_subtitle_timeline_router(setup.subtitles,authorize,require_flag))
    return TestClient(app),authority,executor


def test_original_executor_synthetic_local_selected_only_private_until_explicit_review(rig,setup,monkeypatch):
    p=directed(rig,setup,True);calls=[]
    class Provider:
        local=True
        def generate(self,request):
            calls.append(request)
            return AudioGenerationResult('mock','synthetic','data:audio/wav;base64,'+base64.b64encode(wav_bytes(1000)).decode())
    client,authority,factory=api_client(rig,setup,Provider());base=f'/novels/{rig.nid}/experimental/voice-direction'
    queued=client.post(f'{base}/plans/{p["id"]}/queue',json={'expected_version':p['version'],'segment_ids':[p['segments'][1]['id']],'approve_selected':True}).json()
    assert len(queued['items'])==1 and calls==[]
    job=queued['items'][0]; assert job['estimated_duration_ms'] is None
    original=factory(rig.scope,rig.actor)
    with pytest.raises(AudiobookError,match='声音导演'):original.execute(rig.nid,job['id'],rig.chapter,lambda _:('mock','synthetic',Provider()))
    output=client.post(f'{base}/jobs/{job["id"]}/execute');assert output.status_code==200,output.text
    out=output.json();assert len(calls)==1 and calls[0].prompt==p['segments'][1]['direction']['reviewed_text']
    assert out['approval_status']=='PENDING' and out['timing_status']=='MEASURED_SEGMENT'
    assert rig.assets.list(rig.nid)==[]
    with pytest.raises(FileNotFoundError):rig.assets.content(out['asset_id'])
    assert client.get(f'{base}/jobs/{job["id"]}/audio').content.startswith(b'RIFF')
    authority['actor']='other';assert client.get(f'{base}/jobs').json()['items']==[]
    authority['actor']=rig.actor
    accepted=client.post(f'{base}/jobs/{job["id"]}/approve',json={'expected_asset_version':out['asset_version']})
    assert accepted.status_code==200,accepted.text
    assert len(rig.assets.list(rig.nid))==1
    encoded=json.dumps(accepted.json());assert '_required_features' not in encoded and '_origin_provenance' not in encoded
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2')
    assert original.store.load(rig.nid)['jobs']==[] and rig.assets.list(rig.nid)==[]
    original.store.mutate(rig.nid,lambda state:state.update(voice_bindings=[]))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2,voice_direction_v2,subtitle_timeline_v2')
    assert len(original.store.load(rig.nid)['jobs'])==1


def test_remote_source_change_permission_revocation_never_send(rig,setup):
    p=directed(rig,setup,True);calls=[]
    class Provider:
        local=False
        def generate(self,request):calls.append(request);raise AssertionError('must not send')
    client,auth,factory=api_client(rig,setup,Provider());base=f'/novels/{rig.nid}/experimental/voice-direction'
    def queue():return client.post(f'{base}/plans/{p["id"]}/queue',json={'expected_version':p['version'],'segment_ids':[p['segments'][0]['id']],'approve_selected':True}).json()['items'][0]
    job=queue();response=client.post(f'{base}/jobs/{job["id"]}/execute');assert response.status_code==403 and calls==[]
    job=queue();auth['allowed']=False;assert client.post(f'{base}/jobs/{job["id"]}/execute').status_code==403
    auth['allowed']=True;rig.chapters.save(rig.chapter['id'],{'version':rig.chapter['version'],'content':'Changed'})
    assert client.post(f'{base}/jobs/{job["id"]}/execute').status_code==409 and calls==[]


def caption(rig,setup,**overrides):
    asset=audio_asset(rig,2000)
    body={'asset_id':asset['id'],'title':'双语字幕','cues':[{'id':'cue1','start_tick':0,'end_tick':1000,'text':'你好 🌙\nHello'}],**overrides}
    return setup.subtitles.create_track(rig.nid,rig.scope,rig.actor,body)


def test_measured_waveform_exact_ticks_split_merge_and_export_readback(rig,setup,tmp_path):
    service=setup.subtitles;row=caption(rig,setup,timebase={'numerator':30000,'denominator':1001},cues=[{'id':'a','start_tick':0,'end_tick':30,'text':'你好🌙 Hello'}])
    assert row['media']['duration_seconds']=={'numerator':2,'denominator':1}
    assert row['media']['waveform']['status']=='MEASURED_PCM16_PEAKS'
    row=service.split(rig.nid,rig.scope,rig.actor,row['id'],'a',{'expected_version':row['version'],'split_tick':15,'left_text':'你好🌙','right_text':'Hello'})
    assert row['cues'][0]['end_tick']==row['cues'][1]['start_tick']==15
    second=row['cues'][1]['id']
    row=service.merge(rig.nid,rig.scope,rig.actor,row['id'],'a',{'expected_version':row['version'],'next_cue_id':second})
    for fmt in ['srt','vtt']:
        output=service.download(rig.nid,rig.scope,rig.actor,row['id'],row['version'],fmt)
        path=tmp_path/f'captions.{fmt}';path.write_bytes(output)
        parsed=read_captions(path.read_text(),fmt)
        assert parsed==[{'start_ms':0,'end_ms':1001,'text':'你好🌙\nHello'}]
    restart=SubtitleTimelineService(ExperimentalStore(rig.root,rig.backend,rig.store.database_url),rig.novels,rig.chapters,setup.voice,rig.assets)
    assert restart.records(rig.nid,rig.scope,rig.actor)['items'][0]['cues']==row['cues']


@pytest.mark.parametrize('cues,code',[
    ([{'id':'x','start_tick':2,'end_tick':1,'text':'text'}],'REVERSED'),
    ([{'id':'x','start_tick':0,'end_tick':2001,'text':'text'}],'OUT_OF_MEDIA'),
    ([{'id':'x','start_tick':0,'end_tick':500,'text':' ' }],'NONEMPTY|at least 1 character'),
    ([{'id':'x','start_tick':0,'end_tick':1000,'text':'one'},{'id':'y','start_tick':500,'end_tick':1500,'text':'two'}],'OVERLAP'),
    ([{'id':'x','start_tick':1000,'end_tick':1500,'text':'one'},{'id':'y','start_tick':0,'end_tick':500,'text':'two'}],'ORDER'),
])
def test_caption_invalid_ranges_and_text(rig,setup,cues,code):
    with pytest.raises(ValueError,match=code):caption(rig,setup,cues=cues)


def test_caption_stale_media_speaker_and_permission(rig,setup):
    p=directed(rig,setup);service=setup.subtitles;seg=p['segments'][0]
    row=caption(rig,setup,plan_id=p['id'],expected_plan_version=p['version'],cues=[{'id':'a','start_tick':0,'end_tick':1000,'text':'Speaker','segment_id':seg['id']}])
    assert row['speakers'][seg['id']]['name']=='旁白'
    assert service.records(rig.nid,rig.scope,'other')['items']==[]
    with pytest.raises(FileNotFoundError):service.download(rig.nid,branch_scope(rig),rig.actor,row['id'],row['version'],'srt')
    setup.voice.edit_direction(rig.nid,rig.scope,rig.actor,p['id'],seg['id'],edit(p,seg,setup.profile,reviewed_text='Changed direction'))
    assert service.records(rig.nid,rig.scope,rig.actor)['items'][0]['stale']
    assert 'cues' not in service.records(rig.nid,rig.scope,rig.actor)['items'][0]
    with pytest.raises(StaleSourceError):service.download(rig.nid,rig.scope,rig.actor,row['id'],row['version'],'srt')
    row=caption(rig,setup);rig.assets.update_metadata(row['asset_id'],{'model_id':'replacement-version'})
    with pytest.raises(StaleSourceError,match='MEDIA_CHANGED'):service.download(rig.nid,rig.scope,rig.actor,row['id'],row['version'],'vtt')


def test_mounted_permissions_version_conflict_no_cache_and_off(rig,setup,monkeypatch):
    client,auth,_=api_client(rig,setup);row=caption(rig,setup);base=f'/novels/{rig.nid}/experimental/subtitle-timeline'
    response=client.get(f'{base}/records/{row["id"]}/file.vtt?expected_version=1');assert response.status_code==200 and response.text.startswith('WEBVTT')
    assert response.headers['cache-control']=='no-store'
    conflict=client.put(f'{base}/records/{row["id"]}',json={'expected_version':99,'cues':row['cues']});assert conflict.status_code==409
    assert '你好' not in conflict.text and 'asset_snapshot' not in conflict.text
    auth['allowed']=False;assert client.get(f'{base}/records').status_code==403
    auth['allowed']=True;monkeypatch.setenv('V1_ACCEPTANCE_MODE','true');assert client.get(f'{base}/records').status_code==404


def test_asset_origin_owner_cannot_forge_clear_or_leak_conflict(rig,setup,monkeypatch):
    content=base64.b64encode(wav_bytes()).decode()
    asset=rig.assets.create(rig.nid,'private.wav',content,'audio/wav','audio',required_features=('voice_direction_v2',),owner_actor_id=rig.actor)
    assert rig.assets.list(rig.nid)==[] and rig.assets.list(rig.nid,actor_id='other')==[]
    assert len(rig.assets.list(rig.nid,actor_id=rig.actor))==1
    for method in [rig.assets.get,rig.assets.content]:
        with pytest.raises(FileNotFoundError):method(asset['id'],actor_id='other')
    with pytest.raises(ValueError):rig.assets.update_metadata(asset['id'],{'_owner_actor_id':None},actor_id=rig.actor)
    with pytest.raises(CapabilityVersionConflict) as error:rig.assets.promote_owned(asset['id'],actor_id=rig.actor,branch_id=None,expected_version=99,provenance={})
    assert '_owner_actor_id' not in error.value.current
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    with pytest.raises(FileNotFoundError):rig.assets.content(asset['id'],actor_id=rig.actor)


def test_actual_audio_change_invalidates_linked_captions_and_only_actual_waveform(rig,setup):
    p=directed(rig,setup);seg=p['segments'][0];v=setup.voice;asset=audio_asset(rig,2000)
    p=v.as_actor(rig.actor,v.bind_audio,rig.nid,rig.scope,rig.actor,p['id'],seg['id'],{'expected_version':p['version'],'asset_id':asset['id']})
    row=setup.subtitles.create_track(rig.nid,rig.scope,rig.actor,{'asset_id':asset['id'],'plan_id':p['id'],'expected_plan_version':p['version'],'cues':[{'id':'a','start_tick':0,'end_tick':1000,'text':'old timing','segment_id':seg['id']}]})
    replacement=audio_asset(rig,1000)
    v.as_actor(rig.actor,v.bind_audio,rig.nid,rig.scope,rig.actor,p['id'],seg['id'],{'expected_version':p['version'],'asset_id':replacement['id']})
    with pytest.raises(StaleSourceError):setup.subtitles.download(rig.nid,rig.scope,rig.actor,row['id'],1,'srt')


def test_selected_queue_idempotency_and_source_changes_after_send_discard_output(rig,setup):
    p=directed(rig,setup,True);calls=[]
    class Provider:
        local=True
        def generate(self,request):
            calls.append(request)
            rig.chapters.save(rig.chapter['id'],{'version':rig.chapter['version'],'content':'Changed during generation'})
            return AudioGenerationResult('mock','synthetic','data:audio/wav;base64,'+base64.b64encode(wav_bytes()).decode())
    client,auth,factory=api_client(rig,setup,Provider());base=f'/novels/{rig.nid}/experimental/voice-direction'
    body={'expected_version':p['version'],'segment_ids':[p['segments'][0]['id']],'approve_selected':True}
    one=client.post(f'{base}/plans/{p["id"]}/queue',json=body,headers={'Idempotency-Key':'same-request'}).json()
    again=client.post(f'{base}/plans/{p["id"]}/queue',json=body,headers={'Idempotency-Key':'same-request'}).json()
    assert one['items'][0]['id']==again['items'][0]['id']
    response=client.post(f'{base}/jobs/{one["items"][0]["id"]}/execute')
    assert response.status_code>=400 and len(calls)==1 and rig.assets.list(rig.nid,actor_id=rig.actor)==[]


def test_origin_propagates_to_derived_asset_and_promotion_retry_is_safe(rig,setup,monkeypatch):
    raw=base64.b64encode(wav_bytes()).decode();a=rig.assets.create(rig.nid,'private.wav',raw,'audio/wav','audio',required_features=('voice_direction_v2',),owner_actor_id=rig.actor)
    promoted=rig.assets.promote_owned(a['id'],actor_id=rig.actor,branch_id=None,expected_version=1,provenance={'job':'synthetic'})
    same=rig.assets.promote_owned(a['id'],actor_id=rig.actor,branch_id=None,expected_version=1,provenance={'job':'synthetic'})
    assert promoted==same
    child=rig.assets.create(rig.nid,'derived.wav',raw,'audio/wav','audio')
    rig.assets.update_metadata(child['id'],{'source_asset_ids':[a['id']]})
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','audiobook_v2')
    assert rig.assets.list(rig.nid)==[]
