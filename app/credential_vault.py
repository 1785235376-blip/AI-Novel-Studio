"""Provider credential storage backed by the operating-system secret store."""
from __future__ import annotations

import ctypes
import importlib
import os
import re
import sys
import uuid
from ctypes import wintypes
from typing import Literal, Protocol

_TARGET_PREFIX = "AI-Novel-Studio/provider/"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
SUPPORTED_PROVIDERS = frozenset({"deepseek", "openai", "claude", "gemini", "ddshub", "siliconflow", "aliyun-bailian", "runway", "kling", "minimax", "seedance", "custom"})
VaultBackendName = Literal["windows", "keyring", "memory"]


class VaultUnavailableError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class VaultBackend(Protocol):
    name: VaultBackendName
    persistent: bool
    def set(self, provider: str, secret: str) -> None: ...
    def resolve(self, provider: str) -> str | None: ...
    def clear(self, provider: str) -> None: ...


class MemoryBackend:
    name: VaultBackendName = "memory"
    persistent = False
    def __init__(self): self._store: dict[str, str] = {}
    def set(self, provider: str, secret: str) -> None: self._store[provider] = secret
    def resolve(self, provider: str) -> str | None: return self._store.get(provider)
    def clear(self, provider: str) -> None: self._store.pop(provider, None)


if sys.platform == "win32":
    class _CredentialAttributeW(ctypes.Structure):
        _fields_ = [("Keyword", wintypes.LPWSTR), ("Flags", wintypes.DWORD),
                    ("ValueSize", wintypes.DWORD), ("Value", ctypes.POINTER(ctypes.c_ubyte))]

    class _CredentialW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.POINTER(_CredentialAttributeW)),
            ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
        ]
    _PCREDENTIALW = ctypes.POINTER(_CredentialW)


class WindowsBackend:
    name: VaultBackendName = "windows"
    persistent = True
    def __init__(self):
        if sys.platform != "win32": raise VaultUnavailableError("WINDOWS_CRED_MAN_UNAVAILABLE")

    def set(self, provider: str, secret: str) -> None:
        blob = secret.encode("utf-16-le")
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        credential = _CredentialW()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = _TARGET_PREFIX + provider
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = provider
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        api.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        if not api.CredWriteW(ctypes.byref(credential), 0): raise VaultUnavailableError("WINDOWS_CRED_MAN_ERROR")

    def resolve(self, provider: str) -> str | None:
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_PCREDENTIALW)]
        api.CredReadW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        pointer = _PCREDENTIALW()
        if not api.CredReadW(_TARGET_PREFIX + provider, _CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168: return None
            raise VaultUnavailableError("WINDOWS_CRED_MAN_ERROR")
        try:
            item = pointer.contents
            return ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize).decode("utf-16-le")
        finally: api.CredFree(pointer)

    def clear(self, provider: str) -> None:
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        if not api.CredDeleteW(_TARGET_PREFIX + provider, _CRED_TYPE_GENERIC, 0) and ctypes.get_last_error() != 1168:
            raise VaultUnavailableError("WINDOWS_CRED_MAN_ERROR")


class KeyringBackend:
    name: VaultBackendName = "keyring"
    persistent = True
    def __init__(self, service_name: str, module=None):
        self.service = service_name
        try: self.keyring = module or importlib.import_module("keyring")
        except ImportError as exc: raise VaultUnavailableError("KEYRING_NOT_INSTALLED") from exc

    def _code(self, exc: Exception) -> str:
        name=type(exc).__name__.lower()
        return "KEYRING_PERMISSION_DENIED" if "permission" in name or "denied" in str(exc).lower() else "KEYRING_BACKEND_UNUSABLE"

    def set(self, provider: str, secret: str) -> None:
        try: self.keyring.set_password(self.service, provider, secret)
        except Exception as exc: raise VaultUnavailableError(self._code(exc)) from exc

    def resolve(self, provider: str) -> str | None:
        try: return self.keyring.get_password(self.service, provider)
        except Exception as exc: raise VaultUnavailableError(self._code(exc)) from exc

    def clear(self, provider: str) -> None:
        try: self.keyring.delete_password(self.service, provider)
        except Exception as exc:
            errors=getattr(self.keyring,"errors",None)
            delete_error=getattr(errors,"PasswordDeleteError",None)
            if delete_error and isinstance(exc,delete_error): return
            raise VaultUnavailableError(self._code(exc)) from exc

    def probe(self) -> None:
        key=f"__probe__{uuid.uuid4().hex}"
        try:
            self.set(key,"1")
            if self.resolve(key)!="1": raise VaultUnavailableError("KEYRING_BACKEND_UNUSABLE")
        finally:
            try: self.clear(key)
            except VaultUnavailableError: pass


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name,str(default)).strip().lower() in {"1","true","yes","on"}


class CredentialVault:
    """Stores provider secrets without returning secret material from status()."""
    def __init__(self, *, backend: str | None = None, service_name: str | None = None,
                 allow_memory_fallback: bool | None = None, backend_impl: VaultBackend | None = None):
        requested=(backend or os.getenv("CREDENTIAL_VAULT_BACKEND","auto")).strip().lower()
        if requested not in {"auto","windows","keyring","memory"}: raise ValueError("unsupported credential vault backend")
        self.service_name=service_name or os.getenv("CREDENTIAL_VAULT_SERVICE","AI-Novel-Studio")
        packaged=_env_bool("ENABLE_PACKAGED_RUNTIME",False)
        self.allow_memory_fallback=_env_bool("CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK",not packaged) if allow_memory_fallback is None else allow_memory_fallback
        self.degraded=False
        self.degraded_reason: str | None=None
        if backend_impl is not None:
            self._active_backend=backend_impl
        else:
            self._active_backend=self._select_backend(requested)
        self.backend=self._active_backend.name

    def _select_backend(self, requested: str) -> VaultBackend:
        if requested=="memory": return MemoryBackend()
        if requested=="windows": return WindowsBackend()
        if requested=="auto" and sys.platform=="win32": return WindowsBackend()
        try:
            backend=KeyringBackend(self.service_name)
            backend.probe()
            return backend
        except VaultUnavailableError as exc:
            return self._fallback(exc.code)

    def _fallback(self, reason: str) -> VaultBackend:
        if not self.allow_memory_fallback: raise VaultUnavailableError(reason)
        self.degraded=True;self.degraded_reason=reason
        return MemoryBackend()

    def _validate_provider(self, provider: str) -> None:
        if not isinstance(provider, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', provider):
            raise ValueError("unsupported provider")

    def _degrade_after_failure(self, exc: VaultUnavailableError) -> MemoryBackend:
        backend=self._fallback(exc.code)
        self._active_backend=backend;self.backend=backend.name
        return backend

    def set(self, provider: str, secret: str) -> None:
        self._validate_provider(provider)
        if not isinstance(secret,str) or not secret or len(secret.encode("utf-8"))>4096 or any(c in secret for c in "\0\r\n"):
            raise ValueError("invalid credential")
        try: self._active_backend.set(provider,secret)
        except VaultUnavailableError as exc: self._degrade_after_failure(exc).set(provider,secret)

    def resolve(self, provider: str) -> str | None:
        self._validate_provider(provider)
        try: return self._active_backend.resolve(provider)
        except VaultUnavailableError as exc: return self._degrade_after_failure(exc).resolve(provider)

    def clear(self, provider: str) -> None:
        self._validate_provider(provider)
        try: self._active_backend.clear(provider)
        except VaultUnavailableError as exc: self._degrade_after_failure(exc).clear(provider)

    def has(self, provider: str) -> bool: return self.resolve(provider) is not None

    def status(self, provider: str) -> dict[str, object]:
        self._validate_provider(provider)
        configured=self.has(provider)
        return {"provider":provider,"configured":configured,"backend":self.backend,
                "persistent":self._active_backend.persistent,"degraded":self.degraded,
                "degraded_reason":self.degraded_reason,"secret":None}


credential_vault = CredentialVault()
