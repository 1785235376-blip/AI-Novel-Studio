from __future__ import annotations

import pytest

from app.repositories.file.lore import FileLoreRepository
from app.repository import FileRepository
from app.services.lore_service import LoreService
from tests.test_lore_contract import evidence, proposal


@pytest.fixture
def service(tmp_path):
    backend = FileRepository(tmp_path); backend.create_novel({"id": "lore-test", "title": "Lore Test"}); backend.create_chapter("lore-test", {"number": 1})
    repo = FileLoreRepository(backend)
    return LoreService(repo), repo


def test_proposal_requires_evidence(service):
    lore, _ = service
    with pytest.raises(ValueError, match="requires evidence"): lore.create_proposal(proposal("lore-test"), [])


def test_create_and_approve_proposal(service):
    lore, repo = service; ev = lore.create_evidence(evidence("lore-test")); item = proposal("lore-test")
    created = lore.create_proposal(item, [{"evidence_id": ev["id"], "relevance": "PRIMARY"}])
    approved = lore.approve_proposal(created["id"], {"accepted": True}, "local-user")
    assert approved["status"] == "APPROVED" and approved["payload"] == item["payload"] and approved["approved_payload"] == {"accepted": True}
    with pytest.raises(ValueError): lore.approve_proposal(created["id"], {}, "local-user")


def test_invalidated_evidence_blocks_approval(service):
    lore, _ = service; ev = lore.create_evidence(evidence("lore-test")); created = lore.create_proposal(proposal("lore-test"), [{"evidence_id": ev["id"], "relevance": "PRIMARY"}])
    lore.invalidate_evidence(ev["id"], "superseded source")
    with pytest.raises(ValueError, match="must be ACTIVE"): lore.approve_proposal(created["id"], {}, "local-user")


def test_reject_keeps_evidence(service):
    lore, repo = service; ev = lore.create_evidence(evidence("lore-test")); created = lore.create_proposal(proposal("lore-test"), [{"evidence_id": ev["id"], "relevance": "PRIMARY"}])
    rejected = lore.reject_proposal(created["id"], "local-user", "not durable lore")
    assert rejected["status"] == "REJECTED" and repo.get_evidence(ev["id"])["status"] == "ACTIVE"


def test_primary_evidence_and_novel_isolation_are_required(tmp_path):
    backend = FileRepository(tmp_path); backend.create_novel({"id": "one", "title": "One"}); backend.create_novel({"id": "two", "title": "Two"}); repo = FileLoreRepository(backend); lore = LoreService(repo)
    ev = lore.create_evidence(evidence("one"))
    with pytest.raises(ValueError, match="PRIMARY"): lore.create_proposal(proposal("one"), [{"evidence_id": ev["id"], "relevance": "SUPPORTING"}])
    with pytest.raises(ValueError, match="same novel"): lore.create_proposal(proposal("two"), [{"evidence_id": ev["id"], "relevance": "PRIMARY"}])
