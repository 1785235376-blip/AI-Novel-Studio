"""Scope-atomic experimental metadata with real File/PostgreSQL parity.

The File profile atomically replaces a single scope document under the existing
cross-process workspace lock. PostgreSQL uses a transaction and row lock; all
collections in a scope commit together. Old schemas and legacy records are not
changed. A missing new migration fails closed only on experimental access.
"""
from __future__ import annotations
import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from threading import local

from ..repositories.file.mutation_coordinator import workspace_mutation
from ..storage import atomic_write


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ExperimentalStore:
    schema_version = 1

    def __init__(self, root, backend="file", database_url=""):
        if backend not in {"file", "postgres"}:
            raise ValueError("unsupported experimental storage backend")
        self.root = Path(root)
        self.backend = backend
        self.database_url = database_url.replace("postgresql+psycopg://", "postgresql://")
        self._local = local()

    @property
    def storage_mode(self):
        return self.backend

    @staticmethod
    def key(nid, scope):
        if not isinstance(nid, str) or not nid or not isinstance(scope, dict) or scope.get("novel_id") != nid:
            raise ValueError("experimental scope must identify its project")
        if scope.get("mode") not in {"local", "collaboration"}:
            raise ValueError("unsupported experimental scope")
        if scope["mode"] == "collaboration" and any(not scope.get(k) for k in ("workspace_id", "storyline_id", "branch_id")):
            raise ValueError("complete collaboration scope required")
        return hashlib.sha256(canonical([nid, scope]).encode()).hexdigest()

    def path(self, nid, scope):
        return self.root / "experimental_v1" / f"{self.key(nid, scope)}.json"

    @staticmethod
    def empty(nid, scope):
        return {"schema_version": 1, "novel_id": nid, "scope": copy.deepcopy(scope), "collections": {}}

    @staticmethod
    def validate(doc, nid, scope):
        if (not isinstance(doc, dict) or doc.get("schema_version") != 1
            or doc.get("novel_id") != nid or doc.get("scope") != scope
            or not isinstance(doc.get("collections"), dict)
            or any(not isinstance(rows, dict) for rows in doc["collections"].values())):
            raise ValueError("experimental store corrupt or scope mismatch; restore a verified backup")
        canonical(doc)
        return doc

    def _file_read(self, nid, scope):
        try:
            raw = json.loads(self.path(nid, scope).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return self.empty(nid, scope)
        return self.validate(raw, nid, scope)

    def _connect(self):
        if not self.database_url:
            raise ValueError("PostgreSQL experimental store requires DATABASE_URL")
        import psycopg
        return psycopg.connect(self.database_url, options="-c timezone=UTC")

    def read(self, nid, scope):
        key = self.key(nid, scope)
        active = getattr(self._local, "active", {})
        if key in active:
            return copy.deepcopy(active[key])
        if self.backend == "file":
            with workspace_mutation(self.root, f"experimental:{key}"):
                return copy.deepcopy(self._file_read(nid, scope))
        with self._connect() as connection:
            result = connection.execute("SELECT document FROM experimental_scope_documents WHERE scope_key = %s", (key,)).fetchone()
            return copy.deepcopy(self.validate(result[0], nid, scope) if result else self.empty(nid, scope))

    @contextmanager
    def transaction(self, nid, scope):
        key = self.key(nid, scope)
        if not hasattr(self._local, "active"):
            self._local.active = {}
        if key in self._local.active:
            # Nested writes need an explicit shared transaction, never a hidden
            # independent commit that could survive an outer rollback.
            raise ValueError("nested experimental transaction is not supported")
        if self.backend == "file":
            with workspace_mutation(self.root, f"experimental:{key}"):
                doc = self._file_read(nid, scope)
                self._local.active[key] = doc
                before = canonical(doc)
                try:
                    yield doc
                    self.validate(doc, nid, scope)
                    if canonical(doc) != before:
                        atomic_write(self.path(nid, scope), canonical(doc))
                finally:
                    self._local.active.pop(key, None)
        else:
            from psycopg.types.json import Jsonb
            with self._connect() as connection:
                connection.execute("INSERT INTO experimental_scope_documents (scope_key, novel_id, scope, document) VALUES (%s, %s, %s, %s) ON CONFLICT (scope_key) DO NOTHING", (key, nid, Jsonb(scope), Jsonb(self.empty(nid, scope))))
                result = connection.execute("SELECT document FROM experimental_scope_documents WHERE scope_key = %s FOR UPDATE", (key,)).fetchone()
                doc = self.validate(result[0], nid, scope)
                self._local.active[key] = doc
                before = canonical(doc)
                try:
                    yield doc
                    self.validate(doc, nid, scope)
                    if canonical(doc) != before:
                        connection.execute("UPDATE experimental_scope_documents SET document = %s, revision = revision + 1, updated_at = now() WHERE scope_key = %s", (Jsonb(doc), key))
                finally:
                    self._local.active.pop(key, None)
