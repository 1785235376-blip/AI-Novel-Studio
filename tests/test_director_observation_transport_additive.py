"""Isolated mounted adapter; application mounting and live model I/O are absent."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from creative_director_execution_fixture import lifecycle
from test_director_durable_pending_review import publish, prepare, review, restart, fresh_host
from test_v2_independent_director_adoption import board, review_body, raw_bytes, preview
from app.model_center.discovery_authority import resolve_discovery_authority

pytestmark = pytest.mark.file_backend_only


def mounted(e, *, host=True):
    permissions = []
    def authorize(nid, token, branch, permission):
        permissions.append(permission)
        e.guard()
        if nid != e.nid or branch is not None:
            raise HTTPException(403, {'code': 'FIXTURE_SCOPE_DENIED'})
        return e.actor, deepcopy(e.scope)
    def require_session(token):
        if token != e.token:
            raise HTTPException(403, {'code': 'FIXTURE_SESSION_REQUIRED'})
    def authority(request, token):
        return resolve_discovery_authority(request, token, settings_getter=lambda: e.host_settings,
            resolver_getter=lambda: e.sessions, bootstrap_getter=lambda: None)
    app = FastAPI()
    from app.creative.api import create_creative_router
    from app.experimental.flags import require_flag
    app.include_router(create_creative_router(e.documents, authorize, require_flag,
        require_host_session=require_session if host else None,
        model_host_authority=authority if host else None, director_observation=True))
    client = TestClient(app, client=('127.0.0.1', 41000), base_url='http://127.0.0.1:8000')
    prefix = f'/novels/{e.nid}/experimental/creative/director-proposals/{e.row["id"]}/model-v1'
    return SimpleNamespace(client=client, url=prefix, headers={'X-Session-Token':e.token}, permissions=permissions)


def test_preview_status_is_read_only_bounded_and_does_not_dispatch(lifecycle):
    e = board(lifecycle); preview(e); m = mounted(e)
    before = raw_bytes(e)
    response = m.client.get(m.url+'/status', headers=m.headers)
    assert response.status_code == 200, response.text
    assert response.json()['receipt']['phase'] == 'PREVIEW'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert m.permissions and set(m.permissions) == {'domain.read'}
    assert raw_bytes(e) == before and e.persistence.load_all() == [] and e.requests == []
    assert 'host_principal' not in response.text and 'prompt' not in response.text


def test_exact_adopted_receipt_and_reconciliation_survive_restart(lifecycle):
    e = board(lifecycle); _, terminal = publish(e)
    candidate = prepare(e, terminal); human = review_body(candidate)
    result = review(e, human)
    restart(e); fresh_host(e)
    m = mounted(e); before = raw_bytes(e)
    a = m.client.get(m.url+'/adopted-draft', headers=m.headers)
    b = m.client.post(m.url+'/reconcile-review', headers=m.headers, json=human)
    c = m.client.get(m.url+'/status', headers=m.headers)
    assert a.status_code == b.status_code == c.status_code == 200, (a.text,b.text,c.text)
    assert a.json() == b.json()
    assert a.json()['receipt'] == c.json()['receipt']['adoption']
    assert a.json()['project_id'] == e.nid and a.json()['scope'] == e.scope
    assert a.json()['contract'] == 'DIRECTOR_OBSERVATION_V1'
    assert a.json()['kind'] == 'adopted-draft' and c.json()['kind'] == 'status'
    assert a.json()['receipt']['document']['document_id'] == result['document']['id']
    assert raw_bytes(e) == before and len(e.requests) == 1 and len(e.persistence.load_all()) == 1
    assert set(m.permissions) == {'domain.read'}
    human['title'] += ' altered'
    denied = m.client.post(m.url+'/reconcile-review', headers=m.headers, json=human)
    assert denied.status_code == 409 and denied.json()=={'detail':{'code':'DIRECTOR_OBSERVATION_UNAVAILABLE'}}
    assert raw_bytes(e) == before and len(e.requests) == 1


@pytest.mark.parametrize('change', ['no_host','no_token','other_token','scope','origin','forwarded','revoked'])
def test_current_request_authority_denies_without_disclosure_or_writes(lifecycle, change):
    e = board(lifecycle); preview(e); m = mounted(e, host=change!='no_host')
    headers = dict(m.headers)
    if change=='no_token': headers={}
    if change=='other_token': headers['X-Session-Token']='different-token'
    if change=='scope': headers['X-Branch-ID']='different-branch'
    if change=='origin': headers['Origin']='https://untrusted.example'
    if change=='forwarded': headers['X-Forwarded-For']='203.0.113.1'
    if change=='revoked': e.active=False
    before=raw_bytes(e)
    result=m.client.get(m.url+'/status', headers=headers)
    assert result.status_code in (401,403), result.text
    assert result.headers['cache-control']=='no-store'
    assert result.headers['x-content-type-options']=='nosniff'
    assert 'prompt' not in result.text and 'host_principal' not in result.text
    assert raw_bytes(e)==before and e.requests==[] and e.persistence.load_all()==[]


@pytest.mark.parametrize('body', [{'private-sentinel':'do not echo'}, {'expected_version':True,'title':'secret-text'}, None])
def test_invalid_review_body_never_echoes_submitted_text(lifecycle, body):
    e=board(lifecycle); preview(e); m=mounted(e); before=raw_bytes(e)
    result=m.client.post(m.url+'/reconcile-review',headers=m.headers,json=body)
    assert result.status_code==422
    assert result.json()=={'detail':{'code':'DIRECTOR_OBSERVATION_REQUEST_INVALID'}}
    assert result.headers['cache-control']=='no-store'
    assert raw_bytes(e)==before and e.requests==[] and m.permissions==[]


def test_oversized_body_is_bounded_before_owner_access(lifecycle):
    e=board(lifecycle); preview(e); m=mounted(e); before=raw_bytes(e)
    result=m.client.post(m.url+'/reconcile-review',headers={**m.headers,'Content-Type':'application/json'},
        content=b'"'+b'x'*(1024*1024)+b'"')
    assert result.status_code==413
    assert result.json()=={'detail':{'code':'DIRECTOR_OBSERVATION_REQUEST_LIMIT'}}
    assert raw_bytes(e)==before and m.permissions==[] and e.requests==[]


def test_application_router_does_not_activate_observation_candidate(lifecycle):
    from app.creative.api import create_creative_router
    e=board(lifecycle)
    router=create_creative_router(e.documents, lambda *a: (e.actor,e.scope), lambda *a:None)
    assert not any('/model-v1/' in route.path for route in router.routes)


def test_missing_incarnation_is_not_provisioned_by_observation(lifecycle):
    e=board(lifecycle); preview(e); m=mounted(e)
    marker=e.root/'novels'/e.nid/'creative_project_v2.json'
    marker.unlink()  # Owned temporary fixture only; simulate missing identity.
    before=raw_bytes(e)
    response=m.client.get(m.url+'/status',headers=m.headers)
    assert response.status_code==409 and not marker.exists()
    assert raw_bytes(e)==before and e.requests==[] and e.persistence.load_all()==[]


@pytest.mark.parametrize('mutation', ['extra_private_field','late_authority_revocation'])
def test_owner_result_is_strictly_validated_and_reauthorized(lifecycle,monkeypatch,mutation):
    e=board(lifecycle); preview(e); m=mounted(e); before=raw_bytes(e)
    original=e.coordinator._read_independent_status
    def changed(*args,**kwargs):
        value=original(*args,**kwargs)
        if mutation=='extra_private_field': value['private_prompt']='must-not-leak'
        else: e.active=False
        return value
    monkeypatch.setattr(e.coordinator,'_read_independent_status',changed)
    response=m.client.get(m.url+'/status',headers=m.headers)
    assert response.status_code==(409 if mutation=='extra_private_field' else 403)
    assert 'must-not-leak' not in response.text and 'private_prompt' not in response.text
    assert response.headers['cache-control']=='no-store'
    assert raw_bytes(e)==before and e.requests==[] and e.persistence.load_all()==[]


@pytest.mark.parametrize('flag', ['narrative_production_v2','ai_execution_v2','model_broker_v2','author_context_inspector_v2'])
def test_original_flags_remain_required_for_observation(lifecycle, monkeypatch, flag):
    from creative_director_execution_fixture import FLAGS
    e=board(lifecycle); preview(e); m=mounted(e); before=raw_bytes(e)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(value for value in FLAGS.split(',') if value!=flag))
    result=m.client.get(m.url+'/status',headers=m.headers)
    assert result.status_code in (403,404), result.text
    assert raw_bytes(e)==before and e.requests==[] and e.persistence.load_all()==[]


@pytest.mark.parametrize('value', ['true',1,None])
def test_constructor_opt_in_does_not_accept_truthy_non_boolean(lifecycle,value):
    from app.creative.api import create_creative_router
    e=board(lifecycle)
    with pytest.raises(ValueError,match='DIRECTOR_OBSERVATION_OPTION_INVALID'):
        create_creative_router(e.documents,lambda *a:(e.actor,e.scope),lambda *a:None,director_observation=value)
