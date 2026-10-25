"""Measured TaskCenter bounded offset reads over synthetic real File projects.

The metric stream is evidence only when a real runner executes this file with
pytest -s. No measurements are prefilled. Source bytes describe the actual
semantic_import scope-document file, not every file the HTTP stack may read.
Every sample calls the original owner implementation and the original scope
fence. Cursor mode remains unsupported; these are response-offset measurements,
not database pagination or a claim of reduced owner I/O.
"""
from dataclasses import replace
import hashlib
import json
from time import perf_counter
import tracemalloc

import pytest

from app.experimental.ux import TaskReader
from test_studio_asset_query import rig
from test_taskcenter_query_backend import CTX, get, mounted, reader, row, service, tasks


def business_snapshot(root):
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if relative.parts[0] == ".workspace-mutation-locks" or not path.is_file():
            continue
        info = path.stat()
        result[relative.as_posix()] = (
            info.st_ino, info.st_size, info.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    return result


@pytest.mark.file_backend_only
def test_real_file_per_page_source_reads_and_resource_measurements(mounted):
    """Reuse one mounted fixture for all sizes and sampled first/next/final pages."""
    original_reader = mounted.svc.task_readers[0]
    original_file_read = mounted.store._file_read
    original_scope_fence = mounted.svc._task_in_scope
    counters = {}
    measurements = []

    def measured_reader(ctx):
        counters["reader_calls"] += 1
        value = original_reader.read(ctx)
        rows = value.get("items", []) if isinstance(value, dict) else value
        counters["source_rows_returned"] += len(rows)
        return value

    def measured_file_read(nid, scope):
        counters["source_file_read_calls"] += 1
        path = mounted.store.path(nid, scope)
        counters["source_file_bytes_read"] += path.stat().st_size if path.exists() else 0
        return original_file_read(nid, scope)

    def measured_scope_fence(ctx, owner, value):
        counters["central_rows_examined"] += 1
        return original_scope_fence(ctx, owner, value)

    mounted.monkeypatch.setattr(
        mounted.svc, "task_readers", (replace(original_reader, read=measured_reader),),
    )
    mounted.monkeypatch.setattr(mounted.store, "_file_read", measured_file_read)
    mounted.monkeypatch.setattr(mounted.svc, "_task_in_scope", measured_scope_fence)

    for size in (0, 3, 199, 200, 201, 2000):
        # Fixture writes happen before each query's before/after business proof.
        # Keep seeding out of the measurement counters.
        counters.update(
            reader_calls=0, source_file_read_calls=0, source_file_bytes_read=0,
            source_rows_returned=0, central_rows_examined=0,
        )
        mounted.seed(size)
        observed = min(size, 200)
        source_path = mounted.store.path(mounted.rig.nid, mounted.rig.scope)
        actual_scope_bytes = source_path.stat().st_size

        for page_size in (1, 50, 100):
            offsets = sorted({0, page_size, max(0, observed - page_size)}) if observed > page_size else [0]
            for offset in offsets:
                counters.update(
                    reader_calls=0, source_file_read_calls=0, source_file_bytes_read=0,
                    source_rows_returned=0, central_rows_examined=0,
                )
                before = business_snapshot(mounted.rig.root)
                tracing_was_active = tracemalloc.is_tracing()
                if not tracing_was_active:
                    tracemalloc.start()
                tracemalloc.reset_peak()
                traced_baseline, _ = tracemalloc.get_traced_memory()
                started = perf_counter()
                try:
                    response = get(mounted, {
                        "page_mode": "offset", "authority": "semantic_import",
                        "limit": page_size, "offset": offset,
                    })
                    elapsed = perf_counter() - started
                    traced_current, traced_peak = tracemalloc.get_traced_memory()
                finally:
                    if not tracing_was_active:
                        tracemalloc.stop()
                assert business_snapshot(mounted.rig.root) == before
                assert response.status_code == 200, response.text
                page = response.json()
                expected_items = min(page_size, max(0, observed - offset))
                assert page["observed_total"] == observed
                assert len(page["items"]) == expected_items
                assert page["source_truncated"] is (size > 200)
                assert page["coverage"] == {
                    "scope": "BOUNDED_AUTHORIZED_PROJECTION",
                    "completeness": "NOT_ASSERTED",
                }
                # These are measured wrappers around the original code, not
                # guessed counts derived from response length or source size.
                assert counters["reader_calls"] == 1
                assert counters["source_file_read_calls"] == 1
                assert counters["source_file_bytes_read"] == actual_scope_bytes
                assert counters["source_rows_returned"] == size
                assert counters["central_rows_examined"] == observed

                sample = {
                    "schema": "TASKCENTER_FILE_READ_MEASUREMENT_V1",
                    "synthetic": True,
                    "page_mode": "offset",
                    "database_pagination": False,
                    "cursor_supported": False,
                    "source_measurement": "semantic_import_scope_document",
                    "source_size": size,
                    "scope_document_bytes": actual_scope_bytes,
                    "limit": page_size,
                    "offset": offset,
                    "returned_items": len(page["items"]),
                    "observed_total": page["observed_total"],
                    "central_scan_hard_limit": 200,
                    **counters,
                    "elapsed_seconds_with_tracemalloc": elapsed,
                    "tracemalloc_baseline_bytes": traced_baseline,
                    "tracemalloc_current_bytes": traced_current,
                    "tracemalloc_peak_bytes": traced_peak,
                    "tracemalloc_peak_increment_bytes": max(0, traced_peak - traced_baseline),
                    "business_snapshot_unchanged": True,
                }
                measurements.append(sample)
                print("TASKCENTER_QUERY_MEASUREMENT " + json.dumps(sample, sort_keys=True))

    assert len(measurements) >= 18
    large = [sample for sample in measurements if sample["source_size"] == 2000]
    assert any(sample["offset"] > 0 for sample in large)
    assert all(sample["source_rows_returned"] == 2000 for sample in large)
    assert all(sample["central_rows_examined"] == 200 for sample in large)
    assert len({sample["source_file_bytes_read"] for sample in large}) == 1


@pytest.mark.parametrize("authorities", [
    True, False, "semantic_import", {}, {"semantic_import"}, [], (),
    [1], [None], [True], ["SEMANTIC_IMPORT"], ["semantic_import "],
    ["private-nonexistent"], ["semantic_import"] * 65,
])
def test_direct_authority_parameters_are_strict_and_bounded_before_owner_reads(authorities):
    def forbidden(ctx):
        pytest.fail("invalid authority parameters read an owner")
    svc = service(TaskReader("semantic_import", "Import", "history", forbidden))
    with pytest.raises(ValueError, match="^TASKCENTER_QUERY_INVALID$"):
        tasks(svc, authorities=authorities, limit=1)


def test_direct_authority_64_duplicates_are_valid_and_do_not_duplicate_rows():
    calls = []
    original = TaskReader(
        "semantic_import", "Import", "history",
        lambda ctx: calls.append(ctx) or [row("one")],
    )
    page = tasks(service(original), authorities=["semantic_import"] * 64, limit=100)
    assert [item["id"] for item in page["items"]] == ["one"]
    assert page["observed_total"] == 1 and calls == [CTX]


@pytest.mark.file_backend_only
def test_wire_authority_64_limit_and_65_rejection_do_not_write(mounted):
    before = business_snapshot(mounted.rig.root)
    try:
        valid = get(mounted, [("authority", "semantic_import")] * 64 + [("limit", "1")])
        assert valid.status_code == 200, valid.text
        assert valid.json()["observed_total"] == 3
        invalid = get(mounted, [("authority", "semantic_import")] * 65)
        assert invalid.status_code == 422, invalid.text
        assert invalid.json()["detail"] == {
            "code": "EXPERIMENTAL_INVALID", "message": "TASKCENTER_QUERY_INVALID",
        }
        assert "input" not in invalid.text
    finally:
        assert business_snapshot(mounted.rig.root) == before


def test_unselected_source_hint_cannot_truncate_selected_authority():
    calls = []
    imported = TaskReader(
        "semantic_import", "Import", "history",
        lambda ctx: calls.append("semantic_import") or {
            "items": [row("imported")], "has_more": True,
        },
    )
    media = TaskReader(
        "media", "Media", "history",
        lambda ctx: calls.append("media") or [row("media")],
    )
    page = tasks(service(imported, media), authorities=("media",), limit=100)
    assert calls == ["media"]
    assert [(item["authority"], item["id"]) for item in page["items"]] == [("media", "media")]
    assert page["observed_total"] == 1 and page["source_truncated"] is False
    assert page["truncated"] is False


def test_selected_hidden_only_rows_and_hint_do_not_contribute_observation():
    hidden = row("private-hidden-row", novel_id="other-project")
    svc = service(reader("semantic_import", {"items": [hidden], "has_more": True, "total": 99999}))
    page = tasks(svc, authorities=("semantic_import",), limit=100)
    assert page["items"] == [] and page["observed_total"] == 0
    assert page["source_truncated"] is False and page["has_more"] is False
    assert page["unavailable"] == []
    assert "private-hidden-row" not in str(page) and "99999" not in str(page)
