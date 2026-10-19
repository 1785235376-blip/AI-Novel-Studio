"""Native File Asset/Timeline commits and explicit crash recovery, no renderer jobs.

Input pages use real Comic shapes/text, with no external raster source. The
existing Windows no-follow preview/orphan boundary remains a refused case.
"""
import copy
import hashlib
import io
from contextlib import contextmanager

import pytest
from PIL import Image

from app.asset_providers import AssetProviderRegistry
from app.experimental.comic_layouts import ComicLayoutsService
from app.experimental.comic_timeline_handoff import COLLECTION
from app.services.comic_page_origin import FIELD, FEATURES, record
from test_comic_timeline_handoff import handoff, page, request, preview
from test_v2_independent_workspace import rig, reopened
from test_v2_discovered_image_production import owner


def body(rig, handoff, pages, key='create', durations=None):
    selected = request(pages, durations)
    report, _ = preview(rig, handoff, selected)
    return {'request_id': key, 'request': selected, 'reviewed_preview_digest': report['preview_digest'],
            'acknowledge_losses': True}


def confirm(rig, handoff, value, guard=lambda: None):
    return handoff.confirm(rig.nid, rig.scope, rig.actor, value, guard)


def status(rig, handoff, key='create'):
    return handoff.status(rig.nid, rig.scope, rig.actor, key)


def resume(rig, handoff, key='create'):
    observed = status(rig, handoff, key)
    return handoff.resume(rig.nid, rig.scope, rig.actor, key, observed['version'])


def restart(rig, monkeypatch):
    service = reopened(rig)
    alternate = copy.copy(rig); alternate.service = service
    production = owner(AssetProviderRegistry(), monkeypatch, alternate)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(sorted(FEATURES)))
    comic = ComicLayoutsService(service.store.store, rig.novels, rig.chapters, None, service.assets,
                               independent_store=service.store)
    production.configure_comic(comic)
    return production.comic_handoff


def timelines(rig):
    from app.creative.production_execution import TIMELINES
    return rig.raw_store.read(rig.nid, rig.scope)['collections'].get(TIMELINES, {})


def test_two_real_page_png_assets_and_original_twenty_second_draft(rig, handoff, tmp_path):
    pages = [page(rig, handoff), page(rig, handoff, layers=True, text=True, shift=10)]
    value = body(rig, handoff, pages, durations=[7000, 13000])
    comic_before = copy.deepcopy(rig.raw_store.read(rig.nid, rig.scope)['collections'][handoff.comic.RECORDS])
    result = confirm(rig, handoff, value)
    assert result['status'] == 'DRAFT_CREATED' and len(timelines(rig)) == 1
    assert result['version'] == 4 and not result['approval_inherited'] and not result['video_rendered']
    timeline = result['timeline']['timeline']
    assert timeline['schema_version'] == 2 and timeline['duration_ms'] == 20000
    assert len(timeline['tracks']) == 1 and timeline['tracks'][0]['kind'] == 'VIDEO'
    assert [c['out_ms'] for c in timeline['tracks'][0]['clips']] == [7000, 13000]
    assert [c['start_ms'] for c in timeline['tracks'][0]['clips']] == [0, 7000]
    assert all(c['in_ms'] == 0 and c['speed_num'] == c['speed_den'] == 1 and not c['include_audio']
               for c in timeline['tracks'][0]['clips'])
    assert not timeline['captions']
    with handoff.workspace._asset_scope(rig.nid, rig.scope):
        for index, step in enumerate(result['steps']):
            asset = rig.assets.get(step['asset_id'])
            data = rig.assets.content(asset['id'])
            origin = record(asset)
            assert origin['source']['id'] == pages[index]['id'] and origin['asset_id'] == asset['id']
            assert hashlib.sha256(data).hexdigest() == result['preview']['pages'][index]['png_sha256']
            assert FIELD not in rig.assets.public(asset)
            assert all(asset.get(k) is None for k in ('approved_at', 'source_job_id', 'model_id', 'provider_id'))
            with Image.open(io.BytesIO(data)) as image:
                assert image.size == (320, 640) and image.mode == 'RGB'
            projected = handoff.workspace._view(rig.nid, rig.scope, asset)
            assert projected['comic_page']['classification'] == 'ORIGINAL_COMIC_RENDER_COPY'
            assert projected['provenance']['origin'] == 'DERIVED_PROCESSING'
            assert projected['provenance']['sources'][0]['state'] == 'UNVERIFIED'
            assert projected['provenance']['source_task_id'] is None
            (tmp_path / (str(index) + '.png')).write_bytes(data)
    assert comic_before == rig.raw_store.read(rig.nid, rig.scope)['collections'][handoff.comic.RECORDS]
    assert len(list(rig.assets.root.glob('*.bin'))) == 2


def test_double_confirm_and_real_reopen_readback_do_not_duplicate(rig, handoff, monkeypatch):
    value = body(rig, handoff, [page(rig, handoff)])
    first = confirm(rig, handoff, value)
    second = confirm(rig, handoff, value)
    assert second['timeline_snapshot'] == first['timeline_snapshot']
    current = restart(rig, monkeypatch)
    assert status(rig, current)['timeline_snapshot'] == first['timeline_snapshot']
    assert confirm(rig, current, value)['timeline_snapshot'] == first['timeline_snapshot']
    assert len(timelines(rig)) == len(list(rig.assets.root.glob('*.bin'))) == 1
    bad = copy.deepcopy(value); bad['request']['title'] = 'Different explicit intent'
    with pytest.raises(ValueError, match='REQUEST_CONFLICT'): confirm(rig, current, bad)
    assert len(timelines(rig)) == 1


def test_partial_asset_commit_requires_explicit_resume_and_cas(rig, handoff, monkeypatch):
    value = body(rig, handoff, [page(rig, handoff), page(rig, handoff, shift=10)])
    original = rig.assets.create
    calls = 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise OSError('second native Asset write failed')
        return original(*args, **kwargs)
    monkeypatch.setattr(rig.assets, 'create', fail_second)
    with pytest.raises(OSError): confirm(rig, handoff, value)
    observed = status(rig, handoff)
    assert observed['status'] == 'PLANNED' and observed['version'] == 2
    assert [s['state'] for s in observed['steps']] == ['READY', 'PENDING']
    assert not timelines(rig) and len(list(rig.assets.root.glob('*.bin'))) == 1
    assert confirm(rig, handoff, value)['version'] == 2  # no automatic retry
    with pytest.raises(ValueError): handoff.resume(rig.nid, rig.scope, rig.actor, 'create', 1)
    current = restart(rig, monkeypatch)
    finished = resume(rig, current)
    assert [s['asset_id'] for s in finished['steps']] == [s['asset_id'] for s in observed['steps']]
    assert len(timelines(rig)) == 1 and len(list(rig.assets.root.glob('*.bin'))) == 2


@pytest.mark.parametrize('after_commit', [False, True])
def test_asset_metadata_failure_reconciles_only_planned_exact_id(rig, handoff, monkeypatch, after_commit):
    value = body(rig, handoff, [page(rig, handoff)])
    original = rig.assets._write_meta
    def fail(meta):
        if after_commit: original(meta)
        raise OSError('native Asset metadata acknowledgement lost')
    monkeypatch.setattr(rig.assets, '_write_meta', fail)
    with pytest.raises(OSError): confirm(rig, handoff, value)
    observed = status(rig, handoff)
    aid = observed['steps'][0]['asset_id']
    assert rig.assets._meta_path(aid).exists() is after_commit
    assert rig.assets._bin_path(aid).exists() is after_commit
    assert observed['steps'][0]['observed_state'] == (
        'COMMITTED_AWAITING_EXPLICIT_RESUME' if after_commit else 'AWAITING_EXPLICIT_RESUME')
    monkeypatch.setattr(rig.assets, '_write_meta', original)
    completed = resume(rig, restart(rig, monkeypatch))
    assert completed['steps'][0]['asset_id'] == aid
    assert len(timelines(rig)) == len(list(rig.assets.root.glob('*.bin'))) == 1


@pytest.mark.parametrize('after_commit', [False, True])
def test_original_scope_failure_after_asset_has_no_duplicate(rig, handoff, monkeypatch, after_commit):
    value = body(rig, handoff, [page(rig, handoff)])
    original = rig.raw_store.transaction
    @contextmanager
    def fail(*args, **kwargs):
        with original(*args, **kwargs) as state:
            yield state
            committed_asset = bool(list(rig.assets.root.glob('*.bin')))
            if committed_asset and not after_commit: raise OSError('scope rollback after Asset commit')
        if committed_asset and after_commit: raise OSError('scope acknowledgement lost')
    monkeypatch.setattr(rig.raw_store, 'transaction', fail)
    with pytest.raises(OSError): confirm(rig, handoff, value)
    monkeypatch.setattr(rig.raw_store, 'transaction', original)
    observed = status(rig, handoff)
    assert not timelines(rig) and len(list(rig.assets.root.glob('*.bin'))) == 1
    result = resume(rig, restart(rig, monkeypatch))
    assert result['steps'][0]['asset_id'] == observed['steps'][0]['asset_id']
    assert len(timelines(rig)) == 1


def test_timeline_commit_lost_reply_readback_never_recreates(rig, handoff, monkeypatch):
    value = body(rig, handoff, [page(rig, handoff)])
    original = rig.raw_store.transaction
    @contextmanager
    def lost(*args, **kwargs):
        committed = False
        with original(*args, **kwargs) as state:
            yield state
            committed = any(r.get('status') == 'DRAFT_CREATED' for r in state['collections'].get(COLLECTION, {}).values())
        if committed: raise OSError('Timeline committed; HTTP reply lost')
    monkeypatch.setattr(rig.raw_store, 'transaction', lost)
    with pytest.raises(OSError): confirm(rig, handoff, value)
    monkeypatch.setattr(rig.raw_store, 'transaction', original)
    current = restart(rig, monkeypatch)
    observed = status(rig, current)
    assert observed['status'] == 'DRAFT_CREATED' and len(timelines(rig)) == 1
    assert confirm(rig, current, value)['timeline_snapshot'] == observed['timeline_snapshot']
    with pytest.raises(ValueError): resume(rig, current)
    assert len(timelines(rig)) == 1


@pytest.mark.parametrize('change', ['page', 'review', 'actor', 'incarnation', 'guard'])
def test_partial_recovery_rejects_changed_source_or_authority(rig, handoff, monkeypatch, change):
    saved = page(rig, handoff)
    value = body(rig, handoff, [saved, page(rig, handoff, shift=10)])
    original = rig.assets.create
    def first_only(*args, **kwargs):
        if list(rig.assets.root.glob('*.bin')): raise OSError('stop after one Asset')
        return original(*args, **kwargs)
    monkeypatch.setattr(rig.assets, 'create', first_only)
    with pytest.raises(OSError): confirm(rig, handoff, value)
    observed = status(rig, handoff)
    monkeypatch.setattr(rig.assets, 'create', original)
    actor, guard = rig.actor, lambda: None
    if change == 'page':
        doc = copy.deepcopy(saved['document']); doc['title'] = 'Changed after preview'
        handoff.comic.save(rig.nid, rig.scope, rig.actor, doc, rid=saved['id'], expected_version=saved['version'])
    elif change == 'review':
        with handoff.comic._independent_transaction(rig.nid, rig.scope) as state:
            state['collections'][handoff.comic.RECORDS][saved['id']]['approval']['digest'] = 'f' * 64
    elif change == 'actor': actor = 'another-author'
    elif change == 'guard':
        def guard(): raise PermissionError('authority revoked')
    else:
        rig.novels.delete(rig.nid); rig.create_project('Recreated', nid=rig.nid)
        rig.service.activate(rig.nid, rig.scope, rig.actor)
    with pytest.raises((ValueError, FileNotFoundError, PermissionError)):
        handoff.resume(rig.nid, rig.scope, actor, 'create', observed['version'], guard)
    assert len(list(rig.assets.root.glob('*.bin'))) == 1 and not timelines(rig)


def test_cancel_keeps_partial_assets_and_prevents_future_resume(rig, handoff, monkeypatch):
    value = body(rig, handoff, [page(rig, handoff), page(rig, handoff, shift=10)])
    original = rig.assets.create
    def stop(*args, **kwargs):
        if list(rig.assets.root.glob('*.bin')): raise OSError('explicit stop')
        return original(*args, **kwargs)
    monkeypatch.setattr(rig.assets, 'create', stop)
    with pytest.raises(OSError): confirm(rig, handoff, value)
    observed = status(rig, handoff)
    cancelled = handoff.cancel(rig.nid, rig.scope, rig.actor, 'create', observed['version'])
    assert cancelled['status'] == 'CANCELLED' and len(list(rig.assets.root.glob('*.bin'))) == 1
    with pytest.raises(ValueError): resume(rig, handoff)
    assert not timelines(rig)


def test_stale_preview_or_no_ack_writes_nothing(rig, handoff):
    value = body(rig, handoff, [page(rig, handoff)])
    before = rig.raw_store.read(rig.nid, rig.scope)
    for bad in [{**value, 'reviewed_preview_digest': '0' * 64}, {**value, 'acknowledge_losses': False}]:
        with pytest.raises(ValueError): confirm(rig, handoff, bad)
        assert before == rig.raw_store.read(rig.nid, rig.scope)
        assert not list(rig.assets.root.glob('*.bin'))


def test_asset_origin_immutable_and_ordinary_upload_cannot_mint_it(rig, handoff):
    result = confirm(rig, handoff, body(rig, handoff, [page(rig, handoff)]))
    aid = result['steps'][0]['asset_id']
    with handoff.workspace._asset_scope(rig.nid, rig.scope):
        meta = rig.assets.get(aid)
        for patch in [{FIELD: meta[FIELD]}, {'approved_at': 'forged'}, {'source_job_id': 'forged'},
                      {'source_asset_ids': ['forged']}, {'parameters': {'pretend': 'manual'}}]:
            with pytest.raises(ValueError): rig.assets.update_metadata(aid, patch, expected_version=1)
        assert record(rig.assets.get(aid)) == record(meta)


def test_committed_readback_preserves_later_original_timeline_edits(rig, handoff):
    value = body(rig, handoff, [page(rig, handoff)])
    created = confirm(rig, handoff, value)
    timeline = created['timeline']
    saved = handoff.production.timeline_save(rig.nid, rig.scope, rig.actor, timeline['id'],
        {'expected_version': timeline['version'], 'title': 'User edited original Timeline',
         'timeline': timeline['timeline']}, lambda: None)
    assert saved['version'] == 2
    replay = confirm(rig, handoff, value)
    assert replay['timeline']['version'] == 2 and replay['timeline_state'] == 'MODIFIED_AFTER_CREATION'
    assert replay['timeline']['title'] == 'User edited original Timeline'
    assert replay['timeline_snapshot'] == created['timeline_snapshot']
    assert len(timelines(rig)) == 1


def test_original_timeline_save_rechecks_current_comic_source(rig, handoff):
    saved = page(rig, handoff)
    created = confirm(rig, handoff, body(rig, handoff, [saved]))
    doc = copy.deepcopy(saved['document']); doc['title'] = 'Source becomes a new draft'
    handoff.comic.save(rig.nid, rig.scope, rig.actor, doc, rid=saved['id'], expected_version=saved['version'])
    timeline = created['timeline']
    with pytest.raises(ValueError):
        handoff.production.timeline_save(rig.nid, rig.scope, rig.actor, timeline['id'],
            {'expected_version': 1, 'title': timeline['title'], 'timeline': timeline['timeline']}, lambda: None)
    # Immutable creation readback remains readable; it does not assert freshness.
    observed = status(rig, handoff)
    assert not observed['source_current_checked'] and observed['timeline']['version'] == 1


def test_revocation_after_asset_metadata_commit_retains_exact_effect_for_explicit_recovery(rig, handoff, monkeypatch):
    value = body(rig, handoff, [page(rig, handoff), page(rig, handoff, shift=10)])
    original = rig.assets._write_meta
    revoked = False
    def committed(meta):
        nonlocal revoked
        original(meta); revoked = True
    def guard():
        if revoked: raise PermissionError('revoked after durable Asset write')
    monkeypatch.setattr(rig.assets, '_write_meta', committed)
    with pytest.raises(PermissionError): confirm(rig, handoff, value, guard)
    monkeypatch.setattr(rig.assets, '_write_meta', original)
    observed = status(rig, handoff)
    assert observed['version'] == 1 and observed['steps'][0]['state'] == 'PENDING'
    assert observed['steps'][0]['observed_state'] == 'COMMITTED_AWAITING_EXPLICIT_RESUME'
    assert len(list(rig.assets.root.glob('*.bin'))) == 1 and not timelines(rig)
    with pytest.raises(PermissionError):
        handoff.resume(rig.nid, rig.scope, rig.actor, 'create', observed['version'], guard)
    completed = resume(rig, restart(rig, monkeypatch))
    assert completed['steps'][0]['asset_id'] == observed['steps'][0]['asset_id']
    assert len(list(rig.assets.root.glob('*.bin'))) == 2 and len(timelines(rig)) == 1


def test_unindexed_native_png_keeps_original_no_follow_boundary(rig, handoff, monkeypatch):
    import os
    value = body(rig, handoff, [page(rig, handoff)])
    original = rig.assets.create
    def stopped(*args, **kwargs): raise OSError('simulate crash before Asset commit')
    monkeypatch.setattr(rig.assets, 'create', stopped)
    with pytest.raises(OSError): confirm(rig, handoff, value)
    observed = status(rig, handoff)
    aid = observed['steps'][0]['asset_id']
    _, images = preview(rig, handoff, value['request'])
    rig.assets._bin_path(aid).write_bytes(images[0])  # real exact-ID binary-before-metadata crash
    monkeypatch.setattr(rig.assets, 'create', original)
    if not getattr(os, 'O_NOFOLLOW', 0) or not getattr(os, 'O_NONBLOCK', 0):
        with pytest.raises(ValueError, match='ASSET_BOUNDED_READ_UNSUPPORTED'): resume(rig, handoff)
        assert rig.assets._bin_path(aid).read_bytes() == images[0]
        assert not rig.assets._meta_path(aid).exists() and not timelines(rig)
        assert status(rig, handoff)['steps'][0]['observed_state'] == 'UNINDEXED_BYTES_AWAITING_EXPLICIT_RESUME'
    else:
        result = resume(rig, handoff)
        assert result['steps'][0]['asset_id'] == aid and len(timelines(rig)) == 1


@pytest.mark.parametrize('limit', ['assets', 'bytes', 'receipts'])
def test_whole_request_resource_admission_has_no_partial_writes(rig, handoff, monkeypatch, limit):
    value = body(rig, handoff, [page(rig, handoff), page(rig, handoff, shift=10)])
    before = rig.raw_store.read(rig.nid, rig.scope)
    if limit == 'assets': monkeypatch.setattr(handoff.workspace, 'MAX_ASSETS', 1)
    elif limit == 'bytes': monkeypatch.setattr(handoff.workspace, 'MAX_PROJECT_BYTES', 1)
    else: monkeypatch.setattr('app.experimental.comic_timeline_handoff.MAX_RECEIPTS', 0)
    with pytest.raises(ValueError): confirm(rig, handoff, value)
    assert before == rig.raw_store.read(rig.nid, rig.scope)
    assert not list(rig.assets.root.glob('*.bin'))


@pytest.mark.parametrize('corruption', ['page_count', 'step_id', 'counter', 'digest', 'source'])
def test_corrupt_durable_receipt_never_guesses_or_adopts_assets(rig, handoff, monkeypatch, corruption):
    value = body(rig, handoff, [page(rig, handoff)])
    def stop(*args, **kwargs): raise OSError('planned but no Asset')
    monkeypatch.setattr(rig.assets, 'create', stop)
    with pytest.raises(OSError): confirm(rig, handoff, value)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        row = next(iter(state['collections'][COLLECTION].values()))
        if corruption == 'page_count': row['preview']['pages'] = []
        elif corruption == 'step_id': row['steps'][0]['asset_id'] = '../unknown'
        elif corruption == 'counter': row['version'] = True
        elif corruption == 'digest': row['preview']['preview_digest'] = '0' * 64
        else: row['preview']['pages'][0]['source']['version'] = True
    with pytest.raises(ValueError): status(rig, handoff)
    assert not list(rig.assets.root.glob('*.bin')) and not timelines(rig)


def test_readback_rejects_mismatched_timeline_creation_receipt(rig, handoff):
    created = confirm(rig, handoff, body(rig, handoff, [page(rig, handoff)]))
    from app.creative.production_execution import TIMELINES
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        state['collections'][TIMELINES][created['timeline']['id']]['comic_handoff_origin']['preview_digest'] = '0' * 64
    with pytest.raises(ValueError, match='TIMELINE_RECEIPT_CHANGED'): status(rig, handoff)
    assert len(timelines(rig)) == 1
