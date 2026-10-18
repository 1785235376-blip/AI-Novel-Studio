"""Explicit read-only PCM16 source bounds; generic Save contract stays unchanged."""
import json,os,struct
from pathlib import Path
import pytest
from test_v2_independent_workspace import rig
from test_v2_timeline_waveform_preview import waveform,wav,durable_files,forbid_effects,request_body
from test_v2_timeline_waveform_preview_api import waveform_client,client,mounted,checked,prefix,scoped


def bounds(e,body=None,guard=lambda:None):
    return e.production.timeline_source_bounds(e.rig.nid,e.rig.scope,e.rig.actor,e.saved['id'],body or request_body(e.saved),guard)

@pytest.mark.parametrize('rig',[pytest.param('file',marks=pytest.mark.file_backend_only),pytest.param('postgres',marks=pytest.mark.postgres_backend_only)],indirect=True)
def test_saved_nine_second_span_reports_real_six_second_source_without_rewriting(waveform,monkeypatch):
    e=waveform([0]*48000,out_ms=9000);before=durable_files(e.rig.root);forbid_effects(monkeypatch,e.production)
    result=bounds(e)
    assert result['contract']=='studio-timeline-source-bounds/1' and result['scope']=='SOURCE_DURATION_ONLY'
    assert result['frame_count']==48000 and result['sample_rate']==8000 and result['maximum_out_ms']==6000
    assert result['requested_end_frame']==72000 and result['within_source'] is False
    assert 'peaks' not in result and 'samples_per_bucket' not in result
    assert durable_files(e.rig.root)==before and e.saved['timeline']['tracks'][0]['clips'][0]['out_ms']==9000
    Path(os.environ['NOVEL_DATA_PATH']).parent.joinpath('timeline-source-bounds-wire.json').write_text(json.dumps({'source':e.saved,'result':result},indent=2)+'\n')

@pytest.mark.parametrize('rig',[pytest.param('file',marks=pytest.mark.file_backend_only),pytest.param('postgres',marks=pytest.mark.postgres_backend_only)],indirect=True)
def test_valid_and_fractional_source_limits_use_sample_arithmetic(waveform):
    e=waveform([0]*801,rate=8000,out_ms=100);result=bounds(e)
    assert result['within_source'] is True and result['maximum_out_ms']==100
    assert result['duration_seconds']=={'num':801,'den':8000} and result['requested_end_frame']==800

@pytest.mark.parametrize('rig',[pytest.param('file',marks=pytest.mark.file_backend_only),pytest.param('postgres',marks=pytest.mark.postgres_backend_only)],indirect=True)
def test_truncated_pcm_still_fails_even_when_only_duration_requested(waveform):
    raw=bytearray(wav([0]*800));raw=raw[:-10];struct.pack_into('<I',raw,4,len(raw)-8)
    e=waveform(data=bytes(raw))
    with pytest.raises(ValueError,match='STUDIO_WAVEFORM_INVALID'):bounds(e)

@pytest.mark.parametrize('rig',[pytest.param('file',marks=pytest.mark.file_backend_only),pytest.param('postgres',marks=pytest.mark.postgres_backend_only)],indirect=True)
def test_stale_timeline_source_and_revoked_guard_disclose_no_measurement(waveform):
    e=waveform();body=request_body(e.saved);body['expected_version']+=1
    with pytest.raises(ValueError):bounds(e,body)
    body=request_body(e.saved);body['source_snapshot']['digest']='0'*64
    with pytest.raises(ValueError):bounds(e,body)
    with pytest.raises(PermissionError):bounds(e,guard=lambda:(_ for _ in ()).throw(PermissionError('revoked')))

@pytest.mark.file_backend_only
@pytest.mark.parametrize('mounted',['file'],indirect=True)
def test_original_mounted_bounds_route_keeps_no_store_and_host_authority(waveform_client):
    e=waveform_client;before=durable_files(e.root);path=e.path.replace('waveform-preview','source-bounds')
    response=e.client.post(path,headers=e.headers,json=e.body);result=checked(response)
    assert result['within_source'] is True and result['contract']=='studio-timeline-source-bounds/1'
    assert response.headers['cache-control']=='no-store' and durable_files(e.root)==before
    e.sessions.revoke(e.host);denied=e.client.post(path,headers=e.headers,json=e.body)
    assert denied.status_code in {401,403} and 'frame_count' not in denied.text
