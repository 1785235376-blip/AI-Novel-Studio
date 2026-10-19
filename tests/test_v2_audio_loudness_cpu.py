"""Real CPU synthetic WAV -> original audio job -> private candidate -> review.

Fixed before execution: <=0.2 LU target error, <=-1 dBTP, exact profile/frames,
source interval and byte hashes, <=1 S16 LSB fixed-gain error. No model/API.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import wave
import pytest
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_execution import StudioAudioExecution
from test_v2_independent_workspace import rig, reopened, import_asset
from test_v2_audio_wav_controls import production, command, snapshot, queue, run, get, review, action
from test_v2_audio_peak_contract import pcm


def setup(e, rate=16000, channels=1, amplitude=2000, target=-23, spike=False, dc=False):
    assert shutil.which('ffmpeg'), 'original CPU FFmpeg required; no install or fallback'
    e.service.activate(e.nid,e.scope,e.actor)
    selected=[]
    for i in range(rate*4):
        a=amplitude if dc else round(amplitude*math.sin(2*math.pi*1000*i/rate))
        if spike and i==rate*2: a=28000
        selected.extend([a] if channels==1 else [a,round(a/2)])
    # Discarded clipped boundaries prove that only the requested interval is metered.
    e.original_bytes=pcm([32767]*channels*(rate//2)+selected+[-32768]*channels*(rate//2),rate,channels)
    e.selected_bytes=struct.pack('<'+'h'*len(selected),*selected)
    e.source=import_asset(e,data=e.original_bytes,filename='loudness-source.wav',kind='audio')
    e.production=production(e)
    e.command=command(snapshot(e.source),in_ms=500,out_ms=4500,sample_rate=rate,channels=channels,target_lufs=target)
    return e


def checked_candidate(e,result):
    meta,data=e.production.candidate(e.nid,e.scope,e.actor,'audio',result['id'],lambda:None)
    with wave.open(io.BytesIO(data),'rb') as reader:
        assert reader.getframerate()==e.command['parameters']['sample_rate']
        assert reader.getnchannels()==e.command['parameters']['channels'] and reader.getsampwidth()==2
        frames=reader.getnframes(); raw=reader.readframes(frames)
    proof=result['media_measurement']['loudness_matching']
    assert hashlib.sha256(data).hexdigest()==meta['sha256']==proof['output_sha256']==result['media_measurement']['output_sha256']
    assert hashlib.sha256(raw).hexdigest()==proof['output_pcm_sha256']
    assert hashlib.sha256(e.selected_bytes).hexdigest()==proof['selected_pcm_sha256']
    assert frames==proof['output_frames']==proof['selected_frames']==e.command['parameters']['sample_rate']*4
    assert proof['source_sha256']==e.source['sha256'] and proof['source_version']==e.source['version'] and proof['source_id']==e.source['id']
    assert (proof['in_ms'],proof['out_ms'])==(500,4500)
    assert abs(proof['output_lufs']-proof['target_lufs'])<=0.2 and proof['output_true_peak_dbtp']<=-1
    assert -60<=proof['applied_gain_db']<=12
    factor=10**(proof['applied_gain_db']/20)
    pairs=zip(struct.iter_unpack('<h',e.selected_bytes),struct.iter_unpack('<h',raw))
    assert max(abs(actual[0]-expected[0]*factor) for expected,actual in pairs)<=1
    assert max(abs(x[0]) for x in struct.iter_unpack('<h',raw))==proof['output_peak_s16']<32767
    evidence=os.environ.get('LOUDNESS_EVIDENCE_DIR')
    if evidence:
        folder=Path(evidence);folder.mkdir(parents=True,exist_ok=True)
        name=f"native-{proof['sample_rate']}-{proof['channels']}-{proof['target_lufs']}"
        (folder/(name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        (folder/(name+'.wav')).write_bytes(data)
        (folder/(name+'-source.wav')).write_bytes(e.original_bytes)
    return proof


@pytest.mark.parametrize('rate,channels,target',[(16000,1,-23),(44100,2,-23.5),(48000,2,-30)])
def test_real_cpu_match_candidate_explicit_review_and_reopen(rig,rate,channels,target):
    e=setup(rig,rate,channels,target=target)
    result=run(e,queue(e)); assert result['status']=='AWAITING_REVIEW',result
    proof=checked_candidate(e,result)
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==1
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid,e.scope,result['output_candidate']['id'])
    assert e.service.download(e.nid,e.scope,e.source['id'])[1]==e.original_bytes
    e.production=production(e,reopened(e)); assert get(e,result)==result
    approved=review(e,result); assert approved['status']=='APPROVED' and approved['media_measurement']['loudness_matching']==proof
    e.production=production(e,reopened(e)); assert get(e,result)==approved
    assert len(e.production.workspace.list_assets(e.nid,e.scope)['items'])==2


@pytest.mark.parametrize('options,code',[
    ({'amplitude':0},'SILENCE'),({'amplitude':40},'GAIN_OUT_OF_RANGE'),
    ({'spike':True},'TRUE_PEAK_HEADROOM_REQUIRED'),({'dc':True},'GAIN_OUT_OF_RANGE'),
    ({'amplitude':1},'NONFINITE_MEASUREMENT'),
    ({'amplitude':32767,'dc':True},'CLIPPING_RISK')])
def test_real_unsafe_or_unmeasurable_source_rejected_without_candidate(rig,options,code):
    e=setup(rig,**options); result=run(e,queue(e))
    assert result['status']=='FAILED',result
    assert result['error_code']=='STUDIO_AUDIO_LOUDNESS_'+code,result
    assert result['output_candidate'] is None and result['media_measurement'] is None
    assert len(list(e.assets.root.glob('*.bin')))==1


@pytest.mark.parametrize('change',[{'sample_rate':22050},{'channels':2},{'in_ms':501}])
def test_profile_conversion_and_fractional_frames_are_rejected(rig,change):
    e=setup(rig,rate=44100);e.command['parameters'].update(change)
    result=run(e,queue(e));assert result['status']=='FAILED' and result['output_candidate'] is None,result
    assert result['error_code'] in {'STUDIO_AUDIO_LOUDNESS_SAME_PCM16_PROFILE_REQUIRED','STUDIO_AUDIO_LOUDNESS_FRAME_ALIGNMENT_REQUIRED'}


def test_missing_meter_capability_fails_closed_without_fallback(rig,monkeypatch):
    e=setup(rig)
    import app.services.studio_timeline_export as native
    def absent(*args,**kwargs): raise subprocess.CalledProcessError(1,args[0])
    monkeypatch.setattr(native,'run_guarded_process',absent)
    result=run(e,queue(e));assert result['status']=='FAILED' and result['error_code']=='STUDIO_AUDIO_LOUDNESS_METER_UNAVAILABLE',result
    assert result['output_candidate'] is None and len(list(e.assets.root.glob('*.bin')))==1


@pytest.mark.parametrize('mutation',['missing','version','source','interval','output_hash','frames','gain','peak','nan','target'])
def test_rehashed_corrupt_proof_rejected_on_get_review_reconcile_and_reopen(rig,mutation):
    e=setup(rig);result=run(e,queue(e));assert result['status']=='AWAITING_REVIEW',result
    owner=e.production._audio(e.scope,e.actor);state=owner.store.load(e.nid,include_studio=True);row=state['jobs'][0]
    proof=row['measured']['loudness_matching']
    if mutation=='missing':row['measured'].pop('loudness_matching')
    elif mutation=='version':proof['source_version']+=1
    elif mutation=='source':proof['source_sha256']='a'*64
    elif mutation=='interval':proof['in_ms']+=1
    elif mutation=='output_hash':proof['output_sha256']='a'*64
    elif mutation=='frames':proof['output_frames']+=1
    elif mutation=='gain':proof['applied_gain_db']=0
    elif mutation=='peak':proof['output_true_peak_dbtp']=0
    elif mutation=='target':proof['output_lufs']+=1
    else:proof['input_lufs']='NaN'
    StudioAudioExecution._receipt(row);owner.store.save(e.nid,state,include_studio=True)
    for op in [lambda:get(e,result),lambda:review(e,result),lambda:e.production.reconcile(e.nid,e.scope,e.actor,'audio',result['id'],action(result),lambda:None)]:
        with pytest.raises(AudiobookError):op()
    e.production=production(e,reopened(e))
    with pytest.raises(AudiobookError):get(e,result)


def test_unknown_publication_recovery_does_not_remeasure_or_encode(rig,monkeypatch):
    e=setup(rig);create=e.assets.create
    def lost(*args,**kwargs):create(*args,**kwargs);raise OSError('lost publication reply')
    monkeypatch.setattr(e.assets,'create',lost)
    result=run(e,queue(e));assert result['status']=='UNKNOWN' and result['media_measurement']['loudness_matching'],result
    monkeypatch.setattr(e.assets,'create',create)
    import app.services.studio_timeline_export as native
    monkeypatch.setattr(native,'run_guarded_process',lambda *a,**k:pytest.fail('recovery cannot remeasure or rerender'))
    recovered=e.production.reconcile(e.nid,e.scope,e.actor,'audio',result['id'],action(result),lambda:None)
    assert recovered['status']=='AWAITING_REVIEW' and recovered['media_measurement']==result['media_measurement']
    assert review(e,recovered)['status']=='APPROVED'


@pytest.mark.parametrize('stage',['scan','input','render','output'])
def test_cancel_each_real_processing_stage_discards_candidate(rig,monkeypatch,stage):
    e=setup(rig);queued=queue(e)
    def cancel():
        current=get(e,queued);e.production.cancel(e.nid,e.scope,e.actor,'audio',queued['id'],action(current),lambda:None)
    if stage=='scan':
        import app.services.studio_audio_loudness as helper
        original=helper.pcm
        def wrapped(*a,**k):cancel();return original(*a,**k)
        monkeypatch.setattr(helper,'pcm',wrapped)
    else:
        import app.services.studio_timeline_export as native
        original=native.run_guarded_process;calls=[]
        def wrapped(*a,**k):
            result=original(*a,**k);calls.append(1)
            if len(calls)=={'input':1,'render':2,'output':3}[stage]:cancel()
            return result
        monkeypatch.setattr(native,'run_guarded_process',wrapped)
    result=run(e,queued)
    assert result['status']=='CANCELLED' and result['output_candidate'] is None and result['media_measurement'] is None,result
    assert len(list(e.assets.root.glob('*.bin')))==1


def test_source_version_change_after_real_render_blocks_publication(rig,monkeypatch):
    e=setup(rig);queued=queue(e)
    import app.services.studio_timeline_export as native
    original=native.run_guarded_process;calls=[]
    def changed(*a,**k):
        result=original(*a,**k);calls.append(1)
        if len(calls)==2:
            with e.service._asset_scope(e.nid,e.scope):e.assets.update_metadata(e.source['id'],{'scene_id':'changed'},expected_version=e.source['version'])
        return result
    monkeypatch.setattr(native,'run_guarded_process',changed)
    result=run(e,queued)
    assert result['status']=='FAILED' and result['output_candidate'] is None and result['media_measurement'] is None,result
    assert len(list(e.assets.root.glob('*.bin')))==1
