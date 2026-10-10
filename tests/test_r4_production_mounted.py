"""Mounted File/PG A09/A13 with existing membership and feature authorities."""
import base64
import inspect

import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture
def production_app(mounted, monkeypatch):
    e = mounted
    service = e.experimental.production_lineage_service
    for name, value in (('store', e.store), ('novels', e.novels), ('chapters', e.chapters), ('assets', e.assets), ('media', e.experimental.media_service)):
        monkeypatch.setattr(service, name, value)
    if service.broker:
        for name, value in (('store', e.store), ('novels', e.novels), ('chapters', e.chapters), ('media_registry', e.experimental.media_service.registry)):
            monkeypatch.setattr(service.broker, name, value)
        evidence = getattr(service.broker.evidence_reader, '__self__', None)
        if evidence is not None:
            for name, value in (('store', e.store), ('novels', e.novels), ('chapters', e.chapters)):
                monkeypatch.setattr(evidence, name, value)
    e.production = service
    # The legacy lifecycle router closes over its construction-time services.
    # Rebind those actual dependencies, not its handlers or authorization.
    def routes(router):
        for route in router.routes:
            included = getattr(route, 'original_router', None)
            if included is not None: yield from routes(included)
            else: yield route
    for route in routes(e.main.app):
        if getattr(route, 'name', None) not in {'trash', 'restore'}: continue
        captured = inspect.getclosurevars(route.endpoint).nonlocals
        if 'assets' in captured: monkeypatch.setattr(captured['assets'], 'root', e.assets.root)
        if 'capabilities' in captured: monkeypatch.setattr(captured['capabilities'], 'novels', e.novels)
    return e


def prepare(e, headers=None):
    brief = checked(e.client.post(e.base + '/media/cover-briefs', headers=headers, json={'title': 'Mounted synthetic fixture'}), 201)
    task = checked(e.client.post(e.base + '/media/tasks', headers=headers, json={'brief_id': brief['id'], 'expected_brief_version': 1, 'adapter_id': 'mock-image-v1'}), 201)
    task = checked(e.client.post(e.base + f"/media/tasks/{task['id']}/execute", headers=headers, json={'expected_version': 1}))
    manifest = checked(e.client.post(e.base + '/production/manifests', headers=headers, json={'task_id': task['id'], 'expected_task_version': task['version']}), 201)
    pf = checked(e.client.post(e.base + f"/production/manifests/{manifest['id']}/preflight", headers=headers, json={'expected_version': 1}))
    assert pf['ready'], pf
    replay = checked(e.client.post(e.base + f"/production/manifests/{manifest['id']}/replay", headers=headers, json={
        'expected_version': 1, 'preflight_digest': pf['preflight_digest'], 'idempotency_key': 'mounted-replay',
        'broker_decision_id': pf['broker_decision_id'], 'broker_decision_version': pf['broker_decision_version']}), 201)
    return task, manifest, replay


def test_mounted_production_real_replay_existing_review_no_automatic_assets(production_app):
    e = production_app; original, manifest, replay = prepare(e)
    assert replay['task_id'] != original['id']
    # The ordinary media endpoint cannot dispatch a replay without new guards.
    assert e.client.post(e.base + f"/media/tasks/{replay['task_id']}/execute", json={'expected_version': 1}).status_code == 422
    result = checked(e.client.post(e.base + f"/production/replays/{replay['id']}/execute", json={'expected_task_version': 1}))
    assert result['status'] == 'SUCCEEDED' and result['byte_equal'] is True
    assert all(row['status'] == 'PENDING_REVIEW' for row in result['outputs'])
    assert not e.assets.list(e.nid)
    exported = checked(e.client.get(e.base + f"/production/manifests/{manifest['id']}/export"))
    assert not exported['redaction']['raw_prompts']
    assert e.client.get(e.base + '/production/assets').headers['cache-control'] == 'no-store'


def test_mounted_production_exact_flags_acceptance_and_legacy_capture_off(production_app, monkeypatch):
    e = production_app
    from app.experimental.flags import FLAGS
    for flags, acceptance in [('', 'false'), ('*', 'false'), ('production_manifest_v2', 'false'), (','.join(FLAGS), 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        for path in ('/production/assets', '/production/manifests', '/production/replays'):
            assert e.client.get(e.base + path).status_code == 404
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'media_adapter_registry,cover_storyboard_generation')
    brief = checked(e.client.post(e.base + '/media/cover-briefs', json={'title': 'Legacy mode'}), 201)
    task = checked(e.client.post(e.base + '/media/tasks', json={'brief_id': brief['id'], 'expected_brief_version': 1, 'adapter_id': 'mock-image-v1'}), 201)
    assert 'queued_environment' not in task
    result = checked(e.client.post(e.base + f"/media/tasks/{task['id']}/execute", json={'expected_version': 1}))
    assert 'observed_environment' not in result
    assert e.client.post(e.base + '/media/tasks', json={'brief_id': brief['id'], 'expected_brief_version': 1, 'adapter_id': 'mock-image-v1', 'production_replay_id': 'forged'}).status_code == 422


def test_mounted_legacy_upload_cannot_smuggle_new_lineage_metadata(production_app, monkeypatch):
    e = production_app
    for acceptance in ('false', 'true'):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', ''); monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        row = checked(e.client.post(e.prefix + f'/novels/{e.nid}/assets', json={'novel_id': e.nid, 'filename': 'synthetic.bin', 'content_base64': base64.b64encode(b'synthetic').decode(),
            'parameters': {'asset_lineage_v2': {'origin': 'ORIGINAL_INPUT'}}, 'source_asset_ids': ['secret-parent']}))
        assert 'asset_lineage_v2' not in row.get('parameters', {}) and not row.get('source_asset_ids')
        assert e.client.put(e.base + f"/production/assets/{row['id']}/lineage", json={'expected_version': row['version'], 'origin': 'ORIGINAL_INPUT'}).status_code == 404


def test_mounted_current_actor_branch_and_revocation_before_replay(production_app, monkeypatch):
    e = scoped(production_app, monkeypatch)
    _, m, replay = prepare(e, e.headers)
    assert e.client.post(e.base + f"/production/manifests/{m['id']}/preflight", headers=e.viewer_headers, json={'expected_version': 1}).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    for path in ('/production/assets', '/production/manifests', '/production/replays'):
        assert e.client.get(e.base + path, headers=e.headers).status_code == 403
    assert e.client.post(e.base + f"/production/replays/{replay['id']}/execute", headers=e.headers, json={'expected_task_version': 1}).status_code == 403


def test_mounted_flag_revocation_closes_ordinary_media_dispatch_for_replay(production_app, monkeypatch):
    e = production_app; _, _, replay = prepare(e)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'media_adapter_registry,cover_storyboard_generation')
    assert e.client.post(e.base + f"/production/replays/{replay['id']}/execute", json={'expected_task_version': 1}).status_code == 404
    assert e.client.post(e.base + f"/media/tasks/{replay['task_id']}/execute", json={'expected_version': 1}).status_code == 422
    task = e.experimental.media_service.get(e.nid, e.scope, e.experimental.media_service.TASKS, replay['task_id'])
    assert task['status'] == 'QUEUED'


def test_mounted_off_and_acceptance_hide_prior_lineage_but_preserve_legacy_metadata(production_app, monkeypatch):
    e = production_app
    upload = {'novel_id': e.nid, 'filename': 'original.bin', 'content_base64': base64.b64encode(b'fixture').decode()}
    parent = checked(e.client.post(e.prefix + f'/novels/{e.nid}/assets', json=upload))
    headers = {'Idempotency-Key': 'projection-owned-asset'}
    child = checked(e.client.post(e.prefix + f'/novels/{e.nid}/assets', headers=headers, json={**upload, 'filename': 'child.bin'}))
    checked(e.client.put(e.base + f"/production/assets/{child['id']}/lineage", json={'expected_version': 1, 'origin': 'DERIVED_PROCESSING', 'parent_asset_ids': [parent['id']]}))
    e.assets.update_metadata(child['id'], {'parameters': {'legacy_parameter': 'preserved'}})
    from app.experimental.flags import FLAGS
    for flags, acceptance in [('', 'false'), (','.join(FLAGS), 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        got = checked(e.client.get(e.prefix + f"/assets/{child['id']}?novel_id={e.nid}"))
        assert got['source_asset_ids'] == [parent['id']]
        assert got['parameters'] == {'legacy_parameter': 'preserved'}
        listed = checked(e.client.get(e.prefix + f'/novels/{e.nid}/assets'))
        assert all('asset_lineage_v2' not in row.get('parameters', {}) for row in listed)
        # Idempotent re-upload is also a metadata response, not a loophole.
        reused = checked(e.client.post(e.prefix + f'/novels/{e.nid}/assets', headers=headers, json={**upload, 'filename': 'child.bin'}))
        assert reused['parameters'] == got['parameters'] and reused['id'] == child['id']
        checked(e.client.delete(e.prefix + f"/assets/{child['id']}?novel_id={e.nid}"))
        trash = checked(e.client.get(e.prefix + f'/novels/{e.nid}/asset-trash'))
        assert all('asset_lineage_v2' not in row.get('parameters', {}) for row in trash['items'])
        restored = checked(e.client.post(e.prefix + f"/novels/{e.nid}/assets/{child['id']}/restore"))
        assert restored['parameters'] == {'legacy_parameter': 'preserved'}
        assert 'asset_lineage_v2' in e.assets.get(child['id'])['parameters']
