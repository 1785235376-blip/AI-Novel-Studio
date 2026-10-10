# M4-D initial hosted CI terminal archive

Outcome: all four original attempt-1 runs reached natural terminal states. Cloud CI failed before any job; both Interop events succeeded. This is not full-source acceptance.

- Repository: `1785235376-blip/AI-Novel-Studio`, branch `feature/v2-narrative-platform`, Draft PR #47
- Published commit: `c491d1b0227a877eaa5bad7651ed22ba67463439`
- Published parent: `e6ff3431cf84b01b77cd1bd73a977fd5e784447b`
- Published tree: `5da5d8b5285fc720031889b5b37798a9db328e93`
- PR synthetic merge checkout/event SHA: `d90352f005a33240a88d6369d72844d18f98344e`; its tree equals the published tree. API run `head_sha` remains the published commit.
- All run attempts: 1. No rerun, cancellation, source edit, index mutation, push, or PR update performed.

## Actual hosted results

- [.github/workflows/cloud-ci.yml / push / 38078421006](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38078421006): **FAILURE**; 0 jobs; attempt 1.
  - Zero jobs and zero artifacts. No Cloud test or browser stage executed.
  - Exact workflow-validation annotation unavailable: the check-suite endpoint is outside the official connector allowlist. Failure cause is not asserted from inference.
- [Local Interop V1 / push / 38078421941](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38078421941): **SUCCESS**; 3 jobs; attempt 1.
  - file: 413 collected; 345 passed, 68 skipped, 0 failures/errors; 26.1 s.
  - postgres: 413 collected; 345 passed, 68 skipped, 0 failures/errors; 763.53 s.
  - Actual checked-out/event SHA: `c491d1b0227a877eaa5bad7651ed22ba67463439`; source tree `5da5d8b5285fc720031889b5b37798a9db328e93`.
  - Windows reference: 8 MOCK_ONLY checks; actual Desktop LOCAL_REQUIRED; cross-user hostile attempt NOT_RUN.
  - Each backend preparation harness: 23 MOCK_ONLY passes, 1 native-required NOT_RUN.
- [Shared R123 evidence / pull_request / 38078425519](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38078425519): **SUCCESS**; 1 jobs; attempt 1.
  - Success means `ALL_THREE_KNOWN_DEFECTS_REPRODUCED_RED` at original baseline `c6f2126115b52e17839d48efea091dc21ec08c61` (tree `eb80a9fa5f5aa6b8c2cbd0e1e67f7b7a48ac522f`).
  - Reproduction script exit-zero is not a defect pass; this is not current-source R123 acceptance.
- [Local Interop V1 / pull_request / 38078425636](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38078425636): **SUCCESS**; 3 jobs; attempt 1.
  - file: 413 collected; 345 passed, 68 skipped, 0 failures/errors; 28.72 s.
  - postgres: 413 collected; 345 passed, 68 skipped, 0 failures/errors; 581.45 s.
  - Actual checked-out/event SHA: `d90352f005a33240a88d6369d72844d18f98344e`; source tree `5da5d8b5285fc720031889b5b37798a9db328e93`.
  - Windows reference: 8 MOCK_ONLY checks; actual Desktop LOCAL_REQUIRED; cross-user hostile attempt NOT_RUN.
  - Each backend preparation harness: 23 MOCK_ONLY passes, 1 native-required NOT_RUN.

## Evidence integrity

- Seven downloaded text-only ZIPs, 174,685 bytes and 51 members. Every downloaded ZIP SHA-256 and byte size matches GitHub metadata; CRC, safe member paths, and UTF-8 decoding all pass.
- Seven decoded job logs and complete terminal run/job/artifact metadata are archived. No Windows binaries were downloaded.
- `artifact-integrity.json` records every ZIP digest, size and per-member digest; `terminal.json` records the compact outcome and source distinctions.

## Boundaries retained

- Local stage results are separate: File 153 passed / 118 skipped; adjacent PostgreSQL 131 passed / 16 failed / 124 skipped; export-only 21 passed per backend; UI 2416 passed / 8 old skips; infrastructure 320 passed.
- Local browser remains BLOCKED_OS_SOCKET_EPERM_BEFORE_PAGE. Cloud browser validation did not run because the Cloud workflow has zero jobs.
- Old M4-C FAILED_OBSERVED evidence is unchanged. Historical independent review remains BLOCKED; denied historical artifacts were not requested.
- Hosted Interop success does not erase the local adjacent PostgreSQL failures or establish full-source acceptance.

Observed terminal inventory: 2026-10-10T19:19:58Z.
