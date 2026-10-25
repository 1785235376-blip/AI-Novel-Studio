import json
import pytest
from test_generation_worker_authority import source, _post, _finish
from conftest import restore_global_settings
from app.router import Route

@pytest.mark.parametrize('snapshot_required', [False, True])
@pytest.mark.parametrize('deny_at', [1, 2, 3, 4])
def test_refusal_each_existing_checkpoint_is_terminal_safe_and_settles_once(source, monkeypatch, snapshot_required, deny_at):
    source.manager.snapshot_required = snapshot_required
    original_router = source.runtime.router
    def router(profile, role):
        value = original_router(profile, role)
        value.routes[role] = [Route('mock', 'mock-writer'), Route('mock', 'mock-writer')]
        return value
    monkeypatch.setattr(source.runtime, 'router', router)
    job = _post(source, automatic_route=True)
    callbacks, dispatches, terminals = [], [], []
    def authorize():
        callbacks.append(None)
        if len(callbacks) == deny_at:
            raise RuntimeError('secret-review-token /review-private-root')
    job.request_authorization = authorize
    job.before_dispatch = lambda: dispatches.append(None)
    job.on_terminal = lambda: terminals.append(None)
    _finish(source)
    assert job.status == 'FAILED'
    assert len(callbacks) == deny_at
    assert len(job.route_decisions) == 1
    assert len(terminals) == 1
    assert len(dispatches) == int(not snapshot_required and deny_at == 4)
    assert source.counts['adapter'] == int(not snapshot_required and deny_at == 4)
    expected_snapshots = int(snapshot_required and deny_at >= 3)
    assert source.counts['snapshot'] == expected_snapshots
    saved = source.manager.persistence.get(job.id)
    assert saved['status'] == 'FAILED'
    assert saved['terminal_hook_status'] == 'COMPLETED'
    assert 'secret-review-token' not in json.dumps(saved)
    assert '/review-private-root' not in json.dumps(saved)
    assert 'request_authorization' not in saved

@pytest.mark.parametrize('moment', ['before_worker', 'before_adapter', 'during_stream'])
def test_cancel_still_rejects_late_result_and_settles_once(source, monkeypatch, moment):
    source.manager.snapshot_required = True
    if moment == 'before_adapter':
        source.gate_dispatch()
    job = _post(source)
    terminals = []
    job.on_terminal = lambda: terminals.append(None)
    if moment == 'before_adapter':
        source.release.set()
        assert source.dispatch_entered.wait(10)
    if moment != 'during_stream':
        source.manager.cancel(job.id)
    else:
        provider = source.runtime.providers['mock']
        original_stream = provider.stream
        def stream(*args, **kwargs):
            first = True
            for chunk in original_stream(*args, **kwargs):
                yield chunk
                if first:
                    first = False
                    source.manager.cancel(job.id)
        monkeypatch.setattr(provider, 'stream', stream)
    _finish(source)
    assert job.status == 'CANCELLED'
    assert source.manager.persistence.get(job.id)['status'] == 'CANCELLED'
    assert len(terminals) == 1
    if moment != 'during_stream':
        assert source.counts['adapter'] == 0
        assert job.output == ''
    else:
        assert len(job.output) == 8
