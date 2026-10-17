"""Additive strict standalone fades and frozen pre-edit identity contracts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from app.creative.graph_models import MediaNodeParameters
from app.creative.production_execution import ProductionExecutionService, digest
from app.creative.production_execution_models import MediaCommand, MediaParameters
from app.experimental.store import canonical
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_execution import _body, _binding, _digest, _trim_filters, StudioAudioExecution
from test_v2_audio_wav_controls import command, legacy_preview_service

FIXTURE = Path(__file__).with_name('fixtures') / 'studio_audio_fade_omission_v1.json'


def captured(value, graph=None):
    preview, context, parsed = legacy_preview_service().preview('project', {}, 'author', value, lambda: None, graph_binding=graph)
    context['command'] = parsed.model_dump()
    payload = parsed.model_dump(exclude={'source_snapshots', 'allow_cloud', 'license_note', 'request_id'})
    payload['parameters'] = parsed.parameters.model_dump(exclude_none=True)
    payload['source_snapshots'] = context['sources']
    return preview, context, parsed, _body(payload)


@pytest.mark.parametrize('name', ['wav_omitted', 'wav_controls', 'flac', 'mp3', 'graph_trim'])
def test_frozen_pre_edit_canonical_bytes_and_all_original_hashes(name):
    data = FIXTURE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == '1aa9100e0d3622b6d5a99019b5a7f33aa60e94173a9c962dce0a500c3a63c2d5'
    fixture = json.loads(data)
    assert fixture['source_commit'] == 'fb372d85f67dd32620ee20221e1aaa2b1e65bfba'
    old = fixture['variants'][name]
    preview, context, parsed, body = captured(old['input'], old['graph_binding'])
    assert _binding(context, body) == context
    receipt = deepcopy(old['objects']['receipt']); receipt.pop('receipt_digest')
    StudioAudioExecution._receipt(receipt)
    objects = {'command': parsed.model_dump(), 'preview': preview, 'context': context, 'recipe': preview['execution_recipe'], 'body': body, 'receipt': receipt}
    assert objects == old['objects']
    assert {k: canonical(v) for k,v in objects.items()} == old['canonical']
    assert {k: digest(v) for k,v in objects.items()} == old['sha256']
    assert parsed.model_dump_json() == old['model_dump_json']
    assert _digest({'body': body, 'context': context}) == old['request_sha256']
    assert not {'fade_in_ms', 'fade_out_ms'}.intersection(parsed.model_dump()['parameters'])


@pytest.mark.parametrize('key', ['fade_in_ms', 'fade_out_ms'])
@pytest.mark.parametrize('invalid', [None, True, False, '0', 'afade=1', 0.0, 1.5, -1, 120001, float('nan'), float('inf')])
def test_fades_strict_in_both_original_owners(key, invalid):
    value = command(**{key: invalid})
    with pytest.raises(ValueError): MediaCommand.model_validate(value)
    payload = {k:v for k,v in value.items() if k not in {'request_id', 'allow_cloud', 'license_note'}}
    with pytest.raises(AudiobookError): _body(payload)


@pytest.mark.parametrize('parameters', [{'fade_in_ms': 701}, {'fade_out_ms': 701}, {'fade_in_ms': 400, 'fade_out_ms': 301}])
def test_fades_reject_overlap_not_clamp(parameters):
    value = command(**parameters)
    with pytest.raises(ValueError, match='STUDIO_AUDIO_FADE_RANGE_INVALID'): MediaCommand.model_validate(value)
    with pytest.raises(AudiobookError) as failure:
        _body({k:v for k,v in value.items() if k not in {'request_id', 'allow_cloud', 'license_note'}})
    assert failure.value.code == 'STUDIO_AUDIO_FADE_RANGE_INVALID'


@pytest.mark.parametrize('parameters', [{'fade_in_ms': 0}, {'fade_out_ms': 0}, {'fade_in_ms': 200}, {'fade_out_ms': 700}, {'fade_in_ms': 400, 'fade_out_ms': 300}, {'fade_in_ms': 0, 'fade_out_ms': 0}])
def test_explicit_fades_are_bound_without_inventing_omitted_partner(parameters):
    old = captured(command())
    preview, context, parsed, body = captured(command(**parameters))
    assert _binding(context, body) == context
    for layer in (parsed.model_dump()['parameters'], body['parameters'], preview['execution_recipe']['parameters']):
        assert {k:v for k,v in layer.items() if k.startswith('fade_')} == parameters
    assert preview['request_digest'] != old[0]['request_digest']
    assert preview['preview_digest'] != old[0]['preview_digest']
    assert preview['execution_recipe']['recipe_digest'] != old[0]['execution_recipe']['recipe_digest']
    assert _digest({'body': body, 'context': context}) != _digest({'body': old[3], 'context': old[1]})


@pytest.mark.parametrize('key', ['fade_in_ms', 'fade_out_ms'])
def test_graph_and_other_operations_stay_closed(key):
    with pytest.raises(ValueError): MediaParameters.model_validate({key: 0})
    with pytest.raises(ValueError): MediaNodeParameters.model_validate({'operation_id': 'm8.audio.trim', 'parameters': {'in_ms': 0, 'out_ms': 10, key: 0}})
    with pytest.raises(ValueError, match='STUDIO_OPERATION_PARAMETER_UNSUPPORTED'):
        MediaCommand.model_validate({**command(**{key: 0}), 'operation_id': 'm8.audio.music'})
    with pytest.raises(ValueError, match='STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY'):
        object.__new__(ProductionExecutionService).preview('project', {}, 'author', command(**{key: 0}), lambda: None, graph_binding={})
    old = json.loads(FIXTURE.read_bytes())['variants']['graph_trim']
    body, context = deepcopy(old['objects']['body']), deepcopy(old['objects']['context'])
    body['parameters'][key] = 0
    with pytest.raises(AudiobookError) as failure: _binding(context, body)
    assert failure.value.code == 'STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY'


@pytest.mark.parametrize('layer', ['body', 'command', 'recipe'])
@pytest.mark.parametrize('value', [0, 100, None])
def test_rehashed_cross_layer_fade_injection_cannot_admit(layer, value):
    _, context, _, body = captured(command())
    target = body if layer == 'body' else context['command'] if layer == 'command' else context['execution_recipe']
    target['parameters']['fade_in_ms'] = value
    recipe = context['execution_recipe']
    recipe['recipe_digest'] = digest({k:v for k,v in recipe.items() if k != 'recipe_digest'})
    context['request_digest'] = digest({'context': {k:v for k,v in context.items() if k not in {'command', 'request_digest'}}, 'command': context['command']})
    with pytest.raises((AudiobookError, ValueError)):
        _binding(context, _body(body))


@pytest.mark.parametrize('missing', ['command', 'execution_recipe'])
def test_fades_require_original_captured_layers(missing):
    _, context, _, body = captured(command(fade_in_ms=0))
    context.pop(missing)
    with pytest.raises(AudiobookError) as failure: _binding(context, body)
    assert failure.value.code == 'STUDIO_AUDIO_FADE_BINDING_REQUIRED'


def test_positive_linear_filter_order_and_exact_zero_argv():
    for gain in ({}, {'gain_db': -6.020599913279624}):
        p = {'in_ms': 200, 'out_ms': 1200, **gain}
        original = ['-af', f"volume={gain['gain_db']:.17g}dB"] if gain else []
        assert _trim_filters(p) == original
        assert _trim_filters({**p, 'fade_in_ms': 0, 'fade_out_ms': 0}) == original
    filters = _trim_filters({'in_ms': 200, 'out_ms': 1200, 'gain_db': -6, 'fade_in_ms': 200, 'fade_out_ms': 300})
    assert filters == ['-af', 'volume=-6dB,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.200:curve=tri,afade=t=out:st=0.700:d=0.300:curve=tri']
    assert _trim_filters({'in_ms': 200, 'out_ms': 1200, 'fade_out_ms': 1000}) == ['-af', 'asetpts=PTS-STARTPTS,afade=t=out:st=0.000:d=1.000:curve=tri']
