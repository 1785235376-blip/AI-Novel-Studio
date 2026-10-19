"""Strict standalone LUFS admission; omitted controls retain old identities."""
from copy import deepcopy
import pytest
from app.creative.graph_models import MediaNodeParameters
from app.creative.production_execution import ProductionExecutionService, digest
from app.creative.production_execution_models import MediaCommand, MediaParameters
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_execution import _body, _binding
from test_v2_audio_fade_contract import captured
from test_v2_audio_wav_controls import command


def value(**options):return command(in_ms=500,out_ms=4500,target_lufs=-23.5,**options)
def body(raw):return {k:v for k,v in raw.items() if k not in {'request_id','allow_cloud','license_note'}}


@pytest.mark.parametrize('target',[None,True,False,'-23',-30.1,-13.9,float('nan'),float('inf')])
def test_strict_target_in_model_and_original_owner(target):
    raw=value();raw['parameters']['target_lufs']=target
    with pytest.raises(ValueError):MediaCommand.model_validate(raw)
    with pytest.raises(AudiobookError):_body(body(raw))


@pytest.mark.parametrize('options',[{'output_format':'FLAC'},{'output_format':'MP3'},{'target_peak_dbfs':-6},{'gain_db':1},{'fade_in_ms':1},{'fade_out_ms':1},{'out_ms':3499}])
def test_mutually_exclusive_or_short_processing_rejected(options):
    raw=value();raw['parameters'].update(options)
    with pytest.raises(ValueError):MediaCommand.model_validate(raw)
    with pytest.raises(AudiobookError):_body(body(raw))


def test_explicit_boundaries_and_zero_other_controls_bound_at_all_layers():
    for target in [-30,-23.5,-14]:
        raw=value(gain_db=0,fade_in_ms=0,fade_out_ms=0);raw['parameters']['target_lufs']=target
        preview,context,parsed,shaped=captured(raw)
        assert _binding(context,shaped)==context
        assert parsed.parameters.target_lufs==target and preview['execution_recipe']['parameters']['target_lufs']==target
        assert preview['request_digest']!=captured(command())[0]['request_digest']


def test_graph_and_other_operations_remain_closed():
    with pytest.raises(ValueError):MediaParameters.model_validate({'target_lufs':-23})
    with pytest.raises(ValueError):MediaNodeParameters.model_validate({'operation_id':'m8.audio.trim','parameters':{'in_ms':0,'out_ms':4000,'target_lufs':-23}})
    with pytest.raises(ValueError):MediaCommand.model_validate({**value(),'operation_id':'m8.audio.music'})
    with pytest.raises(ValueError,match='STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY'):
        object.__new__(ProductionExecutionService).preview('project',{},'author',value(),lambda:None,graph_binding={})


@pytest.mark.parametrize('layer',['body','command','recipe'])
@pytest.mark.parametrize('target',[-23,None])
def test_rehashed_cross_layer_injection_is_rejected(layer,target):
    _,context,_,shaped=captured(command(in_ms=0,out_ms=4000))
    captured_layer=shaped if layer=='body' else context['command'] if layer=='command' else context['execution_recipe']
    captured_layer['parameters']['target_lufs']=target
    recipe=context['execution_recipe'];recipe['recipe_digest']=digest({k:v for k,v in recipe.items() if k!='recipe_digest'})
    context['request_digest']=digest({'context':{k:v for k,v in context.items() if k not in {'command','request_digest'}},'command':context['command']})
    with pytest.raises((AudiobookError,ValueError)):_binding(context,_body(shaped))


@pytest.mark.parametrize('missing',['command','execution_recipe'])
def test_requires_captured_command_and_recipe(missing):
    _,context,_,shaped=captured(value());context.pop(missing)
    with pytest.raises(AudiobookError):_binding(context,shaped)
