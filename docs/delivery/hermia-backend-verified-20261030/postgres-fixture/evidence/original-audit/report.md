# Read-only PostgreSQL fixture audit

Source HEAD: 3139927b997c18048704aa958a73787fa12a7251.
No application/test source changes, real database operations, credentials or network calls performed by this audit. Evidence files only were written. Existing PostgreSQL 34-pass milestone remains valid: its database scenarios capture the intended URL before autouse clearing. This audit identifies separate not-yet-validated cases.

## Root cause and exact baseline lines

`tests/conftest.py:27-29` lists three database variables. The function-scoped autouse fixture at39 clears them at60-63 and restores them at65-67. Backend selection at78-87 is collection-time, before this clearing. Runtime readers therefore do not receive the selected URL.

- `tests/test_identity_membership_postgres.py:22-26`: one runtime skip. `load_dotenv()` at23 can instead reload unrelated project environment.
- `tests/test_generation_snapshot_runtime_v056.py:107-110,126-129`: two runtime skips.
- `tests/test_context_intelligence.py:170-173`: one runtime skip; lacks PostgreSQL-only marker.
- `tests/test_lore_context_contract.py:149-152,287-290`: two runtime skips; both lack PostgreSQL-only markers.
- `tests/test_v056_atomic_persistence_integration.py:95-105`: helper load_dotenv at96, runtime URL lookup at97, explicit failure at99 when absent.
- `tests/test_collaboration_ux_api_v057.py:122-126`: load_dotenv at123, lookup124, explicit failure126.
- `tests/test_chapter_concurrency.py:93-99`: collection health_check can connect before backend/test isolation; if successful the later direct environment lookup raises KeyError. Lacks PostgreSQL-only marker.

Count: 9 cases in7files. In a clean process without dotenv fallback: six skip, two explicitly fail, one KeyError (conditional on collection health gate). Source mapping, not nine executed PG tests.

## No-database proof

`no_database_proof.py` imports the actual conftest fixture and invokes its wrapped generator while stubbing four imported application modules. It injects only a non-connection sentinel, proves all listed variables disappear during fixture yield, direct lookup raises KeyError, getenv is empty, and original sentinel state returns at teardown. The captured log contains three passing assertions. This proves fixture mechanics, not PostgreSQL correctness.

## Minimum safe correction recommendation

Keep global provider/database isolation unchanged. Capture only explicit TEST_POSTGRES_DATABASE_URL during pytest configuration, before per-test cleanup, and expose it to these selected tests through a dedicated isolated-test fixture. Never fall back to DATABASE_URL or dotenv. Require explicit PostgreSQL/isolation selection, validate postgres scheme, literal127.0.0.1 host, dedicated synthetic database-name pattern, no query/fragment, and produce credential-free errors. URL shape cannot prove fresh-instance provenance: the launcher must create a new synthetic cluster/database and own cleanup.

Add PostgreSQL-only markers to the four unmarked cases above. Remove chapter collection-time health check and remove affected dotenv fallback. Do not connect during configuration/collection. With File selected, marker filtering skips before fixture use. With PostgreSQL explicitly selected, missing/invalid explicit configuration must fail, not report a misleading unavailable skip.

Validate without a database: URL selection/validation, no fallback, marker gating, no collection connection, absent-configuration failure, credential-safe diagnostic rendering, and existing environment restoration. Real PostgreSQL correctness remains NOT_RUN for these nine cases until a separately authorized fresh test instance is available.
