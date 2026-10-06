"""Offline delivery checks. No discovery, application launch or network access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN_MANIFEST_SHA256 = "77c1f82f0aec0ef385d95cacf6fe04530b83fb62d2403bc7341cbe6bf19c858c"
READINESS = {
    "DONE",
    "PARTIAL",
    "CONTRACT_VERIFIED",
    "MOCK_ONLY",
    "LOCAL_REQUIRED",
    "NOT_RUN",
    "BLOCKED",
}


def check(root: Path = ROOT) -> dict:
    manifest_path = root / "contracts/local-interop/v1/parity-manifest.json"
    raw = manifest_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FROZEN_MANIFEST_SHA256, "V1 manifest changed"
    manifest = json.loads(raw)
    # The parity set is 36 enumerated files plus the manifest itself.
    assert len(manifest["files"]) + 1 == 37, "Frozen V1 file inventory changed"
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, relative
    shared = json.loads((root / "contracts/local-interop/desktop-prep-parity.json").read_text())
    for relative, expected in shared["files"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, relative
    requirements = json.loads((root / "DESKTOP_INTEGRATION_READINESS_MATRIX.json").read_text())
    rows = requirements["requirements"]
    assert [row["section"] for row in rows] == list(range(1, 70)), "Need all 69 sections"
    for row in rows:
        assert row["status"] in READINESS, row
        assert row["evidence"] and row["remaining_boundary"], row
    scenarios = json.loads((root / "DESKTOP_INTEROP_ACCEPTANCE_MATRIX.json").read_text())
    assert [row["id"] for row in scenarios["scenarios"]] == [f"A{i:02d}" for i in range(1, 25)]
    for row in scenarios["scenarios"]:
        assert row["native_status"] in {"LOCAL_REQUIRED", "NOT_RUN"}, row
        assert row["contract_scope"] and row["native_requirement"], row
    for name in (
        "DESKTOP_INTEGRATION_ADAPTER_GUIDE.md",
        "QINGJIAN_DESKTOP_MAPPING_CHECKLIST.md",
    ):
        assert (root / name).is_file(), name
    return {
        "protocol": "PoemSeed Local Interop 1.0",
        "frozen_protocol_files": 37,
        "shared_desktop_preparation_files": len(shared["files"]),
        "manifest_sha256": FROZEN_MANIFEST_SHA256,
        "requirements": 69,
        "acceptance_scenarios": 24,
        "real_desktop_acceptance": "LOCAL_REQUIRED",
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
