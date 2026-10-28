"""Two reviewed graph image nodes carry original on-disk bytes through File owners.

Both provider calls are deterministic stand-ins, not model inference.
"""
import base64
import hashlib
import json
from io import BytesIO

import pytest
from PIL import Image

from app.asset_providers import AssetGenerationResult
from app.creative.graph import CreativeGraphService
from test_studio_backend_integration_v2 import studio
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


def edge(name, source, output, target, input_port):
    return {'id': name, 'source_node_id': source, 'source_port': output,
            'target_node_id': target, 'target_port': input_port}


def entry(run, node):
    return next(item for item in run['media_runtime']['nodes'] if item['node_id'] == node)


def graph_job(run, node):
    execution = entry(run, node)['execution']
    return execution['job']


def test_reviewed_upstream_image_bytes_reach_downstream_edit(studio, monkeypatch):
    e = studio
    image = BytesIO(); Image.new('RGB', (64, 64), (220, 40, 30)).save(image, format='PNG')
    second_bytes = image.getvalue()
    seen = []
    def edit(request, *, operation, images, reference_weights, mask=None):
        assert operation == 'i2i' and reference_weights == [1.0] and mask is None
        request.dispatch_guard()
        assert len(images) == 1 and images[0].startswith('data:image/png;base64,')
        received = base64.b64decode(images[0].split(',', 1)[1], validate=True)
        seen.append(received)
        return AssetGenerationResult(request.provider_id, request.model_id,
            'data:image/png;base64,' + base64.b64encode(second_bytes).decode('ascii'))
    monkeypatch.setattr(e.provider, 'image_recipe_descriptor', {
        'recipe_id': 'automatic1111-img2img-v1', 'components': {'model': 'synthetic.safetensors'},
        'operations': ['t2i', 'i2i', 'inpaint'], 'reference_limit': 1,
        'reference_semantics': 'SINGLE_IMAGE_INITIALIZATION', 'mask_semantics': 'WHITE_KEEP_BLACK_REPAINT',
        'structural_only': True, 'inference_verified': False}, raising=False)
    monkeypatch.setattr(e.provider, 'generate_image', edit)
    graph = CreativeGraphService(e.workspace.store, e.workspace)
    graph.configure_media(e.production)
    params = {'provider_id': 'automatic1111', 'model_id': 'synthetic.safetensors',
              'parameters': {'width': 64, 'height': 64, 'steps': 1, 'seed': 7}}
    nodes = [
        {'id': 'text', 'definition_id': 'text_input', 'parameters': {'text': 'synthetic branch'}},
        {'id': 'prompt_a', 'definition_id': 'image_prompt'},
        {'id': 'prompt_b', 'definition_id': 'image_prompt'},
        {'id': 'first', 'definition_id': 'image_generate', 'parameters': {'operation_id': 'm5.image.t2i', **params}},
        {'id': 'review_a', 'definition_id': 'media_review'},
        {'id': 'second', 'definition_id': 'image_generate', 'parameters': {'operation_id': 'm5.image.i2i', **params, 'parameters': {'steps': 1, 'seed': 7}}},
        {'id': 'review_b', 'definition_id': 'media_review'},
    ]
    edges = [edge('a', 'text', 'text', 'prompt_a', 'text'), edge('b', 'text', 'text', 'prompt_b', 'text'),
        edge('c', 'prompt_a', 'prompt', 'first', 'prompt'), edge('d', 'first', 'candidate', 'review_a', 'candidate'),
        edge('e', 'review_a', 'asset', 'second', 'source'), edge('f', 'prompt_b', 'prompt', 'second', 'prompt'),
        edge('g', 'second', 'candidate', 'review_b', 'candidate')]
    saved = graph.create(e.nid, e.scope, e.actor, {'request_id': 'image-branch',
        'definition': {'schema_version': 4, 'title': 'Synthetic binary branch', 'nodes': nodes, 'edges': edges}})
    plan = graph.preflight(e.nid, e.scope, e.actor, saved['id'], {'expected_version': saved['version']})
    assert plan['executable'], plan
    order = plan['execution_order']
    assert order.index('first') < order.index('review_a') < order.index('second') < order.index('review_b')
    assert order.index('text') < order.index('prompt_a') and order.index('text') < order.index('prompt_b')
    run = graph.create_run(e.nid, e.scope, e.actor, saved['id'], {'expected_graph_version': saved['version'],
        'reviewed_preflight_digest': plan['preflight_digest'], 'request_id': 'image-branch-run'})
    run = graph.action(e.nid, e.scope, e.actor, run['id'], 'execute', {'expected_version': run['version']})
    assert run['current_node_id'] == 'first'
    def drive(run, node, review):
        rid = run['id']; rt = graph.media_runtime; guard = lambda: None
        run = rt.preview(e.nid, e.scope, e.actor, rid, {'node_id': node, 'expected_version': run['version']}, guard)
        pre = entry(run, node)['preview']
        run = rt.dispatch(e.nid, e.scope, e.actor, rid, {'node_id': node, 'expected_version': run['version'],
            'reviewed_preview_digest': pre['preview_digest']}, guard)
        job = graph_job(run, node)
        run = rt.execute_job(e.nid, e.scope, e.actor, rid, {'node_id': node, 'expected_version': run['version'],
            'expected_job_version': job['version'], 'expected_request_digest': job['request_digest']}, guard)
        job = graph_job(run, node)
        assert job['status'] == 'AWAITING_REVIEW' and run['current_node_id'] == review
        run = rt.review(e.nid, e.scope, e.actor, rid, {'node_id': review, 'expected_version': run['version'],
            'expected_job_version': job['version'], 'expected_request_digest': job['request_digest'],
            'reviewed_output_digest': job['output_candidate']['digest']}, guard)
        return run
    run = drive(run, 'first', 'review_a')
    saved_run = e.workspace.store.read(e.nid, e.scope)['collections'][graph.RUNS][run['id']]
    upstream = saved_run['typed_outputs']['review_a']['asset']
    content = e.workspace.assets._bin_path(upstream['asset_id']).read_bytes()
    metadata = json.loads(e.workspace.assets._meta_path(upstream['asset_id']).read_text(encoding='utf-8'))
    assert content == e.png and hashlib.sha256(content).hexdigest() == upstream['digest']
    assert metadata['version'] == upstream['version'] and metadata['sha256'] == upstream['digest']
    assert run['current_node_id'] == 'second'
    run = drive(run, 'second', 'review_b')
    assert seen == [content]
    stored = e.workspace.store.read(e.nid, e.scope)['collections'][graph.RUNS][run['id']]
    downstream_source = stored['media_previews']['second']['command']['source_snapshots'][0]
    assert (downstream_source['id'], downstream_source['version'], downstream_source['digest']) == (
        upstream['asset_id'], upstream['version'], upstream['digest'])
    output = stored['typed_outputs']['review_b']['asset']
    assert e.workspace.assets._bin_path(output['asset_id']).read_bytes() == second_bytes
    assert hashlib.sha256(second_bytes).hexdigest() == output['digest']
    assert graph.get_run(e.nid, e.scope, e.actor, run['id'])['status'] == run['status']
