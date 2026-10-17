"""Atomic same-track selection offsets through original File edit/Save owners.

The UI selection guard is not a backend DTO: duplicate original move operations
are legal, the batch cap is 40 operations, and schema documents cap all clips at
30. Audio overlap is legal. These tests neither extend those contracts nor claim
rendering, decoded-duration validation, browser, provider or PostgreSQL coverage.
"""
from copy import deepcopy
import io
from types import SimpleNamespace
import wave

import pytest
from pydantic import ValidationError

from app.asset_providers import AssetProviderRegistry
from app.experimental.common import StaleSourceError
from app.services.studio_timeline_edit import apply_timeline_edits
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_discovered_image_production import owner
from test_v2_independent_workspace import rig, import_asset, reopened

pytestmark = [pytest.mark.file_backend_only, pytest.mark.parametrize('rig', ['file'], indirect=True)]


def reference(asset):
    return {'id': asset['id'], 'kind': 'ASSET', 'asset_kind': asset['kind'],
            'version': asset['version'], 'digest': asset['sha256']}


def clip(identity, source, start, end, **extra):
    return {'id': identity, 'source_snapshot': deepcopy(source), 'start_ms': start,
            'in_ms': 0, 'out_ms': end, **extra}


def by_id(timeline):
    return {item['id']: item for row in timeline['tracks'] for item in row['clips']}


def moves(timeline, identities, offset):
    """Describe original operations; deliberately not a replacement UI validator."""
    locations = {item['id']: (row['id'], item['start_ms'])
                 for row in timeline['tracks'] for item in row['clips']}
    return [{'op': 'clip.move', 'clip_id': identity, 'track_id': locations[identity][0],
             'start_ms': locations[identity][1] + offset} for identity in identities]


@pytest.fixture
def selection_env(rig, monkeypatch):
    production = owner(AssetProviderRegistry(), monkeypatch, rig)
    image = import_asset(rig)
    data = io.BytesIO()
    with wave.open(data, 'wb') as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(8000)
        writer.writeframes(b'\x00\x00' * 48000)
    audio = import_asset(rig, data=data.getvalue(), filename='selection.wav', kind='audio')
    visual, sound = reference(image), reference(audio)
    timeline = {'schema_version': 2, 'duration_ms': 10000, 'width': 640, 'height': 360, 'fps': 24,
        'tracks': [
            {'id': 'visual', 'kind': 'VIDEO', 'order': 0, 'clips': [
                clip('first', visual, 1000, 1000), clip('second', visual, 2000, 1000),
                clip('fixed', visual, 7000, 1000)]},
            {'id': 'audio', 'kind': 'AUDIO', 'order': 1, 'gain_db': -3, 'clips': [
                clip('rational', sound, 1000, 3600, in_ms=600, speed_num=3, speed_den=2,
                     fade_in_ms=200, fade_out_ms=300, gain_db=-6),
                clip('audio-fixed', sound, 3000, 1000)]},
            {'id': 'other', 'kind': 'AUDIO', 'order': 2, 'locked': True,
             'clips': [clip('locked', sound, 2000, 1000)]}],
        'captions': [{'start_ms': 3000, 'end_ms': 3500, 'text': 'Keep caption 中文🌙'}]}
    def save(value, current=None):
        return production.timeline_save(rig.nid, rig.scope, rig.actor, current['id'] if current else None,
            {'expected_version': current['version'] if current else 0,
             'title': 'Explicit selection Save', 'timeline': value}, lambda: None)
    def get(current):
        fresh = owner(AssetProviderRegistry(), monkeypatch,
            SimpleNamespace(**{**vars(rig), 'service': reopened(rig)}))
        return fresh.timeline_get(rig.nid, rig.scope, rig.actor, current['id'], lambda: None)
    def edit(current, operations, request_id='selection-move'):
        return production.timeline_edit(rig.nid, rig.scope, rig.actor, current['id'],
            {'expected_version': current['version'], 'reviewed_timeline_digest': current['timeline_digest'],
             'request_id': request_id, 'operations': operations}, lambda: None)
    return SimpleNamespace(rig=rig, production=production, timeline=timeline, save=save, get=get, edit=edit)


def history(e, current):
    return e.production.timeline_history(e.rig.nid, e.rig.scope, e.rig.actor, current['id'], lambda: None)


def pins(e):
    return sorted((row['id'], row['version'], row['sha256'])
                  for row in e.rig.service.list_assets(e.rig.nid, e.rig.scope)['items'])


def shifted(timeline, identities, offset):
    expected = deepcopy(timeline)
    for row in expected['tracks']:
        for item in row['clips']:
            if item['id'] in identities:
                item['start_ms'] += offset
        row['clips'].sort(key=lambda item: (item['start_ms'], item['id']))
    return expected


def assert_save_once(e, original, candidate, original_pins):
    assert e.get(original) == original and history(e, original)['items'] == []
    saved = e.save(candidate, original)
    assert saved['version'] == original['version'] + 1
    assert saved['timeline'] == candidate and e.get(saved) == saved
    prior = history(e, saved)
    assert [row['version'] for row in prior['items']] == [original['version']]
    assert prior['items'][0]['timeline'] == original['timeline']
    with pytest.raises(CapabilityVersionConflict):
        e.save(candidate, original)
    with pytest.raises(StaleSourceError, match='STUDIO_TIMELINE_CHANGED'):
        e.edit(original, moves(original['timeline'], [original['timeline']['tracks'][0]['clips'][0]['id']], 1), 'stale-selection')
    assert e.get(saved) == saved and history(e, saved) == prior
    assert pins(e) == original_pins


@pytest.mark.parametrize('offset', [500, -500, 1])
def test_shared_signed_offset_preserves_exact_dto_and_one_explicit_save(selection_env, offset):
    e = selection_env; original = e.save(e.timeline); original_pins = pins(e)
    before = deepcopy(original['timeline']); selected = ['first', 'second', 'rational']
    # Moving only the leading video clip collides transiently for positive offsets.
    if offset > 0:
        with pytest.raises(ValueError, match='STUDIO_TIMELINE_SAME_VIDEO_TRACK_OVERLAP'):
            apply_timeline_edits(before, moves(before, ['first'], offset))
    candidate = apply_timeline_edits(before, moves(before, selected, offset))
    assert before == original['timeline']
    assert candidate == shifted(before, selected, offset)
    rational = by_id(candidate)['rational']
    assert (rational['out_ms'] - rational['in_ms']) * rational['speed_den'] // rational['speed_num'] == 2000
    assert_save_once(e, original, candidate, original_pins)


@pytest.mark.parametrize('offset', [500, -500])
def test_transition_pair_keeps_exact_window_through_save_reopen(selection_env, offset):
    e = selection_env; first, second = e.timeline['tracks'][0]['clips'][:2]
    second['start_ms'] = 1800
    first['transition_out'] = {'kind': 'CROSS_DISSOLVE', 'to_clip_id': 'second', 'duration_ms': 200}
    original = e.save(e.timeline); original_pins = pins(e)
    candidate = apply_timeline_edits(original['timeline'], moves(original['timeline'], ['first', 'second'], offset))
    assert candidate == shifted(original['timeline'], ['first', 'second'], offset)
    assert_save_once(e, original, candidate, original_pins)


def test_original_edit_is_one_atomic_revision_and_idempotent(selection_env):
    e = selection_env; original = e.save(e.timeline); original_pins = pins(e)
    operations = moves(original['timeline'], ['first', 'second', 'rational'], 500)
    saved = e.edit(original, operations)
    assert saved['timeline'] == shifted(original['timeline'], ['first', 'second', 'rational'], 500)
    assert saved['version'] == original['version'] + 1 and e.get(saved) == saved
    prior = history(e, saved)
    assert [row['version'] for row in prior['items']] == [original['version']]
    assert e.edit(original, operations) == saved
    assert history(e, saved) == prior and pins(e) == original_pins


@pytest.mark.parametrize('case,error', [
    ('partial-transition', 'STUDIO_TIMELINE_TRANSITION_WINDOW_INVALID'),
    ('collision', 'STUDIO_TIMELINE_SAME_VIDEO_TRACK_OVERLAP'),
    ('negative', 'STUDIO_TIMELINE_INTEGER_INVALID'),
    ('outside-start', 'STUDIO_TIMELINE_INTEGER_INVALID'),
    ('outside-end', 'STUDIO_TIMELINE_CLIP_RANGE_INVALID'),
    ('locked', 'STUDIO_TIMELINE_TRACK_LOCKED'),
    ('missing', 'STUDIO_TIMELINE_EDIT_CLIP_NOT_FOUND'),
    ('boolean', 'STUDIO_TIMELINE_EDIT_INTEGER_INVALID'),
    ('fractional', 'STUDIO_TIMELINE_EDIT_INTEGER_INVALID'),
])
def test_rejected_batch_preserves_input_and_file_history(selection_env, case, error):
    e = selection_env
    if case == 'partial-transition':
        e.timeline['tracks'][0]['clips'][1]['start_ms'] = 1800
        e.timeline['tracks'][0]['clips'][0]['transition_out'] = {
            'kind': 'CROSS_DISSOLVE', 'to_clip_id': 'second', 'duration_ms': 200}
    original = e.save(e.timeline); before = deepcopy(original['timeline']); original_pins = pins(e)
    identity = 'locked' if case == 'locked' else 'first'
    bad = moves(before, [identity], 500)[0]
    starts = {'negative': -1, 'outside-start': 10000, 'outside-end': 9500,
              'boolean': True, 'fractional': 1000.5}
    if case in starts: bad['start_ms'] = starts[case]
    if case == 'missing': bad['clip_id'] = 'missing'
    operations = moves(before, ['rational'], 1) + [bad]
    prior = history(e, original)
    with pytest.raises(ValueError, match=error):
        apply_timeline_edits(before, operations)
    assert before == original['timeline']
    with pytest.raises(ValueError, match=error):
        e.edit(original, operations, 'reject-' + case)
    assert e.get(original) == original and history(e, original) == prior
    assert pins(e) == original_pins


def test_oversized_original_batch_rejected_without_persistence(selection_env):
    e = selection_env; original = e.save(e.timeline); original_pins = pins(e)
    operations = moves(original['timeline'], ['rational'], 1) * 41
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_EDIT_OPERATION_LIMIT'):
        apply_timeline_edits(original['timeline'], operations)
    # The public owner rejects this at its existing DTO limit before edit dispatch.
    with pytest.raises(ValidationError):
        e.edit(original, operations)
    assert e.get(original) == original and history(e, original)['items'] == []
    assert pins(e) == original_pins


def test_original_duplicate_moves_and_audio_overlap_are_legal(selection_env):
    e = selection_env; original = e.save(e.timeline); original_pins = pins(e)
    # UI duplicate-selection rejection must not be asserted for original batches.
    operations = moves(original['timeline'], ['rational'], 500) * 40
    candidate = apply_timeline_edits(original['timeline'], operations)
    assert candidate == shifted(original['timeline'], ['rational'], 500)
    assert by_id(candidate)['rational']['start_ms'] + 2000 > by_id(candidate)['audio-fixed']['start_ms']
    assert_save_once(e, original, candidate, original_pins)


def test_schema_allows_thirty_distinct_clips_not_forty(selection_env):
    e = selection_env; source = e.timeline['tracks'][0]['clips'][0]['source_snapshot']
    e.timeline['tracks'] = [{'id': 'visual', 'kind': 'VIDEO', 'order': 0,
        'clips': [clip('clip-' + str(index), source, 100 + index * 100, 100) for index in range(30)]}]
    original = e.save(e.timeline); original_pins = pins(e)
    identities = list(by_id(original['timeline']))
    candidate = apply_timeline_edits(original['timeline'], moves(original['timeline'], identities, 100))
    assert candidate == shifted(original['timeline'], identities, 100)
    assert_save_once(e, original, candidate, original_pins)
    # No schema expansion is implied by the 40-operation editing limit.
    oversized = deepcopy(candidate)
    oversized['tracks'][0]['clips'].append(clip('clip-31', source, 9000, 100))
    saved = e.get(original); prior = history(e, saved)
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_CLIP_LIMIT'):
        e.save(oversized, saved)
    assert e.get(saved) == saved and history(e, saved) == prior


def test_zero_offset_is_detached_without_implicit_save(selection_env):
    e = selection_env; original = e.save(e.timeline); original_pins = pins(e)
    candidate = apply_timeline_edits(original['timeline'], moves(original['timeline'], ['first', 'second'], 0))
    assert candidate == original['timeline'] and candidate is not original['timeline']
    by_id(candidate)['first']['start_ms'] = 0
    assert by_id(original['timeline'])['first']['start_ms'] == 1000
    assert e.get(original) == original and history(e, original)['items'] == []
    assert pins(e) == original_pins


def test_save_rejects_changed_source_pins_after_valid_selection_move(selection_env):
    e = selection_env; original = e.save(e.timeline); original_pins = pins(e)
    candidate = apply_timeline_edits(original['timeline'], moves(original['timeline'], ['first', 'second'], 500))
    for item in by_id(candidate).values():
        if item['source_snapshot']['asset_kind'] == 'image':
            item['source_snapshot']['version'] += 1
    with pytest.raises(StaleSourceError, match='STUDIO_TIMELINE_SOURCE_CHANGED'):
        e.save(candidate, original)
    assert e.get(original) == original and history(e, original)['items'] == []
    assert pins(e) == original_pins


def test_whole_document_save_cannot_bypass_selected_track_lock(selection_env):
    e = selection_env; original = e.save(e.timeline); original_pins = pins(e)
    candidate = deepcopy(original['timeline'])
    by_id(candidate)['locked']['start_ms'] += 500
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_TRACK_LOCKED'):
        e.save(candidate, original)
    assert e.get(original) == original and history(e, original)['items'] == []
    assert pins(e) == original_pins
