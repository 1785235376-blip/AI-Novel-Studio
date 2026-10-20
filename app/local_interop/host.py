"""Opt-in Local Interop Host. Observation and advice never execute mutations."""
from __future__ import annotations

import asyncio
import secrets
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app import __version__
from app.experimental.flags import enabled_flags
from app.runtime_events import runtime_events
from local_interop_desktop.events import EventProvenance, InteropEventSourceRegistry
from local_interop_desktop.lifecycle import InteropLifecycleCoordinator
from local_interop_protocol import (
    CAPABILITIES,
    PROTOCOL_VERSION,
    STUDIO_PRODUCT_ID,
    CancelRequest,
    CancelResult,
    CapabilityNegotiation,
    CapabilityState,
    CaseCandidate,
    CaseEnvironment,
    ContextContent,
    ContextEvidence,
    DiscoveryRecord,
    HandshakeHello,
    Heartbeat,
    HelloResult,
    InteropEvent,
    ProductDescriptor,
    ProtocolViolation,
    SessionOpenRequest,
    SessionOpenResult,
    TutorRequest,
    create_capsule,
    create_diagnostic,
    parse_wire,
    validate_capsule,
)

from .desktop import (
    PERMISSIONS,
    CreativeStudioInteropAdapter,
    StudioHostLifecycleBoundary,
)
from .errors import InteropFailure
from .provider import FEATURES, anchor_text, digest
from .transport import LoopbackTransport

FLAG = "local_tutor_interop_v1"
MAX_SESSIONS = 32
MAX_PREVIEWS = 32
MAX_EVENTS = 32
MAX_REQUESTS = 256
METADATA_FIELDS = frozenset({"task", "error", "model", "runtime"})
DIAGNOSTIC_FIELDS = frozenset({"software_id", "software_version", "feature", "error_code", "task_state", "runtime", "model", "capability_state"})


def now(): return datetime.now(UTC)
def uid(prefix): return prefix + "-" + uuid4().hex

def current_task():
    try: return asyncio.current_task()
    except RuntimeError: return None


@dataclass
class LocalSession:
    id: str
    owner: str
    host_token: str = field(repr=False)
    scope: dict
    module: str
    surface: str
    chapter_id: str | None
    task_id: str | None
    authorization: str
    peer: ProductDescriptor
    wire_session: object
    peer_token: str = field(repr=False)
    transport: object = field(repr=False)
    previews: OrderedDict = field(default_factory=OrderedDict, repr=False)
    guidance: OrderedDict = field(default_factory=OrderedDict, repr=False)
    results: OrderedDict = field(default_factory=OrderedDict, repr=False)
    candidates: OrderedDict = field(default_factory=OrderedDict, repr=False)
    events: deque = field(default_factory=lambda: deque(maxlen=MAX_EVENTS), repr=False)
    sequence: int = 0
    sent_sequence: int = 0
    heartbeat_sequence: int = 0
    last_peer_seen: float = 0
    event_grant_id: str | None = None
    event_grant_request_id: str | None = None
    event_grant_binding: str | None = None
    event_metadata_fields: frozenset[str] = field(default_factory=frozenset)
    event_grant_generation: int = 0
    event_dispatch: asyncio.Task | None = field(default=None, repr=False)
    previous: dict | None = field(default=None, repr=False)
    pump: asyncio.Task | None = field(default=None, repr=False)
    revoked: bool = False
    revoked_permissions: set[str] = field(default_factory=set)
    permission_generation: int = 0
    wake: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    source_provenance: dict = field(default_factory=dict)
    loop: object = field(default=None, repr=False)
    source_subscriptions: dict = field(default_factory=dict, repr=False)
    closing_task: asyncio.Task | None = field(default=None, repr=False)
    transport_disconnected: bool = False
    transport_close_state: str = "UNKNOWN"
    peer_disconnect_acknowledged: bool = False
    chapter_identity: str | None = field(default=None, repr=False)


class LocalInteropHost:
    def __init__(self, provider, *, transport_factory=LoopbackTransport, event_interval=.25):
        self.provider = provider
        self.transport_factory = transport_factory
        self.event_interval = max(.05, event_interval)
        self.product = ProductDescriptor(product_id=STUDIO_PRODUCT_ID, display_name="Creative Studio",
            product_version=__version__, instance_id=uid("studio"), product_role="CREATIVE_STUDIO", capabilities=tuple(CAPABILITIES))
        self.enabled_owners = set()
        self.sessions: dict[str, LocalSession] = {}
        self.requests = {}
        self.connect_epochs = {}
        self.seen = OrderedDict()
        self.closed = False
        self.request_sessions = {}
        self.closing_tasks = set()
        self.closed_sessions = OrderedDict()
        self.pending_changes = set()
        self.delivery_bindings = OrderedDict()
        self.desktop = CreativeStudioInteropAdapter(self)
        self.event_sources = InteropEventSourceRegistry()
        self.poll_sources = InteropEventSourceRegistry()
        for module in InteropEventSourceRegistry.MODULES:
            self.event_sources.register(module, provenance=EventProvenance.DIRECT_EVENT if module in {"PROJECT", "CHAPTER", "TASK"} else EventProvenance.POLLING)
            self.poll_sources.register(module, provenance=EventProvenance.POLLING)
        self._unsubscribe_runtime = runtime_events.subscribe(self._on_runtime_change)
        self.lifecycle = InteropLifecycleCoordinator(StudioHostLifecycleBoundary(self),
            revoke_subscriptions=self._revoke_subscriptions, flush_audit=self._flush_audit)
        self.last_audit_count = 0

    def _revoke_subscriptions(self):
        for session in tuple(self.sessions.values()): self._pause_events(session)

    def _flush_audit(self):
        # Bounded metadata only. No durable session/grant or content is restored.
        self.last_audit_count = len(self.desktop.audit)
        self.desktop.audit.clear()

    async def app_start(self):
        if self.closed:
            # A restarted backend receives a fresh instance and empty authority.
            self.__init__(self.provider, transport_factory=self.transport_factory, event_interval=self.event_interval)
        await self.lifecycle.app_start()
        await self.lifecycle.app_ready()

    def _owner(self, token):
        actor = self.provider.actor(token)
        # Neither this opaque projection nor any protocol message exposes token.
        return "user-" + digest({"actor": actor.actor_id, "session": actor.session_id, "workspace": actor.workspace_id})[:48]

    def _enabled(self, owner):
        if self.closed or FLAG not in enabled_flags() or owner not in self.enabled_owners:
            self._revoke_owner(owner)
            raise InteropFailure("PERMISSION_DENIED", 403)

    def status(self, token, session_id=None):
        owner = self._owner(token)
        feature_enabled = FLAG in enabled_flags()
        if not feature_enabled: self._revoke_owner(owner)
        for session in tuple(self.sessions.values()):
            if session.owner == owner:
                try: self._session(token, session.id)
                except InteropFailure: pass
        if session_id is not None:
            closed = self.closed_sessions.get(session_id)
            if closed:
                if closed.owner != owner: raise InteropFailure("PERMISSION_DENIED", 403)
            else:
                self._session(token, session_id)
        sessions = [item for item in self.sessions.values() if item.owner == owner and not item.revoked and (session_id is None or item.id == session_id)]
        import os
        return {"feature_enabled": feature_enabled, "enabled": feature_enabled and owner in self.enabled_owners,
            "acceptance_mode": os.getenv("V1_ACCEPTANCE_MODE", "").lower().strip() in {"true", "1", "yes", "on"},
            "product": self.product.model_dump(mode="json"), "capabilities": list(CAPABILITIES),
            "disabled_capabilities": ["model.execute", "project.write"], "desktop_status": "LOCAL_REQUIRED",
            "desktop": self.desktop.snapshot(owner, sessions, session_id=session_id),
            "sessions": [{"session_id": s.id, "product": s.peer.model_dump(mode="json"), "capabilities": sorted(self._capabilities(s))}
                         for s in sessions]}

    def desktop_response_guard(self, token, value):
        """Pin browser-only permission projections until their last ASGI frame."""
        owner = self._owner(token)
        desktop = value.get("desktop") or {}
        bindings = []
        for row in desktop.get("connections", []):
            session = self._session(token, row["session_id"])
            bindings.append((session.id, session.permission_generation, session.event_grant_generation))
        enabled = owner in self.enabled_owners and FLAG in enabled_flags()
        def guard():
            self._owner(token)
            if enabled != (owner in self.enabled_owners and FLAG in enabled_flags()):
                raise InteropFailure("PERMISSION_DENIED", 403)
            for sid, permissions, events in bindings:
                current = self._session(token, sid)
                if (current.permission_generation, current.event_grant_generation) != (permissions, events):
                    raise InteropFailure("PERMISSION_DENIED", 403)
        return guard

    def status_guard(self, token, session_id=None):
        owner = self._owner(token)
        if session_id is None: return
        if session_id in self.sessions:
            self._session(token, session_id)
            return
        closed = self.closed_sessions.get(session_id)
        if closed is None: raise InteropFailure("SESSION_REVOKED", 401)
        if closed.owner != owner: raise InteropFailure("PERMISSION_DENIED", 403)

    def configure(self, token, enabled):
        owner = self._owner(token)
        if enabled:
            if self.closed or FLAG not in enabled_flags(): raise InteropFailure("PERMISSION_DENIED", 403)
            self.enabled_owners.add(owner)
        else:
            self.enabled_owners.discard(owner)
            self._revoke_owner(owner)
        return self.status(token)

    def _revoke_owner(self, owner):
        for session in tuple(self.sessions.values()):
            if session.owner == owner: self._revoke(session)
        for (request_owner, _), task in tuple(self.requests.items()):
            if request_owner == owner and task is not current_task(): task.cancel()

    def _revoke(self, session):
        if session.revoked: return
        session.revoked = True
        self.desktop.owner_states[session.owner] = "UNKNOWN"
        self.desktop.record(session.owner, "DISCONNECT", session=session)
        for key, sid in tuple(self.request_sessions.items()):
            if sid == session.id:
                self.seen[key] = "CANCELLED"
                task = self.requests.get(key)
                if task and task is not current_task(): task.cancel()
        self._pause_events(session)
        session.previews.clear(); session.guidance.clear(); session.results.clear(); session.candidates.clear(); session.events.clear()
        if session.pump and session.pump is not current_task(): session.pump.cancel()
        peer_token = session.peer_token
        session.peer_token = ""
        try:
            loop = asyncio.get_running_loop()
            session.closing_task = loop.create_task(self._close_peer(session, peer_token))
            self.closing_tasks.add(session.closing_task)
            session.closing_task.add_done_callback(self.closing_tasks.discard)
        except RuntimeError:
            pass
        session.host_token = ""
        self.sessions.pop(session.id, None)
        self.closed_sessions[session.id] = session
        while len(self.closed_sessions) > MAX_SESSIONS: self.closed_sessions.popitem(last=False)

    def _session(self, token, sid, capability=None):
        owner = self._owner(token)
        self._enabled(owner)
        session = self.sessions.get(sid)
        if session is None or session.revoked: raise InteropFailure("SESSION_REVOKED", 401)
        if session.owner != owner: raise InteropFailure("PERMISSION_DENIED", 403)
        if session.wire_session.expires_at <= now():
            self._revoke(session); raise InteropFailure("SESSION_REVOKED", 401)
        try:
            _, fingerprint, _ = self.provider.authorize(token, session.scope)
            if fingerprint != session.authorization: raise InteropFailure("PERMISSION_DENIED", 403)
        except InteropFailure:
            self._revoke(session)
            raise
        if capability and capability not in self._capabilities(session):
            raise InteropFailure("CAPABILITY_NOT_SUPPORTED", 403)
        return session

    async def run(self, token, request_id, operation, session_id=None):
        owner = self._owner(token)
        key = (owner, request_id)
        if key in self.seen or key in self.requests: raise InteropFailure("CANCELLED", 409)
        session = self._session(token, session_id) if session_id is not None else None
        self.seen[key] = "STARTED"
        while len(self.seen) > MAX_REQUESTS: self.seen.popitem(last=False)
        if len(self.requests) >= MAX_SESSIONS: raise InteropFailure("TIMEOUT", 429)
        self.requests[key] = asyncio.current_task()
        if session is not None:
            self.request_sessions[key] = session_id
            self.delivery_bindings[key] = (session_id, session.permission_generation, None)
            while len(self.delivery_bindings) > MAX_REQUESTS: self.delivery_bindings.popitem(last=False)
        try:
            async with asyncio.timeout(15):
                result = await operation()
                self._owner(token)
                if self.seen.get(key) == "CANCELLED": raise InteropFailure("CANCELLED", 409)
                self.seen[key] = "DONE"
                return result
        except asyncio.CancelledError:
            self.seen[key] = "CANCELLED"
            raise InteropFailure("CANCELLED", 409) from None
        except TimeoutError:
            raise InteropFailure("TIMEOUT", 504) from None
        finally:
            self.requests.pop(key, None)
            self.request_sessions.pop(key, None)

    def delivery_guard(self, token, sid=None, request_id=None):
        owner = self._owner(token)
        if request_id and self.seen.get((owner, request_id)) == "CANCELLED":
            raise InteropFailure("CANCELLED", 409)
        if sid:
            session = self._session(token, sid)
            binding = self.delivery_bindings.get((owner, request_id)) if request_id else None
            if binding:
                if binding[:2] != (sid, session.permission_generation):
                    raise InteropFailure("PERMISSION_DENIED", 403)
                if binding[2] is not None and self._snapshot(session)["source_version"] != binding[2]:
                    raise InteropFailure("SOURCE_CHANGED", 409)
                if len(binding) > 3 and binding[3]:
                    self.provider.validate_chapter_bindings(token, session.scope, binding[3])

    def _bind_delivery(self, session, request_id, source_version=None, chapter_bindings=None):
        key = (session.owner, request_id)
        self.delivery_bindings[key] = (session.id, session.permission_generation, source_version, chapter_bindings)
        while len(self.delivery_bindings) > MAX_REQUESTS: self.delivery_bindings.popitem(last=False)
        if key in self.requests: self.request_sessions[key] = session.id

    def cancel(self, token, request_id, sid=None):
        owner = self._owner(token)
        if sid is not None:
            s = self.sessions.get(sid)
            if s and s.owner != owner: raise InteropFailure("PERMISSION_DENIED", 403)
        key = (owner, request_id)
        task = self.requests.get(key)
        self.seen[key] = "CANCELLED"
        while len(self.seen) > MAX_REQUESTS: self.seen.popitem(last=False)
        if task: task.cancel()
        for session in tuple(self.sessions.values()):
            if session.owner != owner: continue
            if session.event_grant_request_id == request_id:
                self._pause_events(session)
            for preview_id, preview in tuple(session.previews.items()):
                if preview.get("kind") == "event" and preview.get("request_id") == request_id:
                    session.previews.pop(preview_id, None)
        return {"request_id": request_id, "status": "CANCELLED"}

    async def discover(self, token, body):
        owner = self._owner(token); self._enabled(owner)
        transport = self.transport_factory(body.endpoint)
        record = parse_wire(DiscoveryRecord, await transport.request("discovery"))
        self._enabled(owner); self._owner(token)
        self.desktop.owner_states[owner] = "DETECTED"
        self.desktop.record(owner, "DISCOVER")
        return {"request_id": body.request_id, "product": record.model_dump(mode="json"), "trust_level": "UNVERIFIED", "peer_authenticated": False}

    async def connect(self, token, body):
        owner = self._owner(token); self._enabled(owner)
        try:
            if not await self.lifecycle.bridge_start(): raise InteropFailure("TRANSPORT_ERROR", 503)
            return await self.lifecycle.peer_found(body, token=token)
        except (InteropFailure, ProtocolViolation) as exc:
            if exc.code != "CANCELLED" and not any(s.owner == owner for s in self.sessions.values()):
                self.desktop.owner_states[owner] = "DEGRADED"
                self.desktop.owner_errors[owner] = [exc.code]
            raise

    async def _connect(self, token, body):
        owner = self._owner(token); self._enabled(owner)
        epoch = self.connect_epochs.get(owner, 0) + 1
        self.connect_epochs[owner] = epoch
        def pending_guard():
            self._enabled(owner)
            if self.connect_epochs.get(owner) != epoch: raise InteropFailure("CANCELLED", 409)
            self._owner(token)
        scope = body.scope.model_dump()
        if body.project_id is not None and body.project_id != scope["project_id"]: raise InteropFailure("PERMISSION_DENIED", 403)
        if body.surface not in FEATURES: raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404)
        snapshot = self.provider.snapshot(token, scope, module=body.module, surface=body.surface, chapter_id=body.chapter_id, task_id=body.task_id)
        transport = self.transport_factory(body.endpoint)
        nonce = secrets.token_hex(32)
        hello = parse_wire(HelloResult, await transport.request("hello", HandshakeHello(product=self.product, transport="LOOPBACK_HTTP", session_nonce=nonce)))
        pending_guard(); self.provider.authorize(token, scope)
        if hello.session_nonce != nonce or hello.product.product_role != "AI_TUTOR" or PROTOCOL_VERSION not in hello.product.protocol_versions:
            raise InteropFailure("PROTOCOL_INCOMPATIBLE", 409)
        requested = tuple(cap for cap in CAPABILITIES if cap in hello.product.capabilities)
        required = {"project.context.read", "tutor.guidance.request", "tutor.guidance.receive"}
        if not required.issubset(requested): raise InteropFailure("CAPABILITY_NOT_SUPPORTED", 409)
        negotiated = parse_wire(CapabilityNegotiation, await transport.request("negotiate", CapabilityNegotiation(hello_id=hello.hello_id, requested_capabilities=requested)))
        if negotiated.hello_id != hello.hello_id or tuple(negotiated.requested_capabilities) != requested or not required.issubset(negotiated.granted_capabilities):
            raise InteropFailure("CAPABILITY_NOT_SUPPORTED", 409)
        pending_guard(); self.provider.authorize(token, scope)
        opened = parse_wire(SessionOpenResult, await transport.request("session", SessionOpenRequest(hello_id=hello.hello_id, session_nonce=nonce, user_identity=owner)))
        wire = opened.session
        if (wire.product_id != hello.product.product_id or wire.instance_id != hello.product.instance_id or
            wire.peer_product_id != self.product.product_id or wire.peer_instance_id != self.product.instance_id or
            wire.user_identity != owner or wire.nonce != nonce or wire.transport != "LOOPBACK_HTTP" or
            tuple(wire.capabilities) != tuple(negotiated.granted_capabilities) or wire.expires_at <= now() or wire.created_at > now() + timedelta(seconds=5)):
            raise InteropFailure("SESSION_REQUIRED", 401)
        pending_guard()
        latest = self.provider.snapshot(token, scope, module=body.module, surface=body.surface, chapter_id=body.chapter_id, task_id=body.task_id)
        if latest["authorization"] != snapshot["authorization"]: raise InteropFailure("PERMISSION_DENIED", 403)
        if (latest["chapter"] or {}).get("id") != (snapshot["chapter"] or {}).get("id"):
            raise InteropFailure("SOURCE_CHANGED", 409)
        if len(self.sessions) >= MAX_SESSIONS: raise InteropFailure("TIMEOUT", 429)
        session = LocalSession(uid("session"), owner, token, scope, body.module, body.surface, body.chapter_id, body.task_id,
            latest["authorization"], hello.product, wire, opened.session_token, transport)
        session.chapter_identity = (latest["chapter"] or {}).get("id")
        # A changed browser scope replaces only that owner's prior sessions.
        self._revoke_owner(owner)
        self.sessions[session.id] = session
        session.loop = asyncio.get_running_loop()
        session.last_peer_seen = session.loop.time()
        session.pump = asyncio.create_task(self._event_pump(session))
        self.desktop.owner_states[owner] = "UNTRUSTED"
        self.desktop.owner_errors.pop(owner, None)
        self.desktop.record(owner, "CONNECT", session=session)
        return {"request_id": body.request_id, "session_id": session.id, "protocol_session_id": wire.session_id, "product": hello.product.model_dump(mode="json"),
            "capabilities": list(wire.capabilities), "desktop_status": "LOCAL_REQUIRED",
            "mode": "MOCK_ONLY" if "MOCK_ONLY" in hello.product.display_name else "LOCAL_REFERENCE",
            "subscription_active": False, "metadata_fields": []}

    def _snapshot(self, session):
        self._session(session.host_token, session.id)
        snapshot = self.provider.snapshot(session.host_token, session.scope, module=session.module, surface=session.surface,
            chapter_id=session.chapter_id, task_id=session.task_id)
        if (snapshot["chapter"] or {}).get("id") != session.chapter_identity:
            raise InteropFailure("SOURCE_CHANGED", 409)
        return snapshot

    def _capsule(self, session, snapshot, *, content=None, metadata_fields=METADATA_FIELDS, selection_id=None):
        state = dict(snapshot["state"])
        metadata_fields = set(metadata_fields)
        available = self._capabilities(session)
        metadata_fields -= {group for group, cap in {"task": "task.status.read", "error": "task.error.read", "model": "model.registry.read", "runtime": "model.runtime.status.read"}.items() if cap not in available}
        if not metadata_fields.issubset(METADATA_FIELDS): raise InteropFailure("INVALID_MESSAGE", 400)
        for group, fields in {"task": ("task_id", "task_type", "task_status"), "error": ("error_code",), "model": ("model_id",), "runtime": ("runtime_id", "runtime_status")}.items():
            if group not in metadata_fields:
                for key in fields: state[key] = None
        evidence = []
        for key, locator in (("project_version", "project"), ("chapter_version", "chapter"), ("task_status", "task"), ("runtime_status", "runtime")):
            value = state.get(key)
            target = state.get(locator + "_id")
            if value is not None and target:
                evidence.append(ContextEvidence(source_id=key, source_version=snapshot["source_version"], locator=locator + ":" + target,
                    content_hash=digest({key: value}), timestamp=now(), authority="AUTHORITATIVE", privacy="LOCAL_ONLY"))
        content = content or ContextContent()
        return create_capsule(capsule_id=uid("capsule"), source_version=snapshot["source_version"],
            product_id=self.product.product_id, product_version=self.product.product_version, instance_id=self.product.instance_id,
            **state, privacy_scope="LOCAL_ONLY", created_at=now(), expires_at=now() + timedelta(minutes=5),
            evidence=tuple(evidence), content=content, selection_id=selection_id,
            selection_hash=digest(content.text) if selection_id else None)

    def sources(self, token, sid):
        session = self._session(token, sid, "project.context.read")
        entries = self.provider.chapter_entries(session.scope)
        result = [{"id": wire_id, "label": "Chapter " + str(index + 1), "version": row["version"]}
                  for index, (wire_id, row) in enumerate(entries[:64])]
        self._session(token, sid)
        return {"session_id": sid, "items": result, "max_selected": 4}

    def sources_guard(self, token, sid, value):
        if self.sources(token, sid) != value:
            raise InteropFailure("SOURCE_CHANGED", 409)

    def context_preview(self, token, body):
        session = self._session(token, body.session_id, "project.context.read")
        if body.chapter_id is not None and body.chapter_id != session.chapter_id: raise InteropFailure("SOURCE_CHANGED", 409)
        snapshot = self._snapshot(session)
        content = ContextContent()
        bindings = None
        selection_id = None
        if body.content_kind != "NONE":
            self._permission(session, {"SELECTION": "selection", "CHAPTER": "current_chapter", "SPECIFIC_CONTEXT": "specific_context"}[body.content_kind])
            chapter = snapshot["chapter"]
            if body.content_kind in {"SELECTION", "CHAPTER"} and (chapter is None or body.expected_chapter_version != chapter["version"]):
                raise InteropFailure("SOURCE_CHANGED", 409)
            if body.content_kind == "SELECTION":
                self._session(token, session.id, "project.selection.share")
                text = anchor_text(chapter["document"])
                start, end = body.selection_start, body.selection_end
                if start is None or end is None or not 0 <= start < end <= len(text) or end - start > 16384:
                    raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 403)
                text = text[start:end]; selection_id = uid("selection")
                level = "SELECTED_TEXT"
            elif body.content_kind == "CHAPTER":
                text = anchor_text(chapter["document"]); level = "CURRENT_CHAPTER"
            else:
                text, bindings = self.provider.specific_context(token, session.scope, body.context_ids)
                level = "PROJECT_CONTEXT"
            if not text or len(text.encode()) > 65536: raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 413)
            content = ContextContent(level=level, text=text, consent_id=uid("consent"))
        elif body.context_ids or body.selection_start is not None or body.selection_end is not None:
            raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 403)
        capsule = self._capsule(session, snapshot, content=content, metadata_fields=body.metadata_fields, selection_id=selection_id)
        preview_id = uid("preview")
        session.previews[preview_id] = {"kind": "context", "capsule": capsule, "source": snapshot["source_version"], "bindings": bindings, "diagnostic": None, "permission_generation": session.permission_generation}
        while len(session.previews) > MAX_PREVIEWS: session.previews.popitem(last=False)
        self._session(token, session.id)
        self._bind_delivery(session, body.request_id, snapshot["source_version"], bindings)
        return {"request_id": body.request_id, "session_id": session.id, "preview_id": preview_id,
                "capsule": capsule.model_dump(mode="json"), "expires_at": capsule.expires_at.isoformat()}

    def diagnostic_preview(self, token, body):
        session = self._session(token, body.session_id, "diagnostics.read")
        # A minimized diagnostic must not run alongside an older, broader grant.
        self._pause_events(session)
        fields = set(body.fields)
        for field_name, capability in {"error_code": "task.error.read", "task_state": "task.status.read", "runtime": "model.runtime.status.read", "model": "model.registry.read"}.items():
            if field_name in fields: self._session(token, body.session_id, capability)
        if not fields.issubset(DIAGNOSTIC_FIELDS): raise InteropFailure("INVALID_MESSAGE", 400)
        snapshot = self._snapshot(session)
        # The required protocol context envelope has no project/chapter/task
        # information. Both envelopes are returned in the preview, exactly as sent.
        capsule = create_capsule(capsule_id=uid("capsule"), source_version=snapshot["source_version"],
            product_id=self.product.product_id, product_version=self.product.product_version,
            instance_id=self.product.instance_id, module="local-interop", surface="diagnostics",
            created_at=now(), expires_at=now()+timedelta(minutes=5), privacy_scope="LOCAL_ONLY")
        state = snapshot["state"]
        values = {"software_id": self.product.product_id, "software_version": self.product.product_version,
            "feature": session.surface, "error_code": state["error_code"], "task_state": state["task_status"],
            "runtime": state["runtime_id"], "model": state["model_id"],
            "capability_state": tuple(CapabilityState(capability=c, available=True) for c in session.wire_session.capabilities)}
        values = {key: value for key, value in values.items() if key in fields}
        diagnostic = create_diagnostic(diagnostic_id=uid("diagnostic"), source_version=snapshot["source_version"], **values,
            privacy_scope="LOCAL_ONLY", created_at=now(), expires_at=now()+timedelta(minutes=5), evidence=(), sanitized=True)
        preview_id = uid("preview")
        session.previews[preview_id] = {"kind": "diagnostic", "capsule": capsule, "source": snapshot["source_version"], "bindings": None, "diagnostic": diagnostic, "permission_generation": session.permission_generation}
        while len(session.previews) > MAX_PREVIEWS: session.previews.popitem(last=False)
        self._session(token, session.id)
        self._bind_delivery(session, body.request_id, snapshot["source_version"])
        return {"request_id": body.request_id, "session_id": session.id, "preview_id": preview_id,
                "diagnostic": diagnostic.model_dump(mode="json"), "capsule": capsule.model_dump(mode="json"), "expires_at": diagnostic.expires_at.isoformat(),
                "event_subscription_paused": True}

    def _validate_preview(self, session, preview):
        if preview.get("permission_generation", session.permission_generation) != session.permission_generation:
            raise InteropFailure("PERMISSION_DENIED", 403)
        snapshot = self._snapshot(session)
        validate_capsule(preview["capsule"], source_version=snapshot["source_version"])
        if preview["source"] != snapshot["source_version"]: raise InteropFailure("SOURCE_CHANGED", 409)
        if preview["bindings"]:
            _, bindings = self.provider.specific_context(session.host_token, session.scope, list(preview["bindings"]))
            if bindings != preview["bindings"]: raise InteropFailure("SOURCE_CHANGED", 409)
        return snapshot

    async def ask(self, token, body, *, diagnostic=False):
        session = self._session(token, body.session_id, "diagnostics.read" if diagnostic else "tutor.guidance.request")
        if not body.confirmed: raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 403)
        preview = session.previews.pop(body.preview_id, None)
        if preview is None or preview.get("kind") != ("diagnostic" if diagnostic else "context"): raise InteropFailure("CONTEXT_STALE", 409)
        self._validate_preview(session, preview)
        self._bind_delivery(session, body.request_id, preview["source"], preview["bindings"])
        request = TutorRequest(request_id=body.request_id, session_id=session.wire_session.session_id,
            context=preview["capsule"], question=body.question, diagnostic=preview["diagnostic"])
        def guard():
            self._session(token, session.id, "diagnostics.read" if diagnostic else "tutor.guidance.request")
            self._validate_preview(session, preview)
        response = await self.desktop.tutor(session, guard).request(request)
        self._session(token, session.id, "tutor.guidance.receive")
        self._validate_preview(session, preview)
        if response.request_id != request.request_id or response.session_id != request.session_id or response.privacy_scope != "LOCAL_ONLY":
            raise InteropFailure("INVALID_MESSAGE", 502)
        session.guidance[response.guidance_id] = {"guidance": response, "source": preview["source"], "capsule": preview["capsule"]}
        while len(session.guidance) > MAX_PREVIEWS: session.guidance.popitem(last=False)
        return {"request_id": body.request_id, "session_id": session.id, "guidance": response.model_dump(mode="json")}

    async def verify(self, token, body):
        session = self._session(token, body.session_id, "verifier.request")
        stored = session.guidance.get(body.guidance_id)
        if not stored: raise InteropFailure("CONTEXT_STALE", 409)
        condition = stored["guidance"].verification_condition
        capsule = self._capsule(session, self._snapshot(session))
        self._bind_delivery(session, body.request_id, capsule.source_version)
        result = self.desktop.verifier(session, body.request_id, stored["capsule"]).verify(condition, capsule, capsule.evidence)
        # Verification is evaluated here from freshly authorized Host state.
        # No Tutor prose or wire-provided AUTHORITATIVE label is a proof.
        await asyncio.sleep(0)
        self._session(token, session.id, "verifier.result.receive")
        if capsule.source_version != self._snapshot(session)["source_version"]: raise InteropFailure("SOURCE_CHANGED", 409)
        session.results[result.result_id] = {"result": result, "guidance_id": body.guidance_id, "source": capsule.source_version}
        while len(session.results) > MAX_PREVIEWS: session.results.popitem(last=False)
        return {"request_id": body.request_id, "session_id": session.id, "result": result.model_dump(mode="json")}

    def handoff(self, token, body):
        return self.desktop.handoff.handle(token, body)

    def _resolve_handoff(self, token, body):
        session = self._session(token, body.session_id)
        if not body.explicit_click: raise InteropFailure("PERMISSION_DENIED", 403)
        target = body.handoff
        if target.target_product_id != self.product.product_id: raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404)
        snapshot = self._snapshot(session)
        cap = {"OPEN_FEATURE": "handoff.open_feature", "OPEN_PROJECT": "handoff.open_project", "OPEN_CHAPTER": "handoff.open_project", "OPEN_TASK": "handoff.open_task"}.get(target.action)
        if cap is None: raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404)
        self._session(token, session.id, cap)
        if target.source_version and target.source_version != snapshot["source_version"]: raise InteropFailure("CONTEXT_STALE", 409)
        if target.project_id is not None and target.project_id != session.scope["project_id"]: raise InteropFailure("PERMISSION_DENIED", 403)
        route = {"action": target.action, "scope": session.scope}
        chapter_bindings = None
        if target.action == "OPEN_FEATURE":
            if target.feature not in FEATURES: raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404)
            route["feature"] = target.feature
        elif target.action == "OPEN_PROJECT": route["project_id"] = target.project_id
        elif target.action == "OPEN_CHAPTER":
            row = self.provider.chapter(session.scope, target.chapter_id)
            route.update(project_id=session.scope["project_id"], chapter_id=row["id"], chapter_version=row["version"])
            chapter_bindings = {target.chapter_id: self.provider.chapter_binding(row)}
        else:
            # These existing panels own selection internally and expose no
            # task-ID navigation port yet. Feature navigation remains supported.
            if session.surface in {"export", "workflow"}:
                raise InteropFailure("HANDOFF_TARGET_NOT_FOUND", 404)
            row = self.provider.task(token, session.scope, target.task_id)
            route.update(project_id=session.scope["project_id"], task_id=target.task_id, task_kind="generation", task_status=self.provider.task_status(row.get("status")))
        self._session(token, session.id)
        self._bind_delivery(session, body.request_id, snapshot["source_version"], chapter_bindings)
        return {"request_id": body.request_id, "session_id": session.id, "route": route}

    def model_registry(self, token, sid):
        session = self._session(token, sid, "model.registry.read")
        registry = self.desktop.models.snapshot()
        if "model.runtime.status.read" not in self._capabilities(session):
            registry = registry.model_copy(update={"models": tuple(model.model_copy(update={"availability": "UNKNOWN", "last_validated": None}) for model in registry.models)})
        self._session(token, sid)
        return registry.model_dump(mode="json")

    def case_preview(self, token, body):
        return self.desktop.case_gate.preview(token, body)

    def _case_preview(self, token, body):
        session = self._session(token, body.session_id, "case.candidate.create")
        stored = session.results.get(body.result_id)
        if not stored or stored["result"].status != "VERIFIED": raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 403)
        if stored["source"] != self._snapshot(session)["source_version"]: raise InteropFailure("CONTEXT_STALE", 409)
        guide = session.guidance[stored["guidance_id"]]["guidance"]
        candidate = CaseCandidate(candidate_id=uid("case"), problem=guide.summary,
            environment=CaseEnvironment(product_id=self.product.product_id, product_version=self.product.product_version, module=session.module),
            diagnosis=guide.diagnosis, guidance=guide, result=stored["result"].reason, verification=stored["result"],
            software_id=self.product.product_id, software_version=self.product.product_version, evidence=stored["result"].evidence,
            privacy_scope="LOCAL_ONLY", created_at=now())
        session.candidates[candidate.candidate_id] = {"candidate": candidate, "approved": False, "source": stored["source"]}
        while len(session.candidates) > MAX_PREVIEWS: session.candidates.popitem(last=False)
        return {"request_id": body.request_id, "session_id": session.id, "candidate": candidate.model_dump(mode="json"), "gate": "USER_APPROVAL_REQUIRED"}

    def case_approve(self, token, body):
        return self.desktop.case_gate.submit(token, body)

    def _case_approve(self, token, body):
        session = self._session(token, body.session_id, "case.candidate.create")
        item = session.candidates.get(body.candidate_id)
        if not item or not body.confirmed: raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 403)
        if item["source"] != self._snapshot(session)["source_version"]: raise InteropFailure("CONTEXT_STALE", 409)
        item["approved"] = True
        return {"candidate": item["candidate"].model_dump(mode="json"), "gate": "LOCAL_PREVIEW_ONLY", "memory_case_gate": "LOCAL_REQUIRED", "uploaded": False}

    def _event_binding(self, session):
        return digest({"session": session.id, "peer_session": session.wire_session.session_id,
            "peer_product": session.peer.product_id, "peer_instance": session.peer.instance_id,
            "nonce": session.wire_session.nonce, "owner": session.owner, "authorization": session.authorization,
            "scope": session.scope, "chapter": session.chapter_id, "task": session.task_id,
            "module": session.module, "surface": session.surface})

    def _pause_events(self, session):
        for registry, key in ((self.event_sources, "DIRECT_EVENT"), (self.poll_sources, "POLLING")):
            source_id = session.source_subscriptions.pop(key, None)
            if source_id: registry.revoke(source_id)
        session.source_provenance.clear()
        session.event_grant_generation += 1
        session.wake.set()
        session.event_grant_id = None
        session.event_grant_request_id = None
        session.event_grant_binding = None
        session.event_metadata_fields = frozenset()
        session.events.clear()
        session.previous = None
        for preview_id, preview in tuple(session.previews.items()):
            if preview.get("kind") == "event": session.previews.pop(preview_id, None)
        if session.event_dispatch and session.event_dispatch is not current_task():
            session.event_dispatch.cancel()

    def _event_guard(self, session, grant_id, token=None):
        self._session(token or session.host_token, session.id, "project.context.read")
        # Queued metadata/SSE frames still refer to a live, exact owner object.
        # A removed chapter cannot survive in a previously granted event queue.
        chapter = self.provider.chapter(session.scope, session.chapter_id)
        if (chapter or {}).get("id") != session.chapter_identity:
            raise InteropFailure("SOURCE_CHANGED", 409)
        self._permission(session, "standing_metadata_events")
        if not grant_id or session.event_grant_id != grant_id:
            raise InteropFailure("CANCELLED", 409)
        if session.event_grant_binding != self._event_binding(session):
            self._pause_events(session)
            raise InteropFailure("CONTEXT_STALE", 409)

    def event_preview(self, token, body):
        session = self._session(token, body.session_id, "project.context.read")
        self._permission(session, "standing_metadata_events")
        self.delivery_guard(token, session.id, body.request_id)
        self._session(token, body.session_id, "task.status.read")
        self._pause_events(session)
        fields = frozenset(body.metadata_fields)
        if not fields.issubset(METADATA_FIELDS): raise InteropFailure("INVALID_MESSAGE", 400)
        for group, cap in {"task": "task.status.read", "error": "task.error.read", "model": "model.registry.read", "runtime": "model.runtime.status.read"}.items():
            if group in fields: self._session(token, session.id, cap)
        snapshot = self._snapshot(session)
        capsule = self._capsule(session, snapshot, metadata_fields=fields)
        preview_id = uid("event-preview")
        session.previews[preview_id] = {"kind": "event", "request_id": body.request_id,
            "capsule": capsule, "source": snapshot["source_version"], "bindings": None, "diagnostic": None,
            "generation": session.event_grant_generation, "event_binding": self._event_binding(session), "metadata_fields": fields}
        while len(session.previews) > MAX_PREVIEWS: session.previews.popitem(last=False)
        self._session(token, session.id)
        self._bind_delivery(session, body.request_id, snapshot["source_version"])
        return {"request_id": body.request_id, "session_id": session.id, "preview_id": preview_id,
            "capsule": capsule.model_dump(mode="json"), "metadata_fields": sorted(fields),
            "expires_at": capsule.expires_at.isoformat(), "subscription_active": False}

    def event_subscribe(self, token, body):
        session = self._session(token, body.session_id, "project.context.read")
        self._permission(session, "standing_metadata_events")
        self.delivery_guard(token, session.id, body.request_id)
        if not body.confirmed: raise InteropFailure("CONTEXT_NOT_AUTHORIZED", 403)
        preview = session.previews.pop(body.preview_id, None)
        if not preview or preview.get("kind") != "event": raise InteropFailure("CONTEXT_STALE", 409)
        if preview["generation"] != session.event_grant_generation or preview["event_binding"] != self._event_binding(session):
            raise InteropFailure("CONTEXT_STALE", 409)
        self._validate_preview(session, preview)
        session.event_grant_id = uid("subscription")
        session.event_grant_request_id = body.request_id
        session.event_grant_binding = preview["event_binding"]
        session.event_metadata_fields = preview["metadata_fields"]
        grant_id = session.event_grant_id
        def authorize(capsule):
            self._event_guard(session, grant_id)
            return capsule.project_id == session.scope["project_id"] and capsule.chapter_id == session.chapter_id and capsule.content.level == "NONE"
        for registry, key in ((self.event_sources, "DIRECT_EVENT"), (self.poll_sources, "POLLING")):
            session.source_subscriptions[key] = registry.subscribe(session_id=session.wire_session.session_id,
                peer_id=session.id, expires_at=session.wire_session.expires_at, authorize=authorize)
        session.wake.set()
        self.desktop.record(session.owner, "SUBSCRIBE", session=session)
        return {"request_id": body.request_id, "session_id": session.id,
            "subscription_id": session.event_grant_id, "subscription_active": True,
            "metadata_fields": sorted(session.event_metadata_fields)}

    def event_unsubscribe(self, token, body):
        session = self._session(token, body.session_id)
        self._pause_events(session)
        return {"request_id": body.request_id, "session_id": session.id,
            "subscription_active": False, "metadata_fields": []}

    async def _event_pump(self, session):
        idle_delay = self.event_interval
        try:
            while not session.revoked:
                self._session(session.host_token, session.id)
                # Connection itself authorizes only protocol liveness. No source
                # capture, event queue or publication exists before explicit grant.
                if session.event_grant_id:
                    changed = self.capture_event(session.host_token, session.id)
                    idle_delay = self.event_interval if changed else min(5.0, idle_delay * 2)
                    grant_id = session.event_grant_id
                    pending = tuple(event for event in session.events if event.sequence > session.sent_sequence)
                    for event in pending:
                        self._event_guard(session, grant_id)
                        dispatch = asyncio.create_task(session.transport.request("events", event,
                            token=session.peer_token, before_send=lambda grant_id=grant_id: self._event_guard(session, grant_id)))
                        session.event_dispatch = dispatch
                        try:
                            acknowledgement = parse_wire(InteropEvent, await dispatch)
                            self._event_guard(session, grant_id)
                        except (asyncio.CancelledError, InteropFailure):
                            if not session.revoked and session.event_grant_id != grant_id:
                                break  # Explicit pause cancels data, not the connection.
                            raise
                        finally:
                            if session.event_dispatch is dispatch: session.event_dispatch = None
                        if acknowledgement != event: raise InteropFailure("INVALID_MESSAGE", 502)
                        session.sent_sequence = event.sequence
                        session.last_peer_seen = asyncio.get_running_loop().time()
                if asyncio.get_running_loop().time() - session.last_peer_seen >= 10:
                    session.heartbeat_sequence += 1
                    heartbeat = Heartbeat(session_id=session.wire_session.session_id, sequence=session.heartbeat_sequence, created_at=now())
                    self._session(session.host_token, session.id)
                    acknowledged = parse_wire(Heartbeat, await session.transport.request("heartbeat", heartbeat, token=session.peer_token))
                    self._session(session.host_token, session.id)
                    if acknowledged != heartbeat: raise InteropFailure("SESSION_REVOKED", 401)
                    session.last_peer_seen = asyncio.get_running_loop().time()
                try:
                    await asyncio.wait_for(session.wake.wait(), timeout=idle_delay if session.event_grant_id else 5.0)
                    session.wake.clear()
                    idle_delay = self.event_interval
                except TimeoutError:
                    pass
        except (InteropFailure, asyncio.CancelledError):
            if not session.revoked:
                self._revoke(session)
                self.desktop.owner_states[session.owner] = "DEGRADED"
                self.desktop.owner_errors[session.owner] = ["TRANSPORT_ERROR"]
        except Exception:  # noqa: BLE001 - isolate background bridge/source failures
            self._revoke(session)
            self.desktop.owner_states[session.owner] = "DEGRADED"
            self.desktop.owner_errors[session.owner] = ["TRANSPORT_ERROR"]

    def capture_event(self, token, sid, *, provenance="POLLING"):
        session = self._session(token, sid, "project.context.read")
        if not session.event_grant_id: return None
        self._event_guard(session, session.event_grant_id)
        snapshot = self._snapshot(session)
        capsule = self._capsule(session, snapshot, metadata_fields=session.event_metadata_fields)
        # Change detection and event names use only the approved projection.
        # Omitted task/model/error fields cannot leak via event names or timing.
        state = {key: getattr(capsule, key) for key in snapshot["state"]}
        previous = session.previous
        if previous and previous["state"] == state: return None
        event_type = "PROJECT_OPENED" if previous is None else "TASK_UPDATED"
        if previous:
            old = previous["state"]
            if state["task_status"] != old["task_status"]:
                event_type = {"FAILED": "TASK_FAILED", "COMPLETED": "TASK_COMPLETED", "CANCELLED": "TASK_CANCELLED", "RUNNING": "TASK_STARTED"}.get(state["task_status"], "TASK_UPDATED")
            elif state["model_id"] != old["model_id"]: event_type = "MODEL_CHANGED"
            elif state["runtime_status"] != old["runtime_status"]: event_type = {"READY": "RUNTIME_AVAILABLE", "UNKNOWN": "VALIDATION_REQUIRED"}.get(state["runtime_status"], "RUNTIME_UNAVAILABLE")
            elif state["chapter_version"] != old["chapter_version"]: event_type = "CHAPTER_OPENED"
        module = "TASK" if event_type.startswith("TASK_") else "CHAPTER" if event_type == "CHAPTER_OPENED" else "MODEL" if event_type == "MODEL_CHANGED" else "RUNTIME" if event_type.startswith("RUNTIME_") or event_type == "VALIDATION_REQUIRED" else "PROJECT"
        if module == "TASK" and session.surface in {"export", "workflow"}: module = session.surface.upper()
        registry = self.event_sources if provenance == "DIRECT_EVENT" else self.poll_sources
        source_id = session.source_subscriptions.get(provenance)
        if not source_id: return None
        registry.publish(module, event_type, capsule, subscription_id=source_id)
        projected = registry.drain(source_id)
        if not projected: return None
        capsule = projected[-1].event.context
        self._event_guard(session, session.event_grant_id)
        session.sequence += 1
        event = InteropEvent(event_id=uid("event"), session_id=session.wire_session.session_id, sequence=session.sequence,
            event_type=event_type, created_at=now(), context=capsule)
        # Coalesce high frequency same-kind metadata, retaining terminal changes.
        if event_type == "TASK_UPDATED" and session.events and session.events[-1].event_type == event_type: session.events.pop()
        session.events.append(event)
        session.source_provenance[event.event_id] = provenance
        for key in tuple(session.source_provenance):
            if not any(item.event_id == key for item in session.events): session.source_provenance.pop(key, None)
        session.previous = {"state": state, "source_version": snapshot["source_version"]}
        self._session(token, sid)
        return event

    def events(self, token, sid, after=0, *, capture=True):
        session = self._session(token, sid, "project.context.read")
        if capture: self.capture_event(token, sid)
        # Per-subscriber cursors: reading never consumes another subscriber's data.
        events = [event.model_dump(mode="json") for event in session.events if event.sequence > after]
        self._session(token, sid)
        return {"session_id": sid, "events": events, "sequence": session.sequence,
            "subscription_active": bool(session.event_grant_id), "metadata_fields": sorted(session.event_metadata_fields),
            "evidence": [{"event_id": item["event_id"], "provenance": session.source_provenance.get(item["event_id"], "POLLING")} for item in events]}

    def disconnect(self, token, sid):
        owner = self._owner(token)
        session = self.sessions.get(sid)
        if session and session.owner != owner: raise InteropFailure("PERMISSION_DENIED", 403)
        if session: self._revoke(session)
        return {"session_id": sid, "status": "DISCONNECTED"}

    def _capabilities(self, session):
        revoked = {cap for permission in session.revoked_permissions for cap in PERMISSIONS[permission][1]}
        return set(session.wire_session.capabilities) - revoked

    @staticmethod
    def _permission(session, permission):
        if permission in session.revoked_permissions:
            raise InteropFailure("PERMISSION_DENIED", 403)

    def permission_revoke(self, token, body):
        session = self._session(token, body.session_id)
        if body.permission_id not in PERMISSIONS: raise InteropFailure("INVALID_MESSAGE", 400)
        session.revoked_permissions.add(body.permission_id)
        session.permission_generation += 1
        # No old preview or late response can survive a changed consent scope.
        session.previews.clear(); session.guidance.clear(); session.results.clear(); session.candidates.clear()
        self._pause_events(session)
        for key, sid in tuple(self.request_sessions.items()):
            if sid == session.id:
                self.seen[key] = "CANCELLED"
                task = self.requests.get(key)
                if task and task is not current_task(): task.cancel()
        self.desktop.record(session.owner, "REVOKE", session=session, permission_id=body.permission_id)
        return {"request_id": body.request_id, "session_id": session.id, "permission_id": body.permission_id,
            "status": "REVOKED", "permissions": self.desktop.permissions(session),
            "desktop": self.desktop.snapshot(session.owner, [session])}

    async def disconnect_revoke(self, token, body):
        owner = self._owner(token)
        session = self.sessions.get(body.session_id) or self.closed_sessions.get(body.session_id)
        if session is None: raise InteropFailure("SESSION_REVOKED", 401)
        if session.owner != owner: raise InteropFailure("PERMISSION_DENIED", 403)
        already_revoked = session.revoked
        self._revoke(session)  # Revoke local authority before any peer round trip.
        if already_revoked and not session.transport_disconnected and (session.closing_task is None or session.closing_task.done()):
            session.closing_task = asyncio.create_task(self._close_local_transport(session))
            self.closing_tasks.add(session.closing_task)
            session.closing_task.add_done_callback(self.closing_tasks.discard)
        if session.closing_task:
            _, pending = await asyncio.wait({session.closing_task}, timeout=.55)
            for task in pending:
                session.transport_close_state = "TIMEOUT"
                task.cancel()
        return {"request_id": body.request_id, "session_id": body.session_id, "status": "DISCONNECTED" if session.transport_disconnected else "UNKNOWN", "revoked": True,
            "subscriptions_stopped": True, "pending_cancelled": True, "standing_grants_cleared": True,
            "transport_disconnected": session.transport_disconnected, "transport_close_state": session.transport_close_state,
            "peer_disconnect_acknowledged": session.peer_disconnect_acknowledged}

    async def _close_peer(self, session, peer_token):
        try:
            async with asyncio.timeout(.25):
                request = CancelRequest(request_id=uid("disconnect"), session_id=session.wire_session.session_id)
                response = parse_wire(CancelResult, await session.transport.request("disconnect", request, token=peer_token))
                session.peer_disconnect_acknowledged = response.request_id == request.request_id and response.session_id == request.session_id
        except (Exception, asyncio.CancelledError):  # noqa: BLE001,S110 - remote ACK is optional and cannot restore local authority
            pass
        finally:
            await self._close_local_transport(session)

    async def _close_local_transport(self, session):
        close = getattr(session.transport, "shutdown", None)
        if close:
            try:
                result = close()
                if __import__("inspect").isawaitable(result):
                    async with asyncio.timeout(.25): result = await result
                session.transport_disconnected = result is True
                session.transport_close_state = "CLOSED" if result is True else "UNKNOWN"
            except (TimeoutError, asyncio.CancelledError):
                session.transport_close_state = "TIMEOUT"
            except Exception:  # noqa: BLE001 - optional platform close must not block application exit
                session.transport_close_state = "FAILED"
        if not any(s.owner == session.owner for s in self.sessions.values()):
            self.desktop.owner_states[session.owner] = "DISCONNECTED" if session.transport_disconnected else "DEGRADED" if session.transport_close_state in {"FAILED", "TIMEOUT"} else "UNKNOWN"

    def _on_runtime_change(self, change):
        if self.closed: return
        for session in tuple(self.sessions.values()):
            if session.revoked or not session.event_grant_id or session.scope["project_id"] != change.project_id: continue
            if change.module == "CHAPTER" and change.entity_id != session.chapter_identity: continue
            if change.module == "TASK" and (change.entity_id != session.task_id or not session.event_metadata_fields): continue
            loop = session.loop
            if loop is None or loop.is_closed(): continue
            key = (session.id, change.module)
            if key in self.pending_changes: continue
            self.pending_changes.add(key)
            def project(session=session, key=key):
                self.pending_changes.discard(key)
                try:
                    if session.revoked or not session.event_grant_id: return
                    self.capture_event(session.host_token, session.id, provenance="DIRECT_EVENT")
                    session.wake.set()
                except InteropFailure:
                    if not session.revoked: self._revoke(session)
                except Exception:  # noqa: BLE001 - one source failure cannot stop the product or another peer
                    # Main program and other peers remain available.
                    if not session.revoked: self._pause_events(session)
            loop.call_soon_threadsafe(project)

    async def shutdown(self, timeout=1.0):
        self.closed = True
        if self._unsubscribe_runtime:
            self._unsubscribe_runtime(); self._unsubscribe_runtime = None
        tasks = [s.pump for s in self.sessions.values() if s.pump]
        for session in tuple(self.sessions.values()): self._revoke(session)
        for task in tuple(self.requests.values()):
            if task is not current_task():
                task.cancel()
                tasks.append(task)
        tasks.extend(self.closing_tasks)
        tasks = list({task for task in tasks if task is not current_task()})
        if tasks:
            # asyncio.wait is bounded even for an uncooperative cancellation
            # target; wait_for(gather) would wait for that target to terminate.
            _, pending = await asyncio.wait(tasks, timeout=max(0.0, min(float(timeout), 2.0)))
            for task in pending: task.cancel()
        self.event_sources.shutdown(); self.poll_sources.shutdown()
        self.enabled_owners.clear(); self.requests.clear(); self.seen.clear(); self.connect_epochs.clear()
        self.request_sessions.clear(); self.delivery_bindings.clear()
        self.desktop.handoff.presence.clear()
        self.pending_changes.clear()
