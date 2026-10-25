"""Bounded fingerprints of existing authorization owners; never an authority registry."""
from __future__ import annotations
import hashlib
import json
import os
import stat

MAX_AUTHORITY_BYTES = 8 * 1024 * 1024
MAX_AUTHORITY_ROWS = 10000

def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')

def _file_digest(path):
    try:
        before = path.lstat()
    except FileNotFoundError:
        return 'absent'
    def regular(info):
        return stat.S_ISREG(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    if not regular(before) or before.st_size > MAX_AUTHORITY_BYTES:
        raise ValueError('AUDIO_HISTORY_AUTHORITY_LIMIT')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not regular(opened) or identity(opened) != identity(before):
            raise ValueError('AUDIO_HISTORY_AUTHORITY_CHANGED')
        raw = stream.read(MAX_AUTHORITY_BYTES + 1)
        if len(raw) > MAX_AUTHORITY_BYTES or identity(os.fstat(stream.fileno())) != identity(before) or identity(path.lstat()) != identity(before):
            raise ValueError('AUDIO_HISTORY_AUTHORITY_CHANGED')
    return hashlib.sha256(_canonical([identity(before), hashlib.sha256(raw).hexdigest()])).hexdigest()

def authority_snapshot(workspace, nid, token, actor, scope, *, session_resolver=None, authorization_repository=None):
    from ..experimental.flags import enabled_flags
    binding = [actor, workspace.store.key(nid, scope), workspace.store.incarnation(nid), sorted(enabled_flags())]
    if scope.get('mode') == 'collaboration':
        if session_resolver is None or authorization_repository is None:
            raise ValueError('AUDIO_HISTORY_AUTHORITY_REQUIRED')
        try:
            binding.append(session_resolver.binding_generation(token))
        except (KeyError, ValueError):
            raise ValueError('AUDIO_HISTORY_AUTHORITY_CHANGED') from None
        repository = authorization_repository
        if hasattr(repository, 'path'):
            binding += [_file_digest(repository.path), _file_digest(repository.path.with_name('identity.json'))]
        else:
            values, total = [], 0
            with repository.connection_factory() as connection:
                for table in ('domain_role_assignments', 'permission_assignments', 'authorization_audit_events'):
                    rows = connection.execute(
                        f"SELECT id::text, xmin::text, octet_length(payload::text) FROM {table} ORDER BY id LIMIT %s",
                        (MAX_AUTHORITY_ROWS + 1,)).fetchall()
                    if len(rows) > MAX_AUTHORITY_ROWS:
                        raise ValueError('AUDIO_HISTORY_AUTHORITY_LIMIT')
                    total += sum(row[2] for row in rows)
                    if total > MAX_AUTHORITY_BYTES:
                        raise ValueError('AUDIO_HISTORY_AUTHORITY_LIMIT')
                    values.append([table, rows])
                for table, query, params in (
                    ('users', "SELECT id::text, xmin::text, status, octet_length(COALESCE(metadata::text,'')) FROM users WHERE id=%s LIMIT 2", (actor,)),
                    ('workspace_memberships', "SELECT id::text, xmin::text, status, octet_length(COALESCE(metadata::text,'')) FROM workspace_memberships WHERE user_id=%s AND workspace_id=%s LIMIT 2", (actor, scope.get('workspace_id'))),
                ):
                    rows = connection.execute(query, params).fetchall()
                    if len(rows) != 1:
                        raise ValueError('AUDIO_HISTORY_AUTHORITY_CHANGED')
                    total += rows[0][3]
                    if total > MAX_AUTHORITY_BYTES:
                        raise ValueError('AUDIO_HISTORY_AUTHORITY_LIMIT')
                    values.append([table, rows])
            binding.extend(values)
    return hashlib.sha256(_canonical(binding)).hexdigest()
