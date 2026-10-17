"""Mounted standalone fade admission: original preview and queue, no encoding."""
from copy import deepcopy

import pytest

from test_v2_audio_wav_controls_api import audio_client, client, preview, queue
from test_r3_mounted_contracts import checked, mounted, prefix


@pytest.mark.parametrize('parameters', [{'fade_in_ms': None}, {'fade_out_ms': True}, {'fade_in_ms': 10.0}, {'fade_out_ms': '10'}, {'fade_in_ms': -1}, {'fade_out_ms': 701}, {'fade_in_ms': 400, 'fade_out_ms': 301}])
def test_mounted_strict_fades_reject_before_job_or_asset_creation(audio_client, parameters):
    e = audio_client
    e.command['parameters'].update(parameters)
    response = preview(e)
    assert response.status_code == 422, response.text
    assert len(list(e.assets.root.glob('*.bin'))) == 1
    assert checked(e.client.get(e.base + '/jobs', headers=e.headers))['items'] == []


def test_mounted_zero_and_absence_have_distinct_reviewed_identity(audio_client):
    e = audio_client
    old = checked(preview(e))
    e.command['parameters']['fade_in_ms'] = 0
    current = checked(preview(e))
    assert current['request_digest'] != old['request_digest']
    assert current['execution_recipe']['parameters']['fade_in_ms'] == 0
    assert 'fade_out_ms' not in current['command']['parameters']
    rejected = e.client.post(e.base + '/jobs', headers=e.headers, json={'command': e.command, 'reviewed_preview_digest': old['preview_digest']})
    assert rejected.status_code == 409, rejected.text
    payload = {'command': e.command, 'reviewed_preview_digest': current['preview_digest']}
    queued = checked(e.client.post(e.base + '/jobs', headers=e.headers, json=payload), 201)
    replay = checked(e.client.post(e.base + '/jobs', headers=e.headers, json=payload), 201)
    assert replay == queued and queued['status'] == 'QUEUED'
    assert queued['execution_recipe']['parameters']['fade_in_ms'] == 0
    assert len(list(e.assets.root.glob('*.bin'))) == 1


def test_mounted_fade_change_requires_new_preview_and_request_identity(audio_client):
    e = audio_client
    e.command['parameters'].update(fade_in_ms=300, fade_out_ms=400)
    captured, queued = queue(e)
    changed = deepcopy(e.command); changed['parameters']['fade_out_ms'] = 399
    denied = e.client.post(e.base + '/jobs', headers=e.headers, json={'command': changed, 'reviewed_preview_digest': captured['preview_digest']})
    assert denied.status_code == 409, denied.text
    e.command = changed
    fresh = checked(preview(e))
    conflict = e.client.post(e.base + '/jobs', headers=e.headers, json={'command': changed, 'reviewed_preview_digest': fresh['preview_digest']})
    assert conflict.status_code == 409, conflict.text
    assert checked(e.client.get(e.base + '/jobs/audio/' + queued['id'], headers=e.headers)) == queued
