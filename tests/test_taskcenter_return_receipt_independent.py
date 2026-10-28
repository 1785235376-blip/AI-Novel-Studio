"""Independent engine receipt lifetime checks; no HTTP or permission substitution."""
from dataclasses import replace
import math
import os

import pytest

from app.experimental.taskcenter_cursor import (
    CursorPage, TaskCenterCursorEngine, TaskCenterCursorRestart,
    TaskCenterCursorUnsupported,
)


def options(total=3, **changes):
    return dict(binding='a'*64, query='b'*64, projection='c'*64,
                observed_total=total, limit=1, supported=True, **changes)


def setup(total=3, **changes):
    clock = [100.0]
    engine = TaskCenterCursorEngine(ttl_seconds=10, capacity=1,
                                    clock=lambda: clock[0], **changes)
    return engine, clock, engine.page(**options(total))


@pytest.mark.parametrize('total', [0, 1, 3])
def test_exact_deadline_rejects_even_ephemeral_first_page(total):
    engine, clock, page = setup(total)
    clock[0] = 109.999
    engine.validate_return(page)
    clock[0] = 110.0
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(page)


@pytest.mark.parametrize('total', [0, 1, 3])
def test_other_engine_and_receiptless_page_are_rejected(total):
    engine, clock, page = setup(total)
    other = TaskCenterCursorEngine(clock=lambda: clock[0])
    with pytest.raises(TaskCenterCursorRestart):
        other.validate_return(page)
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(CursorPage(page.offset, page.next_cursor, page.has_more))
    engine.validate_return(page)


@pytest.mark.parametrize('change', [{'offset': 1}, {'next_cursor': 'changed'},
                                   {'has_more': False}, {'_receipt': object()}])
def test_replaced_page_position_is_rejected_without_poisoning(change):
    engine, _, page = setup()
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(replace(page, **change))
    engine.validate_return(page)


@pytest.mark.parametrize('change', [{'offset': False}, {'offset': 0.0}, {'has_more': 1}])
def test_type_coercion_cannot_rescue_replaced_position(change):
    engine, _, page = setup()
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(replace(page, **change))


def test_eviction_rejects_old_issued_page_and_accepts_new_one():
    engine, _, first = setup()
    second = engine.page(**options())
    assert len(engine._states) == 1
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(first)
    engine.validate_return(second)


def test_final_page_replay_and_validation_never_allocate_or_renew():
    engine, clock, first = setup(2)
    before = list(engine._states.items())
    clock[0] = 109
    last = engine.page(**options(2, token=first.next_cursor))
    assert last.has_more is False and last.next_cursor is None
    for _ in range(3):
        engine.validate_return(first)
        engine.validate_return(last)
        again = engine.page(**options(2, token=first.next_cursor))
        engine.validate_return(again)
        assert list(engine._states.items()) == before
    clock[0] = 110
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(last)
    assert len(engine._states) == 0


@pytest.mark.parametrize('total', [0, 1])
def test_ephemeral_pages_never_allocate_observation(total):
    engine, _, page = setup(total)
    for _ in range(4):
        engine.validate_return(page)
    assert not engine._states


@pytest.mark.parametrize('total', [0, 3])
def test_fork_guard_runs_before_acquiring_inherited_lock(total, monkeypatch):
    engine, _, page = setup(total)
    class ForbiddenLock:
        def __enter__(self):
            pytest.fail('inherited engine lock was acquired')
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(engine, '_lock', ForbiddenLock())
    monkeypatch.setattr(os, 'getpid', lambda: engine._pid + 1)
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(page)


@pytest.mark.parametrize('total', [0, 3])
@pytest.mark.parametrize('bad', [math.nan, math.inf, -1.0, True])
def test_invalid_clock_invalidates_old_receipts_after_recovery(total, bad):
    engine, clock, page = setup(total)
    clock[0] = bad
    with pytest.raises(TaskCenterCursorUnsupported):
        engine.validate_return(page)
    clock[0] = 101.0
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(page)
    fresh = engine.page(**options(total))
    engine.validate_return(fresh)


@pytest.mark.parametrize('total', [0, 3])
def test_rollback_invalidates_receipts_without_resurrection(total):
    engine, clock, page = setup(total)
    clock[0] = 99.0
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(page)
    clock[0] = 101.0
    with pytest.raises(TaskCenterCursorRestart):
        engine.validate_return(page)
    engine.validate_return(engine.page(**options(total)))


def test_internal_receipt_is_not_in_page_repr():
    _, _, page = setup()
    value = repr(page)
    assert '_ReturnReceipt' not in value and 'deadline' not in value
    assert '_receipt' not in value and "'a'" not in value

# Mounted original-owner route checks, separate from engine-only evidence above.
from test_taskcenter_lifecycle_http import cursor_rig, rig
from test_taskcenter_local_mixed_http import mixed, get as mixed_get, snapshot


@pytest.mark.file_backend_only
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('continuation', [False, True])
@pytest.mark.parametrize('event', ['engine_swap', 'clock_rollback', 'eviction', 'authorization_denial'])
def test_final_mixed_observation_cannot_return_changed_engine_state(mixed, prefix, continuation, event):
    from fastapi import HTTPException
    e = mixed
    clock = [100.0]
    engine = TaskCenterCursorEngine(ttl_seconds=10, capacity=1, clock=lambda: clock[0])
    e.monkeypatch.setattr(e.adapter, 'engine', engine)
    params = {}
    if continuation:
        first = mixed_get(e, prefix=prefix)
        assert first.status_code == 200, first.text
        params['cursor'] = first.json()['next_cursor']
    before = snapshot(e.rig.root)
    component = e.adapter.components['exports']
    original = component._checked_capture
    calls = []
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(True)
        if len(calls) == 3:
            if event == 'engine_swap':
                e.monkeypatch.setattr(e.adapter, 'engine', TaskCenterCursorEngine())
            elif event == 'clock_rollback':
                clock[0] = 99.0
            elif event == 'eviction':
                engine.page(**options())
            else:
                # The final original authorization error must win over the
                # new expired receipt check, not be remapped to restart.
                clock[0] = 110.0
                raise HTTPException(403, {'code': 'SYNTHETIC_FINAL_AUTHORITY_DENIAL'})
        return result
    e.monkeypatch.setattr(component, '_checked_capture', changed)
    response = mixed_get(e, params, prefix)
    assert len(calls) == 3
    assert response.status_code == (403 if event == 'authorization_denial' else 409), response.text
    assert response.headers['cache-control'] == 'no-store'
    assert 'items' not in response.json()
    assert snapshot(e.rig.root) == before
