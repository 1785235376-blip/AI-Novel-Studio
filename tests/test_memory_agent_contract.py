from __future__ import annotations

from dataclasses import replace
import json

import pytest
from pydantic import ValidationError

from app.agents import AgentRegistry, AgentRunner
from app.config import Settings
from app.lore.memory_agent import MemoryAgentOutput, MemoryAgentRunner
from app.model_runtime import (
    GenerationRuntime, LegacyTextProviderAdapter, ModelDescriptor, ModelRegistry,
    ModelRuntimeError, Modality, ProviderDescriptor, ProviderRegistry, RuntimeErrorCode,
)
from app.providers import MockProvider, ProviderError
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, GenerationService, LoreService, NovelService
from app.storage import atomic_write
from app.jobs import Job, JobManager


class MemoryMockProvider(MockProvider):
    def __init__(self, text):
        super().__init__(delay_ms=0)
        self.text, self.calls = text, []

    def _text(self, prompt):
        self.calls.append(prompt)
        return self.text


class RecordingAdapter(LegacyTextProviderAdapter):
    def __init__(self, provider):
        super().__init__("mock", provider)
        self.requests = []

    def generate_text(self, request):
        self.requests.append(request)
        return super().generate_text(request)


class Runtime:
    """Current normalized local contract, not a bypass of the local verifier."""
    def __init__(self, text, *, provider_type="development", configured=True, provider=None):
        self.provider = provider or MemoryMockProvider(text)
        self.adapter = RecordingAdapter(self.provider)
        self.provider_registry = ProviderRegistry()
        self.model_registry = ModelRegistry()
        self.provider_registry.register(
            ProviderDescriptor("mock", "Memory contract mock", provider_type,
                frozenset({Modality.TEXT}), configured, True), self.adapter)
        # Legacy adapter supplies JSON text, not native structured-output support.
        self.model_registry.register(ModelDescriptor("memory-test", "mock", "Memory contract mock",
            Modality.TEXT, frozenset({"generate"})))
        self.generation_runtime = GenerationRuntime(self.provider_registry, self.model_registry)
        self.prepared = []

    def prepare_text_route(self, provider_id, model_id):
        self.model_registry.resolve(provider_id, model_id, Modality.TEXT)
        self.provider_registry.resolve(provider_id)
        self.prepared.append((provider_id, model_id))
        return self.generation_runtime.text_node


@pytest.fixture
def memory_settings(monkeypatch):
    import app.lore.memory_agent as memory_module
    monkeypatch.setattr(memory_module, "settings", replace(memory_module.settings,
        mock_provider=True, enable_packaged_runtime=False))
    return memory_module


def runner(tmp_path, output, *, runtime=None):
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path), tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    nid = novels.create({"id": "agent-test", "title": "Agent"})["id"]
    chapter = chapters.create(nid, {"title": "One", "content": "Lin learned the harbor secret."})
    current = chapters.get(chapter["id"])
    saved = chapters.save(chapter["id"], {"content": "Lin learned the harbor secret.",
        "version": current["version"], "source": "AI_ACCEPT"})
    atomic_write(tmp_path / "novels" / nid / "characters" / "characters.json",
        json.dumps([{"id": "lin", "name": "Lin"}]))
    agent = MemoryAgentRunner(bundle.novels, bundle.chapters, LoreService(bundle.lore),
        GenerationService(bundle.generations), AgentRunner(AgentRegistry()),
        runtime or Runtime(json.dumps(output)))
    return agent, bundle, nid, chapter["id"], saved["version"]


def valid_output():
    return {"proposals": [{"proposal_type": "CHARACTER_MEMORY",
        "payload": {"character_id": "lin", "memory_type": "KNOWLEDGE_CHANGE", "content": {"fact": "harbor secret"}},
        "confidence": 0.9, "evidence": [{"chapter_id": "agent-test:1", "chapter_version": 2,
            "excerpt": "Lin learned the harbor secret.", "locator": {"kind": "DOCUMENT_RANGE", "from": 1, "to": 31}}]}]}


def test_json_output_and_evidence_contract():
    assert MemoryAgentOutput.model_validate(valid_output()).proposals[0].confidence == 0.9
    with pytest.raises(ValidationError):
        MemoryAgentOutput.model_validate({"proposals": [{"proposal_type": "EVENT", "payload": {}, "confidence": .5, "evidence": []}]})
    with pytest.raises(ValidationError):
        MemoryAgentOutput.model_validate({"proposals": [{"proposal_type": "CANON_SUGGESTION", "payload": {}, "confidence": .5,
            "evidence": [{"chapter_id": "n:1", "chapter_version": 1, "excerpt": "x", "locator": {"kind": "DOCUMENT_RANGE"}}]}]})


@pytest.mark.file_backend_only
def test_extract_creates_pending_proposal_with_evidence_and_is_idempotent(tmp_path, memory_settings):
    agent, bundle, nid, cid, version = runner(tmp_path, valid_output())
    first = agent.extract(nid, cid, version, profile="HYBRID", job_id="memory-job-1")
    second = agent.extract(nid, cid, version, job_id="memory-job-2")
    assert first == second and len(bundle.lore.list_proposals(nid)) == 1
    proposal = bundle.lore.get_proposal(first[0])
    relations = bundle.lore.list_proposal_evidence(first[0])
    assert proposal["status"] == "PENDING" and len(relations) == 1
    evidence = bundle.lore.get_evidence(relations[0]["evidence_id"])
    assert (evidence["chapter_id"], evidence["chapter_version"], evidence["excerpt"], evidence["privacy"]) == (
        cid, version, "Lin learned the harbor secret.", "LOCAL_ONLY")
    assert len(bundle.lore.list_evidence(nid)) == 1 and bundle.lore.list_memories(nid) == []
    assert agent.runtime.prepared == [("mock", "memory-test")] * 2
    assert len(agent.runtime.adapter.requests) == len(agent.runtime.provider.calls) == 2
    for request in agent.runtime.adapter.requests:
        assert request.metadata == {"purpose": "memory_extraction", "privacy_level": "LOCAL_ONLY"}
        assert request.dispatch_guard is not None and request.structured_output_schema is None
        assert cid in request.prompt and "harbor secret" in request.prompt
    for jid in ("memory-job-1", "memory-job-2"):
        record = bundle.generations.get(jid)
        assert record["status"] == "COMPLETED" and record["execution_mode"] == "mock_standin"
        assert record["provider"] == "mock" and record["request"]["profile"] == "LOCAL_ONLY"


@pytest.mark.file_backend_only
def test_invalid_json_marks_independent_job_failed(tmp_path, memory_settings):
    agent, bundle, nid, cid, version = runner(tmp_path, {"wrong": []})
    with pytest.raises(ValidationError):
        agent.extract(nid, cid, version, job_id="memory-failed")
    record = bundle.generations.get("memory-failed")
    assert record["status"] == "FAILED" and record["error_code"] == "MEMORY_EXTRACTION_FAILED"
    assert len(agent.runtime.provider.calls) == 1
    assert bundle.lore.list_proposals(nid) == bundle.lore.list_evidence(nid) == bundle.lore.list_memories(nid) == []


class UnverifiedProvider:
    name = "not-a-verified-local-provider"
    def __init__(self): self.calls = []
    def generate(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("Unverified provider must not execute")


@pytest.mark.parametrize("mode", ["unconfigured", "remote", "unverified-local", "mock-disabled", "packaged"])
def test_memory_extraction_rejects_unverified_routes_without_egress(tmp_path, memory_settings, monkeypatch, mode):
    runtime = Runtime(json.dumps(valid_output()),
        configured=mode != "unconfigured",
        provider_type={"remote": "remote", "unverified-local": "local"}.get(mode, "development"),
        provider=UnverifiedProvider() if mode == "unverified-local" else None)
    if mode in {"mock-disabled", "packaged"}:
        monkeypatch.setattr(memory_settings, "settings", replace(memory_settings.settings,
            mock_provider=mode != "mock-disabled", enable_packaged_runtime=mode == "packaged"))
    agent, bundle, nid, cid, version = runner(tmp_path, valid_output(), runtime=runtime)
    with pytest.raises(ModelRuntimeError, match="^MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED$") as caught:
        agent.extract(nid, cid, version, profile="HYBRID", job_id="memory-refused")
    assert caught.value.code is RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED
    assert runtime.prepared == runtime.adapter.requests == runtime.provider.calls == []
    record = bundle.generations.get("memory-refused")
    assert record["status"] == "NOT_CONFIGURED" and record["request"]["profile"] == "LOCAL_ONLY"
    assert bundle.lore.list_proposals(nid) == bundle.lore.list_evidence(nid) == bundle.lore.list_memories(nid) == []


def test_memory_failure_does_not_fall_back_to_remote_provider(tmp_path, memory_settings):
    class FailingMock(MemoryMockProvider):
        def _text(self, prompt):
            self.calls.append(prompt)
            raise ProviderError("synthetic local failure")

    runtime = Runtime("", provider=FailingMock(""))
    remote = UnverifiedProvider()
    runtime.provider_registry.register(ProviderDescriptor("remote", "Forbidden remote", "remote",
        frozenset({Modality.TEXT}), True, True), LegacyTextProviderAdapter("remote", remote))
    runtime.model_registry.register(ModelDescriptor("remote-model", "remote", "Remote",
        Modality.TEXT, frozenset({"generate"})))
    agent, bundle, nid, cid, version = runner(tmp_path, valid_output(), runtime=runtime)
    with pytest.raises(ModelRuntimeError) as caught:
        agent.extract(nid, cid, version, profile="HYBRID", job_id="memory-failure")
    assert caught.value.code is RuntimeErrorCode.PROVIDER_UNAVAILABLE
    assert len(runtime.provider.calls) == 1 and remote.calls == []
    assert bundle.generations.get("memory-failure")["status"] == "FAILED"
    assert bundle.lore.list_proposals(nid) == bundle.lore.list_evidence(nid) == []


def test_memory_dispatch_revalidates_selected_adapter(tmp_path, memory_settings, monkeypatch):
    runtime = Runtime(json.dumps(valid_output()))
    replacement = MemoryMockProvider(json.dumps(valid_output()))
    original_prepare = runtime.prepare_text_route

    def replace_after_selection(provider_id, model_id):
        node = original_prepare(provider_id, model_id)
        runtime.provider_registry.register(runtime.provider_registry.descriptors()[0],
            LegacyTextProviderAdapter("mock", replacement), replace=True)
        return node

    monkeypatch.setattr(runtime, "prepare_text_route", replace_after_selection)
    agent, bundle, nid, cid, version = runner(tmp_path, valid_output(), runtime=runtime)
    with pytest.raises(ModelRuntimeError) as caught:
        agent.extract(nid, cid, version, job_id="memory-changed")
    assert caught.value.code is RuntimeErrorCode.INVALID_CONFIGURATION
    assert runtime.provider.calls == replacement.calls == []
    assert bundle.generations.get("memory-changed")["status"] == "FAILED"
    assert bundle.lore.list_proposals(nid) == bundle.lore.list_evidence(nid) == []


def test_accept_survives_memory_enqueue_failure():
 class Store:
  def __init__(self):self.items={}
  def save(self,x):self.items[x["id"]]=x
  def load_all(self):return []
 class Chapters:
  def __init__(self):self.item={"id":"n:1","novel_id":"n","number":1,"content":"old","version":1}
  def get(self,c):return dict(self.item)
  def save(self,c,p):self.item.update(content=p["content"],version=self.item["version"]+1);return dict(self.item)
  def save_summary(self,*a):pass
 class Canon:
  def save_pending(self,x):return x
 class Failing:
  def enqueue(self,*a):raise RuntimeError("agent unavailable")
 store=Store();chapters=Chapters();manager=JobManager(generations=store,chapters=chapters,contexts=object(),canon=Canon(),memory_extractor=Failing());job=Job("j","continue","n","n:1","","LOCAL_ONLY",status="COMPLETED",output="new");manager.jobs[job.id]=job
 result=manager.accept(job.id);assert result["chapter"]["content"]=="old\n\nnew" and job.status=="ACCEPTED"
