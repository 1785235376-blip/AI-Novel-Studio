"""Actual File private lifecycle, fixture adapter output, not live model quality."""
from copy import deepcopy
import json
import pytest
from creative_director_execution_fixture import lifecycle, raw_proposal, wait
from test_v2_screenplay_private_preview import screenplay, preview
from test_v2_screenplay_scene_contract import output
from test_director_durable_pending_review import prepare, read, review, restart, fresh_host
from test_v2_independent_director_adoption import review_body
from app.creative.director_terminal_evidence import FIELD, digest

pytestmark = pytest.mark.file_backend_only


def publish(e):
    e.wire_text = json.dumps(output(e.source,e.row))
    p = preview(e)
    receipt = e.coordinator._dispatch_independent(e.ctx,e.row['id'], {
        'expected_version': p['version'], 'reviewed_preview_digest': p['model_preview']['preview_digest']},
        e.guard,host_authority=e.authority,terminal_evidence=True)
    job = wait(e,e.manager.get(receipt['model_execution']['job_id']))
    assert job.status == 'COMPLETED' and job.terminal_hook_status == 'COMPLETED'
    saved = e.persistence.get(job.id)
    assert saved[FIELD]['source_binding']['source_kind'] == 'SCREENPLAY'
    return job, {'expected_version':raw_proposal(e)['version'], 'terminal_evidence_digest':digest(saved[FIELD])}


def test_real_private_completion_restart_pending_human_review_and_draft_reopen(lifecycle):
    e = screenplay(lifecycle); job, body = publish(e)
    restart(e); fresh_host(e)
    candidate = prepare(e,body)
    assert candidate['provenance']['source_mode'] == 'SCREENPLAY'
    assert candidate['provenance']['source_mapping'][0]['source_sequence'] == 4
    assert 'source_shot_id' not in candidate['provenance']['source_mapping'][0]
    restart(e); fresh_host(e)
    assert read(e) == candidate
    human = review_body(candidate);human['director_notes'][0]['note'] = 'Human reviewed screenplay suggestion'
    adopted = review(e,human); draft = deepcopy(adopted['document'])
    assert draft['mode'] == 'DIRECTOR' and draft['status'] == 'DRAFT'
    assert draft['source_documents'][e.source['id']]['digest'] == e.documents.document_digest(e.source)
    assert draft['director_notes'][0]['note'] == human['director_notes'][0]['note']
    restart(e)
    assert e.documents.get(e.nid,e.scope,draft['id']) == draft
    assert len(e.requests) == len(e.broker.ledger(e.nid,e.scope,e.actor)) == 1


def test_preview_mapping_tamper_and_legacy_projection_cannot_dispatch(lifecycle):
    e = screenplay(lifecycle); p = preview(e)
    from app.creative.director_transport_contract import project_preview
    with pytest.raises(ValueError): project_preview(p)
    with e.raw.transaction(e.nid,e.scope) as raw:
        row=raw['collections'][e.documents.proposals.COLLECTION][e.row['id']]
        row['model_preview']['source_mapping'][0]['note_id']='changed'
    with pytest.raises(ValueError):
        e.coordinator._dispatch_independent(e.ctx,e.row['id'], {
            'expected_version':p['version'],'reviewed_preview_digest':p['model_preview']['preview_digest']},
            e.guard,host_authority=e.authority,terminal_evidence=True)
    assert not e.manager.jobs and not e.requests


@pytest.mark.parametrize('fault', ['host', 'source', 'incarnation'])
def test_pending_rechecks_original_authority_and_source(lifecycle, fault):
    from test_v2_independent_director_adoption import raw_bytes
    from fastapi import HTTPException
    e=screenplay(lifecycle); _,body=publish(e)
    if fault=='host': e.sessions.revoke(e.token)
    else:
        with e.raw.transaction(e.nid,e.scope) as raw:
            if fault=='source': raw['collections'][e.documents.COLLECTION][e.source['id']]['title']='changed'
            else: raw['collections'][e.documents.proposals.COLLECTION][e.row['id']]['project_incarnation']='changed'
    before=raw_bytes(e)
    with pytest.raises((ValueError,HTTPException,PermissionError,FileNotFoundError)): prepare(e,body)
    assert raw_bytes(e)==before


def test_original_public_v1_rejects_v2_before_admission(lifecycle):
    from test_director_observation_transport_additive import mounted
    from test_v2_independent_director_adoption import raw_bytes
    e=screenplay(lifecycle);p=preview(e);m=mounted(e,actions=True);before=raw_bytes(e)
    body={'expected_version':p['version'],'reviewed_preview_digest':p['model_preview']['preview_digest']}
    response=m.client.post(m.url+'/dispatch',headers=m.headers,json=body)
    assert response.status_code==409
    assert m.client.get(m.url+'/preview',headers=m.headers).status_code==409
    assert m.client.get(m.url+'/status',headers=m.headers).status_code==409
    assert not e.manager.jobs and not e.requests and raw_bytes(e)==before
