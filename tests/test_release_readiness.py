import json
from types import SimpleNamespace

from app.release_readiness import build_release_readiness
from app.credential_vault import VaultUnavailableError


class Vault:
    def __init__(self, *, persistent: bool, degraded: bool = False):
        self.persistent = persistent
        self.degraded = degraded

    def status(self, provider: str):
        return {
            "provider": provider,
            "configured": provider == "deepseek",
            "backend": "keyring" if self.persistent else "memory",
            "persistent": self.persistent,
            "degraded": self.degraded,
            "degraded_reason": "KEYRING_BACKEND_UNUSABLE" if self.degraded else None,
            "secret": None,
        }

    def has(self, provider: str) -> bool:
        return provider in {"deepseek", "openai", "ddshub"}


class TextModality:
    value = "text"


def runtime(*, configured=True, available=True):
    descriptor = SimpleNamespace(
        configured=configured,
        available=available,
        supported_modalities={TextModality()},
    )
    return SimpleNamespace(provider_registry=SimpleNamespace(descriptors=lambda: [descriptor]))


def settings(*, packaged=False, collaboration=False, allow_fallback=True):
    return SimpleNamespace(
        enable_packaged_runtime=packaged,
        enable_collaboration_runtime=collaboration,
        collaboration_dev_sessions_json='[{"token":"opaque"}]' if collaboration else "",
        credential_vault_allow_memory_fallback=allow_fallback,
    )


def test_memory_vault_is_degraded_without_leaking_secret():
    result = build_release_readiness(
        settings=settings(), credential_vault=Vault(persistent=False, degraded=True),
        runtime=runtime(), image_registry=SimpleNamespace(_providers={"ddshub": object()}),
        packaged_bootstrap=False,
    )
    assert result["status"] == "DEGRADED"
    assert "VAULT_MEMORY_BACKEND" in result["warnings"]
    assert "secret" not in json.dumps(result).lower()


def test_packaged_memory_vault_and_allowed_fallback_are_blocked():
    result = build_release_readiness(
        settings=settings(packaged=True, collaboration=True, allow_fallback=True),
        credential_vault=Vault(persistent=False), runtime=runtime(),
        image_registry=SimpleNamespace(_providers={"ddshub": object()}), packaged_bootstrap=True,
    )
    assert result["status"] == "BLOCKED"
    assert result["checks"]["packaged"]["status"] == "FAIL"
    assert "VAULT_NOT_PERSISTENT" in result["blockers"]
    assert "PACKAGED_MEMORY_FALLBACK_ALLOWED" in result["blockers"]


def test_plugin_runtime_is_deferred_and_does_not_block_ready_gate():
    result = build_release_readiness(
        settings=settings(allow_fallback=False), credential_vault=Vault(persistent=True),
        runtime=runtime(), image_registry=SimpleNamespace(_providers={"ddshub": object()}),
        packaged_bootstrap=False,
    )
    assert result["status"] == "READY"
    assert result["checks"]["plugin_runtime"] == {
        "status": "DEFERRED", "execution_supported": False, "isolation": "DENY_ALL"
    }


def test_unavailable_vault_is_a_stable_blocker():
    vault = Vault(persistent=True)
    vault.backend = "keyring"
    vault.status = lambda _provider: (_ for _ in ()).throw(VaultUnavailableError("KEYRING_BACKEND_UNUSABLE"))
    result = build_release_readiness(
        settings=settings(), credential_vault=vault, runtime=runtime(),
        image_registry=SimpleNamespace(_providers={"ddshub": object()}), packaged_bootstrap=False,
    )
    assert result["status"] == "BLOCKED"
    assert result["checks"]["vault"]["status"] == "FAIL"
    assert result["blockers"] == ["VAULT_UNAVAILABLE"]
