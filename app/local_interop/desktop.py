"""Studio product composition for the frozen desktop integration contracts.

All data is projected from existing Studio owners. Local health, provenance and
permission controls are browser DTOs, never additions to the 1.0 wire schema.
"""
from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from uuid import uuid4

from local_interop_desktop.providers import InteropHandoffHandler, UserPresenceGate
from local_interop_protocol import (
    CAPABILITIES,
    PROTOCOL_VERSION,
    ModelRegistry,
    SharedModelDescriptor,
    TutorGuidance,
    VerifierResult,
    parse_wire,
)

from .errors import InteropFailure

PERMISSIONS = {
    "app_status": ("App Status", ("project.context.read",)),
    "task_status": ("Task Status", ("task.status.read", "task.error.read")),
    "model_metadata": ("Model Metadata", ("model.registry.read", "model.runtime.status.read")),
    "diagnostics": ("Diagnostics", ("diagnostics.read",)),
    "selection": ("Selection", ("project.selection.share",)),
    "current_chapter": ("Current Chapter", ()),
    "specific_context": ("Specific Context", ()),
    "standing_metadata_events": ("Standing Metadata Events", ()),
    "deep_link": ("Deep Link", ("handoff.open_feature", "handoff.open_project", "handoff.open_task")),
}
EVENT_SOURCES = (
    {"module": "PROJECT", "provenance": "DIRECT_EVENT"},
    {"module": "CHAPTER", "provenance": "DIRECT_EVENT"},
    {"module": "TASK", "provenance": "DIRECT_EVENT"},
    {"module": "MODEL", "provenance": "POLLING"},
    {"module": "RUNTIME", "provenance": "POLLING"},
    {"module": "EXPORT", "provenance": "POLLING"},
    {"module": "WORKFLOW", "provenance": "POLLING"},
)


class StudioContextProvider:
    """A session-bound InteropContextProvider, with no shadow state or DB."""
    def __init__(self, host, token, session_id):
        self.host, self.token, self.session_id = host, token, session_id

    def _session(self):
        return self.host._session(self.token, self.session_id, "project.context.read")

    def _snapshot(self):
        return self.host._snapshot(self._session())

    def current_product_context(self):
        self._session()
        return self.host.product.model_dump(mode="json")

    def current_project_context(self):
        state = self._snapshot()["state"]
        return {key: state[key] for key in ("workspace_id", "project_id", "storyline_id", "branch_id", "project_version", "chapter_id", "chapter_version")}

    def current_surface(self):
        state = self._snapshot()["state"]
        return {"module": state["module"], "surface": state["surface"]}

    def current_task(self):
        self.host._session(self.token, self.session_id, "task.status.read")
        state = self._snapshot()["state"]
        return {key: state[key] for key in ("task_id", "task_type", "task_status")}

    def current_model_state(self):
        self.host._session(self.token, self.session_id, "model.registry.read")
        return {"model_id": self._snapshot()["state"]["model_id"]}

    def current_runtime_state(self):
        self.host._session(self.token, self.session_id, "model.runtime.status.read")
        state = self._snapshot()["state"]
        return {key: state[key] for key in ("runtime_id", "runtime_status")}

    def selected_content_metadata(self):
        # Read only this session's existing version-bound preview. There is no
        # ambient editor scraping, copied manuscript store or implicit consent.
        session = self._session()
        snapshot = self._snapshot()
        state = snapshot["state"]
        selected = next((item["capsule"] for item in reversed(session.previews.values())
            if item.get("kind") == "context" and item["source"] == snapshot["source_version"]
            and item["capsule"].selection_id and item["capsule"].expires_at > datetime.now(UTC)), None)
        return {"chapter_id": state["chapter_id"], "chapter_version": state["chapter_version"],
            "selection_available": selected is not None, "selection_id": selected.selection_id if selected else None,
            "selection_hash": selected.selection_hash if selected else None, "consent_required": True}

    def build_capsule(self, scope):
        session = self._session()
        if not isinstance(scope, dict) or scope.get("content_kind", "NONE") != "NONE" or set(scope) - {"content_kind", "metadata_fields"}:
            raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 403)
        return self.host._capsule(session, self._snapshot(), metadata_fields=scope.get("metadata_fields", ()))


class StudioModelRegistryProvider:
    """Live allowlisted Model Center metadata; never probes or launches models."""
    def __init__(self, provider):
        self.provider = provider

    def snapshot(self):
        return ModelRegistry(models=tuple(SharedModelDescriptor(**row) for row in self.provider.model_rows()), created_at=datetime.now(UTC))

    def freshness(self):
        rows = self.provider.model_rows()
        return "STALE" if any(row["last_validated"] is None for row in rows) else "FRESH" if rows else "UNKNOWN"


class StudioVerifierAdapter:
    def __init__(self, request_id, session_id, original_context=None):
        self.request_id, self.session_id, self.original_context = request_id, session_id, original_context

    def verify(self, condition, fresh_context, trusted_evidence):
        status, evidence = self.evaluate(condition, fresh_context, trusted_evidence, original_context=self.original_context)
        return VerifierResult(request_id=self.request_id, session_id=self.session_id,
            result_id="verification-" + uuid4().hex, status=status,
            reason="Fresh Studio source satisfies the structured condition." if status == "VERIFIED" else "Fresh Studio state does not satisfy the condition." if status == "FAILED" else "No matching authoritative source is available.",
            evidence=evidence, privacy_scope="LOCAL_ONLY", created_at=datetime.now(UTC))

    def evaluate(self, condition, fresh_context, trusted_evidence, *, original_context=None):
        if original_context is not None:
            # A repaired task may legitimately move FAILED -> COMPLETED. A
            # different project/chapter revision cannot inherit that proof.
            anchors = ("workspace_id", "project_id", "storyline_id", "branch_id", "project_version", "chapter_id", "chapter_version", "task_id", "module", "surface", "instance_id")
            if any(getattr(fresh_context, key) != getattr(original_context, key) for key in anchors):
                return "UNKNOWN", ()
        if condition is None:
            return "UNKNOWN", ()
        evidence = tuple(item for item in trusted_evidence if item.source_id == condition.field == condition.source_id and item.source_version == fresh_context.source_version and item.authority == "AUTHORITATIVE")
        actual = getattr(fresh_context, condition.field)
        if not evidence or actual is None or actual == "UNKNOWN":
            return "UNKNOWN", ()
        matches = {"EQ": lambda: actual == condition.expected_value, "NE": lambda: actual != condition.expected_value,
                   "GTE": lambda: type(actual) is int and actual >= condition.expected_value}[condition.operator]()
        return ("VERIFIED" if matches else "FAILED"), evidence


class StudioTutorAdapter:
    def __init__(self, session, guard):
        self.session, self.guard = session, guard

    async def request(self, request):
        self.guard()
        raw = await self.session.transport.request("diagnostics" if request.diagnostic else "tutor", request,
            token=self.session.peer_token, before_send=self.guard)
        self.guard()
        return parse_wire(TutorGuidance, raw)


class StudioHandoffAdapter:
    def __init__(self, host):
        self.host = host
        self.presence = UserPresenceGate()

    def handle(self, token, body):
        session = self.host._session(token, body.session_id)
        self.host._permission(session, "deep_link")
        if not body.explicit_click:
            raise InteropFailure("PERMISSION_DENIED", 403)
        target = body.handoff
        key = {"OPEN_FEATURE": "feature", "OPEN_PROJECT": "project_id", "OPEN_CHAPTER": "chapter_id", "OPEN_TASK": "task_id"}.get(target.action)
        if key is None: raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404)
        result = {}
        def resolve(candidate):
            result.update(self.host._resolve_handoff(token, body))
            return True
        def open_target(candidate):
            # Platform-neutral route is returned to the existing Studio router.
            # Nothing opens/executes from a Tutor response without this click.
            self.host._session(token, body.session_id)
        handler = InteropHandoffHandler(self.presence, resolve=resolve, open_target=open_target)
        gesture = self.presence.issue_target(target, session_id=session.id, source="USER_CLICK")
        handler.open(target, user_presence_token=gesture, session_id=session.id)
        return result


class StudioCaseGateAdapter:
    def __init__(self, host):
        self.host = host

    def preview(self, token, body):
        return self.host._case_preview(token, body)

    def submit(self, token, body):
        # Native Tutor Case/Memory Gate is absent. Explicit approval only
        # records this bounded local candidate receipt; no case store write.
        return self.host._case_approve(token, body)


class CreativeStudioInteropAdapter:
    """Actual Studio composition. The native signed peer boundary stays absent."""
    def __init__(self, host):
        self.host = host
        self.models = StudioModelRegistryProvider(host.provider)
        self.handoff = StudioHandoffAdapter(host)
        self.case_gate = StudioCaseGateAdapter(host)
        self.owner_states = {}
        self.owner_errors = {}
        self.audit = deque(maxlen=128)

    def verifier(self, session, request_id, original_context=None):
        return StudioVerifierAdapter(request_id, session.wire_session.session_id, original_context)

    def tutor(self, session, guard):
        return StudioTutorAdapter(session, guard)

    def context(self, token, session_id):
        return StudioContextProvider(self.host, token, session_id)

    def record(self, owner, operation, *, session=None, capability=None, permission_id=None, result="OK", error_code=None):
        # Fixed vocabulary only: never log body, exception text or endpoint.
        allowed = {"DISCOVER", "CONNECT", "DISCONNECT", "REVOKE", "PAUSE", "SUBSCRIBE", "SHUTDOWN", "SOURCE_EVENT"}
        if operation not in allowed:
            raise ValueError("unsupported audit operation")
        if capability is not None and capability not in CAPABILITIES: raise ValueError("unknown wire capability")
        if permission_id is not None and permission_id not in PERMISSIONS: raise ValueError("unknown local permission")
        self.audit.append({"timestamp": datetime.now(UTC).isoformat(), "owner": owner,
            "operation": operation, "peer_product_id": session.peer.product_id if session else None,
            "capability": capability, "permission_id": permission_id, "decision": "REVOKED" if operation in {"REVOKE", "DISCONNECT"} else "ALLOWED",
            "result": result, "error_code": error_code})

    @staticmethod
    def permissions(session):
        return [{"id": key, "label": label, "capabilities": list(capabilities),
                 "state": "REVOKED" if key in session.revoked_permissions else "GRANTED" if key == "standing_metadata_events" and session.event_grant_id else "AVAILABLE",
                 "standing": key == "standing_metadata_events"} for key, (label, capabilities) in PERMISSIONS.items()]

    def snapshot(self, owner, sessions, *, session_id=None):
        current = datetime.now(UTC)
        connections = [{"session_id": s.id, "product_display_name": s.peer.display_name, "product_id": s.peer.product_id,
            "product_version": s.peer.product_version, "protocol_version": PROTOCOL_VERSION,
            "trust_level": "UNVERIFIED", "transport": s.wire_session.transport,
            "mode": "MOCK_ONLY" if "MOCK_ONLY" in s.peer.display_name else "LOCAL_REFERENCE",
            "transport_connected": True, "handshake_complete": True, "peer_authenticated": False,
            "session_established": True, "capabilities_negotiated": True,
            "capabilities": sorted(self.host._capabilities(s)), "session_age_seconds": max(0, int((current - s.wire_session.created_at).total_seconds())),
            "expires_at": s.wire_session.expires_at.isoformat(), "permissions": self.permissions(s),
            "standing_permissions": ["standing_metadata_events"] if s.event_grant_id else [],
            "standing_metadata_fields": sorted(s.event_metadata_fields) if s.event_grant_id else []} for s in sessions]
        close_receipts = [{"session_id": s.id, "transport_disconnected": s.transport_disconnected,
            "transport_close_state": s.transport_close_state, "peer_disconnect_acknowledged": s.peer_disconnect_acknowledged,
            "revoked": True} for s in self.host.closed_sessions.values() if s.owner == owner and (session_id is None or s.id == session_id)]
        unconfirmed = [row for row in close_receipts if not row["transport_disconnected"]]
        present = bool(connections)
        # Discovery and product_id are peer claims; no authentication is inferred
        # from a successful reference HTTP exchange or the local user's consent.
        state = "UNTRUSTED" if present else self.owner_states.get(owner, "UNKNOWN")
        transport_state = "READY" if present else "FAILED" if state == "DEGRADED" else "STOPPED"
        if unconfirmed:
            failed = any(row["transport_close_state"] in {"FAILED", "TIMEOUT"} for row in unconfirmed)
            state = "DEGRADED" if failed else "UNKNOWN"
            transport_state = "FAILED" if failed else "DISCONNECTING"
        health = {"transport": "READY" if present else "DEGRADED" if state == "DEGRADED" else "UNAVAILABLE", "peer": "DEGRADED" if present else "UNKNOWN",
            "session": "READY" if present else "UNAVAILABLE", "capabilities": "READY" if present else "UNKNOWN",
            "events": "READY" if any(s.event_grant_id for s in sessions) else "UNAVAILABLE",
            "tutor": "READY" if present else "UNAVAILABLE", "verifier": "READY" if present else "UNAVAILABLE"}
        if unconfirmed:
            health["transport"] = "DEGRADED" if state == "DEGRADED" else "UNKNOWN"
        try:
            freshness = self.models.freshness()
        except Exception:  # noqa: BLE001 - unavailable model owner is isolated from Studio and settings
            freshness = "UNKNOWN"
        return {"state": state, "transport_state": transport_state, "boundary": "LOCAL_REQUIRED",
            "connections": connections, "health": health, "event_sources": list(EVENT_SOURCES), "close_receipts": close_receipts,
            "model_registry_freshness": freshness,
            "diagnostics": {"protocol_version": PROTOCOL_VERSION, "error_codes": self.owner_errors.get(owner, []), "trust_state": "UNVERIFIED",
                "state_machine": transport_state, "timings": {}, "production_peer_authentication": "LOCAL_REQUIRED"}}


class StudioHostLifecycleBoundary:
    """Coordinator seam around the actual host; never opens an implicit listener."""
    def __init__(self, host):
        self.host = host

    @property
    def instance_id(self):
        return self.host.product.instance_id

    async def start(self):
        return not self.host.closed

    async def connect(self, peer, *, token):
        return await self.host._connect(token, peer)

    def _invalidate(self):
        self.host.closed = True
        for session in tuple(self.host.sessions.values()):
            self.host._revoke(session)

    async def disconnect(self, *, peer=None):
        import asyncio
        if peer is not None:
            session = self.host.sessions.get(peer)
            if session is not None: self.host._revoke(session)
            return
        for session in tuple(self.host.sessions.values()):
            self.host._revoke(session)
        for owner in tuple(self.host.connect_epochs):
            self.host.connect_epochs[owner] += 1
        for key, task in tuple(self.host.requests.items()):
            self.host.seen[key] = "CANCELLED"
            if task is not asyncio.current_task(): task.cancel()

    async def shutdown(self, *, timeout=1.0):
        await self.host.shutdown(timeout=timeout)
