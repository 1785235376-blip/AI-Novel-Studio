def current_empty_fixture(run_id: str) -> dict[str, object]:
    workspace_id = f"acceptance-roundtrip-empty-{run_id}"
    return {
        "run_id": run_id,
        "roundtrip_empty": {"id": workspace_id, "name": workspace_id},
        "eligible_paths": [],
        "default_path": None,
    }


def test_dynamic_empty_workspace_is_current_run_and_projectless():
    fixture = current_empty_fixture("run-a")
    assert fixture["roundtrip_empty"]["id"] == "acceptance-roundtrip-empty-run-a"
    assert fixture["eligible_paths"] == []
    assert fixture["default_path"] is None


def test_legacy_acceptance_empty_is_not_selected():
    fixture = current_empty_fixture("run-a")
    assert fixture["roundtrip_empty"]["id"] != "acceptance-empty"


def test_previous_run_fixture_is_not_selected():
    previous = current_empty_fixture("run-a")
    current = current_empty_fixture("run-b")
    assert current["roundtrip_empty"]["id"] != previous["roundtrip_empty"]["id"]


def test_retry_for_same_run_is_stable():
    assert current_empty_fixture("run-a") == current_empty_fixture("run-a")


def test_historical_mutation_cannot_pollute_future_run_fixture():
    previous = current_empty_fixture("run-a")
    previous["eligible_paths"] = [{"project_id": "persisted"}]
    current = current_empty_fixture("run-b")
    assert current["eligible_paths"] == []
    assert current["default_path"] is None
