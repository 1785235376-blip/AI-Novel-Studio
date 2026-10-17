"""Constructor-gated advertisement; reads do not create a preview or Job."""
import pytest
from creative_director_execution_fixture import lifecycle
from test_v2_independent_director_adoption import board,raw_bytes
from test_director_observation_transport_additive import mounted
pytestmark=pytest.mark.file_backend_only

def url(m):
    return m.url.rsplit('/',2)[0]+'/model-capabilities'

@pytest.mark.parametrize('actions',[False,True])
def test_advertisement_matches_actual_router_and_preserves_persistence(lifecycle,actions):
    e=board(lifecycle);m=mounted(e,actions=actions);before=raw_bytes(e)
    response=m.client.get(url(m),headers=m.headers)
    assert response.status_code==200,response.text
    assert response.json().get('independent_director_contract')==('CREATIVE_DIRECTOR_MODEL_V1' if actions else None)
    assert raw_bytes(e)==before and e.requests==[] and e.persistence.load_all()==[]
    assert set(m.permissions)=={'domain.read'}

def test_unsupported_persistence_is_not_advertised(lifecycle,monkeypatch):
    e=board(lifecycle);m=mounted(e,actions=True);before=raw_bytes(e)
    def unsupported(): raise ValueError('CREATIVE_DIRECTOR_PENDING_BACKEND_UNSUPPORTED')
    monkeypatch.setattr(e.documents.proposals.generation,'_pending_repository',unsupported)
    response=m.client.get(url(m),headers=m.headers)
    assert response.status_code==200,response.text
    assert 'independent_director_contract' not in response.json()
    assert raw_bytes(e)==before and e.requests==[]

def test_capability_still_requires_host_session(lifecycle):
    e=board(lifecycle);m=mounted(e,actions=True)
    response=m.client.get(url(m),headers={'X-Session-Token':'wrong'})
    assert response.status_code==403
    assert 'independent_director_contract' not in response.text and e.requests==[]
