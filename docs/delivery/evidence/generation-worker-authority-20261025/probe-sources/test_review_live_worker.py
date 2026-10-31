import pytest
from test_generation_worker_authority import source, _post, _mutate, _finish
from conftest import restore_global_settings

@pytest.mark.parametrize('change', ['archive', 'replace_owner'])
def test_no_completed_publication_after_live_authority_changes_during_stream(source, change):
    source.manager.snapshot_required = True
    job = _post(source)
    source.hooks.after_stream = lambda: _mutate(source, change)
    _finish(source)
    print('OBSERVED', change, job.status, source.counts, len(job.output), source.manager.persistence.get(job.id)['status'])
    with pytest.raises(Exception):
        source.authority[0]()
    assert job.status == 'FAILED', 'revoked live source was published as COMPLETED'

@pytest.mark.parametrize('snapshot_required', [False, True])
def test_no_late_delta_after_source_archive(source, monkeypatch, snapshot_required):
    source.manager.snapshot_required = snapshot_required
    provider = source.runtime.providers['mock']
    original_stream = provider.stream
    revoked, late_chunks = [], []
    def stream(*args, **kwargs):
        first = True
        for chunk in original_stream(*args, **kwargs):
            if first:
                first = False
                yield chunk
                _mutate(source, 'archive')
                revoked.append(True)
            else:
                late_chunks.append(chunk)
                yield chunk
    monkeypatch.setattr(provider, 'stream', stream)
    job = _post(source)
    _finish(source)
    print('LATE', snapshot_required, job.status, len(job.output), len(''.join(late_chunks)), source.counts)
    assert revoked
    assert not late_chunks or ''.join(late_chunks) not in job.output, 'post-revocation deltas persisted in ordinary output'
