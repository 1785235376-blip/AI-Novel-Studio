# Explicit asset handoff into weighted IMAGE references

Base: `d91e5c85eff52ca36e312eda3d1df3d9d971f529`.
Branch: `work/dot-reference-handoff-20261016`.

## Scope and ownership

The existing Asset → IMAGE handoff now accepts a user-selected `m5.image.reference` operation. It remains a metadata-only, two-step review and accept flow. The original media controller owns the draft, the existing `exactHandoffAsset` validates the pin, and the original image-reference insertion policy is shared with the manual picker. No API, backend, dependency, schema, store, execution engine, or protected shell changes.

The reference path requires an explicitly selected matching IMAGE provider with image capabilities, enforces the provider reference limit and hard cap of five, and rejects duplicates, source/base/mask conflicts, invalid kinds, deleted/manual-mask assets, and mismatched current-list pins. Both preview and acceptance reread metadata. Acceptance appends the exact pin with weight `1`, preserving existing order, pins, weights, purposes, notes, prompt, parameters, license note, provider, and route. The original `edit` invalidates the prior execution preview; cloud consent is cleared. It never automatically selects an operation/provider, reads execution preview, saves, creates, executes, or downloads.

Existing request identity, revision, provider reload, permissions, current-owner, busy/UNKNOWN, cancellation, unmount, and ABA fences remain. The manual picker retains its existing replacement/removal semantics; stricter admission applies only to handoff.

## Verification

- Focused stable run: 10 files, 162 tests passed, including 50 new additive tests.
- Original selected asset, image runtime, image reference, and route suites ran unchanged.
- `focused-tests-initial.log` retains the one initial additive-test failure: an incorrect expectation that the retained hook snapshot clears after unmount.
- `focused-tests-repeated-initial.log` retains a repeated run of the old assertion after a correction command used the wrong working-directory-relative path. The source correction was loaded only on the final stable run.
- Corrected additive coverage proves unchanged draft, no post-cleanup dirty callback, no execution, and no further metadata reads when the retained callback is invoked after unmount. It does not claim an unmounted hook renders again.
- Final commands use one Vitest worker, no cache, and unchanged default timeouts. No original tests, guards, or manifests were changed.
- Forced typecheck, production build, and token audit results are in their individual logs.

## Limits

Actual image quality, provider inference, GPU, cloud execution, browser/visual acceptance, and live end-to-end workflow acceptance are **NOT_RUN**. No browser retry or Python execution was attempted. Canonical IMAGE reference and DS-v1.0 were reviewed; the sole visible change is explanatory copy in the existing panel, using existing primitives without layout/token changes.

No push, main merge, release, paid APIs/compute, dependency installation, or user-machine work. Source review accepted; local commit and inventory binding are recorded separately.

Final checks: forced `tsc -b --force` PASS; `vite build` PASS (existing large-chunk warning retained); UI token guard PASS (52 files). Git blob comparison checked 2,180 tracked test/spec/guard/manifest/package/lock paths against HEAD, with zero changed. The first attempt to compare whole file contents hit Node's default subprocess buffer on a large historical evidence file; the completed check compares Git blob hashes instead. No test failures or skipped live acceptance are concealed by these build checks.

Independent verification passed 110 overlapping cases across six suites with unchanged frontend source/config snapshots. Its raw receipt/log and before/after maps are preserved in `independent/`; these are not additional unique tests. Raw evidence retains its original formatting, including any EOF whitespace warnings.

Staged full diff-check: exit 2 from preserved raw log whitespace/EOF only; the same check excluding raw logs passes. Raw evidence was not normalized.

Inventory binding staging note: `git diff --cached --check` reported exit 2 for one trailing space in the preserved `inventory/confirmation-launcher.mjs` invocation artifact. Its reviewed bytes/hash were retained. This artifact warning does not change the successful collection/closure proof or product-source checks.
