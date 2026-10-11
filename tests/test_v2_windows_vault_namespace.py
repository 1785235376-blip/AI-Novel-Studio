"""Cloud-only namespace contracts using real ctypes records and fake Windows APIs.

These tests never load Advapi32 or access Windows Credential Manager. They verify
Python marshalling and routing, not native Windows ABI/runtime behavior.
"""
from __future__ import annotations

import ctypes
import importlib.util
import sys
from types import SimpleNamespace

import pytest

from app import credential_vault as installed_vault


DEFAULT_TARGET = "AI-Novel-Studio/provider/openai"
V2_TARGET = "AI-Novel-Studio-V2/provider/openai"
PROFILE_ENV = "AI_NOVEL_PACKAGED_PROFILE"


class FakeFunction:
    """Accept the signature assignments made by the real ctypes adapter."""

    def __init__(self, implementation):
        self.implementation = implementation
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.implementation(*args)


class FakeAdvapi32:
    def __init__(self, module):
        self.module = module
        self.store = {}
        self.calls = []
        self.dll_calls = []
        self.writes = []
        self.allocations = []
        self.freed = []
        self.fail = None
        self.last_error = 0
        self.CredWriteW = FakeFunction(self.write)
        self.CredReadW = FakeFunction(self.read)
        self.CredDeleteW = FakeFunction(self.delete)
        self.CredFree = FakeFunction(self.free)

    def load(self, name, *, use_last_error):
        self.dll_calls.append((name, use_last_error))
        return self

    def write(self, pointer, flags):
        item = ctypes.cast(pointer, self.module._PCREDENTIALW).contents
        target = item.TargetName
        self.calls.append(("write", target, item.Type, flags))
        blob = ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize)
        self.writes.append((target, item.Type, item.Persist, item.UserName, blob))
        if self.fail == "write":
            self.last_error = 5
            return False
        self.store[target] = blob
        return True

    def read(self, target, credential_type, flags, output):
        self.calls.append(("read", target, credential_type, flags))
        if self.fail == "read" or target not in self.store:
            self.last_error = 5 if self.fail == "read" else 1168
            return False
        blob = self.store[target]
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        item = self.module._CredentialW()
        item.TargetName = target
        item.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        item.CredentialBlobSize = len(blob)
        pointer = ctypes.pointer(item)
        self.allocations.append((buffer, item, pointer))
        ctypes.cast(output, ctypes.POINTER(self.module._PCREDENTIALW))[0] = pointer
        return True

    def delete(self, target, credential_type, flags):
        self.calls.append(("delete", target, credential_type, flags))
        if self.fail == "delete" or target not in self.store:
            self.last_error = 5 if self.fail == "delete" else 1168
            return False
        del self.store[target]
        return True

    def free(self, pointer):
        self.freed.append(ctypes.addressof(pointer.contents))


@pytest.fixture
def windows_vault(monkeypatch):
    """Load the production Windows structures without changing the app singleton."""
    spec = importlib.util.spec_from_file_location(
        "app._v2_windows_vault_contract", installed_vault.__file__,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)

    def forbidden_native_load(*_args, **_kwargs):
        raise AssertionError("native Windows API loading is forbidden in this test")

    # Import only under a short-lived platform override. The singleton is memory
    # backed during import, and even an accidental Windows load hits a tripwire.
    with monkeypatch.context() as importing:
        importing.setattr(sys, "platform", "win32")
        importing.setattr(ctypes, "WinDLL", forbidden_native_load, raising=False)
        importing.setenv(PROFILE_ENV, "default")
        importing.setenv("CREDENTIAL_VAULT_BACKEND", "memory")
        importing.setenv("ENABLE_PACKAGED_RUNTIME", "false")
        spec.loader.exec_module(module)
    module.sys = SimpleNamespace(platform="win32")
    api = FakeAdvapi32(module)
    monkeypatch.setattr(module.ctypes, "WinDLL", api.load, raising=False)
    monkeypatch.setattr(module.ctypes, "get_last_error", lambda: api.last_error, raising=False)
    monkeypatch.delenv(PROFILE_ENV, raising=False)
    monkeypatch.setenv("ENABLE_PACKAGED_RUNTIME", "false")
    monkeypatch.setenv("CREDENTIAL_VAULT_BACKEND", "auto")
    monkeypatch.delenv("CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK", raising=False)
    return module, api


def enable_v2(monkeypatch):
    monkeypatch.setenv(PROFILE_ENV, "v2")
    monkeypatch.setenv("ENABLE_PACKAGED_RUNTIME", "true")


def forbid_alternate_backends(monkeypatch, module):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("V2 must never construct an alternate backend")
    monkeypatch.setattr(module, "MemoryBackend", forbidden)
    monkeypatch.setattr(module, "KeyringBackend", forbidden)


@pytest.mark.parametrize("namespace,target", [(None, DEFAULT_TARGET), ("default", DEFAULT_TARGET), ("v2", V2_TARGET)])
def test_real_ctypes_marshalling_routes_every_operation_to_fixed_target(windows_vault, namespace, target):
    module, api = windows_vault
    backend = module.WindowsBackend() if namespace is None else module.WindowsBackend(namespace=namespace)
    assert api.dll_calls == []
    secret = "TEST_ONLY_凭据_🔒"
    backend.set("openai", secret)
    assert backend.resolve("openai") == secret
    backend.clear("openai")
    assert backend.resolve("openai") is None
    assert api.calls == [(operation, target, 1, 0) for operation in ("write", "read", "delete", "read")]
    assert api.writes == [(target, 1, 2, "openai", secret.encode("utf-16-le"))]
    assert api.dll_calls == [("Advapi32.dll", True)] * 4
    assert len(api.freed) == 1
    assert api.store == {}
    assert api.CredWriteW.argtypes == [module._PCREDENTIALW, module.wintypes.DWORD]
    assert api.CredReadW.argtypes == [module.wintypes.LPCWSTR, module.wintypes.DWORD,
                                     module.wintypes.DWORD, ctypes.POINTER(module._PCREDENTIALW)]
    assert api.CredDeleteW.argtypes == [module.wintypes.LPCWSTR, module.wintypes.DWORD, module.wintypes.DWORD]
    assert api.CredFree.argtypes == [ctypes.c_void_p]
    assert api.CredWriteW.restype is module.wintypes.BOOL
    assert api.CredReadW.restype is module.wintypes.BOOL
    assert api.CredDeleteW.restype is module.wintypes.BOOL


@pytest.mark.parametrize("platform", ["win32", "linux"])
@pytest.mark.parametrize("namespace", ["", "V2", "v1", " default", "v2 ", "../v2", "AI-Novel-Studio-V2/provider/", None, [], {}])
def test_unknown_namespace_is_rejected_before_platform_or_api_checks(windows_vault, platform, namespace):
    module, api = windows_vault
    module.sys.platform = platform
    with pytest.raises(ValueError, match="PACKAGED_PROFILE_UNSUPPORTED"):
        module.WindowsBackend(namespace=namespace)
    assert api.dll_calls == [] and api.calls == []


@pytest.mark.parametrize("profile", ["", "V2", "v1", " default", "v2 ", "../v2"])
def test_unknown_backend_profile_is_rejected_before_any_backend_operation(windows_vault, monkeypatch, profile):
    module, api = windows_vault
    monkeypatch.setenv(PROFILE_ENV, profile)
    forbid_alternate_backends(monkeypatch, module)
    monkeypatch.setattr(module, "WindowsBackend", lambda **_kwargs: pytest.fail("profile must be validated first"))
    with pytest.raises(ValueError, match="PACKAGED_PROFILE_UNSUPPORTED"):
        module.CredentialVault()
    assert api.dll_calls == [] and api.calls == []


@pytest.mark.parametrize("backend", ["auto", "windows"])
def test_v2_profile_selects_windows_and_keeps_status_redacted(windows_vault, monkeypatch, backend):
    module, api = windows_vault
    enable_v2(monkeypatch)
    forbid_alternate_backends(monkeypatch, module)
    vault = module.CredentialVault(backend=backend)
    assert vault.profile == "v2"
    assert vault.allow_memory_fallback is False
    assert api.calls == [] and api.dll_calls == []
    api.store[DEFAULT_TARGET] = "LEGACY_TEST_ONLY".encode("utf-16-le")
    vault.set("openai", "V2_TEST_ONLY")
    assert vault.resolve("openai") == "V2_TEST_ONLY"
    assert vault.status("openai") == {"provider": "openai", "configured": True,
        "backend": "windows", "persistent": True, "degraded": False,
        "degraded_reason": None, "secret": None}
    vault.clear("openai")
    assert vault.resolve("openai") is None
    assert {call[1] for call in api.calls} == {V2_TARGET}
    assert api.store == {DEFAULT_TARGET: "LEGACY_TEST_ONLY".encode("utf-16-le")}


def test_v2_missing_credentials_never_probe_or_migrate_legacy_namespace(windows_vault, monkeypatch):
    module, api = windows_vault
    enable_v2(monkeypatch)
    api.store[DEFAULT_TARGET] = b"LEGACY_TEST_ONLY"
    vault = module.CredentialVault()
    assert vault.resolve("openai") is None
    assert vault.has("openai") is False
    assert vault.status("openai")["configured"] is False
    vault.clear("openai")
    assert api.calls == [(operation, V2_TARGET, 1, 0) for operation in ("read", "read", "read", "delete")]
    assert api.store == {DEFAULT_TARGET: b"LEGACY_TEST_ONLY"}
    assert api.writes == [] and api.freed == []
    assert vault.degraded is False


@pytest.mark.parametrize("operation", ["write", "read", "delete"])
def test_v2_api_errors_fail_closed_without_fallback_or_legacy_access(windows_vault, monkeypatch, operation):
    module, api = windows_vault
    enable_v2(monkeypatch)
    forbid_alternate_backends(monkeypatch, module)
    api.store[DEFAULT_TARGET] = b"LEGACY_TEST_ONLY"
    api.fail = operation
    vault = module.CredentialVault()
    active = vault._active_backend
    with pytest.raises(module.VaultUnavailableError) as raised:
        if operation == "write":
            vault.set("openai", "V2_TEST_ONLY")
        elif operation == "read":
            vault.resolve("openai")
        else:
            vault.clear("openai")
    assert raised.value.code == "WINDOWS_CRED_MAN_ERROR"
    assert api.calls == [(operation, V2_TARGET, 1, 0)]
    assert api.store == {DEFAULT_TARGET: b"LEGACY_TEST_ONLY"}
    assert vault.backend == "windows" and vault._active_backend is active
    assert vault.degraded is False and vault.degraded_reason is None


@pytest.mark.parametrize("packaged", [None, "false", "0"])
def test_v2_requires_packaged_runtime_before_windows_access(windows_vault, monkeypatch, packaged):
    module, api = windows_vault
    monkeypatch.setenv(PROFILE_ENV, "v2")
    if packaged is None:
        monkeypatch.delenv("ENABLE_PACKAGED_RUNTIME", raising=False)
    else:
        monkeypatch.setenv("ENABLE_PACKAGED_RUNTIME", packaged)
    with pytest.raises(ValueError, match="packaged runtime"):
        module.CredentialVault()
    assert api.calls == [] and api.dll_calls == []


@pytest.mark.parametrize("backend", ["memory", "keyring", "unrecognized"])
@pytest.mark.parametrize("via_environment", [False, True])
def test_v2_rejects_alternate_backend_configuration(windows_vault, monkeypatch, backend, via_environment):
    module, api = windows_vault
    enable_v2(monkeypatch)
    forbid_alternate_backends(monkeypatch, module)
    options = {"backend": backend}
    if via_environment:
        monkeypatch.setenv("CREDENTIAL_VAULT_BACKEND", backend)
        options = {}
    with pytest.raises(ValueError, match="backend"):
        module.CredentialVault(**options)
    assert api.calls == [] and api.dll_calls == []


@pytest.mark.parametrize("via_environment", [False, True])
def test_v2_rejects_memory_fallback_configuration(windows_vault, monkeypatch, via_environment):
    module, api = windows_vault
    enable_v2(monkeypatch)
    forbid_alternate_backends(monkeypatch, module)
    options = {"allow_memory_fallback": True}
    if via_environment:
        monkeypatch.setenv("CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK", "true")
        options = {}
    with pytest.raises(ValueError, match="memory fallback"):
        module.CredentialVault(**options)
    assert api.calls == [] and api.dll_calls == []


@pytest.mark.parametrize("name", ["memory", "keyring", "windows"])
def test_v2_rejects_all_injected_backends(windows_vault, monkeypatch, name):
    module, api = windows_vault
    enable_v2(monkeypatch)
    injected = SimpleNamespace(name=name, persistent=True)
    with pytest.raises(ValueError, match="injected backends"):
        module.CredentialVault(backend_impl=injected)
    assert api.calls == [] and api.dll_calls == []


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize("backend", ["auto", "windows"])
def test_v2_non_windows_fails_closed(windows_vault, monkeypatch, platform, backend):
    module, api = windows_vault
    enable_v2(monkeypatch)
    forbid_alternate_backends(monkeypatch, module)
    module.sys.platform = platform
    with pytest.raises(module.VaultUnavailableError) as raised:
        module.CredentialVault(backend=backend)
    assert raised.value.code == "WINDOWS_CRED_MAN_UNAVAILABLE"
    assert api.calls == [] and api.dll_calls == []


@pytest.mark.parametrize("profile", [None, "default"])
def test_default_profile_preserves_legacy_target_and_fallback_contract(windows_vault, monkeypatch, profile):
    module, api = windows_vault
    if profile is not None:
        monkeypatch.setenv(PROFILE_ENV, profile)
    vault = module.CredentialVault(backend="windows", allow_memory_fallback=True)
    vault.set("openai", "DEFAULT_TEST_ONLY")
    assert vault.resolve("openai") == "DEFAULT_TEST_ONLY"
    vault.clear("openai")
    api.fail = "write"
    vault.set("openai", "MEMORY_TEST_ONLY")
    assert vault.resolve("openai") == "MEMORY_TEST_ONLY"
    assert vault.backend == "memory" and vault.degraded is True
    assert vault.degraded_reason == "WINDOWS_CRED_MAN_ERROR"
    assert {call[1] for call in api.calls} == {DEFAULT_TARGET}


def test_service_name_and_frontend_flags_cannot_select_or_redirect_v2(windows_vault, monkeypatch):
    module, api = windows_vault
    monkeypatch.setenv("CREDENTIAL_VAULT_SERVICE", "AI-Novel-Studio-V2")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,ai_execution_v2,model_broker_v2")
    default_vault = module.CredentialVault(backend="windows")
    default_vault.set("openai", "DEFAULT_TEST_ONLY")
    enable_v2(monkeypatch)
    v2_vault = module.CredentialVault(backend="windows", service_name="AI-Novel-Studio")
    v2_vault.set("openai", "V2_TEST_ONLY")
    assert [call[1] for call in api.calls] == [DEFAULT_TARGET, V2_TARGET]
    assert api.store == {DEFAULT_TARGET: "DEFAULT_TEST_ONLY".encode("utf-16-le"),
                         V2_TARGET: "V2_TEST_ONLY".encode("utf-16-le")}


def test_instance_namespace_stays_fixed_when_process_environment_changes(windows_vault, monkeypatch):
    module, api = windows_vault
    default_vault = module.CredentialVault(backend="windows")
    enable_v2(monkeypatch)
    v2_vault = module.CredentialVault(backend="windows")
    monkeypatch.setenv(PROFILE_ENV, "default")
    default_vault.set("openai", "DEFAULT_TEST_ONLY")
    v2_vault.set("openai", "V2_TEST_ONLY")
    assert default_vault.resolve("openai") == "DEFAULT_TEST_ONLY"
    assert v2_vault.resolve("openai") == "V2_TEST_ONLY"
    v2_vault.clear("openai")
    assert default_vault.resolve("openai") == "DEFAULT_TEST_ONLY"
    assert api.calls == [("write", DEFAULT_TARGET, 1, 0), ("write", V2_TARGET, 1, 0),
                         ("read", DEFAULT_TARGET, 1, 0), ("read", V2_TARGET, 1, 0),
                         ("delete", V2_TARGET, 1, 0), ("read", DEFAULT_TARGET, 1, 0)]


def test_v2_fallback_invariant_survives_a_changed_fallback_attribute(windows_vault, monkeypatch):
    module, api = windows_vault
    enable_v2(monkeypatch)
    forbid_alternate_backends(monkeypatch, module)
    vault = module.CredentialVault()
    vault.allow_memory_fallback = True
    api.fail = "read"
    with pytest.raises(module.VaultUnavailableError, match="WINDOWS_CRED_MAN_ERROR"):
        vault.resolve("openai")
    assert vault.backend == "windows" and vault.degraded is False
    assert api.calls == [("read", V2_TARGET, 1, 0)]
