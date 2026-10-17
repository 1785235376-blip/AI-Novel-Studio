# Explicit storyboard model context UI

The original Director proposal owner now accepts an additive authenticated capability advertisement for `STORYBOARD_SHOT_CONTEXT_V1`. Missing or unknown capability/endpoints, missing actual source, inconsistent provenance, changed version, altered authored snapshots or mappings fail closed. Legacy SCREENPLAY payloads and controls are unchanged.

The UI shows the exact adapter request and frozen source mapping. It checks complete authored scenes and sorted shots against the instruction, and the instruction against the actual request prompt. Preview is not execution. A separate one-call checkbox and button are required; consent retires on source/client/authority/selection changes. No automatic model call, retry, save, graph pin, paid route or cloud fallback is added.

Source-independent boards without chapter anchors are unsupported. There are at most 20 chapter IDs and 20000 instruction characters; output bytes/time remain bounded by the existing owner. These are not token-fit or live-model quality guarantees. Scene evidence is the supported evidence contract; shot-field citations are not fabricated. Rule seed copied/suggested field records remain historical source records after model refresh, not model output provenance.

All new UI tests mock providers/transports. Tests are in `DirectorModelControls.storyboard-model.additive.test.tsx`; original protected tests remain unchanged.

## Verification and corrected admission lifecycle (2026-10-17 UTC)

The final frontend validation passed **8 suites / 126 unique tests: 49 new additive cases and 77 unchanged existing cases**. The full `frontend/src` manifest is identical before and after every r3 check. The seven existing suites remain unchanged from HEAD `abff2ee7acc842e87abd53e0858110669922f9bc`.

- r1: 124 passed / 1 failed. The new complete-input test initially matched quoted text inside escaped JSON. Its assertion was corrected to parse the displayed JSON and compare the entire request, exact mapping, and complete storyboard title/scenes/sorted shots. Production source did not change between r1 and r2.
- r2: 124 passed / 1 failed. The corrected assertions passed, revealing a genuine dispatch liveness bug later in the same test. An enabled direct-owner dispatch button did not issue a request.
- Diagnostic: both ordinary DOM click and retained same-turn double click failed with **zero dispatch calls**. This was not treated as a fixture-only problem or fixed by relaxing assertions.
- Correction: admission uses a fresh per-render Symbol published by `useLayoutEffect` only on commit. Discarded/no-op React renders no longer invalidate live committed handlers. Consent/selection/operation/unmount still invalidate admission synchronously; existing source/client generation, authority, locking and parent dirty/uncertain-result owners remain intact.
- r3: all 126 tests passed, including normal DOM dispatch, same-turn duplicate suppression, pre-paint consent revocation, source/client ABA, authority retirement, unmount, graph-owned mutation leases and empty-note receipts.
- `tsc -b --force`: PASS, exit 0.
- Production `vite build`: PASS, exit 0; reports chunks larger than 500 kB. This warning is retained, not suppressed.
- Original `node scripts/check_ui_design_tokens.mjs`: PASS, 52 files. This guard checks the existing shared-UI token scope; it is not a universal styling or visual audit.

All runs used the existing dependency symlink. Vitest ran with one worker, no cache and default timeouts. No packages were installed; no protected tests or design-system guards were edited.

Exact raw r1, r2, diagnostic and r3 logs, stage snapshots and exit records are in [storyboard-model-ui-validation](storyboard-model-ui-validation/). `SHA256SUMS` records every copied evidence file. Historical failure logs are retained unchanged. The r1 source manifests are identical; recovery/r2 differ from r1 only in the new test correction. Final r3 manifests include the minimal admission fix and normal-click regression.

Runtime model quality remains **NOT_RUN**. These are mocked unit/integration checks plus static type, production build and token checks. Browser visual regression, geometry/browser acceptance, full E2E, live provider execution and PostgreSQL validation were not performed in this UI slice. No model-quality or end-to-end product acceptance is implied.
