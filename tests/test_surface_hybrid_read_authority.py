"""Hybrid retrieval uses current branch read authority, never write authority.

Mounted File/real-PostgreSQL contracts share the existing trusted-session and
membership fixtures. Only embedding outputs are synthetic, with no model claim.
"""
from uuid import uuid4

import pytest

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.experimental.embeddings import MockEmbeddingProvider
from test_r3_mounted_contracts import checked, mounted, prefix, scoped


PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8A"
    "AwMCAO+a2S0AAAAASUVORK5CYII="
)


def create_index(e, asset, title):
    row = checked(e.client.post(e.emb + "/indexes", headers=e.headers, json={
        "title": title, "entities": [{"entity_type": "ASSET", "entity_id": asset["id"]}],
    }), 201)
    return checked(e.client.post(e.emb + f"/indexes/{row['id']}/rebuild",
                                 headers=e.headers, json={"expected_version": row["version"]}))


@pytest.fixture
def readable_index(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    e.embedding = e.experimental.embedding_service
    e.provider = MockEmbeddingProvider()
    monkeypatch.setattr(e.embedding, "provider", e.provider)
    e.emb = e.base + "/embeddings"
    asset = e.assets.create(e.nid, "shared-healer.png", PNG, "image/png", "image",
                            branch_id=e.branch, owner_actor_id=e.lead)
    # Seed through the real approval authority; no mainline manuscript is used.
    e.asset = e.assets.promote_owned(asset["id"], actor_id=e.lead, branch_id=e.branch,
        expected_version=asset["version"], provenance={"source": "hybrid-read-authority-test"})
    assert e.asset["approved_at"]
    e.index = create_index(e, e.asset, "Shared branch healer")
    assert e.index["status"] == "ACTIVE" and not e.index["private_sources"]
    e.query = {"index_id": e.index["id"], "text": "healer",
               "expected_index_version": e.index["index_version"]}
    return e


def test_branch_reader_queries_shared_index_but_cannot_mutate(readable_index):
    e = readable_index
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    assert e.authorization.is_allowed(e.viewer, "domain.read", ModalityDomain.NOVEL, scope)
    assert not e.authorization.is_allowed(e.viewer, "domain.write", ModalityDomain.NOVEL, scope)
    assert e.authorization.repository.list_role_assignments(e.viewer) == []
    before = e.store.read(e.nid, e.scope)
    for endpoint, mode in (("query", "VECTOR"), ("hybrid-query", "HYBRID_LEXICAL_VECTOR")):
        response = e.client.post(e.emb + "/" + endpoint, headers=e.viewer_headers, json=e.query)
        result = checked(response)
        assert response.headers["Cache-Control"] == "no-store"
        assert result["retrieval_mode"] == mode
        assert result["verification"] == "MOCK_ONLY" and result["model_quality"] == "NOT_RUN"
        assert len(result["items"]) == 1
        citation = result["items"][0]["citation"]
        assert citation["branch_id"] == e.branch and citation["novel_id"] == e.nid
        assert citation["entity"]["entity_id"] == e.asset["id"]
        assert citation["source_digest"] == e.asset["sha256"]
        assert citation["source_version"] == e.asset["version"]

    body = {"title": "Denied edit", "entities": e.index["entities"]}
    assert e.client.post(e.emb + "/indexes", headers=e.viewer_headers, json=body).status_code == 403
    assert e.client.put(e.emb + f"/indexes/{e.index['id']}", headers=e.viewer_headers,
                        json={**body, "expected_version": e.index["version"]}).status_code == 403
    for action in ("rebuild", "invalidate", "remove", "cancel"):
        response = e.client.post(e.emb + f"/indexes/{e.index['id']}/{action}",
            headers=e.viewer_headers, json={"expected_version": e.index["version"]})
        assert response.status_code == 403, response.text
    assert e.store.read(e.nid, e.scope) == before
    assert e.assets.get(e.asset["id"], branch_id=e.branch, actor_id=e.viewer)["version"] == e.asset["version"]


def test_branch_reader_cannot_query_private_or_other_branch_index(readable_index):
    e = readable_index
    private = e.assets.create(e.nid, "private-healer.png", PNG, "image/png", "image",
                              branch_id=e.branch, owner_actor_id=e.lead)
    private_index = create_index(e, private, "Private branch healer")
    assert private_index["private_sources"]
    listed = checked(e.client.get(e.emb + "/indexes", headers=e.viewer_headers))["items"]
    assert [row["id"] for row in listed] == [e.index["id"]]
    denied = e.client.post(e.emb + "/hybrid-query", headers=e.viewer_headers,
                           json={**e.query, "index_id": private_index["id"]})
    assert denied.status_code == 404 and "Private branch healer" not in denied.text

    other_headers = {**e.viewer_headers, "X-Branch-ID": e.other_branch}
    assert e.client.post(e.emb + "/hybrid-query", headers=other_headers, json=e.query).status_code == 403
    other_scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.other_branch)
    e.authorization.assign_permission(PermissionAssignment("read-other-" + uuid4().hex, e.viewer,
        "domain.read", ModalityDomain.NOVEL, other_scope, e.lead))
    denied = e.client.post(e.emb + "/hybrid-query", headers=other_headers, json=e.query)
    assert denied.status_code == 404 and e.asset["id"] not in denied.text


@pytest.mark.parametrize("revoke_at", ["provider_return", "service_return"])
def test_hybrid_reader_late_permission_revocation_discards_results(readable_index, monkeypatch, revoke_at):
    e = readable_index
    assignments = e.authorization.repository.list_permission_assignments(e.viewer)
    assert len(assignments) == 1 and assignments[0]["permission"] == "domain.read"
    before = e.store.read(e.nid, e.scope)
    target, method = (e.provider, "embed") if revoke_at == "provider_return" else (e.embedding, "query")
    original = getattr(target, method)
    completed = []

    def revoke_after_work(*args, **kwargs):
        result = original(*args, **kwargs)
        if revoke_at == "service_return":
            assert result["items"][0]["citation"]["entity"]["entity_id"] == e.asset["id"]
        completed.append(True)
        e.authorization.revoke_permission(assignments[0]["id"], e.lead)
        return result

    monkeypatch.setattr(target, method, revoke_after_work)
    response = e.client.post(e.emb + "/hybrid-query", headers=e.viewer_headers, json=e.query)
    assert completed == [True]
    assert response.status_code == 403, response.text
    assert "items" not in response.json() and e.asset["id"] not in response.text
    assert "source_digest" not in response.text and "Shared branch healer" not in response.text
    assert e.store.read(e.nid, e.scope) == before
    # The initial guard also rejects a now-revoked reader before any more work.
    assert e.client.post(e.emb + "/hybrid-query", headers=e.viewer_headers, json=e.query).status_code == 403
    assert completed == [True]
