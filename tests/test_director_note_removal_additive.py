"""Original owner persistence after explicit local author-note removal."""
import copy
import pytest
from test_v2_creative_foundation import rig, public
from app.creative.service import CreativeService


def test_removed_note_uses_original_save_history_reopen_and_restore(rig):
    e = rig
    row = e.service.create(e.nid, e.scope, e.actor, {
        'mode': 'DIRECTOR', 'title': 'Synthetic direction', 'source_independent': True,
        'scenes': [{'id': 'scene', 'sequence': 1, 'heading': 'Room'}],
        'director_notes': [{'id': 'first', 'scene_id': 'scene', 'number': 1, 'note': 'Keep history'},
                           {'id': 'last', 'scene_id': 'scene', 'number': 3, 'note': 'Keep original numbering'}]})
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    body = public(row)
    body['director_notes'] = [note for note in body['director_notes'] if note['id'] != 'first']
    assert e.store.read(e.nid, e.scope) == before
    saved = e.service.update(e.nid, e.scope, e.actor, row['id'], 1, body)
    service = CreativeService(e.store, e.novels, e.chapters)
    reopened = service.get(e.nid, e.scope, row['id'])
    assert reopened == saved and reopened['version'] == 2
    assert [(n['id'], n['number']) for n in reopened['director_notes']] == [('last', 3)]
    assert reopened['scenes'] == row['scenes']
    history = service.history(e.nid, e.scope, row['id'])
    assert history['items'][0]['director_notes'] == row['director_notes']
    persisted = copy.deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(ValueError):
        service.update(e.nid, e.scope, e.actor, row['id'], 1, body)
    assert e.store.read(e.nid, e.scope) == persisted
    restored = service.restore(e.nid, e.scope, e.actor, row['id'], 2, 1)
    assert restored['version'] == 3 and restored['director_notes'] == row['director_notes']
    assert service.get(e.nid, e.scope, row['id']) == restored
