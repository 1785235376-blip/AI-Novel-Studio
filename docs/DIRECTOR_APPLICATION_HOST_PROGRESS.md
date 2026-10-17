# Application-mounted versioned Director actions

The existing application composition now explicitly opts into the existing observation and model-action adapters. The router factory still defaults to off; original narrative/model/inspection feature flags, current local Host session, origin/forwarded-identity checks, project/scope authority and original storage owners remain mandatory. No second workflow engine, automatic model call, retry or adoption was added.

A real application-composition RED run first showed missing advertisement and 404 model-preview routes at both /api and /api/v1. The application mount closes that gap. Actual main-app tests use the original workbench resolver and registered synthetic Host sessions, not replacement authorization functions. File preview, one original Job, explicit candidate preparation, human review, DRAFT persistence and read-only reopening pass. Two cases also use native loopback TCP through Uvicorn and HTTPX; optional application lifespan workers are not started. The LocalTextAdapter is real, but its provider response is still a test fixture: this is not live-model, GPU, browser or packaged-Windows quality evidence.

The pending review repository remains File-only. Two fresh real PostgreSQL cases use actual PostgreSQL generation persistence and prove no advertisement, a closed preview rejection, unchanged scope data and unchanged Jobs. They do not implement PostgreSQL pending review.

Original default-off constructor tests remain unchanged. Original Host and feature denials are preserved. Corrected new test assumptions are retained in failed logs: revoke takes a token rather than actor ID; the existing global loopback middleware rejects remote callers before route cache headers; full application errors have the existing normalized envelope; absent adoption is a denied read, not a None receipt. No original tests or guards were weakened.

The original API-catalog generator also catches up the complete mounted source map: 2,315 operations, 72 previously uncatalogued method/path entries, none removed. Only 20 of those are the newly mounted versioned Director operations; the remainder include already-existing owners and Research inspection. This is source inventory, not 72 newly implemented or accepted features.

Targeted checks: 59 File/Host/catalog checks pass, including the two native TCP cases; two real PostgreSQL unsupported-storage checks pass. Broader integrated regressions, current packaging and V2 inventory reconciliation follow. Browser/geometry, real provider quality, complete advanced-feature scope and release acceptance remain open.

Final broad gates at source 29df291: 556 File, 235 real PostgreSQL, 399 frontend, forced TypeScript/build/token checks, and 87 PUBLIC packaging tests passed. Four actual artifacts and all final source hashes were reconciled; see delivery/v2-development/director-application-host-20261017/README.md. Canonical coverage inventory reconciliation remains pending.
