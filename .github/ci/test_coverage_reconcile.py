"""Standalone verifier self-tests, deliberately outside product test collection."""

from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "coverage_reconcile", Path(__file__).with_name("coverage_reconcile.py")
)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

NODES = [
    ("tests/test_local_interop_demo.py::test_file", "file"),
    ("tests/test_local_interop_demo.py::test_postgres", "postgres"),
    ("tests/test_local_interop_demo.py::test_shared", "both"),
    ("tests/test_optional.py::test_manual", "both"),
    ('tests/test_values.py::TestUnicode::test_value[a::b<"&\\雪]', "both"),
    ("tests/test_new.py::test_added", "both"),
]
OPTIONAL = NODES[3][0]
OPTIONAL_REASON = "Explicit historical opt-in contract"


def report(when="call", outcome="passed", reason=None, wasxfail=False):
    return {
        "when": when,
        "outcome": outcome,
        "wasxfail": wasxfail,
        "skip_reason": reason,
    }


def write_xml(path: Path, receipt: dict) -> None:
    root = ET.Element("testsuites")
    suite = ET.SubElement(
        root,
        "testsuite",
        tests=str(len(receipt["outcomes"])),
        failures="0",
        errors="0",
        skipped="0",
    )
    skips = 0
    for item in receipt["outcomes"]:
        case = ET.SubElement(
            suite,
            "testcase",
            classname="intentionally.not.reconstructable",
            name="display-only",
        )
        properties = ET.SubElement(case, "properties")
        ET.SubElement(properties, "property", name="ci_nodeid", value=item["nodeid"])
        for phase in item["reports"]:
            if phase["outcome"] == "skipped":
                ET.SubElement(
                    case, "skipped", type="pytest.skip", message=phase["skip_reason"]
                )
                skips += 1
    suite.set("skipped", str(skips))
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


class Evidence:
    def __init__(
        self,
        root: Path,
        *,
        scope="backend",
        shards=None,
        compressed=False,
        external_tcp=False,
    ):
        nodes = NODES + (
            [(node, "file") for node in gate.TCP_NODES] if external_tcp else []
        )
        self.root = root
        self.receipts = root / "receipts"
        self.receipts.mkdir()
        self.scope = scope
        self.shards = shards or {"file": 1, "postgres": 2}
        self.constraints = root / "constraints.txt"
        self.constraints.write_text("pytest==8.4.2\n", encoding="utf-8")
        source = root / "tests/test_frozen.py"
        source.parent.mkdir()
        source.write_text("# frozen test source\n", encoding="utf-8")
        sources = {"tests/test_frozen.py": gate._digest(source)}
        for filename in {node.split("::", 1)[0] for node, _ in nodes}:
            path = root / filename
            path.write_text("# frozen synthetic product source\n", encoding="utf-8")
            sources[filename] = gate._digest(path)
        self.manifest_path = root / (
            "manifest.json.gz" if compressed else "manifest.json"
        )
        self.manifest = {
            "schema_version": 1,
            "product_nodes": [node for node, _ in nodes],
            "added_nodes": [NODES[-1][0]],
            "source_files": sources,
            "skips": {
                "file": {OPTIONAL: OPTIONAL_REASON},
                "postgres": {OPTIONAL: OPTIONAL_REASON},
            },
        }
        if external_tcp:
            self.manifest["external_gates"] = {
                "file": {
                    node: {
                        "reason": gate.TCP_REASON,
                        "junit_filename": gate.TCP_JUNIT_FILENAME,
                    }
                    for node in gate.TCP_NODES
                },
                "postgres": {},
            }
            for backend in ("file", "postgres"):
                self.manifest["skips"][backend].update(
                    dict.fromkeys(gate.TCP_NODES, gate.TCP_REASON)
                )
        self.save_manifest()
        self.identity = {
            "checked_out_sha": "a" * 40,
            "source_tree": "b" * 40,
            "event_sha": "a" * 40,
            "run_id": "12345",
            "run_attempt": "2",
            "python_version": "3.11.9",
            "platform": "linux",
            "source_manifest_sha256": gate._digest(self.manifest_path),
            "dependency_digest": gate._digest(self.constraints),
            "repository": "owner/repository",
        }
        self.expected = {key: self.identity[key] for key in gate.ANCHOR_KEYS}
        self.inventory = [
            {"nodeid": node, "backend": backend}
            for node, backend in nodes
            if scope != "interop" or gate._interop_node(node)
        ]
        self.paths = []
        for backend, count in self.shards.items():
            for index in range(count):
                directory = self.receipts / f"{backend}-{index}"
                directory.mkdir()
                path = directory / "coverage.json"
                assigned = [
                    item["nodeid"]
                    for item in self.inventory
                    if gate.assigned_shard(item["nodeid"], count) == index
                ]
                outcomes = []
                for node in assigned:
                    classification = next(
                        item["backend"]
                        for item in self.inventory
                        if item["nodeid"] == node
                    )
                    reason = (
                        gate.OPPOSITE_REASONS[backend]
                        if classification not in {"both", backend}
                        else None
                    )
                    if node == OPTIONAL:
                        reason = OPTIONAL_REASON
                    if external_tcp and node in gate.TCP_NODES:
                        reason = gate.TCP_REASON
                    reports = (
                        [report("setup", "skipped", reason), report("teardown")]
                        if reason
                        else [report("setup"), report("call"), report("teardown")]
                    )
                    outcomes.append({"nodeid": node, "reports": reports})
                receipt = {
                    "schema_version": 1,
                    "scope": scope,
                    "identity": copy.deepcopy(self.identity),
                    "backend": backend,
                    "shard": {"index": index, "count": count},
                    "inventory": copy.deepcopy(self.inventory),
                    "inventory_digest": gate.inventory_digest(self.inventory),
                    "assigned": assigned,
                    "outcomes": outcomes,
                    "pytest_exitstatus": 0,
                    "collection_errors": [],
                    "validation_errors": [],
                    "complete": True,
                    "junit_filename": "backend.xml"
                    if scope == "backend"
                    else "local-interop.xml",
                }
                self.paths.append(path)
                self.save(path, receipt, xml=True)
                if external_tcp and scope == "backend" and backend == "file":
                    root = ET.Element("testsuites")
                    suite = ET.SubElement(
                        root,
                        "testsuite",
                        tests="2",
                        failures="0",
                        errors="0",
                        skipped="0",
                    )
                    for classname, name in gate.TCP_JUNIT_IDENTITIES:
                        ET.SubElement(suite, "testcase", classname=classname, name=name)
                    ET.ElementTree(root).write(
                        directory / gate.TCP_JUNIT_FILENAME, encoding="utf-8"
                    )

    def save_manifest(self):
        raw = json.dumps(self.manifest).encode("utf-8")
        if self.manifest_path.suffix == ".gz":
            self.manifest_path.write_bytes(gzip.compress(raw, mtime=0))
        else:
            self.manifest_path.write_bytes(raw)

    def update_manifest(self):
        self.save_manifest()
        for path in self.paths:
            receipt = json.loads(path.read_text())
            receipt["identity"]["source_manifest_sha256"] = gate._digest(
                self.manifest_path
            )
            self.save(path, receipt)

    def load(self, index=0):
        return json.loads(self.paths[index].read_text(encoding="utf-8"))

    def save(self, path, receipt, *, xml=False):
        path.write_text(json.dumps(receipt), encoding="utf-8")
        if xml:
            write_xml(path.parent / receipt["junit_filename"], receipt)

    def check(self):
        return gate.reconcile(
            self.receipts,
            self.manifest_path,
            scope=self.scope,
            expected_identity=self.expected,
            expected_shards=self.shards,
            constraints_path=self.constraints,
            source_root=self.root,
        )

    def xml(self, index=0):
        path = self.paths[index].parent / self.load(index)["junit_filename"]
        return path, ET.parse(path)


@pytest.fixture
def evidence(tmp_path):
    return Evidence(tmp_path)


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize(
    "shards", [{"file": 1, "postgres": 2}, {"file": 1, "postgres": 1}]
)
def test_exact_disjoint_complete_profiles(tmp_path, compressed, shards):
    result = Evidence(tmp_path, shards=shards, compressed=compressed).check()
    assert result["status"] == "complete"
    assert result["unique_collected_per_profile"] == 6
    for backend in shards:
        assert result["profiles"][backend] == {
            "collected": 6,
            "passed": 4,
            "skipped": 2,
            "shards": shards[backend],
        }


@pytest.mark.parametrize(
    "shards", [{"file": 1}, {"postgres": 1}, {"file": 1, "postgres": 1}]
)
def test_interop_scope_exact_subset(tmp_path, shards):
    result = Evidence(tmp_path, scope="interop", shards=shards).check()
    assert result["unique_collected_per_profile"] == 3
    assert set(result["profiles"]) == set(shards)


def test_reviewed_optional_call_skip(evidence):
    for path in evidence.paths:
        receipt = json.loads(path.read_text())
        for item in receipt["outcomes"]:
            if item["nodeid"] == OPTIONAL:
                item["reports"] = [
                    report("setup"),
                    report("call", "skipped", OPTIONAL_REASON),
                    report("teardown"),
                ]
        evidence.save(path, receipt, xml=True)
    assert evidence.check()["status"] == "complete"


def test_original_tcp_external_gate_does_not_inflate_full_suite_counts(tmp_path):
    result = Evidence(tmp_path, external_tcp=True).check()
    assert result["unique_collected_per_profile"] == 8
    assert result["profiles"]["file"] == {
        "collected": 8,
        "passed": 4,
        "skipped": 4,
        "shards": 1,
    }
    assert result["external_gates"] == {
        "file": {
            gate.TCP_JUNIT_FILENAME: {"passed": 2, "nodeids": list(gate.TCP_NODES)}
        }
    }


@pytest.mark.parametrize("scope", ["backend", "interop"])
def test_frozen_opposite_skipif_reason_only_accepted_in_full_backend(tmp_path, scope):
    evidence = Evidence(tmp_path, scope=scope)
    node = NODES[1][0]
    legacy_reason = "original missing-database skipif precedes profile skip"
    evidence.manifest["skips"]["file"][node] = legacy_reason
    evidence.update_manifest()
    receipt = evidence.load()
    next(item for item in receipt["outcomes"] if item["nodeid"] == node)["reports"][0][
        "skip_reason"
    ] = legacy_reason
    evidence.save(evidence.paths[0], receipt, xml=True)
    if scope == "backend":
        assert evidence.check()["status"] == "complete"
    else:
        with pytest.raises(gate.CoverageError, match="unexpected skip reason"):
            evidence.check()


def test_applicable_postgres_cannot_use_frozen_skip_allowlist(evidence):
    node = NODES[1][0]
    evidence.manifest["skips"]["postgres"][node] = "database unavailable"
    evidence.update_manifest()
    for path in evidence.paths[1:]:
        receipt = json.loads(path.read_text())
        for item in receipt["outcomes"]:
            if item["nodeid"] == node:
                item["reports"] = [
                    report("setup", "skipped", "database unavailable"),
                    report("teardown"),
                ]
        evidence.save(path, receipt, xml=True)
    with pytest.raises(gate.CoverageError, match="applicable backend contract skipped"):
        evidence.check()


def test_opposite_profile_successful_call_rejected(evidence):
    receipt = evidence.load()
    receipt["outcomes"][1]["reports"] = [report("setup"), report(), report("teardown")]
    evidence.save(evidence.paths[0], receipt, xml=True)
    with pytest.raises(
        gate.CoverageError, match="opposite-profile contract did not skip"
    ):
        evidence.check()


@pytest.mark.parametrize(
    "change",
    [
        "missing-manifest",
        "missing-node",
        "extra-node",
        "wrong-reason",
        "wrong-filename",
        "postgres-gate",
        "wrong-skip-reason",
    ],
)
def test_external_tcp_exception_cannot_expand_or_disappear(tmp_path, change):
    evidence = Evidence(tmp_path, external_tcp=True)
    external = evidence.manifest["external_gates"]
    if change == "missing-manifest":
        evidence.manifest.pop("external_gates")
    elif change == "missing-node":
        external["file"].pop(gate.TCP_NODES[0])
    elif change == "extra-node":
        external["file"][NODES[0][0]] = {
            "reason": gate.TCP_REASON,
            "junit_filename": gate.TCP_JUNIT_FILENAME,
        }
    elif change == "wrong-reason":
        external["file"][gate.TCP_NODES[0]]["reason"] = "different reason"
    elif change == "wrong-filename":
        external["file"][gate.TCP_NODES[0]]["junit_filename"] = "../other.xml"
    elif change == "postgres-gate":
        external["postgres"] = copy.deepcopy(external["file"])
    else:
        evidence.manifest["skips"]["file"][gate.TCP_NODES[0]] = "different reason"
    evidence.update_manifest()
    with pytest.raises(gate.CoverageError, match="external gate|external TCP"):
        evidence.check()


def test_original_tcp_nodes_cannot_change_classification(tmp_path):
    evidence = Evidence(tmp_path, external_tcp=True)
    for path in evidence.paths:
        receipt = json.loads(path.read_text())
        for item in receipt["inventory"]:
            if item["nodeid"] in gate.TCP_NODES:
                item["backend"] = "both"
        receipt["inventory_digest"] = gate.inventory_digest(receipt["inventory"])
        evidence.save(path, receipt)
    with pytest.raises(gate.CoverageError, match="File-only classification"):
        evidence.check()


def test_external_tcp_source_cannot_be_removed_from_frozen_proof(tmp_path):
    evidence = Evidence(tmp_path, external_tcp=True)
    evidence.manifest["source_files"].pop("tests/test_r5_offline_sync_tcp.py")
    evidence.update_manifest()
    with pytest.raises(gate.CoverageError, match="source_files missing"):
        evidence.check()


def test_fixed_external_mapping_matches_real_pytest_xml(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")
    (tests / "test_r5_offline_sync_tcp.py").write_text(
        "\n".join(
            f"def {node.split('::')[1]}():\n    assert True\n"
            for node in gate.TCP_NODES
        )
    )
    xml = tmp_path / gate.TCP_JUNIT_FILENAME
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-q",
            "tests/test_r5_offline_sync_tcp.py",
            f"--junitxml={xml}",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    gate._junit(xml, dict.fromkeys(gate.TCP_NODES), external_tcp=True)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "truncated",
        "missing-case",
        "extra-case",
        "duplicate-case",
        "failure",
        "error",
        "skip",
        "xfail",
        "wrong-name",
        "wrong-classname",
        "parametrized-name",
        "count",
        "skip-count",
        "conflicting-property",
        "duplicate-property",
    ],
)
def test_external_tcp_raw_junit_must_prove_exact_two_passes(tmp_path, change):
    evidence = Evidence(tmp_path, external_tcp=True)
    path = evidence.paths[0].parent / gate.TCP_JUNIT_FILENAME
    tree = ET.parse(path)
    suite = tree.getroot().find("testsuite")
    case = suite.find("testcase")
    if change == "missing":
        path.unlink()
    elif change == "truncated":
        path.write_text("<testsuites><testsuite>")
    else:
        if change == "missing-case":
            suite.remove(case)
            suite.set("tests", "1")
        elif change == "extra-case":
            ET.SubElement(
                suite, "testcase", classname="tests.test_other", name="test_unrelated"
            )
            suite.set("tests", "3")
        elif change == "duplicate-case":
            suite.append(copy.deepcopy(case))
            suite.set("tests", "3")
        elif change in {"failure", "error"}:
            ET.SubElement(case, change)
        elif change in {"skip", "xfail"}:
            ET.SubElement(
                case,
                "skipped",
                type="pytest.skip" if change == "skip" else "pytest.xfail",
                message=gate.TCP_REASON,
            )
            suite.set("skipped", "1")
        elif change == "wrong-name":
            case.set("name", "test_unrelated")
        elif change == "wrong-classname":
            case.set("classname", "tests.test_unrelated")
        elif change == "parametrized-name":
            case.set("name", case.get("name") + "[parameter]")
        elif change == "count":
            suite.set("tests", "999")
        elif change == "skip-count":
            suite.set("skipped", "1")
        else:
            properties = ET.SubElement(case, "properties")
            ET.SubElement(
                properties,
                "property",
                name="ci_nodeid",
                value="wrong"
                if change == "conflicting-property"
                else gate.TCP_NODES[0],
            )
            if change == "duplicate-property":
                ET.SubElement(
                    properties, "property", name="ci_nodeid", value=gate.TCP_NODES[0]
                )
        tree.write(path, encoding="utf-8")
    with pytest.raises(gate.CoverageError, match="JUnit"):
        evidence.check()


@pytest.mark.parametrize("key", sorted(gate.IDENTITY_KEYS) + ["repository"])
def test_cross_shard_identity_mismatch(evidence, key):
    receipt = evidence.load(1)
    receipt["identity"][key] = "different"
    evidence.save(evidence.paths[1], receipt)
    with pytest.raises(gate.CoverageError, match="identity"):
        evidence.check()


@pytest.mark.parametrize("key", sorted(gate.ANCHOR_KEYS))
def test_all_shards_agreeing_on_wrong_run_still_fail(evidence, key):
    for path in evidence.paths:
        receipt = json.loads(path.read_text())
        receipt["identity"][key] = "wrong"
        evidence.save(path, receipt)
    with pytest.raises(gate.CoverageError, match=f"wrong identity {key}"):
        evidence.check()


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("complete", False, "session-finish"),
        ("complete", 1, "session-finish"),
        ("pytest_exitstatus", 1, "exit status"),
        ("pytest_exitstatus", 2, "exit status"),
        ("pytest_exitstatus", 3, "exit status"),
        ("pytest_exitstatus", 5, "exit status"),
        ("pytest_exitstatus", False, "exit status"),
        ("collection_errors", ["collection failed"], "collection errors"),
        ("validation_errors", ["external deselection"], "validation errors"),
        ("schema_version", True, "schema_version"),
        ("scope", "other", "scope"),
        ("backend", "unknown", "backend"),
        ("shard", {"index": 0, "count": 2}, "shard index/count"),
        ("shard", {"index": True, "count": 1}, "shard metadata"),
        ("junit_filename", "../other.xml", "JUnit filename"),
        ("inventory_digest", "wrong", "digest"),
        ("outcomes", [], "observed node set"),
        ("assigned", [], "assignment"),
    ],
)
def test_invalid_receipt_fields(evidence, field, value, match):
    receipt = evidence.load()
    receipt[field] = value
    evidence.save(evidence.paths[0], receipt)
    with pytest.raises(gate.CoverageError, match=match):
        evidence.check()


def test_missing_shard(evidence):
    evidence.paths[1].unlink()
    with pytest.raises(gate.CoverageError, match="missing or extra"):
        evidence.check()


def test_duplicate_shard(evidence):
    evidence.save(evidence.paths[2], evidence.load(1))
    with pytest.raises(gate.CoverageError, match="duplicate shard"):
        evidence.check()


def test_extra_receipt(evidence):
    directory = evidence.receipts / "historical-attempt"
    directory.mkdir()
    evidence.save(directory / "coverage.json", evidence.load())
    with pytest.raises(gate.CoverageError, match="missing or extra"):
        evidence.check()


@pytest.mark.parametrize(
    "change",
    ["omit-original", "omit-new", "duplicate", "reorder", "unstable-id", "unknown"],
)
def test_inventory_drift_even_when_receipts_agree(evidence, change):
    for path in evidence.paths:
        receipt = json.loads(path.read_text())
        inventory = receipt["inventory"]
        if change == "omit-original":
            inventory.pop(0)
        elif change == "omit-new":
            inventory.pop(-1)
        elif change == "duplicate":
            inventory.append(copy.deepcopy(inventory[0]))
        elif change == "reorder":
            inventory.reverse()
        else:
            inventory[0]["nodeid"] += (
                "[unknown-uuid-drift]" if change == "unstable-id" else "-unknown"
            )
        receipt["inventory_digest"] = gate.inventory_digest(inventory)
        evidence.save(path, receipt)
    with pytest.raises(gate.CoverageError, match="inventory|duplicate"):
        evidence.check()


def test_marker_disagreement(evidence):
    receipt = evidence.load(1)
    receipt["inventory"][0]["backend"] = "both"
    receipt["inventory_digest"] = gate.inventory_digest(receipt["inventory"])
    evidence.save(evidence.paths[1], receipt)
    with pytest.raises(gate.CoverageError, match="classification mismatch"):
        evidence.check()


def test_contradictory_markers(evidence):
    receipt = evidence.load()
    receipt["inventory"][0]["backend"] = ["file", "postgres"]
    evidence.save(evidence.paths[0], receipt)
    with pytest.raises(gate.CoverageError, match="contradictory"):
        evidence.check()


@pytest.mark.parametrize("change", ["overlap", "wrong-hash", "duplicate", "order"])
def test_assignment_must_be_exact_hash_partition(evidence, change):
    receipt = evidence.load(1)
    if change in {"overlap", "wrong-hash"}:
        receipt["assigned"].append(evidence.load(2)["assigned"][0])
    elif change == "duplicate":
        receipt["assigned"].append(receipt["assigned"][0])
    else:
        receipt = evidence.load()
        receipt["assigned"].reverse()
    index = 0 if change == "order" else 1
    evidence.save(evidence.paths[index], receipt)
    with pytest.raises(gate.CoverageError, match="assignment|duplicate"):
        evidence.check()


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "unknown",
        "missing-call",
        "missing-teardown",
        "duplicate-phase",
        "setup-failure",
        "call-failure",
        "teardown-failure",
        "xfail",
        "xpass",
        "malformed-phase",
    ],
)
def test_incomplete_or_unsuccessful_observation(evidence, change):
    receipt = evidence.load()
    item = receipt["outcomes"][0]
    if change == "missing":
        receipt["outcomes"].pop(0)
    elif change == "duplicate":
        receipt["outcomes"].append(copy.deepcopy(item))
    elif change == "unknown":
        item["nodeid"] = "tests/test_unknown.py::test_unknown"
    elif change == "missing-call":
        item["reports"].pop(1)
    elif change == "missing-teardown":
        item["reports"].pop(-1)
    elif change == "duplicate-phase":
        item["reports"].append(report("teardown"))
    elif change.endswith("failure"):
        phase = change.removesuffix("-failure")
        next(value for value in item["reports"] if value["when"] == phase)[
            "outcome"
        ] = "failed"
    elif change in {"xfail", "xpass"}:
        item["reports"][1]["wasxfail"] = True
    else:
        item["reports"][0]["when"] = []
    evidence.save(evidence.paths[0], receipt)
    with pytest.raises(gate.CoverageError, match="outcomes|phase|xfail"):
        evidence.check()


@pytest.mark.parametrize(
    "change",
    [
        "unknown-reason",
        "applicable-contract",
        "opposite-call",
        "skip-teardown",
        "unapproved-node",
    ],
)
def test_skips_fail_closed(evidence, change):
    receipt = evidence.load()
    item = receipt["outcomes"][1]
    if change == "unknown-reason":
        item["reports"][0]["skip_reason"] = "database unavailable"
    elif change == "opposite-call":
        item["reports"] = [
            report("setup"),
            report("call", "skipped", gate.OPPOSITE_REASONS["file"]),
            report("teardown"),
        ]
    elif change == "skip-teardown":
        item["reports"][1] = report(
            "teardown", "skipped", gate.OPPOSITE_REASONS["file"]
        )
    else:
        item = receipt["outcomes"][0 if change == "applicable-contract" else 2]
        item["reports"] = [
            report("setup", "skipped", OPTIONAL_REASON),
            report("teardown"),
        ]
        if change == "applicable-contract":
            evidence.manifest["skips"]["file"][item["nodeid"]] = OPTIONAL_REASON
            evidence.save_manifest()
            for path in evidence.paths:
                other = json.loads(path.read_text())
                other["identity"]["source_manifest_sha256"] = gate._digest(
                    evidence.manifest_path
                )
                evidence.save(path, other)
            receipt["identity"]["source_manifest_sha256"] = gate._digest(
                evidence.manifest_path
            )
    evidence.save(evidence.paths[0], receipt, xml=True)
    with pytest.raises(gate.CoverageError, match="skip"):
        evidence.check()


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "truncated",
        "missing-property",
        "duplicate-property",
        "wrong-node",
        "duplicate-case",
        "missing-case",
        "failure",
        "error",
        "count",
        "skip-count",
        "xfail",
        "skip-reason",
        "pass-as-skip",
    ],
)
def test_raw_junit_reconciliation(evidence, change):
    path, tree = evidence.xml()
    root = tree.getroot()
    suite = root.find("testsuite")
    case = suite.find("testcase")
    skipped = suite.findall("testcase")[1].find("skipped")
    if change == "missing":
        path.unlink()
    elif change == "truncated":
        path.write_text("<testsuites><testsuite>")
    else:
        if change == "missing-property":
            case.remove(case.find("properties"))
        elif change == "duplicate-property":
            case.find("properties").append(
                copy.deepcopy(case.find("properties/property"))
            )
        elif change == "wrong-node":
            case.find("properties/property").set("value", "test_unknown")
        elif change == "duplicate-case":
            suite.append(copy.deepcopy(case))
        elif change == "missing-case":
            suite.remove(case)
            suite.set("tests", str(int(suite.get("tests")) - 1))
        elif change in {"failure", "error"}:
            ET.SubElement(case, change)
        elif change == "count":
            suite.set("tests", "999")
        elif change == "skip-count":
            suite.set("skipped", "999")
        elif change == "xfail":
            skipped.set("type", "pytest.xfail")
        elif change == "skip-reason":
            skipped.set("message", "different reason")
        else:
            ET.SubElement(case, "skipped", type="pytest.skip", message=OPTIONAL_REASON)
        tree.write(path, encoding="utf-8")
    with pytest.raises(gate.CoverageError, match="JUnit"):
        evidence.check()


def test_manifest_and_dependency_digests_are_independent(evidence):
    evidence.constraints.write_text("pytest==8.4.1\n")
    with pytest.raises(gate.CoverageError, match="dependency_digest"):
        evidence.check()


@pytest.mark.parametrize("change", ["missing", "changed", "escape"])
def test_frozen_source_files_checked_independently(evidence, change):
    source = evidence.root / "tests/test_frozen.py"
    if change == "missing":
        source.unlink()
    elif change == "changed":
        source.write_text("# changed source\n")
    else:
        evidence.manifest["source_files"]["../escape.py"] = "a" * 64
        evidence.save_manifest()
    with pytest.raises(gate.CoverageError, match="read|digest|escapes"):
        evidence.check()


def test_duplicate_json_keys_rejected(evidence):
    raw = evidence.paths[0].read_text()
    evidence.paths[0].write_text(
        raw.replace('"complete": true', '"complete": false, "complete": true')
    )
    with pytest.raises(gate.CoverageError, match="duplicate JSON key"):
        evidence.check()


def test_multimegabyte_raw_node_id_survives_exact_junit_mapping(tmp_path):
    node = "tests/test_payload.py::test_security[" + "x" * 4_194_304 + "]"
    path = tmp_path / "backend.xml"
    write_xml(
        path,
        {
            "outcomes": [
                {
                    "nodeid": node,
                    "reports": [report("setup"), report(), report("teardown")],
                }
            ]
        },
    )
    gate._junit(path, {node: None})
    with pytest.raises(gate.CoverageError, match="unknown or unassigned"):
        gate._junit(path, {node + "x": None})


def test_real_pytest_plugin_shards_reconcile(tmp_path):
    """Exercise actual hook ordering and pytest-generated XML, without product fixtures."""
    tests = tmp_path / "tests"
    tests.mkdir()
    ci = tmp_path / ".github/ci"
    ci.mkdir(parents=True)
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\ntestpaths = tests\nmarkers =\n    file_backend_only\n    postgres_backend_only\n"
    )
    (tests / "test_fixture.py").write_text(
        "import pytest\n"
        "@pytest.mark.file_backend_only\ndef test_file():\n    assert True\n"
        "@pytest.mark.postgres_backend_only\ndef test_postgres():\n    assert True\n"
        "def test_both():\n    assert True\n"
        f"@pytest.mark.skip(reason={OPTIONAL_REASON!r})\ndef test_optional():\n    assert False\n"
    )
    (tests / "conftest.py").write_text(
        "import os\nimport pytest\n"
        "def pytest_collection_modifyitems(items):\n"
        "    backend = os.environ['STORAGE_BACKEND']\n"
        "    for item in items:\n"
        "        if backend == 'file' and item.get_closest_marker('postgres_backend_only'):\n"
        f"            item.add_marker(pytest.mark.skip(reason={gate.OPPOSITE_REASONS['file']!r}))\n"
        "        if backend == 'postgres' and item.get_closest_marker('file_backend_only'):\n"
        f"            item.add_marker(pytest.mark.skip(reason={gate.OPPOSITE_REASONS['postgres']!r}))\n"
    )
    constraints = ci / "python-constraints.txt"
    constraints.write_text("pytest==8.4.2\n")
    nodes = [
        "tests/test_fixture.py::test_" + suffix
        for suffix in ("file", "postgres", "both", "optional")
    ]
    manifest = {
        "schema_version": 1,
        "product_nodes": nodes,
        "added_nodes": [],
        "source_files": {
            path.relative_to(tmp_path).as_posix(): gate._digest(path)
            for path in tests.glob("*.py")
        },
        "skips": {
            backend: {nodes[-1]: OPTIONAL_REASON} for backend in ("file", "postgres")
        },
    }
    manifest_path = ci / "coverage_manifest.json.gz"
    manifest_path.write_bytes(gzip.compress(json.dumps(manifest).encode(), mtime=0))
    receipts = tmp_path / "receipts"
    identity = {
        "checked_out_sha": "a" * 40,
        "source_tree": "b" * 40,
        "event_sha": "a" * 40,
        "run_id": "12345",
        "run_attempt": "2",
    }
    environment = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parent),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "CI_COVERAGE_SHA": identity["checked_out_sha"],
        "CI_COVERAGE_TREE": identity["source_tree"],
        "GITHUB_SHA": identity["event_sha"],
        "GITHUB_RUN_ID": identity["run_id"],
        "GITHUB_RUN_ATTEMPT": identity["run_attempt"],
        "GITHUB_REPOSITORY": "owner/repository",
    }
    for backend, count in {"file": 1, "postgres": 2}.items():
        for index in range(count):
            directory = receipts / f"{backend}-{index}"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-p",
                    "suite_coverage",
                    "-p",
                    "no:cacheprovider",
                    "-q",
                    f"--ci-coverage-dir={directory}",
                    f"--ci-shard-index={index}",
                    f"--ci-shard-count={count}",
                    f"--junitxml={directory / 'backend.xml'}",
                ],
                cwd=tmp_path,
                env={**environment, "STORAGE_BACKEND": backend},
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert completed.returncode == 0, completed.stdout + completed.stderr
    result = gate.reconcile(
        receipts,
        manifest_path,
        scope="backend",
        expected_identity=identity,
        constraints_path=constraints,
        source_root=tmp_path,
    )
    assert result["unique_collected_per_profile"] == 4
    assert all(
        profile["passed"] == profile["skipped"] == 2
        for profile in result["profiles"].values()
    )


def test_cli_success_and_failure_are_read_only_except_requested_summary(
    evidence, capsys
):
    output = evidence.root / "summary.json"
    arguments = [
        "--manifest",
        str(evidence.manifest_path),
        "--scope",
        "backend",
        "--receipts-dir",
        str(evidence.receipts),
        "--expected-sha",
        evidence.identity["checked_out_sha"],
        "--expected-tree",
        evidence.identity["source_tree"],
        "--expected-run",
        "12345",
        "--expected-attempt",
        "2",
        "--constraints",
        str(evidence.constraints),
        "--source-root",
        str(evidence.root),
        "--expected-repository",
        "owner/repository",
        "--expected-shards",
        "file=1",
        "postgres=2",
        "--output",
        str(output),
    ]
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in evidence.receipts.rglob("*")
        if path.is_file()
    }
    assert gate.main(arguments) == 0
    assert json.loads(output.read_text())["status"] == "complete"
    assert before == {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before
    }
    evidence.paths[0].unlink()
    assert gate.main(arguments) == 1
    assert "Coverage reconciliation failed" in capsys.readouterr().err
