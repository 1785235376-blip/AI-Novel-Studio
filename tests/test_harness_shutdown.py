import asyncio
from app.main import app_lifespan
from app.dependencies import harness_process_service

def test_shutdown_reclaims_owned_harness(monkeypatch):
    calls=[]
    monkeypatch.setattr(harness_process_service, "stop", lambda: calls.append(True) or {"running":False,"pid":None})
    async def run():
        async with app_lifespan(None):
            pass
    asyncio.run(run())
    assert calls==[True]
