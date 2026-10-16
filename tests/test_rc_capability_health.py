from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.asset_providers import DEFAULT_IMAGE_ENDPOINTS
from app.credential_vault import CredentialVault, MemoryBackend, VaultUnavailableError
from app.provider_support import ProviderSupportRegistry


class RecordingBackend(MemoryBackend):
    def __init__(self):
        super().__init__()
        self.resolved = []
        self.fail_resolve = False

    def resolve(self, provider):
        self.resolved.append(provider)
        if self.fail_resolve:
            raise VaultUnavailableError("TEST_RESOLVE_FAILED")
        return super().resolve(provider)


@pytest.fixture
def health_client(monkeypatch):
    api = importlib.import_module("app.api")
    registry = ProviderSupportRegistry()
    backend = RecordingBackend()
    vault = CredentialVault(
        backend_impl=backend, allow_memory_fallback=False,
        supports_provider=registry.supports_provider,
    )
    monkeypatch.setattr(api, "credential_vault", vault)
    application = FastAPI()
    application.include_router(api.router, prefix="/api")
    return TestClient(application, raise_server_exceptions=False), registry, vault, backend


def assert_health_contract(response):
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "image_providers", "vision_providers", "vision_credentials",
        "speech_credentials", "video_provider_configs", "media_validation",
    }
    assert payload["vision_providers"] == [
        {"id": provider, "configured": item["configured"]}
        for provider, item in zip(
            (pid for pid in DEFAULT_IMAGE_ENDPOINTS if pid != "custom"),
            payload["vision_providers"], strict=True,
        )
    ]
    assert all(type(item["configured"]) is bool for item in payload["vision_providers"])
    assert set(payload["media_validation"]) == {
        "pcm_wav", "ffmpeg", "ffprobe", "image_video_ingestion",
        "video_assembly_profile", "codec_binaries_bundled",
    }
    return payload


def test_fresh_original_catalog_health_without_local_credential_access(health_client):
    client, registry, _vault, backend = health_client
    assert {"comfyui", "automatic1111"} <= DEFAULT_IMAGE_ENDPOINTS.keys()
    assert not registry.supports_provider("comfyui")
    assert not registry.supports_provider("automatic1111")

    payload = assert_health_contract(client.get("/api/multimodal/health"))

    assert not any(item["configured"] for item in payload["vision_providers"])
    assert payload["vision_credentials"] is False
    assert payload["speech_credentials"] is False
    assert backend.resolved == [
        pid for pid, endpoint in DEFAULT_IMAGE_ENDPOINTS.items()
        if pid != "custom" and endpoint and registry.supports_provider(pid)
    ]
    assert "comfyui" not in backend.resolved and "automatic1111" not in backend.resolved


@pytest.mark.parametrize("configured", [False, True])
def test_supported_remote_credential_status_stays_accurate_and_secret_free(
    health_client, caplog, configured,
):
    client, _registry, vault, backend = health_client
    secret = "TEST_ONLY_HEALTH_SECRET_MUST_NOT_BE_EXPOSED"
    if configured:
        vault.set("openai", secret)
    backend.resolved.clear()

    response = client.get("/api/multimodal/health")
    payload = assert_health_contract(response)

    statuses = {item["id"]: item["configured"] for item in payload["vision_providers"]}
    assert statuses["openai"] is configured
    assert all(not value for pid, value in statuses.items() if pid != "openai")
    assert payload["vision_credentials"] is configured
    assert payload["speech_credentials"] is configured
    assert "openai" in backend.resolved
    assert secret not in response.text and secret not in caplog.text


def test_supported_vault_failure_is_not_reported_as_unconfigured(health_client):
    client, _registry, _vault, backend = health_client
    backend.fail_resolve = True

    response = client.get("/api/multimodal/health")

    assert response.status_code == 500
    assert backend.resolved == ["ddshub"]
    assert "configured" not in response.text
