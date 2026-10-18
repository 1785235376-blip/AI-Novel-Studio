"""Original Asset review and atomic receipt/page attachment: File/real PG variants."""
import copy
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import io
import pytest
from PIL import Image
from test_v2_independent_workspace import rig, reopened
from test_comic_ora_staging import staging, prepare, stage, adapter
from test_comic_ora_import import archive
from app.services.v1_capability_service import CapabilityVersionConflict
from app.experimental.comic_ora_staging import COLLECTION


def reviewed(rig, staging, row, raw=None):
    raw = raw or archive()
    manifest = staging.review_manifest(rig.nid, rig.scope, rig.actor, row['id'], raw, guard=lambda: None)
    return staging.review(rig.nid, rig.scope, rig.actor, row['id'], raw,
        manifest_digest=manifest['manifest_digest'], license_note='Fixture author declaration; origin remains unverified',
        acknowledge_raster_text=True, guard=lambda: None)


def page(rig, staging):
    return staging.comic.save(rig.nid, rig.scope, rig.actor,
        {'title': 'Existing page', 'source_mode': 'INDEPENDENT', 'width': 320, 'height': 320, 'panels': []})


def attach(rig, staging, row, target):
    return staging.attach(rig.nid, rig.scope, rig.actor, row['id'], target['id'],
        expected_page_version=target['version'], review_digest=row['review_digest'], guard=lambda: None)


def test_review_attach_render_reedit_exact_replay_and_legacy_reads(rig, staging):
    row = prepare(rig, staging); stage(rig, staging, row); target = page(rig, staging)
    review = reviewed(rig, staging, row)
    assert review['status'] == 'REVIEWED_READY_FOR_ATTACHMENT'
    attached = attach(rig, staging, review, target)
    document = attached['page']['document']; item = document['layer_stack']['items'][0]
    assert item['kind'] == 'RASTER' and document['panels'] == []
    assert item['opacity_percent'] == 50 and item['pin']['version'] == 2
    assert attach(rig, adapter(reopened(rig)), review, target) == attached
    assert not attached['page']['stale'] and attached['page']['status'] == 'DRAFT'
    report = staging.comic.preflight(rig.nid, rig.scope, rig.actor, target['id'], 2)
    assert report['can_render']
    png = staging.comic.preview(rig.nid, rig.scope, rig.actor, target['id'], 2, 0)
    # Preview service returns original image bytes, not a synthetic canvas.
    if isinstance(png, tuple): png = png[0]
    assert Image.open(io.BytesIO(png)).getpixel((10, 20))[:3] == (255, 127, 127)
    changed = copy.deepcopy(document); changed['layer_stack']['items'][0]['visible'] = False
    updated = staging.comic.save(rig.nid, rig.scope, rig.actor, changed, rid=target['id'], expected_version=2)
    assert updated['document']['layer_stack']['items'][0]['visible'] is False
    with pytest.raises(ValueError, match='REPLAY_CHANGED'): attach(rig, staging, review, target)
    aid = item['target_id']
    with pytest.raises(FileNotFoundError): staging.comic._asset(rig.nid, rig.scope, rig.actor, aid)
    assert not staging.comic._manual(rig.assets._load(aid))


@pytest.mark.parametrize('after_commit', [False, True])
def test_review_asset_ack_failure_is_separate_from_receipt(rig, staging, monkeypatch, after_commit):
    row = prepare(rig, staging); stage(rig, staging, row)
    original = rig.assets._write_meta
    def fail(meta):
        if after_commit: original(meta)
        raise OSError('promotion acknowledgement lost')
    monkeypatch.setattr(rig.assets, '_write_meta', fail)
    with pytest.raises(OSError): reviewed(rig, staging, row)
    monkeypatch.setattr(rig.assets, '_write_meta', original)
    meta = rig.assets._load(row['steps'][0]['asset_id'])
    assert meta['version'] == (2 if after_commit else 1)
    result = reviewed(rig, adapter(reopened(rig)), row)
    assert result['status'] == 'REVIEWED_READY_FOR_ATTACHMENT'
    assert rig.assets._load(meta['id'])['version'] == 2


@pytest.mark.parametrize('after_commit', [False, True])
def test_attachment_atomic_scope_rollback_or_lost_ack(rig, staging, monkeypatch, after_commit):
    row = prepare(rig, staging); stage(rig, staging, row); review = reviewed(rig, staging, row); target = page(rig, staging)
    original = rig.raw_store.transaction
    @contextmanager
    def fail(*args, **kwargs):
        with original(*args, **kwargs) as state:
            yield state
            if not after_commit: raise OSError('scope rollback')
        if after_commit: raise OSError('lost attachment acknowledgement')
    monkeypatch.setattr(rig.raw_store, 'transaction', fail)
    with pytest.raises(OSError): attach(rig, staging, review, target)
    monkeypatch.setattr(rig.raw_store, 'transaction', original)
    state = rig.raw_store.read(rig.nid, rig.scope)
    assert ('attachment' in state['collections'][COLLECTION][row['id']]) is after_commit
    assert state['collections'][staging.comic.RECORDS][target['id']]['version'] == (2 if after_commit else 1)
    assert rig.assets._load(row['steps'][0]['asset_id'])['version'] == 2
    result = attach(rig, adapter(reopened(rig)), review, target)
    assert result['page']['version'] == 2
    assert len(result['page']['document']['layer_stack']['items']) == 1


def test_concurrent_attachment_reuses_one_page_revision(rig, staging):
    row = prepare(rig, staging); stage(rig, staging, row); review = reviewed(rig, staging, row); target = page(rig, staging)
    barrier = Barrier(2)
    def run():
        current = adapter(reopened(rig)); barrier.wait(timeout=5)
        return attach(rig, current, review, target)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(run), pool.submit(run)
        assert a.result(timeout=20) == b.result(timeout=20)


def test_review_hash_ack_generic_seal_and_page_cas_reject(rig, staging):
    row = prepare(rig, staging); stage(rig, staging, row)
    manifest = staging.review_manifest(rig.nid, rig.scope, rig.actor, row['id'], archive(), guard=lambda: None)
    for digest, ack, message in [('0'*64, True, 'MANIFEST_CHANGED'), (manifest['manifest_digest'], False, 'LOSS_ACK')]:
        with pytest.raises(ValueError, match=message):
            staging.review(rig.nid, rig.scope, rig.actor, row['id'], archive(), manifest_digest=digest,
                license_note='Fixture', acknowledge_raster_text=ack, guard=lambda: None)
    review = reviewed(rig, staging, row); target = page(rig, staging)
    stale = {**target, 'version': target['version'] + 1}
    with pytest.raises(CapabilityVersionConflict): attach(rig, staging, review, stale)
    with rig.service._asset_scope(rig.nid, rig.scope):
        meta = rig.assets.get(row['steps'][0]['asset_id'], actor_id=rig.actor)
        with pytest.raises(ValueError, match='SEAL_REQUIRED'):
            rig.assets.promote_owned(meta['id'], actor_id=rig.actor, branch_id=None, expected_version=1,
                provenance=meta['_comic_ora_review'], guard=lambda: None, _comic_ora_review=meta['_comic_ora_review'])


def test_native_text_layers_and_legacy_unbound_image_survive_attach_copy(rig, staging):
    import base64
    from test_comic_ora_import import png
    from test_comic_layers import layered
    legacy = rig.assets.create(rig.nid, 'legacy.png', base64.b64encode(png()).decode(), 'image/png', 'image')
    staging.comic.approve_image(rig.nid, rig.scope, rig.actor, legacy['id'], legacy['version'])
    legacy = rig.assets.get(legacy['id'])
    body = {'title': 'Native text', 'source_mode': 'INDEPENDENT', 'width': 320, 'height': 320, 'panels': [
        {'id': 'native_panel', 'order': 1, 'x': 24, 'y': 24, 'width': 272, 'height': 272,
         'asset_id': legacy['id'], 'expected_asset_version': legacy['version'], 'bubbles': [
             {'id': 'native_bubble', 'x': 40, 'y': 40, 'width': 220, 'height': 80, 'text': 'Editable native dialogue'}]}]}
    body = layered(body); body['layer_stack']['items'][0]['opacity_percent'] = 73
    body['layer_stack']['items'][2]['visible'] = False
    body['layer_stack']['items'][2:4] = reversed(body['layer_stack']['items'][2:4])
    target = staging.comic.save(rig.nid, rig.scope, rig.actor, body)
    native = copy.deepcopy(target['document'])
    row = prepare(rig, staging); stage(rig, staging, row); review = reviewed(rig, staging, row)
    result = attach(rig, staging, review, target)
    after = result['page']['document']
    assert after['panels'] == native['panels']
    assert after['layer_stack']['items'][1:] == native['layer_stack']['items']
    book = staging.comic.save_book(rig.nid, rig.scope, rig.actor,
        {'title': 'Book', 'chapters': [{'id': 'chapter', 'title': 'Chapter', 'pages': [target['id']]}],
         'expected_page_versions': {target['id']: 2}})
    copied = staging.comic.book_page(rig.nid, rig.scope, rig.actor, book['id'],
        {'expected_version': book['version'], 'chapter_id': 'chapter', 'source_layout_id': target['id'], 'expected_source_version': 2})['page']['document']
    assert copied['panels'][0]['id'] != native['panels'][0]['id']
    assert copied['panels'][0]['bubbles'][0]['text'] == 'Editable native dialogue'
    assert copied['layer_stack']['items'][0]['target_id'] == after['layer_stack']['items'][0]['target_id']
    assert copied['layer_stack']['items'][0]['pin'] == after['layer_stack']['items'][0]['pin']
    assert {i['id'] for i in copied['layer_stack']['items']}.isdisjoint(i['id'] for i in after['layer_stack']['items'])
    assert [i['opacity_percent'] for i in copied['layer_stack']['items']] == [i['opacity_percent'] for i in after['layer_stack']['items']]


def test_reviewed_raster_export_parse_and_asset_revocation(rig, staging):
    from app.experimental.comic_ora_import import preview_ora
    row = prepare(rig, staging); stage(rig, staging, row); review = reviewed(rig, staging, row); target = page(rig, staging)
    attach(rig, staging, review, target)
    report = staging.comic.preflight(rig.nid, rig.scope, rig.actor, target['id'], 2)
    approved = staging.comic.approve(rig.nid, rig.scope, rig.actor, target['id'], 2, report['review_digest'], True)
    exported = staging.comic.export_ora(rig.nid, rig.scope, rig.actor, target['id'], approved['version'])
    parsed = preview_ora(exported)
    assert parsed.report['merged_preview_matches']
    assert any(layer.opacity_percent == 50 for layer in parsed.layers)
    with rig.service._asset_scope(rig.nid, rig.scope):
        rig.assets.delete(row['steps'][0]['asset_id'], actor_id=rig.actor)
    assert staging.comic.records(rig.nid, rig.scope, rig.actor)['items'][0]['stale']
    with pytest.raises((FileNotFoundError, ValueError)):
        staging.comic.export_ora(rig.nid, rig.scope, rig.actor, target['id'], approved['version'])


def test_concurrent_review_promotes_once(rig, staging):
    row = prepare(rig, staging); stage(rig, staging, row)
    barrier = Barrier(2)
    def run():
        current = adapter(reopened(rig)); barrier.wait(timeout=5)
        return reviewed(rig, current, row)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(run), pool.submit(run)
        assert a.result(timeout=20) == b.result(timeout=20)
    assert rig.assets._load(row['steps'][0]['asset_id'])['version'] == 2


def test_attach_authority_revocation_rolls_back_page_only(rig, staging, monkeypatch):
    row = prepare(rig, staging); stage(rig, staging, row); review = reviewed(rig, staging, row); target = page(rig, staging)
    original = staging.comic._payload; allowed = [True]
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs); allowed[0] = False; return result
    def guard():
        if not allowed[0]: raise PermissionError('authority revoked')
    monkeypatch.setattr(staging.comic, '_payload', revoked)
    with pytest.raises(PermissionError):
        staging.attach(rig.nid, rig.scope, rig.actor, row['id'], target['id'], expected_page_version=1,
            review_digest=review['review_digest'], guard=guard)
    state = rig.raw_store.read(rig.nid, rig.scope)
    assert state['collections'][staging.comic.RECORDS][target['id']]['version'] == 1
    assert 'attachment' not in state['collections'][COLLECTION][row['id']]
    assert rig.assets._load(row['steps'][0]['asset_id'])['version'] == 2


@pytest.mark.parametrize('phase', ['review', 'attach'])
def test_owner_deletion_serializes_review_or_attachment(rig, staging, monkeypatch, phase):
    from threading import Event
    row = prepare(rig, staging); stage(rig, staging, row); target = page(rig, staging)
    review = reviewed(rig, staging, row) if phase == 'attach' else None
    entered, release, deleting, deleted = Event(), Event(), Event(), Event()
    if phase == 'review':
        original = rig.assets._write_meta
        def pause(*args, **kwargs):
            entered.set(); assert release.wait(10); return original(*args, **kwargs)
        monkeypatch.setattr(rig.assets, '_write_meta', pause)
    else:
        original = staging.comic._payload
        def pause(*args, **kwargs):
            entered.set(); assert release.wait(10); return original(*args, **kwargs)
        monkeypatch.setattr(staging.comic, '_payload', pause)
    def write():
        try:
            return reviewed(rig, staging, row) if phase == 'review' else attach(rig, staging, review, target)
        except FileNotFoundError: return None  # deletion can win the post-review status read
    def delete():
        deleting.set(); rig.novels.delete(rig.nid); deleted.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(write)
        try:
            assert entered.wait(5)
            deleter = pool.submit(delete)
            assert deleting.wait(5) and not deleted.wait(.2)
        finally: release.set()
        writer.result(timeout=20); deleter.result(timeout=20)
    if rig.backend == 'postgres':
        with rig.raw_store._connect() as connection:
            assert connection.execute('SELECT id FROM novels WHERE slug = %s', (rig.nid,)).fetchone() is None
    else:
        assert not (rig.root/'novels'/rig.nid/'creative_project_v2.json').exists()
    rig.create_project(nid=rig.nid); rig.service.store.incarnation(rig.nid)
    with pytest.raises(FileNotFoundError):
        staging.review_manifest(rig.nid, rig.scope, rig.actor, row['id'], archive(), guard=lambda: None)


def test_attachment_decode_budget_rollback_preserves_reviewed_candidates(rig, staging, monkeypatch):
    row = prepare(rig, staging); stage(rig, staging, row); review = reviewed(rig, staging, row); target = page(rig, staging)
    monkeypatch.setattr('app.experimental.comic_layers.MAX_ORA_DECODE_PIXELS', 10)
    with pytest.raises(ValueError, match='DECODE_WORK_LIMIT'): attach(rig, staging, review, target)
    state = rig.raw_store.read(rig.nid, rig.scope)
    assert state['collections'][staging.comic.RECORDS][target['id']]['version'] == 1
    assert 'attachment' not in state['collections'][COLLECTION][row['id']]
    assert rig.assets._load(row['steps'][0]['asset_id'])['version'] == 2
