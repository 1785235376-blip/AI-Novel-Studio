"""Cold observation must not warm the original strict-only admission state."""
import os
import subprocess
import sys

from app.repositories.file.mutation_coordinator import workspace_mutation


def test_disk_observation_cannot_upgrade_later_strict_request(tmp_path):
    with workspace_mutation(tmp_path, 'synthetic'):
        pass
    child_code = r'''
import os
from pathlib import Path
from app.repositories.file import mutation_coordinator as m
root = Path(os.environ['INDEPENDENT_LOCK_ROOT'])
assert not m._locks
try:
    with m.existing_coordination_only(), m.workspace_mutation(root, 'synthetic'):
        raise AssertionError('original strict unexpectedly admitted cold process')
except m.ReadOnlyCoordinationUnavailable:
    pass
with m.existing_disk_coordination_only(), m.workspace_mutation(root, 'synthetic'):
    pass
try:
    with m.existing_coordination_only(), m.workspace_mutation(root, 'synthetic'):
        raise AssertionError('prior observation warmed strict-only admission')
except m.ReadOnlyCoordinationUnavailable:
    pass
'''
    env = {**os.environ, 'INDEPENDENT_LOCK_ROOT': str(tmp_path), 'PYTHONUTF8': '1'}
    child = subprocess.run([sys.executable, '-c', child_code], env=env, capture_output=True, timeout=30)
    assert child.returncode == 0, (child.stdout, child.stderr)


def test_failed_observation_cannot_warm_later_strict_request(tmp_path):
    child_code = r'''
import os, subprocess, sys
from pathlib import Path
from app.repositories.file import mutation_coordinator as m
root = Path(os.environ['INDEPENDENT_LOCK_ROOT'])
assert not m._locks
try:
    with m.existing_disk_coordination_only(), m.workspace_mutation(root, 'synthetic'):
        raise AssertionError('missing disk lock was admitted')
except m.ReadOnlyCoordinationUnavailable:
    pass
assert not (root / '.workspace-mutation-locks').exists()
writer = "from pathlib import Path; import os; from app.repositories.file.mutation_coordinator import workspace_mutation; " \
         "root=Path(os.environ['INDEPENDENT_LOCK_ROOT']); c=workspace_mutation(root,'synthetic'); c.__enter__(); c.__exit__(None,None,None)"
subprocess.run([sys.executable, '-c', writer], check=True)
try:
    with m.existing_coordination_only(), m.workspace_mutation(root, 'synthetic'):
        raise AssertionError('failed observation warmed strict-only admission')
except m.ReadOnlyCoordinationUnavailable:
    pass
'''
    env = {**os.environ, 'INDEPENDENT_LOCK_ROOT': str(tmp_path), 'PYTHONUTF8': '1'}
    child = subprocess.run([sys.executable, '-c', child_code], env=env, capture_output=True, timeout=30)
    assert child.returncode == 0, (child.stdout, child.stderr)
