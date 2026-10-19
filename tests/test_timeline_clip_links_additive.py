"""Bounded pair edits and real File CAS; synthetic PNG/WAV, no render/model."""
from copy import deepcopy
import pytest

from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from app.services.studio_timeline_edit import apply_timeline_edits, require_timeline_lock_preservation
from app.services.studio_timeline_render import normalize_studio_timeline
from test_v2_independent_workspace import rig, import_asset, reopened, wav_bytes
from test_v2_audio_editing_pipeline import production, source, edit_body


def timeline(video=None, audio=None):
    def snapshot(kind):
        return {'id': 'synthetic-' + kind, 'kind': 'ASSET', 'asset_kind': kind, 'version': 1, 'digest': 'a' * 64}
    return {'schema_version': 2, 'duration_ms': 8000, 'width': 64, 'height': 64, 'fps': 25, 'captions': [], 'tracks': [
        {'id': 'visual', 'kind': 'VIDEO', 'order': 0, 'clips': [
            {'id': 'picture', 'source_snapshot': video or snapshot('image'), 'start_ms': 1000, 'in_ms': 0, 'out_ms': 500}]},
        {'id': 'voice', 'kind': 'AUDIO', 'order': 1, 'clips': [
            {'id': 'sound', 'source_snapshot': audio or snapshot('audio'), 'start_ms': 1250, 'in_ms': 0, 'out_ms': 100}]}]}


LINK = {'op': 'clip.link', 'video_clip_id': 'picture', 'audio_clip_id': 'sound'}


def test_legacy_bytes_pair_move_once_and_explicit_unlink():
    original = normalize_studio_timeline(timeline())
    assert 'clip_links' not in original
    assert normalize_studio_timeline(original) == original
    linked = apply_timeline_edits(original, [LINK])
    assert linked['clip_links'] == [{'video_clip_id': 'picture', 'audio_clip_id': 'sound', 'offset_ms': 250}]
    moved = apply_timeline_edits(linked, [
        {'op': 'clip.move', 'clip_id': 'picture', 'track_id': 'visual', 'start_ms': 1500},
        {'op': 'clip.move', 'clip_id': 'sound', 'track_id': 'voice', 'start_ms': 1750}])
    assert [track['clips'][0]['start_ms'] for track in moved['tracks']] == [1500, 1750]
    assert moved['clip_links'] == linked['clip_links']
    unlinked = apply_timeline_edits(moved, [{'op': 'clip.unlink', 'clip_id': 'sound'}])
    assert 'clip_links' not in unlinked
    assert 'clip_links' not in original


@pytest.mark.parametrize('operation', [
    {'op': 'clip.trim', 'clip_id': 'picture', 'in_ms': 0, 'out_ms': 400, 'ripple': False},
    {'op': 'clip.split', 'clip_id': 'picture', 'at_ms': 1200, 'new_clip_id': 'head'},
    {'op': 'clip.slip', 'clip_id': 'sound', 'offset_ms': 10},
    {'op': 'clip.update', 'clip_id': 'sound', 'changes': {'start_ms': 1400}},
])
def test_linked_unsupported_edits_explicitly_refuse_without_mutation(operation):
    linked = apply_timeline_edits(timeline(), [LINK]); before = deepcopy(linked)
    with pytest.raises(ValueError, match='UNSUPPORTED_UNLINK_FIRST'):
        apply_timeline_edits(linked, [operation])
    assert linked == before


@pytest.mark.parametrize('field,value', [('audio_clip_id', 'picture'), ('audio_clip_id', 'missing'), ('offset_ms', 251), ('offset_ms', True)])
def test_closed_schema_rejects_invalid_links(field, value):
    linked = apply_timeline_edits(timeline(), [LINK])
    linked['clip_links'][0][field] = value
    with pytest.raises(ValueError): normalize_studio_timeline(linked)


def test_whole_dto_cannot_retime_or_redefine_pair_and_legacy_schema_stays_closed():
    linked = apply_timeline_edits(timeline(), [LINK])
    changed = deepcopy(linked); changed['tracks'][0]['clips'][0]['out_ms'] = 400
    with pytest.raises(ValueError, match='UNSUPPORTED_UNLINK_FIRST'):
        require_timeline_lock_preservation(linked, changed)
    changed = deepcopy(linked); changed['tracks'][1]['clips'][0]['start_ms'] += 100; changed['clip_links'][0]['offset_ms'] += 100
    with pytest.raises(ValueError, match='OFFSET_CHANGED'):
        require_timeline_lock_preservation(linked, changed)
    for schema in (None, 3):
        row = timeline(); row['clip_links'] = []
        if schema is None: row.pop('schema_version')
        else: row = {'schema_version': 3, 'media_kind': 'AUDIO', 'duration_ms': 8000, 'tracks': [row['tracks'][1]], 'clip_links': []}
        with pytest.raises(ValueError): normalize_studio_timeline(row)


@pytest.fixture
def linked_file(rig):
    e = rig; e.service.activate(e.nid, e.scope, e.actor)
    e.picture = import_asset(e)  # Valid imported PNG on the VIDEO track, no generated video claim.
    e.sound = import_asset(e, data=wav_bytes(), kind='audio', filename='synthetic.wav')
    e.production = production(e)
    e.saved = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {'expected_version': 0, 'title': 'Synthetic linked File timeline', 'timeline': timeline(source(e.picture), source(e.sound))}, lambda: None)
    return e


def edit(e, saved, operations, key):
    return e.production.timeline_edit(e.nid, e.scope, e.actor, saved['id'], edit_body(saved, operations, key), lambda: None)


def persisted(e):
    return {str(path.relative_to(e.root)): path.read_bytes() for path in e.root.rglob('*.json')}


def test_file_link_move_cas_history_reopen_and_unlink(linked_file):
    e = linked_file
    linked = edit(e, e.saved, [LINK], 'link')
    moved = edit(e, linked, [{'op': 'clip.move', 'clip_id': 'sound', 'track_id': 'voice', 'start_ms': 1750}], 'move')
    assert [track['clips'][0]['start_ms'] for track in moved['timeline']['tracks']] == [1500, 1750]
    reopened_owner = production(e, reopened(e))
    assert reopened_owner.timeline_get(e.nid, e.scope, e.actor, moved['id'], lambda: None) == moved
    changed = deepcopy(moved['timeline'])
    for track in changed['tracks']: track['clips'][0]['start_ms'] += 100
    saved = reopened_owner.timeline_save(e.nid, e.scope, e.actor, moved['id'],
        {'expected_version': moved['version'], 'title': moved['title'], 'timeline': changed}, lambda: None)
    assert saved['version'] == moved['version'] + 1
    before = persisted(e)
    with pytest.raises(CapabilityVersionConflict):
        e.production.timeline_save(e.nid, e.scope, e.actor, saved['id'],
            {'expected_version': moved['version'], 'title': saved['title'], 'timeline': changed}, lambda: None)
    assert persisted(e) == before
    history = e.production.timeline_history(e.nid, e.scope, e.actor, saved['id'], lambda: None)
    assert any(row['timeline'].get('clip_links') == moved['timeline']['clip_links'] for row in history['items'])
    unlinked = edit(e, saved, [{'op': 'clip.unlink', 'clip_id': 'picture'}], 'unlink')
    assert 'clip_links' not in unlinked['timeline']
    assert production(e, reopened(e)).timeline_get(e.nid, e.scope, e.actor, saved['id'], lambda: None) == unlinked


def test_file_locked_or_outside_pair_rolls_back_entire_batch(linked_file):
    e = linked_file
    linked = edit(e, e.saved, [LINK], 'link')
    before = persisted(e)
    with pytest.raises(ValueError):
        edit(e, linked, [{'op': 'clip.move', 'clip_id': 'picture', 'track_id': 'visual', 'start_ms': -1}], 'outside')
    assert persisted(e) == before
    with pytest.raises(ValueError, match='UNSUPPORTED_UNLINK_FIRST'):
        edit(e, linked, [{'op': 'clip.move', 'clip_id': 'picture', 'track_id': 'visual', 'start_ms': 1500},
                         {'op': 'clip.trim', 'clip_id': 'sound', 'in_ms': 0, 'out_ms': 80, 'ripple': False}], 'prefix-rollback')
    assert persisted(e) == before
    changed = deepcopy(linked['timeline']); changed['tracks'][0]['clips'][0]['out_ms'] = 400
    with pytest.raises(ValueError, match='UNSUPPORTED_UNLINK_FIRST'):
        e.production.timeline_save(e.nid, e.scope, e.actor, linked['id'],
            {'expected_version': linked['version'], 'title': linked['title'], 'timeline': changed}, lambda: None)
    assert persisted(e) == before
    locked = edit(e, linked, [{'op': 'track.update', 'track_id': 'voice', 'changes': {'locked': True}}], 'lock')
    for operations in ([{'op': 'clip.move', 'clip_id': 'picture', 'track_id': 'visual', 'start_ms': 1500}],
                       [{'op': 'clip.unlink', 'clip_id': 'picture'}]):
        before = persisted(e)
        with pytest.raises(ValueError, match='TRACK_LOCKED'): edit(e, locked, operations, 'locked-attempt')
        assert persisted(e) == before
        assert e.production.timeline_get(e.nid, e.scope, e.actor, locked['id'], lambda: None) == locked


def test_file_stale_source_rejects_linked_move_without_partial_write(linked_file):
    e = linked_file
    linked = edit(e, e.saved, [LINK], 'link')
    # Alter only the imported asset revision through the original owner, never a fake source validator.
    e.service.lifecycle(e.nid, e.scope, e.sound['id'], e.sound['version'], actor_id=e.actor)
    before = persisted(e)
    with pytest.raises((ValueError, FileNotFoundError, StaleSourceError)):
        edit(e, linked, [{'op': 'clip.move', 'clip_id': 'picture', 'track_id': 'visual', 'start_ms': 1500}], 'stale')
    assert persisted(e) == before
