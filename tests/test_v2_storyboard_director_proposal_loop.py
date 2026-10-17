"""Saved STORYBOARD -> reviewed Director -> original Graph/File restart.

Rule-assisted mechanics only; no model inference, render, network or job dispatch.
Run through scripts/run_v2_checks.py with -m file_backend_only.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_v2_independent_workspace import rig, reopened, import_asset, asset_files, branch_scope
from test_v2_storyboard_workspace import board_value, content, configured, bind, approve


def source_value():
    value = board_value()
    value['shots'][0].update(shot_size='WIDE', camera_angle='HIGH_ANGLE', camera_motion='PAN',
                            duration_seconds=9, action='The visitor stops.', emotion='Hesitant',
                            composition='Door on the right', lens='35mm', color='Cold blue',
                            environment='Stone doorway', sound='Rain', sound_effect='Footstep',
                            dialogue=[{'speaker': 'visitor', 'text': 'Wait.', 'delivery': 'Quietly'}])
    value['shots'][1].update(shot_size='CLOSE_UP', camera_angle='LOW_ANGLE', camera_motion='STATIC',
                            duration_seconds=4, action='The visitor looks up.')
    # The original document owner, not the proposal adapter, owns normalization.
    value['shots'].reverse()
    return value


def create_pair(rig, value=None):
    creative = rig.service.creative
    source = creative.create(rig.nid, rig.scope, rig.actor, value or source_value())
    proposal = creative.proposals.create(rig.nid, rig.scope, rig.actor, {
        'source_document_id': source['id'], 'expected_source_version': source['version']})
    return source, proposal


def review_body(proposal):
    return {'expected_version': proposal['version'], 'reviewed_output_digest': proposal['output_digest'],
            'title': 'Human-reviewed storyboard direction', 'director_notes': deepcopy(proposal['director_notes'])}


def persisted(rig):
    """Read actual original File-owner bytes, not only public projections."""
    return rig.raw_store.path(rig.nid, rig.scope).read_bytes()


def test_saved_board_review_restart_pin_preserves_original_bytes_and_assets(rig, monkeypatch):
    from app.creative.graph import CreativeGraphService
    from app.creative.service import document_digest
    from app.creative.storyboard import storyboard_receipt
    from app.experimental.store import canonical
    creative, _ = configured(rig, monkeypatch)
    source = creative.create(rig.nid, rig.scope, rig.actor, source_value())
    asset = import_asset(rig, filename='storyboard-director-source.png')
    bind(creative, rig, source['id'], 'shot-1', asset)
    approved = approve(creative, rig, source['id'])
    source = creative.get(rig.nid, rig.scope, source['id'])
    before = json.loads(persisted(rig))['collections']
    source_bytes = canonical(before[creative.COLLECTION][source['id']]).encode()
    files_before = asset_files(rig)
    proposal = creative.proposals.create(rig.nid, rig.scope, rig.actor, {
        'source_document_id': source['id'], 'expected_source_version': source['version']})
    assert proposal['status'] == 'NEEDS_REVIEW'
    assert len(creative.list(rig.nid, rig.scope)) == 1
    assert proposal['provenance']['method'] == 'RULE_ASSISTED'
    assert proposal['provenance']['model_called'] is False
    assert proposal['provenance']['source_mode'] == 'STORYBOARD'
    assert proposal['model_preview'] is None and proposal['model_execution'] is None
    assert proposal['source_version'] == source['version']
    assert proposal['source_digest'] == document_digest(source)
    notes = proposal['director_notes']
    assert [n['number'] for n in notes] == [1, 2]
    assert [n['scene_id'] for n in notes] == ['scene-1', 'scene-1']
    for shot, note, evidence in zip(source['shots'], notes, proposal['provenance']['source_shots']):
        assert evidence['note_id'] == note['id']
        assert evidence['source_shot_id'] == shot['id'] and evidence['source_shot'] == shot
        assert evidence['source_number'] == note['number'] and evidence['scene_id'] == note['scene_id']
        for field in ('shot_size', 'camera_angle', 'camera_motion', 'duration_seconds', 'composition', 'lens', 'lighting'):
            assert note[field] == shot[field]
        assert note['note'] == shot['frame_prompt'] and note['shot_suggestion'] == shot['action']
        assert note['color_palette'] == shot['color']
        assert set(evidence['suggested_fields']) == {'pacing', 'blocking'}
        assert {'dialogue', 'continuity', 'environment', 'sound', 'sound_effect', 'director_notes'} <= set(evidence['retained_source_only_fields'])
    body = review_body(proposal)
    body['director_notes'][0]['note'] = 'Human edit: hold before entering.'
    body['director_notes'][1]['duration_seconds'] = 6
    accepted = creative.proposals.review(rig.nid, rig.scope, rig.actor, proposal['id'], body)
    director = accepted['document']
    assert director['status'] == 'DRAFT' and director['mode'] == 'DIRECTOR'
    assert director['id'] != source['id'] and director['shots'] == []
    assert director['source_documents'] == {source['id']: {'version': source['version'], 'digest': document_digest(source)}}
    assert director['provenance']['source_shots'] == proposal['provenance']['source_shots']
    assert director['director_notes'][0]['note'] == body['director_notes'][0]['note']
    assert director['director_notes'][1]['duration_seconds'] == 6
    owner = CreativeGraphService(rig.store, rig.service)
    assert owner.list(rig.nid, rig.scope, rig.actor)['items'] == []
    pin = {'id': director['id'], 'version': director['version'], 'digest': document_digest(director)}
    graph = owner.create(rig.nid, rig.scope, rig.actor, {
        'request_id': 'storyboard-director-pin-' + uuid4().hex,
        'definition': {'schema_version': 4, 'title': 'Human explicit pin', 'nodes': [
            {'id': 'director', 'definition_id': 'director_plan', 'parameters': {'document_snapshot': pin}}], 'edges': []}})
    workspace = reopened(rig)
    restored = CreativeGraphService(workspace.store, workspace)
    assert restored.get(rig.nid, rig.scope, rig.actor, graph['id'])['reference_states'][0]['state'] == 'CURRENT'
    assert restored.get(rig.nid, rig.scope, rig.actor, graph['id'])['definition']['nodes'][0]['parameters']['document_snapshot'] == pin
    assert workspace.creative.get(rig.nid, rig.scope, director['id']) == director
    assert workspace.creative.proposals.get(rig.nid, rig.scope, rig.actor, proposal['id']) == accepted['proposal']
    assert restored.runs(rig.nid, rig.scope, rig.actor, graph['id'])['items'] == []
    assert storyboard_receipt(workspace.creative.get(rig.nid, rig.scope, source['id'])) == approved
    after = json.loads(persisted(rig))['collections']
    assert canonical(after[creative.COLLECTION][source['id']]).encode() == source_bytes
    assert asset_files(rig) == files_before
    assert source.get('storyboard_video_bindings') is None
    # Every unrelated collection (including any media/job bookkeeping) is exact.
    for name in set(before) | set(after):
        if name not in {creative.COLLECTION, creative.proposals.COLLECTION, owner.GRAPHS}:
            assert before.get(name) == after.get(name)
    assert len(after[creative.COLLECTION]) == 2


@pytest.mark.parametrize('fault', ['version', 'digest', 'actor', 'scope', 'association', 'order', 'duplicate'])
def test_review_failures_have_no_persisted_side_effects(rig, fault):
    from app.services.v1_capability_service import CapabilityVersionConflict
    source, proposal = create_pair(rig)
    body = review_body(proposal)
    actor, scope = rig.actor, rig.scope
    if fault == 'version': body['expected_version'] += 1
    if fault == 'digest': body['reviewed_output_digest'] = '0' * 64
    if fault == 'actor': actor = 'another-actor'
    if fault == 'scope': scope = branch_scope(rig)
    if fault == 'association': body['director_notes'][0]['id'] = 'replacement-note'
    if fault == 'order': body['director_notes'].reverse()
    if fault == 'duplicate': body['director_notes'][1] = deepcopy(body['director_notes'][0])
    before = persisted(rig)
    with pytest.raises((ValueError, FileNotFoundError, CapabilityVersionConflict)):
        rig.service.creative.proposals.review(rig.nid, scope, actor, proposal['id'], body)
    assert persisted(rig) == before


@pytest.mark.parametrize('change', ['edit', 'archive'])
def test_stale_or_deleted_source_fails_closed_after_reopen(rig, change):
    from app.experimental.common import StaleSourceError
    source, proposal = create_pair(rig)
    creative = rig.service.creative
    if change == 'edit':
        value = content(source); value['shots'][0]['duration_seconds'] = 10
        creative.update(rig.nid, rig.scope, rig.actor, source['id'], source['version'], value)
    else:
        creative.archive(rig.nid, rig.scope, rig.actor, source['id'], source['version'])
    before = persisted(rig)
    proposals = reopened(rig).creative.proposals
    with pytest.raises((StaleSourceError, FileNotFoundError)):
        proposals.get(rig.nid, rig.scope, rig.actor, proposal['id'])
    with pytest.raises((StaleSourceError, FileNotFoundError)):
        proposals.review(rig.nid, rig.scope, rig.actor, proposal['id'], review_body(proposal))
    assert proposals.list(rig.nid, rig.scope, rig.actor) == []
    assert persisted(rig) == before


@pytest.mark.parametrize('terminal', ['cancel', 'approve'])
def test_terminal_review_never_duplicates_draft(rig, terminal):
    source, proposal = create_pair(rig)
    proposals = rig.service.creative.proposals
    if terminal == 'cancel':
        row = proposals.cancel(rig.nid, rig.scope, rig.actor, proposal['id'], {'expected_version': proposal['version']})
    else:
        row = proposals.review(rig.nid, rig.scope, rig.actor, proposal['id'], review_body(proposal))['proposal']
    before = persisted(rig)
    body = review_body(proposal); body['expected_version'] = row['version']
    with pytest.raises(ValueError, match='CREATIVE_PROPOSAL_NOT_REVIEWABLE'):
        proposals.review(rig.nid, rig.scope, rig.actor, proposal['id'], body)
    assert persisted(rig) == before
    assert len(rig.service.creative.list(rig.nid, rig.scope)) == (1 if terminal == 'cancel' else 2)


@pytest.mark.parametrize('field,length', [('frame_prompt', 8001), ('action', 8001), ('emotion', 2001)])
def test_oversized_authored_fields_reject_without_truncation_or_proposal(rig, field, length):
    value = source_value(); value['shots'][0][field] = 'x' * length
    creative = rig.service.creative
    source = creative.create(rig.nid, rig.scope, rig.actor, value)
    before = persisted(rig)
    with pytest.raises(ValueError, match='CREATIVE_PROPOSAL_STORYBOARD_FIELD_LIMIT'):
        creative.proposals.create(rig.nid, rig.scope, rig.actor, {
            'source_document_id': source['id'], 'expected_source_version': source['version']})
    assert persisted(rig) == before
    assert creative.get(rig.nid, rig.scope, source['id']) == source


def test_empty_board_and_wrong_create_version_have_no_proposal(rig):
    from app.services.v1_capability_service import CapabilityVersionConflict
    creative = rig.service.creative
    source = creative.create(rig.nid, rig.scope, rig.actor, board_value(shots=[]))
    before = persisted(rig)
    for version, error in [(1, ValueError), (2, CapabilityVersionConflict)]:
        with pytest.raises(error):
            creative.proposals.create(rig.nid, rig.scope, rig.actor, {
                'source_document_id': source['id'], 'expected_source_version': version})
    assert persisted(rig) == before


def test_mapping_preserves_surrounding_whitespace_exactly():
    from app.creative.proposals import DirectorProposalService
    value = source_value(); value['shots'][0]['frame_prompt'] = ' surrounding whitespace '
    notes, associations = DirectorProposalService._storyboard_notes(value)
    assert notes[1]['note'] == ' surrounding whitespace '
    assert associations[1]['source_shot']['frame_prompt'] == ' surrounding whitespace '


@pytest.mark.parametrize('operation', ['preview', 'dispatch'])
def test_storyboard_model_admission_denied_before_any_broker_preparer_manager_work(rig, monkeypatch, operation):
    from app.creative.generation import DirectorModelCoordinator, REQUIRED_FLAGS
    source, proposal = create_pair(rig)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(REQUIRED_FLAGS))
    class Forbidden:
        def __getattr__(self, name):
            raise AssertionError('Storyboard model admission touched downstream owner: ' + name)
    coordinator = DirectorModelCoordinator(rig.service.creative.proposals, Forbidden(), Forbidden(), Forbidden())
    ctx = SimpleNamespace(novel_id=rig.nid, scope=rig.scope, actor=rig.actor)
    body = {'expected_version': proposal['version']}
    body.update({'route_id': 'unused-local-route'} if operation == 'preview' else {'reviewed_preview_digest': '0' * 64})
    before = persisted(rig)
    with pytest.raises(ValueError, match='CREATIVE_MODEL_SCREENPLAY_SOURCE_REQUIRED'):
        getattr(coordinator, operation)(ctx, proposal['id'], body, lambda: None)
    assert persisted(rig) == before
