from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.document import document_to_markdown, markdown_to_document
from app.idempotency import IdempotencyStore
from app.jobs import JobManager
from app.main import app
from app.repositories.factory import create_repository_bundle
from app.services import CanonService, ChapterService, ContextService, GenerationService, LoreService, NovelService


@pytest.fixture
def source(tmp_path, monkeypatch):
    """Real File owners with synthetic staging, explicitly legacy HYBRID mode.

    New keyed LOCAL_ONLY admission requires original memory/dispatch composition
    and is covered separately by test_file_keyed_activation.py.
    """
    import app.api as api
    import app.jobs as jobs_module
    import app.main as main_module

    config = Settings(storage_backend="file", novel_data=tmp_path, mock_provider=True,
                      enable_collaboration_runtime=False, enable_packaged_runtime=False)
    bundle = create_repository_bundle(config, tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    novel = novels.create({"id": "variants-book", "title": "Variant contracts"})
    created = chapters.create(novel["id"], {"title": "One", "content": "Original source"})
    chapter = chapters.get(created["id"])
    manager = JobManager(
        generations=GenerationService(bundle.generations), chapters=chapters,
        contexts=ContextService(bundle.novels, bundle.chapters, LoreService(bundle.lore)),
        canon=CanonService(bundle.canon), snapshot_required=False,
        memory_extractor=SimpleNamespace(enqueue=lambda *_args: "synthetic-memory-job"),
    )
    dispatched = []

    def stage_without_model(job):
        if job.request_authorization is not None:
            job.request_authorization()
        with manager.lock:
            job.status = "QUEUED"
            manager.jobs[job.id] = job
            manager._persist(job)
            dispatched.append(job.id)
        return job

    monkeypatch.setattr(manager, "start_prepared", stage_without_model)
    for module in (api, main_module, jobs_module):
        monkeypatch.setattr(module, "settings", config)
    monkeypatch.setattr(api, "novel_service", novels)
    monkeypatch.setattr(api, "chapter_service", chapters)
    monkeypatch.setattr(api, "jobs", manager)
    monkeypatch.setattr(api, "_idempotency_store", IdempotencyStore(tmp_path / "idempotency.json"))
    return SimpleNamespace(
        client=TestClient(app), manager=manager, novels=novels, chapters=chapters,
        chapter=chapter, dispatched=dispatched,
        payload={"novel_id": novel["id"], "chapter_id": chapter["id"],
                 "instruction": "继续", "profile": "HYBRID"},
    )


def _variants(source):
    response = source.client.post("/api/generate/continue/variants", json={**source.payload, "count": 3})
    assert response.status_code == 202, response.text
    return response.json()


def _persist_status(source, job_id, status, output=""):
    """Synthetic completion, never evidence of actual model execution."""
    job = source.manager.get(job_id)
    job.status, job.output = status, output
    source.manager._persist(job)
    return job


def test_generation_is_idempotent_under_concurrent_submission(source):
    def submit(_):
        response = source.client.post("/api/generate/continue",
            headers={"Idempotency-Key": "generation-race-unique"}, json=source.payload)
        assert response.status_code == 202, response.text
        return response.json()["job_id"]

    with ThreadPoolExecutor(max_workers=3) as pool:
        ids = list(pool.map(submit, range(3)))
    assert len(set(ids)) == 1
    assert source.dispatched == [ids[0]]
    assert source.manager.persistence.get(ids[0])["chapter_id"] == source.chapter["id"]
    assert source.chapters.get(source.chapter["id"]) == source.chapter


def test_variant_generation_creates_independent_jobs(source):
    body = _variants(source)
    ids = [item["job_id"] for item in body["variants"]]
    jobs = [source.manager.get(jid) for jid in ids]
    assert body["count"] == 3 and len(set(ids)) == 3
    assert source.dispatched == ids
    assert len({job.instruction for job in jobs}) == 3
    assert {job.variant_group_id for job in jobs} == {body["group_id"]}
    assert [job.variant_index for job in jobs] == [1, 2, 3]
    assert all(job.chapter_id == source.chapter["id"] and
               job.base_chapter_version == source.chapter["version"] for job in jobs)
    assert source.chapters.get(source.chapter["id"]) == source.chapter


def test_variant_generation_limits_count(source):
    for count in (1, 4):
        response = source.client.post("/api/generate/continue/variants", json={**source.payload, "count": count})
        assert response.status_code == 422
    assert source.dispatched == []


def test_variant_lifecycle_accepts_one_and_rejects_the_rest(source):
    ids = [row["job_id"] for row in _variants(source)["variants"]]
    for index, jid in enumerate(ids, 1):
        _persist_status(source, jid, "COMPLETED", f"candidate {index}")

    accepted_response = source.client.post(f"/api/generation/{ids[1]}/accept", json={})
    assert accepted_response.status_code == 200, accepted_response.text
    accepted = accepted_response.json()
    assert accepted["chapter"]["id"] != source.chapter["id"]
    assert accepted["chapter"]["novel_id"] == source.payload["novel_id"]
    expected_content = f"# 第{source.chapter['number'] + 1}章\n\ncandidate 2"
    assert accepted["chapter"]["content"] == expected_content
    assert accepted["pending_canon"]["status"] == "PENDING"
    assert [source.manager.get(jid).status for jid in ids] == ["COMPLETED", "ACCEPTED", "COMPLETED"]
    for jid in (ids[0], ids[2]):
        response = source.client.post(f"/api/generation/{jid}/reject")
        assert response.status_code == 200, response.text
    responses = [source.client.get(f"/api/generation/{jid}") for jid in ids]
    assert all(response.status_code == 200 for response in responses)
    assert [response.json()["status"] for response in responses] == ["REJECTED", "ACCEPTED", "REJECTED"]
    assert [source.manager.persistence.get(jid)["status"] for jid in ids] == ["REJECTED", "ACCEPTED", "REJECTED"]
    assert source.chapters.get(source.chapter["id"]) == source.chapter
    chapters = source.chapters.list(source.payload["novel_id"])
    assert len(chapters) == 2
    persisted = source.chapters.get(accepted["chapter"]["id"])
    expected_document = markdown_to_document(expected_content)
    assert persisted["document"] == expected_document
    assert persisted["content"] == document_to_markdown(expected_document)


def test_failed_variant_can_be_retried_independently(source):
    ids = [row["job_id"] for row in _variants(source)["variants"]]
    failed = _persist_status(source, ids[1], "FAILED")
    response = source.client.post(f"/api/generation/{failed.id}/retry")
    assert response.status_code == 202, response.text
    body = response.json()
    retried = source.manager.get(body["job_id"])
    assert retried.id not in ids and body["retry_of"] == failed.id
    assert body["status"] == "QUEUED" and body["base_chapter_version"] == source.chapter["version"]
    assert body["events_url"] == f"/api/generation/{retried.id}/events"
    assert (retried.operation, retried.instruction, retried.novel_id, retried.chapter_id) == (
        failed.operation, failed.instruction, failed.novel_id, failed.chapter_id)
    assert [source.manager.get(jid).status for jid in ids] == ["QUEUED", "FAILED", "QUEUED"]


def test_completed_variant_cannot_be_retried(source):
    jid = _variants(source)["variants"][0]["job_id"]
    _persist_status(source, jid, "COMPLETED", "candidate")
    before = list(source.dispatched)
    response = source.client.post(f"/api/generation/{jid}/retry")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "GENERATION_NOT_RETRYABLE"
    assert source.dispatched == before


def test_variant_jobs_can_be_cancelled_independently(source):
    ids = [row["job_id"] for row in _variants(source)["variants"]]
    for jid in ids[:2]:
        _persist_status(source, jid, "GENERATING")
    first = source.client.post(f"/api/generation/{ids[0]}/cancel")
    assert first.status_code == 200 and first.json()["status"] == "CANCELLED"
    assert [source.manager.get(jid).status for jid in ids] == ["CANCELLED", "GENERATING", "QUEUED"]
    second = source.client.post(f"/api/generation/{ids[1]}/cancel")
    assert second.status_code == 200 and second.json()["status"] == "CANCELLED"
    assert source.manager.get(ids[2]).status == "QUEUED"
    assert source.chapters.get(source.chapter["id"]) == source.chapter


@pytest.mark.parametrize("invalid_source", ["missing", "other-project", "deleted"])
def test_variants_reject_invalid_source_before_dispatch(source, invalid_source):
    payload = {**source.payload, "count": 3}
    if invalid_source == "missing":
        payload["chapter_id"] = "missing:1"
    elif invalid_source == "other-project":
        payload["novel_id"] = source.novels.create({"title": "Other project"})["id"]
    else:
        source.chapters.delete(source.chapter["id"])
    response = source.client.post("/api/generate/continue/variants", json=payload)
    assert response.status_code == 404, response.text
    if invalid_source == "other-project":
        assert response.json()["detail"]["code"] == "CHAPTER_OUTSIDE_PROJECT"
    assert source.dispatched == [] and source.manager.persistence.load_all() == []
