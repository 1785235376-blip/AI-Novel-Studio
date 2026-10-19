"""Real File-owner Comic handoff contracts; no inference or video acceptance."""
import copy
import hashlib
import io
import os

import pytest
from PIL import Image

from app.asset_providers import AssetProviderRegistry
from app.experimental.comic_layouts import ComicLayoutsService
from app.experimental.comic_timeline_handoff import ComicTimelineHandoff, HandoffConfirm
from app.experimental.media import digest
from app.services.comic_page_origin import marker, record, validate_png, FIELD, FEATURES
from test_v2_independent_workspace import rig, reopened
from test_v2_discovered_image_production import owner


@pytest.fixture
def handoff(rig, monkeypatch):
    production = owner(AssetProviderRegistry(), monkeypatch, rig)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(sorted(FEATURES)))
    comic = ComicLayoutsService(rig.raw_store, rig.novels, rig.chapters, None, rig.assets,
                               independent_store=rig.store)
    return ComicTimelineHandoff(comic, production)


def page(rig, handoff, *, approved=True, layers=False, text=False, shift=0):
    body = {'title': 'Synthetic complete page', 'source_mode': 'INDEPENDENT', 'preset': 'PAGE',
            'width': 320, 'height': 640, 'segment_height': 320,
            'panels': [{'id': 'p', 'order': 1, 'artwork_mode': 'BLANK',
                        'x': 24 + shift, 'y': 24, 'width': 240, 'height': 580, 'bubbles': []}]}
    if text:
        body['panels'][0]['bubbles'] = [{'id': 'b', 'kind': 'DIALOGUE', 'text': '你好，漫画',
            'x': 48, 'y': 370, 'width': 190, 'height': 150, 'font_size': 24,
            'text_align': 'RIGHT', 'line_height_percent': 180}]
    if layers:
        kinds = [('PANEL_ART', 'p'), ('PANEL_FRAME', 'p')]
        if text: kinds += [('BUBBLE_SHAPE', 'b'), ('BUBBLE_TEXT', 'b')]
        body['layer_stack'] = {'schema_version': 1, 'items': [
            {'id': 'layer_' + str(i), 'kind': kind, 'target_id': target, 'name': kind}
            for i, (kind, target) in enumerate(kinds)]}
    saved = handoff.comic.save(rig.nid, rig.scope, rig.actor, body)
    if approved:
        report = handoff.comic.preflight(rig.nid, rig.scope, rig.actor, saved['id'], saved['version'])
        saved = handoff.comic.approve(rig.nid, rig.scope, rig.actor, saved['id'], saved['version'],
                                      report['review_digest'], True)
    saved['review_digest'] = handoff.comic.preflight(rig.nid, rig.scope, rig.actor, saved['id'], saved['version'])['review_digest']
    return saved


def request(pages, durations=None):
    return {'title': 'Explicit static draft', 'width': 640, 'height': 360, 'fps': 24,
            'pages': [{'id': row['id'], 'version': row['version'],
                       'review_digest': row['review_digest'],
                       'duration_ms': (durations or [5000] * len(pages))[i]}
                      for i, row in enumerate(pages)]}


def preview(rig, handoff, body):
    return handoff.preview(rig.nid, rig.scope, rig.actor, body)


def test_real_full_page_bytes_order_and_no_mutation(rig, handoff):
    a, b = page(rig, handoff), page(rig, handoff, shift=10)
    body = request([b, a], [7000, 13000])
    before = rig.raw_store.read(rig.nid, rig.scope)
    before_assets = list(rig.assets.root.glob('*'))
    report, images = preview(rig, handoff, body)
    assert before == rig.raw_store.read(rig.nid, rig.scope)
    assert before_assets == list(rig.assets.root.glob('*'))
    assert report['duration_ms'] == 20000 and [p['source']['id'] for p in report['pages']] == [b['id'], a['id']]
    assert [p['duration_ms'] for p in report['pages']] == [7000, 13000]
    for pin, data in zip(report['pages'], images):
        assert hashlib.sha256(data).hexdigest() == pin['png_sha256']
        with Image.open(io.BytesIO(data)) as image:
            assert image.size == (320, 640) and image.mode == 'RGB'
            # The panel bottom is in the second original segment.
            assert image.getpixel((pin['source']['id'] == b['id'] and 34 or 24, 602)) == (0, 0, 0)
    assert report['preview_digest'] == digest({k: v for k, v in report.items() if k != 'preview_digest'})
    assert not report['automatic_dispatch'] and not report['video_rendered'] and not report['approval_inherited']
    assert preview(rig, handoff, body) == (report, images)


def test_all_four_selected_pages_preserved(rig, handoff):
    pages = [page(rig, handoff, shift=i) for i in range(4)]
    report, images = preview(rig, handoff, request(pages))
    assert len(images) == len(report['pages']) == 4


def test_layer_stack_and_chinese_text_use_original_composition(rig, handoff, monkeypatch):
    font = os.environ.get('R2_TEST_FONT_FILE')
    assert font, 'Supply the existing pinned licensed test font; do not fake font metrics'
    monkeypatch.setenv('AI_NOVEL_STUDIO_PDF_FONT', font)
    saved = page(rig, handoff, layers=True, text=True)
    _, images = preview(rig, handoff, request([saved]))
    from app.experimental.comic_publication import _render_page
    with handoff._phase(rig.nid, rig.scope, rig.actor, lambda: None):
        expected = _render_page(handoff.comic, rig.nid, rig.scope, rig.actor,
                                handoff.comic._row(rig.nid, rig.scope, rig.actor, saved['id']))
    assert images == (expected,)
    with Image.open(io.BytesIO(images[0])) as image:
        ink = sum(pixel != (255, 255, 255) for pixel in image.crop((62, 385, 225, 430)).get_flattened_data())
        assert ink > 100


@pytest.mark.parametrize('change', ['empty', 'five', 'duplicate', 'zero', 'negative', 'float', 'bool',
                                   'total', 'odd', 'unknown', 'path', 'url', 'fps'])
def test_reject_whole_invalid_request_before_render_or_write(rig, handoff, monkeypatch, change):
    saved = page(rig, handoff)
    body = request([saved])
    if change == 'empty': body['pages'] = []
    elif change == 'five': body['pages'] *= 5
    elif change == 'duplicate': body['pages'] *= 2
    elif change in {'zero', 'negative', 'float', 'bool'}:
        body['pages'][0]['duration_ms'] = {'zero': 0, 'negative': -1, 'float': 1.2, 'bool': True}[change]
    elif change == 'total':
        other = page(rig, handoff)
        body = request([saved, other], [600000, 1])
    elif change == 'odd': body['width'] = 641
    elif change == 'unknown': body['executable'] = 'do not run'
    elif change == 'path': body['pages'][0]['id'] = '../outside'
    elif change == 'url': body['pages'][0]['id'] = 'https://invalid.example/page'
    else: body['fps'] = 61
    before = rig.raw_store.read(rig.nid, rig.scope)
    monkeypatch.setattr('app.experimental.comic_timeline_handoff._render_page',
                        lambda *a: pytest.fail('invalid request rendered'))
    with pytest.raises(ValueError): preview(rig, handoff, body)
    assert before == rig.raw_store.read(rig.nid, rig.scope)
    assert not list(rig.assets.root.glob('*.bin'))


@pytest.mark.parametrize('change', ['draft', 'version', 'review', 'actor', 'scope', 'webtoon'])
def test_unapproved_changed_or_foreign_source_fails(rig, handoff, change):
    saved = page(rig, handoff, approved=change != 'draft')
    body = request([saved])
    actor, scope = rig.actor, rig.scope
    if change == 'version': body['pages'][0]['version'] -= 1
    elif change == 'review': body['pages'][0]['review_digest'] = 'a' * 64
    elif change == 'actor': actor = 'other-author'
    elif change == 'scope': scope = {**rig.scope, 'mode': 'other'}
    elif change == 'webtoon':
        doc = copy.deepcopy(saved['document']); doc['preset'] = 'WEBTOON'
        saved = handoff.comic.save(rig.nid, rig.scope, rig.actor, doc, rid=saved['id'], expected_version=saved['version'])
        saved['review_digest'] = handoff.comic.preflight(rig.nid, rig.scope, rig.actor, saved['id'], saved['version'])['review_digest']
        body = request([saved])
    before = rig.raw_store.read(rig.nid, rig.scope)
    with pytest.raises((ValueError, FileNotFoundError)):
        handoff.preview(rig.nid, scope, actor, body)
    assert before == rig.raw_store.read(rig.nid, rig.scope)


def test_guard_revocation_after_render_returns_no_preview(rig, handoff, monkeypatch):
    saved = page(rig, handoff)
    import app.experimental.comic_timeline_handoff as module
    original = module._render_page
    revoked = False
    def render(*args):
        nonlocal revoked
        data = original(*args); revoked = True; return data
    def guard():
        if revoked: raise PermissionError('revoked')
    monkeypatch.setattr(module, '_render_page', render)
    before = rig.raw_store.read(rig.nid, rig.scope)
    with pytest.raises(PermissionError): handoff.preview(rig.nid, rig.scope, rig.actor, request([saved]), guard)
    assert before == rig.raw_store.read(rig.nid, rig.scope)


def test_renderer_change_during_work_invalidates_all_pages(rig, handoff, monkeypatch):
    saved = page(rig, handoff)
    import app.experimental.comic_layouts as module
    original = module.renderer_status
    before = rig.raw_store.read(rig.nid, rig.scope)
    changed_build = False
    original_render = __import__('app.experimental.comic_timeline_handoff', fromlist=['_render_page'])._render_page
    def render(*args):
        nonlocal changed_build
        data = original_render(*args); changed_build = True; return data
    def changed():
        status = original()
        return {**status, 'version': 'changed-build'} if changed_build else status
    monkeypatch.setattr(module, 'renderer_status', changed)
    monkeypatch.setattr('app.experimental.comic_timeline_handoff._render_page', render)
    with pytest.raises(ValueError): preview(rig, handoff, request([saved]))
    assert before == rig.raw_store.read(rig.nid, rig.scope)


def test_resource_failure_is_atomic_and_keeps_no_output(rig, handoff, monkeypatch):
    saved = page(rig, handoff)
    before = rig.raw_store.read(rig.nid, rig.scope)
    monkeypatch.setattr('app.experimental.comic_publication_budget.MAX_RENDER_PIXELS', 1)
    with pytest.raises(ValueError, match='_LIMIT'): preview(rig, handoff, request([saved]))
    assert before == rig.raw_store.read(rig.nid, rig.scope) and not list(rig.assets.root.glob('*.bin'))


@pytest.mark.parametrize('ack', [False, 1, 'true', None])
def test_confirmation_contract_requires_explicit_boolean_ack(rig, handoff, ack):
    saved = page(rig, handoff)
    body = request([saved]); report, _ = preview(rig, handoff, body)
    before = rig.raw_store.read(rig.nid, rig.scope)
    with pytest.raises(ValueError):
        HandoffConfirm.model_validate({'request_id': 'explicit', 'request': body,
            'reviewed_preview_digest': report['preview_digest'], 'acknowledge_losses': ack})
    assert before == rig.raw_store.read(rig.nid, rig.scope) and not list(rig.assets.root.glob('*.bin'))


def test_passive_origin_contract_and_real_png(rig, handoff):
    saved = page(rig, handoff)
    report, images = preview(rig, handoff, request([saved]))
    origin = {'contract': 'studio-comic-page-asset/1', 'actor': rig.actor,
        'scope_key': report['scope_key'], 'incarnation': report['incarnation'],
        'receipt_id': 'receipt', 'asset_id': 'exact-asset', 'index': 0,
        'request_digest': report['request_digest'], 'preview_digest': report['preview_digest'],
        **{k: report['pages'][0][k] for k in ('source', 'width', 'height', 'png_sha256', 'render_fingerprint')}}
    assert marker(origin) == origin
    validate_png(images[0], origin)
    meta = {'id': 'exact-asset', 'kind': 'image', 'media_type': 'image/png', 'sha256': origin['png_sha256'],
        'version': 1, 'source_asset_ids': [], '_project_binding': {'scope_key': report['scope_key'],
        'incarnation': report['incarnation']}, '_required_features': sorted(FEATURES), FIELD: origin}
    assert record(meta) == origin
    for field, bad in [('index', True), ('asset_id', '../escape'), ('source', {**origin['source'], 'version': True}),
                       ('scope_key', 'bad'), ('incarnation', 'file:other'), ('width', 999999)]:
        with pytest.raises(ValueError): marker({**origin, field: bad})
    with pytest.raises(ValueError): marker({**origin, 'approved': True})
    for patch in [{'approved_at': 'now'}, {'source_job_id': 'fake-job'}, {'_owner_actor_id': rig.actor},
                  {'source_asset_ids': ['pretend-parent']}, {'id': 'other-id'}, {'kind': 'video'}]:
        with pytest.raises(ValueError): record({**meta, **patch})
    with pytest.raises(ValueError): validate_png(images[0] + b'tamper', origin)


def test_original_uploaded_artwork_preserves_native_bounded_read_boundary(rig, handoff):
    import base64
    from test_v2_independent_workspace import png_bytes
    original_png = png_bytes(b'\x11\x22\x33')
    asset = rig.assets.create(rig.nid, 'original.png', base64.b64encode(original_png).decode(), 'image/png')
    reviewed = handoff.comic.approve_image(rig.nid, rig.scope, rig.actor, asset['id'], asset['version'])
    saved = page(rig, handoff)
    doc = copy.deepcopy(saved['document'])
    doc['panels'][0].update(artwork_mode='IMAGE', asset_id=asset['id'], expected_asset_version=reviewed['version'])
    saved = handoff.comic.save(rig.nid, rig.scope, rig.actor, doc, rid=saved['id'], expected_version=saved['version'])
    report = handoff.comic.preflight(rig.nid, rig.scope, rig.actor, saved['id'], saved['version'])
    saved = handoff.comic.approve(rig.nid, rig.scope, rig.actor, saved['id'], saved['version'], report['review_digest'], True)
    saved['review_digest'] = report['review_digest']
    body = request([saved])
    before = rig.raw_store.read(rig.nid, rig.scope)
    if not getattr(os, 'O_NOFOLLOW', 0) or not getattr(os, 'O_NONBLOCK', 0):
        # Preserve the original platform boundary. This is a refusal test,
        # never a claim that artwork-page preview was accepted on Windows.
        with pytest.raises(ValueError, match='ASSET_BOUNDED_READ_UNSUPPORTED'):
            preview(rig, handoff, body)
        assert before == rig.raw_store.read(rig.nid, rig.scope)
        return
    _, images = preview(rig, handoff, body)
    with Image.open(io.BytesIO(images[0])) as image:
        assert image.getpixel((144, 320)) == (17, 34, 51)
        assert image.getpixel((24, 602)) == (0, 0, 0)
    assert before == rig.raw_store.read(rig.nid, rig.scope)
    rig.assets.update_metadata(asset['id'], {'filename': 'source-edited.png'}, expected_version=reviewed['version'])
    with pytest.raises(ValueError): preview(rig, handoff, body)


def test_real_reopen_and_recreated_owner_do_not_adopt_old_page(rig, handoff, monkeypatch):
    saved = page(rig, handoff)
    body = request([saved])
    before = preview(rig, handoff, body)
    service = reopened(rig)
    alternate = copy.copy(rig); alternate.service = service
    production = owner(AssetProviderRegistry(), monkeypatch, alternate)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(sorted(FEATURES)))
    comic = ComicLayoutsService(service.store.store, rig.novels, rig.chapters, None, service.assets,
                               independent_store=service.store)
    assert preview(rig, ComicTimelineHandoff(comic, production), body) == before
    rig.novels.delete(rig.nid)
    rig.create_project('Recreated owner', nid=rig.nid)
    service.activate(rig.nid, rig.scope, rig.actor)
    with pytest.raises((ValueError, FileNotFoundError)):
        preview(rig, ComicTimelineHandoff(comic, production), body)


def test_missing_owner_is_not_initialized_by_preview(rig, handoff):
    nid = rig.create_project('Unactivated owner')
    scope = {'mode': 'local', 'novel_id': nid}
    with pytest.raises(FileNotFoundError):
        handoff.preview(nid, scope, rig.actor, {'title': 'No provisioning', 'pages': [
            {'id': 'missing', 'version': 1, 'review_digest': '0' * 64, 'duration_ms': 1000}]})
    with handoff.owner.existing_owner_only(), pytest.raises(FileNotFoundError):
        handoff.owner.incarnation(nid)
