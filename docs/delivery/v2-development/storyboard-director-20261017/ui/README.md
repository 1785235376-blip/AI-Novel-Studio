# Frontend verification evidence

Source base: `00b305c9c784bd316a8c23a70a28157d19366f09`. These are local bounded mock-client/jsdom checks, not browser or live model acceptance. All logs and full `frontend/src` manifests under `r1/` and `r2/` are byte-exact copies of the original command outputs, verified at copy time. `sha256.json` binds each copied file.

## Final primary r2

- Eight suites, **88 unique tests passed**, including **19 new** storyboard cases.
- `tsc -b --force`: exit 0.
- `npm run build`: exit 0; existing-style large-chunk and npm environment warnings retained verbatim.
- `npm run lint`: exit 0, token guard PASS for 52 files.
- Before/after frontend source manifests identical; manifest SHA256 `21516041c37a2f5fc2f70fe06f966237a4124bd8409d33418723c312afa4bcc5`.
- No source edits during the serialized window; original default test timeouts unchanged.

The exact Vitest command from `frontend/` was:

```sh
./node_modules/.bin/vitest run src/creative/AIDirectorPanel.storyboard.additive.test.tsx src/creative/AIDirectorPanel.test.tsx src/creative/AIDirectorPanel.reasoning.additive.test.tsx src/creative/AIDirectorFastReceipt.test.tsx src/creative/AIDirectorReopen.test.tsx src/creative/GraphDirectorProposalReview.test.tsx src/creative/DirectorModelControls.test.tsx src/creative/StudioGraphDirectorConsole.test.tsx --maxWorkers=1 --minWorkers=1 --no-cache
```

## Retained initial r1

Eight suites / 86 tests passed at an earlier source checkpoint. Forced TypeScript then failed because the new test's generic mutation mock inferred `Promise<unknown>` instead of preserving the callback's `Promise<T>`. The run stopped before build/lint; the failure is retained in `r1/tsc.log`. After an explicit editing window, the test wrapper was corrected and two discard-consent regressions were added; all eight suites and all acceptance commands were rerun in r2. The initial 86 tests overlap r2 and are **not added** to the 88 unique total. Source manifests were unchanged within each run, but differ between checkpoints as expected.

## Boundaries

The mounted original Graph review owner is tested with mock transport: saved STORYBOARD → rule-assisted proposal → edited human review → separate DIRECTOR DRAFT → verified reopen. Original backend File tests separately cover durable Graph pin/restart and persisted source/binding/asset immutability. UI tests cover authored shot association/order, copied-versus-hypothetical fields, retained-only snapshots, missing/contradictory source-mode model gating, dirty content, actual retained callbacks, source/client ABA, source version changes, permission retirement, unmount and same-event-batch consent revocation.

No live model/provider calls, paid calls, browser/socket, PostgreSQL, GPU or desktop acceptance was performed. STORYBOARD model preview/dispatch remains blocked; this slice does not implement intelligent model analysis. Independent final verification passed 60 repeated cases across three files (19 new plus 41 original), with all 2,535 source-plus-companion hashes stable. [Exact independent artifacts](independent/) and the [final source approval](../dot-storyboard-director-final-source-review-20261017.json) are retained separately. These are overlapping subsets and do not inflate the primary 88 unique UI total.
