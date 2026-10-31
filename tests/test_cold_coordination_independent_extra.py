"""Cold observation must not warm the original strict-only admission state."""
import os
import subprocess
import sys

import pytest

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


@pytest.mark.parametrize('first_observer', [True, False])
def test_cold_observer_and_writer_share_exact_thread_lock(tmp_path, first_observer):
    with workspace_mutation(tmp_path, 'synthetic'):
        pass
    code = r'''
import os, threading
from pathlib import Path
from app.repositories.file import mutation_coordinator as m
root = Path(os.environ['INDEPENDENT_LOCK_ROOT'])
first_observer = os.environ['FIRST_OBSERVER'] == '1'
entered, attempted, second_entered, release = (threading.Event() for _ in range(4))
errors = []
def run(first, observation):
    try:
        if not first:
            assert entered.wait(10)
            attempted.set()
        mode = m.existing_disk_coordination_only() if observation else __import__('contextlib').nullcontext()
        with mode, m.workspace_mutation(root, 'synthetic'):
            if first:
                entered.set()
                assert release.wait(10)
            else:
                second_entered.set()
    except BaseException as exc:
        errors.append(exc)
a = threading.Thread(target=run, args=(True, first_observer))
b = threading.Thread(target=run, args=(False, not first_observer))
a.start(); b.start()
assert attempted.wait(10) and not second_entered.wait(.3)
release.set(); a.join(10); b.join(10)
assert not a.is_alive() and not b.is_alive() and not errors and second_entered.is_set()
with m.existing_coordination_only(), m.workspace_mutation(root, 'synthetic'):
    pass  # the completed ordinary writer legitimately warmed original policy
'''
    env = {**os.environ, 'INDEPENDENT_LOCK_ROOT': str(tmp_path), 'PYTHONUTF8': '1',
           'FIRST_OBSERVER': '1' if first_observer else '0'}
    child = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, timeout=30)
    assert child.returncode == 0, (child.stdout, child.stderr)
