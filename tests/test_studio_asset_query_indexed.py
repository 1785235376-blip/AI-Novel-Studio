"""M1: real route/owner results and observable File reads, not mocked storage.

Small budget overrides make rejection deterministic. Fault-injection wrappers
only schedule actual source/index writes; every query still reads real files.
"""
from collections import Counter
import errno
import json
import os
from pathlib import Path
import sqlite3
import sys

import pytest

from test_studio_asset_query import get, ids, rig
from test_studio_asset_query_authority import source_snapshot


pytestmark = pytest.mark.file_backend_only


class FileReads:
    """Python audit events count actual source opens and root enumerations."""

    def __init__(self, root):
        self.root = os.fsencode(root)
        self.active = False
        self.counts = Counter()
        sys.addaudithook(self.observe)

    def observe(self, event, args):
        if not self.active:
            return
        if event == "os.scandir":
            path = args[0]
            if isinstance(path, (str, bytes, os.PathLike)) and os.fsencode(path) == self.root:
                self.counts["enumerations"] += 1
        elif event == "open":
            path, _mode, flags = args
            if not isinstance(path, (str, bytes, os.PathLike)):
                return
            path = os.fsencode(path)
            if os.path.dirname(path) != self.root:
                return
            kind = "metadata" if path.endswith(b".json") else "content" if path.endswith(b".bin") else None
            if kind:
                if not flags & os.O_WRONLY:
                    self.counts[kind] += 1
                if flags & (os.O_WRONLY | os.O_RDWR):
                    self.counts["source_writes"] += 1

    def query(self, rig, params):
        self.counts.clear()
        self.active = True
        try:
            response = get(rig, params)
        finally:
            self.active = False
        return response, dict(self.counts)


def assert_safe_failure(rig, response, status, code, asset_ids=()):
    assert response.status_code == status, response.text
    assert response.json()["detail"]["code"] == code
    assert response.headers["cache-control"] == "no-store"
    assert "items" not in response.json() and "total" not in response.json()
    assert str(rig.root) not in response.text
    assert all(aid not in response.text for aid in asset_ids)


def test_cold_hot_deep_low_hit_and_exact_total_file_read_costs(rig):
    rows = [rig.seed(f"{'needle' if number == 53 else 'ordinary'}-{number:03d}.bin",
                     "audio" if number % 2 else "image",
                     stamp=f"2026-01-01T00:00:{number:02d}+00:00") for number in range(60)]
    audit = FileReads(rig.assets.root)
    before = source_snapshot(rig.root)

    cold, cold_cost = audit.query(rig, {"limit": 4})
    assert ids(cold) == [row["id"] for row in rows[:4]]
    assert cold.json()["total"] == 60
    # Cold construction really reads the source corpus. Page projection also
    # uses the original owner; it is not represented as an index-only result.
    assert 60 <= cold_cost["metadata"] <= 60 + 4 * 4
    assert cold_cost["content"] == 4
    assert 2 <= cold_cost["enumerations"] <= 3

    hot, hot_cost = audit.query(rig, {"limit": 4})
    assert hot.json() == cold.json()
    assert hot_cost["metadata"] <= 4 * 4 < 60
    assert hot_cost["content"] == 4 and hot_cost["enumerations"] == 2

    deep, deep_cost = audit.query(rig, {"limit": 4, "offset": 56})
    assert ids(deep) == [row["id"] for row in rows[56:]]
    assert deep.json()["total"] == 60 and deep.json()["has_more"] is False
    assert deep_cost["metadata"] <= 4 * 4 and deep_cost["content"] == 4

    sparse, sparse_cost = audit.query(rig, {"q": "needle", "kind": "audio", "limit": 4})
    assert ids(sparse) == [rows[53]["id"]] and sparse.json()["total"] == 1
    assert sparse_cost["metadata"] <= 4 and sparse_cost["content"] == 1

    total_only, total_cost = audit.query(rig, {"limit": 1, "offset": 1_000_000})
    assert total_only.json() == {"items": [], "total": 60, "limit": 1,
                                 "offset": 1_000_000, "has_more": False}
    assert total_cost.get("metadata", 0) == total_cost.get("content", 0) == 0
    assert total_cost["enumerations"] == 2
    assert all(cost.get("source_writes", 0) == 0 for cost in
               (cold_cost, hot_cost, deep_cost, sparse_cost, total_cost))
    assert source_snapshot(rig.root) == before


def test_index_corpus_budget_is_explicit_and_never_returns_partial_total(rig, monkeypatch):
    from app.services.asset_query_index import FileAssetQueryIndex

    rows = [rig.seed(f"budget-{number}.png") for number in range(3)]
    monkeypatch.setattr(FileAssetQueryIndex, "MAX_METADATA_FILES", 2)
    before = source_snapshot(rig.root)
    response = get(rig, {"limit": 1})
    assert_safe_failure(rig, response, 503, "ASSET_QUERY_BUDGET_EXCEEDED",
                        [row["id"] for row in rows])
    assert source_snapshot(rig.root) == before


def test_content_budget_rejects_whole_page_and_is_request_local(rig, monkeypatch):
    from app.services.asset_query_budget import AssetQueryReadBudget

    rows = [rig.seed(f"content-budget-{number}.png") for number in range(3)]
    assert len(ids(get(rig, {"limit": 3}))) == 3
    monkeypatch.setattr(AssetQueryReadBudget, "MAX_CONTENT_BYTES", rows[0]["size"])
    before = source_snapshot(rig.root)
    response = get(rig, {"limit": 3})
    assert_safe_failure(rig, response, 503, "ASSET_QUERY_BUDGET_EXCEEDED",
                        [row["id"] for row in rows])
    assert len(ids(get(rig, {"limit": 1}))) == 1
    monkeypatch.setattr(AssetQueryReadBudget, "MAX_CONTENT_BYTES", 0)
    # The opt-in query budget cannot change an unrelated existing asset route.
    detail = rig.client.get(f"/api/projects/{rig.nid}/studio/assets/{rows[0]['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == rows[0]["id"]
    assert source_snapshot(rig.root) == before


def test_matching_off_page_invalid_revision_keeps_owner_failure(rig):
    first = rig.seed("good.png", stamp="2026-01-01T00:00:00+00:00")
    invalid = rig.seed("bad.wav", "audio", stamp="2026-01-02T00:00:00+00:00")
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        invalid["version"] = 0
        rig.assets._write_meta(invalid)
    response = get(rig, {"limit": 1})
    assert_safe_failure(rig, response, 422, "EXPERIMENTAL_INVALID", [first["id"], invalid["id"]])
    assert response.json()["message"] == "CREATIVE_ASSET_VERSION_INVALID"
    # Filtering before the historical workspace validation remains compatible.
    selected = get(rig, {"kind": "image", "limit": 1})
    assert ids(selected) == [first["id"]] and selected.json()["total"] == 1


def test_metadata_rename_type_and_deletion_refresh_real_index(rig):
    row = rig.seed("before.png")
    assert ids(get(rig, {"q": "before", "kind": "image", "limit": 1})) == [row["id"]]
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        row.update(filename="after.wav", kind="audio", version=row["version"] + 1)
        rig.assets._write_meta(row)
    assert get(rig, {"q": "before", "kind": "image", "limit": 1}).json()["total"] == 0
    assert ids(get(rig, {"q": "after", "kind": "audio", "limit": 1})) == [row["id"]]
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.delete(row["id"])
    assert get(rig, {"q": "after", "limit": 1}).json()["total"] == 0
    assert ids(get(rig, {"q": "after", "limit": 1, "include_deleted": True})) == [row["id"]]


def test_query_detects_actual_source_change_before_return(rig, monkeypatch):
    row = rig.seed("unchanged.png")
    assert ids(get(rig, {"limit": 1})) == [row["id"]]
    index = rig.workspace.query_index
    original_verify = index.verify
    changed = False

    def verify_after_external_write(snapshot, **kwargs):
        nonlocal changed
        if not changed:
            # Model an external writer ignoring the owner lease, not a fake
            # fingerprint or a replacement storage implementation.
            path = rig.assets.root / (row["id"] + ".json")
            value = json.loads(path.read_text(encoding="utf-8"))
            value["filename"] = "changed.png"
            path.write_text(json.dumps(value), encoding="utf-8")
            changed = True
        return original_verify(snapshot, **kwargs)

    monkeypatch.setattr(index, "verify", verify_after_external_write)
    response = get(rig, {"limit": 1})
    assert_safe_failure(rig, response, 409, "ASSET_QUERY_RESTART_REQUIRED", [row["id"]])
    assert ids(get(rig, {"q": "changed", "limit": 1})) == [row["id"]]


def test_damaged_derived_filter_cannot_silently_hide_source_match(rig):
    row = rig.seed("needle.png")
    assert ids(get(rig, {"q": "needle", "limit": 1})) == [row["id"]]
    before = source_snapshot(rig.root)
    with sqlite3.connect(rig.workspace.query_index.path) as connection:
        connection.execute("UPDATE sources SET filename_folded=? WHERE asset_id=?",
                           ("nonmatching damage", row["id"]))
    response = get(rig, {"q": "needle", "limit": 1})
    assert ids(response) == [row["id"]] and response.json()["total"] == 1
    assert source_snapshot(rig.root) == before


def test_injected_content_io_failure_returns_fixed_error_without_path(rig, monkeypatch):
    row = rig.seed("io-failure.png")
    assert ids(get(rig, {"limit": 1})) == [row["id"]]
    target = rig.assets.root / (row["id"] + ".bin")
    original_open = Path.open

    def open_with_device_failure(path, *args, **kwargs):
        if path == target:
            # Auxiliary fault injection: real metadata/index/routes remain in
            # use. This does not claim to have induced an actual device fault.
            raise OSError(errno.EIO, "synthetic storage failure", str(target))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_device_failure)
    response = get(rig, {"limit": 1})
    assert_safe_failure(rig, response, 503, "ASSET_QUERY_INDEX_UNAVAILABLE", [row["id"]])
    assert "synthetic storage failure" not in response.text
