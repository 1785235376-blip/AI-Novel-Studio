"""Real pinned-font artifact through original Comic owner, synthetic artwork only."""
import hashlib
import io
import json
import os
import zipfile
import pytest
from test_r5_comic_layouts import rig,comic,image_asset,layout,save,preflight,approve
from app.experimental.comic_layouts import ComicLayoutsService,licensed_font
pytestmark=[pytest.mark.file_backend_only,pytest.mark.parametrize('rig',['file'],indirect=True)]


def test_original_approved_cjk_comic_exports_real_glyph_pixels(rig,comic,image_asset,tmp_path):
    if not os.getenv('R2_TEST_FONT_FILE'):pytest.skip('NOT_RUN: original pinned OFL font must be supplied explicitly')
    data,license_data,coverage=licensed_font()
    assert hashlib.sha256(data).hexdigest()=='eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461'
    text='中文对白：请保留每一份创作。'
    assert coverage.issuperset(map(ord,text))
    body=layout(rig,image_asset);body['panels'][0]['bubbles']=[{'id':'cjk-dialogue','text':text,'font_size':32,'x':40,'y':40,'width':680,'height':160}]
    row=save(comic,rig,body);report=preflight(comic,rig,row);assert report['can_render']
    approved=approve(comic,rig,row,report)
    fresh=ComicLayoutsService(rig.store,rig.novels,rig.chapters,rig.screenplays,rig.assets)
    result=fresh.export(rig.nid,rig.scope,rig.actor,row['id'],approved['version'])
    with zipfile.ZipFile(io.BytesIO(result)) as archive:
        assert archive.read('OFL.txt')==license_data
        image=archive.read('segment-001.png');assert image==fresh.preview(rig.nid,rig.scope,rig.actor,row['id'],approved['version'],0)
        from PIL import Image
        decoded=Image.open(io.BytesIO(image));assert len(set(decoded.crop((52,52,670,96)).get_flattened_data()))>20
        manifest=json.loads(archive.read('manifest.json'))
    (tmp_path/'comic-cjk-verified.png').write_bytes(image);(tmp_path/'comic-cjk-verified.zip').write_bytes(result)
    (tmp_path/'comic-cjk-proof.json').write_text(json.dumps({'font_sha256':hashlib.sha256(data).hexdigest(),'png_sha256':hashlib.sha256(image).hexdigest(),'zip_sha256':hashlib.sha256(result).hexdigest(),'text':text,'artwork':'SYNTHETIC_TEST_ASSET','manifest':manifest},ensure_ascii=False,indent=2)+'\n')
