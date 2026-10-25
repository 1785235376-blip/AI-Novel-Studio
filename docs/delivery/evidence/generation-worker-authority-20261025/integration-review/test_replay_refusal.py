import pytest
from conftest import restore_global_settings
from test_generation_worker_authority import source, _finish
from app import api

@pytest.mark.parametrize('reserved', [False, True])
def test_refused_worker_restored_authority_never_replays(source, monkeypatch, reserved):
    original_prepare = source.manager.prepare_job
    def prepare(*args, **kwargs):
        job = original_prepare(*args, **kwargs)
        original = job.request_authorization
        calls = []
        def once_refused():
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError('synthetic transient revocation')
            return original()
        job.request_authorization = once_refused
        return job
    monkeypatch.setattr(source.manager, 'prepare_job', prepare)
    original_store = api._store_idempotent
    def store(key, scope, value):
        if reserved and value.get('schema_version') == 2:
            raise OSError('synthetic final admission storage failure')
        return original_store(key, scope, value)
    monkeypatch.setattr(api, '_store_idempotent', store)
    def post():
        return source.client.post('/api/generate/continue', json=source.payload,
            headers={'Idempotency-Key':'independent-refused-replay'})
    first = post()
    assert first.status_code == (503 if reserved else 202), first.text
    assert source.entered.wait(10)
    assert len(source.manager.jobs) == 1
    job = next(iter(source.manager.jobs.values()))
    _finish(source)
    assert job.status == 'FAILED' and job.output == ''
    assert source.counts['context'] == source.counts['adapter'] == 0
    source.authority[0]()  # Real API closure is currently valid again.
    replay = post()
    assert replay.status_code == (409 if reserved else 202), replay.text
    if reserved:
        assert replay.json()['detail']['code'] == 'ADMISSION_UNCONFIRMED'
    else:
        assert replay.json()['job_id'] == job.id
    assert len(source.manager.jobs) == 1
    assert source.counts['context'] == source.counts['adapter'] == 0
    assert source.manager.persistence.get(job.id)['status'] == 'FAILED'
