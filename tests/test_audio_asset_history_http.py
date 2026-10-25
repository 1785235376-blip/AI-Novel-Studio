import hashlib
import uuid
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.actor_context import SessionContext
from app.identity import IdentityStatus
import pytest
from test_studio_asset_query import rig, shared_scope

PAYLOAD = b'synthetic fixture bytes'

def _history_url(rig, aid):
    return f'/api/projects/{rig.nid}/studio/assets/{aid}/history'

def test_mounted_history_returns_head_and_original_bytes(rig):
    row = rig.seed('sound.wav', 'audio')
    url = _history_url(rig, row['id'])
    response = rig.client.get(url)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['current_version'] == row['version']
    assert body['items']
    first = body['items'][0]
    assert body['head'] == first['version_id']
    assert first['sha256'] == hashlib.sha256(PAYLOAD).hexdigest()
    assert first['size'] == len(PAYLOAD)
    detail = rig.client.get(f"{url}/{first['version_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()['version'] == first
    download = rig.client.get(f"{url}/{first['version_id']}/download")
    assert download.status_code == 200, download.text
    assert download.content == PAYLOAD
    assert hashlib.sha256(download.content).hexdigest() == first['sha256']

def test_history_projection_excludes_owner_private_fields(rig):
    row = rig.seed('secret-name.wav', 'audio', owner='local-author')
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.update_metadata(row['id'], {'parameters': {'prompt': 'synthetic-secret-prompt', 'api_key': 'synthetic-secret-key'}},
            branch_id=rig.scope.get('branch_id'), expected_version=row['version'], actor_id='local-author')
    response = rig.client.get(_history_url(rig, row['id']))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body['items']) == 2
    for item in body['items']:
        assert set(item['metadata']) <= {'kind', 'media_type', 'deleted', 'historically_approved'}
        assert 'parameters' not in item['metadata']
        assert 'filename' not in item['metadata']
        detail = rig.client.get(f"{_history_url(rig, row['id'])}/{item['version_id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()['version'] == item
    for secret in ('synthetic-secret-prompt', 'synthetic-secret-key', 'secret-name.wav', '_origin_provenance'):
        assert secret not in response.text

def test_history_hides_other_actors_private_asset(rig):
    row = rig.seed('private.wav', 'audio', owner='alice')
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        owner_listing = rig.assets.audio_history(row['id'], branch_id=rig.scope.get('branch_id'), actor_id='alice')
    version = owner_listing['items'][0]['version_id']
    url = _history_url(rig, row['id'])
    for endpoint in (url, f'{url}/{version}', f'{url}/{version}/download'):
        response = rig.client.get(endpoint)
        assert response.status_code == 404, response.text
        assert 'private.wav' not in response.text
        assert version not in response.text

def test_history_download_rejects_corrupt_immutable_blob(rig):
    row = rig.seed('corrupt.wav', 'audio')
    url = _history_url(rig, row['id'])
    listing = rig.client.get(url)
    assert listing.status_code == 200, listing.text
    record = listing.json()['items'][0]
    path = rig.assets.root / '.audio-history' / row['id'] / 'blobs' / (record['sha256'] + '.bin')
    path.write_bytes(b'synthetic-corruption')
    response = rig.client.get(f"{url}/{record['version_id']}/download")
    assert response.status_code in (404, 422), response.text
    assert response.content != b'synthetic-corruption'
    assert str(path) not in response.text
    assert str(rig.root) not in response.text

@pytest.fixture(autouse=True)
def _current_authority_owner(rig, monkeypatch):
    from app import api
    monkeypatch.setattr(api, 'authorization_service', rig.grants)

def test_history_is_inaccessible_after_real_permission_revocation(rig):
    scope, headers = shared_scope(rig)
    row = rig.seed('collaboration.wav', 'audio', scope_value=scope, owner='reader')
    url = _history_url(rig, row['id'])
    response = rig.client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    version = response.json()['items'][0]['version_id']
    rig.grants.revoke_permission('query-read', 'fixture')
    for endpoint in (url, f'{url}/{version}', f'{url}/{version}/download'):
        denied = rig.client.get(endpoint, headers=headers)
        assert denied.status_code == 403, denied.text
        assert row['id'] not in denied.text
        assert version not in denied.text
        assert 'collaboration.wav' not in denied.text

def test_revocation_after_owner_read_discards_history_response(rig, monkeypatch):
    scope, headers = shared_scope(rig)
    row = rig.seed('return-race.wav', 'audio', scope_value=scope, owner='reader')
    original = rig.assets.audio_history
    called = []
    def revoke_after_read(*args, **kwargs):
        value = original(*args, **kwargs)
        called.append(True)
        rig.grants.revoke_permission('query-read', 'fixture')
        return value
    monkeypatch.setattr(rig.assets, 'audio_history', revoke_after_read)
    response = rig.client.get(_history_url(rig, row['id']), headers=headers)
    assert called == [True]
    assert response.status_code == 403, response.text
    assert row['id'] not in response.text
    assert 'return-race.wav' not in response.text
    assert 'items' not in response.json()

def _persisted_audio_files(rig):
    return {str(path.relative_to(rig.assets.root)): path.read_bytes() for path in rig.assets.root.rglob('*') if path.is_file() and path.suffix in ('.json', '.bin')}

def test_restore_preview_reports_unavailable_and_confirm_cannot_write(rig):
    row = rig.seed('restore-gate.wav', 'audio')
    url = _history_url(rig, row['id'])
    initial = rig.client.get(url)
    assert initial.status_code == 200, initial.text
    before = initial.json()
    version = before['items'][0]['version_id']
    operation = str(uuid.uuid4())
    persisted_before = _persisted_audio_files(rig)
    preview = rig.client.post(f'{url}/{version}/restore-preview', json={'operation_id': operation})
    assert preview.status_code == 200, preview.text
    value = preview.json()
    assert value['confirmation_available'] is False
    assert value['admission_available'] is False
    assert value['review_path_available'] is False
    assert value['observation_token'] is None
    assert value['expires_at'] is None
    confirm = rig.client.post(f'{url}/{version}/restore-confirm', json={'operation_id': operation, 'observation_token': 'not-a-valid-observation', 'confirm': True})
    assert confirm.status_code == 409, confirm.text
    assert 'AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE' in confirm.text
    assert _persisted_audio_files(rig) == persisted_before
    after = rig.client.get(url)
    assert after.status_code == 200, after.text
    assert after.json() == before

def test_restore_confirm_rejects_integer_as_confirmation(rig):
    row = rig.seed('strict-confirm.wav', 'audio')
    url = _history_url(rig, row['id'])
    listing = rig.client.get(url)
    assert listing.status_code == 200, listing.text
    version = listing.json()['items'][0]['version_id']
    before = _persisted_audio_files(rig)
    response = rig.client.post(f'{url}/{version}/restore-confirm', json={'operation_id': str(uuid.uuid4()), 'observation_token': 'not-a-valid-observation', 'confirm': 1})
    assert response.status_code == 422, response.text
    assert _persisted_audio_files(rig) == before

def test_recreated_project_cannot_read_old_audio_owner_history(rig):
    row = rig.seed('previous-incarnation.wav', 'audio')
    old_url = _history_url(rig, row['id'])
    first = rig.client.get(old_url)
    assert first.status_code == 200, first.text
    old_version = first.json()['items'][0]['version_id']
    rig.novels.delete(rig.nid)
    rig.project(rig.nid)
    replacement = rig.seed('replacement.wav', 'audio')
    fresh = rig.client.get(_history_url(rig, replacement['id']))
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()['items'][0]['version_id'] != old_version
    for endpoint in (old_url, f'{old_url}/{old_version}', f'{old_url}/{old_version}/download'):
        denied = rig.client.get(endpoint)
        assert denied.status_code == 404, denied.text
        assert 'previous-incarnation.wav' not in denied.text
        assert old_version not in denied.text

def _collaboration_history_cursor(rig):
    scope, headers = shared_scope(rig)
    row = rig.seed('cursor.wav', 'audio', scope_value=scope, owner='reader')
    with rig.workspace._asset_scope(rig.nid, scope):
        rig.assets.update_metadata(row['id'], {'parameters': {'take': 2}}, branch_id=scope['branch_id'], actor_id='reader', expected_version=1)
    url = _history_url(rig, row['id'])
    first = rig.client.get(url, headers=headers, params={'limit': 1})
    assert first.status_code == 200, first.text
    assert len(first.json()['items']) == 1
    cursor = first.json()['next_cursor']
    assert cursor
    return scope, headers, row, url, cursor

@pytest.mark.parametrize('aba_kind', ['permission', 'membership', 'session'])
def test_history_cursor_rejects_same_valued_authority_aba(rig, aba_kind):
    scope, headers, row, url, cursor = _collaboration_history_cursor(rig)
    if aba_kind == 'permission':
        rig.grants.revoke_permission('query-read', 'fixture')
        grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
        rig.grants.assign_permission(PermissionAssignment('query-read', 'reader', 'domain.read', ModalityDomain.NOVEL, grant_scope, 'fixture'))
    elif aba_kind == 'membership':
        rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.INACTIVE)
        rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.ACTIVE)
    else:
        rig.sessions.revoke('token-reader')
        rig.sessions.register('token-reader', SessionContext('session-reader', 'client', 'reader', 'query-workspace'))
    fresh = rig.client.get(url, headers=headers, params={'limit': 1})
    assert fresh.status_code == 200, fresh.text
    replay = rig.client.get(url, headers=headers, params={'limit': 1, 'cursor': cursor})
    assert replay.status_code == 422, replay.text
    assert 'items' not in replay.json()
    assert row['id'] not in replay.text
    assert cursor not in replay.text

def test_history_cursor_cannot_be_replayed_in_another_branch(rig):
    scope, headers, row, url, cursor = _collaboration_history_cursor(rig)
    other_scope = dict(scope, branch_id='query-branch-b')
    other_headers = dict(headers, **{'X-Branch-Id': 'query-branch-b'})
    other = rig.seed('other-branch.wav', 'audio', scope_value=other_scope, owner='reader')
    other_url = _history_url(rig, other['id'])
    fresh = rig.client.get(other_url, headers=other_headers, params={'limit': 1})
    assert fresh.status_code == 200, fresh.text
    own_replay = rig.client.get(url, headers=headers, params={'limit': 1, 'cursor': cursor})
    assert own_replay.status_code == 200, own_replay.text
    replay = rig.client.get(other_url, headers=other_headers, params={'limit': 1, 'cursor': cursor})
    assert replay.status_code == 422, replay.text
    assert 'items' not in replay.json()
    assert row['id'] not in replay.text
    assert cursor not in replay.text

def test_history_cursor_is_bound_to_actor_with_equal_read_access(rig):
    scope, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    rig.grants.assign_permission(PermissionAssignment('query-second-reader', 'no-grants', 'domain.read', ModalityDomain.NOVEL, grant_scope, 'fixture'))
    row = rig.seed('shared-cursor.wav', 'audio', scope_value=scope)
    with rig.workspace._asset_scope(rig.nid, scope):
        rig.assets.update_metadata(row['id'], {'parameters': {'take': 2}}, branch_id=scope['branch_id'], actor_id='reader', expected_version=1)
    url = _history_url(rig, row['id'])
    first = rig.client.get(url, headers=headers, params={'limit': 1})
    assert first.status_code == 200, first.text
    cursor = first.json()['next_cursor']
    assert cursor
    second_headers = {'X-Session-Token': 'token-no-grants', 'X-Branch-Id': 'query-branch-a'}
    fresh = rig.client.get(url, headers=second_headers, params={'limit': 1})
    assert fresh.status_code == 200, fresh.text
    own_replay = rig.client.get(url, headers=headers, params={'limit': 1, 'cursor': cursor})
    assert own_replay.status_code == 200, own_replay.text
    replay = rig.client.get(url, headers=second_headers, params={'limit': 1, 'cursor': cursor})
    assert replay.status_code == 422, replay.text
    assert 'items' not in replay.json()
    assert cursor not in replay.text

def test_restore_preview_missing_historical_blob_is_unavailable_without_writes(rig):
    row = rig.seed('missing-history.wav', 'audio')
    url = _history_url(rig, row['id'])
    initial = rig.client.get(url)
    assert initial.status_code == 200, initial.text
    record = initial.json()['items'][0]
    blob = rig.assets.root / '.audio-history' / row['id'] / 'blobs' / (record['sha256'] + '.bin')
    blob.unlink()
    before = _persisted_audio_files(rig)
    response = rig.client.post(f"{url}/{record['version_id']}/restore-preview", json={'operation_id': str(uuid.uuid4())})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['source_available'] is False
    assert value['binary_content_verified'] is False
    assert value['confirmation_available'] is False
    assert value['observation_token'] is None
    assert value['candidate']['created'] is False
    assert _persisted_audio_files(rig) == before
    assert str(blob) not in response.text

def test_restore_preview_rejects_soft_deleted_source_without_writes(rig):
    row = rig.seed('deleted-history.wav', 'audio')
    url = _history_url(rig, row['id'])
    initial = rig.client.get(url)
    assert initial.status_code == 200, initial.text
    version = initial.json()['items'][0]['version_id']
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.delete(row['id'], branch_id=rig.scope.get('branch_id'), actor_id='local-author')
    before = _persisted_audio_files(rig)
    response = rig.client.post(f'{url}/{version}/restore-preview', json={'operation_id': str(uuid.uuid4())})
    assert response.status_code == 404, response.text
    assert _persisted_audio_files(rig) == before
    assert 'deleted-history.wav' not in response.text

def test_history_observation_does_not_initialize_missing_owner(rig):
    row = rig.seed('missing-marker.wav', 'audio')
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        version = rig.assets.audio_history(row['id'])['head']
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    marker.unlink()
    before = _persisted_audio_files(rig)
    url = _history_url(rig, row['id'])
    for endpoint in (url, f'{url}/{version}', f'{url}/{version}/download'):
        response = rig.client.get(endpoint)
        assert response.status_code == 404, response.text
        assert not marker.exists()
        assert _persisted_audio_files(rig) == before
    preview = rig.client.post(f'{url}/{version}/restore-preview', json={'operation_id': 'missing-owner'})
    assert preview.status_code == 404, preview.text
    assert not marker.exists()
    assert _persisted_audio_files(rig) == before

def test_history_trace_real_lineage_pin(rig):
    parent = rig.seed('trace-parent.wav', 'audio')
    child = rig.seed('trace-child.wav', 'audio')
    url = f'/api/projects/{rig.nid}/studio/assets/{child["id"]}'
    response = rig.client.put(url + '/lineage', json={
        'expected_version': child['version'], 'origin': 'MANUAL_EDIT',
        'parent_asset_ids': [parent['id']], 'operation': 'Synthetic manual derivation'})
    assert response.status_code == 200, response.text
    child_version = response.json()['version']
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.update_metadata(parent['id'], {'parameters': {'synthetic_revision': 2}}, branch_id=None,
            expected_version=parent['version'])
    response = rig.client.get(url + '/history')
    assert response.status_code == 200, response.text
    version = next(row for row in response.json()['items'] if row['asset_version'] == child_version)
    assert version['sources'] == [{'kind': 'ASSET', 'id': parent['id'], 'version': parent['version'],
        'digest': parent['sha256'], 'state': 'HISTORICAL_VERIFIED', 'content_verified': False}]
    detail = rig.client.get(url + '/history/' + version['version_id'])
    assert detail.status_code == 200, detail.text
    assert detail.json()['version']['sources'] == version['sources']

def test_current_formal_source_does_not_authorize_old_private_pin(rig):
    parent = rig.seed('private-source.wav', 'audio', owner='alice')
    child = rig.seed('private-derivation.wav', 'audio', owner='alice')
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        derived = rig.assets.update_metadata(child['id'], {
            'source_asset_ids': [parent['id']],
            'parameters': {'asset_lineage_v2': {
                'schema': 'asset-lineage-v2', 'origin': 'MANUAL_EDIT',
                'license': {'label': 'UNSPECIFIED', 'source': '', 'note': ''},
                'license_verification': 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION',
                'operation': 'Synthetic private derivation', 'sources': {},
                'parents': {parent['id']: {'version': parent['version'], 'digest': parent['sha256']}},
                'output_digest': child['sha256']}}}, branch_id=None, actor_id='alice',
                expected_version=child['version'], _lineage_write=True)
        rig.assets.promote_owned(parent['id'], actor_id='alice', branch_id=None,
            expected_version=parent['version'], provenance={'operation': 'Synthetic owner review'}, guard=lambda: None)
        formal = rig.assets.promote_owned(child['id'], actor_id='alice', branch_id=None,
            expected_version=derived['version'], provenance={'operation': 'Synthetic owner review'}, guard=lambda: None)
        owner_history = rig.assets.audio_history(child['id'], branch_id=None, actor_id='alice')
        target = next(item['version_id'] for item in owner_history['items'] if item['asset_version'] == formal['version'])
    base = f'/api/projects/{rig.nid}/studio/assets/'
    control = rig.client.get(base + parent['id'] + '/history')
    assert control.status_code == 200, control.text
    assert all(item['asset_version'] != parent['version'] for item in control.json()['items'])
    for suffix in ('/history', '/history/' + target, '/history/' + target + '/download'):
        denied = rig.client.get(base + child['id'] + suffix)
        assert denied.status_code == 404, denied.text
        assert denied.json()['detail'] == {'code': 'AUDIO_HISTORY_UNAVAILABLE'}
        assert parent['id'] not in denied.text

def test_unversioned_source_declaration_never_invents_pin(rig):
    parent = rig.seed('unversioned-parent.wav', 'audio')
    child = rig.seed('unversioned-child.wav', 'audio')
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.update_metadata(child['id'], {'source_asset_ids': [parent['id']]},
            expected_version=child['version'])
    response = rig.client.get(_history_url(rig, child['id']))
    assert response.status_code == 200, response.text
    trace = response.json()['items'][0]['sources']
    assert trace == [{'kind': 'ASSET', 'id': parent['id'], 'state': 'UNVERSIONED_DECLARATION',
        'content_verified': False}]
    assert 'version' not in trace[0] and 'digest' not in trace[0]

def test_restore_preview_rejects_duplicate_json_keys_without_writes(rig):
    row = rig.seed('duplicate-request.wav', 'audio')
    url = _history_url(rig, row['id'])
    listing = rig.client.get(url)
    assert listing.status_code == 200, listing.text
    before = _persisted_audio_files(rig)
    version = listing.json()['head']
    response = rig.client.post(f'{url}/{version}/restore-preview',
        content='{"operation_id":"first","operation_id":"second"}',
        headers={'Content-Type': 'application/json'})
    assert response.status_code == 422, response.text
    assert _persisted_audio_files(rig) == before

def test_private_generated_audio_history_uses_creator_authority(rig):
    import base64
    scope, headers = shared_scope(rig)
    rig.grants.assign_permission(PermissionAssignment('audio-history-other-read', 'no-grants', 'domain.read',
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.PROJECT, scope['workspace_id'], rig.nid), 'fixture'))
    source = rig.seed('synthetic-origin-source.wav', 'audio', scope_value=scope)
    raw = b'synthetic private audio origin bytes'
    job_id = 'synthetic-owner-origin-reference'
    prompt = 'synthetic-private-prompt-sentinel'
    with rig.workspace._asset_scope(rig.nid, scope):
        origin = {'contract': 'studio-production-result/1', 'actor': 'reader',
            'scope_key': rig.workspace.store.key(rig.nid, scope),
            'incarnation': rig.workspace.store.incarnation(rig.nid), 'request_digest': 'a' * 64,
            'job_id': job_id, 'operation_id': 'm8.audio.trim',
            'sources': [{'kind': 'ASSET', 'asset_kind': 'audio', 'id': source['id'],
                'version': source['version'], 'digest': source['sha256']}],
            'provider_id': 'synthetic-provider', 'model_id': 'synthetic-model'}
        row = rig.assets.create(rig.nid, 'synthetic-private-result.wav', base64.b64encode(raw).decode(),
            'application/octet-stream', 'audio', branch_id=scope['branch_id'],
            required_features=('narrative_production_v2',), owner_actor_id='reader',
            guard=lambda: None, _initial_studio_result=origin)
        assert row.get('_origin_provenance') is None
        rig.assets.update_metadata(row['id'], {'parameters': {'prompt': prompt}},
            actor_id='reader', branch_id=scope['branch_id'], expected_version=row['version'])
    url = f'/api/projects/{rig.nid}/studio/assets/{row["id"]}/history'
    response = rig.client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['items']
    assert job_id not in response.text and prompt not in response.text
    assert 'provider_id' not in response.text and 'parameters' not in response.text
    target = response.json()['items'][0]['version_id']
    detail = rig.client.get(url + '/' + target, headers=headers)
    assert detail.status_code == 200, detail.text
    data = rig.client.get(url + '/' + target + '/download', headers=headers)
    assert data.status_code == 200 and data.content == raw
    other = {**headers, 'X-Session-Token': 'token-no-grants'}
    for suffix in ('', '/' + target, '/' + target + '/download'):
        denied = rig.client.get(url + suffix, headers=other)
        assert denied.status_code == 404, denied.text
        assert denied.json()['detail'] == {'code': 'AUDIO_HISTORY_UNAVAILABLE'}
        assert job_id not in denied.text and prompt not in denied.text and source['id'] not in denied.text

def test_history_cursor_rejects_changed_current_head(rig):
    row = rig.seed('changed-head.wav', 'audio')
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.update_metadata(row['id'], {'parameters': {'take': 2}}, expected_version=1)
    url = _history_url(rig, row['id'])
    page = rig.client.get(url, params={'limit': 1})
    assert page.status_code == 200, page.text
    cursor = page.json()['next_cursor']
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.update_metadata(row['id'], {'parameters': {'take': 3}}, expected_version=2)
    rejected = rig.client.get(url, params={'limit': 1, 'cursor': cursor})
    assert rejected.status_code == 422, rejected.text
    assert 'items' not in rejected.json()

def test_feature_revocation_before_return_discards_history(rig, monkeypatch):
    row = rig.seed('feature-race.wav', 'audio',
        required_features=('narrative_production_v2', 'asset_lineage_v2'))
    original = rig.assets.audio_history
    called = []
    def revoke_after_read(*args, **kwargs):
        result = original(*args, **kwargs)
        called.append(True)
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
        return result
    monkeypatch.setattr(rig.assets, 'audio_history', revoke_after_read)
    response = rig.client.get(_history_url(rig, row['id']))
    assert called == [True]
    assert response.status_code == 403, response.text
    assert row['id'] not in response.text
    assert 'feature-race.wav' not in response.text
