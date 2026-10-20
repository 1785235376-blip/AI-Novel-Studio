"""Original File Graph/Job/Review with synthetic Comfy HTTP; no real inference or batch scheduler."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, reopened
from test_v2_graph_image_nodes import graph_owner
from test_v2_image_discovery_capabilities import enabled
from test_v2_discovered_image_production import owner as production_owner
from test_v2_image_provider_recipes import Transport

def fixture(e, tmp_path, monkeypatch):
    _, registry, adapter, _ = enabled(tmp_path, 'sdxl-fixture.safetensors', 'COMFYUI')
    production = production_owner(registry, monkeypatch, e); wire = Transport(); adapter.delegate.transport = wire
    owner = graph_owner(e, monkeypatch, production)
    source = json.loads((Path(__file__).parent / 'fixtures/text_image_output_graph_plan.json').read_text(encoding='utf-8'))
    assert source['producer'] == 'buildImageOutputStarter'
    plan = source['two']['plan']; value = deepcopy(plan['definition'])
    assert plan['count'] == 2 and len(value['nodes']) == 8 and len(value['edges']) == 6
    for node in value['nodes']:
        if node['definition_id'] == 'image_generate':
            assert node['parameters']['provider_id'] == node['parameters']['model_id'] == '' and node['parameters']['allow_cloud'] is False
            node['parameters'].update(provider_id=adapter.candidate['provider_id'], model_id=adapter.candidate['id'])
    graph = owner.create(e.nid, e.scope, e.actor, {'request_id': 'text-images', 'definition': value})
    value['title'] = '明确保存的作者产物草稿'
    graph = owner.save(e.nid, e.scope, e.actor, graph['id'], {'expected_version': graph['version'], 'definition': value})
    from app.creative.graph import CreativeGraphService
    fresh = reopened(e); assert CreativeGraphService(fresh.store, fresh).get(e.nid, e.scope, e.actor, graph['id']) == graph
    flight = owner.preflight(e.nid, e.scope, e.actor, graph['id'], {'expected_version': graph['version'], 'target_node_ids': []})
    assert flight['executable'], flight['issues']
    assert set(flight['target_node_ids']) == {node['id'] for node in graph['definition']['nodes']}
    run = owner.create_run(e.nid, e.scope, e.actor, graph['id'], {'expected_graph_version': graph['version'], 'reviewed_preflight_digest': flight['preflight_digest'], 'target_node_ids': flight['target_node_ids'], 'request_id': 'text-images-run'})
    assert wire.calls == []
    return owner, wire, graph, run, plan

def prepare(e, owner, run, output):
    if run['node_states'][output['generatorNodeId']]['status'] == 'PENDING':
        run = owner.action(e.nid, e.scope, e.actor, run['id'], 'execute', {'expected_version': run['version']})
    runtime = owner.media_runtime
    run = runtime.preview(e.nid, e.scope, e.actor, run['id'], {'expected_version': run['version'], 'node_id': output['generatorNodeId']}, lambda: None)
    preview = next(row for row in run['media_runtime']['nodes'] if row['node_id'] == output['generatorNodeId'])['preview']
    assert preview['command']['prompt'] == output['prompt'] and preview['command']['source_snapshots'] == []
    assert preview['command']['allow_cloud'] is False
    return run, preview

def dispatch(e, owner, run, output, preview):
    return owner.media_runtime.dispatch(e.nid, e.scope, e.actor, run['id'], {'expected_version': run['version'], 'node_id': output['generatorNodeId'], 'reviewed_preview_digest': preview['preview_digest']}, lambda: None)

def execution(run, output):return next(row for row in run['media_runtime']['nodes'] if row['node_id'] == output['generatorNodeId'])['execution']
def action(run, output):
    job = execution(run, output)['job']
    return {'expected_version': run['version'], 'node_id': output['generatorNodeId'], 'expected_job_version': job['version'], 'expected_request_digest': job['request_digest']}
def posts(wire):return [row for row in wire.calls if row[0].endswith('/prompt')]

@pytest.mark.parametrize('scenario', ['complete', 'cancel', 'unknown', 'source-change'])
def test_text_outputs_original_budget_review_cancel_unknown_and_version_pin(rig, tmp_path, monkeypatch, scenario):
    e = rig; owner, wire, graph, run, plan = fixture(e, tmp_path, monkeypatch); outputs = plan['outputs']; first = outputs[0]
    run, preview = prepare(e, owner, run, first)
    assert not posts(wire)
    if scenario == 'source-change':
        changed = deepcopy(graph['definition']); next(node for node in changed['nodes'] if node['id'] == first['inputNodeId'])['parameters']['text'] = '作者已经修改来源文字'
        owner.save(e.nid, e.scope, e.actor, graph['id'], {'expected_version': graph['version'], 'definition': changed})
        with pytest.raises((ValueError, StaleSourceError)):dispatch(e, owner, run, first, preview)
        assert not owner._owned(e.nid, e.scope, e.actor, owner.RUNS, run['id']).get('media_executions') and not posts(wire)
        return
    run = dispatch(e, owner, run, first, preview)
    original_job = execution(run, first)['job']['id']; assert not posts(wire)
    if scenario == 'cancel':
        queued_evidence = action(run, first)
        run = owner.action(e.nid, e.scope, e.actor, run['id'], 'cancel', {'expected_version': run['version']})
        assert run['status'] == 'CANCELLED'
        with pytest.raises((ValueError, StaleSourceError)):owner.media_runtime.execute_job(e.nid, e.scope, e.actor, run['id'], {**queued_evidence, 'expected_version': run['version']}, lambda: None)
        raw = owner._owned(e.nid, e.scope, e.actor, owner.RUNS, run['id'])
        assert list(raw['media_executions']) == [first['generatorNodeId']] and not posts(wire)
        assert execution(run, first)['job'] is None
        persisted = next(row for row in owner.media_runtime.production._image(e.actor)._load(e.nid, None) if row['id'] == original_job)
        assert persisted['status'] == 'CANCELLED' and persisted['output_asset_id'] is None
        assert 'dispatch_started' not in persisted and 'dispatch_intent_at' not in persisted
        return
    if scenario == 'unknown':
        original_post = wire.post
        def lost_reply(url, **kwargs):
            result = original_post(url, **kwargs)
            if url.endswith('/prompt'):raise TimeoutError('synthetic accepted request with lost reply')
            return result
        monkeypatch.setattr(wire, 'post', lost_reply)
        run = owner.media_runtime.execute_job(e.nid, e.scope, e.actor, run['id'], action(run, first), lambda: None)
        row = execution(run, first)
        assert row['job']['status'] == 'UNKNOWN' and row['send_reserved'] is True and len(posts(wire)) == 1
        assert row['job']['error_code'] and row['job']['output_candidate'] is None
        with pytest.raises(ValueError):owner.media_runtime.execute_job(e.nid, e.scope, e.actor, run['id'], action(run, first), lambda: None)
        with pytest.raises(ValueError):owner.media_runtime.preview(e.nid, e.scope, e.actor, run['id'], {'expected_version': run['version'], 'node_id': outputs[1]['generatorNodeId']}, lambda: None)
        owner.get_run(e.nid, e.scope, e.actor, run['id'], reconcile=False)
        assert len(posts(wire)) == 1 and list(owner._owned(e.nid, e.scope, e.actor, owner.RUNS, run['id'])['media_executions']) == [first['generatorNodeId']]
        return
    jobs, assets, candidates = [], [], {}
    for index, output in enumerate(outputs):
        if index:
            run, preview = prepare(e, owner, run, output); run = dispatch(e, owner, run, output, preview)
        run = owner.media_runtime.execute_job(e.nid, e.scope, e.actor, run['id'], action(run, output), lambda: None)
        job = execution(run, output)['job']; candidate = job['output_candidate']; jobs.append(job['id'])
        assert job['status'] == 'AWAITING_REVIEW' and len(posts(wire)) == index + 1
        with pytest.raises(FileNotFoundError):e.service.asset(e.nid, e.scope, candidate['id'])
        candidates[output['reviewNodeId']] = candidate
    # Original executor drives remaining computational branches before selecting
    # human approvals. Follow its current review node, never invent a scheduler.
    assert run['status'] == 'WAITING_APPROVAL' and len(posts(wire)) == 2
    for _ in outputs:
        output = next(row for row in outputs if row['reviewNodeId'] == run['current_node_id'])
        candidate = candidates[output['reviewNodeId']]
        run = owner.media_runtime.review(e.nid, e.scope, e.actor, run['id'], {**action(run, output), 'node_id': output['reviewNodeId'], 'reviewed_output_digest': candidate['digest']}, lambda: None)
        assets.append(e.service.asset(e.nid, e.scope, candidate['id']))
    assert run['status'] == 'SUCCEEDED' and len(set(jobs)) == len({row['id'] for row in assets}) == len(posts(wire)) == 2
    raw = owner._owned(e.nid, e.scope, e.actor, owner.RUNS, run['id'])
    assert set(raw['media_executions']) == {row['generatorNodeId'] for row in outputs}
    assert all(run['node_states'][row['reviewNodeId']]['status'] == 'SUCCEEDED' for row in outputs)
    (tmp_path/'text-image-complete-receipt.json').write_text(json.dumps({'graph_id': graph['id'], 'graph_version': graph['version'], 'run_id': run['id'], 'status': run['status'], 'original_job_ids': jobs, 'formal_asset_ids': [row['id'] for row in assets], 'prompt_posts': len(posts(wire)), 'transport': 'EXISTING_SYNTHETIC_COMFY_ONLY'}, indent=2)+'\n', encoding='utf-8')
