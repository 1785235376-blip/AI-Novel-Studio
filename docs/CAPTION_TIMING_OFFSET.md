# B04 bounded caption timing-offset preview

Baseline: `b5f52c823b4df58ffe69ec309bfc2fc0e4a114fe`.
Branch: `work/dot-caption-offset-20261017`.
Status: implemented; primary targeted checks and independent final source/contract review passed. This is not full product or release acceptance.

## Original owners and local behavior

The existing `SubtitleTimelinePanel` owns the draft. `voiceSubtitleClient.saveCues`, the original caption PUT, `SubtitleTimelineService`, source pins, CAS, embedded history and exporters remain unchanged. There is no offset endpoint, new persistence store, parser change or new save owner.

A new pure `captionTimingOffset.ts` helper accepts all cues or explicitly selected current cue IDs and a signed safe-integer tick string. It returns exact before/after tick pairs and copied cues. It checks the original 2,000-cue bound, safe integers, bounded cue fields, original ordering, the maximum earlier end for overlap, and exact rational measured-media duration using BigInt cross products. The entire candidate fails atomically if invalid, including conflicts with unselected neighbors. It never clamps, sorts, synthesizes overlap explanations, changes IDs/text/speakers, or rewrites the timebase. This is local preflight; original save authority and live source validation still apply.

The panel offers an explicit read-only preview followed by an explicit local apply. Zero offset provides no apply action and preserves local input. Apply and one-step undo preserve historical restoration provenance and existing split inputs. Undo restores the exact prior local cues, including unsaved edits, rather than restoring persisted cues. Subsequent cue edits, split edits, replacement, refresh, source/head change or save admission retire undo. Persistence remains a separate original save action.

Owner, control-revision, draft and catalog-admission epochs synchronously retire stale handlers and previews, including ABA changes. A live input-value check and composition flag reject apply while an IME value is uncommitted. Revision invalidation both updates its ref immediately and guarantees a render so fresh handlers recover after unchanged input events. Selected IDs missing after deletion/replacement are removed only on the user's explicit range/checkbox selection action; cue content is never silently dropped.

## Verification chronology and preserved failures

1. Static review found JavaScript `$` could accept a final newline. An exact trim-equality guard was added before the integer pattern. This was caught before test execution.
2. A selected-row deletion usability defect was corrected before the first UI run: stale selected IDs otherwise could not be cleared using the remaining visible checkboxes. Only explicit range/checkbox actions filter IDs against current rows; an additive test covers recovery.
3. Original natural startup and actual runner-child origin r1 passed before that selection correction. UI r1 launched just before the renewed-origin instruction arrived. Those original receipts are preserved; r1 is not represented as the final same-source provenance bracket.
4. UI r1 completed with **221 passed, 2 failed**. Both failures and their complete raw log remain retained:
   - New test harness defect: an empty array in `it.each` became zero callback arguments, invoking the helper wrapper's default all-cue selection. The new table was nested so the empty selection is actually passed. No existing test was edited.
   - Actual runtime defect: unchanged composition completion could increment the revision ref while every state setter was a same-value no-op. Without a render, fresh handlers remained stale. `invalidate()` now advances its synchronous ref first and sets a revision render state. A new regression checks unchanged IME completion and recovery after repeated invalid preview.
5. Final source was refrozen. Fresh natural startup r2 and actual unchanged-runner child r2 proofs passed before all final gates. Final UI r2 passed all **224 tests in 7 files**, including both new files and unchanged history, import, voice and transfer regressions.
6. Backend r1 passed **213 cases**, with **200 PostgreSQL-only cases explicitly deselected** using `-m 'not postgres_backend_only'`. Neutral tests remain included. The normal conftest and explicit runner profile/basetemp were used. New tests exercise original PUT, fresh File store/service reopen, exact exported/read-back SRT and VTT, both mounted aliases and rational rates. They explicitly do not claim that Python executed the TypeScript helper or that a browser completed this journey.
7. Forced TypeScript (`tsc -b --force`), production Vite build and original token guard passed. Token guard inspected **52 files**.

The only Python interpreter was the established clean `studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python`. The original `scripts/run_v2_checks.py` was not edited. Natural proof used unset outer PYTHONPATH and ordinary startup, without replacing sys.path. The actual runner child independently used its original runner-provided root PYTHONPATH. Both proofs checked actual product/dependency specs and startup finders without importing product modules or pytest. All final checks used isolated original runner profiles and normal test behavior; no installs occurred.

All **2,613 source entries** were identical across final origin/UI/backend/TypeScript/build/token checks. Each final receipt records `sources_changed_during_check: false`. The final before/after full-source manifests match byte-for-byte. **1,229 baseline protected test/runner paths** were checked unchanged. New tests are additive.

## Warnings and limits

Backend emitted existing Starlette/httpx deprecation and `GlossaryDocument.schema` shadowing warnings. Build emitted the existing warning about chunks larger than 500 kB. These were not suppressed or repaired in this slice.

Browser geometry/visual QA, real-browser end-to-end acceptance, PostgreSQL, real model/provider calls, Windows/package checks and target subtitle application rendering remain **NOT_RUN**. This is bounded deterministic contract verification, not full product acceptance. Original save still has its existing uncertain-outcome limitations; this feature adds no durable write reconciliation or automatic retry. No remote write, main update, merge, release or paid resource was used.

## Final source identity

| File | SHA-256 |
| --- | --- |
| `frontend/src/experimental/SubtitleTimelinePanel.tsx` | `9588ff20a637ab864c222e5069260ce02b0adf010ef363fa23827baa8c7657b9` |
| `frontend/src/experimental/captionTimingOffset.ts` | `0e318e8b04ebc27b55f6993320add8fefe598acd25501674aac9d5cf82bda647` |
| `frontend/src/experimental/captionTimingOffset.test.ts` | `c7e8e7c019dd7abbd12332dcbfc4307d26767330d1ddeb43612bcffdf19cb1d7` |
| `frontend/src/experimental/SubtitleTimelinePanel.offset.test.tsx` | `bb76c24351be51598e32189b4d40baccdd45a20dad7cb0d3c69cdc5fc9584493` |
| `tests/test_caption_timing_offset_additive.py` | `88dec88edef22790fb92b1e1ac82d4b9355411a25680f552b4217fb39247fb41` |

## Evidence index

All paths below are under `docs/delivery/v2-development/`. Files were retained unchanged; origin/protected/full-source files were copied byte-for-byte from their execution evidence. The JSON receipts include exact commands, isolated profiles, timestamps, source maps and log hashes. Earlier r1 evidence is historical, not substituted for final r2 evidence.

| Evidence | SHA-256 |
| --- | --- |
| `caption-offset-origin-r1.json` | `50206f078c66075bd8565459c3ed584d703b4a5315746c0afad165a56d7ce8a9` |
| `caption-offset-origin-r1.log` | `90ecd95eca407dd8f8abe8ddc7af9513019b34217a1a3c385a290a9b0aee0da0` |
| `caption-offset-origin-r2.json` | `ea98693afe513dae290cdc563362511c7461914012a4c5ed87084199477e54b0` |
| `caption-offset-origin-r2.log` | `992a240f65854a808432b1045e7a2de0aa37e0003dc654621c4445cb596c77eb` |
| `caption-offset-ui-r1.json` | `37a248dc7d254a074cf31f250e5dded756d47d8cfc2169e45e421af7ccee2529` |
| `caption-offset-ui-r1.log` | `080111f7f9e4ec9dab052ce1a27ca792961a8cee6d48a6102f56b242a70b6e6d` |
| `caption-offset-ui-r2.json` | `1252a866177be637a65117c8c89f44db8c5b4d55343385ea434ddae8f09cbede` |
| `caption-offset-ui-r2.log` | `2e5e0341b370336f9bc04d0016f11486d9c9f886fc1295cbd752d7db514132a2` |
| `caption-offset-backend-r1.json` | `d79ff7ec4dcba0fbdefa396238895435da4c2414939e0a12f5fe272218f437b8` |
| `caption-offset-backend-r1.log` | `d5ea01f00e7ccc871b4c479ed7ae480f74649cbd99e0c54588143236edb03cc7` |
| `caption-offset-tsc-r1.json` | `e2c7edf0afc7a05964ea7228e9ea0a0eef5d2d17d4d5abde87c34fd4020e76dd` |
| `caption-offset-tsc-r1.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `caption-offset-build-r1.json` | `b1fcdbc16f1fe222893c3da346f8f897348d50d4e379146262ffc9ba3a8cee88` |
| `caption-offset-build-r1.log` | `4d454190b891b733551186dc36d986a9a1deecb3d8f021902b3e022d3f2657ff` |
| `caption-offset-tokens-r1.json` | `550239c3229d721d3605897a068dbc3650f61de76697bbabaac1062fbaa7a0d9` |
| `caption-offset-tokens-r1.log` | `720c976bb800c2f989255bfef0431c263b72c50e0b2c052599e3b39e1cb1de50` |
| `caption-offset-origin/origin-probe.py` | `58dcd0b1d83968a6a28c24cc6150ebec82382810d95259919ade4eb1bdb8cc7d` |
| `caption-offset-origin/normal-startup.json` | `b449c47ce272a65a73e3ad74de969d96d33869deb28c4a91f842087a6da20c5a` |
| `caption-offset-origin/normal-startup.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `caption-offset-origin/normal-startup-r2.json` | `cde2f02e2818c959fdb762cd535a9021eac5d38091b5abcd81852380d03fe591` |
| `caption-offset-origin/normal-startup-r2.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `caption-offset-origin/full-source-r2-before.sha256` | `0b3455046f848c01fcf906bcdf0230c44eafe873896c3663f60c8a87e7479b09` |
| `caption-offset-origin/full-source-r2-after.sha256` | `0b3455046f848c01fcf906bcdf0230c44eafe873896c3663f60c8a87e7479b09` |
| `caption-offset-origin/protected-before.sha256` | `5177cecf51b32f399ffb83f21302a41427108a94d417c6269e60ebfbfcc2dcdf` |
| `caption-offset-origin/protected-after-check.log` | `cb967ce6e7f8585dc2833d69e317f07c49ce5e53b40bc695f9d1e11b273b88dc` |
| `caption-offset-origin/primary-report.json` | `be03d42db5d336b8d2a46c49aabaf6dc0a781ccf2406b70a2d43312b797fb7b7` |

## Independent final verification

Independent review passed at `2026-10-17T10:52:04.968851+00:00` against the exact final source identities above. It repeated **224 UI passes** and **213 backend passes with 200 PostgreSQL cases deselected**, with the same two existing backend warnings. These repeated checks overlap the primary counts and are not added to them.

The reviewer independently verified natural startup and actual original-runner child origins, all **2,613 source entries** across primary/final/independent receipts, all **1,229 protected paths**, every original log hash and preservation of the earlier **221-pass/2-fail** UI evidence. Forced TypeScript/build/token checks were not repeated by the reviewer; their primary receipts were validated against the identical full source maps and log hashes. Browser, PostgreSQL, provider, Windows and target application limits above remain unchanged.

The independent audit and natural proof below were copied byte-for-byte into this evidence directory and compared to their originals. No raw log or existing receipt was rewritten.

| Independent evidence under `docs/delivery/v2-development/` | SHA-256 |
| --- | --- |
| `caption-offset-independent/audit.json` | `8400e7a3ddeb6cd4c6b53d77ddd4dcaae4504bd9fccb5234273baebd325244bf` |
| `caption-offset-independent/normal-startup.json` | `5f7afd1917d78f38eac7ed8443f47b6574eb7137793b2943d7bb74deb1ec0a5d` |
| `caption-offset-independent/normal-startup.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `caption-offset-independent/protected-after-check.log` | `cb967ce6e7f8585dc2833d69e317f07c49ce5e53b40bc695f9d1e11b273b88dc` |
| `caption-offset-independent-backend.json` | `6ed202269e9497e128da299462627dc654cd73188267b6a8d7fe9c6b5c460218` |
| `caption-offset-independent-origin.json` | `060a5f92b9bc44e912aaa7a785cac750c469d8897f902be4305a484b605390cf` |
| `caption-offset-independent-ui.json` | `939b94957d628249ce7d2cdb230ad417a74aa6965caa11f2e8946765d1c5b613` |
| `caption-offset-independent-backend.log` | `5f1bad1ea95d8f657294813f11c530a34f07ce82da5cc077529d74f4840fffd8` |
| `caption-offset-independent-origin.log` | `2f9ed5b937aa7ecee300e380b63373c3b784745c1c1ecc3605123dfd1e78eb13` |
| `caption-offset-independent-ui.log` | `ddddd839b61c7f0656e76126c7a2d2bc64aa346f733c4127f2f4cc1ad121d820` |
