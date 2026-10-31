"""Explicit rerun reuses only local inputs from an approved original run."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest

from app.creative.graph import CreativeGraphService
from test_studio_backend_integration_v2 import studio
from test_studio_asset_query import rig
from test_graph_binary_branch_actual import edge, entry, graph_job

pytestmark = pytest.mark.file_backend_only


def setup_graph(e, fail_first=False):
    graph = CreativeGraphService(e.workspace.store, e.workspace)
    graph.configure_media(e.production)
    params = {'provider_id': 'automatic1111', 'model_id': 'synthetic.safetensors',
              'operation_id': 'm5.image.t2i', 'parameters': {'width': 64, 'height': 64, 'steps': 1, 'seed': 7}}
    nodes = [{'id': 'text', 'definition_id': 'text_input', 'parameters': {'text': 'synthetic'}},
        {'id': 'prompt_a', 'definition_id': 'image_prompt'}, {'id': 'prompt_b', 'definition_id': 'image_prompt'},
        {'id': 'first', 'definition_id': 'image_generate', 'parameters': params}, {'id': 'review_a', 'definition_id': 'media_review'},
        {'id': 'second', 'definition_id': 'image_generate', 'parameters': params}, {'id': 'review_b', 'definition_id': 'media_review'}]
    edges = [edge('a', 'text', 'text', 'prompt_a', 'text'), edge('b', 'text', 'text', 'prompt_b', 'text'),
        edge('c', 'prompt_a', 'prompt', 'first', 'prompt'), edge('d', 'first', 'candidate', 'review_a', 'candidate'),
        edge('e', 'prompt_b', 'prompt', 'second', 'prompt'), edge('f', 'second', 'candidate', 'review_b', 'candidate')]
    import base64
    with e.workspace._asset_scope(e.nid, e.scope):
        a = e.workspace.assets.create(e.nid, 'isolated-branch.png', base64.b64encode(e.png).decode(), 'image/png', 'image', required_features=('narrative_production_v2',))
    e.unrelated = a
    nodes.append({'id':'isolated_asset','definition_id':'asset_reference','parameters':{'asset_id':a['id'],'version':a['version'],'digest':a['sha256'],'kind':'image'}})
    saved = graph.create(e.nid, e.scope, e.actor, {'request_id': 'rerun-source-graph',
        'definition': {'schema_version': 4, 'title': 'two image branches', 'nodes': nodes, 'edges': edges}})
    plan = graph.preflight(e.nid, e.scope, e.actor, saved['id'], {'expected_version': saved['version']})
    assert plan['executable'], plan
    run = graph.create_run(e.nid, e.scope, e.actor, saved['id'], {'expected_graph_version': saved['version'],
        'reviewed_preflight_digest': plan['preflight_digest'], 'request_id': 'rerun-source'})
    run = graph.action(e.nid, e.scope, e.actor, run['id'], 'execute', {'expected_version': run['version']})
    review_nodes = {'review_a': 'first', 'review_b': 'second'}
    while run['status'] != 'SUCCEEDED':
        current = run['current_node_id']
        if current in ('first', 'second'):
            node = current
            run = graph.media_runtime.preview(e.nid, e.scope, e.actor, run['id'], {'node_id': node, 'expected_version': run['version']}, lambda: None)
            run = graph.media_runtime.dispatch(e.nid, e.scope, e.actor, run['id'], {'node_id': node, 'expected_version': run['version'],
                'reviewed_preview_digest': entry(run, node)['preview']['preview_digest']}, lambda: None)
            job = graph_job(run, node)
            run = graph.media_runtime.execute_job(e.nid, e.scope, e.actor, run['id'], {'node_id': node, 'expected_version': run['version'],
                'expected_job_version': job['version'], 'expected_request_digest': job['request_digest']}, lambda: None)
            if fail_first:
                return graph, saved, run
        else:
            assert current in review_nodes, current
            job = graph_job(run, review_nodes[current])
            run = graph.media_runtime.review(e.nid, e.scope, e.actor, run['id'], {'node_id': current, 'expected_version': run['version'],
                'expected_job_version': job['version'], 'expected_request_digest': job['request_digest'],
                'reviewed_output_digest': job['output_candidate']['digest']}, lambda: None)
    assert run['status'] == 'SUCCEEDED'
    return graph, saved, run


def request(saved, source):
    return {'expected_version': source['version'], 'expected_graph_version': saved['version'], 'node_id': 'second'}


def test_explicit_leaf_rerun_does_not_dispatch_or_include_other_branch(studio, monkeypatch):
    e=studio; graph,saved,source=setup_graph(e); calls=len(e.calls)
    preview=graph.executor.preview_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],request(saved,source),lambda:None)
    assert preview['affected_node_ids'] == ['second','review_b']
    assert set(preview['selected_closure']) == {'text','prompt_b','second','review_b'}
    assert not preview['automatic_dispatch'] and not preview['media_output_reused']
    created=graph.executor.create_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],
        {**request(saved,source),'request_id':'explicit-rerun','reviewed_impact_digest':preview['impact_digest']},lambda:None)
    assert created['status']=='QUEUED' and len(e.calls)==calls
    same=graph.executor.create_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],
        {**request(saved,source),'request_id':'explicit-rerun','reviewed_impact_digest':preview['impact_digest']},lambda:None)
    assert same['id']==created['id']
    created=graph.action(e.nid,e.scope,e.actor,created['id'],'execute',{'expected_version':created['version']})
    assert created['current_node_id']=='second' and len(e.calls)==calls
    assert set(created['node_states'])=={'text','prompt_b','second','review_b'}
    created=graph.media_runtime.preview(e.nid,e.scope,e.actor,created['id'],{'node_id':'second','expected_version':created['version']},lambda:None)
    created=graph.media_runtime.dispatch(e.nid,e.scope,e.actor,created['id'],{'node_id':'second','expected_version':created['version'],
        'reviewed_preview_digest':entry(created,'second')['preview']['preview_digest']},lambda:None)
    job=graph_job(created,'second')
    provider_errors=[]
    real_generate=e.provider.generate
    def traced_generate(req):
        try: return real_generate(req)
        except Exception as error:
            provider_errors.append(repr(error))
            raise
    monkeypatch.setattr(e.provider,'generate',traced_generate)
    real_callbacks=e.production._callbacks
    def traced_callbacks(*args, **kwargs):
        publish, promote=real_callbacks(*args, **kwargs)
        def traced_publish(*a, **k):
            try: return publish(*a, **k)
            except Exception as error:
                provider_errors.append('publish: '+repr(error))
                raise
        return traced_publish, promote
    monkeypatch.setattr(e.production,'_callbacks',traced_callbacks)
    created=graph.media_runtime.execute_job(e.nid,e.scope,e.actor,created['id'],{'node_id':'second','expected_version':created['version'],
        'expected_job_version':job['version'],'expected_request_digest':job['request_digest']},lambda:None)
    job=graph_job(created,'second')
    assert job['output_candidate'] is not None, (job, provider_errors, len(e.calls)-calls)
    created=graph.media_runtime.review(e.nid,e.scope,e.actor,created['id'],{'node_id':'review_b','expected_version':created['version'],
        'expected_job_version':job['version'],'expected_request_digest':job['request_digest'],
        'reviewed_output_digest':job['output_candidate']['digest']},lambda:None)
    assert created['status']=='SUCCEEDED' and len(e.calls)==calls+1
    assert graph.get_run(e.nid,e.scope,e.actor,source['id'])['version']==source['version']


def test_changed_reconstructed_input_stops_before_media(studio, monkeypatch):
    e=studio;graph,saved,source=setup_graph(e); calls=len(e.calls)
    preview=graph.executor.preview_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],request(saved,source),lambda:None)
    created=graph.executor.create_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],
        {**request(saved,source),'request_id':'different-input','reviewed_impact_digest':preview['impact_digest']},lambda:None)
    original=graph.executor.adapter.execute
    def changed(req):
        if req.node_type=='text_input': return {'text':'changed'}
        return original(req)
    monkeypatch.setattr(graph.executor.adapter,'execute',changed)
    with pytest.raises(Exception,match='CREATIVE_GRAPH_RERUN_LOCAL_INPUT_CHANGED'):
        graph.action(e.nid,e.scope,e.actor,created['id'],'execute',{'expected_version':created['version']})
    assert len(e.calls)==calls


def test_denied_revoked_expired_and_changed_preview_do_not_create(studio, monkeypatch):
    from app.creative import graph_media_rerun as rerun
    e=studio;graph,saved,source=setup_graph(e); request_body=request(saved,source)
    preview=graph.executor.preview_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],request_body,lambda:None)
    body={**request_body,'request_id':'blocked','reviewed_impact_digest':preview['impact_digest']}
    before=deepcopy(e.workspace.store.read(e.nid,e.scope))
    with pytest.raises(Exception):
        graph.executor.create_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],{**body,'reviewed_impact_digest':'0'*64},lambda:None)
    def revoked(): raise PermissionError('synthetic revocation')
    with pytest.raises(PermissionError): graph.executor.create_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],body,revoked)
    class Expired(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.fromisoformat(preview['expires_at']) + timedelta(seconds=1)
    monkeypatch.setattr(rerun,'datetime',Expired)
    with pytest.raises(Exception, match='CREATIVE_GRAPH_RERUN_PREVIEW_EXPIRED'):
        graph.executor.create_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],body,lambda:None)
    assert e.workspace.store.read(e.nid,e.scope)==before


def test_unknown_source_is_not_rerun(studio, monkeypatch):
    e=studio
    def lost(request):
        request.dispatch_guard(); e.calls.append(request); raise RuntimeError('synthetic lost reply')
    monkeypatch.setattr(e.provider,'generate',lost)
    graph,saved,source=setup_graph(e,fail_first=True)
    assert graph_job(source,'first')['status']=='UNKNOWN'
    with pytest.raises(ValueError,match='CREATIVE_GRAPH_RERUN_COMPLETED_IMAGE_SOURCE_REQUIRED'):
        graph.executor.preview_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],request(saved,source),lambda:None)
    assert len(e.calls)==1


def test_audit_publication_after_source_run_other_asset_revoked(studio, monkeypatch):
    import base64
    from app.asset_providers import AssetGenerationResult
    e=studio;graph,saved,source=setup_graph(e)
    pre=graph.executor.preview_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],request(saved,source),lambda:None)
    run=graph.executor.create_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],{**request(saved,source),'request_id':'audit','reviewed_impact_digest':pre['impact_digest']},lambda:None)
    run=graph.action(e.nid,e.scope,e.actor,run['id'],'execute',{'expected_version':run['version']})
    run=graph.media_runtime.preview(e.nid,e.scope,e.actor,run['id'],{'node_id':'second','expected_version':run['version']},lambda:None)
    run=graph.media_runtime.dispatch(e.nid,e.scope,e.actor,run['id'],{'node_id':'second','expected_version':run['version'],'reviewed_preview_digest':entry(run,'second')['preview']['preview_digest']},lambda:None)
    job=graph_job(run,'second')
    with e.workspace._asset_scope(e.nid,e.scope):
        before = {a['id'] for a in e.workspace.assets.list(e.nid,actor_id=e.actor)}
    def changed_after_send(req):
        req.dispatch_guard()
        with e.workspace._asset_scope(e.nid,e.scope):
            e.workspace.assets.delete(e.unrelated['id'])
        return AssetGenerationResult(req.provider_id,req.model_id,'data:image/png;base64,'+base64.b64encode(e.png).decode())
    monkeypatch.setattr(e.provider,'generate',changed_after_send)
    try:
        graph.media_runtime.execute_job(e.nid,e.scope,e.actor,run['id'],{'node_id':'second','expected_version':run['version'],'expected_job_version':job['version'],'expected_request_digest':job['request_digest']},lambda:None)
    except Exception as exc:
        print('raised=',type(exc).__name__,str(exc))
    with e.workspace._asset_scope(e.nid,e.scope):
        after={a['id'] for a in e.workspace.assets.list(e.nid,actor_id=e.actor)}
    print('new_assets=', after-before)
    assert not (after-before), 'source changed before candidate publication'
