"""An explicit cancellation survives only its own RESERVED→DISPATCHED race."""
from threading import Event
import pytest
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_broker_mounted import broker_app, quote, author_body, wait_ledger


def test_cancel_follows_owned_reservation_dispatch_without_losing_stop(broker_app, monkeypatch):
    from app.runtime import runtime
    e=broker_app; started=Event(); release=Event()
    def stream(prompt, model, **kwargs):
        started.set(); assert release.wait(5)
        yield 'Synthetic output must be discarded after explicit cancel'
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    selected=quote(e); author=author_body(e)
    preview=checked(e.client.post(e.base+'/author-context/preview',headers=e.headers,json=author))
    generated=checked(e.client.post(e.base+'/model-broker/generate',headers=e.headers,json={
        'preview_id':selected['id'],'expected_version':selected['version'],'request_id':'cancel-dispatch-race',
        'author':{**author,'preview_digest':preview['preview_digest']}}),202)
    try:
        assert started.wait(5)
        current=checked(e.client.get(e.base+'/model-broker/jobs/'+generated['reservation_id'],headers=e.headers))
        assert current['ledger']['version']==2 and current['ledger']['status']=='DISPATCHED'
        result=e.client.post(e.base+'/model-broker/jobs/'+generated['reservation_id']+'/cancel',headers=e.headers,json={'expected_version':1})
        assert result.status_code==200,result.text
        assert result.json()['job']['status']=='CANCELLED'
    finally: release.set()
    result=wait_ledger(e,generated['reservation_id'])
    assert result['job']['status']=='CANCELLED' and not result['job']['output']
    assert result['ledger']['status']=='SETTLED' and result['ledger']['actual_microusd']==0


def test_future_cancel_version_is_redacted_and_does_not_stop_owned_job(broker_app, monkeypatch):
    from app.runtime import runtime
    e=broker_app; started=Event(); release=Event()
    def stream(prompt, model, **kwargs):
        started.set(); assert release.wait(5);yield 'Synthetic completed'
    monkeypatch.setattr(runtime.providers['mock'],'stream',stream)
    selected=quote(e);author=author_body(e);preview=checked(e.client.post(e.base+'/author-context/preview',headers=e.headers,json=author))
    generated=checked(e.client.post(e.base+'/model-broker/generate',headers=e.headers,json={'preview_id':selected['id'],'expected_version':selected['version'],'request_id':'cancel-future','author':{**author,'preview_digest':preview['preview_digest']}}),202)
    try:
        assert started.wait(5)
        response=e.client.post(e.base+'/model-broker/jobs/'+generated['reservation_id']+'/cancel',headers=e.headers,json={'expected_version':999})
        assert response.status_code==409
        assert 'authorization_digest' not in response.text and 'history' not in response.text
        assert not e.manager.get(generated['job_id']).cancelled.is_set()
    finally:release.set()
    assert wait_ledger(e,generated['reservation_id'])['job']['status']=='COMPLETED'


@pytest.mark.parametrize('field,value', [('job_id','different'),('scope',{'mode':'local','novel_id':'other'}),('authorization_digest','changed'),('status','SETTLED'),('version',3)])
def test_dispatch_cancel_exception_never_accepts_another_identity_or_transition(field,value):
    from copy import deepcopy
    from app.experimental.model_broker_api import cancellation_version_matches
    original={'id':'r','job_id':'j','scope':{'mode':'local','novel_id':'n'},'authorization_digest':'digest','status':'RESERVED','version':1}
    row={**original,'status':'DISPATCHED','version':2,'history':[deepcopy(original)]}
    assert cancellation_version_matches(row,1)
    row[field]=value
    assert not cancellation_version_matches(row,1)
