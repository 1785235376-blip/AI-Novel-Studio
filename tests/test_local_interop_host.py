"""MOCK_ONLY peer, real File repositories/session/membership/scope authorization.

The separate two-process suite owns live HTTP evidence; these tests isolate
permission/consent/state races without model or external network activity.
"""
from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.actor_context import SessionContext
from app.authorization import (
    AuthorizationScope,
    ModalityDomain,
    PermissionAssignment,
    ScopeKind,
)
from app.collaboration import Branch, Storyline, Workspace
from app.collaboration_api import CollaborationReadService
from app.config import Settings
from app.identity import IdentityStatus, User, WorkspaceMembership
from app.local_interop.api import (
    AskInput,
    ConnectInput,
    ContextPreviewInput,
    DiagnosticPreviewInput,
    HandoffInput,
    VerifyInput,
    create_local_interop_router,
)
from app.local_interop.errors import InteropFailure
from app.local_interop.host import LocalInteropHost
from app.local_interop.provider import InteropContextProvider, anchor_text
from app.local_interop.synthetic_tutor import SyntheticTutor, create_synthetic_tutor_app
from app.local_interop.transport import assert_endpoint
from app.repositories.factory import create_repository_bundle
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.identity_service import IdentityService
from app.services.membership_authorization_service import MembershipAuthorizationService
from app.trusted_sessions import TrustedSessionResolver
from local_interop_protocol import (
    HandoffTarget,
    ProtocolViolation,
    VerificationCondition,
    canonical_hash,
)


@pytest.fixture(params=[
    pytest.param("file", marks=pytest.mark.file_backend_only),
    pytest.param("postgres", marks=pytest.mark.postgres_backend_only),
])
def env(request, tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "local_tutor_interop_v1")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    backend = request.param
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "") if backend == "postgres" else ""
    if backend == "postgres" and not url: pytest.fail("real PostgreSQL interop requires TEST_POSTGRES_DATABASE_URL")
    suffix = uuid4().hex
    project_id = "interop-" + suffix
    workspace_id, storyline_id, branch_id, other_branch_id = (prefix + suffix for prefix in ("w-", "s-", "b-", "other-"))
    actor_ids = {name: name + "-" + suffix for name in ("author", "reader")}
    permission_ids = {name: "read-" + actor_ids[name] for name in actor_ids}
    config = Settings(storage_backend=backend, database_url=url, novel_data=tmp_path, mock_provider=True, enable_cloud=False)
    bundle = create_repository_bundle(config, data_root=tmp_path)
    project = bundle.novels.create({"id": project_id, "title": "Synthetic book"})
    chapter = bundle.chapters.create(project_id, {"title": "Gate", "content": "Synthetic text 😀\nNo private novel."})
    chapter = bundle.chapters.get(chapter["id"])
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    scopes.create_workspace(Workspace(workspace_id, "Synthetic"))
    scopes.link_project(workspace_id, project_id)
    scopes.create_storyline(Storyline(storyline_id, workspace_id, project_id, "Main"))
    scopes.create_branch(Branch(branch_id, workspace_id, project_id, storyline_id, "Main"))
    scopes.create_branch(Branch(other_branch_id, workspace_id, project_id, storyline_id, "Other"))
    identity = IdentityService(bundle.identity, scopes)
    authorization = AuthorizationService(bundle.authorization, scopes)
    membership = MembershipAuthorizationService(identity, authorization)
    sessions = TrustedSessionResolver()
    scope = {"workspace_id": workspace_id, "project_id": project_id, "storyline_id": storyline_id, "branch_id": branch_id}
    auth_scope = AuthorizationScope(ScopeKind.BRANCH, **scope)
    for actor in ("author", "reader"):
        identity.create_user(User(actor_ids[actor], actor))
        identity.add_membership(WorkspaceMembership("member-" + actor_ids[actor], actor_ids[actor], workspace_id))
        sessions.register(actor, SessionContext("host-" + actor_ids[actor], "client-" + actor_ids[actor], actor_ids[actor], workspace_id))
        authorization.assign_permission(PermissionAssignment(permission_ids[actor], actor_ids[actor], "domain.read", ModalityDomain.NOVEL, auth_scope, actor_ids["author"]))
    collaboration = CollaborationReadService(sessions=sessions, membership_authorization=membership,
        identity=identity, authorization=authorization, scopes=scopes, chapters=bundle.chapters,
        generations=bundle.generations, lore_repository=bundle.lore, novels=bundle.novels)
    peer = SyntheticTutor()
    tutor_app = create_synthetic_tutor_app(peer)
    recorded = []
    class InProcessTransport:
        def __init__(self, endpoint): assert_endpoint(endpoint)
        async def request(self, operation, message=None, *, token=None):
            recorded.append((operation, message, token))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tutor_app, client=("127.0.0.1", 41000)), base_url="http://127.0.0.1") as client:
                response = await client.request("GET" if operation == "discovery" else "POST", "/interop/v1/" + operation,
                    json=message.model_dump(mode="json") if message is not None else None,
                    headers={"Authorization": "Bearer " + token} if token else {})
            if response.status_code >= 400: raise InteropFailure(response.json()["code"], response.status_code)
            return response.content
    host = LocalInteropHost(InteropContextProvider(collaboration), transport_factory=InProcessTransport, event_interval=.05)
    e = SimpleNamespace(**locals())
    def body(**extra):
        return ConnectInput(request_id=uuid4().hex, endpoint="http://127.0.0.1:41000", scope=scope,
                            project_id=project_id, module="NOVEL", surface="editor", chapter_id=chapter["id"], **extra)
    e.body = body
    async def connect(token="author", **extra):
        host.configure(token, True)
        b = body(**extra)
        result = await host.run(token, b.request_id, lambda: host.connect(token, b))
        return result["session_id"]
    e.connect = connect
    yield e
    if backend == "postgres":
        try: bundle.novels.delete(project_id)
        finally: bundle.novels.database.engine.dispose()


def run(test): return asyncio.run(test())


def test_real_authorization_metadata_preview_and_explicit_selection(env):
    e = env
    async def scenario():
        sid = await e.connect()
        result = e.host.context_preview("author", ContextPreviewInput(session_id=sid))
        capsule = result["capsule"]
        assert capsule["content"] == {"level": "NONE", "text": None, "consent_id": None}
        assert "Synthetic text" not in json.dumps(capsule)
        assert capsule["project_id"] == e.project_id
        preview = e.host.context_preview("author", ContextPreviewInput(session_id=sid, chapter_id=e.chapter["id"],
            expected_chapter_version=e.chapter["version"], content_kind="SELECTION", selection_start=0, selection_end=9))
        assert preview["capsule"]["content"]["text"] == anchor_text(e.chapter["document"])[:9]
        assert preview["capsule"]["selection_hash"] == canonical_hash(preview["capsule"]["content"]["text"])
        assert not any(op == "tutor" for op, _, _ in e.recorded)
        body = AskInput(session_id=sid, preview_id=preview["preview_id"], confirmed=False)
        with pytest.raises(InteropFailure, match="CONTEXT_NOT_AUTHORIZED"): await e.host.ask("author", body)
        body = body.model_copy(update={"confirmed": True})
        answer = await e.host.ask("author", body)
        assert answer["guidance"]["authority"] == "ADVISORY"
        assert "MOCK_ONLY" in answer["guidance"]["summary"]
        assert e.bundle.chapters.get(e.chapter["id"])["version"] == e.chapter["version"]
        with pytest.raises(InteropFailure, match="CONTEXT_STALE"): await e.host.ask("author", body)
        await e.host.shutdown()
    run(scenario)


@pytest.mark.parametrize("change", ["chapter", "document-same-version", "project"])
def test_preview_stale_source_fails_closed(env, change):
    e = env
    async def scenario():
        sid = await e.connect()
        preview = e.host.context_preview("author", ContextPreviewInput(session_id=sid, expected_chapter_version=e.chapter["version"], content_kind="CHAPTER"))
        if change == "chapter":
            e.bundle.chapters.save(e.chapter["id"], {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "New text"}]}]}, e.chapter["version"])
        elif change == "project": e.bundle.novels.update(e.project_id, {"title": "Changed metadata"})
        else:
            # A malformed same-version write cannot bypass the document hash.
            if e.backend == "file":
                _, _, path = e.bundle.chapters._paths(e.chapter["id"])
                row = json.loads(path.read_text()); row["document"]["content"][0]["content"][0]["text"] = "Same version tampered"
                path.write_text(json.dumps(row))
            else:
                from app.repositories.postgres.common import chapter_or_raise
                with e.bundle.chapters.database.session() as session:
                    _, row = chapter_or_raise(session, e.chapter["id"])
                    document = json.loads(json.dumps(row.document))
                    document["content"][0]["content"][0]["text"] = "Same version tampered"
                    row.document = document
        with pytest.raises((InteropFailure, ProtocolViolation)) as error:
            await e.host.ask("author", AskInput(session_id=sid, preview_id=preview["preview_id"], confirmed=True))
        assert error.value.code in {"SOURCE_CHANGED", "CONTEXT_STALE"}
        assert not any(op == "tutor" for op, _, _ in e.recorded)
        await e.host.shutdown()
    run(scenario)


@pytest.mark.parametrize("change", ["session", "membership", "permission", "branch", "disabled", "acceptance"])
def test_revocation_stops_old_events_independent_reader_survives(env, monkeypatch, change):
    e = env
    async def scenario():
        first, second = await e.connect(), await e.connect("reader")
        assert e.host.events("author", first)["events"]
        assert e.host.events("reader", second)["events"]
        if change == "session": e.sessions.revoke("author")
        elif change == "membership": e.identity.set_membership_status(e.actor_ids["author"], e.workspace_id, IdentityStatus.INACTIVE)
        elif change == "permission": e.authorization.revoke_permission(e.permission_ids["author"], e.actor_ids["author"])
        elif change == "branch":
            # Session binds to exact authority fingerprint, not just any readable branch.
            e.host.sessions[first].scope = {**e.scope, "branch_id": e.other_branch_id}
        elif change == "disabled": e.host.configure("author", False)
        else: monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
        with pytest.raises(InteropFailure): e.host.events("author", first)
        if change != "acceptance": assert e.host.events("reader", second)["events"]
        else:
            with pytest.raises(InteropFailure): e.host.events("reader", second)
        await e.host.shutdown()
        assert not e.host.sessions and not e.host.enabled_owners
    run(scenario)


def test_project_scope_cannot_be_borrowed(env):
    e = env
    async def scenario():
        e.host.configure("author", True)
        body = e.body().model_copy(update={"scope": e.body().scope.model_copy(update={"branch_id": e.other_branch_id})})
        with pytest.raises(InteropFailure, match="PERMISSION_DENIED"): await e.host.connect("author", body)
        assert not e.recorded
        await e.host.shutdown()
    run(scenario)


def test_diagnostic_allowlist_and_removed_fields_not_smuggled(env):
    e = env
    async def scenario():
        sid = await e.connect()
        preview = e.host.diagnostic_preview("author", DiagnosticPreviewInput(session_id=sid, fields=[]))
        assert preview["diagnostic"]["feature"] is None
        assert preview["diagnostic"]["software_id"] is None
        assert preview["capsule"]["project_id"] is None
        assert preview["capsule"]["chapter_id"] is None
        assert "Synthetic text" not in json.dumps(preview)
        await e.host.ask("author", AskInput(session_id=sid, preview_id=preview["preview_id"], confirmed=True), diagnostic=True)
        sent = next(msg for op, msg, _ in e.recorded if op == "diagnostics")
        assert sent.context.model_dump(mode="json") == preview["capsule"]
        assert sent.diagnostic.model_dump(mode="json") == preview["diagnostic"]
        await e.host.shutdown()
    run(scenario)


def test_case_and_verifier_only_accept_real_current_task_state(env):
    e = env
    task = {"id": "task-" + e.suffix, "novel_id": e.project_id, "chapter_id": e.chapter["id"], "actor_id": e.actor_ids["author"], "workspace_id": e.workspace_id,
            "scope": {"kind": "BRANCH", **e.scope}, "operation": "continue", "status": "FAILED", "error_code": "SYNTHETIC_ERROR", "updated_at": "1"}
    e.bundle.generations.save(task)
    original = e.peer.guidance
    def guidance(request):
        return original(request).model_copy(update={"verification_condition": VerificationCondition(field="task_status", expected_value="COMPLETED", source_id="task_status")})
    e.peer.guidance = guidance
    async def scenario():
        sid = await e.connect(task_id=task["id"])
        preview = e.host.context_preview("author", ContextPreviewInput(session_id=sid))
        answer = await e.host.ask("author", AskInput(session_id=sid, preview_id=preview["preview_id"], confirmed=True))
        verify = VerifyInput(session_id=sid, guidance_id=answer["guidance"]["guidance_id"])
        result = await e.host.verify("author", verify)
        assert result["result"]["status"] == "FAILED"
        assert e.bundle.generations.get(task["id"])["status"] == "FAILED"
        task.update(status="COMPLETED", updated_at="2"); e.bundle.generations.save(task)
        result = await e.host.verify("author", verify)
        assert result["result"]["status"] == "VERIFIED"
        assert result["result"]["evidence"][0]["authority"] == "AUTHORITATIVE"
        from app.local_interop.api import CaseApproveInput, CasePreviewInput
        preview = e.host.case_preview("author", CasePreviewInput(session_id=sid, result_id=result["result"]["result_id"]))
        assert preview["candidate"]["privacy_scope"] == "LOCAL_ONLY"
        with pytest.raises(InteropFailure): e.host.case_approve("author", CaseApproveInput(session_id=sid, candidate_id=preview["candidate"]["candidate_id"], confirmed=False))
        approved = e.host.case_approve("author", CaseApproveInput(session_id=sid, candidate_id=preview["candidate"]["candidate_id"], confirmed=True))
        assert approved["uploaded"] is False and approved["memory_case_gate"] == "LOCAL_REQUIRED"
        await e.host.shutdown()
    run(scenario)


def test_handoff_requires_click_exists_scope_and_source(env):
    e = env
    async def scenario():
        sid = await e.connect()
        target = HandoffTarget(action="OPEN_FEATURE", target_product_id="poemseed.creative.studio", feature="model-center")
        body = HandoffInput(session_id=sid, handoff=target, explicit_click=False)
        with pytest.raises(InteropFailure, match="PERMISSION_DENIED"): e.host.handoff("author", body)
        assert e.host.handoff("author", body.model_copy(update={"explicit_click": True}))["route"]["feature"] == "model-center"
        for changed in ({"target_product_id": "other.product"}, {"feature": "run-model"}):
            with pytest.raises(InteropFailure, match="HANDOFF_TARGET_NOT_FOUND"):
                e.host.handoff("author", body.model_copy(update={"explicit_click": True, "handoff": target.model_copy(update=changed)}))
        capsule = e.host.context_preview("author", ContextPreviewInput(session_id=sid))["capsule"]
        for chapter, code in ((e.project_id + ":999", "HANDOFF_TARGET_NOT_FOUND"),):
            target = HandoffTarget(action="OPEN_CHAPTER", target_product_id="poemseed.creative.studio", chapter_id=chapter, source_version=capsule["source_version"])
            with pytest.raises(InteropFailure, match=code): e.host.handoff("author", HandoffInput(session_id=sid, handoff=target, explicit_click=True))
        await e.host.shutdown()
    run(scenario)


@pytest.mark.parametrize("endpoint", ["http://0.0.0.0:9", "http://localhost:9", "http://192.168.1.1:9", "https://127.0.0.1:9", "http://127.0.0.1:9/?token=hidden", "http://x:y@127.0.0.1:9", "http://127.0.0.1:9/#fragment", "http://[::1]:9"])
def test_transport_rejects_nonliteral_loopback_and_url_credentials(endpoint):
    with pytest.raises(InteropFailure, match="TRANSPORT_ERROR"): assert_endpoint(endpoint)


def test_cancellation_during_handshake_and_late_reply_isolation(env):
    e = env
    async def scenario():
        gate = asyncio.Event()
        original = e.host.transport_factory
        class Delayed(original):
            async def request(self, operation, message=None, *, token=None):
                if operation == "hello": await gate.wait()
                return await super().request(operation, message, token=token)
        e.host.transport_factory = Delayed
        e.host.configure("author", True)
        body = e.body()
        pending = asyncio.create_task(e.host.run("author", body.request_id, lambda: e.host.connect("author", body)))
        await asyncio.sleep(.01)
        e.host.cancel("author", body.request_id)
        with pytest.raises(InteropFailure, match="CANCELLED"): await pending
        gate.set()
        assert not e.host.sessions
        e.host.transport_factory = original
        sid = await e.connect()
        assert sid in e.host.sessions
        with pytest.raises(InteropFailure, match="CANCELLED"):
            await e.host.run("author", body.request_id, lambda: e.host.connect("author", body))
        await e.host.shutdown()
    run(scenario)


def test_browser_routes_live_auth_unknown_fields_and_acceptance_off(env, monkeypatch):
    e = env
    app = FastAPI(); app.include_router(create_local_interop_router(e.host))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 123)), base_url="http://127.0.0.1") as client:
            prefix = "/api/local-interop"
            assert (await client.get(prefix + "/status")).status_code == 401
            client.headers["X-Session-Token"] = "author"
            assert (await client.get(prefix + "/status")).json()["enabled"] is False
            bad = await client.post(prefix + "/settings", json={"enabled": True, "api_key": "SYNTHETIC_SECRET"})
            assert bad.status_code == 400 and "SYNTHETIC_SECRET" not in bad.text
            assert (await client.post(prefix + "/settings", json={"enabled": True})).json()["enabled"] is True
            connected = await client.post(prefix + "/connect", json=e.body().model_dump(mode="json"))
            assert connected.status_code == 200, connected.text
            sid = connected.json()["session_id"]
            preview = await client.post(prefix + "/context/preview", json={"session_id": sid})
            assert preview.status_code == 200, preview.text
            assert (await client.get(prefix + "/events", params={"session_id": sid, "token": "bad"})).status_code == 400
            monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
            assert (await client.get(prefix + "/status")).json()["enabled"] is False
            assert (await client.post(prefix + "/settings", json={"enabled": True})).status_code == 403
        await e.host.shutdown()
    run(scenario)


def test_anchor_text_includes_nested_blocks_hardbreak_and_unicode():
    doc = {"type": "doc", "content": [{"type": "heading", "content": [{"type": "text", "text": "标题"}]}, {"type": "blockquote", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "甲"}, {"type": "hardBreak"}, {"type": "text", "text": "乙😀"}]}]}]}
    assert anchor_text(doc) == "标题\n甲\n乙😀"


def test_peer_event_cursor_independent_and_queue_bounded(env):
    e = env
    async def scenario():
        sid = await e.connect()
        first = e.host.events("author", sid)
        first_again = e.host.events("author", sid)
        assert first_again == first
        # Polling first must not steal the peer's initial event.
        await asyncio.sleep(.12)
        session = e.host.sessions[sid]
        assert e.peer.event_sequences[session.wire_session.session_id] == first["sequence"]
        for i in range(45):
            row = e.bundle.chapters.get(e.chapter["id"])
            e.bundle.chapters.save(e.chapter["id"], {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": f"Synthetic revision {i}"}]}]}, row["version"])
            e.host.events("author", sid)
        assert len(session.events) == 32
        assert e.host.events("author", sid, after=session.sequence)["events"] == []
        assert e.host.events("author", sid, after=0)["events"]
        await e.host.shutdown()
        assert session.events == __import__("collections").deque()
    run(scenario)


@pytest.mark.parametrize("change", ["membership", "chapter", "session-replaced", "cancel"])
def test_pending_guidance_cannot_cross_revocation_or_source_change(env, change):
    e = env
    async def scenario():
        original = e.host.transport_factory
        entered, release = asyncio.Event(), asyncio.Event()
        class Delayed(original):
            async def request(self, operation, message=None, *, token=None):
                result = await super().request(operation, message, token=token)
                if operation == "tutor": entered.set(); await release.wait()
                return result
        e.host.transport_factory = Delayed
        sid = await e.connect()
        preview = e.host.context_preview("author", ContextPreviewInput(session_id=sid))
        body = AskInput(session_id=sid, preview_id=preview["preview_id"], confirmed=True)
        pending = asyncio.create_task(e.host.run("author", body.request_id, lambda: e.host.ask("author", body)))
        await entered.wait()
        if change == "membership": e.identity.set_membership_status(e.actor_ids["author"], e.workspace_id, IdentityStatus.INACTIVE)
        elif change == "chapter":
            e.bundle.chapters.save(e.chapter["id"], {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Changed source"}]}]}, e.chapter["version"])
        elif change == "session-replaced":
            e.host.transport_factory = original
            await e.connect()
        else: e.host.cancel("author", body.request_id, sid)
        release.set()
        with pytest.raises((InteropFailure, ProtocolViolation)): await pending
        assert not any(s.guidance for s in e.host.sessions.values())
        await e.host.shutdown()
    run(scenario)


def test_json_and_sse_final_send_recheck_real_authority(env):
    from app.local_interop.api import AuthorityEventResponse, AuthorityJSONResponse
    e = env
    async def scenario():
        sid = await e.connect()
        sent = []
        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.start": e.sessions.revoke("author")
        async def receive(): await asyncio.sleep(10)
        response = AuthorityJSONResponse({"private": "SYNTHETIC_PROSE_MUST_NOT_ESCAPE"}, lambda: e.host._session("author", sid))
        await response({"type": "http"}, receive, send)
        bodies = b"".join(item.get("body", b"") for item in sent)
        assert b"SYNTHETIC_PROSE_MUST_NOT_ESCAPE" not in bodies
        assert json.loads(bodies)["code"] == "SESSION_REQUIRED"
        e.sessions.register("author", SessionContext("host-" + e.actor_ids["author"], "client-" + e.actor_ids["author"], e.actor_ids["author"], e.workspace_id))
        sid = await e.connect()
        sent.clear()
        async def frames(): yield b"data: SYNTHETIC_PROSE_MUST_NOT_ESCAPE\n\n"
        response = AuthorityEventResponse(frames(), lambda: e.host._session("author", sid))
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
        assert all(not item.get("body") for item in sent)
        await e.host.shutdown()
    run(scenario)


def test_cancel_after_operation_before_response_body_is_typed(env):
    from app.local_interop.api import AuthorityJSONResponse
    e = env
    async def scenario():
        sid = await e.connect()
        request_id = uuid4().hex
        async def ready(): return {"private": "SYNTHETIC_LATE_RESULT"}
        value = await e.host.run("author", request_id, ready)
        sent = []
        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.start": e.host.cancel("author", request_id, sid)
        async def receive(): return {"type": "http.request"}
        response = AuthorityJSONResponse(value, lambda: e.host.delivery_guard("author", sid, request_id))
        await response({"type": "http"}, receive, send)
        data = json.loads(b"".join(item.get("body", b"") for item in sent))
        assert data["code"] == "CANCELLED" and "private" not in data
        await e.host.shutdown()
    run(scenario)


def test_exact_specific_context_grant_stales_when_one_source_changes(env):
    e = env
    extra = e.bundle.chapters.create(e.project_id, {"title": "Second", "content": "Synthetic explicit second chapter"})
    async def scenario():
        sid = await e.connect()
        sources = e.host.sources("author", sid)
        assert len(sources["items"]) == 2
        assert "Synthetic explicit" not in json.dumps(sources)
        preview = e.host.context_preview("author", ContextPreviewInput(session_id=sid, content_kind="SPECIFIC_CONTEXT", context_ids=[extra["id"]]))
        assert "Synthetic explicit second chapter" in preview["capsule"]["content"]["text"]
        assert "Synthetic text" not in preview["capsule"]["content"]["text"]
        row = e.bundle.chapters.get(extra["id"])
        e.bundle.chapters.save(extra["id"], {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Changed selected source"}]}]}, row["version"])
        with pytest.raises(InteropFailure, match="SOURCE_CHANGED"):
            await e.host.ask("author", AskInput(session_id=sid, preview_id=preview["preview_id"], confirmed=True))
        await e.host.shutdown()
    run(scenario)


def test_model_registry_projection_excludes_credentials_paths_and_generic_metadata(env):
    from app.model_center.domain import (
        Capability,
        ModelDefinition,
        RuntimeDefinition,
        RuntimeInstance,
        RuntimeType,
    )
    e = env
    model = ModelDefinition(id="model", display_name="Synthetic", family="synthetic", variant="base", version="1", capabilities=(Capability.TEXT,), runtime_type=RuntimeType.LLAMA_CPP, model_format="GGUF", local_paths=("C:\\PRIVATE_PATH\\model.gguf",), metadata={"api_key": "SYNTHETIC_SECRET", "prompt": "PRIVATE_PROMPT"})
    runtime = RuntimeDefinition(id="runtime", runtime_type=RuntimeType.LLAMA_CPP, executable="C:\\PRIVATE_PATH\\run.exe", environment={"PROVIDER_TOKEN": "SYNTHETIC_SECRET"})
    e.host.provider.model_center = SimpleNamespace(models={model.id: model}, runtimes={runtime.id: runtime}, lifecycle=SimpleNamespace(instances={runtime.id: RuntimeInstance(runtime.id, http_reachable=True, last_health_check=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())}))
    async def scenario():
        sid = await e.connect()
        registry = e.host.model_registry("author", sid)
        assert registry["models"][0]["availability"] == "AVAILABLE"
        text = json.dumps(registry)
        assert all(marker not in text for marker in ("SYNTHETIC_SECRET", "PRIVATE_PATH", "PRIVATE_PROMPT", "api_key", "environment", "local_paths"))
        assert registry["models"][0]["verified_capabilities"] == []
        await e.host.shutdown()
    run(scenario)


def test_studio_restart_rejects_previous_session_and_never_auto_enables(env):
    e = env
    async def scenario():
        sid = await e.connect()
        replacement = LocalInteropHost(e.host.provider, transport_factory=e.InProcessTransport)
        assert replacement.product.instance_id != e.host.product.instance_id
        assert replacement.status("author")["enabled"] is False
        replacement.configure("author", True)
        with pytest.raises(InteropFailure, match="SESSION_REVOKED"): replacement.events("author", sid)
        await e.host.shutdown(); await replacement.shutdown()
    run(scenario)


@pytest.mark.parametrize("attack,code", [("hello-nonce", "PROTOCOL_INCOMPATIBLE"), ("missing-capability", "CAPABILITY_NOT_SUPPORTED"), ("peer-instance", "SESSION_REQUIRED"), ("user-identity", "SESSION_REQUIRED")])
def test_handshake_correlation_and_minimum_capabilities_fail_closed(env, attack, code):
    e = env
    original = e.host.transport_factory
    class Hostile(original):
        async def request(self, operation, message=None, *, token=None):
            raw = await super().request(operation, message, token=token)
            value = json.loads(raw)
            if attack == "hello-nonce" and operation == "hello": value["session_nonce"] = "different-" + "a" * 24
            if attack == "missing-capability" and operation == "negotiate": value["granted_capabilities"].remove("tutor.guidance.receive")
            if attack == "peer-instance" and operation == "session": value["session"]["peer_instance_id"] = "different-instance"
            if attack == "user-identity" and operation == "session": value["session"]["user_identity"] = "different-local-user"
            return json.dumps(value).encode()
    e.host.transport_factory = Hostile
    async def scenario():
        with pytest.raises(InteropFailure, match=code): await e.connect()
        assert not e.host.sessions
        await e.host.shutdown()
    run(scenario)


def test_slow_earlier_connect_cannot_replace_newer_session(env):
    e = env
    original = e.host.transport_factory
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        class Slow(original):
            async def request(self, operation, message=None, *, token=None):
                if operation == "hello": entered.set(); await release.wait()
                return await super().request(operation, message, token=token)
        e.host.transport_factory = Slow
        first = asyncio.create_task(e.connect())
        await entered.wait()
        e.host.transport_factory = original
        latest = await e.connect()
        release.set()
        with pytest.raises(InteropFailure, match="CANCELLED"): await first
        assert list(e.host.sessions) == [latest]
        await e.host.shutdown()
    run(scenario)


def test_old_cached_runtime_health_is_unknown_not_verified(env):
    from app.model_center.domain import (
        Capability,
        ModelDefinition,
        RuntimeDefinition,
        RuntimeInstance,
        RuntimeType,
    )
    e = env
    model = ModelDefinition(id="model", display_name="Synthetic", family="synthetic", variant="base", version="1", capabilities=(Capability.TEXT,), runtime_type=RuntimeType.LLAMA_CPP, model_format="GGUF")
    runtime = RuntimeDefinition(id="runtime", runtime_type=RuntimeType.LLAMA_CPP)
    instance = RuntimeInstance(runtime.id, http_reachable=True, last_health_check="2000-01-01T00:00:00+00:00")
    e.host.provider.model_center = SimpleNamespace(models={model.id: model}, runtimes={runtime.id: runtime}, lifecycle=SimpleNamespace(instances={runtime.id: instance}))
    assert e.host.provider.model_rows()[0]["availability"] == "UNKNOWN"
    assert e.host.provider.model_rows()[0]["last_validated"] is None
