from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.actor_context import ActorContext, SessionContext
from app.collaboration_api import CollaborationReadService, create_collaboration_router
from app.model_runtime import ModelDescriptor, ModelRegistry, Modality, ProviderDescriptor, ProviderRegistry
from app.visual_workflow import WORKFLOW_CONTRACT_VERSION, VisualTextWorkflowAdapter


class Provider:
    provider_id = "deepseek"
    calls = 0
    def generate_text(self, request): self.calls += 1; raise AssertionError("read-only composition executed provider")
    def stream_text(self, request): self.calls += 1; raise AssertionError("read-only composition streamed provider")


def adapter():
    providers, models = ProviderRegistry(), ModelRegistry()
    providers.register(ProviderDescriptor("deepseek", "DeepSeek", "remote", frozenset({Modality.TEXT}), True, True), Provider())
    models.register(ModelDescriptor("deepseek-chat", "deepseek", "DeepSeek Chat", Modality.TEXT, frozenset({"stream", "generate"}), streaming=True))
    return VisualTextWorkflowAdapter(providers, models)


def test_contract_is_versioned_deterministic_identity_preserving_and_secret_safe():
    value = adapter()
    first = value.compose("deepseek", "deepseek-chat")
    second = value.compose("deepseek", "deepseek-chat")
    assert first == second
    assert first.workflow_contract_version == WORKFLOW_CONTRACT_VERSION
    assert first.read_only is True
    assert [node.kind for node in first.nodes] == ["context", "text_model", "stream", "draft", "accept", "revision"]
    assert [node.production_boundary for node in first.nodes] == [
        "context.privacy_filter", "runtime.text_model_node", "runtime.generation_events",
        "generation.draft_diff", "generation.explicit_accept", "revision.immutable_append",
    ]
    model = first.nodes[1]
    assert (model.provider_id, model.model_id) == ("deepseek", "deepseek-chat")
    assert first.edges[0].target == model.stable_id == first.edges[1].source
    assert len(first.edges) == len(first.nodes) - 1
    serialized = first.model_dump_json()
    for forbidden in ("api_key", "authorization", "credential", "prompt", "ActorContext"):
        assert forbidden.casefold() not in serialized.casefold()


def test_unknown_model_fails_without_provider_execution():
    import pytest
    with pytest.raises(Exception) as failure:
        adapter().compose("deepseek", "unknown")
    assert "未找到指定模型" in str(failure.value)


def test_non_streaming_model_fails_safely_without_execution():
    import pytest
    providers, models = ProviderRegistry(), ModelRegistry(); provider = Provider()
    providers.register(ProviderDescriptor("deepseek", "DeepSeek", "remote", frozenset({Modality.TEXT}), True, True), provider)
    models.register(ModelDescriptor("batch-only", "deepseek", "Batch", Modality.TEXT, frozenset({"generate"}), streaming=False))
    with pytest.raises(Exception) as failure:
        VisualTextWorkflowAdapter(providers, models).compose("deepseek", "batch-only")
    assert "不支持流式文本生成" in str(failure.value) and provider.calls == 0


class Sessions:
    def resolve(self, token):
        if token != "trusted": raise KeyError(token)
        return ActorContext("author", "workspace-a", SessionContext("session", "client", "author", "workspace-a"))


class Membership:
    def require(self, actor, permission, domain, scope):
        if scope.workspace_id != actor.workspace_id: raise PermissionError("outside workspace")
    def is_allowed(self, actor, permission, domain, scope): return True


class Scopes:
    def validate_scope(self, scope): return scope


class ExplodingDependency:
    def __init__(self, name): self.name, self.calls = name, 0
    def __getattr__(self, key): self.calls += 1; raise AssertionError(f"{self.name} side effect: {key}")


def client(*, workflow_adapter=None):
    dependencies = {name: ExplodingDependency(name) for name in ("chapters", "generations", "lore")}
    service = CollaborationReadService(
        sessions=Sessions(), membership_authorization=Membership(), identity=SimpleNamespace(repository=SimpleNamespace()),
        authorization=SimpleNamespace(), scopes=Scopes(), chapters=dependencies["chapters"], generations=dependencies["generations"],
        lore_repository=dependencies["lore"], visual_workflows=workflow_adapter or adapter(),
    )
    app = FastAPI(); app.include_router(create_collaboration_router(service)); return TestClient(app), dependencies


BASE = "/api/collaboration/workspaces/workspace-a/projects/project/storylines/story/branches/branch/visual-text-workflow"


def test_trusted_read_api_is_workspace_isolated_and_has_no_mutation_routes():
    api, _ = client()
    response = api.get(BASE, headers={"X-Session-Token": "trusted"}, params={"provider_id": "deepseek", "model_id": "deepseek-chat"})
    assert response.status_code == 200
    assert response.json()["workflow_contract_version"] == WORKFLOW_CONTRACT_VERSION
    assert api.get(BASE, params={"provider_id": "deepseek", "model_id": "deepseek-chat"}).status_code == 401
    outside = BASE.replace("workspace-a", "workspace-b")
    assert api.get(outside, headers={"X-Session-Token": "trusted"}, params={"provider_id": "deepseek", "model_id": "deepseek-chat"}).status_code == 403
    assert api.post(BASE, headers={"X-Session-Token": "trusted"}).status_code == 405


def test_workflow_read_has_zero_generation_manuscript_revision_or_snapshot_side_effects():
    value = adapter(); provider = value.provider_registry.resolve("deepseek")
    api, dependencies = client(workflow_adapter=value)
    response = api.get(BASE, headers={"X-Session-Token": "trusted"}, params={"provider_id": "deepseek", "model_id": "deepseek-chat"})
    assert response.status_code == 200
    assert provider.calls == 0
    assert {name: dependency.calls for name, dependency in dependencies.items()} == {"chapters": 0, "generations": 0, "lore": 0}


def test_sensitive_registry_metadata_is_redacted_from_dto_and_api():
    sentinel = "sk-SENTINEL_NEVER_SERIALIZE"
    providers, models = ProviderRegistry(), ModelRegistry(); provider = Provider()
    providers.register(ProviderDescriptor("deepseek", "DeepSeek", "remote", frozenset({Modality.TEXT}), True, True), provider)
    models.register(ModelDescriptor("deepseek-chat", "deepseek", f"Authorization Bearer {sentinel}", Modality.TEXT, frozenset({"stream", sentinel}), streaming=True))
    value = VisualTextWorkflowAdapter(providers, models)
    dto = value.compose("deepseek", "deepseek-chat").model_dump_json()
    api, _ = client(workflow_adapter=value)
    response = api.get(BASE, headers={"X-Session-Token": "trusted"}, params={"provider_id": "deepseek", "model_id": "deepseek-chat"})
    assert response.status_code == 200
    assert sentinel not in dto and sentinel not in response.text
    assert response.json()["nodes"][1]["label"] == "文本模型"
