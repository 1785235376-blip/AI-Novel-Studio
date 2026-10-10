import pytest
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_broker_mounted import broker_app, quote, author_body, wait_ledger

@pytest.mark.parametrize('off', ['disabled','v1'])
def test_audit_broker_job_cannot_be_accepted_through_legacy_route_when_off(broker_app, monkeypatch, off):
    e=broker_app
    selected=quote(e); body=author_body(e)
    preview=checked(e.client.post(e.base+'/author-context/preview',headers=e.headers,json=body))
    generated=checked(e.client.post(e.base+'/model-broker/generate',headers=e.headers,json={'preview_id':selected['id'],'expected_version':selected['version'],'request_id':'audit-off','author':{**body,'preview_digest':preview['preview_digest']}}),202)
    state=wait_ledger(e,generated['reservation_id']); assert state['job']['status']=='COMPLETED'
    before=e.chapters.list(e.nid)
    monkeypatch.setattr(e.manager,'memory_extractor',None)
    monkeypatch.setattr(e.manager,'canon',e.canon)
    monkeypatch.setattr(e.manager,'collaboration_updates',None)
    if off=='disabled':monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    else:monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert e.client.get(e.base+'/model-broker/status',headers=e.headers).status_code==404
    result=e.client.post(e.prefix+f'/generation/{generated["job_id"]}/accept',headers=e.headers,json={'content':'AUDIT EXPERIMENTAL CONTENT','expected_version':e.chapter['version']})
    assert result.status_code in {403,404,409}, (result.status_code,result.text,[r['content'] for r in e.chapters.list(e.nid)])
    assert e.chapters.list(e.nid)==before

def test_audit_accept_does_not_race_budget_terminal_settlement(broker_app, monkeypatch):
    import app.jobs as jobs_module
    from threading import Event
    import time
    e=broker_app; completed=Event(); release=Event()
    def pause_log(**kwargs):
        if kwargs.get('status')=='COMPLETED':
            completed.set(); assert release.wait(5)
    monkeypatch.setattr(jobs_module.runtime_log,'write',pause_log)
    monkeypatch.setattr(e.manager,'memory_extractor',None)
    monkeypatch.setattr(e.manager,'canon',e.canon)
    monkeypatch.setattr(e.manager,'collaboration_updates',None)
    selected=quote(e); body=author_body(e)
    preview=checked(e.client.post(e.base+'/author-context/preview',headers=e.headers,json=body))
    created=checked(e.client.post(e.base+'/model-broker/generate',headers=e.headers,json={'preview_id':selected['id'],'expected_version':selected['version'],'request_id':'audit-terminal-race','author':{**body,'preview_digest':preview['preview_digest']}}),202)
    try:
        assert completed.wait(5)
        response=e.client.post(e.prefix+f'/generation/{created["job_id"]}/accept',headers=e.headers,json={'content':'APPROVED SYNTHETIC TEXT','expected_version':e.chapter['version']})
        assert response.status_code==200,response.text
    finally:release.set()
    deadline=time.monotonic()+5
    while e.manager.get(created['job_id']).terminal_hook_status is None and time.monotonic()<deadline:time.sleep(.01)
    job=e.manager.get(created['job_id'])
    ledger=e.broker.get(e.nid,e.scope,e.broker.LEDGER,created['reservation_id'])
    assert job.terminal_hook_status=='COMPLETED',(job.status,job.terminal_hook_status,ledger['status'])
    assert job.status=='ACCEPTED' and ledger['status']=='SETTLED'
