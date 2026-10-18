"""ModelCenter-owned, explicitly admitted single-GGUF transfer lifecycle.

Production starts with no sources or destination. Synthetic injection does not
populate the catalog. This owner never registers, enables, loads or executes a
model, and never becomes a project/workflow scheduler.
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
import threading
import time
from uuid import uuid4

from pydantic import Field, ValidationError

from .transfer_files import (TransferFiles, MAX_TASKS, identity, signature, unlink_owned,
    open_directory, open_file, read_json, write_json, supported)
from .transfer_types import (ACTIVE_STATES, TRANSFER_STATES, ClosedInput,
    ReviewedTransferSource, TransferError, task_id)

CHUNK_BYTES = 256 * 1024
RESERVE_BYTES = 64 * 1024**2
PREVIEW_TTL = 120
EMPTY_SHA = hashlib.sha256(b'').hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class TransferRecord(ClosedInput):
    contract: str = 'studio-model-transfer-record/1'
    id: str = Field(pattern=r'^[a-f0-9]{32}$')
    source: ReviewedTransferSource
    source_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    root_identity: list[int] = Field(min_length=2, max_length=2)
    directory_identity: list[int] = Field(min_length=2, max_length=2)
    file_identity: list[int] = Field(min_length=2, max_length=2)
    state: str
    version: int = Field(ge=1, le=2**53 - 1)
    bytes_received: int = Field(ge=0)
    prefix_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    etag: str | None = Field(default=None, max_length=1024)
    error_code: str | None = Field(default=None, max_length=100)
    run_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    cleanup_pending: bool = False


class _Stop(Exception):
    def __init__(self, state, code=None):
        self.state, self.code = state, code


class ModelTransfers:
    def __init__(self, center, *, root=None, sources=(), transport=None,
                 disk_free=None, clock=time.time, quota_bytes=64 * 1024**3):
        if type(quota_bytes) is not int or not 8 <= quota_bytes <= 2**53 - 1:
            raise TransferError('MODEL_TRANSFER_QUOTA_INVALID')
        source_map = {}
        for item in sources:
            if (type(item) is not ReviewedTransferSource or item.id in source_map
                    or item.model_id not in center.models or len(source_map) >= 16):
                raise TransferError('MODEL_TRANSFER_SOURCE_INVALID')
            source_map[item.id] = item
        self.center, self.sources = center, source_map
        self.files = TransferFiles(root)
        self.clock, self.quota_bytes = clock, quota_bytes
        self._disk_free = disk_free or (lambda fd: os.fstatvfs(fd).f_bavail * os.fstatvfs(fd).f_frsize)
        self._transport = transport
        self._previews = {}
        self._preview_lock = threading.RLock()
        self._threads = set()
        self._closed = False

    def _ready(self):
        if not supported():
            raise TransferError('MODEL_TRANSFER_PLATFORM_UNSUPPORTED')
        if not self.sources:
            raise TransferError('DOWNLOAD_SOURCE_NOT_CONFIGURED')
        if self.files.root is None:
            raise TransferError('MODEL_TRANSFER_DESTINATION_NOT_CONFIGURED')
        if self._closed:
            raise TransferError('MODEL_TRANSFER_OWNER_CLOSED')

    def _source(self, source_id):
        self._ready()
        try:
            return self.sources[source_id]
        except KeyError:
            raise TransferError('DOWNLOAD_SOURCE_NOT_CONFIGURED') from None

    def _read(self, directory, identifier):
        identifier = task_id(identifier)
        task = open_directory(directory, identifier)
        try:
            raw, journal_identity = read_json(task, 'journal.json')
            try:
                record = TransferRecord.model_validate(raw)
            except ValidationError:
                raise TransferError('MODEL_TRANSFER_JOURNAL_INVALID') from None
            if (record.contract != 'studio-model-transfer-record/1' or record.id != identifier
                    or record.state not in TRANSFER_STATES or record.bytes_received > record.source.size_bytes
                    or record.source_digest != digest(record.source.model_dump())
                    or record.root_identity != self.files.root_identity
                    or record.directory_identity != identity(os.fstat(task))
                    or any(v < 0 for v in record.root_identity + record.directory_identity + record.file_identity)):
                raise TransferError('MODEL_TRANSFER_JOURNAL_INVALID')
            return record.model_dump(), journal_identity
        finally:
            os.close(task)

    def _all(self, directory, *, incomplete=None):
        rows = []
        for name in ([] if directory is None else self.files.task_names(directory)):
            try:
                rows.append(self._read(directory, name)[0])
            except (OSError, TransferError):
                if incomplete is None: raise TransferError('MODEL_TRANSFER_INCOMPLETE_OWNED_STATE') from None
                incomplete.append('MODEL_TRANSFER_INCOMPLETE_OWNED_STATE')
        return rows

    def _save(self, directory, row, journal_identity):
        try:
            TransferRecord.model_validate(row)
        except ValidationError:
            raise TransferError('MODEL_TRANSFER_JOURNAL_INVALID') from None
        task = open_directory(directory, row['id'], row['directory_identity'])
        try:
            return write_json(task, 'journal.json', row, expected=journal_identity)
        finally:
            os.close(task)

    def _capacity(self, root, rows, directory, *, excluding=None):
        try:
            free = self._disk_free(root)
        except OSError:
            raise TransferError('MODEL_TRANSFER_CAPACITY_UNAVAILABLE') from None
        if type(free) is not int or free < 0:
            raise TransferError('MODEL_TRANSFER_CAPACITY_UNAVAILABLE')
        used = 0
        for row in rows:
            if row['state'] == 'CLEANED': continue
            task = open_directory(directory, row['id'], row['directory_identity'])
            try:
                binary, _ = self._binary(task, row)
                try: allocated = os.fstat(binary).st_size
                finally: os.close(binary)
            finally: os.close(task)
            # Include uncheckpointed owned bytes after a failed write. Excluding
            # an active reservation still counts that task's allocated bytes.
            used += (max(allocated, row['source']['size_bytes'])
                     if row['id'] != excluding and row['state'] in ACTIVE_STATES | {'COMPLETED'} else allocated)
        return max(0, min(free - RESERVE_BYTES, self.quota_bytes - used))

    @staticmethod
    def _public(row):
        resumable = (row['state'] in {'PAUSED', 'INTERRUPTED'}
                     and (row['bytes_received'] in {0, row['source']['size_bytes']} or bool(row['etag'])))
        return {'id': row['id'], 'source_id': row['source']['id'], 'model_id': row['source']['model_id'],
            'display_name': row['source']['display_name'], 'state': row['state'], 'version': row['version'],
            'bytes_received': row['bytes_received'], 'total_bytes': row['source']['size_bytes'],
            'error_code': row['error_code'], 'can_resume': resumable}

    def snapshot(self, guard):
        guard()
        blockers = []
        if not supported(): blockers.append('MODEL_TRANSFER_PLATFORM_UNSUPPORTED')
        if not self.sources: blockers.append('DOWNLOAD_SOURCE_NOT_CONFIGURED')
        if self.files.root is None: blockers.append('MODEL_TRANSFER_DESTINATION_NOT_CONFIGURED')
        rows = []
        if supported() and self.files.root is not None:
            with self.files.access() as (_, directory):
                rows = self._all(directory, incomplete=blockers)
                if directory is not None:
                    try:
                        lease = self.files.lease(directory)
                    except TransferError as exc:
                        if exc.code != 'MODEL_TRANSFER_BUSY': raise
                    else:
                        try:
                            # No worker owns these states: persist truthful
                            # recovery without networking or touching weights.
                            for row in rows:
                                if row['cleanup_pending']:
                                    task = open_directory(directory, row['id'], row['directory_identity'])
                                    try:
                                        if self._owned_names(task) == {'journal.json'}:
                                            _, ji = self._read(directory, row['id'])
                                            row.update(state='CLEANED', version=row['version'] + 1, bytes_received=0,
                                                prefix_sha256=EMPTY_SHA, cleanup_pending=False, error_code=None)
                                            guard()
                                            self._save(directory, row, ji)
                                    finally: os.close(task)
                                if row['state'] in ACTIVE_STATES:
                                    _, ji = self._read(directory, row['id'])
                                    row.update(state='INTERRUPTED', version=row['version'] + 1,
                                               error_code='MODEL_TRANSFER_RESTARTED')
                                    guard()
                                    self._save(directory, row, ji)
                        finally:
                            os.close(lease)
        guard()
        return {'contract': 'studio-model-transfers/1', 'configured': not blockers,
            'platform_supported': supported(), 'blockers': blockers,
            'sources': [item.model_dump() for item in self.sources.values()],
            'items': [self._public(row) for row in rows]}

    def _remember(self, value, principal, *, private=None):
        if not principal:
            raise TransferError('MODEL_TRANSFER_HOST_PRINCIPAL_REQUIRED')
        with self._preview_lock:
            now = self.clock()
            self._previews = {key: row for key, row in self._previews.items() if row['expires_at'] > now}
            if len(self._previews) >= 16:
                raise TransferError('MODEL_TRANSFER_PREVIEW_LIMIT')
            result = {**value, 'preview_id': uuid4().hex, 'expires_at': now + PREVIEW_TTL}
            result['preview_digest'] = digest(result)
            self._previews[result['preview_id']] = {**result, '_principal': principal, '_task_id': None, **(private or {})}
            return result

    def _confirmation(self, value, principal, kind):
        with self._preview_lock:
            row = self._previews.get(value.preview_id)
            if (not row or row['_principal'] != principal or row['expires_at'] <= self.clock()
                    or row['preview_digest'] != value.preview_digest or row['contract'] != kind):
                raise TransferError('MODEL_TRANSFER_PREVIEW_STALE')
            return row

    def preview(self, source_id, principal, guard):
        guard()
        source = self._source(source_id)
        with self.files.access() as (root, directory):
            rows = self._all(directory)
            if len(rows) >= MAX_TASKS:
                raise TransferError('MODEL_TRANSFER_RECORD_LIMIT')
            available = self._capacity(root, rows, directory)
            if source.size_bytes > available:
                raise TransferError('MODEL_TRANSFER_LOW_SPACE_OR_QUOTA')
            guard()
            value = {'contract': 'studio-model-transfer-preview/1', 'source': source.model_dump(),
                'destination': str(self.files.root / '.studio-model-transfers'),
                'required_bytes': source.size_bytes, 'available_bytes': available,
                'reserve_bytes': RESERVE_BYTES}
        guard()
        return self._remember(value, principal)

    def start(self, value, principal, guard):
        guard()
        with self._preview_lock:
            preview = self._confirmation(value, principal, 'studio-model-transfer-preview/1')
            source = self._source(preview['source']['id'])
            if source.model_dump() != preview['source']:
                raise TransferError('MODEL_TRANSFER_SOURCE_CHANGED')
            if preview['_task_id']:
                return self.get(preview['_task_id'], guard)
            with self.files.access(create=True) as (root, directory):
                lease = self.files.lease(directory)
                try:
                    rows = self._all(directory)
                    if len(rows) >= MAX_TASKS: raise TransferError('MODEL_TRANSFER_RECORD_LIMIT')
                    if any(row['source_digest'] == digest(source.model_dump()) and row['state'] != 'CLEANED' for row in rows):
                        raise TransferError('MODEL_TRANSFER_ALREADY_OWNED')
                    if source.size_bytes > self._capacity(root, rows, directory):
                        raise TransferError('MODEL_TRANSFER_LOW_SPACE_OR_QUOTA')
                    guard()
                    identifier = uuid4().hex
                    os.mkdir(identifier, 0o700, dir_fd=directory)
                    task = open_directory(directory, identifier)
                    try:
                        binary = open_file(task, 'partial.gguf', writable=True, create=True)
                        try:
                            row = TransferRecord(id=identifier, source=source, source_digest=digest(source.model_dump()),
                                root_identity=self.files.root_identity, directory_identity=identity(os.fstat(task)),
                                file_identity=identity(os.fstat(binary)), state='TRANSFERRING', version=1,
                                bytes_received=0, prefix_sha256=EMPTY_SHA, run_id=uuid4().hex).model_dump()
                            write_json(task, 'journal.json', row)
                            os.fsync(task)
                        finally:
                            os.close(binary)
                    finally:
                        os.close(task)
                    os.fsync(directory)
                    preview['_task_id'] = identifier
                    try:
                        guard()
                    except Exception:
                        _, ji = self._read(directory, identifier)
                        row.update(state='INTERRUPTED', version=2, error_code='MODEL_TRANSFER_AUTHORITY_CHANGED')
                        self._save(directory, row, ji)
                        raise
                    self._launch(row, lease, guard)
                    lease = None
                    return self._public(row)
                finally:
                    if lease is not None: os.close(lease)

    def get(self, identifier, guard):
        guard()
        with self.files.access() as (_, directory):
            if directory is None: raise TransferError('MODEL_TRANSFER_NOT_FOUND')
            row, _ = self._read(directory, identifier)
        guard()
        return self._public(row)

    def control(self, identifier, action, version, guard):
        guard()
        with self.files.access() as (_, directory):
            if directory is None: raise TransferError('MODEL_TRANSFER_NOT_FOUND')
            row, ji = self._read(directory, identifier)
            if row['version'] != version: raise TransferError('MODEL_TRANSFER_VERSION_CONFLICT')
            if action == 'pause' and row['state'] == 'TRANSFERRING':
                target = 'PAUSING'
            elif action == 'cancel' and row['state'] in ACTIVE_STATES:
                target = 'CANCELLING'
            elif action == 'cancel' and row['state'] in {'PAUSED', 'INTERRUPTED', 'FAILED'}:
                target = 'CANCELLED'
            else:
                raise TransferError('MODEL_TRANSFER_TRANSITION_INVALID')
            guard()
            row.update(state=target, version=row['version'] + 1, error_code=None)
            self._save(directory, row, ji)
        guard()
        return self._public(row)

    def resume(self, identifier, version, guard):
        guard()
        self._ready()
        with self.files.access() as (root, directory):
            if directory is None: raise TransferError('MODEL_TRANSFER_NOT_FOUND')
            lease = self.files.lease(directory)
            try:
                row, ji = self._read(directory, identifier)
                if row['version'] != version: raise TransferError('MODEL_TRANSFER_VERSION_CONFLICT')
                if not self._public(row)['can_resume']: raise TransferError('MODEL_TRANSFER_RESUME_UNAVAILABLE')
                if self._source(row['source']['id']).model_dump() != row['source']:
                    raise TransferError('MODEL_TRANSFER_SOURCE_CHANGED')
                task = open_directory(directory, identifier, row['directory_identity'])
                try:
                    binary, _ = self._binary(task, row)
                    try: allocated = os.fstat(binary).st_size
                    finally: os.close(binary)
                finally: os.close(task)
                # Existing tail bytes will be verified/truncated by this
                # explicit resume before networking. Admission reserves net
                # additional growth, while capacity counts the whole tail.
                needed = max(0, row['source']['size_bytes'] - max(allocated, row['bytes_received']))
                if needed > self._capacity(root, self._all(directory), directory, excluding=identifier):
                    raise TransferError('MODEL_TRANSFER_LOW_SPACE_OR_QUOTA')
                guard()
                row.update(state='TRANSFERRING', version=row['version'] + 1, error_code=None, run_id=uuid4().hex)
                self._save(directory, row, ji)
                self._launch(row, lease, guard)
                lease = None
                return self._public(row)
            finally:
                if lease is not None: os.close(lease)

    def _launch(self, row, lease, guard):
        worker = threading.Thread(target=self._work, args=(row['id'], row['run_id'], lease, guard),
                                  name='model-center-transfer', daemon=True)
        self._threads.add(worker)
        try:
            worker.start()
        except BaseException:
            self._threads.discard(worker)
            raise

    def _check(self, identifier, run_id, guard):
        guard()
        if self._closed: raise _Stop('INTERRUPTED', 'MODEL_TRANSFER_OWNER_CLOSED')
        with self.files.access() as (_, directory):
            row, _ = self._read(directory, identifier)
            if row['run_id'] != run_id: raise _Stop('INTERRUPTED', 'MODEL_TRANSFER_WORKER_RETIRED')
            if row['state'] == 'CANCELLING': raise _Stop('CANCELLED')
            if row['state'] == 'PAUSING': raise _Stop('PAUSED')
            if row['state'] not in {'TRANSFERRING', 'VERIFYING'}:
                raise _Stop('INTERRUPTED', 'MODEL_TRANSFER_WORKER_RETIRED')
            if self._source(row['source']['id']).model_dump() != row['source']:
                raise TransferError('MODEL_TRANSFER_SOURCE_CHANGED')
            return row

    def _checkpoint(self, identifier, run_id, guard, *, received=None, prefix=None, etag=None, state=None):
        guard()
        with self.files.access() as (_, directory):
            row, ji = self._read(directory, identifier)
            if row['run_id'] != run_id: raise _Stop('INTERRUPTED', 'MODEL_TRANSFER_WORKER_RETIRED')
            # Control may have won after the write; preserve its request while
            # checkpointing bytes that were fsynced before it arrived.
            if received is not None: row.update(bytes_received=received, prefix_sha256=prefix)
            if etag is not None: row['etag'] = etag
            if state is not None and row['state'] == 'TRANSFERRING':
                row.update(state=state, version=row['version'] + 1)
            guard()
            self._save(directory, row, ji)
            return row

    def _finish(self, identifier, run_id, state, code=None):
        with self.files.access() as (_, directory):
            row, ji = self._read(directory, identifier)
            if row['run_id'] != run_id or row['state'] in {'COMPLETED', 'CLEANED'}: return
            if row['state'] == 'CANCELLING': state, code = 'CANCELLED', None
            elif row['state'] == 'PAUSING': state, code = 'PAUSED', None
            row.update(state=state, error_code=code, version=row['version'] + 1)
            self._save(directory, row, ji)

    @staticmethod
    def _owned_names(task):
        names = set(os.listdir(task))
        import re
        temporaries = {name for name in names if re.fullmatch(r'\.journal-[a-f0-9]{32}', name)}
        if len(temporaries) > 2:
            raise TransferError('MODEL_TRANSFER_METADATA_RECOVERY_REQUIRED')
        for name in temporaries:
            fd = open_file(task, name)
            try:
                if os.fstat(fd).st_size > 32 * 1024:
                    raise TransferError('MODEL_TRANSFER_METADATA_RECOVERY_REQUIRED')
            finally: os.close(fd)
        if not names - temporaries <= {'journal.json', 'partial.gguf', 'model.gguf'}:
            raise TransferError('MODEL_TRANSFER_OWNED_LAYOUT_INVALID')
        return names - temporaries

    def _binary(self, task, row, *, writable=False):
        names = self._owned_names(task)
        both = {'partial.gguf', 'model.gguf'} <= names
        name = 'partial.gguf' if 'partial.gguf' in names else 'model.gguf'
        binary = open_file(task, name, writable=writable, expected=row['file_identity'], links=2 if both else 1)
        try:
            if both:
                other = open_file(task, 'model.gguf', expected=row['file_identity'], links=2)
                os.close(other)
            if 'model.gguf' in names and row['bytes_received'] != row['source']['size_bytes']:
                raise TransferError('MODEL_TRANSFER_PUBLICATION_INVALID')
            return binary, names
        except BaseException:
            os.close(binary)
            raise

    def _work(self, identifier, run_id, lease, guard):
        task = binary = None
        try:
            row = self._check(identifier, run_id, guard)
            with self.files.access() as (_, directory):
                task = open_directory(directory, identifier, row['directory_identity'])
                binary, names = self._binary(task, row, writable=True)
            check = lambda: self._check(identifier, run_id, guard)
            check()
            size = os.fstat(binary).st_size
            if size < row['bytes_received'] or size > row['source']['size_bytes']:
                raise TransferError('MODEL_TRANSFER_PARTIAL_CHANGED')
            hasher = hashlib.sha256()
            left = row['bytes_received']
            while left:
                check()
                data = os.read(binary, min(CHUNK_BYTES, left))
                if not data: raise TransferError('MODEL_TRANSFER_PARTIAL_CHANGED')
                hasher.update(data); left -= len(data)
            if hasher.hexdigest() != row['prefix_sha256']:
                raise TransferError('MODEL_TRANSFER_PARTIAL_CHANGED')
            # Extra bytes were never committed to a checkpoint. Only the same
            # exclusive owned partial may be truncated, never a published file.
            if size > row['bytes_received']:
                if 'model.gguf' in names: raise TransferError('MODEL_TRANSFER_PUBLICATION_INVALID')
                check(); os.ftruncate(binary, row['bytes_received']); os.fsync(binary)
            received = row['bytes_received']
            if received < row['source']['size_bytes']:
                if self._transport is None:
                    from .transfer_transport import HttpsTransferTransport
                    transport = HttpsTransferTransport()
                else: transport = self._transport
                with transport.open(row['source']['url'], expected_size=row['source']['size_bytes'],
                                    offset=received, validator=row['etag'], guard=check) as stream:
                    self._checkpoint(identifier, run_id, guard, etag=stream.etag)
                    while received < row['source']['size_bytes']:
                        check()
                        with self.files.access() as (root, directory):
                            available = self._capacity(root, self._all(directory), directory, excluding=identifier)
                            if row['source']['size_bytes'] - received > available:
                                raise _Stop('PAUSED', 'MODEL_TRANSFER_LOW_SPACE_OR_QUOTA')
                        data = stream.read_chunk(min(CHUNK_BYTES, row['source']['size_bytes'] - received))
                        if not data: raise TransferError('MODEL_TRANSFER_TRUNCATED')
                        if not isinstance(data, bytes) or len(data) > min(CHUNK_BYTES, row['source']['size_bytes'] - received):
                            raise TransferError('MODEL_TRANSFER_SIZE_MISMATCH')
                        check()
                        # The response read can block while other disk users
                        # consume capacity. Admission must be current at write.
                        with self.files.access() as (root, directory):
                            if row['source']['size_bytes'] - received > self._capacity(root, self._all(directory), directory, excluding=identifier):
                                raise _Stop('PAUSED', 'MODEL_TRANSFER_LOW_SPACE_OR_QUOTA')
                        view = memoryview(data)
                        while view:
                            wrote = os.write(binary, view)
                            if wrote < 1: raise OSError('short write')
                            view = view[wrote:]
                        os.fsync(binary)
                        received += len(data); hasher.update(data)
                        self._checkpoint(identifier, run_id, guard, received=received, prefix=hasher.hexdigest())
                    if stream.read_chunk(1): raise TransferError('MODEL_TRANSFER_SIZE_MISMATCH')
            self._checkpoint(identifier, run_id, guard, state='VERIFYING')
            # Always verify bytes again, rather than promoting a rolling hash
            # whose earlier pages might have been changed during the transfer.
            check(); os.lseek(binary, 0, os.SEEK_SET)
            before_verify = signature(os.fstat(binary))
            verified = hashlib.sha256(); total = 0; header = b''
            while True:
                check(); data = os.read(binary, CHUNK_BYTES)
                if not data: break
                if total == 0: header = data[:8]
                verified.update(data); total += len(data)
                if total > row['source']['size_bytes']: raise TransferError('MODEL_TRANSFER_SIZE_MISMATCH')
            if (total != row['source']['size_bytes'] or verified.hexdigest() != row['source']['sha256']):
                raise TransferError('MODEL_TRANSFER_INTEGRITY_FAILED')
            if signature(os.fstat(binary)) != before_verify:
                raise TransferError('MODEL_TRANSFER_PARTIAL_CHANGED')
            if len(header) != 8 or header[:4] != b'GGUF' or int.from_bytes(header[4:], 'little') not in {2, 3}:
                raise TransferError('MODEL_TRANSFER_GGUF_INVALID')
            check()
            with self.files.access() as (_, directory):
                current, ji = self._read(directory, identifier)
                if current['run_id'] != run_id or current['state'] != 'VERIFYING':
                    raise _Stop('CANCELLED' if current['state'] == 'CANCELLING' else 'PAUSED')
                guard()
                same = open_directory(directory, identifier, row['directory_identity'])
                try:
                    check_fd, names = self._binary(same, current)
                    try:
                        if signature(os.fstat(check_fd)) != before_verify:
                            raise TransferError('MODEL_TRANSFER_PARTIAL_CHANGED')
                        if 'model.gguf' not in names:
                            os.link('partial.gguf', 'model.gguf', src_dir_fd=same, dst_dir_fd=same, follow_symlinks=False)
                            os.fsync(same)
                        # The pathname used by link() may have been replaced
                        # after an earlier open. Verify the actual new name
                        # before removing anything or issuing completion.
                        final = open_file(same, 'model.gguf', expected=current['file_identity'],
                                          links=2 if 'partial.gguf' in names else 1)
                        try:
                            info = os.fstat(final)
                            if info.st_size != total or info.st_mtime_ns != before_verify[3]:
                                raise TransferError('MODEL_TRANSFER_PARTIAL_CHANGED')
                        finally: os.close(final)
                        if 'partial.gguf' in names:
                            unlink_owned(same, 'partial.gguf', current['file_identity'], links=2)
                        guard()
                        current.update(state='COMPLETED', version=current['version'] + 1, error_code=None)
                        self._save(directory, current, ji)
                    finally:
                        os.close(check_fd)
                finally:
                    os.close(same)
        except _Stop as exc:
            self._safe_finish(identifier, run_id, exc.state, exc.code)
        except TransferError as exc:
            self._safe_finish(identifier, run_id, 'FAILED', exc.code)
        except OSError as exc:
            self._safe_finish(identifier, run_id, 'PAUSED' if exc.errno == errno.ENOSPC else 'FAILED',
                              'MODEL_TRANSFER_LOW_SPACE_OR_QUOTA' if exc.errno == errno.ENOSPC else 'MODEL_TRANSFER_IO_FAILED')
        except Exception as exc:
            # Host-authority and transport failures are safe fixed codes. No
            # filesystem paths, URLs, headers or credentials enter a journal.
            from .transfer_transport import TransferTransportError
            self._safe_finish(identifier, run_id, 'PAUSED',
                'MODEL_TRANSFER_NETWORK_FAILED' if isinstance(exc, TransferTransportError) else 'MODEL_TRANSFER_AUTHORITY_CHANGED')
        finally:
            if binary is not None: os.close(binary)
            if task is not None: os.close(task)
            os.close(lease)
            self._threads.discard(threading.current_thread())

    def _safe_finish(self, identifier, run_id, state, code):
        try:
            self._finish(identifier, run_id, state, code)
        except (OSError, TransferError):
            # A journal write may fail on a full disk. Its prior active state
            # is reconciled to INTERRUPTED on the next authorized read.
            pass

    def cleanup_preview(self, identifier, version, principal, guard):
        guard()
        with self.files.access() as (_, directory):
            if directory is None: raise TransferError('MODEL_TRANSFER_NOT_FOUND')
            row, _ = self._read(directory, identifier)
            if row['version'] != version: raise TransferError('MODEL_TRANSFER_VERSION_CONFLICT')
            if row['state'] not in {'PAUSED', 'INTERRUPTED', 'CANCELLED', 'FAILED'}:
                raise TransferError('MODEL_TRANSFER_CLEANUP_UNAVAILABLE')
            task = open_directory(directory, identifier, row['directory_identity'])
            try:
                binary, names = self._binary(task, row)
                try:
                    if 'model.gguf' in names: raise TransferError('MODEL_TRANSFER_CLEANUP_UNAVAILABLE')
                    size = os.fstat(binary).st_size
                    file_signature = signature(os.fstat(binary))
                finally: os.close(binary)
            finally: os.close(task)
            guard()
            value = {'contract': 'studio-model-transfer-cleanup/1', 'task_id': identifier,
                     'version': version, 'bytes': size}
        guard()
        return self._remember(value, principal, private={'_file_signature': file_signature})

    def cleanup(self, identifier, value, principal, guard):
        guard()
        with self._preview_lock:
            preview = self._confirmation(value, principal, 'studio-model-transfer-cleanup/1')
            if preview['task_id'] != identifier or preview['version'] != value.expected_version:
                raise TransferError('MODEL_TRANSFER_PREVIEW_STALE')
            with self.files.access() as (_, directory):
                if directory is None: raise TransferError('MODEL_TRANSFER_NOT_FOUND')
                lease = self.files.lease(directory)
                try:
                    row, ji = self._read(directory, identifier)
                    if preview['_task_id'] and row['state'] == 'CLEANED': return self._public(row)
                    if row['version'] != value.expected_version: raise TransferError('MODEL_TRANSFER_VERSION_CONFLICT')
                    if row['state'] not in {'PAUSED', 'INTERRUPTED', 'CANCELLED', 'FAILED'}:
                        raise TransferError('MODEL_TRANSFER_CLEANUP_UNAVAILABLE')
                    task = open_directory(directory, identifier, row['directory_identity'])
                    try:
                        binary, names = self._binary(task, row)
                        try:
                            if 'model.gguf' in names or os.fstat(binary).st_size != preview['bytes']:
                                raise TransferError('MODEL_TRANSFER_PREVIEW_STALE')
                            guard()
                            # Durable deletion intent lets recovery acknowledge
                            # an already-removed partial without deleting again.
                            row['cleanup_pending'] = True
                            ji = self._save(directory, row, ji)
                            guard()
                            unlink_owned(task, 'partial.gguf', row['file_identity'],
                                         expected_signature=preview['_file_signature'])
                        finally: os.close(binary)
                        row.update(state='CLEANED', version=row['version'] + 1, bytes_received=0,
                                   prefix_sha256=EMPTY_SHA, cleanup_pending=False, error_code=None)
                        self._save(directory, row, ji)
                        preview['_task_id'] = identifier
                    finally: os.close(task)
                    guard()
                    return self._public(row)
                finally: os.close(lease)

    def close(self):
        self._closed = True
        # Cooperative stop; DNS/socket bounds are owned by the transport. Never
        # claim every worker stopped merely because shutdown was requested.
