"""Real original File owner screenplay→review→director→graph and restart loop.

This checks manual workflow/persistence only: no models, media execution, project
retirement, session changes or lifecycle candidate tests are involved.
"""
from copy import deepcopy
from uuid import uuid4

from test_v2_independent_workspace import rig, reopened


def test_reviewed_director_draft_pins_and_reopens_with_original_graph_owner(rig):
    from app.creative.graph import CreativeGraphService
    from app.creative.service import document_digest

    creative = rig.service.creative
    source = creative.create(rig.nid, rig.scope, rig.actor, {
        'mode': 'SCREENPLAY', 'title': 'Synthetic original screenplay', 'source_independent': True,
        'scenes': [{'id': 'scene-one', 'sequence': 1, 'heading': 'EXT. HARBOR - MORNING',
                    'action': 'The visitor stops before the gate.'}]})
    suggestion = creative.proposals.create(rig.nid, rig.scope, rig.actor, {
        'source_document_id': source['id'], 'expected_source_version': source['version']})
    assert suggestion['status'] == 'NEEDS_REVIEW'
    assert [row['id'] for row in creative.list(rig.nid, rig.scope)] == [source['id']]
    notes = deepcopy(suggestion['director_notes'])
    notes[0]['note'] = 'Human reviewed: hold the pause before the turn.'
    accepted = creative.proposals.review(rig.nid, rig.scope, rig.actor, suggestion['id'], {
        'expected_version': suggestion['version'], 'reviewed_output_digest': suggestion['output_digest'],
        'title': 'Human-reviewed original director', 'director_notes': notes})
    director = accepted['document']
    assert accepted['proposal']['status'] == 'APPROVED' and director['status'] == 'DRAFT'
    assert director['provenance']['model_called'] is False
    assert director['source_documents'] == {source['id']: {'version': source['version'], 'digest': document_digest(source)}}
    owner = CreativeGraphService(rig.store, rig.service)
    assert owner.list(rig.nid, rig.scope, rig.actor)['items'] == []
    pin = {'id': director['id'], 'version': director['version'], 'digest': document_digest(director)}
    graph = owner.create(rig.nid, rig.scope, rig.actor, {
        'request_id': 'review-pin-' + uuid4().hex,
        'definition': {'schema_version': 4, 'title': 'Explicit human pin', 'nodes': [
            {'id': 'director', 'definition_id': 'director_plan', 'parameters': {'document_snapshot': pin}}], 'edges': []}})
    workspace = reopened(rig)
    restored_owner = CreativeGraphService(workspace.store, workspace)
    restored_graph = restored_owner.get(rig.nid, rig.scope, rig.actor, graph['id'])
    restored_proposal = workspace.creative.proposals.get(rig.nid, rig.scope, rig.actor, suggestion['id'])
    restored_director = workspace.creative.get(rig.nid, rig.scope, restored_proposal['document_id'])
    assert restored_graph['version'] == 1 and restored_graph['definition']['nodes'][0]['parameters']['document_snapshot'] == pin
    assert restored_graph['reference_states'][0]['state'] == 'CURRENT'
    assert restored_director == director and restored_director['status'] == 'DRAFT'
    assert restored_proposal['document_id'] == director['id']
    assert workspace.creative.export(rig.nid, rig.scope, director['id'])['document_digest'] == pin['digest']
    assert restored_owner.runs(rig.nid, rig.scope, rig.actor, graph['id'])['items'] == []
    assert workspace.creative.get(rig.nid, rig.scope, source['id']) == source
    assert len(workspace.creative.list(rig.nid, rig.scope)) == 2
