"""Additive sample-peak admission and immutable pre-edit serializer evidence.

Pure helper tests use fixed synthetic PCM, not an executed job/native claim.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import wave
import pytest
from app.creative.graph_models import MediaNodeParameters
from app.creative.production_execution import ProductionExecutionService, digest
from app.creative.production_execution_models import MediaCommand, MediaParameters
from app.experimental.store import canonical
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_execution import _body, _binding, _digest, _peak_pcm, _peak_proof, _trim_filters, StudioAudioExecution
from test_v2_audio_fade_contract import captured
from test_v2_audio_wav_controls import command

FIXTURE = Path(__file__).with_name('fixtures') / 'studio_audio_peak_omission_v1.json'

@pytest.mark.parametrize('name', ['wav_omitted','wav_controls','flac','mp3','graph_trim','fades_zero','fades_positive'])
def test_frozen_pre_edit_actual_original_serializer_identity(name):
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'd818680bf5895014cd400671d5ed95d3ca61a8886cec4e58c2f8dfcc0c4dcc16'
    frozen = json.loads(raw)
    assert frozen['source_commit'] == 'e1e66cedeb7a140b6894850bc21a1e5ac7e06c16'
    old = frozen['variants'][name]
    preview, context, parsed, body = captured(old['input'], old['graph_binding'])
    receipt = deepcopy(old['objects']['receipt']); receipt.pop('receipt_digest')
    StudioAudioExecution._receipt(receipt)
    objects = dict(command=parsed.model_dump(), preview=preview, context=context, recipe=preview['execution_recipe'], body=body, receipt=receipt)
    assert objects == old['objects']
    assert {key:canonical(value) for key,value in objects.items()} == old['canonical']
    assert {key:digest(value) for key,value in objects.items()} == old['sha256']
    assert parsed.model_dump_json() == old['model_dump_json']
    assert _digest({'body':body,'context':context}) == old['request_sha256']
    assert 'target_peak_dbfs' not in parsed.model_dump()['parameters']

@pytest.mark.parametrize('value', [None, True, False, '-6', 0, -25, -0.99, float('nan'), float('inf')])
def test_strict_target_in_both_original_owners(value):
    raw = command(target_peak_dbfs=value)
    with pytest.raises(ValueError): MediaCommand.model_validate(raw)
    with pytest.raises(AudiobookError): _body({k:v for k,v in raw.items() if k not in {'request_id','allow_cloud','license_note'}})

@pytest.mark.parametrize('options', [{'target_peak_dbfs': -6}, {'target_peak_dbfs': -6.5}, {'target_peak_dbfs': -24, 'gain_db': -60}, {'target_peak_dbfs': -1}])
def test_target_explicitly_bound_at_every_original_layer(options):
    preview, context, parsed, body = captured(command(**options))
    assert _binding(context, body) == context
    assert parsed.model_dump()['parameters']['target_peak_dbfs'] == options['target_peak_dbfs']
    assert preview['execution_recipe']['parameters']['target_peak_dbfs'] == options['target_peak_dbfs']
    assert preview['request_digest'] != captured(command())[0]['request_digest']

@pytest.mark.parametrize('options', [{'output_format':'FLAC'}, {'output_format':'MP3'}, {'gain_db': 6}])
def test_unsupported_format_and_insufficient_headroom_rejected(options):
    raw = command(target_peak_dbfs=-6, **options)
    with pytest.raises(ValueError): MediaCommand.model_validate(raw)
    with pytest.raises(AudiobookError): _body({k:v for k,v in raw.items() if k not in {'request_id','allow_cloud','license_note'}})


def test_graph_and_other_operations_stay_closed():
    with pytest.raises(ValueError): MediaParameters.model_validate({'target_peak_dbfs':-6})
    with pytest.raises(ValueError): MediaNodeParameters.model_validate({'operation_id':'m8.audio.trim','parameters':{'in_ms':0,'out_ms':10,'target_peak_dbfs':-6}})
    with pytest.raises(ValueError): MediaCommand.model_validate({**command(target_peak_dbfs=-6),'operation_id':'m8.audio.music'})
    with pytest.raises(ValueError, match='STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY'):
        object.__new__(ProductionExecutionService).preview('project',{},'author',command(target_peak_dbfs=-6),lambda:None,graph_binding={})

@pytest.mark.parametrize('layer', ['body','command','recipe'])
@pytest.mark.parametrize('value', [-6, None])
def test_rehashed_cross_layer_injection_rejected(layer,value):
    _, context, _, body = captured(command())
    target = body if layer == 'body' else context['command'] if layer == 'command' else context['execution_recipe']
    target['parameters']['target_peak_dbfs'] = value
    recipe = context['execution_recipe']; recipe['recipe_digest'] = digest({k:v for k,v in recipe.items() if k != 'recipe_digest'})
    context['request_digest'] = digest({'context':{k:v for k,v in context.items() if k not in {'command','request_digest'}},'command':context['command']})
    with pytest.raises((AudiobookError,ValueError)): _binding(context,_body(body))

@pytest.mark.parametrize('missing',['command','execution_recipe'])
def test_normalization_requires_captured_layers(missing):
    _, context, _, body = captured(command(target_peak_dbfs=-6))
    context.pop(missing)
    with pytest.raises(AudiobookError,match='峰值'): _binding(context,body)


def pcm(samples, rate=16000, channels=1):
    result=io.BytesIO()
    with wave.open(result,'wb') as writer:
        writer.setnchannels(channels); writer.setsampwidth(2); writer.setframerate(rate)
        writer.writeframes(struct.pack('<'+'h'*len(samples),*samples))
    return result.getvalue()


def test_selected_pcm_uses_shared_stereo_peak_and_signed_full_scale():
    # Loudest discarded samples cannot affect selected frames or selected hash.
    data=pcm([32767,-32768]*16 + [2000,-4000]*16 + [32767,-32768]*16,channels=2)
    params={'in_ms':1,'out_ms':2,'sample_rate':16000,'channels':2}
    actual=_peak_pcm(data,params,lambda:None,selected=True)
    assert actual == {'peak_s16':4000,'frames':16,'first_frame':16,'pcm_sha256':hashlib.sha256(struct.pack('<hh',2000,-4000)*16).hexdigest()}
    assert _peak_pcm(data,{**params,'in_ms':0,'out_ms':1},lambda:None,selected=True)['peak_s16'] == 32768

@pytest.mark.parametrize('parameters', [{'in_ms':1,'out_ms':20,'sample_rate':44100,'channels':1}, {'in_ms':0,'out_ms':10,'sample_rate':16000,'channels':2}])
def test_fractional_frames_or_profile_conversion_fail_closed(parameters):
    with pytest.raises(AudiobookError): _peak_pcm(pcm([1000]*1000,rate=44100),parameters,lambda:None,selected=True)


def test_scan_observes_guard_between_chunks():
    calls=[]
    def guard():
        calls.append(1)
        if len(calls)==3: raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError,match='cancelled'):
        _peak_pcm(pcm([1000]*32000),{'in_ms':0,'out_ms':2000,'sample_rate':16000,'channels':1},guard,selected=True)


def test_combined_double_gain_then_original_fades_and_legacy_argv():
    p={'in_ms':100,'out_ms':800,'gain_db':-6,'fade_in_ms':200,'fade_out_ms':300}
    assert _trim_filters(p)==['-af','volume=-6dB,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.200:curve=tri,afade=t=out:st=0.400:d=0.300:curve=tri']
    assert _trim_filters(p,normalization_gain_db=8)[1].startswith('volume=2dB:precision=double,asetpts=PTS-STARTPTS,afade=')


def proof():
    return {'contract':'studio-audio-sample-peak/1','source_sha256':'b'*64,'selected_pcm_sha256':'c'*64,'selected_frames':11200,
        'source_peak_s16':8000,'target_peak_dbfs':-6,'normalization_gain_db':-6-20*math.log10(8000/32768),'manual_gain_db':0,
        'output_peak_s16':round(32768*10**(-6/20)),'output_frames':11200,'output_pcm_sha256':'d'*64}

@pytest.mark.parametrize('key,value',[('source_peak_s16',0),('source_peak_s16',True),('normalization_gain_db',float('nan')),('normalization_gain_db',0),('output_peak_s16',32767),('output_frames',11201),('selected_frames',0),('target_peak_dbfs',-7),('manual_gain_db',1),('selected_pcm_sha256','bad')])
def test_strict_proof_rejects_invalid_fields(key,value):
    p=proof(); p[key]=value
    with pytest.raises(AudiobookError): _peak_proof(p,{'in_ms':100,'out_ms':800,'target_peak_dbfs':-6},16000)
