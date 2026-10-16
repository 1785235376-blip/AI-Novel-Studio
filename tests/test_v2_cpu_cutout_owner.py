"""Standalone CPU cutout through original File and actual PostgreSQL owners."""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest

from app.creative.production_execution import ProductionExecutionService
from app.creative.production_execution_models import MediaCommand, MediaCreate, MediaJobAction, MediaReview
from app.services.image_job_service import ImageJobService
from test_v2_independent_workspace import rig, reopened
from test_v2_manual_mask_owner import mask, save


class NoControl:
    def __getattr__(self, name):
        raise AssertionError('cutout attempted external control: ' + name)


def snapshot(row):
    return {'kind': 'ASSET', 'asset_kind': 'image', 'id': row['id'], 'version': row['version'], 'digest': row['sha256']}


def production(e, workspace=None):
    return ProductionExecutionService(workspace or e.service, ImageJobService(e.root), NoControl(),
        NoControl(), {}, {}, NoControl(), NoControl(), NoControl())


@pytest.fixture
def cutout(mask, monkeypatch):
    e = mask
    e.service.activate(e.nid, e.scope, e.actor)
    e.mask = save(e)['asset']; e.production = production(e)
    e.command = {'operation_id': 'm5.image.cutout', 'request_id': 'cutout-one', 'provider_id': None,
        'model_id': None, 'prompt': '', 'parameters': {}, 'allow_cloud': False,
        'source_snapshots': [snapshot(e.source), snapshot(e.mask)], 'license_note': 'Synthetic owned pixels'}
    def denied(*a, **k): raise AssertionError('CPU cutout must not launch processes or inspect generic media')
    import app.creative.production_execution as module
    import app.services.studio_image_execution as image_owner
    import subprocess
    monkeypatch.setattr(module, 'inspect_image', denied)
    monkeypatch.setattr(image_owner, 'inspect_image', denied)
    monkeypatch.setattr(subprocess, 'run', denied)
    monkeypatch.setattr(subprocess, 'Popen', denied)
    return e


def preview(e, command=None, guard=lambda: None):
    return e.production.preview(e.nid, e.scope, e.actor, command or e.command, guard)[0]


def queue(e, command=None, guard=lambda: None):
    body = command or e.command; captured = preview(e, body, guard)
    return e.production.create(e.nid, e.scope, e.actor, {'command': body, 'reviewed_preview_digest': captured['preview_digest']}, guard)


def action(row, review=False):
    values = {'expected_version': row['version'], 'expected_request_digest': row['request_digest']}
    if review: return MediaReview(**values, reviewed_output_digest=row['output_candidate']['digest'])
    return MediaJobAction(**values)


def get(e, row): return e.production.get(e.nid, e.scope, e.actor, 'image', row['id'], lambda: None)


def run(e, row, guard=lambda: None):
    return e.production.execute(e.nid, e.scope, e.actor, 'image', row['id'], action(row), guard)


def cancel(e, row):
    return e.production.cancel(e.nid, e.scope, e.actor, 'image', row['id'], action(row), lambda: None)


def review(e, row, guard=lambda: None):
    return e.production.review(e.nid, e.scope, e.actor, 'image', row['id'], action(row, True), guard)


def reconcile(e, row):
    return e.production.reconcile(e.nid, e.scope, e.actor, 'image', row['id'], action(row), lambda: None)


def revise(e, row):
    with e.service._asset_scope(e.nid, e.scope):
        return e.assets.update_metadata(row['id'], {'scene_id': 'new-revision'}, expected_version=row['version'])


def test_source_pair_preview_private_result_explicit_review_and_reopen(cutout):
    e = cutout; p = preview(e)
    assert p['provider'] is None and p['execution_recipe']['adapter'] == 'LOCAL_CPU_MASK'
    assert p['execution_recipe']['parameters'] == {} and not p['automatic_dispatch']
    queued = queue(e); assert queue(e) == queued
    assert queued['processing_proof'] is None and queued['status'] == 'QUEUED'
    candidate = run(e, queued)
    assert candidate['status'] == 'AWAITING_REVIEW' and candidate['attempt'] == 1
    assert candidate['provider'] is None and not candidate['remote_compute_may_continue']
    proof = candidate['processing_proof']; asset = candidate['output_candidate']
    assert proof['source_sha256'] == e.source['sha256'] and proof['mask_sha256'] == e.mask['sha256']
    assert proof['output_sha256'] == asset['digest'] and proof['keep_pixels'] == 512
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, asset['id'])
    meta, data = e.production.candidate(e.nid, e.scope, e.actor, 'image', candidate['id'], lambda: None)
    from app.services.studio_image_cutout import render_cutout
    with e.service._asset_scope(e.nid, e.scope):
        expected, _ = render_cutout(e.assets.content(e.source['id']), e.assets.content(e.mask['id']))
    assert data == expected and meta['sha256'] == proof['output_sha256']
    approved = review(e, candidate)
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    projected = e.service.asset(e.nid, e.scope, asset['id'])
    assert projected['provenance']['origin'] == 'DERIVED_PROCESSING'
    assert {p['id'] for p in projected['provenance']['parents']} == {e.source['id'], e.mask['id']}
    e.production = production(e, reopened(e)); assert get(e, queued) == approved
    assert review(e, candidate) == approved


@pytest.mark.parametrize('change', ['provider', 'model', 'prompt', 'parameters', 'cloud', 'missing', 'duplicate', 'document', 'swapped'])
def test_closed_command_and_pair_cannot_be_widened(cutout, change):
    e = cutout; value = deepcopy(e.command)
    if change == 'provider': value['provider_id'] = 'invented'
    elif change == 'model': value['model_id'] = 'invented'
    elif change == 'prompt': value['prompt'] = 'remove background'
    elif change == 'parameters': value['parameters'] = {'width': 64, 'height': 64}
    elif change == 'cloud': value['allow_cloud'] = True
    elif change == 'missing': value['source_snapshots'].pop()
    elif change == 'duplicate': value['source_snapshots'][1] = value['source_snapshots'][0]
    elif change == 'document': value['source_snapshots'][1] = {'kind': 'CREATIVE_DOCUMENT', 'id': 'text', 'version': 1, 'digest': 'a' * 64}
    else: value['source_snapshots'].reverse()
    with pytest.raises(ValueError): preview(e, value)
    assert not list(e.root.rglob('image-jobs/*.json'))


def test_current_mask_annotation_version_and_different_author_are_allowed(cutout):
    e = cutout
    e.mask = e.service.annotate(e.nid, e.scope, e.actor, e.mask['id'], {'expected_version': 1,
        'origin': 'MANUAL_EDIT', 'parent_asset_ids': [e.source['id']], 'license': {'label': 'Synthetic'}})
    e.command['source_snapshots'][1] = snapshot(e.mask)
    e.actor = 'another-current-author'
    assert run(e, queue(e))['status'] == 'AWAITING_REVIEW'


@pytest.mark.parametrize('source_index', [0, 1])
@pytest.mark.parametrize('stage', ['queue', 'execute', 'review', 'recovery'])
def test_source_or_mask_revision_never_refreshes_implicitly(cutout, monkeypatch, source_index, stage):
    e = cutout; original = None
    if stage == 'queue': captured = preview(e)
    else: row = queue(e)
    if stage == 'recovery':
        original = e.assets.create
        def lost(*a, **k): original(*a, **k); raise OSError('lost private publication response')
        monkeypatch.setattr(e.assets, 'create', lost)
    if stage in {'review', 'recovery'}: row = run(e, row)
    if stage == 'recovery':
        assert row['status'] == 'UNKNOWN'; monkeypatch.setattr(e.assets, 'create', original)
    revise(e, e.source if source_index == 0 else e.mask)
    if stage == 'recovery': assert reconcile(e, row)['status'] == 'UNKNOWN'
    else:
        with pytest.raises(ValueError):
            if stage == 'queue': e.production.create(e.nid, e.scope, e.actor, {'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}, lambda: None)
            elif stage == 'execute': run(e, row)
            else: review(e, row)
    assert all(r['id'] in {e.source['id'], e.mask['id']} for r in e.service.list_assets(e.nid, e.scope)['items'])


def test_forged_png_mask_has_no_original_authored_marker(cutout):
    e = cutout
    with e.service._asset_scope(e.nid, e.scope):
        data = e.assets.content(e.mask['id'])
        uploaded = e.assets.create(e.nid, 'lookalike.png', base64.b64encode(data).decode(), 'image/png', 'image', 'fake', required_features=('narrative_production_v2',))
    e.command['source_snapshots'][1] = snapshot(uploaded)
    with pytest.raises(ValueError, match='IMAGE_MASK_ORIGIN_INVALID'): preview(e)


def test_private_candidate_cannot_be_reused_as_source(cutout):
    e = cutout; candidate = run(e, queue(e))['output_candidate']
    e.command['source_snapshots'][0] = {'kind': 'ASSET', 'asset_kind': 'image', **{k: candidate[k] for k in ('id', 'version', 'digest')}}
    with pytest.raises((ValueError, FileNotFoundError)): preview(e)


@pytest.mark.parametrize('moment', ['before', 'during', 'after_publication'])
def test_cancel_is_terminal_and_never_promotes(cutout, monkeypatch, moment):
    e = cutout; row = queue(e)
    if moment == 'before':
        cancelled = cancel(e, row)
        with pytest.raises(ValueError): run(e, cancelled)
    elif moment == 'during':
        import app.services.studio_image_cutout as pixels
        original = pixels.render_cutout
        def stopped(*a, **k):
            cancel(e, get(e, row))
            return original(*a, **k)
        monkeypatch.setattr(pixels, 'render_cutout', stopped)
        cancelled = run(e, row)
    else:
        original = e.assets.create
        def stopped(*a, **k):
            result = original(*a, **k)
            if k.get('_initial_studio_result'): cancel(e, get(e, row))
            return result
        monkeypatch.setattr(e.assets, 'create', stopped)
        cancelled = run(e, row)
        assert cancelled['output_candidate'] is not None
        assert e.production.candidate(e.nid, e.scope, e.actor, 'image', row['id'], lambda: None)[1]
    assert cancelled['status'] == 'CANCELLED'
    assert cancelled['cancellation_mode'] == 'COOPERATIVE_LOCAL_CANCEL'
    assert not cancelled['remote_compute_may_continue']
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2
    with pytest.raises(ValueError): reconcile(e, cancelled)
    if cancelled['output_candidate']:
        with pytest.raises(ValueError): review(e, cancelled)


def test_same_page_cancel_does_not_wait_for_execution_lease(cutout, monkeypatch):
    e = cutout; row = queue(e); entered, released = Event(), Event()
    import app.services.studio_image_cutout as pixels
    original = pixels.render_cutout
    def paused(*a, **k):
        entered.set(); assert released.wait(10)
        return original(*a, **k)
    monkeypatch.setattr(pixels, 'render_cutout', paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = pool.submit(run, e, row)
        assert entered.wait(10)
        running = get(e, row); assert running['status'] == 'RUNNING'
        try: assert cancel(e, running)['status'] == 'CANCELLED'
        finally: released.set()
        assert result.result(10)['status'] == 'CANCELLED'


def test_lost_publication_recovers_exact_private_candidate_without_render(cutout, monkeypatch):
    e = cutout; row = queue(e); original = e.assets.create
    def lost(*a, **k): original(*a, **k); raise OSError('synthetic lost response')
    monkeypatch.setattr(e.assets, 'create', lost)
    interrupted = run(e, row); assert interrupted['status'] == 'UNKNOWN' and interrupted['processing_proof']
    monkeypatch.setattr(e.assets, 'create', original)
    import app.services.studio_image_cutout as pixels
    monkeypatch.setattr(pixels, 'render_cutout', lambda *a, **k: pytest.fail('recovery regenerated'))
    recovered = reconcile(e, interrupted)
    assert recovered['status'] == 'AWAITING_REVIEW' and recovered['attempt'] == 1
    assert recovered['processing_proof'] == interrupted['processing_proof']
    assert review(e, recovered)['status'] == 'APPROVED'


@pytest.mark.parametrize('change', ['guard', 'flag', 'source', 'mask'])
def test_renderer_boundary_change_cannot_publish(cutout, monkeypatch, change):
    e = cutout; row = queue(e); revoked = False
    def guard():
        if revoked: raise ValueError('authority revoked')
    import app.services.studio_image_cutout as pixels
    original = pixels.render_cutout
    def changed(*a, **k):
        nonlocal revoked
        result = original(*a, **k)
        if change == 'guard': revoked = True
        elif change == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
        else: revise(e, e.source if change == 'source' else e.mask)
        return result
    monkeypatch.setattr(pixels, 'render_cutout', changed)
    if change in {'guard', 'flag'}:
        with pytest.raises(Exception): run(e, row, guard)
    else: assert run(e, row)['status'] == 'FAILED'
    assert len(list(e.assets.root.glob('*.bin'))) == 2


def test_graph_union_and_advisory_descriptor_stay_standalone(cutout):
    from app.creative.graph_models import MediaNodeParameters
    from app.creative.production_contracts import production_catalog
    with pytest.raises(ValueError): MediaNodeParameters(operation_id='m5.image.cutout')
    descriptor = next(row for row in production_catalog(cutout.nid, cutout.scope).operations if row.id == 'm5.image.cutout')
    assert all(not row.id.startswith('graph_') for row in descriptor.actions)
    assert descriptor.owner.class_name == 'ProductionExecutionService'


@pytest.mark.parametrize('change', ['source', 'mask', 'lineage', 'incarnation'])
def test_queue_rechecks_inputs_in_original_atomic_write_phase(cutout, monkeypatch, change):
    e = cutout; captured = preview(e); original = ImageJobService.create_studio
    def changed(owner, *a, **k):
        if change in {'source', 'mask'}: revise(e, e.source if change == 'source' else e.mask)
        elif change == 'lineage': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
        else: monkeypatch.setattr(e.production.store, 'incarnation', lambda nid: 'file:11111111-1111-4111-8111-111111111111')
        return original(owner, *a, **k)
    monkeypatch.setattr(ImageJobService, 'create_studio', changed)
    with pytest.raises(Exception):
        e.production.create(e.nid, e.scope, e.actor, {'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}, lambda: None)
    assert not list(e.root.rglob('image-jobs/*.json'))


def test_queue_rechecks_authority_after_original_queue_load(cutout, monkeypatch):
    e = cutout; revoked = False; original = ImageJobService._load
    def loaded(owner, *a, **k):
        nonlocal revoked
        result = original(owner, *a, **k); revoked = True
        return result
    def guard():
        if revoked: raise ValueError('authority revoked during queue read')
    monkeypatch.setattr(ImageJobService, '_load', loaded)
    with pytest.raises(ValueError, match='authority revoked'): queue(e, guard=guard)
    assert not list(e.root.rglob('image-jobs/*.json'))


def test_preview_tail_rechecks_mask_feature(cutout, monkeypatch):
    e = cutout; original = e.production._recipe
    def recipe(*a, **k):
        result = original(*a, **k)
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
        return result
    monkeypatch.setattr(e.production, '_recipe', recipe)
    with pytest.raises(Exception): preview(e)


def test_cancelled_lost_publication_recovers_inspection_only(cutout, monkeypatch):
    e = cutout; row = queue(e); original = e.assets._write_meta
    def lost(meta):
        original(meta)
        if meta.get('_studio_result_origin'):
            cancel(e, get(e, row)); raise OSError('committed cancelled candidate lost response')
    monkeypatch.setattr(e.assets, '_write_meta', lost)
    cancelled = run(e, row)
    assert cancelled['status'] == 'CANCELLED' and cancelled['output_candidate'] is None
    assert cancelled['processing_proof'] is not None
    monkeypatch.setattr(e.assets, '_write_meta', original)
    recovered = reconcile(e, cancelled)
    assert recovered['status'] == 'CANCELLED' and recovered['output_candidate'] is not None
    assert not recovered['remote_compute_may_continue']
    assert e.production.candidate(e.nid, e.scope, e.actor, 'image', row['id'], lambda: None)[1]
    with pytest.raises(ValueError): review(e, recovered)
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2


@pytest.mark.parametrize('field', ['keep_pixels', 'width', 'output_bytes'])
def test_recovery_rejects_corrupt_pixel_proof(cutout, monkeypatch, field):
    e = cutout; row = queue(e); original = e.assets.create
    def lost(*a, **k): original(*a, **k); raise OSError('lost private response')
    monkeypatch.setattr(e.assets, 'create', lost)
    interrupted = run(e, row); monkeypatch.setattr(e.assets, 'create', original)
    owner = e.production._image(e.actor)
    def damage(rows):
        raw = owner._find(rows, row['id']); proof = raw['processing_proof']
        if field == 'keep_pixels': proof['keep_pixels'] += 1; proof['remove_pixels'] -= 1
        elif field == 'width': proof['width'] = 128; proof['height'] = 32
        else: proof['output_bytes'] += 1; raw['publication_ready']['output_bytes'] += 1
        return raw
    owner._mutate(e.nid, e.scope.get('branch_id'), damage)
    if field == 'keep_pixels': assert reconcile(e, interrupted)['status'] == 'UNKNOWN'
    else:
        with pytest.raises(ValueError): reconcile(e, interrupted)
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2


def test_lost_review_completion_retries_original_promotion_without_reexecution(cutout, monkeypatch):
    e = cutout; row = run(e, queue(e)); original = e.assets.promote_owned
    def lost(*a, **k): original(*a, **k); raise OSError('lost committed approval response')
    monkeypatch.setattr(e.assets, 'promote_owned', lost)
    with pytest.raises(OSError): review(e, row)
    reviewing = get(e, row); assert reviewing['status'] == 'REVIEWING'
    monkeypatch.setattr(e.assets, 'promote_owned', original)
    # Recovery never guesses that an already-promoted asset is private again.
    assert reconcile(e, reviewing)['status'] == 'REVIEWING'
    approved = review(e, reviewing)
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2


def test_review_late_lineage_revocation_does_not_promote(cutout, monkeypatch):
    e = cutout; row = run(e, queue(e)); original = e.assets.promote_owned
    def changed(*a, **k):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
        return original(*a, **k)
    monkeypatch.setattr(e.assets, 'promote_owned', changed)
    with pytest.raises(Exception): review(e, row)
    with e.service._asset_scope(e.nid, e.scope):
        meta = e.assets.get(row['output_candidate']['id'], actor_id=e.actor)
    assert meta['_owner_actor_id'] == e.actor and meta['version'] == 1


def test_network_and_generic_image_controls_are_unavailable_for_cpu_flow(cutout, monkeypatch):
    import httpx
    import socket
    import urllib.request
    import app.services.studio_image_execution as owner
    def denied(*a, **k): raise AssertionError('unexpected CPU external I/O')
    monkeypatch.setattr(httpx.Client, 'request', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(urllib.request, 'urlopen', denied)
    monkeypatch.setattr(owner, 'fetch_media_bytes', denied)
    e = cutout
    assert review(e, run(e, queue(e)))['status'] == 'APPROVED'


def test_concurrent_original_queue_and_execute_have_one_exact_candidate(cutout):
    e = cutout
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: queue(e), range(2)))
    assert rows[0] == rows[1]
    def execute_once(_):
        try: return run(e, rows[0])
        except ValueError: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(execute_once, range(2)))
    completed = [row for row in outcomes if row is not None]
    assert len(completed) == 1 and completed[0]['status'] == 'AWAITING_REVIEW'
    assert len(list(e.assets.root.glob('*.bin'))) == 3
    assert len(e.production._image(e.actor)._load(e.nid, e.scope.get('branch_id'))) == 1


def test_running_provider_image_jobs_remain_not_cancellable(cutout):
    from app.creative.production_execution import digest
    e = cutout; owner = e.production._image(e.actor)
    body = {'operation_id': 'm5.image.t2i', 'provider_id': 'synthetic', 'model_id': 'synthetic', 'prompt': 'Original provider job', 'parameters': {}}
    context = {**e.production._base(e.nid, e.scope, e.actor, lambda: None), 'request_id': 'original-provider',
        'operation_id': body['operation_id'], 'request_digest': digest(body), 'sources': [],
        'provider_binding': {'provider_id': 'synthetic', 'model_id': 'synthetic'}, 'rights': {}}
    row = owner.create_studio(e.nid, None, e.actor, body, context, lambda: None)
    def running(rows):
        raw = owner._find(rows, row['id']); raw['status'] = 'RUNNING'; return raw
    owner._mutate(e.nid, None, running)
    with pytest.raises(ValueError, match='STUDIO_IMAGE_NOT_CANCELLABLE'):
        owner.cancel_studio(e.nid, None, e.actor, row['id'], expected_version=row['version'],
            expected_request_digest=row['request_digest'], guard=lambda: None)
