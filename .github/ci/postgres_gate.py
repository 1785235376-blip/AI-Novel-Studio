"""Fail the real database CI job if a PostgreSQL contract silently skips."""
from __future__ import annotations

import os

import pytest

_required: set[str] = set()
_skipped: set[str] = set()


def pytest_sessionstart(session):
    _required.clear()
    _skipped.clear()
    if os.environ.get("STORAGE_BACKEND") == "postgres" and not os.environ.get("TEST_POSTGRES_DATABASE_URL"):
        raise pytest.UsageError("PostgreSQL CI requires an explicit TEST_POSTGRES_DATABASE_URL")


def pytest_collection_modifyitems(items):
    if os.environ.get("STORAGE_BACKEND") == "postgres":
        _required.update(item.nodeid for item in items if item.get_closest_marker("postgres_backend_only"))
        if not _required:
            raise pytest.UsageError("PostgreSQL CI collected no PostgreSQL contracts")


def pytest_runtest_logreport(report):
    if report.skipped and report.nodeid in _required:
        _skipped.add(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    if _skipped:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter):
    if _skipped:
        terminalreporter.write_sep("=", "PostgreSQL contracts must execute in CI", red=True)
        for nodeid in sorted(_skipped):
            terminalreporter.write_line(nodeid, red=True)
