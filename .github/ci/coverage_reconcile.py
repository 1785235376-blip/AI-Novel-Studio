"""Read-only, fail-closed reconciliation of complete pytest shard receipts.

Counts are derived only after exact node identity, collection, assignment, phase,
and raw JUnit agreement. This proves collected coverage, not preservation of
the interactions of a single PostgreSQL process running the entire suite.
"""

from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath


class CoverageError(ValueError):
    """The supplied evidence cannot establish complete collected coverage."""


IDENTITY_KEYS = {
    "checked_out_sha",
    "source_tree",
    "event_sha",
    "run_id",
    "run_attempt",
    "python_version",
    "platform",
    "source_manifest_sha256",
    "dependency_digest",
}
ANCHOR_KEYS = {"checked_out_sha", "source_tree", "event_sha", "run_id", "run_attempt"}
OPPOSITE_REASONS = {
    "file": "PostgreSQL implementation contract; covered by the real PostgreSQL full suite",
    "postgres": "File-backend implementation contract; covered by the default/File full suite",
}
TCP_REASON = "explicit real-loopback subprocess gate; not an in-process substitute"
TCP_JUNIT_FILENAME = "sync-tcp.xml"
TCP_NODES = (
    "tests/test_r5_offline_sync_tcp.py::test_two_isolated_tcp_endpoints_add_edit_conflict_disconnect_replay_tombstone_and_revocation",
    "tests/test_r5_offline_sync_tcp.py::test_two_isolated_tcp_endpoints_stale_dispatch_selective_withdrawal_and_fresh_baseline",
)
# This is the only legacy JUnit mapping without a ci_nodeid property. These two
# fixed, non-parametrized functions have an injective classname/name mapping.
TCP_JUNIT_IDENTITIES = {
    ("tests.test_r5_offline_sync_tcp", node.split("::")[1]): node for node in TCP_NODES
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoverageError(message)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                raw = stream.read()
        else:
            raw = path.read_text(encoding="utf-8")
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (OSError, EOFError, UnicodeError, json.JSONDecodeError) as exc:
        raise CoverageError(f"cannot read complete JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"{path}: expected JSON object")
    return value


def _digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CoverageError(f"cannot read {path}: {exc}") from exc


def inventory_digest(inventory: list[dict]) -> str:
    return hashlib.sha256(
        json.dumps(inventory, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def assigned_shard(nodeid: str, count: int) -> int:
    return (
        int.from_bytes(hashlib.sha256(nodeid.encode("utf-8")).digest(), "big") % count
    )


def _node_list(value: object, label: str, *, nonempty: bool = True) -> list[str]:
    _require(isinstance(value, list), f"{label}: expected node list")
    _require(
        all(isinstance(node, str) and node for node in value),
        f"{label}: invalid node ID",
    )
    _require(len(value) == len(set(value)), f"{label}: duplicate node ID")
    _require(bool(value) or not nonempty, f"{label}: empty inventory")
    return value


def _interop_node(nodeid: str) -> bool:
    path = PurePosixPath(nodeid.split("::", 1)[0])
    return path.parent == PurePosixPath("tests") and fnmatch.fnmatchcase(
        path.name, "test_local_interop*.py"
    )


def _manifest(path: Path, scope: str) -> tuple[dict, list[str]]:
    manifest = _read_json(path)
    _require(
        type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1,
        "manifest: unsupported schema_version",
    )
    nodes = _node_list(manifest.get("product_nodes"), "manifest product_nodes")
    added = _node_list(
        manifest.get("added_nodes"), "manifest added_nodes", nonempty=False
    )
    _require(set(added) <= set(nodes), "manifest added_nodes outside product inventory")
    source_files = manifest.get("source_files")
    _require(
        isinstance(source_files, dict) and bool(source_files),
        "manifest: missing source_files",
    )
    for name, digest in source_files.items():
        _require(
            isinstance(name, str)
            and bool(name)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            "manifest: invalid source file digest",
        )
    _require(
        {node.split("::", 1)[0] for node in nodes} <= set(source_files),
        "manifest: source_files missing a product test file",
    )
    skips = manifest.get("skips")
    _require(
        isinstance(skips, dict) and set(skips) == {"file", "postgres"},
        "manifest: invalid skip profiles",
    )
    for backend, allowed in skips.items():
        _require(
            isinstance(allowed, dict), f"manifest: invalid {backend} skip allowlist"
        )
        _require(
            set(allowed) <= set(nodes),
            f"manifest: {backend} skip outside product inventory",
        )
        _require(
            all(isinstance(reason, str) and reason for reason in allowed.values()),
            f"manifest: invalid {backend} skip reason",
        )
    external = manifest.get("external_gates", {"file": {}, "postgres": {}})
    _require(
        isinstance(external, dict)
        and set(external) == {"file", "postgres"}
        and isinstance(external["file"], dict)
        and external["postgres"] == {},
        "manifest: invalid external gate profiles",
    )
    expected_external = {
        node: {"reason": TCP_REASON, "junit_filename": TCP_JUNIT_FILENAME}
        for node in TCP_NODES
    }
    if set(nodes).intersection(TCP_NODES) or external["file"]:
        _require(set(TCP_NODES) <= set(nodes), "manifest: missing original TCP node")
        _require(
            external["file"] == expected_external,
            "manifest: external gate must contain exactly the two original TCP nodes",
        )
        _require(
            all(skips["file"].get(node) == TCP_REASON for node in TCP_NODES),
            "manifest: external TCP skip reason differs from frozen baseline",
        )
    manifest["external_gates"] = external
    selected = [node for node in nodes if scope != "interop" or _interop_node(node)]
    _require(bool(selected), f"manifest: empty {scope} inventory")
    return manifest, selected


def _source_files(root: Path, manifest: dict) -> None:
    root = root.resolve()
    for name, expected in manifest["source_files"].items():
        path = (root / name).resolve()
        _require(
            not Path(name).is_absolute() and path.is_relative_to(root),
            f"manifest source path escapes source root: {name}",
        )
        _require(
            _digest(path) == expected, f"frozen source file digest differs: {name}"
        )


def _outcomes(
    receipt: dict,
    assigned: list[str],
    classifications: dict[str, str],
    skips: dict[str, str],
    external: dict[str, dict],
) -> dict[str, str | None]:
    values = receipt.get("outcomes")
    _require(isinstance(values, list), "outcomes: expected list")
    observed = {}
    assigned_set = set(assigned)
    backend = receipt["backend"]
    for item in values:
        _require(isinstance(item, dict), "outcomes: invalid node record")
        node = item.get("nodeid")
        _require(
            isinstance(node, str) and node in assigned_set,
            f"outcomes: unknown or unassigned node {node!r}",
        )
        _require(node not in observed, f"outcomes: duplicate execution {node}")
        reports = item.get("reports")
        _require(
            isinstance(reports, list) and reports, f"{node}: missing phase reports"
        )
        for report in reports:
            _require(isinstance(report, dict), f"{node}: invalid phase report")
            _require(
                isinstance(report.get("when"), str)
                and report["when"] in {"setup", "call", "teardown"},
                f"{node}: unknown report phase",
            )
            _require(
                isinstance(report.get("outcome"), str)
                and report["outcome"] in {"passed", "skipped", "failed"},
                f"{node}: unknown report outcome",
            )
            _require(
                report.get("wasxfail") is False,
                f"{node}: xfail/xpass or missing wasxfail evidence",
            )
            _require("skip_reason" in report, f"{node}: missing skip_reason field")
            if report["outcome"] != "skipped":
                _require(
                    report["skip_reason"] is None,
                    f"{node}: skip reason on non-skip report",
                )
        phases = [report["when"] for report in reports]
        opposite = classifications[node] not in {"both", backend}
        skipped_reports = [
            report for report in reports if report["outcome"] == "skipped"
        ]
        if skipped_reports:
            _require(len(skipped_reports) == 1, f"{node}: multiple skipped phases")
            skipped_phase = skipped_reports[0]["when"]
            expected_phases = (
                ["setup", "teardown"]
                if skipped_phase == "setup"
                else ["setup", "call", "teardown"]
            )
            _require(
                skipped_phase in {"setup", "call"} and phases == expected_phases,
                f"{node}: incomplete or duplicate skipped phases",
            )
            _require(
                all(
                    report["outcome"] == "passed"
                    for report in reports
                    if report is not skipped_reports[0]
                ),
                f"{node}: unsuccessful phase accompanying skip",
            )
            _require(
                not opposite or skipped_phase == "setup",
                f"{node}: opposite-profile skip must occur in setup",
            )
            reason = skipped_reports[0]["skip_reason"]
            external_skip = (
                receipt["scope"] == "backend"
                and backend == "file"
                and classifications[node] == "file"
                and node in external
            )
            if opposite:
                expected_reason = OPPOSITE_REASONS[backend]
                if receipt["scope"] == "backend":
                    expected_reason = skips.get(node, expected_reason)
            elif external_skip:
                expected_reason = external[node]["reason"]
            else:
                expected_reason = skips.get(node)
            _require(
                opposite or receipt["scope"] != "interop",
                f"{node}: applicable Interop node skipped",
            )
            _require(
                isinstance(reason, str) and bool(reason) and reason == expected_reason,
                f"{node}: unexpected skip reason {reason!r}",
            )
            _require(
                classifications[node] != backend or external_skip,
                f"{node}: applicable backend contract skipped",
            )
            observed[node] = reason
        else:
            _require(
                phases == ["setup", "call", "teardown"],
                f"{node}: incomplete, reordered, or duplicate phases",
            )
            _require(
                all(report["outcome"] == "passed" for report in reports),
                f"{node}: unsuccessful phase",
            )
            _require(not opposite, f"{node}: opposite-profile contract did not skip")
            observed[node] = None
    _require(
        set(observed) == set(assigned),
        "outcomes: observed node set does not equal assigned set",
    )
    return observed


def _junit(
    path: Path, observed: dict[str, str | None], *, external_tcp: bool = False
) -> None:
    if external_tcp:
        _require(
            set(observed) == set(TCP_NODES)
            and all(reason is None for reason in observed.values()),
            "JUnit: invalid fixed external TCP mapping",
        )
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise CoverageError(f"missing or incomplete JUnit {path}: {exc}") from exc
    _require(root.tag in {"testsuites", "testsuite"}, "JUnit: unexpected root")
    suites = [root] if root.tag == "testsuite" else list(root)
    _require(
        bool(suites) and all(suite.tag == "testsuite" for suite in suites),
        "JUnit: missing or invalid suites",
    )
    seen = set()
    for suite in suites:
        cases = list(suite.findall("testcase"))
        _require(not suite.findall("testsuite"), "JUnit: nested suites are unsupported")
        actual_skips = 0
        for case in cases:
            properties = case.findall("properties/property[@name='ci_nodeid']")
            if external_tcp:
                key = (case.get("classname"), case.get("name"))
                _require(
                    key in TCP_JUNIT_IDENTITIES,
                    "JUnit: unknown external TCP testcase identity",
                )
                node = TCP_JUNIT_IDENTITIES[key]
                _require(
                    not properties
                    or (len(properties) == 1 and properties[0].get("value") == node),
                    "JUnit: conflicting external TCP ci_nodeid property",
                )
            else:
                _require(
                    len(properties) == 1 and "value" in properties[0].attrib,
                    "JUnit: missing or duplicate exact ci_nodeid property",
                )
                node = properties[0].attrib["value"]
            _require(node in observed, f"JUnit: unknown or unassigned node {node!r}")
            _require(node not in seen, f"JUnit: duplicate testcase {node}")
            seen.add(node)
            _require(
                not case.findall("failure") and not case.findall("error"),
                f"JUnit: failure/error for {node}",
            )
            skipped = case.findall("skipped")
            reason = observed[node]
            if reason is None:
                _require(not skipped, f"JUnit: unexpected skip for {node}")
            else:
                _require(
                    len(skipped) == 1, f"JUnit: missing or duplicate skip for {node}"
                )
                _require(
                    skipped[0].get("type") == "pytest.skip",
                    f"JUnit: xfail or unknown skip type for {node}",
                )
                _require(
                    skipped[0].get("message") == reason,
                    f"JUnit: skip reason mismatch for {node}",
                )
                actual_skips += 1
        for attribute, expected in {
            "tests": len(cases),
            "errors": 0,
            "failures": 0,
            "skipped": actual_skips,
        }.items():
            raw = suite.get(attribute)
            _require(
                isinstance(raw, str)
                and re.fullmatch(r"[0-9]+", raw) is not None
                and int(raw) == expected,
                f"JUnit: inconsistent {attribute} count",
            )
    _require(
        seen == set(observed), "JUnit: testcase node set does not equal observed set"
    )
    _require(
        len(list(root.iter("testcase"))) == len(seen),
        "JUnit: nested or unaccounted testcases",
    )


def reconcile(
    receipts_dir: Path,
    manifest_path: Path,
    *,
    scope: str,
    expected_identity: dict[str, str],
    expected_shards: dict[str, int] | None = None,
    constraints_path: Path | None = None,
    source_root: Path | None = None,
) -> dict:
    """Validate evidence without modifying any receipt, source, or manifest."""
    _require(scope in {"backend", "interop"}, "unknown coverage scope")
    expected_shards = (
        expected_shards
        if expected_shards is not None
        else {
            "file": 1,
            "postgres": 2 if scope == "backend" else 1,
        }
    )
    _require(
        isinstance(expected_shards, dict) and bool(expected_shards),
        "missing expected shard matrix",
    )
    _require(set(expected_shards) <= {"file", "postgres"}, "unknown expected backend")
    _require(
        all(
            type(count) is int and count in {1, 2} for count in expected_shards.values()
        ),
        "expected shard counts must be 1 or 2",
    )
    _require(isinstance(expected_identity, dict), "expected identity must be an object")
    expected_identity = dict(expected_identity)
    expected_identity.setdefault("event_sha", expected_identity.get("checked_out_sha"))
    _require(
        ANCHOR_KEYS <= set(expected_identity)
        and all(
            isinstance(value, str) and value for value in expected_identity.values()
        ),
        "missing independently expected SHA/tree/event/run/attempt identity",
    )
    manifest, expected_nodes = _manifest(Path(manifest_path), scope)
    _source_files(
        Path(source_root)
        if source_root is not None
        else Path(manifest_path).resolve().parents[2],
        manifest,
    )
    expected_identity["source_manifest_sha256"] = _digest(Path(manifest_path))
    expected_identity["dependency_digest"] = _digest(
        Path(constraints_path)
        if constraints_path is not None
        else Path(__file__).with_name("python-constraints.txt")
    )
    paths = sorted(Path(receipts_dir).rglob("coverage.json"))
    expected_pairs = {
        (backend, index)
        for backend, count in expected_shards.items()
        for index in range(count)
    }
    _require(len(paths) == len(expected_pairs), "missing or extra shard receipts")
    seen_pairs = set()
    canonical_inventory = None
    canonical_identity = None
    unions = {backend: set() for backend in expected_shards}
    totals = {
        backend: {
            "collected": len(expected_nodes),
            "passed": 0,
            "skipped": 0,
            "shards": count,
        }
        for backend, count in expected_shards.items()
    }
    external_results = {}
    if (
        scope == "backend"
        and manifest["external_gates"]["file"]
        and "file" in expected_shards
    ):
        _require(
            expected_shards["file"] == 1,
            "external TCP coverage requires the monolithic File profile",
        )
    for path in paths:
        receipt = _read_json(path)
        try:
            _require(
                type(receipt.get("schema_version")) is int
                and receipt["schema_version"] == 1,
                "unsupported receipt schema_version",
            )
            _require(receipt.get("scope") == scope, "wrong scope")
            backend = receipt.get("backend")
            _require(
                isinstance(backend, str) and backend in expected_shards, "wrong backend"
            )
            shard = receipt.get("shard")
            _require(
                isinstance(shard, dict)
                and type(shard.get("index")) is int
                and type(shard.get("count")) is int,
                "invalid shard metadata",
            )
            index, count = shard["index"], shard["count"]
            _require(
                count == expected_shards[backend] and 0 <= index < count,
                "wrong shard index/count",
            )
            pair = (backend, index)
            _require(pair not in seen_pairs, "duplicate shard receipt")
            seen_pairs.add(pair)
            identity = receipt.get("identity")
            _require(
                isinstance(identity, dict)
                and IDENTITY_KEYS <= set(identity)
                and all(
                    isinstance(value, str) and value for value in identity.values()
                ),
                "invalid receipt identity",
            )
            for key, value in expected_identity.items():
                _require(identity.get(key) == value, f"wrong identity {key}")
            if canonical_identity is None:
                canonical_identity = identity
            _require(identity == canonical_identity, "cross-shard identity mismatch")
            _require(
                receipt.get("complete") is True,
                "missing complete session-finish marker",
            )
            _require(
                type(receipt.get("pytest_exitstatus")) is int
                and receipt["pytest_exitstatus"] == 0,
                "nonzero or missing pytest exit status",
            )
            _require(
                receipt.get("collection_errors") == [],
                "collection errors or missing collection evidence",
            )
            _require(
                receipt.get("validation_errors") == [],
                "validation errors or missing validation evidence",
            )
            inventory = receipt.get("inventory")
            _require(
                isinstance(inventory, list) and inventory, "missing full inventory"
            )
            for item in inventory:
                _require(
                    isinstance(item, dict) and set(item) == {"nodeid", "backend"},
                    "invalid inventory record",
                )
                _require(
                    isinstance(item["backend"], str)
                    and item["backend"] in {"both", "file", "postgres"},
                    "invalid or contradictory backend classification",
                )
            nodes = _node_list(
                [item["nodeid"] for item in inventory], "receipt inventory"
            )
            _require(
                nodes == expected_nodes,
                "full inventory differs from frozen manifest membership/order",
            )
            _require(
                receipt.get("inventory_digest") == inventory_digest(inventory),
                "inventory digest mismatch",
            )
            if canonical_inventory is None:
                canonical_inventory = inventory
            _require(
                inventory == canonical_inventory,
                "cross-shard inventory/classification mismatch",
            )
            assigned = _node_list(receipt.get("assigned"), "assigned", nonempty=False)
            _require(
                assigned
                == [node for node in nodes if assigned_shard(node, count) == index],
                "assignment differs from exact deterministic hash membership/order",
            )
            _require(
                not unions[backend].intersection(assigned),
                "overlapping shard assignment",
            )
            unions[backend].update(assigned)
            classifications = {item["nodeid"]: item["backend"] for item in inventory}
            if scope == "backend" and manifest["external_gates"]["file"]:
                _require(
                    all(classifications.get(node) == "file" for node in TCP_NODES),
                    "original external TCP nodes must retain File-only classification",
                )
            observed = _outcomes(
                receipt,
                assigned,
                classifications,
                manifest["skips"][backend],
                manifest["external_gates"][backend],
            )
            junit_filename = (
                "backend.xml" if scope == "backend" else "local-interop.xml"
            )
            _require(
                receipt.get("junit_filename") == junit_filename, "wrong JUnit filename"
            )
            _junit(path.parent / junit_filename, observed)
            if (
                scope == "backend"
                and backend == "file"
                and manifest["external_gates"][backend]
            ):
                _junit(
                    path.parent / TCP_JUNIT_FILENAME,
                    dict.fromkeys(TCP_NODES),
                    external_tcp=True,
                )
                external_results[backend] = {
                    TCP_JUNIT_FILENAME: {
                        "passed": len(TCP_NODES),
                        "nodeids": list(TCP_NODES),
                    }
                }
            totals[backend]["skipped"] += sum(
                reason is not None for reason in observed.values()
            )
            totals[backend]["passed"] += sum(
                reason is None for reason in observed.values()
            )
        except CoverageError as exc:
            raise CoverageError(f"{path}: {exc}") from exc
    _require(seen_pairs == expected_pairs, "missing or wrong shard matrix entries")
    for backend, nodes in unions.items():
        _require(
            nodes == set(expected_nodes),
            f"{backend}: shard union differs from full collected inventory",
        )
    return {
        "schema_version": 1,
        "scope": scope,
        "status": "complete",
        "identity": canonical_identity,
        "unique_collected_per_profile": len(expected_nodes),
        "profiles": totals,
        "external_gates": external_results,
        "evidence": "complete collected backend coverage; not monolithic PostgreSQL interaction equivalence",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scope", choices=("backend", "interop"), required=True)
    parser.add_argument("--receipts-dir", type=Path, required=True)
    parser.add_argument("--expected-shards", nargs="+", metavar="BACKEND=COUNT")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--expected-event-sha")
    parser.add_argument("--expected-repository")
    parser.add_argument("--expected-run", required=True)
    parser.add_argument("--expected-attempt", required=True)
    parser.add_argument("--constraints", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        shards = None
        if args.expected_shards is not None:
            shards = {}
            for value in args.expected_shards:
                match = re.fullmatch(r"(file|postgres)=([12])", value)
                _require(match is not None, f"invalid expected shard setting: {value}")
                _require(
                    match[1] not in shards, f"duplicate expected backend: {match[1]}"
                )
                shards[match[1]] = int(match[2])
        identity = {
            "checked_out_sha": args.expected_sha,
            "source_tree": args.expected_tree,
            "event_sha": args.expected_event_sha or args.expected_sha,
            "run_id": args.expected_run,
            "run_attempt": args.expected_attempt,
        }
        if args.expected_repository is not None:
            identity["repository"] = args.expected_repository
        result = reconcile(
            args.receipts_dir,
            args.manifest,
            scope=args.scope,
            expected_identity=identity,
            expected_shards=shards,
            constraints_path=args.constraints,
            source_root=args.source_root,
        )
        rendered = json.dumps(result, indent=2) + "\n"
        if args.output is not None:
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except (CoverageError, OSError) as exc:
        print(f"Coverage reconciliation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
