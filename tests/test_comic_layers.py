"""Native reference layers; real synthetic PNGs, no model or external application claim."""
import copy
import io
import json
import os
import zipfile
from xml.etree.ElementTree import fromstring

import pytest
from pydantic import ValidationError
from PIL import Image
from app.experimental.comic_layouts import ComicLayoutsService, LayoutIn, compose, licensed_font, _image
from app.experimental.comic_ora import encode_ora, _BoundedBuffer
from app.creative.project_store import CreativeProjectStore
from app.experimental.common import StaleSourceError
from test_r3_media_support import rig
from test_r5_comic_layouts import comic, image_asset, layout, save, preflight, approve, synthetic_png


def layered(body):
    body = copy.deepcopy(body)
    items = []
    for panel in sorted(body['panels'], key=lambda p: p['order']):
        refs = [(kind, panel['id']) for kind in ('PANEL_ART', 'PANEL_FRAME')]
        refs += [(kind, b['id']) for b in panel.get('bubbles', []) for kind in ('BUBBLE_SHAPE', 'BUBBLE_TEXT')]
        for kind, target in refs:
            items.append({'id': f'layer_{len(items)}', 'kind': kind, 'target_id': target,
                          'name': kind, 'visible': True, 'opacity_percent': 100})
    body['layer_stack'] = {'schema_version': 1, 'items': items}
    return body


def blank():
    return {'title': 'Layer fixture', 'source_mode': 'INDEPENDENT', 'panels': [
        {'id': 'panel', 'artwork_mode': 'BLANK', 'order': 1, 'x': 24, 'y': 24, 'width': 400, 'height': 320, 'bubbles': []}]}


def test_legacy_omission_exact_report_and_pixels():
    old = LayoutIn.model_validate(blank()).model_dump()
    assert 'layer_stack' not in old
    assert LayoutIn.model_validate(old).model_dump() == old
    old_report, old_png = compose(old, {}, render=True)
    new = LayoutIn.model_validate(layered(old)).model_dump()
    report, png = compose(new, {}, render=True)
    assert report.pop('layer_profile') == 'NATIVE_REFERENCE_LAYERS_V1'
    assert report == old_report and png == old_png
    assert set(old_report) == {'issues', 'segments', 'placements', 'can_render', 'geometry'}


@pytest.mark.parametrize('change', ['null', 'duplicate_id', 'duplicate_ref', 'missing', 'unknown', 'opacity', 'namespace', 'name', 'schema', 'schema_bool', 'xml_name', 'xml_title'])
def test_layer_contract_rejects_invalid(change):
    body = layered(blank()); items = body['layer_stack']['items']
    if change == 'null': body['layer_stack'] = None
    elif change == 'duplicate_id': items[1]['id'] = items[0]['id']
    elif change == 'duplicate_ref': items[1]['kind'] = items[0]['kind']
    elif change == 'missing': items.pop()
    elif change == 'unknown': items[0]['target_id'] = 'missing'
    elif change == 'opacity': items[0]['opacity_percent'] = True
    elif change == 'namespace': items[0]['id'] = 'panel'
    elif change == 'name': items[0]['name'] = '\x00bad'
    elif change == 'schema_bool': body['layer_stack']['schema_version'] = True
    elif change == 'xml_name': items[0]['name'] = '\uffff'
    elif change == 'xml_title': body['title'] = '\x00'
    else: body['layer_stack']['schema_version'] = 2
    with pytest.raises(ValidationError): LayoutIn.model_validate(body)


def test_layer_pixels_bounded_before_render():
    body = blank()
    body['panels'] *= 6
    body['panels'] = [{**p, 'id': str(i), 'width': 1600, 'height': 12000} for i, p in enumerate(body['panels'])]
    with pytest.raises(ValidationError, match='LAYER_PIXEL_LIMIT'): LayoutIn.model_validate(layered(body))


def test_visibility_opacity_changes_only_reference_surface():
    body = LayoutIn.model_validate(layered(blank())).model_dump()
    body['layer_stack']['items'][1]['opacity_percent'] = 50
    _, output = compose(body, {}, render=True)
    image = Image.open(io.BytesIO(output[0]))
    assert image.getpixel((24, 24)) == (127, 127, 127)
    assert image.getpixel((100, 100)) == (255, 255, 255)
    body['layer_stack']['items'][1]['visible'] = False
    _, output = compose(body, {}, render=True)
    assert Image.open(io.BytesIO(output[0])).getpixel((24, 24)) == (255, 255, 255)


def test_layer_save_reopen_approval_and_restore(rig, comic, image_asset):
    body = layered(layout(rig, image_asset))
    row = save(comic, rig, body); approved = approve(comic, rig, row)
    original = copy.deepcopy(row['document'])
    changed = copy.deepcopy(original); changed['layer_stack']['items'][0]['visible'] = False
    edited = comic.save(rig.nid, rig.scope, rig.actor, changed, rid=row['id'], expected_version=approved['version'])
    assert edited['status'] == 'DRAFT'
    reopened = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    assert reopened.records(rig.nid, rig.scope, rig.actor)['items'][0]['document'] == changed
    with pytest.raises(ValueError, match='APPROVAL'): reopened.export_ora(rig.nid, rig.scope, rig.actor, row['id'], edited['version'])
    restored = reopened.restore(rig.nid, rig.scope, rig.actor, row['id'], edited['version'], 1)
    assert restored['document'] == original and restored['status'] == 'DRAFT'
    assert len(rig.assets.list(rig.nid)) == 1


def test_real_ora_separate_layers_and_recomposition(rig, comic, image_asset):
    row = save(comic, rig, layered(layout(rig, image_asset)))
    approved = approve(comic, rig, row)
    raw = comic.export_ora(rig.nid, rig.scope, rig.actor, row['id'], approved['version'])
    assert raw == comic.export_ora(rig.nid, rig.scope, rig.actor, row['id'], approved['version'])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.infolist()[0].filename == 'mimetype'
        assert archive.infolist()[0].compress_type == zipfile.ZIP_STORED
        assert archive.read('mimetype') == b'image/openraster'
        xml = fromstring(archive.read('stack.xml'))
        layers = list(xml.find('stack'))
        assert len(layers) == 3 and layers[0].get('name') == 'PANEL_FRAME'
        surfaces = [Image.open(io.BytesIO(archive.read(layer.get('src')))).convert('RGBA') for layer in layers]
        assert surfaces[0].getpixel((40, 40))[3] == 0
        assert surfaces[1].getpixel((40, 40))[3] == 255
        merged = Image.open(io.BytesIO(archive.read('mergedimage.png'))).convert('RGBA')
        independent = Image.new('RGBA', merged.size)
        for layer, surface in reversed(list(zip(layers, surfaces))):
            independent.alpha_composite(surface, (int(layer.get('x')), int(layer.get('y'))))
        assert independent.tobytes() == merged.tobytes()
        report, segments = compose(row['document'], {image_asset['id']: rig.assets.content(image_asset['id'])}, render=True)
        assert merged.crop((0, 0, 800, 560)).convert('RGB').tobytes() == Image.open(io.BytesIO(segments[0])).tobytes()
        thumb = Image.open(io.BytesIO(archive.read('Thumbnails/thumbnail.png')))
        assert max(thumb.size) <= 256
        receipt = json.loads(archive.read('comic-loss-receipt.json'))
        assert len(receipt['layers']) == 2 and any('TEXT_AND_SHAPES_RASTERIZED' in loss for loss in receipt['losses'])
    assert len(rig.assets.list(rig.nid)) == 1


def test_ora_rechecks_source_and_version_after_encoding(rig, comic, image_asset, monkeypatch):
    row = approve(comic, rig, save(comic, rig, layered(layout(rig, image_asset))))
    import app.experimental.comic_ora as module
    original = module.encode_ora
    def raced(*args):
        result = original(*args)
        rig.assets.update_metadata(image_asset['id'], {'approved_at': None}, expected_version=image_asset['version'])
        return result
    monkeypatch.setattr(module, 'encode_ora', raced)
    with pytest.raises(ValueError, match='REVIEW'): comic.export_ora(rig.nid, rig.scope, rig.actor, row['id'], row['version'])


def test_ora_requires_explicit_stack(rig, comic, image_asset):
    row = approve(comic, rig, save(comic, rig, layout(rig, image_asset)))
    with pytest.raises(ValueError, match='EXPLICIT_LAYER_STACK'): comic.export_ora(rig.nid, rig.scope, rig.actor, row['id'], row['version'])


def test_ora_size_checked_during_writes(monkeypatch):
    monkeypatch.setattr('app.experimental.comic_ora.MAX_ORA_BYTES', 4)
    with pytest.raises(ValueError, match='ORA_SIZE'): _BoundedBuffer().write(b'12345')


def test_source_budget_checked_before_decoding_and_shared_across_sources():
    budget = [150]
    stream = io.BytesIO(); Image.new('RGB', (10, 10), 'red').save(stream, 'PNG'); raw = stream.getvalue()
    assert _image(raw, pixel_budget=budget).size == (10, 10)
    assert budget == [50]
    with pytest.raises(ValueError, match='SOURCE_PIXEL_LIMIT'): _image(raw, pixel_budget=budget)
    assert budget == [50]


def test_layer_source_budget_in_payload_and_preflight(rig, comic, image_asset, monkeypatch):
    import app.experimental.comic_layouts as module
    old = layout(rig, image_asset)
    # Layer policy must not change legacy source validation or old digests.
    monkeypatch.setattr(module, 'MAX_LAYER_SOURCE_PIXELS', 1)
    row = save(comic, rig, old)
    assert preflight(comic, rig, row)['can_render']
    with pytest.raises(ValueError, match='SOURCE_PIXEL_LIMIT'): save(comic, rig, layered(old))
    assert len(comic.records(rig.nid, rig.scope, rig.actor)['items']) == 1


def test_whole_ora_budget_counts_repeated_rechecks_and_resets(rig, comic, image_asset, monkeypatch):
    row = approve(comic, rig, save(comic, rig, layered(layout(rig, image_asset))))
    monkeypatch.setattr('app.experimental.comic_layers.MAX_ORA_DECODE_PIXELS', 50_000)
    with pytest.raises(ValueError, match='ORA_DECODE_WORK_LIMIT'):
        comic.export_ora(rig.nid, rig.scope, rig.actor, row['id'], row['version'])
    # The same source fits one decode but not the repeated operation. No leaked
    # request-local budget may affect subsequent legacy operations.
    assert _image(rig.assets.content(image_asset['id'])).size == (240, 160)
    assert comic.records(rig.nid, rig.scope, rig.actor)['items'][0]['status'] == 'APPROVED'


def test_aggregate_resample_work_blocks_before_allocations():
    body = blank(); body['height'] = 2400
    body['panels'] = [{**body['panels'][0], 'id': str(i), 'order': i + 1, 'y': 24 + 400 * i,
                       'artwork_mode': 'IMAGE', 'asset_id': 'image', 'expected_asset_version': 1, 'fit': 'COVER'} for i in range(5)]
    body = LayoutIn.model_validate(layered(body)).model_dump()
    data = io.BytesIO(); Image.new('RGB', (10, 1000), 'red').save(data, 'PNG')
    report, png = compose(body, {'image': data.getvalue()}, render=True)
    assert not png and not report['can_render']
    assert any(i['code'] == 'COMIC_LAYER_RESAMPLE_PIXEL_LIMIT_64000000' for i in report['issues'])


def test_archive_and_png_limit_propagate_without_delivery(monkeypatch):
    body = LayoutIn.model_validate(layered(blank())).model_dump()
    report = {**compose(body, {})[0], 'review_digest': 'a' * 64}
    monkeypatch.setattr('app.experimental.comic_ora.MAX_ORA_BYTES', 200)
    with pytest.raises(ValueError, match='ORA_SIZE'): encode_ora(body, {}, report, 1)


@pytest.mark.parametrize('hidden', [False, True])
def test_ora_xml_opacity_visibility_and_reorder_recompose(rig, comic, image_asset, hidden):
    body = layered(layout(rig, image_asset))
    body['title'] = '<Synthetic & safe>'
    body['layer_stack']['items'][0].update(visible=not hidden, opacity_percent=37, name='Art <&>')
    body['layer_stack']['items'][1]['opacity_percent'] = 61
    body['layer_stack']['items'].reverse()
    row = approve(comic, rig, save(comic, rig, body))
    raw = comic.export_ora(rig.nid, rig.scope, rig.actor, row['id'], row['version'])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        xml = fromstring(archive.read('stack.xml'))
        assert xml.get('name') == body['title']
        merged = Image.open(io.BytesIO(archive.read('mergedimage.png'))).convert('RGBA')
        actual = Image.new('RGBA', merged.size)
        for layer in reversed(list(xml.find('stack'))):
            if layer.get('visibility') == 'hidden': continue
            surface = Image.open(io.BytesIO(archive.read(layer.get('src')))).convert('RGBA')
            opacity = float(layer.get('opacity'))
            surface.putalpha(surface.getchannel('A').point(lambda a: int(a * opacity + 0.5)))
            actual.alpha_composite(surface, (int(layer.get('x')), int(layer.get('y'))))
        assert actual.tobytes() == merged.tobytes()


def test_hidden_text_still_obeys_original_font_gate(monkeypatch):
    import app.experimental.comic_layouts as module
    def unavailable(): raise ValueError('COMIC_PINNED_OFL_CJK_FONT_UNAVAILABLE')
    monkeypatch.setattr(module, 'licensed_font', unavailable)
    body = blank(); body['panels'][0]['bubbles'] = [{'id': 'bubble', 'text': '中文', 'x': 40, 'y': 40, 'width': 300, 'height': 160}]
    body = LayoutIn.model_validate(layered(body)).model_dump()
    body['layer_stack']['items'][-1]['visible'] = False
    report, output = compose(body, {}, render=True)
    assert not output and not report['can_render']
    assert any(i['code'] == 'COMIC_PINNED_OFL_CJK_FONT_UNAVAILABLE' for i in report['issues'])


def test_pinned_font_native_dialogue_and_separate_text_png(monkeypatch):
    # No substitution with an unlicensed/system font, no fabricated availability.
    path = os.environ.get('R2_TEST_FONT_FILE')
    if path: monkeypatch.setenv('AI_NOVEL_STUDIO_PDF_FONT', path)
    try: licensed_font()
    except ValueError: pytest.skip('NOT_RUN: existing pinned licensed CJK font unavailable')
    body = blank(); body['panels'][0]['bubbles'] = [{'id': 'bubble', 'text': '中文对白', 'x': 40, 'y': 40, 'width': 300, 'height': 160}]
    old = LayoutIn.model_validate(body).model_dump()
    body = LayoutIn.model_validate(layered(body)).model_dump()
    report, png = compose(body, {}, render=True)
    assert png == compose(old, {}, render=True)[1]
    raw = encode_ora(body, {}, {**report, 'review_digest': 'a' * 64}, 1)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        text = Image.open(io.BytesIO(archive.read('data/layer-004.png')))
        assert text.getbbox() is not None and text.getpixel((0, 0))[3] == 0
        assert 'OFL.txt' in archive.namelist()
    assert body['panels'][0]['bubbles'][0]['text'] == '中文对白'
