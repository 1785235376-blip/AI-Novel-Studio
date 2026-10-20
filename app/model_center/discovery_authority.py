"""Current Host authority for the host-private discovery surface only.

Collaboration membership is not host provenance. This does not change Model
Center's separate historical authorization contract or issue any credential.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import json
from typing import Callable

from fastapi import HTTPException, Request

from ..actor_context import SessionContext
from ..packaging.local_session_bootstrap import BootstrapDenied


@dataclass(frozen=True)
class DiscoveryAuthority:
    principal: str
    guard: Callable[[], None]


def resolve_discovery_authority(request: Request, token: str | None, *,
                                settings_getter, resolver_getter, bootstrap_getter):
    """Resolve and capture existing host provenance, including binding ABA fencing."""
    def resolve():
        settings = settings_getter()
        packaged = bool(getattr(settings, "enable_packaged_runtime", False))
        collaboration = bool(getattr(settings, "enable_collaboration_runtime", False))
        if collaboration and not packaged:
            raise HTTPException(403, {"code": "LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE"})
        # Never accept a forwarded identity as proof of a local host caller.
        if any(name in request.headers for name in
               ("forwarded", "x-forwarded-for", "x-real-ip", "x-forwarded-host", "x-forwarded-proto")):
            raise HTTPException(403, {"code": "LOCAL_AI_DIRECT_HOST_CONNECTION_REQUIRED"})
        host = request.client.host if request.client else ""
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            # Existing in-process TestClient transport, not an HTTP header.
            loopback = host == "testclient"
        if not loopback:
            raise HTTPException(403, {"code": "LOCAL_AI_DIRECT_HOST_CONNECTION_REQUIRED"})
        if not token:
            raise HTTPException(401, {"code": "SESSION_REQUIRED"})
        try:
            manager = bootstrap_getter() if packaged else None
            if packaged:
                if not collaboration or manager is None:
                    raise KeyError("missing current packaged Host")
                registry = manager.sessions
                actor = manager.resolve_issued_session(token)
                expected_origin = manager.expected_origin
                mode = "PACKAGED_BOOTSTRAP"
            else:
                registry = resolver_getter()
                actor = registry.resolve(token)
                expected_origin = getattr(settings, "frontend_origin", "")
                mode = "LOCAL_HOST"
            origin = request.headers.get("origin")
            if origin and (not expected_origin or origin.rstrip("/") != expected_origin.rstrip("/")):
                raise HTTPException(403, {"code": "LOCAL_AI_HOST_ORIGIN_DENIED"})
            actor_id = getattr(actor, "actor_id", None)
            if not isinstance(actor_id, str) or not actor_id:
                raise KeyError("missing actor")
            session = getattr(actor, "session", None)
            if isinstance(session, SessionContext):
                generation = registry.binding_generation(token)
                # Detect a binding change between resolving identity and epoch.
                if registry.resolve(token).session is not session:
                    raise KeyError("changed binding")
                values = (mode, id(registry), id(manager) if manager else 0, generation,
                          session.session_id, session.client_id, session.actor_id, session.workspace_id)
                principal = hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()
            else:
                # Preserve legacy explicitly injected test authorizers. Such an
                # incomplete identity can never issue a new scope consent.
                values = (mode, id(registry), id(manager) if manager else 0, actor_id)
                principal = ""
            return values, principal
        except (BootstrapDenied, KeyError, ValueError, AttributeError):
            raise HTTPException(401, {"code": "INVALID_SESSION"}) from None

    captured, principal = resolve()

    def current():
        values, _ = resolve()
        if values != captured:
            raise HTTPException(401, {"code": "LOCAL_AI_HOST_SESSION_CHANGED"})

    current()
    return DiscoveryAuthority(principal, current)
