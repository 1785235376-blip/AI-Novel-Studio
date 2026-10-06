"""Functional Host APIs + real repositories + a separate loopback MOCK_ONLY peer."""
import asyncio

import httpx
from fastapi import FastAPI

from app.identity import IdentityStatus
from app.local_interop.api import create_local_interop_router
from app.local_interop.transport import LoopbackTransport
from test_local_interop_host import env  # noqa: F401 - shared real-authority fixture
from test_local_interop_tcp import synthetic_endpoint  # noqa: F401 - separate process


def test_real_host_api_metadata_guidance_diagnostics_verifier_and_revocation(env, synthetic_endpoint):
    e = env
    e.host.transport_factory = LoopbackTransport
    app = FastAPI()
    app.include_router(create_local_interop_router(e.host))
    task = {"id": "task-live", "novel_id": e.project_id, "chapter_id": e.chapter["id"],
            "actor_id": e.actor_ids["author"], "workspace_id": e.workspace_id, "scope": {"kind": "BRANCH", **e.scope},
            "operation": "continue", "status": "FAILED", "error_code": "SYNTHETIC_ERROR", "updated_at": "1"}
    e.bundle.generations.save(task)

    async def scenario():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 41001))
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1",
                                   headers={"X-Session-Token": "author"}) as client:
            async def post(path, body):
                response = await client.post("/api/local-interop/" + path, json=body)
                assert response.status_code == 200, (path, response.text)
                return response.json()
            await post("settings", {"enabled": True})
            connected = await post("connect", e.body(task_id="task-live").model_copy(
                update={"endpoint": synthetic_endpoint}).model_dump(mode="json"))
            sid = connected["session_id"]
            assert connected["mode"] == "MOCK_ONLY"
            preview = await post("context/preview", {"session_id": sid})
            assert preview["capsule"]["content"]["level"] == "NONE"
            assert "Synthetic text" not in str(preview["capsule"])
            answer = await post("ask", {"session_id": sid, "preview_id": preview["preview_id"], "confirmed": True})
            assert answer["guidance"]["authority"] == "ADVISORY"
            assert e.bundle.generations.get("task-live")["status"] == "FAILED"
            verify_body = {"session_id": sid, "guidance_id": answer["guidance"]["guidance_id"]}
            failed = await post("verify", verify_body)
            assert failed["result"]["status"] == "FAILED"
            task.update(status="COMPLETED", updated_at="2")
            e.bundle.generations.save(task)
            verified = await post("verify", verify_body)
            assert verified["result"]["status"] == "VERIFIED"
            assert verified["result"]["evidence"][0]["source_id"] == "task_status"
            candidate = await post("case/preview", {"session_id": sid, "result_id": verified["result"]["result_id"]})
            assert candidate["candidate"]["privacy_scope"] == "LOCAL_ONLY"
            approved = await post("case/approve", {"session_id": sid, "candidate_id": candidate["candidate"]["candidate_id"], "confirmed": True})
            assert approved["uploaded"] is False
            diagnostic = await post("diagnostics/preview", {"session_id": sid, "fields": ["feature"]})
            assert diagnostic["diagnostic"]["error_code"] is None
            assert diagnostic["capsule"]["task_status"] is None
            shared = await post("diagnostics/share", {"session_id": sid, "preview_id": diagnostic["preview_id"], "confirmed": True})
            assert shared["guidance"]["authority"] == "ADVISORY"
            assert e.bundle.chapters.get(e.chapter["id"])["version"] == e.chapter["version"]
            for _ in range(100):
                await asyncio.sleep(.02)
                local = e.host.sessions.get(sid)
                if local and local.sent_sequence >= 1:
                    break
            assert e.host.sessions[sid].sent_sequence >= 1
            e.identity.set_membership_status(e.actor_ids["author"], e.workspace_id, IdentityStatus.INACTIVE)
            revoked = await client.get("/api/local-interop/events", params={"session_id": sid})
            assert revoked.status_code in {401, 403}
            assert revoked.json()["code"] in {"SESSION_REVOKED", "PERMISSION_DENIED"}
            assert sid not in e.host.sessions
        await e.host.shutdown()
    asyncio.run(scenario())
