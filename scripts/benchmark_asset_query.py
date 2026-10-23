"""Reproducible File query measurements through the actual mounted application.

Run with the repository's development Python environment, for example:
    python scripts/benchmark_asset_query.py --sizes 100 1000 10000
    python scripts/benchmark_asset_query.py --cursor-only --sizes 10000

The driver only creates fresh synthetic stores below .runtime/asset-scale. It
never reuses a user data directory. Fixture construction copies one real owner
record's schema and writes actual metadata/content files; it does not benchmark
ingestion. Every size is queried by a fresh child process, then queried again in
that same process. 'Cold' means cold application/index state, NOT dropped kernel
page caches. Python audit events observe real filesystem opens/enumerations;
no storage read or application response is mocked.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
KINDS = ("image", "video", "audio", "model", "text", "prompt")
PROJECT = "asset-query-benchmark"
MEASURED_SOURCES = ("app/creative/workspace.py", "app/creative/asset_query_service.py",
    "app/creative/asset_query_cursor.py", "app/services/asset_library_service.py",
    "app/services/asset_query_index.py", "app/services/asset_query_budget.py",
    "scripts/benchmark_asset_query.py")


def configure(root: Path) -> None:
    """Constrain every application side effect to this synthetic cloud store."""
    os.environ.update(PROJECT_ROOT=str(REPO), NOVEL_DATA_PATH=str(root),
        LOCALAPPDATA=str(root / "appdata"), MOCK_PROVIDER="true", ENABLE_CLOUD="false",
        ENABLE_COLLABORATION_RUNTIME="false", ENABLE_PACKAGED_RUNTIME="false",
        CREDENTIAL_VAULT_BACKEND="memory", STORAGE_BACKEND="file",
        EXPERIMENTAL_FEATURES="narrative_production_v2,asset_lineage_v2")
    for key in ("V1_ACCEPTANCE_MODE", "DATABASE_URL", "TEST_POSTGRES_DATABASE_URL"):
        os.environ.pop(key, None)


def prepare(root: Path, count: int) -> dict:
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("benchmark preparation requires a new empty synthetic directory")
    configure(root)
    from app import api
    from app.experimental.api import independent_workspace_service as workspace

    api.novel_service.create({"id": PROJECT, "title": "Synthetic benchmark only"})
    scope = {"mode": "local", "novel_id": PROJECT}
    data = b"synthetic asset query benchmark bytes"
    with workspace._asset_scope(PROJECT, scope):
        template = workspace.assets.create(PROJECT, "template.bin", base64.b64encode(data).decode(),
            "application/octet-stream", "image", required_features=("narrative_production_v2",))
        for index in range(count):
            row = copy.deepcopy(template)
            row.update(id=template["id"] if index == 0 else f"benchmark-{index:08d}",
                filename=f"{'needle' if index % 1000 == 0 else 'asset'}-{KINDS[index % 6]}-{index:08d}.bin",
                kind=KINDS[index % 6], created_at=f"2026-01-01T00:00:00.{index:06d}+00:00")
            # Deliberate fixture bulk preparation; production writes still use
            # the original owner. No create-loop idempotency scans are hidden.
            (workspace.assets.root / (row["id"] + ".json")).write_text(json.dumps(row), encoding="utf-8")
            (workspace.assets.root / (row["id"] + ".bin")).write_bytes(data)
    summary = {"records": count, "asset_content_bytes_each": len(data),
               "fixture": "real-owner-schema copied to synthetic File metadata and binary files"}
    (root / ".asset-query-benchmark.json").write_text(json.dumps(summary), encoding="utf-8")
    return summary


class FileAudit:
    """Count actual filesystem operations without replacing file contents."""
    def __init__(self, asset_root: Path):
        self.asset_root = os.fsencode(asset_root)
        self.active = False
        self.counts: dict[str, int] = {}
        sys.addaudithook(self.observe)

    def reset(self) -> None:
        self.counts = dict(directory_enumerations=0, metadata_reads=0, content_reads=0,
                           metadata_writes=0, content_writes=0, index_connections=0,
                           derived_directory_enumerations=0)

    def observe(self, event, args):
        if not self.active:
            return
        if event == "sqlite3.connect":
            path = args[0]
            if isinstance(path, (str, bytes, os.PathLike)) and b".asset-query-index" in os.fsencode(path):
                self.counts["index_connections"] += 1
        elif event == "os.scandir":
            path = args[0]
            if isinstance(path, (str, bytes, os.PathLike)):
                if os.fsencode(path) == self.asset_root:
                    self.counts["directory_enumerations"] += 1
                elif os.fsencode(path) == os.path.join(self.asset_root, b".asset-query-index"):
                    self.counts["derived_directory_enumerations"] += 1
        elif event == "open":
            path, _mode, flags = args
            if not isinstance(path, (str, bytes, os.PathLike)):
                return
            path = os.fsencode(path)
            if os.path.dirname(path) != self.asset_root:
                return
            if os.path.basename(path).startswith(b"."):
                return  # Derived index/journal files are not source metadata.
            prefix = "metadata" if path.endswith(b".json") else "content" if path.endswith(b".bin") else None
            if prefix is None:
                return
            if flags & (os.O_WRONLY | os.O_RDWR):
                self.counts[prefix + "_writes"] += 1
            if not flags & os.O_WRONLY:
                self.counts[prefix + "_reads"] += 1


def measure(root: Path, count: int, *, reopen: bool = False, cursor_only: bool = False) -> list[dict]:
    marker = root / ".asset-query-benchmark.json"
    if not marker.is_file() or json.loads(marker.read_text())["records"] != count:
        raise ValueError("benchmark fixture marker is missing or mismatched")
    configure(root)
    from fastapi.testclient import TestClient
    from app.main import app

    def verify_source():
        expected = json.loads(os.environ.get("ASSET_QUERY_BENCHMARK_EXPECTED_SOURCES", "{}"))
        for name, digest in expected.items():
            path = REPO / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise RuntimeError("benchmark source changed during measurement")
            module = sys.modules.get(name.removesuffix(".py").replace("/", "."))
            if module is not None and Path(module.__file__).resolve() != path:
                raise RuntimeError("benchmark imported a module from a different source directory")

    verify_source()
    if cursor_only:
        # httpx INFO logs contain the query string; tokens stay only in this
        # fresh synthetic store and are never emitted in measurement output.
        logging.getLogger("httpx").setLevel(logging.WARNING)

    audit = FileAudit(root / "assets")
    scenarios = [
        ("cold_first_page", {"limit": 50, "offset": 0}),
        ("hot_first_page", {"limit": 50, "offset": 0}),
        ("deep_page", {"limit": 50, "offset": max(0, count - 50)}),
        ("low_hit_keyword_kind", {"q": "needle", "kind": "image", "limit": 50}),
        ("exact_total_empty_page", {"limit": 1, "offset": 1_000_000}),
    ] + [("keyword_kind_" + kind, {"q": "asset", "kind": kind, "limit": 50}) for kind in KINDS]
    scenarios += [("legacy_unpaged", {})]
    if reopen:
        scenarios = [("cold_process_persistent_index", {"limit": 50, "offset": 0})]
    cursor_state = root / ".asset-query-cursor-state.json"
    state, first_ids, continuation = {}, [], None
    if cursor_only:
        common = {"page_mode": "cursor", "limit": 50}
        scenarios = [("cold_cursor_first_page", dict(common)),
            ("hot_cursor_first_page", dict(common)),
            ("cursor_continuation_page_2", dict(common)),
            ("cursor_low_hit_keyword_kind", dict(common, q="needle", kind="image")),
            ("cursor_exact_total_no_results", dict(common, q="benchmark-no-such-filename"))]
        if reopen:
            state = json.loads(cursor_state.read_text())
            scenarios = [("cold_process_cursor_continuation_page_3", dict(common, cursor=state["cursor"]))]
    rows = []
    index_directory = root / "assets" / ".asset-query-index"

    def index_size():
        return sum(path.stat().st_size for path in index_directory.iterdir() if path.is_file()) if index_directory.is_dir() else 0

    with TestClient(app) as client:
        for label, query in scenarios:
            if label == "cursor_continuation_page_2":
                query["cursor"] = continuation
            verify_source()
            audit.reset()
            index_bytes_before = index_size()
            tracemalloc.start()
            started = time.perf_counter()
            audit.active = True
            try:
                response = client.get(f"/api/projects/{PROJECT}/studio/assets", params=query)
                body = response.json()
            finally:
                audit.active = False
                elapsed = time.perf_counter() - started
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
            verify_source()
            if cursor_only:
                if response.status_code != 200 or body.get("projection") != "asset-metadata/1":
                    raise RuntimeError("cursor benchmark did not return the metadata projection")
                if audit.counts["content_reads"] or audit.counts["metadata_writes"] or audit.counts["content_writes"]:
                    raise RuntimeError("cursor benchmark read content or wrote source assets")
                expected_total, start = count, 0
                if label == "cursor_continuation_page_2":
                    start = 50
                elif reopen:
                    start = 100
                expected_indices = list(range(start, min(start + 50, count)))
                if label == "cursor_low_hit_keyword_kind":
                    expected_indices = list(range(0, count, 3000))
                    expected_total = len(expected_indices)
                    expected_indices = expected_indices[:50]
                elif label == "cursor_exact_total_no_results":
                    expected_indices, expected_total = [], 0
                filenames = [f"{'needle' if i % 1000 == 0 else 'asset'}-{KINDS[i % 6]}-{i:08d}.bin"
                             for i in expected_indices]
                if body.get("total") != expected_total or [item["filename"] for item in body["items"]] != filenames:
                    raise RuntimeError("cursor benchmark returned an inaccurate total or page")
                ids = [item["id"] for item in body["items"]]
                if label == "cold_cursor_first_page":
                    first_ids, continuation = ids, body.get("next_cursor")
                elif label == "hot_cursor_first_page" and ids != first_ids:
                    raise RuntimeError("cursor first page was unstable")
                elif label == "cursor_continuation_page_2":
                    if set(ids) & set(first_ids) or not body.get("next_cursor"):
                        raise RuntimeError("cursor continuation repeated a row or missed a successor")
                    state = {"cursor": body["next_cursor"], "seen_ids": first_ids + ids}
                elif reopen and set(ids) & set(state["seen_ids"]):
                    raise RuntimeError("cross-process cursor continuation repeated a row")
            rows.append({"scenario": label, "records": count,
                "query": {key: "<redacted>" if key == "cursor" else value for key, value in query.items()},
                "http_status": response.status_code,
                "returned": len(body.get("items", [])), "total": body.get("total"),
                "error_code": body.get("code"), "elapsed_seconds": round(elapsed, 6),
                "python_peak_bytes": peak, "process_max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "derived_index_bytes_before": index_bytes_before, "derived_index_bytes_after": index_size(),
                **audit.counts})
    if cursor_only and not reopen:
        descriptor = os.open(cursor_state, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(state, handle)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int)
    parser.add_argument("--cursor-only", action="store_true", help="measure only new metadata cursor scenarios (default 10000 rows)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", choices=("prepare", "measure", "reopen"))
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    args.sizes = args.sizes or ([10000] if args.cursor_only else [100, 1000, 10000])
    if any(size < 1 or size > 100_000 for size in args.sizes):
        parser.error("sample sizes must be within 1..100000")
    if args.cursor_only and min(args.sizes) < 101:
        parser.error("cursor-only samples need at least 101 rows for real third-page continuation")
    if args.worker:
        if args.root is None or not args.root.resolve().is_relative_to(REPO / ".runtime" / "asset-scale"):
            parser.error("worker roots must be synthetic .runtime/asset-scale directories")
        result = prepare(args.root.resolve(), args.sizes[0]) if args.worker == "prepare" else measure(args.root.resolve(), args.sizes[0], reopen=args.worker == "reopen", cursor_only=args.cursor_only)
        print(json.dumps(result, ensure_ascii=False))
        return
    base = REPO / ".runtime" / "asset-scale"
    base.mkdir(parents=True, exist_ok=True)
    result = {"schema": "asset-query-benchmark/1", "commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "python": sys.version.split()[0], "dependencies": {name: importlib.metadata.version(name)
            for name in ("fastapi", "starlette", "pydantic", "httpx")},
        "cold_semantics": "fresh process and owner; OS page cache is not flushed",
        "measurement_limits": ["Source open counts exclude native SQLite I/O; derived index bytes are file size, not bytes read.",
            "36-byte synthetic content validates population scaling and read counts, not maximum-sized media page cost.",
            "Audit and tracemalloc instrumentation affect timings; process max RSS is a process lifetime high-water mark."],
        "samples": []}
    worker_environment = dict(os.environ)
    if args.cursor_only:
        result["mode"] = "cursor-only"
        result["source_files_sha256"] = {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()
                                          for name in MEASURED_SOURCES}
        worker_environment["ASSET_QUERY_BENCHMARK_EXPECTED_SOURCES"] = json.dumps(result["source_files_sha256"])
    for count in args.sizes:
        root = Path(tempfile.mkdtemp(prefix=f"benchmark-{count}-", dir=base))
        payload = {"records": count, "synthetic_store": str(root.relative_to(REPO))}
        for worker in ("prepare", "measure", "reopen"):
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", worker,
                "--root", str(root), "--sizes", str(count)] + (["--cursor-only"] if args.cursor_only else [])
            completed = subprocess.run(command, cwd=REPO, text=True, env=worker_environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            payload[worker] = json.loads(completed.stdout)
        result["samples"].append(payload)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
