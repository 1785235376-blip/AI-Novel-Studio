"""Independent boundary checks for the PostgreSQL parity repairs."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.postgres.novel import PostgresNovelRepository


@pytest.mark.parametrize("field", ["target_words", "target_chapters"])
def test_parity_audit_negative_goal_cannot_replace_saved_goal(field):
    client = TestClient(app)
    created = client.post("/api/novels", json={"title": f"Goal audit {uuid4()}"})
    assert created.status_code == 201
    url = f"/api/novels/{created.json()['id']}/writing-goal"
    goal = {"target_words": 100, "target_chapters": 2, "deadline": "2027-01-01"}
    assert client.put(url, json=goal).status_code == 200
    before = client.get(url).json()
    rejected = client.put(url, json={**goal, field: -1})
    assert rejected.status_code == 422
    assert client.get(url).json() == before
    zero = {"target_words": 0, "target_chapters": 0, "deadline": ""}
    assert client.put(url, json=zero).status_code == 200
    persisted = client.get(url).json()
    assert {key: persisted[key] for key in zero} == zero
    assert persisted["words_progress"] == persisted["chapters_progress"] == 0


def test_parity_audit_novel_metadata_cannot_expand_authority():
    stamp = datetime.now(timezone.utc)
    goal = {"target_words": 0, "target_chapters": 0, "deadline": ""}
    record = SimpleNamespace(
        slug="authoritative-id", title="Authoritative title", created_at=stamp,
        updated_at=stamp, metadata_json={
            "id": "forged", "title": "forged", "created_at": "forged",
            "updated_at": "forged", "owner_id": "forged", "authorization": "admin",
            "privacy_level": "CLOUD_ALLOWED", "writing_goal": goal,
        },
    )
    result = PostgresNovelRepository._meta(record)
    assert result == {
        "id": "authoritative-id", "title": "Authoritative title", "genre": "",
        "status": "Writing", "created_at": stamp.isoformat(),
        "updated_at": stamp.isoformat(), "writing_goal": goal,
    }
