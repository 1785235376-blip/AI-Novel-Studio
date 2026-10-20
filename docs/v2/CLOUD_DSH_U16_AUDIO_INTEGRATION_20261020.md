# DSH U16 + Audio manifest cloud integration

Date: 2026-10-20. Engineering integration and focused validation only; no product-release acceptance.

## Input and preservation

The user-supplied consolidated TXT is 243,592 bytes. SHA256:
`4e1d1dd499b2cb070506ac4723ec349e01ff704145ea50c6c84c18572653d1b7`.
It matches the supplied sidecar. Six exact patch bodies were extracted using their declared byte lengths; every patch SHA256 and the embedded original SHA256SUMS hash matched. No instruction in the attachment or earlier report was treated as execution authorization.

Patches were first applied in order to the exact `19d90d51eed4a9683c4290592dd91495125e5fcf` base in an isolated reconstruction, then to cloud baseline `b8371a48816b852176d45151eb9a0e3618a32c07` in a separate worktree. Both applied without conflicts. All 29 per-patch postimage comparisons agree between reconstruction and integration and match the patches' eight-character index prefixes. The source commit objects were not supplied, so original full commit identities and their tree IDs cannot be independently reconstructed from format-patch metadata alone. Fresh commit IDs reflect the new committer and integration parents.

| Patch | Source commit declared in patch | Cloud replay |
|---|---|---|
| 0001 | c1c400cdcbcfb4a191a4e7f7ae4750fbdc03ddc8 | e665237149d120bf1521086b55f4393a568cfcb8 |
| 0002 | 6d8176e6095c861d069ad7940a0e44065caec941 | 295db650d541041aca61140b5040a46aa23a1891 |
| 0003 | 0cb20c8f8d78d2697bb9954392597d9bab88d615 | d043a8758d2c286db92b00b64855b2cf634a2100 |
| 0004 | 0dc15d4ddf7ae807350c5bc042b27ab580c36732 | 0039b11fad0cb5fc06eca4124c39e99f325fa9d8 |
| 0005 | e815fc3fdb4d80f9d36ca2453a2fa6f237b9888a | f50eafa38e4b35014e0a6f2d6164fc6403574763 |
| 0006 | 0516c6d8a9c9c94d1ccd05fc81c6210ef5d55452 | 04a059a06351f87c772fb2d5720aa256433303d9 |

Only these six imports were applied. The older Audio originals 58bb5ed8 and 8afacfa5 were not separately applied. All 28 files from the prior cloud mask-redo, model-structure, asset-comparison and portable-cache changes remain blob-identical to b8371a48. Original refs, worktrees, user changes and unique evidence were retained. No push, main merge, Release, force update, or local-computer work occurred.

The [source-binding manifest](../delivery/v2-development/cloud-dsh-integration-source-bindings.json) contains all six hashes, byte counts, reconstructed commits, full locally verified blob IDs, preservation checks, corrective source hashes and evidence hashes.

## Review findings and separate correction

The imported tree passed the original focused selection, but new review found three defects. They are corrected separately in `3b26e0f3d5cef43a0ec199488670af4e833de53a`:

1. Bound cutout source checks could read the File scope store under asset/project locks, reversing the order of concurrent preflight/confirm. A bound-only original source lease now precedes asset/project acquisition for bounded source/mask validation. Already-leased callers remain unchanged; rendering and live stop/revocation checkpoints remain outside that lease. A deterministic lock-order assertion reproduces the original defect without hanging test threads.
2. Bound recovery listing validated the requested binding against unrelated jobs before filtering, causing a ValueError. It now filters captured-binding mismatches first and still strictly validates exact matches. Recovery beside unrelated jobs locates the original queued request without resending or treating QUEUED as completed.
3. One denied original image read could terminate the refresh loop while later cached image results survived; cancelled batches skipped refresh. All cached image payloads are now removed before refresh. Eligible jobs are independently re-read, non-404 authorization errors propagate, and cancelled payloads remain cleared.

Only two product files changed in that correction: `production_execution.py` and `safe_batches.py`, plus one new focused regression file. An independent read-only review checked the correction and found no weakened authority guards. The original six commits and all Audio author implementation files remain intact.

## Audio mount and authority

The imported mount uses `create_audio_manifest_router(_AudioManifestOwner(), mask_call)` in the existing production-service branch. `mask_call` is the original `create_production_invoker`, retaining Host session, principal, current authority, actor/scope, incarnation and permission checks. The small live-owner shim resolves the current production store/workspace; it creates no new owner.

Reads use `domain.read`. Recording obtains read and write authority, requires matching actor/scope, and rechecks both before commit. Reviewed job/version/request/receipt/output digests, formal asset version/digest and source pins remain bound. No callable invoker fails closed. The manifest module creates no execution, approval, promotion or replay operation. Environment evidence remains UNKNOWN and replay is unsupported.

The imported `AUDIO_MANIFEST_HANDOFF.md` is preserved author-stage history and still describes mounting as pending. This receipt records the later actual mounted code and synthetic-Host testing; it does not convert that history into real-Host acceptance.

## Actual cloud validation

| Check | Result |
|---|---|
| Imported U16 + Audio + mounted safe-batch File/API selection | 103 passed; 102 PostgreSQL cases deselected |
| Deterministic pre-fix regressions | Lock-order and unrelated-job lookup failed; corrected two-mask read fixture reproduced all 4 cached-read variants |
| First corrected regression selection | 8 passed; 8 PostgreSQL cases deselected |
| Final File/API selection with expanded adversarial regressions | 115 passed; 114 PostgreSQL cases deselected |
| Seven focused frontend files | 53 passed |
| UI token guard | PASS, 52 files |
| Single serial `npm run build` | `tsc -b` and Vite build passed; existing large-chunk warning |
| Diff/preservation checks | No whitespace errors; prior 28 cloud files unchanged |

Final backend tests use the existing `scripts/run_v2_checks.py` isolation and existing dependency interpreter, File storage, synthetic owned image/audio inputs and trusted synthetic Host fixtures. They call mounted product routes under both `/api` and `/api/v1`; they do not prove a live user's Host or collaboration-role configuration. The source snapshot recorded by the final test receipt matches the corrective commit contents, and no source changed during the checks.

An initial custom backend launch produced 103 **setup errors** because application import attempted a default read-only home identity path. No test was counted from it. The retry used the repository's documented isolated profile, without writing to or changing that denied path. The first new regression fixture also initially duplicated the same image/mask pair; those four duplicate-item rejections are not counted as defect evidence. After giving the second item a distinct valid mask, all four intended stale-cache regressions failed before the fix and passed afterward. Both unsuccessful and successful raw receipts are preserved with hashes.

Final Python warnings are the existing Starlette/httpx deprecation and Pydantic `schema` shadow warning. Build output also includes an npm environment-config notice. No dependency or build configuration was changed.

Logs: [final File/API](../delivery/v2-development/cloud-dsh-final-file-api.log), [frontend](../delivery/v2-development/cloud-dsh-frontend.log), [tokens](../delivery/v2-development/cloud-dsh-design-tokens.log), [build](../delivery/v2-development/cloud-dsh-serial-build.log). Full source-snapshot receipts and bootstrap/reproduction evidence remain in the owned `.runtime/dsh-integration-evidence-20261020/` directory; their hashes are recorded in the manifest.

## Unvalidated scope

Real Host/desktop, PostgreSQL, full Python/frontend suites, Clean-Windows, real GPU/models/paid APIs and Audio replay/environment reproducibility remain NOT_RUN or unsupported. Browser geometry/E2E was already blocked by the cloud Unix-socket/bwrap restriction and was not retried or bypassed. No real-Host, PostgreSQL, end-to-end, overall V2 completion or release-readiness claim follows from these focused tests.
