"""Stable, side-effect-free release readiness aggregation."""
from __future__ import annotations

import json
from typing import Any

from .credential_vault import VaultUnavailableError


ENV_DOCS = [
    "CREDENTIAL_VAULT_BACKEND",
    "CREDENTIAL_VAULT_SERVICE",
    "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK",
    "OUTBOUND_LOOPBACK_ALLOWLIST",
]


def _provider_check(runtime: Any, credential_vault: Any, image_registry: Any) -> dict[str, Any]:
    def has_credential(provider_id: str) -> bool:
        try:
            return credential_vault.has(provider_id)
        except VaultUnavailableError:
            return False

    descriptors = list(runtime.provider_registry.descriptors())
    text_descriptors = [item for item in descriptors if "text" in {str(value.value).lower() for value in item.supported_modalities}]
    text_configured = any(item.configured for item in text_descriptors)
    text_reachable = any(item.configured and item.available for item in text_descriptors)

    registered_image_ids = set(getattr(image_registry, "_providers", {}).keys())
    configured_image_ids = {
        provider_id for provider_id in registered_image_ids
        if provider_id == "deterministic" or has_credential(provider_id)
    }
    vision_configured = any(has_credential(provider_id) for provider_id in ("openai", "ddshub", "custom"))
    speech_configured = any(has_credential(provider_id) for provider_id in ("openai", "custom"))

    configured_modalities = sum((text_configured, bool(configured_image_ids), speech_configured, vision_configured))
    status = "PASS" if configured_modalities == 4 and text_reachable else "DEGRADED"
    return {
        "status": status,
        "text": {"configured": text_configured, "reachable": text_reachable},
        "image": {"registered": len(registered_image_ids), "configured": len(configured_image_ids)},
        "speech": {"configured": speech_configured},
        "vision": {"configured": vision_configured},
    }


def build_release_readiness(*, settings: Any, credential_vault: Any, runtime: Any,
                            image_registry: Any, packaged_bootstrap: bool) -> dict[str, Any]:
    """Return the canonical readiness contract without exposing credential material."""
    profile = "packaged" if settings.enable_packaged_runtime else (
        "collaboration" if settings.enable_collaboration_runtime else "local"
    )
    vault_unavailable = False
    try:
        vault_status = credential_vault.status("deepseek")
        vault = {
            "status": "DEGRADED" if vault_status["degraded"] or not vault_status["persistent"] else "PASS",
            "backend": vault_status["backend"],
            "persistent": vault_status["persistent"],
            "degraded": vault_status["degraded"],
            "degraded_reason": vault_status["degraded_reason"],
        }
    except VaultUnavailableError as exc:
        vault_unavailable = True
        vault = {
            "status": "FAIL",
            "backend": getattr(credential_vault, "backend", "memory"),
            "persistent": False,
            "degraded": True,
            "degraded_reason": exc.code,
        }

    if profile == "packaged":
        session_pass = settings.enable_collaboration_runtime and packaged_bootstrap
        session_mode = "packaged_bootstrap"
        session_detail = "Packaged bootstrap and opaque session boundary are configured." if session_pass else "Packaged bootstrap or collaboration session boundary is incomplete."
    elif profile == "collaboration":
        try:
            session_count = len(json.loads(settings.collaboration_dev_sessions_json or "[]"))
        except (TypeError, ValueError):
            session_count = 0
        session_pass = session_count > 0
        session_mode = "session_required"
        session_detail = "Trusted collaboration sessions are configured." if session_pass else "No trusted collaboration session is configured."
    else:
        session_pass = True
        session_mode = "loopback_only"
        session_detail = "Local runtime rejects non-loopback clients."

    session_boundary = {"status": "PASS" if session_pass else "FAIL", "mode": session_mode, "detail": session_detail}
    if profile == "packaged":
        packaged_pass = packaged_bootstrap and not settings.credential_vault_allow_memory_fallback
        packaged = {
            "status": "PASS" if packaged_pass else "FAIL",
            "bootstrap": packaged_bootstrap,
            "memory_fallback_allowed": settings.credential_vault_allow_memory_fallback,
        }
    else:
        packaged = {"status": "SKIP", "bootstrap": False, "memory_fallback_allowed": settings.credential_vault_allow_memory_fallback}

    providers = _provider_check(runtime, credential_vault, image_registry)
    blockers: list[str] = []
    warnings: list[str] = []
    if vault_unavailable:
        blockers.append("VAULT_UNAVAILABLE")
    elif profile == "packaged" and not vault["persistent"]:
        blockers.append("VAULT_NOT_PERSISTENT")
    elif vault["degraded"] or not vault["persistent"]:
        warnings.append("VAULT_MEMORY_BACKEND")
    if vault["degraded"] and "VAULT_MEMORY_BACKEND" not in warnings and profile != "packaged":
        warnings.append("VAULT_MEMORY_BACKEND")
    if not session_pass:
        blockers.append("SESSION_BOUNDARY_INCOMPLETE")
    if packaged["status"] == "FAIL":
        if not packaged_bootstrap and "SESSION_BOUNDARY_INCOMPLETE" not in blockers:
            blockers.append("PACKAGED_BOOTSTRAP_INCOMPLETE")
        if settings.credential_vault_allow_memory_fallback:
            blockers.append("PACKAGED_MEMORY_FALLBACK_ALLOWED")
    if providers["status"] != "PASS":
        warnings.append("PROVIDERS_PARTIALLY_CONFIGURED")

    status = "BLOCKED" if blockers else ("DEGRADED" if warnings else "READY")
    return {
        "status": status,
        "profile": profile,
        "checks": {
            "vault": vault,
            "session_boundary": session_boundary,
            "providers": providers,
            "packaged": packaged,
            "plugin_runtime": {"status": "DEFERRED", "execution_supported": False, "isolation": "DENY_ALL"},
        },
        "blockers": blockers,
        "warnings": warnings,
        "docs": {"env": ENV_DOCS},
    }
