from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.lore.schemas import Evidence, LoreProposal
from app.repositories.file.lore import FileLoreRepository
from app.repositories.postgres.lore import PostgresLoreRepository
from app.repository import FileRepository


def evidence(novel_id: str, *, evidence_id: str | None = None) -> dict:
    excerpt = "The captain recognized the signal."
    return {"id": evidence_id or str(uuid.uuid4()), "novel_id": novel_id, "schema_version": 1, "source_type": "CHAPTER_VERSION", "source_id": f"{novel_id}:1:v1", "chapter_id": f"{novel_id}:1", "chapter_version": 1, "excerpt": excerpt, "locator": {"kind": "DOCUMENT_RANGE", "from": 1, "to": 38}, "content_hash": hashlib.sha256(excerpt.encode()).hexdigest(), "privacy": "CLOUD_ALLOWED", "status": "ACTIVE"}


def proposal(novel_id: str, *, proposal_id: str | None = None) -> dict:
    return {"id": proposal_id or str(uuid.uuid4()), "novel_id": novel_id, "schema_version": 1, "proposal_type": "CHARACTER_MEMORY", "payload": {"character_id": "captain", "memory_type": "EXPERIENCE", "content": {"event": "recognized signal"}}, "status": "PENDING", "confidence": 0.8, "agent_name": "memory_agent", "generation_job_id": str(uuid.uuid4())}


@pytest.fixture
def file_lore(tmp_path: Path):
    backend = FileRepository(tmp_path)
    backend.create_novel({"id": "lore-test", "title": "Lore Test"})
    backend.create_chapter("lore-test", {"number": 1, "title": "One"})
    return FileLoreRepository(backend)


def run_repository_contract(repo, novel_id: str):
    ev = repo.create_evidence(evidence(novel_id)); assert repo.get_evidence(ev["id"]) == ev
    assert repo.list_evidence(novel_id) == [ev]
    prop = repo.create_proposal(proposal(novel_id)); assert prop["status"] == "PENDING"
    relation = repo.link_evidence({"schema_version": 1, "proposal_id": prop["id"], "evidence_id": ev["id"], "relevance": "PRIMARY"})
    assert repo.list_proposal_evidence(prop["id"]) == [relation]
    approved = repo.approve_proposal(prop["id"], {"accepted": True}, "tester"); assert approved["status"] == "APPROVED"
    with pytest.raises(ValueError): repo.approve_proposal(prop["id"], {}, "tester")


def test_file_lore_repository_contract(file_lore):
    run_repository_contract(file_lore, "lore-test")


def test_schema_validation_rejects_unknown_version_and_enum():
    with pytest.raises(ValidationError): Evidence.model_validate({**evidence("n"), "schema_version": 2})
    with pytest.raises(ValidationError): Evidence.model_validate({**evidence("n"), "source_type": "INVENTED"})
    with pytest.raises(ValidationError): LoreProposal.model_validate({**proposal("n"), "proposal_type": "INVENTED"})


def test_evidence_is_immutable_and_can_only_be_invalidated(file_lore):
    item = file_lore.create_evidence(evidence("lore-test"))
    with pytest.raises(FileExistsError): file_lore.create_evidence({**item, "excerpt": "changed"})
    invalidated = file_lore.invalidate_evidence(item["id"], "source withdrawn")
    assert invalidated["status"] == "INVALIDATED"
    with pytest.raises(ValueError): file_lore.invalidate_evidence(item["id"], "again")


def test_relation_enforces_novel_isolation(tmp_path: Path):
    backend = FileRepository(tmp_path); backend.create_novel({"id": "one", "title": "One"}); backend.create_novel({"id": "two", "title": "Two"})
    repo = FileLoreRepository(backend); ev = repo.create_evidence(evidence("one")); prop = repo.create_proposal(proposal("two"))
    with pytest.raises(ValueError): repo.link_evidence({"proposal_id": prop["id"], "evidence_id": ev["id"], "relevance": "PRIMARY"})


def test_postgres_repository_fails_clearly_without_migration_004():
    class EmptyDatabase:
        from sqlalchemy import create_engine
        engine = create_engine("sqlite://")
    database = EmptyDatabase()
    try:
        with pytest.raises(RuntimeError, match="missing tables"):
            PostgresLoreRepository(database).list_evidence("anything")
    finally:
        database.engine.dispose()


@pytest.mark.skip(reason="Migration 004 is intentionally absent in Phase 1")
def test_postgres_lore_repository_contract_when_schema_is_available():
    raise AssertionError("activate after Migration 004 is available in a disposable database")
