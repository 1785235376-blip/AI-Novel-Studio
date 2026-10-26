# A+B+C source integration decisions

The user explicitly authorized a fresh isolated local GitHub clone with synthetic data after the initial cloud-only M0 checkpoint. All subsequent work is confined to `D:\PoemSeed-Unified-20261027-94f1c72e`; the earlier M0 execution blocker is historical, not the current environment decision.

Inputs remain A `457ea4a5a45ab13f351980665e053c5c77d15c82`, B `f6473e307e9d0501a41dc46dd991645a437103d7`, C `fe4f55412299fadfada0354725b3ca46e418c46a`. B was cherry-picked with `-x` as `f02ff272ecbef9bdc007c4b28cca2d47b08f8ecc`; its original asset-protection and TaskCenter ancestors were not replayed. The A+B real-TCP test extension is `7387dd1f6a45e2ee755b0268885617c9b7ff7085`, tree `0ea839400bdd2ec7e5200324dcab5e97e36a0ed9`.

C was integrated by a normal three-way merge, with common ancestor `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`. C changes no `app/**`, root `scripts/**`, `.codex/**`, frontend package manifest or Vite config relative to that ancestor. All A+B backend progress is retained automatically. Endpoint A-to-C deletions are not instructions to remove backend files.

| Conflicted file / symbols | Resolution and retained owner |
| --- | --- |
| `frontend/src/api.ts`: `downloadCall`, `scopedChapters` | Retain C's sanitized shared error parser and strict chapter-list response adaptation. Preserve A's other transport/context and protected endpoints. |
| `frontend/src/creative/studioProductionClient.ts`: imports and client methods | Retain C's translation import and its paging/filter contracts. Preserve A's protected node observation, discard, target-view and recovery methods; retain the strict `canvas_image_node` parser. |
| `frontend/src/rebuild/canvas/DualCanvas.tsx`: hint | Combine C's layout explanation with A's explicit browser-local draft / unsaved-server boundary and separate image confirmation / unsupported VIDEO statements. |
| `frontend/src/rebuild/canvas/RebuildCanvas.tsx`: props, session, selection, persistence and geometry | Retain C's viewport/selection restoration, scoped storage key, session persistence, palette, reveal-once, positive width geometry and VIDEO unsupported states. Preserve the automatically combined A `active`, selection epoch, prompt/position revisions, formal source-current checks and owner-key remount. |
| `frontend/src/rebuild/image/CanvasImageQueue.test.tsx`: two error assertions | Retain all scenarios; accept C's shared sanitized unavailable message in the two existing failure cases. No dispatch/permission expectation is weakened. |
| `frontend/src/rebuild/image/ImageRebuild.tsx`: imports, task bindings and view selection | Retain C's DualStack professional layout and its own drawer; retain the ordinary single-canvas task owner and scope guards. Remove duplicate imports and the semantically identical second task-binding declaration introduced outside conflict markers. |
| `frontend/src/taskcenter/StudioProductionTasks.tsx`: View/load/filter and node actions | Retain C's explicit paging/filter UI. Preserve A's selection retirement, protected observation POST callbacks, discard eligibility and consent boundaries. Remove the duplicate C declarations of `hasCanvasTarget` and `discardEligible`; retain A's safety comments. |

`App.tsx` merged automatically and remains subject to route and browser regression verification. No new UI shell, theme system, queue, authorization owner or model provider was introduced. Repository UI skill, design system, protected surfaces and canonical IMAGE reference were read before conflict editing.

The initial merged build exposed the duplicated `ImageRebuild` bindings (TS2451); after deduplication, `pnpm 10.6.5 build` on Node 22.14.0 exited 0 in 38.28 seconds. Raw failure and corrected logs are retained outside the source checkout for final evidence publication. This build is not whole-suite or browser acceptance. An initial wrapper invocation from the wrong working directory also failed before compilation and remains in development evidence.

The independent M1 verification checkout is frozen at `7387dd1f6a45e2ee755b0268885617c9b7ff7085`; it is not edited while its backend combination groups run. The fixed C frontend baseline runs in a separate clean checkout at its original SHA. Their results will be recorded independently of final unified-source acceptance.
