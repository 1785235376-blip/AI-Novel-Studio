"""P2 regression: the original File queue must bind denoise declarations exactly."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from app.creative.production_execution import digest
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_denoise import PROFILE
from app.services.studio_audio_execution import _binding
from test_v2_audio_fade_contract import captured
from test_v2_audio_wav_controls import command, production, queue, snapshot, wav_bytes
from test_v2_independent_workspace import rig, import_asset


@pytest.mark.parametrize('mode', ['missing_command', 'missing_recipe', 'command_profile_removed'])
def test_denoise_original_file_queue_requires_exact_binding(rig, mode):
    e = rig
    e.service.activate(e.nid, e.scope, e.actor)
    e.source = import_asset(e, data=wav_bytes(rate=22050, channels=2, milliseconds=5000), filename='binding-source.wav', kind='audio')
    e.production = production(e)
    e.command = command(snapshot(e.source), in_ms=1000, out_ms=4500, sample_rate=22050, channels=2, denoise_profile=PROFILE)
    normal = queue(e)
    owner = e.production._audio(e.scope, e.actor)
    stored = owner.store.load(e.nid, include_studio=True)['jobs'][0]
    assert normal['status'] == 'QUEUED' and _binding(stored['context'], stored['_studio_body']) == stored['context']
    context = deepcopy(stored['context'])
    context['request_id'] = 'binding-regression-' + mode
    context['command']['request_id'] = context['request_id']
    if mode == 'missing_command': context.pop('command')
    elif mode == 'missing_recipe': context.pop('execution_recipe')
    else: context['command']['parameters'].pop('denoise_profile')
    if 'command' in context:
        # Rehash the inconsistent declaration, so rejection proves the request
        # body/command fence rather than just detecting an old digest.
        context['request_digest'] = digest({'context': {key: value for key, value in context.items() if key not in {'command', 'request_digest'}}, 'command': context['command']})
    errors, admitted = {}, {}
    for target, work in {
        'binding': lambda: _binding(context, stored['_studio_body']),
        'file_queue': lambda: owner.queue(e.nid, stored['_studio_body'], context, lambda: None, e.production._source_guard(e.nid, e.scope, lambda: None)),
    }.items():
        try:
            result = work()
            admitted[target] = {'status': result.get('status'), 'id': result.get('id')}
        except AudiobookError as error:
            errors[target] = {'code': error.code, 'status': error.status}
    jobs = owner.store.load(e.nid, include_studio=True)['jobs']
    record = {'mode': mode, 'normal_status': normal['status'], 'normal_job_id': normal['id'], 'admitted': admitted,
        'errors': errors, 'persisted_jobs': len(jobs), 'executed': False, 'external_permission_bypass_claimed': False}
    folder = os.environ.get('DENOISE_BINDING_EVIDENCE_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        (Path(folder) / (mode + '.json')).write_text(json.dumps(record, indent=2), encoding='utf-8')
    assert admitted == {}, record
    expected = 'STUDIO_AUDIO_DENOISE_BINDING_CHANGED' if mode == 'command_profile_removed' else 'STUDIO_AUDIO_DENOISE_BINDING_REQUIRED'
    assert {error['code'] for error in errors.values()} == {expected}
    assert len(errors) == 2 and len(jobs) == 1


def test_legacy_omitted_control_keeps_original_optional_layers():
    _, context, _, body = captured(command())
    assert 'denoise_profile' not in body['parameters']
    assert _binding(context, body) == context
    historical = {key: value for key, value in context.items() if key not in {'command', 'execution_recipe'}}
    assert _binding(historical, body) == historical
