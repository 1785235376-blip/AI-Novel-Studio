"""Real CPU sample-peak tests through original File owners, no provider/model.

Fixed acceptance: lossless sample-peak error <= 1 S16 LSB; exact selected/output
frame count and hashes; stereo ratio <= 1 LSB; fade envelope <= 2 LSB. These
thresholds are fixed before first native run and must not be tuned to outputs.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
import shutil
import struct
import wave
import pytest
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_execution import StudioAudioExecution
from test_v2_independent_workspace import rig, reopened, import_asset
from test_v2_audio_wav_controls import production, command, snapshot, preview, queue, run, get, review, action
from test_v2_audio_peak_contract import pcm


def setup(e, rate=16000, channels=1, amplitude=8000, target=-6, **options):
    assert shutil.which('ffmpeg'), 'original CPU FFmpeg required; no install or fallback'
    e.service.activate(e.nid,e.scope,e.actor)
    selected=[]
    for i in range(rate//2): selected.extend([amplitude] if channels==1 else [amplitude,-amplitude//2])
    raw=([32767]*channels*(rate//10) + selected + [-32768]*channels*(rate//10))
    e.original_bytes=pcm(raw,rate,channels)
    e.selected_bytes=struct.pack('<'+'h'*len(selected),*selected)
    e.source=import_asset(e,data=e.original_bytes,filename='bounded-peak-source.wav',kind='audio')
    e.production=production(e)
    e.command=command(snapshot(e.source),in_ms=100,out_ms=600,sample_rate=rate,channels=channels,target_peak_dbfs=target,**options)
    return e


def candidate(e,result):
    meta,data=e.production.candidate(e.nid,e.scope,e.actor,'audio',result['id'],lambda:None)
    with wave.open(io.BytesIO(data),'rb') as reader:
        frames=reader.getnframes(); channels=reader.getnchannels(); raw=reader.readframes(frames)
    values=[value[0] for value in struct.iter_unpack('<h',raw)]
    proof=result['media_measurement']['peak_normalization']
    assert hashlib.sha256(data).hexdigest()==meta['sha256']==result['media_measurement']['output_sha256']
    assert hashlib.sha256(raw).hexdigest()==proof['output_pcm_sha256']
    assert max(abs(v) for v in values)==proof['output_peak_s16']
    assert frames==proof['output_frames']==proof['selected_frames']
    assert hashlib.sha256(e.selected_bytes).hexdigest()==proof['selected_pcm_sha256']
    assert proof['source_sha256']==e.source['sha256']
    assert proof['source_peak_s16']==max(abs(v[0]) for v in struct.iter_unpack('<h',e.selected_bytes))
    return [values[channel::channels] for channel in range(channels)],proof

@pytest.mark.parametrize('rate,channels,amplitude,target,gain',[(16000,1,8000,-6,0),(44100,2,8000,-6.5,0),(16000,1,-32768,-6,0),(16000,2,20000,-12,-3),(16000,1,8000,-24,-60)])
def test_actual_exact_selected_peak_private_review_and_reopen(rig,tmp_path,rate,channels,amplitude,target,gain):
    e=setup(rig,rate,channels,amplitude,target,gain_db=gain)
    queued=queue(e); result=run(e,queued)
    assert result['status']=='AWAITING_REVIEW',result
    samples,proof=candidate(e,result)
    assert abs(proof['output_peak_s16']-32768*10**((target+gain)/20))<=1
    if channels==2:
        assert max(abs(b + a/2) for a,b in zip(*samples))<=1
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==1
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid,e.scope,result['output_candidate']['id'])
    assert e.service.download(e.nid,e.scope,e.source['id'])[1]==e.original_bytes
    e.production=production(e,reopened(e)); assert get(e,result)==result
    approved=review(e,result); assert approved['status']=='APPROVED'
    assert review(e,approved)==approved
    e.production=production(e,reopened(e)); assert get(e,result)==approved
    assert approved['media_measurement']==result['media_measurement']
    assert len(e.production.workspace.list_assets(e.nid,e.scope)['items'])==2
    (tmp_path/'peak-observation.json').write_text(json.dumps({'source':e.source['sha256'],'measurement':result['media_measurement']},indent=2))

@pytest.mark.parametrize('fade_in,fade_out',[(100,150),(250,250),(500,0),(0,500)])
def test_actual_manual_gain_then_original_linear_fades(rig,fade_in,fade_out):
    e=setup(rig,gain_db=-3,fade_in_ms=fade_in,fade_out_ms=fade_out)
    result=run(e,queue(e)); assert result['status']=='AWAITING_REVIEW',result
    samples,proof=candidate(e,result)
    level=32768*10**(-9/20)
    for i,value in enumerate(samples[0]):
        ms=i*1000/16000
        envelope=(min(1,ms/fade_in) if fade_in else 1)*(min(1,(500-ms)/fade_out) if fade_out else 1)
        assert abs(value-level*envelope)<=2
    assert proof['output_peak_s16']<=level+1

@pytest.mark.parametrize('amplitude,code',[(0,'STUDIO_AUDIO_PEAK_SILENCE'),(1,'STUDIO_AUDIO_PEAK_GAIN_OUT_OF_RANGE')])
def test_silence_or_unbounded_boost_has_no_candidate(rig,amplitude,code):
    e=setup(rig,amplitude=amplitude)
    result=run(e,queue(e)); assert result['status']=='FAILED',result
    assert result['error_code']==code and result['output_candidate'] is None and result['media_measurement'] is None
    assert len(list(e.assets.root.glob('*.bin')))==1

@pytest.mark.parametrize('change',[{'sample_rate':22050},{'channels':2},{'in_ms':101}])
def test_mismatch_or_fractional_frame_is_not_rounded_or_remixed(rig,change):
    e=setup(rig,rate=44100); e.command['parameters'].update(change)
    result=run(e,queue(e)); assert result['status']=='FAILED' and result['output_candidate'] is None
    assert result['error_code'] in {'STUDIO_AUDIO_PEAK_PCM_PROFILE_REQUIRED','STUDIO_AUDIO_PEAK_FRAME_ALIGNMENT_REQUIRED'}

@pytest.mark.parametrize('mutation',['missing','source','frames','peak','gain','nan'])
def test_corrupt_peak_proof_fails_get_review_reconcile_and_reopen(rig,mutation):
    e=setup(rig); result=run(e,queue(e)); assert result['status']=='AWAITING_REVIEW'
    owner=e.production._audio(e.scope,e.actor); state=owner.store.load(e.nid,include_studio=True); row=state['jobs'][0]
    proof=row['measured']['peak_normalization']
    if mutation=='missing': row['measured'].pop('peak_normalization')
    elif mutation=='source': proof['source_sha256']='a'*64
    elif mutation=='frames': proof['output_frames']+=1
    elif mutation=='peak': proof['output_peak_s16']=32767
    elif mutation=='gain': proof['normalization_gain_db']=0
    else: proof['normalization_gain_db']='NaN'  # JSON-safe malicious nonnumeric persisted value.
    StudioAudioExecution._receipt(row)  # Even recomputing outer receipt cannot legitimize invalid proof.
    owner.store.save(e.nid,state,include_studio=True)
    for operation in [lambda:get(e,result),lambda:review(e,result),lambda:e.production.reconcile(e.nid,e.scope,e.actor,'audio',result['id'],action(result),lambda:None)]:
        with pytest.raises(AudiobookError): operation()
    e.production=production(e,reopened(e))
    with pytest.raises(AudiobookError): get(e,result)


def test_unknown_publication_recovers_without_reencoding(rig,monkeypatch):
    e=setup(rig); queued=queue(e); create=e.assets.create
    def lost(*args,**kwargs): create(*args,**kwargs); raise OSError('lost response')
    monkeypatch.setattr(e.assets,'create',lost)
    result=run(e,queued); assert result['status']=='UNKNOWN' and result['media_measurement']['peak_normalization']
    monkeypatch.setattr(e.assets,'create',create)
    import app.services.studio_timeline_export as native
    monkeypatch.setattr(native,'run_guarded_process',lambda *a,**k:pytest.fail('reconcile cannot reencode'))
    recovered=e.production.reconcile(e.nid,e.scope,e.actor,'audio',result['id'],action(result),lambda:None)
    assert recovered['status']=='AWAITING_REVIEW' and recovered['media_measurement']==result['media_measurement']
    assert review(e,recovered)['status']=='APPROVED'

@pytest.mark.parametrize('stage',['scan','native'])
def test_cancel_during_scan_or_after_encoding_discards_result(rig,monkeypatch,stage):
    e=setup(rig); queued=queue(e)
    def cancel():
        current=get(e,queued)
        e.production.cancel(e.nid,e.scope,e.actor,'audio',queued['id'],action(current),lambda:None)
    if stage=='native':
        import app.services.studio_timeline_export as module
        original=module.run_guarded_process
        def wrapped(*args,**kwargs):
            result=original(*args,**kwargs); cancel(); return result
        monkeypatch.setattr(module,'run_guarded_process',wrapped)
    else:
        import app.services.studio_audio_execution as module
        original=module._peak_pcm
        def wrapped(*args,**kwargs): cancel(); return original(*args,**kwargs)
        monkeypatch.setattr(module,'_peak_pcm',wrapped)
    result=run(e,queued)
    assert result['status']=='CANCELLED' and result['output_candidate'] is None and result['media_measurement'] is None
    assert len(list(e.assets.root.glob('*.bin')))==1


def test_source_change_after_encoding_prevents_publication(rig,monkeypatch):
    e=setup(rig); queued=queue(e)
    import app.services.studio_timeline_export as native
    original=native.run_guarded_process
    def changed(*args,**kwargs):
        result=original(*args,**kwargs)
        with e.service._asset_scope(e.nid,e.scope):
            e.assets.update_metadata(e.source['id'],{'scene_id':'changed'},expected_version=e.source['version'])
        return result
    monkeypatch.setattr(native,'run_guarded_process',changed)
    result=run(e,queued)
    assert result['status']=='FAILED' and result['output_candidate'] is None and result['media_measurement'] is None
    assert len(list(e.assets.root.glob('*.bin')))==1
