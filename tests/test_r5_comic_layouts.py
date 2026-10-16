"""B06 actual raster output, source fences and File/real-PG histories.

All images in this suite are clearly labeled synthetic test assets. No artwork
quality/model claim follows from a deterministic raster test.
"""
import base64
import copy
import hashlib
import io
import json
import os
import zipfile
import pytest
from app.experimental.comic_layouts import ComicLayoutsService, LayoutIn, compose, licensed_font
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig, branch_scope
from test_r4_director import screenplay


def synthetic_png(width=240, height=160):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (width, height), 'white'); draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, width - 8, height - 8), outline='black', width=3)
    draw.line((10, height - 10, width // 2, 16, width - 10, height - 10), fill='blue', width=3)
    draw.text((12, height // 2), 'SYNTHETIC TEST ASSET', fill='black')
    stream = io.BytesIO(); image.save(stream, format='PNG'); return stream.getvalue()


@pytest.fixture
def comic(rig):
    return ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)


@pytest.fixture
def image_asset(rig, comic):
    asset = rig.assets.create(rig.nid, 'SYNTHETIC-TEST-ASSET.png', base64.b64encode(synthetic_png()).decode(), 'image/png')
    approved = comic.approve_image(rig.nid, rig.scope, rig.actor, asset['id'], asset['version'])
    return rig.assets.get(approved['id'])


def layout(rig, asset=None):
    source = screenplay(rig)
    return {'title': 'Synthetic test layout', 'screenplay_id': source['id'], 'expected_screenplay_version': source['edit_version'],
            'width': 800, 'height': 1120, 'safe_area': 24, 'segment_height': 560,
            'panels': [{'id': 'panel', 'shot_id': source['shots'][0]['id'], 'order': 1, 'x': 24, 'y': 24, 'width': 752, 'height': 1000,
                        'asset_id': asset['id'] if asset else None, 'expected_asset_version': asset['version'] if asset else None}]}


def save(comic, rig, body): return comic.save(rig.nid, rig.scope, rig.actor, body)
def preflight(comic, rig, row): return comic.preflight(rig.nid, rig.scope, rig.actor, row['id'], row['version'])
def approve(comic, rig, row, report=None):
    report = report or preflight(comic, rig, row)
    return comic.approve(rig.nid, rig.scope, rig.actor, row['id'], row['version'], report['review_digest'], True)


def test_real_png_segment_export_matches_preview_exactly_and_restarts(rig, comic, image_asset):
    row = save(comic, rig, layout(rig, image_asset)); report = preflight(comic, rig, row)
    assert report['can_render'] and row['status'] == 'DRAFT'
    with pytest.raises(ValueError, match='APPROVAL'): comic.export(rig.nid, rig.scope, rig.actor, row['id'], 1)
    approved = approve(comic, rig, row)
    reopened = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    result = reopened.export(rig.nid, rig.scope, rig.actor, row['id'], approved['version'])
    assert result == reopened.export(rig.nid, rig.scope, rig.actor, row['id'], approved['version'])
    with zipfile.ZipFile(io.BytesIO(result)) as archive:
        manifest = json.loads(archive.read('manifest.json')); assert len(manifest['segments']) == 2
        for segment in manifest['segments']:
            data = archive.read(segment['filename']); assert data == reopened.preview(rig.nid, rig.scope, rig.actor, row['id'], approved['version'], segment['index'])
            assert hashlib.sha256(data).hexdigest() == segment['sha256']
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image: assert image.size == (800, 560)
        assert set(archive.namelist()) == {'segment-001.png', 'segment-002.png', 'manifest.json'}
    assert rig.screenplays.list(rig.nid)[0]['edit_version'] == row['document']['expected_screenplay_version']
    assert len(rig.assets.list(rig.nid)) == 1


def test_missing_image_is_visible_blocker_and_cannot_export(rig, comic):
    row = save(comic, rig, layout(rig)); report = preflight(comic, rig, row)
    assert {'code': 'COMIC_MISSING_APPROVED_IMAGE', 'target': 'panel', 'severity': 'BLOCKER'} in report['issues']
    with pytest.raises(ValueError, match='BLOCKED'): approve(comic, rig, row)
    with pytest.raises(ValueError, match='BLOCKED'): comic.preview(rig.nid, rig.scope, rig.actor, row['id'], 1, 0)


def test_edit_revokes_approval_restore_creates_draft_and_keeps_history(rig, comic, image_asset):
    row = save(comic, rig, layout(rig, image_asset)); approved = approve(comic, rig, row)
    changed = copy.deepcopy(row['document']); changed['panels'][0]['x'] = 25
    edited = comic.save(rig.nid, rig.scope, rig.actor, changed, rid=row['id'], expected_version=approved['version'])
    assert edited['status'] == 'DRAFT' and edited['history_versions'] == [1, 2]
    restored = comic.restore(rig.nid, rig.scope, rig.actor, row['id'], edited['version'], 1)
    assert restored['version'] == 4 and restored['document'] == row['document'] and restored['status'] == 'DRAFT'
    with pytest.raises(CapabilityVersionConflict): comic.restore(rig.nid, rig.scope, rig.actor, row['id'], 3, 1)


def test_actor_branch_and_source_versions_fail_closed(rig, comic, image_asset):
    row = save(comic, rig, layout(rig, image_asset)); approved = approve(comic, rig, row)
    assert comic.records(rig.nid, rig.scope, 'other')['items'] == []
    assert comic.records(rig.nid, branch_scope(rig), rig.actor)['items'] == []
    with pytest.raises(FileNotFoundError): comic.preflight(rig.nid, rig.scope, 'other', row['id'], 2)
    rig.chapters.save(rig.chapter['id'], {'version': rig.chapter['version'], 'content': 'Changed'})
    view = comic.records(rig.nid, rig.scope, rig.actor)['items'][0]
    assert view['stale'] and 'document' not in view
    with pytest.raises(StaleSourceError): comic.export(rig.nid, rig.scope, rig.actor, approved['id'], approved['version'])


@pytest.mark.parametrize('mutation', ['asset', 'character', 'privacy'])
def test_asset_character_privacy_changes_invalidate_outputs(rig, comic, image_asset, mutation):
    from app.source_privacy import review_source_privacy, content_digest
    body = layout(rig, image_asset); body['panels'][0]['character_ids'] = ['alice']; row = save(comic, rig, body)
    if mutation == 'asset': rig.assets.update_metadata(image_asset['id'], {'parameters': {'changed': True}}, expected_version=image_asset['version'])
    elif mutation == 'character': rig.novels.upsert_character(rig.nid, 'alice', {'name': 'New Alice'})
    else: review_source_privacy(rig.chapter, None, rig.actor, 'CLOUD_ALLOWED', rig.chapter['version'], content_digest(rig.chapter), rig.root)
    assert comic.records(rig.nid, rig.scope, rig.actor)['items'][0]['stale']
    with pytest.raises((ValueError, FileNotFoundError)): preflight(comic, rig, row)


def test_manual_review_versions_and_generated_asset_boundary(rig, comic):
    row = rig.assets.create(rig.nid, 'SYNTHETIC-TEST-ASSET.png', base64.b64encode(synthetic_png()).decode(), 'image/png')
    body = layout(rig, row)
    with pytest.raises(ValueError, match='REVIEW_REQUIRED'): save(comic, rig, body)
    with pytest.raises(CapabilityVersionConflict): comic.approve_image(rig.nid, rig.scope, rig.actor, row['id'], 999)
    rig.assets.update_metadata(row['id'], {'provider_id': 'test-provider'}, expected_version=1)
    with pytest.raises(ValueError, match='ORIGINAL_GENERATION_REVIEW'): comic.approve_image(rig.nid, rig.scope, rig.actor, row['id'], 2)
    assert comic.catalog(rig.nid, rig.scope, rig.actor)['assets'][0]['manual_review_available'] is False


@pytest.mark.parametrize('kind,code', [('outside', 'COMIC_PANEL_OUTSIDE_SAFE_AREA'), ('order', 'COMIC_READING_ORDER_CONFLICT'), ('overlap', 'COMIC_PANEL_OVERLAP'), ('bubble', 'COMIC_BUBBLE_OUTSIDE_PANEL_SAFE_AREA')])
def test_geometry_preflight_is_visible(rig, comic, image_asset, kind, code):
    body = layout(rig, image_asset)
    if kind == 'outside': body['panels'][0]['x'] = 0
    if kind == 'order': body['panels'][0]['order'] = 2
    if kind == 'overlap': body['panels'].append({**body['panels'][0], 'id': 'second', 'order': 2})
    if kind == 'bubble': body['panels'][0]['bubbles'] = [{'id': 'b', 'text': 'Test', 'x': 0, 'y': 0, 'width': 200, 'height': 100}]
    row = save(comic, rig, body); report = preflight(comic, rig, row)
    assert code in [i['code'] for i in report['issues']] and not report['can_render']


def test_crop_warning_requires_digest_bound_acknowledgement(rig, comic, image_asset):
    body = layout(rig, image_asset); body['panels'][0]['fit'] = 'COVER'; row = save(comic, rig, body); report = preflight(comic, rig, row)
    assert report['can_render'] and 'COMIC_CENTER_CROP' in [i['code'] for i in report['issues']]
    with pytest.raises(ValueError, match='WARNINGS'): comic.approve(rig.nid, rig.scope, rig.actor, row['id'], 1, report['review_digest'], False)
    with pytest.raises(StaleSourceError): comic.approve(rig.nid, rig.scope, rig.actor, row['id'], 1, '0' * 64, True)
    assert approve(comic, rig, row)['status'] == 'APPROVED'


def test_revocation_during_render_does_not_return_bytes(rig, comic, image_asset):
    row = approve(comic, rig, save(comic, rig, layout(rig, image_asset)))
    def revoked(): raise PermissionError('revoked')
    with pytest.raises(PermissionError): comic.export(rig.nid, rig.scope, rig.actor, row['id'], row['version'], revoked)
    def changed(): rig.assets.update_metadata(image_asset['id'], {'parameters': {'changed': True}})
    with pytest.raises(StaleSourceError): comic.preview(rig.nid, rig.scope, rig.actor, row['id'], row['version'], 0, changed)


def test_font_unavailable_is_explicit_blocker_never_tofu(rig, comic, image_asset, monkeypatch):
    import app.experimental.comic_layouts as module
    def unavailable(): raise ValueError('COMIC_PINNED_OFL_CJK_FONT_UNAVAILABLE')
    monkeypatch.setattr(module, 'licensed_font', unavailable)
    body = layout(rig, image_asset); body['panels'][0]['bubbles'] = [{'id': 'dialogue', 'text': '中文对白', 'x': 40, 'y': 40, 'width': 680, 'height': 120}]
    row = save(comic, rig, body); report = preflight(comic, rig, row)
    assert not report['can_render'] and any(i['code'] == 'COMIC_PINNED_OFL_CJK_FONT_UNAVAILABLE' for i in report['issues'])


def test_real_pinned_cjk_font_readable_text_and_overflow(rig, comic, image_asset, monkeypatch):
    path = os.getenv('R2_TEST_FONT_FILE')
    if not path: pytest.skip('NOT_RUN: pinned OFL test font not supplied; hosted gate prepares it')
    monkeypatch.setenv('AI_NOVEL_STUDIO_PDF_FONT', path)
    assert licensed_font()[2].issuperset(map(ord, '中文对白'))
    from app.experimental.comic_layouts import _text_layout
    font_data, _, coverage = licensed_font()
    _, lines, _ = _text_layout({'text': '中文对白：这是合成测试素材，不代表最终美术。', 'font_size': 32, 'width': 720, 'height': 160}, font_data, coverage)
    assert ''.join(lines) == '中文对白：这是合成测试素材，不代表最终美术。'
    assert all(not line.startswith(('，', '。')) for line in lines)
    body = layout(rig, image_asset); body['panels'][0]['bubbles'] = [{'id': 'dialogue', 'text': '中文对白：这里是合成测试素材。', 'font_size': 32, 'x': 40, 'y': 40, 'width': 680, 'height': 160}]
    row = save(comic, rig, body); assert preflight(comic, rig, row)['can_render']; approved = approve(comic, rig, row)
    with zipfile.ZipFile(io.BytesIO(comic.export(rig.nid, rig.scope, rig.actor, row['id'], approved['version']))) as archive:
        assert b'SIL OPEN FONT LICENSE' in archive.read('OFL.txt')
        from PIL import Image
        image = Image.open(io.BytesIO(archive.read('segment-001.png')))
        assert len(set(image.crop((52, 52, 670, 96)).get_flattened_data())) > 20  # actual anti-aliased glyph pixels
    body['panels'][0]['bubbles'][0]['text'] = '中文' * 300
    overflow = save(comic, rig, body)
    assert 'COMIC_TEXT_OVERFLOW' in [i['code'] for i in preflight(comic, rig, overflow)['issues']]


def test_bounds_and_untrusted_media_rejected(rig, comic):
    with pytest.raises(ValueError): LayoutIn.model_validate({**layout(rig), 'width': 1600, 'height': 12000})
    bad = rig.assets.create(rig.nid, 'SYNTHETIC-bad.png', base64.b64encode(b'<svg onload="evil()"/>').decode(), 'image/png')
    with pytest.raises(ValueError, match='INVALID_RASTER'): comic.approve_image(rig.nid, rig.scope, rig.actor, bad['id'], 1)
    assert comic.catalog(rig.nid, rig.scope, rig.actor)['assets'] == []


def test_spatial_reading_order_and_extreme_resampling_are_blocked(rig, comic, image_asset):
    body = layout(rig, image_asset)
    body['panels'][0].update(height=300, order=2)
    body['panels'].append({**body['panels'][0], 'id': 'second', 'order': 1, 'y': 400})
    row = save(comic, rig, body)
    assert 'COMIC_SPATIAL_ORDER_CONFLICT' in [i['code'] for i in preflight(comic, rig, row)['issues']]
    # Tiny encoded input cannot trigger an unbounded cover-resize allocation.
    from PIL import Image
    stream = io.BytesIO(); Image.new('RGB', (1, 20000)).save(stream, format='PNG')
    document = LayoutIn.model_validate(layout(rig, image_asset)).model_dump(); document['panels'][0]['fit'] = 'COVER'
    report, output = compose(document, {image_asset['id']: stream.getvalue()}, render=True)
    assert not output and 'COMIC_IMAGE_RESAMPLE_LIMIT' in [i['code'] for i in report['issues']]


def test_font_license_hash_rejects_unverified_and_unsupported_font_names(rig, monkeypatch, tmp_path):
    from pathlib import Path
    from app.experimental.comic_layouts import font_status
    monkeypatch.setattr('app.pdf_export._font_candidates', lambda: [tmp_path / 'NotoSansSC-Regular.ttf'])
    (tmp_path / 'NotoSansSC-Variable.ttf').write_bytes(b'unverified font')
    (tmp_path / 'OFL.txt').write_bytes(b'not the pinned license')
    assert font_status()['available'] is False
    with pytest.raises(ValueError): LayoutIn.model_validate({**layout(rig), 'font_family': 'Unlicensed System Font'})


def test_stale_source_during_initial_save_cannot_persist(rig, comic, image_asset):
    body = layout(rig, image_asset)
    def changed(): rig.chapters.save(rig.chapter['id'], {'version': rig.chapter['version'], 'content': 'Changed during save'})
    with pytest.raises(StaleSourceError): comic.save(rig.nid, rig.scope, rig.actor, body, changed)
    assert comic.records(rig.nid, rig.scope, rig.actor)['items'] == []
