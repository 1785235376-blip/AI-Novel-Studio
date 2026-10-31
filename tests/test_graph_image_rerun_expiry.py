from datetime import datetime, timedelta, timezone
import pytest
from app.creative import graph_media_rerun as rerun
from test_studio_backend_integration_v2 import studio
from test_studio_asset_query import rig
from test_graph_binary_branch_actual import entry, graph_job
from test_graph_image_leaf_rerun import setup_graph, request

pytestmark = pytest.mark.file_backend_only


def ready(e):
    graph,saved,source=setup_graph(e)
    preview=graph.executor.preview_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],request(saved,source),lambda:None)
    row=graph.executor.create_image_leaf_rerun(e.nid,e.scope,e.actor,source['id'],
        {**request(saved,source),'request_id':'expiry-test','reviewed_impact_digest':preview['impact_digest']},lambda:None)
    row=graph.action(e.nid,e.scope,e.actor,row['id'],'execute',{'expected_version':row['version']})
    row=graph.media_runtime.preview(e.nid,e.scope,e.actor,row['id'],{'node_id':'second','expected_version':row['version']},lambda:None)
    row=graph.media_runtime.dispatch(e.nid,e.scope,e.actor,row['id'],{'node_id':'second','expected_version':row['version'],
        'reviewed_preview_digest':entry(row,'second')['preview']['preview_digest']},lambda:None)
    return graph,row,preview,graph_job(row,'second')


def clock(monkeypatch, expiry):
    state={'expired':False}
    class Controlled(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(expiry)+timedelta(seconds=1) if state['expired'] else datetime.now(tz)
    monkeypatch.setattr(rerun,'datetime',Controlled)
    return state


def execute(e,graph,row,job):
    return graph.media_runtime.execute_job(e.nid,e.scope,e.actor,row['id'],{'node_id':'second',
        'expected_version':row['version'],'expected_job_version':job['version'],
        'expected_request_digest':job['request_digest']},lambda:None)


def asset_ids(e):
    with e.workspace._asset_scope(e.nid,e.scope):
        return {item['id'] for item in e.workspace.assets.list(e.nid,actor_id=e.actor)}


def test_expired_before_send_does_not_reserve_or_call(studio,monkeypatch):
    e=studio;graph,row,preview,job=ready(e); before=len(e.calls)
    state=clock(monkeypatch,preview['expires_at']);state['expired']=True
    with pytest.raises(ValueError,match='CREATIVE_GRAPH_RERUN_PREVIEW_EXPIRED'):
        execute(e,graph,row,job)
    current=graph.get_run(e.nid,e.scope,e.actor,row['id'])
    assert current['version']==row['version'] and graph_job(current,'second')['status']=='QUEUED'
    assert len(e.calls)==before


@pytest.mark.parametrize('when', ['provider_return','asset_commit','after_final_guard'])
def test_expired_after_send_cannot_publish_or_repeat(studio,monkeypatch,when):
    e=studio;graph,row,preview,job=ready(e); before=len(e.calls); assets=asset_ids(e)
    state=clock(monkeypatch,preview['expires_at'])
    if when=='provider_return':
        generate=e.provider.generate
        def expire_after_send(req):
            result=generate(req);state['expired']=True;return result
        monkeypatch.setattr(e.provider,'generate',expire_after_send)
    elif when=='asset_commit':
        create=e.workspace.assets.create
        def expire_on_create(*args,**kwargs):
            state['expired']=True
            return create(*args,**kwargs)
        monkeypatch.setattr(e.workspace.assets,'create',expire_on_create)
    else:
        require=e.workspace.storage_admission.require
        def expire_after_check(size):
            result=require(size)
            if size==1: state['expired']=True
            return result
        monkeypatch.setattr(e.workspace.storage_admission,'require',expire_after_check)
    result=execute(e,graph,row,job)
    assert graph_job(result,'second')['status']=='UNKNOWN'
    assert graph_job(result,'second')['output_candidate'] is None
    assert asset_ids(e)==assets and len(e.calls)==before+1
    observed=graph.get_run(e.nid,e.scope,e.actor,row['id'])
    assert graph_job(observed,'second')['status']=='UNKNOWN'
    with pytest.raises(ValueError):
        execute(e,graph,observed,graph_job(observed,'second'))
    assert len(e.calls)==before+1 and asset_ids(e)==assets


def test_expired_before_review_cannot_promote_existing_candidate(studio,monkeypatch):
    e=studio;graph,row,preview,job=ready(e)
    row=execute(e,graph,row,job);job=graph_job(row,'second')
    assert job['status']=='AWAITING_REVIEW' and job['output_candidate'] is not None
    state=clock(monkeypatch,preview['expires_at']);state['expired']=True
    review={'node_id':'review_b','expected_version':row['version'],'expected_job_version':job['version'],
        'expected_request_digest':job['request_digest'],'reviewed_output_digest':job['output_candidate']['digest']}
    with pytest.raises(ValueError,match='CREATIVE_GRAPH_RERUN_PREVIEW_EXPIRED'):
        graph.media_runtime.review(e.nid,e.scope,e.actor,row['id'],review,lambda:None)
    visible=graph.get_run(e.nid,e.scope,e.actor,row['id'])
    assert visible['version']==row['version'] and graph_job(visible,'second')['status']=='AWAITING_REVIEW'
    with e.workspace._asset_scope(e.nid,e.scope):
        asset=e.workspace.assets.get(job['output_candidate']['id'],actor_id=e.actor)
        assert asset['_owner_actor_id']==e.actor
