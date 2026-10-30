import hashlib, os, subprocess, sys
from pathlib import Path
from test_studio_canvas_audio_return import audio_canvas, rig, queue, run


def test_candidate_cold_restart(audio_canvas):
    e = audio_canvas
    row = run(e, queue(e))
    assert row['status'] == 'AWAITING_REVIEW'
    expected = row['output_candidate']['digest']
    code = r'''
import hashlib, os, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path.cwd() / 'tests'))
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService
from test_studio_canvas_audio_return import services, production
from app.repositories.file.mutation_coordinator import _locks
root = Path(os.environ['COLD_ROOT'])
bundle = create_repository_bundle(Settings(storage_backend='file', novel_data=root, enable_cloud=False, mock_provider=True), data_root=root)
novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
service = services(root, 'file', '', novels, chapters)
e = SimpleNamespace(root=root, service=service)
nid = os.environ['COLD_NID']; scope = {'mode': 'local', 'novel_id': nid}
print('initial_locks', len(_locks), flush=True)
lock = root / 'assets' / '.workspace-mutation-locks' / (hashlib.sha256(b'asset-library').hexdigest() + '.lock')
assert lock.is_file() and lock.stat().st_size > 0, str(lock)
def snapshot():
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
before = snapshot()
try:
    meta, data = production(e).candidate(nid, scope, 'local-studio-author', 'audio', os.environ['COLD_JOB'], lambda: None)
    print('digest', hashlib.sha256(data).hexdigest(), flush=True)
    assert hashlib.sha256(data).hexdigest() == os.environ['COLD_DIGEST']
finally:
    print('filesystem_bytes_unchanged', snapshot() == before, flush=True)
    assert snapshot() == before

'''
    env = os.environ.copy()
    env.update(COLD_ROOT=str(e.root), COLD_NID=e.nid, COLD_JOB=row['id'], COLD_DIGEST=expected, PYTHONUTF8='1')
    target = Path(os.environ['COLD_TARGET'])
    runchild = subprocess.run([sys.executable, '-c', code], cwd=target, env=env, text=True, capture_output=True, timeout=40)
    print(runchild.stdout, runchild.stderr)
    assert runchild.returncode == 0
import pytest
@pytest.fixture(autouse=True)
def synthetic_seed_only(monkeypatch):
    from app.creative.workspace import IndependentWorkspaceService
    monkeypatch.setattr(IndependentWorkspaceService, '_require_manual_import_capacity', staticmethod(lambda: None))
