# Grok unified-workspace independent verification

Fixed GitHub target: `work/hermia-unified-workspace-20261023` at `51ff02b2622e6f992f7729702bf4bbb79b1a09a6`, tree `f4cf078bffad5675a305fd74781cae9abde22dbd`. Its parent is `0bf7bdeb95e6cb4bd1f9e9c2f825926bacfe2eaf`; the final commit adds 14 review-document lines, with no product or test changes. The review author field and external Vera report were treated as source evidence, not our independent execution.

Separate detached worktrees were used for test execution and type/build control. No target source, tests, manifest or lock was edited, installed or merged. The existing dependency environment matched all three committed manifest/lock files byte-for-byte. Actual runtime: Node **24.19.0**, pnpm **10.6.5**, TypeScript **5.9.3**, Vitest **2.1.9**, Vite **6.4.3**. Node 24 satisfies the target's `>=22.14.0 <25` requirement. The original Node 22 environment was unavailable; it was not installed or simulated.

## Actual independent results

| Check | Actual result and interpretation |
| --- | --- |
| Window/layout/canvas/task-center unit selection | **503 passed, 1 failed**, 63 files / 504 tests, exit 1. Real Vitest discovery confirms the file/test counts. The filters also match two root workspace tests case-insensitively; counts were taken from runtime JSON. This is unit/jsdom acceptance, not browser geometry. |
| One necessary isolated failure check | The affected `TaskCenter.additive.test.tsx` file then passed **4/4**. This does not erase the first failure, prove a cause or establish a known flaky baseline. |
| Original type command | `npx tsc --noEmit -p .`: **FAIL**, exit 2, six diagnostics. |
| Standard build | `corepack pnpm build` (`tsc -b && vite build`): **FAIL**, exit 1 at TypeScript. Vite did not run; no Vite-only bypass was used. |
| Same-environment type baseline | Common base `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`, tree `4193b3c22c49647dfc6e52241b5ff459f0064654`, reproduces the same six diagnostics. Only the unchanged App statement moved seven lines. No new type diagnostic was found; the existing build debt remains a delivery limitation. |
| Full Node 24 diagnostic | **11,106 passed, 313 failed, 6 skipped** (JSON `pending`), 910 files / 11,425 tests, exit 1; one run completed normally in 712.293 seconds within the 15-minute budget. No full-suite Node 24 common-base control was run, so the 313 failures are not classified as Grok-introduced regressions. No Node 22 gate is inferred from this single diagnostic. |
| Browser, native Windows, real backend/provider | **NOT_RUN**. Prior sandbox/media restrictions were preserved. No backend, browser server, paid provider or GPU was started. |

The targeted command used the frozen Vitest binary with these arguments:

```sh
vitest run src/workspace src/workbench src/rebuild src/taskcenter --pool=forks --maxWorkers=2 --minWorkers=1 --reporter=json --outputFile=<private-evidence>/targeted.json
```

The failing case is `src/taskcenter/TaskCenter.additive.test.tsx:72`, **original task receipt companion view shows receipt evidence and preserves task info on a later failed read**. After explicit receipt selection, it timed out finding `1.000001 USD（1000001 micro-USD）`; the task remained visible, while the expected companion amount was absent. That file passed 4/4 both in the isolated check and in the later full run. The test, receipt controller/view and helper blobs match the common base. The general task controller has a deferred mount-read change and list error wording changed, so source similarity alone does not prove runtime equivalence or identify a regression. A deterministic lifecycle diagnosis is needed before claiming a fix or labeling the case flaky.

The full run has 57 failed file entries, including a zero-case collection error in `LocalAiBrowserJourneyContracts.test.tsx` reading absent `frontend/tests/e2e/v2-local-ai-files-live.spec.ts`. The contract test blob and missing fixture path are also present/absent respectively in the common base; this is source comparison, not a base full-suite execution. Of the 313 failed assertions, 144 first-error messages concern a `FeatureLauncher` mock missing `FEATURE_GROUPS`; that grouping does not establish their origin or justify deleting assertions. No explicit Vitest test/hook-timeout message was found. RTL element-wait failures are not automatically resource or engine timeouts. No further full run was started.

The six type errors are:

| Target location | Diagnostic | Classification from actual baseline control |
| --- | --- | --- |
| `src/App.tsx:1970:80` | TS2554: `acceptGeneratedDraft()` called without its required argument | Existing production type error; identical base statement at line 1963 |
| `src/creative/GraphCanvas.tsx:577:31` | TS2339: `contains` is not on `readonly string[]` | Existing production type error; the current expression also has an optional/fallback path, so this diagnostic alone is not a demonstrated runtime crash |
| `src/ui/ModuleStartGate.tsx:43:21` | TS2339: missing `ImportMeta.env` type | Existing production type error |
| `src/ui/handoffSmoke.xUx10.test.tsx:60:7`, `:207:13`, `:232:11` | TS2322: `StudioModule` is wider than `WorkspaceModule` | Three existing test type errors |

An existing public cloud commit, [the minimal type-contract repair `0a3a9eb72bbbd5416a010958018a8b8c86f71b74`](https://github.com/1785235376-blip/AI-Novel-Studio/commit/0a3a9eb72bbbd5416a010958018a8b8c86f71b74), already contains corresponding call/type fixes and focused test updates. Its remote identity and ancestry through the published cloud branch were verified. The next executor should inspect and reuse the relevant minimal patch rather than rebuild the repair or merge the entire cloud branch. This verification itself did not apply that commit to the Grok target.

## Gate and matrix boundaries

The committed regression rule is `adjusted = raw failed - IndependentStudioIdentity failures + 8`, with **best-of-three adjusted ≤297**. The reported 297/297/298 therefore satisfies that specific best-run rule; it is not three individually passing runs or an all-green suite. Those reports use Node 22.14 and an earlier M6 snapshot. The later final snapshot's full suite was not rerun in the external report, and its three raw JSON files were not committed. This independent Node 24 verification does not retroactively validate them.

The committed matrix has **87 PASS / 7 PARTIAL / 2 BLOCKED / 1 NOT_RUN / 1 FAIL** across 98 rows. It is not our 98-row browser/product acceptance. The non-PASS boundaries remain:

- PARTIAL: browser zoom coverage (M1-ZOOM), opt-in-only product entry (M1-E2E), loading-state browser coverage (M2-03), real-backend rename (M2-07), TaskCenter's real session integration (M2S-07), reload-surviving viewport memory (M3-08), and full zoom/size geometry grid (M4-05).
- BLOCKED: server canvas-graph persistence for this UI contract (M3-03) and unavailable original specification trace (M3-13). Existing other CanvasView APIs are not interchangeable graph persistence contracts.
- NOT_RUN: actual reduced-motion verification (M4-08).
- FAIL: the external report's legacy rail color-contrast findings (M4-09). We did not rerun axe/browser checks and cannot relabel them PASS.

Source confirms two useful follow-up areas: viewport state currently lives only in a per-project `useRef`, and the preview host hardcodes its layout scope to `local/preview/preview`. Replacing these placeholders requires truthful existing host scope and fail-closed persistence, not invented actor/incarnation data. The generic task adapter also uses an empty session token; it is not a proven real authenticated task integration.

## Integration boundary

Common base with the cloud image line is `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`. The inspected cloud snapshot `afb3c8d718215ff184ae82145b3d0edcd8865f3f` overlaps the Grok changes in `App.tsx`, `DualCanvas.tsx` and `RebuildCanvas.tsx`; these three cloud files remain byte-identical through `06d19b0404b0ff8cb686adbe7ce3d00a1687c0e4`. A text-only merge was clean for the first two and had four conflict blocks in `RebuildCanvas.tsx` (imports, formal-task props, source/selection lifecycle refs and pointer selection); that is not integration acceptance. The `?uw=1` canvas panels lack the cloud formal image-task callbacks. Original keyed-source, project-remount and late-callback guards must survive any future integration.

No Grok branch was merged, cherry-picked or pushed by this verification. Main and the original owners remain unchanged. The next task is a continuous repair-plus-feature package based on the evidence above, with a separate authorized integration decision later.
