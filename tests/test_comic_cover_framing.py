"""Bounded COVER alignment over original owner; all artwork is synthetic."""
import base64
import copy
import hashlib
import io
import json
import zipfile

import pytest
from pydantic import ValidationError
from app.experimental.comic_layouts import ComicLayoutsService, LayoutEdit, LayoutIn, compose
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from support_reconciliation_test_r3_media_support import rig
from support_reconciliation_test_r4_director import screenplay


def synthetic(width=101, height=64, orientation=None):
    from PIL import Image
    image = Image.new('RGBA', (width, height))
    image.putdata([(x * 2 % 256, y * 3 % 256, (x + y) % 256, 128 if x % 7 == 0 else 255)
                   for y in range(height) for x in range(width)])
    stream = io.BytesIO()
    options = {}
    if orientation:
        exif = Image.Exif(); exif[274] = orientation; options['exif'] = exif
    image.save(stream, format='PNG', **options)
    return stream.getvalue()


def body():
    return {'title': 'SYNTHETIC LEGACY COVER BASELINE', 'screenplay_id': 'fixed-screenplay', 'expected_screenplay_version': 1,
            'width': 320, 'height': 320, 'safe_area': 0, 'segment_height': 320,
            'panels': [{'id': 'panel', 'shot_id': 'fixed-shot', 'order': 1, 'x': 8, 'y': 8,
                        'width': 64, 'height': 64, 'asset_id': 'fixed-asset', 'expected_asset_version': 2, 'fit': 'COVER'}]}


def normalized(value=None):
    return LayoutIn.model_validate(value or body()).model_dump()


@pytest.mark.parametrize('key', ['cover_x_percent', 'cover_y_percent'])
@pytest.mark.parametrize('value', [-1, 101, True, False, 1.0, 1.5, '50', None])
def test_strict_alignment_rejects_invalid_numbers(key, value):
    draft = body(); draft['panels'][0][key] = value
    with pytest.raises(ValidationError): LayoutIn.model_validate(draft)


def test_omission_survives_create_update_revalidation_and_explicit_center():
    original = normalized()
    assert 'cover_x_percent' not in original['panels'][0] and 'cover_y_percent' not in original['panels'][0]
    update = LayoutEdit.model_validate({**original, 'expected_version': 7}).model_dump(exclude={'expected_version'})
    assert update == original and normalized(update) == original
    assert json.loads(LayoutIn.model_validate(original).model_dump_json()) == original
    for key in ('cover_x_percent', 'cover_y_percent'):
        draft = body(); draft['panels'][0][key] = 50
        result = normalized(draft)
        assert result['panels'][0][key] == 50
        other = 'cover_y_percent' if key == 'cover_x_percent' else 'cover_x_percent'
        assert other not in result['panels'][0]
        assert normalized(LayoutEdit.model_validate({**result, 'expected_version': 7}).model_dump(exclude={'expected_version'})) == result


def test_original_pre_edit_center_png_golden_and_exact_odd_floor():
    # Captured from unchanged d10b72c original owner before these fields existed.
    report, images = compose(normalized(), {'fixed-asset': synthetic()}, render=True)
    assert report['placements']['panel'] == {'size': (101, 64), 'offset': (-19, 0)}
    assert report['issues'] == [{'code': 'COMIC_CENTER_CROP', 'target': 'panel', 'severity': 'WARNING'}]
    assert hashlib.sha256(images[0]).hexdigest() == 'f299606e9ab739c97742d7c41b5310f2096a9fb2236b7aedc4a32a2dcc6c03c0'
    explicit = normalized(); explicit['panels'][0].update(cover_x_percent=50, cover_y_percent=50)
    assert compose(explicit, {'fixed-asset': synthetic()}, render=True) == (report, images)


@pytest.mark.parametrize('axis', ['x', 'y'])
@pytest.mark.parametrize('percent', [0, 1, 25, 49, 50, 75, 100])
def test_real_striped_pixels_follow_full_crop_travel_and_negative_floor(axis, percent):
    from PIL import Image
    source = synthetic(101, 64) if axis == 'x' else synthetic(64, 101)
    document = normalized(); document['panels'][0][f'cover_{axis}_percent'] = percent
    report, outputs = compose(document, {'fixed-asset': source}, render=True)
    offset = -37 * percent // 100
    assert report['placements']['panel']['offset'] == ((offset, 0) if axis == 'x' else (0, offset))
    with Image.open(io.BytesIO(source)) as original, Image.open(io.BytesIO(outputs[0])) as rendered:
        for x, y in [(3, 3), (20, 20), (60, 60)]:
            sx, sy = (x - offset, y) if axis == 'x' else (x, y - offset)
            rgba = original.getpixel((sx, sy))
            expected = tuple((channel * rgba[3] + 255 * (255 - rgba[3]) + 127) // 255 for channel in rgba[:3])
            assert rendered.getpixel((8 + x, 8 + y)) == expected
    expected_code = 'COMIC_CENTER_CROP' if offset == -19 else 'COMIC_POSITIONED_CROP'
    assert report['issues'] == [{'code': expected_code, 'target': 'panel', 'severity': 'WARNING'}]


def test_inactive_axis_contain_and_exact_aspect_do_not_change_pixels_or_warnings():
    original = normalized(); original['panels'][0]['fit'] = 'CONTAIN'
    changed = copy.deepcopy(original); changed['panels'][0].update(cover_x_percent=0, cover_y_percent=100)
    assert compose(original, {'fixed-asset': synthetic()}, render=True) == compose(changed, {'fixed-asset': synthetic()}, render=True)
    changed['panels'][0]['fit'] = 'COVER'; changed['panels'][0].update(cover_x_percent=50, cover_y_percent=0)
    assert compose(changed, {'fixed-asset': synthetic()})[0]['issues'][0]['code'] == 'COMIC_CENTER_CROP'
    assert compose(changed, {'fixed-asset': synthetic(64, 64)})[0]['issues'] == []


def test_exif_normalization_precedes_crop_and_output_strips_metadata():
    from PIL import Image, ImageOps
    source = synthetic(101, 64, orientation=6)
    with Image.open(io.BytesIO(source)) as image:
        rotated = ImageOps.exif_transpose(image).convert('RGBA'); rotated.info.clear()
        stream = io.BytesIO(); rotated.save(stream, format='PNG')
    draft = normalized(); draft['panels'][0].update(cover_x_percent=0, cover_y_percent=100)
    actual = compose(draft, {'fixed-asset': source}, render=True)
    assert actual == compose(draft, {'fixed-asset': stream.getvalue()}, render=True)
    assert actual[0]['placements']['panel']['offset'] == (0, -37)
    with Image.open(io.BytesIO(actual[1][0])) as output: assert not output.getexif()


def test_original_resample_budget_still_blocks_before_render():
    document = normalized(); document['width'] = 1600
    document['panels'][0].update(x=0, width=1600, height=16, cover_x_percent=100, cover_y_percent=0)
    report, outputs = compose(document, {'fixed-asset': synthetic(1, 1000)}, render=True)
    assert not report['can_render'] and not outputs
    assert any(issue['code'] == 'COMIC_IMAGE_RESAMPLE_LIMIT' for issue in report['issues'])


@pytest.fixture
def owner(rig):
    service = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    source = screenplay(rig)
    asset = rig.assets.create(rig.nid, 'SYNTHETIC-COVER.png', base64.b64encode(synthetic()).decode(), 'image/png')
    service.approve_image(rig.nid, rig.scope, rig.actor, asset['id'], asset['version'])
    asset = rig.assets.get(asset['id'])
    document = body(); document.update(screenplay_id=source['id'], expected_screenplay_version=source['edit_version'])
    document['panels'][0].update(shot_id=source['shots'][0]['id'], asset_id=asset['id'], expected_asset_version=asset['version'])
    return service, asset, document


def test_file_owner_save_review_export_restore_and_unchanged_original_assets(rig, owner):
    service, asset, document = owner
    initial = service.save(rig.nid, rig.scope, rig.actor, document)
    draft = copy.deepcopy(initial['document']); draft['panels'][0].update(cover_x_percent=100, cover_y_percent=25)
    edited = service.save(rig.nid, rig.scope, rig.actor, draft, rid=initial['id'], expected_version=1)
    with pytest.raises(CapabilityVersionConflict): service.save(rig.nid, rig.scope, rig.actor, draft, rid=initial['id'], expected_version=1)
    report = service.preflight(rig.nid, rig.scope, rig.actor, edited['id'], edited['version'])
    assert report['issues'][0]['code'] == 'COMIC_POSITIONED_CROP'
    with pytest.raises(ValueError, match='WARNINGS'): service.approve(rig.nid, rig.scope, rig.actor, edited['id'], edited['version'], report['review_digest'], False)
    accepted = service.approve(rig.nid, rig.scope, rig.actor, edited['id'], edited['version'], report['review_digest'], True)
    reopened = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    assert reopened.records(rig.nid, rig.scope, rig.actor)['items'][0]['document'] == draft
    exported = reopened.export(rig.nid, rig.scope, rig.actor, accepted['id'], accepted['version'])
    with zipfile.ZipFile(io.BytesIO(exported)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        segment = manifest['segments'][0]
        assert archive.read(segment['filename']) == reopened.preview(rig.nid, rig.scope, rig.actor, accepted['id'], accepted['version'], 0)
        assert manifest['asset_bindings'][asset['id']]['sha256'] == asset['sha256']
        assert manifest['asset_bindings'][asset['id']]['version'] == asset['version']
    draft['panels'][0]['cover_x_percent'] = 0
    next_row = reopened.save(rig.nid, rig.scope, rig.actor, draft, rid=accepted['id'], expected_version=accepted['version'])
    assert next_row['status'] == 'DRAFT'
    with pytest.raises(ValueError, match='APPROVAL'): reopened.export(rig.nid, rig.scope, rig.actor, next_row['id'], next_row['version'])
    with pytest.raises(StaleSourceError): reopened.approve(rig.nid, rig.scope, rig.actor, next_row['id'], next_row['version'], report['review_digest'], True)
    restored = reopened.restore(rig.nid, rig.scope, rig.actor, next_row['id'], next_row['version'], 1)
    assert restored['document'] == initial['document'] and restored['status'] == 'DRAFT'
    assert 'cover_x_percent' not in restored['document']['panels'][0]
    assert rig.assets.get(asset['id']) == asset and len(rig.assets.list(rig.nid)) == 1


@pytest.mark.parametrize('mutation', ['asset', 'source', 'privacy', 'guard'])
def test_positioned_crop_preserves_original_source_privacy_and_revocation_fences(rig, owner, mutation):
    service, asset, draft = owner; draft['panels'][0]['cover_x_percent'] = 0
    row = service.save(rig.nid, rig.scope, rig.actor, draft)
    report = service.preflight(rig.nid, rig.scope, rig.actor, row['id'], row['version'])
    row = service.approve(rig.nid, rig.scope, rig.actor, row['id'], row['version'], report['review_digest'], True)
    if mutation == 'guard':
        def revoked(): raise PermissionError('revoked')
        with pytest.raises(PermissionError): service.export(rig.nid, rig.scope, rig.actor, row['id'], row['version'], revoked)
        return
    if mutation == 'asset': rig.assets.update_metadata(asset['id'], {'parameters': {'changed': True}}, expected_version=asset['version'])
    elif mutation == 'source': rig.chapters.save(rig.chapter['id'], {'version': rig.chapter['version'], 'content': 'Changed'})
    else:
        from app.source_privacy import review_source_privacy, content_digest
        review_source_privacy(rig.chapter, None, rig.actor, 'CLOUD_ALLOWED', rig.chapter['version'], content_digest(rig.chapter), rig.root)
    assert service.records(rig.nid, rig.scope, rig.actor)['items'][0]['stale']
    with pytest.raises((ValueError, FileNotFoundError)): service.export(rig.nid, rig.scope, rig.actor, row['id'], row['version'])


@pytest.mark.parametrize('percent,expected_left', [(25, 15), (50, 29), (100, 57)])
def test_resampled_odd_excess_matches_independent_alpha_crop(percent, expected_left):
    from PIL import Image
    source = synthetic()
    draft = normalized(); draft['panels'][0].update(width=95, height=96, cover_x_percent=percent)
    report, outputs = compose(draft, {'fixed-asset': source}, render=True)
    # Height drives scale=1.5, round(101*1.5)=152; crop travel is 57 px.
    assert report['placements']['panel'] == {'size': (152, 96), 'offset': (-expected_left, 0)}
    with Image.open(io.BytesIO(source)) as original:
        resized = original.resize((152, 96), Image.Resampling.LANCZOS)
        background = Image.new('RGBA', (152, 96), 'white')
        expected = Image.alpha_composite(background, resized).convert('RGB').crop((expected_left + 2, 2, expected_left + 93, 94))
    with Image.open(io.BytesIO(outputs[0])) as actual:
        assert actual.crop((10, 10, 101, 102)).tobytes() == expected.tobytes()
