"""Owned synthetic bytes only; no network, models, providers or processes."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from app.model_center.transfer_types import (ReviewedTransferSource, ConfirmationInput,
    CleanupInput, ResumeInput, TransferError)
from app.model_center.transfers import ModelTransfers, RESERVE_BYTES
from app.model_center import transfer_files


DATA = b'GGUF\x03\0\0\0' + bytes(range(256)) * 8
GUARD = lambda: None


def source(data=DATA, **overrides):
    # Deliberately synthetic, never placed in production composition.
    values = dict(id='synthetic-fixture', model_id='fixture-model', display_name='Synthetic fixture',
        publisher='Fixture publisher', license_name='Fixture only', license_url='https://fixture.example.test/license',
        model_card_url='https://fixture.example.test/card', url='https://fixture.example.test/pinned/model.gguf',
        revision='synthetic-immutable-revision', size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return ReviewedTransferSource(**(values | overrides))


class FixtureTransport:
    def __init__(self, data=DATA, *, etag='"fixture-v1"', before_read=None, chunk=512):
        self.data, self.etag, self.before_read, self.chunk = data, etag, before_read, chunk
        self.calls, self.closed = [], 0

    @contextmanager
    def open(self, url, *, expected_size, offset, validator, guard):
        self.calls.append({'url': url, 'size': expected_size, 'offset': offset, 'validator': validator})
        transport = self
        class Stream:
            etag = transport.etag
            def __init__(self): self.position = offset
            def read_chunk(self, maximum):
                guard()
                if transport.before_read: transport.before_read(self.position)
                guard()
                data = transport.data[self.position:self.position + min(maximum, transport.chunk)]
                self.position += len(data)
                return data
        try: yield Stream()
        finally: self.closed += 1


def service(tmp_path, *, transport=None, sources=None, root=None, **kwargs):
    root = root or tmp_path / 'approved-model-destination'
    root.mkdir(mode=0o700, exist_ok=True)
    center = SimpleNamespace(models={'fixture-model': object()})
    return ModelTransfers(center, root=root, sources=sources or (source(),), transport=transport or FixtureTransport(),
        disk_free=kwargs.pop('disk_free', lambda fd: RESERVE_BYTES + len(DATA) * 100), **kwargs)


def start(svc, guard=GUARD, source_id='synthetic-fixture'):
    preview = svc.preview(source_id, 'principal-one', guard)
    confirmation = ConfirmationInput(preview_id=preview['preview_id'], preview_digest=preview['preview_digest'], confirmed=True)
    return svc.start(confirmation, 'principal-one', guard), confirmation


def settled(svc, identifier):
    for thread in list(svc._threads):
        thread.join(5)
        assert not thread.is_alive(), 'bounded fixture transfer did not stop'
    return svc.get(identifier, GUARD)


def artifact(svc, identifier, name='partial.gguf'):
    return svc.files.root / '.studio-model-transfers' / identifier / name


def paused(svc, offset=512):
    entered, release = threading.Event(), threading.Event()
    def block(position):
        if position == offset:
            entered.set(); assert release.wait(5)
    svc._transport.before_read = block
    row, confirmation = start(svc)
    assert entered.wait(5)
    before = svc.get(row['id'], GUARD)
    requested = svc.control(row['id'], 'pause', before['version'], GUARD)
    assert requested['state'] == 'PAUSING'
    release.set()
    return settled(svc, row['id']), confirmation


def test_default_owner_has_no_source_destination_or_side_effect(tmp_path):
    center = SimpleNamespace(models={'fixture-model': object()})
    svc = ModelTransfers(center)
    result = svc.snapshot(GUARD)
    assert result['sources'] == result['items'] == []
    assert not result['configured'] and 'DOWNLOAD_SOURCE_NOT_CONFIGURED' in result['blockers']
    with pytest.raises(TransferError, match='DOWNLOAD_SOURCE_NOT_CONFIGURED'):
        svc.preview('fixture-model', 'principal', GUARD)
    assert list(tmp_path.iterdir()) == []


def test_preview_only_and_exact_success_never_registers_or_executes(tmp_path):
    svc = service(tmp_path)
    preview = svc.preview('synthetic-fixture', 'principal-one', GUARD)
    assert preview['required_bytes'] == len(DATA) and preview['reserve_bytes'] == RESERVE_BYTES
    assert list(svc.files.root.iterdir()) == [] and svc._transport.calls == []
    row, confirmation = start(svc)
    done = settled(svc, row['id'])
    assert done['state'] == 'COMPLETED' and done['bytes_received'] == len(DATA)
    assert artifact(svc, row['id'], 'model.gguf').read_bytes() == DATA
    assert not artifact(svc, row['id']).exists()
    assert set(svc.center.models) == {'fixture-model'}
    assert svc.start(confirmation, 'principal-one', GUARD) == done
    assert len(svc._transport.calls) == 1


@pytest.mark.parametrize('field,value', [('url', 'http://fixture.example.test/model.gguf'),
    ('url', 'https://user:secret@fixture.example.test/model.gguf'), ('url', 'https://fixture.example.test/model.gguf?secret=x'),
    ('url', 'https://fixture.example.test/model.py'), ('sha256', '0'*63), ('size_bytes', True), ('size_bytes', 0)])
def test_invalid_source_inputs_rejected(field, value):
    data = source().model_dump(); data[field] = value
    with pytest.raises(ValueError): ReviewedTransferSource.model_validate(data)


@pytest.mark.parametrize('confirmed', [False, 1, 'true', None])
def test_confirmation_and_resume_require_literal_true(confirmed):
    with pytest.raises(ValueError):
        ConfirmationInput(preview_id='a'*32, preview_digest='b'*64, confirmed=confirmed)
    with pytest.raises(ValueError): ResumeInput(expected_version=1, confirmed=confirmed)


@pytest.mark.parametrize('wrong', ['principal', 'digest', 'expired'])
def test_preview_is_bound_and_never_writes_or_calls_network(tmp_path, wrong):
    now = [1000.0]
    svc = service(tmp_path, clock=lambda: now[0])
    preview = svc.preview('synthetic-fixture', 'principal-one', GUARD)
    if wrong == 'expired': now[0] += 121
    body = ConfirmationInput(preview_id=preview['preview_id'],
        preview_digest='a'*64 if wrong == 'digest' else preview['preview_digest'], confirmed=True)
    with pytest.raises(TransferError, match='PREVIEW_STALE'):
        svc.start(body, 'foreign' if wrong == 'principal' else 'principal-one', GUARD)
    assert svc._transport.calls == [] and list(svc.files.root.iterdir()) == []


def test_pause_resume_rehashes_prefix_and_uses_exact_offset(tmp_path):
    svc = service(tmp_path)
    row, _ = paused(svc)
    assert row['state'] == 'PAUSED' and row['bytes_received'] == 512 and row['can_resume']
    svc._transport.before_read = None
    svc.resume(row['id'], row['version'], GUARD)
    assert settled(svc, row['id'])['state'] == 'COMPLETED'
    assert [call['offset'] for call in svc._transport.calls] == [0, 512]
    assert svc._transport.calls[-1]['validator'] == '"fixture-v1"'


def test_tampered_partial_fails_before_resumed_network(tmp_path):
    svc = service(tmp_path)
    row, _ = paused(svc)
    artifact(svc, row['id']).write_bytes(b'X'*512)
    svc.resume(row['id'], row['version'], GUARD)
    done = settled(svc, row['id'])
    assert done['state'] == 'FAILED' and done['error_code'] == 'MODEL_TRANSFER_PARTIAL_CHANGED'
    assert len(svc._transport.calls) == 1 and not artifact(svc, row['id'], 'model.gguf').exists()


def test_no_etag_cannot_append_or_silently_restart(tmp_path):
    svc = service(tmp_path, transport=FixtureTransport(etag=None))
    row, _ = paused(svc)
    assert not row['can_resume']
    with pytest.raises(TransferError, match='RESUME_UNAVAILABLE'): svc.resume(row['id'], row['version'], GUARD)
    assert len(svc._transport.calls) == 1


def test_version_conflict_and_cancel_are_not_a_completion_claim(tmp_path):
    svc = service(tmp_path)
    row, _ = paused(svc)
    with pytest.raises(TransferError, match='VERSION_CONFLICT'): svc.control(row['id'], 'cancel', 1, GUARD)
    cancelled = svc.control(row['id'], 'cancel', row['version'], GUARD)
    assert cancelled['state'] == 'CANCELLED' and artifact(svc, row['id']).exists()


def test_confirmed_cleanup_removes_only_owned_partial_and_keeps_receipt(tmp_path):
    svc = service(tmp_path)
    external = svc.files.root / 'user-existing.gguf'; external.write_bytes(b'existing-user-file')
    row, _ = paused(svc)
    preview = svc.cleanup_preview(row['id'], row['version'], 'principal-one', GUARD)
    assert artifact(svc, row['id']).exists() and preview['bytes'] == 512
    body = CleanupInput(expected_version=row['version'], preview_id=preview['preview_id'], preview_digest=preview['preview_digest'], confirmed=True)
    result = svc.cleanup(row['id'], body, 'principal-one', GUARD)
    assert result['state'] == 'CLEANED' and not artifact(svc, row['id']).exists()
    assert artifact(svc, row['id'], 'journal.json').exists() and external.read_bytes() == b'existing-user-file'
    assert svc.cleanup(row['id'], body, 'principal-one', GUARD) == result


def test_cleanup_stale_file_identity_never_removes_replacement(tmp_path):
    svc = service(tmp_path); row, _ = paused(svc)
    preview = svc.cleanup_preview(row['id'], row['version'], 'principal-one', GUARD)
    part = artifact(svc, row['id']); part.rename(part.with_name('preserved-original'))
    part.write_bytes(b'user-file')
    body = CleanupInput(expected_version=row['version'], preview_id=preview['preview_id'], preview_digest=preview['preview_digest'], confirmed=True)
    with pytest.raises(TransferError): svc.cleanup(row['id'], body, 'principal-one', GUARD)
    assert part.read_bytes() == b'user-file'


@pytest.mark.parametrize('data,code', [(DATA[:-1], 'MODEL_TRANSFER_TRUNCATED'),
    (DATA[:-1]+b'X', 'MODEL_TRANSFER_INTEGRITY_FAILED'), (DATA+b'X', 'MODEL_TRANSFER_SIZE_MISMATCH')])
def test_bad_response_never_publishes(tmp_path, data, code):
    svc = service(tmp_path, transport=FixtureTransport(data))
    row, _ = start(svc); done = settled(svc, row['id'])
    assert done['state'] == 'FAILED' and done['error_code'] == code
    assert not artifact(svc, row['id'], 'model.gguf').exists()


def test_exact_hash_of_non_gguf_still_never_publishes(tmp_path):
    data = b'not-model-data'; svc = service(tmp_path, sources=(source(data),), transport=FixtureTransport(data))
    row, _ = start(svc); done = settled(svc, row['id'])
    assert done['error_code'] == 'MODEL_TRANSFER_GGUF_INVALID'


@pytest.mark.parametrize('free', [0, RESERVE_BYTES, -1, None, True])
def test_low_or_unknown_capacity_blocks_before_binary_mutation(tmp_path, free):
    svc = service(tmp_path, disk_free=lambda fd: free)
    with pytest.raises(TransferError): svc.preview('synthetic-fixture', 'principal-one', GUARD)
    assert list(svc.files.root.iterdir()) == [] and not svc._transport.calls


def test_low_disk_during_stream_pauses_without_auto_resume(tmp_path):
    free = [RESERVE_BYTES + len(DATA)*100]
    def change(position):
        if position == 0: free[0] = RESERVE_BYTES
    svc = service(tmp_path, disk_free=lambda fd: free[0], transport=FixtureTransport(before_read=change))
    row, _ = start(svc); done = settled(svc, row['id'])
    assert done['state'] == 'PAUSED' and done['error_code'] == 'MODEL_TRANSFER_LOW_SPACE_OR_QUOTA'
    assert done['bytes_received'] == 0 and len(svc._transport.calls) == 1


def test_revoked_authority_discards_inflight_chunk_without_publishing(tmp_path):
    active = [True]
    def guard():
        if not active[0]: raise RuntimeError('private token must not appear')
    svc = service(tmp_path, transport=FixtureTransport(before_read=lambda position: active.__setitem__(0, False)))
    row, _ = start(svc, guard); done = settled(svc, row['id'])
    assert done['state'] == 'PAUSED' and done['bytes_received'] == 0
    assert done['error_code'] == 'MODEL_TRANSFER_AUTHORITY_CHANGED'
    assert 'private token' not in artifact(svc, row['id'], 'journal.json').read_text()


def test_restart_never_downloads_and_requires_explicit_resume(tmp_path):
    svc = service(tmp_path); row, _ = paused(svc)
    path = artifact(svc, row['id'], 'journal.json'); stored = json.loads(path.read_text())
    stored['state'] = 'TRANSFERRING'; path.write_text(json.dumps(stored))
    restarted = service(tmp_path, root=svc.files.root)
    observed = restarted.snapshot(GUARD)['items'][0]
    assert observed['state'] == 'INTERRUPTED' and restarted._transport.calls == []
    restarted.resume(row['id'], observed['version'], GUARD)
    assert settled(restarted, row['id'])['state'] == 'COMPLETED'


def test_uncommitted_tail_is_rechecked_and_truncated_only_on_resume(tmp_path):
    svc = service(tmp_path); row, _ = paused(svc)
    with artifact(svc, row['id']).open('ab') as file: file.write(b'uncommitted')
    svc._transport.before_read = None
    svc.resume(row['id'], row['version'], GUARD)
    assert settled(svc, row['id'])['state'] == 'COMPLETED'
    assert artifact(svc, row['id'], 'model.gguf').read_bytes() == DATA


def test_duplicate_source_and_cross_owner_active_lease_fail_closed(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def block(position): entered.set(); assert release.wait(5)
    svc = service(tmp_path, transport=FixtureTransport(before_read=block)); row, _ = start(svc)
    assert entered.wait(5)
    other = service(tmp_path, root=svc.files.root)
    assert other.snapshot(GUARD)['items'][0]['state'] == 'TRANSFERRING'
    preview = other.preview('synthetic-fixture', 'principal-one', GUARD)
    body = ConfirmationInput(preview_id=preview['preview_id'], preview_digest=preview['preview_digest'], confirmed=True)
    with pytest.raises(TransferError, match='BUSY'): other.start(body, 'principal-one', GUARD)
    pending = other.control(row['id'], 'cancel', row['version'], GUARD)
    assert pending['state'] == 'CANCELLING'
    release.set(); assert settled(svc, row['id'])['state'] == 'CANCELLED'


def test_linked_root_or_partial_and_unsupported_platform_fail_closed(tmp_path, monkeypatch):
    target = tmp_path / 'real'; target.mkdir(mode=0o700)
    link = tmp_path / 'link'; link.symlink_to(target, target_is_directory=True)
    with pytest.raises(OSError): service(tmp_path, root=link)
    svc = service(tmp_path); row, _ = paused(svc)
    original = artifact(svc, row['id']); original.unlink()
    sentinel = tmp_path / 'user.gguf'; sentinel.write_bytes(b'untouched')
    original.symlink_to(sentinel)
    with pytest.raises(OSError): svc.resume(row['id'], row['version'], GUARD)
    assert len(svc._transport.calls) == 1 and sentinel.read_bytes() == b'untouched'
    monkeypatch.setattr('app.model_center.transfers.supported', lambda: False)
    assert not svc.snapshot(GUARD)['platform_supported']
    with pytest.raises(TransferError, match='PLATFORM_UNSUPPORTED'): svc.preview('synthetic-fixture', 'principal-one', GUARD)


@pytest.mark.parametrize('offset,other_size,quota', [(512, 2200, 4000), (2048, 1000, 3052)])
def test_resume_counts_own_partial_and_other_owned_bytes_even_near_completion(tmp_path, offset, other_size, quota):
    other = b'GGUF\x03\0\0\0' + b'Z' * (other_size - 8)
    svc = service(tmp_path, sources=(source(), source(other, id='second-fixture')), quota_bytes=quota,
                  transport=FixtureTransport(chunk=offset))
    row, _ = paused(svc, offset=offset)
    svc._transport = FixtureTransport(other)
    second, _ = start(svc, source_id='second-fixture')
    assert settled(svc, second['id'])['state'] == 'COMPLETED'
    assert offset + other_size <= quota < len(DATA) + other_size
    svc._transport = FixtureTransport()
    with pytest.raises(TransferError, match='LOW_SPACE_OR_QUOTA'):
        svc.resume(row['id'], row['version'], GUARD)
    assert not svc._transport.calls and artifact(svc, row['id']).stat().st_size == offset


def test_long_valid_etag_keeps_journal_and_snapshot_readable(tmp_path):
    svc = service(tmp_path, transport=FixtureTransport(etag='"' + 'a'*300 + '"'))
    row, _ = start(svc)
    assert settled(svc, row['id'])['state'] == 'COMPLETED'
    assert svc.snapshot(GUARD)['items'][0]['state'] == 'COMPLETED'


def test_cleanup_rechecks_leaf_after_last_authority_callback(tmp_path):
    svc = service(tmp_path); row, _ = paused(svc)
    preview = svc.cleanup_preview(row['id'], row['version'], 'principal-one', GUARD)
    part = artifact(svc, row['id'])
    count = [0]
    def guard():
        count[0] += 1
        if count[0] == 2:
            part.unlink(); part.write_bytes(b'foreign replacement')
    body = CleanupInput(expected_version=row['version'], preview_id=preview['preview_id'], preview_digest=preview['preview_digest'], confirmed=True)
    with pytest.raises(TransferError): svc.cleanup(row['id'], body, 'principal-one', guard)
    assert part.read_bytes() == b'foreign replacement'


def test_publication_collision_does_not_overwrite_or_delete_user_file(tmp_path, monkeypatch):
    svc = service(tmp_path)
    original = os.link
    def collide(src, dst, **kwargs):
        descriptor = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=kwargs['dst_dir_fd'])
        try: os.write(descriptor, b'user final')
        finally: os.close(descriptor)
        return original(src, dst, **kwargs)
    monkeypatch.setattr('app.model_center.transfers.os.link', collide)
    monkeypatch.setattr('app.model_center.transfer_files.supported', lambda: True)
    monkeypatch.setattr('app.model_center.transfers.supported', lambda: True)
    row, _ = start(svc); done = settled(svc, row['id'])
    assert done['state'] == 'FAILED'
    assert artifact(svc, row['id'], 'model.gguf').read_bytes() == b'user final'
    assert artifact(svc, row['id']).read_bytes() == DATA


def test_publication_detects_leaf_swap_inside_link_boundary_without_deleting_it(tmp_path, monkeypatch):
    svc = service(tmp_path)
    original = os.link
    def swap(src, dst, **kwargs):
        parent = kwargs['src_dir_fd']
        os.unlink(src, dir_fd=parent)
        descriptor = os.open(src, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent)
        try: os.write(descriptor, b'foreign partial')
        finally: os.close(descriptor)
        return original(src, dst, **kwargs)
    monkeypatch.setattr('app.model_center.transfers.os.link', swap)
    monkeypatch.setattr('app.model_center.transfer_files.supported', lambda: True)
    monkeypatch.setattr('app.model_center.transfers.supported', lambda: True)
    row, _ = start(svc); done = settled(svc, row['id'])
    assert done['state'] == 'FAILED' and done['error_code'] == 'MODEL_TRANSFER_PATH_IDENTITY_CHANGED'
    assert artifact(svc, row['id']).read_bytes() == b'foreign partial'


@pytest.mark.parametrize('retained_temporary', [False, True])
def test_removed_partial_reconciles_cleanup_metadata_without_removing_again(tmp_path, monkeypatch, retained_temporary):
    svc = service(tmp_path); row, _ = paused(svc)
    temporary = artifact(svc, row['id'], '.journal-'+'b'*32)
    if retained_temporary: temporary.write_bytes(b'preserved-interrupted-metadata')
    preview = svc.cleanup_preview(row['id'], row['version'], 'principal-one', GUARD)
    body = CleanupInput(expected_version=row['version'], preview_id=preview['preview_id'], preview_digest=preview['preview_digest'], confirmed=True)
    original = svc._save
    def fail_after_remove(directory, value, journal_identity):
        if value['state'] == 'CLEANED': raise OSError('synthetic interrupted final metadata commit')
        return original(directory, value, journal_identity)
    monkeypatch.setattr(svc, '_save', fail_after_remove)
    with pytest.raises(OSError): svc.cleanup(row['id'], body, 'principal-one', GUARD)
    assert not artifact(svc, row['id']).exists()
    recovered = service(tmp_path, root=svc.files.root)
    assert recovered.snapshot(GUARD)['items'][0]['state'] == 'CLEANED'
    assert not recovered._transport.calls
    if retained_temporary: assert temporary.read_bytes() == b'preserved-interrupted-metadata'


def test_exact_fit_resume_can_reclaim_its_verified_uncheckpointed_tail(tmp_path):
    svc = service(tmp_path, quota_bytes=len(DATA)); row, _ = paused(svc)
    with artifact(svc, row['id']).open('ab') as file: file.write(b'uncommitted')
    svc._transport.before_read = None
    svc.resume(row['id'], row['version'], GUARD)
    assert settled(svc, row['id'])['state'] == 'COMPLETED'


def test_preview_does_not_hold_file_lock_while_waiting_for_preview_lock(tmp_path, monkeypatch):
    svc = service(tmp_path)
    value = svc.preview('synthetic-fixture', 'principal-one', GUARD)
    body = ConfirmationInput(preview_id=value['preview_id'], preview_digest=value['preview_digest'], confirmed=True)
    waiting, release, started = threading.Event(), threading.Event(), threading.Event()
    remember = svc._remember
    errors = []
    def blocked(*args, **kwargs):
        waiting.set(); assert release.wait(5)
        return remember(*args, **kwargs)
    monkeypatch.setattr(svc, '_remember', blocked)
    def prepare():
        try: svc.preview('synthetic-fixture', 'principal-two', GUARD)
        except Exception as error: errors.append(error)
    def begin():
        try: svc.start(body, 'principal-one', GUARD); started.set()
        except Exception as error: errors.append(error)
    first = threading.Thread(target=prepare); first.start(); assert waiting.wait(5)
    second = threading.Thread(target=begin); second.start()
    try: assert started.wait(3), 'preview retained the file lock and blocked admission'
    finally: release.set(); first.join(5); second.join(5)
    for worker in list(svc._threads): worker.join(5)
    assert not first.is_alive() and not second.is_alive() and not errors


@pytest.mark.parametrize('partial', [False, True])
def test_incomplete_task_initialization_does_not_hide_valid_receipts_or_delete_files(tmp_path, partial):
    svc = service(tmp_path); row, _ = start(svc); settled(svc, row['id'])
    incomplete = svc.files.root / '.studio-model-transfers' / ('d'*32)
    incomplete.mkdir(mode=0o700)
    if partial: (incomplete/'partial.gguf').write_bytes(b'unknown-incomplete-owned-file')
    snapshot = svc.snapshot(GUARD)
    assert snapshot['items'][0]['state'] == 'COMPLETED'
    assert snapshot['blockers'] == ['MODEL_TRANSFER_INCOMPLETE_OWNED_STATE'] and not snapshot['configured']
    assert incomplete.exists()
    if partial: assert (incomplete/'partial.gguf').read_bytes() == b'unknown-incomplete-owned-file'
    with pytest.raises(TransferError, match='INCOMPLETE_OWNED_STATE'):
        svc.preview('synthetic-fixture', 'principal-one', GUARD)


def test_bounded_journal_temporary_is_retained_without_blocking_verified_resume(tmp_path):
    svc = service(tmp_path); row, _ = paused(svc)
    temporary = artifact(svc, row['id'], '.journal-'+'c'*32)
    temporary.write_bytes(b'unknown-interrupted-metadata')
    svc._transport.before_read = None
    svc.resume(row['id'], row['version'], GUARD)
    assert settled(svc, row['id'])['state'] == 'COMPLETED'
    assert temporary.read_bytes() == b'unknown-interrupted-metadata'


def test_incomplete_container_is_explicitly_blocked_and_never_deleted(tmp_path):
    svc = service(tmp_path)
    incomplete = svc.files.root / '.studio-model-transfers'; incomplete.mkdir(mode=0o700)
    with pytest.raises(TransferError, match='INITIALIZATION_INCOMPLETE'): svc.snapshot(GUARD)
    assert incomplete.is_dir() and not list(incomplete.iterdir()) and not svc._transport.calls


def test_completed_publication_with_interrupted_journal_requires_explicit_reconciliation(tmp_path, monkeypatch):
    svc = service(tmp_path)
    original = svc._save
    def interrupt(directory, row, journal_identity):
        if row['state'] == 'COMPLETED': raise RuntimeError('synthetic lost commit')
        return original(directory, row, journal_identity)
    monkeypatch.setattr(svc, '_save', interrupt)
    row, _ = start(svc); first = settled(svc, row['id'])
    assert first['state'] == 'PAUSED' and artifact(svc, row['id'], 'model.gguf').read_bytes() == DATA
    recovered = service(tmp_path, root=svc.files.root)
    current = recovered.snapshot(GUARD)['items'][0]
    recovered.resume(row['id'], current['version'], GUARD)
    assert settled(recovered, row['id'])['state'] == 'COMPLETED' and not recovered._transport.calls


def test_guard_revocation_after_initial_record_keeps_truthful_recoverable_operation(tmp_path, monkeypatch):
    svc = service(tmp_path)
    guard_active = [True]
    original = __import__('app.model_center.transfers', fromlist=['write_json']).write_json
    def write_and_revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[1] == 'journal.json': guard_active[0] = False
        return result
    monkeypatch.setattr('app.model_center.transfers.write_json', write_and_revoke)
    def guard():
        if not guard_active[0]: raise RuntimeError('revoked')
    with pytest.raises(RuntimeError, match='revoked'): start(svc, guard)
    state = svc.snapshot(GUARD)
    assert state['items'][0]['state'] == 'INTERRUPTED' and state['configured']
    assert not svc._transport.calls
