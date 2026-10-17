"""Authored copy through original File owner; all artwork is synthetic.

The shared fixture is also asserted against the actual TS duplication helper.
No renderer/font/source/approval contract is replaced for this feature.
"""
import base64
import copy
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from app.config import Settings
from app.experimental.comic_layouts import ComicLayoutsService, licensed_font
from app.experimental.store import ExperimentalStore
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService
from app.services.asset_library_service import AssetLibraryService
from app.services.screenplay_service import ScreenplayService
from app.services.v1_capability_service import CapabilityVersionConflict
from support_reconciliation_test_r3_media_support import rig
from support_reconciliation_test_r4_director import screenplay

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' / 'comic_panel_duplicate.json').read_text())


def synthetic():
    from PIL import Image
    image = Image.new('RGB', (192, 128))
    image.putdata([(x % 256, y % 256, (x + y) % 256) for y in range(128) for x in range(192)])
    stream = io.BytesIO(); image.save(stream, format='PNG'); return stream.getvalue()


def restart(rig):
    # New store, repository bundle and every service, reading only persisted File
    # state. No live rows or in-memory service state cross this boundary.
    config = Settings(storage_backend='file', database_url='', novel_data=rig.root)
    bundle = create_repository_bundle(config, data_root=rig.root)
    return ComicLayoutsService(ExperimentalStore(rig.root, 'file', ''),
                               NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters),
                               ScreenplayService(bundle.novels, bundle.chapters), AssetLibraryService(rig.root))


def authored(rig, text=True):
    service = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    source = screenplay(rig)
    asset = rig.assets.create(rig.nid, 'SYNTHETIC-DUPLICATE.png', base64.b64encode(synthetic()).decode(), 'image/png')
    service.approve_image(rig.nid, rig.scope, rig.actor, asset['id'], asset['version'])
    asset = rig.assets.get(asset['id'])
    document = copy.deepcopy(FIXTURE['document']); duplicate = copy.deepcopy(FIXTURE['expectedPanel'])
    document.update(screenplay_id=source['id'], expected_screenplay_version=source['edit_version'])
    for panel in [document['panels'][0], duplicate]:
        panel.update(shot_id=source['shots'][0]['id'], asset_id=asset['id'], expected_asset_version=asset['version'])
        panel['appearance_references'][0].update(asset_id=asset['id'], expected_asset_version=asset['version'])
        if not text: panel['bubbles'] = []
    return service, source, asset, document, duplicate


def save_pair(rig, text=True):
    service, source, asset, document, duplicate = authored(rig, text)
    original = service.save(rig.nid, rig.scope, rig.actor, document)
    document['panels'].append(duplicate)
    copied = service.save(rig.nid, rig.scope, rig.actor, document, rid=original['id'], expected_version=original['version'])
    assert copied['status'] == 'DRAFT' and copied['document']['panels'][0] == original['document']['panels'][0]
    with pytest.raises(CapabilityVersionConflict):
        service.save(rig.nid, rig.scope, rig.actor, document, rid=original['id'], expected_version=original['version'])
    assert service.records(rig.nid, rig.scope, rig.actor)['items'][0]['version'] == copied['version']
    return service, source, asset, original, copied


def test_authored_unicode_references_and_geometry_survive_real_file_restart(rig):
    if rig.backend != 'file': pytest.skip('File-only restart acceptance')
    service, source, asset, original, copied = save_pair(rig)
    reopened = restart(rig)
    row = reopened.records(rig.nid, rig.scope, rig.actor)['items'][0]
    assert row['document'] == copied['document']
    first, second = row['document']['panels']
    assert second['bubbles'][0] == {**first['bubbles'][0], 'id': 'duplicate-speech', 'x': 168, 'y': 344}
    assert second['appearance_references'] == first['appearance_references']
    report = reopened.preflight(rig.nid, rig.scope, rig.actor, row['id'], row['version'])
    try: licensed_font()
    except ValueError:
        assert not report['can_render']
        assert any(issue['code'] == 'COMIC_PINNED_OFL_CJK_FONT_UNAVAILABLE' for issue in report['issues'])
        with pytest.raises(ValueError, match='BLOCKED'):
            reopened.approve(rig.nid, rig.scope, rig.actor, row['id'], row['version'], report['review_digest'], True)
        with pytest.raises(ValueError, match='BLOCKED'):
            reopened.preview(rig.nid, rig.scope, rig.actor, row['id'], row['version'], 0)
    assert rig.assets.get(asset['id']) == asset
    assert next(row for row in rig.screenplays.list(rig.nid) if row['id'] == source['id']) == source
    restored = reopened.restore(rig.nid, rig.scope, rig.actor, row['id'], row['version'], original['version'])
    assert restored['document'] == original['document'] and restored['status'] == 'DRAFT'


def test_no_text_copy_file_restart_preflight_explicit_review_zip_exact_pixels(rig):
    if rig.backend != 'file': pytest.skip('File-only restart acceptance')
    _, source, asset, original, copied = save_pair(rig, text=False)
    reopened = restart(rig)
    row = reopened.records(rig.nid, rig.scope, rig.actor)['items'][0]
    assert row['document'] == copied['document']
    report = reopened.preflight(rig.nid, rig.scope, rig.actor, row['id'], row['version'])
    assert report['can_render']
    assert report['placements']['authored'] == report['placements']['duplicate'] == {'size': (192, 128), 'offset': (-64, 0)}
    with pytest.raises(ValueError, match='APPROVAL'):
        reopened.export(rig.nid, rig.scope, rig.actor, row['id'], row['version'])
    with pytest.raises(ValueError, match='WARNINGS'):
        reopened.approve(rig.nid, rig.scope, rig.actor, row['id'], row['version'], report['review_digest'], False)
    approved = reopened.approve(rig.nid, rig.scope, rig.actor, row['id'], row['version'], report['review_digest'], True)
    exported = reopened.export(rig.nid, rig.scope, rig.actor, row['id'], approved['version'])
    assert exported == reopened.export(rig.nid, rig.scope, rig.actor, row['id'], approved['version'])
    from PIL import Image
    with zipfile.ZipFile(io.BytesIO(exported)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert len(manifest['segments']) == 2 and manifest['automatic_publication'] is False
        assert manifest['asset_bindings'][asset['id']]['sha256'] == asset['sha256']
        assert manifest['asset_bindings'][asset['id']]['version'] == asset['version']
        original_ref, copied_ref = manifest['panel_sources']
        assert copied_ref == {**original_ref, 'panel_id': 'duplicate'}
        images = []
        for segment in manifest['segments']:
            data = archive.read(segment['filename'])
            assert hashlib.sha256(data).hexdigest() == segment['sha256']
            assert data == reopened.preview(rig.nid, rig.scope, rig.actor, row['id'], approved['version'], segment['index'])
            image = Image.open(io.BytesIO(data)); image.load(); images.append(image)
        assert images[0].crop((16, 16, 144, 144)).tobytes() == images[1].crop((160, 16, 288, 144)).tobytes()
        # Independently inspect positioned crop and untouched surrounding canvas.
        for x, y in [(5, 5), (63, 63), (120, 120)]:
            assert images[0].getpixel((16 + x, 16 + y)) == (x + 64, y, (x + 64 + y) % 256)
        assert images[1].getpixel((159, 16)) == (255, 255, 255)
        assert images[1].getpixel((288, 16)) == (255, 255, 255)
        for image in images: image.close()
    assert rig.assets.get(asset['id']) == asset and len(rig.assets.list(rig.nid)) == 1
    assert next(row for row in rig.screenplays.list(rig.nid) if row['id'] == source['id']) == source
    restored = reopened.restore(rig.nid, rig.scope, rig.actor, row['id'], approved['version'], original['version'])
    assert restored['document'] == original['document'] and restored['status'] == 'DRAFT'


def test_authored_copy_text_pixels_require_real_pinned_font(rig):
    if rig.backend != 'file': pytest.skip('File-only restart acceptance')
    try: licensed_font()
    except ValueError: pytest.skip('BLOCKED: original pinned OFL font unavailable; no rendered Unicode claim')
    _, _, _, _, copied = save_pair(rig)
    reopened = restart(rig)
    report = reopened.preflight(rig.nid, rig.scope, rig.actor, copied['id'], copied['version'])
    assert report['can_render']
    approved = reopened.approve(rig.nid, rig.scope, rig.actor, copied['id'], copied['version'], report['review_digest'], True)
    with zipfile.ZipFile(io.BytesIO(reopened.export(rig.nid, rig.scope, rig.actor, copied['id'], approved['version']))) as archive:
        assert 'OFL.txt' in archive.namelist()
