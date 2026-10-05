# R2 test results — checkpoint ledger

Status: **final release test set PENDING_LEAD**. Fixed inspection snapshot `547167e8abce15cad3495779f52e845310a0a1fe`, tree `528459b8c7d6b94dde8b70e37c1e52d12524fc81`. Results below belong to their stated checkpoints, not automatically to later source changes.

## Environment and safe execution

Local tests use isolated HOME/XDG/runtime-data roots, File backend, synthetic manuscript/media, cloud disabled, test-only memory vault and explicit Mock/recording adapters. No user credentials, real model/GPU or paid calls were used. Python 3.12.14, Node 24.19.0, pnpm 10.6.5 locally. CI configuration pins Python 3.12.9, Node 22.14.0, PostgreSQL 16 and .NET 8.0.424/Windows 2022; actual job runs remain a separate result.

## Current and historical checkpoints

| Scope | Result | Revision/evidence qualification |
|---|---|---|
| Independent audit original Python | At eb165609: 9 failed / 1 passed | `evidence/independent-before/AUDIT_REPORT.md`, `adversarial-final.log`; grouped into seven findings with UI |
| Independent original UI scope assertion | Failed at eb165609 | `evidence/independent-before/workflow-ui-scope.log` |
| Original Python invariants after repairs | 10 passed | Current stdout inspected; unchanged original assertions; publishable exact-checkout receipt **PENDING_LEAD** |
| Exact original UI assertion after repair | Passed | Byte-identical archived test included in `evidence/workflow-scope.xml`; focused suite 30 passed/5 files |
| Acceptance integrity focused | 35 passed | `evidence/acceptance-integrity.txt/.xml`; 17 new tests include two-process single-host contention. Not distributed PG verification |
| Dispatch repair focused | 136 passed / 1 skipped | `evidence/dispatch-repair.txt/.xml`; synthetic recording transport and regression checks |
| Latest full File backend | **2032 passed / 35 skipped / 1 failed** | Integration worktree stdout inspected. Public full log/XML + precise test revision **PENDING_LEAD** |
| Latest focused contract correction | **143 passed** | Current local stdout inspected; integration lead identifies this as corrected contract regression. Public exact-checkout artifact **PENDING_LEAD**; not a full-suite pass |
| Latest full frontend unit | **548 passed / 108 files** | Integration worktree stdout inspected. Public final log/XML + precise test revision **PENDING_LEAD** |
| Earlier UI consent checkpoint | 547 passed / 1 failed | `evidence/manual-cloud-consent-frontend.txt`; superseded by inspected 548-pass checkpoint, preserved failure evidence |
| Earlier discovery/provider/hardware combined | 263 passed / 1 skipped | `evidence/local-ai-provider-hardware.txt/.xml`; independent later discovery findings remain open |
| Earlier dedicated discovery/backend | 204 passed | `evidence/local-ai-backend.txt/.xml`; overlaps combined run, mostly standalone lifecycle rather than final app execution |
| Earlier Local AI/frontend focus | 36 passed | `evidence/local-ai-frontend.txt`; not proof of later callback repairs |
| Structured planning integration | 40 focused checks passed | `planning-work.md`, `evidence/planning-review.txt/.xml`; actual mounted aliases and draft-only flow; model adapters synthetic |
| Inventory worker initial/expanded | 18 passed, later overlapping 47 passed | `evidence/readiness-focused.*`, `readiness-planning-focused.*`; earlier worktree checkpoints, not additive |
| Exports focused | 133 backend / 72 frontend passed | `evidence/export-backend.txt`, `export-frontend.txt`; complete fountain-js parser included |
| Local File scale fixture | 200 chapters, 1,002,092 characters, 800 heuristic candidates; 53.848 s; Python tracemalloc peak 19,250,094 bytes | `evidence/synthetic-scale.json`; measured synthetic environment only, not discovery/GPU or universal performance acceptance |
| PDF font checks | Pinned licensed font, embedded TrueType/Unicode mapping observed | `evidence/font-manifest.json`, `pdf-fonts.txt`; not Windows print/layout acceptance |

Counts overlap. Skipped tests do not pass. Earlier full eb165609 audit had 1845 passed/36 skipped and frontend 484/103 files; those cannot be reused for the expanded current candidate. Earlier lead pre-publish full run failed an outdated PG Session fake, documented in `evidence/integration-prepublish.txt`; this is separate from the latest import-policy fixture failure.

## Latest full-suite failure

`tests/test_r2_import_boundaries.py::test_import_excerpt_confirmation_does_not_waive_stored_secrets` is the sole latest failure. The stricter API rejects a test double lacking required current policy authority with 403; the old fixture expects its prior error path. Integration lead reports a fixture correction without relaxing production authorization; the current 143-test focused run is green. **Focused contract rerun passes 143 tests (local stdout inspected); its public exact-checkout receipt and complete final rerun are PENDING_LEAD** here. Do not relabel the failed full run as passing.

## Independent Discovery review still open

Fixed `547167e8abce15cad3495779f52e845310a0a1fe` is under separate independent review. Findings cover Ollama remote-model locality, enabled text streaming eligibility, model-digest rescan revocation, Disable-versus-late-enable and external llama alias mapping. Author fixes are newer working-tree changes; tests above do not establish they passed. See the matrix's LAD-01–LAD-28 section and discovery review ledger.

## Required final exact-SHA gate slots

| Gate | Final checkout SHA | Result | Run/job/artifact/hash |
|---|---|---|---|
| Full File backend | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |
| Real PostgreSQL 16 full suite + migration/restart/restore/concurrency | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |
| Full frontend unit | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |
| TypeScript/Vite/design tokens/frozen lock install | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |
| Original independent invariants + new discovery probes | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |
| Browser full authoring/Draft/Diff/Accept/restore/conflict/export | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |
| Browser export isolation and Local AI lifecycle/three viewports | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |
| Hosted Windows Host build/native contracts | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |
| Artifact manifest/license/font/package hashes | PENDING_LEAD | PENDING_LEAD | PENDING_LEAD |

Record push branch SHA and PR merge checkout separately. Do not assign a later documentation commit to earlier test runs.

## Reproduction entry points

Use only a clean exact checkout and new synthetic runtime-data/HOME/XDG directories. The checked-in CI harness `.github/ci/prepare.sh`, `.github/ci/postgres_gate.py`, `.github/ci/receipt.py` and `.github/workflows/cloud-ci.yml` define isolated setup and receipt capture. Do not run against existing user data.

- Backend: `python -m pytest -q -ra --junitxml=<new-evidence-dir>/backend.xml`
- Critical focused tests: `tests/test_r2_outbound_dispatch_authority.py`, `test_r2_dispatch_revalidation.py`, `test_r2_legacy_egress_guards.py`, `test_r2_acceptance_integrity.py`, `test_local_ai_discovery.py`, `test_r2_import_boundaries.py`.
- Frontend: `pnpm install --frozen-lockfile`, `pnpm test`, `pnpm build`, `pnpm lint` in `frontend`.
- Browser: `pnpm exec playwright test --config playwright.r2.config.ts`; `playwright.export.config.ts`; and `playwright.visual.config.ts --grep 'shell geometry|compact desktop|Local AI' --update-snapshots=none`.
- Real-PG gate uses an explicit disposable database and matching PostgreSQL 16 client tools. Missing configured database is NOT_RUN, not substitute coverage.

## NOT_RUN/BLOCKED

Local Chromium fails before page assertions due socket EPERM (bundled executable also unavailable). See `evidence/export-browser-bundled-blocked.txt` and `export-browser-system-blocked.txt`; no fabricated screenshots/goldens. Current hosted browser result is PENDING_LEAD.

Interactive Windows/WebView2/OS Credential Manager, install/upgrade/uninstall retention, Chinese IME, true GPU/model execution, Comfy custom workflows, actual licenses and user acceptance remain NOT_RUN. Hosted Windows compilation/native contracts cannot replace a real interactive desktop or complete installer. No new-head hosted result is inferred from workflow YAML.
