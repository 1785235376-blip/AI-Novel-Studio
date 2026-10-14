"""Pin the five runtime levels the discovery report keeps separate.

Audit of `app/model_center/discovery.py` found the scan report already distinguishes:

  1. file existence      -> `executable_exists` / GGUF `file_exists`
  2. runtime existence   -> never probed at process level; only inferred
  3. connectivity        -> bounded numeric-loopback HTTP probe
  4. recognisability     -> GGUF header/architecture, or a provider model list
  5. executability       -> never claimed (`EXECUTABLE_NOT_EXECUTED`, inference NOT_RUN)

Levels 1-4 are implemented and level 5 is refused by design, but no existing test
asserted the scan-time *runtime report* shape. `tests/test_v2_llama_locality_validation.py`
covers the later `validate()` outcome; `tests/test_local_ai_environment_v2.py` and
`tests/test_v2_discovery_file_projection.py` cover filesystem observations.

These tests are purely additive: they observe the existing report and change no
discovery semantics, registry, endpoint, limit or fail-closed path. No process is
started and no model is downloaded or generated.
"""
from __future__ import annotations

import pytest

from app.model_center.discovery_types import LocalRuntimeInput
from test_local_ai_discovery import gguf, scan, service

ENDPOINT = "http://127.0.0.1:19992"


def llama_runtime(tmp_path, *, executable=True, model_path=True):
    """Real synthetic artifacts on disk; connectivity is decided by the fixture client."""
    svc = service(tmp_path)
    path = tmp_path / "qwen.gguf"
    gguf(path)
    binary = tmp_path / "llama-server"
    binary.write_bytes(b"SYNTHETIC_NOT_EXECUTABLE")
    runtime = svc.configure_runtime(LocalRuntimeInput(
        name="Synthetic llama", type="LLAMA_CPP", endpoint=ENDPOINT,
        model_path=str(path) if model_path else "",
        management="EXTERNAL", executable=str(binary) if executable else ""))
    return svc, runtime, path


def report_for(job, runtime_id):
    return next(row for row in job["runtimes"] if row["id"] == runtime_id)


def candidate_for(job, runtime_id):
    return next(row for row in job["candidates"] if row["runtime_id"] == runtime_id)


def test_artifacts_present_without_connectivity_is_discovered_never_running(tmp_path):
    """Levels 1 and 4 hold for the file; level 3 is absent; so the runtime is not RUNNING."""
    svc, runtime, _ = llama_runtime(tmp_path)      # no /v1/models payload -> probe fails
    job = scan(svc)
    report = report_for(job, runtime["id"])

    # Level 1: the executable exists on disk and is reported, without ever being run.
    assert report["executable_exists"] is True
    assert "EXECUTABLE_NOT_EXECUTED" in report["notes"]
    # Level 3 absent: file existence is not connectivity, so this is DISCOVERED, not RUNNING.
    assert report["status"] == "DISCOVERED" and report["status"] != "RUNNING"
    assert "EXTERNAL_RUNTIME_NOT_RUNNING" in report["notes"]
    # Level 4 for the runtime failed too: no model list was obtained, so the key is absent
    # rather than an empty list that could be mistaken for a successful empty enumeration.
    assert "available_models" not in report
    # Level 5: no version, accelerator or readiness claim of any kind is made.
    assert report["version"] is None and report["version_source"] == "NOT_VERIFIED"
    assert report["cuda_status"] == "NOT_VERIFIED"

    candidate = candidate_for(job, runtime["id"])
    # Levels 1 and 4 hold for the configured file, yet the candidate stays ineligible.
    assert candidate["evidence"]["file_exists"] is True
    assert candidate["evidence"]["header_valid"] is True
    assert candidate["verified_capabilities"] == [] and candidate["verified"] is False
    assert candidate["enable_eligible"] is False and candidate["enable_blockers"] == ["VALIDATION_REQUIRED"]
    assert job["status"] == "PARTIAL"
    svc.center.lifecycle.start.assert_not_called()


def test_connectivity_without_artifact_is_running_but_not_a_verified_model(tmp_path):
    """Level 3 present with level 1 absent: a reachable runtime is not a runnable model."""
    svc, runtime, _ = llama_runtime(tmp_path, executable=False, model_path=False)
    svc.client.payloads[(ENDPOINT, "/v1/models")] = {"data": [{"id": "qwen.gguf"}]}
    job = scan(svc)
    report = report_for(job, runtime["id"])

    assert report["status"] == "RUNNING" and "EXTERNAL_RUNTIME_NOT_RUNNING" not in report["notes"]
    # No configured executable was observed: level 1 is reported absent, never assumed.
    assert report["executable_exists"] is False
    # Level 4 here is only the provider's own list, and level 5 is still not attempted.
    assert report["available_models"] == ["qwen.gguf"]
    assert "EXECUTABLE_NOT_EXECUTED" in report["notes"]

    candidate = candidate_for(job, runtime["id"])
    assert candidate["evidence"]["model_listed"] is True
    assert "file_exists" not in candidate["evidence"]
    assert candidate["local_path"] == ""
    assert candidate["verified_capabilities"] == [] and candidate["enable_eligible"] is False
    svc.center.lifecycle.start.assert_not_called()


def test_validated_local_header_verifies_capability_without_granting_readiness(tmp_path):
    """The enable gate keys on connectivity evidence, not on a recognised local file."""
    svc, runtime, _ = llama_runtime(tmp_path)      # still unreachable
    candidate = candidate_for(scan(svc), runtime["id"])

    assert not svc.registrations
    validated = svc.validate(candidate["id"])
    # Level 4 succeeds from the local GGUF header alone, so capability is verified.
    assert validated["verified_capabilities"] == ["TEXT"]
    assert validated["compatible"] == "POSSIBLY_COMPATIBLE"
    # But level 3 is still absent, so readiness is refused and locality is not granted.
    assert validated["enable_eligible"] is False
    assert "RUNTIME_MODEL_UNVERIFIED" in validated["enable_blockers"]
    assert validated["local"] is False and validated["source_locality"] == "NOT_VERIFIED"
    # Level 5 stays refused: no inference, executable version or accelerator is verified.
    assert "INFERENCE_NOT_RUN" in validated["validation_notes"]
    assert "EXECUTABLE_VERSION_NOT_VERIFIED" in validated["validation_notes"]
    assert validated["verified"] is False

    svc.register(candidate["id"])
    with pytest.raises(ValueError, match="LOCAL_AI_ENABLE_BLOCKED"):
        svc.enable(candidate["id"])
    assert svc.registrations[candidate["id"]]["enabled"] is False
    svc.center.lifecycle.start.assert_not_called()


def test_runtime_existence_is_never_probed_at_process_level(tmp_path):
    """Level 2 is absent by construction: the scan reports no process fact at all.

    Level 1 is a stat of the configured executable and level 3 is an HTTP answer; in
    between, nothing observes whether a process exists. `RuntimeInstance.process_alive`
    and `http_reachable` live on the lifecycle object, which discovery never consults --
    so "the runtime exists" is never *observed* during a scan, only *inferred* from a
    configured executable plus a silent endpoint. This test pins that gap so a later
    change cannot quietly start presenting a level-2 fact as measured evidence.
    """
    svc, runtime, _ = llama_runtime(tmp_path)
    report = report_for(scan(svc), runtime["id"])

    # Level 1 observed, and it is a file observation rather than a process observation.
    assert report["executable_exists"] is True
    assert report["executable_size"] is not None
    for process_key in ("process_alive", "process_id", "pid", "running", "state", "http_reachable"):
        assert process_key not in report
    # The DISCOVERED verdict is connectivity-derived (level 3 absent), which is not the
    # same claim as "no runtime process exists" (level 2) -- that stays unknown.
    assert report["status"] == "DISCOVERED"
    assert "EXTERNAL_RUNTIME_NOT_RUNNING" in report["notes"]
    assert "RUNTIME_NOT_RUNNING" not in report["notes"]
    # The lifecycle, the only place MANAGED liveness is knowable, is never touched.
    svc.center.lifecycle.start.assert_not_called()
