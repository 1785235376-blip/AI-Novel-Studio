"""Exact CPU pixels and original File Image Job -> private candidate -> review."""
from copy import deepcopy
import hashlib
import io
import json
import base64
import os
from pathlib import Path

from PIL import Image
import pytest

from app.services import studio_image_composite as composite
from app.services.studio_image_cutout import _rgba_png
from app.services.studio_image_execution import _context, _advance
from app.creative.production_execution_models import MediaCommand
from test_v2_cpu_cutout_api import cpu_client, mask_client, client, checked, mounted, prefix, queue, run, action
from test_v2_manual_mask_api import post
from test_v2_cpu_cutout_owner import snapshot


def png(pixel, width=64):
    return _rgba_png((b'\0' + bytes(pixel) * width) * 64, width, 64, lambda: None)


def settings(values, opacity=(255, 255), visible=(True, True)):
    return [{'source': {'id': 'layer-' + str(i), 'kind': 'ASSET', 'asset_kind': 'image', 'version': 1,
        'digest': hashlib.sha256(data).hexdigest()}, 'visible': visible[i], 'opacity': opacity[i]} for i, data in enumerate(values)]


@pytest.mark.parametrize('bottom,top,opacity,visible,expected', [
    ((255, 0, 0, 255), (0, 0, 255, 128), (255, 255), (True, True), (127, 0, 128, 255)),
    ((255, 0, 0, 128), (0, 0, 255, 128), (255, 255), (True, True), (85, 0, 170, 192)),
    ((255, 0, 0, 255), (0, 0, 255, 255), (255, 128), (True, True), (127, 0, 128, 255)),
    ((7, 8, 9, 200), (1, 2, 3, 255), (255, 255), (True, False), (7, 8, 9, 200)),
    ((8, 9, 10, 0), (90, 80, 70, 0), (255, 255), (True, True), (0, 0, 0, 0)),
    ((80, 90, 100, 1), (1, 2, 3, 0), (1, 255), (True, True), (0, 0, 0, 0)),
])
def test_cpu_source_over_golden_pixels(bottom, top, opacity, visible, expected):
    values = [png(bottom), png(top)]
    data, proof = composite.render(values, settings(values, opacity, visible))
    with Image.open(io.BytesIO(data)) as decoded:
        assert decoded.format == 'PNG' and decoded.mode == 'RGBA' and decoded.size == (64, 64)
        raw = decoded.tobytes(); assert raw == bytes(expected) * 4096
    assert proof['rgba_sha256'] == hashlib.sha256(raw).hexdigest()
    assert proof['output_sha256'] == hashlib.sha256(data).hexdigest()


def test_cpu_limits_strict_chunks_order_and_cooperative_abort():
    values = [png((255, 0, 0, 255)), png((0, 0, 255, 255))]
    forward, _ = composite.render(values, settings(values))
    reverse, _ = composite.render(values[::-1], settings(values[::-1]))
    assert forward != reverse
    with pytest.raises(ValueError, match='DIMENSIONS_MISMATCH'):
        composite.render([values[0], png((0, 0, 0, 255), 128)], settings([values[0], png((0, 0, 0, 255), 128)]))
    with pytest.raises(ValueError): composite.validate_inputs([values[0][:-1], values[1]])
    with pytest.raises(ValueError, match='SOURCE_LIMIT'):
        composite.validate_inputs([b'x' * (8 * 1024 * 1024 + 1), values[1]])
    class Cancelled(Exception): pass
    calls = 0
    def checkpoint():
        nonlocal calls
        calls += 1
        if calls == 20: raise Cancelled('cancelled')
    with pytest.raises(Cancelled): composite.render(values, settings(values), checkpoint)


@pytest.fixture
def composite_client(cpu_client):
    e = cpu_client
    e.command.update(operation_id=composite.OPERATION, image_layers=[
        {'source': snapshot(e.source), 'visible': True, 'opacity': 255},
        {'source': snapshot(e.mask), 'visible': True, 'opacity': 128}])
    return e


def test_file_recipe_reopen_private_candidate_exact_review_and_asset(composite_client):
    e = composite_client
    preview, queued = queue(e)
    assert preview['provider'] is None and preview['execution_recipe'] == composite.recipe(e.command['image_layers'])
    assert queue(e)[1] == queued
    # Read the original persisted queue, not a substituted in-memory store.
    stored = next(job for path in e.root.glob('image-jobs/actors/*/image-jobs/*.json')
        for job in json.loads(path.read_text(encoding='utf-8')) if job['id'] == queued['id'])
    assert stored['context']['execution_recipe'] == preview['execution_recipe']
    assert stored['body']['image_layers'] == e.command['image_layers']
    executed = checked(run(e, queued)); assert executed['status'] == 'AWAITING_REVIEW', executed
    candidate = executed['output_candidate']
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers).status_code == 404
    response = e.client.get(e.base + '/jobs/image/' + executed['id'] + '/candidate', headers=e.headers)
    assert response.status_code == 200 and response.headers['content-type'].startswith('image/png')
    sources = [e.client.get(e.studio_base + '/assets/' + s['id'] + '/download', headers=e.headers).content for s in e.command['source_snapshots']]
    expected, proof = composite.render(sources, e.command['image_layers'])
    assert response.content == expected and executed['processing_proof'] == proof
    assert e.client.post(e.base + '/jobs/image/' + executed['id'] + '/review', headers=e.headers,
        json={**action(executed), 'reviewed_output_digest': '0' * 64}).status_code == 422
    approved = checked(e.client.post(e.base + '/jobs/image/' + executed['id'] + '/review', headers=e.headers,
        json={**action(executed), 'reviewed_output_digest': candidate['digest']}))
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    saved = checked(e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers))
    assert saved['media_type'] == 'image/png' and saved['provenance']['origin'] == 'DERIVED_PROCESSING'
    assert saved['provider_id'] is None and saved['model_id'] is None
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'] + '/download', headers=e.headers).content == expected
    if os.environ.get('STUDIO_CAPTURE_IMAGE_COMPOSITE') and e.prefix == '/api':
        public_sources = [checked(e.client.get(e.studio_base + '/assets/' + item['id'], headers=e.headers)) for item in e.command['source_snapshots']]
        capture = {'command': e.command, 'preview': preview, 'queued': queued, 'executed': executed, 'approved': approved,
            'assets': public_sources, 'saved': saved, 'source_base64': [base64.b64encode(value).decode() for value in sources],
            'output_base64': base64.b64encode(expected).decode(), 'backend': 'real File / native CPU pixels / original Image Job Review Asset'}
        target = Path(os.environ['STUDIO_CAPTURE_IMAGE_COMPOSITE']); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(capture, ensure_ascii=False, indent=2), encoding='utf-8')


def test_strict_route_and_original_recipe_source_binding(composite_client):
    e = composite_client
    for change in ({'image_layers': None}, {'parameters': {'blend_mode': 'screen'}}, {'provider_id': 'any'},
                   {'execution_recipe': {}}, {'image_layers': e.command['image_layers'] * 2}):
        assert e.client.post(e.base + '/preview', headers=e.headers, json={**e.command, **change}).status_code == 422
    changed = deepcopy(e.command); changed['image_layers'][0]['opacity'] = True
    assert e.client.post(e.base + '/preview', headers=e.headers, json=changed).status_code == 422
    _, queued = queue(e)
    stored = next(job for path in e.root.glob('image-jobs/actors/*/image-jobs/*.json')
        for job in json.loads(path.read_text(encoding='utf-8')) if job['id'] == queued['id'])
    for key in ('command', 'execution_recipe'):
        context = deepcopy(stored['context']); context.pop(key)
        with pytest.raises(ValueError): _context(context, stored['body'], stored['owner_actor_id'])
    context = deepcopy(stored['context']); context['execution_recipe']['layers'][0]['opacity'] = 0
    with pytest.raises(ValueError): _context(context, stored['body'], stored['owner_actor_id'])


def test_cancel_and_unknown_original_job_cannot_execute_or_replay(composite_client, monkeypatch):
    e = composite_client
    _, queued = queue(e)
    cancelled = checked(e.client.post(e.base + '/jobs/image/' + queued['id'] + '/cancel', headers=e.headers, json=action(queued)))
    assert cancelled['status'] == 'CANCELLED'
    assert run(e, cancelled).status_code == 422
    e.command['request_id'] += '-unknown'
    _, queued = queue(e)
    persisted = next(job for path in e.root.glob('image-jobs/actors/*/image-jobs/*.json')
        for job in json.loads(path.read_text(encoding='utf-8')) if job['id'] == queued['id'])
    owner = e.production._image(persisted['owner_actor_id'])
    def interrupt(rows):
        row = next(row for row in rows if row['id'] == queued['id'])
        return _advance(row, status='RUNNING', execution_token='lost-response')
    owner._mutate(e.nid, e.scope.get('branch_id'), interrupt)
    unknown = checked(e.client.get(e.base + '/jobs/image/' + queued['id'], headers=e.headers))
    monkeypatch.setattr(composite, 'render', lambda *a, **k: pytest.fail('UNKNOWN replayed'))
    unknown = checked(run(e, unknown)); assert unknown['status'] == 'UNKNOWN'
    assert run(e, unknown).status_code == 422
    assert queue(e)[1]['id'] == unknown['id']


def test_hidden_layer_pin_and_permission_revoked_before_publication(composite_client, monkeypatch):
    e = composite_client
    bad = deepcopy(e.command)
    bad['image_layers'][1]['visible'] = False
    bad['image_layers'][1]['source']['version'] += 1
    bad['source_snapshots'][1]['version'] += 1
    assert e.client.post(e.base + '/preview', headers=e.headers, json=bad).status_code == 409
    _, queued = queue(e)
    original = composite.render
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.host)
        return result
    monkeypatch.setattr(composite, 'render', revoke)
    assert run(e, queued).status_code == 401
    stored = next(job for path in e.root.glob('image-jobs/actors/*/image-jobs/*.json')
        for job in json.loads(path.read_text(encoding='utf-8')) if job['id'] == queued['id'])
    assert not stored.get('output_asset_id') and not stored.get('publication_ready')


def test_running_original_job_cancel_stops_cpu_publication(composite_client, monkeypatch):
    e = composite_client
    _, queued = queue(e)
    stored = next(job for path in e.root.glob('image-jobs/actors/*/image-jobs/*.json')
        for job in json.loads(path.read_text(encoding='utf-8')) if job['id'] == queued['id'])
    actor, branch = stored['owner_actor_id'], e.scope.get('branch_id')
    owner = e.production._image(actor)
    original, calls = composite.render, 0
    def cancelling(values, settings, checkpoint):
        def check():
            nonlocal calls
            calls += 1
            if calls == 20:
                running = owner.get_studio(e.nid, branch, actor, queued['id'], lambda: None)
                assert running['status'] == 'RUNNING'
                owner.cancel_studio(e.nid, branch, actor, queued['id'],
                    **action(running), guard=lambda: None)
            checkpoint()
        return original(values, settings, check)
    monkeypatch.setattr(composite, 'render', cancelling)
    cancelled = checked(run(e, queued))
    assert cancelled['status'] == 'CANCELLED'
    assert cancelled['cancellation_mode'] == 'COOPERATIVE_LOCAL_CANCEL'
    assert not cancelled.get('output_candidate') and not cancelled.get('processing_proof')
    assert run(e, cancelled).status_code == 422
