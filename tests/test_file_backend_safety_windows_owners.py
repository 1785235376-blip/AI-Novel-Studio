"""Windows original-owner commit boundaries using synthetic File records.

Spawn + duplex Pipes select exact boundaries; no timing sleeps or notification
of killed synchronization waiters. TerminateProcess is not a power-loss proof.
The original POSIX suite's pure owner helpers are reused without its tests.
"""
from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path

import pytest

from test_taskcenter_rebuilt_process_boundaries import (
    KINDS, append, paired_rows, seed, target,
)

pytestmark = [pytest.mark.file_backend_only,
              pytest.mark.skipif(os.name != 'nt', reason='Windows owner boundary evidence')]


def _controlled_append(root, kind, name, mode, control):
    """Run the real owner; only its existing native-lock/replace calls are gated."""
    from app import storage
    from app.repositories.file import mutation_coordinator

    root = Path(root)
    destination = target(root, kind).resolve()
    original_replace = storage.os.replace
    original_lock = mutation_coordinator._lock_file
    first_lock = True

    def send(phase):
        control.send({'phase': phase, 'kind': kind, 'pid': os.getpid()})

    def replace(source, path):
        if Path(path).resolve() != destination:
            return original_replace(source, path)
        if mode == 'after_replace':
            original_replace(source, path)
        if mode in {'before_replace', 'after_replace', 'hold'}:
            send('COMMIT_READY')
            # The parent terminates crash probes while this exact Pipe receive
            # is blocked. Closing a Pipe never notifies an abandoned Condition.
            if control.recv() != 'COMMIT':
                raise RuntimeError('unexpected commit barrier command')
        elif mode == 'contend':
            send('COMMIT_READY')
        if mode != 'after_replace':
            return original_replace(source, path)

    def lock(handle, **kwargs):
        nonlocal first_lock
        observe = mode == 'contend' and first_lock
        if observe:
            first_lock = False
            send('LOCK_ATTEMPT')
        result = original_lock(handle, **kwargs)
        if observe:
            send('LOCK_ACQUIRED')
        return result

    storage.os.replace = replace
    mutation_coordinator._lock_file = lock
    try:
        append(root, kind, name)
        send('DONE')
    except BaseException as exc:
        control.send({'phase': 'ERROR', 'kind': kind, 'pid': os.getpid(),
                      'error_type': type(exc).__name__, 'error': str(exc)})
        raise
    finally:
        control.close()


def _start(root, kind, name, mode):
    context = mp.get_context('spawn')
    parent, child_end = context.Pipe(duplex=True)
    process = context.Process(target=_controlled_append,
                              args=(str(root), kind, name, mode, child_end))
    process.start()
    child_end.close()
    return process, parent


def _expect(worker, phase):
    process, control = worker
    assert control.poll(40), ('missing process boundary', phase, process.pid, process.exitcode)
    message = control.recv()
    assert message['phase'] == phase and message['pid'] == process.pid, message
    return message


def _finish(worker):
    process, _ = worker
    process.join(20)
    assert not process.is_alive() and process.exitcode == 0, (process.pid, process.exitcode)


def _cleanup(worker):
    if worker is None:
        return
    process, control = worker
    try:
        if process.is_alive():
            process.terminate()
            process.join(20)
        assert not process.is_alive(), ('worker did not exit', process.pid)
    finally:
        control.close()
        if not process.is_alive():
            process.close()


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('boundary', ['before_replace', 'after_replace'])
def test_windows_termination_keeps_business_and_original_lifecycle_paired(tmp_path, kind, boundary):
    seed(tmp_path, kind)
    path = target(tmp_path, kind)
    physical = path.read_bytes()
    ids, metadata = paired_rows(tmp_path, kind)
    worker = _start(tmp_path, kind, 'new', boundary)
    try:
        _expect(worker, 'COMMIT_READY')
        process, _ = worker
        process.terminate()  # multiprocessing's Windows TerminateProcess path.
        process.join(20)
        assert not process.is_alive() and process.exitcode != 0
    finally:
        _cleanup(worker)
    current, evidence = paired_rows(tmp_path, kind)
    assert current == set(evidence) and evidence['seed'] == metadata['seed']
    if boundary == 'before_replace':
        assert path.read_bytes() == physical and current == ids and evidence == metadata
    else:
        assert path.read_bytes() != physical and current == ids | {'new'}
        assert evidence['new'] != evidence['seed']
    reopened = _start(tmp_path, kind, 'reopened', 'plain')
    try:
        _expect(reopened, 'DONE')
        _finish(reopened)
    finally:
        _cleanup(reopened)
    final_ids, final_evidence = paired_rows(tmp_path, kind)
    assert final_ids == set(final_evidence) == current | {'reopened'}
    assert all(final_evidence[key] == value for key, value in evidence.items())
    print('WINDOWS_OWNER_TERMINATE_PROCESS', kind, boundary, 'paired_and_fresh_process_reopened')


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('fault', ['fsync', 'replace'])
def test_windows_failed_commit_preserves_exact_file_and_recovers(tmp_path, kind, fault, monkeypatch):
    from app import storage
    from app.repositories.file import mutation_coordinator

    seed(tmp_path, kind)
    path = target(tmp_path, kind)
    physical, original = path.read_bytes(), paired_rows(tmp_path, kind)
    reached = []

    def fail(*_args, **_kwargs):
        reached.append(fault)
        raise OSError('synthetic commit boundary failure')

    with monkeypatch.context() as patch:
        patch.setattr(storage.os, fault, fail)
        with pytest.raises(OSError, match='synthetic commit boundary failure'):
            append(tmp_path, kind, 'failed')
    assert reached == [fault]
    assert path.read_bytes() == physical and paired_rows(tmp_path, kind) == original
    assert not getattr(mutation_coordinator._thread_state, 'depths', {})
    assert not list(path.parent.glob(path.name + '.*.tmp'))
    reopened = _start(tmp_path, kind, 'recovered', 'plain')
    try:
        _expect(reopened, 'DONE')
        _finish(reopened)
    finally:
        _cleanup(reopened)
    ids, metadata = paired_rows(tmp_path, kind)
    assert ids == set(metadata) == {'seed', 'recovered'}
    assert metadata['seed'] == original[1]['seed']
    print('WINDOWS_OWNER_COMMIT_FAILURE', kind, fault, 'exact_file_and_fresh_process_recovered')


@pytest.mark.parametrize('kind', KINDS)
def test_windows_original_lock_serializes_two_controlled_processes(tmp_path, kind):
    seed(tmp_path, kind)
    physical = target(tmp_path, kind).read_bytes()
    first = _start(tmp_path, kind, 'first', 'hold')
    second = None
    try:
        _expect(first, 'COMMIT_READY')
        second = _start(tmp_path, kind, 'second', 'contend')
        _expect(second, 'LOCK_ATTEMPT')
        # The first process still holds its original writer lease at replace;
        # a payload read is safe here, whereas calling an owner lease would
        # deadlock this coordinating parent. No sleep predicts worker progress.
        assert target(tmp_path, kind).read_bytes() == physical
        assert first[0].is_alive() and second[0].is_alive()
        first[1].send('COMMIT')
        _expect(first, 'DONE')
        _finish(first)
        _expect(second, 'LOCK_ACQUIRED')
        _expect(second, 'COMMIT_READY')
        _expect(second, 'DONE')
        _finish(second)
    finally:
        _cleanup(first)
        _cleanup(second)
    ids, metadata = paired_rows(tmp_path, kind)
    assert ids == set(metadata) == {'seed', 'first', 'second'}
    assert len(set(metadata.values())) == 3
    print('WINDOWS_OWNER_TWO_PROCESS_SERIALIZATION', kind, 'both_commits_preserved')
