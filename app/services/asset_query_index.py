"""Bounded, disposable metadata acceleration for the existing File asset owner.

Callers must hold the owner's existing asset-library mutation lease throughout
snapshot, candidate iteration, owner revalidation and verify. This module never
authorizes an asset and never writes its source JSON or binary. Every query still
enumerates source metadata signatures; it is not an O(page-size) filesystem API.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid


class AssetQueryBudgetExceeded(Exception):
    def __init__(self):
        super().__init__("ASSET_QUERY_BUDGET_EXCEEDED")


class AssetQueryChanged(Exception):
    def __init__(self):
        super().__init__("ASSET_QUERY_RESTART_REQUIRED")


class AssetQueryUnavailable(Exception):
    def __init__(self):
        super().__init__("ASSET_QUERY_INDEX_UNAVAILABLE")


class _RebuildRequired(Exception):
    pass


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _stat_signature(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


@lru_cache(maxsize=1)
def _windows_signature_api():
    """Cache API declarations only; never cache a source handle or its state."""
    import ctypes
    from ctypes import wintypes

    class BasicInfo(ctypes.Structure):
        _fields_ = [(name, ctypes.c_int64) for name in
            ("creation", "access", "write", "change")] + [("attributes", wintypes.DWORD)]

    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    dll.CreateFileW.restype = wintypes.HANDLE
    dll.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
        ctypes.c_void_p, wintypes.DWORD]
    dll.GetFileInformationByHandleEx.restype = wintypes.BOOL
    dll.CloseHandle.argtypes = [wintypes.HANDLE]
    dll.CloseHandle.restype = wintypes.BOOL
    return dll, BasicInfo


def _windows_signature(path, value):
    """Read native ChangeTime, not Python 3.11's Windows creation-time ctime.

    FILE_READ_ATTRIBUTES reads no content. OPEN_REPARSE_POINT prevents following
    a replacement leaf link; the brief handle denies writers/deletion while its
    identity and time are observed. Existing owner leases still span the query.
    Missing native support fails closed, never reuses an untrustworthy cache.
    """
    import ctypes
    import msvcrt

    handle, descriptor = None, None
    try:
        dll, BasicInfo = _windows_signature_api()
        name = os.path.abspath(path)
        if not name.startswith("\\\\?\\"):
            name = "\\\\?\\UNC\\" + name[2:] if name.startswith("\\\\") else "\\\\?\\" + name
        # FILE_READ_ATTRIBUTES, FILE_SHARE_READ, OPEN_EXISTING,
        # FILE_FLAG_OPEN_REPARSE_POINT. No creation or content read is allowed.
        handle = dll.CreateFileW(name, 0x80, 0x1, None, 3, 0x00200000, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            handle = None
            raise AssetQueryUnavailable()
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        handle = None  # descriptor owns the native handle from this point.
        opened = os.fstat(descriptor)
        basic = BasicInfo()
        if not dll.GetFileInformationByHandleEx(msvcrt.get_osfhandle(descriptor), 0,
                ctypes.byref(basic), ctypes.sizeof(basic)):
            raise AssetQueryUnavailable()
        if (not stat.S_ISREG(opened.st_mode) or basic.attributes & (0x400 | 0x10)
                or basic.change <= 0):
            raise AssetQueryUnavailable()
        expected = _stat_signature(value)
        if _stat_signature(opened) != expected or _stat_signature(os.lstat(path)) != expected:
            raise AssetQueryChanged()
        return (*expected[:-1], basic.change)
    except (OSError, AttributeError, ImportError, ValueError):
        raise AssetQueryUnavailable() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        elif handle is not None:
            dll.CloseHandle(handle)


def _signature(value, path):
    return _windows_signature(path, value) if os.name == "nt" else _stat_signature(value)


def _revision(fingerprints):
    digest = hashlib.sha256()
    for name, signature in fingerprints:
        digest.update(_json([name, signature]).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


@dataclass(frozen=True)
class AssetQuerySnapshot:
    revision: str
    fingerprints: tuple
    index_identity: tuple


class FileAssetQueryIndex:
    """A derived SQLite index with bounded source reconciliation and cold reopen.

    Source signatures include change time, inode and size, so an in-place edit is not
    mistaken for an unchanged directory. This detects ordinary writes; it does
    not defend against a privileged local actor forging filesystem metadata.
    A revision conservatively covers all asset metadata, including other scopes.
    """

    # Old Windows signatures contained creation time and must be rebuilt once.
    FORMAT_VERSION = "2-windows-change-time" if os.name == "nt" else "1"
    MAX_METADATA_FILES = 50_000
    MAX_DIRECTORY_ENTRIES = 200_000
    MAX_METADATA_BYTES = 1024 * 1024
    MAX_SOURCE_BYTES = 256 * 1024 * 1024
    MAX_INDEX_BYTES = 512 * 1024 * 1024
    MAX_INDEX_DIRECTORY_ENTRIES = 128
    MAX_INDEX_DIRECTORY_BYTES = MAX_INDEX_BYTES * 4
    MAX_INDEX_JOURNAL_HEADROOM_BYTES = 32 * 1024 * 1024
    # Capacity for first cursor provisioning belongs to the same bounded store.
    # The identity marker is currently 88 bytes; reserve room for its framing.
    CURSOR_RESERVED_FILES = {"cursor.key": 32, "cursor.identity": 128}
    MAX_OPERATION_SECONDS = 30.0
    COLUMNS = ("name", "fingerprint", "asset_id", "novel_id", "binding",
               "filename_folded", "kind", "created_at", "payload")

    def __init__(self, asset_root: Path):
        self.root = Path(asset_root)
        self.directory = self.root / ".asset-query-index"
        self.path = self.directory / "index.sqlite3"
        self._verified_identity = None
        self._verified_revision = None

    def _deadline(self):
        return time.monotonic() + self.MAX_OPERATION_SECONDS

    @staticmethod
    def _check_time(deadline):
        if time.monotonic() > deadline:
            raise AssetQueryBudgetExceeded()

    def _scan(self, deadline):
        entries, source_bytes, fingerprints = 0, 0, []
        try:
            with os.scandir(self.root) as directory:
                for entry in directory:
                    entries += 1
                    if entries > self.MAX_DIRECTORY_ENTRIES:
                        raise AssetQueryBudgetExceeded()
                    self._check_time(deadline)
                    if not entry.name.endswith(".json"):
                        continue
                    entry.name.encode("utf-8")
                    if len(fingerprints) >= self.MAX_METADATA_FILES:
                        raise AssetQueryBudgetExceeded()
                    # Windows DirEntry.stat may omit inode/device identity.
                    info = os.lstat(entry.path) if os.name == "nt" else entry.stat(follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        raise AssetQueryUnavailable()
                    if info.st_size > self.MAX_METADATA_BYTES:
                        raise AssetQueryBudgetExceeded()
                    source_bytes += info.st_size
                    if source_bytes > self.MAX_SOURCE_BYTES:
                        raise AssetQueryBudgetExceeded()
                    fingerprints.append((entry.name, _signature(info, entry.path)))
        except FileNotFoundError:
            raise AssetQueryChanged() from None
        except (OSError, UnicodeError):
            raise AssetQueryUnavailable() from None
        return tuple(sorted(fingerprints))

    def _ensure_directory(self):
        try:
            if not self.directory.exists():
                self.directory.mkdir(mode=0o700)
            info = self.directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or self.directory.is_symlink():
                raise AssetQueryUnavailable()
            if os.name != "nt" and stat.S_IMODE(info.st_mode) != 0o700:
                raise AssetQueryUnavailable()
        except OSError:
            raise AssetQueryUnavailable() from None

    def _directory_usage(self, deadline, *, reserve_bytes=0, reserve_entries=0):
        """Bound retained crash evidence without deleting prior artifacts.

        Before rebuilding, reserve a full staging database and rollback journal.
        Unknown ordinary files, cursor key files and interrupted builds all count.
        Missing cursor files retain capacity before their first provisioning.
        The original asset lease serializes cooperating derived-directory writers.
        This is a capacity preflight and observed-size check, not an OS quota;
        reserved journal headroom allows for SQLite page/sector framing overhead.
        """
        entries, size = reserve_entries, reserve_bytes
        missing_cursor = dict(self.CURSOR_RESERVED_FILES)
        try:
            with os.scandir(self.directory) as directory:
                for entry in directory:
                    self._check_time(deadline)
                    entries += 1
                    if entries > self.MAX_INDEX_DIRECTORY_ENTRIES:
                        raise AssetQueryBudgetExceeded()
                    info = entry.stat(follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        raise AssetQueryUnavailable()
                    missing_cursor.pop(entry.name, None)
                    size += info.st_size
                    if size > self.MAX_INDEX_DIRECTORY_BYTES:
                        raise AssetQueryBudgetExceeded()
        except OSError:
            raise AssetQueryUnavailable() from None
        entries += len(missing_cursor)
        size += sum(missing_cursor.values())
        if entries > self.MAX_INDEX_DIRECTORY_ENTRIES or size > self.MAX_INDEX_DIRECTORY_BYTES:
            raise AssetQueryBudgetExceeded()

    def _index_identity(self):
        # Canonical databases are published only after a closed DELETE-journal
        # transaction. A live sidecar can never belong to this publication path.
        # Reject it even when the main file stat still matches the warm cache.
        for suffix in ("-wal", "-shm", "-journal"):
            try:
                Path(str(self.path) + suffix).lstat()
            except FileNotFoundError:
                continue
            except OSError:
                raise AssetQueryUnavailable() from None
            raise AssetQueryUnavailable()
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return None
        except OSError:
            raise AssetQueryUnavailable() from None
        if not stat.S_ISREG(info.st_mode) or self.path.is_symlink():
            raise AssetQueryUnavailable()
        if info.st_size > self.MAX_INDEX_BYTES:
            raise AssetQueryBudgetExceeded()
        return _signature(info, self.path)

    def _connect(self, path, *, readonly=False):
        if readonly:
            connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5)
        else:
            connection = sqlite3.connect(path, timeout=5)
        # Bound SQLite's own cell/row allocation before a damaged cell can be
        # materialized in Python. Valid derived rows fit within this ceiling.
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, self.MAX_METADATA_BYTES * 8)
        if not readonly:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _bounded_tables(self, connection):
        """Validate size/type in SQL before fetching untrusted derived cells."""
        if connection.execute("SELECT COUNT(*) FROM metadata").fetchone()[0] > 16:
            raise _RebuildRequired()
        if connection.execute("""SELECT 1 FROM metadata WHERE
                typeof(key) != 'text' OR length(CAST(key AS BLOB)) > 128 OR
                typeof(value) != 'text' OR length(CAST(value AS BLOB)) > 1024 LIMIT 1""").fetchone():
            raise _RebuildRequired()
        if connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0] > self.MAX_METADATA_FILES:
            raise _RebuildRequired()
        ceilings = {"name": 255, "fingerprint": 256, "asset_id": 240,
                    "novel_id": self.MAX_METADATA_BYTES, "binding": self.MAX_METADATA_BYTES,
                    "filename_folded": self.MAX_METADATA_BYTES * 2,
                    "kind": self.MAX_METADATA_BYTES, "created_at": self.MAX_METADATA_BYTES,
                    "payload": self.MAX_METADATA_BYTES, "row_digest": 64}
        nullable = set(self.COLUMNS[2:])
        predicates, parameters = [], []
        for column, ceiling in ceilings.items():
            predicate = f"(typeof({column}) != 'text' OR length(CAST({column} AS BLOB)) > ?)"
            if column in nullable:
                predicate = f"({column} IS NOT NULL AND {predicate})"
            predicates.append(predicate)
            parameters.append(ceiling)
        if connection.execute("SELECT 1 FROM sources WHERE " + " OR ".join(predicates) + " LIMIT 1", parameters).fetchone():
            raise _RebuildRequired()

    def _state(self, identity, deadline):
        if identity == self._verified_identity:
            return self._verified_revision
        try:
            with closing(self._connect(self.path, readonly=True)) as connection:
                connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                if connection.execute("PRAGMA quick_check(1)").fetchall() != [("ok",)]:
                    raise _RebuildRequired()
                self._bounded_tables(connection)
                metadata = dict(connection.execute("SELECT key, value FROM metadata"))
                if (metadata.get("format") != self.FORMAT_VERSION
                        or metadata.get("source_root") != _hash(str(self.root.resolve()))):
                    raise _RebuildRequired()
                aggregate, fingerprints, count = hashlib.sha256(), [], 0
                # Validate all derived columns, including SQL filtering columns:
                # a damaged filename/kind must not silently hide a matching row.
                for record in connection.execute("SELECT " + ",".join(self.COLUMNS) + ", row_digest FROM sources ORDER BY name"):
                    self._check_time(deadline)
                    count += 1
                    if count > self.MAX_METADATA_FILES:
                        raise AssetQueryBudgetExceeded()
                    values, expected_digest = record[:-1], record[-1]
                    if _hash(values) != expected_digest:
                        raise _RebuildRequired()
                    signature = json.loads(values[1])
                    if (not isinstance(values[0], str) or not values[0].endswith(".json")
                            or not isinstance(signature, list) or len(signature) != 6
                            or any(type(value) is not int for value in signature)):
                        raise _RebuildRequired()
                    fingerprints.append((values[0], tuple(signature)))
                    aggregate.update((expected_digest + "\n").encode("ascii"))
                if (metadata.get("rows_digest") != aggregate.hexdigest()
                        or metadata.get("count") != str(count)
                        or metadata.get("revision") != _revision(fingerprints)):
                    raise _RebuildRequired()
                revision = metadata["revision"]
        except (sqlite3.DatabaseError, UnicodeError, ValueError, TypeError, KeyError):
            self._check_time(deadline)
            raise _RebuildRequired() from None
        if self._index_identity() != identity:
            raise AssetQueryChanged()
        self._verified_identity, self._verified_revision = identity, revision
        return revision

    def _rebuild_checkpoint(self, phase):
        """Internal fault-injection seam for subprocess recovery tests only."""

    def _row_values(self, name, signature, loader):
        try:
            payload = loader(name[:-5])
        except (ValueError, FileNotFoundError):
            # Exactly the original AssetLibraryService.list exclusion policy.
            payload = None
        except OSError:
            raise AssetQueryUnavailable() from None
        if payload is None:
            return (name, _json(signature), None, None, None, None, None, None, None)
        if not isinstance(payload, dict):
            raise AssetQueryUnavailable()
        binding = payload.get("_project_binding")
        return (name, _json(signature), payload.get("id"),
                payload.get("novel_id") if isinstance(payload.get("novel_id"), str) else None,
                _json(binding) if isinstance(binding, dict) else None,
                str(payload.get("filename", "")).casefold(),
                payload.get("kind") if isinstance(payload.get("kind"), str) else None,
                payload.get("created_at", "") if isinstance(payload.get("created_at", ""), str) else None,
                _json(payload))

    def _build(self, fingerprints, revision, loader, deadline, *, reuse, previous_identity):
        staging = self.directory / ("building-" + uuid.uuid4().hex + ".sqlite3")
        connection = None
        try:
            self._directory_usage(deadline, reserve_bytes=(self.MAX_INDEX_BYTES * 2
                                                          + self.MAX_INDEX_JOURNAL_HEADROOM_BYTES),
                                  reserve_entries=2)
            descriptor = os.open(staging, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            connection = self._connect(staging)
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            if reuse:
                if self._index_identity() != previous_identity:
                    raise AssetQueryChanged()
                with closing(self._connect(self.path, readonly=True)) as source:
                    source.backup(connection, pages=128,
                                  progress=lambda status, remaining, total: self._check_time(deadline))
                if self._index_identity() != previous_identity:
                    raise AssetQueryChanged()
            else:
                connection.executescript("""
                    CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE sources (
                        name TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                        asset_id TEXT, novel_id TEXT, binding TEXT, filename_folded TEXT,
                        kind TEXT, created_at TEXT, payload TEXT, row_digest TEXT NOT NULL);
                    CREATE INDEX scoped_order ON sources(novel_id, binding, created_at, asset_id);
                    CREATE INDEX scoped_kind_order ON sources(novel_id, binding, kind, created_at, asset_id);
                """)
            # SQLite bounds the staging DB while growing, before the final
            # filesystem size check. Backup itself is bounded by the old DB cap.
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            connection.execute(f"PRAGMA max_page_count={self.MAX_INDEX_BYTES // page_size}")
            existing = dict(connection.execute("SELECT name, fingerprint FROM sources"))
            connection.execute("BEGIN IMMEDIATE")
            current_names = set()
            for name, signature in fingerprints:
                self._check_time(deadline)
                current_names.add(name)
                if existing.get(name) == _json(signature):
                    continue
                values = self._row_values(name, signature, loader)
                connection.execute("INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)",
                                   (*values, _hash(values)))
                self._rebuild_checkpoint("row")
            for name in existing.keys() - current_names:
                connection.execute("DELETE FROM sources WHERE name=?", (name,))
            aggregate = hashlib.sha256()
            for (digest,) in connection.execute("SELECT row_digest FROM sources ORDER BY name"):
                self._check_time(deadline)
                aggregate.update((digest + "\n").encode("ascii"))
            metadata = {"format": self.FORMAT_VERSION, "revision": revision,
                        "source_root": _hash(str(self.root.resolve())),
                        "count": str(len(fingerprints)), "rows_digest": aggregate.hexdigest()}
            connection.execute("DELETE FROM metadata")
            connection.executemany("INSERT INTO metadata VALUES (?,?)", metadata.items())
            self._rebuild_checkpoint("staged")
            if self._scan(deadline) != fingerprints:
                raise AssetQueryChanged()
            connection.commit()
            self._rebuild_checkpoint("committed")
            connection.close()
            connection = None
            if staging.stat().st_size > self.MAX_INDEX_BYTES:
                raise AssetQueryBudgetExceeded()
            self._directory_usage(deadline)
            # Windows _commit requires a writable descriptor. The database is
            # already closed; reopen without truncation before durable publish.
            with staging.open("r+b") as handle:
                os.fsync(handle.fileno())
            os.replace(staging, self.path)
            self._rebuild_checkpoint("published")
            # A complete new DB is published in one rename. Directory fsync
            # covers crash persistence where supported by the host platform.
            if os.name != "nt":
                fd = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            identity = self._index_identity()
            self._verified_identity, self._verified_revision = identity, revision
            return identity
        except (sqlite3.DatabaseError, OSError, UnicodeError) as error:
            self._check_time(deadline)
            # SQLite uses SQLITE_FULL for both the configured page ceiling and
            # exhausted host storage. Both are a safe capacity-budget failure;
            # the driver does not reliably distinguish the underlying cause.
            if isinstance(error, sqlite3.DatabaseError) and getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
                raise AssetQueryBudgetExceeded() from None
            raise AssetQueryUnavailable() from None
        finally:
            if connection is not None:
                connection.close()
            # Only this invocation's disposable staging files are removed.
            # Previous interrupted files and cursor.key are never overwritten.
            for candidate in (staging, Path(str(staging) + "-journal")):
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass

    def snapshot(self, loader, *, deadline=None):
        deadline = self._deadline() if deadline is None else deadline
        fingerprints = self._scan(deadline)
        revision = _revision(fingerprints)
        self._ensure_directory()
        self._directory_usage(deadline)
        identity = self._index_identity()
        reuse = False
        if identity is not None:
            try:
                saved_revision = self._state(identity, deadline)
                if saved_revision == revision:
                    return AssetQuerySnapshot(revision, fingerprints, identity)
                reuse = True
            except _RebuildRequired:
                self._verified_identity = self._verified_revision = None
        identity = self._build(fingerprints, revision, loader, deadline,
                               reuse=reuse, previous_identity=identity)
        return AssetQuerySnapshot(revision, fingerprints, identity)

    def iter_candidates(self, snapshot, novel_id, binding, *, keyword="", kind=None, deadline=None):
        """Stream candidates, not authorized/public assets; count in the owner."""
        deadline = self._deadline() if deadline is None else deadline
        if self._index_identity() != snapshot.index_identity:
            raise AssetQueryChanged()
        clauses, parameters = ["novel_id=?", "binding=?", "payload IS NOT NULL"], [novel_id, _json(binding)]
        if keyword:
            clauses.append("instr(filename_folded, ?) > 0")
            parameters.append(keyword)
        if kind is not None:
            clauses.append("kind=?")
            parameters.append(kind)
        sql = ("SELECT payload FROM sources WHERE " + " AND ".join(clauses)
               + " ORDER BY created_at, asset_id")
        try:
            with closing(self._connect(self.path, readonly=True)) as connection:
                connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                for (raw,) in connection.execute(sql, parameters):
                    self._check_time(deadline)
                    if not isinstance(raw, str) or len(raw.encode("utf-8")) > self.MAX_METADATA_BYTES:
                        raise AssetQueryUnavailable()
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise AssetQueryUnavailable()
                    yield payload
        except (sqlite3.DatabaseError, OSError, UnicodeError, ValueError):
            self._check_time(deadline)
            raise AssetQueryUnavailable() from None
        if self._index_identity() != snapshot.index_identity:
            raise AssetQueryChanged()

    def verify(self, snapshot, *, deadline=None):
        deadline = self._deadline() if deadline is None else deadline
        self._directory_usage(deadline)
        if (self._index_identity() != snapshot.index_identity
                or self._scan(deadline) != snapshot.fingerprints):
            raise AssetQueryChanged()
