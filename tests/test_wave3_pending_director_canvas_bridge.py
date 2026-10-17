"""Private durable pending review → original DRAFT pin → saved Canvas File reopen.

Uses original File owners and the existing mocked adapter wire. No public
activation, graph execution, provider/network, UI or rendered-canvas claim.
"""
from copy import deepcopy
from uuid import uuid4

import pytest

from creative_director_execution_fixture import lifecycle, raw_proposal
from test_director_durable_pending_review import publish, prepare, read, review, restart, fresh_host
from test_v2_independent_director_adoption import board, review_body
from test_v2_independent_workspace import services

pytestmark = pytest.mark.file_backend_only


def test_private_pending_edited_draft_exact_pin_and_canvas_survive_file_restart(lifecycle):
    from app.creative.graph import CreativeGraphService
    from app.creative.graph_planning_nodes import execute_planning_local
    from app.creative.service import document_digest
    from app.experimental.common import StaleSourceError
    from app.experimental.model_broker import ModelBrokerService
    from app.repositories.file.generation import FileGenerationRepository
    from app.repositories.file.novel import FileNovelRepository
    from app.repository import FileRepository
    from app.services.generation_service import GenerationService

    e = board(lifecycle)
    source = deepcopy(e.source)
    job, prepare_body = publish(e)
    pending = prepare(e, prepare_body)
    assert raw_proposal(e)['status'] == 'INTERNAL_MODEL_PENDING_REVIEW'
    assert raw_proposal(e)['document_id'] is None
    assert len(e.requests) == 1

    # A new File-backed coordinator reads the persisted pending candidate; this
    # is not the old live-result adoption path or an in-memory candidate cache.
    restart(e)
    fresh_host(e)
    assert read(e) == pending
    jobs_before = deepcopy(e.persistence.load_all())
    ledger_before = deepcopy(e.broker.ledger(e.nid, e.scope, e.actor))
    assert [row['id'] for row in jobs_before] == [job.id]
    assert len(ledger_before) == 1
    human = review_body(pending)
    human['director_notes'][0]['note'] = 'Human review: hold before the visitor turns.'
    adopted = review(e, human)
    director = deepcopy(adopted['document'])
    assert adopted['proposal']['status'] == 'APPROVED'
    assert director['mode'] == 'DIRECTOR' and director['status'] == 'DRAFT'
    assert director['director_notes'] == human['director_notes']
    assert director['provenance']['terminal_evidence_digest'] == prepare_body['terminal_evidence_digest']
    assert director['source_documents'] == {source['id']: {
        'version': source['version'], 'digest': document_digest(source)}}
    proposal = deepcopy(raw_proposal(e))

    # Assemble the same original workspace owners used by existing Graph tests.
    workspace = services(e.root, 'file', '', e.novels, e.forbidden)
    owner = CreativeGraphService(workspace.store, workspace)
    assert owner.list(e.nid, e.scope, e.actor)['items'] == []
    pin = {'id': director['id'], 'version': director['version'], 'digest': document_digest(director)}
    graph = owner.create(e.nid, e.scope, e.actor, {
        'request_id': 'pending-reviewed-canvas-' + uuid4().hex,
        'definition': {'schema_version': 4, 'title': 'Explicit reviewed Director pin',
            'nodes': [{'id': 'director', 'definition_id': 'director_plan',
                       'parameters': {'document_snapshot': pin}}], 'edges': []}}, e.guard)
    layout = deepcopy(graph['definition'])
    layout['nodes'][0]['position'] = {'x': 336.0, 'y': 48.0}
    layout['viewport'] = {'x': 123.0, 'y': -45.0, 'zoom': 1.4}
    layout['presentation'] = {'comment': 'Human-reviewed direction, manually pinned.'}
    saved = owner.save(e.nid, e.scope, e.actor, graph['id'], {
        'expected_version': graph['version'], 'definition': layout}, e.guard)
    assert saved['version'] == graph['version'] + 1
    assert saved['definition'] == layout
    assert saved['definition_digest'] != graph['definition_digest']
    assert saved['execution_digest'] == graph['execution_digest']
    assert saved['reference_states'] == [{'node_id': 'director', 'state': 'CURRENT'}]
    assert owner.runs(e.nid, e.scope, e.actor, graph['id'])['items'] == []

    # The source Storyboard is an ancestor, not a Director-derived descendant.
    # Exercise the original pure planning adapter without admitting a GraphRun.
    direction = execute_planning_local(owner, e.nid, e.scope, layout['nodes'][0], {}, e.guard)
    source_node = {'id': 'original-source', 'definition_id': 'storyboard_plan', 'parameters': {
        'document_snapshot': {'id': source['id'], 'version': source['version'], 'digest': document_digest(source)}}}
    with pytest.raises(StaleSourceError, match='CREATIVE_GRAPH_STORYBOARD_DIRECTOR_BINDING_REQUIRED'):
        execute_planning_local(owner, e.nid, e.scope, source_node, direction, e.guard)
    assert owner.get(e.nid, e.scope, e.actor, graph['id']) == saved

    # Recreate repository, raw/Creative/workspace/asset/Graph owners, not just a
    # Graph service over the old in-memory workspace. No model runtime is wired.
    fresh_novels = FileNovelRepository(FileRepository(e.root))
    reopened = services(e.root, 'file', '', fresh_novels, e.forbidden)
    restored_owner = CreativeGraphService(reopened.store, reopened)
    restored = restored_owner.get(e.nid, e.scope, e.actor, graph['id'])
    assert restored == saved
    assert restored['definition']['nodes'][0]['parameters']['document_snapshot'] == pin
    assert reopened.creative.get(e.nid, e.scope, director['id']) == director
    assert reopened.creative.export(e.nid, e.scope, director['id'])['document_digest'] == pin['digest']
    assert reopened.creative.get(e.nid, e.scope, source['id']) == source
    assert reopened.store.read(e.nid, e.scope)['collections'][e.documents.proposals.COLLECTION][e.row['id']] == proposal
    assert restored_owner.list(e.nid, e.scope, e.actor)['items'] == [saved]
    assert restored_owner.runs(e.nid, e.scope, e.actor, graph['id'])['items'] == []
    assert reopened.store.read(e.nid, e.scope)['collections'].get(restored_owner.RUNS, {}) == {}
    fresh_jobs = GenerationService(FileGenerationRepository(e.root))
    fresh_broker = ModelBrokerService(reopened.creative.store.store, fresh_novels, e.forbidden, runtime=e.runtime)
    assert fresh_jobs.load_all() == jobs_before
    assert fresh_broker.ledger(e.nid, e.scope, e.actor) == ledger_before
    assert len(e.requests) == 1
