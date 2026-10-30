"""Real STYLE read path against a synthetic old File chapter and residue."""
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.experimental.style_dna import StyleDNAService
from app.services.creation_workbench_service import CreationWorkbenchService
from test_studio_asset_query import rig

pytestmark = [pytest.mark.file_backend_only, pytest.mark.skipif(os.name != 'nt', reason='Windows scope fence')]


def test_style_visibility_does_not_materialize_old_chapter_after_scope_crash(rig):
    chapter = rig.workspace.creative.chapters.create(rig.nid, {'title': 'Synthetic old', 'content': 'Synthetic legacy.'})
    path = rig.workspace.creative.chapters.repository._paths(chapter['id'])[2]
    if path.exists():
        path.unlink()  # only the newly created synthetic test fixture
    assert not path.exists()
    identity = rig.workspace.store.incarnation(rig.nid)
    store = rig.workspace.store.store
    with store.transaction(rig.nid, rig.scope) as state:
        state['collections']['synthetic'] = {'before': {'value': 'original'}}
    code = r'''
import os
from pathlib import Path
from app.experimental.store import ExperimentalStore
nid = os.environ['SYNTHETIC_NID']
scope = {'mode': 'local', 'novel_id': nid}
def crash(*_): os._exit(73)
os.replace = crash
with ExperimentalStore(Path(os.environ['SYNTHETIC_ROOT'])).transaction(nid, scope) as state:
    state['collections']['synthetic']['after'] = {'value': 'unfinished'}
'''
    env = os.environ.copy()
    env.update(SYNTHETIC_ROOT=str(rig.root), SYNTHETIC_NID=rig.nid, PYTHONUTF8='1')
    child = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, timeout=30)
    assert child.returncode == 73, (child.returncode, child.stderr)
    scope_path = store.path(rig.nid, rig.scope)
    assert list(scope_path.parent.glob(scope_path.name + '.*.tmp'))
    creation = CreationWorkbenchService(SimpleNamespace(), rig.workspace.creative.chapters, rig.novels)
    creation.style_dna_service = StyleDNAService(rig.workspace.creative, creation)
    row = {'style_dna': {'schema_version': 1, 'global_rules': {'writing_tone': 'synthetic'}, 'overrides': []},
           'style_dna_project_incarnation': identity, 'source_versions': {chapter['id']: 1}, 'history': []}
    try:
        assert creation._style_visible(rig.nid, rig.scope, row) is True
    except ValueError as exc:
        assert str(exc) == 'EXPERIMENTAL_SCOPE_UNRECONCILED'
    assert not path.exists(), 'read-only STYLE visibility must not create a document package'
    with pytest.raises(ValueError, match='^EXPERIMENTAL_SCOPE_UNRECONCILED$'):
        creation._style_public(rig.nid, rig.scope, row)
    assert not path.exists(), 'unreconciled state must not be hidden as ordinary stale'
