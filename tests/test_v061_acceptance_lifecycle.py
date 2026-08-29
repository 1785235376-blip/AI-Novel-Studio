from datetime import datetime, timedelta, timezone
import os

from scripts import v061_acceptance_supervisor as supervisor
from scripts.v061_process_ownership import ProcessEvidence, process_identity
from scripts.v061_process_ownership import terminate_if_still_owned


cleanup_targets = supervisor.cleanup_targets


def state(run="current", fastapi=None, preview=None):
    return {"run_id": run, "services": {"fastapi": fastapi or {}, "preview": preview or {}}}


def service(run="current", launcher=10, listener=20):
    return {"run_id": run, "launcher_pid": launcher, "listener_pid": listener}


def test_normal_spawn_ready_state_is_cleanup_addressable():
    assert cleanup_targets(state(fastapi=service())) == [20, 10]


def test_descendant_listener_and_launcher_are_both_tracked():
    assert cleanup_targets(state(fastapi=service(launcher=11, listener=12))) == [12, 11]


def test_process_exit_before_listener_leaves_launcher_cleanup_target():
    assert cleanup_targets(state(fastapi=service(listener=0))) == [10]


def test_timeout_partial_state_remains_cleanup_addressable():
    assert cleanup_targets(state(fastapi=service(), preview=service(launcher=30, listener=0))) == [30, 20, 10]


def test_partial_startup_cleans_all_recorded_services():
    assert cleanup_targets(state(fastapi=service(), preview=service(launcher=30, listener=31))) == [31, 30, 20, 10]


def test_parent_exited_child_survives_is_still_cleanup_targeted():
    assert cleanup_targets(state(fastapi=service(launcher=0, listener=22))) == [22]


def test_cleanup_target_discovery_is_idempotent():
    value = state(fastapi=service())
    assert cleanup_targets(value) == cleanup_targets(value)


def test_unrelated_same_executable_run_is_untouched():
    assert cleanup_targets(state(fastapi=service(run="other"))) == []


def test_pid_reuse_protection_rejects_prior_run_record():
    assert cleanup_targets(state(run="new", fastapi=service(run="old"))) == []


def test_stale_prior_run_manifest_is_not_current():
    assert cleanup_targets({"run_id": "new", "services": {"fastapi": service(run="old")}}) == []


NOW = datetime.now(timezone.utc)


def evidence(pid, parent=None, *, exe=r"C:\runtime\python.exe", argv=("owned.py",), port=None):
    return ProcessEvidence(pid, parent, NOW, exe, argv, port)


def verified_state(*, run="current", identity_run="current", created=NOW):
    current = ProcessEvidence(20, 10, created, r"C:\runtime\python.exe", ("owned.py",), 59880)
    identity = process_identity(run_id=identity_run, role="fastapi_listener", evidence=evidence(20, 10, port=59880))
    return {
        "run_id": run,
        "services": {
            "fastapi": {
                "run_id": run,
                "identities": {"listener": identity},
            }
        },
    }, current


def test_verified_cleanup_allows_same_run_same_identity(monkeypatch):
    value, current = verified_state()
    monkeypatch.setattr(supervisor, "inspect_process", lambda pid, port=None: current)
    assert supervisor.verified_cleanup_targets(value) == ([20], [])


def test_verified_cleanup_rejects_cross_run_manifest(monkeypatch):
    value, current = verified_state(identity_run="other")
    monkeypatch.setattr(supervisor, "inspect_process", lambda pid, port=None: current)
    targets, rejected = supervisor.verified_cleanup_targets(value)
    assert targets == []
    assert rejected[0]["reason"] == "RUN_ID_MISMATCH"


def test_verified_cleanup_rejects_reused_pid(monkeypatch):
    value, _ = verified_state()
    reused = evidence(20, 10, argv=("unrelated.py",), port=59880)
    monkeypatch.setattr(supervisor, "inspect_process", lambda pid, port=None: reused)
    targets, rejected = supervisor.verified_cleanup_targets(value)
    assert targets == []
    assert rejected[0]["reason"] == "COMMAND_IDENTITY_MISMATCH"


def test_verified_cleanup_missing_identity_fails_closed():
    targets, rejected = supervisor.verified_cleanup_targets(state(fastapi=service()))
    assert targets == []
    assert rejected[0]["reason"] == "INSUFFICIENT_IDENTITY"


def test_verified_cleanup_is_idempotent_after_process_exit(monkeypatch):
    value, current = verified_state()
    observations = iter((current, None))
    monkeypatch.setattr(supervisor, "inspect_process", lambda pid, port=None: next(observations))
    assert supervisor.verified_cleanup_targets(value) == ([20], [])
    assert supervisor.verified_cleanup_targets(value) == ([], [])


def test_direct_listener_launcher_duplicate_is_not_reported_rejected(monkeypatch):
    current = evidence(30, 10, argv=("preview.js",), port=59881)
    identity = process_identity(run_id="current", role="preview", evidence=current)
    value = {
        "run_id": "current",
        "services": {
            "preview": {
                "run_id": "current",
                "identities": {"listener": identity, "launcher": identity},
            }
        },
    }
    monkeypatch.setattr(supervisor, "inspect_process", lambda pid, port=None: current)
    assert supervisor.verified_cleanup_targets(value) == ([30], [])


class FakeHandle:
    def __init__(self, current):
        self.handle = True
        self.error = 0
        self.current = current
        self.terminated = False
        self.closed = False
        self.termination_result = True
        self.is_exited = False

    def evidence(self, *, port, inspector):
        return self.current

    def terminate(self):
        self.terminated = True
        return self.termination_result

    def exited(self):
        return self.is_exited

    def close(self):
        self.closed = True


def final_termination(recorded, current, *, run="current", role="fastapi_listener"):
    handle = FakeHandle(current)
    result = terminate_if_still_owned(
        recorded,
        expected_run_id=run,
        expected_role=role,
        handle_factory=lambda pid: handle,
    )
    return result, handle


def assert_linux_process_identity_fail_closed(result, handle):
    assert result.status == "UNKNOWN_IDENTITY_FAIL_CLOSED"
    assert result.reason == "UNSUPPORTED_PLATFORM"
    assert handle.terminated is False


def test_final_boundary_valid_identity_terminates_same_handle():
    current = evidence(20, 10, port=59880)
    record = process_identity(run_id="current", role="fastapi_listener", evidence=current)
    result, handle = final_termination(record, current)
    if os.name != "nt":
        assert_linux_process_identity_fail_closed(result, handle)
        return
    assert result.status == "TERMINATED"
    assert handle.terminated is True
    assert handle.closed is True


def test_toctou_pid_reuse_after_initial_validation_is_rejected():
    original = evidence(20, 10, port=59880)
    record = process_identity(run_id="current", role="fastapi_listener", evidence=original)
    replacement = ProcessEvidence(20, 99, NOW + timedelta(seconds=1), r"C:\unrelated\python.exe", ("unrelated.py",), 59880)
    result, handle = final_termination(record, replacement)
    if os.name != "nt":
        assert_linux_process_identity_fail_closed(result, handle)
        return
    assert result.status in {"REJECTED_PID_REUSE", "REJECTED_IDENTITY_MISMATCH"}
    assert handle.terminated is False


def test_final_creation_time_mismatch_does_not_terminate():
    original = evidence(20, 10, port=59880)
    record = process_identity(run_id="current", role="fastapi_listener", evidence=original)
    changed = ProcessEvidence(20, 10, NOW + timedelta(seconds=1), original.executable, original.argv, 59880)
    result, handle = final_termination(record, changed)
    if os.name != "nt":
        assert_linux_process_identity_fail_closed(result, handle)
        return
    assert result.status == "REJECTED_PID_REUSE"
    assert handle.terminated is False


def test_final_executable_mismatch_does_not_terminate():
    original = evidence(20, 10, port=59880)
    record = process_identity(run_id="current", role="fastapi_listener", evidence=original)
    result, handle = final_termination(record, evidence(20, 10, exe=r"C:\other\python.exe", port=59880))
    if os.name != "nt":
        assert_linux_process_identity_fail_closed(result, handle)
        return
    assert result.reason == "EXECUTABLE_MISMATCH"
    assert handle.terminated is False


def test_final_argv_mismatch_does_not_terminate():
    original = evidence(20, 10, port=59880)
    record = process_identity(run_id="current", role="fastapi_listener", evidence=original)
    result, handle = final_termination(record, evidence(20, 10, argv=("other.py",), port=59880))
    if os.name != "nt":
        assert_linux_process_identity_fail_closed(result, handle)
        return
    assert result.reason == "COMMAND_IDENTITY_MISMATCH"
    assert handle.terminated is False


def test_final_run_id_mismatch_does_not_terminate():
    current = evidence(20, 10, port=59880)
    record = process_identity(run_id="old", role="fastapi_listener", evidence=current)
    result, handle = final_termination(record, current, run="new")
    if os.name != "nt":
        assert_linux_process_identity_fail_closed(result, handle)
        return
    assert result.reason == "RUN_ID_MISMATCH"
    assert handle.terminated is False


def test_final_identity_query_failure_fails_closed():
    current = evidence(20, 10, port=59880)
    record = process_identity(run_id="current", role="fastapi_listener", evidence=current)
    result, handle = final_termination(record, None)
    assert result.status == "UNKNOWN_IDENTITY_FAIL_CLOSED"
    assert handle.terminated is False


def test_final_parent_exited_child_identity_can_still_terminate():
    child = evidence(20, 10, port=59880)
    record = process_identity(run_id="current", role="fastapi_listener", evidence=child)
    result, handle = final_termination(record, child)
    if os.name != "nt":
        assert_linux_process_identity_fail_closed(result, handle)
        return
    assert result.status == "TERMINATED"
    assert handle.terminated is True


def test_process_exiting_during_handle_termination_is_safe_success():
    current = evidence(20, 10, port=59880)
    record = process_identity(run_id="current", role="fastapi_listener", evidence=current)
    handle = FakeHandle(current)
    handle.termination_result = False
    handle.is_exited = True
    result = terminate_if_still_owned(
        record,
        expected_run_id="current",
        expected_role="fastapi_listener",
        handle_factory=lambda pid: handle,
    )
    if os.name != "nt":
        assert result.status == "UNKNOWN_IDENTITY_FAIL_CLOSED"
        assert result.reason == "UNSUPPORTED_PLATFORM"
        assert handle.terminated is False
        return
    assert result.status == "ALREADY_EXITED"
