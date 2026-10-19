"""File service routing: ORA pins stay separate from generic Comic images.

Real PNGs and original review owners are used. The Studio transport fixture is
an in-process synthetic HTTP response; no model or live request is executed.
"""
import base64
from contextlib import nullcontext
from copy import deepcopy
import io

from PIL import Image
import pytest

from app.experimental.common import StaleSourceError
from app.services.comic_ora_origin import CONTRACT, FIELD
from test_v2_independent_workspace import rig, png_bytes
from test_comic_ora_staging import staging, prepare, stage
from test_comic_ora_review_attach import reviewed, page, attach
from test_v2_comic_image_generation import comic_image, queue, execute, review

pytestmark = [pytest.mark.file_backend_only,
              pytest.mark.parametrize('rig', ['file'], indirect=True)]


@pytest.mark.parametrize('bound', [False, True], ids=['project-fallback', 'bound-scope'])
@pytest.mark.parametrize('promoted', [False, True], ids=['private-stage', 'reviewed'])
def test_generic_ora_refusal_is_not_found_before_bytes(rig, staging, monkeypatch, bound, promoted):
    row = prepare(rig, staging); stage(rig, staging, row)
    if promoted:
        reviewed(rig, staging, row)
    aid = row['steps'][0]['asset_id']
    before = deepcopy(rig.assets._load(aid))
    assert before[FIELD]['contract'] == CONTRACT
    assert before['version'] == (2 if promoted else 1)
    calls = []
    def forbidden(*_args, **_kwargs):
        calls.append(True)
        pytest.fail('generic ORA refusal reached a byte reader')
    monkeypatch.setattr(rig.assets, 'content', forbidden)
    monkeypatch.setattr(rig.assets, '_verified_content', forbidden)
    scope = rig.service._asset_scope(rig.nid, rig.scope) if bound else nullcontext()
    with scope:
        with pytest.raises(FileNotFoundError) as error:
            staging.comic._asset(rig.nid, rig.scope, rig.actor, aid)
    assert error.value.args == (aid,)
    assert calls == [] and rig.assets._load(aid) == before


@pytest.mark.parametrize('bound', [False, True], ids=['project-fallback', 'bound-scope'])
def test_reviewed_ora_keeps_original_raster_pin_reader(rig, staging, monkeypatch, bound):
    row = prepare(rig, staging); stage(rig, staging, row)
    result = attach(rig, staging, reviewed(rig, staging, row), page(rig, staging))
    item = result['page']['document']['layer_stack']['items'][0]
    before = deepcopy(rig.assets._load(item['target_id']))
    raw = rig.assets._bin_path(item['target_id']).read_bytes()
    scope = rig.service._asset_scope(rig.nid, rig.scope) if bound else nullcontext()
    with scope:
        meta, actual = staging.comic._raster_asset(rig.nid, rig.scope, rig.actor, item)
    assert actual == raw and meta['version'] == 2
    assert meta['_comic_ora_review']['review_digest'] == item['pin']['review_digest']
    with Image.open(io.BytesIO(actual)) as image:
        image.load(); assert image.format == 'PNG' and image.size == (item['width'], item['height'])
    changed = deepcopy(item); changed['pin']['sha256'] = '0' * 64
    def forbidden(*_args, **_kwargs):
        pytest.fail('invalid ORA pin reached the byte reader')
    monkeypatch.setattr(rig.assets, 'content', forbidden)
    scope = rig.service._asset_scope(rig.nid, rig.scope) if bound else nullcontext()
    with scope, pytest.raises(StaleSourceError, match='^COMIC_RASTER_REVIEW_CHANGED$'):
        staging.comic._raster_asset(rig.nid, rig.scope, rig.actor, changed)
    assert rig.assets._load(item['target_id']) == before


def test_ordinary_upload_keeps_original_manual_review_and_generic_read(rig, staging):
    raw = png_bytes()
    asset = rig.assets.create(rig.nid, 'SYNTHETIC-unbound-upload.png',
        base64.b64encode(raw).decode(), 'image/png', 'image')
    approved = staging.comic.approve_image(rig.nid, rig.scope, rig.actor, asset['id'], 1)
    before = deepcopy(rig.assets._load(asset['id']))
    meta, actual = staging.comic._asset(rig.nid, rig.scope, rig.actor, asset['id'])
    assert actual == raw and meta['version'] == approved['version'] == 2
    assert FIELD not in meta and '_studio_result_origin' not in meta
    assert rig.assets._load(asset['id']) == before


@pytest.mark.parametrize('bound', [False, True], ids=['project-fallback', 'bound-scope'])
def test_studio_image_keeps_original_review_and_generic_read(comic_image, bound):
    e = comic_image
    result = review(e, execute(e, queue(e)))
    assert result['status'] == 'APPROVED' and len(e.posts) == 1
    aid = result['output_candidate']['id']
    before = deepcopy(e.assets._load(aid))
    assert FIELD not in before and before['_studio_result_origin']['operation_id'].startswith('m5.image.')
    scope = e.service._asset_scope(e.nid, e.scope) if bound else nullcontext()
    with scope:
        meta, actual = e.comic._asset(e.nid, e.scope, e.actor, aid)
    assert actual == e.pixels and meta['version'] == result['approved_asset_version']
    assert e.assets._load(aid) == before and len(e.posts) == 1


@pytest.mark.parametrize('bound', [False, True], ids=['project-fallback', 'bound-scope'])
@pytest.mark.parametrize('marker', [None, CONTRACT, {'contract': 'unknown-private-stage/1'},
    {'contract': 'comic-ora-private-stage/2'}], ids=['null', 'string', 'unknown', 'other-version'])
def test_classifier_does_not_relabel_unknown_marker_as_ora(rig, staging, monkeypatch, bound, marker):
    # Project only the metadata seen by the dispatcher. Original owner admission
    # remains untouched; this is not a claim that malformed metadata is readable.
    projected = {FIELD: marker}
    monkeypatch.setattr(rig.assets, 'get', lambda *_args, **_kwargs: projected)
    def missing(*_args, **_kwargs):
        raise FileNotFoundError('synthetic legacy namespace miss')
    def forbidden(*_args, **_kwargs):
        pytest.fail('unknown-origin review failure reached the byte reader')
    monkeypatch.setattr(staging.comic, '_read_asset', missing)
    monkeypatch.setattr(rig.assets, 'content', forbidden)
    scope = rig.service._asset_scope(rig.nid, rig.scope) if bound else nullcontext()
    with scope, pytest.raises(ValueError, match='^COMIC_USE_ORIGINAL_GENERATION_REVIEW$'):
        staging.comic._asset(rig.nid, rig.scope, rig.actor, 'synthetic-unknown-origin')
