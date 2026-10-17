"""Private digest-only history on original File owners; no new consumer authority.

Run only through scripts/run_v2_checks.py after source freeze and approval.
"""
from copy import deepcopy
import hashlib
import json

import pytest
from fastapi import HTTPException

from app.creative.director_terminal_evidence import FIELD, validate_evidence
from app.jobs import JobManager, generation_content_available
from creative_director_execution_fixture import (
    TEXT, ForbiddenOwner, lifecycle, preview, raw_proposal, result, run, wait,
)

pytestmark = pytest.mark.file_backend_only
DENIALS = (ValueError, HTTPException, PermissionError, FileNotFoundError, KeyError)


def publish(e):
    prepared = preview(e)
    try:
        receipt = e.coordinator._dispatch_independent(e.ctx, prepared["id"], {
            "expected_version": prepared["version"],
            "reviewed_preview_digest": prepared["model_preview"]["preview_digest"],
        }, e.guard, host_authority=e.authority, terminal_evidence=True)
    except DENIALS:
        if len(e.manager.jobs) != 1:
            raise
        receipt = raw_proposal(e)
    job = e.manager.get(receipt["model_execution"]["job_id"])
    return prepared, wait(e, job)


def test_original_success_is_digest_only_passive_history(lifecycle):
    e = lifecycle
    prepared, job = publish(e)
    assert job.status == "COMPLETED" and job.creative_execution_authority.publication_state == "ACKNOWLEDGED"
    saved = e.persistence.get(job.id)
    evidence = saved[FIELD]
    assert validate_evidence(evidence, saved) == evidence
    assert evidence["source_binding"] == job.creative_director_binding
    assert evidence["request_digest"] == job.expected_request_digest
    assert evidence["output_digest"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert evidence["output_bytes"] == len(TEXT.encode())
    assert evidence["admission"]["preview_digest"] == prepared["model_preview"]["preview_digest"]
    assert evidence["admission"]["output_contract"] is None
    assert evidence["route"]["parameters"] == {"max_output_tokens": 512, "temperature": 0.0}
    assert evidence["accounting"]["status"] == "SETTLED"
    assert evidence["consumer_authority"] is False
    assert evidence["semantics"] == "AUTHORITY_AND_BOUNDS_SAMPLED_PRE_COMMIT"
    assert TEXT not in json.dumps(evidence)
    assert prepared["model_preview"]["prompt"] not in json.dumps(evidence)
    assert FIELD not in job.public()
    assert not generation_content_available(job)
    # Existing private live result still requires its original capability and
    # deadline. It does not consume the historical envelope.
    assert result(e)["text"] == TEXT
    assert len(e.requests) == 1 and len(e.broker.ledger(e.nid, e.scope, e.actor)) == 1


@pytest.mark.parametrize("change", ["null", "empty", "output", "source", "accounting", "extra", "bool_cost", "bool_schema", "numeric_type_alias"])
def test_generic_save_cannot_replace_or_erase_history(lifecycle, change):
    e = lifecycle
    _, job = publish(e)
    saved = e.persistence.get(job.id)
    changed = deepcopy(saved)
    if change == "null": changed[FIELD] = None
    elif change == "empty": changed[FIELD] = {}
    elif change == "output": changed[FIELD]["output_digest"] = "a" * 64
    elif change == "source": changed[FIELD]["source_binding"]["source_version"] += 1
    elif change == "accounting": changed[FIELD]["accounting"]["version"] += 1
    elif change == "bool_cost": changed[FIELD]["accounting"]["actual_microusd"] = False
    elif change == "bool_schema": changed[FIELD]["schema_version"] = True
    elif change == "numeric_type_alias": changed[FIELD]["route"]["parameters"]["temperature"] = 0
    else: changed[FIELD]["arbitrary"] = "forged"
    with pytest.raises(ValueError): e.persistence.save(changed)
    assert e.persistence.get(job.id) == saved


def test_generic_omission_preserves_history_despite_live_output_clear_and_restart(lifecycle):
    e = lifecycle
    _, job = publish(e)
    saved = e.persistence.get(job.id)
    changed = job.public()
    changed.update(status="FAILED", output="", error_code="HISTORICAL_LIVE_AUTHORITY_EXPIRED")
    e.persistence.save(changed)
    historical = e.persistence.get(job.id)
    assert historical[FIELD] == saved[FIELD]
    assert validate_evidence(historical[FIELD], historical) == saved[FIELD]
    forbidden = ForbiddenOwner()
    reopened = JobManager(e.persistence, forbidden, forbidden, forbidden, memory_extractor=forbidden,
        snapshot_required=True, collaboration_updates=forbidden)
    restored = reopened.get(job.id)
    assert restored.creative_execution_authority is None
    assert FIELD not in restored.public() and not generation_content_available(restored)
    reopened._persist(restored)
    assert e.persistence.get(job.id)[FIELD] == saved[FIELD]
    with pytest.raises(ValueError):
        e.persistence.repository._publish_director_terminal(restored, None, saved[FIELD])
    assert len(e.requests) == 1


@pytest.mark.parametrize("value", [None, {}, {"contract": "CREATIVE_DIRECTOR_TERMINAL_HISTORY_V1"}])
def test_generic_save_cannot_mint_history_on_legacy_completion(lifecycle, value):
    e = lifecycle
    _, _, job = run(e)
    saved = e.persistence.get(job.id)
    assert FIELD not in saved and job.creative_execution_authority.publication_state is None
    changed = deepcopy(saved); changed[FIELD] = value
    with pytest.raises(ValueError): e.persistence.save(changed)
    assert e.persistence.get(job.id) == saved


@pytest.mark.parametrize("value", [None, 0, 1, "true", [], {}])
def test_private_option_is_strict_before_any_admission_effect(lifecycle, value):
    e = lifecycle
    before = e.raw.read(e.nid, e.scope)
    with pytest.raises(ValueError, match="TERMINAL_OPTION_INVALID"):
        e.coordinator._dispatch_independent(e.ctx, e.row["id"], {}, e.guard,
            host_authority=e.authority, terminal_evidence=value)
    assert e.raw.read(e.nid, e.scope) == before
    assert not e.requests and not e.manager.jobs


def test_unsupported_repository_denied_before_admission(lifecycle, monkeypatch):
    e = lifecycle
    before = e.raw.read(e.nid, e.scope)
    monkeypatch.setattr(e.persistence, "repository", ForbiddenOwner())
    with pytest.raises(ValueError, match="TERMINAL_BACKEND_UNSUPPORTED"):
        e.coordinator._dispatch_independent(e.ctx, e.row["id"], {}, e.guard,
            host_authority=e.authority, terminal_evidence=True)
    assert e.raw.read(e.nid, e.scope) == before and not e.requests and not e.manager.jobs


def test_postgres_reserved_field_rejection_never_opens_database():
    from app.repositories.postgres.generation import PostgresGenerationRepository
    class NoDatabase:
        def session(self): raise AssertionError("PostgreSQL execution is not authorized")
    repository = PostgresGenerationRepository(NoDatabase())
    with pytest.raises(ValueError, match="TERMINAL_POSTGRES_UNSUPPORTED"):
        repository.save({"id": "forged", FIELD: None})


@pytest.mark.parametrize("change", ["secret_parameter", "bool_cost", "bool_schema", "consumer", "future_checkpoint"])
def test_passive_schema_is_closed_and_historical(lifecycle, change):
    e = lifecycle
    _, job = publish(e)
    saved = e.persistence.get(job.id)
    evidence = deepcopy(saved[FIELD])
    if change == "secret_parameter": evidence["route"]["parameters"]["api_key"] = "never-retain"
    elif change == "bool_cost": evidence["accounting"]["actual_microusd"] = False
    elif change == "bool_schema": evidence["schema_version"] = True
    elif change == "consumer": evidence["consumer_authority"] = True
    else: evidence["checkpoint_at"] = evidence["generation_deadline"]
    with pytest.raises(ValueError): validate_evidence(evidence, saved)


@pytest.mark.parametrize("jid", ["../jobs/original", "./original", "nested/../original", "nested\\original", "/original", "C:original", ".", "..", "bad\x00id"])
def test_path_alias_is_rejected_before_repository_io(tmp_path, monkeypatch, jid):
    from app.repositories.generation_repository import GenerationRepository
    from app.repositories.file import mutation_coordinator
    repository = GenerationRepository(tmp_path)
    original = {"id": "original", "status": "COMPLETED", "output": "unchanged"}
    repository.save(original)
    target = repository.root / "original.json"
    before = target.read_bytes()
    def forbidden(*args, **kwargs): raise AssertionError("Invalid ID reached filesystem lock")
    monkeypatch.setattr(mutation_coordinator, "workspace_mutation", forbidden)
    with pytest.raises(ValueError, match="GENERATION_JOB_ID_INVALID"):
        repository.save({"id": jid, "output": "overwrite"})
    with pytest.raises(ValueError, match="GENERATION_JOB_ID_INVALID"):
        repository.get(jid)
    assert target.read_bytes() == before


def test_ordinary_legacy_basename_ids_remain_supported(tmp_path):
    from app.repositories.generation_repository import GenerationRepository
    repository = GenerationRepository(tmp_path)
    for jid in ("job", "interrupted", "old-job", "legacy_job.1", "job:legacy"):
        item = {"id": jid, "status": "FAILED"}
        repository.save(item)
        assert repository.get(jid) == item


def test_canonical_leaf_key_respects_platform_case_normalization(tmp_path, monkeypatch):
    import app.repositories.generation_repository as module
    repository = module.GenerationRepository(tmp_path)
    monkeypatch.setattr(module.os.path, "normcase", lambda path: path.lower())
    assert repository._write_key(repository._job_path("ABC")) == repository._write_key(repository._job_path("abc"))


def test_callback_substitution_at_final_guard_cannot_acknowledge_without_publication(lifecycle, monkeypatch):
    import app.jobs as jobs_module
    e = lifecycle
    original_emit, original_bounds = e.manager._emit, jobs_module.check_generation_bounds
    final_emit, swapped, fake_calls = [], [], []
    def emit(job, *args, **kwargs):
        response = original_emit(job, *args, **kwargs)
        if job.status == "COMPLETED" and job.terminal_hook_status == "COMPLETED":
            final_emit.append(job.id)
        return response
    def bounds(job, **kwargs):
        response = original_bounds(job, **kwargs)
        if final_emit and not swapped:
            capability = job.creative_execution_authority
            original = capability.terminal_publication
            def fake():
                fake_calls.append(1)
                capability.terminal_publication = original
            capability.terminal_publication = fake
            swapped.append(1)
        return response
    monkeypatch.setattr(e.manager, "_emit", emit)
    monkeypatch.setattr(jobs_module, "check_generation_bounds", bounds)
    _, job = publish(e)
    assert swapped == [1] and fake_calls == []
    assert job.creative_execution_authority.publication_state == "UNKNOWN"
    assert job.status == "FAILED" and not job.output
    assert FIELD not in e.persistence.get(job.id)
    with pytest.raises(DENIALS): result(e)
    assert len(e.requests) == 1


def test_original_capability_cannot_publish_twice(lifecycle, monkeypatch):
    import app.repositories.generation_repository as repository_module
    e = lifecycle
    _, job = publish(e)
    saved = e.persistence.get(job.id)
    def forbidden(*args, **kwargs): raise AssertionError("Repeated publication attempted IO")
    monkeypatch.setattr(repository_module, "atomic_write", forbidden)
    with pytest.raises(ValueError, match="TERMINAL_OWNER_REQUIRED"):
        e.persistence.repository._publish_director_terminal(job, job.creative_execution_authority, saved[FIELD])
    assert e.persistence.get(job.id) == saved
    assert job.creative_execution_authority.publication_state == "ACKNOWLEDGED"
    assert len(e.requests) == 1
