"""Real original File/PG records and mounted version-bound source controls."""
import json
from app.author_request import request_payload
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_author_scope_variants_mounted import author_app, author, wait_jobs


def source_body(e):
    for rid, label, text in [('item-removed', 'Excluded record', 'SOURCE_ITEM_CANARY'), ('item-kept', 'Retained record', 'RETAINED_ITEM')]:
        e.bundle.novels.upsert_character(e.nid, rid, {'name': label, 'personality': text, 'privacy_level': 'LOCAL_ONLY'})
    e.bundle.novels.update(e.nid, {'long_term_summary': 'SOURCE_ITEM_CANARY'})
    body = author(e); body['instruction'] = 'Excluded record and Retained record, synthetic source-control test.'
    value = checked(e.client.post(e.base + '/author-context/preview', json=body))
    row = next(row for row in value['source_manifest']['items'] if row['label'] == 'Excluded record')
    body['request_scope']['source_items'] = [{'key': row['key'], 'source_digest': row['source_digest'], 'include': False}]
    return body


def test_mounted_exact_exclusion_survives_persistence_and_original_adapter_send(author_app, monkeypatch):
    import app.jobs as jobs
    e = author_app; body = source_body(e)
    value = checked(e.client.post(e.base + '/author-context/preview', json=body))
    assert 'SOURCE_ITEM_CANARY' not in json.dumps(value['request']) and 'RETAINED_ITEM' in value['request']['prompt']
    observed = []; prepare = jobs.runtime.prepare_text_route
    class Capture:
        def __init__(self, node): self.node = node
        def stream(self, inputs):
            inputs.request.dispatch_guard(); observed.append(request_payload(inputs.request))
            yield from self.node.stream(inputs)
    monkeypatch.setattr(jobs.runtime, 'prepare_text_route', lambda *args: Capture(prepare(*args)))
    result = checked(e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': value['preview_digest']}), 202)
    job = wait_jobs(e, [result['job_id']])[0]
    assert job.status == 'COMPLETED' and observed == [value['request']]
    stored = e.manager.persistence.get(job.id)
    assert stored['request_scope'] == body['request_scope']
    assert e.chapters.get(e.chapter['id'])['content'] == e.chapter['content']


def test_mounted_original_record_edit_invalidates_pinned_exclusion(author_app):
    e = author_app; body = source_body(e)
    value = checked(e.client.post(e.base + '/author-context/preview', json=body))
    e.bundle.novels.upsert_character(e.nid, 'item-removed', {'name': 'Excluded record', 'personality': 'NEW_PRIVATE_CONTENT', 'privacy_level': 'LOCAL_ONLY'})
    result = e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': value['preview_digest']})
    assert result.status_code == 409 and 'NEW_PRIVATE_CONTENT' not in result.text
    assert not e.manager.jobs


def test_mounted_removed_approved_reference_cannot_reenter_through_summary(author_app):
    e = author_app
    profile = checked(e.client.post(e.base + '/style-analysis/profiles', json={'title': 'Excluded approved style',
        'instructions': 'APPROVED_STYLE_EXCLUSION_CANARY', 'chapter_ids': [e.chapter['id']]}), 201)
    checked(e.client.post(e.base + '/style-analysis/profiles/' + profile['id'] + '/approve', json={'expected_version': profile['version']}))
    e.bundle.novels.update(e.nid, {'long_term_summary': 'APPROVED_STYLE_EXCLUSION_CANARY'})
    body = {**author(e, include_style_reference=False), 'style_profile_id': profile['id']}
    value = checked(e.client.post(e.base + '/author-context/preview', json=body))
    assert not value['creation_records'] and 'APPROVED_STYLE_EXCLUSION_CANARY' not in json.dumps(value['request'])
    assert value['source_manifest']['dependent_context_omitted']
