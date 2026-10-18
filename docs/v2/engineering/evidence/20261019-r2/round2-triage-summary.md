# Round-2 triage evidence summary (2026-10-19)

Full narrative and classification: docs/v2/engineering/TRIAGE_20261019_r2.md

Commands were executed with the isolated profile under <repo>/.runtime, PYTHONPATH=<repo>,
Git-for-Windows bin on PATH, STORAGE_BACKEND=file, MOCK_PROVIDER=true, ENABLE_CLOUD=false.
Collaboration suites additionally used ENABLE_COLLABORATION_RUNTIME + EXPERIMENTAL_FEATURES
and NOVEL_DATA_PATH under .runtime/v2-checks/<label> as recorded in the RUNBOOK.

Key results:

- Previously failing files (34 files, default profile): 995 passed, 6 failed, 12 errors, 426 skipped.
- After fixes, four residual files: 104 passed, 1 failed (D-18 performance harness), 3 skipped.
- R3-I adoption: 4 passed (collaboration off, runner profile).
- R3-I authorized: 8 passed (collaboration on).
- Prompt-process revocation: 22 passed, 2 intermittent failures, 24 skipped; rerun 4 passed then 3+1 intermittent.
- Authority commit leases with PYTHONPATH: 11 passed.
- Real-text runner on Windows: 97 skipped with explicit POSIX-only reason.
- Catalog + interop contracts + engineering guards: 208 passed.
