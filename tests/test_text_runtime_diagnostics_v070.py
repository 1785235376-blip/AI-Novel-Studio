from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.actor_context import ActorContext, SessionContext
from app.collaboration_api import CollaborationReadService, create_collaboration_router
from app.model_runtime import ModelDescriptor, ModelRegistry, Modality, ProviderDescriptor, ProviderRegistry
from app.runtime_diagnostics import (
    DIAGNOSTICS_CONTRACT_VERSION,
    TextRuntimeDiagnosticsAdapter,
    TextRuntimeState,
)
from app.visual_workflow import WORKFLOW_CONTRACT_VERSION


class ProviderSpy:
    provider_id = "deepseek"

    def __init__(self):
        self.calls = 0

    def generate_text(self, request):
        self.calls += 1
        raise AssertionError("diagnostics executed provider")

    def stream_text(self, request):
        self.calls += 1
        raise AssertionError("diagnostics streamed provider")


def adapter(*, configured=True, available=True, enabled=True, streaming=True, capabilities=frozenset({"generate", "stream"}), modality=Modality.TEXT):
    providers, models, provider = ProviderRegistry(), ModelRegistry(), ProviderSpy()
    providers.register(ProviderDescriptor(
        "deepseek", "DeepSeek", "remote", frozenset({Modality.TEXT}), configured, available,
        "available" if available else "unavailable",
    ), provider)
    models.register(ModelDescriptor(
        "deepseek-chat", "deepseek", "DeepSeek Chat", modality, capabilities,
        streaming=streaming, enabled=enabled,
    ))
    return TextRuntimeDiagnosticsAdapter(providers, models), provider


@pytest.mark.parametrize(("options", "expected"), [
    ({}, TextRuntimeState.READY),
    ({"configured": False, "available": False}, TextRuntimeState.NOT_CONFIGURED),
    ({"available": False}, TextRuntimeState.UNAVAILABLE),
    ({"enabled": False}, TextRuntimeState.MODEL_DISABLED),
    ({"streaming": False, "capabilities": frozenset({"generate"})}, TextRuntimeState.STREAMING_UNSUPPORTED),
])
def test_registry_only_diagnostics_cover_normalized_states_without_provider_calls(options, expected):
    target, provider = adapter(**options)
    result = target.diagnose("deepseek", "deepseek-chat")
    assert result.diagnostics_contract_version == DIAGNOSTICS_CONTRACT_VERSION
    assert result.read_only is True
    assert result.state is expected
    assert (result.provider_id, result.model_id) == ("deepseek", "deepseek-chat")
    assert result.state_label and result.explanation and result.author_action
    assert provider.calls == 0
    assert WORKFLOW_CONTRACT_VERSION == "visual-text-workflow/v2"


def test_unknown_route_fails_without_fallback_or_provider_calls():
    target, provider = adapter()
    with pytest.raises(Exception, match="未找到指定模型"):
        target.diagnose("deepseek", "unknown")
    assert provider.calls == 0


def test_non_text_model_is_rejected_without_fallback_or_provider_calls():
    target, provider = adapter(modality=Modality.IMAGE)
    with pytest.raises(Exception, match="不是文本模型"):
        target.diagnose("deepseek", "deepseek-chat")
    assert provider.calls == 0


class Sessions:
    def resolve(self, token):
        if token != "trusted":
            raise KeyError(token)
        return ActorContext("author", "workspace-a", SessionContext("session", "client", "author", "workspace-a"))


class Membership:
    def require(self, actor, permission, domain, scope):
        if scope.workspace_id != actor.workspace_id:
            raise PermissionError("outside workspace")

    def is_allowed(self, actor, permission, domain, scope):
        return True


class Scopes:
    def validate_scope(self, scope):
        return scope


class ExplodingDependency:
    def __init__(self, name):
        self.name, self.calls = name, 0

    def __getattr__(self, key):
        self.calls += 1
        raise AssertionError(f"{self.name} side effect: {key}")


def client(target=None):
    dependencies = {name: ExplodingDependency(name) for name in ("chapters", "generations", "lore", "novels")}
    service = CollaborationReadService(
        sessions=Sessions(), membership_authorization=Membership(), identity=SimpleNamespace(repository=SimpleNamespace()),
        authorization=SimpleNamespace(), scopes=Scopes(), chapters=dependencies["chapters"],
        generations=dependencies["generations"], lore_repository=dependencies["lore"], novels=dependencies["novels"],
        runtime_diagnostics=target or adapter()[0],
    )
    app = FastAPI()
    app.include_router(create_collaboration_router(service))
    return TestClient(app), dependencies


BASE = "/api/collaboration/workspaces/workspace-a/projects/project/storylines/story/branches/branch/text-runtime-diagnostics"
PARAMS = {"provider_id": "deepseek", "model_id": "deepseek-chat"}


def test_diagnostics_api_preserves_trusted_authorization_workspace_isolation_and_read_only_boundary():
    api, _ = client()
    assert api.get(BASE, headers={"X-Session-Token": "trusted"}, params=PARAMS).status_code == 200
    assert api.get(BASE, params=PARAMS).status_code == 401
    assert api.get(BASE.replace("workspace-a", "workspace-b"), headers={"X-Session-Token": "trusted"}, params=PARAMS).status_code == 403
    assert api.post(BASE, headers={"X-Session-Token": "trusted"}).status_code == 405


def test_api_read_has_zero_provider_generation_context_persistence_manuscript_or_revision_side_effects():
    target, provider = adapter()
    api, dependencies = client(target)
    response = api.get(BASE, headers={"X-Session-Token": "trusted"}, params=PARAMS)
    assert response.status_code == 200
    assert response.json()["state"] == "READY"
    assert provider.calls == 0
    assert {name: value.calls for name, value in dependencies.items()} == {
        "chapters": 0, "generations": 0, "lore": 0, "novels": 0,
    }


def test_api_rejects_non_text_route_without_provider_or_repository_access():
    target, provider = adapter(modality=Modality.IMAGE)
    api, dependencies = client(target)
    response = api.get(BASE, headers={"X-Session-Token": "trusted"}, params=PARAMS)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "CAPABILITY_NOT_SUPPORTED"
    assert provider.calls == 0
    assert all(value.calls == 0 for value in dependencies.values())


def test_contract_allowlists_capabilities_and_never_serializes_secret_or_prompt_metadata():
    sentinel = "sk-SENTINEL_NEVER_SERIALIZE"
    target, _ = adapter(capabilities=frozenset({"generate", "stream", sentinel, "authorization"}))
    serialized = target.diagnose("deepseek", "deepseek-chat").model_dump_json()
    assert sentinel not in serialized
    assert "authorization" not in serialized.casefold()
    assert "prompt" not in serialized.casefold()
    assert "credential" not in serialized.casefold()
