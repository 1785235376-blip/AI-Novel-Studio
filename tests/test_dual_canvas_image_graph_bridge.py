"""Real File owners and validated PNGs; original synthetic Comfy transport, no inference."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.creative.graph import CreativeGraphService
from test_v2_independent_workspace import rig, reopened
from test_v2_manual_mask_owner import mask
from test_v2_image_runtime_owner import runtime
from test_v2_graph_image_nodes import graph_owner


def test_two_saved_cards_authored_graph_job_review_and_explicit_asset_return(mask, tmp_path, monkeypatch):
    e = mask
    _, adapter, production, wire, command = runtime(e, tmp_path, monkeypatch, 'reference', 'COMFYUI')
    owner = graph_owner(e, monkeypatch, production)
    fixture = json.loads((Path(__file__).parent / 'fixtures/dual_canvas_image_graph_plan.json').read_text(encoding='utf-8'))
    assert fixture['producer'] == 'buildCanvasImageGraphStarter'
    plan = fixture['plan']; value = deepcopy(plan['definition'])
    assert len(value['nodes']) == 7 and len(value['edges']) == 6
    cards = []
    for index, (source, snapshot) in enumerate(zip(plan['sources'], command['source_snapshots'], strict=True)):
        reference = {'asset_id': snapshot['id'], 'version': snapshot['version'], 'digest': snapshot['digest'], 'kind': 'image'}
        next(n for n in value['nodes'] if n['id'] == source['nodeId'])['parameters'] = reference
        cards.append({'id': source['cardId'], 'position': {'x': index * 280, 'y': 0}, 'asset': reference})
    board = owner.canvas_views.create(e.nid, e.scope, e.actor, {'request_id': 'dual-board', 'definition': {'title': 'Two real saved cards', 'cards': cards}})
    assert all(row['state'] == 'CURRENT_METADATA' for row in board['reference_states'])
    assert board['execution_authority'] is False and board['binary_content_verified'] is False
    generator = next(n for n in value['nodes'] if n['id'] == plan['generatorNodeId'])
    assert generator['parameters']['provider_id'] == generator['parameters']['model_id'] == ''
    # Explicit author configuration uses the existing synthetic local discovery fixture.
    generator['parameters'].update(provider_id=adapter.candidate['provider_id'], model_id=adapter.candidate['id'])
    assert generator['parameters']['allow_cloud'] is False
    graph = owner.create(e.nid, e.scope, e.actor, {'request_id': 'dual-graph', 'definition': value})
    value['title'] = 'Explicitly saved two-image author graph'
    graph = owner.save(e.nid, e.scope, e.actor, graph['id'], {'expected_version': graph['version'], 'definition': value})
    fresh = reopened(e); fresh_owner = CreativeGraphService(fresh.store, fresh)
    assert fresh_owner.get(e.nid, e.scope, e.actor, graph['id']) == graph
    assert fresh_owner.canvas_views.get(e.nid, e.scope, e.actor, board['id']) == board
    assert next(n for n in graph['definition']['nodes'] if n['id'] == plan['promptNodeId'])['parameters']['text'] == fixture['request']['prompt']
    assert all(row['state'] == 'CURRENT' for row in graph['reference_states'])
    assert wire.calls == []

    flight = owner.preflight(e.nid, e.scope, e.actor, graph['id'], {'expected_version': graph['version']})
    assert flight['executable'], flight['issues']
    run = owner.create_run(e.nid, e.scope, e.actor, graph['id'], {'expected_graph_version': graph['version'], 'reviewed_preflight_digest': flight['preflight_digest'], 'target_node_ids': flight['target_node_ids'], 'request_id': 'dual-run'})
    run = owner.action(e.nid, e.scope, e.actor, run['id'], 'execute', {'expected_version': run['version']})
    runtime_owner = owner.media_runtime; node_id = generator['id']
    run = runtime_owner.preview(e.nid, e.scope, e.actor, run['id'], {'expected_version': run['version'], 'node_id': node_id}, lambda: None)
    preview = run['media_runtime']['nodes'][0]['preview']
    assert preview['command']['prompt'] == fixture['request']['prompt']
    assert preview['command']['source_snapshots'] == [{**row, 'reference_only': True} for row in command['source_snapshots']]
    assert [r['weight'] for r in preview['command']['image_references']] == [.75, .5]
    assert [r['purpose'] for r in preview['command']['image_references']] == ['character', 'environment']
    assert wire.calls == []
    run = runtime_owner.dispatch(e.nid, e.scope, e.actor, run['id'], {'expected_version': run['version'], 'node_id': node_id, 'reviewed_preview_digest': preview['preview_digest']}, lambda: None)
    job = run['media_runtime']['nodes'][0]['execution']['job']
    run = runtime_owner.execute_job(e.nid, e.scope, e.actor, run['id'], {'expected_version': run['version'], 'node_id': node_id, 'expected_job_version': job['version'], 'expected_request_digest': job['request_digest']}, lambda: None)
    job = run['media_runtime']['nodes'][0]['execution']['job']; candidate = job['output_candidate']
    assert job['status'] == 'AWAITING_REVIEW'
    with pytest.raises(FileNotFoundError): fresh.asset(e.nid, e.scope, candidate['id'])
    before = deepcopy(e.raw_store.read(e.nid, e.scope))
    with pytest.raises((ValueError, FileNotFoundError)):
        owner.canvas_views.save(e.nid, e.scope, e.actor, board['id'], {'expected_version': board['version'], 'definition': {'title': 'Unreviewed candidate rejected', 'cards': cards + [{'id': 'Candidate', 'position': {'x': 560, 'y': 0}, 'asset': {'asset_id': candidate['id'], 'version': candidate['version'], 'digest': candidate['digest'], 'kind': 'image'}}]}})
    assert e.raw_store.read(e.nid, e.scope) == before
    review = next(n['id'] for n in value['nodes'] if n['definition_id'] == 'media_review')
    run = runtime_owner.review(e.nid, e.scope, e.actor, run['id'], {'expected_version': run['version'], 'node_id': review, 'expected_job_version': job['version'], 'expected_request_digest': job['request_digest'], 'reviewed_output_digest': candidate['digest']}, lambda: None)
    assert run['status'] == 'SUCCEEDED' and run['reviewed']
    formal = fresh.asset(e.nid, e.scope, candidate['id'])
    returned = owner.canvas_views.save(e.nid, e.scope, e.actor, board['id'], {'expected_version': board['version'], 'definition': {'title': 'Explicitly returned formal asset', 'cards': cards + [{'id': 'Approved', 'position': {'x': 560, 'y': 0}, 'asset': {'asset_id': formal['id'], 'version': formal['version'], 'digest': formal['sha256'], 'kind': 'image'}}]}})
    assert fresh_owner.canvas_views.get(e.nid, e.scope, e.actor, board['id']) == returned
    assert returned['definition']['cards'][:2] == board['definition']['cards']
    assert len(returned['definition']['cards']) == 3 and all(row['state'] == 'CURRENT_METADATA' for row in returned['reference_states'])
    assert fresh_owner.get(e.nid, e.scope, e.actor, graph['id']) == graph
    assert len([url for url, _ in wire.calls if url.endswith('/prompt')]) == 1
