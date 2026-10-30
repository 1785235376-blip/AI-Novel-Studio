"""Real File commit/recreation ordering with synthetic U16 source checks."""
import threading
from copy import deepcopy
import os
import subprocess
import sys
import textwrap

import pytest

from app.actor_context import SessionContext
from app.experimental import store as store_module
from app.experimental.common import change_row
from app.experimental.planning import digest
from test_studio_asset_query import rig
from test_u16_capacity_claim import instrumented_batch


def test_mixed_stop_commits_before_project_recreation(rig, monkeypatch):
    old_identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'])
    # The original image snapshot carries the project-owner incarnation.
    with service.store.transaction(rig.nid, rig.scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot']['steps'][0]['configuration'] = {'incarnation': old_identity}
        row['snapshot_digest'] = digest(row['snapshot'])
    started, finished = threading.Event(), threading.Event()
    errors, owner_at_replace = [], []
    def recreate():
        try:
            started.set()
            rig.novels.delete(rig.nid)
            rig.project(rig.nid)
            rig.workspace.store.incarnation(rig.nid)
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()
    thread = threading.Thread(target=recreate)
    def original_guard():
        # This is the original project identity check, but _owned/_assert are
        # stubbed by the synthetic fixture; no claim of full U16 auth coverage.
        assert rig.workspace.store.incarnation(rig.nid) == old_identity
        thread.start()
        assert started.wait(10)
        finished.wait(.3)
    original_write = store_module.atomic_write
    def observe_replace(path, contents):
        if path == service.store.path(rig.nid, rig.scope):
            owner_at_replace.append(rig.workspace.store.incarnation(rig.nid))
        return original_write(path, contents)
    monkeypatch.setattr(store_module, 'atomic_write', observe_replace)
    service.stop(ctx, batch['id'], {'expected_version': batch['version']}, original_guard)
    thread.join(10)
    assert not thread.is_alive() and not errors
    assert rig.workspace.store.incarnation(rig.nid) != old_identity
    assert owner_at_replace == [old_identity]


@pytest.mark.parametrize('alias', [False, True])
def test_mixed_stop_http_keeps_host_and_project_fence(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    old_identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'], actor='local-author')
    with service.store.transaction(rig.nid, rig.scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot']['steps'][0]['configuration'] = {'incarnation': old_identity}
        row['snapshot_digest'] = digest(row['snapshot'])
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', service.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    # Real mounted host, session, project identity, File scope and transaction.
    # The historical row/source lookup itself is an explicit synthetic stub.
    monkeypatch.setattr(mounted, '_owned', service._owned)
    monkeypatch.setattr(mounted, '_public', lambda row: deepcopy(row))
    started, finished = threading.Event(), threading.Event()
    errors, owner_at_replace = [], []
    def recreate():
        try:
            started.set()
            rig.novels.delete(rig.nid)
            rig.project(rig.nid)
            rig.workspace.store.incarnation(rig.nid)
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()
    thread = threading.Thread(target=recreate)
    original_write = store_module.atomic_write
    def observe_replace(path, contents):
        if path == service.store.path(rig.nid, rig.scope):
            thread.start()
            assert started.wait(10)
            finished.wait(.3)
            owner_at_replace.append(rig.workspace.store.incarnation(rig.nid))
        return original_write(path, contents)
    monkeypatch.setattr(store_module, 'atomic_write', observe_replace)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop'
    unauthorized = rig.client.post(path, json={'expected_version': batch['version']})
    assert unauthorized.status_code == 401, unauthorized.text
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'},
                               json={'expected_version': batch['version']})
    thread.join(10)
    assert not thread.is_alive() and not errors
    assert response.status_code in (200, 403, 404), response.text
    assert owner_at_replace == [old_identity]
    assert rig.workspace.store.incarnation(rig.nid) != old_identity


def test_original_authority_lease_orders_stop_before_membership_revocation(rig, monkeypatch):
    from app import api
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.identity import IdentityStatus
    from test_studio_asset_query import shared_scope
    scope, headers = shared_scope(rig)
    rig.scope = scope
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    rig.grants.assign_permission(PermissionAssignment('u16-write', 'reader', 'domain.write',
        ModalityDomain.NOVEL, grant_scope, 'synthetic'))
    monkeypatch.setattr(api, 'authorization_service', rig.grants)
    old_identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'], actor='reader')
    with service.store.transaction(rig.nid, scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot']['steps'][0]['configuration'] = {'incarnation': old_identity}
        row['snapshot_digest'] = digest(row['snapshot'])
    token = headers['X-Session-Token']
    def guard():
        actor, selected = api._workbench_authorize(rig.nid, token, 'query-branch-a', 'domain.write')
        assert (actor, selected) == ('reader', scope)
    started, finished = threading.Event(), threading.Event()
    errors, membership_at_replace = [], []
    def revoke():
        try:
            started.set()
            rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.INACTIVE)
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()
    thread = threading.Thread(target=revoke)
    original_write = store_module.atomic_write
    def observe_replace(path, contents):
        if path == service.store.path(rig.nid, scope):
            thread.start()
            assert started.wait(10)
            finished.wait(.3)
            membership_at_replace.append(rig.identities.get_membership('reader', 'query-workspace').status)
        return original_write(path, contents)
    monkeypatch.setattr(store_module, 'atomic_write', observe_replace)
    # The original authorization lease is acquired before scope/project locks.
    # The synthetic fixture stubs row/source visibility, not the authorizer.
    with api._workbench_authority_lease(rig.nid, token, 'reader', scope):
        guard()
        result = service.stop(ctx, batch['id'], {'expected_version': batch['version']}, guard)
        assert result['status'] == 'CANCELLED' and not finished.is_set()
    thread.join(10)
    assert not thread.is_alive() and not errors
    assert membership_at_replace == [IdentityStatus.ACTIVE]
    assert rig.identities.get_membership('reader', 'query-workspace').status == IdentityStatus.INACTIVE


def test_mixed_stop_file_owner_orders_actual_child_process_recreation(rig, monkeypatch, tmp_path):
    old_identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'])
    with service.store.transaction(rig.nid, rig.scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot']['steps'][0]['configuration'] = {'incarnation': old_identity}
        row['snapshot_digest'] = digest(row['snapshot'])
    script = tmp_path / 'synthetic_recreate.py'
    ready = tmp_path / 'child-ready'
    script.write_text(textwrap.dedent('''
        from pathlib import Path
        import sys
        from app.config import Settings
        from app.creative.project_store import CreativeProjectStore
        from app.experimental.store import ExperimentalStore
        from app.repositories.factory import create_repository_bundle
        from app.services import NovelService
        root, nid, ready = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
        bundle = create_repository_bundle(Settings(storage_backend='file', novel_data=root,
            enable_cloud=False, mock_provider=True), data_root=root)
        novels = NovelService(bundle.novels, bundle.chapters)
        ready.write_text('ready', encoding='utf-8')
        novels.delete(nid)
        novels.create({'id': nid, 'title': 'Synthetic recreated project'})
        print(CreativeProjectStore(ExperimentalStore(root, 'file', '')).incarnation(nid), flush=True)
    '''), encoding='utf-8')
    process = None
    owner_at_replace = []
    original_write = store_module.atomic_write
    def observe_replace(path, contents):
        nonlocal process
        if path == service.store.path(rig.nid, rig.scope):
            process = subprocess.Popen([sys.executable, str(script), str(rig.root), rig.nid, str(ready)],
                                       cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Wait for the child to reach the actual repository operation, not
            # merely for process creation. It must not complete the delete yet.
            import time
            deadline = time.monotonic() + 10
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            assert ready.exists(), 'child failed before entering the project operation'
            try:
                process.wait(timeout=.3)
            except subprocess.TimeoutExpired:
                pass
            owner_at_replace.append(rig.workspace.store.incarnation(rig.nid))
        return original_write(path, contents)
    monkeypatch.setattr(store_module, 'atomic_write', observe_replace)
    service.stop(ctx, batch['id'], {'expected_version': batch['version']})
    assert process is not None
    stdout, stderr = process.communicate(timeout=15)
    assert process.returncode == 0, stderr.decode('utf-8', errors='replace')
    assert stdout.decode('utf-8').strip() != old_identity
    assert owner_at_replace == [old_identity]


@pytest.mark.parametrize('alias', [False, True])
def test_mixed_stop_http_holds_real_host_session_until_file_commit(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    old_identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'], actor='local-author')
    with service.store.transaction(rig.nid, rig.scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot']['steps'][0]['configuration'] = {'incarnation': old_identity}
        row['snapshot_digest'] = digest(row['snapshot'])
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', service.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    monkeypatch.setattr(mounted, '_owned', service._owned)
    monkeypatch.setattr(mounted, '_public', lambda row: deepcopy(row))
    started, finished = threading.Event(), threading.Event()
    errors, valid_at_replace = [], []
    def revoke():
        try:
            started.set()
            rig.sessions.revoke('synthetic-host')
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()
    thread = threading.Thread(target=revoke)
    original_write = store_module.atomic_write
    def observe_replace(path, contents):
        if path == service.store.path(rig.nid, rig.scope):
            thread.start()
            assert started.wait(10)
            finished.wait(.3)
            try:
                rig.sessions.resolve('synthetic-host')
                valid_at_replace.append(True)
            except KeyError:
                valid_at_replace.append(False)
        return original_write(path, contents)
    monkeypatch.setattr(store_module, 'atomic_write', observe_replace)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop'
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'},
                               json={'expected_version': batch['version']})
    thread.join(10)
    assert not thread.is_alive() and not errors
    assert response.status_code in (200, 401, 403), response.text
    assert valid_at_replace == [True]
    assert finished.is_set()


def test_mixed_stop_and_edit_have_one_cas_winner(rig, monkeypatch):
    identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'])
    with service.store.transaction(rig.nid, rig.scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot']['steps'][0]['configuration'] = {'incarnation': identity}
        row['snapshot_digest'] = digest(row['snapshot'])
    barrier = threading.Barrier(2)
    errors, outcomes = [], []
    original_owned = service._owned
    def concurrent_owned(ctx, rid):
        row = original_owned(ctx, rid)
        barrier.wait(timeout=10)
        return row
    monkeypatch.setattr(service, '_owned', concurrent_owned)
    def cancel():
        try:
            service.stop(ctx, batch['id'], {'expected_version': batch['version']})
            outcomes.append('stop')
        except Exception as exc:
            errors.append(exc)
    def edit():
        try:
            barrier.wait(timeout=10)
            with service.store.transaction(rig.nid, rig.scope) as doc:
                row = doc['collections'][service.BATCHES][batch['id']]
                change_row(row, ctx.actor, batch['version'], lambda r: r.update(status='PARTIAL'))
            outcomes.append('edit')
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=cancel), threading.Thread(target=edit)]
    for thread in threads: thread.start()
    for thread in threads: thread.join(15)
    assert all(not thread.is_alive() for thread in threads)
    assert len(outcomes) == len(errors) == 1
    assert type(errors[0]).__name__ == 'CapabilityVersionConflict'
    final = service.get(rig.nid, rig.scope, service.BATCHES, batch['id'])
    assert final['version'] == batch['version'] + 1
    assert final['status'] == ('CANCELLED' if outcomes == ['stop'] else 'PARTIAL')


def test_old_mixed_batch_is_not_adopted_after_same_id_recreation(rig, monkeypatch):
    old_identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'])
    with service.store.transaction(rig.nid, rig.scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot']['steps'][0]['configuration'] = {'incarnation': old_identity}
        row['snapshot_digest'] = digest(row['snapshot'])
    rig.novels.delete(rig.nid)
    rig.project(rig.nid)
    assert rig.workspace.store.incarnation(rig.nid) != old_identity
    before = service.store._file_bytes(rig.nid, rig.scope)
    with pytest.raises(ValueError, match='BATCH_STUDIO_IMAGE_OWNER_CHANGED'):
        service.stop(ctx, batch['id'], {'expected_version': batch['version']})
    assert service.store._file_bytes(rig.nid, rig.scope) == before


def test_unbound_old_mixed_batch_is_not_silently_adopted(rig, monkeypatch):
    rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'])
    with service.store.transaction(rig.nid, rig.scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot_digest'] = digest(row['snapshot'])
    before = service.store._file_bytes(rig.nid, rig.scope)
    with pytest.raises(ValueError, match='BATCH_STUDIO_IMAGE_OWNER_CHANGED'):
        service.stop(ctx, batch['id'], {'expected_version': batch['version']})
    assert service.store._file_bytes(rig.nid, rig.scope) == before


def test_nonimage_batch_stop_retains_existing_behavior(rig, monkeypatch):
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['EXPORT'], ['PENDING'])
    result = service.stop(ctx, batch['id'], {'expected_version': batch['version']})
    assert result['status'] == 'CANCELLED' and result['items'][0]['status'] == 'CANCELLED'


def real_mixed_batch(rig, monkeypatch):
    """Synthetic historical batch; original _owned source and host checks remain."""
    from app.experimental import api as experimental_api
    from app.experimental.common import new_row
    from app.experimental.voice_direction_api import create_runtime_executor
    from test_voice_queue_execution_closed import prepared
    from types import SimpleNamespace
    voice, chapter, plan, segment, _ = prepared(rig, monkeypatch)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    image, mask = rig.seed('image.bin', 'image'), rig.seed('mask.bin', 'image')
    def snap(row):
        return {'id': row['id'], 'kind': 'ASSET', 'asset_kind': 'image', 'version': row['version'], 'digest': row['sha256']}
    selection = {'request_id': 'synthetic', 'image': snap(image), 'mask': snap(mask)}
    executor = create_runtime_executor(rig.scope, 'local-author')
    config = {'provider_id': 'local', 'model_id': 'local', 'voice': 'synthetic',
        'experimental_origin': 'voice_direction_v2', 'local_only': True, 'max_cost': 0,
        'direction_binding': {'plan_id': plan['id'], 'segment_id': segment['id'],
            'fingerprint': voice.segment_fingerprint(segment), 'actor': 'local-author', 'scope': rig.scope}}
    job = executor.queue(rig.nid, chapter, config, [], source_chapter=chapter)
    identity = rig.workspace.store.incarnation(rig.nid)
    image_step = {'input': {'kind': 'STUDIO_IMAGE', 'studio_image': selection}, 'sources': {},
        'source_versions': {}, 'configuration': {'incarnation': identity, 'command': {'request_id': 'synthetic'}},
        'resource_requirements': [], 'permission': 'STUDIO_HOST_AND_DOMAIN_WRITE'}
    voice_step = {'input': {'kind': 'VOICE_REDO', 'voice_job_id': job['id'], 'broker_preview_id': 'synthetic'},
        'sources': {chapter['id']: 'a' * 64}, 'source_versions': {chapter['id']: chapter['version']},
        'configuration': {}, 'resource_requirements': [], 'permission': 'domain.write'}
    frozen = {'steps': [image_step, voice_step], 'budget': {'state': 'NOT_CONFIGURED'}, 'concurrency': 1}
    items = [{'index': i, 'status': 'PENDING', 'attempts': 0, 'receipts': [], 'claim': None} for i in range(2)]
    batch = new_row(rig.nid, rig.scope, 'local-author', {'status': 'READY', 'confirmed': True,
        'snapshot_digest': digest(frozen), 'snapshot': frozen, 'items': items})
    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['safe_batches_v2'] = {batch['id']: batch}
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', rig.workspace.store.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    monkeypatch.setattr(mounted, 'chapters', rig.workspace.creative.chapters)
    monkeypatch.setattr(mounted, 'sources', SimpleNamespace(novels=rig.novels, chapter_reader=None))
    return batch


@pytest.mark.parametrize('alias', [False, True])
def test_real_owned_mixed_sources_stop_and_reopen(rig, monkeypatch, alias):
    batch = real_mixed_batch(rig, monkeypatch)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop'
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'},
                               json={'expected_version': batch['version']})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'CANCELLED'
    persisted = rig.workspace.store.store.read(rig.nid, rig.scope)['collections']['safe_batches_v2'][batch['id']]
    assert persisted['status'] == 'CANCELLED' and persisted['version'] == batch['version'] + 1


@pytest.mark.parametrize('alias', [False, True])
def test_real_owned_mixed_sources_do_not_stop_recreated_project(rig, monkeypatch, alias):
    batch = real_mixed_batch(rig, monkeypatch)
    rig.novels.delete(rig.nid)
    rig.project(rig.nid)
    before = rig.workspace.store.store._file_bytes(rig.nid, rig.scope)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop'
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'},
                               json={'expected_version': batch['version']})
    assert response.status_code in (404, 409, 422), response.text
    assert rig.workspace.store.store._file_bytes(rig.nid, rig.scope) == before


@pytest.mark.parametrize('alias', [False, True])
def test_real_owned_mixed_stop_does_not_commit_under_recreated_project(rig, monkeypatch, alias):
    batch = real_mixed_batch(rig, monkeypatch)
    old_identity = rig.workspace.store.incarnation(rig.nid)
    started, finished = threading.Event(), threading.Event()
    errors, owner_at_replace = [], []
    def recreate():
        try:
            started.set()
            rig.novels.delete(rig.nid)
            rig.project(rig.nid)
            rig.workspace.store.incarnation(rig.nid)
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()
    thread = threading.Thread(target=recreate)
    original_write = store_module.atomic_write
    def observe_replace(path, contents):
        if path == rig.workspace.store.store.path(rig.nid, rig.scope):
            thread.start()
            assert started.wait(10)
            finished.wait(.3)
            owner_at_replace.append(rig.workspace.store.incarnation(rig.nid))
        return original_write(path, contents)
    monkeypatch.setattr(store_module, 'atomic_write', observe_replace)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop'
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'},
                               json={'expected_version': batch['version']})
    thread.join(10)
    assert not thread.is_alive() and not errors
    assert response.status_code in (200, 403, 404), response.text
    assert owner_at_replace == [old_identity]
    assert rig.workspace.store.incarnation(rig.nid) != old_identity


@pytest.mark.parametrize('alias', [False, True])
def test_missing_host_commit_lease_fails_closed(rig, monkeypatch, alias):
    from app import main
    from app.experimental import api as experimental_api
    from types import SimpleNamespace
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    identity = rig.workspace.store.incarnation(rig.nid)
    service, batch, ctx = instrumented_batch(rig, monkeypatch, ['STUDIO_IMAGE', 'VOICE_REDO'],
                                               ['PENDING', 'PENDING'], actor='local-author')
    with service.store.transaction(rig.nid, rig.scope) as doc:
        row = doc['collections'][service.BATCHES][batch['id']]
        row['snapshot']['steps'][0]['configuration'] = {'incarnation': identity}
        row['snapshot_digest'] = digest(row['snapshot'])
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', service.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    monkeypatch.setattr(mounted, '_owned', service._owned)
    original_authority = main._local_discovery_host_authority
    def no_lease(request, token):
        authority = original_authority(request, token)
        return SimpleNamespace(principal=authority.principal, guard=authority.guard, lease=None)
    monkeypatch.setattr(main, '_local_discovery_host_authority', no_lease)
    before = service.store._file_bytes(rig.nid, rig.scope)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop'
    response = rig.client.post(path, headers={'X-Session-Token': 'synthetic-host'},
                               json={'expected_version': batch['version']})
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'LOCAL_AI_HOST_COMMIT_LEASE_UNSUPPORTED'
    assert service.store._file_bytes(rig.nid, rig.scope) == before


def test_simulated_packaged_host_commit_lease_is_explicitly_unsupported(rig):
    from fastapi import HTTPException, Request
    from app.model_center.discovery_authority import resolve_discovery_authority
    from types import SimpleNamespace
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    manager = SimpleNamespace(sessions=rig.sessions, expected_origin='http://127.0.0.1',
                              resolve_issued_session=rig.sessions.resolve)
    settings = SimpleNamespace(enable_packaged_runtime=True, enable_collaboration_runtime=True,
                               frontend_origin='http://127.0.0.1')
    request = Request({'type': 'http', 'method': 'POST', 'scheme': 'http', 'path': '/',
                       'client': ('127.0.0.1', 12345), 'server': ('127.0.0.1', 80),
                       'query_string': b'', 'headers': []})
    authority = resolve_discovery_authority(request, 'synthetic-host', settings_getter=lambda: settings,
        resolver_getter=lambda: rig.sessions, bootstrap_getter=lambda: manager)
    with pytest.raises(HTTPException) as exc:
        with authority.lease():
            pytest.fail('simulated packaged commit must not be admitted')
    assert exc.value.status_code == 503
    assert exc.value.detail['code'] == 'LOCAL_AI_HOST_COMMIT_LEASE_UNSUPPORTED'
