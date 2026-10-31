"""Independent review probes. Only isolated files and synthetic workers are used."""
from pathlib import Path
from contextlib import contextmanager
import json
import multiprocessing
import os
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from app import api
from app.idempotency import IdempotencyStore
from test_generation_admission_receipts import _install, _post, _rows, _only_receipt

TIMEOUT = 25


def _check_denied(response, code):
    assert response.status_code == 503, response.text
    assert response.json()['code'] == code
    assert 'private-secret-key' not in response.text
    assert '/private/fs/cache' not in response.text
    assert 'postgresql://' not in response.text


def _assert_replay_fenced(f):
    before = f.store.path.read_bytes()
    count = len(f.starts)
    result = _post(f)
    assert result.status_code == 409, result.text
    assert result.json()['code'] == 'ADMISSION_UNCONFIRMED'
    assert 'job_id' not in result.text
    assert len(f.starts) == count
    assert f.store.path.read_bytes() == before


@pytest.mark.parametrize('terminal_persist_fails', [False, True])
def test_thread_started_then_start_raises_never_redispatches(tmp_path, monkeypatch, terminal_persist_fails):
    f = _install(tmp_path, monkeypatch)
    original_start = threading.Thread.start
    original_save = f.bundle.generations.save
    def started_then_raise(thread):
        is_worker = getattr(thread, '_target', None) is f.manager._run
        result = original_start(thread)
        if is_worker:
            thread.join(TIMEOUT)
            assert not thread.is_alive()
            raise RuntimeError('/private/fs/cache private-secret-key postgresql://secret')
        return result
    def save(value):
        if terminal_persist_fails and value['status'] == 'FAILED':
            raise OSError('/private/fs/cache private-secret-key postgresql://secret')
        return original_save(value)
    monkeypatch.setattr(threading.Thread, 'start', started_then_raise)
    monkeypatch.setattr(f.bundle.generations, 'save', save)
    _check_denied(_post(f), 'GENERATION_ADMISSION_UNCONFIRMED')
    assert len(f.starts) == len(f.runs) == 1
    receipt = _only_receipt(f)
    assert receipt['schema_version'] == 3
    assert receipt['job_id'] == f.runs[0]
    _assert_replay_fenced(f)


@pytest.mark.parametrize('boundary', ['auth', 'thread-start'])
def test_other_process_store_write_completes_while_admission_paused(tmp_path, monkeypatch, boundary):
    f = _install(tmp_path, monkeypatch)
    paused, release = threading.Event(), threading.Event()
    original_context = api._generation_request_context
    calls = 0
    def pause():
        paused.set()
        assert release.wait(TIMEOUT), 'release missing'
    def context(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = original_context(*args, **kwargs)
        if calls == 4:
            pause()
        return result
    if boundary == 'auth':
        monkeypatch.setattr(api, '_generation_request_context', context)
    else:
        f.control.before_start = lambda job: pause()
    result = {}
    thread = threading.Thread(target=lambda: result.setdefault('response', _post(f)))
    thread.start()
    try:
        assert paused.wait(TIMEOUT)
        assert _only_receipt(f)['schema_version'] == 3
        ctx = multiprocessing.get_context('spawn')
        process = ctx.Process(target=_ordinary_write, args=(str(f.store.path),))
        process.start()
        process.join(TIMEOUT)
        assert process.exitcode == 0, 'ordinary put blocked behind active admission'
        assert _rows(f)['ordinary-independent']['value'] == {'kept': True}
        assert thread.is_alive()
    finally:
        release.set()
        thread.join(TIMEOUT)
    assert not thread.is_alive()
    assert result['response'].status_code == 202, result['response'].text
    assert len(f.starts) == 1
    assert _rows(f)['ordinary-independent']['value'] == {'kept': True}


def _ordinary_write(path):
    IdempotencyStore(Path(path)).put('ordinary-independent', {'kept': True})


def _exit_after_started(root, connection):
    with pytest.MonkeyPatch.context() as mp:
        f = _install(Path(root), mp, initialize=False)
        original = f.store.put
        def put(key, value):
            if value.get('schema_version') == 2:
                connection.send({'job_id': value['result']['job_id'], 'starts': len(f.starts)})
                os._exit(74)
            return original(key, value)
        mp.setattr(f.store, 'put', put)
        _post(f)
    os._exit(99)


def test_real_exit_after_thread_start_before_complete_receipt(tmp_path, monkeypatch):
    f = _install(tmp_path, monkeypatch)
    ctx = multiprocessing.get_context('spawn')
    parent, child = ctx.Pipe()
    process = ctx.Process(target=_exit_after_started, args=(str(tmp_path), child))
    process.start(); child.close()
    try:
        assert parent.poll(TIMEOUT)
        started = parent.recv()
        process.join(TIMEOUT)
        assert process.exitcode == 74
        assert started['starts'] == 1
        receipt = _only_receipt(f)
        assert receipt['schema_version'] == 3
        assert receipt['job_id'] == started['job_id']
        restarted = _install(tmp_path, monkeypatch, initialize=False)
        _assert_replay_fenced(restarted)
        assert not restarted.starts
        assert restarted.manager.persistence.get(receipt['job_id'])['status'] == 'FAILED'
    finally:
        if process.is_alive(): process.terminate()
        process.join(TIMEOUT); parent.close()


def test_legacy_complete_receipt_shape_replays_without_preparing(tmp_path, monkeypatch):
    f = _install(tmp_path, monkeypatch)
    accepted = _post(f)
    assert accepted.status_code == 202
    rows = _rows(f)
    entry = next(iter(rows.values()))
    entry['value']['result']['job_id'] = 'legacy-job-identifier'
    entry['value']['result']['events_url'] = '/api/generation/legacy-job-identifier/events'
    f.store.path.write_text(json.dumps(rows))
    monkeypatch.setattr(f.manager, 'prepare_job', lambda *a, **k: pytest.fail('old complete receipt must not prepare'))
    before = f.store.path.read_bytes()
    replay = _post(f)
    assert replay.status_code == 202, replay.text
    assert replay.json() == entry['value']['result']
    assert f.store.path.read_bytes() == before
    assert len(f.starts) == 1
