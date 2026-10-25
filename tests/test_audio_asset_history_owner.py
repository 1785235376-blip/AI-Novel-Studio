from __future__ import annotations
import base64
import hashlib
import json
import os
import multiprocessing
from pathlib import Path
import pytest
from app.services.asset_library_service import AssetLibraryService, AssetIdempotencyConflict
from app.services.audio_asset_history_store import AudioHistoryIntegrityError, AudioHistoryCapacityError
import app.services.audio_asset_history_store as history_store

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

def _hard_exit_worker(root, aid, stage):
    owner = AssetLibraryService(Path(root))
    def exit_at(actual):
        if actual == stage:
            os._exit(91)
    owner._audio_history_store.fault = exit_at
    owner.update_metadata(aid, {'parameters': {'take': 2}}, expected_version=1)
    os._exit(92)

@pytest.mark.parametrize('stage,expected_version', [('after_blob', 1), ('after_record', 1), ('before_current_commit', 1), ('after_current_commit', 2)])
def test_process_termination_recovers_committed_head_only(audio_owner, stage, expected_version):
    root, owner, row = audio_owner
    before = owner.audio_history(row['id'])['items'][0]
    ctx = multiprocessing.get_context('spawn')
    worker = ctx.Process(target=_hard_exit_worker, args=(str(root), row['id'], stage))
    try:
        worker.start()
        worker.join(timeout=25)
        assert not worker.is_alive(), f'child stuck at {stage}'
        assert worker.exitcode == 91, f'fault point {stage} not reached: {worker.exitcode}'
        restarted = AssetLibraryService(root)
        listing = restarted.audio_history(row['id'])
        assert listing['current_version'] == expected_version
        assert len(listing['items']) == expected_version
        assert listing['items'][-1] == before
        assert listing['head'] == listing['items'][0]['version_id']
        for item in listing['items']:
            assert_snapshot(restarted, row['id'], item)
        if expected_version == 1:
            restarted.update_metadata(row['id'], {'parameters': {'take': 2}}, expected_version=1)
            recovered = AssetLibraryService(root).audio_history(row['id'])
            assert recovered['current_version'] == 2
            assert len(recovered['items']) == 2
        else:
            assert listing['items'][0]['metadata']['parameters']['take'] == 2
    finally:
        if worker.is_alive():
            worker.terminate()
        if worker.pid is not None:
            worker.join(timeout=5)

def test_legacy_version_seven_is_not_backfilled_by_read(audio_owner):
    root, owner, row = audio_owner
    aid = row['id']
    meta_path = owner.root / (aid + '.json')
    metadata = json.loads(meta_path.read_text(encoding='utf-8'))
    metadata.pop('_audio_history_head', None)
    metadata['version'] = 7
    meta_path.write_text(json.dumps(metadata), encoding='utf-8')
    history_root = owner.root / '.audio-history' / aid
    before_files = {str(path.relative_to(history_root)): path.read_bytes() for path in history_root.rglob('*') if path.is_file()}
    before_meta = meta_path.read_bytes()
    restarted = AssetLibraryService(root)
    legacy = restarted.audio_history(aid)
    assert legacy['coverage'] == 'UNCAPTURED'
    assert legacy['head'] is None
    assert legacy['current_version'] == 7
    assert legacy['items'] == []
    assert meta_path.read_bytes() == before_meta
    assert {str(path.relative_to(history_root)): path.read_bytes() for path in history_root.rglob('*') if path.is_file()} == before_files
    restarted.update_metadata(aid, {'parameters': {'take': 8}}, expected_version=7)
    history = AssetLibraryService(root).audio_history(aid)
    assert history['coverage'] == 'PARTIAL'
    assert [item['asset_version'] for item in history['items']] == [8, 7]
    assert [item['history_sequence'] for item in history['items']] == [2, 1]
    assert history['items'][1]['parent_version_id'] is None
    assert history['items'][0]['parent_version_id'] == history['items'][1]['version_id']
    for item in history['items']:
        assert_snapshot(restarted, aid, item)

def test_create_exact_retry_has_one_snapshot_and_changed_payload_conflicts(audio_owner):
    root, owner, row = audio_owner
    before = owner.audio_history(row['id'])
    repeated = owner.create('synthetic-project', 'sound.wav', base64.b64encode(PAYLOAD).decode(), 'audio/wav', 'audio', idempotency_key='import-one')
    assert repeated['id'] == row['id']
    assert repeated['version'] == row['version']
    assert owner.audio_history(row['id']) == before
    with pytest.raises(AssetIdempotencyConflict):
        owner.create('synthetic-project', 'sound.wav', base64.b64encode(PAYLOAD + b'-changed').decode(), 'audio/wav', 'audio', idempotency_key='import-one')
    assert AssetLibraryService(root).audio_history(row['id']) == before

def _same_key_worker(root, ready, start, results):
    try:
        owner = AssetLibraryService(Path(root))
        ready.put(True)
        if not start.wait(20):
            results.put(('timeout', None, None))
            return
        row = owner.create('synthetic-project', 'sound.wav', base64.b64encode(PAYLOAD).decode(), 'audio/wav', 'audio', idempotency_key='parallel-import')
        results.put(('ok', row['id'], row['version']))
    except Exception as exc:
        results.put(('error', type(exc).__name__, str(exc)))

def test_two_process_same_key_create_returns_one_asset(tmp_path):
    ctx = multiprocessing.get_context('spawn')
    ready, start, results = ctx.Queue(), ctx.Event(), ctx.Queue()
    workers = [ctx.Process(target=_same_key_worker, args=(str(tmp_path), ready, start, results)) for _ in range(2)]
    try:
        for worker in workers:
            worker.start()
        assert ready.get(timeout=25) is True
        assert ready.get(timeout=25) is True
        start.set()
        outcomes = [results.get(timeout=25), results.get(timeout=25)]
        for worker in workers:
            worker.join(timeout=10)
            assert not worker.is_alive(), outcomes
            assert worker.exitcode == 0, outcomes
        assert all(item[0] == 'ok' for item in outcomes), outcomes
        assert outcomes[0][1] == outcomes[1][1], outcomes
        assert [item[2] for item in outcomes] == [1, 1]
        listing = AssetLibraryService(tmp_path).audio_history(outcomes[0][1])
        assert len(listing['items']) == 1
        assert listing['current_version'] == 1
        assert_snapshot(AssetLibraryService(tmp_path), outcomes[0][1], listing['items'][0])
    finally:
        start.set()
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            if worker.pid is not None:
                worker.join(timeout=5)
        ready.close()
        results.close()

def test_immutable_blob_digest_mismatch_fails_closed(audio_owner):
    root, owner, row = audio_owner
    record = owner.audio_history(row['id'])['items'][0]
    path = owner.root / '.audio-history' / row['id'] / 'blobs' / (record['sha256'] + '.bin')
    path.write_bytes(b'synthetic-corrupt-blob')
    with pytest.raises(AudioHistoryIntegrityError):
        AssetLibraryService(root).audio_history_content(row['id'], record['version_id'])

def test_immutable_record_digest_mismatch_fails_closed(audio_owner):
    root, owner, row = audio_owner
    record = owner.audio_history(row['id'])['items'][0]
    path = owner.root / '.audio-history' / row['id'] / 'records' / (record['version_id'] + '.bin')
    value = json.loads(path.read_text(encoding='utf-8'))
    value['metadata']['parameters'] = {'tampered': 'synthetic'}
    path.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(AudioHistoryIntegrityError):
        AssetLibraryService(root).audio_history_detail(row['id'], record['version_id'])

def test_formal_promotion_does_not_publish_older_private_snapshot(tmp_path):
    owner = AssetLibraryService(tmp_path)
    row = owner.create('synthetic-project', 'private.wav', base64.b64encode(PAYLOAD).decode(), 'audio/wav', 'audio', owner_actor_id='alice')
    aid = row['id']
    private = owner.audio_history(aid, actor_id='alice')['items'][0]
    owner.promote_owned(aid, actor_id='alice', branch_id=None, expected_version=1, provenance={'source': 'test'}, guard=lambda: None)
    current = owner.audio_history(aid, actor_id='alice')['items'][0]
    assert current['version_id'] != private['version_id']
    assert owner.audio_history_content(aid, current['version_id'], actor_id='bob') == PAYLOAD
    with pytest.raises(FileNotFoundError):
        owner.audio_history_detail(aid, private['version_id'], actor_id='bob')
    with pytest.raises(FileNotFoundError):
        owner.audio_history_content(aid, private['version_id'], actor_id='bob')
    assert owner.audio_history_content(aid, private['version_id'], actor_id='alice') == PAYLOAD

def test_chain_read_budget_rejects_mutation_before_current_commit(audio_owner, monkeypatch):
    root, owner, row = audio_owner
    aid = row['id']
    before = owner.audio_history(aid)
    record_path = owner.root / '.audio-history' / aid / 'records' / (before['head'] + '.bin')
    meta_path = owner.root / (aid + '.json')
    raw_before = meta_path.read_bytes()
    monkeypatch.setattr(history_store, 'MAX_CHAIN_BYTES', len(record_path.read_bytes()) + 100)
    with pytest.raises(AudioHistoryCapacityError):
        owner.update_metadata(aid, {'parameters': {'budget_probe': 'x' * 256}}, expected_version=1)
    assert meta_path.read_bytes() == raw_before
    restarted = AssetLibraryService(root)
    assert restarted.audio_history(aid) == before
    assert_snapshot(restarted, aid, before['items'][0])

def test_history_current_metadata_read_is_bounded(audio_owner):
    from app.services.asset_query_index import AssetQueryBudgetExceeded
    root, owner, row = audio_owner
    meta_path = owner.root / (row['id'] + '.json')
    with meta_path.open('ab') as stream:
        stream.write(b' ' * (1024 * 1024 + 1))
    with pytest.raises(AssetQueryBudgetExceeded):
        AssetLibraryService(root).audio_history(row['id'])

def test_internal_same_revision_write_allocates_new_revision_and_rejects_stale_head(audio_owner):
    from copy import deepcopy
    from app.services.audio_asset_history_store import AudioHistoryConflict
    root, owner, row = audio_owner
    stale = deepcopy(row)
    row['created_at'] = '2026-01-01T00:00:00+00:00'
    owner._write_meta(row)
    assert row['version'] == 2
    listing = owner.audio_history(row['id'])
    assert [item['asset_version'] for item in listing['items']] == [2, 1]
    assert listing['items'][1]['metadata']['created_at'] == stale['created_at']
    stale['created_at'] = '2026-01-02T00:00:00+00:00'
    with pytest.raises(AudioHistoryConflict):
        owner._write_meta(stale)
    assert AssetLibraryService(root).audio_history(row['id']) == listing

def test_history_capacity_preserves_original_disk_safety_reserve(audio_owner, monkeypatch):
    import shutil
    from collections import namedtuple
    from app.creative.storage_admission import StudioStorageAdmission
    root, owner, row = audio_owner
    before = owner.audio_history(row['id'])
    current = owner._meta_path(row['id']).read_bytes()
    usage = namedtuple('usage', 'total used free')
    monkeypatch.setattr(shutil, 'disk_usage', lambda _: usage(1024 ** 3, 0, StudioStorageAdmission.RESERVE_BYTES + 1))
    with pytest.raises(AudioHistoryCapacityError, match='AUDIO_HISTORY_LOW_SPACE'):
        owner.update_metadata(row['id'], {'parameters': {'low_space': True}}, expected_version=1)
    assert owner._meta_path(row['id']).read_bytes() == current
    assert AssetLibraryService(root).audio_history(row['id']) == before
