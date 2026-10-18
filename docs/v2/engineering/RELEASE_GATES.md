# V2 release gates — full-release definition and evidence policy

Version: `ENG-2026.10.19-r1`. **This round is not a release.** No tag, no merge to `main`, no
Draft-PR conversion and no "RELEASE_READY" claim may follow from this document. It defines what a
future official V2 release must satisfy.

## 1. Release definition (user decision of 2026-10-19)

Official V2 ships only after **all** of the following are complete and accepted on the same release
candidate:

1. The original Master Roadmap release-required items (M0–M11 cloud scope; M12 user-authorized
   Windows acceptance) are satisfied or the user explicitly accepts a documented exception.
2. DIF-01–DIF-12 differentiated capabilities are implemented, integrated and accepted.
3. IMAGE-COMIC-01–20 are implemented, integrated and accepted under Image Studio.
4. Final acceptance on an identical build: real Windows install/upgrade, real local model/GPU
   execution where claimed, browser journeys, PostgreSQL/File parity, media artifacts, and the
   user's explicit sign-off.

Intermediate checkpoints, internal builds and test runs are allowed and must be labeled as such.

## 2. Gate categories

| Gate | Must hold | Evidence type |
| --- | --- | --- |
| G1 Source & data authority | Single owners preserved; no forked Project/Asset/Job/Provider/Model Center/Timeline; migrations append-only; backup/restore proven | source diff review + migration receipts + restore test |
| G2 Backend contracts | Full File suite PASS on the candidate SHA; full real-PostgreSQL suite PASS with zero silently skipped PG contracts; CAS/idempotency/UNKNOWN/cancel/recovery tests pass | JUnit XML + logs bound to SHA + database endpoint receipt |
| G3 Frontend | `pnpm test`, `pnpm build` (`tsc -b` + vite), design-token lint PASS; no unit suite failure hidden by e2e collection errors | logs + tool versions + lockfile hash |
| G4 Real browser | Playwright journeys PASS against the isolated real backend profile and real browser; navigation, edit, save, refresh-recovery, permission and asset/task/model/export surfaces exercised; screenshots/geometry where a golden exists | Playwright JUnit + screenshots + backend request evidence (launch/list alone is not PASS) |
| G5 Real media | Image/audio/video/subtitle/timeline/export artifacts produced by the real executors and verified by an independent parser (`ffprobe`/PIL/zip) with hashes, duration, streams, fps, dimensions | artifact hashes + ffprobe/PIL excerpts + recipes |
| G6 Model execution | Only claimed for explicitly installed/authorized local runtimes, with version, timing, VRAM/RAM peak and raw errors; no-model mode still fully usable; no hidden cloud fallback | run receipt + resource measurement; otherwise `LOCAL_REQUIRED` |
| G7 Security & privacy | Scope/role/CAS enforced; host trust; cloud egress requires explicit consent; secrets never logged; public/internal edition isolation implemented (currently PLANNED); source-privacy/egress tests pass; C2PA claims only if implemented | security test run + edition design+implementation review |
| G8 Comic capability | All IMAGE-COMIC-01–20 accepted; ORA/CBZ/PDF/layer/generation features only if truly implemented; font license (OFL) complete; deterministic export verified | traceability matrix rows ACCEPTED + artifact checks |
| G9 Windows/local | Clean install/upgrade/uninstall, no-model start, real model/GPU run on the user's hardware, Chinese IME, high-DPI, crash recovery, disk cleanup limited to app-owned paths | user-executed acceptance report bound to package SHA256 |
| G10 CI truth | Hosted CI result must be the actual run on the candidate SHA. A runner-allocation failure or canceled job is `CI_BLOCKED_NO_RUNNER` / `CANCELED`, never CI PASS; local runs do not substitute for required hosted evidence unless the user explicitly accepts the alternative | GitHub run URL + job conclusions + JUnit receipts |
| G11 Reproducible package | Versioned wheel/setup artifacts built from a clean tree; lockfile and constraints hashed; package scan; signing policy satisfied | build receipt + SHA256SUMS + scan audit |
| G12 Documentation & traceability | This engineering directory, requirement matrix validator, CHANGELOG/feature matrix updated; defects closed or explicitly accepted; known limitations published | validator exit 0 + matrix counts + doc links |

## 3. Evidence rules

- Evidence is bound to the exact Git SHA (or package SHA256) and environment; an older green run is
  not evidence for a newer SHA. Never splice Push/PR/merge runs into one fake "single success".
- Two independent result axes are mandatory: requirement status (PLANNED/IMPLEMENTED/
  INTEGRATION_VERIFIED/ACCEPTED/BLOCKED) and test result (PASS/FAIL/PARTIAL/BLOCKED/NOT_RUN).
- Never delete tests, weaken assertions, add unjustified skips/xfails or change frozen hashes to make
  a gate green. A known failing contract remains a defect.
- Mock/synthetic evidence must be labeled MOCK_ONLY and cannot satisfy G4/G5/G6/G8 quality claims.
- No secrets, user novels, private paths or personal data in artifacts.

## 4. Candidate/branch/tag policy

- Work happens on isolated engineering branches; `main` is untouched; no force-push, no history
  rewrite, no closing others' PRs, no merge of `main`, no official tag/Release without the user.
- A candidate must include: exact commit SHA, build artifact SHA256SUMS, test receipt index, known
  limitations, rollback/backup instructions.
- Signing/provenance policy must be defined before public distribution; model weights are not
  packaged; user data stays local by default.
- CI capacity/budget is a release concern: timeout/canceled evidence must be recorded as capacity
  failure, not silently retried until green.

## 5. Performance, disk, and reliability budgets (release candidate)

- Budgets must be measured, not aspirational: startup time, canvas drag response, project open time,
  job queue latency, export render time, peak RAM/VRAM, and peak disk per operation.
- Tests must run with bounded disk; large regenerable media is replaced by hashes + recipes.
- Crash/restart must not corrupt project data: CAS writes, atomic file writes, PostgreSQL
  transactions and restart recovery are verified. Unknown upstream state never auto-replays.
- Offline/no-model mode is a supported path: editing, saving, reopening and existing-content export
  must work with no model and no network.

## 6. Current readiness snapshot (2026-10-19, SHA `a072cf90`)

| Gate | Status | Reason |
| --- | --- | --- |
| G1 | PARTIAL | Owners preserved in the tree; backup/restore not re-proven this round |
| G2 | PARTIAL | Complete File suite re-run in round 2: **27 failed / 10021 passed / 5094 skipped / 13 errors** (was 190 failed / 14 errors). 37 remaining nodes are suites run without their required runner profile/flag (verified passing there); 2 OPEN (D-09, D-18), 2 intermittent harness cases (D-17, D-19). Focused real-PostgreSQL subset: 118 passed, 0 failed; full PG suite BLOCKED_ENVIRONMENT (D-07) |
| G3 | PASS (after fix) | `pnpm test` 4303 passed / 8 skipped / 0 failed after excluding Playwright e2e specs from Vitest (D-01); build and token lint pass |
| G4 | PARTIAL | System Edge 152: visual/geometry/Local-AI 15/15 PASS; creative-workbench journeys 8 failed at launcher precondition (D-10); live-backend E2E not executed |
| G5 | PARTIAL | Real CPU media/comic paths exist; acceptance artifacts not fully regenerated this round |
| G6 | NOT_RUN / LOCAL_REQUIRED | No authorized local model was run; no paid API used |
| G7 | PARTIAL / HIGH RISK | Public/internal edition isolation MISSING (PLANNED); C2PA MISSING; consent/privacy controls exist |
| G8 | PLANNED | 3/20 comic items implemented and 3 partial; remaining PLANNED |
| G9 | NOT_RUN / LOCAL_REQUIRED | Requires the user's Windows machine and explicit authorization |
| G10 | BLOCKED_EXTERNAL | Hosted CI account/runner unavailable; local runs only |
| G11 | NOT_RUN | Candidate packaging/signing not part of this baseline round |
| G12 | PARTIAL | This directory + matrix + validator added; matrix itself tracks remaining work |

**Verdict: NOT RELEASE_READY.** Do not publish V2 from this branch.
