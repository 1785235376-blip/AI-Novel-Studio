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


def test_opt_in_multishot_http_restart_review_and_original_derive(lifecycle):
    """Injected synthetic wire only; this is lifecycle validation, not inference acceptance."""
    from test_v2_screenplay_shot_plan import shot_output
    from app.creative.screenplay_model import SHOT_PLAN_CONTRACT, screenplay_allowed_slots
    e = lifecycle
    e.source = e.documents.create(e.nid, e.scope, e.actor, {
        'mode': 'SCREENPLAY', 'source_independent': True, 'title': 'Two authored scenes',
        'scenes': [{'id': 'second', 'sequence': 8, 'heading': 'HALL', 'action': 'The door opens.'},
                   {'id': 'first', 'sequence': 3, 'heading': 'ROOM', 'action': 'The visitor waits.'}]})
    e.row = e.documents.proposals.create(e.nid, e.scope, e.actor,
        {'source_document_id': e.source['id'], 'expected_source_version': e.source['version']})
    original = deepcopy(e.source); original_digest = e.documents.document_digest(original)
    e.wire_text = json.dumps(shot_output(e.source, e.row))
    allowed = screenplay_allowed_slots(e.row, e.source)
    m = mounted(e, actions=True); m.url = m.url.replace('/model-v1', '/model-v2')
    first = m.client.post(m.url+'/preview', headers=m.headers,
        json={**preview_request(e), 'planning_mode': 'MULTI_SHOT_V1', 'max_output_tokens': 2048})
    assert first.status_code == 200, first.text
    p = first.json()['receipt']
    assert p['contract'] == 'DIRECTOR_SCREENPLAY_MODEL_PREVIEW_V3'
    assert p['allowed_source_mapping'] == allowed and not e.requests
    assert 'source_mapping' not in p
    dispatch_body = {'expected_version': p['version'], 'reviewed_preview_digest': p['reviewed_preview_digest']}
    dispatched = m.client.post(m.url+'/dispatch', headers=m.headers, json=dispatch_body)
    assert dispatched.status_code in (200, 409), dispatched.text
    assert len(e.manager.jobs) == 1
    job = wait(e, next(iter(e.manager.jobs.values())))
    assert job.status == 'COMPLETED' and job.terminal_hook_status == 'COMPLETED'
    status = m.client.get(m.url+'/status', headers=m.headers).json()['receipt']
    assert status['phase'] == 'COMPLETED'
    restart(e); fresh_host(e); m = mounted(e, actions=True); m.url = m.url.replace('/model-v1', '/model-v2')
    pending = m.client.post(m.url+'/prepare-review', headers=m.headers, json={
        'expected_version': status['version'], 'terminal_evidence_digest': status['terminal_evidence_digest']})
    assert pending.status_code == 200, pending.text
    c = pending.json()['receipt']
    assert c['contract'] == 'DIRECTOR_SCREENPLAY_MODEL_PENDING_REVIEW_V3'
    assert len(c['director_notes']) == len(c['provenance']['source_mapping']) == 4
    assert c['provenance']['allowed_source_mapping'] == allowed
    assert c['provenance']['output_contract'] == SHOT_PLAN_CONTRACT
    before = raw_bytes(e)
    repeated = m.client.post(m.url+'/prepare-review', headers=m.headers, json={
        'expected_version': status['version'], 'terminal_evidence_digest': status['terminal_evidence_digest']})
    assert repeated.json() == pending.json() and raw_bytes(e) == before
    changed = m.client.post(m.url+'/prepare-review', headers=m.headers, json={
        'expected_version': status['version'], 'terminal_evidence_digest': '0'*64})
    assert changed.status_code == 409 and raw_bytes(e) == before
    restart(e); fresh_host(e); m = mounted(e, actions=True); m.url = m.url.replace('/model-v1', '/model-v2')
    assert m.client.get(m.url+'/pending-review', headers=m.headers).json() == pending.json()
    human = review_body(c)
    for change in ('id', 'scene_id', 'number', 'omit', 'reorder'):
        invalid = deepcopy(human)
        if change in ('id', 'scene_id'): invalid['director_notes'][0][change] = 'changed'
        if change == 'number': invalid['director_notes'][0]['number'] = 6
        if change == 'omit': invalid['director_notes'].pop()
        if change == 'reorder': invalid['director_notes'].reverse()
        before = raw_bytes(e)
        assert m.client.post(m.url+'/review', headers=m.headers, json=invalid).status_code == 409
        assert raw_bytes(e) == before
    human['director_notes'][0]['note'] = 'Human revised dramatic beat'
    human['director_notes'][0]['duration_seconds'] = 12
    adopted = m.client.post(m.url+'/review', headers=m.headers, json=human)
    assert adopted.status_code == 200, adopted.text
    receipt = adopted.json()['receipt']
    assert receipt['document']['status'] == 'DRAFT'
    draft = e.documents.get(e.nid, e.scope, receipt['document']['document_id'])
    assert draft['director_notes'][0]['note'] == human['director_notes'][0]['note']
    assert e.persistence.get(job.id)['output'] == e.wire_text
    assert draft['provenance']['candidate_output_digest'] == c['output_digest']
    assert draft['provenance']['reviewed_output_digest'] != c['output_digest']
    assert draft['source_documents'][original['id']] == {'version': original['version'], 'digest': original_digest}
    board = e.documents.derive(e.nid, e.scope, e.actor, draft['id'], {
        'expected_version': draft['version'], 'mode': 'STORYBOARD', 'shot_policy': 'DIRECTOR_NOTES'})
    assert len(board['shots']) == 4
    assert [(s['scene_id'], s['director_note_ids']) for s in board['shots']] == [
        (n['scene_id'], [n['id']]) for n in draft['director_notes']]
    assert board['source_documents'][draft['id']] == {'version': draft['version'], 'digest': e.documents.document_digest(draft)}
    assert set(board['source_documents']) == {draft['id']}
    ancestor = e.documents.get(e.nid, e.scope, next(iter(board['source_documents'])))
    assert ancestor['source_documents'] == {original['id']: {'version': original['version'], 'digest': original_digest}}
    assert board['status'] == draft['status'] == 'DRAFT'
    assert e.documents.get(e.nid, e.scope, original['id']) == original
    assert m.client.post(m.url+'/dispatch', headers=m.headers, json=dispatch_body).status_code == 409
    assert m.client.post(m.url+'/review', headers=m.headers, json=human).status_code == 409
    assert m.client.get(m.url+'/adopted-draft', headers=m.headers).json() == adopted.json()
    assert len(e.requests) == len(e.broker.ledger(e.nid, e.scope, e.actor)) == 1
    assert len([d for d in e.raw.read(e.nid, e.scope)['collections'][e.documents.COLLECTION].values()
        if d.get('mode') == 'DIRECTOR']) == 1
    (e.root/'screenplay-multishot-wire.json').write_text(json.dumps({'source': original,
        'preview': first.json(), 'pending': pending.json(), 'submitted_review': human,
        'adopted': adopted.json(), 'document': draft, 'storyboard': board}, ensure_ascii=False, indent=2)+'\n')


def test_opt_in_source_and_token_bounds_reject_before_admission(lifecycle):
    e = lifecycle
    e.source = e.documents.create(e.nid, e.scope, e.actor, {
        'mode': 'SCREENPLAY', 'source_independent': True, 'title': 'Three scenes are unsupported',
        'scenes': [{'id': f's{i}', 'sequence': i+1, 'heading': 'ROOM', 'action': 'Wait.'} for i in range(3)]})
    e.row = e.documents.proposals.create(e.nid, e.scope, e.actor,
        {'source_document_id': e.source['id'], 'expected_source_version': e.source['version']})
    m = mounted(e, actions=True); m.url = m.url.replace('/model-v1', '/model-v2')
    before = raw_bytes(e)
    response = m.client.post(m.url+'/preview', headers=m.headers,
        json={**preview_request(e), 'planning_mode': 'MULTI_SHOT_V1'})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'CREATIVE_MODEL_SHOT_PLAN_REQUIRES_ONE_OR_TWO_SCENES'
    assert raw_bytes(e) == before and not e.requests and not e.manager.jobs
    response = m.client.post(m.url+'/preview', headers=m.headers,
        json={**preview_request(e), 'planning_mode': 'MULTI_SHOT_V1', 'max_output_tokens': 2049})
    assert response.status_code == 422 and raw_bytes(e) == before
    # No new implicit planning mode on the old storyboard endpoint.
    legacy = m.url.replace('/model-v2', '/model-v1')
    response = m.client.post(legacy+'/preview', headers=m.headers,
        json={**preview_request(e), 'planning_mode': 'MULTI_SHOT_V1'})
    assert response.status_code == 422 and raw_bytes(e) == before


def test_incomplete_multishot_json_never_publishes_or_replays(lifecycle):
    from test_v2_screenplay_shot_plan import shot_output
    e = screenplay(lifecycle)
    e.wire_text = json.dumps(shot_output(e.source, e.row, (0, 2)))[:-2]
    m = mounted(e, actions=True); m.url = m.url.replace('/model-v1', '/model-v2')
    response = m.client.post(m.url+'/preview', headers=m.headers,
        json={**preview_request(e), 'planning_mode': 'MULTI_SHOT_V1'})
    assert response.status_code == 200, response.text
    p = response.json()['receipt']
    body = {'expected_version': p['version'], 'reviewed_preview_digest': p['reviewed_preview_digest']}
    m.client.post(m.url+'/dispatch', headers=m.headers, json=body)
    assert len(e.manager.jobs) == 1
    job = wait(e, next(iter(e.manager.jobs.values())))
    assert job.status == 'COMPLETED'
    st = m.client.get(m.url+'/status', headers=m.headers).json()['receipt']
    restart(e); fresh_host(e); m = mounted(e, actions=True); m.url = m.url.replace('/model-v1', '/model-v2')
    before = raw_bytes(e)
    result = m.client.post(m.url+'/prepare-review', headers=m.headers, json={
        'expected_version': st['version'], 'terminal_evidence_digest': st['terminal_evidence_digest']})
    assert result.status_code == 409
    assert result.json()['detail']['code'] == 'CREATIVE_MODEL_SHOT_PLAN_INVALID_OR_INCOMPLETE_JSON'
    assert raw_bytes(e) == before
    assert m.client.get(m.url+'/pending-review', headers=m.headers).status_code == 409
    assert m.client.post(m.url+'/dispatch', headers=m.headers, json=body).status_code == 409
    assert len(e.requests) == len(e.broker.ledger(e.nid, e.scope, e.actor)) == 1


def test_default_v2_preview_survives_restart_without_new_fields(lifecycle):
    e = screenplay(lifecycle); m = mounted(e, actions=True); m.url = m.url.replace('/model-v1', '/model-v2')
    response = m.client.post(m.url+'/preview', headers=m.headers, json=preview_request(e))
    assert response.status_code == 200, response.text
    assert response.json()['receipt']['contract'] == 'DIRECTOR_SCREENPLAY_MODEL_PREVIEW_V2'
    assert 'planning_mode' not in response.text and 'allowed_source_mapping' not in response.text
    restart(e); fresh_host(e); m = mounted(e, actions=True); m.url = m.url.replace('/model-v1', '/model-v2')
    before = raw_bytes(e)
    read = m.client.get(m.url+'/preview', headers=m.headers)
    assert read.status_code == 200 and read.content == response.content
    assert raw_bytes(e) == before and not e.requests and not e.manager.jobs


def test_omitted_and_null_mode_retain_exact_legacy_preview_arguments(lifecycle, monkeypatch):
    from app.creative.screenplay_model import SCREENPLAY_CONTRACT
    from app.experimental.store import canonical
    e = screenplay(lifecycle); seen = []
    def capture(ctx, rid, value, guard, *, host_authority, output_contract):
        seen.append((canonical(value), output_contract, ctx, rid, guard, host_authority))
    monkeypatch.setattr(e.coordinator, '_preview_independent_contract', capture)
    body = preview_request(e)
    for payload in (body, {**body, 'planning_mode': None}):
        e.coordinator._preview_independent_screenplay(e.ctx, e.row['id'], payload, e.guard, host_authority=e.authority)
    assert seen[0] == seen[1]
    assert seen[0] == (canonical(body), SCREENPLAY_CONTRACT, e.ctx, e.row['id'], e.guard, e.authority)
