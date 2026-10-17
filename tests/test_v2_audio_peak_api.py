"""Mounted strict sample-peak admission through existing audio route."""
import pytest
from test_v2_audio_wav_controls_api import audio_client, client, preview, queue
from test_r3_mounted_contracts import checked, mounted, prefix

@pytest.mark.parametrize('parameters',[{'target_peak_dbfs':None},{'target_peak_dbfs':True},{'target_peak_dbfs':'-6'},{'target_peak_dbfs':0},{'target_peak_dbfs':-25},{'target_peak_dbfs':-6,'gain_db':6},{'target_peak_dbfs':-6,'output_format':'FLAC'}])
def test_invalid_target_never_creates_job(audio_client,parameters):
    e=audio_client; e.command['parameters'].update(parameters)
    response=preview(e); assert response.status_code==422,response.text
    assert checked(e.client.get(e.base+'/jobs',headers=e.headers))['items']==[]
    assert len(list(e.assets.root.glob('*.bin')))==1


def test_target_change_invalidates_reviewed_identity_and_queue_is_idempotent(audio_client):
    e=audio_client; old=checked(preview(e))
    e.command['parameters'].update(target_peak_dbfs=-18,sample_rate=16000)
    current=checked(preview(e)); assert current['request_digest']!=old['request_digest']
    denied=e.client.post(e.base+'/jobs',headers=e.headers,json={'command':e.command,'reviewed_preview_digest':old['preview_digest']})
    assert denied.status_code==409
    payload={'command':e.command,'reviewed_preview_digest':current['preview_digest']}
    queued=checked(e.client.post(e.base+'/jobs',headers=e.headers,json=payload),201)
    assert checked(e.client.post(e.base+'/jobs',headers=e.headers,json=payload),201)==queued
    assert queued['status']=='QUEUED' and queued['media_measurement'] is None
    assert queued['command']['parameters']['target_peak_dbfs']==-18

@pytest.mark.parametrize('stage',['scan','native'])
@pytest.mark.parametrize('change',['revoke','aba'])
def test_normalized_scan_and_encoding_honor_late_host_fence(audio_client,monkeypatch,stage,change):
    from test_v2_audio_wav_controls_api import run
    e=audio_client; e.command['parameters'].update(target_peak_dbfs=-18,sample_rate=16000)
    _,queued=queue(e)
    if stage=='scan':
        import app.services.studio_audio_execution as module
        name='_peak_pcm'
    else:
        import app.services.studio_timeline_export as module
        name='run_guarded_process'
    original=getattr(module,name)
    def changed(*args,**kwargs):
        result=original(*args,**kwargs)
        e.sessions.revoke(e.host)
        if change=='aba': e.sessions.register(e.host,e.session)
        return result
    monkeypatch.setattr(module,name,changed)
    response=run(e,queued)
    assert response.status_code in {401,403,404},response.text
    assert len(list(e.assets.root.glob('*.bin')))==1
