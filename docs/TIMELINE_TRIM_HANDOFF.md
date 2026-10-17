# Bounded Timeline inspector trim/ripple handoff

Source base: `ca067c42c95d35fab5bce612cf2095555e990cba`.
Status: implementation, primary verification, and scoped independent verification complete. This is a bounded wiring repair, not full feature or release acceptance.

## Original owners and useful behavior

The mounted `ClipInspectorPanel` already offered trim inputs and an explicit ripple choice. `timelineOps.editCommand('trim', ...)` already emitted the original `clip.trim` descriptor, but `StudioTimelineEditor` required a position before dispatch and only routed split/duplicate/move. The new trim branch runs before position-only validation and hands source in/out values to `useStudioTimelineEditor.trimClip`.

The original manual in/out fields remain available and unchanged. No duplicate trim editor, second editing engine, new backend owner, route, store, schema, or migration was added. The existing source-operation `timelineEdit` validators were not repurposed. The new operation validates a detached local draft through `checkedTimelineDraft` and commits exactly once through the existing `change()` history owner. Rejected or unchanged trim returns false without a history entry. Successful trim is one local undo/redo step; only the existing explicit **保存时间线** action persists it using original `timelineSave` CAS. Original GET and explicit adoption reopen the saved result. Trim does not automatically save, render, export, create an asset, or rebind source pins.

## Exact trim and ripple semantics

The local computation matches the existing `app/services/studio_timeline_edit.py` `clip.trim` and `shift` rules:

1. Keep the selected clip's timeline start and source snapshot unchanged; update its source `in_ms` and `out_ms`.
2. Rendered duration is `(out_ms - in_ms) * speed_den / speed_num`, using the existing rational speed and integer-millisecond contract.
3. With ripple explicitly selected, shift only other clips on the same track whose starts are at or after the selected clip's **old** end. Shift by new rendered duration minus old rendered duration.
4. Earlier/overlapping starts, other tracks, captions, source pins, assets, and total canvas duration remain unchanged. Extension moves qualifying clips later; shortening moves them earlier. Ripple does not automatically resize the canvas or repair transitions.

Existing validation still enforces positive integer durations, image zero-in/1:1-speed rules, same-track video overlap, fades, exact transition windows, locks, and total timeline bounds. A cross-dissolve neighbor starting before the old end is deliberately not shifted; a trim that breaks the existing exact transition window is rejected atomically.

The UI explains that ripple affects this track only. It also explicitly states: **Save does not prove actual source duration.** Original Save validates timeline structure and source identity/content; the existing renderer remains responsible for reading media and validating measured source bounds. An additive File test deliberately saves a structurally valid 9,000 ms source span against a 6,000 ms WAV, demonstrating this limitation without claiming rendering succeeds.

## Lifecycle and preserved protections

Trim callbacks bind to the semantic controller generation and client owner rather than an unconditional render counter. The mounted route also checks current selection and current context. Inspector trim points and ripple consent reset when the selected target/source state changes; unrelated rerenders preserve in-progress input. The router derives the first selected target in timeline order, matching the inspector.

Original authority, pending-operation, lock, conflict, UNKNOWN-result, and stale-context gates remain in force. Original Save/reconciliation ownership is unchanged. No durable crash-proof recovery is introduced. Successful local trim never supplies render/export consent, bypasses source validation, or turns a descriptor-generation message into proof of persistence.

## Primary verification

All commands used the unchanged `scripts/run_v2_checks.py`, the previously verified clean interpreter, owned run-scoped profiles, and retained raw receipts/logs. Normal interpreter startup and the actual original-runner child origin were independently recorded without product/pytest imports or `sys.path` replacement. Outer injection variables were sanitized; the original runner supplied the child current-root `PYTHONPATH`.

- File backend: **17 passed** (16 additive trim cases and one unchanged original Timeline history case), **one PostgreSQL case deselected**, one existing Starlette/httpx deprecation warning. The new file explicitly targets File; no neutral case was omitted by a backend marker filter. Tests use synthetic PCM media, real original File owners, CAS, original history, and fresh store/service reopen. No HTTP/browser/render evidence is claimed.
- UI: **198 passed across eight suites**, including **29 additive trim tests**. Coverage includes mounted original inspector routing, rational positive/negative deltas, exact old-end threshold, unchanged other tracks/captions/pins, no-ripple behavior, one-step history, original Save/GET reopen, invalid ranges/image/fade/transition/overlap/locks/overflow, pending Save, conflict/UNKNOWN, and retained callback invalidation. These are jsdom/mock-transport checks, separate from File persistence evidence.
- Forced `tsc -b --force`: passed.
- Production Vite build: passed; existing greater-than-500-kB chunk advisory retained in the raw log.
- Original UI token guard: passed, 52 files.
- All primary runner receipts record exit code 0 and `sources_changed_during_check: false`; 2,541 relevant source entries were frozen. Original tests and runner were not edited.

Independent verification passed **29 additive UI cases** and **16 additive File cases**; these overlap the primary totals and are not added. The [independent review](delivery/v2-development/timeline-trim-independent-review-r1.json) found no remaining blocker. It verified all eight runner receipts against the same 2,541-source manifest, exact before/after equality, and exact log hashes. Canonical baseline comparison found only the three expected frontend runtime changes; protected original baseline sources remained exact. The broader canonical manifest has 2,601 source entries and 16,101 nodes and is distinct from the runner's 2,541-entry source set. Semantic first-selected routing and the measured-duration disclaimer were resolved before source freeze.

## Boundaries and remote observation

Browser/geometry, native input, target-platform, packaged-runtime, PostgreSQL, rendered-media quality, provider/model, and full E2E/feature/release acceptance remain NOT_RUN/open. No installation, provider call, GPU workload, browser/server, remote push, merge, tag, or release was performed by this slice. The plain-text explanation reuses existing UI surfaces and does not change shared design tokens or shell geometry.

Parent read-only GitHub observation at **2026-10-17 04:44:14 UTC** recorded main `fed2404c8e30b44061b7139dced45b7f3301601c`, draft/open PR #47 `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3`, and draft/open PR #48 `58bbaad11360330d51f49fc2bb78a955a26469f0`. This is remote-head observation only, not hosted-CI or remote-write evidence.

## Byte-exact evidence index

Evidence is retained beneath `docs/delivery/v2-development/`. SHA-256 values bind the retained bytes; original logs, receipts, paths, and warnings were not rewritten.

| Evidence | SHA-256 |
| --- | --- |
| [Origin runner receipt](delivery/v2-development/timeline-trim-origin-r1.json) | `144ab27bdef14dbaff26f0fe5735d78304156201de456955460620c27e4567a4` |
| [Origin runner log](delivery/v2-development/timeline-trim-origin-r1.log) | `459efcf8ce4072003a3638dc09c8baac182936182d6abfb80285647e1e7aab04` |
| [File receipt](delivery/v2-development/timeline-trim-file-r1.json) | `c847e293db8dc90bac8675a2cb2e3c82ba2287041ec507d47603b2d36576bfc4` |
| [File log](delivery/v2-development/timeline-trim-file-r1.log) | `a58c303cc791e51b8a800220e5a2709b847d44dae2ea181edfedeb4334d9100e` |
| [UI receipt](delivery/v2-development/timeline-trim-ui-r1.json) | `45c251d92bc9cbd04c9b079606dae7396659ee5d7f9b07a49a3db00304ca0df6` |
| [UI log](delivery/v2-development/timeline-trim-ui-r1.log) | `264425295a476dfd33b5fc6794189f8b30039ac67f46e9b6d128cd1c9ecdf993` |
| [Forced TypeScript receipt](delivery/v2-development/timeline-trim-types-r1.json) | `f83687daa9cb4b2fbe0b6d288e156325fb4cbd66d08e0b9203d0d6dd1171ee5c` |
| [Forced TypeScript log](delivery/v2-development/timeline-trim-types-r1.log) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [Production build receipt](delivery/v2-development/timeline-trim-build-r1.json) | `0621d6c1dc3d6679ebefd111c5932e060d02ed21df07e296cc1257ea63fc8f4c` |
| [Production build log](delivery/v2-development/timeline-trim-build-r1.log) | `7e699a783fc7e799f08663e2280c2762b399adb500cef247d2cf2d96808ecc57` |
| [Token guard receipt](delivery/v2-development/timeline-trim-tokens-r1.json) | `c280069090bbba5134a1519e957e3c957ab4a6e7d935a87dbe1f2bb2091b5d0f` |
| [Token guard log](delivery/v2-development/timeline-trim-tokens-r1.log) | `720c976bb800c2f989255bfef0431c263b72c50e0b2c052599e3b39e1cb1de50` |
| [Origin probe](delivery/v2-development/timeline-trim-origin/origin-probe.py) | `e420c0a198cae77ea6af427b960c68ef8ca8a352d03980706d1bf2d06ee4554e` |
| [Normal startup receipt](delivery/v2-development/timeline-trim-origin/normal-startup.json) | `cd2dfd3ae1eb2e324d536bac98a366d9e6f88fe051ab484504ae626b80425634` |
| [Origin launch script](delivery/v2-development/timeline-trim-origin/run-proof.sh) | `ffd4d41128a6188a67963b95a83eaac684c06c5748de4670822cbcb3f8da5825` |
| [Origin launcher log](delivery/v2-development/timeline-trim-origin/launcher.log) | `40f1a0dcac4db61393a15cb48f46e502317577eb71c1a6ad38a8ef1875ed905b` |
| [File launcher log](delivery/v2-development/timeline-trim-origin/file-launcher.log) | `528e3ef0ea659d765d0c16519e6fa28f8da83aad196cbd1c0057c4d9844a0541` |
| [Normal startup stderr](delivery/v2-development/timeline-trim-origin/normal-startup.stderr.log) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [Parent remote-head receipt](delivery/v2-development/remote-heads-20261017T044414Z.json) | `514d57444cbb3764b52e49ffead4d3f35d9b30b1e663df9246c7fd8411113ef2` |
| [Independent UI receipt](delivery/v2-development/timeline-trim-independent-ui-r1.json) | `197eb2171a60790be716412a4ccdcf36feef6c7f5eee997af4203184a9ea503c` |
| [Independent UI log](delivery/v2-development/timeline-trim-independent-ui-r1.log) | `dbddb89d2d3fdde66fb93cca569f4b94a478e307f2f7af35f9e74d0b0594b8d7` |
| [Independent File receipt](delivery/v2-development/timeline-trim-independent-file-r1.json) | `3589d310abe7c99d6a81eaa1aee104b20cf0181ef4c183c1b1280c6f225933ef` |
| [Independent File log](delivery/v2-development/timeline-trim-independent-file-r1.log) | `8a85977768cef02df97a615f967e43cf12ce948902c8180e2b8ec6229b43c141` |
| [Independent final review](delivery/v2-development/timeline-trim-independent-review-r1.json) | `e734fb4a196f1083638bb4d1871aaee145c7f171afda5a18fb82eaf14a9e14b6` |
