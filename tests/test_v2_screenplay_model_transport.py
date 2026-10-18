"""Real mounted V2 HTTP over original File owners, mocked model wire only."""
import json
from copy import deepcopy
import pytest
from creative_director_execution_fixture import lifecycle, wait
from test_v2_screenplay_private_preview import screenplay
from test_v2_screenplay_scene_contract import output
from test_director_observation_transport_additive import mounted
from test_director_model_transport_additive import preview_request
from test_v2_independent_director_adoption import review_body, raw_bytes
from test_director_durable_pending_review import restart, fresh_host

pytestmark=pytest.mark.file_backend_only


def test_versioned_http_screenplay_review_and_reopen(lifecycle):
    e=screenplay(lifecycle); original=deepcopy(e.source); e.wire_text=json.dumps(output(e.source,e.row))
    m=mounted(e,actions=True); m.url=m.url.replace('/model-v1','/model-v2')
    first=m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e))
    assert first.status_code==200,first.text
    p=first.json()['receipt'];assert p['contract']=='DIRECTOR_SCREENPLAY_MODEL_PREVIEW_V2' and p['source_mode']=='SCREENPLAY'
    assert p['model_called'] is False and not e.requests
    assert 'host_principal' not in first.text and 'broker_decision' not in first.text
    before=raw_bytes(e); assert m.client.get(m.url+'/preview',headers=m.headers).json()==first.json()
    assert raw_bytes(e)==before
    dispatch_body={'expected_version':p['version'],'reviewed_preview_digest':p['reviewed_preview_digest']}
    dispatched=m.client.post(m.url+'/dispatch',headers=m.headers,json=dispatch_body)
    assert dispatched.status_code in (200,409),dispatched.text
    assert len(e.manager.jobs)==1
    job=wait(e,next(iter(e.manager.jobs.values())))
    assert job.status=='COMPLETED' and job.terminal_hook_status=='COMPLETED'
    status=m.client.get(m.url+'/status',headers=m.headers);assert status.status_code==200,status.text
    st=status.json()['receipt'];assert st['phase']=='COMPLETED'
    assert m.client.post(m.url+'/dispatch',headers=m.headers,json=dispatch_body).status_code==409
    restart(e);fresh_host(e);m=mounted(e,actions=True);m.url=m.url.replace('/model-v1','/model-v2')
    pending=m.client.post(m.url+'/prepare-review',headers=m.headers,json={'expected_version':st['version'],'terminal_evidence_digest':st['terminal_evidence_digest']})
    assert pending.status_code==200,pending.text
    candidate=pending.json()['receipt']; assert candidate['contract']=='DIRECTOR_SCREENPLAY_MODEL_PENDING_REVIEW_V2'
    assert candidate['provenance']['source_mode']=='SCREENPLAY'
    assert 'source_shot_id' not in pending.text and 'reservation_id' not in pending.text
    assert m.client.get(m.url+'/pending-review',headers=m.headers).json()==pending.json()
    human=review_body(candidate);human['director_notes'][0]['note']='HTTP human-reviewed screenplay'
    adopted=m.client.post(m.url+'/review',headers=m.headers,json=human)
    assert adopted.status_code==200,adopted.text
    receipt=adopted.json()['receipt'];assert receipt['document']['status']=='DRAFT'
    reopen=m.client.get(m.url+'/adopted-draft',headers=m.headers)
    assert reopen.status_code==200 and reopen.json()==adopted.json()
    assert len(e.requests)==len(e.broker.ledger(e.nid,e.scope,e.actor))==1
    draft=e.documents.get(e.nid,e.scope,receipt['document']['document_id'])
    assert draft['director_notes'][0]['note']==human['director_notes'][0]['note']
    (e.root/'screenplay-wire.json').write_text(json.dumps({'source':original,'preview':first.json(),
        'completed_status':status.json(),'pending':pending.json(),'submitted_review':human,
        'adopted':adopted.json(),'document':draft},ensure_ascii=False,indent=2)+'\n')


def test_v2_rejects_storyboard_and_missing_host_before_mutation(lifecycle):
    e=lifecycle;m=mounted(e,actions=True);m.url=m.url.replace('/model-v1','/model-v2');before=raw_bytes(e)
    response=m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e))
    assert response.status_code==409 and raw_bytes(e)==before and not e.requests
    e=screenplay(e);m=mounted(e,actions=True,host=False);m.url=m.url.replace('/model-v1','/model-v2')
    before=raw_bytes(e)
    assert m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e)).status_code in (403,409)
    assert raw_bytes(e)==before and not e.requests
