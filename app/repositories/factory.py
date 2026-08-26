from __future__ import annotations
from pathlib import Path
from ..config import Settings,settings
from ..repository import FileRepository
from .bundle import RepositoryBundle
from .file import FileNovelRepository,FileChapterRepository,FileCanonRepository,FileGenerationRepository,FileLoreRepository
from .file.continuity import FileContinuityRepository
from .file.narrative import FileNarrativeRepository

def create_repository_bundle(config:Settings=settings,data_root:Path|None=None)->RepositoryBundle:
    backend=config.storage_backend
    if backend=="postgres":
        from .postgres import Database,PostgresNovelRepository,PostgresChapterRepository,PostgresCanonRepository,PostgresGenerationRepository,PostgresLoreRepository
        database=Database(config.database_url);database.require_healthy()
        import psycopg
        from .postgres.continuity import PostgresContinuityRepository
        url=config.database_url.replace("postgresql+psycopg://","postgresql://")
        from .postgres.narrative import PostgresNarrativeRepository
        connection=lambda:psycopg.connect(url, options="-c timezone=UTC")
        from .postgres.scope import PostgresScopeRepository
        from .postgres.scope import PostgresAuthorizationRepository
        from .postgres.identity import PostgresIdentityRepository
        return RepositoryBundle(PostgresNovelRepository(database),PostgresChapterRepository(database),PostgresCanonRepository(database),PostgresGenerationRepository(database),PostgresLoreRepository(database),PostgresContinuityRepository(connection),PostgresNarrativeRepository(connection),PostgresScopeRepository(connection),PostgresAuthorizationRepository(connection),PostgresIdentityRepository(connection))
    if backend!="file":raise ValueError(f"Unsupported STORAGE_BACKEND: {backend!r}")
    root=data_root or config.data_path();shared=FileRepository(root)
    from .file.scope import FileScopeRepository
    from .file.scope import FileAuthorizationRepository
    from .file.identity import FileIdentityRepository
    return RepositoryBundle(FileNovelRepository(shared),FileChapterRepository(shared),FileCanonRepository(shared),FileGenerationRepository(root),FileLoreRepository(shared),FileContinuityRepository(root/"continuity"),FileNarrativeRepository(root/"narrative"),FileScopeRepository(root),FileAuthorizationRepository(root),FileIdentityRepository(root))
