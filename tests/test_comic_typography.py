"""Original Comic typography: exact legacy bytes, real text pixels and history."""
import copy
import hashlib
import io
import json
import zipfile

import pytest
from PIL import Image, ImageChops
from pydantic import ValidationError

from app.experimental.comic_layouts import LayoutIn, LayoutEdit, ComicLayoutsService, compose
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig, branch_scope
from test_r5_comic_layouts import comic, image_asset, layout, save, preflight, approve
from test_comic_layers import layered


def document():
    return LayoutIn.model_validate({'title': 'Synthetic typography', 'source_mode': 'INDEPENDENT',
        'width': 640, 'height': 640, 'segment_height': 640,
        'panels': [{'id': 'panel', 'order': 1, 'artwork_mode': 'BLANK', 'x': 24, 'y': 24,
            'width': 592, 'height': 592, 'bubbles': [{'id': 'text', 'text': '天地\n日',
                'font_size': 32, 'x': 40, 'y': 40, 'width': 300, 'height': 200}]}]}).model_dump()


def pixels(doc):
    report, output = compose(doc, {}, render=True)
    assert report['can_render'], report
    assert len(output) == 1
    return report, output[0]


@pytest.mark.parametrize('field,bad', [
    ('text_align', 'JUSTIFY'), ('text_align', 'left'), ('text_align', None), ('text_align', {}),
    ('line_height_percent', 99), ('line_height_percent', 251), ('line_height_percent', True),
    ('line_height_percent', 150.0), ('line_height_percent', '150'), ('line_height_percent', None),
])
def test_strict_typography_fields_reject_malformed_values(field, bad):
    doc = document()
    doc['panels'][0]['bubbles'][0][field] = bad
    with pytest.raises(ValidationError): LayoutIn.model_validate(doc)


def test_legacy_omission_and_explicit_defaults_survive_serialization():
    old = document()
    assert 'text_align' not in old['panels'][0]['bubbles'][0]
    assert 'line_height_percent' not in old['panels'][0]['bubbles'][0]
    assert LayoutEdit.model_validate({**old, 'expected_version': 7}).model_dump(exclude={'expected_version'}) == old
    assert json.loads(LayoutIn.model_validate(old).model_dump_json()) == old
    explicit = copy.deepcopy(old)
    explicit['panels'][0]['bubbles'][0].update(text_align='LEFT', line_height_percent=150)
    assert LayoutIn.model_validate(explicit).model_dump() == explicit
    assert pixels(explicit) == pixels(old)


def test_legacy_default_pixels_match_unchanged_baseline_golden():
    assert hashlib.sha256(pixels(document())[1]).hexdigest() == '80c60591c6e8cb3249802e7d631d796c242930f236725d57434566a3a32c1dff'


def text_bounds(data):
    image = Image.open(io.BytesIO(data)).convert('RGB').crop((52, 52, 328, 228))
    return ImageChops.difference(image, Image.new('RGB', image.size, 'white')).getbbox()


def test_real_alignment_and_line_spacing_pixels_match_native_layers(tmp_path):
    doc = document()
    results = {}
    for align in ('LEFT', 'CENTER', 'RIGHT'):
        for spacing in (150, 200):
            current = copy.deepcopy(doc)
            current['panels'][0]['bubbles'][0].update(text_align=align, line_height_percent=spacing)
            report, data = pixels(current)
            layer_doc = LayoutIn.model_validate(layered(current)).model_dump()
            layer_report, layer_data = pixels(layer_doc)
            assert layer_data == data
            results[align, spacing] = text_bounds(data)
            (tmp_path / f'{align.lower()}-{spacing}.png').write_bytes(data)
    assert results['LEFT', 150][0] < results['CENTER', 150][0] < results['RIGHT', 150][0]
    for align in ('LEFT', 'CENTER', 'RIGHT'):
        assert results[align, 200][1] == results[align, 150][1]
        assert results[align, 200][3] - results[align, 150][3] == 16


def test_larger_spacing_uses_existing_overflow_blocker():
    doc = document(); bubble = doc['panels'][0]['bubbles'][0]
    bubble.update(height=128, line_height_percent=150)
    assert pixels(doc)
    bubble['line_height_percent'] = 250
    report, output = compose(doc, {}, render=True)
    assert output == [] and not report['can_render']
    assert any(issue['code'] == 'COMIC_TEXT_OVERFLOW' and issue['target'] == bubble['id'] for issue in report['issues'])


def test_original_save_reopen_restore_and_approval_keep_other_objects(rig, comic, image_asset):
    body = layout(rig, image_asset)
    panel = body['panels'][0]
    panel['bubbles'] = [
        {'id': 'first', 'text': '天地\n日', 'x': 40, 'y': 40, 'width': 300, 'height': 200},
        {'id': 'other', 'text': 'Unchanged', 'x': 400, 'y': 40, 'width': 300, 'height': 200},
    ]
    original = save(comic, rig, body)
    original_report = preflight(comic, rig, original)
    approved = approve(comic, rig, original, original_report)
    before = copy.deepcopy(approved['document'])
    other_page = save(comic, rig, {**body, 'title': 'Other unchanged page'})
    changed = copy.deepcopy(before)
    changed['panels'][0]['bubbles'][0].update(text_align='RIGHT', line_height_percent=200)
    edited = comic.save(rig.nid, rig.scope, rig.actor, changed, rid=approved['id'], expected_version=approved['version'])
    assert edited['status'] == 'DRAFT'
    assert edited['document']['panels'][0]['bubbles'][1] == before['panels'][0]['bubbles'][1]
    assert {k: v for k, v in edited['document']['panels'][0].items() if k != 'bubbles'} == {k: v for k, v in before['panels'][0].items() if k != 'bubbles'}
    reopened = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    assert next(item for item in reopened.records(rig.nid, rig.scope, rig.actor)['items'] if item['id'] == edited['id'])['document'] == changed
    with pytest.raises(ValueError, match='APPROVAL'): reopened.export(rig.nid, rig.scope, rig.actor, edited['id'], edited['version'])
    with pytest.raises(CapabilityVersionConflict): reopened.save(rig.nid, rig.scope, rig.actor, changed, rid=edited['id'], expected_version=approved['version'])
    assert reopened.records(rig.nid, rig.scope, 'other')['items'] == []
    assert reopened.records(rig.nid, branch_scope(rig), rig.actor)['items'] == []
    with pytest.raises(StaleSourceError): reopened.approve(rig.nid, rig.scope, rig.actor, edited['id'], edited['version'], original_report['review_digest'], True)
    current = approve(reopened, rig, edited)
    preview = reopened.preview(rig.nid, rig.scope, rig.actor, edited['id'], current['version'], 0)
    with zipfile.ZipFile(io.BytesIO(reopened.export(rig.nid, rig.scope, rig.actor, edited['id'], current['version']))) as archive:
        assert archive.read('segment-001.png') == preview
    restored = reopened.restore(rig.nid, rig.scope, rig.actor, edited['id'], current['version'], original['version'])
    assert restored['document'] == before and restored['status'] == 'DRAFT'
    assert next(item for item in reopened.records(rig.nid, rig.scope, rig.actor)['items'] if item['id'] == other_page['id']) == other_page
    assert len(rig.assets.list(rig.nid)) == 1
