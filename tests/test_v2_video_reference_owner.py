"""Real CPU frame preparation, original-Asset commit and File/PostgreSQL fences."""
import base64
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from test_v2_independent_workspace import rig, reopened, upload


@pytest.fixture(scope='module')
def video_bytes(tmp_path_factory):
    target = tmp_path_factory.mktemp('video-reference-cpu') / 'source.mp4'
    ffmpeg = shutil.which('ffmpeg'); assert ffmpeg
    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-threads', '1', '-f', 'lavfi', '-i',
        'testsrc2=size=64x48:rate=10:duration=2', '-an', '-c:v', 'mpeg4', '-threads', '1', '-y', str(target)],
        check=True, capture_output=True, timeout=20)
    return target.read_bytes()


def source_asset(e, data):
    e.service.activate(e.nid, e.scope, e.actor)
    return e.service.import_asset(e.nid, e.scope, e.actor, upload(data, filename='source.mp4', kind='video'))


def preview_body(source):
    return {'contract': 'studio-video-reference-preview/1', 'source_version': source['version'],
            'source_sha256': source['sha256'], 'in_ms': 300, 'out_ms': 1300, 'sample_count': 2}


def prepared(e, data):
    source = source_asset(e, data)
    preview = e.service.preview_video_reference(e.nid, e.scope, source['id'], preview_body(source), lambda: None)
    return source, preview, {**preview_body(source), 'contract': 'studio-video-reference-asset/1',
        'selected_index': 1, 'reviewed_preview_digest': preview['preview_digest'],
        'reviewed_png_sha256': preview['frames'][1]['png_sha256'], 'confirm_reference': True,
        'idempotency_key': 'same-reviewed-frame'}


def save(e, source, body, guard=lambda: None):
    return e.service.save_video_reference(e.nid, e.scope, e.actor, source['id'], body, guard)


def files(e):
    return {p.name: p.read_bytes() for p in e.assets.root.iterdir() if p.is_file()}


def test_preview_is_ephemeral_exact_decoded_observation(rig, video_bytes):
    e = rig; source = source_asset(e, video_bytes); before = files(e)
    result = e.service.preview_video_reference(e.nid, e.scope, source['id'], preview_body(source), lambda: None)
    assert result['source'] == {'id': source['id'], 'version': source['version'], 'sha256': source['sha256']}
    assert [f['source_frame_index'] for f in result['frames']] == [3, 8]
    assert [f['time_ms'] for f in result['frames']] == [{'num': 300, 'den': 1}, {'num': 800, 'den': 1}]
    assert files(e) == before and e.chapters.list(e.nid) == []
    assert result['model_called'] is False and result['semantic_analysis'] is False
    assert '_project_binding' not in json.dumps(result) and str(e.root) not in json.dumps(result)


def test_reviewed_pixels_first_commit_reopen_replay_and_wire(rig, video_bytes, monkeypatch):
    e = rig; source, preview, body = prepared(e, video_bytes); seen = []; original = e.assets._write_meta
    def write(row):
        if '_video_reference_origin' in row:
            assert row['parameters']['asset_lineage_v2']['parents'] == {source['id']: {'version': source['version'], 'digest': source['sha256']}}
            assert row['source_asset_ids'] == [source['id']]
            seen.append(row['id'])
        return original(row)
    monkeypatch.setattr(e.assets, '_write_meta', write)
    result = save(e, source, body); asset = result['asset']
    assert seen == [asset['id']] and asset['kind'] == 'image' and asset['media_type'] == 'image/png'
    assert result['receipt']['asset_created'] and not result['receipt']['replayed']
    assert asset['video_reference']['source_frame_index'] == 8
    assert asset['provenance']['integrity'] == 'VERIFIED' and asset['provenance']['origin'] == 'MANUAL_EDIT'
    assert not asset['provenance']['stale'] and '_video_reference_origin' not in json.dumps(result)
    service = reopened(e)
    assert service.asset(e.nid, e.scope, asset['id']) == asset
    assert service.download(e.nid, e.scope, asset['id'])[1] == base64.b64decode(preview['frames'][1]['content_base64'])
    replay = save(e, source, body)
    assert replay['asset'] == asset and replay['receipt']['replayed'] and not replay['receipt']['asset_created']
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2
    if e.backend == 'file':
        (Path(os.environ['NOVEL_DATA_PATH']).parent / 'video-reference-wire.json').write_text(
            json.dumps({'source': source, 'review': preview, 'result': result}, ensure_ascii=False, indent=2) + '\n')


@pytest.mark.parametrize('change', ['pixels', 'preview', 'selected', 'source', 'confirm', 'actor'])
def test_changed_review_or_identity_cannot_duplicate(rig, video_bytes, change):
    e = rig; source, preview, body = prepared(e, video_bytes); save(e, source, body); before = files(e)
    if change == 'pixels': body['reviewed_png_sha256'] = '0' * 64
    elif change == 'preview': body['reviewed_preview_digest'] = '0' * 64
    elif change == 'selected': body['selected_index'] = 0
    elif change == 'source': body['source_version'] += 1
    elif change == 'confirm': body['confirm_reference'] = False
    elif change == 'actor': e.actor = 'other-author'
    with pytest.raises(ValueError): save(e, source, body)
    assert files(e) == before


@pytest.mark.parametrize('change', ['version', 'delete', 'bytes', 'recreate', 'revoke', 'flag'])
def test_interleaving_during_native_work_prevents_publication(rig, video_bytes, monkeypatch, change):
    import app.services.studio_video_reference_frames as native
    e = rig; source, preview, body = prepared(e, video_bytes); original = native.prepare_frames; allowed = True
    def changed(*a, **kw):
        nonlocal allowed
        result = original(*a, **kw)
        if change == 'recreate': e.novels.delete(e.nid); e.create_project(nid=e.nid)
        elif change == 'revoke': allowed = False
        elif change == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
        else:
            with e.service._asset_scope(e.nid, e.scope):
                if change == 'version': e.assets.update_metadata(source['id'], {'scene_id': 'changed'}, expected_version=source['version'])
                elif change == 'delete': e.assets.delete(source['id'])
                else: e.assets._bin_path(source['id']).write_bytes(b'tampered')
        return result
    def guard():
        if not allowed: raise PermissionError('revoked')
    monkeypatch.setattr(native, 'prepare_frames', changed)
    from fastapi import HTTPException
    with pytest.raises((ValueError, FileNotFoundError, PermissionError, HTTPException)): save(e, source, body, guard)
    assert len(list(e.assets.root.glob('*.json'))) == 1


@pytest.mark.parametrize('after_commit', [False, True])
def test_durable_commit_failure_retries_original_receipt(rig, video_bytes, monkeypatch, after_commit):
    e = rig; source, preview, body = prepared(e, video_bytes); before = files(e); original = e.assets._write_meta
    def failed(row):
        if '_video_reference_origin' in row:
            if after_commit: original(row)
            raise OSError('synthetic acknowledgement failure')
        return original(row)
    monkeypatch.setattr(e.assets, '_write_meta', failed)
    with pytest.raises(OSError): save(e, source, body)
    if not after_commit: assert files(e) == before
    else: assert len(list(e.assets.root.glob('*.json'))) == 2
    monkeypatch.setattr(e.assets, '_write_meta', original)
    result = save(e, source, body)
    assert result['receipt']['replayed'] is after_commit
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2


def test_source_pin_immutable_annotation_and_staleness(rig, video_bytes):
    e = rig; source, preview, body = prepared(e, video_bytes); asset = save(e, source, body)['asset']; before = files(e)
    with e.service._asset_scope(e.nid, e.scope):
        for fields in ({'source_asset_ids': []}, {'provider_id': 'fake'}, {'approved_at': 'pretend'}):
            with pytest.raises(ValueError): e.assets.update_metadata(asset['id'], fields, expected_version=1)
    assert files(e) == before
    changed = e.service.annotate(e.nid, e.scope, e.actor, asset['id'], {'expected_version': 1,
        'origin': 'MANUAL_EDIT', 'parent_asset_ids': [source['id']], 'license': {'label': 'Author claim'}, 'operation': 'Reference note'})
    assert changed['version'] == 2 and changed['video_reference'] == asset['video_reference']
    assert save(e, source, body)['asset'] == changed
    with e.service._asset_scope(e.nid, e.scope):
        e.assets.update_metadata(source['id'], {'scene_id': 'changed'}, expected_version=source['version'])
    stale = e.service.asset(e.nid, e.scope, asset['id'])
    assert stale['provenance']['stale'] and stale['video_reference'] == asset['video_reference']


def test_same_key_concurrency_converges(rig, video_bytes):
    e = rig; source, preview, body = prepared(e, video_bytes); second = reopened(e); gate = Barrier(2)
    def run(service):
        gate.wait(timeout=10)
        return service.save_video_reference(e.nid, e.scope, e.actor, source['id'], body, lambda: None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(run, e.service), pool.submit(run, second)
        one, two = a.result(timeout=60), b.result(timeout=60)
    assert one['asset'] == two['asset'] and sorted([one['receipt']['replayed'], two['receipt']['replayed']]) == [False, True]


def test_quota_low_disk_and_private_source_fail_closed(rig, video_bytes, monkeypatch):
    from app.creative.storage_admission import StudioStorageCapacityError
    e = rig; source, preview, body = prepared(e, video_bytes); before = files(e)
    monkeypatch.setattr(e.service, 'MAX_ASSETS', 1)
    with pytest.raises(ValueError, match='CREATIVE_PROJECT_ASSET_QUOTA'): save(e, source, body)
    assert files(e) == before
    monkeypatch.setattr(e.service, 'MAX_ASSETS', 100)
    monkeypatch.setattr(e.service.storage_admission, 'require', lambda *a: (_ for _ in ()).throw(StudioStorageCapacityError('CREATIVE_STORAGE_LOW_SPACE')))
    with pytest.raises(StudioStorageCapacityError): save(e, source, body)
    assert files(e) == before
    raw = e.assets._load(source['id']); raw['_owner_actor_id'] = e.actor; e.assets._write_meta(raw)
    with pytest.raises((FileNotFoundError, ValueError)): e.service.preview_video_reference(e.nid, e.scope, source['id'], preview_body(source), lambda: None)


@pytest.mark.parametrize('field', ['contract', 'source', 'pts', 'png_sha256', 'time_ms'])
def test_corrupt_origin_cannot_gain_legacy_visibility(rig, video_bytes, field):
    e = rig; source, preview, body = prepared(e, video_bytes); asset = save(e, source, body)['asset']
    raw = e.assets._load(asset['id']); raw['_video_reference_origin'][field] = 'invalid'; e.assets._write_meta(raw)
    with e.service._asset_scope(e.nid, e.scope):
        with pytest.raises(FileNotFoundError): e.assets.get(asset['id'])
    with pytest.raises(ValueError, match='VIDEO_REFERENCE_RECEIPT_UNAVAILABLE'): save(e, source, body)


@pytest.mark.parametrize('change', ['version', 'digest', 'kind', 'deleted', 'private', 'feature'])
def test_bad_source_rejected_before_native_spawn(rig, video_bytes, monkeypatch, change):
    import app.services.studio_video_reference_frames as native
    from fastapi import HTTPException
    e = rig; source = source_asset(e, video_bytes); body = preview_body(source)
    if change == 'version': body['source_version'] += 1
    elif change == 'digest': body['source_sha256'] = '0' * 64
    elif change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    else:
        raw = e.assets._load(source['id'])
        if change == 'kind': raw['kind'] = 'audio'
        elif change == 'deleted': raw['deleted_at'] = '2026-10-18T00:00:00Z'
        else: raw['_owner_actor_id'] = e.actor
        e.assets._write_meta(raw)
    before = files(e)
    monkeypatch.setattr(native, 'prepare_frames', lambda *a, **k: (_ for _ in ()).throw(AssertionError('native must not start')))
    with pytest.raises((ValueError, FileNotFoundError, HTTPException)):
        e.service.preview_video_reference(e.nid, e.scope, source['id'], body, lambda: None)
    assert files(e) == before


def test_deleted_reference_retry_never_recreates(rig, video_bytes, monkeypatch):
    e = rig; source, preview, body = prepared(e, video_bytes); asset = save(e, source, body)['asset']
    with e.service._asset_scope(e.nid, e.scope): e.assets.delete(asset['id'])
    before = files(e)
    with pytest.raises(ValueError): save(e, source, body)
    assert files(e) == before and len(list(e.assets.root.glob('*.json'))) == 2
