"""U08 original source pointers, persistent jobs and exact dispatch. Synthetic only."""
import copy
import json
import os

import pytest

from app.author_request import request_payload
from app.jobs import JobManager, generation_content_available
from app.author_context_sources import NativeAuthorContext, AddedAuthorSource
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_author_scope_variants_mounted import author_app, author, wait_jobs
from test_r4_research_library import payload


def catalog(e, kind, **kwargs):
    return checked(e.client.post(e.base + '/author-context/sources', json={
        'kind': kind, 'provider_id': 'mock', **kwargs}))


def pointer(row, **options):
    return {key: row[key] for key in ('kind', 'id', 'version', 'source_digest', 'citation') if row.get(key) is not None} | {'include': True, 'max_characters': 4000, **options}


def request(e, refs):
    return {**author(e, source_mode='NONE'), 'request_scope': {**author(e, source_mode='NONE')['request_scope'], 'added_sources': refs}}


def preview(e, refs):
    body = request(e, refs)
    return body, checked(e.client.post(e.base + '/author-context/preview', json=body))


def research(e, text='NATIVE_RESEARCH_CANARY.\n\nSecond paragraph.', actor='local-author', **options):
    return e.experimental.research_library_service.import_file(e.nid, e.scope, actor, payload(text=text, **options), guard=lambda: None)


def generate(e, body, value):
    result = checked(e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': value['preview_digest']}), 202)
    return wait_jobs(e, [result['job_id']])[0]


def test_original_chapter_pointer_exact_prompt_send_persistence_restart(author_app, monkeypatch):
    import app.jobs as jobs
    e = author_app
    row = catalog(e, 'CHAPTER')['items'][0]
    assert row['id'] == e.chapter['id'] and row['version'] == e.chapter['version'] and row['preview'] == e.chapter['content'][:500]
    body, value = preview(e, [pointer(row)])
    assert value['source_strategy'] == 'NO_MANUSCRIPT' and value['source_characters'] == 0
    assert list(value['request']['context']) == ['explicit_sources']
    actual = value['request']['context']['explicit_sources']['items'][0]
    assert actual['text'] == e.chapter['content'] and actual['untrusted_data'] and not actual['instructions_allowed']
    observed = []; prepare = jobs.runtime.prepare_text_route
    class Capture:
        def __init__(self, node): self.node = node
        def stream(self, inputs):
            inputs.request.dispatch_guard(); observed.append(request_payload(inputs.request))
            yield from self.node.stream(inputs)
    monkeypatch.setattr(jobs.runtime, 'prepare_text_route', lambda *args: Capture(prepare(*args)))
    job = generate(e, body, value)
    assert job.status == 'COMPLETED' and observed == [value['request']]
    stored = e.manager.persistence.get(job.id)
    assert stored['request_scope']['added_sources'] == body['request_scope']['added_sources']
    assert 'author_context_resolver' not in stored and 'request_authorization' not in stored
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts, canon=e.manager.canon, snapshot_required=False)
    recovered = restarted.get(job.id)
    assert recovered.author_context_resolver is None and generation_content_available(recovered)
    assert e.chapters.get(e.chapter['id'])['content'] == e.chapter['content']


def test_research_exact_citation_preview_exclude_budget_and_no_canon_promotion(author_app):
    e = author_app; source = research(e, 'NATIVE_RESEARCH_CANARY ' + 'x' * 600)
    row = catalog(e, 'RESEARCH')['items'][0]
    assert row['citation'] == source['paragraphs'][0]['citation'] and row['preview_truncated']
    body, value = preview(e, [pointer(row, max_characters=256)])
    item = value['request']['context']['explicit_sources']['items'][0]
    assert len(item['text']) == 256 and item['truncated'] and item['layer'] == 'RESEARCH'
    assert item['evidence']['source_digest'] == source['content_sha256']
    assert value['source_manifest']['added_items'][0]['characters'] == 256
    excluded, omitted = preview(e, [pointer(row, include=False)])
    assert 'NATIVE_RESEARCH_CANARY' not in json.dumps(omitted['request'])
    assert omitted['source_manifest']['added_items'][0]['included'] is False
    assert e.experimental.world_service.canon(e.nid, e.scope) == []
    assert e.client.post(e.base + '/author-context/generate', json={**excluded, 'preview_digest': value['preview_digest']}).status_code == 409


@pytest.mark.parametrize('kind', ['CANON', 'STORY_GRAPH'])
def test_original_approved_records_pin_source_version_and_archive_withholds_result(author_app, kind):
    e = author_app
    service = e.experimental.world_service if kind == 'CANON' else e.experimental.story_graph_service
    data = {'kind': 'ABILITY', 'title': 'NATIVE_CANON', 'data': {'name': 'Native power'}} if kind == 'CANON' else {
        'kind': 'STORY_CONCEPT', 'title': 'NATIVE_GRAPH', 'chapter_id': e.chapter['id'], 'data': {'concept_type': 'OBJECT', 'description': 'An original item'}}
    candidate = service.create_record(e.nid, e.scope, 'local-author', data)
    assert catalog(e, kind)['items'] == []
    approved = service.review(e.nid, e.scope, 'local-author', candidate['id'], 'approve', candidate['version'])
    row = catalog(e, kind)['items'][0]
    body, value = preview(e, [pointer(row)])
    assert data['title'] in value['request']['prompt']
    job = generate(e, body, value)
    assert job.status == 'COMPLETED' and generation_content_available(job)
    service.review(e.nid, e.scope, 'local-author', candidate['id'], 'archive', approved['version'])
    assert not generation_content_available(job)
    assert e.client.get(e.prefix + '/generation/' + job.id).status_code == 404


@pytest.mark.parametrize('mutation', ['replace', 'revoke', 'feature'])
def test_current_research_changes_at_transport_boundary_prevent_send(author_app, monkeypatch, mutation):
    import app.jobs as jobs
    e = author_app; source = research(e); body, value = preview(e, [pointer(catalog(e, 'RESEARCH')['items'][0])])
    prepare = jobs.runtime.prepare_text_route; sent = []
    class Capture:
        def __init__(self, node): self.node = node
        def stream(self, inputs):
            if mutation == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', os.environ['EXPERIMENTAL_FEATURES'].replace('research_library_v2', ''))
            elif mutation == 'revoke': e.experimental.research_library_service.transition_source(e.nid, e.scope, 'local-author', source['id'], 1, 'revoke', guard=lambda: None)
            else: e.experimental.research_library_service.replace_file(e.nid, e.scope, 'local-author', source['id'], {**payload(text='NEW_PRIVATE_TEXT'), 'expected_version': 1}, guard=lambda: None)
            inputs.request.dispatch_guard(); sent.append(request_payload(inputs.request)); yield from self.node.stream(inputs)
    monkeypatch.setattr(jobs.runtime, 'prepare_text_route', lambda *args: Capture(prepare(*args)))
    job = generate(e, body, value)
    assert job.status == 'FAILED' and sent == []
    assert not generation_content_available(job)
    assert e.client.get(e.prefix + '/generation/' + job.id).status_code == 404


def test_research_restart_revocation_hides_output_and_old_receipt(author_app):
    e = author_app; source = research(e); refs = [pointer(catalog(e, 'RESEARCH')['items'][0])]
    body, value = preview(e, refs); job = generate(e, body, value)
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts, canon=e.manager.canon, snapshot_required=False)
    recovered = restarted.get(job.id); assert generation_content_available(recovered)
    e.experimental.research_library_service.transition_source(e.nid, e.scope, 'local-author', source['id'], 1, 'revoke', guard=lambda: None)
    assert not generation_content_available(recovered)
    assert e.client.post(e.base + '/author-context/preview', json=body).status_code == 404
    assert e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': value['preview_digest']}).status_code == 404


def test_local_only_catalog_cloud_hidden_and_actual_cloud_resolve_blocked(author_app, monkeypatch):
    e = author_app; source = research(e); row = catalog(e, 'RESEARCH')['items'][0]
    native = e.experimental.author_preparer.native_sources
    ctx = NativeAuthorContext(e.nid, e.scope, 'local-author')
    assert native.catalog(ctx, kind='RESEARCH', cloud=True)['items'] == []
    with pytest.raises(ValueError, match='UNAVAILABLE_OR_CHANGED'): native.resolve(ctx, [pointer(row)], cloud=True)
    import app.experimental.author_context_api as endpoint
    monkeypatch.setattr(endpoint.runtime, 'is_remote_text_provider', lambda _: True)
    result = catalog(e, 'RESEARCH')
    assert result['items'] == [] and source['id'] not in json.dumps(result) and source['title'] not in json.dumps(result)


def test_private_research_scope_flags_unknown_inputs_and_character_mode_fail_closed(author_app, monkeypatch):
    e = author_app; private = research(e, actor='another-author'); assert catalog(e, 'RESEARCH')['items'] == []
    source = research(e); ref = pointer(catalog(e, 'RESEARCH')['items'][0])
    for invalid in ([ref, ref], [{**ref, 'text': 'CLIENT_INJECTION'}], [{**ref, 'citation': {**ref['citation'], 'paragraph': 0}}]):
        response = e.client.post(e.base + '/author-context/preview', json=request(e, invalid))
        assert response.status_code == 422 and 'CLIENT_INJECTION' not in response.text
    body = {**request(e, [ref]), 'character_id': 'alice'}
    assert e.client.post(e.base + '/author-context/preview', json=body).status_code == 422
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'author_context_inspector_v2')
    assert e.client.post(e.base + '/author-context/sources', json={'kind': 'RESEARCH', 'provider_id': 'mock'}).status_code == 404
    assert not e.manager.jobs


def test_collaboration_current_owner_and_private_research_catalog_recheck(author_app, monkeypatch):
    e = scoped(author_app, monkeypatch)
    research(e, actor=e.lead)
    body = {'kind': 'RESEARCH', 'provider_id': 'mock'}
    assert checked(e.client.post(e.base + '/author-context/sources', json=body, headers=e.headers))['items']
    assert checked(e.client.post(e.base + '/author-context/sources', json=body, headers=e.viewer_headers))['items'] == []
    assert checked(e.client.post(e.base + '/author-context/sources', json={'kind': 'CHAPTER', 'provider_id': 'mock'}, headers=e.headers))['branch_sources_available'] is False
    original = e.experimental.research_library_service.source
    def revoked(*args):
        value = original(*args); e.authorization.revoke_role(e.role, e.lead); return value
    monkeypatch.setattr(e.experimental.research_library_service, 'source', revoked)
    response = e.client.post(e.base + '/author-context/sources', json=body, headers=e.headers)
    assert response.status_code == 403 and 'NATIVE_RESEARCH_CANARY' not in response.text


def test_research_search_finds_late_exact_paragraph_beyond_preview_window(author_app):
    e = author_app
    research(e, '\n\n'.join('Synthetic ordinary paragraph ' + str(i) for i in range(220)) + '\n\nLATE_SOURCE_CANARY')
    row = catalog(e, 'RESEARCH', query='LATE_SOURCE_CANARY')['items'][0]
    assert row['citation']['paragraph'] == 221
    _, value = preview(e, [pointer(row)])
    assert 'LATE_SOURCE_CANARY' in value['request']['prompt']


def test_legacy_canon_without_version_has_content_identity_and_stays_original(author_app):
    e = author_app
    pending = {'id': 'original-canon-fixture', 'novel_id': e.nid, 'chapter_id': e.chapter['id'], 'status': 'PENDING',
        'proposals': [{'entity_type': 'story', 'fact_key': 'original', 'fact_value': 'LEGACY_CANON_CANARY', 'privacy_level': 'LOCAL_ONLY'}]}
    e.canon.save_pending(pending); e.canon.approve(pending['id'])
    before = copy.deepcopy(e.canon.list(e.nid))
    row = next(row for row in catalog(e, 'CANON')['items'] if row['id'].startswith(('legacy:', 'legacy-content:')))
    assert row['version'] is None and len(row['source_digest']) == 64
    _, value = preview(e, [pointer(row)])
    assert 'LEGACY_CANON_CANARY' in value['request']['prompt'] and e.canon.list(e.nid) == before


def test_persisted_cloud_reference_privacy_revocation_withholds_original_output(author_app, monkeypatch):
    from app.source_privacy import review_source_privacy, content_digest
    e = author_app; row = catalog(e, 'CHAPTER')['items'][0]
    body, value = preview(e, [pointer(row)]); job = generate(e, body, value)
    # The original synthetic job is inspected as a cloud record, without any
    # provider call: current outbound-source privacy remains the authority.
    native = e.experimental.author_preparer.native_sources
    monkeypatch.setattr(native.legacy.runtime, 'is_remote_text_provider', lambda _: True)
    review_source_privacy(e.chapter, None, 'local-author', 'CLOUD_ALLOWED', e.chapter['version'], content_digest(e.chapter))
    assert generation_content_available(job)
    review_source_privacy(e.chapter, None, 'local-author', 'LOCAL_ONLY', e.chapter['version'], content_digest(e.chapter))
    assert not generation_content_available(job)
    assert e.client.get(e.prefix + '/generation/' + job.id).status_code == 404


def test_nested_legacy_canon_privacy_cannot_be_overridden_by_public_parent(author_app):
    e = author_app
    pending = {'id': 'nested-privacy-fixture', 'novel_id': e.nid, 'status': 'PENDING', 'proposals': [
        {'entity_type': 'story', 'fact_key': 'Nested private fact', 'fact_value': {'secret': 'NESTED_PRIVATE_CANARY', 'privacy_level': 'LOCAL_ONLY'}, 'privacy_level': 'CLOUD_ALLOWED'}]}
    e.canon.save_pending(pending); e.canon.approve(pending['id'])
    native = e.experimental.author_preparer.native_sources; ctx = NativeAuthorContext(e.nid, e.scope, 'local-author')
    local = native.catalog(ctx, kind='CANON'); assert local['items']
    assert all(row['privacy_level'] == 'LOCAL_ONLY' for row in local['items'])
    cloud = native.catalog(ctx, kind='CANON', cloud=True)
    assert cloud['items'] == [] and 'NESTED_PRIVATE_CANARY' not in json.dumps(cloud)


def test_added_source_output_never_downgrades_collaboration_authority_to_local(author_app, monkeypatch):
    from app.jobs import Job, mark_generation_origin
    e = author_app; source = research(e); ref = pointer(catalog(e, 'RESEARCH')['items'][0])
    job = Job(id='synthetic-scoped-history', operation='continue', novel_id=e.nid, chapter_id=e.chapter['id'], instruction='', profile='LOCAL_ONLY',
        request_scope={'added_sources': [ref]}, actor_id='former-author', workspace_id='former-workspace',
        scope={'kind': 'BRANCH', 'workspace_id': 'former-workspace', 'project_id': e.nid, 'storyline_id': 'old-line', 'branch_id': 'old-branch'})
    mark_generation_origin(job, 'author_context')
    assert not generation_content_available(job)
    job.scope = None
    assert not generation_content_available(job)


def test_persisted_added_sources_revalidate_original_project_role(author_app, monkeypatch):
    from app.jobs import Job, mark_generation_origin
    e = scoped(author_app, monkeypatch)
    source = research(e, actor=e.lead)
    native = e.experimental.author_preparer.native_sources
    ctx = NativeAuthorContext(e.nid, e.scope, e.lead, e.lead, e.branch)
    ref = pointer(native.catalog(ctx, kind='RESEARCH')['items'][0])
    job = Job(id='authorized-source-history', operation='continue', novel_id=e.nid, chapter_id=e.chapter['id'], instruction='', profile='LOCAL_ONLY',
        actor_id=e.lead, workspace_id=e.workspace, session_id='session-' + e.lead, client_id='client-' + e.lead,
        scope={'kind': 'BRANCH', 'workspace_id': e.workspace, 'project_id': e.nid, 'storyline_id': e.storyline, 'branch_id': e.branch},
        request_scope={'added_sources': [ref]})
    mark_generation_origin(job, 'author_context')
    assert generation_content_available(job)
    e.authorization.revoke_role(e.role, e.lead)
    assert not generation_content_available(job)
