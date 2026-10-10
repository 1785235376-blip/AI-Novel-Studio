"""Run the original TCP gate and join immutable, same-attempt CI evidence.

The original coverage verifier remains authoritative and unmodified. Downloaded
artifacts are never rewritten: a fresh, byte-verified aggregation copy carries
TCP XML beside the File receipt solely for the verifier's historical layout.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

import coverage_reconcile as gate

RECEIPT = "tcp-evidence.json"
LOG = "sync-tcp.log"
PACKAGES = "python-packages.txt"
IDENTITY_ENV = {
    "checked_out_sha": "CI_COVERAGE_SHA", "source_tree": "CI_COVERAGE_TREE",
    "event_sha": "GITHUB_SHA", "run_id": "GITHUB_RUN_ID",
    "run_attempt": "GITHUB_RUN_ATTEMPT", "repository": "GITHUB_REPOSITORY",
}
EXPECTED_KEYS = set(IDENTITY_ENV)


def write_json(path: Path, value: dict, *, exclusive=False) -> None:
    import json
    with path.open("x" if exclusive else "w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=True, indent=2) + "\n")


def snapshot(root: Path, manifest: dict) -> dict[str, str]:
    gate._source_files(root, manifest)
    return {name: gate._digest(root / name) for name in manifest["source_files"]}


def validate_packages(path: Path, constraints: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    gate._require(bool(lines) and len(lines) == len(set(lines)), "missing/duplicate installed dependencies")
    normalized = {}
    for line in lines:
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
        gate._require(match is not None, "unpinned installed dependency")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        gate._require(name not in normalized, "duplicate installed dependency name")
        normalized[name] = match[2]
    for line in constraints.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
        gate._require(match is not None, "non-exact dependency constraint")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        gate._require(normalized.get(name) == match[2], "installed dependency differs from constraint: " + name)
    return gate._digest(path)


def actual_identity(root: Path, manifest: Path, constraints: Path) -> dict:
    identity = {key: os.environ.get(env, "") for key, env in IDENTITY_ENV.items()}
    gate._require(all(identity.values()), "missing independent CI identity")
    gate._require(bool(os.environ.get("GITHUB_WORKSPACE")), "missing checked-out Git workspace")
    checkout = Path(os.environ["GITHUB_WORKSPACE"])
    gate._require(checkout.is_dir(), "missing checked-out Git workspace")
    for key, revision in (("checked_out_sha", "HEAD"), ("source_tree", "HEAD^{tree}")):
        actual = subprocess.check_output(["git", "rev-parse", revision], cwd=checkout, text=True).strip()
        gate._require(identity[key] == actual, "wrong actual checkout " + key)
    identity.update(python_version=platform.python_version(), platform=sys.platform,
                    source_manifest_sha256=gate._digest(manifest), dependency_digest=gate._digest(constraints))
    return identity


def tcp_command(basetemp: Path, receipts: Path) -> list[str]:
    # Preserve the exact original pytest scope/options; no TestClient substitute,
    # deselection, retries, xfail or newly approved skip exists in this gate.
    return [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
            f"--basetemp={basetemp}", "-q", "-ra", "--tb=short",
            "tests/test_r5_offline_sync_tcp.py", f"--junitxml={receipts / gate.TCP_JUNIT_FILENAME}"]


def run_tcp(root: Path, manifest_path: Path, constraints: Path, receipts: Path, basetemp: Path) -> int:
    root, receipts, basetemp = root.resolve(), receipts.resolve(), basetemp.resolve()
    manifest, _ = gate._manifest(manifest_path, "backend")
    gate._require(bool(manifest["external_gates"]["file"]), "missing original external TCP gate")
    gate._require(os.environ.get("RUN_B10_TCP_SYNC_TEST") == "1" and os.environ.get("STORAGE_BACKEND") == "file", "explicit real File TCP environment required")
    for name in (RECEIPT, LOG, gate.TCP_JUNIT_FILENAME):
        gate._require(not (receipts / name).exists(), "refusing to overwrite TCP evidence: " + name)
    receipts.mkdir(parents=True, exist_ok=True)
    identity = actual_identity(root, manifest_path, constraints)
    sources_before = snapshot(root, manifest)
    packages = receipts / PACKAGES
    installed = subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--exclude-editable"], cwd=root)
    gate._require(packages.read_bytes() == installed, "installed dependencies differ from install receipt")
    package_digest = validate_packages(packages, constraints)
    command = tcp_command(basetemp, receipts)
    receipt = {"schema_version": 1, "scope": "original-file-tcp", "identity": identity,
               "complete": False, "pytest_exitstatus": None, "validation_errors": [],
               "command": command, "environment": {"RUN_B10_TCP_SYNC_TEST": "1", "STORAGE_BACKEND": "file"},
               "nodes": list(gate.TCP_NODES), "source_sha256_before": sources_before,
               "source_sha256_after": None, "installed_dependencies_sha256": package_digest,
               "junit_filename": gate.TCP_JUNIT_FILENAME, "junit_sha256": None,
               "log_filename": LOG, "log_sha256": None,
               "started_utc": datetime.now(timezone.utc).isoformat(), "finished_utc": None}
    write_json(receipts / RECEIPT, receipt, exclusive=True)
    with (receipts / LOG).open("xb") as stream:
        result = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT)
    receipt["pytest_exitstatus"] = result.returncode
    receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
    try:
        receipt["source_sha256_after"] = snapshot(root, manifest)
        gate._require(actual_identity(root, manifest_path, constraints) == identity, "identity changed during TCP execution")
        gate._require(subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--exclude-editable"], cwd=root) == installed, "installed dependencies changed during TCP execution")
        gate._require(result.returncode == 0, "nonzero TCP pytest exit status")
        gate._junit(receipts / gate.TCP_JUNIT_FILENAME, dict.fromkeys(gate.TCP_NODES), external_tcp=True)
        receipt["junit_sha256"] = gate._digest(receipts / gate.TCP_JUNIT_FILENAME)
        receipt["complete"] = True
    except (gate.CoverageError, OSError, subprocess.SubprocessError) as exc:
        receipt["validation_errors"].append(str(exc))
    receipt["log_sha256"] = gate._digest(receipts / LOG)
    write_json(receipts / RECEIPT, receipt)
    print((receipts / LOG).read_text(encoding="utf-8", errors="replace"), end="")
    return 0 if receipt["complete"] else 1


def artifact_snapshot(directory: Path) -> dict[str, str]:
    gate._require(directory.is_dir() and not directory.is_symlink(), "missing or symlink artifact directory")
    result = {}
    for path in sorted(directory.rglob("*")):
        gate._require(not path.is_symlink(), "symlink in artifact evidence")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = gate._digest(path)
        else:
            gate._require(path.is_dir(), "unsupported artifact entry")
    gate._require(bool(result), "empty artifact evidence")
    return result


def validate_tcp(directory: Path, manifest_path: Path, constraints: Path, root: Path,
                 expected_identity: dict[str, str]) -> dict:
    receipt = gate._read_json(directory / RECEIPT)
    manifest, _ = gate._manifest(manifest_path, "backend")
    sources = snapshot(root, manifest)
    expected = dict(expected_identity, source_manifest_sha256=gate._digest(manifest_path),
                    dependency_digest=gate._digest(constraints))
    identity = receipt.get("identity")
    gate._require(isinstance(identity, dict) and set(identity) == gate.IDENTITY_KEYS | {"repository"}, "invalid TCP identity")
    gate._require(EXPECTED_KEYS <= set(expected_identity) and all(isinstance(v, str) and v for v in expected_identity.values()), "missing expected TCP identity")
    for key, value in expected.items():
        gate._require(identity.get(key) == value, "wrong TCP identity " + key)
    gate._require(all(isinstance(v, str) and v for v in identity.values()), "empty TCP identity")
    gate._require(type(receipt.get("schema_version")) is int and receipt["schema_version"] == 1, "unsupported TCP evidence schema")
    gate._require(receipt.get("scope") == "original-file-tcp", "wrong TCP scope")
    gate._require(receipt.get("complete") is True and type(receipt.get("pytest_exitstatus")) is int and receipt["pytest_exitstatus"] == 0, "incomplete or unsuccessful TCP execution")
    gate._require(receipt.get("validation_errors") == [], "TCP validation errors")
    gate._require(receipt.get("nodes") == list(gate.TCP_NODES), "wrong or duplicate TCP nodes")
    gate._require(receipt.get("environment") == {"RUN_B10_TCP_SYNC_TEST": "1", "STORAGE_BACKEND": "file"}, "wrong TCP execution environment")
    for key in ("source_sha256_before", "source_sha256_after"):
        gate._require(receipt.get(key) == sources, "TCP source hashes differ: " + key)
    command = receipt.get("command")
    gate._require(isinstance(command, list) and len(command) == 11 and isinstance(command[0], str) and bool(command[0]) and command[1:5] == ["-m", "pytest", "-p", "no:cacheprovider"] and isinstance(command[5], str) and command[5].startswith("--basetemp=") and command[6:10] == ["-q", "-ra", "--tb=short", "tests/test_r5_offline_sync_tcp.py"] and isinstance(command[10], str) and command[10].startswith("--junitxml=") and Path(command[10].split("=", 1)[1]).name == gate.TCP_JUNIT_FILENAME, "TCP command differs from original exact scope/options")
    try:
        started = datetime.fromisoformat(receipt["started_utc"])
        finished = datetime.fromisoformat(receipt["finished_utc"])
        gate._require(started.tzinfo is not None and finished.tzinfo is not None and finished >= started, "invalid TCP execution timestamps")
    except (KeyError, TypeError, ValueError) as exc:
        raise gate.CoverageError("missing or invalid TCP execution timestamps") from exc
    gate._require(receipt.get("installed_dependencies_sha256") == validate_packages(directory / PACKAGES, constraints), "TCP installed dependency digest differs")
    for prefix, filename in (("junit", gate.TCP_JUNIT_FILENAME), ("log", LOG)):
        gate._require(receipt.get(prefix + "_filename") == filename and receipt.get(prefix + "_sha256") == gate._digest(directory / filename), "TCP raw " + prefix + " evidence differs")
    gate._junit(directory / gate.TCP_JUNIT_FILENAME, dict.fromkeys(gate.TCP_NODES), external_tcp=True)
    return receipt


def join(backend_dir: Path, tcp_dir: Path, output: Path, manifest_path: Path,
         constraints: Path, source_root: Path, expected_identity: dict[str, str],
         *, execution_result: str, tcp_result: str) -> dict:
    gate._require(execution_result == "success" and tcp_result == "success", "every full shard and TCP job must succeed")
    gate._require(not output.exists() and not output.is_symlink(), "refusing to overwrite aggregation evidence")
    backend_before, tcp_before = artifact_snapshot(backend_dir), artifact_snapshot(tcp_dir)
    gate._require(set(tcp_dir.rglob(RECEIPT)) == {tcp_dir / RECEIPT}, "missing or duplicate TCP receipt")
    gate._require(set(tcp_dir.rglob(gate.TCP_JUNIT_FILENAME)) == {tcp_dir / gate.TCP_JUNIT_FILENAME}, "missing or duplicate TCP JUnit")
    receipt = validate_tcp(tcp_dir, manifest_path, constraints, source_root, expected_identity)
    paths = sorted(backend_dir.rglob("coverage.json"))
    gate._require(len(paths) == 3, "missing or duplicate full shard receipts")
    pairs = set()
    file_path = None
    for path in paths:
        shard = gate._read_json(path)
        pair = (shard.get("backend"), shard.get("shard", {}).get("index"))
        gate._require(pair in {("file", 0), ("postgres", 0), ("postgres", 1)} and pair not in pairs, "wrong or duplicate full shard")
        pairs.add(pair)
        gate._require(shard.get("identity") == receipt["identity"], "TCP/full-shard identity mismatch")
        gate._require(validate_packages(path.parent / PACKAGES, constraints) == receipt["installed_dependencies_sha256"], "TCP/full-shard installed dependencies differ")
        if pair == ("file", 0):
            file_path = path
    gate._require(not list(backend_dir.rglob(gate.TCP_JUNIT_FILENAME)), "refusing to replace existing backend TCP evidence")
    gate._require(file_path is not None, "missing File receipt")
    # Keep the originals intact. Every new file is exclusive and byte-verified.
    output.mkdir(parents=True, exist_ok=False)
    for name, digest in backend_before.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write((backend_dir / name).read_bytes())
        gate._require(gate._digest(target) == digest, "backend aggregation copy changed bytes")
    target = output / file_path.parent.relative_to(backend_dir) / gate.TCP_JUNIT_FILENAME
    with target.open("xb") as stream:
        stream.write((tcp_dir / gate.TCP_JUNIT_FILENAME).read_bytes())
    gate._require(gate._digest(target) == receipt["junit_sha256"], "TCP aggregation copy changed bytes")
    result = gate.reconcile(output, manifest_path, scope="backend", expected_identity=expected_identity,
                            expected_shards={"file": 1, "postgres": 2}, constraints_path=constraints, source_root=source_root)
    gate._require(artifact_snapshot(backend_dir) == backend_before and artifact_snapshot(tcp_dir) == tcp_before, "original artifact evidence changed during join")
    expected_copy = dict(backend_before, **{target.relative_to(output).as_posix(): receipt["junit_sha256"]})
    gate._require(artifact_snapshot(output) == expected_copy, "aggregation evidence changed during validation")
    return {"schema_version": 1, "status": "complete", "identity": receipt["identity"],
            "execution_job_result": execution_result, "tcp_job_result": tcp_result,
            "original_backend_sha256": backend_before, "original_tcp_sha256": tcp_before,
            "aggregation_sha256": expected_copy, "tcp_destination": target.relative_to(output).as_posix(),
            "evidence_boundary": "Downloaded originals unchanged; exclusive byte-identical local copies only. Original reconciler independently accepted all full shards and the original two real TCP tests.",
            "coverage": result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("run", "join"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--constraints", type=Path, required=True)
        command.add_argument("--source-root", type=Path, required=True)
        if name == "run":
            command.add_argument("--receipts", type=Path, required=True)
            command.add_argument("--basetemp", type=Path, required=True)
        else:
            command.add_argument("--backend-dir", type=Path, required=True)
            command.add_argument("--tcp-dir", type=Path, required=True)
            command.add_argument("--output-dir", type=Path, required=True)
            command.add_argument("--report", type=Path, required=True)
            command.add_argument("--execution-result", required=True)
            command.add_argument("--tcp-result", required=True)
            for key in IDENTITY_ENV:
                command.add_argument("--expected-" + key.replace("_", "-"), required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            return run_tcp(args.source_root, args.manifest, args.constraints, args.receipts, args.basetemp)
        gate._require(not args.report.exists(), "refusing to overwrite join report")
        expected = {key: getattr(args, "expected_" + key) for key in IDENTITY_ENV}
        result = join(args.backend_dir, args.tcp_dir, args.output_dir, args.manifest, args.constraints,
                      args.source_root, expected, execution_result=args.execution_result, tcp_result=args.tcp_result)
        write_json(args.report, result, exclusive=True)
        return 0
    except (gate.CoverageError, OSError, subprocess.SubprocessError) as exc:
        print("TCP evidence rejected: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
