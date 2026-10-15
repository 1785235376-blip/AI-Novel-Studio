"""R3-I — cleanup-script protection logic and DTO digest format.

The cleanup assertions use SYNTHETIC receipts in a temp directory: they exercise the guard
logic itself and deliberately do NOT recreate the four databases that were already dropped.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load_cleanup():
    spec = importlib.util.spec_from_file_location(
        "_cleanup", REPO / "scripts" / "cleanup_r3i_test_databases.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _receipt(folder: Path, filename: str, **over):
    data = {"database": "v2_r3i_synthetic", "database_created": True,
            "database_existed_before": False, "database_oid": 12345}
    data.update(over)
    (folder / filename).write_text(json.dumps(data), encoding="utf-8")


# ------------------------------------------------- cleanup guard logic (no database) --
def test_a_receipt_without_an_oid_cannot_authorise_a_drop(tmp_path):
    _load_cleanup()
    mod = _load_cleanup()
    _receipt(tmp_path, "r3i-a.json", database_oid=None)
    owned, blocked = mod.claimed_databases(tmp_path, "r3i-*.json")
    assert owned == {}, "a missing oid must not authorise deletion"
    assert blocked and "oid" in blocked[0][1]


def test_a_non_integer_oid_cannot_authorise_a_drop(tmp_path):
    mod = _load_cleanup()
    _receipt(tmp_path, "r3i-a.json", database_oid="12345")
    owned, blocked = mod.claimed_databases(tmp_path, "r3i-*.json")
    assert owned == {}, "a string oid is not a proof of identity"
    assert blocked


def test_contradictory_receipts_keep_the_database(tmp_path):
    mod = _load_cleanup()
    _receipt(tmp_path, "r3i-a.json", database_oid=111)
    _receipt(tmp_path, "r3i-b.json", database_oid=222)
    owned, blocked = mod.claimed_databases(tmp_path, "r3i-*.json")
    assert owned == {}, "conflicting oids must never be resolved by guessing"
    assert blocked and "contradictory" in blocked[0][1]


def test_a_receipt_that_does_not_prove_creation_keeps_the_database(tmp_path):
    mod = _load_cleanup()
    _receipt(tmp_path, "r3i-a.json", database_existed_before=True)
    owned, blocked = mod.claimed_databases(tmp_path, "r3i-*.json")
    assert owned == {}, "a pre-existing database is not ours to drop"
    assert blocked


def test_only_receipts_matching_the_pattern_are_considered(tmp_path):
    mod = _load_cleanup()
    _receipt(tmp_path, "phase6-old.json", database="v2_phase6_old", database_oid=999)
    owned, blocked = mod.claimed_databases(tmp_path, "r3i-*.json")
    assert owned == {} and blocked == [], "other runs' receipts must not be acted on"


def test_a_fully_proven_receipt_is_owned(tmp_path):
    mod = _load_cleanup()
    _receipt(tmp_path, "r3i-a.json", database="v2_r3i_proven", database_oid=4242)
    owned, blocked = mod.claimed_databases(tmp_path, "r3i-*.json")
    assert list(owned) == ["v2_r3i_proven"]
    assert owned["v2_r3i_proven"]["oid"] == 4242
    assert blocked == []


def test_the_script_defaults_to_a_read_only_precheck(tmp_path):
    """A LEGAL precheck must return exactly 0; an illegal target must return exactly 2.

    A controlled fixture stands in for the cluster-ownership guard (a real owned cluster is not
    started and the four already-dropped databases are NOT recreated). With ownership satisfied
    and nothing provably owned, a precheck is a clean no-op: exit 0.
    """
    mod = _load_cleanup()

    class _OwnedStub:
        @staticmethod
        def validate_owned_cluster(repo_root, pg_bin, data):
            # Ownership confirmed. Also assert the caller passed Path objects, because the real
            # implementation calls .resolve() on them.
            assert hasattr(pg_bin, "resolve") and hasattr(data, "resolve"), \
                "validate_owned_cluster must receive Path objects, not strings"

    mod.load_runner = lambda repo_root: _OwnedStub
    code = mod.main(["--repo-root", str(REPO), "--pg-bin", str(tmp_path), "--data", str(tmp_path),
                     "--receipts", str(tmp_path)])
    assert code == 0, f"a legal read-only precheck must return 0, got {code}"

    # The same invocation WITHOUT --execute must never drop anything, even with an owned
    # receipt present, because dry-run is the default.
    _receipt(tmp_path, "r3i-owned.json", database="v2_r3i_owned", database_oid=777)
    assert mod.main(["--repo-root", str(REPO), "--pg-bin", str(tmp_path), "--data", str(tmp_path),
                     "--receipts", str(tmp_path)]) == 0


def test_a_non_loopback_host_is_refused(tmp_path):
    mod = _load_cleanup()
    assert mod.main(["--repo-root", str(REPO), "--pg-bin", str(tmp_path), "--data", str(tmp_path),
                     "--receipts", str(tmp_path), "--host", "10.0.0.5"]) == 2


def test_an_unowned_directory_is_blocked(tmp_path):
    """Real guard, no stub: a temp dir is not an owned cluster, so this must be BLOCKED."""
    mod = _load_cleanup()
    bogus = tmp_path / "not-a-cluster"
    bogus.mkdir()
    code = mod.main(["--repo-root", str(REPO), "--pg-bin", str(tmp_path), "--data", str(bogus),
                     "--receipts", str(tmp_path)])
    assert code == 2, f"an unowned data directory must be BLOCKED (2), got {code}"


def test_a_missing_data_directory_is_blocked(tmp_path):
    mod = _load_cleanup()
    code = mod.main(["--repo-root", str(REPO), "--pg-bin", str(tmp_path),
                     "--data", str(tmp_path / "absent"), "--receipts", str(tmp_path)])
    assert code == 2


# ----------------------------------------------------------- DTO digest format --
@pytest.fixture(scope="module")
def client():
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip("requires the isolated runner")
    os.environ.setdefault("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


BASE = "/api/projects/does-not-exist/studio/documents/d1/shots/s1/prompt-adoption"


def _body(**over):
    data = {"shot_id": "s1", "family_id": "f1", "asset_id": "a1", "revision": 1,
            "expected_digest": "a" * 64, "expected_version": 1,
            "expected_digest_target": "b" * 64, "request_id": "r1"}
    data.update(over)
    return data


def _invalid_fields(response):
    assert response.status_code == 422, response.text[:200]
    return {tuple(item["loc"]) for item in response.json()["detail"]}


def test_a_legal_sha256_body_is_not_rejected_by_the_dto(client):
    """Reaching the resource check (not a 422) proves the DTO accepted the format."""
    response = client.post(BASE, json=_body())
    assert response.status_code != 422, response.text[:200]


@pytest.mark.parametrize("field", ["expected_digest", "expected_digest_target"])
def test_a_short_digest_is_rejected(client, field):
    assert ("body", field) in _invalid_fields(client.post(BASE, json=_body(**{field: "a" * 63})))


@pytest.mark.parametrize("field", ["expected_digest", "expected_digest_target"])
def test_an_uppercase_digest_is_rejected(client, field):
    assert ("body", field) in _invalid_fields(
        client.post(BASE, json=_body(**{field: "A" * 64})))


@pytest.mark.parametrize("field", ["expected_digest", "expected_digest_target"])
def test_a_non_hex_digest_is_rejected(client, field):
    assert ("body", field) in _invalid_fields(
        client.post(BASE, json=_body(**{field: "z" * 64})))
    assert ("body", field) in _invalid_fields(
        client.post(BASE, json=_body(**{field: "a" * 63 + "-"})))


def test_an_unknown_field_is_rejected(client):
    assert ("body", "unexpected") in _invalid_fields(
        client.post(BASE, json=_body(unexpected="x")))
