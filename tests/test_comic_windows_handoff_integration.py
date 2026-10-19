"""Combined native Windows/File service checks; no HTTP/UI or inference run."""
import base64
import copy
import hashlib
import io
import os

from PIL import Image
import pytest

from app.services import asset_bounded_file_windows as native_reader
from app.services.comic_page_origin import record
from test_v2_independent_workspace import rig, png_bytes
from test_comic_timeline_handoff import handoff, page, request, preview
from test_comic_timeline_handoff_recovery import body, confirm, status, resume, restart, timelines

pytestmark = [pytest.mark.skipif(os.name != 'nt', reason='Native Windows integration required'),
              pytest.mark.file_backend_only, pytest.mark.parametrize('rig', ['file'], indirect=True)]


def external_page(rig, handoff):
    raw = png_bytes(b'\x11\x22\x33')
    asset = rig.assets.create(rig.nid, 'SYNTHETIC-external-page.png',
        base64.b64encode(raw).decode(), 'image/png')
    reviewed = handoff.comic.approve_image(rig.nid, rig.scope, rig.actor, asset['id'], asset['version'])
    saved = page(rig, handoff)
    document = copy.deepcopy(saved['document'])
    document['panels'][0].update(artwork_mode='IMAGE', asset_id=asset['id'],
                                 expected_asset_version=reviewed['version'])
    saved = handoff.comic.save(rig.nid, rig.scope, rig.actor, document,
        rid=saved['id'], expected_version=saved['version'])
    report = handoff.comic.preflight(rig.nid, rig.scope, rig.actor, saved['id'], saved['version'])
    saved = handoff.comic.approve(rig.nid, rig.scope, rig.actor, saved['id'], saved['version'],
        report['review_digest'], True)
    saved['review_digest'] = report['review_digest']
    return saved


def orphan_png(rig, handoff, monkeypatch):
    value = body(rig, handoff, [page(rig, handoff)], key='native-orphan')
    def stopped(*_args, **_kwargs):
        raise OSError('synthetic crash before Asset metadata commit')
    with monkeypatch.context() as patch:
        patch.setattr(rig.assets, 'create', stopped)
        with pytest.raises(OSError, match='^synthetic crash before Asset metadata commit$'):
            confirm(rig, handoff, value)
    observed = status(rig, handoff, 'native-orphan')
    aid = observed['steps'][0]['asset_id']
    _, images = preview(rig, handoff, value['request'])
    assert not rig.assets._meta_path(aid).exists() and not rig.assets._bin_path(aid).exists()
    rig.assets._bin_path(aid).write_bytes(images[0])
    assert status(rig, handoff, 'native-orphan')['steps'][0]['observed_state'] == 'UNINDEXED_BYTES_AWAITING_EXPLICIT_RESUME'
    assert not rig.assets._meta_path(aid).exists() and not timelines(rig)
    return aid, images[0]


def test_external_artwork_full_page_then_save_and_real_reopen(rig, handoff, monkeypatch):
    saved = external_page(rig, handoff)
    selected = request([saved], [6500])
    before = copy.deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    assets_before = {p.name: p.read_bytes() for p in rig.assets.root.iterdir() if p.is_file()}
    report, images = preview(rig, handoff, selected)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    assert {p.name: p.read_bytes() for p in rig.assets.root.iterdir() if p.is_file()} == assets_before
    with Image.open(io.BytesIO(images[0])) as image:
        image.load(); assert image.size == (320, 640)
        assert image.getpixel((144, 320)) == (17, 34, 51)
        assert image.getpixel((24, 602)) == (0, 0, 0)
    value = {'request_id': 'external-page', 'request': selected,
        'reviewed_preview_digest': report['preview_digest'], 'acknowledge_losses': True}
    created = confirm(rig, handoff, value)
    assert created['status'] == 'DRAFT_CREATED' and not created['approval_inherited'] and not created['video_rendered']
    timeline = created['timeline']
    edited = handoff.production.timeline_save(rig.nid, rig.scope, rig.actor, timeline['id'],
        {'expected_version': timeline['version'], 'title': 'Saved external-page draft',
         'timeline': timeline['timeline']}, lambda: None)
    fresh = restart(rig, monkeypatch)
    observed = status(rig, fresh, 'external-page')
    assert observed['timeline'] == edited and edited['version'] == 2
    assert observed['timeline_state'] == 'MODIFIED_AFTER_CREATION'
    assert observed['timeline_snapshot'] == created['timeline_snapshot']
    aid = created['steps'][0]['asset_id']
    assert fresh.workspace.assets is not rig.assets
    with fresh.workspace._asset_scope(rig.nid, rig.scope):
        meta = fresh.workspace.assets.get(aid)
        assert record(meta)['source']['id'] == saved['id']
        actual = fresh.workspace.assets.content(aid, max_bytes=len(images[0]))
    assert actual == images[0] and hashlib.sha256(actual).hexdigest() == report['pages'][0]['png_sha256']
    assert len(timelines(rig)) == 1


def test_unindexed_png_requires_explicit_resume_then_reopens_exact_bytes(rig, handoff, monkeypatch):
    aid, raw = orphan_png(rig, handoff, monkeypatch)
    fresh = restart(rig, monkeypatch)
    assert not fresh.workspace.assets._meta_path(aid).exists()
    assert status(rig, fresh, 'native-orphan')['steps'][0]['observed_state'] == 'UNINDEXED_BYTES_AWAITING_EXPLICIT_RESUME'
    assert not fresh.workspace.assets._meta_path(aid).exists() and not timelines(rig)
    result = resume(rig, fresh, 'native-orphan')
    assert result['status'] == 'DRAFT_CREATED' and result['steps'][0]['asset_id'] == aid
    timeline = result['timeline']
    edited = fresh.production.timeline_save(rig.nid, rig.scope, rig.actor, timeline['id'],
        {'expected_version': timeline['version'], 'title': 'Saved recovered-PNG draft',
         'timeline': timeline['timeline']}, lambda: None)
    again = restart(rig, monkeypatch)
    observed = status(rig, again, 'native-orphan')
    assert observed['timeline_snapshot'] == result['timeline_snapshot']
    assert observed['timeline'] == edited and edited['version'] == 2
    assert observed['timeline_state'] == 'MODIFIED_AFTER_CREATION'
    with again.workspace._asset_scope(rig.nid, rig.scope):
        meta = again.workspace.assets.get(aid)
        assert record(meta)['asset_id'] == aid and meta['version'] == 1
        assert again.workspace.assets.content(aid, max_bytes=len(raw)) == raw
    assert len(list(rig.assets.root.glob('*.bin'))) == len(timelines(rig)) == 1


def test_missing_native_capability_refuses_full_page_without_effects(rig, handoff, monkeypatch):
    selected = request([external_page(rig, handoff)])
    before = copy.deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    assets_before = {p.name: p.read_bytes() for p in rig.assets.root.iterdir() if p.is_file()}
    monkeypatch.setattr(native_reader, 'windows_bounded_read_supported', lambda: False)
    with pytest.raises(ValueError, match='^ASSET_BOUNDED_READ_UNSUPPORTED$'):
        preview(rig, handoff, selected)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    assert {p.name: p.read_bytes() for p in rig.assets.root.iterdir() if p.is_file()} == assets_before
    assert not timelines(rig)


def test_missing_native_capability_never_adopts_orphan_png(rig, handoff, monkeypatch):
    aid, raw = orphan_png(rig, handoff, monkeypatch)
    before = copy.deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    monkeypatch.setattr(native_reader, 'windows_bounded_read_supported', lambda: False)
    with pytest.raises(ValueError, match='^ASSET_BOUNDED_READ_UNSUPPORTED$'):
        resume(rig, handoff, 'native-orphan')
    assert rig.assets._bin_path(aid).read_bytes() == raw
    assert not rig.assets._meta_path(aid).exists() and not timelines(rig)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
