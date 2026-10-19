"""Committed local-CI evidence receipts must not reference dangling files."""
from __future__ import annotations

from pathlib import Path

from scripts.check_local_ci_evidence_index import check_evidence_root

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "docs" / "v2" / "engineering" / "evidence" / "local-ci"


def test_committed_evidence_index_has_no_missing_declared_files():
    report = check_evidence_root(EVIDENCE_ROOT)
    assert report["receipts"] > 0
    assert report["checked_paths"] > 0
    assert report["missing"] == []
    assert report["xml_invalid"] == []
    assert report["status"] == "PASS"
