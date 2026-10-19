# Hosted PostgreSQL parity repairs

## Source evidence

The PostgreSQL 16 full-suite run for head `460fa31ac3e0a1d712e52e0fe858b5c3cc571520` reported 1508 passed, 37 skipped, and five failures. The original job log is retained outside the checkout as `ai-novel-cloud-evidence/job-111128965905.log`; a diagnostic excerpt and local focused-test output are in `.cloud-validation/postgres-repairs/`.

## Root causes and contracts

1. **Context migration serialization (production):** File source characters and locations can omit the default privacy field. Migration previously discarded that presence information, while PostgreSQL serialization always emitted it. Secret migration discarded extensions such as `type` and manufactured a public `title` absent from the source. Migration now stores field-presence provenance in existing JSON metadata and keeps secret extension fields. Serializers reconstruct source shape while authoritative database identity, content, status and privacy columns override extensions. The absence marker suppresses only `CLOUD_ALLOWED`; a stricter stored policy is always explicit. Existing records without new provenance retain their previous serialization. Re-running migration populates provenance using the existing idempotent sync flow. No schema or policy-value change is made.
2. **Writing goal (production):** PostgreSQL update omitted `writing_goal` from its metadata allowlist, and metadata reads omitted it too. Both now include this single authorized field. Unknown update keys cannot alter identity or ownership. API tests verify update response, subsequent GET, and overview.
3. **Location status (production):** The generic extension-field filter reserves `status` because character status has an authoritative column. Locations keep status in facts, so their serializer must explicitly restore it. Other reserved fields remain protected. The API test checks update/list equality and preserved `LOCAL_ONLY` privacy.
4. **Adaptation (test):** PostgreSQL emits canonical Markdown with trailing block newlines. The old suffix assertion wrongly assumed raw File formatting. Production content is unchanged. The test now requires exact source/copy content equality, unchanged original records, equal structured documents, the exact original paragraph text and a single title heading.
5. **Plugin startup (test harness):** The subprocess inherited `STORAGE_BACKEND=postgres` while the safety fixture correctly scrubbed database credentials. This test exercises plugin startup isolation, not connectivity; its subprocess now explicitly selects File. No credentials are restored or exposed globally, and PostgreSQL production startup remains fail-closed.

## Separate File-suite timing flake

`test_agent_job_timeout_is_terminal_and_retry_creates_new_job` slept 1.1 seconds against a one-second background timer. On a loaded hosted runner, callback scheduling and I/O can leave the job working at the observation instant. The replacement controls only the timer scheduler and blocks model completion with an event. It verifies the production timer is started at the requested interval, fires the production timeout callback, checks `FAILED/TIMEOUT`, then releases and joins the late worker and verifies the terminal state cannot be overwritten. The independent retry assertions remain. This removes wall-clock assumptions without retries, exclusions, or weaker terminal-state assertions.

## Validation

- 71 focused tests passed locally, including migration-to-serializer source-shape checks, restrictive-privacy and reserved-field negative cases, writing-goal metadata persistence, location round trips, adaptation, plugin startup, and agent-job tests.
- `git diff --check` and compilation of the changed production modules passed.
- Local validation used the repository virtualenv, isolated HOME/XDG/data directories, File storage, mock providers, cloud disabled, and memory credential vault.
- PostgreSQL is not installed in this local executor. These local results do **not** establish a new real-PostgreSQL pass. The existing strict raw/serialized/context-pack comparison and real migration idempotence tests remain for the next hosted PostgreSQL 16 full-suite run on the published exact head.
