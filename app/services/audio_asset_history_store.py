from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import re
import stat
import tempfile
import time
from pathlib import Path

HEAD = '_audio_history_head'
ORIGIN = '_audio_history_restore_origin'
CONTRACT = 'audio-asset-history/1'
MAX_RECORD_BYTES = 512 * 1024
MAX_VERSIONS = 100
MAX_RETAINED_BYTES = 128 * 1024 * 1024
MAX_CHAIN_BYTES = 8 * 1024 * 1024
MAX_CHAIN_SECONDS = 5.0
DIGEST = re.compile(r'[a-f0-9]{64}')

class AudioHistoryIntegrityError(ValueError):
    pass

class AudioHistoryConflict(ValueError):
    pass

class AudioHistoryCapacityError(ValueError):
    pass

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def snapshot(meta):
    result = copy.deepcopy(meta)
    result.pop(HEAD, None)
    return result

def _regular(info):
    if (not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
        raise AudioHistoryIntegrityError('AUDIO_HISTORY_FILE_INVALID')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

def read_verified(path, *, trusted_root, expected_size, expected_digest, maximum, guard=lambda: None):
    if type(expected_size) is not int or not 0 < expected_size <= maximum:
        raise AudioHistoryIntegrityError('AUDIO_HISTORY_SIZE_INVALID')
    guard()
    if os.name == 'nt':
        from .asset_bounded_file_windows import (WindowsBoundedAssetError, read_windows_bounded_asset, windows_bounded_read_supported)
        if not windows_bounded_read_supported():
            raise ValueError('ASSET_BOUNDED_READ_UNSUPPORTED')
        try:
            data = read_windows_bounded_asset(path, trusted_root=trusted_root, expected_size=expected_size,
                expected_sha256=expected_digest, max_bytes=maximum, guard=guard)
        except WindowsBoundedAssetError as exc:
            guard()
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_CONTENT_INVALID') from exc
        guard()
        return data
    if not getattr(os, 'O_NOFOLLOW', 0) or not getattr(os, 'O_NONBLOCK', 0):
        raise ValueError('ASSET_BOUNDED_READ_UNSUPPORTED')
    fd = None
    try:
        before = _regular(path.lstat())
        if before[2] != expected_size:
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_SIZE_INVALID')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if _regular(os.fstat(fd)) != before:
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_FILE_CHANGED')
        handle = os.fdopen(fd, 'rb')
        fd = None
        with handle:
            parts, total, checksum = [], 0, hashlib.sha256()
            while total <= maximum:
                guard()
                block = handle.read(min(65536, maximum + 1 - total))
                guard()
                if not block:
                    break
                total += len(block)
                parts.append(block)
                checksum.update(block)
            if (_regular(os.fstat(handle.fileno())) != before or _regular(path.lstat()) != before
                    or total != expected_size or not hmac.compare_digest(checksum.hexdigest(), expected_digest)):
                raise AudioHistoryIntegrityError('AUDIO_HISTORY_CONTENT_INVALID')
        guard()
        return b''.join(parts)
    except OSError as exc:
        guard()
        raise AudioHistoryIntegrityError('AUDIO_HISTORY_CONTENT_UNAVAILABLE') from exc
    finally:
        if fd is not None:
            os.close(fd)

class AudioAssetHistoryStore:
    """Current metadata head is the sole commit point; reads never migrate.

    Caller holds original asset-library cross-process mutation lock. Unreachable
    prepared records and temp files are counted but never presented as history.
    """
    def __init__(self, asset_root: Path):
        self.asset_root = asset_root
        self.root = asset_root / '.audio-history'

    def fault(self, stage):
        """Test fault-injection seam. Production has no side effects."""

    @staticmethod
    def _directory(path, *, create=False):
        if create:
            try: path.mkdir()
            except FileExistsError: pass
        try: info = path.lstat()
        except FileNotFoundError: return False
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_DIRECTORY_INVALID')
        return True

    def paths(self, asset_id, *, create=False):
        if not isinstance(asset_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,239}', asset_id):
            raise ValueError('AUDIO_HISTORY_ASSET_INVALID')
        for path in (self.root, self.root / asset_id):
            if not self._directory(path, create=create): return None
        path = self.root / asset_id
        for name in ('records', 'blobs'):
            if not self._directory(path / name, create=create): return None
        return path

    @staticmethod
    def _sync_directory(path):
        if os.name != 'nt':
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try: os.fsync(fd)
            finally: os.close(fd)

    def _immutable(self, path, data, *, maximum):
        sha = hashlib.sha256(data).hexdigest()
        if path.exists() or path.is_symlink():
            read_verified(path, trusted_root=path.parent, expected_size=len(data), expected_digest=sha, maximum=maximum)
            return
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.prepared-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try: os.link(temporary, path)
            except FileExistsError:
                read_verified(path, trusted_root=path.parent, expected_size=len(data), expected_digest=sha, maximum=maximum)
            self._sync_directory(path.parent)
        finally:
            os.unlink(temporary)

    def _usage(self, path):
        total = count = 0
        for folder in ('records', 'blobs'):
            for item in (path / folder).iterdir():
                info = item.lstat()
                _regular(info)
                total += info.st_size
                count += 1
                if count > MAX_VERSIONS * 3 or total > MAX_RETAINED_BYTES:
                    raise AudioHistoryCapacityError('AUDIO_HISTORY_CAPACITY')
        return total

    def prepare(self, meta, data, parent=None):
        saved = snapshot(meta)
        if (saved.get('kind') != 'audio' or type(saved.get('version')) is not int or saved['version'] < 1
                or len(data) != saved.get('size') or hashlib.sha256(data).hexdigest() != saved.get('sha256')):
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_SNAPSHOT_INVALID')
        if parent is not None and (not isinstance(parent, str) or not DIGEST.fullmatch(parent)):
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_HEAD_INVALID')
        sequence = 1 if parent is None else self.record(saved['id'], parent)['history_sequence'] + 1
        if sequence > MAX_VERSIONS:
            raise AudioHistoryCapacityError('AUDIO_HISTORY_VERSION_LIMIT')
        record = {'contract': CONTRACT, 'asset_id': saved['id'], 'asset_version': saved['version'],
                  'history_sequence': sequence, 'parent_version_id': parent,
                  'metadata_digest': digest(saved), 'sha256': saved['sha256'],
                  'size': saved['size'], 'metadata': saved,
                  'created_at': saved.get('updated_at', saved.get('created_at'))}
        raw = encoded(record)
        if len(raw) > MAX_RECORD_BYTES:
            raise AudioHistoryCapacityError('AUDIO_HISTORY_METADATA_LIMIT')
        version_id = hashlib.sha256(raw).hexdigest()
        path = self.paths(saved['id'], create=True)
        blob = path / 'blobs' / (record['sha256'] + '.bin')
        target = path / 'records' / (version_id + '.bin')
        required = (0 if blob.exists() else len(data)) + (0 if target.exists() else len(raw))
        reserve = max(len(data) if not blob.exists() else 0, len(raw) if not target.exists() else 0)
        if self._usage(path) + required + reserve > MAX_RETAINED_BYTES:
            raise AudioHistoryCapacityError('AUDIO_HISTORY_CAPACITY')
        self._immutable(blob, data, maximum=25 * 1024 * 1024)
        self.fault('after_blob')
        self._immutable(target, raw, maximum=MAX_RECORD_BYTES)
        self.fault('after_record')
        return version_id

    def record(self, asset_id, version_id, *, guard=lambda: None, budget=None):
        if not isinstance(version_id, str) or not DIGEST.fullmatch(version_id):
            raise ValueError('AUDIO_HISTORY_VERSION_INVALID')
        path = self.paths(asset_id)
        if path is None:
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_RECORD_MISSING')
        target = path / 'records' / (version_id + '.bin')
        try:
            size = _regular(target.lstat())[2]
            if budget is not None:
                budget['bytes'] += size
                if budget['bytes'] > MAX_CHAIN_BYTES or time.monotonic() - budget['started'] > MAX_CHAIN_SECONDS:
                    raise AudioHistoryCapacityError('AUDIO_HISTORY_READ_BUDGET')
            raw = read_verified(target, trusted_root=target.parent, expected_size=size,
                expected_digest=version_id, maximum=MAX_RECORD_BYTES, guard=guard)
            record = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_RECORD_INVALID') from exc
        meta = record.get('metadata') if isinstance(record, dict) else None
        if (not isinstance(meta, dict) or record.get('contract') != CONTRACT
                or record.get('asset_id') != asset_id or meta.get('id') != asset_id
                or meta.get('kind') != 'audio' or HEAD in meta
                or type(record.get('asset_version')) is not int or record['asset_version'] < 1
                or type(record.get('history_sequence')) is not int or not 1 <= record['history_sequence'] <= MAX_VERSIONS
                or meta.get('version') != record['asset_version']
                or record.get('metadata_digest') != digest(meta)
                or record.get('sha256') != meta.get('sha256') or record.get('size') != meta.get('size')
                or not isinstance(record.get('sha256'), str) or not DIGEST.fullmatch(record['sha256'])
                or type(record.get('size')) is not int or not 0 < record['size'] <= 25 * 1024 * 1024
                or (record.get('parent_version_id') is not None and
                    (not isinstance(record['parent_version_id'], str) or not DIGEST.fullmatch(record['parent_version_id'])))):
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_RECORD_INVALID')
        return {**record, 'version_id': version_id}

    def chain(self, meta, *, guard=lambda: None):
        head = meta.get(HEAD)
        if HEAD not in meta: return []
        if not isinstance(head, str) or not DIGEST.fullmatch(head):
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_HEAD_INVALID')
        records, seen, previous = [], set(), None
        budget = {'bytes': 0, 'started': time.monotonic()}
        previous_sequence = None
        while head is not None:
            if len(records) >= MAX_VERSIONS or head in seen:
                raise AudioHistoryCapacityError('AUDIO_HISTORY_CHAIN_LIMIT')
            seen.add(head)
            record = self.record(meta['id'], head, guard=guard, budget=budget)
            if time.monotonic() - budget['started'] > MAX_CHAIN_SECONDS:
                raise AudioHistoryCapacityError('AUDIO_HISTORY_READ_BUDGET')
            if not records and record['metadata'] != snapshot(meta):
                raise AudioHistoryIntegrityError('AUDIO_HISTORY_CURRENT_MISMATCH')
            if previous is not None and record['asset_version'] != previous - 1:
                raise AudioHistoryIntegrityError('AUDIO_HISTORY_CHAIN_INVALID')
            if previous_sequence is not None and record['history_sequence'] != previous_sequence - 1:
                raise AudioHistoryIntegrityError('AUDIO_HISTORY_CHAIN_INVALID')
            records.append(record)
            previous_sequence = record['history_sequence']
            previous, head = record['asset_version'], record['parent_version_id']
        if records[-1]['history_sequence'] != 1:
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_CHAIN_INVALID')
        return records

    def content(self, record, *, maximum, guard=lambda: None):
        if type(maximum) is not int or not 1 <= maximum <= 25 * 1024 * 1024:
            raise ValueError('AUDIO_HISTORY_CONTENT_LIMIT')
        path = self.paths(record['asset_id'])
        if path is None:
            raise AudioHistoryIntegrityError('AUDIO_HISTORY_RECORD_MISSING')
        return read_verified(path / 'blobs' / (record['sha256'] + '.bin'), trusted_root=path / 'blobs',
            expected_size=record['size'], expected_digest=record['sha256'], maximum=maximum, guard=guard)

    def prepare_commit(self, owner, meta, *, guard=lambda: None):
        try: old = owner._load(meta['id'])
        except FileNotFoundError: old = None
        if old is not None:
            if old.get('kind') != 'audio':
                raise AudioHistoryIntegrityError('AUDIO_HISTORY_KIND_CHANGED')
            if snapshot(old) == snapshot(meta):
                self.chain(old, guard=guard)
                if old.get(HEAD) is None:
                    raise AudioHistoryConflict('AUDIO_HISTORY_CAPTURE_REQUIRED')
                return old[HEAD]
            if (type(meta.get('version')) is not int or meta['version'] != old.get('version', 0) + 1
                    or meta.get(HEAD) != old.get(HEAD)
                    or meta.get('_project_binding') != old.get('_project_binding')
                    or meta.get('sha256') != old.get('sha256') or meta.get('size') != old.get('size')):
                raise AudioHistoryConflict('AUDIO_HISTORY_STALE_HEAD')
            chain = self.chain(old, guard=guard)
            if len(chain) >= MAX_VERSIONS:
                raise AudioHistoryCapacityError('AUDIO_HISTORY_VERSION_LIMIT')
            parent = old.get(HEAD)
            if parent is None:
                before = owner._verified_content(old, max_bytes=owner.MAX_BYTES, guard=guard)
                parent = self.prepare(old, before)
        else:
            if meta.get(HEAD) is not None or meta.get('version') != 1:
                raise AudioHistoryConflict('AUDIO_HISTORY_NEW_ASSET_INVALID')
            parent = None
        data = owner._verified_content(meta, max_bytes=owner.MAX_BYTES, guard=guard)
        return self.prepare(meta, data, parent)
