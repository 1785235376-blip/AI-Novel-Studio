"""Exact collected-node sharding and fail-closed per-process outcome receipts.

No product test is ignored during collection. Assignment is applied only after
ordinary collection hooks, and the complete unfiltered inventory is recorded.
The independent coverage_reconcile.py verifier owns cross-job/JUnit proof.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import pytest

FILE_SKIP = (
    "File-backend implementation contract; covered by the default/File full suite"
)
POSTGRES_SKIP = (
    "PostgreSQL implementation contract; covered by the real PostgreSQL full suite"
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def shard_for(nodeid, count):
    return (
        int.from_bytes(hashlib.sha256(nodeid.encode("utf-8")).digest(), "big") % count
    )


def read_manifest(path):
    raw = Path(path).read_bytes()
    data = gzip.decompress(raw) if str(path).endswith(".gz") else raw
    return json.loads(data), hashlib.sha256(raw).hexdigest()


def scope_nodes(manifest, scope):
    nodes = manifest["product_nodes"]
    if scope == "interop":
        nodes = [
            node
            for node in nodes
            if node.split("::", 1)[0].startswith("tests/test_local_interop")
        ]
    return nodes


def source_errors(root, manifest):
    errors = []
    for name, expected in manifest["source_files"].items():
        path = root / name
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            errors.append("frozen product test/source digest differs: " + name)
    return errors


def outcome_errors(inventory, assigned, outcomes, backend, scope, manifest):
    errors = []
    classifications = {row["nodeid"]: row["backend"] for row in inventory}
    if set(outcomes) != set(assigned):
        errors.append("observed node set differs from assigned node set")
    legacy = manifest["skips"][backend]
    for nodeid in assigned:
        reports = outcomes.get(nodeid, [])
        phases = [row["when"] for row in reports]
        if any(row["wasxfail"] for row in reports):
            errors.append("xfail/xpass is forbidden: " + nodeid)
            continue
        if any(row["outcome"] == "failed" for row in reports):
            errors.append("failed setup/call/teardown: " + nodeid)
            continue
        skipped = [row for row in reports if row["outcome"] == "skipped"]
        if not skipped:
            if classifications[nodeid] not in {"both", backend}:
                errors.append(
                    "opposite backend node executed in the wrong profile: " + nodeid
                )
            if phases != ["setup", "call", "teardown"] or any(
                row["outcome"] != "passed" for row in reports
            ):
                errors.append("missing successful setup/call/teardown: " + nodeid)
            continue
        if len(skipped) != 1 or phases not in (
            ["setup", "teardown"],
            ["setup", "call", "teardown"],
        ):
            errors.append("invalid skipped phase sequence: " + nodeid)
            continue
        skip = skipped[0]
        if reports[-1]["when"] != "teardown" or reports[-1]["outcome"] != "passed":
            errors.append("skipped node teardown did not pass: " + nodeid)
        if phases == ["setup", "teardown"] and skip["when"] != "setup":
            errors.append("invalid setup skip: " + nodeid)
        if phases == ["setup", "call", "teardown"] and (
            reports[0]["outcome"] != "passed" or skip["when"] != "call"
        ):
            errors.append("invalid call skip: " + nodeid)
        classification = classifications[nodeid]
        opposite = classification != "both" and classification != backend
        if opposite:
            expected = FILE_SKIP if classification == "file" else POSTGRES_SKIP
            if scope == "backend":
                expected = legacy.get(nodeid, expected)
            if skip["when"] != "setup" or skip["skip_reason"] != expected:
                errors.append("opposite profile skip differs: " + nodeid)
        elif scope == "backend" and nodeid in manifest.get("external_gates", {}).get(
            backend, {}
        ):
            # The two original File TCP nodes execute in their unchanged,
            # separately verified opt-in gate. No other marked skip qualifies.
            if (
                manifest["external_gates"][backend][nodeid]["reason"]
                != skip["skip_reason"]
            ):
                errors.append("external-gate skip differs: " + nodeid)
        elif (
            classification == backend
            or scope == "interop"
            or legacy.get(nodeid) != skip["skip_reason"]
        ):
            errors.append("unexpected applicable-node skip: " + nodeid)
    return errors


def pytest_addoption(parser):
    group = parser.getgroup("exact backend coverage")
    group.addoption(
        "--ci-coverage-dir",
        help="Required output directory for fail-closed shard receipts",
    )
    group.addoption(
        "--ci-coverage-manifest", default=".github/ci/coverage_manifest.json.gz"
    )
    group.addoption("--ci-scope", choices=("backend", "interop"), default="backend")
    group.addoption("--ci-shard-index", type=int, default=0)
    group.addoption("--ci-shard-count", type=int, choices=(1, 2), default=1)


def pytest_configure(config):
    if not config.getoption("ci_coverage_dir"):
        raise pytest.UsageError("suite_coverage requires --ci-coverage-dir")
    config.pluginmanager.register(Coverage(config), "exact-suite-coverage")


class Coverage:
    def __init__(self, config):
        self.config = config
        self.root = Path(config.rootpath)
        self.output = Path(config.getoption("ci_coverage_dir"))
        self.output.mkdir(parents=True, exist_ok=True)
        self.manifest, manifest_hash = read_manifest(
            self.root / config.getoption("ci_coverage_manifest")
        )
        if self.manifest.get("schema_version") != 1:
            raise pytest.UsageError("unsupported coverage manifest schema")
        self.scope = config.getoption("ci_scope")
        for option in ("keyword", "markexpr", "ignore", "ignore_glob", "deselect"):
            if getattr(config.option, option, None):
                raise pytest.UsageError(
                    "external test filtering is forbidden: " + option
                )
        self.index, self.count = (
            config.getoption("ci_shard_index"),
            config.getoption("ci_shard_count"),
        )
        if not 0 <= self.index < self.count:
            raise pytest.UsageError("invalid deterministic shard index")
        self.backend = os.environ.get("STORAGE_BACKEND")
        if self.backend not in {"file", "postgres"}:
            raise pytest.UsageError(
                "coverage requires an explicit file/postgres backend"
            )
        required = (
            "CI_COVERAGE_SHA",
            "CI_COVERAGE_TREE",
            "GITHUB_SHA",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "GITHUB_REPOSITORY",
        )
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise pytest.UsageError(
                "missing independent CI identity: " + ", ".join(missing)
            )
        errors = source_errors(self.root, self.manifest)
        if errors:
            raise pytest.UsageError("; ".join(errors))
        self.identity = {
            "checked_out_sha": os.environ["CI_COVERAGE_SHA"],
            "source_tree": os.environ["CI_COVERAGE_TREE"],
            "event_sha": os.environ["GITHUB_SHA"],
            "run_id": os.environ["GITHUB_RUN_ID"],
            "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
            "repository": os.environ["GITHUB_REPOSITORY"],
            "python_version": platform.python_version(),
            "platform": sys.platform,
            "source_manifest_sha256": manifest_hash,
            "dependency_digest": hashlib.sha256(
                (self.root / ".github/ci/python-constraints.txt").read_bytes()
            ).hexdigest(),
        }
        self.inventory = []
        self.assigned = []
        self.assigned_set = set()
        self.outcomes = {}
        self.collection_errors = []
        self.validation_errors = []
        self.own_deselection = False
        self.collection_finished = False
        self.finished_nodes = set()
        self.write_receipt(complete=False, exitstatus=None)

    def write_receipt(self, *, complete, exitstatus):
        junit = self.config.getoption("xmlpath")
        data = {
            "schema_version": 1,
            "scope": self.scope,
            "identity": self.identity,
            "backend": self.backend,
            "shard": {"index": self.index, "count": self.count},
            "inventory": self.inventory,
            "inventory_digest": digest(self.inventory),
            "assigned": self.assigned,
            "outcomes": [
                {"nodeid": nodeid, "reports": reports}
                for nodeid, reports in self.outcomes.items()
            ],
            "pytest_exitstatus": exitstatus,
            "collection_errors": self.collection_errors,
            "validation_errors": self.validation_errors,
            "complete": complete,
            "junit_filename": Path(junit).name if junit else "",
        }
        temporary = self.output / "coverage.json.tmp"
        temporary.write_text(
            json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.output / "coverage.json")

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_collection_modifyitems(self, session, config, items):
        yield
        self.inventory = [
            {
                "nodeid": item.nodeid,
                "backend": "postgres"
                if item.get_closest_marker("postgres_backend_only")
                else "file"
                if item.get_closest_marker("file_backend_only")
                else "both",
            }
            for item in items
        ]
        actual = [row["nodeid"] for row in self.inventory]
        expected = scope_nodes(self.manifest, self.scope)
        if len(actual) != len(set(actual)) or actual != expected:
            self.validation_errors.append(
                "complete ordered collection differs from frozen product inventory"
            )
            raise pytest.UsageError(self.validation_errors[-1])
        if any(
            item.get_closest_marker("postgres_backend_only")
            and item.get_closest_marker("file_backend_only")
            for item in items
        ):
            raise pytest.UsageError("contradictory backend-only markers")
        selected, deselected = [], []
        for item in items:
            if shard_for(item.nodeid, self.count) == self.index:
                item.user_properties.append(("ci_nodeid", item.nodeid))
                selected.append(item)
            else:
                deselected.append(item)
        self.assigned = [item.nodeid for item in selected]
        self.assigned_set = set(self.assigned)
        if not self.assigned:
            raise pytest.UsageError("empty deterministic shard")
        self.own_deselection = True
        try:
            config.hook.pytest_deselected(items=deselected)
        finally:
            self.own_deselection = False
        items[:] = selected
        self.collection_finished = True
        self.write_receipt(complete=False, exitstatus=None)

    def pytest_deselected(self, items):
        if items and not self.own_deselection:
            self.validation_errors.append("external deselection is forbidden")

    def pytest_collectreport(self, report):
        if report.failed or report.skipped:
            self.collection_errors.append(str(report.nodeid) + ": " + report.outcome)

    def pytest_runtest_logreport(self, report):
        if report.nodeid not in self.assigned_set:
            self.validation_errors.append(
                "report for unassigned node: " + report.nodeid
            )
        if report.nodeid in self.finished_nodes:
            self.validation_errors.append("duplicate node execution: " + report.nodeid)
        reason = None
        if report.skipped and isinstance(report.longrepr, tuple):
            reason = str(report.longrepr[2])
            reason = reason.removeprefix("Skipped: ")
        row = {
            "when": report.when,
            "outcome": report.outcome,
            "wasxfail": hasattr(report, "wasxfail"),
            "skip_reason": reason,
        }
        self.outcomes.setdefault(report.nodeid, []).append(row)
        if report.when == "teardown":
            self.finished_nodes.add(report.nodeid)
        with (self.output / "coverage-events.jsonl").open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(
                json.dumps(
                    {"nodeid": report.nodeid, **row},
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
                + "\n"
            )

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_sessionfinish(self, session, exitstatus):
        yield
        if not self.collection_finished:
            self.validation_errors.append("collection did not finish")
        if self.config.option.collectonly:
            self.validation_errors.append(
                "collect-only is inventory evidence, not execution proof"
            )
        self.validation_errors.extend(
            outcome_errors(
                self.inventory,
                self.assigned,
                self.outcomes,
                self.backend,
                self.scope,
                self.manifest,
            )
        )
        junit = self.config.getoption("xmlpath")
        if not junit or not Path(junit).is_file():
            self.validation_errors.append("missing final JUnit report")
        if self.collection_errors or self.validation_errors:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        self.write_receipt(
            complete=self.collection_finished
            and int(session.exitstatus) == 0
            and not self.collection_errors
            and not self.validation_errors,
            exitstatus=int(session.exitstatus),
        )

    def pytest_terminal_summary(self, terminalreporter):
        if self.validation_errors:
            terminalreporter.write_sep(
                "=", "Exact collected coverage rejected", red=True
            )
            for error in self.validation_errors[:20]:
                terminalreporter.write_line(error[:500], red=True)
