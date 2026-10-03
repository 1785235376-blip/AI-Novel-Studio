# Cloud baseline repairs (2026-10-03)

Base: `fed2404c` (live main checkout). This report describes the focused backend repair, not PostgreSQL, packaged-runtime, real-provider, UI, or release certification.

## Reproduced baseline

The unmodified File-backend suite produced **1,440 passed, 2 failed, 29 skipped**. The two failures also reproduced in isolation: **2 failed, 2 passed** across `test_user_preference_service.py` and `test_world_rule_payload.py`.

Local evidence:

- `.cloud-validation/baseline-full.log`
- `.cloud-validation/repairs/before.log`
- `.cloud-validation/repairs/after-focused.log`

These local logs are verification artifacts and are not intended as repository source files.

## World-rule normalization: production repair

`normalize_world_rule_payload()` previously wrapped an entire comma-delimited string as a single forbidden term. Consequently, a stored rule such as `永生,无需代价` did not match text containing only `永生`.

String input now uses the editor's existing delimiters: ASCII comma, Chinese comma, and newline. Trimming handles CRLF; duplicate and blank terms retain existing normalization behavior. Explicit list elements remain literal terms, so a comma inside an explicitly supplied list item is not split. `forbidden_terms` still takes precedence over the legacy `forbidden` alias. The existing 100-item limit applies after string splitting, before deduplication. Existing free-form metadata is preserved and input is not mutated.

Tests cover both input names, all delimiters, literal list commas, duplicate/blank handling, invalid containers, limits after splitting, metadata preservation, and an individual-term continuity finding. No proposal approval, canonical write, trusted-session, Diff, acceptance, or AtomicCommit path was changed.

## Preference payload: evidence-based test correction

The older failure registry labels the extra `harness_enabled` field as `PRODUCT_BASELINE` and says production changes are required. Current source inspection establishes a conflicting, explicit contract:

- `UserPreferenceService.list()` includes the field with a false default, including in the initial source-import commit `ddf7997`.
- Harness status/context/process-start API paths read this field for authorization.
- `tests/test_harness_enable_api.py` requires the field and checks its enable round-trip.
- `frontend/src/api.ts` declares the field; `AiControlCenter.tsx` uses it to disable unauthorized Harness startup.

Removing the field to satisfy the older exact-dictionary assertion would break these consumers. The test's exact expected shape now includes `harness_enabled: False`; the assertion remains exact. Production preference code is unchanged. Additional tests verify that preference enablement, sharing, and Harness authorization stay independent and persist across service instances, and that legacy files without the Harness field default to false. This is a stale test-contract correction, not a claim that a production preference defect was fixed. Historical reports remain historical evidence and should not be rewritten as prior passing runs.

## Focused verification

Command (using the existing isolated mock/File environment):

```sh
.venv/bin/python -m pytest tests/test_user_preference_service.py \
  tests/test_world_rule_payload.py tests/test_harness* tests/test_p1_regression.py -q
```

Result: **54 passed**, one pre-existing Starlette/httpx deprecation warning. No paid provider calls. The parent task owns the final integrated full-suite rerun after all concurrently developed changes are present.

Additional downstream guard: `.venv/bin/python -m pytest tests/test_continuity_api.py tests/test_lore* -q` produced **19 passed, 6 skipped**, one identical deprecation warning. The PostgreSQL-dependent skips are not PostgreSQL verification. Evidence: `.cloud-validation/repairs/after-lore-continuity.log`.
