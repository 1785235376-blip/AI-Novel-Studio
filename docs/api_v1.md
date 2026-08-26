# AI Novel Studio V1.0 API

Canonical API prefix: `/api/v1`  
Legacy compatibility prefix: `/api` (kept for the current desktop frontend during migration)

Base URL: `http://127.0.0.1:8000`

Interactive OpenAPI documentation is available at `/docs`; the machine-readable schema is `/openapi.json`.

## Runtime

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service health and version |
| GET | `/api/v1/providers` | Text provider status |
| GET | `/api/v1/models` | Available text models |
| GET | `/api/v1/asset-providers` | Image provider catalog; never returns secrets |
| PUT/DELETE/GET | `/api/v1/credentials/{provider}` | Credential Manager-backed credential lifecycle |

## Novel and writing

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/v1/novels` | List/create novels |
| GET/POST | `/api/v1/novels/{novel_id}/chapters` | List/create chapters |
| POST | `/api/v1/generate/{job_id}` | Generate a draft |
| GET | `/api/v1/generation/{job_id}/events` | Stream generation events |
| POST | `/api/v1/generation/{job_id}/accept` | Accept a reviewed draft |

## Import and export

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/novels/import` | Preview or confirm TXT/Markdown/JSON/DOCX/PDF import; binary files are sent as an in-memory base64 payload |
| POST | `/api/v1/novels/{novel_id}/import/knowledge-base/review` | Accept, reject, or skip the import's knowledge-base candidates; accepts optional `review_id` and note |
| GET | `/api/v1/novels/{novel_id}/import/knowledge-base/review` | List durable pending/completed review records (`items`, `pending`) for reopen after restart |
| GET/PUT | `/api/v1/novels/{novel_id}/import/knowledge-base/review/{review_id}` | Read or edit a pending candidate set before deciding |
| POST | `/api/v1/exports?novel_id={novel_id}` | Create a durable asynchronous export task; send `Idempotency-Key` for a 24-hour retry window |
| GET | `/api/v1/exports/{job_id}` | Read export task status and result metadata |
| POST | `/api/v1/exports/{job_id}/cancel` | Cancel a queued/running task; cancellation is cooperative for an exporter already running |
| POST | `/api/v1/exports/{job_id}/retry` | Create a new attempt for a failed/cancelled task; response includes `retry_of` and `attempt` |
| GET | `/api/v1/exports/{job_id}/download` | Download a succeeded text/CSV/DOCX/EPUB export with a safe attachment filename |

The current export queue supports JSON, TXT, Markdown, minimal standards-compliant DOCX and EPUB packages, deterministic screenplay preview, shot-list CSV, and storyboard preview. Queue creation captures an immutable project snapshot with source versions, a resource manifest (`available`/`missing`) and permission context. Completed payloads are additionally written to a service-owned artifact file with SHA-256 metadata; the bounded inline payload remains as a compatibility fallback. Job records include a durable `progress` (0-100), `progress_message`, `retry_of`, `attempt`, recovery metadata, `snapshot_id`, `missing_resources`, and artifact metadata. On desktop process startup, queued/running records from an interrupted process are requeued; a cancellation request wins a race with exporter completion. PDF binary export and standard screenplay layout remain planned V1.0 work; those formats are intentionally rejected instead of returning a fake file.

Asset uploads are limited to 25 MiB per file. Filenames and MIME types are normalized before persistence and downloads use a safe attachment header.

## Screenplay pipeline

The pipeline is ordered: screenplay -> shots -> storyboard -> transitions/assets -> approval. Approved stages are frozen.

| Method | Path suffix | Purpose |
|---|---|---|
| POST | `/screenplays` | Create screenplay |
| POST | `/screenplays/{id}/approve` | Freeze screenplay |
| POST | `/screenplays/{id}/shots` | Plan shots |
| POST | `/screenplays/{id}/shots/approve` | Freeze shot plan |
| POST | `/screenplays/{id}/storyboard` | Plan storyboard |
| POST | `/screenplays/{id}/storyboard/approve` | Freeze storyboard |
| POST | `/screenplays/{id}/assets` | Plan asset requirements |
| POST | `/screenplays/{id}/assets/approve` | Freeze asset requirements |

All screenplay routes are under `/api/v1/novels/{novel_id}`. PUT routes edit an individual scene, shot, card, transition, or asset.

## Asset tasks and Worker

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/novels/{id}/screenplays/{sid}/asset-tasks` | Create idempotent task queue |
| POST | `/api/v1/novels/{id}/asset-tasks/claim` | Claim bounded `PENDING` tasks |
| POST | `/api/v1/novels/{id}/asset-tasks/dispatch` | Claim; execute only with `execute=true` |
| POST | `/api/v1/novels/{id}/asset-tasks/worker/run-once` | One worker poll |
| POST/STOP/GET | `/api/v1/novels/{id}/asset-tasks/worker/{start,stop,status}` | Worker lifecycle |
| GET | `/api/v1/novels/{id}/asset-tasks/stats` | Queue counts |
| POST | `/api/v1/novels/{id}/asset-tasks/timeout` | Fail stale running tasks |
| POST | `/api/v1/novels/{id}/screenplays/{sid}/asset-tasks/recover` | Recover interrupted tasks |
| POST | `/api/v1/novels/{id}/screenplays/{sid}/asset-tasks/cleanup` | Remove succeeded/cancelled tasks |

In packaged runtime, real execution requires a valid `X-Session-Token`. API keys are stored only in the OS credential vault.

## Errors

Validation and business-rule errors return HTTP 400. Missing resources return 404, revision conflicts return 409, and packaged-runtime authentication failures return 401/501. Never log or return credential values.
