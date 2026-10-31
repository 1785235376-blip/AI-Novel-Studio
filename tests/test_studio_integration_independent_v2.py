"""Independent adversarial checks authored after production freeze caa7c1ce.

Reuse setup only: real main.app routes, original File services and authority.
Barriers and one-shot fault hooks control ordering; provider output is synthetic.
These tests neither patch authorization decisions nor manufacture owner receipts.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, Event, Lock

import pytest

from test_studio_asset_query import rig
from test_studio_backend_integration_v2 import studio

pytestmark = pytest.mark.file_backend_only


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def post(e, url, body):
    return e.client.post(url, headers=e.headers, json=body)


def url(e, row):
    return e.base + '/production/jobs/image/' + row['id']


def action(row):
    return {'expected_version': row['version'], 'expected_request_digest': row['request_digest']}


def prepared(e, key='independent-request'):
    shot = e.storyboard['shots'][0]
    request = ok(post(e, e.doc_url + '/shots/shot-one/image-request', {
        'expected_version': e.storyboard['document_snapshot']['version'],
        'shot_version': shot['shot_version'], 'shot_digest': shot['shot_digest'],
        'request_id': key,
        'provider': {'operation_id': 'm5.image.t2i', 'provider_id': 'automatic1111',
                     'model_id': 'synthetic.safetensors'},
        'parameters': {'width': 64, 'height': 64, 'steps': 1, 'seed': 53}}))
    preview = ok(post(e, e.base + '/production/preview', request['command']))
    return {'command': request['command'], 'reviewed_preview_digest': preview['preview_digest']}


def queued(e):
    return ok(post(e, e.base + '/production/jobs', prepared(e)), 201)


def candidate(e):
    row = queued(e)
    result = ok(post(e, url(e, row) + '/execute', action(row)))
    assert result['status'] == 'AWAITING_REVIEW'
    return result


def review_body(row):
    return {**action(row), 'reviewed_output_digest': row['output_candidate']['digest']}


def all_jobs(e):
    return ok(e.client.get(e.base + '/production/jobs', headers=e.headers))['items']


def test_simultaneous_same_request_admission_is_one_durable_job(studio, monkeypatch):
    from app.services.image_job_service import ImageJobService
    e = studio
    body = prepared(e)
    gate = Barrier(2)
    original = ImageJobService.create_studio

    def synchronized(self, *args, **kwargs):
        gate.wait(10)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ImageJobService, 'create_studio', synchronized)
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(post, e, e.base + '/production/jobs', deepcopy(body)) for _ in range(2)]
        rows = [ok(call.result(20), 201) for call in calls]
    assert rows[0] == rows[1]
    assert len(all_jobs(e)) == 1 and e.calls == []
    e.reopen()
    assert all_jobs(e) == [rows[0]]


def test_pending_execute_can_be_observed_and_duplicate_never_dispatches(studio, monkeypatch):
    from app.creative.production_execution import ProductionExecutionService
    e = studio
    row = queued(e)
    provider = e.production.image_registry.get('automatic1111')
    original = provider.generate
    entered, release, duplicate_entered = Event(), Event(), Event()
    execute_original = ProductionExecutionService.execute
    arrivals, arrival_lock = [], Lock()

    def observe_execute(self, *args, **kwargs):
        with arrival_lock:
            arrivals.append(True)
            if len(arrivals) == 2:
                duplicate_entered.set()
        return execute_original(self, *args, **kwargs)

    def held(request):
        entered.set()
        assert release.wait(15), 'provider release was not signaled'
        return original(request)

    monkeypatch.setattr(provider, 'generate', held)
    monkeypatch.setattr(ProductionExecutionService, 'execute', observe_execute)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(post, e, url(e, row) + '/execute', action(row))
        try:
            assert entered.wait(10)
            observed = ok(e.client.get(url(e, row), headers=e.headers))
            assert observed['status'] == 'RUNNING' and observed['output_candidate'] is None
            duplicate = pool.submit(post, e, url(e, row) + '/execute', action(row))
            assert duplicate_entered.wait(10), 'duplicate did not reach the original executor'
        finally:
            release.set()
        result = ok(first.result(20))
        repeated = duplicate.result(20)
    assert result['status'] == 'AWAITING_REVIEW'
    assert repeated.status_code == 409, repeated.text
    assert len(e.calls) == 1
    assert ok(e.client.get(e.doc_url + '/storyboard', headers=e.headers))['shots'][0]['image_asset'] is None


def test_two_review_confirmations_promote_exactly_once(studio, monkeypatch):
    from app.services.image_job_service import ImageJobService
    from app.services.asset_library_service import AssetLibraryService
    e = studio
    row = candidate(e)
    gate, lock = Barrier(2), Lock()
    original = ImageJobService.accept_studio
    promote = AssetLibraryService.promote_owned
    promotions = []

    def synchronized(self, *args, **kwargs):
        gate.wait(10)
        return original(self, *args, **kwargs)

    def counted(self, *args, **kwargs):
        with lock:
            promotions.append(1)
        return promote(self, *args, **kwargs)

    monkeypatch.setattr(ImageJobService, 'accept_studio', synchronized)
    monkeypatch.setattr(AssetLibraryService, 'promote_owned', counted)
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(post, e, url(e, row) + '/review', review_body(row)) for _ in range(2)]
        results = [ok(call.result(20)) for call in calls]
    assert results[0] == results[1]
    assert results[0]['status'] == 'APPROVED'
    assert results[0]['approved_asset_version'] == row['output_candidate']['version'] + 1
    assert len(promotions) == 1 and len(e.calls) == 1


def test_lost_queue_response_recovers_original_identity_without_execution(studio, monkeypatch):
    from app.services.image_job_service import ImageJobService
    e = studio
    body = prepared(e)
    original = ImageJobService.create_studio

    def lose_response(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError('independent injected lost response after durable commit')

    with monkeypatch.context() as fault:
        fault.setattr(ImageJobService, 'create_studio', lose_response)
        with pytest.raises(RuntimeError, match='lost response'):
            post(e, e.base + '/production/jobs', body)
    observed = all_jobs(e)
    assert len(observed) == 1 and observed[0]['status'] == 'QUEUED'
    e.reopen()
    retry = ok(post(e, e.base + '/production/jobs', body), 201)
    assert retry == observed[0] and all_jobs(e) == observed and e.calls == []


def test_session_revoked_at_queue_owner_entry_cannot_write(studio, monkeypatch):
    from app.services.image_job_service import ImageJobService
    e = studio
    body = prepared(e)
    original = ImageJobService._mutate
    touched = []

    def revoke_then_mutate(self, *args, **kwargs):
        touched.append(self._path(e.nid))
        e.rig.sessions.revoke(e.headers['X-Session-Token'])
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ImageJobService, '_mutate', revoke_then_mutate)
    response = post(e, e.base + '/production/jobs', body)
    assert response.status_code in (401, 403), response.text
    assert touched and all(not path.exists() for path in touched)
    assert e.calls == []


def test_candidate_bytes_are_not_returned_after_mid_read_revocation(studio, monkeypatch):
    from app.services.asset_library_service import AssetLibraryService
    e = studio
    row = candidate(e)
    original = AssetLibraryService.content
    read = []

    def revoke_after_read(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        read.append(True)
        e.rig.sessions.revoke(e.headers['X-Session-Token'])
        return result

    monkeypatch.setattr(AssetLibraryService, 'content', revoke_after_read)
    response = e.client.get(url(e, row) + '/candidate', headers=e.headers)
    assert read
    assert response.status_code in (401, 403), response.text
    assert not response.content.startswith(b'\x89PNG') and len(e.calls) == 1


def test_source_edit_after_provider_result_prevents_candidate_publication(studio, monkeypatch):
    e = studio
    row = queued(e)
    provider = e.production.image_registry.get('automatic1111')
    original = provider.generate

    def edit_source(request):
        result = original(request)
        changed = deepcopy(e.document_input)
        changed['shots'][0]['frame_prompt'] = 'A different red courtyard'
        ok(e.client.put(e.doc_url, headers=e.headers,
            json={**changed, 'expected_version': e.document['version']}))
        return result

    monkeypatch.setattr(provider, 'generate', edit_source)
    result = ok(post(e, url(e, row) + '/execute', action(row)))
    assert result['status'] == 'UNKNOWN' and result['output_candidate'] is None
    e.reopen()
    assert ok(e.client.get(url(e, row), headers=e.headers)) == result
    assert post(e, url(e, row) + '/execute', action(result)).status_code != 200
    assert len(e.calls) == 1


def test_review_receipt_failure_recovers_existing_promotion_without_regeneration(studio, monkeypatch):
    from app.services.image_job_service import ImageJobService
    e = studio
    row = candidate(e)
    original = ImageJobService._mutate
    failed = []

    def fail_approved_commit(self, nid, branch, operation):
        def fault(rows):
            result = operation(rows)
            if result.get('status') == 'APPROVED' and not failed:
                failed.append(True)
                raise OSError('independent failure before approved receipt persistence')
            return result
        return original(self, nid, branch, fault)

    with monkeypatch.context() as fault:
        fault.setattr(ImageJobService, '_mutate', fail_approved_commit)
        with pytest.raises(OSError, match='approved receipt'):
            post(e, url(e, row) + '/review', review_body(row))
    assert failed
    interrupted = ok(e.client.get(url(e, row), headers=e.headers))
    assert interrupted['status'] == 'REVIEWING'
    e.reopen()
    recovered = ok(post(e, url(e, row) + '/review', review_body(row)))
    assert recovered['status'] == 'APPROVED'
    assert recovered['approved_asset_version'] == row['output_candidate']['version'] + 1
    assert len(e.calls) == 1


def binding_body(e, approved):
    shot = e.storyboard['shots'][0]
    return {'expected_version': e.storyboard['document_snapshot']['version'],
        'shot_version': shot['shot_version'], 'shot_digest': shot['shot_digest'],
        'asset': {'asset_id': approved['output_candidate']['id'],
                  'version': approved['approved_asset_version'],
                  'digest': approved['output_candidate']['digest'], 'kind': 'image'}}


def test_concurrent_storyboard_adoption_uses_document_cas(studio, monkeypatch):
    from app.creative.storyboard import StoryboardWorkspace
    e = studio
    row = candidate(e)
    approved = ok(post(e, url(e, row) + '/review', review_body(row)))
    body = binding_body(e, approved)
    gate = Barrier(2)
    original = StoryboardWorkspace.bind_image

    def synchronized(self, *args, **kwargs):
        gate.wait(10)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(StoryboardWorkspace, 'bind_image', synchronized)
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(post, e, e.doc_url + '/shots/shot-one/image-binding', body) for _ in range(2)]
        responses = [call.result(20) for call in calls]
    assert sorted(response.status_code for response in responses) == [200, 409]
    saved = next(response.json() for response in responses if response.status_code == 200)
    assert saved['document_snapshot']['version'] == e.storyboard['document_snapshot']['version'] + 1
    assert saved['shots'][0]['image_asset'] == body['asset']
    e.reopen()
    assert ok(e.client.get(e.doc_url + '/storyboard', headers=e.headers)) == saved
    assert len(e.calls) == 1


def test_adoption_revocation_after_asset_validation_rolls_back_storyboard(studio, monkeypatch):
    e = studio
    row = candidate(e)
    approved = ok(post(e, url(e, row) + '/review', review_body(row)))
    before = e.workspace.creative.get(e.nid, e.scope, e.document['id'])
    owner = e.production.timeline_inputs
    original = owner._read
    reached = []

    def revoke_after_validation(*args, **kwargs):
        result = original(*args, **kwargs)
        reached.append(True)
        e.rig.sessions.revoke(e.headers['X-Session-Token'])
        return result

    monkeypatch.setattr(owner, '_read', revoke_after_validation)
    response = post(e, e.doc_url + '/shots/shot-one/image-binding', binding_body(e, approved))
    assert reached and response.status_code in (401, 403), response.text
    assert e.workspace.creative.get(e.nid, e.scope, e.document['id']) == before
    assert len(e.calls) == 1


def test_deleted_source_recreated_with_identical_content_does_not_resolve_old_pin(studio):
    e = studio
    row = candidate(e)
    deleted = e.client.delete(e.doc_url, headers=e.headers,
        params={'expected_version': e.document['version']})
    assert deleted.status_code == 200, deleted.text
    replacement = ok(post(e, e.creative + '/documents', e.document_input), 201)
    assert replacement['id'] != e.document['id']
    e.reopen()
    response = post(e, url(e, row) + '/review', review_body(row))
    assert response.status_code in (404, 409), response.text
    current = ok(e.client.get(url(e, row), headers=e.headers))
    assert current['status'] == 'AWAITING_REVIEW' and current['approved_asset_version'] is None
    assert len(e.calls) == 1


def test_project_id_reuse_hides_old_receipts_and_forbids_old_candidate(studio):
    e = studio
    row = candidate(e)
    e.rig.novels.delete(e.nid)
    replacement = e.rig.novels.create({'id': e.nid, 'title': 'Independent replacement project'})
    assert replacement['id'] == e.nid
    e.reopen()
    ok(post(e, e.base + '/activate', {}))
    assert all_jobs(e) == []
    for suffix in ('', '/candidate'):
        response = e.client.get(url(e, row) + suffix, headers=e.headers)
        assert response.status_code == 404, response.text
        assert row['output_candidate']['id'] not in response.text
    assert post(e, url(e, row) + '/review', review_body(row)).status_code == 404
    assert len(e.calls) == 1
