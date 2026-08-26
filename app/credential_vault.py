"""Provider credential storage with Windows Credential Manager support."""
from __future__ import annotations
import ctypes
import os
import sys
from ctypes import wintypes

_TARGET_PREFIX = "AI-Novel-Studio/provider/"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
# Keep the provider allow-list centralized so the vault, desktop bridge, and
# API cannot silently drift into accepting different credential namespaces.
SUPPORTED_PROVIDERS = frozenset({"deepseek", "openai", "claude", "gemini", "ddshub", "custom"})

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

class CredentialVault:
    """Stores secrets in Windows Credential Manager, with an in-memory test fallback."""
    def __init__(self, *, backend: str | None = None):
        self.backend = backend or os.getenv("CREDENTIAL_VAULT_BACKEND", "windows")
        self._memory: dict[str, str] = {}

    def _target(self, provider: str) -> str:
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError("unsupported provider")
        return _TARGET_PREFIX + provider

    def set(self, provider: str, secret: str) -> None:
        target = self._target(provider)
        if not isinstance(secret, str) or not secret or len(secret.encode()) > 4096 or any(c in secret for c in "\0\r\n"):
            raise ValueError("invalid credential")
        if self.backend != "windows" or sys.platform != "win32":
            self._memory[provider] = secret; return
        blob = secret.encode("utf-16-le")
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        credential = _CredentialW()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = provider
        advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        advapi32.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
        advapi32.CredWriteW.restype = wintypes.BOOL
        if not advapi32.CredWriteW(ctypes.byref(credential), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def resolve(self, provider: str) -> str | None:
        target = self._target(provider)
        if self.backend != "windows" or sys.platform != "win32":
            return self._memory.get(provider)
        advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        advapi32.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_PCREDENTIALW)]
        advapi32.CredReadW.restype = wintypes.BOOL
        advapi32.CredFree.argtypes = [ctypes.c_void_p]
        pointer = _PCREDENTIALW()
        if not advapi32.CredReadW(target, _CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == 1168: return None
            raise ctypes.WinError(error)
        try:
            item = pointer.contents
            blob = ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize)
            return blob.decode("utf-16-le")
        finally:
            advapi32.CredFree(pointer)

    def clear(self, provider: str) -> None:
        target = self._target(provider)
        if self.backend != "windows" or sys.platform != "win32":
            self._memory.pop(provider, None); return
        advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        advapi32.CredDeleteW.restype = wintypes.BOOL
        if not advapi32.CredDeleteW(target, _CRED_TYPE_GENERIC, 0):
            error = ctypes.get_last_error()
            if error != 1168: raise ctypes.WinError(error)

    def has(self, provider: str) -> bool:
        return self.resolve(provider) is not None

    def status(self, provider: str) -> dict[str, object]:
        self._target(provider)
        value = self.resolve(provider)
        return {"provider": provider, "configured": value is not None, "backend": self.backend, "secret": None}

credential_vault = CredentialVault()
