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
from uuid import UUID, uuid4

from ..repositories.file.mutation_coordinator import workspace_mutation
from ..storage import atomic_write


# This is original-owner metadata, not a second task store. Only the File/local
# semantic-import observation contract consumes it; legacy documents are never
# claimed or migrated by a read or by an ordinary business transaction.
LIFECYCLE = "_taskcenter_lifecycle_v1"
OBSERVED_COLLECTION = "semantic_import_jobs"
TEAM_LIFECYCLE = "_taskcenter_team_lifecycle_v1"
TEAM_COLLECTION = "team_runs"
LIFECYCLE_MODES = {LIFECYCLE: ("local", OBSERVED_COLLECTION),
                   TEAM_LIFECYCLE: ("collaboration", TEAM_COLLECTION)}
OBSERVATION_UNSUPPORTED = "EXPERIMENTAL_OBSERVATION_UNSUPPORTED"


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("experimental store contains duplicate JSON keys")
        value[key] = item
    return value


def _nonce(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = UUID(value)
        return parsed.version == 4 and str(parsed) == value
    except ValueError:
        return False


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
        for lifecycle, (mode, collection) in LIFECYCLE_MODES.items():
            if lifecycle not in doc:
                continue
            metadata = doc[lifecycle]
            if (not isinstance(metadata, dict)
                    or set(metadata) != {"schema_version", "project_identity", "document_incarnation", "rows"}
                    or type(metadata.get("schema_version")) is not int or metadata["schema_version"] != 1
                    or not isinstance(metadata.get("project_identity"), str)
                    or not metadata["project_identity"].startswith("file:")
                    or not _nonce(metadata["project_identity"][5:])
                    or not _nonce(metadata.get("document_incarnation"))
                    or not isinstance(metadata.get("rows"), dict)
                    or any(not isinstance(rid, str) or not rid or not _nonce(nonce)
                           for rid, nonce in metadata["rows"].items())
                    or scope.get("mode") != mode
                    or set(doc["collections"].get(collection, {})) != set(metadata["rows"])):
                raise ValueError("experimental lifecycle metadata is invalid")
        canonical(doc)
        return doc

    def _file_bytes(self, nid, scope):
        try:
            return self.path(nid, scope).read_bytes()
        except FileNotFoundError:
            return None

    def _file_snapshot(self, nid, scope):
        raw = self._file_bytes(nid, scope)
        if raw is None:
            return None, self.empty(nid, scope)
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        return raw, self.validate(document, nid, scope)

    def _file_read(self, nid, scope):
        return self._file_snapshot(nid, scope)[1]

    @contextmanager
    def _existing_project_owner(self, nid):
        # Reuse the real marker parser and scope -> project lock order. Creating
        # an identity here would falsely adopt old or unowned source rows.
        from ..creative.project_store import CreativeProjectStore
        owner = CreativeProjectStore(self)
        with owner.existing_owner_only(), owner.owner_lease(nid) as identity:
            yield identity

    def _initial_project_identity(self, nid, scope):
        if scope.get("mode") not in {"local", "collaboration"}:
            return None
        try:
            with self._existing_project_owner(nid) as identity:
                return identity
        except (FileNotFoundError, ValueError):
            # Ordinary unprotected writers keep their existing behavior. They
            # cannot turn missing/invalid ownership into observation support.
            return None

    @staticmethod
    def _advance_lifecycles(document, previous, identity=None):
        lifecycle = LIFECYCLE if document["scope"]["mode"] == "local" else TEAM_LIFECYCLE
        collection = LIFECYCLE_MODES[lifecycle][1]
        if lifecycle in previous:
            metadata = copy.deepcopy(previous[lifecycle])
        elif identity is not None:
            metadata = {"schema_version": 1, "project_identity": identity,
                        "document_incarnation": str(uuid4()), "rows": {}}
        else:
            return
        before = previous["collections"].get(collection, {})
        after = document["collections"].get(collection, {})
        metadata["rows"] = {rid: nonce for rid, nonce in metadata["rows"].items() if rid in after}
        for rid in after:
            if rid not in before or canonical(before[rid]) != canonical(after[rid]):
                # A recreation receives a fresh random identity even when the
                # row ID/content/version repeats. Retaining deleted IDs is not
                # needed for that property and would grow without a bound.
                metadata["rows"][rid] = str(uuid4())
        document[lifecycle] = metadata

    def capture_committed_collection(self, nid, scope, collection=OBSERVED_COLLECTION):
        """Return one committed File/local source with original-owner proofs.

        Rows and proofs come from the same physical snapshot, never ``read``'s
        active transaction buffer. The caller must retain the original source
        authorization/scope checks and bind only its authorized finite window,
        not this whole map or any unrelated collection's state. There is no
        legacy migration and no guarantee against external byte-for-byte backup
        replay, which does not participate in this owner's commit boundary.
        """
        mode = scope.get("mode") if isinstance(scope, dict) else None
        lifecycle = next((key for key, pair in LIFECYCLE_MODES.items()
                          if pair == (mode, collection)), None)
        if self.backend != "file" or lifecycle is None:
            raise ValueError(OBSERVATION_UNSUPPORTED)
        key = self.key(nid, scope)
        with workspace_mutation(self.root, f"experimental:{key}"):
            raw, document = self._file_snapshot(nid, scope)
            if raw is None or lifecycle not in document:
                raise ValueError(OBSERVATION_UNSUPPORTED)
            metadata = document[lifecycle]
            try:
                with self._existing_project_owner(nid) as identity:
                    if identity != metadata["project_identity"]:
                        raise ValueError(OBSERVATION_UNSUPPORTED)
                    rows = document["collections"].get(collection, {})
                    return copy.deepcopy({
                        "rows": list(rows.values()), "project_identity": identity,
                        "document_incarnation": metadata["document_incarnation"],
                        "row_lifecycles": {rid: metadata["rows"][rid] for rid in rows},
                    })
            except (FileNotFoundError, ValueError) as exc:
                raise ValueError(OBSERVATION_UNSUPPORTED) from exc

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
                original_bytes, doc = self._file_snapshot(nid, scope)
                original = copy.deepcopy(doc)
                identity = self._initial_project_identity(nid, scope) if original_bytes is None else None
                self._local.active[key] = doc
                before = canonical(doc)
                try:
                    yield doc
                    # Reserved metadata is owner-maintained. Accept detached
                    # deep copies (CreativeProjectStore.clear/update), not a
                    # caller's removal, injection, rollback or replacement.
                    for lifecycle in LIFECYCLE_MODES:
                        if ((lifecycle in doc) != (lifecycle in original)
                                or (lifecycle in original and canonical(doc[lifecycle]) != canonical(original[lifecycle]))):
                            raise ValueError("experimental lifecycle metadata is owner-managed")
                    business = copy.deepcopy(doc)
                    for lifecycle in LIFECYCLE_MODES:
                        business.pop(lifecycle, None)
                    self.validate(business, nid, scope)
                    # The workspace lock is reentrant across store instances.
                    # Compare existence and exact committed bytes even for an
                    # unchanged callback/source_lease, not read(active).
                    if self._file_bytes(nid, scope) != original_bytes:
                        raise ValueError("EXPERIMENTAL_SCOPE_CONCURRENT_WRITE")
                    if canonical(doc) != before:
                        self._advance_lifecycles(doc, original, identity)
                        self.validate(doc, nid, scope)
                        if identity is not None:
                            with self._existing_project_owner(nid) as current_identity:
                                if current_identity != identity:
                                    raise ValueError("EXPERIMENTAL_PROJECT_OWNER_CHANGED")
                                if self._file_bytes(nid, scope) != original_bytes:
                                    raise ValueError("EXPERIMENTAL_SCOPE_CONCURRENT_WRITE")
                                atomic_write(self.path(nid, scope), canonical(doc))
                        else:
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
