"""Actual PostgreSQL policy revocation with a normalized recording model node.

Requires the explicit disposable TEST_POSTGRES_DATABASE_URL. The provider is an
in-process recording adapter: no network, paid API, credentials or real model.
"""
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.agents import agent_runner
from app.config import Settings
from app.model_runtime import (Modality, ModelDescriptor, ModelRegistry, ProviderDescriptor,
                               ProviderRegistry, TextGenerationResponse, TextModelNode)
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.chapter import PostgresChapterRepository
from app.repositories.postgres.generation import PostgresGenerationRepository
from app.repositories.postgres.models import CharacterModel, NovelModel
from app.repositories.postgres.novel import PostgresNovelRepository
from app.services import ContextService
from app.services.agent_context_service import AgentContextService
from app.services.agent_job_service import AgentJobService

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
pytestmark = [
    pytest.mark.postgres_backend_only,
    pytest.mark.skipif(not TEST_URL, reason="NOT_RUN: disposable TEST_POSTGRES_DATABASE_URL not configured"),
]


@pytest.fixture
def pg_dispatch():
    config = Settings(storage_backend="postgres", database_url=TEST_URL)
    bundle = create_repository_bundle(config)
    observer = create_repository_bundle(config)
    novel_id = None
    try:
        assert isinstance(bundle.novels, PostgresNovelRepository)
        assert isinstance(bundle.chapters, PostgresChapterRepository)
        assert isinstance(bundle.generations, PostgresGenerationRepository)
        assert isinstance(observer.novels, PostgresNovelRepository)
        novel_id = bundle.novels.create({"id": "r2-dispatch-pg-" + uuid4().hex, "title": "Synthetic PG dispatch"})["id"]
        bundle.chapters.create(novel_id, {"title": "Original", "content": "Synthetic manuscript"})
        yield bundle, observer, novel_id
    finally:
        try:
            if novel_id is not None:
                bundle.novels.delete(novel_id)  # Only the project created here.
        finally:
            bundle.novels.database.engine.dispose()
            observer.novels.database.engine.dispose()


@pytest.mark.parametrize("boundary", ["route_preparation", "normalized_provider_resolution"])
def test_postgres_character_policy_revocation_blocks_agent_dispatch(pg_dispatch, monkeypatch, boundary):
    bundle, observer, novel_id = pg_dispatch
    character_id = "fact-" + uuid4().hex
    fact = {"name": "PRIVATE_PG_FACT_CANARY", "privacy_level": "CLOUD_ALLOWED"}
    bundle.novels.upsert_character(novel_id, character_id, fact)

    def persisted_policy():
        with observer.novels.database.session() as session:
            row = session.scalar(select(CharacterModel).join(NovelModel, CharacterModel.novel_id == NovelModel.id)
                                 .where(NovelModel.slug == novel_id, CharacterModel.slug == character_id))
            assert row is not None and row.name == fact["name"]
            return row.privacy

    assert persisted_policy() == "CLOUD_ALLOWED"
    contexts = AgentContextService(bundle.novels, bundle.chapters, ContextService(bundle.novels, bundle.chapters))
    reviewed = contexts.build("planner", novel_id, 1, cloud=True)
    assert fact["name"] in json.dumps(reviewed["sections"])
    prompts, revocations = [], []

    class RecordingProvider:
        def generate_text(self, request):
            prompts.append(request.prompt)
            payload = {"schema": "story_plan_proposal", "agent_id": "planner", "summary": "Synthetic",
                       "proposals": [], "findings": [], "context_hash": request.context["context_hash"]}
            return TextGenerationResponse(json.dumps(payload), "completed", request.provider_id, request.model_id)

    providers, models = ProviderRegistry(), ModelRegistry()
    providers.register(ProviderDescriptor("recording-remote", "Recording adapter", "test", frozenset({Modality.TEXT}), True, True), RecordingProvider())
    models.register(ModelDescriptor("fixture", "recording-remote", "Recording model", Modality.TEXT, frozenset({"generate"})))
    node = TextModelNode(providers, models)

    def revoke():
        assert persisted_policy() == "CLOUD_ALLOWED"
        # Commit through an independent repository/connection before dispatch.
        observer.novels.upsert_character(novel_id, character_id, {**fact, "privacy_level": "LOCAL_ONLY"})
        assert persisted_policy() == "LOCAL_ONLY"
        revocations.append(True)

    def prepare(*args):
        if boundary == "route_preparation":
            revoke()
        return node

    if boundary == "normalized_provider_resolution":
        original_resolve = providers.resolve

        def resolve(provider_id):
            revoke()
            return original_resolve(provider_id)

        monkeypatch.setattr(providers, "resolve", resolve)

    runtime = SimpleNamespace(is_remote_text_provider=lambda _: True, prepare_text_route=prepare, providers={})
    service = AgentJobService(bundle.generations, contexts, bundle.novels, runtime, agent_runner)
    job = service.create("planner", novel_id, 1, provider="recording-remote", model="fixture", execution_mode="model")
    assert job["context_hash"] == reviewed["context_hash"]
    assert observer.generations.get(job["id"])["status"] == "QUEUED"
    result = service.execute(job["id"])
    assert revocations == [True]
    assert prompts == []
    assert result["status"] == "FAILED" and result["error_code"] == "AGENT_SOURCE_CHANGED"
    persisted_job = observer.generations.get(job["id"])
    assert persisted_job["status"] == "FAILED" and persisted_job["error_code"] == "AGENT_SOURCE_CHANGED"
    assert persisted_policy() == "LOCAL_ONLY"
    assert fact["name"] not in json.dumps(contexts.build("planner", novel_id, 1, cloud=True)["sections"])
