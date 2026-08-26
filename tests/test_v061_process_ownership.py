from datetime import datetime, timedelta, timezone

from scripts.v061_process_ownership import (
    ProcessEvidence,
    classify_owner,
    identity_matches,
    process_identity,
)


NOW = datetime.now(timezone.utc)
EXE = r"C:\runtime\python.exe"
ENTRY = "v061_fastapi_server.py"


def process(pid, parent=None, *, created=NOW, exe=EXE, argv=None, port=59880):
    return ProcessEvidence(pid, parent, created, exe, argv or (ENTRY, "--port", str(port)), port)


def classify(listener, processes=None, launcher=10, port=59880):
    return classify_owner(
        launcher_pid=launcher,
        listener=listener,
        processes=processes or {listener.pid: listener},
        launch_time=NOW - timedelta(seconds=1),
        selected_port=port,
        expected_executable=EXE,
        expected_entrypoint=ENTRY,
    )


def test_direct_owner_passes():
    assert classify(process(10))[0] == "DIRECT"


def test_descendant_owner_passes_with_parent_chain():
    parent = process(10)
    listener = process(20, 10)
    assert classify(listener, {10: parent, 20: listener}) == ("DESCENDANT", (20, 10))


def test_unrelated_same_executable_is_rejected():
    assert classify(process(20, 99))[0] == "UNRELATED"


def test_old_process_is_rejected():
    assert classify(process(10, created=NOW - timedelta(minutes=1)))[0] == "UNRELATED"


def test_wrong_port_is_rejected():
    assert classify(process(10, port=60000), port=59880)[0] == "UNRELATED"


def test_environment_selected_port_does_not_need_to_appear_in_argv():
    assert classify(process(10, argv=(ENTRY,)))[0] == "DIRECT"


def test_unknown_lineage_fails_closed():
    assert classify(ProcessEvidence(10, None, None, None, None, None))[0] == "UNKNOWN"


def identity(evidence=None, *, run="run-a", role="fastapi_listener"):
    return process_identity(run_id=run, role=role, evidence=evidence or process(10))


def matches(recorded, current=None, *, run="run-a", role="fastapi_listener"):
    return identity_matches(recorded, current or process(10), expected_run_id=run, expected_role=role)


def test_complete_same_run_identity_matches():
    assert matches(identity()) == (True, "MATCH")


def test_cross_run_identity_is_rejected():
    assert matches(identity(run="run-a"), run="run-b") == (False, "RUN_ID_MISMATCH")


def test_pid_reuse_creation_time_is_rejected():
    current = process(10, created=NOW + timedelta(seconds=1))
    assert matches(identity(), current) == (False, "CREATION_TIME_MISMATCH")


def test_changed_executable_is_rejected():
    current = process(10, exe=r"C:\other\python.exe")
    assert matches(identity(), current) == (False, "EXECUTABLE_MISMATCH")


def test_changed_command_identity_is_rejected():
    current = process(10, argv=("other.py", "--port", "59880"))
    assert matches(identity(), current) == (False, "COMMAND_IDENTITY_MISMATCH")


def test_changed_role_is_rejected():
    assert matches(identity(role="preview")) == (False, "ROLE_MISMATCH")


def test_changed_lineage_is_rejected():
    recorded = identity(process(10, parent=5))
    assert matches(recorded, process(10, parent=6)) == (False, "LINEAGE_MISMATCH")


def test_missing_identity_metadata_fails_closed():
    assert matches({"run_id": "run-a", "pid": 10}) == (False, "INSUFFICIENT_IDENTITY")


def test_missing_current_process_fails_closed():
    assert identity_matches(identity(), None, expected_run_id="run-a", expected_role="fastapi_listener") == (
        False,
        "INSUFFICIENT_IDENTITY",
    )
