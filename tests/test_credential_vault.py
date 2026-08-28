from app.credential_vault import CredentialVault, KeyringBackend, MemoryBackend, SUPPORTED_PROVIDERS, VaultUnavailableError
from app.provider_support import ProviderSupportRegistry
import sys
import os
import uuid
import pytest

def test_vault_round_trip_and_redacted_status():
    vault = CredentialVault(backend="memory")
    vault.set("deepseek", "TEST_ONLY_SECRET")
    assert vault.resolve("deepseek") == "TEST_ONLY_SECRET"
    assert vault.status("deepseek") == {"provider": "deepseek", "configured": True, "backend": "memory", "persistent":False,"degraded":False,"degraded_reason":None,"secret": None}
    vault.clear("deepseek")
    assert vault.resolve("deepseek") is None

def test_injected_persistent_backend_and_overwrite():
    class Fake:
        name="keyring";persistent=True
        def __init__(self):self.data={}
        def set(self,provider,secret):self.data[provider]=secret
        def resolve(self,provider):return self.data.get(provider)
        def clear(self,provider):self.data.pop(provider,None)
    backend=Fake();vault=CredentialVault(backend_impl=backend)
    vault.set("openai","first");vault.set("openai","second")
    assert vault.resolve("openai")=="second"
    assert vault.status("openai")["persistent"] is True
    assert vault.status("openai")["secret"] is None

def test_backend_failure_degrades_only_when_allowed():
    class Broken:
        name="keyring";persistent=True
        def set(self,provider,secret):raise VaultUnavailableError("KEYRING_BACKEND_UNUSABLE")
        def resolve(self,provider):raise VaultUnavailableError("KEYRING_BACKEND_UNUSABLE")
        def clear(self,provider):raise VaultUnavailableError("KEYRING_BACKEND_UNUSABLE")
    vault=CredentialVault(backend_impl=Broken(),allow_memory_fallback=True)
    vault.set("openai","secret")
    status=vault.status("openai")
    assert status["configured"] is True and status["backend"]=="memory"
    assert status["degraded"] is True and status["degraded_reason"]=="KEYRING_BACKEND_UNUSABLE"
    with pytest.raises(VaultUnavailableError):CredentialVault(backend_impl=Broken(),allow_memory_fallback=False).set("openai","secret")

def test_memory_backend_is_explicitly_non_persistent_and_clear_is_idempotent():
    vault=CredentialVault(backend_impl=MemoryBackend())
    vault.clear("custom");vault.set("custom","secret");vault.clear("custom");vault.clear("custom")
    assert vault.status("custom")["configured"] is False
    assert vault.status("custom")["persistent"] is False

def test_keyring_backend_uses_service_and_idempotent_delete():
    class PasswordDeleteError(Exception):pass
    class FakeKeyring:
        errors=type("Errors",(),{"PasswordDeleteError":PasswordDeleteError})
        def __init__(self):self.data={}
        def set_password(self,service,user,value):self.data[(service,user)]=value
        def get_password(self,service,user):return self.data.get((service,user))
        def delete_password(self,service,user):
            if self.data.pop((service,user),None) is None:raise PasswordDeleteError()
    fake=FakeKeyring();backend=KeyringBackend("Studio Test",fake)
    backend.probe();backend.set("openai","secret")
    assert backend.resolve("openai")=="secret"
    backend.clear("openai");backend.clear("openai")

def test_explicit_keyring_without_dependency_fails_closed(monkeypatch):
    def missing(_name):raise ImportError("missing")
    monkeypatch.setattr("app.credential_vault.importlib.import_module",missing)
    with pytest.raises(VaultUnavailableError) as raised:
        CredentialVault(backend="keyring",allow_memory_fallback=False)
    assert raised.value.code=="KEYRING_NOT_INSTALLED"

def test_auto_keyring_can_report_memory_degradation(monkeypatch):
    def missing(_name):raise ImportError("missing")
    monkeypatch.setattr("app.credential_vault.importlib.import_module",missing)
    vault=CredentialVault(backend="keyring",allow_memory_fallback=True)
    status=vault.status("openai")
    assert status["backend"]=="memory" and status["persistent"] is False
    assert status["degraded"] is True and status["degraded_reason"]=="KEYRING_NOT_INSTALLED"

def test_vault_rejects_invalid_or_unknown_credentials():
    vault = CredentialVault(backend="memory")
    for value in ("", "bad\nsecret", "x"*4097):
        try: vault.set("deepseek", value)
        except ValueError: pass
        else: raise AssertionError("invalid credential accepted")
    try: vault.set("unknown", "x")
    except ValueError: pass
    else: raise AssertionError("unknown provider accepted")

def test_static_provider_operations_remain_compatible():
    vault=CredentialVault(backend="memory")
    for provider in SUPPORTED_PROVIDERS:
        assert vault.supports_provider(provider)
        vault.set(provider,"TEST_ONLY")
        assert vault.resolve(provider)=="TEST_ONLY"
        assert vault.has(provider) is True
        assert vault.status(provider)["secret"] is None
        vault.clear(provider)

def test_unknown_and_resolver_failure_never_touch_backend():
    class Spy:
        name="memory";persistent=False
        def __init__(self):self.calls=[]
        def set(self,*args):self.calls.append(("set",args))
        def resolve(self,*args):self.calls.append(("resolve",args));return None
        def clear(self,*args):self.calls.append(("clear",args))
    for resolver in (lambda _provider:False,lambda _provider:(_ for _ in ()).throw(RuntimeError("resolver failed"))):
        backend=Spy();vault=CredentialVault(backend_impl=backend,supports_provider=resolver)
        for operation in (
            lambda:vault.set("unknown-provider","TEST_ONLY"),
            lambda:vault.resolve("unknown-provider"),lambda:vault.has("unknown-provider"),
            lambda:vault.status("unknown-provider"),lambda:vault.clear("unknown-provider"),
        ):
            with pytest.raises(ValueError):operation()
        assert vault.supports_provider("unknown-provider") is False
        assert backend.calls==[]

def test_dynamic_registry_sources_and_canonical_boundaries():
    registry=ProviderSupportRegistry()
    vault=CredentialVault(backend="memory",supports_provider=registry.supports_provider)
    provider="x"*64
    for rejected in ("", "x"*65, "Upper", "bad.provider"):
        registry.register("asset","valid")
        with pytest.raises(ValueError):vault.set(rejected,"TEST_ONLY")
    assert not vault.supports_provider(provider)
    registry.register("asset",provider);registry.register("audio",provider)
    assert registry.sources_for(provider)==frozenset({"asset","audio"})
    assert registry.supports_after_removing("asset",provider)
    vault.set(provider,"TEST_ONLY");registry.remove("asset",provider)
    assert vault.resolve(provider)=="TEST_ONLY"
    assert not registry.supports_after_removing("audio",provider)
    vault.clear(provider);registry.remove("audio",provider)
    assert not vault.supports_provider(provider)

@pytest.mark.skipif(sys.platform != "win32" or os.getenv("RUN_WINDOWS_CREDENTIAL_VAULT_INTEGRATION")!="1", reason="manual Windows Credential Manager integration only")
def test_windows_credential_manager_round_trip():
    vault = CredentialVault(backend="windows")
    secret = "TEST_ONLY_" + uuid.uuid4().hex
    vault.clear("deepseek")
    try:
        vault.set("deepseek", secret)
        assert vault.resolve("deepseek") == secret
        assert vault.status("deepseek")["secret"] is None
    finally:
        vault.clear("deepseek")
    assert vault.resolve("deepseek") is None
