from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.compare_context_backends import canonical_json_normalize, compare, differences
from app.migrate_file_to_postgres import migrate


DATABASE_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")


def test_canonical_normalization_preserves_array_order_and_normalizes_numbers():
    assert canonical_json_normalize({"b": 1.0, "a": [2, 1]}) == {"a": [2, 1], "b": 1}
    assert differences([1, 2], [2, 1], "items") == [
        {"path": "items[0]", "file": 1, "postgres": 2},
        {"path": "items[1]", "file": 2, "postgres": 1},
    ]


@pytest.mark.skipif(not DATABASE_URL, reason="NOT VERIFIED: TEST_POSTGRES_DATABASE_URL is not configured")
def test_real_file_and_postgres_contexts_match(tmp_path):
    # PostgreSQL tests must not depend on a fixture left by a prior script or
    # test order. Seed the authoritative File fixture into this database.
    migrate(Path("novel_data"), DATABASE_URL, tmp_path / "migration.json")
    report = compare(Path("novel_data"), DATABASE_URL, "sample_novel", 2,
                     "Continue validation scene", True, tmp_path / "compare.json")
    assert report["raw_sources_equal"], report["differences"]
    assert report["serialized_sources_equal"], report["differences"]
    assert report["context_pack_equal"], report["differences"]
    assert report["status"] == "MATCH"
