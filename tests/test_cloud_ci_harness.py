"""Cloud harness regressions: dedicated database scope and fail-closed receipts."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import postgres_test_environment

ROOT = Path(__file__).resolve().parents[1]


def load_helper(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ".github" / "ci" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("backend,marked,dedicated", [
    ("file", True, "postgresql://test"),
    ("postgres", False, "postgresql://test"),
    ("postgres", True, ""),
])
def test_database_environment_stays_scrubbed_without_explicit_scope(backend, marked, dedicated):
    request = SimpleNamespace(node=SimpleNamespace(get_closest_marker=lambda name: marked))
    environment = {"STORAGE_BACKEND": backend, "DATABASE_URL": "postgresql://ambient",
                   "TEST_POSTGRES_DATABASE_URL": dedicated, "OPENAI_API_KEY": "must-not-copy"}
    assert postgres_test_environment(request, environment) == {}


def test_marked_postgres_case_gets_only_dedicated_endpoint():
    request = SimpleNamespace(node=SimpleNamespace(get_closest_marker=lambda name: True))
    environment = {"STORAGE_BACKEND": "postgres", "DATABASE_URL": "postgresql://ambient",
                   "TEST_POSTGRES_DATABASE_URL": "postgresql://test", "OPENAI_API_KEY": "must-not-copy"}
    assert postgres_test_environment(request, environment) == {
        "TEST_POSTGRES_DATABASE_URL": "postgresql://test", "DATABASE_URL": "postgresql://test"}


def test_postgres_gate_rejects_skipped_contract_and_resets(monkeypatch):
    gate = load_helper("postgres_gate")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("TEST_POSTGRES_DATABASE_URL", "postgresql://test")
    gate.pytest_sessionstart(None)
    gate.pytest_collection_modifyitems([
        SimpleNamespace(nodeid="required", get_closest_marker=lambda name: True)])
    gate.pytest_runtest_logreport(SimpleNamespace(nodeid="required", skipped=True))
    session = SimpleNamespace(exitstatus=0)
    gate.pytest_sessionfinish(session, 0)
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    gate.pytest_sessionstart(None)
    assert not gate._required and not gate._skipped


def test_postgres_gate_requires_dedicated_url_and_real_contracts(monkeypatch):
    gate = load_helper("postgres_gate")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.delenv("TEST_POSTGRES_DATABASE_URL", raising=False)
    with pytest.raises(pytest.UsageError, match="explicit TEST_POSTGRES_DATABASE_URL"):
        gate.pytest_sessionstart(None)
    monkeypatch.setenv("TEST_POSTGRES_DATABASE_URL", "postgresql://test")
    gate.pytest_sessionstart(None)
    with pytest.raises(pytest.UsageError, match="no PostgreSQL contracts"):
        gate.pytest_collection_modifyitems([])


def test_receipt_never_infers_success_from_missing_test_output(tmp_path):
    receipt = load_helper("receipt")
    (tmp_path / "revision.txt").write_text("checked_out_sha=test\n", encoding="utf-8")
    assert receipt.summarize(tmp_path)["report_status"] == "NOT RUN / NO TEST REPORT"
    (tmp_path / "report.xml").write_text(
        '<testsuite><testcase/><testcase><skipped/></testcase>'
        '<testcase><failure/></testcase><testcase><error/></testcase></testsuite>', encoding="utf-8")
    assert receipt.summarize(tmp_path)["test_reports"]["report.xml"] == {
        "tests": 4, "failures": 1, "errors": 1, "skipped": 1}
