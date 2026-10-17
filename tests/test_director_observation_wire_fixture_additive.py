"""Capture genuine isolated-router JSON for the staged frontend decoder.

Uses original File owners and mocked provider wire, not a live provider.
Only writes within the owned pytest fixture directory.
"""
import json
import pytest
from creative_director_execution_fixture import lifecycle
from test_director_durable_pending_review import publish, prepare, review
from test_v2_independent_director_adoption import board, preview, review_body
from test_director_observation_transport_additive import mounted


pytestmark = pytest.mark.file_backend_only

def test_capture_real_router_wire_contract(lifecycle, tmp_path):
    e=board(lifecycle); preview(e); m=mounted(e)
    # Publish uses the original separate lifecycle helper on a fresh proposal;
    # capture this preview, then a second independent fixture source proposal.
    preview_response=m.client.get(m.url+'/status',headers=m.headers)
    assert preview_response.status_code==200
    e.row=e.documents.proposals.create(e.nid,e.scope,e.actor,
        {'source_document_id':e.source['id'],'expected_source_version':e.source['version']})
    _,terminal=publish(e); m=mounted(e)
    completed=m.client.get(m.url+'/status',headers=m.headers); assert completed.status_code==200
    candidate=prepare(e,terminal)
    pending=m.client.get(m.url+'/status',headers=m.headers); assert pending.status_code==200
    review(e,review_body(candidate))
    adopted=m.client.get(m.url+'/adopted-draft',headers=m.headers)
    status=m.client.get(m.url+'/status',headers=m.headers)
    assert adopted.status_code==status.status_code==200
    payload={'preview':preview_response.json(),'completed':completed.json(),'pending':pending.json(),
             'adopted':adopted.json(),'adopted_status':status.json()}
    path=tmp_path/'director-observation-wire.json'
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print('WIRE_CONTRACT_FIXTURE='+str(path))
