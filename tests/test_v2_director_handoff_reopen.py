"""Nonsecurity original-owner handoff persistence; human-authored fixture only."""
from test_v2_creative_foundation import rig
from test_v2_director_storyboard_production import independent_direction, production_input


def test_original_director_derive_reopen_and_edit(rig):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    source = rig.service.create(rig.nid, rig.scope, rig.actor, independent_direction())
    snapshot = rig.service.export(rig.nid, rig.scope, source['id'])
    board = rig.service.derive(rig.nid, rig.scope, rig.actor, source['id'], {
        'expected_version': source['version'], 'mode': 'STORYBOARD', 'shot_policy': 'DIRECTOR_NOTES'})
    reopened = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
    receipt = reopened.export(rig.nid, rig.scope, board['id'])
    assert reopened.get(rig.nid, rig.scope, board['id']) == board
    assert receipt['document'] == {key: value for key, value in board.items() if key != 'history'}
    assert 'history' not in receipt['document']
    assert board['status'] == 'DRAFT'
    assert board['source_documents'] == {source['id']: {
        'version': source['version'], 'digest': snapshot['document_digest']}}
    assert board['shots'][0]['director_note_ids'] == [source['director_notes'][0]['id']]
    assert board['provenance']['model_called'] is False
    edit = production_input(board)
    edit['title'] = 'Human reviewed shot draft'
    changed = reopened.update(rig.nid, rig.scope, rig.actor, board['id'], board['version'], edit)
    assert changed['version'] == 2 and changed['status'] == 'DRAFT'
    assert changed['source_documents'] == board['source_documents']
    assert reopened.get(rig.nid, rig.scope, source['id']) == source
    assert reopened.export(rig.nid, rig.scope, board['id'])['document'] == {key: value for key, value in changed.items() if key != 'history'}


def test_director_history_exact_digests_and_stale_storyboard_remain_gated(rig):
    """History projection adds receipts, never a bypass for stale derived documents."""
    import pytest
    from app.creative.service import CreativeService, document_digest
    from app.experimental.store import ExperimentalStore
    from app.experimental.common import StaleSourceError
    source = rig.service.create(rig.nid, rig.scope, rig.actor, independent_direction())
    original = rig.service.export(rig.nid, rig.scope, source['id'])
    board = rig.service.derive(rig.nid, rig.scope, rig.actor, source['id'], {
        'expected_version': 1, 'mode': 'STORYBOARD', 'shot_policy': 'DIRECTOR_NOTES'})
    edit = production_input(source)
    edit['director_notes'][0]['note'] = 'Turn after a deliberate pause'
    edited = rig.service.update(rig.nid, rig.scope, rig.actor, source['id'], 1, edit)
    reopened = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
    history = reopened.history(rig.nid, rig.scope, source['id'])
    assert history['current_version'] == 2
    assert history['snapshot_digests'] == [
        {'version': 1, 'digest': original['document_digest']},
        {'version': 2, 'digest': document_digest(edited)}]
    assert history['snapshot_digests'][0]['digest'] != history['snapshot_digests'][1]['digest']
    assert history['items'][0]['director_notes'][0]['note'] != history['items'][1]['director_notes'][0]['note']
    assert all('snapshot_digests' not in item for item in history['items'])
    assert board['id'] not in [row['id'] for row in reopened.list(rig.nid, rig.scope)]
    with pytest.raises(StaleSourceError):
        reopened.export(rig.nid, rig.scope, board['id'])
    assert reopened._raw(rig.nid, rig.scope, board['id'])['source_documents'][source['id']] == {
        'version': 1, 'digest': original['document_digest']}
    assert reopened.get(rig.nid, rig.scope, source['id']) == edited
