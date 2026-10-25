"""Bind keyed text-generation receipts to the existing project owner.

No registry or replacement identity is introduced. File uses the original
CreativeProjectStore marker/lifecycle; PostgreSQL uses its original UUID SQL
through the actual repository Database. Never infer an owner from settings.
"""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.engine import make_url

from ..creative.project_store import CreativeProjectStore
from ..repository import FileRepository


class GenerationOwnerUnverified(ValueError):
    pass


class _DatabaseOwnerAdapter:
    backend = "postgres"

    def __init__(self, database):
        self.database = database

    @contextmanager
    def _connect(self):
        # Preserve CreativeProjectStore's SELECT ... FOR KEY SHARE protocol,
        # but use the exact repository engine rather than constructing a pool
        # or selecting a possibly different settings/environment database.
        with self.database.engine.connect() as connection:
            with connection.begin():
                yield SimpleNamespace(execute=connection.exec_driver_sql)


def _database_url(url):
    # Driver spelling is transport-specific, not a different database owner.
    # Keep credentials and query configuration in comparison, never in errors.
    return make_url(url).set(drivername="postgresql")


class GenerationIdempotencyAuthority:
    def __init__(self, novels, chapters):
        novel_repository = getattr(novels, "novels", None)
        chapter_repository = getattr(chapters, "repository", None)
        novel_backend = getattr(novel_repository, "backend", None)
        chapter_backend = getattr(chapter_repository, "backend", None)
        if isinstance(novel_backend, FileRepository):
            if (not isinstance(chapter_backend, FileRepository)
                    or Path(novel_backend.data).resolve() != Path(chapter_backend.data).resolve()):
                raise GenerationOwnerUnverified("generation repository owners differ")
            self.backend = "file"
            self.root = Path(novel_backend.data).resolve()
            self.database = None
            transport = SimpleNamespace(backend="file", root=self.root)
        else:
            from ..repositories.postgres.session import Database

            database = getattr(novel_repository, "database", None)
            if not isinstance(database, Database) or getattr(chapter_repository, "database", None) is not database:
                raise GenerationOwnerUnverified("generation repository owner is unavailable")
            self.backend, self.database = "postgres", database
            self.root = None
            transport = _DatabaseOwnerAdapter(database)

        resolver = getattr(chapters, "branch_authority", None)
        if callable(resolver):
            owner = getattr(resolver, "__self__", None)
            store = getattr(owner, "store", None)
            if store is None or store.backend != self.backend:
                raise GenerationOwnerUnverified("generation branch owner differs")
            if self.backend == "file":
                if Path(store.root).resolve() != self.root:
                    raise GenerationOwnerUnverified("generation branch root differs")
            else:
                try:
                    same_database = _database_url(store.database_url) == _database_url(self.database.engine.url)
                except (TypeError, ValueError):
                    same_database = False
                if not same_database:
                    raise GenerationOwnerUnverified("generation branch database differs")
            # The branch service must also validate projects against this same
            # repository, not a second service that happens to reuse a slug.
            branch_novels = getattr(getattr(owner, "novels", None), "novels", None)
            branch_mainline = getattr(getattr(owner, "mainline", None), "repository", None)
            if self.backend == "file":
                for repository in (branch_novels, branch_mainline):
                    backend = getattr(repository, "backend", None)
                    if not isinstance(backend, FileRepository) or Path(backend.data).resolve() != self.root:
                        raise GenerationOwnerUnverified("generation branch repositories differ")
            elif any(getattr(repository, "database", None) is not self.database
                     for repository in (branch_novels, branch_mainline)):
                raise GenerationOwnerUnverified("generation branch repositories differ")
        self.owner = CreativeProjectStore(transport)

    def capture_new(self, novel_id):
        """Only a new explicit request key may provision a missing marker."""
        return self.owner.incarnation(novel_id)

    @contextmanager
    def verify_existing(self, novel_id, expected):
        # Keep this short: callers must not acquire auth/source/jobs locks here.
        with self.owner.existing_owner_only(), self.owner.owner_lease(novel_id) as current:
            if current != expected:
                raise GenerationOwnerUnverified("generation project incarnation changed")
            yield
