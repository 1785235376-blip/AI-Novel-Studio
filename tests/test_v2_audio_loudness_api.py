"""Mounted original authenticated route with real CPU loudness output."""
import hashlib
import json
import math
import os
from pathlib import Path
import pytest
from test_v2_audio_wav_controls_api import audio_client, client, preview, queue, run, action
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace import upload
from test_v2_audio_peak_contract import pcm
from test_v2_audio_wav_controls import command, snapshot


def source(e):
    rate=16000
    data=pcm([round(2000*math.sin(2*math.pi*1000*i/rate)) for i in range(rate*5)],rate)
    e.source=checked(e.client.post(e.studio_base+'/assets',headers=e.headers,json=upload(data,kind='audio',filename='real-loudness.wav')),201)
    e.command=command(snapshot(e.source),in_ms=500,out_ms=4500,target_lufs=-23.5,sample_rate=rate,channels=1)
    return e


def test_mounted_native_candidate_review_and_frontend_receipt(audio_client):
    e=source(audio_client);captured,queued=queue(e)
    assert queued['status']=='QUEUED' and queued['media_measurement'] is None
    executed=checked(run(e,queued));assert executed['status']=='AWAITING_REVIEW',executed
    proof=executed['media_measurement']['loudness_matching'];assert abs(proof['output_lufs']+23.5)<=0.2
    candidate=checked(e.client.get(e.base+'/jobs/audio/'+executed['id'],headers=e.headers))['output_candidate']
    assert e.client.get(e.studio_base+'/assets/'+candidate['id'],headers=e.headers).status_code==404
    data=e.client.get(e.base+'/jobs/audio/'+executed['id']+'/candidate',headers=e.headers)
    assert data.status_code==200 and hashlib.sha256(data.content).hexdigest()==proof['output_sha256']==data.headers['x-asset-sha256']
    approved=checked(e.client.post(e.base+'/jobs/audio/'+executed['id']+'/review',headers=e.headers,json={**action(executed),'reviewed_output_digest':candidate['digest']}))
    assert approved['status']=='APPROVED' and approved['media_measurement']==executed['media_measurement']
    assert checked(e.client.get(e.studio_base+'/assets/'+candidate['id'],headers=e.headers))['provenance']['origin']=='DERIVED_PROCESSING'
    assert data.headers['cache-control']=='no-store' and data.headers['x-content-type-options']=='nosniff'
    folder=os.environ.get('LOUDNESS_EVIDENCE_DIR')
    if folder:
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        (folder/'mounted-actual.json').write_text(json.dumps({'command':e.command,'source':e.source,'preview':captured,'queued':queued,'executed':executed,'approved':approved},indent=2),encoding='utf-8')
        (folder/'mounted-actual.wav').write_bytes(data.content)


@pytest.mark.parametrize('change',['missing','forged','origin','forwarded','feature','acceptance'])
def test_existing_host_boundary_blocks_loudness_preview(audio_client,monkeypatch,change):
    e=source(audio_client)
    if change=='missing':e.headers={}
    elif change=='forged':e.headers={'X-Session-Token':'forged'}
    elif change=='origin':e.headers={**e.headers,'Origin':'https://untrusted.invalid'}
    elif change=='forwarded':e.headers={**e.headers,'Forwarded':'for=127.0.0.1'}
    elif change=='feature':monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    else:monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert preview(e).status_code in {401,403,404}
    assert len(list(e.assets.root.glob('*.bin')))==2


@pytest.mark.parametrize('stage',[1,2,3])
@pytest.mark.parametrize('change',['revoke','aba'])
def test_real_measure_render_remeasure_observe_late_host_fence(audio_client,monkeypatch,stage,change):
    e=source(audio_client);_,queued=queue(e)
    import app.services.studio_timeline_export as native
    original=native.run_guarded_process;calls=[]
    def changed(*args,**kwargs):
        result=original(*args,**kwargs);calls.append(1)
        if len(calls)==stage:
            e.sessions.revoke(e.host)
            if change=='aba':e.sessions.register(e.host,e.session)
        return result
    monkeypatch.setattr(native,'run_guarded_process',changed)
    response=run(e,queued)
    assert response.status_code in {401,403,404},response.text
    assert len(list(e.assets.root.glob('*.bin')))==2
