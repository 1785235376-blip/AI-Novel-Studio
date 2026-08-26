# Docker Readiness Report

Date: 2026-08-09

## Audit result

`docker-compose.yml` is configured for `postgres:16-alpine` and was not modified.

| Area | Configured | Audit |
|---|---|---|
| Port | `127.0.0.1:${POSTGRES_PORT:-54329}:5432` | Localhost-only exposure is appropriate for development. |
| Environment | DB, user, required password | Password must exist in `.env`; startup intentionally fails when missing. |
| Volume | `novel_postgres_data:/var/lib/postgresql/data` | Data survives container recreation. |
| Migrations | Read-only mount to `/docker-entrypoint-initdb.d` | Runs automatically only when the PostgreSQL data directory is empty. |
| Health check | `pg_isready`, 10-second interval, 5-second timeout, 10 retries | Service waits for PostgreSQL readiness. |
| Dependency | Backend waits for `service_healthy` | Correct startup ordering, not a substitute for migration verification. |

## Required environment

- Docker Desktop with Docker Engine and Compose v2.
- `.env` created from `.env.example` with a non-placeholder password.
- Host-side `DATABASE_URL=postgresql+psycopg://novel_studio:<password>@localhost:54329/ai_novel_studio`.
- Inside the backend container, the hostname must be `postgres` and port `5432`; a localhost URL points back to the backend container itself.

## Startup

Run `docker version`, then `docker compose up -d postgres`, and check `docker compose ps` plus `scripts/check_postgres_ready.ps1`.

## Risks

1. Existing named volumes do not rerun `/docker-entrypoint-initdb.d`; use `scripts/migrate-db.ps1` for an existing database and verify `schema_versions`.
2. `.env.example` contains a placeholder password and must not be used unchanged outside isolated development.
3. Migration scripts are not rollback scripts. Back up a populated database before manual execution.
4. Host and container database URLs require different hostnames/ports.

Current Docker/PostgreSQL runtime status: **REAL VERIFIED** on 2026-08-09. Docker Engine 29.6.2, Compose 5.3.1, and the PostgreSQL 16 container were healthy.
