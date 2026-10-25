from __future__ import annotations
import base64
import hashlib
import multiprocessing
from pathlib import Path
import pytest
from app.services.asset_library_service import AssetLibraryService

PAYLOAD = b'RIFF-synthetic-audio-history-20261025'

@pytest.fixture
def audio_owner(tmp_path):
    owner = AssetLibraryService(tmp_path)
    row = owner.create('synthetic-project', 'sound.wav', base64.b64encode(PAYLOAD).decode(), 'audio/wav', 'audio', idempotency_key='import-one')
    return tmp_path, owner, row

def assert_snapshot(owner, aid, record, expected_bytes=PAYLOAD):
    version_id = record['version_id']
    assert len(version_id) == 64
    assert len(record['metadata_digest']) == 64
    assert record['sha256'] == hashlib.sha256(expected_bytes).hexdigest()
    assert record['size'] == len(expected_bytes)
    detail = owner.audio_history_detail(aid, version_id)
    assert detail['version'] == record
    assert owner.audio_history_content(aid, version_id) == expected_bytes

def test_create_snapshot_is_readable_after_owner_restart(audio_owner):
    root, owner, row = audio_owner
    listing = owner.audio_history(row['id'])
    assert listing['coverage'] == 'COMPLETE'
    assert listing['current_version'] == 1
    assert len(listing['items']) == 1
    record = listing['items'][0]
    assert record['asset_version'] == 1
    assert record['history_sequence'] == 1
    assert record['parent_version_id'] is None
    assert listing['head'] == record['version_id']
    assert_snapshot(owner, row['id'], record)
    restarted = AssetLibraryService(root)
    assert restarted.audio_history(row['id']) == listing
    assert_snapshot(restarted, row['id'], record)

def test_metadata_edit_preserves_old_record_and_old_bytes(audio_owner):
    root, owner, row = audio_owner
    aid = row['id']
    first = owner.audio_history(aid)['items'][0]
    old_record_path = owner.root / '.audio-history' / aid / 'records' / (first['version_id'] + '.bin')
    persisted_before = old_record_path.read_bytes()
    owner.update_metadata(aid, {'parameters': {'take': 2}}, expected_version=1)
    history = AssetLibraryService(root).audio_history(aid)
    assert history['current_version'] == 2
    assert [item['history_sequence'] for item in history['items']] == [2, 1]
    assert [item['asset_version'] for item in history['items']] == [2, 1]
    assert history['head'] == history['items'][0]['version_id']
    assert history['items'][0]['parent_version_id'] == first['version_id']
    assert history['items'][0]['metadata_digest'] != first['metadata_digest']
    assert history['items'][0]['metadata']['parameters']['take'] == 2
    assert history['items'][1] == first
    assert old_record_path.read_bytes() == persisted_before
    for item in history['items']:
        assert_snapshot(owner, aid, item)

def test_delete_and_undelete_capture_distinct_history_entries(audio_owner):
    root, owner, row = audio_owner
    aid = row['id']
    owner.delete(aid)
    owner.restore(aid)
    history = AssetLibraryService(root).audio_history(aid)
    assert history['current_version'] == 3
    assert [item['asset_version'] for item in history['items']] == [3, 2, 1]
    assert [item['history_sequence'] for item in history['items']] == [3, 2, 1]
    assert bool(history['items'][1]['metadata']['deleted_at'])
    assert history['items'][0]['metadata']['deleted_at'] is None
    for item in history['items']:
        assert_snapshot(owner, aid, item)

class InjectedHistoryCrash(RuntimeError):
    pass

@pytest.mark.parametrize('stage', ['after_blob', 'after_record', 'before_current_commit'])
def test_precommit_failure_keeps_old_head_and_retry_commits_once(audio_owner, monkeypatch, stage):
    root, owner, row = audio_owner
    aid = row['id']
    before = owner.audio_history(aid)
    fired = []
    def fail_at(actual):
        if actual == stage:
            fired.append(actual)
            raise InjectedHistoryCrash(stage)
    monkeypatch.setattr(owner._audio_history_store, 'fault', fail_at)
    with pytest.raises(InjectedHistoryCrash):
        owner.update_metadata(aid, {'parameters': {'take': 2}}, expected_version=1)
    assert fired == [stage]
    restarted = AssetLibraryService(root)
    assert restarted.audio_history(aid) == before
    assert_snapshot(restarted, aid, before['items'][0])
    restarted.update_metadata(aid, {'parameters': {'take': 2}}, expected_version=1)
    history = AssetLibraryService(root).audio_history(aid)
    assert history['current_version'] == 2
    assert len(history['items']) == 2
    assert history['items'][1] == before['items'][0]
    assert history['items'][0]['metadata']['parameters']['take'] == 2

def test_postcommit_failure_is_visible_once_after_restart(audio_owner, monkeypatch):
    root, owner, row = audio_owner
    aid = row['id']
    before = owner.audio_history(aid)
    fired = []
    def fail_at(actual):
        if actual == 'after_current_commit':
            fired.append(actual)
            raise InjectedHistoryCrash(actual)
    monkeypatch.setattr(owner._audio_history_store, 'fault', fail_at)
    with pytest.raises(InjectedHistoryCrash):
        owner.update_metadata(aid, {'parameters': {'take': 2}}, expected_version=1)
    assert fired == ['after_current_commit']
    restarted = AssetLibraryService(root)
    history = restarted.audio_history(aid)
    assert history['current_version'] == 2
    assert len(history['items']) == 2
    assert history['items'][1] == before['items'][0]
    assert history['items'][0]['metadata']['parameters']['take'] == 2
    assert_snapshot(restarted, aid, history['items'][0])

def _cas_worker(root, aid, take, ready, start, results):
    try:
        owner = AssetLibraryService(Path(root))
        ready.put(take)
        if not start.wait(20):
            results.put(('worker_timeout', take, None))
            return
        row = owner.update_metadata(aid, {'parameters': {'take': take}}, expected_version=1)
        results.put(('ok', take, row['version']))
    except Exception as exc:
        results.put(('error', take, type(exc).__name__ + ': ' + str(exc)))

def test_two_processes_compare_and_swap_only_one_commit(audio_owner):
    root, owner, row = audio_owner
    before = owner.audio_history(row['id'])['items'][0]
    ctx = multiprocessing.get_context('spawn')
    ready, results, start = ctx.Queue(), ctx.Queue(), ctx.Event()
    workers = [ctx.Process(target=_cas_worker, args=(str(root), row['id'], take, ready, start, results)) for take in (2, 3)]
    try:
        for worker in workers:
            worker.start()
        assert {ready.get(timeout=25), ready.get(timeout=25)} == {2, 3}
        start.set()
        outcomes = [results.get(timeout=25), results.get(timeout=25)]
        for worker in workers:
            worker.join(timeout=10)
            assert not worker.is_alive(), outcomes
            assert worker.exitcode == 0, outcomes
        successes = [outcome for outcome in outcomes if outcome[0] == 'ok']
        failures = [outcome for outcome in outcomes if outcome[0] == 'error']
        assert len(successes) == 1, outcomes
        assert len(failures) == 1, outcomes
        assert successes[0][2] == 2
        assert 'version' in failures[0][2].lower() or 'conflict' in failures[0][2].lower(), outcomes
        history = AssetLibraryService(root).audio_history(row['id'])
        assert history['current_version'] == 2
        assert len(history['items']) == 2
        assert history['items'][1] == before
        assert history['items'][0]['metadata']['parameters']['take'] == successes[0][1]
        assert history['items'][0]['parent_version_id'] == before['version_id']
    finally:
        start.set()
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            if worker.pid is not None:
                worker.join(timeout=5)
        ready.close()
        results.close()
