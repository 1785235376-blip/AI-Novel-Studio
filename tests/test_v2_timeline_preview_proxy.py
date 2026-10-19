"""Fixed half preview output, real CPU/File original export owner; synthetic media only."""
from copy import deepcopy
import hashlib,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.services.studio_timeline_export import PREVIEW_SCALE,export_profile_digest,export_video_dimensions,normalize_export_profile,validate_export_admission,probe_media_file,run_guarded_process
from app.services.studio_timeline_render import normalize_studio_timeline
from test_v2_independent_workspace import rig as original_rig,import_asset,reopened
from test_v2_audio_editing_pipeline import production,source
from test_v2_audio_wav_controls import action

CAP=25*1024*1024
PROFILE={'preset':'DELIVERY_H264_MP4','video_bitrate_kbps':1500,'audio_bitrate_kbps':96,'crf':28}
HALF={**PROFILE,'preview_scale':PREVIEW_SCALE}
LEGACY={'REVIEW_MP4': {'profile': {'preset': 'REVIEW_MP4'}, 'digest': '570cd5c5655bd5a9bd680658c9810583d89398c16faa543ca5472b2e5abd7ab4'}, 'DELIVERY_H264_MP4': {'profile': {'preset': 'DELIVERY_H264_MP4', 'video_bitrate_kbps': 4000, 'audio_bitrate_kbps': 192, 'crf': 20}, 'digest': 'b80a4ff2c93b505c993832b881f49e95e5af5664f8d36dc74c8b8cd8081b539a'}, 'DELIVERY_VP9_WEBM': {'profile': {'preset': 'DELIVERY_VP9_WEBM', 'video_bitrate_kbps': 2000, 'audio_bitrate_kbps': 128, 'crf': 30}, 'digest': 'fcb580086f322de8f81a5d329fb0f3ddf734bc9919fbe695691ab7cf5ed12e2f'}, 'AUDIO_WAV_PCM16': {'profile': {'preset': 'AUDIO_WAV_PCM16'}, 'digest': '4884af4718e40fb54f7ccc5d7baaaaa406422d869de08c0b789a40d931815440'}}
@pytest.fixture
def proxy_owner(tmp_path,monkeypatch):
    generator=original_rig.__wrapped__(SimpleNamespace(param='file'),tmp_path,monkeypatch);e=next(generator)
    e.service.activate(e.nid,e.scope,e.actor)
    clip=tmp_path/'synthetic-source.mp4'
    run_guarded_process([shutil.which('ffmpeg'),'-nostdin','-v','error','-threads','1','-f','lavfi','-i','testsrc2=s=98x66:r=10:d=1','-an','-c:v','mpeg4','-threads','1','-y',str(clip)],cwd=tmp_path,guard=lambda:None,timeout=20)
    e.source_data=clip.read_bytes();e.source=import_asset(e,data=e.source_data,filename='synthetic-source.mp4',kind='video');e.production=production(e)
    value={'schema_version':2,'duration_ms':1000,'width':98,'height':66,'fps':10,'captions':[],
        'tracks':[{'id':'picture','kind':'VIDEO','order':0,'clips':[{'id':'clip','source_snapshot':source(e.source),'start_ms':0,'in_ms':0,'out_ms':1000}]}]}
    e.timeline=e.production.timeline_save(e.nid,e.scope,e.actor,None,{'title':'Half preview proof','expected_version':0,'timeline':value},lambda:None)
    yield e
    try:next(generator)
    except StopIteration:pass

def reviewed(e):return {'expected_version':e.timeline['version'],'reviewed_timeline_digest':e.timeline['timeline_digest']}
def export(e,profile,key):
    preview=e.production.timeline_export_preview(e.nid,e.scope,e.actor,e.timeline['id'],{**reviewed(e),'export_profile':profile},lambda:None)
    body={**reviewed(e),'export_profile':profile,'request_id':key,'reviewed_export_digest':preview['preview_digest']}
    return preview,body,e.production.timeline_export(e.nid,e.scope,e.actor,e.timeline['id'],body,lambda:None)

def test_closed_proxy_profile_retains_all_legacy_default_identities():
    for item in LEGACY.values():
        profile={'preset':item['profile']['preset']}
        assert normalize_export_profile(profile)==item['profile'] and export_profile_digest(profile)==item['digest']
    for preset in ['REVIEW_MP4','DELIVERY_VP9_WEBM','AUDIO_WAV_PCM16']:
        with pytest.raises(ValueError):normalize_export_profile({'preset':preset,'preview_scale':PREVIEW_SCALE})
    for value in [None,True,False,0,.5,'HALF','scale=iw/2:ih/2',{},[]]:
        with pytest.raises(ValueError):normalize_export_profile({**PROFILE,'preview_scale':value})
    assert export_video_dimensions({'width':98,'height':66},HALF)==(48,32)
    assert export_video_dimensions({'width':34,'height':34},HALF)==(16,16)
    assert export_video_dimensions({'width':98,'height':66},PROFILE)==(98,66)
    with pytest.raises(ValueError,match='DIMENSIONS_UNSUPPORTED'):export_video_dimensions({'width':30,'height':64},HALF)
    assert export_profile_digest(PROFILE)!=export_profile_digest(HALF)


def test_real_file_half_candidate_reuses_original_job_and_final_export_retains_canvas(proxy_owner,monkeypatch,tmp_path):
    e=proxy_owner;before=deepcopy(e.timeline);observed=[]
    import app.services.studio_timeline_export as native
    original=native.run_guarded_process
    def capture(argv,**kwargs):
        if '-filter_complex' in argv:observed.append(argv[argv.index('-filter_complex')+1])
        return original(argv,**kwargs)
    monkeypatch.setattr(native,'run_guarded_process',capture)
    preview,body,job=export(e,HALF,'half-original-export');assert job['status']=='SUCCEEDED',job
    assert job['execution_recipe']['timeline']==before['timeline'] and job['execution_recipe']['export_profile']==HALF
    assert job['media_measurement']['width']==48 and job['media_measurement']['height']==32
    assert 'scale=48:32:flags=bilinear,setsar=1[vpreview]' in observed[0]
    meta,data=e.production.candidate(e.nid,e.scope,e.actor,'timeline',job['id'],lambda:None)
    path=tmp_path/'actual-half.mp4';path.write_bytes(data);probe=probe_media_file(path,guard=lambda:None)
    video=next(s for s in probe['streams'] if s['codec_type']=='video');audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert (video['width'],video['height'],video['codec_name'])==(48,32,'h264')
    assert video['avg_frame_rate']=='10/1' and int(video['nb_frames'])==10
    assert abs(float(probe['format']['duration'])-1)<.1 and audio['codec_name']=='aac' and audio['channels']==2 and int(audio['sample_rate'])==48000
    with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,job['output_candidate']['id'])
    fresh=production(e,reopened(e));again=fresh.timeline_export(e.nid,e.scope,e.actor,e.timeline['id'],body,lambda:None)
    assert all(again[key] == value for key, value in job.items() if key not in {'execution_state', 'needs_reconciliation'})
    assert again['execution_state'] == 'SUCCEEDED' and again['needs_reconciliation'] is False and len(observed) == 1
    normal_preview,_,normal=export(e,PROFILE,'normal-final-export');assert normal['status']=='SUCCEEDED',normal
    assert normal['media_measurement']['width']==98 and normal['media_measurement']['height']==66
    assert preview['preview_digest']!=normal_preview['preview_digest'] and len(observed)==2
    _, full_data=e.production.candidate(e.nid,e.scope,e.actor,'timeline',normal['id'],lambda:None)
    full_path=tmp_path/'actual-full.mp4';full_path.write_bytes(full_data);full_probe=probe_media_file(full_path,guard=lambda:None)
    full_video=next(stream for stream in full_probe['streams'] if stream['codec_type']=='video')
    assert (full_video['width'],full_video['height'],int(full_video['nb_frames']))==(98,66,10)
    assert e.production.timeline_get(e.nid,e.scope,e.actor,e.timeline['id'],lambda:None)==before
    assert (e.assets.root/(e.source['id']+'.bin')).read_bytes()==e.source_data
    record={'scope':'original export owner; playback public request wiring separately required','row':before,'source':e.source,'half_job':job,'normal_job':normal,'full_probe':full_probe,'half_preview':preview,'normal_preview':normal_preview,'probe':probe,'sha256':hashlib.sha256(data).hexdigest(),'source_sha256':hashlib.sha256(e.source_data).hexdigest(),'timeline_unchanged':True,'render_calls':len(observed)}
    (tmp_path/'half-proof.json').write_text(json.dumps(record,indent=2),encoding='utf-8')


@pytest.mark.parametrize('change',['cancel','source','unknown'])
def test_proxy_original_cancel_source_and_unknown_do_not_repeat_render(proxy_owner,monkeypatch,change):
    e=proxy_owner;import app.services.studio_timeline_export as native
    original=native.run_guarded_process;renders=[]
    def guarded(argv,**kwargs):
        result=original(argv,**kwargs)
        if '-filter_complex' in argv:
            renders.append(argv)
            if change=='source':
                with e.service._asset_scope(e.nid,e.scope):e.assets.update_metadata(e.source['id'],{'scene_id':'changed'},expected_version=e.source['version'])
            elif change=='cancel':
                live=next(j for j in e.production.list(e.nid,e.scope,e.actor,lambda:None)['items'] if j['status']=='RUNNING')
                assert e.production.cancel(e.nid,e.scope,e.actor,'timeline',live['id'],action(live),lambda:None)['status']=='CANCELLED'
        return result
    monkeypatch.setattr(native,'run_guarded_process',guarded)
    create=e.assets.create
    if change=='unknown':
        def lost(*args,**kwargs):create(*args,**kwargs);raise OSError('lost publication reply')
        monkeypatch.setattr(e.assets,'create',lost)
    _,body,job=export(e,HALF,'half-boundary-'+change)
    assert len(renders)==1
    assert job['status']=={'cancel':'CANCELLED','source':'FAILED','unknown':'UNKNOWN'}[change],job
    if change!='unknown':assert job['output_candidate'] is None
    monkeypatch.setattr(native,'run_guarded_process',lambda *a,**k:pytest.fail('old request must never re-render'))
    monkeypatch.setattr(e.assets,'create',create)
    if change!='source':
        assert e.production.timeline_export(e.nid,e.scope,e.actor,e.timeline['id'],body,lambda:None)['id']==job['id']
    if change=='unknown':
        recovered=e.production.reconcile(e.nid,e.scope,e.actor,'timeline',job['id'],action(job),lambda:None)
        assert recovered['status']=='SUCCEEDED' and recovered['media_measurement']==job['media_measurement']
        with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,recovered['output_candidate']['id'])
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==1


def test_public_playback_resolution_is_closed_and_waveform_does_not_inherit_it():
    from pydantic import ValidationError
    from app.creative.production_execution_models import TimelinePlaybackPreview, TimelinePlaybackBuild, TimelinePlaybackAttestation, TimelineWaveformPreview
    base={'expected_version':1,'reviewed_timeline_digest':'a'*64}
    assert TimelinePlaybackPreview.model_validate(base).model_dump()==base
    assert TimelinePlaybackPreview.model_validate({**base,'preview_resolution':'HALF'}).model_dump()=={**base,'preview_resolution':'HALF'}
    for model, extra in [(TimelinePlaybackPreview,{}),(TimelinePlaybackBuild,{'reviewed_playback_digest':'b'*64}),
            (TimelinePlaybackAttestation,{'reviewed_playback_digest':'b'*64,'expected_job_version':1,'expected_request_digest':'c'*64})]:
        for invalid in [None,True,False,0,.5,'ORIGINAL','half','scale=iw/2',{},[]]:
            with pytest.raises(ValidationError):model.model_validate({**base,**extra,'preview_resolution':invalid})
    audio={'clip_id':'sound','source_snapshot':{'id':'audio','kind':'ASSET','asset_kind':'audio','version':1,'digest':'d'*64}}
    assert TimelineWaveformPreview.model_validate({**base,**audio}).model_dump()=={**base,**audio}
    with pytest.raises(ValidationError,match='WAVEFORM_PLAYBACK_RESOLUTION_UNSUPPORTED'):
        TimelineWaveformPreview.model_validate({**base,**audio,'preview_resolution':'HALF'})


def test_audio_file_playback_keeps_original_wav_and_refuses_video_resolution(tmp_path,monkeypatch):
    from test_v2_audio_wav_controls import wav_bytes
    generator=original_rig.__wrapped__(SimpleNamespace(param='file'),tmp_path,monkeypatch);e=next(generator)
    try:
        e.service.activate(e.nid,e.scope,e.actor);p=production(e)
        asset=import_asset(e,data=wav_bytes(),filename='audio-resolution-boundary.wav',kind='audio')
        row=p.timeline_save(e.nid,e.scope,e.actor,None,{'title':'Audio stays WAV','expected_version':0,'timeline':{
            'schema_version':3,'media_kind':'AUDIO','duration_ms':100,'tracks':[{'id':'sound','kind':'AUDIO','order':0,'clips':[
                {'id':'voice','source_snapshot':source(asset),'start_ms':0,'in_ms':0,'out_ms':100}]}]}},lambda:None)
        value={'expected_version':row['version'],'reviewed_timeline_digest':row['timeline_digest']}
        preview=p.timeline_playback_preview(e.nid,e.scope,e.actor,row['id'],value,lambda:None)
        assert preview['export_preview']['export_profile']=={'preset':'AUDIO_WAV_PCM16'} and preview['job']is None
        with pytest.raises(ValueError,match='PLAYBACK_VIDEO_RESOLUTION_REQUIRED'):
            p.timeline_playback_preview(e.nid,e.scope,e.actor,row['id'],{**value,'preview_resolution':'HALF'},lambda:None)
        assert p.timeline_get(e.nid,e.scope,e.actor,row['id'],lambda:None)==row and p.list(e.nid,e.scope,e.actor,lambda:None)['items']==[]
    finally:
        try:next(generator)
        except StopIteration:pass


def test_real_playback_half_cache_reopen_attest_and_default_identity(proxy_owner,monkeypatch,tmp_path):
    import subprocess
    from app.creative.timeline_playback import TimelinePlayback
    from app.experimental.common import StaleSourceError
    import app.services.studio_timeline_export as native
    e=proxy_owner; before=deepcopy(e.timeline); renders=[]; original=native.run_guarded_process
    def counted(argv,**kwargs):
        if '-filter_complex' in argv:renders.append(argv)
        return original(argv,**kwargs)
    monkeypatch.setattr(native,'run_guarded_process',counted)
    # Compare omitted resolution against the exact pre-feature owner implementation.
    baseline=subprocess.check_output(['git','show','d9b2ea4b602af099f133e7ef7e954fb7618979ae:app/creative/timeline_playback.py'],cwd=Path(__file__).resolve().parents[1])
    namespace={'__package__':'app.creative','__name__':'app.creative._legacy_playback_probe'}
    exec(compile(baseline,'<exact d9b playback owner>','exec'),namespace)
    full=e.production.timeline_playback_preview(e.nid,e.scope,e.actor,before['id'],reviewed(e),lambda:None)
    old=namespace['TimelinePlayback'](e.production).preview(e.nid,e.scope,e.actor,before['id'],reviewed(e),lambda:None)
    assert full==old and full['cache_state']=='MISSING' and not renders
    half_input={**reviewed(e),'preview_resolution':'HALF'}
    half=e.production.timeline_playback_preview(e.nid,e.scope,e.actor,before['id'],half_input,lambda:None)
    assert half['cache_key']!=full['cache_key'] and half['request_id']!=full['request_id'] and half['job_id']!=full['job_id']
    assert half['export_preview']['export_profile']==HALF and half['export_preview']['sources']==full['export_preview']['sources']
    assert half['export_preview']['execution_recipe']['timeline']==before['timeline'] and not renders
    with pytest.raises(StaleSourceError,match='PREVIEW_CHANGED'):
        e.production.timeline_playback_build(e.nid,e.scope,e.actor,before['id'],{**half_input,'reviewed_playback_digest':full['playback_digest']},lambda:None)
    build={**half_input,'reviewed_playback_digest':half['playback_digest']}
    built=e.production.timeline_playback_build(e.nid,e.scope,e.actor,before['id'],build,lambda:None)
    job=built['job'];assert job['status']=='SUCCEEDED' and len(renders)==1
    assert (job['media_measurement']['width'],job['media_measurement']['height'])==(48,32)
    fresh=production(e,reopened(e))
    cached=fresh.timeline_playback_preview(e.nid,e.scope,e.actor,before['id'],half_input,lambda:None)
    again=fresh.timeline_playback_build(e.nid,e.scope,e.actor,before['id'],build,lambda:None)
    assert cached['cache_key']==half['cache_key'] and cached['playback_digest']==half['playback_digest'] and cached['cache_state']=='RECORDED'
    assert cached['job']['id']==again['job']['id']==job['id'] and len(renders)==1
    attestation_input={**build,'expected_job_version':again['job']['version'],'expected_request_digest':again['job']['request_digest']}
    proof=fresh.timeline_playback_attest(e.nid,e.scope,e.actor,before['id'],attestation_input,lambda:None)
    meta,data=fresh.candidate(e.nid,e.scope,e.actor,'timeline',job['id'],lambda:None)
    assert proof['sha256']==hashlib.sha256(data).hexdigest()==meta['sha256'] and proof['byte_count']==len(data)
    assert proof['cache_key']==half['cache_key'] and proof['product_acceptance']=='LOCAL_REQUIRED'
    path=tmp_path/'actual-playback-half.mp4';path.write_bytes(data);probe=probe_media_file(path,guard=lambda:None)
    video=next(stream for stream in probe['streams']if stream['codec_type']=='video')
    assert (video['width'],video['height'],int(video['nb_frames']),video['avg_frame_rate'])==(48,32,10,'10/1')
    assert abs(float(probe['format']['duration'])-1)<.1
    with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,job['output_candidate']['id'])
    assert e.service.list_assets(e.nid,e.scope)['items']==[e.source]
    assert fresh.timeline_get(e.nid,e.scope,e.actor,before['id'],lambda:None)==before
    # The original full-resolution cache remains independent and has no render yet.
    full_after=fresh.timeline_playback_preview(e.nid,e.scope,e.actor,before['id'],reviewed(e),lambda:None)
    assert full_after==full and len(renders)==1
    # Exact encoder bytes, source pins and Timeline version participate in the original cache plan.
    from app.creative import timeline_playback as owner
    engines=owner._engines();changed=deepcopy(engines);changed[0]['sha256']='0'*64
    monkeypatch.setattr(owner,'_engines',lambda:changed)
    engine_change=fresh.timeline_playback_preview(e.nid,e.scope,e.actor,before['id'],half_input,lambda:None)
    assert engine_change['cache_key']!=half['cache_key']
    monkeypatch.setattr(owner,'_engines',lambda:engines)
    changed_row=fresh.timeline_save(e.nid,e.scope,e.actor,before['id'],{'title':before['title']+' version 2','expected_version':before['version'],'timeline':before['timeline']},lambda:None)
    with pytest.raises(StaleSourceError,match='TIMELINE_CHANGED'):
        fresh.timeline_playback_attest(e.nid,e.scope,e.actor,before['id'],attestation_input,lambda:None)
    versioned=fresh.timeline_playback_preview(e.nid,e.scope,e.actor,before['id'],{'expected_version':changed_row['version'],'reviewed_timeline_digest':changed_row['timeline_digest'],'preview_resolution':'HALF'},lambda:None)
    assert versioned['cache_key']!=half['cache_key'] and versioned['cache_state']=='MISSING'
    with e.service._asset_scope(e.nid,e.scope):e.assets.update_metadata(e.source['id'],{'scene_id':'changed pin'},expected_version=e.source['version'])
    with pytest.raises(StaleSourceError):
        fresh.timeline_playback_preview(e.nid,e.scope,e.actor,before['id'],{'expected_version':changed_row['version'],'reviewed_timeline_digest':changed_row['timeline_digest'],'preview_resolution':'HALF'},lambda:None)
    assert len(renders)==1
    record={'scope':'real File TimelinePlayback preview/build/cache/reopen/candidate/attestation; CPU FFmpeg only',
        'row':before,'source':e.source,'half_preview':half['export_preview'],'normal_preview':full['export_preview'],
        'half_playback_preview':half,'normal_playback_preview':full,'half_playback_built':built,'half_playback_reopened':again,
        'half_attestation':proof,'probe':probe,'render_calls':len(renders),'default_exact_parent':'d9b2ea4b602af099f133e7ef7e954fb7618979ae',
        'engine_key_changed':True,'version_key_changed':True,'stale_source_rejected':True,'private_candidate':True,'timeline_unchanged_before_deliberate_version_test':True}
    (tmp_path/'playback-proof.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
