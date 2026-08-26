# PostgreSQL Setup Guide for Windows

This guide contains no automatic installation steps.

1. Install Docker Desktop manually from the official Docker distribution, then start Docker Desktop and wait for its engine to report ready.
2. In PowerShell, verify `docker version` and `docker compose version`.
3. Copy `.env.example` to `.env`, replace `POSTGRES_PASSWORD`, and keep `POSTGRES_PORT=54329` unless that port is occupied.
4. Start PostgreSQL with `docker compose up -d postgres` and inspect `docker compose ps`.
5. For host-side commands set `DATABASE_URL=postgresql+psycopg://novel_studio:<password>@localhost:54329/ai_novel_studio`. For the compose backend service use `postgres:5432` instead of localhost.
6. On a new empty volume, 001/002/003 execute through `/docker-entrypoint-initdb.d`. On an existing volume run `./scripts/migrate-db.ps1` and verify the `schema_versions` rows `0.1.0`, `0.2.0`, and `0.4.0`.
7. Run `./scripts/check_postgres_ready.ps1`.
8. Run `./scripts/validate_postgres_backend.ps1` and inspect `postgres_runtime_validation_report.json`.
9. Run the File-to-PostgreSQL migration twice only after backing up data, then inspect both reports for idempotent skips.

Do not claim REAL VERIFIED until the database contracts, Context Pack comparison, and complete author flow have all run against the real server.
