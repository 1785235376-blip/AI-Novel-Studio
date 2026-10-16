"""Review and explicitly write an additive V2 collection manifest.

The frozen V1 manifest, exact historical skips, baseline test bodies and existing
coverage gates are never rewritten. Collection is inventory, not passing tests.
No CI auto-generation: --write is an explicit local generation step after review.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_v2_checks import isolated_environment, source_snapshot

MIGRATION_PATH = "tests/test_windows_portable_entry.py"
MIGRATION_COMMIT = "1b7ff50a7e64742916bc64730df884cea819b379"
MIGRATION_BEFORE = "d100e27589fb45cb921c13a82a83a911485fef1c0ed82a1e50eb5efc94f24799"
MIGRATION_AFTER = "9f0d2d5f78a44e54a0fcc00925dc6d67038060408d3bd44753461ca57152fe1f"
V2_BASELINE_COMMIT = "e21075d10801a60bdcb4282a6d5ce8068be21503"
FROZEN_MANIFEST_SHA256 = "6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262"


class ExtensionError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def protected_source(name: str) -> bool:
    return (name.startswith(("tests/", "frontend/tests/", ".github/ci/"))
            or ".test." in name or ".spec." in name or "__snapshots__/" in name)


def verified_baseline_migration(root: Path, before: str, after: str) -> dict:
    if (before, after) != (MIGRATION_BEFORE, MIGRATION_AFTER):
        raise ExtensionError("unreviewed baseline test drift: " + MIGRATION_PATH)
    original = subprocess.check_output(["git", "show", f"{MIGRATION_COMMIT}^:{MIGRATION_PATH}"], cwd=root)
    migrated = subprocess.check_output(["git", "show", f"{MIGRATION_COMMIT}:{MIGRATION_PATH}"], cwd=root)
    if (sha256(original), sha256(migrated)) != (before, after):
        raise ExtensionError("baseline migration provenance hashes do not match")
    old, new = b'"%PYTHON%" -I -m', b'"%PYTHON%" -B -I -m'
    if original.count(old) != 1 or original.replace(old, new) != migrated:
        raise ExtensionError("baseline migration contains more than the reviewed -B addition")
    return {"path": MIGRATION_PATH, "commit": MIGRATION_COMMIT,
            "frozen_sha256": before, "v2_baseline_sha256": after,
            "delta": "Add -B before -I in the fixed launcher expectation only; all other bytes preserved",
            "purpose": "Reconcile the preexisting V2 isolation baseline, not a historical audit approval"}


def current_sources(root: Path, baseline: dict) -> dict[str, str]:
    result = source_snapshot(root)
    for name in baseline["source_files"]:
        path = root / name
        if not path.is_file():
            raise ExtensionError("baseline source removed: " + name)
        result[name] = sha256(path.read_bytes())
    for path in (root / ".github/ci").glob("*.py"):
        result[path.relative_to(root).as_posix()] = sha256(path.read_bytes())
    return dict(sorted(result.items()))


def extend_manifest(root: Path, baseline: dict, rows: list[dict], sources: dict,
                    frozen_digest: str) -> tuple[dict, dict]:
    nodes = [row["nodeid"] for row in rows]
    if len(nodes) != len(set(nodes)):
        raise ExtensionError("duplicate collected node IDs")
    if not rows or any(row.get("backend") not in {"file", "postgres", "both"} for row in rows):
        raise ExtensionError("missing or invalid collection classification")
    original = baseline["product_nodes"]
    original_set = set(original)
    if [node for node in nodes if node in original_set] != original:
        raise ExtensionError("baseline nodes removed or reordered")
    migrations, changed = [], []
    for name, before in baseline["source_files"].items():
        after = sources.get(name)
        if not after:
            raise ExtensionError("baseline source removed: " + name)
        if before != after:
            changed.append({"path": name, "before_sha256": before, "after_sha256": after})
            if protected_source(name):
                if name != MIGRATION_PATH:
                    raise ExtensionError("baseline test/gate bytes changed: " + name)
                migrations.append(verified_baseline_migration(root, before, after))
    if {node.split("::", 1)[0] for node in nodes} - set(sources):
        raise ExtensionError("collected test file is missing source hash")
    new_nodes = [node for node in nodes if node not in original_set]
    result = copy.deepcopy(baseline)
    result["product_nodes"] = nodes
    result["added_nodes"] = [*baseline["added_nodes"], *new_nodes]
    result["source_files"] = sources
    result["v2_extension"] = {
        "frozen_manifest_sha256": frozen_digest,
        "original_v2_baseline_commit": V2_BASELINE_COMMIT,
        "original_product_node_count": len(original),
        "new_nodes": new_nodes,
        "baseline_test_migrations": migrations,
        "source_changes_from_frozen_manifest": changed,
        "collection_classifications_sha256": sha256(json.dumps(rows, separators=(",", ":")).encode()),
        "evidence_boundary": "Complete collection only; no execution or successful-coverage claim",
    }
    # These must remain exact copies: no new missing-service/runtime skip is allowed.
    if result["skips"] != baseline["skips"] or result.get("external_gates") != baseline.get("external_gates"):
        raise ExtensionError("historical skip policy changed")
    report = {"status": "INVENTORY_ONLY", "baseline_nodes": len(original), "collected_nodes": len(nodes),
              "new_nodes": len(new_nodes), "baseline_nodes_preserved_in_order": True,
              "historical_skips_unchanged": True, "baseline_test_migrations": migrations,
              "source_changes": changed, "tests_executed": False}
    return result, report


def collect_worker(target: Path, basetemp: Path) -> int:
    import pytest

    class Inventory:
        def __init__(self):
            self.rows, self.errors = [], []

        def pytest_collection_finish(self, session):
            for item in session.items:
                pg = bool(item.get_closest_marker("postgres_backend_only"))
                file = bool(item.get_closest_marker("file_backend_only"))
                if pg and file:
                    self.errors.append("contradictory backend markers: " + item.nodeid)
                self.rows.append({"nodeid": item.nodeid, "backend": "postgres" if pg else "file" if file else "both"})

        def pytest_collectreport(self, report):
            if report.failed or report.skipped:
                self.errors.append(str(report.nodeid) + ": " + report.outcome + ": " + str(report.longrepr)[:2000])

    inventory = Inventory()
    status = int(pytest.main(["--collect-only", "-p", "no:terminal", "-p", "no:cacheprovider",
                              "--basetemp=" + str(basetemp)], plugins=[inventory]))
    target.write_text(json.dumps({"exit_code": status, "rows": inventory.rows, "errors": inventory.errors},
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"collection_exit_code": status, "collected_nodes": len(inventory.rows),
                      "collection_errors": len(inventory.errors), "tests_executed": False}))
    return status or bool(inventory.errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=".github/ci/coverage_manifest.json.gz")
    parser.add_argument("--output", default=".github/ci/coverage_manifest_v2.json.gz")
    parser.add_argument("--report", default="docs/delivery/v2-development/cloud-v2-collection.json")
    parser.add_argument("--write", action="store_true", help="Write separate V2 manifest after all preservation checks")
    parser.add_argument("--collect-worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--basetemp", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.collect_worker:
        return collect_worker(args.collect_worker, args.basetemp)
    root = Path(__file__).resolve().parents[1]
    baseline_path, output = (root / args.baseline).resolve(), (root / args.output).resolve()
    if baseline_path == output or not output.is_relative_to(root):
        parser.error("output must be a separate V2 manifest inside this checkout")
    raw = baseline_path.read_bytes()
    frozen_digest = sha256(raw)
    if frozen_digest != FROZEN_MANIFEST_SHA256:
        parser.error("baseline manifest differs from the immutable V1 evidence carried by V2 baseline " + V2_BASELINE_COMMIT)
    baseline = json.loads(gzip.decompress(raw) if baseline_path.suffix == ".gz" else raw)
    profile = root / ".runtime/v2-checks/v2-manifest-collection"
    env = os.environ.copy()
    for key in list(env):
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET")) or key in {"DATABASE_URL", "TEST_POSTGRES_DATABASE_URL", "E2E_DATABASE_URL", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"}:
            env.pop(key, None)
    env.update(isolated_environment(root, profile))
    before = current_sources(root, baseline)
    collection = profile / "collection.json"
    command = [sys.executable, str(Path(__file__).resolve()), "--collect-worker", str(collection),
               "--basetemp", str(profile / "pytest")]
    completed = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
    report = {"utc": datetime.now(timezone.utc).isoformat(), "status": "REJECTED", "tests_executed": False,
              "frozen_manifest_sha256": frozen_digest, "collection_stdout": completed.stdout,
              "collection_stderr": completed.stderr, "collection_exit_code": completed.returncode}
    result = None
    try:
        collected = json.loads(collection.read_text(encoding="utf-8"))
        if completed.returncode or collected["exit_code"] or collected["errors"]:
            raise ExtensionError("collection failed: " + repr(collected.get("errors")))
        after = current_sources(root, baseline)
        report["collected_nodes"] = len(collected["rows"])
        report["baseline_nodes"] = len(baseline["product_nodes"])
        report["source_changes"] = [{"path": name, "before_sha256": digest, "after_sha256": after.get(name)}
                                    for name, digest in baseline["source_files"].items() if after.get(name) != digest]
        if before != after:
            raise ExtensionError("sources changed during collection; collect again only after edits settle")
        if sha256(baseline_path.read_bytes()) != frozen_digest:
            raise ExtensionError("frozen baseline manifest changed during collection")
        result, summary = extend_manifest(root, baseline, collected["rows"], after, frozen_digest)
        report.update(summary)
        result["v2_extension"]["collection_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        if args.write:
            data = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(gzip.compress(data, mtime=0) if output.suffix == ".gz" else data)
            report.update(manifest_written=output.relative_to(root).as_posix(), manifest_sha256=sha256(output.read_bytes()))
    except (ExtensionError, OSError, ValueError) as exc:
        result = None
        report["status"] = "REJECTED"
        report["error"] = str(exc)
    report_path = root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"source_changes", "collection_stdout", "collection_stderr"}}, indent=2))
    return 0 if result is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
