"""Cloud integration regressions with real File owners and synthetic Host."""
from copy import deepcopy
import base64

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_manual_mask_api import mask_client
from test_v2_cpu_cutout_api import cpu_client
from test_u16_studio_image_batch_api import images, freeze, confirm, dispatch, read, post, version


def two_items(e):
    mask_body = deepcopy(e.body)
    mask_body['idempotency_key'] = 'cloud-second-mask'
    mask_body['bitplane_base64'] = base64.b64encode(bytes(
        value ^ 255 for value in base64.b64decode(mask_body['bitplane_base64']))).decode()
    mask = checked(e.client.post(e.path, headers=e.headers, json=mask_body), 201)['asset']
    second = deepcopy(e.item)
    second['studio_image']['request_id'] = 'cloud-second-item'
    second['studio_image']['mask'] = {'id': mask['id'], 'version': mask['version'],
        'digest': mask['sha256'], 'kind': 'ASSET', 'asset_kind': 'image'}
    return [e.item, second]


def test_bound_pixel_checks_keep_scope_before_asset_lock(images, monkeypatch):
    """Detect the ABBA acquisition deterministically, without hanging threads."""
    e = images
    row = confirm(e, freeze(e))
    original = e.store.read
    guarded_reads = []
    import app.services.studio_image_cutout as pixels
    render = pixels.render_cutout

    def unleased_render(*args, **kwargs):
        assert e.store.key(e.nid, e.scope) not in getattr(e.store._local, 'active', {})
        return render(*args, **kwargs)

    def ordered(nid, scope):
        if getattr(e.assets._scope, 'binding', None) is not None:
            key = e.store.key(nid, scope)
            assert key in getattr(e.store._local, 'active', {}), (
                'scope read under asset/project locks without prior scope lease')
            guarded_reads.append(key)
        return original(nid, scope)

    monkeypatch.setattr(e.store, 'read', ordered)
    monkeypatch.setattr(pixels, 'render_cutout', unleased_render)
    done = checked(dispatch(e, row))
    assert done['status'] == 'COMPLETED'
    assert guarded_reads


def test_bound_recovery_list_filters_unrelated_original_jobs(images):
    e = images
    command = deepcopy(e.command)
    command['request_id'] = 'cloud-unrelated-standalone'
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=command))
    unrelated = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': command, 'reviewed_preview_digest': preview['preview_digest']}), 201)
    done = checked(dispatch(e, confirm(e, freeze(e))))
    raw = e.batches.get(e.nid, e.scope, e.batches.BATCHES, done['id'])
    binding = e.batches.studio_image.binding(raw, 0, e.production.store.key(e.nid, e.scope))
    jobs = e.production.list(e.nid, e.scope, raw['created_by'], lambda: None,
        batch_binding=binding)['items']
    assert [job['id'] for job in jobs] == [done['items'][0]['image_job_id']]
    assert unrelated['id'] not in [job['id'] for job in jobs]


@pytest.mark.parametrize('state,deny_all', [('COMPLETED', True), ('COMPLETED', False), ('CANCELLED', True)])
def test_every_private_image_result_is_revalidated_or_removed(images, monkeypatch, state, deny_all):
    e = images
    selected = two_items(e)
    if state == 'CANCELLED':
        selected.append({'kind': 'PROOF', 'chapter_ids': [e.chapter['id']]})
    first = checked(dispatch(e, confirm(e, freeze(e, selected))))
    done = checked(dispatch(e, first))
    if state == 'CANCELLED':
        done = checked(post(e, '/' + done['id'] + '/stop', version(done)))
    job_ids = {item['image_job_id'] for item in done['items'] if item.get('image_job_id')}
    original = e.production.get
    seen = set()
    denied = job_ids if deny_all else {done['items'][0]['image_job_id']}

    def unavailable(*args, **kwargs):
        if args[4] in job_ids:
            seen.add(args[4])
        if args[4] in denied:
            raise FileNotFoundError('synthetic original jobs withdrawn')
        return original(*args, **kwargs)

    monkeypatch.setattr(e.production, 'get', unavailable)
    current = read(e)
    assert current['status'] == state
    if state == 'COMPLETED':
        assert seen == job_ids
    assert 'image_result' not in current['items'][0]
    if deny_all:
        assert all('image_result' not in item for item in current['items'])
    else:
        assert current['items'][1]['image_result']['id'] == done['items'][1]['image_job_id']


def test_lost_create_ack_finds_original_key_beside_unrelated_job_without_resend(images, monkeypatch):
    e = images
    command = deepcopy(e.command)
    command['request_id'] = 'cloud-unrelated-before-lost-ack'
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=command))
    checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': command, 'reviewed_preview_digest': preview['preview_digest']}), 201)
    row = confirm(e, freeze(e))
    create, jobs = e.production.create, []

    def lost(*args, **kwargs):
        jobs.append(create(*args, **kwargs))
        raise ValueError('SYNTHETIC_LOST_ACK_AFTER_ORIGINAL_CREATE')

    monkeypatch.setattr(e.production, 'create', lost)
    assert dispatch(e, row).status_code == 422
    unknown = read(e)
    assert unknown['status'] == 'UNKNOWN'
    assert not unknown['items'][0].get('image_job_id')
    query, recovered = e.batches.studio_image.job, []

    def observe(*args, **kwargs):
        job = query(*args, **kwargs)
        recovered.append(job)
        return job

    monkeypatch.setattr(e.batches.studio_image, 'job', observe)
    # A QUEUED receipt is observable but does not authorize dispatch or replay.
    assert post(e, '/' + row['id'] + '/reconcile', version(unknown)).status_code == 422
    assert len(jobs) == 1
    assert [job['id'] for job in recovered] == [jobs[0]['id']]
    assert recovered[0]['status'] == 'QUEUED'
    assert dispatch(e, read(e)).status_code == 422
