from __future__ import annotations

import pytest

from app import jobs as jobs_module
from app.jobs import Job, JobManager
from app.model_runtime import GenerationEvent, TextGenerationResponse
from app.router import ModelRouter, Route
from app.runtime import Runtime


class MemoryGenerations:
    def __init__(self): self.values = {}
    def load_all(self): return []
    def save(self, value): self.values[value["id"]] = value


class Chapters:
    def get(self, _chapter_id): return {"content": "chapter", "number": 1, "version": 2}


class Contexts:
    def __init__(self): self.cloud = None
    def for_chapter(self, *_args): self.cloud = _args[2]; return {"chapter": "context"}
    def save_snapshot(self, *_args, **_kwargs): return None


class Node:
    def stream(self, value):
        request = value.request
        yield GenerationEvent("generation.delta", request.job_id, delta="draft")
        yield GenerationEvent("generation.completed", request.job_id, response=TextGenerationResponse("draft", "stop", request.provider_id, request.model_id))


def manager():
    return JobManager(generations=MemoryGenerations(), chapters=Chapters(), contexts=Contexts(), canon=object(), memory_extractor=object(), snapshot_required=False, collaboration_updates=object())


def test_text_model_catalog_comes_from_registry_without_credentials():
    items = Runtime().text_models()
    assert {item["model_id"] for item in items} >= {"deepseek-chat", "deepseek-reasoner"}
    assert all(set(item) == {"provider_id", "model_id", "display_name", "available"} for item in items)
    assert "api_key" not in repr(items).casefold() and "authorization" not in repr(items).casefold()


def test_generation_selection_must_be_provider_model_pair(monkeypatch):
    value = manager()
    monkeypatch.setattr(value, "_run", lambda _job: None)
    with pytest.raises(ValueError, match="selected together"):
        value.create("continue", {"novel_id": "n", "chapter_id": "c", "provider_id": "deepseek"})


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ({}, ("mock", "mock-writer")),
        ({"provider_id": "deepseek", "model_id": "deepseek-chat"}, ("deepseek", "deepseek-chat")),
    ],
)
def test_explicit_model_selection_reaches_provider_neutral_runtime_without_fallback(monkeypatch, selection, expected):
    captured = []
    monkeypatch.setattr(jobs_module.agent_runner, "build_prompt", lambda *_args: "prompt")
    monkeypatch.setattr(jobs_module, "deterministic_review", lambda *_args: [])
    monkeypatch.setattr(jobs_module.runtime, "router", lambda _profile, role: ModelRouter({}, {role: [Route("mock", "mock-writer")] }))
    monkeypatch.setattr(jobs_module.runtime, "is_remote_text_provider", lambda provider: provider == "deepseek")
    monkeypatch.setattr(jobs_module.runtime, "prepare_text_route", lambda provider, model, _provider=None: captured.append((provider, model)) or Node())
    value = manager()
    job = Job("job", "continue", "n", "c", "", "LOCAL_ONLY", requested_provider=selection.get("provider_id"), requested_model=selection.get("model_id"))
    value._run(job)
    assert job.status == "COMPLETED"
    assert captured == [expected]
    assert (job.provider, job.model) == expected
    assert value.contexts.cloud is bool(selection)
