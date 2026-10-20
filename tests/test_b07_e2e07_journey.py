"""B07 E2E-07: real mounted-API samples, integration journey and target evidence regression.

These tests reuse the real composition fixture from tests/test_r3_mounted_contracts.py
(real File repository bundle, production routers, real trusted-session/role stack,
in-process FastAPI TestClient) and call the same generator functions as
scripts/b07_e2e07_journey.py.  Nothing about story authority, review, export or
playback is mocked.

The target-runtime portion is opt-in: external runtimes are only launched when the
environment explicitly allows it, because a unit test suite is not the place to
start engines.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from test_r3_mounted_contracts import checked, mounted

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "scripts" / "b07_e2e07_journey.py"


def load_journey_module():
    name = "b07_e2e07_journey"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["/api"])
def prefix(request):
    """The mounted fixture is imported with a single real route prefix for speed."""
    return request.param


@pytest.fixture()
def journal():
    return load_journey_module()


def test_real_api_samples_are_fixtures_with_play_authority(tmp_path, mounted, journal):
    recorder = journal.Recorder("pytest-samples")
    delivery = tmp_path / "delivery"
    scratch = tmp_path / "scratch"
    samples = journal.run_samples(recorder, mounted, delivery / "samples", scratch, runtime=False)
    assert set(samples) == {"A_basic_linear", "B_conditional_branch", "C_complex_boundaries"}
    story = journal.story_authority()
    expected_ending_counts = {"A_basic_linear": 1, "B_conditional_branch": 3, "C_complex_boundaries": 2}
    for key, sample in samples.items():
        assert sample["story"]["version"] == sample["review"]["approved_version"]
        assert sample["review"]["approved_status"] == "APPROVED"
        assert len(sample["analysis"]["endings"]) == expected_ending_counts[key]
        assert sample["analysis"]["can_review"] is True
        # every recorded expected state really comes from play()
        for case in sample["cases"]:
            for index, state in enumerate(case["expected_states"]):
                authority = story.play(sample["spec"], case["choices"][:index])
                assert state["node_id"] == authority["node"]["node_id"]
                assert state["variables"] == authority["variables"]
                assert state["steps"] == authority["steps"]
                assert state["enabled_choice_ids"] == [item["id"] for item in authority["choices"] if item["enabled"]]
                assert state["status"] == authority["status"]
        assert all(item["status"] == "PASS" for item in sample["feature_checks"]), key
        # B must really demonstrate a route disabled under the initial variable state
        if key == "B_conditional_branch":
            initial = sample["cases"][0]["expected_states"][0]
            assert initial["disabled_choice_ids"] == ["call"]
            assert sample["features"]["condition_driven_divergence"]
        # C must really hit the explicit step cap and carry unicode
        if key == "C_complex_boundaries":
            statuses = [case["expected_states"][-1]["status"] for case in sample["cases"]]
            assert "STEP_CAP_REACHED" in statuses
            assert sample["features"]["cycle_node_ids"]
            assert sample["features"]["special_characters"]["emoji"]
            assert sample["features"]["save_restore_cases"]
        legacy = sample["exports"]["legacy"]
        assert legacy["archive"]["status"] == "PASS"
        assert legacy["runtime"]["status"] in ("NOT_RUN", "BLOCKED_ENVIRONMENT", "EXECUTED_AND_ALIGNED")
        # a second independent export must be byte-identical
        assert legacy["deterministic_repeat"]["identical"] is True
        for target_id, record in sample["exports"]["new_targets"].items():
            assert record["status"] in {"TARGET_NOT_AVAILABLE", "NOT_EXPORT_READY", "PREVIEW_BLOCKED", "EXPORTED"}
            if record["status"] == "EXPORTED":
                assert record["archive"]["status"] == "PASS"


def test_real_api_journey_review_export_and_artifact_alignment(tmp_path, mounted, journal):
    recorder = journal.Recorder("pytest-journey")
    delivery = tmp_path / "delivery"
    scratch = tmp_path / "scratch"
    doc = journal.run_journey(recorder, mounted, delivery / "journey", scratch, runtime=False)
    story = journal.story_authority()
    assert doc["story"]["revision"] == doc["versions"]["approved_v4"] == 4
    assert doc["story"]["status"] == "APPROVED"
    assert doc["review"]["preview_digest"] == doc["story"]["review_preview_digest"]
    assert len(doc["previews"]) >= 2
    assert any(item["server"]["status"] == "ENDING" for item in doc["previews"])
    assert any(item["server"]["status"] == "STEP_CAP_REACHED" for item in doc["previews"])
    for preview in doc["draft_previews"] + doc["previews"] + [doc["approved_preview"]]:
        assert preview["server"] == preview["play"]
    # review preview authority equals the play() analysis for the approved revision
    authority = journal.analyze_summary(doc["spec_approved"])
    assert doc["review"]["can_approve"] is True
    assert record_analysis_matches(doc["analysis"], authority)
    service_view = doc["exports"]["service_view"]
    assert service_view["witness"] == authority["endings"]
    assert service_view["story"]["spec_digest"] == journal.digest_json(doc["spec_approved"])
    assert service_view["can_export_any"] is True
    legacy = doc["exports"]["legacy"]
    assert legacy["archive"]["status"] == "PASS"
    assert legacy["archive"]["ink_witness_alignment"]["status"] == "PASS"
    assert legacy["deterministic_repeat"]["identical"] is True
    assert legacy["runtime"]["status"] in ("NOT_RUN", "BLOCKED_ENVIRONMENT", "EXECUTED_AND_ALIGNED")
    for target_id in journal.TARGET_ORDER:
        record = doc["exports"]["new_targets"][target_id]
        assert record["status"] in {"TARGET_NOT_AVAILABLE", "NOT_EXPORT_READY", "PREVIEW_BLOCKED", "EXPORTED"}
        if record["status"] == "EXPORTED":
            assert record["archive"]["status"] == "PASS"
            assert record["deterministic_repeat"]["identical"] is True
            assert record["runtime"]["status"] in ("NOT_RUN", "BLOCKED_ENVIRONMENT",
                                                   "EXECUTED_AND_ALIGNED", "EXECUTED_WITH_MISMATCH")
            runtime_alignment = record["runtime"].get("alignment")
            assert runtime_alignment is None or runtime_alignment["status"] in ("PASS", "FAIL")
    # delivered bytes exist on disk for the legacy bundle
    assert (delivery / "journey" / "exports" / "legacy").is_dir()


def record_analysis_matches(left, right):
    keys = ("issues", "warnings", "states_checked", "analysis_complete", "step_limit_reached",
            "max_steps", "can_review", "method")
    return all(left.get(key) == right.get(key) for key in keys) and left.get("endings") == right.get("endings")


def test_runtime_result_normalization_and_step_alignment(journal):
    spec = {
        "title": "adapter normalization fixture",
        "graph_id": "g",
        "graph_version": 1,
        "entry_node_id": "a",
        "max_steps": 3,
        "variables": [{"name": "flag", "type": "bool", "initial": False}],
        "nodes": [
            {"node_id": "a", "node_version": 1, "title": "A", "dialogue": "start",
             "choices": [{"id": "go", "label": "Go", "target": "b", "assignments": {"flag": True}},
                         {"id": "stop", "label": "Stop", "target": "c", "condition": "flag"}]},
            {"node_id": "b", "node_version": 1, "title": "B", "ending": "good"},
            {"node_id": "c", "node_version": 1, "title": "C", "ending": "other"},
        ],
    }
    story = journal.story_authority()
    spec = story.StorySpec.model_validate(spec).model_dump()
    analysis = journal.analyze_summary(spec)
    cases = journal.build_cases(spec, analysis)
    # a synthetic verifier result using alternate names/labels must normalize to the same steps
    payload = {
        "cases": [
            {"id": case["id"],
             "snapshots": [
                 {"node": ["a", "b", "c"].index(state["node_id"]),
                  "values": {"ans_var_0": state["variables"]["flag"]},
                  "choices": [item["label"] for item in state["choices"] if item["enabled"]],
                  "steps": state["steps"], "status": {"PLAYING": 0, "ENDING": 1}.get(state["status"], 0)}
                 for state in case["expected_states"]]}
            for case in cases
        ]
    }
    normalized = journal.normalize_runtime_cases(payload, spec, cases)
    assert normalized, "normalization must accept index/label/legacy-code verifier output"
    recorder = journal.Recorder("pytest-normalization")
    alignment = journal.align_runtime_cases(recorder, "SYNTHETIC_TARGET", normalized, cases)
    assert alignment["status"] == "PASS"
    # a corrupted runtime state must fail, not pass silently
    payload["cases"][0]["snapshots"][0]["steps"] = 99
    corrupted = journal.normalize_runtime_cases(payload, spec, cases)
    recorder = journal.Recorder("pytest-normalization-fail")
    try:
        journal.align_runtime_cases(recorder, "SYNTHETIC_TARGET", corrupted, cases)
        assert False, "misaligned runtime states must raise"
    except RuntimeError as exc:
        assert "runtime-step-alignment" in str(exc)
