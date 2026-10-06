"""Real Studio owners + MOCK_ONLY peer. No manuscript, model run or native claim."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from test_local_interop_host import env as _runtime_env
from test_local_interop_host import run, wait_for_observation

from app.local_interop.api import (
    AskInput,
    AuthorityJSONResponse,
    ContextPreviewInput,
    HandoffInput,
    PermissionRevokeInput,
    SessionInput,
    VerifyInput,
    create_local_interop_router,
)
from app.local_interop.desktop import PERMISSIONS
from app.local_interop.errors import InteropFailure
from app.local_interop.provider import InteropContextProvider
from app.runtime_events import RuntimeEventSource, committed_change, runtime_events
from local_interop_protocol import (
    HandoffTarget,
    VerificationCondition,
)

env = _runtime_env


def test_desktop_state_reports_reference_trust_and_owner_scoped_details(env):
    e = env
    async def scenario():
        assert e.host.status("author")["desktop"]["state"] == "UNKNOWN"
        a, b = await e.connect(), await e.connect("reader")
        result = e.host.status("author", a)["desktop"]
        assert result["state"] == "UNTRUSTED" and result["boundary"] == "LOCAL_REQUIRED"
        assert len(result["connections"]) == 1
        details = result["connections"][0]
        assert details["session_id"] == a and details["session_id"] != b
        assert details["transport_connected"] and details["handshake_complete"]
        assert details["session_established"] and details["capabilities_negotiated"]
        assert details["peer_authenticated"] is False and details["trust_level"] == "UNVERIFIED"
        assert details["mode"] == "MOCK_ONLY" and details["transport"] == "LOOPBACK_HTTP"
        assert {row["id"] for row in details["permissions"]} == set(PERMISSIONS)
        assert details["standing_permissions"] == []
        assert set(result["health"]) == {"transport", "peer", "session", "capabilities", "events", "tutor", "verifier"}
        assert "Synthetic text" not in json.dumps(result)
        with pytest.raises(InteropFailure): e.host.status("author", b)
        await e.host.shutdown()
    run(scenario)


@pytest.mark.parametrize("permission", tuple(PERMISSIONS))
def test_every_permission_revoke_stops_only_its_session_and_fences_previews(env, permission):
    e = env
    async def scenario():
        a, b = await e.connect(), await e.connect("reader")
        old = e.host.context_preview("author", ContextPreviewInput(session_id=a))
        e.subscribe(a); e.subscribe(b, "reader")
        result = e.host.permission_revoke("author", PermissionRevokeInput(session_id=a, permission_id=permission))
        assert result["status"] == "REVOKED"
        assert next(row for row in result["permissions"] if row["id"] == permission)["state"] == "REVOKED"
        assert e.host.sessions[a].event_grant_id is None
        assert e.host.sessions[b].event_grant_id is not None
        assert not e.host.sessions[a].previews
        with pytest.raises(InteropFailure):
            await e.host.ask("author", AskInput(session_id=a, preview_id=old["preview_id"], confirmed=True))
        e.bundle.novels.update(e.project_id, {"title": "Synthetic changed project"})
        assert e.host.events("reader", b)["events"]
        if permission in {"selection", "current_chapter", "specific_context"}:
            kind = {"selection": "SELECTION", "current_chapter": "CHAPTER", "specific_context": "SPECIFIC_CONTEXT"}[permission]
            with pytest.raises(InteropFailure):
                e.host.context_preview("author", ContextPreviewInput(session_id=a, content_kind=kind,
                    expected_chapter_version=e.chapter["version"], selection_start=0 if kind == "SELECTION" else None,
                    selection_end=1 if kind == "SELECTION" else None,
                    context_ids=[e.chapter["id"]] if kind == "SPECIFIC_CONTEXT" else []))
        if permission == "task_status":
            capsule = e.host.context_preview("author", ContextPreviewInput(session_id=a))["capsule"]
            assert all(capsule[key] is None for key in ("task_id", "task_type", "task_status", "error_code"))
        if permission == "model_metadata":
            capsule = e.host.context_preview("author", ContextPreviewInput(session_id=a))["capsule"]
            assert all(capsule[key] is None for key in ("model_id", "runtime_id", "runtime_status"))
            with pytest.raises(InteropFailure): e.host.model_registry("author", a)
        await e.host.shutdown()
    run(scenario)


def test_actual_committed_chapter_and_task_owners_drive_direct_events(env):
    e = env
    task = {"id": "task-" + e.suffix, "novel_id": e.project_id, "actor_id": e.actor_ids["author"],
            "workspace_id": e.workspace_id, "scope": e.scope, "operation": "continue", "status": "RUNNING", "updated_at": "1"}
    e.bundle.generations.save(task)
    async def scenario():
        e.host.event_interval = 60  # Direct source must not depend on the timer.
        sid = await e.connect(task_id=task["id"])
        e.subscribe(sid)
        e.host.capture_event("author", sid)
        await asyncio.sleep(0)
        before = e.host.sessions[sid].sequence
        e.bundle.chapters.save(e.chapter["id"], {"type": "doc", "content": []}, e.chapter["version"])
        await wait_for_observation(lambda: e.host.sessions[sid].sequence > before)
        session = e.host.sessions[sid]
        assert session.events[-1].event_type == "CHAPTER_OPENED"
        assert session.source_provenance[session.events[-1].event_id] == "DIRECT_EVENT"
        before = session.sequence
        task.update(status="COMPLETED", updated_at="2")
        e.bundle.generations.save(task)
        await wait_for_observation(lambda: session.sequence > before)
        assert session.events[-1].event_type == "TASK_COMPLETED"
        assert session.source_provenance[session.events[-1].event_id] == "DIRECT_EVENT"
        assert session.events[-1].context.content.level == "NONE"
        await e.host.shutdown()
    run(scenario)


def test_runtime_source_never_retains_payload_or_breaks_owner_writes():
    captured = []
    def callback(change): captured.append(asdict(change))
    close = runtime_events.subscribe(callback)
    class Owner:
        @committed_change("TASK")
        def save(self, item): return None
    try:
        Owner().save({"id": "task-1", "novel_id": "project-1", "version": 3,
            "prompt": "PRIVATE_PROMPT", "source": "PRIVATE_MANUSCRIPT", "api_key": "SYNTHETIC_CREDENTIAL"})
        assert captured == [{"module": "TASK", "project_id": "project-1", "entity_id": "task-1", "version": 3}]
        source = RuntimeEventSource()
        def broken(change): raise RuntimeError("consumer broken")
        source.subscribe(broken)
        source.publish(SimpleNamespace(module="TASK"))
    finally:
        close()


def test_source_version_37_to_38_is_unknown_and_late_preview_cannot_be_delivered(env):
    e = env
    chapter = e.chapter
    while chapter["version"] < 37:
        chapter = e.bundle.chapters.save(chapter["id"], chapter["document"], chapter["version"])
    original = e.peer.guidance
    e.peer.guidance = lambda request: original(request).model_copy(update={"verification_condition": VerificationCondition(field="chapter_version", expected_value=38, source_id="chapter_version")})
    async def scenario():
        sid = await e.connect()
        body = ContextPreviewInput(session_id=sid, content_kind="CHAPTER", expected_chapter_version=37)
        preview = e.host.context_preview("author", body)
        result = await e.host.ask("author", AskInput(session_id=sid, preview_id=preview["preview_id"], confirmed=True))
        queued = e.host.context_preview("author", ContextPreviewInput(session_id=sid, content_kind="CHAPTER", expected_chapter_version=37))
        current = e.bundle.chapters.save(chapter["id"], chapter["document"], 37)
        assert current["version"] == 38
        verified = await e.host.verify("author", VerifyInput(session_id=sid, guidance_id=result["guidance"]["guidance_id"]))
        assert verified["result"]["status"] == "UNKNOWN" and verified["result"]["evidence"] == []
        sent = []
        response = AuthorityJSONResponse(queued, lambda: e.host.delivery_guard("author", sid, queued["request_id"]))
        async def send(message): sent.append(message)
        await response({"type": "http"}, None, send)
        assert b"SOURCE_CHANGED" in sent[-1]["body"] and b"Synthetic text" not in sent[-1]["body"]
        await e.host.shutdown()
    run(scenario)


def test_permission_revoke_cancels_inflight_and_new_session_never_inherits_grant(env):
    e = env
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        original = e.host.transport_factory
        class Delayed(original):
            async def request(self, operation, message=None, **kwargs):
                result = await super().request(operation, message, **kwargs)
                if operation == "tutor": entered.set(); await release.wait()
                return result
        e.host.transport_factory = Delayed
        a = await e.connect()
        e.subscribe(a)
        preview = e.host.context_preview("author", ContextPreviewInput(session_id=a))
        body = AskInput(session_id=a, preview_id=preview["preview_id"], confirmed=True)
        pending = asyncio.create_task(e.host.run("author", body.request_id, lambda: e.host.ask("author", body), session_id=a))
        await entered.wait()
        e.host.permission_revoke("author", PermissionRevokeInput(session_id=a, permission_id="selection"))
        release.set()
        with pytest.raises(InteropFailure, match="CANCELLED"): await pending
        receipt = await e.host.disconnect_revoke("author", SessionInput(session_id=a))
        assert all(receipt[key] for key in ("revoked", "subscriptions_stopped", "pending_cancelled", "standing_grants_cleared"))
        assert receipt["status"] == "UNKNOWN"
        assert receipt["transport_disconnected"] is False and receipt["transport_close_state"] == "UNKNOWN"
        assert receipt["peer_disconnect_acknowledged"] is True
        b = await e.connect()
        assert b != a and e.host.sessions[b].event_grant_id is None
        assert not e.host.sessions[b].guidance
        assert e.host.events("author", b)["events"] == []
        with pytest.raises(InteropFailure): e.host.delivery_guard("author", a, body.request_id)
        await e.host.shutdown()
    run(scenario)


def test_api_permission_receipts_no_owner_leak_and_emergency_cleanup(env):
    e = env
    async def scenario():
        a, b = await e.connect(), await e.connect("reader")
        app = FastAPI(); app.include_router(create_local_interop_router(e.host))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)), base_url="http://127.0.0.1", headers={"X-Session-Token": "author"}) as client:
            root = "/api/local-interop"
            assert (await client.get(root + "/status", params={"session_id": b})).status_code == 403
            reply = await client.post(root + "/permissions/revoke", json={"session_id": a, "permission_id": "deep_link"})
            assert reply.status_code == 200 and reply.json()["status"] == "REVOKED"
            with pytest.raises(InteropFailure):
                e.host.handoff("author", HandoffInput(session_id=a, explicit_click=True,
                    handoff=HandoffTarget(action="OPEN_FEATURE", target_product_id=e.host.product.product_id, feature="editor")))
            receipt = await client.post(root + "/disconnect-revoke", json={"session_id": a})
            assert receipt.status_code == 200 and receipt.json()["revoked"] is True
            assert b in e.host.sessions
        await e.host.shutdown()
    run(scenario)


def test_lifecycle_sleep_shutdown_restart_preserves_no_authority(env):
    e = env
    async def scenario():
        await e.host.app_start()
        original = e.host.product.instance_id
        sid = await e.connect(); e.subscribe(sid)
        await e.host.lifecycle.app_sleep()
        assert not e.host.sessions
        assert "APP_SLEEP" in e.host.lifecycle.events
        await e.host.lifecycle.shutdown(timeout=.5)
        assert e.host.closed and not e.host.enabled_owners
        await e.host.app_start()
        assert original != e.host.product.instance_id
        assert not e.host.sessions and not e.host.enabled_owners
        with pytest.raises(InteropFailure): e.host._session("author", sid)
        await e.host.shutdown()
    run(scenario)


def test_export_and_workflow_polling_use_existing_owners_with_exact_scope(env):
    e = env
    export = {"id": "export-1", "novel_id": e.project_id, "status": "succeeded", "updated_at": "1",
        "permission_context": {"mode": "collaboration", "actor_id": e.actor_ids["author"], "workspace_id": e.workspace_id,
            "novel_id": e.project_id, "storyline_id": e.storyline_id, "branch_id": e.branch_id}, "result": {"content": "PRIVATE_EXPORT"}}
    workflow = {"id": "workflow-1", "novel_id": e.project_id, "status": "WAITING_APPROVAL", "version": 2,
        "owner": {"actor_id": e.actor_ids["author"], "workspace_id": e.workspace_id}, "branch_id": e.branch_id,
        "definition_snapshot": {"prompt": "PRIVATE_WORKFLOW"}}
    provider = InteropContextProvider(e.collaboration, export_jobs=SimpleNamespace(get=lambda _: export), workflow_reader=lambda _: workflow)
    for surface, tid in (("export", "export-1"), ("workflow", "workflow-1")):
        row = provider.snapshot("author", e.scope, module="NOVEL", surface=surface, task_id=tid)
        assert row["state"]["task_status"] == ("COMPLETED" if surface == "export" else "WAITING")
        assert "PRIVATE" not in json.dumps(row["state"])
        with pytest.raises(InteropFailure): provider.snapshot("reader", e.scope, module="NOVEL", surface=surface, task_id=tid)
    export["permission_context"]["branch_id"] = e.other_branch_id
    workflow["branch_id"] = e.other_branch_id
    for surface, tid in (("export", "export-1"), ("workflow", "workflow-1")):
        with pytest.raises(InteropFailure): provider.snapshot("author", e.scope, module="NOVEL", surface=surface, task_id=tid)


@pytest.mark.parametrize("failure", ["failed-close", "uncooperative-close", "missing-peer-ack"])
def test_disconnect_receipt_distinguishes_authority_from_transport_proof(env, failure):
    e = env
    async def scenario():
        release = asyncio.Event()
        original = e.host.transport_factory
        class ClosingTransport(original):
            async def request(self, operation, message=None, **kwargs):
                if operation == "disconnect" and failure == "missing-peer-ack":
                    raise RuntimeError("PRIVATE_PEER_ERROR")
                return await super().request(operation, message, **kwargs)
            async def shutdown(self):
                if failure == "failed-close": raise RuntimeError("PRIVATE_PLATFORM_PATH")
                if failure == "uncooperative-close":
                    while not release.is_set():
                        try: await release.wait()
                        except asyncio.CancelledError: continue
                return True
        e.host.transport_factory = ClosingTransport
        sid = await e.connect(); e.subscribe(sid)
        start = asyncio.get_running_loop().time()
        receipt = await e.host.disconnect_revoke("author", SessionInput(session_id=sid))
        assert asyncio.get_running_loop().time() - start < 1.0
        assert receipt["revoked"] and receipt["standing_grants_cleared"] and sid not in e.host.sessions
        assert "PRIVATE" not in json.dumps(receipt)
        if failure == "missing-peer-ack":
            assert receipt["status"] == "DISCONNECTED"
            assert receipt["transport_disconnected"] and receipt["transport_close_state"] == "CLOSED"
            assert receipt["peer_disconnect_acknowledged"] is False
        else:
            assert receipt["transport_disconnected"] is False
            assert receipt["transport_close_state"] == ("FAILED" if failure == "failed-close" else "TIMEOUT")
            assert receipt["peer_disconnect_acknowledged"] is True
        # Even an adapter that swallows task cancellation cannot hold app exit.
        start = asyncio.get_running_loop().time()
        await e.host.shutdown(timeout=.02)
        assert asyncio.get_running_loop().time() - start < .3
        release.set()
        if e.host.closing_tasks: await asyncio.gather(*tuple(e.host.closing_tasks), return_exceptions=True)
    run(scenario)


def test_loopback_close_proof_waits_for_inflight_clients(monkeypatch):
    from app.local_interop.transport import LoopbackTransport
    async def scenario():
        transport = LoopbackTransport("http://127.0.0.1:12345")
        entered, release = asyncio.Event(), asyncio.Event()
        async def resistant(*args, **kwargs):
            entered.set()
            while not release.is_set():
                try: await release.wait()
                except asyncio.CancelledError: continue
            return b"{}"
        monkeypatch.setattr(transport, "_exchange", resistant)
        pending = asyncio.create_task(transport.request("discovery"))
        await entered.wait()
        assert await transport.shutdown(timeout=.01) is False
        with pytest.raises(InteropFailure): await transport.request("discovery")
        release.set(); await pending
        assert await transport.shutdown(timeout=.01) is True
    run(scenario)


def test_emergency_retry_is_owner_bound_and_status_retains_unproven_close(env):
    e = env
    async def scenario():
        original = e.host.transport_factory
        class RetryClose(original):
            attempts = 0
            async def shutdown(self):
                self.attempts += 1
                return self.attempts > 1
        e.host.transport_factory = RetryClose
        sid = await e.connect(); e.subscribe(sid)
        first = await e.host.disconnect_revoke("author", SessionInput(session_id=sid))
        assert first["status"] == "UNKNOWN"
        assert not first["transport_disconnected"]
        status = e.host.status("author", sid)["desktop"]
        assert status["state"] == "UNKNOWN" and status["health"]["transport"] == "UNKNOWN"
        assert status["transport_state"] == "DISCONNECTING"
        assert status["connections"] == []
        assert not e.host.closed_sessions[sid].host_token and not e.host.closed_sessions[sid].peer_token
        assert not e.host.closed_sessions[sid].previews and not e.host.closed_sessions[sid].guidance
        with pytest.raises(InteropFailure): await e.host.disconnect_revoke("reader", SessionInput(session_id=sid))
        with pytest.raises(InteropFailure): e.host.status("reader", sid)
        second = await e.host.disconnect_revoke("author", SessionInput(session_id=sid))
        assert second["transport_disconnected"] and second["transport_close_state"] == "CLOSED"
        assert second["peer_disconnect_acknowledged"] is True
        assert e.host.status("author", sid)["desktop"]["state"] == "DISCONNECTED"
        third = await e.host.disconnect_revoke("author", SessionInput(session_id=sid))
        assert third["transport_disconnected"] and e.host.closed_sessions[sid].transport.attempts == 2
        with pytest.raises(InteropFailure): e.host._session("author", sid)
        app = FastAPI(); app.include_router(create_local_interop_router(e.host))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)), base_url="http://127.0.0.1", headers={"X-Session-Token": "author"}) as client:
            value = await client.get("/api/local-interop/status", params={"session_id": sid})
            assert value.status_code == 200 and value.json()["desktop"]["close_receipts"][0]["transport_disconnected"]
        await e.host.shutdown()
    run(scenario)


def test_context_adapter_reads_current_owners_and_selection_metadata_only(env):
    e = env
    async def scenario():
        sid = await e.connect()
        context = e.host.desktop.context("author", sid)
        assert context.current_product_context()["instance_id"] == e.host.product.instance_id
        assert context.current_project_context()["project_id"] == e.project_id
        assert context.current_surface() == {"module": "NOVEL", "surface": "editor"}
        assert context.current_task()["task_id"] is None
        assert context.current_model_state()["model_id"] is None
        assert context.current_runtime_state()["runtime_id"] is None
        assert not context.selected_content_metadata()["selection_available"]
        preview = e.host.context_preview("author", ContextPreviewInput(session_id=sid, content_kind="SELECTION",
            expected_chapter_version=e.chapter["version"], selection_start=0, selection_end=8))
        metadata = context.selected_content_metadata()
        assert metadata["selection_available"] and metadata["selection_id"] == preview["capsule"]["selection_id"]
        assert "text" not in metadata and "Synthetic" not in json.dumps(metadata)
        assert context.build_capsule({}).content.level == "NONE"
        with pytest.raises(InteropFailure): context.build_capsule({"content_kind": "CHAPTER"})
        e.bundle.chapters.save(e.chapter["id"], {"type": "doc", "content": []}, e.chapter["version"])
        assert context.current_project_context()["chapter_version"] == e.chapter["version"] + 1
        assert not context.selected_content_metadata()["selection_available"]
        await e.host.shutdown()
    run(scenario)


def test_optional_bridge_start_failure_cannot_prevent_app_ready(env, monkeypatch):
    e = env
    async def scenario():
        async def broken(): raise RuntimeError("PRIVATE_PLATFORM_PATH")
        monkeypatch.setattr(e.host.lifecycle.transport, "start", broken)
        await e.host.app_start()
        assert e.host.lifecycle.app_is_ready and not e.host.closed
        with pytest.raises(InteropFailure, match="TRANSPORT_ERROR"): await e.connect()
        status = e.host.status("author")["desktop"]
        assert status["state"] == "DEGRADED" and status["health"]["transport"] == "DEGRADED"
        assert status["diagnostics"]["error_codes"] == ["TRANSPORT_ERROR"]
        assert "PRIVATE" not in json.dumps(status)
        await e.host.shutdown()
    run(scenario)
