"""The runnable preparation harness must not disguise missing native evidence."""

import asyncio
import json
from pathlib import Path

import pytest

from local_interop_desktop.acceptance import (
    DesktopInteropAcceptanceHarness,
    SyntheticAcceptanceAdapter,
)
from local_interop_desktop.testing import SyntheticContextOwner
from local_interop_protocol import ProtocolViolation


def test_all_24_scenarios_execute_and_native_cross_user_remains_not_run():
    report = asyncio.run(DesktopInteropAcceptanceHarness(SyntheticAcceptanceAdapter()).run())
    assert report["summary"] == {"PASS": 23, "FAIL": 0, "NOT_RUN": 1}
    assert [row["id"] for row in report["results"]] == [f"A{i:02d}" for i in range(1, 25)]
    assert report["results"][20]["outcome"] == "NOT_RUN"
    assert report["native_acceptance"] == "LOCAL_REQUIRED"
    assert all(row["native_status"] in {"LOCAL_REQUIRED", "NOT_RUN"} for row in report["results"])
    assert all(row["scope"] in {"MOCK_ONLY", "NATIVE_REQUIRED"} for row in report["results"])
    encoded = json.dumps(report)
    assert "Synthetic selected text" not in encoded
    assert "Synthetic chapter" not in encoded
    assert "session_token" not in encoded
    assert "executable_path" not in encoded


def test_harness_reports_failures_instead_of_silent_skip_or_exception_text():
    class FailingAdapter:
        async def create_fixture(self, scenario_id):
            raise ValueError("sensitive local fixture detail must not be reported")

    report = asyncio.run(DesktopInteropAcceptanceHarness(FailingAdapter()).run())
    assert report["summary"] == {"PASS": 0, "FAIL": 23, "NOT_RUN": 1}
    assert "sensitive local fixture detail" not in json.dumps(report)
    assert report["results"][0]["error_code"] == "ValueError"


@pytest.mark.parametrize("level", ["SELECTED_TEXT", "CURRENT_CHAPTER", "PROJECT_CONTEXT"])
def test_fixture_never_infers_content_consent(level):
    context = SyntheticContextOwner()
    with pytest.raises(ProtocolViolation) as error:
        context.capsule(level)
    assert error.value.code == "CONTEXT_NOT_AUTHORIZED"
    assert context.capsule(level, approved=True).content.level == level


def test_delivery_manifest_has_all_requirements_and_honest_native_gaps():
    root = Path(__file__).resolve().parents[1]
    requirements = json.loads((root / "DESKTOP_INTEGRATION_READINESS_MATRIX.json").read_text())
    assert [row["section"] for row in requirements["requirements"]] == list(range(1, 70))
    matrix = json.loads((root / "DESKTOP_INTEROP_ACCEPTANCE_MATRIX.json").read_text())
    assert len(matrix["scenarios"]) == 24
    assert matrix["production_acceptance"] == "LOCAL_REQUIRED"
    assert matrix["scenarios"][20]["native_status"] == "NOT_RUN"
