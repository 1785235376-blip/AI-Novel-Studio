"""Reuse unchanged V2 HTTP scenarios with genuine PostgreSQL persistence."""
import pytest
from creative_director_postgres_fixture_additive import pg_lifecycle
from test_director_postgres_pending_additive import restart
from app.experimental.store import canonical
import test_v2_screenplay_model_transport as original
pytestmark=pytest.mark.postgres_backend_only


def test_original_versioned_screenplay_http_flow_with_postgres(pg_lifecycle,monkeypatch):
    # Equivalent persisted-content assertion for JSONB, not a fabricated view.
    monkeypatch.setattr(original,'raw_bytes',lambda e:canonical(e.raw.read(e.nid,e.scope)).encode())
    monkeypatch.setattr(original,'restart',restart)
    original.test_versioned_http_screenplay_review_and_reopen(pg_lifecycle)


def test_original_versioned_screenplay_source_and_host_denials_with_postgres(pg_lifecycle,monkeypatch):
    monkeypatch.setattr(original,'raw_bytes',lambda e:canonical(e.raw.read(e.nid,e.scope)).encode())
    original.test_v2_rejects_storyboard_and_missing_host_before_mutation(pg_lifecycle)
