import copy
import pytest
from test_generation_worker_authority import source, _mutate, _finish
from conftest import restore_global_settings
from app import jobs as jobs_module


@pytest.fixture(autouse=True)
def publication_broker_features(monkeypatch):
    # Accounting hooks require these existing features. The worker and API
    # authority still use their production paths; no authorization is patched.
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'author_context_inspector_v2,model_broker_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)


def post_operation(source, operation):
    response = source.client.post('/api/generate/' + operation, json=dict(source.payload),
        headers={'Idempotency-Key': 'review-publication-key'})
    assert response.status_code == 202, response.text
    assert source.entered.wait(10)
    job = source.manager.jobs[response.json()['job_id']]
    assert job.status == 'QUEUED'
    return job


def watch(source, monkeypatch):
    revoked, emissions, saves, dispatches, terminals = [], [], [], [], []
    original_emit = source.manager._emit
    def emit(job, chunk=''):
        emissions.append((bool(revoked), chunk, job.status))
        return original_emit(job, chunk)
    monkeypatch.setattr(source.manager, '_emit', emit)
    original_save = source.manager.persistence.save
    def save(payload):
        saves.append((bool(revoked), copy.deepcopy(payload)))
        return original_save(payload)
    monkeypatch.setattr(source.manager.persistence, 'save', save)
    return revoked, emissions, saves, dispatches, terminals


@pytest.mark.parametrize('operation', ['continue', 'polish'])
@pytest.mark.parametrize('snapshot_required', [False, True])
@pytest.mark.parametrize('moment', ['midstream', 'before_completed_event'])
@pytest.mark.parametrize('change', ['archive', 'replace_owner'])
def test_revoked_live_source_stops_new_output_and_terminal_publish(source, monkeypatch, operation, snapshot_required, moment, change):
    source.manager.snapshot_required = snapshot_required
    revoked, emissions, saves, dispatches, terminals = watch(source, monkeypatch)
    def revoke():
        _mutate(source, change)
        revoked.append(True)
    if moment == 'before_completed_event':
        source.hooks.after_stream = revoke
    else:
        provider = source.runtime.providers['mock']
        original_stream = provider.stream
        def stream(*args, **kwargs):
            first = True
            for chunk in original_stream(*args, **kwargs):
                yield chunk
                if first:
                    first = False
                    revoke()
        monkeypatch.setattr(provider, 'stream', stream)
    job = post_operation(source, operation)
    job.dispatch_hooks_required = True
    job.before_dispatch = lambda: dispatches.append(None)
    job.on_terminal = lambda: terminals.append(None)
    _finish(source)
    assert revoked
    assert job.status == 'FAILED'
    assert job.output == ''
    assert source.manager.persistence.get(job.id)['output'] == ''
    assert source.counts['adapter'] == 1
    assert len(dispatches) == len(terminals) == 1
    assert job.terminal_hook_status == 'COMPLETED'
    assert not any(chunk for after, chunk, _ in emissions if after)
    assert not any(after and row['status'] == 'COMPLETED' for after, row in saves)
    assert source.counts['snapshot'] == int(snapshot_required)
    if moment == 'midstream':
        assert sum(len(chunk) for after, chunk, _ in emissions if not after) == 8
    assert job.route_decisions[0]['status'] in {'DISPATCHED', 'FAILED', 'COMPLETED'}


@pytest.mark.parametrize('operation', ['continue', 'polish'])
@pytest.mark.parametrize('snapshot_required', [False, True])
@pytest.mark.parametrize('moment', ['final_review', 'terminal_hook'])
def test_final_publication_rechecks_after_review_or_settlement_without_losing_execution_receipts(source, monkeypatch, operation, snapshot_required, moment):
    source.manager.snapshot_required = snapshot_required
    revoked, emissions, saves, dispatches, terminals = watch(source, monkeypatch)
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    monkeypatch.setattr(provider, 'supports_stream_usage', True, raising=False)
    def stream(*args, **kwargs):
        kwargs['usage_callback']({'input_tokens': 13, 'output_tokens': 21})
        yield from original_stream(*args, **kwargs)
    monkeypatch.setattr(provider, 'stream', stream)
    def revoke():
        _mutate(source, 'archive')
        revoked.append(True)
    if moment == 'final_review':
        original_review = jobs_module.deterministic_review
        def review(*args, **kwargs):
            result = original_review(*args, **kwargs)
            revoke()
            return result
        monkeypatch.setattr(jobs_module, 'deterministic_review', review)
    job = post_operation(source, operation)
    job.dispatch_hooks_required = True
    job.before_dispatch = lambda: dispatches.append(None)
    def settle():
        terminals.append(None)
        if moment == 'terminal_hook':
            revoke()
    job.on_terminal = settle
    _finish(source)
    assert revoked
    assert job.status == 'FAILED'
    assert job.output == ''
    assert job.usage == {'input_tokens': 13, 'output_tokens': 21, 'total_tokens': 34}
    assert job.usage_status == 'REPORTED'
    assert job.execution_mode == 'mock_standin'
    assert job.provider == 'mock' and job.model == 'mock-writer'
    assert job.route_decisions[0]['status'] == 'COMPLETED'
    assert job.execution_outcome == 'COMPLETED', 'provider execution completed before authority was revoked'
    assert len(dispatches) == len(terminals) == 1
    assert job.terminal_hook_status == 'COMPLETED'
    assert job.error_code != 'GENERATION_TERMINAL_PERSISTENCE_UNCERTAIN'
    assert job.error_code != 'TERMINAL_RECONCILIATION_REQUIRED'
    assert source.counts['snapshot'] == int(snapshot_required or operation == 'continue')
    assert not any(after and row['status'] == 'COMPLETED' for after, row in saves)
    saved = source.manager.persistence.get(job.id)
    assert saved['status'] == 'FAILED' and saved['output'] == ''
    assert saved['usage'] == job.usage


@pytest.mark.parametrize('terminal', ['CANCELLED', 'ACCEPTED', 'REJECTED'])
def test_late_worker_event_does_not_reauthorize_or_rewrite_existing_terminal(source, monkeypatch, terminal):
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    job = post_operation(source, 'continue')
    baseline = []
    original_authorize = job.request_authorization
    def authorize():
        assert not baseline, 'late callback checked after already published terminal'
        return original_authorize()
    job.request_authorization = authorize
    def stream(*args, **kwargs):
        first = True
        for chunk in original_stream(*args, **kwargs):
            yield chunk
            if first:
                first = False
                # Controlled persisted terminal fixture. This does not claim a
                # running task is adoptable through the actual accept API.
                with job.condition:
                    if terminal == 'CANCELLED':
                        source.manager.cancel(job.id)
                    else:
                        job.status = terminal
                        source.manager._persist(job)
                    baseline.append(copy.deepcopy(source.manager.persistence.get(job.id)))
                _mutate(source, 'archive')
    monkeypatch.setattr(provider, 'stream', stream)
    _finish(source)
    assert baseline
    assert job.status == terminal
    assert source.manager.persistence.get(job.id) == baseline[0]


@pytest.mark.parametrize('also_revoke', [False, True])
def test_terminal_hook_cancel_preserves_completed_execution_fact_and_cannot_publish(source, monkeypatch, also_revoke):
    revoked, emissions, saves, dispatches, terminals = watch(source, monkeypatch)
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    monkeypatch.setattr(provider, 'supports_stream_usage', True, raising=False)
    def stream(*args, **kwargs):
        kwargs['usage_callback']({'input_tokens': 13, 'output_tokens': 21})
        yield from original_stream(*args, **kwargs)
    monkeypatch.setattr(provider, 'stream', stream)
    job = post_operation(source, 'continue')
    job.dispatch_hooks_required = True
    job.before_dispatch = lambda: dispatches.append(None)
    at_hook = []
    def settle():
        terminals.append(None)
        at_hook.append((job.status, job.execution_outcome))
        source.manager.cancel(job.id)
        if also_revoke:
            _mutate(source, 'archive')
            revoked.append(True)
    job.on_terminal = settle
    _finish(source)
    assert at_hook == [('SETTLING', 'COMPLETED')]
    assert job.status == 'CANCELLED'
    assert job.execution_outcome == 'COMPLETED'
    assert job.usage == {'input_tokens': 13, 'output_tokens': 21, 'total_tokens': 34}
    assert len(dispatches) == len(terminals) == 1
    assert job.terminal_hook_status == 'COMPLETED'
    assert not any(row['status'] == 'COMPLETED' for _, row in saves)
    assert source.manager.persistence.get(job.id)['status'] == 'CANCELLED'


@pytest.mark.parametrize('snapshot_required', [False, True])
def test_late_adapter_guard_refusal_cannot_leave_partial_buffer_reviewable(source, monkeypatch, snapshot_required):
    source.manager.snapshot_required = snapshot_required
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    monkeypatch.setattr(provider, 'supports_dispatch_guard', True, raising=False)
    refused = []
    def stream(*args, **kwargs):
        first = True
        for chunk in original_stream(*args, **kwargs):
            yield chunk
            if first:
                first = False
                _mutate(source, 'archive')
                refused.append(True)
                kwargs['dispatch_guard']()
    monkeypatch.setattr(provider, 'stream', stream)
    job = post_operation(source, 'continue')
    _finish(source)
    assert refused
    assert job.status == 'FAILED'
    assert job.output == ''
    assert source.manager.persistence.get(job.id)['output'] == ''
