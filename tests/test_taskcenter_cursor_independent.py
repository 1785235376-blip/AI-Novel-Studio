"""Independent adversarial checks for the unmounted cursor engine.

All identity epochs and projection digests below are synthetic test inputs.
These checks do not establish original-owner or mounted cursor support. The
HTTP adapter deliberately refuses cursor mode until reliable lifecycle evidence
can be supplied without changing original authority owners.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.experimental.taskcenter_cursor import (
    TaskCenterCursorEngine,
    TaskCenterCursorInvalid,
    TaskCenterCursorRestart,
    TaskCenterCursorUnsupported,
)


def hashed(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


BINDING = hashed({"actor": "synthetic-reader", "project_incarnation": "original-owner-epoch-1",
                  "session_binding_generation": 7, "branch": "synthetic-branch"})
QUERY = hashed({"q": "synthetic-private-search", "failed_only": False,
                "authorities": ["semantic_import"], "sort_version": 1})
ROWS = [{"id": f"synthetic-task-{n}", "revision": n + 1} for n in range(7)]


def options(rows=None, **changes):
    observed = ROWS if rows is None else rows
    return {"binding": BINDING, "query": QUERY, "projection": hashed(observed),
            "observed_total": len(observed), "limit": 2, "supported": True, **changes}


def start(engine, rows=None, **changes):
    page = engine.page(**options(rows, **changes))
    assert page.offset == 0
    return page


def refusal(error, operation, message):
    with pytest.raises(error) as caught:
        operation()
    assert str(caught.value) == message
    assert "synthetic-private-search" not in str(caught.value)
    assert "synthetic-task" not in str(caught.value)


def test_engine_is_explicitly_opted_in_and_default_refusal_has_no_projection():
    engine = TaskCenterCursorEngine()
    values = options()
    values.pop("supported")
    refusal(TaskCenterCursorUnsupported, lambda: engine.page(**values),
            "TASKCENTER_CURSOR_UNSUPPORTED")


@pytest.mark.parametrize("change", [
    {"binding": hashed("another-authorized-actor")},
    {"binding": hashed("another-project-incarnation")},
    {"binding": hashed("another-session-binding-generation")},
    {"binding": hashed("another-branch")},
    {"query": hashed("different-authority-filter")},
    {"query": hashed("different-search")},
    {"limit": 1},
    {"observed_total": len(ROWS) + 1},
])
def test_cross_context_refusal_cannot_poison_the_legitimate_observation(change):
    engine = TaskCenterCursorEngine()
    first = start(engine)
    token = first.next_cursor
    assert token
    refusal(TaskCenterCursorRestart,
            lambda: engine.page(**options(token=token, **change)),
            "TASKCENTER_CURSOR_RESTART_REQUIRED")
    valid = engine.page(**options(token=token))
    assert valid.offset == 2
    assert valid.has_more is True


@pytest.mark.parametrize("change", ["revision-outside-page", "reorder", "same-size-replacement",
                                   "insert", "delete"])
def test_entire_observation_changes_invalidate_even_when_the_requested_page_is_unchanged(change):
    engine = TaskCenterCursorEngine()
    first = start(engine)
    altered = deepcopy(ROWS)
    if change == "revision-outside-page":
        altered[-1]["revision"] += 1
    elif change == "reorder":
        altered[-2:] = reversed(altered[-2:])
    elif change == "same-size-replacement":
        altered[-1] = {"id": "synthetic-task-replacement", "revision": 1}
    elif change == "insert":
        altered.append({"id": "synthetic-task-new", "revision": 1})
    else:
        altered.pop()
    assert altered[2:4] == ROWS[2:4]
    refusal(TaskCenterCursorRestart,
            lambda: engine.page(**options(altered, token=first.next_cursor)),
            "TASKCENTER_CURSOR_RESTART_REQUIRED")


def test_provided_original_epoch_detects_a_b_a_without_claiming_to_mint_an_identity():
    engine = TaskCenterCursorEngine()
    first = start(engine)
    # The original authority must provide a fresh epoch. An equal public slug
    # or restored string is not accepted here as evidence of the original A.
    for binding in (hashed({"public_id": "B", "original_epoch": 2}),
                    hashed({"public_id": "A", "original_epoch": 3})):
        refusal(TaskCenterCursorRestart,
                lambda binding=binding: engine.page(**options(binding=binding, token=first.next_cursor)),
                "TASKCENTER_CURSOR_RESTART_REQUIRED")


def test_capacity_one_allows_replay_and_full_traversal_without_self_eviction():
    engine = TaskCenterCursorEngine(capacity=1)
    first = start(engine, limit=1)
    one = engine.page(**options(limit=1, token=first.next_cursor))
    replay = engine.page(**options(limit=1, token=first.next_cursor))
    assert (one.offset, one.next_cursor, one.has_more) == (
        replay.offset, replay.next_cursor, replay.has_more)
    offsets = [0, one.offset]
    cursor = one.next_cursor
    while cursor is not None:
        page = engine.page(**options(limit=1, token=cursor))
        offsets.append(page.offset)
        cursor = page.next_cursor
    assert offsets == list(range(len(ROWS)))
    assert page.has_more is False
    # Repeated reads do not advance a server-side mutable page pointer.
    assert engine.page(**options(limit=1, token=first.next_cursor)).offset == 1


def test_fifo_capacity_is_bounded_and_reading_does_not_refresh_a_session():
    engine = TaskCenterCursorEngine(capacity=2)
    a = start(engine)
    b = start(engine, query=hashed("query-b"))
    assert engine.page(**options(token=a.next_cursor)).offset == 2
    start(engine, query=hashed("query-c"))
    refusal(TaskCenterCursorRestart,
            lambda: engine.page(**options(token=a.next_cursor)),
            "TASKCENTER_CURSOR_RESTART_REQUIRED")
    assert engine.page(**options(query=hashed("query-b"), token=b.next_cursor)).offset == 2


def test_ttl_is_not_renewed_by_reading_or_issuing_a_successor():
    clock = [100.0]
    engine = TaskCenterCursorEngine(ttl_seconds=10, clock=lambda: clock[0])
    first = start(engine)
    clock[0] = 109.0
    second = engine.page(**options(token=first.next_cursor))
    assert second.offset == 2 and second.next_cursor
    clock[0] = 110.0
    for token in (first.next_cursor, second.next_cursor):
        refusal(TaskCenterCursorRestart,
                lambda token=token: engine.page(**options(token=token)),
                "TASKCENTER_CURSOR_RESTART_REQUIRED")


def test_last_page_must_recheck_expiration_before_returning():
    class Clock:
        now = 100.0
        armed = False
        calls = 0

        def __call__(self):
            if self.armed:
                self.calls += 1
                return 109.0 if self.calls == 1 else 110.0
            return self.now

    clock = Clock()
    engine = TaskCenterCursorEngine(ttl_seconds=10, clock=clock)
    first = start(engine, ROWS[:2], limit=1)
    clock.armed = True
    refusal(TaskCenterCursorRestart,
            lambda: engine.page(**options(ROWS[:2], limit=1, token=first.next_cursor)),
            "TASKCENTER_CURSOR_RESTART_REQUIRED")
    assert clock.calls >= 2


@pytest.mark.parametrize("token", ["", " ", "\t", "\n", "非ASCII", "x" * 161,
                                  "tc1.", "tc1.a.1.b", "tc1." + "A" * 43 + ".01." + "B" * 43])
def test_raw_malformed_tokens_are_bounded_without_echo(token):
    engine = TaskCenterCursorEngine()
    refusal(TaskCenterCursorInvalid, lambda: engine.page(**options(token=token)),
            "TASKCENTER_QUERY_INVALID")


@pytest.mark.parametrize("padding", [" ", "\t", "\n", "\u3000"])
def test_valid_tokens_cannot_be_rescued_by_trimming(padding):
    engine = TaskCenterCursorEngine()
    token = start(engine).next_cursor
    for candidate in (padding + token, token + padding):
        refusal(TaskCenterCursorInvalid, lambda candidate=candidate: engine.page(**options(token=candidate)),
                "TASKCENTER_QUERY_INVALID")


def test_valid_shape_mac_and_position_tampering_have_one_safe_restart_error():
    engine = TaskCenterCursorEngine()
    token = start(engine).next_cursor
    prefix, handle, offset, mac = token.split(".")
    changed_mac = ("A" if mac[0] != "A" else "B") + mac[1:]
    changed_handle = ("A" if handle[0] != "A" else "B") + handle[1:]
    candidates = [f"{prefix}.{handle}.{offset}.{changed_mac}",
                  f"{prefix}.{changed_handle}.{offset}.{mac}",
                  f"{prefix}.{handle}.4.{mac}"]
    for candidate in candidates:
        refusal(TaskCenterCursorRestart, lambda candidate=candidate: engine.page(**options(token=candidate)),
                "TASKCENTER_CURSOR_RESTART_REQUIRED")
    assert engine.page(**options(token=token)).offset == 2


def test_tokens_contain_no_readable_query_projection_or_owner_digest():
    engine = TaskCenterCursorEngine()
    token = start(engine).next_cursor
    assert token.isascii() and len(token) <= 160
    assert "synthetic" not in token
    assert all(value not in token for value in (BINDING, QUERY, hashed(ROWS)))


@pytest.mark.parametrize("change", [{"limit": True}, {"limit": 1.0}, {"limit": "2"},
                                   {"limit": 0}, {"limit": 101}, {"observed_total": True},
                                   {"observed_total": -1}, {"observed_total": 1_000_001},
                                   {"binding": "a" * 63}, {"query": "A" * 64},
                                   {"projection": "z" * 64}])
def test_internal_input_validation_is_strict_and_sanitized(change):
    engine = TaskCenterCursorEngine()
    refusal(TaskCenterCursorInvalid, lambda: engine.page(**options(**change)),
            "TASKCENTER_QUERY_INVALID")


def test_empty_and_single_page_observations_have_no_continuation():
    engine = TaskCenterCursorEngine()
    empty = start(engine, [])
    assert empty.has_more is False and empty.next_cursor is None
    last = start(engine, ROWS[:2], limit=2)
    assert last.has_more is False and last.next_cursor is None


def test_cold_engine_cannot_treat_a_token_as_authority_or_source_data():
    token = start(TaskCenterCursorEngine()).next_cursor
    refusal(TaskCenterCursorRestart,
            lambda: TaskCenterCursorEngine().page(**options(token=token)),
            "TASKCENTER_CURSOR_RESTART_REQUIRED")


def test_independent_process_cannot_continue_the_parent_observation():
    engine = TaskCenterCursorEngine()
    token = start(engine).next_cursor
    script = (
        "import json,sys\n"
        "from app.experimental.taskcenter_cursor import TaskCenterCursorEngine,TaskCenterCursorRestart\n"
        "value=json.load(sys.stdin)\n"
        "try:\n"
        " TaskCenterCursorEngine().page(**value)\n"
        "except TaskCenterCursorRestart:\n"
        " sys.stdout.write('SAFE_RESTART')\n"
        "else:\n"
        " raise AssertionError('foreign process accepted cursor')\n"
    )
    result = subprocess.run([sys.executable, "-c", script],
                            input=json.dumps(options(token=token)), text=True,
                            capture_output=True, timeout=30,
                            cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr
    assert result.stdout == "SAFE_RESTART"


def test_engine_creates_no_visible_or_hidden_durable_cursor_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    business = tmp_path / "synthetic-business"
    business.mkdir()
    (business / ".private-source").write_bytes(b"synthetic-private-source")
    (business / "task.json").write_text('{"version":1}', encoding="utf-8")

    def snapshot():
        return {str(p.relative_to(tmp_path)): (p.stat().st_size, p.stat().st_mtime_ns,
                                               hashlib.sha256(p.read_bytes()).hexdigest())
                for p in tmp_path.rglob("*") if p.is_file()}

    before = snapshot()
    engine = TaskCenterCursorEngine()
    first = start(engine)
    engine.page(**options(token=first.next_cursor))
    assert snapshot() == before


def test_inherited_engine_refuses_repeated_uses_before_touching_a_parent_lock(monkeypatch):
    import app.experimental.taskcenter_cursor as cursor_module

    engine = TaskCenterCursorEngine()
    token = start(engine).next_cursor
    original_pid = os.getpid()
    with monkeypatch.context() as patch:
        patch.setattr(cursor_module.os, "getpid", lambda: original_pid + 1)
        for _ in range(2):
            refusal(TaskCenterCursorRestart,
                    lambda: engine.page(**options(token=token)),
                    "TASKCENTER_CURSOR_RESTART_REQUIRED")
    # PID simulation does not mutate the real parent's observation or key.
    assert engine.page(**options(token=token)).offset == 2


def test_clock_rollback_invalidates_existing_observations():
    clock = [100.0]
    engine = TaskCenterCursorEngine(clock=lambda: clock[0])
    token = start(engine).next_cursor
    clock[0] = 99.0
    refusal(TaskCenterCursorRestart, lambda: engine.page(**options(token=token)),
            "TASKCENTER_CURSOR_RESTART_REQUIRED")
    clock[0] = 101.0
    refusal(TaskCenterCursorRestart, lambda: engine.page(**options(token=token)),
            "TASKCENTER_CURSOR_RESTART_REQUIRED")


@pytest.mark.parametrize("change", [{"ttl_seconds": True}, {"ttl_seconds": 0},
                                   {"ttl_seconds": 901}, {"capacity": 0},
                                   {"capacity": 1025}, {"max_page_size": 101}])
def test_constructor_resource_limits_cannot_be_relaxed_by_implicit_coercion(change):
    refusal(TaskCenterCursorInvalid, lambda: TaskCenterCursorEngine(**change),
            "TASKCENTER_QUERY_INVALID")
