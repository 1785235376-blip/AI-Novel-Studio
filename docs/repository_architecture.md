# Repository Architecture

## Persistence boundary

API routes call Services. Services depend on Repository Protocols. `create_repository_bundle()` selects one concrete backend.

```text
API -> Services -> RepositoryBundle -> File or PostgreSQL adapters
```

The bundle contains `novels`, `chapters`, `canon`, and `generations`.

## File mode

`STORAGE_BACKEND=file` preserves all existing Markdown, JSON, document, history, summary, pending Canon, and Job formats. Legacy `FileRepository` imports and `build_context(Path, ...)` remain compatible.

## PostgreSQL mode

`STORAGE_BACKEND=postgres` uses SQLAlchemy 2.x repositories over migrations 001/002/003. `DATABASE_URL` is mandatory and startup runs a connection health check. Failure is explicit; there is no File fallback. See `docs/postgres_backend_architecture.md`.

## Contracts

- `NovelRepositoryProtocol`: CRUD, datasets, public Secrets, Context sources.
- `ChapterRepositoryProtocol`: CRUD, duplicate/rename/move, optimistic save, history/restore, summaries.
- `CanonRepositoryProtocol`: Canon and Pending Canon lifecycle.
- `GenerationRepositoryProtocol`: save/get/load_all.

Contracts and Service calls contain no backend-specific methods.

## Failure behavior

- `file`: creates a File bundle using one shared data root.
- `postgres`: requires a healthy configured database.
- unknown backend: raises `ValueError`.
