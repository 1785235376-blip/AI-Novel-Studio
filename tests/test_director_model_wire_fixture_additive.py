"""Capture genuine versioned action responses for frontend contract tests."""
import json
import pytest
from creative_director_execution_fixture import lifecycle
from test_v2_independent_director_adoption import board,review_body
from test_director_observation_transport_additive import mounted
from test_director_model_transport_additive import completed

pytestmark=pytest.mark.file_backend_only


def test_capture_versioned_model_transport_json(lifecycle,tmp_path):
    e=board(lifecycle);m=mounted(e,actions=True)
    preview,status=completed(e,m)
    prepared=m.client.post(m.url+'/prepare-review',headers=m.headers,json={
        'expected_version':status['version'],'terminal_evidence_digest':status['terminal_evidence_digest']})
    assert prepared.status_code==200
    candidate=prepared.json()['receipt'];human=review_body(candidate)
    adopted=m.client.post(m.url+'/review',headers=m.headers,json=human)
    assert adopted.status_code==200
    document=e.documents.get(e.nid,e.scope,adopted.json()['receipt']['document']['document_id'])
    value={'preview':{'contract':'DIRECTOR_OBSERVATION_V1','project_id':e.nid,'scope':e.scope,'kind':'preview','receipt':preview},
           'pending':prepared.json(),'adopted':adopted.json(),'draft':document}
    path=tmp_path/'director-model-wire.json';path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('WIRE_CONTRACT_FIXTURE='+str(path))
