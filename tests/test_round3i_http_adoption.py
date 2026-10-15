"""R3-I — File HTTP closed loop through the REAL mounted FastAPI application.

Drives the official routes with TestClient. No service is called directly and no route is faked.
The route-held `studio_prompt_adoption_service` is asserted to be the one bound to this isolated
environment, by inspecting the live objects rather than trusting environment variables.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.file_backend_only


@pytest.fixture(scope="module")
def ctx():
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip("requires the isolated runner")
    # The mounted app gates its studio routes on this flag, and the flag is read per request,
    # so it must be set before the request is made (and before app.main is imported).
    os.environ["EXPERIMENTAL_FEATURES"] = "narrative_production_v2,asset_lineage_v2"
    os.environ.setdefault("STORAGE_BACKEND", "file")
    os.environ.setdefault("ENABLE_CLOUD", "false")
    os.environ.setdefault("MOCK_PROVIDER", "true")

    from fastapi.testclient import TestClient

    import app.creative.prompt_adoption_api as adopt_api
    import app.experimental.api as exp_api
    from app.main import app

    # The ROUTE-HELD service, not a fresh one.
    svc = exp_api.studio_prompt_adoption_service
    inner = getattr(svc.workspace.creative.store, "store", svc.workspace.creative.store)
    # FAIL-CLOSED: a missing NOVEL_DATA_PATH is a hard failure, never a skipped assertion.
    # Without it there is no proof these routes use an isolated store rather than real data.
    data_path = os.environ.get("NOVEL_DATA_PATH")
    assert data_path, (
        "NOVEL_DATA_PATH is not set: refusing to run, because the route-held service identity "
        "cannot be proven to use an isolated store")
    raw_path = Path(data_path)
    # Check the ORIGINAL value is absolute, before any abspath() could paper over a relative
    # path by anchoring it to the current directory.
    assert raw_path.is_absolute(), f"NOVEL_DATA_PATH must be absolute, got {data_path!r}"
    resolved = raw_path.resolve()

    # The route-held ExperimentalStore really is rooted in that directory, and is File-backed.
    store_root = Path(str(getattr(inner, "root", ""))).resolve()
    assert store_root == resolved, (
        f"route-held store root {store_root!r} != isolated NOVEL_DATA_PATH {resolved!r}: "
        "the routes captured a different service graph")
    assert getattr(inner, "backend", None) == "file", getattr(inner, "backend", None)

    # The route-held workspace's AssetLibraryService is rooted under the same isolated dir.
    # Path-aware containment, not a string prefix: "/tmp/ab" must not count as inside "/tmp/a".
    assets_root = Path(str(getattr(svc.workspace.assets, "root", ""))).resolve()
    assert assets_root.is_relative_to(resolved), (
        f"asset root {assets_root} is not inside the isolated root {resolved}")
    # The isolated root must really be the runner's per-label profile, so a test cannot
    # accidentally point at a shared or permanent directory.
    assert "v2-checks" in resolved.parts, (
        f"the isolated root {resolved} is not a runner profile directory")

    # Every prompt service shares the SAME isolated workspace OBJECT, not merely a similar one.
    assert svc.workspace is exp_api.independent_workspace_service, \
        "the adoption service does not use the route-held workspace"
    assert svc.prompts.workspace is svc.workspace, \
        "PromptWorkspaceService uses a different workspace"
    assert exp_api.studio_prompt_service.workspace is svc.workspace, \
        "the route-held PromptWorkspaceService uses a different workspace"
    assert exp_api.studio_prompt_authoring_service.workspace is svc.workspace, \
        "the route-held PromptAuthoringService uses a different workspace"
    return {"client": TestClient(app, raise_server_exceptions=False), "svc": svc,
            "adopt_api": adopt_api, "data_path": resolved}


@pytest.fixture
def flow(ctx):
    """Build the real chain over HTTP and return every real identifier."""
    client = ctx["client"]
    # A unique title per run: the project id is derived from it, so a fixed title collides
    # with the same run in a shared data root.
    project = client.post("/api/experimental/projects",
                          json={"title": "R3I HTTP " + uuid4().hex[:8]})
    assert project.status_code == 201, project.text[:300]
    nid = project.json()["id"]
    creative, studio = f"/api/novels/{nid}/experimental/creative", f"/api/projects/{nid}/studio"

    screenplay = client.post(f"{creative}/documents", json={
        "mode": "SCREENPLAY", "title": "R3-I HTTP 验收剧本", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日",
                    "action": "人物走向窗边"}]})
    assert screenplay.status_code == 201, screenplay.text[:300]
    sp = screenplay.json()

    derived = client.post(f"{creative}/documents/{sp['id']}/derive", json={
        "expected_version": sp["version"], "mode": "STORYBOARD",
        "title": "R3-I HTTP 分镜", "shot_policy": "SCENE"})
    assert derived.status_code == 201, derived.text[:300]
    board = derived.json()
    shots = board.get("shots") or []
    assert shots, "derive must produce real shots; none are fabricated"
    shot_id = shots[0]["id"]

    prompt = client.post(f"{studio}/prompts", json={
        "text": "电影感中景，人物站在窗前，柔和侧光", "purpose": "IMAGE", "origin": "MANUAL",
        "request_id": "r3i-http-prompt-" + uuid4().hex[:8]})
    assert prompt.status_code == 201, prompt.text[:300]
    p = prompt.json()
    approved = client.post(
        f"{studio}/prompts/{p['family_id']}/revisions/{p['asset_id']}/approve",
        params={"expected_version": p["asset_version"]})
    assert approved.status_code == 200, approved.text[:300]

    body = client.get(f"{studio}/prompts/{p['family_id']}/revisions/{p['asset_id']}/body")
    assert body.status_code == 200, body.text[:300]
    source = body.json()

    read = client.get(f"{studio}/documents/{board['id']}/prompt-adoption")
    assert read.status_code == 200, read.text[:300]
    target = read.json()

    dto = {"shot_id": shot_id, "family_id": p["family_id"], "asset_id": p["asset_id"],
           "revision": 1, "expected_digest": source["digest"],
           "expected_version": target["version"],
           "expected_digest_target": target["digest"], "request_id": "r3i-http-adopt-" + uuid4().hex[:8]}
    return {"client": client, "nid": nid, "studio": studio, "creative": creative,
            "board": board, "shot_id": shot_id, "prompt": p, "source": source,
            "target": target, "dto": dto,
            "adopt_url": f"{studio}/documents/{board['id']}/shots/{shot_id}/prompt-adoption",
            "read_url": f"{studio}/documents/{board['id']}/prompt-adoption"}


def test_the_closed_switch_refuses_an_authorized_write_and_changes_nothing(flow):
    """With the production default the route must refuse and leave the document untouched."""
    from app.creative.prompt_adoption_api import PROMPT_ADOPTION_WRITE_ENABLED
    assert PROMPT_ADOPTION_WRITE_ENABLED is False, "the production default must stay closed"
    response = flow["client"].post(flow["adopt_url"], json=flow["dto"])
    assert response.status_code == 503, response.text[:300]
    after = flow["client"].get(flow["read_url"]).json()
    assert after["version"] == flow["target"]["version"], "a closed switch must not write"
    assert after["adoptions"] == []


def test_the_official_http_adoption_closed_loop(ctx, flow):
    """The round's key deliverable: a real HTTP adoption, read back, then replayed."""
    client = flow["client"]
    ctx["adopt_api"].PROMPT_ADOPTION_WRITE_ENABLED = True   # in-process only
    try:
        response = client.post(flow["adopt_url"], json=flow["dto"])
        assert response.status_code == 200, response.text[:400]
        result = response.json()
        assert result["committed"] is True
        assert result["version"] == flow["target"]["version"] + 1

        # The proof describes the real source revision.
        proof = result["adoption"]
        assert proof["asset_id"] == flow["prompt"]["asset_id"]
        assert proof["revision"] == 1
        assert proof["digest"] == flow["source"]["digest"]
        assert proof["result_version"] == result["version"]

        # Read the document back and confirm the SHOT text is byte-identical to the source.
        reopen = client.get(f"{flow['creative']}/documents/{flow['board']['id']}")
        assert reopen.status_code == 200, reopen.text[:300]
        live = reopen.json()
        assert live["version"] == result["version"]
        shot = next(item for item in live["shots"] if item["id"] == flow["shot_id"])
        assert shot["frame_prompt"] == flow["source"]["value"], "text must be verbatim"
        assert hashlib.sha256(shot["frame_prompt"].encode("utf-8")).hexdigest() == proof["digest"]

        # GET projection agrees.
        read = client.get(flow["read_url"]).json()
        entry = read["adoptions"][-1]
        assert read["version"] == result["version"]
        assert entry["still_applied"] is True
        assert entry["asset_id"] == flow["prompt"]["asset_id"]

        # Same request_id retried: replay, and no second revision or proof.
        again = client.post(flow["adopt_url"], json=flow["dto"])
        assert again.status_code == 200, again.text[:300]
        assert again.json()["replayed"] is True
        assert again.json()["version"] == result["version"]
        final = client.get(flow["read_url"]).json()
        assert final["version"] == result["version"]
        assert len([a for a in final["adoptions"]
                    if a["request_id"] == flow["dto"]["request_id"]]) == 1

        # No model or media work was started.
        assert not any("job" in name.lower()
                       for name in ctx["svc"].workspace.store.read(
                           flow["nid"], {"mode": "local", "novel_id": flow["nid"]}
                       ).get("collections", {}))
    finally:
        # The production default must be restored no matter what happened above.
        ctx["adopt_api"].PROMPT_ADOPTION_WRITE_ENABLED = False
    assert ctx["adopt_api"].PROMPT_ADOPTION_WRITE_ENABLED is False


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_the_same_loop_is_reachable_under_both_api_prefixes(ctx, prefix):
    """A light reachability check: both prefixes expose the route and validate the DTO."""
    client = ctx["client"]
    url = f"{prefix}/projects/no-such-project/studio/documents/d1/shots/s1/prompt-adoption"
    empty = client.post(url, json={})
    assert empty.status_code == 422, empty.text[:200]
    assert ("body", "shot_id") in {tuple(i["loc"]) for i in empty.json()["detail"]}
