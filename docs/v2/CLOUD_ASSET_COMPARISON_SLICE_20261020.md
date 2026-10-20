# Asset comparison media slice — cloud continuation, 2026-10-20

## Scope and baseline

Base product: `9ce5e243f925f6fb5141046758045c59b1dca46f`.
Branch: `work/cloud-asset-compare-20261020`.

Source inspection confirmed that AssetBrowserPanel read the right candidate metadata, but AssetComparePanel rendered media only for LEFT. This closes the missing two-sided media consumer in IMAGE-02 / IMAGE-09 / IMAGE-13; it does **not** claim those broad matrix rows are fully accepted.

## Delivered behavior

- Both original Asset snapshots can be previewed separately by explicit user action, with shared image zoom and mutually exclusive, non-autoplay audio/video playback.
- Candidate id/version/digest and project/branch checks reject substitution of a current asset for an old disclosed pin.
- Preview reads use the injected read boundary and the existing owner GET endpoints. The selected snapshot is checked before/after bytes; size, MIME and SHA-256 must match. The existing canvas-compatible 32 MiB and safe-format policy is retained.
- Changing selection, version, authority, reader, active state or scope retires old results, stops playback, and revokes object URLs. ABA and late replies cannot revive old media. Decoder failures clear the preview and allow explicit retry.
- A narrow host-only Asset transport memo preserves comparisons during unrelated host rerenders, while retaining session/client changes and explicit localHostToken rotation. Task transport behavior is unchanged.
- Original Grid thumbnails retain their existing behavior. “Explicit reads” here describes comparison media, not a new thumbnail policy.
- No owner writes, automatic adoption, binding updates, models, paid APIs or new backend were introduced. DSH batch/Audio files and other cloud slices are untouched.

## Acceptance boundary

Targeted helper/component and actual-mounted-host regressions use deterministic owner HTTP fixtures and mocked browser media APIs. These prove client state/transport handling; they are not real browser codec, Host, PostgreSQL or full end-to-end acceptance.

Real Chromium/desktop geometry was not run for this slice: the shared cloud environment had already failed with `process_singleton_posix socket() failed: Operation not permitted`, followed by a supported escalation failing to create a restricted session mount. This slice did not retry that blocked launch. Existing two-column classes and shared UI primitives are reused; screenshots and the 1366/1440/1920 browser checks remain pending.

Targeted verification:

- `vitest run src/assetbrowser/AssetBrowserPanel.test.tsx src/assetbrowser/AssetBrowserPanel.comparison.test.tsx src/assetbrowser/AssetComparePanel.test.tsx src/assetbrowser/assetComparisonPreview.test.ts --maxWorkers=1 --minWorkers=1`: **60 passed**.
- Independent actual-mounted-host regression, `vitest run src/assetbrowser/AssetBrowserHost.comparison.test.tsx --maxWorkers=1 --minWorkers=1`: **7 passed**.
- `npm run build` (`tsc -b && vite build`): **PASS** after final review fixes; Vite 8.86 seconds, existing chunk-size warning only.
- `node scripts/check_ui_design_tokens.mjs`: **PASS** (52 files); `git diff --check`: **PASS**.
- Independent review found two P2 issues (decoder failure cleanup and unstable host transport), both fixed and verified in the actual-mounted-host tests; no remaining scoped P1/P2 findings.

Final TypeScript/production-build output, exact Git receipts and hashes are recorded in the accompanying cloud evidence receipt. No main merge, release or push was performed.
