"""U16 actual File + mounted API/Host/ImageJob + CPU pixels, no provider/GPU."""
from copy import deepcopy
import json
import os

import pytest

from app.experimental.flags import FLAGS
from app.experimental.ux import ReadContext
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_manual_mask_api import mask_client
from test_v2_cpu_cutout_api import cpu_client, action


@pytest.fixture
def images(cpu_client, monkeypatch):
    e = cpu_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join([*FLAGS, 'narrative_production_v2']))
    e.batch_base = e.prefix + f'/novels/{e.nid}/experimental/safe-batches'
    e.batches = e.experimental.safe_batches_service
    e.item = {'kind': 'STUDIO_IMAGE', 'studio_image': {'image': deepcopy(e.command['source_snapshots'][0]),
        'mask': deepcopy(e.command['source_snapshots'][1]), 'request_id': 'u16-cutout-one', 'license_note': 'synthetic test-owned images'}}
    return e


def post(e, suffix, body):
    return e.client.post(e.batch_base + suffix, headers=e.headers, json=body)


def freeze(e, items=None):
    return checked(post(e, '/preflight', {'items': items or [e.item]}))


def version(row): return {'expected_version': row['version']}


def confirm(e, row):
    return checked(post(e, '/' + row['id'] + '/confirm', {**version(row), 'snapshot_digest': row['snapshot_digest'],
        'budget_microusd': 0, 'confirmed': True}))


def dispatch(e, row): return post(e, '/' + row['id'] + '/dispatch-next', version(row))


def read(e): return checked(e.client.get(e.batch_base, headers=e.headers))['items'][-1]


def review_body(row):
    job = row['items'][0]['image_result']
    return {**version(row), 'snapshot_digest': row['snapshot_digest'], 'confirmed': True, 'budget_microusd': 0,
        'item_index': 0, 'job_id': job['id'], 'expected_job_version': job['version'],
        'expected_request_digest': job['request_digest'], 'reviewed_output_digest': job['output_candidate']['digest']}


def test_original_preflight_confirm_no_job_one_dispatch_and_per_item_review(images, tmp_path):
    e = images
    catalog = checked(e.client.get(e.batch_base + '/studio-image/catalog', headers=e.headers))
    assert {a['id'] for a in catalog['assets']} == {e.source['id'], e.mask['id']}
    assert catalog['automatic_dispatch'] is False and catalog['model'] == 'NONE'
    row = freeze(e)
    frozen = deepcopy(row)
    assert row['status'] == 'PREFLIGHT' and row['items'][0]['attempts'] == 0
    config = row['items'][0]['configuration_summary']['command']
    assert config['source_snapshots'][0]['id'] == e.source['id']
    assert config['source_snapshots'][1]['id'] == e.mask['id']
    assert config['provider_id'] is None and config['model_id'] is None and config['allow_cloud'] is False
    assert checked(e.client.get(e.base + '/jobs', headers=e.headers))['items'] == []
    row = confirm(e, row)
    assert checked(e.client.get(e.base + '/jobs', headers=e.headers))['items'] == []
    done = checked(dispatch(e, row))
    job = done['items'][0]['image_result']
    assert done['status'] == 'COMPLETED' and job['status'] == 'AWAITING_REVIEW'
    assert done['items'][0]['attempts'] == 1 and done['items'][0]['image_job_id'] == job['id']
    assert e.client.get(e.base + '/jobs/image/' + job['id'], headers=e.headers).status_code == 404
    assert e.client.get(e.studio_base + '/assets/' + job['output_candidate']['id'], headers=e.headers).status_code == 404
    candidate = e.client.get(e.batch_base + '/' + row['id'] + '/items/0/image', headers=e.headers)
    assert candidate.status_code == 200, candidate.text
    assert candidate.headers['content-type'].startswith('image/png')
    assert candidate.content.startswith(b'\x89PNG') and candidate.headers['cache-control'] == 'no-store'
    approved = checked(post(e, '/' + row['id'] + '/approve-image', review_body(done)))
    assert approved['items'][0]['image_result']['status'] == 'APPROVED'
    asset = checked(e.client.get(e.studio_base + '/assets/' + job['output_candidate']['id'], headers=e.headers))
    assert asset['provenance']['origin'] == 'DERIVED_PROCESSING'
    assert dispatch(e, approved).status_code == 422
    assert read(e)['items'][0]['image_result']['status'] == 'APPROVED'
    if os.environ.get('U16_CAPTURE') == '1':
        (tmp_path / 'u16-studio-image.file-api.json').write_text(json.dumps({'provenance': 'actual mounted File API + original trusted Studio Host invoker + CPU ImageJob; synthetic owned pixels; not live Host/PG',
            'catalog': catalog, 'selection': e.item, 'preflight': frozen, 'ready': row, 'executed': done, 'approved': approved}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


@pytest.mark.parametrize('change', ['wrong_source', 'wrong_digest', 'duplicate', 'over20', 'concurrency', 'budget', 'cloud', 'mixed_input'])
def test_invalid_or_unbounded_selections_never_create_jobs(images, change):
    e = images
    body = {'items': [deepcopy(e.item)]}
    if change == 'wrong_source': body['items'][0]['studio_image']['image']['id'] = 'foreign-or-hidden'
    elif change == 'wrong_digest': body['items'][0]['studio_image']['mask']['digest'] = 'f' * 64
    elif change == 'duplicate': body['items'] *= 2
    elif change == 'over20': body['items'] *= 21
    elif change == 'concurrency': body['concurrency'] = 2
    elif change == 'budget': body['budget_microusd'] = 1
    elif change == 'cloud': body['items'][0]['studio_image']['allow_cloud'] = True
    else: body['items'][0]['chapter_ids'] = [e.chapter['id']]
    assert post(e, '/preflight', body).status_code in {404, 409, 422}
    assert len(list(e.assets.root.glob('*.bin'))) == 2


@pytest.mark.parametrize('change', ['origin', 'forwarded', 'host', 'studio_flag', 'lineage', 'incarnation', 'source'])
def test_authority_source_and_incarnation_change_prevent_dispatch(images, monkeypatch, change):
    e = images
    row = confirm(e, freeze(e))
    if change == 'origin': e.headers['Origin'] = 'https://untrusted.invalid'
    elif change == 'forwarded': e.headers['Forwarded'] = 'for=127.0.0.1'
    elif change == 'host': e.sessions.revoke(e.host)
    elif change in {'studio_flag', 'lineage'}:
        removed = 'narrative_production_v2' if change == 'studio_flag' else 'asset_lineage_v2'
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(f for f in [*FLAGS, 'narrative_production_v2'] if f != removed))
    elif change == 'incarnation':
        from uuid import uuid4
        monkeypatch.setattr(e.production.store, 'incarnation', lambda nid: 'file:' + str(uuid4()))
    else:
        with e.studio._asset_scope(e.nid, e.scope):
            e.assets.update_metadata(e.source['id'], {'scene_id': 'changed'}, expected_version=e.source['version'])
    assert dispatch(e, row).status_code in {401, 403, 404, 409, 422}
    assert len(list(e.assets.root.glob('*.bin'))) == 2


@pytest.mark.parametrize('change', ['stop', 'revoke_aba', 'source'])
def test_late_stop_revocation_or_source_change_discards_candidate_without_next_stage(images, monkeypatch, change):
    e = images
    row = confirm(e, freeze(e, [e.item, {'kind': 'PROOF', 'chapter_ids': [e.chapter['id']]}]))
    import app.services.studio_image_cutout as pixels
    original = pixels.render_cutout
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if change == 'stop':
            fresh = read(e)
            assert checked(post(e, '/' + row['id'] + '/stop', version(fresh)))['status'] == 'CANCELLED'
        elif change == 'revoke_aba':
            e.sessions.revoke(e.host); e.sessions.register(e.host, e.session)
        else:
            with e.studio._asset_scope(e.nid, e.scope):
                e.assets.update_metadata(e.source['id'], {'scene_id': 'late-change'}, expected_version=e.source['version'])
        return result
    monkeypatch.setattr(pixels, 'render_cutout', changed)
    response = dispatch(e, row)
    assert response.status_code in {401, 403, 404, 409, 422}
    visible = checked(e.client.get(e.batch_base, headers=e.headers))['items']
    current = visible[-1] if visible else e.batches.get(e.nid, e.scope, e.batches.BATCHES, row['id'])
    assert current['status'] in {'CANCELLED', 'UNKNOWN'}
    if not current.get('stale'):
        assert current['items'][1]['attempts'] == 0
    assert len(list(e.assets.root.glob('*.bin'))) == 2
    assert dispatch(e, current).status_code in {403, 409, 422}


@pytest.mark.parametrize('lost_at', ['create', 'execute'])
def test_unknown_retains_exact_key_and_queries_original_receipt_without_resending(images, monkeypatch, lost_at):
    e = images
    row = confirm(e, freeze(e))
    calls = []
    original = getattr(e.production, lost_at)
    def lost(*args, **kwargs):
        calls.append((args, kwargs)); original(*args, **kwargs)
        raise ValueError('SYNTHETIC_LOST_ACK_AFTER_ORIGINAL_COMMIT')
    monkeypatch.setattr(e.production, lost_at, lost)
    assert dispatch(e, row).status_code == 422
    current = read(e)
    assert current['status'] == 'UNKNOWN' and current['items'][0]['attempts'] == 1
    assert freeze(e)['id'] == row['id']
    assert current['items'][0]['configuration_summary']['command']['request_id'] == e.item['studio_image']['request_id']
    for suffix in ['/dispatch-next', '/retry-failed']:
        assert post(e, '/' + row['id'] + suffix, version(current)).status_code == 422
    response = post(e, '/' + row['id'] + '/reconcile', version(current))
    if lost_at == 'execute':
        recovered = checked(response)
        assert recovered['status'] == 'COMPLETED' and recovered['items'][0]['image_result']['status'] == 'AWAITING_REVIEW'
    else:
        assert response.status_code == 422
    assert len(calls) == 1


def test_concurrent_repeated_preflight_keeps_one_original_batch_and_key(images):
    from concurrent.futures import ThreadPoolExecutor
    e = images
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: freeze(e), range(2)))
    assert rows[0]['id'] == rows[1]['id'] and rows[0]['version'] == rows[1]['version']
    changed = deepcopy(e.item); changed['studio_image']['license_note'] = 'different binding, same request key'
    assert post(e, '/preflight', {'items': [changed]}).status_code == 422
    stored = e.batches.list(e.nid, e.scope, e.batches.BATCHES)
    assert len(stored) == 1 and stored[0]['items'][0]['attempts'] == 0


def test_old_nonimage_frozen_dto_has_no_added_fields(images):
    e = images
    row = freeze(e, [{'kind': 'PROOF', 'chapter_ids': [e.chapter['id']]}])
    original = e.batches.get(e.nid, e.scope, e.batches.BATCHES, row['id'])
    assert 'studio_image' not in original['input']['items'][0]
    assert 'studio_image' not in original['snapshot']['steps'][0]['input']


@pytest.mark.parametrize('change', ['job', 'output_digest', 'batch_version'])
def test_per_item_review_refuses_wrong_original_job_output_or_batch_cas(images, change):
    e = images
    row = checked(dispatch(e, confirm(e, freeze(e))))
    body = review_body(row)
    if change == 'job': body['job_id'] = 'another-job'
    elif change == 'output_digest': body['reviewed_output_digest'] = 'f' * 64
    else: body['expected_version'] -= 1
    assert post(e, '/' + row['id'] + '/approve-image', body).status_code in {409, 422}
    job = row['items'][0]['image_result']
    assert e.client.get(e.studio_base + '/assets/' + job['output_candidate']['id'], headers=e.headers).status_code == 404


def test_unreadable_original_job_never_returns_cached_private_candidate(images, monkeypatch):
    e = images
    row = checked(dispatch(e, confirm(e, freeze(e))))
    original = e.production.get
    def denied(*args, **kwargs):
        if args[4] == row['items'][0]['image_job_id']: raise FileNotFoundError('synthetic revoked receipt')
        return original(*args, **kwargs)
    monkeypatch.setattr(e.production, 'get', denied)
    current = read(e)
    assert 'image_result' not in current['items'][0]


def test_neutral_studio_cutout_batch_requires_no_novel_chapters(images):
    e = images
    e.chapters.delete(e.chapter['id'])
    assert e.chapters.list(e.nid) == []
    row = freeze(e)
    assert row['items'][0]['chapter_ids'] == []
    done = checked(dispatch(e, confirm(e, row)))
    assert done['items'][0]['image_result']['status'] == 'AWAITING_REVIEW'
    assert e.chapters.list(e.nid) == []
