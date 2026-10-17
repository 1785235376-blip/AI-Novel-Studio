"""Compare new owner to untouched pre-edit capture, using a data copy."""
import sys, json, hashlib, shutil, argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--work', type=Path, required=True)
args = parser.parse_args()
ROOT = args.source.resolve()
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from app.experimental.comic_layouts import ComicLayoutsService, LayoutIn, LayoutEdit, compose, renderer_status, font_status
from app.config import Settings
from app.experimental.store import ExperimentalStore
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService
from app.services.asset_library_service import AssetLibraryService
from app.services.screenplay_service import ScreenplayService
expected = json.loads((BASE / 'expected.json').read_text())
assert renderer_status() == expected['renderer'] and font_status() == expected['font']
document = LayoutIn.model_validate(expected['fixed_body']).model_dump()
assert document == expected['fixed_document']
assert LayoutIn.model_validate(LayoutEdit.model_validate({**document, 'expected_version': 4}).model_dump(exclude={'expected_version'})).model_dump() == document
report, png = compose(document, {'fixed-asset': (BASE / 'synthetic-input.png').read_bytes()}, render=True)
assert json.loads(json.dumps(report)) == expected['fixed_report']
assert png[0] == (BASE / 'fixed-center.png').read_bytes()
target = args.work.resolve(); assert not target.exists(); shutil.copytree(BASE / 'file-data', target)
config = Settings(storage_backend='file', database_url='', novel_data=target)
bundle = create_repository_bundle(config, data_root=target)
novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
store = ExperimentalStore(target, 'file', '')
owner = ComicLayoutsService(store, novels, chapters, ScreenplayService(bundle.novels, bundle.chapters), AssetLibraryService(target))
nid, scope, actor, row = (expected[k] for k in ('nid', 'scope', 'actor', 'approved'))
assert store.read(nid, scope) == expected['stored']
assert owner.records(nid, scope, actor)['items'][0] == row
actual = owner.preflight(nid, scope, actor, row['id'], row['version'])
assert actual['review_digest'] == expected['preflight']['review_digest']
assert json.loads(json.dumps(actual)) == expected['preflight']
assert owner.preview(nid, scope, actor, row['id'], row['version'], 0) == (BASE / 'owner-center.png').read_bytes()
assert owner.export(nid, scope, actor, row['id'], row['version']) == (BASE / 'owner-approved.zip').read_bytes()
assert store.read(nid, scope) == expected['stored']
print(json.dumps({'legacy_normalized_document': 'EXACT', 'legacy_report': 'EXACT', 'approved_row': 'EXACT_WITHOUT_REAPPROVAL', 'stored_state': 'UNCHANGED', 'png': 'BYTE_EXACT', 'zip': 'BYTE_EXACT', 'review_digest': actual['review_digest']}))
