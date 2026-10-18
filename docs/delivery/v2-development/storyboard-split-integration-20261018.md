# Storyboard canvas return and reviewed Timeline selection split

Product checkpoint: f0d7fa56024f4f47d6fe8a68fc5310c119769f68. Original V2 scope remains PARTIAL / NOT ACCEPTED.

## Director-derived Storyboard returns to current canvas

After the original Creative owner derives a separate Storyboard DRAFT, the handoff now offers an explicit action to add that exact draft to the current Graph. It independently rereads the Storyboard and current Director, checking ID/version/digest and source ancestry. The new document is still DRAFT: a reviewed Director does not approve its derived Storyboard or media.

The existing planning handoff and insertNode/history owner append one unconnected storyboard_plan. Existing graph edits and edges remain; original undo/redo and explicit CAS Save/reopen preserve the exact scalar pin. There is no automatic graph replacement, connection, schema upgrade, save, approval, generation or second workflow engine. Existing Director receipt validation is retained.

Verification captures source/canvas lifetime before asynchronous reads. Source, canvas, selection or authority changes permanently retire the intent, including ABA. It is consumed once, and a fresh derivation clears an older verified board immediately. UNKNOWN creation never unlocks placement or automatic retries. Wrong ancestry/version/digest, unsupported schema, capacity and permission failures fail closed.

## Exact selected-clip split at the playhead

The Timeline inspector lists each explicitly selected clip as affected or skipped at the exact playhead. Only clips with the point strictly inside their rendered range split; boundaries and outside clips are visibly skipped. A crossing locked clip, invalid/fractional source conversion, capacity violation, fade or final transition geometry rejects the whole operation. The action never snaps the point or silently expands selection.

A detached validated result reaches one original change/history operation, so undo/redo is atomic. Original clip IDs remain on left halves; each right half receives one new ID after preflight. Rational trim/speed arithmetic and still-image rules match the original Python owner. Left outgoing transition is removed, right retains it; only the original inner fades are cleared. Source pins, speed, gain, crop/color, other tracks, captions and total duration are preserved. The old single-clip branch now narrowly reuses the same validator, fixing its source-confirmed outgoing-transition mismatch; no executed pre-fix failure is implied.

Selection/playhead/draft and parent authority/lifecycle generations fence review. Transfer Locate updates those same generations. Stale callbacks fail before ID allocation, and repeated actions cannot allocate or apply twice. The split-only playhead fence preserves unrelated move/copy inputs. Existing explicit Save remains the persistence path.

## Verification and limits

- Root combined frontend: 213 tests in 15 suites, full TypeScript/Vite production build and token guard passed on unchanged source. All 3184 recorded source paths match integration.
- Storyboard branch: 70 targeted tests plus types/token; selected-split branch: 143 targeted tests plus types/token and 12 pure differential checks. Counts overlap the root suite and are not additive.
- Existing chunk-size warnings remain. No full product or large-scene performance acceptance is inferred from the build.

The 12 differential checks execute the actual TypeScript compiler in Node and compare its descriptors and full result with original Python apply_timeline_edits across video/audio/image, rational speed, fades/transitions and failures. They are pure original-owner checks, not File repository persistence or media decoding. Mounted save/reopen tests use synthetic client contracts. Independent review passed 44 Storyboard tests; Timeline review inspected final differential evidence and corrected transfer/freshness findings.

No backend runtime, schema, catalog or packaging changed. All 1,527 prior PG non-frontend hashes still match; the previous PUBLIC receipt differs only in the older test-only collection teardown. Exact differential compiler inputs match integration. Existing backend/wheel evidence is reused instead of rerunning unchanged owners. Full same-candidate E2E, browser, Windows, model quality, rendering and independent target-app acceptance remain open. This closes a concrete workflow bridge and manual editing operation, not full intelligent Director completion.

Raw failures are preserved: two genuine Inspector input-reset regressions were corrected, one scalar-to-selected-batch expectation intentionally changed, an unrelated differential-test bootstrap import was avoided with isolated pure-function loading, and one source-changing typecheck was superseded by stable verification. No test was weakened to hide a product failure.

Previous source 9752db6a is independently archived as 8c789eaee1f63f86caabe92daa1b853178d0700b, exact parent fc629c8e: 14 files / 4,548,104 bytes. Archives are prerequisite-bound bundles, not main/PR source updates or releases.
