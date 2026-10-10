"""A V2-only view of scope storage, fenced by the actual project incarnation.

Public slugs and branch scopes are reusable. File keeps an opaque V2 marker
inside the removable owner directory; PostgreSQL already has a UUID owner PK.
Old/unbound rows stay intact in the original scope document, but are never
adopted by another owner. No legacy metadata, schema, or deletion path changes.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager, ExitStack
import json
import os
import stat
from threading import local
from uuid import UUID, uuid4

from ..file_project_lifecycle import project_operation
from ..storage import atomic_write

COLLECTIONS = ("creative_documents_v2", "creative_director_proposals_v2", "creative_project_preferences_v2",
               "creative_graph_definitions_v2", "creative_graph_runs_v2")
BINDING = "project_incarnation"
MAX_MARKER_BYTES = 256


def _read_marker(path):
    """Never follow a marker symlink/reparse point or read unbounded content."""
    info = path.lstat()
    def regular(value):
        return stat.S_ISREG(value.st_mode) and not (
            getattr(value, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    if not regular(info) or info.st_size > MAX_MARKER_BYTES:
        raise ValueError("CREATIVE_PROJECT_IDENTITY_INVALID")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    except OSError as exc:
        raise ValueError("CREATIVE_PROJECT_IDENTITY_INVALID") from exc
    with os.fdopen(descriptor, "rb") as handle:
        opened, current = os.fstat(handle.fileno()), path.lstat()
        if (not regular(opened) or not regular(current) or opened.st_size > MAX_MARKER_BYTES
                or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)):
            raise ValueError("CREATIVE_PROJECT_IDENTITY_INVALID")
        content = handle.read(MAX_MARKER_BYTES + 1)
    if len(content) > MAX_MARKER_BYTES:
        raise ValueError("CREATIVE_PROJECT_IDENTITY_INVALID")
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise ValueError("CREATIVE_PROJECT_IDENTITY_INVALID") from None


class CreativeProjectStore:
    def __init__(self, store):
        self.store = store
        self._local = local()

    def __getattr__(self, name):
        return getattr(self.store, name)

    @contextmanager
    def _owner(self, nid):
        owners = getattr(self._local, "owners", None)
        if owners is None:
            owners = self._local.owners = {}
        if nid in owners:
            yield owners[nid]
            return
        with ExitStack() as locks:
            if self.backend == "file":
                locks.enter_context(project_operation(self.root, nid))
                path = self.root / "novels" / nid / "creative_project_v2.json"
                try:
                    marker = _read_marker(path)
                except FileNotFoundError:
                    marker = {"schema_version": 1, BINDING: str(uuid4())}
                    atomic_write(path, json.dumps(marker, sort_keys=True))
                if (not isinstance(marker, dict) or set(marker) != {"schema_version", BINDING}
                        or type(marker.get("schema_version")) is not int or marker["schema_version"] != 1
                        or not isinstance(marker.get(BINDING), str)):
                    raise ValueError("CREATIVE_PROJECT_IDENTITY_INVALID")
                try:
                    parsed = UUID(marker[BINDING])
                    if parsed.version != 4 or str(parsed) != marker[BINDING]:
                        raise ValueError("invalid identity")
                    identity = "file:" + str(parsed)
                except ValueError:
                    raise ValueError("CREATIVE_PROJECT_IDENTITY_INVALID") from None
            else:
                connection = locks.enter_context(self.store._connect())
                row = connection.execute("SELECT id FROM novels WHERE slug = %s FOR KEY SHARE", (nid,)).fetchone()
                if row is None:
                    raise FileNotFoundError(nid)
                identity = "postgres:" + str(row[0])
            owners[nid] = identity
            try:
                yield identity
            finally:
                owners.pop(nid, None)

    def incarnation(self, nid):
        with self._owner(nid) as identity:
            return identity

    def owner_lease(self, nid):
        """Hold the existing owner through an asset operation, without a new registry."""
        return self._owner(nid)

    @staticmethod
    def _view(document, identity):
        view = copy.deepcopy(document)
        for name in COLLECTIONS:
            if name in view["collections"]:
                view["collections"][name] = {
                    rid: row for rid, row in view["collections"][name].items()
                    if isinstance(row, dict) and row.get(BINDING) == identity
                }
        return view

    def read(self, nid, scope):
        key = self.store.key(nid, scope)
        active = getattr(self._local, "active", {})
        if key in active:
            return copy.deepcopy(active[key])
        # Scope first, then owner, as in the existing experimental services.
        # Re-resolving the owner after the snapshot also fences a racing delete.
        document = self.store.read(nid, scope)
        with self._owner(nid) as identity:
            return self._view(document, identity)

    @contextmanager
    def source_lease(self, nid, scope):
        """Lease an unchanged source before acquiring asset -> project locks.

        This deliberately enters the raw scope owner, not ``transaction``:
        holding a creative transaction's project lease while acquiring assets
        would reverse the established asset -> project ordering. Reads by the
        same raw store instance see its active snapshot without another lock.
        The caller must recheck incarnation under its later asset/project lease.
        No scope writes, including changes to the detached view, are admitted.
        """
        from ..experimental.store import canonical
        key = self.store.key(nid, scope)
        if (key in getattr(self._local, "active", {})
                or key in getattr(self.store._local, "active", {})
                or nid in getattr(self._local, "owners", {})):
            raise ValueError("CREATIVE_SOURCE_LEASE_NESTED_OR_ORDER_INVALID")
        with self.store.transaction(nid, scope) as document:
            before = canonical(document)
            # Resolve only briefly here; no project lock is held at yield.
            view = self._view(document, self.incarnation(nid))
            snapshot = canonical(view)
            try:
                yield view
            finally:
                if canonical(document) != before or canonical(view) != snapshot:
                    raise ValueError("CREATIVE_SOURCE_LEASE_MUTATION_DENIED")

    @contextmanager
    def transaction(self, nid, scope):
        key = self.store.key(nid, scope)
        if not hasattr(self._local, "active"):
            self._local.active = {}
        # Acquire in the existing scope -> project order, but keep the owner
        # lock until the underlying atomic commit finishes. The owner delete
        # therefore cannot finish midway through a creative mutation.
        with ExitStack() as lifecycle:
            with self.store.transaction(nid, scope) as document:
                identity = lifecycle.enter_context(self._owner(nid))
                view = self._view(document, identity)
                self._local.active[key] = view
                try:
                    yield view
                    for name in COLLECTIONS:
                        current = view["collections"].get(name, {})
                        if any(not isinstance(row, dict) or row.get(BINDING) != identity for row in current.values()):
                            raise ValueError("CREATIVE_PROJECT_BINDING_INVALID")
                        # Retain other incarnations byte-for-byte as JSON values.
                        # They do not consume the current owner's document quota.
                        retained = {rid: row for rid, row in document["collections"].get(name, {}).items()
                                    if not isinstance(row, dict) or row.get(BINDING) != identity}
                        if retained:
                            view["collections"][name] = {**retained, **current}
                    document.clear()
                    document.update(view)
                finally:
                    self._local.active.pop(key, None)
