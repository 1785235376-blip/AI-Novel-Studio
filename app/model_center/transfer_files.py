"""POSIX descriptor-confined storage for Model Center's own transfer artifacts.

No Windows pathname fallback: native handle/reparse acceptance is still pending.
The selected directory is never scanned or cleaned; only our closed child layout
is touched. This is not an asset store or a general filesystem cleanup service.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from ..repositories.file.mutation_coordinator import workspace_mutation_lock
from .transfer_types import TransferError

CONTAINER = '.studio-model-transfers'
MAX_TASKS = 16
MAX_JOURNAL = 32 * 1024


def supported():
    return (os.name == 'posix' and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY')
            and all(fn in os.supports_dir_fd for fn in (os.open, os.stat, os.mkdir, os.unlink, os.rename, os.link)))


def identity(info):
    return [info.st_dev, info.st_ino]


def signature(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def unlink_owned(parent, name, expected, *, links=1, expected_signature=None):
    """Revalidate the leaf immediately before removal, after caller callbacks.

    POSIX cannot atomically compare an inode and unlink a name. This private
    directory excludes other OS users; hostile concurrent same-UID mutation is
    outside the supported boundary. Descriptor confinement still prevents any
    symlink/ancestor redirection from deleting a target outside this directory.
    """
    fd = open_file(parent, name, expected=expected, links=links)
    try:
        if expected_signature is not None and signature(os.fstat(fd)) != expected_signature:
            raise TransferError('MODEL_TRANSFER_PATH_IDENTITY_CHANGED')
        os.unlink(name, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(fd)


def ordinary(info, *, directory=False, links=1):
    if ((not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode))
            or not info.st_ino or info.st_uid != os.geteuid()
            or info.st_mode & 0o022 or (not directory and info.st_nlink != links)):
        raise TransferError('MODEL_TRANSFER_PATH_IDENTITY_CHANGED')


def open_root(path):
    if not supported():
        raise TransferError('MODEL_TRANSFER_PLATFORM_UNSUPPORTED')
    raw = str(path)
    p = Path(raw)
    if (not p.is_absolute() or p == Path(p.anchor) or raw.startswith('//')
            or any(part in {'.', '..'} for part in raw.split('/')[1:])
            or any(ord(c) < 32 for c in raw)):
        raise TransferError('MODEL_TRANSFER_DESTINATION_INVALID')
    descriptor = os.open(p.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in p.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        ordinary(os.fstat(descriptor), directory=True)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def open_directory(parent, name, expected=None):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        info = os.fstat(fd)
        ordinary(info, directory=True)
        if expected is not None and identity(info) != expected:
            raise TransferError('MODEL_TRANSFER_PATH_IDENTITY_CHANGED')
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_file(parent, name, *, writable=False, create=False, expected=None, links=1):
    flags = (os.O_RDWR if writable else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(name, flags, 0o600, dir_fd=parent)
    try:
        info = os.fstat(fd)
        ordinary(info, links=links)
        if expected is not None and identity(info) != expected:
            raise TransferError('MODEL_TRANSFER_PATH_IDENTITY_CHANGED')
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_json(parent, name):
    fd = open_file(parent, name)
    try:
        if os.fstat(fd).st_size > MAX_JOURNAL:
            raise TransferError('MODEL_TRANSFER_JOURNAL_INVALID')
        raw = os.read(fd, MAX_JOURNAL + 1)
        if len(raw) > MAX_JOURNAL:
            raise TransferError('MODEL_TRANSFER_JOURNAL_INVALID')
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError('duplicate')
                result[key] = value
            return result
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('constant'))), identity(os.fstat(fd))
    except (ValueError, TypeError, UnicodeError):
        raise TransferError('MODEL_TRANSFER_JOURNAL_INVALID') from None
    finally:
        os.close(fd)


def write_json(parent, name, value, *, expected=None):
    """Atomic metadata replacement, confined to already-held directory handles."""
    if expected is not None:
        fd = open_file(parent, name, expected=expected)
        os.close(fd)
    elif name in os.listdir(parent):
        raise TransferError('MODEL_TRANSFER_PATH_COLLISION')
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    if len(data) > MAX_JOURNAL:
        raise TransferError('MODEL_TRANSFER_JOURNAL_INVALID')
    temporary = '.journal-' + uuid4().hex
    fd = open_file(parent, temporary, writable=True, create=True)
    try:
        view = memoryview(data)
        while view:
            wrote = os.write(fd, view)
            if wrote < 1:
                raise OSError('short write')
            view = view[wrote:]
        os.fsync(fd)
        if expected is not None:
            current = open_file(parent, name, expected=expected)
            os.close(current)
        # Directory is private and retained. Replacement targets only the
        # operation's fixed journal, never a model artifact or supplied path.
        os.rename(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
        return identity(os.fstat(fd))
    finally:
        os.close(fd)
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass


class TransferFiles:
    def __init__(self, root):
        self.root = Path(root) if root is not None else None
        self.root_identity = None
        if self.root is not None and supported():
            fd = open_root(self.root)
            try:
                self.root_identity = identity(os.fstat(fd))
            finally:
                os.close(fd)

    def check_root(self):
        if not supported():
            raise TransferError('MODEL_TRANSFER_PLATFORM_UNSUPPORTED')
        if self.root is None:
            raise TransferError('MODEL_TRANSFER_DESTINATION_NOT_CONFIGURED')
        fd = open_root(self.root)
        if identity(os.fstat(fd)) != self.root_identity:
            os.close(fd)
            raise TransferError('MODEL_TRANSFER_PATH_IDENTITY_CHANGED')
        return fd

    @contextmanager
    def access(self, *, create=False):
        root = self.check_root()
        import fcntl
        directory = None
        try:
            # Reuse the original owner coordination's in-process RLock. Its
            # pathname lock-file helper is deliberately not used for binaries:
            # the cross-process lock here is the verified root descriptor.
            with workspace_mutation_lock(self.root, 'model-center-transfers'):
                fcntl.flock(root, fcntl.LOCK_EX)
                current = self.check_root()
                os.close(current)
                try:
                    directory = open_directory(root, CONTAINER)
                except FileNotFoundError:
                    if not create:
                        yield root, None
                        return
                    os.mkdir(CONTAINER, 0o700, dir_fd=root)
                    directory = open_directory(root, CONTAINER)
                    write_json(directory, 'owner.json', {'contract': 'studio-model-transfer-files/1',
                        'root_identity': self.root_identity})
                    os.fsync(root)
                try:
                    marker, _ = read_json(directory, 'owner.json')
                except FileNotFoundError:
                    raise TransferError('MODEL_TRANSFER_INITIALIZATION_INCOMPLETE') from None
                if marker != {'contract': 'studio-model-transfer-files/1', 'root_identity': self.root_identity}:
                    raise TransferError('MODEL_TRANSFER_PATH_IDENTITY_CHANGED')
                yield root, directory
        finally:
            if directory is not None:
                os.close(directory)
            os.close(root)

    @staticmethod
    def task_names(directory):
        names = []
        with os.scandir(directory) as entries:
            for entry in entries:
                names.append(entry.name)
                if len(names) > MAX_TASKS + 1:
                    raise TransferError('MODEL_TRANSFER_RECORD_LIMIT')
        tasks = [name for name in names if re.fullmatch(r'[a-f0-9]{32}', name)]
        if len(tasks) > MAX_TASKS or any(name != 'owner.json' and name not in tasks for name in names):
            raise TransferError('MODEL_TRANSFER_OWNED_LAYOUT_INVALID')
        return sorted(tasks)

    @staticmethod
    def lease(directory):
        import fcntl
        # Separate open description from access() so a long transfer lease does
        # not hold the short metadata/root mutation lock.
        fd = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise TransferError('MODEL_TRANSFER_BUSY') from None
        except BaseException:
            os.close(fd)
            raise
        return fd
