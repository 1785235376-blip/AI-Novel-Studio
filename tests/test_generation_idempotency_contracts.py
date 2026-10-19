from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Thread

import pytest
import hashlib
import json
from fastapi.testclient import TestClient

from app.idempotency import IdempotencyStore
from app.main import app

PAYLOAD = {"novel_id": "n", "chapter_id": "c", "instruction": "继续"}
CACHED = {
    "job_id": "cached-job",
    "status": "QUEUED",
    "events_url": "/api/generation/cached-job/events",
    "base_chapter_version": 1,
}


class _Item:
    def __init__(self, jid):
        self.id = jid
        self.status = "QUEUED"
        self.base_chapter_version = 1


@pytest.fixture
def isolated_generation_idempotency_store(tmp_path, monkeypatch):
    """Run-scoped store. Does not read or write repository novel_data."""
    import app.api as api

    store = IdempotencyStore(tmp_path / "idempotency.json")
    monkeypatch.setattr(api, "_idempotency_store", store)
    return store


@pytest.fixture(autouse=True)
def synthetic_chapter_authority(monkeypatch):
    # These tests replace the executor; its synthetic chapter must now also be
    # present at the mandatory pre-idempotency ownership check.
    import app.api as api
    monkeypatch.setattr(api.chapter_service, "get", lambda cid: {"id": cid, "novel_id": "n", "version": 1})


def scoped_cache_key(operation, key):
    authority = ["n", "c", "local-author", "local", None]
    return "generate:" + operation + ":" + hashlib.sha256(json.dumps(authority).encode()).hexdigest() + ":" + key


def cached_envelope():
    from app.api import GenerateIn
    payload = GenerateIn(**PAYLOAD).model_dump(exclude={"count"})
    return {"request_digest": hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), "result": CACHED}


def test_generation_replay_returns_cached_result_without_creating(monkeypatch, isolated_generation_idempotency_store):
    from app.api import jobs

    isolated_generation_idempotency_store.put(scoped_cache_key("continue", "replay-key"), cached_envelope())
    created = []

    def create(*args, **kwargs):
        created.append(1)
        return _Item("should-not-create")

    monkeypatch.setattr(jobs, "create", create)
    response = TestClient(app).post(
        "/api/generate/continue",
        headers={"Idempotency-Key": "replay-key"},
        json=PAYLOAD,
    )
    assert response.status_code == 202
    assert response.json() == CACHED
    assert created == []


def test_generation_replay_contract_is_stable_across_repeats(monkeypatch, isolated_generation_idempotency_store):
    from app.api import jobs

    isolated_generation_idempotency_store.put(scoped_cache_key("continue", "replay-stable"), cached_envelope())
    created = []

    def create(*args, **kwargs):
        created.append(1)
        return _Item("should-not-create")

    monkeypatch.setattr(jobs, "create", create)
    client = TestClient(app)
    for _ in range(20):
        response = client.post(
            "/api/generate/continue",
            headers={"Idempotency-Key": "replay-stable"},
            json=PAYLOAD,
        )
        assert response.status_code == 202
        assert response.json() == CACHED
    assert created == []


def test_generation_without_idempotency_key_creates_independently(monkeypatch, isolated_generation_idempotency_store):
    from app.api import jobs

    created = []

    def create(*args, **kwargs):
        created.append(1)
        return _Item(f"job-{len(created)}")

    monkeypatch.setattr(jobs, "create", create)
    client = TestClient(app)
    first = client.post("/api/generate/continue", json=PAYLOAD)
    second = client.post("/api/generate/continue", json=PAYLOAD)
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(created) == 2


def test_generation_distinct_keys_create_once_each(monkeypatch, isolated_generation_idempotency_store):
    from app.api import jobs

    created = []

    def create(*args, **kwargs):
        created.append(1)
        return _Item(f"job-{len(created)}")

    monkeypatch.setattr(jobs, "create", create)
    client = TestClient(app)
    first = client.post("/api/generate/continue", headers={"Idempotency-Key": "k1"}, json=PAYLOAD)
    second = client.post("/api/generate/continue", headers={"Idempotency-Key": "k2"}, json=PAYLOAD)
    assert first.json()["job_id"] == "job-1"
    assert second.json()["job_id"] == "job-2"
    assert len(created) == 2


def test_generation_idempotency_is_namespaced_by_operation(monkeypatch, isolated_generation_idempotency_store):
    from app.api import jobs

    created = []

    def create(*args, **kwargs):
        created.append(1)
        return _Item(f"job-{len(created)}")

    monkeypatch.setattr(jobs, "create", create)
    client = TestClient(app)
    first = client.post("/api/generate/continue", headers={"Idempotency-Key": "same"}, json=PAYLOAD)
    second = client.post("/api/generate/rewrite", headers={"Idempotency-Key": "same"}, json=PAYLOAD)
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(created) == 2


def test_generation_create_failure_is_not_cached_and_releases_lock(monkeypatch, isolated_generation_idempotency_store):
    from app.api import jobs

    calls = {"n": 0}

    def create(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return _Item("after-error")

    monkeypatch.setattr(jobs, "create", create)
    client = TestClient(app, raise_server_exceptions=False)
    first = client.post("/api/generate/continue", headers={"Idempotency-Key": "err-key"}, json=PAYLOAD)
    assert first.status_code == 500
    assert isolated_generation_idempotency_store.get(scoped_cache_key("continue", "err-key")) is None
    box = {}

    def retry():
        box["response"] = client.post(
            "/api/generate/continue",
            headers={"Idempotency-Key": "err-key"},
            json=PAYLOAD,
        )

    worker = Thread(target=retry)
    worker.start()
    worker.join(5)
    assert worker.is_alive() is False
    second = box["response"]
    assert second.status_code == 202
    assert second.json()["job_id"] == "after-error"
    assert calls["n"] == 2


def test_generation_fresh_store_concurrent_submission_survives_repeated_races(monkeypatch, tmp_path):
    import time

    import app.api as api
    from app.api import jobs

    for round_id in range(100):
        store = IdempotencyStore(tmp_path / f"round-{round_id}.json")
        monkeypatch.setattr(api, "_idempotency_store", store)
        created = []
        start = Barrier(3)

        def create(*args, **kwargs):
            time.sleep(0.005)
            created.append(1)
            return _Item("one-job")

        monkeypatch.setattr(jobs, "create", create)
        headers = {"Idempotency-Key": f"fresh-{round_id}"}

        def submit(_):
            start.wait(timeout=5)
            return TestClient(app).post("/api/generate/continue", headers=headers, json=PAYLOAD).json()

        with ThreadPoolExecutor(max_workers=3) as pool:
            bodies = list(pool.map(submit, range(3)))
        assert [body["job_id"] for body in bodies] == ["one-job"] * 3
        assert all(body == bodies[0] for body in bodies)
        assert len(created) == 1
