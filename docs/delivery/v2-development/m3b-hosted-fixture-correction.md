# M3-B hosted browser fixture correction

Base: `c386b0608ae92d18c351b5cb6e367380808a45cf`.

## Diagnosis

The preserved hosted jobs `113928707575` and `113928741339` each reported 11 passing and 3 failing browser cases. This correction addresses deterministic assumptions in the two additive M3-B journey files. It does not change product behavior.

- The files journey intentionally follows the original consent journey and requires its scan to remain `COMPLETED`. `LocalAiDiscovery.tsx` initially renders a disabled `预览 AI 检测范围` action while reading the snapshot, then correctly renders the enabled `重新预览检测范围` action for an existing scan. The files journey waited for the initial-only label, which disappeared after the completed snapshot arrived. The hosted log records exactly this disabled-then-absent progression.
- The legacy default-off and acceptance-mode journeys remained in the CONTROL module after rejecting the revoked host. Their rebind helper tried to open NOVEL's feature navigation without returning to NOVEL. The existing CONTROL route correctly has no FeatureLauncher. The same prerequisite also applies to the files journey's later reload/rebind path.

The shared discovery owner, host epoch, authorization handling, CONTROL shell and component labels are unchanged. The existing API/session-owner tests remain passing.

## Narrow correction

- Both additive host-entry helpers explicitly select the existing `小说` module tab before opening its feature navigation.
- The files journey asserts that the retained `COMPLETED` state is visible, then asserts/enacts the exact existing rescan action.
- No synthetic state reset, direct API bypass, alternate credential path, timeout increase, skip, retry, broad locator or product UI change was introduced.

`m3b-hosted-journey-preservation.json` verifies that reversing only these authorized prerequisite/label additions and comments produces the original two files byte-for-byte. Original M3-A consent, browser configuration and workflows are unchanged. Existing authentication, revoked-host purge, file visibility, HTTP payload, scan-count, metadata-only, no-inference and isolation assertions remain intact.

## Evidence and limits

- `m3b-hosted-journey-contracts-assertion-red.json/.log`: genuine pre-correction regression baseline, 3 failed and 1 passed. The new tests mount the real discovery UI and shared CONTROL/NOVEL routing, then check the actual browser helper/locator source against those states.
- `m3b-hosted-journey-contracts-final.json/.log`: 74 tests passed across eight suites, including all four new regressions and existing consent/owner/navigation coverage. Source hashes remained stable during this check.
- `m3b-hosted-journey-typecheck-final.json/.log`: TypeScript passed. Concurrent work elsewhere in the checkout changed source hashes during this invocation; integration must repeat its final aggregate check after all source edits finish.
- `m3b-hosted-journey-lint.json/.log`: token guard passed, 50 guarded files.
- `m3b-hosted-journey-collection-isolated.json/.log` and `m3b-fixture-collection/`: collection remains 14 tests across 6 files, with original titles/order. Collection does not execute Chromium.
- `git diff --check` passed.

Two early unit-harness imports failed before collection (`...contracts-red` and `...contracts-red-baseline`), and the first typecheck found unsupported Testing Library role options. These setup failures are retained separately; they are not the behavioral RED evidence. Correcting the new test harness did not alter its checks or the hosted journey's assertions.

The first collection invocation used the configuration's default reporter directory and rewrote historical `cloud-v2-independent-browser/junit.xml` and `results.json`. Both historical files were restored byte-for-byte from HEAD immediately; the full inventory was retained in the collection log, and a separate collection invocation wrote fresh reporter outputs only to `m3b-fixture-collection/` via `CI_RECEIPTS`.

No local browser launch or denied artifact retrieval was attempted. Mounted/source-contract tests and collection are not hosted-browser success. The corrected browser journeys still require hosted Chromium execution on the integrated commit before M3-B browser acceptance can be reported as passing.
