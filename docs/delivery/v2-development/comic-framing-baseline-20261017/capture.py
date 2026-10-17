"""Pre-edit legacy capture. No monkeypatches, time/ID hooks, or renderer substitutes."""
import sys, json, hashlib, io, base64
from pathlib import Path
from types import SimpleNamespace
ROOT = Path('/workspace/scratch/20a0022d2b33/studio-comic-framing')
OUT = Path('/workspace/scratch/20a0022d2b33/comic-framing-baseline-r1')
assert not (OUT / 'expected.json').exists(), 'Never overwrite original capture'
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
import PIL, pydantic
from PIL import Image
import app.experimental.comic_layouts as module
from app.experimental.comic_layouts import LayoutIn, ComicLayoutsService, compose
from support_reconciliation_test_r3_media_support import rig
from support_reconciliation_test_r4_director import screenplay
print(json.dumps({'executable': sys.executable, 'prefix': sys.prefix, 'pillow': [PIL.__version__, PIL.__file__], 'pydantic': [pydantic.__version__, pydantic.__file__], 'owner': module.__file__, 'sys_path_inserts': [str(ROOT), str(ROOT / 'tests')]}), flush=True)
assert PIL.__version__ == '12.3.0'
image = Image.new('RGBA', (101, 64))
image.putdata([(x * 2, y * 3, (x + y) % 256, 128 if x % 7 == 0 else 255) for y in range(64) for x in range(101)])
stream = io.BytesIO(); image.save(stream, format='PNG'); pixels = stream.getvalue()
(OUT / 'synthetic-input.png').write_bytes(pixels)
body = {'title': 'SYNTHETIC LEGACY COVER BASELINE', 'screenplay_id': 'fixed-screenplay', 'expected_screenplay_version': 1, 'width': 320, 'height': 320, 'safe_area': 0, 'segment_height': 320, 'panels': [{'id': 'panel', 'shot_id': 'fixed-shot', 'order': 1, 'x': 8, 'y': 8, 'width': 64, 'height': 64, 'asset_id': 'fixed-asset', 'expected_asset_version': 2, 'fit': 'COVER'}]}
document = LayoutIn.model_validate(body).model_dump()
report, outputs = compose(document, {'fixed-asset': pixels}, render=True)
assert report['can_render'] and report['placements']['panel']['offset'] == (-19, 0)
(OUT / 'fixed-center.png').write_bytes(outputs[0])
data = OUT / 'file-data'; data.mkdir()
generator = rig.__wrapped__(SimpleNamespace(param='file'), data)
r = next(generator)
service = ComicLayoutsService(r.store, r.novels, r.chapters, r.screenplays, r.assets)
source = screenplay(r)
a = r.assets.create(r.nid, 'SYNTHETIC-LEGACY-COVER.png', base64.b64encode(pixels).decode(), 'image/png')
a = service.approve_image(r.nid, r.scope, r.actor, a['id'], a['version'])
actual = json.loads(json.dumps(body)); actual.update(screenplay_id=source['id'], expected_screenplay_version=source['edit_version'])
actual['panels'][0].update(shot_id=source['shots'][0]['id'], asset_id=a['id'], expected_asset_version=a['version'])
row = service.save(r.nid, r.scope, r.actor, actual)
before = service.preflight(r.nid, r.scope, r.actor, row['id'], row['version'])
approved = service.approve(r.nid, r.scope, r.actor, row['id'], row['version'], before['review_digest'], True)
after = service.preflight(r.nid, r.scope, r.actor, row['id'], approved['version'])
preview = service.preview(r.nid, r.scope, r.actor, row['id'], approved['version'], 0)
export = service.export(r.nid, r.scope, r.actor, row['id'], approved['version'])
(OUT / 'owner-center.png').write_bytes(preview); (OUT / 'owner-approved.zip').write_bytes(export)
assert outputs[0] == preview
expected = {'capture_source_head': 'd10b72c', 'hooks': [], 'fixed_body': body, 'fixed_document': document, 'fixed_report': report, 'fixed_png_sha256': hashlib.sha256(outputs[0]).hexdigest(), 'nid': r.nid, 'scope': r.scope, 'actor': r.actor, 'approved': approved, 'preflight': after, 'stored': r.store.read(r.nid, r.scope), 'owner_png_sha256': hashlib.sha256(preview).hexdigest(), 'owner_zip_sha256': hashlib.sha256(export).hexdigest(), 'renderer': module.renderer_status(), 'font': module.font_status()}
(OUT / 'expected.json').write_text(json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
print(json.dumps({'review_digest': after['review_digest'], 'png': expected['owner_png_sha256'], 'zip': expected['owner_zip_sha256'], 'font': expected['font'], 'renderer': expected['renderer']}), flush=True)
generator.close()
