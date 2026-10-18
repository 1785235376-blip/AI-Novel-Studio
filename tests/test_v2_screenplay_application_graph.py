"""Application TCP screenplay model-to-Graph loop; fixture provider, no browser."""
import json
import pytest
from creative_director_execution_fixture import lifecycle, wait
from test_director_application_host_additive import application_host
from test_v2_screenplay_private_preview import screenplay
from test_v2_screenplay_scene_contract import output
from test_director_model_transport_additive import preview_request

pytestmark=pytest.mark.file_backend_only


def screenplay_pending(e,m):
    e.wire_text=json.dumps(output(e.source,e.row))
    response=m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e))
    assert response.status_code==200,response.text
    p=response.json()['receipt'];assert p['source_mode']=='SCREENPLAY'
    result=m.client.post(m.url+'/dispatch',headers=m.headers,json={
        'expected_version':p['version'],'reviewed_preview_digest':p['reviewed_preview_digest']})
    assert result.status_code in (200,409),result.text
    assert len(e.manager.jobs)==1
    job=wait(e,next(iter(e.manager.jobs.values())))
    assert job.status=='COMPLETED' and job.terminal_hook_status=='COMPLETED'
    response=m.client.get(m.url+'/status',headers=m.headers)
    assert response.status_code==200,response.text
    status=response.json()['receipt']
    pending=m.client.post(m.url+'/prepare-review',headers=m.headers,json={
        'expected_version':status['version'],'terminal_evidence_digest':status['terminal_evidence_digest']})
    assert pending.status_code==200,pending.text
    assert pending.json()['receipt']['provenance']['source_mode']=='SCREENPLAY'
    return pending.json()['receipt']


def test_screenplay_original_application_graph_save_execution_and_reopen(application_host,monkeypatch):
    import test_director_application_graph_handoff as original
    e,m=application_host;screenplay(e)
    m.url=m.base+f'/{e.row["id"]}/model-v2'
    # Reuse every original graph/CAS/source-preservation/reopen assertion,
    # changing only the explicit source-specific HTTP preparation helper.
    monkeypatch.setattr(original,'pending',screenplay_pending)
    original.test_reviewed_director_pin_saves_and_reopens_over_actual_app((e,m),monkeypatch,True)
