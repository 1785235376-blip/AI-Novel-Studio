"""File scope interruption versus the existing mixed U16 claim sequence."""
import json
import os
import subprocess
import sys

import pytest

from test_studio_asset_query import rig
from test_u16_capacity_claim import instrumented_batch


@pytest.mark.skipif(os.name != 'nt', reason='Windows scoped residue fence')
def test_interrupted_scope_prevents_mixed_batch_claim_and_image_dispatch(rig, monkeypatch):
    # This fixture uses the real File scope owner but explicitly stubs the
    # U16 source/authority checks. It proves claim order, not authorization.
    service, batch, ctx = instrumented_batch(rig, monkeypatch,
        ['STUDIO_IMAGE', 'VOICE_REDO'], ['PENDING', 'PENDING'])
    sent = []
    service.studio_image = type('ImageProbe', (), {
        'dispatch': lambda *_: sent.append('unexpected image side effect')})()
    code = r'''
import json, os
from pathlib import Path
from app.experimental.store import ExperimentalStore
root = Path(os.environ['SYNTHETIC_ROOT'])
scope = json.loads(os.environ['SYNTHETIC_SCOPE'])
def stop_after_fsync(*_): os._exit(73)
os.replace = stop_after_fsync
with ExperimentalStore(root).transaction(scope['novel_id'], scope) as state:
    state['collections']['synthetic-interrupted'] = {'x': {'value': 'synthetic'}}
'''
    env = os.environ.copy()
    env.update(SYNTHETIC_ROOT=str(rig.root), SYNTHETIC_SCOPE=json.dumps(rig.scope), PYTHONUTF8='1')
    child = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, timeout=30)
    assert child.returncode == 73, (child.returncode, child.stderr)
    path = service.store.path(rig.nid, rig.scope)
    leftovers = list(path.parent.glob(path.name + '.*.tmp'))
    assert len(leftovers) == 1
    before_scope, before_residue = path.read_bytes(), leftovers[0].read_bytes()
    with pytest.raises(ValueError, match='EXPERIMENTAL_SCOPE_UNRECONCILED'):
        service.dispatch(ctx, batch['id'], {'expected_version': batch['version']})
    after = service.get(ctx.novel_id, ctx.scope, service.BATCHES, batch['id'])
    assert after['version'] == batch['version']
    assert after['status'] == 'READY' and after['items'][0]['status'] == 'PENDING'
    assert after['items'][0]['attempts'] == 0 and not sent
    assert path.read_bytes() == before_scope and leftovers[0].read_bytes() == before_residue
