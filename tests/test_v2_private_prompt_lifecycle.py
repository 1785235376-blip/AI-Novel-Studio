"""Private prompt deletion through original identity, Asset and project owners."""
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

import pytest

from app.authorization import AuthorizationScope, ScopeKind
from test_v2_project_retirement import checked, mounted, prefix, retirement, role


TEXT = "PRIVATE_PROMPT_BODY\n保留原始创作文本"


@pytest.fixture
def prompts(retirement, monkeypatch):
    from app.creative.service import CreativeService
    e = retirement
    creative = CreativeService(e.store, e.novels, e.chapters)
    e.studio = e.experimental.independent_workspace_service
    for name, value in (("creative", creative), ("store", creative.store), ("novels", e.novels),
                        ("assets", e.assets), ("lineage", e.experimental.production_lineage_service)):
        monkeypatch.setattr(e.studio, name, value)
    e.prompt_base = e.prefix + f"/projects/{e.nid}/studio/prompts"
    e.asset_base = e.prefix + f"/projects/{e.nid}/studio/assets"
    e.prompt_service = e.experimental.studio_prompt_service
    return e


def create(e, *, text=TEXT, request_id=None):
    body = {"text": text, "purpose": "IMAGE", "origin": "MANUAL",
            "request_id": request_id or "private-delete-" + uuid4().hex}
    return checked(e.client.post(e.prompt_base, headers=e.activate(e.lead, branch=e.branch), json=body), 201), body


def read_body(e, receipt, *, actor=None):
    return e.client.get(e.prompt_base + f"/{receipt['family_id']}/revisions/{receipt['asset_id']}/body",
                        headers=e.activate(actor or e.lead, branch=e.branch))


def remove(e, receipt, version=None, *, actor=None, branch=None):
    return e.client.delete(e.asset_base + "/" + receipt["asset_id"],
        params={"expected_version": version or receipt["asset_version"]},
        headers=e.activate(actor or e.lead, branch=branch or e.branch))


def not_found(response):
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "EXPERIMENTAL_NOT_FOUND", response.text
    assert "PRIVATE_PROMPT_BODY" not in response.text


def metadata(e, aid):
    with e.studio._asset_scope(e.nid, e.scope):
        return deepcopy(e.assets.get(aid, branch_id=e.branch, actor_id=e.lead, include_deleted=True))


def owner_rows(e):
    with e.studio._asset_scope(e.nid, e.scope):
        return {row["id"]: deepcopy(row) for row in e.assets.list(
            e.nid, branch_id=e.branch, actor_id=e.lead, include_deleted=True)}


def interrupted_write(e, monkeypatch, operation, *, legacy=False):
    first, _ = create(e, text="Existing target predecessor")
    other, _ = create(e, text="Other family predecessor")
    body = {"text": TEXT, "purpose": "IMAGE", "origin": "MANUAL", "request_id": uuid4().hex}
    route = e.prompt_base
    if operation == "REVISE":
        route += f"/{first['family_id']}/revisions"
        body.update(expected_previous_asset_id=first["asset_id"], expected_revision=1)
    original_update, original_create = e.assets.update_metadata, e.assets.create
    interrupted = []
    def fail_once(aid, fields, **kwargs):
        if not interrupted:
            interrupted.append(aid)
            raise RuntimeError("INJECTED_AFTER_PROMPT_BODY_COMMIT")
        return original_update(aid, fields, **kwargs)
    def legacy_owner(*args, **kwargs):
        # Model a pre-marker body commit through the real original owner.
        # Identity, membership, session, scope and authorization stay untouched.
        kwargs.pop("_initial_prompt_write", None)
        return original_create(*args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(e.assets, "update_metadata", fail_once)
        if legacy:
            patch.setattr(e.assets, "create", legacy_owner)
        with pytest.raises(RuntimeError, match="INJECTED_AFTER_PROMPT_BODY_COMMIT"):
            e.client.post(route, headers=e.activate(e.lead, branch=e.branch), json=body)
    assert len(interrupted) == 1
    return route, body, first, other, interrupted[0]


def test_author_delete_returns_tombstone_without_removing_original_bytes(prompts):
    e = prompts
    receipt, _ = create(e)
    before = metadata(e, receipt["asset_id"])
    raw = (e.assets.root / (receipt["asset_id"] + ".bin")).read_bytes()
    original = checked(read_body(e, receipt))
    assert original["value"] == TEXT and original["verified"] is True
    removed = checked(remove(e, receipt))
    assert removed["id"] == receipt["asset_id"]
    assert removed["version"] == before["version"] + 1
    assert removed["deleted_at"] and removed["provenance"]["integrity"] == "DELETED"
    assert "_owner_actor_id" not in removed and "_project_binding" not in removed
    after = metadata(e, receipt["asset_id"])
    assert {k: v for k, v in after.items() if k not in {"version", "updated_at", "deleted_at"}} == {
        k: v for k, v in before.items() if k not in {"version", "updated_at", "deleted_at"}}
    assert (e.assets.root / (receipt["asset_id"] + ".bin")).read_bytes() == raw
    assert sha256(raw).hexdigest() == after["sha256"]
    body = checked(read_body(e, receipt))
    assert body["state"] == "DELETED" and body["value"] is None
    assert body["digest"] is None and body["verified"] is False and body["available"] is False
    detail = checked(e.client.get(e.prompt_base + "/" + receipt["family_id"],
        headers=e.activate(e.lead, branch=e.branch)))
    assert detail["family_id"] == receipt["family_id"]
    assert "DELETED" in str(detail) and TEXT not in str(detail)
    assert checked(e.client.get(e.prompt_base, headers=e.activate(e.lead, branch=e.branch)))["entries"] == []


def test_nonowner_and_readonly_actor_cannot_delete_private_prompt(prompts):
    e = prompts
    receipt, _ = create(e)
    before = metadata(e, receipt["asset_id"])
    role(e, e.new_actor, AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid))
    not_found(remove(e, receipt, actor=e.new_actor))
    not_found(read_body(e, receipt, actor=e.new_actor))
    denied = remove(e, receipt, actor=e.viewer)
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "PROJECT_SCOPE_FORBIDDEN", denied.text
    assert metadata(e, receipt["asset_id"]) == before
    assert checked(read_body(e, receipt))["value"] == TEXT


def test_delete_cas_retry_and_create_retry_cannot_resurrect_prompt(prompts):
    e = prompts
    receipt, body = create(e)
    removed = checked(remove(e, receipt))
    stale = remove(e, receipt)
    assert stale.status_code == 409, stale.text
    again = checked(remove(e, receipt, removed["version"]))
    assert again == removed
    replay = e.client.post(e.prompt_base, headers=e.activate(e.lead, branch=e.branch), json=body)
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["code"] == "PROMPT_REQUEST_DELETED", replay.text
    restore = e.client.post(e.asset_base + "/" + receipt["asset_id"] + "/restore",
        headers=e.activate(e.lead, branch=e.branch), json={"expected_version": removed["version"]})
    not_found(restore)
    assert metadata(e, receipt["asset_id"])["version"] == removed["version"]
    assert checked(read_body(e, receipt))["state"] == "DELETED"
    tombstone = metadata(e, receipt["asset_id"])
    raw = (e.assets.root / (receipt["asset_id"] + ".bin")).read_bytes()
    revise = e.client.post(e.prompt_base + f"/{receipt['family_id']}/revisions",
        headers=e.activate(e.lead, branch=e.branch), json={**body, "request_id": uuid4().hex,
            "expected_previous_asset_id": receipt["asset_id"], "expected_revision": 1})
    not_found(revise)
    assert metadata(e, receipt["asset_id"]) == tombstone
    assert (e.assets.root / (receipt["asset_id"] + ".bin")).read_bytes() == raw
    distinct, _ = create(e, text="A separate legitimate family")
    assert distinct["family_id"] != receipt["family_id"] and distinct["asset_id"] != receipt["asset_id"]
    assert checked(read_body(e, distinct))["value"] == "A separate legitimate family"


def test_delete_preserves_prior_revision_and_other_branch(prompts):
    e = prompts
    first, _ = create(e, text="PRIVATE_PROMPT_BODY original revision")
    second = checked(e.client.post(e.prompt_base + f"/{first['family_id']}/revisions",
        headers=e.activate(e.lead, branch=e.branch), json={"text": TEXT, "purpose": "IMAGE", "origin": "MANUAL",
            "request_id": uuid4().hex, "expected_previous_asset_id": first["asset_id"], "expected_revision": 1}), 201)
    prior = metadata(e, first["asset_id"])
    prior_body = checked(read_body(e, first))
    not_found(remove(e, second, branch=e.other_branch))
    checked(remove(e, second))
    assert metadata(e, first["asset_id"]) == prior
    reopened = checked(read_body(e, first))
    assert {k: v for k, v in reopened.items() if k != "generated_at"} == {
        k: v for k, v in prior_body.items() if k != "generated_at"}
    assert checked(read_body(e, second))["state"] == "DELETED"


def test_deleted_latest_revision_remains_family_cas_head(prompts):
    e = prompts
    first, _ = create(e, text="Original immutable family revision")
    revision_body = {"text": TEXT, "purpose": "IMAGE", "origin": "MANUAL", "request_id": uuid4().hex,
                     "expected_previous_asset_id": first["asset_id"], "expected_revision": 1}
    second = checked(e.client.post(e.prompt_base + f"/{first['family_id']}/revisions",
        headers=e.activate(e.lead, branch=e.branch), json=revision_body), 201)
    checked(remove(e, second))
    before = {r["asset_id"]: metadata(e, r["asset_id"]) for r in (first, second)}
    binaries = {aid: (e.assets.root / (aid + ".bin")).read_bytes() for aid in before}
    detail = checked(e.client.get(e.prompt_base + "/" + first["family_id"],
        headers=e.activate(e.lead, branch=e.branch)))
    assert detail["head_asset_id"] == second["asset_id"] and detail["revision"] == 2
    assert detail["body"]["state"] == "DELETED" and detail["body"]["value"] is None
    assert [r["asset_id"] for r in detail["versions"]] == [first["asset_id"], second["asset_id"]]
    stale = e.client.post(e.prompt_base + f"/{first['family_id']}/revisions",
        headers=e.activate(e.lead, branch=e.branch), json={**revision_body, "request_id": uuid4().hex})
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "PROMPT_REVISION_STALE", stale.text
    assert stale.json()["detail"]["current_revision"] == 2, stale.text
    deleted = e.client.post(e.prompt_base + f"/{first['family_id']}/revisions",
        headers=e.activate(e.lead, branch=e.branch), json={**revision_body, "request_id": uuid4().hex,
            "expected_previous_asset_id": second["asset_id"], "expected_revision": 2})
    assert deleted.status_code == 409, deleted.text
    assert deleted.json()["detail"]["code"] == "PROMPT_REVISION_DELETED", deleted.text
    replay = e.client.post(e.prompt_base + f"/{first['family_id']}/revisions",
        headers=e.activate(e.lead, branch=e.branch), json=revision_body)
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["code"] == "PROMPT_REQUEST_DELETED", replay.text
    assert {aid: metadata(e, aid) for aid in before} == before
    assert {aid: (e.assets.root / (aid + ".bin")).read_bytes() for aid in before} == binaries
    reopened = checked(e.client.get(e.prompt_base + "/" + first["family_id"],
        headers=e.activate(e.lead, branch=e.branch)))
    assert {k: v for k, v in reopened.items() if k != "generated_at"} == {
        k: v for k, v in detail.items() if k != "generated_at"}


@pytest.mark.parametrize("changed_identity", ["other_family", "previous_asset", "expected_revision", "create_route"])
def test_revision_replay_is_bound_to_original_family_route_and_expectations(prompts, changed_identity):
    e = prompts
    first, _ = create(e, text="First immutable predecessor")
    other, _ = create(e, text="Independent family predecessor")
    route = e.prompt_base + f"/{first['family_id']}/revisions"
    body = {"text": TEXT, "purpose": "IMAGE", "origin": "MANUAL", "request_id": uuid4().hex,
            "expected_previous_asset_id": first["asset_id"], "expected_revision": 1}
    saved = checked(e.client.post(route, headers=e.activate(e.lead, branch=e.branch), json=body), 201)
    valid = checked(e.client.post(route, headers=e.activate(e.lead, branch=e.branch), json=body), 201)
    assert valid["idempotent_replay"] is True
    assert {k: v for k, v in valid.items() if k != "idempotent_replay"} == {
        k: v for k, v in saved.items() if k != "idempotent_replay"}
    with e.studio._asset_scope(e.nid, e.scope):
        before = {row["id"]: deepcopy(row) for row in e.assets.list(
            e.nid, branch_id=e.branch, actor_id=e.lead, include_deleted=True)}
    binaries = {aid: (e.assets.root / (aid + ".bin")).read_bytes() for aid in before}
    changed = dict(body)
    if changed_identity == "other_family":
        route = e.prompt_base + f"/{other['family_id']}/revisions"
        changed["expected_previous_asset_id"] = other["asset_id"]
    elif changed_identity == "previous_asset":
        changed["expected_previous_asset_id"] = other["asset_id"]
    elif changed_identity == "expected_revision":
        changed["expected_revision"] = 2
    else:
        route = e.prompt_base
        changed.pop("expected_previous_asset_id")
        changed.pop("expected_revision")
    refused = e.client.post(route, headers=e.activate(e.lead, branch=e.branch), json=changed)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "PROMPT_REQUEST_ID_REUSED", refused.text
    assert TEXT not in refused.text and first["asset_id"] not in refused.text and other["asset_id"] not in refused.text
    with e.studio._asset_scope(e.nid, e.scope):
        after = {row["id"]: deepcopy(row) for row in e.assets.list(
            e.nid, branch_id=e.branch, actor_id=e.lead, include_deleted=True)}
    assert after == before
    assert {aid: (e.assets.root / (aid + ".bin")).read_bytes() for aid in after} == binaries


@pytest.mark.parametrize(("operation", "change"), [
    ("CREATE", "operation"), ("CREATE", "metadata"), ("CREATE", "purpose"),
    ("CREATE", "negative_prompt"), ("CREATE", "text"),
    ("REVISE", "operation"), ("REVISE", "family"), ("REVISE", "previous_asset"),
    ("REVISE", "expected_revision"), ("REVISE", "metadata"), ("REVISE", "purpose"),
    ("REVISE", "negative_prompt"), ("REVISE", "text"),
])
def test_pending_prompt_retry_keeps_atomic_original_target_and_content(prompts, monkeypatch, operation, change):
    e = prompts
    route, body, first, other, aid = interrupted_write(e, monkeypatch, operation)
    before = owner_rows(e)
    binaries = {identity: (e.assets.root / (identity + ".bin")).read_bytes() for identity in before}
    pending = before[aid]
    marker = deepcopy(pending["_prompt_write_origin"])
    assert marker["contract"] == "studio-prompt-write-origin/1" and marker["operation"] == operation
    assert marker["allocated_family_id"]
    assert marker["expected_previous_asset_id"] == (first["asset_id"] if operation == "REVISE" else None)
    assert marker["expected_revision"] == (1 if operation == "REVISE" else None)
    assert len(marker["request_digest"]) == 64
    assert "_prompt_write_origin" not in e.assets.public(pending)
    assert binaries[aid] == TEXT.encode("utf-8")
    changed_route, changed = route, dict(body)
    if change == "operation":
        if operation == "CREATE":
            changed_route = e.prompt_base + f"/{first['family_id']}/revisions"
            changed.update(expected_previous_asset_id=first["asset_id"], expected_revision=1)
        else:
            changed_route = e.prompt_base
            changed.pop("expected_previous_asset_id")
            changed.pop("expected_revision")
    elif change == "family":
        changed_route = e.prompt_base + f"/{other['family_id']}/revisions"
        changed["expected_previous_asset_id"] = other["asset_id"]
    elif change == "previous_asset":
        changed["expected_previous_asset_id"] = other["asset_id"]
    elif change == "expected_revision":
        changed["expected_revision"] = 2
    elif change == "metadata":
        changed["parameters"] = {"steps": 31}
    elif change == "purpose":
        changed["purpose"] = "VIDEO"
    elif change == "negative_prompt":
        changed["negative_prompt"] = "Different authored negative prompt"
    else:
        changed["text"] = TEXT + " different text"
    refused = e.client.post(changed_route, headers=e.activate(e.lead, branch=e.branch), json=changed)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "PROMPT_REQUEST_ID_REUSED", refused.text
    assert TEXT not in refused.text and aid not in refused.text
    assert owner_rows(e) == before
    assert {identity: (e.assets.root / (identity + ".bin")).read_bytes() for identity in before} == binaries
    resumed = checked(e.client.post(route, headers=e.activate(e.lead, branch=e.branch), json=body), 201)
    assert resumed["asset_id"] == aid and resumed["family_id"] == marker["allocated_family_id"]
    assert resumed["revision"] == (2 if operation == "REVISE" else 1)
    completed = owner_rows(e)
    assert set(completed) == set(before)
    assert completed[aid]["_prompt_write_origin"] == marker
    assert {identity: row for identity, row in completed.items() if identity != aid} == {
        identity: row for identity, row in before.items() if identity != aid}
    assert {identity: (e.assets.root / (identity + ".bin")).read_bytes() for identity in completed} == binaries
    replay = checked(e.client.post(route, headers=e.activate(e.lead, branch=e.branch), json=body), 201)
    assert replay["asset_id"] == aid and replay["idempotent_replay"] is True
    assert owner_rows(e) == completed


@pytest.mark.parametrize("operation", ["CREATE", "REVISE"])
def test_legacy_pending_prompt_without_target_origin_stays_unverified(prompts, monkeypatch, operation):
    e = prompts
    route, body, _, _, aid = interrupted_write(e, monkeypatch, operation, legacy=True)
    before = owner_rows(e)
    binaries = {identity: (e.assets.root / (identity + ".bin")).read_bytes() for identity in before}
    assert "_prompt_write_origin" not in before[aid]
    refused = e.client.post(route, headers=e.activate(e.lead, branch=e.branch), json=body)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "PROMPT_REQUEST_ORIGIN_UNVERIFIED", refused.text
    assert aid not in refused.text and TEXT not in refused.text
    assert owner_rows(e) == before
    assert {identity: (e.assets.root / (identity + ".bin")).read_bytes() for identity in before} == binaries
