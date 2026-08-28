from __future__ import annotations

import importlib
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.credential_vault import CredentialVault, MemoryBackend, VaultUnavailableError
from app.provider_support import ProviderSupportRegistry


class SpyBackend(MemoryBackend):
    name="keyring"
    persistent=True
    def __init__(self):
        super().__init__();self.calls=[];self.fail_clear=False;self.fail_resolve=False
    def set(self,provider,secret):self.calls.append(("set",provider));super().set(provider,secret)
    def resolve(self,provider):
        self.calls.append(("resolve",provider))
        if self.fail_resolve:raise VaultUnavailableError("TEST_RESOLVE_FAILED")
        return super().resolve(provider)
    def clear(self,provider):
        self.calls.append(("clear",provider))
        if self.fail_clear:raise VaultUnavailableError("TEST_CLEAR_FAILED")
        super().clear(provider)


@pytest.fixture
def isolated_api(tmp_path,monkeypatch):
    monkeypatch.setenv("NOVEL_DATA_PATH",str(tmp_path/"novel-data"))
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH",str(tmp_path/"asset.json"))
    monkeypatch.setenv("AUDIO_PROVIDER_CONFIG_PATH",str(tmp_path/"audio.json"))
    api=importlib.import_module("app.api")
    registry=ProviderSupportRegistry();backend=SpyBackend()
    vault=CredentialVault(backend_impl=backend,allow_memory_fallback=True,supports_provider=registry.supports_provider)
    original_configs=api._video_provider_configs;original_path=api._video_provider_config_path
    with monkeypatch.context() as scoped:
        scoped.setattr(api,"provider_support_registry",registry)
        scoped.setattr(api,"credential_vault",vault)
        scoped.setattr(api,"_video_provider_config_path",tmp_path/"video.json")
        scoped.setattr(api,"_video_provider_configs",{})
        registry.replace_source("asset",());registry.replace_source("audio",());registry.replace_source("video",())
        yield api,registry,vault,backend
    assert api._video_provider_configs is original_configs
    assert api._video_provider_config_path == original_path


def test_api_unknown_provider_contract_without_backend_access(isolated_api):
    api,_registry,_vault,backend=isolated_api
    application=FastAPI();application.include_router(api.router,prefix="/api");client=TestClient(application)
    for response in (
        client.get("/api/credentials/unknown-provider"),
        client.put("/api/credentials/unknown-provider",json={"provider":"unknown-provider","credential":"TEST_ONLY"}),
        client.delete("/api/credentials/unknown-provider"),
    ):
        assert response.status_code==400
        assert response.json()["detail"]=={"code":"UNSUPPORTED_PROVIDER","message":"不支持的服务商"}
    assert backend.calls==[]


def test_multi_source_delete_preserves_shared_credential(isolated_api,monkeypatch):
    api,registry,vault,backend=isolated_api;provider="shared-provider"
    asset={provider:{"endpoint":"https://asset.example/v1"}};audio={provider:{"endpoint":"https://audio.example/v1"}}
    monkeypatch.setattr(api,"load_asset_provider_config",lambda:asset)
    monkeypatch.setattr(api,"delete_asset_provider_config",lambda pid:not not asset.pop(pid,None))
    registry.replace_source("asset",asset);registry.replace_source("audio",audio)
    vault.set(provider,"TEST_ONLY");backend.calls.clear()
    assert api.asset_provider_config_delete(provider)["deleted"] is True
    assert ("clear",provider) not in backend.calls
    assert vault.resolve(provider)=="TEST_ONLY"


@pytest.mark.parametrize("domain",["asset","audio","video"])
def test_last_source_clear_failure_keeps_config_and_registry(isolated_api,monkeypatch,caplog,domain):
    api,registry,vault,backend=isolated_api;provider=f"{domain}-only";config={provider:{"endpoint":f"https://{domain}.example/v1"}}
    delete_calls=[]
    if domain=="asset":
        monkeypatch.setattr(api,"load_asset_provider_config",lambda:config)
        monkeypatch.setattr(api,"delete_asset_provider_config",lambda pid:delete_calls.append(pid) or bool(config.pop(pid,None)))
        operation=lambda:api.asset_provider_config_delete(provider)
    elif domain=="audio":
        monkeypatch.setattr(api,"load_audio_provider_config",lambda:config)
        monkeypatch.setattr(api,"delete_audio_provider_config",lambda pid:delete_calls.append(pid) or bool(config.pop(pid,None)))
        operation=lambda:api.remove_audio_provider(provider)
    else:
        api._video_provider_configs.update(config)
        operation=lambda:api.delete_video_provider_config(provider)
    registry.replace_source(domain,config);vault.set(provider,"TEST_ONLY_SECRET");backend.calls.clear();backend.fail_clear=True
    with pytest.raises(HTTPException) as raised:operation()
    assert raised.value.status_code==503 and raised.value.detail["code"]=="TEST_CLEAR_FAILED"
    assert provider in config and provider in (api._video_provider_configs if domain=="video" else config)
    assert registry.supports_provider(provider)
    assert backend.calls==[("clear",provider)] and delete_calls==[]
    assert vault.backend=="keyring" and vault._active_backend is backend
    assert "TEST_ONLY_SECRET" not in str(raised.value.detail)
    assert "TEST_ONLY_SECRET" not in caplog.text


@pytest.mark.parametrize("domain",["asset","audio","video"])
def test_degraded_vault_keeps_provider_config_and_registry(isolated_api,monkeypatch,caplog,domain):
    api,registry,vault,backend=isolated_api;provider=f"degraded-{domain}";config={provider:{"endpoint":f"https://{domain}.example/v1"}}
    delete_calls=[]
    if domain=="asset":
        monkeypatch.setattr(api,"load_asset_provider_config",lambda:config)
        monkeypatch.setattr(api,"delete_asset_provider_config",lambda pid:delete_calls.append(pid) or bool(config.pop(pid,None)))
        operation=lambda:api.asset_provider_config_delete(provider)
    elif domain=="audio":
        monkeypatch.setattr(api,"load_audio_provider_config",lambda:config)
        monkeypatch.setattr(api,"delete_audio_provider_config",lambda pid:delete_calls.append(pid) or bool(config.pop(pid,None)))
        operation=lambda:api.remove_audio_provider(provider)
    else:
        api._video_provider_configs.update(config)
        operation=lambda:api.delete_video_provider_config(provider)
    registry.replace_source(domain,config)
    vault.set(provider,"TEST_ONLY_SECRET");backend.fail_resolve=True
    assert vault.resolve(provider) is None
    assert vault.degraded is True and vault.backend=="memory"
    memory_clear_calls=[]
    monkeypatch.setattr(vault._active_backend,"clear",lambda pid:memory_clear_calls.append(pid))
    with pytest.raises(HTTPException) as raised:operation()
    assert raised.value.status_code==503 and raised.value.detail["code"]=="TEST_RESOLVE_FAILED"
    assert provider in config and provider in (api._video_provider_configs if domain=="video" else config)
    assert registry.supports_provider(provider) and delete_calls==[] and memory_clear_calls==[]
    assert "TEST_ONLY_SECRET" not in str(raised.value.detail) and "TEST_ONLY_SECRET" not in caplog.text


def test_video_delete_clears_last_credential_and_restart_restores_source(isolated_api):
    api,registry,vault,backend=isolated_api;provider="video-only"
    api._video_provider_configs[provider]={"provider_id":provider,"endpoint":"https://video.example/v1"}
    api._video_provider_config_path.write_text(json.dumps(api._video_provider_configs),encoding="utf-8")
    registry.replace_source("video",api._video_provider_configs);vault.set(provider,"TEST_ONLY");backend.calls.clear()
    api._video_provider_configs.clear();api._load_video_provider_configs();registry.replace_source("video",api._video_provider_configs)
    assert registry.supports_provider(provider)
    assert api.delete_video_provider_config(provider)=={"provider_id":provider,"deleted":True}
    assert ("clear",provider) in backend.calls and not registry.supports_provider(provider)
    assert provider not in json.loads(api._video_provider_config_path.read_text(encoding="utf-8"))


def test_asset_audio_video_configuration_and_last_source_cleanup(isolated_api,monkeypatch):
    api,registry,vault,backend=isolated_api
    from app import dependencies
    monkeypatch.setattr(api,"refresh_asset_provider",lambda _provider:False)
    monkeypatch.setattr(dependencies,"refresh_video_provider",lambda *_args,**_kwargs:False)
    providers=("asset-new","audio-new","video-new")
    assert all(not vault.supports_provider(provider) for provider in providers)
    api.asset_provider_config_set("asset-new",api.AssetProviderConfigIn(
        endpoint="https://asset.example/v1",default_model="image-v1",display_name="Asset New"
    ))
    api.configure_audio_provider("audio-new",api.AudioProviderConfigIn(
        endpoint="https://audio.example/v1",default_model="voice-v1",display_name="Audio New",
        local=False,enabled=True,requires_credential=True,capabilities=["TTS"],
    ))
    api.configure_video_provider("video-new",api.VideoProviderConfigIn(
        endpoint="https://video.example/v1",model_id="video-v1",display_name="Video New"
    ))
    for provider in providers:
        assert vault.supports_provider(provider)
        vault.set(provider,"TEST_ONLY")
        assert vault.status(provider)["secret"] is None
    backend.calls.clear()
    assert api.asset_provider_config_delete("asset-new")["deleted"] is True
    assert api.remove_audio_provider("audio-new")["deleted"] is True
    assert api.delete_video_provider_config("video-new")["deleted"] is True
    assert [(kind,provider) for kind,provider in backend.calls if kind=="clear"]==[
        ("clear","asset-new"),("clear","audio-new"),("clear","video-new")
    ]
    assert all(not registry.supports_provider(provider) for provider in providers)
