"""Retire project authority through the existing scope and authorization owners.

File uses the existing project lock and compensating multi-file transaction;
PostgreSQL callers supply the transaction that deletes the original novel.
Audit history and workspace authority deliberately survive retirement.
"""
from __future__ import annotations

import shutil
import logging
import os
import stat
from uuid import uuid4

from .file_project_lifecycle import project_operation
from .storage import atomic_write


def quarantine_failed_file_creation(root):
    """Remove a failed create from the public namespace before reclamation."""
    if not root.exists():
        return None
    backup = root.with_name(f".{root.name}.delete-backup-{uuid4()}")
    root.rename(backup)
    return backup


def _tree_signature(root):
    """Inventory deletion effects without reading potentially large media bytes."""
    entries=[]
    pending=[root]
    try:
        while pending:
            path=pending.pop()
            info=path.lstat()
            entries.append((str(path.relative_to(root)),stat.S_IFMT(info.st_mode),info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns))
            reparse=getattr(info,"st_file_attributes",0)&getattr(stat,"FILE_ATTRIBUTE_REPARSE_POINT",0x400)
            if stat.S_ISDIR(info.st_mode) and not reparse:
                with os.scandir(path) as children:
                    pending.extend(path / child.name for child in children)
        return sorted(entries)
    except OSError:
        return None


def reclaim_retired_file_project(backup, *, restore_unchanged=None):
    if backup is None:
        return
    original=_tree_signature(backup) if restore_unchanged is not None else None
    try:
        shutil.rmtree(backup)
    except OSError:
        # Preserve the existing failure contract when reclamation changed
        # absolutely nothing. Once any entry was removed, restoration would
        # expose a damaged project and is forbidden.
        if restore_unchanged is not None and original is not None and _tree_signature(backup)==original:
            restore_unchanged()
            raise
        logging.getLogger(__name__).warning("Retired project reclaim pending: %s", backup, exc_info=True)


def retire_file_project(backend, nid, *, scopes=None, authorization=None, audit_event=None, audit_append=None, reauthorize=lambda: None):
    from .repositories.file.scope import FileScopeRepository, FileAuthorizationRepository
    from .repositories.file.mutation_coordinator import workspace_mutation
    scopes = scopes or FileScopeRepository(backend.data)
    authorization = authorization or FileAuthorizationRepository(backend.data)
    # Lock order matches the audited mutation port: authorization -> project.
    with authorization.mutation(), project_operation(backend.data, nid), workspace_mutation(backend.data, "collaboration-scope"):
        reauthorize()
        workspace = scopes.project_workspace(nid)
        paths = (scopes.path, authorization.path)
        before = {path: path.read_bytes() if path.exists() else None for path in paths}
        root = backend.novels / nid
        backup = root.with_name(f".{root.name}.delete-backup-{uuid4()}")
        def restore():
            if backup.exists() and not root.exists():
                backup.rename(root)
            for path,value in before.items():
                if value is None:path.unlink(missing_ok=True)
                else:atomic_write(path,value.decode("utf-8"))
        try:
            root.rename(backup)
            authorization.retire_project(nid, workspace)
            scopes.retire_project(nid, workspace)
            if audit_event is not None:
                (audit_append or authorization.append_audit_event)(audit_event)
        except Exception:
            restore()
            raise
        # The public owner is retired now. Physical reclamation is a separate
        # step: rmtree can fail after unlinking some files, so it must never
        # restore that partial directory together with the old authority.
        reclaim_retired_file_project(backup,restore_unchanged=restore)


def retire_postgres_project(repository, session, model, *, scopes=None, authorization=None, audit_event=None, reauthorize=lambda: None):
    from sqlalchemy import text
    from .repositories.postgres.scope import PostgresScopeRepository, PostgresAuthorizationRepository
    # These owners use the supplied SQLAlchemy transaction; they never open or
    # commit an independent connection during retirement.
    scopes = scopes or PostgresScopeRepository(None)
    authorization = authorization or PostgresAuthorizationRepository(None)
    workspace = session.execute(text("SELECT workspace_id FROM project_workspaces WHERE project_id=:p"), {"p": model.slug}).scalar()
    reauthorize()
    authorization.retire_project(model.slug, workspace, session=session)
    scopes.retire_project(model.slug, workspace, session=session)
    session.delete(model)
    if audit_event is not None:
        import json
        session.execute(text("INSERT INTO authorization_audit_events(id,payload) VALUES (:id,CAST(:payload AS jsonb))"),
                        {"id": audit_event["id"], "payload": json.dumps(audit_event)})
