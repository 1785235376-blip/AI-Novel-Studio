"""M0: query decoding follows the real route's original authority boundary.

Fixtures are shared with the original mounted-route tests. No permission
resolver or File owner is replaced with a mock.
"""
import hashlib

import pytest

from test_studio_asset_query import get, ids, rig, shared_scope


pytestmark = pytest.mark.file_backend_only


def source_snapshot(root):
    """Observe durable source bytes and rewrite metadata, excluding lock files.

    File owner lock directories are operational coordination, not asset or
    project source data. Read atime is deliberately not a write assertion.
    """
    rows = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if not path.is_file() or any(part.startswith(".") for part in relative.parts):
            continue
        info = path.stat()
        rows[relative.as_posix()] = (info.st_ino, info.st_size, info.st_mtime_ns,
                                     hashlib.sha256(path.read_bytes()).hexdigest())
    return rows


@pytest.mark.parametrize("case, invalid, expected", [
    ("no_read", {"kind": "unknown"}, 403),
    ("no_read", {"limit": "0"}, 403),
    ("missing_branch", {"limit": "0"}, 400),
    ("revoked_member", {"offset": "-1"}, 403),
    ("feature_disabled", {"q": "x" * 256}, 404),
    ("missing_project", {"kind": "unknown"}, 404),
])
def test_original_refusal_precedes_bad_query(rig, monkeypatch, case, invalid, expected):
    headers = None
    nid = rig.nid
    if case in {"no_read", "missing_branch", "revoked_member"}:
        scope, headers = shared_scope(rig)
        row = rig.seed("private-scope-fixture.png", scope_value=scope)
        assert ids(get(rig, {"limit": 1}, headers=headers)) == [row["id"]]
        if case == "no_read":
            headers = {**headers, "X-Session-Token": "token-no-grants"}
        elif case == "missing_branch":
            headers = {"X-Session-Token": "token-reader"}
        else:
            from app.identity import IdentityStatus
            rig.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    else:
        row = rig.seed("private-scope-fixture.png")
        assert ids(get(rig, {"limit": 1})) == [row["id"]]
        if case == "feature_disabled":
            monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
        else:
            nid = "missing-query-project"

    before = source_snapshot(rig.root)
    try:
        # The valid control and the formerly callback-validated newline must
        # retain the same refusal as the formerly FastAPI-validated values.
        for params in ({"limit": 1}, {"q": "secret\nname"}, invalid):
            response = get(rig, params, nid=nid, headers=headers)
            assert response.status_code == expected, response.text
            assert response.headers["cache-control"] == "no-store"
            assert row["id"] not in response.text
            assert "total" not in response.json() and "items" not in response.json()
            assert str(rig.root) not in response.text
    finally:
        assert source_snapshot(rig.root) == before


def test_authorized_validation_and_queries_do_not_write_source_data(rig):
    row = rig.seed("stable-source.png")
    assert ids(get(rig, {"limit": 1})) == [row["id"]]
    before = source_snapshot(rig.root)
    try:
        for params in ({"kind": "unknown"}, {"limit": 0}, {"offset": -1},
                       {"q": "x" * 256}, {"q": "secret\nname"}):
            response = get(rig, params)
            assert response.status_code == 422
            assert response.json()["code"] == "EXPERIMENTAL_INVALID"
            assert response.json()["message"] == "ASSET_QUERY_INVALID"
            assert response.headers["cache-control"] == "no-store"
            assert "input" not in response.text and row["id"] not in response.text
            assert str(rig.root) not in response.text
        assert ids(get(rig, {"q": "stable", "limit": 1})) == [row["id"]]
    finally:
        assert source_snapshot(rig.root) == before


def test_existing_scalar_last_value_and_integral_decimal_compatibility(rig):
    row = rig.seed("kept.png")
    # These forms were accepted by the original FastAPI/Pydantic binding.
    # M0 relocates validation; it does not silently tighten their grammar.
    response = get(rig, [("q", "absent"), ("q", "kept"),
                         ("kind", "unknown"), ("kind", "image"),
                         ("limit", "0"), ("limit", "1.0"), ("offset", "0.0")])
    assert ids(response) == [row["id"]]
    assert response.json()["limit"] == 1 and response.json()["offset"] == 0
