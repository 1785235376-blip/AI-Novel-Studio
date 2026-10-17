"""Selected-copy descriptors through the original File timeline owners.

This composes existing duplicate/update commands, not a new backend selection
DTO. Backend repeated-source commands and audio overlaps remain legal. These
checks cover detached candidates and explicit Save, not browser/native render,
media-duration validation, providers, PostgreSQL or release acceptance.
"""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from app.creative.production_execution import TIMELINES
from app.experimental.common import StaleSourceError
from app.services.studio_timeline_edit import apply_timeline_edits
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig
from test_v2_timeline_selection_handoff import selection_env, by_id, clip, history, pins

pytestmark = [pytest.mark.file_backend_only, pytest.mark.parametrize('rig', ['file'], indirect=True)]


def copies(timeline, mapping, offset):
    """Explicit original descriptors, with internal edges restored at batch end."""
    locations = {item['id']: (row['id'], item)
                 for row in timeline['tracks'] for item in row['clips']}
    operations = [{'op': 'clip.duplicate', 'clip_id': identity, 'new_clip_id': copied,
                   'track_id': locations[identity][0],
                   'start_ms': locations[identity][1]['start_ms'] + offset}
                  for identity, copied in mapping.items()]
    for identity, copied in mapping.items():
        transition = locations[identity][1].get('transition_out')
        if transition and transition['to_clip_id'] in mapping:
            operations.append({'op': 'clip.update', 'clip_id': copied, 'changes': {
                'transition_out': {**transition, 'to_clip_id': mapping[transition['to_clip_id']]}}})
    return operations


def expected_copies(timeline, mapping, offset):
    expected = deepcopy(timeline)
    for row in expected['tracks']:
        originals = list(row['clips'])
        for original in originals:
            if original['id'] not in mapping:
                continue
            item = deepcopy(original)
            item.update(id=mapping[original['id']], start_ms=original['start_ms'] + offset)
            transition = item.pop('transition_out', None)
            if transition and transition['to_clip_id'] in mapping:
                item['transition_out'] = {**transition, 'to_clip_id': mapping[transition['to_clip_id']]}
            row['clips'].append(item)
        row['clips'].sort(key=lambda item: (item['start_ms'], item['id']))
    return expected


def durable_files(e):
    return {str(path.relative_to(e.rig.root)): path.read_bytes()
            for path in e.rig.root.rglob('*') if path.is_file()}


def source_files(e):
    result = {}
    for asset in e.rig.service.list_assets(e.rig.nid, e.rig.scope)['items']:
        for path in (e.rig.assets._meta_path(asset['id']), e.rig.assets._bin_path(asset['id'])):
            result[str(path)] = path.read_bytes()
    return result


def other_collections(e):
    return {key: value for key, value in e.rig.raw_store.read(e.rig.nid, e.rig.scope)['collections'].items()
            if key != TIMELINES}


def assert_saved_once(e, original, candidate):
    assets, collections, asset_pins = source_files(e), other_collections(e), pins(e)
    assert e.get(original) == original and history(e, original)['items'] == []
    saved = e.save(candidate, original)
    assert saved['timeline'] == candidate and saved['version'] == original['version'] + 1
    assert e.get(saved) == saved  # A fresh service/store is opened by the fixture.
    prior = history(e, saved)
    assert [row['version'] for row in prior['items']] == [original['version']]
    assert prior['items'][0]['timeline'] == original['timeline']
    before = durable_files(e)
    with pytest.raises(CapabilityVersionConflict):
        e.save(candidate, original)
    with pytest.raises(StaleSourceError, match='STUDIO_TIMELINE_CHANGED'):
        e.edit(original, copies(original['timeline'], {'rational': 'stale-copy'}, 0), 'stale-copy')
    assert durable_files(e) == before
    assert e.get(saved) == saved and history(e, saved) == prior
    assert pins(e) == asset_pins and source_files(e) == assets and other_collections(e) == collections
    return saved


@pytest.mark.parametrize('offset', [3000, -3000])
def test_mixed_group_exact_fields_originals_pins_and_explicit_save(selection_env, offset):
    e = selection_env
    if offset < 0:
        for row in e.timeline['tracks'][:2]:
            for item in row['clips']:
                if item['id'] in {'first', 'second', 'rational'}:
                    item['start_ms'] += 3000
    first = by_id(e.timeline)['first']
    first.update(crop={'x': 0, 'y': 0, 'width': 2, 'height': 2},
                 opacity=0.6, x=2, y=4, width=320, height=180,
                 fade_in_ms=100, fade_out_ms=200, muted=True)
    by_id(e.timeline)['rational']['muted'] = True
    original = e.save(e.timeline)
    mapping = {'first': 'copy-first', 'second': 'copy-second', 'rational': 'copy-rational'}
    before = deepcopy(original['timeline']); files = durable_files(e)
    candidate = apply_timeline_edits(before, copies(before, mapping, offset))
    assert before == original['timeline'] and durable_files(e) == files
    assert candidate == expected_copies(before, mapping, offset)
    for identity, item in by_id(before).items():
        assert by_id(candidate)[identity] == item
    assert candidate['duration_ms'] == before['duration_ms'] and candidate['captions'] == before['captions']
    rational = by_id(candidate)['copy-rational']
    assert (rational['out_ms'] - rational['in_ms']) * rational['speed_den'] // rational['speed_num'] == 2000
    assert_saved_once(e, original, candidate)
    # Copies do not share mutable snapshots or crop dictionaries with originals.
    by_id(candidate)['copy-first']['crop']['width'] = 1
    by_id(candidate)['copy-first']['source_snapshot']['version'] += 1
    assert by_id(candidate)['first'] == by_id(before)['first']


@pytest.mark.parametrize('selected', [('first', 'second'), ('first',), ('second',)])
def test_internal_transition_remap_and_external_edges_not_copied(selection_env, selected):
    e = selection_env
    by_id(e.timeline)['second']['start_ms'] = 1800
    by_id(e.timeline)['first']['transition_out'] = {
        'kind': 'CROSS_DISSOLVE', 'to_clip_id': 'second', 'duration_ms': 200}
    original = e.save(e.timeline); before = deepcopy(original['timeline'])
    mapping = {identity: 'copy-' + identity for identity in selected}
    operations = copies(before, mapping, 3000)
    if len(selected) == 2:
        assert operations[-1] == {'op': 'clip.update', 'clip_id': 'copy-first', 'changes': {
            'transition_out': {'kind': 'CROSS_DISSOLVE', 'to_clip_id': 'copy-second', 'duration_ms': 200}}}
        with pytest.raises(ValueError, match='STUDIO_TIMELINE_SAME_VIDEO_TRACK_OVERLAP'):
            apply_timeline_edits(before, operations[:-1])
    candidate = apply_timeline_edits(before, operations)
    assert before == original['timeline'] and candidate == expected_copies(before, mapping, 3000)
    assert by_id(candidate)['first']['transition_out']['to_clip_id'] == 'second'
    if len(selected) == 1:
        assert 'transition_out' not in by_id(candidate)['copy-' + selected[0]]
    assert_saved_once(e, original, candidate)


@pytest.mark.parametrize('offset', [0, 1, -500])
def test_audio_overlap_zero_and_signed_offsets_remain_legal(selection_env, offset):
    e = selection_env; original = e.save(e.timeline)
    mapping = {'rational': 'copy-rational', 'audio-fixed': 'copy-audio-fixed'}
    candidate = apply_timeline_edits(original['timeline'], copies(original['timeline'], mapping, offset))
    assert candidate == expected_copies(original['timeline'], mapping, offset)
    assert_saved_once(e, original, candidate)


def test_original_repeated_source_commands_are_legal_and_edit_is_atomic_idempotent(selection_env):
    e = selection_env; original = e.save(e.timeline)
    operations = copies(original['timeline'], {'rational': 'copy-one'}, 0)
    operations += copies(original['timeline'], {'rational': 'copy-two'}, 0)
    candidate = apply_timeline_edits(original['timeline'], operations)
    assets, collections = source_files(e), other_collections(e)
    saved = e.edit(original, operations, 'two-explicit-copies')
    assert saved['timeline'] == candidate and saved['version'] == original['version'] + 1
    assert e.get(saved) == saved
    prior = history(e, saved)
    assert [row['version'] for row in prior['items']] == [original['version']]
    assert e.edit(original, operations, 'two-explicit-copies') == saved
    assert history(e, saved) == prior and source_files(e) == assets and other_collections(e) == collections


@pytest.mark.parametrize('case,error', [
    ('collision', 'STUDIO_TIMELINE_SAME_VIDEO_TRACK_OVERLAP'),
    ('negative', 'STUDIO_TIMELINE_INTEGER_INVALID'),
    ('outside-start', 'STUDIO_TIMELINE_INTEGER_INVALID'),
    ('outside-end', 'STUDIO_TIMELINE_CLIP_RANGE_INVALID'),
    ('locked-source', 'STUDIO_TIMELINE_TRACK_LOCKED'),
    ('locked-target', 'STUDIO_TIMELINE_TRACK_LOCKED'),
    ('missing-source', 'STUDIO_TIMELINE_EDIT_CLIP_NOT_FOUND'),
    ('missing-track', 'STUDIO_TIMELINE_EDIT_TRACK_NOT_FOUND'),
    ('wrong-kind', 'STUDIO_TIMELINE_EDIT_MOVE_KIND_INVALID'),
    ('existing-id', 'STUDIO_TIMELINE_CLIP_ID_DUPLICATE'),
    ('repeated-new-id', 'STUDIO_TIMELINE_CLIP_ID_DUPLICATE'),
    ('invalid-id', 'STUDIO_TIMELINE_EDIT_ID_INVALID'),
    ('boolean', 'STUDIO_TIMELINE_EDIT_INTEGER_INVALID'),
    ('fractional', 'STUDIO_TIMELINE_EDIT_INTEGER_INVALID'),
    ('external-target', 'STUDIO_TIMELINE_TRANSITION_WINDOW_INVALID'),
])
def test_rejected_batch_has_no_partial_copy_revision_or_product_write(selection_env, case, error):
    e = selection_env; original = e.save(e.timeline); before = deepcopy(original['timeline'])
    valid = copies(before, {'rational': 'copy-rational'}, 0)
    bad = copies(before, {'first': 'copy-first'}, 3000)[0]
    replacements = {'collision': {'start_ms': 1000}, 'negative': {'start_ms': -1},
        'outside-start': {'start_ms': 10000}, 'outside-end': {'start_ms': 9500},
        'locked-source': {'clip_id': 'locked', 'track_id': 'audio'},
        'locked-target': {'clip_id': 'rational', 'track_id': 'other'},
        'missing-source': {'clip_id': 'missing'}, 'missing-track': {'track_id': 'missing'},
        'wrong-kind': {'track_id': 'audio'}, 'existing-id': {'new_clip_id': 'first'},
        'repeated-new-id': {'new_clip_id': 'copy-rational'}, 'invalid-id': {'new_clip_id': '../bad'},
        'boolean': {'start_ms': True}, 'fractional': {'start_ms': 4000.5}}
    bad.update(replacements.get(case, {})); operations = valid + [bad]
    if case == 'external-target':
        operations.append({'op': 'clip.update', 'clip_id': 'copy-first', 'changes': {
            'transition_out': {'kind': 'CROSS_DISSOLVE', 'to_clip_id': 'second', 'duration_ms': 200}}})
    files = durable_files(e)
    with pytest.raises(ValueError, match=error):
        apply_timeline_edits(before, operations)
    with pytest.raises(ValueError, match=error):
        e.edit(original, operations, 'rejected-' + case)
    assert before == original['timeline'] and durable_files(e) == files
    assert e.get(original) == original and history(e, original)['items'] == []


def test_original_operation_and_byte_limits_reject_before_writes(selection_env):
    e = selection_env; original = e.save(e.timeline); files = durable_files(e)
    operation = copies(original['timeline'], {'rational': 'copy-rational'}, 0)[0]
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_EDIT_OPERATION_LIMIT'):
        apply_timeline_edits(original['timeline'], [operation] * 41)
    with pytest.raises(ValidationError):
        e.edit(original, [operation] * 41)
    oversized = [{**operation, 'new_clip_id': 'x' * 128001}]
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_EDIT_BYTES_LIMIT'):
        apply_timeline_edits(original['timeline'], oversized)
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_EDIT_BYTES_LIMIT'):
        e.edit(original, oversized)
    assert durable_files(e) == files and e.get(original) == original


def test_thirty_clips_and_forty_operations_are_distinct_existing_limits(selection_env):
    e = selection_env; source = by_id(e.timeline)['first']['source_snapshot']
    e.timeline['tracks'][0]['clips'] = [clip('visual-' + str(index), source, 100 + index * 100, 100)
                                       for index in range(26)]
    # 26 visual plus three audio originals = 29 total; one duplicate reaches 30.
    original = e.save(e.timeline)
    operations = copies(original['timeline'], {'rational': 'copy-rational'}, 0)
    operations += [{'op': 'clip.update', 'clip_id': 'copy-rational', 'changes': {'gain_db': -6}}] * 39
    candidate = apply_timeline_edits(original['timeline'], operations)
    assert len(by_id(candidate)) == 30
    saved = assert_saved_once(e, original, candidate); files = durable_files(e)
    rejected = copies(saved['timeline'], {'rational': 'clip-31'}, 0)
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_CLIP_LIMIT'):
        apply_timeline_edits(saved['timeline'], rejected)
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_CLIP_LIMIT'):
        e.edit(saved, rejected, 'exceeds-thirty')
    assert durable_files(e) == files and e.get(saved) == saved


@pytest.mark.parametrize('change', ['source-version', 'source-digest', 'private', 'wrong-actor', 'wrong-scope'])
def test_original_live_source_and_scope_authority_reject_save_and_edit_without_writes(selection_env, change):
    e = selection_env; original = e.save(e.timeline)
    operations = copies(original['timeline'], {'rational': 'copy-rational'}, 0)
    candidate = apply_timeline_edits(original['timeline'], operations)
    actor, scope = e.rig.actor, e.rig.scope
    if change in {'source-version', 'source-digest', 'private'}:
        source = by_id(original['timeline'])['rational']['source_snapshot']
        path = e.rig.assets._meta_path(source['id']); metadata = json.loads(path.read_text())
        if change == 'source-version': metadata['version'] += 1
        elif change == 'source-digest': metadata['sha256'] = '0' * 64
        else: metadata['_owner_actor_id'] = actor
        path.write_text(json.dumps(metadata))
    elif change == 'wrong-actor':
        actor = 'different-author'
    else:
        scope = {**scope, 'branch_id': 'wrong-branch'}
        # Original read may create an empty advisory lock, never a document.
        e.rig.raw_store.read(e.rig.nid, scope)
    files = durable_files(e)
    with pytest.raises((ValueError, FileNotFoundError, StaleSourceError)):
        e.production.timeline_save(e.rig.nid, scope, actor, original['id'],
            {'expected_version': original['version'], 'title': original['title'], 'timeline': candidate}, lambda: None)
    assert durable_files(e) == files
    with pytest.raises((ValueError, FileNotFoundError, StaleSourceError)):
        e.production.timeline_edit(e.rig.nid, scope, actor, original['id'],
            {'expected_version': original['version'], 'reviewed_timeline_digest': original['timeline_digest'],
             'request_id': 'reject-authority', 'operations': operations}, lambda: None)
    assert durable_files(e) == files
    assert e.get(original) == original and history(e, original)['items'] == []


def test_whole_document_save_cannot_bypass_locked_copy(selection_env):
    e = selection_env; original = e.save(e.timeline)
    unlocked = deepcopy(original['timeline']); unlocked['tracks'][2]['locked'] = False
    candidate = apply_timeline_edits(unlocked, copies(unlocked, {'locked': 'copy-locked'}, 0))
    candidate['tracks'][2]['locked'] = True
    files = durable_files(e)
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_TRACK_LOCKED'):
        e.save(candidate, original)
    assert durable_files(e) == files and e.get(original) == original
