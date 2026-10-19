# V2 Engineering Baseline and Norms — entry point

Version: `ENG-2026.10.19-r1`
Date: 2026-10-19 (Asia/Shanghai)
Branch: `work/v2-eng-baseline-20261019` (base `origin/feature/v2-narrative-platform` @ `a072cf90`)
Repository: `1785235376-blip/AI-Novel-Studio`

This directory is the **single entry point for V2 engineering evidence and norms**.
It does not replace the product requirements; it binds them to a runnable, reproducible
engineering baseline, a machine-readable requirement index, and explicit release gates.

## Read this first

| Document | What it owns | What it does NOT claim |
| --- | --- | --- |
| [BASELINE_20261019_r1.md](BASELINE_20261019_r1.md) | Actual host/toolchain, Git/remote/PR state, commands actually executed, PASS/FAIL/BLOCKED/NOT_RUN results, evidence paths, disk accounting | No release qualification; no Windows final acceptance |
| [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) | Human entry to the unique machine-readable requirement matrix (`requirements-traceability.json`) covering original V2 modules, A/B/U packages, DIF-01–12, IMAGE-COMIC-01–20 | Rows are not promoted to ACCEPTED by the existence of a document or a contract test |
| [RUNBOOK.md](RUNBOOK.md) | Isolated environment, dependencies, no-model mode, exact test commands (backend File/PostgreSQL, frontend, media, browser, desktop), diagnostics, cleanup | Not a substitute for the user's Windows/GPU acceptance |
| [EXECUTION_AND_DATA_CONTRACTS.md](EXECUTION_AND_DATA_CONTRACTS.md) | Single-authority owners, DTO/schema/version rules, Graph ports/nodes, Job/Review/Timeline state machines, CAS/idempotency/UNKNOWN, cancellation, error layering, atomicity, observability | Not a new API surface; it records the contracts already owned by existing modules |
| [SECURITY_AND_ISOLATION.md](SECURITY_AND_ISOLATION.md) | Host trust, project scope/roles, public vs internal-research separation, cloud consent, secret/log redaction, path boundaries, third-party licensing, C2PA/source-claim boundaries | Not a claim that Windows host attestation or remote collaboration is accepted |
| [MEDIA_AND_COMIC_CONTRACTS.md](MEDIA_AND_COMIC_CONTRACTS.md) | Image/Video/Audio/Subtitle/Timeline/Comic engineering contracts, real media verification, layer/panel/bubble data, export capability table, loss reporting, dynamic-comic handoff | Does not claim ORA/CBZ/PDF comic export, AI comic generation or dynamic comics exist |
| [RELEASE_GATES.md](RELEASE_GATES.md) | Release gate definition for the full V2 (roadmap + DIF + COMIC), artifact/signing policy, CI/offline rules, performance/disk budgets, human acceptance duties | This round is **not** release-ready and cannot issue a V2 tag |
| [TRIAGE_20261019_r2.md](TRIAGE_20261019_r2.md) | Round-2 classification of all 203 round-1 failures and remaining open issues |
| [TRIAGE_20261019_r3.md](TRIAGE_20261019_r3.md) | Round-3 closure: D-09/D-18/D-19, revocation profile status, JUnit accounting correction, suite skip/order audit, unified Windows entry results |
| [REQUIREMENT_SOURCES.md](REQUIREMENT_SOURCES.md) | Authoritative requirement sources, SPEC-2026.10.19-r1 ingestion hash/verification, matrix binding and update procedure |
| [EDITIONS_AND_BUILD_BOUNDARIES.md](EDITIONS_AND_BUILD_BOUNDARIES.md) | Public vs internal-research edition boundary, executed build invariants, remaining BLOCKED deployment isolation |
| [SINGLE_AUTHORITY_MAP.md](SINGLE_AUTHORITY_MAP.md) | Graph/Asset/Job/Review/Timeline single-authority owners and cross-media dependency/recovery rules |
| [COMPATIBILITY_MIGRATIONS_AND_OPERATIONS.md](COMPATIBILITY_MIGRATIONS_AND_OPERATIONS.md) | API/DTO/schema compatibility, DB migrations/rollback, incarnation/permissions, logging/backup/disk/supply-chain contracts |
| [PROVIDER_MODEL_RESOURCE_POLICY.md](PROVIDER_MODEL_RESOURCE_POLICY.md) | Provider admission, model capability evidence, VRAM/resource/reclamation policy and honest gaps |
| [WORLD_DEPENDENCY_INCREMENT_AUDIT.md](WORLD_DEPENDENCY_INCREMENT_AUDIT.md) | Story-world semantic dependency audit: reusable owners, implemented provenance increment, DIF-01/02 dependency block |
| [DEFECTS_20261019_r1.md](DEFECTS_20261019_r1.md) | Defects found, minimal reproduction, fix commit, regression evidence, remaining defects | Fixed defects are evidence-bound to a SHA |

## Authority order

1. Live code, real migrations, actual test/production evidence at the recorded SHA.
2. Machine-readable requirement index: [requirements-traceability.json](requirements-traceability.json).
3. This engineering directory.
4. History documents: `AI_NOVEL_STUDIO_V2_ARCHITECTURE.md`, `AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md`,
   `AI_NOVEL_STUDIO_V2_FINAL_DEVELOPMENT_REPORT.md`, `V2_ADVANCED_CAPABILITY_GAP_REPORT.md`,
   `docs/v2/*`, `docs/delivery/*`. These are evidence/history, not current status.
5. User-issued scope documents. The release-scope file `PoemSeed_Studio_V2_Release_Scope_20261019.txt`
   (SPEC-2026.10.19-r1) is now **ingested and hash-verified** at
   [spec/SPEC-2026.10.19-r1.txt](spec/SPEC-2026.10.19-r1.txt) (SHA256
   `a681eb0f1deff156bbb2a7db437e19cabc11f290d28416f9f0c8fe8bd07785ac`, 37,693 bytes / 352 lines).
   Matrix DIF/COMIC rows bind its section/line/MUST/acceptance text; see [REQUIREMENT_SOURCES.md](REQUIREMENT_SOURCES.md).

## Status vocabulary (fixed)

Two independent axes — never mix them:

- Requirement status: `PLANNED` / `IMPLEMENTED` / `INTEGRATION_VERIFIED` / `ACCEPTED` / `BLOCKED`
- Test result: `PASS` / `FAIL` / `PARTIAL` / `BLOCKED` / `NOT_RUN`

`IMPLEMENTED` means owning source exists. `INTEGRATION_VERIFIED` requires a real executed
integration/browser/media test at the recorded SHA. `ACCEPTED` requires the explicit human
acceptance defined in [RELEASE_GATES.md](RELEASE_GATES.md); no automated run can grant it.

## Verify the requirement index

```powershell
python scripts/validate_requirements_traceability.py
python -m pytest -q tests/test_engineering_traceability.py
```

The validator fails on: duplicate/missing IDs, unknown status enums, missing required fields,
DIF/COMIC ID gaps, A/B/U package gaps, and release-gate references that do not exist.

## Non-claims of this baseline

- The full V2 release is **not** ready. Most DIF-01–12 capabilities are `PLANNED` or partial
  integrations; most IMAGE-COMIC-01–20 features are `PLANNED`. See the matrix counts.
- No model was called. No paid API was used. No model weights were downloaded.
- Real Windows installation/upgrade and GPU inference acceptance remain `LOCAL_REQUIRED`.
- Hosted CI could not be treated as evidence (account/billing lock; runner never started).
