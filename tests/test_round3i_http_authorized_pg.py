"""R3-I — REAL PostgreSQL collaboration-authorized HTTP acceptance (PG-HTTP-A/B/C).

Marked `postgres_backend_only`, so under a File run these are SKIPPED and can never stand in for
a PostgreSQL result; under the PostgreSQL runner the File variants are skipped instead.

Identity, membership, branch and role fixtures, and the HTTP business chain, are shared with the
File suite via `r3i_authorized_shared`. The backend identity is asserted on the LIVE objects the
routes use, and any mismatch FAILS rather than skipping or falling back to File.
"""
from __future__ import annotations

import os

import pytest

from r3i_authorized_shared import build_authorized, chain, full_adoption_assertions, make_env

pytestmark = pytest.mark.postgres_backend_only


@pytest.fixture(scope="module")
def env():
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip("requires the isolated runner")
    return make_env("postgres")()


@pytest.fixture
def authorized(env):
    return build_authorized(env)


def test_pg_runtime_identity_is_real_postgresql(env):
    """Every claim about the backend is checked on the real objects, and a mismatch FAILS."""
    import app.experimental.api as exp_api

    # 1. the app really is configured for postgres
    assert env.main.settings.storage_backend == "postgres"

    # 2/3. the app's own repository bundle is PostgreSQL-backed for novels, scope and auth
    repositories = env.deps.repositories
    # Assert the real class rather than importing a specific module path, so this does not
    # depend on the package layout.
    for name in ("novels", "scope", "identity", "authorization"):
        repo = getattr(repositories, name, None)
        assert repo is not None, f"no {name} repository in the bundle"
        assert "postgres" in type(repo).__module__.lower() or \
            "postgres" in type(repo).__name__.lower(), \
            f"{name} repository {type(repo).__name__} is not PostgreSQL-backed"

    # 4/5. the ROUTE-HELD adoption service uses a real PostgreSQL ExperimentalStore
    svc = exp_api.studio_prompt_adoption_service
    inner = getattr(svc.workspace.creative.store, "store", svc.workspace.creative.store)
    assert inner.backend == "postgres", f"route-held store backend is {inner.backend!r}"

    # 6/7/8. a live connection: database identity, and the schema really exists
    with inner._connect() as connection:
        database = connection.execute("SELECT current_database()").fetchone()[0]
        table = connection.execute(
            "SELECT to_regclass('public.experimental_scope_documents')").fetchone()[0]
        version = connection.execute("SHOW server_version").fetchone()[0]
    assert table is not None, "experimental_scope_documents is missing: migrations not applied"
    print(f"[R3-I PG] server {version}, database {database}, table {table}")
    assert database, "current_database() returned nothing"
    url = os.environ.get("TEST_POSTGRES_DATABASE_URL", "")
    if url:
        assert database in url, f"connected to {database!r} which is not in the runner URL"

    # 9. assets remain on this round's isolated FILE root, not in the database
    from pathlib import Path
    assets_root = Path(str(getattr(svc.workspace.assets, "root", ""))).resolve()
    data_path = env.data_path
    assert data_path, "NOVEL_DATA_PATH must be exported by the runner"
    assert assets_root.is_relative_to(Path(data_path).resolve()), \
        f"asset root {assets_root} is outside the isolated root {data_path}"


def test_PG_HTTP_A_authorized_adoption_over_api(env, authorized):
    """PG-HTTP-A: the complete authorized chain over /api on real PostgreSQL."""
    import app.creative.prompt_adoption_api as adopt_api

    e = authorized
    c = e.client
    flow = chain(e, "/api", e.headers)

    closed = c.post(flow["adopt_url"], headers=e.headers, json=flow["dto"])
    assert closed.status_code == 503, (closed.status_code, closed.text[:300])

    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        ok = c.post(flow["adopt_url"], headers=e.headers, json=flow["dto"])
        assert ok.status_code == 200, ("PG adopt", ok.status_code, ok.text[:400])
        flow = {**flow, "client": c, "headers": e.headers, "result": ok.json()}
        full_adoption_assertions(e, flow, e.writer, prefix_label="PG-HTTP-A")
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
    assert adopt_api.PROMPT_ADOPTION_WRITE_ENABLED is False

    # A brand-new PostgreSQL connection must observe the same committed state.
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    fresh = ExperimentalStore(e.deps.repositories.novels.root
                              if hasattr(e.deps.repositories.novels, "root") else e.data_path,
                              "postgres", os.environ.get("TEST_POSTGRES_DATABASE_URL", ""))
    assert fresh.backend == "postgres"
    reopened = CreativeService(fresh, env.novels, env.deps.chapter_service)
    live = reopened.get(e.nid, {"mode": "collaboration", "novel_id": e.nid,
                               "workspace_id": e.workspace, "storyline_id": e.storyline,
                               "branch_id": e.branch}, flow["board"]["id"])
    shot = next(i for i in live["shots"] if i["id"] == flow["shot_id"])
    assert shot["frame_prompt"] == flow["source"]["value"], \
        "a fresh PostgreSQL connection must read the same committed text"
    assert live["version"] == flow["result"]["version"]


def test_PG_HTTP_B_authorized_adoption_over_api_v1(env, authorized):
    """PG-HTTP-B: the same complete chain over /api/v1 on real PostgreSQL."""
    import app.creative.prompt_adoption_api as adopt_api

    e = authorized
    flow = chain(e, "/api/v1", e.headers)
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        ok = e.client.post(flow["adopt_url"], headers=e.headers, json=flow["dto"])
        assert ok.status_code == 200, ("PG v1 adopt", ok.status_code, ok.text[:400])
        flow = {**flow, "client": e.client, "headers": e.headers, "result": ok.json()}
        full_adoption_assertions(e, flow, e.writer, prefix_label="PG-HTTP-B")
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False


def test_PG_HTTP_C_read_only_user_is_refused_with_403(env, authorized):
    """PG-HTTP-C: the switch is ON, so a refusal is authorization and must be exactly 403."""
    import app.creative.prompt_adoption_api as adopt_api

    e = authorized
    flow = chain(e, "/api", e.headers)
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        denied = e.client.post(flow["adopt_url"], headers=e.reader_headers, json=flow["dto"])
        assert denied.status_code == 403, ("PG read-only", denied.status_code, denied.text[:400])
        after = e.client.get(flow["read_url"], headers=e.headers).json()
        assert after["version"] == flow["target"]["version"], "a refused write must not commit"
        assert after["adoptions"] == []
        live = e.client.get(f"{flow['creative']}/documents/{flow['board']['id']}",
                            headers=e.headers).json()
        shot = next(i for i in live["shots"] if i["id"] == flow["shot_id"])
        assert shot["frame_prompt"] == ""
        assert flow["source"]["value"] not in denied.text

        # exact codes for the other unauthorized shapes
        base = {"X-Branch-ID": e.branch}
        bad = e.client.post(flow["adopt_url"], headers=base, json=flow["dto"])
        assert bad.status_code == 401, (bad.status_code, bad.text[:200])
        invalid = e.client.post(flow["adopt_url"],
                                headers={"X-Session-Token": "nope", "X-Branch-ID": e.branch},
                                json=flow["dto"])
        assert invalid.status_code == 401, (invalid.status_code, invalid.text[:200])
        other = e.client.post(flow["adopt_url"], headers=e.wrong_branch_headers, json=flow["dto"])
        assert other.status_code == 403, (other.status_code, other.text[:200])
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
