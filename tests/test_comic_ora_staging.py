"""Original owner staging boundaries, with genuine File/PG scope variants."""
import copy
import hashlib
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from test_v2_independent_workspace import rig, reopened
from test_comic_ora_import import archive
from app.experimental.comic_layouts import ComicLayoutsService
from app.experimental.comic_ora_staging import ComicOraStaging, COLLECTION
from app.services.comic_ora_origin import FIELD


def adapter(workspace):
    comic = ComicLayoutsService(workspace.store.store, workspace.novels, workspace.creative.chapters,
        None, workspace.assets, independent_store=workspace.store)
    return ComicOraStaging(comic, workspace)


@pytest.fixture
def staging(rig, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,comic_layouts_v2,ai_director_v2')
    # Original owner creation is explicit fixture setup, never staging provision.
    rig.service.store.incarnation(rig.nid)
    return adapter(rig.service)


def prepare(rig, staging, raw=None, key='test'):
    raw = raw or archive()
    return staging.prepare(rig.nid, rig.scope, rig.actor, raw,
        archive_sha256=hashlib.sha256(raw).hexdigest(), request_key=key, guard=lambda: None)


def stage(rig, staging, row, raw=None, **kw):
    return staging.stage(rig.nid, rig.scope, rig.actor, row['id'], raw or archive(), guard=lambda: None, **kw)


def test_real_private_staging_status_resume_and_no_page(rig, staging):
    row = prepare(rig, staging)
    assert not list(rig.assets.root.glob('*.bin'))
    result = stage(rig, staging, row)
    assert result['status'] == 'STAGED_PRIVATE_REVIEW_PENDING'
    assert stage(rig, adapter(reopened(rig)), row) == result
    aid = result['steps'][0]['asset_id']
    assert set(rig.raw_store.read(rig.nid, rig.scope)['collections']) == {COLLECTION}
    with rig.service._asset_scope(rig.nid, rig.scope):
        meta = rig.assets.get(aid, actor_id=rig.actor)
        assert meta[FIELD]['origin_status'] == 'UNVERIFIED_EXTERNAL_RASTER' and meta['version'] == 1
        assert FIELD not in rig.assets.public(meta)
        assert not ComicLayoutsService._manual(meta)
        for actor in (None, 'other'):
            with pytest.raises(FileNotFoundError): rig.assets.get(aid, actor_id=actor)
        with pytest.raises(ValueError, match='IMMUTABLE'):
            rig.assets.update_metadata(aid, {'approved_at': 'now'}, actor_id=rig.actor)
        with pytest.raises(ValueError, match='REVIEW_NOT_IMPLEMENTED'):
            rig.assets.promote_owned(aid, actor_id=rig.actor, branch_id=None, expected_version=1, provenance={})
    with pytest.raises(FileNotFoundError): rig.assets.get(aid, actor_id=rig.actor)
    assert len(list(rig.assets.root.glob('*.bin'))) == 1


@pytest.mark.parametrize('after_commit', [False, True])
def test_asset_metadata_failure_exact_id_cleanup_and_resume(rig, staging, monkeypatch, after_commit):
    row = prepare(rig, staging); aid = row['steps'][0]['asset_id']
    original = rig.assets._write_meta
    def fail(meta):
        assert meta['id'] == aid and FIELD in meta
        if after_commit: original(meta)
        raise OSError('lost asset acknowledgement')
    monkeypatch.setattr(rig.assets, '_write_meta', fail)
    with pytest.raises(OSError): stage(rig, staging, row)
    assert rig.assets._meta_path(aid).exists() is after_commit
    assert rig.assets._bin_path(aid).exists() is after_commit
    assert not list(rig.assets.root.glob('*.tmp'))
    monkeypatch.setattr(rig.assets, '_write_meta', original)
    observed = staging.status(rig.nid, rig.scope, rig.actor, row['id'], guard=lambda: None)
    assert observed['steps'][0]['observed_state'] == ('COMMITTED_AWAITING_RECEIPT_RESUME' if after_commit else 'AWAITING_ARCHIVE_STAGE')
    final = stage(rig, adapter(reopened(rig)), row)
    assert final['steps'][0]['asset_id'] == aid and len(list(rig.assets.root.glob('*.bin'))) == 1


@pytest.mark.parametrize('after_commit', [False, True])
def test_scope_failure_after_asset_commit_reconciles_exact_id(rig, staging, monkeypatch, after_commit):
    row = prepare(rig, staging); original = rig.raw_store.transaction
    @contextmanager
    def fail(*args, **kwargs):
        with original(*args, **kwargs) as state:
            yield state
            if not after_commit: raise OSError('scope rollback after durable Asset')
        if after_commit: raise OSError('lost scope acknowledgement')
    monkeypatch.setattr(rig.raw_store, 'transaction', fail)
    with pytest.raises(OSError): stage(rig, staging, row)
    assert len(list(rig.assets.root.glob('*.bin'))) == 1
    monkeypatch.setattr(rig.raw_store, 'transaction', original)
    assert stage(rig, adapter(reopened(rig)), row)['status'] == 'STAGED_PRIVATE_REVIEW_PENDING'
    assert len(list(rig.assets.root.glob('*.bin'))) == 1


def test_prepare_lost_ack_and_concurrent_resume(rig, staging, monkeypatch):
    original = rig.raw_store.transaction
    @contextmanager
    def lost(*args, **kwargs):
        with original(*args, **kwargs) as state: yield state
        raise OSError('lost prepare acknowledgement')
    monkeypatch.setattr(rig.raw_store, 'transaction', lost)
    with pytest.raises(OSError): prepare(rig, staging)
    monkeypatch.setattr(rig.raw_store, 'transaction', original)
    row = prepare(rig, adapter(reopened(rig)))
    barrier = Barrier(2)
    def run():
        current = adapter(reopened(rig)); barrier.wait(timeout=5)
        return stage(rig, current, row)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(run), pool.submit(run)
        assert a.result(timeout=15) == b.result(timeout=15)
    assert len(list(rig.assets.root.glob('*.bin'))) == 1


def test_hash_scope_actor_and_quota_fail_closed(rig, staging, monkeypatch):
    raw = archive()
    with pytest.raises(ValueError, match='PREVIEW_CHANGED'):
        staging.prepare(rig.nid, rig.scope, rig.actor, raw, archive_sha256='0'*64, request_key='key', guard=lambda: None)
    assert not rig.raw_store.read(rig.nid, rig.scope)['collections']
    row = prepare(rig, staging)
    with pytest.raises(FileNotFoundError):
        staging.stage(rig.nid, rig.scope, 'other', row['id'], raw, guard=lambda: None)
    monkeypatch.setattr(rig.service, 'MAX_ASSETS', 0)
    with pytest.raises(ValueError, match='QUOTA'): stage(rig, staging, row)
    assert not list(rig.assets.root.glob('*.bin'))
    monkeypatch.setattr(rig.service, 'MAX_ASSETS', 1000)
    monkeypatch.setattr(rig.service.storage_admission, 'require', lambda _: (_ for _ in ()).throw(ValueError('LOW_SPACE')))
    with pytest.raises(ValueError, match='LOW_SPACE'): stage(rig, staging, row)
    assert not list(rig.assets.root.glob('*.bin'))


def test_owner_deletion_serializes_real_commit_then_blocks_resume(rig, staging, monkeypatch):
    row = prepare(rig, staging)
    entered, release, deleting, deleted = Event(), Event(), Event(), Event()
    original = rig.assets._write_meta
    def pause(meta):
        entered.set(); assert release.wait(10); original(meta)
    monkeypatch.setattr(rig.assets, '_write_meta', pause)
    def delete():
        deleting.set(); rig.novels.delete(rig.nid); deleted.set()
    # stage() includes a post-commit status read, which may lose to deletion.
    def write():
        try: return stage(rig, staging, row)
        except FileNotFoundError: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(write)
        try:
            assert entered.wait(5)
            deleter = pool.submit(delete)
            assert deleting.wait(5) and not deleted.wait(.2)
        finally: release.set()
        writer.result(timeout=15); deleter.result(timeout=15)
    if rig.backend == 'postgres':
        with rig.raw_store._connect() as connection:
            assert connection.execute('SELECT id FROM novels WHERE slug = %s', (rig.nid,)).fetchone() is None
    else:
        assert not (rig.root/'novels'/rig.nid/'creative_project_v2.json').exists()
    rig.create_project(nid=rig.nid)
    rig.service.store.incarnation(rig.nid)
    with pytest.raises(FileNotFoundError): stage(rig, adapter(reopened(rig)), row)


def test_unrelated_asset_survives_failed_stage_and_origin_conflict(rig, staging, monkeypatch):
    from test_v2_independent_workspace import import_asset
    other = import_asset(rig)
    row = prepare(rig, staging)
    original = rig.assets._write_meta
    monkeypatch.setattr(rig.assets, '_write_meta', lambda _: (_ for _ in ()).throw(OSError('fail')))
    with pytest.raises(OSError): stage(rig, staging, row)
    monkeypatch.setattr(rig.assets, '_write_meta', original)
    assert rig.assets._bin_path(other['id']).exists()
    stage(rig, staging, row)
    aid = row['steps'][0]['asset_id']; meta = rig.assets._load(aid)
    meta[FIELD]['archive_sha256'] = '0'*64; original(meta)
    with pytest.raises(ValueError, match='CHANGED'): stage(rig, staging, row)


def test_multilayer_partial_stage_only_advances_requested_steps(rig, staging):
    from test_comic_ora_import import png
    xml = b'<image w="320" h="320"><stack><layer src="data/blue.png"/><layer src="data/red.png"/></stack></image>'
    raw = archive(xml=xml, additions=[('data/blue.png', png(color='blue'))])
    row = prepare(rig, staging, raw)
    first = stage(rig, staging, row, raw)
    assert first['status'] == 'PARTIALLY_STAGED'
    assert [s['state'] for s in first['steps']] == ['STAGED', 'PENDING']
    assert len(list(rig.assets.root.glob('*.bin'))) == 1
    final = stage(rig, adapter(reopened(rig)), row, raw)
    assert final['status'] == 'STAGED_PRIVATE_REVIEW_PENDING'
    assert [s['asset_id'] for s in final['steps']] == [s['asset_id'] for s in row['steps']]
    assert len(list(rig.assets.root.glob('*.bin'))) == 2


def test_binary_before_metadata_crash_exact_recovery(rig, staging, monkeypatch):
    from app.experimental.comic_ora_import import preview_ora
    row = prepare(rig, staging); aid = row['steps'][0]['asset_id']
    binary = rig.assets._bin_path(aid)
    binary.write_bytes(b'unrelated collision')
    with pytest.raises(ValueError, match='CONTENT_INVALID'): stage(rig, staging, row)
    assert binary.read_bytes() == b'unrelated collision'
    binary.write_bytes(preview_ora(archive()).layers[0].png)
    assert staging.status(rig.nid, rig.scope, rig.actor, row['id'], guard=lambda: None)['steps'][0]['observed_state'] == 'ORPHAN_BINARY_REQUIRES_ARCHIVE_RESUME'
    original = rig.assets._write_meta
    monkeypatch.setattr(rig.assets, '_write_meta', lambda _: (_ for _ in ()).throw(OSError('fail recovery')))
    with pytest.raises(OSError): stage(rig, staging, row)
    assert binary.exists() and not rig.assets._meta_path(aid).exists()
    monkeypatch.setattr(rig.assets, '_write_meta', original)
    assert stage(rig, staging, row)['status'] == 'STAGED_PRIVATE_REVIEW_PENDING'
    assert len(list(rig.assets.root.glob('*.bin'))) == 1


def test_guard_revocation_after_asset_commit_is_recoverable(rig, staging, monkeypatch):
    row = prepare(rig, staging)
    original = rig.assets._write_meta; allowed = [True]
    def write(meta): original(meta); allowed[0] = False
    def guard():
        if not allowed[0]: raise PermissionError('authority revoked')
    monkeypatch.setattr(rig.assets, '_write_meta', write)
    with pytest.raises(PermissionError):
        staging.stage(rig.nid, rig.scope, rig.actor, row['id'], archive(), guard=guard)
    assert len(list(rig.assets.root.glob('*.bin'))) == 1
    monkeypatch.setattr(rig.assets, '_write_meta', original)
    # Explicit new authorization only; denied request never gets a successful receipt.
    allowed[0] = True
    assert stage(rig, adapter(reopened(rig)), row)['status'] == 'STAGED_PRIVATE_REVIEW_PENDING'


def test_no_write_status_and_feature_gate(rig, staging, monkeypatch):
    row = prepare(rig, staging)
    before = rig.raw_store.read(rig.nid, rig.scope)
    monkeypatch.setattr(rig.raw_store, 'transaction', lambda *_: (_ for _ in ()).throw(AssertionError('status writes')))
    staging.status(rig.nid, rig.scope, rig.actor, row['id'], guard=lambda: None)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2')
    with pytest.raises(ValueError, match='FEATURES_REQUIRED'):
        staging.status(rig.nid, rig.scope, rig.actor, row['id'], guard=lambda: None)


def test_feature_revoked_after_asset_commit_cannot_acknowledge_receipt(rig, staging, monkeypatch):
    row = prepare(rig, staging); original = rig.assets._write_meta
    def write(meta):
        original(meta)
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2')
    monkeypatch.setattr(rig.assets, '_write_meta', write)
    with pytest.raises(ValueError, match='FEATURES_REQUIRED'): stage(rig, staging, row)
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'][COLLECTION][row['id']]['steps'][0]['state'] == 'PENDING'
    assert len(list(rig.assets.root.glob('*.bin'))) == 1


def test_orphan_special_file_rejected_without_opening(rig, staging):
    import os
    if not hasattr(os, 'mkfifo'): pytest.skip('FIFO fixture unavailable on this platform')
    row = prepare(rig, staging)
    path = rig.assets._bin_path(row['steps'][0]['asset_id'])
    os.mkfifo(path)
    try:
        with pytest.raises(ValueError, match='CONTENT_INVALID'): stage(rig, staging, row)
        assert path.exists() and not rig.assets._meta_path(row['steps'][0]['asset_id']).exists()
    finally:
        path.unlink()  # exact test-owned FIFO only


def test_planned_orphan_retained_bytes_and_slot_count_across_receipts(rig, staging, monkeypatch):
    from app.experimental.comic_ora_import import preview_ora
    first = prepare(rig, staging, key='first'); second = prepare(rig, staging, key='second')
    content = preview_ora(archive()).layers[0].png
    rig.assets._bin_path(first['steps'][0]['asset_id']).write_bytes(content)
    monkeypatch.setattr(rig.service, 'MAX_ASSETS', 1)
    with pytest.raises(ValueError, match='QUOTA'): stage(rig, staging, second)
    monkeypatch.setattr(rig.service, 'MAX_ASSETS', 1000)
    monkeypatch.setattr(rig.service, 'MAX_PROJECT_BYTES', len(content))
    with pytest.raises(ValueError, match='QUOTA'): stage(rig, staging, second)
    monkeypatch.setattr(rig.service, 'MAX_ASSETS', 1)
    # Existing orphan consumes the quota exactly; recovery must not count twice.
    assert stage(rig, staging, first)['status'] == 'STAGED_PRIVATE_REVIEW_PENDING'
    assert len(list(rig.assets.root.glob('*.bin'))) == 1
    with pytest.raises(ValueError, match='QUOTA'): stage(rig, staging, second)


def test_status_rechecks_features_after_read(rig, staging, monkeypatch):
    row = prepare(rig, staging); stage(rig, staging, row)
    original = staging._verify
    def revoke(*args, **kwargs):
        value = original(*args, **kwargs)
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2')
        return value
    monkeypatch.setattr(staging, '_verify', revoke)
    with pytest.raises(ValueError, match='FEATURES_REQUIRED'):
        staging.status(rig.nid, rig.scope, rig.actor, row['id'], guard=lambda: None)


def test_archive_timestamp_changes_rejected_even_with_identical_layer_pixels(rig, staging):
    import io
    import zipfile
    from app.experimental.comic_ora_import import preview_ora
    raw = archive(); row = prepare(rig, staging, raw)
    changed = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(changed, 'w') as target:
        for info in source.infolist():
            assert info.date_time == (2000, 1, 1, 0, 0, 0)
            content = source.read(info)
            info.date_time = (2000, 1, 1, 0, 0, 2)
            target.writestr(info, content)
    changed = changed.getvalue()
    assert changed != raw
    assert preview_ora(changed).layers[0].png == preview_ora(raw).layers[0].png
    with pytest.raises(ValueError, match='PREVIEW_CHANGED'):
        stage(rig, staging, row, changed)
    assert not list(rig.assets.root.glob('*.bin'))
    assert stage(rig, staging, row, raw)['status'] == 'STAGED_PRIVATE_REVIEW_PENDING'
