"""Cold-process coordination uses existing lock files without disk writes."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from app.repositories.file.mutation_coordinator import (
    ReadOnlyCoordinationUnavailable, existing_disk_coordination_only, workspace_mutation,
)


def _files(root):
    found = {}
    for path in root.rglob('*'):
        if path.is_file():
            info = path.stat()
            found[str(path.relative_to(root))] = (info.st_dev, info.st_ino, info.st_size,
                                                  hashlib.sha256(path.read_bytes()).hexdigest())
    return found


def _child(root, code):
    env = os.environ.copy()
    env.update(COORDINATION_TEST_ROOT=str(root), PYTHONUTF8='1')
    return subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, timeout=30)


def test_cold_process_registers_memory_lock_without_disk_changes(tmp_path):
    with workspace_mutation(tmp_path, 'synthetic'):
        pass
    before = _files(tmp_path)
    code = r'''
import os
from pathlib import Path
from app.repositories.file import mutation_coordinator as m
root = Path(os.environ['COORDINATION_TEST_ROOT'])
assert not m._locks
with m.existing_disk_coordination_only(), m.workspace_mutation(root, 'synthetic'):
    assert len(m._locks) == 1
'''
    child = _child(tmp_path, code)
    assert child.returncode == 0, (child.stdout, child.stderr)
    assert _files(tmp_path) == before


def test_missing_disk_lock_never_created_in_cold_process(tmp_path):
    before = _files(tmp_path)
    code = r'''
import os
from pathlib import Path
from app.repositories.file import mutation_coordinator as m
root = Path(os.environ['COORDINATION_TEST_ROOT'])
assert not m._locks
try:
    with m.existing_disk_coordination_only(), m.workspace_mutation(root, 'synthetic'):
        raise AssertionError('missing file must not be admitted')
except m.ReadOnlyCoordinationUnavailable:
    pass
'''
    child = _child(tmp_path, code)
    assert child.returncode == 0, (child.stdout, child.stderr)
    assert _files(tmp_path) == before and not (tmp_path / '.workspace-mutation-locks').exists()


def test_warm_memory_lock_does_not_replace_missing_disk_lock(tmp_path):
    with workspace_mutation(tmp_path, 'synthetic'):
        pass
    path = tmp_path / '.workspace-mutation-locks' / (hashlib.sha256(b'synthetic').hexdigest() + '.lock')
    path.unlink()  # this test's synthetic lock only
    before = _files(tmp_path)
    with pytest.raises(ReadOnlyCoordinationUnavailable):
        with existing_disk_coordination_only(), workspace_mutation(tmp_path, 'synthetic'):
            pytest.fail('memory lock must not replace a missing disk lock')
    assert _files(tmp_path) == before and not path.exists()


def test_explicit_strict_nesting_never_weakens_existing_policy(tmp_path):
    with workspace_mutation(tmp_path, 'synthetic'):
        pass
    before = _files(tmp_path)
    code = r'''
import os
from pathlib import Path
from app.repositories.file import mutation_coordinator as m
root = Path(os.environ['COORDINATION_TEST_ROOT'])
assert not m._locks
for outer, inner in [(m.existing_coordination_only, m.existing_disk_coordination_only),
                     (m.existing_disk_coordination_only, m.existing_coordination_only)]:
    try:
        with outer(), inner(), m.workspace_mutation(root, 'synthetic'):
            raise AssertionError('strict inner/outer must not register a lock')
    except m.ReadOnlyCoordinationUnavailable:
        pass
assert not m._locks
'''
    child = _child(tmp_path, code)
    assert child.returncode == 0, (child.stdout, child.stderr)
    assert _files(tmp_path) == before


def test_independent_request_clears_inherited_memory_permission(tmp_path):
    with workspace_mutation(tmp_path, 'synthetic'):
        pass
    before = _files(tmp_path)
    code = r'''
import os
from pathlib import Path
from app.repositories.file import mutation_coordinator as m
root=Path(os.environ['COORDINATION_TEST_ROOT'])
assert not m._locks
with m.existing_disk_coordination_only():
    with m.isolate_coordination_request_context(), m.existing_coordination_only():
        try:
            with m.workspace_mutation(root, 'synthetic'):
                raise AssertionError('independent strict request must not inherit memory permission')
        except m.ReadOnlyCoordinationUnavailable:
            pass
assert not m._locks
'''
    child = _child(tmp_path, code)
    assert child.returncode == 0, (child.stdout, child.stderr)
    assert _files(tmp_path) == before


def test_cold_threads_share_one_original_process_lock(tmp_path):
    with workspace_mutation(tmp_path, 'synthetic'):
        pass
    before = _files(tmp_path)
    code = r'''
import os, threading
from pathlib import Path
from app.repositories.file import mutation_coordinator as m
root = Path(os.environ['COORDINATION_TEST_ROOT'])
entered, second_entered, release = threading.Event(), threading.Event(), threading.Event()
errors = []
def first():
    try:
        with m.existing_disk_coordination_only(), m.workspace_mutation(root, 'synthetic'):
            entered.set()
            assert release.wait(10)
    except BaseException as exc: errors.append(exc)
def second():
    try:
        assert entered.wait(10)
        with m.existing_disk_coordination_only(), m.workspace_mutation(root, 'synthetic'):
            second_entered.set()
    except BaseException as exc: errors.append(exc)
a, b = threading.Thread(target=first), threading.Thread(target=second)
a.start(); b.start()
assert entered.wait(10)
assert not second_entered.wait(.3)
release.set(); a.join(10); b.join(10)
assert not a.is_alive() and not b.is_alive() and not errors and second_entered.is_set()
assert len(m._locks) == 1
'''
    child = _child(tmp_path, code)
    assert child.returncode == 0, (child.stdout, child.stderr)
    assert _files(tmp_path) == before


def test_existing_disk_observation_waits_for_cooperating_process(tmp_path):
    with workspace_mutation(tmp_path, 'synthetic'):
        pass
    before = _files(tmp_path)
    ready, release = tmp_path / 'ready', tmp_path / 'release'
    code1 = r'''
import os, time
from pathlib import Path
from app.repositories.file.mutation_coordinator import workspace_mutation
root=Path(os.environ['COORDINATION_TEST_ROOT'])
with workspace_mutation(root, 'synthetic'):
    Path(os.environ['COORDINATION_READY']).write_text('ready', encoding='utf-8')
    deadline=time.monotonic()+15
    while not Path(os.environ['COORDINATION_RELEASE']).exists():
        if time.monotonic() >= deadline: raise RuntimeError('wait timeout')
        time.sleep(.02)
'''
    code2 = r'''
import os
from pathlib import Path
from app.repositories.file.mutation_coordinator import workspace_mutation, existing_disk_coordination_only
with existing_disk_coordination_only(), workspace_mutation(Path(os.environ['COORDINATION_TEST_ROOT']), 'synthetic'):
    pass
'''
    env = os.environ.copy()
    env.update(COORDINATION_TEST_ROOT=str(tmp_path), COORDINATION_READY=str(ready),
               COORDINATION_RELEASE=str(release), PYTHONUTF8='1')
    first = subprocess.Popen([sys.executable, '-c', code1], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    second = None
    try:
        deadline = time.monotonic() + 15
        while not ready.exists():
            assert first.poll() is None and time.monotonic() < deadline
            time.sleep(.02)
        second = subprocess.Popen([sys.executable, '-c', code2], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(.4)
        assert second.poll() is None
        release.write_text('release', encoding='utf-8')
        out1, err1 = first.communicate(timeout=20)
        out2, err2 = second.communicate(timeout=20)
        assert first.returncode == second.returncode == 0, (out1, err1, out2, err2)
    finally:
        if first.poll() is None: first.kill(); first.wait(timeout=10)
        if second is not None and second.poll() is None: second.kill(); second.wait(timeout=10)
    # Harness synchronization files are not coordination facilities.
    after = _files(tmp_path)
    after.pop('ready'); after.pop('release')
    assert after == before
