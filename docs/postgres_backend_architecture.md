# PostgreSQL Backend Architecture

## Runtime selection

`STORAGE_BACKEND=file` preserves the existing file layout. `STORAGE_BACKEND=postgres` requires `DATABASE_URL`, creates a SQLAlchemy 2.x engine, performs `SELECT 1`, and fails startup when unavailable. It never falls back to files.

The database must already have migrations `001`, `002`, and `003` applied. Runtime code never calls `Base.metadata.create_all()` and does not alter the schema.

## Persistence and IDs

API → Service → Repository is unchanged. The PostgreSQL boundary maps novel slug and external `slug:number` chapter IDs to UUID rows. Pending Canon and Generation legacy IDs use stable UUIDv5 values while their original IDs remain in JSONB and in API responses.

The four implementations are `PostgresNovelRepository`, `PostgresChapterRepository`, `PostgresCanonRepository`, and `PostgresGenerationRepository`. Transactions are session-scoped and roll back on failure. Chapter moves swap adjacent `chapter_number` values because migrations 001–003 contain no separate ordering column.

## File migration

```powershell
./scripts/migrate_file_to_postgres.ps1 -Source novel_data -DatabaseUrl $env:DATABASE_URL -Report migration_report.json
```

The idempotent tool imports Novel, Chapter, current Document, Version, Summary, Canon, Pending Canon, Story State, and Generation Job data. The report contains `imported`, `skipped`, `failed`, `conflicts`, `source_id`, `target_uuid`, and `timestamp`.

Characters, locations, timeline, foreshadowing, and secrets have ORM/read support. Bulk import is deferred because current Repository contracts provide no write operations for these datasets; ambiguous file shapes are not silently transformed.

## Verification

Set `TEST_POSTGRES_DATABASE_URL` to an isolated, migrated database and run `python -m pytest tests/test_postgres_repository_contracts.py -q`. Without a reachable URL the tests explicitly skip as `NOT VERIFIED`.
