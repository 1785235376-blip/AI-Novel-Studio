"""Additive TCP infrastructure tests; synthetic fixtures never claim product passes."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import tcp_evidence as tcp
import test_coverage_reconcile as fixtures

gate = tcp.gate


class Evidence:
    def __init__(self, root):
        self.base = fixtures.Evidence(root, external_tcp=True)
        self.root = root
        self.tcp = root / "tcp"
        self.tcp.mkdir()
        self.output = root / "joined"
        self.identity = self.base.identity
        self.expected = {key: self.identity[key] for key in tcp.EXPECTED_KEYS}
        for path in self.base.paths:
            (path.parent / tcp.PACKAGES).write_text("pytest==8.4.2\n")
        (self.tcp / tcp.PACKAGES).write_text("pytest==8.4.2\n")
        original = self.base.paths[0].parent / gate.TCP_JUNIT_FILENAME
        (self.tcp / gate.TCP_JUNIT_FILENAME).write_bytes(original.read_bytes())
        original.unlink()
        (self.tcp / tcp.LOG).write_text("Synthetic infrastructure fixture, not product execution.\n")
        self.receipt = {"schema_version": 1, "scope": "original-file-tcp", "identity": copy.deepcopy(self.identity),
                        "complete": True, "pytest_exitstatus": 0, "validation_errors": [],
                        "nodes": list(gate.TCP_NODES),
                        "environment": {"RUN_B10_TCP_SYNC_TEST": "1", "STORAGE_BACKEND": "file"},
                        "command": tcp.tcp_command(root / "pytest", self.tcp),
                        "source_sha256_before": copy.deepcopy(self.base.manifest["source_files"]),
                        "source_sha256_after": copy.deepcopy(self.base.manifest["source_files"]),
                        "installed_dependencies_sha256": gate._digest(self.tcp / tcp.PACKAGES),
                        "junit_filename": gate.TCP_JUNIT_FILENAME,
                        "junit_sha256": gate._digest(self.tcp / gate.TCP_JUNIT_FILENAME),
                        "log_filename": tcp.LOG, "log_sha256": gate._digest(self.tcp / tcp.LOG),
                        "started_utc": "2026-10-09T08:00:00+00:00", "finished_utc": "2026-10-09T08:01:00+00:00"}
        self.save()

    def save(self):
        tcp.write_json(self.tcp / tcp.RECEIPT, self.receipt)

    def join(self, **kwargs):
        return tcp.join(self.base.receipts, self.tcp, self.output, self.base.manifest_path,
                        self.base.constraints, self.root, self.expected,
                        execution_result=kwargs.get("execution_result", "success"),
                        tcp_result=kwargs.get("tcp_result", "success"))

    def change_xml(self, edit):
        path = self.tcp / gate.TCP_JUNIT_FILENAME
        tree = ET.parse(path)
        edit(tree.getroot())
        tree.write(path, encoding="utf-8")
        self.receipt["junit_sha256"] = gate._digest(path)
        self.save()


@pytest.fixture
def evidence(tmp_path):
    return Evidence(tmp_path)


def test_valid_join_is_byte_identical_and_original_reconciler_accepts(evidence):
    before = tcp.artifact_snapshot(evidence.base.receipts)
    original_tcp = tcp.artifact_snapshot(evidence.tcp)
    result = evidence.join()
    assert result["status"] == "complete"
    assert result["coverage"]["profiles"]["file"]["collected"] == 8
    assert result["coverage"]["external_gates"]["file"][gate.TCP_JUNIT_FILENAME]["passed"] == 2
    assert tcp.artifact_snapshot(evidence.base.receipts) == before
    assert tcp.artifact_snapshot(evidence.tcp) == original_tcp
    assert (evidence.output / result["tcp_destination"]).read_bytes() == (evidence.tcp / gate.TCP_JUNIT_FILENAME).read_bytes()
    assert gate.reconcile(evidence.output, evidence.base.manifest_path, scope="backend",
                          expected_identity=evidence.expected, source_root=evidence.root,
                          constraints_path=evidence.base.constraints)["status"] == "complete"


@pytest.mark.parametrize("key", sorted(gate.IDENTITY_KEYS | {"repository"}))
def test_wrong_tcp_identity_rejected(evidence, key):
    evidence.receipt["identity"][key] = "foreign"
    evidence.save()
    with pytest.raises(gate.CoverageError, match="identity"):
        evidence.join()


@pytest.mark.parametrize("key", sorted(tcp.EXPECTED_KEYS))
def test_missing_independent_expected_identity_rejected(evidence, key):
    del evidence.expected[key]
    with pytest.raises(gate.CoverageError, match="missing expected"):
        evidence.join()


@pytest.mark.parametrize("status", ["failure", "cancelled", "skipped", "", "in_progress", "neutral"])
@pytest.mark.parametrize("job", ["execution_result", "tcp_result"])
def test_missing_failed_cancelled_skipped_or_pending_job_never_green(evidence, status, job):
    with pytest.raises(gate.CoverageError, match="must succeed"):
        evidence.join(**{job: status})
    assert not evidence.output.exists()


@pytest.mark.parametrize("filename", [tcp.RECEIPT, gate.TCP_JUNIT_FILENAME, tcp.LOG, tcp.PACKAGES])
def test_missing_tcp_artifacts_rejected(evidence, filename):
    (evidence.tcp / filename).unlink()
    with pytest.raises((gate.CoverageError, OSError)):
        evidence.join()


@pytest.mark.parametrize("filename", [tcp.RECEIPT, gate.TCP_JUNIT_FILENAME])
def test_duplicate_tcp_artifacts_rejected(evidence, filename):
    duplicate = evidence.tcp / "duplicate"
    duplicate.mkdir()
    (duplicate / filename).write_bytes((evidence.tcp / filename).read_bytes())
    with pytest.raises(gate.CoverageError, match="duplicate"):
        evidence.join()


@pytest.mark.parametrize("key,value", [("complete", False), ("complete", None),
    ("pytest_exitstatus", 1), ("pytest_exitstatus", -15), ("pytest_exitstatus", None),
    ("pytest_exitstatus", False), ("validation_errors", ["partial source"]),
    ("nodes", [gate.TCP_NODES[0]]), ("nodes", [gate.TCP_NODES[0]] * 2),
    ("source_sha256_before", {}), ("source_sha256_after", None),
    ("installed_dependencies_sha256", "wrong"), ("junit_sha256", "wrong"),
    ("log_sha256", "wrong"), ("environment", {"STORAGE_BACKEND": "file"}),
    ("finished_utc", None), ("schema_version", True), ("command", ["pytest", "-k", "one"]),
    ("junit_filename", "foreign.xml"), ("scope", "foreign")])
def test_incomplete_or_tampered_tcp_receipt_rejected(evidence, key, value):
    evidence.receipt[key] = value
    evidence.save()
    with pytest.raises(gate.CoverageError):
        evidence.join()


@pytest.mark.parametrize("change", ["skip", "failure", "error", "missing", "duplicate", "wrong-node", "truncated", "false-count"])
def test_original_junit_validator_rejects_forged_raw_tcp(evidence, change):
    def edit(root):
        suite = root.find("testsuite")
        case = suite.find("testcase")
        if change in {"skip", "failure", "error"}:
            ET.SubElement(case, "skipped" if change == "skip" else change)
        elif change == "missing":
            suite.remove(case)
        elif change == "duplicate":
            suite.append(copy.deepcopy(case))
        elif change == "wrong-node":
            case.set("name", "test_unrelated")
        elif change == "false-count":
            suite.set("tests", "1")
    evidence.change_xml(edit)
    if change == "truncated":
        path = evidence.tcp / gate.TCP_JUNIT_FILENAME
        path.write_text("<testsuites><testsuite")
        evidence.receipt["junit_sha256"] = gate._digest(path)
        evidence.save()
    with pytest.raises(gate.CoverageError, match="JUnit"):
        evidence.join()


@pytest.mark.parametrize("change", ["missing", "duplicate", "identity", "failed", "incomplete", "source", "manifest", "constraints", "packages", "raw-junit"])
def test_full_shards_and_sources_still_fail_closed(evidence, change):
    first = evidence.base.paths[0]
    if change == "missing":
        first.unlink()
    elif change == "duplicate":
        folder = evidence.base.receipts / "duplicate"
        folder.mkdir()
        (folder / "coverage.json").write_bytes(first.read_bytes())
    elif change in {"identity", "failed", "incomplete"}:
        receipt = gate._read_json(first)
        if change == "identity":
            receipt["identity"]["run_attempt"] = "99"
        elif change == "failed":
            receipt["pytest_exitstatus"] = 1
        else:
            receipt["complete"] = False
        tcp.write_json(first, receipt)
    elif change == "source":
        (evidence.root / next(iter(evidence.base.manifest["source_files"]))).write_text("changed")
    elif change == "manifest":
        evidence.base.manifest_path.write_text(evidence.base.manifest_path.read_text() + " ")
    elif change == "constraints":
        evidence.base.constraints.write_text("pytest==1.0.0\n")
    elif change == "packages":
        (first.parent / tcp.PACKAGES).write_text("pytest==8.4.2\nforeign==1\n")
    else:
        (first.parent / "backend.xml").write_text("<testsuite/>")
    with pytest.raises(gate.CoverageError):
        evidence.join()


@pytest.mark.parametrize("target", ["aggregation", "backend-tcp", "symlink"])
def test_overwrite_and_symlink_refusal(evidence, target):
    if target == "aggregation":
        evidence.output.mkdir()
    elif target == "backend-tcp":
        (evidence.base.paths[0].parent / gate.TCP_JUNIT_FILENAME).write_text("existing evidence")
    else:
        (evidence.tcp / "linked").symlink_to(evidence.base.constraints)
    with pytest.raises(gate.CoverageError):
        evidence.join()


def test_duplicate_json_key_refusal(evidence):
    path = evidence.tcp / tcp.RECEIPT
    path.write_text(path.read_text().replace('"complete": true', '"complete": false, "complete": true'))
    with pytest.raises(gate.CoverageError, match="duplicate JSON"):
        evidence.join()


@pytest.mark.parametrize("packages", ["", "pytest==8.4.2\npytest==8.4.2\n", "pytest==1\n", "pytest @ file:///tmp/foo\n", "pytest==8.4.2\nPyTest==8.4.2\n"])
def test_bad_installed_dependencies_refused(evidence, packages):
    (evidence.tcp / tcp.PACKAGES).write_text(packages)
    with pytest.raises(gate.CoverageError):
        evidence.join()


@pytest.mark.parametrize("outcome", ["pass", "fail", "skip", "source-change"])
def test_runner_retains_actual_synthetic_subprocess_outcomes(tmp_path, monkeypatch, outcome):
    evidence = Evidence(tmp_path)
    # Keep this synthetic subprocess root independent even when its temporary
    # directory is below the real repository (owned-profile verification).
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    # This is an actual pytest subprocess over explicitly synthetic functions;
    # real product TCP execution is tested separately and never inferred here.
    source = tmp_path / "tests/test_r5_offline_sync_tcp.py"
    body = "import pytest\nfrom pathlib import Path\n"
    for node in gate.TCP_NODES:
        statement = {"pass": "assert True", "fail": "assert False", "skip": "pytest.skip('not permitted')",
                     "source-change": "Path(__file__).write_text(Path(__file__).read_text() + '# mutation\\n')"}[outcome]
        body += "def " + node.split("::")[1] + "():\n    " + statement + "\n"
    source.write_text(body)
    evidence.base.manifest["source_files"][source.relative_to(tmp_path).as_posix()] = gate._digest(source)
    evidence.base.save_manifest()
    for name in (tcp.RECEIPT, tcp.LOG, gate.TCP_JUNIT_FILENAME):
        (evidence.tcp / name).unlink()
    monkeypatch.setenv("RUN_B10_TCP_SYNC_TEST", "1")
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setattr(tcp, "actual_identity", lambda *args: copy.deepcopy(evidence.identity))
    monkeypatch.setattr(tcp.subprocess, "check_output", lambda *args, **kwargs: b"pytest==8.4.2\n")
    code = tcp.run_tcp(tmp_path, evidence.base.manifest_path, evidence.base.constraints, evidence.tcp, tmp_path / "pytest")
    receipt = gate._read_json(evidence.tcp / tcp.RECEIPT)
    assert receipt["complete"] is (outcome == "pass")
    assert code == (0 if outcome == "pass" else 1)
    assert receipt["pytest_exitstatus"] == (1 if outcome == "fail" else 0)
    if outcome == "pass":
        assert receipt["validation_errors"] == []
    else:
        assert receipt["validation_errors"]
    assert gate._digest(evidence.tcp / tcp.LOG) == receipt["log_sha256"]
    assert (evidence.tcp / gate.TCP_JUNIT_FILENAME).is_file()


def test_runner_marks_aborted_execution_incomplete(tmp_path, monkeypatch):
    evidence = Evidence(tmp_path)
    for name in (tcp.RECEIPT, tcp.LOG, gate.TCP_JUNIT_FILENAME):
        (evidence.tcp / name).unlink()
    monkeypatch.setenv("RUN_B10_TCP_SYNC_TEST", "1")
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    monkeypatch.setattr(tcp, "actual_identity", lambda *args: copy.deepcopy(evidence.identity))
    monkeypatch.setattr(tcp.subprocess, "check_output", lambda *args, **kwargs: b"pytest==8.4.2\n")
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(tcp.subprocess, "run", interrupt)
    with pytest.raises(KeyboardInterrupt):
        tcp.run_tcp(tmp_path, evidence.base.manifest_path, evidence.base.constraints, evidence.tcp, tmp_path / "pytest")
    receipt = gate._read_json(evidence.tcp / tcp.RECEIPT)
    assert receipt["complete"] is False and receipt["pytest_exitstatus"] is None
    assert receipt["finished_utc"] is None


@pytest.mark.parametrize("existing", [tcp.RECEIPT, tcp.LOG, gate.TCP_JUNIT_FILENAME])
def test_runner_refuses_to_overwrite_existing_evidence(evidence, monkeypatch, existing):
    monkeypatch.setenv("RUN_B10_TCP_SYNC_TEST", "1")
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    for name in (tcp.RECEIPT, tcp.LOG, gate.TCP_JUNIT_FILENAME):
        if name != existing:
            (evidence.tcp / name).unlink()
    with pytest.raises(gate.CoverageError, match="overwrite"):
        tcp.run_tcp(evidence.root, evidence.base.manifest_path, evidence.base.constraints, evidence.tcp, evidence.root / "pytest")


def test_checkout_identity_is_verified_independently(evidence, monkeypatch):
    repo = evidence.root / "checkout"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-c", "user.name=CI fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "Synthetic identity fixture"], cwd=repo, check=True)
    for key, env in tcp.IDENTITY_ENV.items():
        monkeypatch.setenv(env, evidence.identity[key])
    monkeypatch.setenv("GITHUB_WORKSPACE", str(repo))
    with pytest.raises(gate.CoverageError, match="actual checkout"):
        tcp.actual_identity(evidence.root, evidence.base.manifest_path, evidence.base.constraints)
    for key, revision in (("checked_out_sha", "HEAD"), ("source_tree", "HEAD^{tree}")):
        monkeypatch.setenv(tcp.IDENTITY_ENV[key], subprocess.check_output(["git", "rev-parse", revision], cwd=repo, text=True).strip())
    identity = tcp.actual_identity(evidence.root, evidence.base.manifest_path, evidence.base.constraints)
    assert identity["checked_out_sha"] == os.environ["CI_COVERAGE_SHA"]
    assert identity["source_tree"] == os.environ["CI_COVERAGE_TREE"]


def workflow_job(name, source):
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  [\w-]+:\n|\Z)", source, re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(0)


def test_workflow_preserves_frozen_jobs_limits_and_full_suite_command():
    root = Path(__file__).resolve().parents[2]
    workflow = root / ".github/workflows/cloud-ci.yml"
    source = workflow.read_text()
    full = workflow_job("backend-execution", source)
    assert "timeout-minutes: ${{ matrix.backend == 'postgres' && 55 || 20 }}" in full
    assert "RUN_B10_TCP_SYNC_TEST" not in full
    assert "shard_count: 1" in full and full.count("shard_count: 2") == 2
    assert "--ci-scope=backend --ci-shard-index=${{ matrix.shard_index }} --ci-shard-count=${{ matrix.shard_count }}" in full
    tcp_job = workflow_job("backend-tcp", source)
    assert "timeout-minutes: 10" in tcp_job
    assert "bash .github/ci/prepare.sh backend-tcp" in tcp_job
    assert "python-version: '3.12.9'" in tcp_job
    install = "python -m pip install -c .github/ci/python-constraints.txt -e '.[dev,fontbuild,otio,comic]'"
    assert install in full and install in tcp_job
    aggregate = workflow_job("backend", source)
    assert "needs: [backend-execution, backend-tcp]" in aggregate
    assert 'test "$EXECUTION_RESULT" = success' in aggregate and 'test "$TCP_RESULT" = success' in aggregate
    assert "backend: [file, postgres]" in aggregate
    assert "tcp_evidence.py join" in aggregate
    assert "coverage_reconcile.py" in aggregate
    assert "--receipts-dir joined-backend-receipts" in aggregate
    assert "continue-on-error" not in tcp_job + aggregate
    assert "|| true" not in tcp_job + aggregate
    assert "if-no-files-found: error" in tcp_job
    assert "github.sha" in tcp_job and "github.run_attempt" in tcp_job
    for job in (tcp_job, aggregate):
        for block in re.findall(r"^        run: \|\n((?:          .*\n)+)", job, re.MULTILINE):
            result = subprocess.run(["bash", "-n"], input=block, text=True, capture_output=True)
            assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name,expected", [
    ("frontend", "fbfe69540e4a9d5a48a43d1bc3d44c06e2909271c78c4fb932a5b0a687c04798"),
    ("v2-creative-browser", "35d5bcb0b01d5cfdee60fed714c6c2d912141b887c8494bb648d4848f7f46277"),
    ("windows-host", "00f36f08e98d9d2cac1621c19e35a8638328ef451c3cfc1c4d92ec2a9c18deed"),
    ("windows-package", "d4314dd6a4bc4645a6af7df089df8d51a91497f0228d5d31bf9c4691214a33ec"),
])
def test_unrelated_jobs_preserved_exactly(name, expected):
    import hashlib
    source = (Path(__file__).resolve().parents[1] / "workflows/cloud-ci.yml").read_text()
    assert hashlib.sha256(workflow_job(name, source).encode()).hexdigest() == expected


@pytest.mark.parametrize("name,expected", [
    ("suite_coverage.py", "570892af0975c125868710e250eb7f30cc5e51ba7cbef9429a3b0f8f10238da7"),
    ("coverage_reconcile.py", "f097904d51cc21cb6f1ce8dcc688f692cf89bdd473f3952605eba3b1ae02e66a"),
    ("postgres_gate.py", "d18ee804595ab98f8aec4c25745a7961e65a36755e318c8f4f257663b4358a8c"),
    ("prepare.sh", "1acd01e7f251dbd5c92af5f139ef026a820f2f412d15d248cdd7a62b80deb76d"),
])
def test_original_gate_and_prepare_bytes_preserved(name, expected):
    assert gate._digest(Path(__file__).with_name(name)) == expected


def test_original_full_suite_execution_step_preserved_byte_for_byte():
    import hashlib
    source = (Path(__file__).resolve().parents[1] / "workflows/cloud-ci.yml").read_text()
    start = source.index('      - name: Complete backend collection / assigned shard execution\n')
    end = source.index('      - name: Summarize exact revision and test counts\n', start)
    assert hashlib.sha256(source[start:end].encode()).hexdigest() == "fc9eaf0f91ef99caf842e672209eaaf52780f6b030de602fd384f0b0470e8e43"
    full = workflow_job("backend-execution", source)
    assert ".github/ci/test_tcp_evidence.py" not in full
    assert ".github/ci/test_tcp_evidence.py" in workflow_job("backend-tcp", source)


def test_cli_join_refuses_existing_report(evidence):
    report = evidence.root / "report.json"
    report.write_text("original")
    args = ["join", "--manifest", str(evidence.base.manifest_path),
            "--constraints", str(evidence.base.constraints), "--source-root", str(evidence.root),
            "--backend-dir", str(evidence.base.receipts), "--tcp-dir", str(evidence.tcp),
            "--output-dir", str(evidence.output), "--report", str(report),
            "--execution-result", "success", "--tcp-result", "success"]
    for key, value in evidence.expected.items():
        args.extend(["--expected-" + key.replace("_", "-"), value])
    assert tcp.main(args) == 1
    assert report.read_text() == "original"
    assert not evidence.output.exists()
