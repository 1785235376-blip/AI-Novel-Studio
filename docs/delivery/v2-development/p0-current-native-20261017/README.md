# Current-code native P0 verification

Source checkpoint: 468457706f64d9b8cc793b9a6fa39fa4b354aa15. No product code, tests, migrations, runner or approval rules changed in this acceptance step.

Real PostgreSQL 17.11: 38 selected original tests passed, 38 non-PG cases deselected. File: 43 original tests passed, 37 PG cases deselected. These are scoped results, not full-product or whole-PostgreSQL acceptance.

The original wrapper created a fresh v2_director_security_20261017_r1 database from template0 in a new checkout-owned disposable cluster. Live version/database/user/OID/loopback identity was verified. It had no application objects before all 20 original sorted migrations were applied. The owned server was stopped successfully after testing; the database is retained. The old cluster and its databases were not reused or changed.

The unchanged tests inspect actual persisted roles, permissions, workspace bindings, storyline/branch records, audits and original database rows. They reuse the same public project ID and old session/branch in negative controls, verify explicit PROJECT_SCOPE_FORBIDDEN rather than a missing-scope error, preserve valid new actors and unrelated workspace authority, cover create/link rollback, delayed deletion/grants, and generation incarnation isolation. The fix itself predates this run; this packet does not claim a new before-fix execution or overwrite historical defect evidence.

Both backend runs bracket the same source hashes. Original package checksums match the retained signed Debian provenance. TCP loopback is usable even though Unix socket creation is restricted; PostgreSQL is launched by the unchanged wrapper with Unix sockets disabled. That distinction is why the earlier browser startup failure must not be generalized to database testing.

Independent Director durable pending review remains explicitly File-only; this P0 success does not change that implementation boundary. Browser/Windows/GPU/live-provider acceptance and full V2 release are still open. This evidence was produced after the fixed fourteen-commit archive candidate and is not silently added to that upload request.
