import asyncio
import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history
from app.creative.asset_usage_budget import current_usage_budget, usage_read_budget
from app.creative.asset_usage_request import AssetUsageRequestBudgetMiddleware
from app.repositories.file.mutation_coordinator import strict_coordination_active

@pytest.mark.parametrize('alias', ['', '/v1'])
def test_history_request_gets_fresh_budget_without_inheriting(alias):
    observed = []
    async def app(scope, receive, send):
        observed.append((current_usage_budget(), strict_coordination_active()))
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})
    async def run():
        middleware = AssetUsageRequestBudgetMiddleware(app)
        async def send(message): pass
        async def receive(): return {'type': 'http.request', 'body': b''}
        with usage_read_budget() as outer:
            scope={'type':'http','method':'GET','path':f'/api{alias}/projects/p/studio/assets/a/history','query_string':b''}
            await middleware(scope, receive, send)
            await middleware(scope, receive, send)
            assert current_usage_budget() is outer
            assert observed[0][0] is not outer and observed[1][0] is not outer
            assert observed[0][0] is not observed[1][0]
            assert observed[0][1] and observed[1][1]
    asyncio.run(run())

def test_missing_project_marker_never_initialized(audio_history):
    e = audio_history
    marker = e.rig.root / 'novels' / e.rig.nid / 'creative_project_v2.json'
    assert marker.is_file()
    marker.unlink()
    response = e.client.get(e.base + '/assets/' + e.asset['id'] + '/history', headers=e.headers)
    assert response.status_code != 200, response.text
    assert not marker.exists()

def test_project_identity_changes_after_asset_lease_no_status(audio_history, monkeypatch):
    e = audio_history
    owner = e.rig.assets
    original = owner.project_scope
    marker = e.rig.root / 'novels' / e.rig.nid / 'creative_project_v2.json'
    @contextmanager
    def changed(*args, **kwargs):
        with original(*args, **kwargs):
            yield
        # Inject replacement of the synthetic identity after lease release.
        value = json.loads(marker.read_text(encoding='utf-8'))
        value['project_incarnation'] = str(uuid4())
        marker.write_text(json.dumps(value), encoding='utf-8')
    monkeypatch.setattr(owner, 'project_scope', changed)
    response = e.client.get(e.base + '/assets/' + e.asset['id'] + '/history', headers=e.headers)
    assert response.status_code != 200, response.text
    assert 'UNCAPTURED' not in response.text

def test_concurrent_edit_waits_for_existing_asset_lease(audio_history, monkeypatch):
    import threading
    e = audio_history
    began, finished = threading.Event(), threading.Event()
    failures = []
    original = e.rig.assets.content
    workers = []
    def competing_write():
        began.set()
        try:
            with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
                e.rig.assets.update_metadata(e.asset['id'], {'parameters': {'synthetic': True}}, expected_version=1)
        except Exception as exc:
            failures.append(repr(exc))
        finally:
            finished.set()
    def read_and_race(*args, **kwargs):
        result = original(*args, **kwargs)
        t = threading.Thread(target=competing_write)
        workers.append(t)
        t.start()
        assert began.wait(2)
        assert not finished.wait(0.1), 'writer escaped original asset owner lock'
        return result
    monkeypatch.setattr(e.rig.assets, 'content', read_and_race)
    response = e.client.get(e.base + '/assets/' + e.asset['id'] + '/history', headers=e.headers)
    assert response.status_code == 200, response.text
    assert response.json()['current_version'] == 1
    for t in workers:
        t.join(10)
        assert not t.is_alive()
    assert not failures, failures
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        assert e.rig.assets.get(e.asset['id'])['version'] == 2
