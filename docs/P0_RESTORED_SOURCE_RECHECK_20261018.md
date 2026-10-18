# Original project-retirement P0: restored-source recheck

Checked source: c02be1600bf89176dfd0c9f4f9b658c2f3df848e, 2026-10-18 12:26–12:29 UTC. This is fresh evidence for the existing fix, not a new security implementation and not a rerun of the pre-fix vulnerable version.

The earlier evidence commit is 093c8f66bfd5172d08f6d2d724b9964f15fdf2af, verified as an ancestor of current HEAD. Its retained logs are p0-current-file-r1.log and p0-current-postgres-r1.log. The present checks use the recovered dependency-only interpreter and current source, not the earlier donor interpreter.

## Results

- File: 43 passed, 37 deselected.
- PostgreSQL: 38 passed, 38 deselected.
- PostgreSQL 17.11, existing isolated UTF8 database v2_recovered_ocr_export_20261018, OID 16384; original migration setup is retained from recovery. This was reuse, not a newly initialized database. Server stopped successfully.
- Original assertions and tests unchanged.

Test modules: test_v2_project_retirement.py, test_v2_project_retirement_file_io.py, test_v2_generation_incarnation.py, test_v2_retirement_lock_order.py, test_round3i_pg_incarnation.py. The File and PostgreSQL commands select their relevant original backend cases.

Coverage includes actual persisted project-workspace bindings, project/branch authority retirement without erasing workspace/audit data, same-id recreation with fresh legitimate authority, old-generation/data/asset/idempotency isolation, create-and-link failure atomicity, partial file cleanup failures, delayed old deletes/grants, rollback and lock ordering. For exact assertions, consult those original test modules and raw receipts rather than treating this prose as a test substitute.

## Retained setup failure

The first PostgreSQL recheck passed 37 cases and failed one fixture before its assertion because the invocation omitted the original --collaboration-runtime runner option. The historical receipt and fixture both require that isolated test flag before app.main import. The corrected invocation supplied that original option and all 38 cases passed. No test, production default, authentication gate or application source was changed to obtain the pass. Both runs and their server-stop receipts are retained.

Evidence: docs/delivery/v2-development/p0-restored-current-*. These targeted security checks are not full V2, browser, Windows, real-model or release acceptance.
