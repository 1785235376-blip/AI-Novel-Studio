# UI reconciliation status

## Scope

- 18 protected files restored exactly to a072cf9;18 SHA-256 matches.
- 18 extraction files:67 genuine added definitions and1 explicitly migrated Lineage definition.
- 9 existing runtime files changed and3 new runtime files for the four approved compatibility boundaries.
- 5 new compatibility suites and1 adapted unprotected receipt-hook suite.
- 54 changed/new paths total, with exact SHA-256 and per-case provenance in the JSON ledger.
- No protected assertions, config, manifests, original guards, staging, commits, network, installs, browser, backend or security runs changed/performed by this worker.

## Verification

- Initial restored boundary:262 tests,258 passed,4 genuine runtime failures.
- Approved repair run: 337/337 collected tests passed across 41 files; two App files initially failed collection because of a canvas-owned JSX error. The failed receipt is preserved.
- Final retry after the parser fix: 21/21 passed across both App files and the receipt hook.
- Aggregate: 348 unique cases passed across 43 files, using two runs (the 10 hook cases overlap). Protected originals: 186/186; additive files: 78/78; five new compatibility suites: 35/35; receipt hook: 10/10; unchanged receipt guard: 39/39.
- TypeScript --noEmit, Vite production build, UI token lint, and git diff --check all passed. Build emitted the standard large-chunk warning.
- Every frontend source/config snapshot stayed identical through the final retry and checks. No broad CI or browser claim is made.
- Shared ReceiptNavigation implementation remains byte-identical to base.
- All four formerly failing original runtime assertions passed in the runtime run.

## Approved runtime boundaries

- research: Scope the restored NOT_CONFIGURED wording to this actual local-literal search entry, retain separate embedding/adapter caveats.
- simulator: Restore exact three-field child callbacks; simulator-origin host adapter validates proposal IDs, refuses contradictory authority and enriches only that origin.
- costReceipt: Separate TaskCostReceiptClient and captured-scope factory; original owner has five methods and no hidden receipt property. Panel constructs both clients; controller explicitly injects companion and fences its epoch.
- lineage: Authority-lifetime pristine gate enables the original primary navigation only before interactions and atomically once, targeting validated exact task ID. Any editor/task/focus/refresh/submit/execute/cancel or existing leave-confirmation intent retires gate. All later primary interactions use unchanged ReceiptNavigation confirmation. Layout cleanup and receipt/target/callback/busy epochs prevent stale callbacks.

## Extraction integrity

- Initial extraction preserved all67 new calls exactly. Later approved interface migration leaves60 entire calls identical and changes construction/injection in7; every original extracted assertion remains unchanged.
- The single Lineage migrated variant retains its original callback assertions and is not counted as a new unique capability.
- Exact migrated cases:
- frontend/src/experimental/StorySimulatorPanel.additive.test.tsx :: reopens the persisted route review after remount without saving again or copying input
- frontend/src/taskcenter/TaskCenter.additive.test.tsx :: shows receipt evidence and preserves task info on a later failed read
- frontend/src/taskcenter/TaskCenter.additive.test.tsx :: renders %s without implying an invoice or enabling retry
- frontend/src/taskcenter/taskCenterClient.additive.test.ts :: uses only the original scoped history GET, preserves signal, never reads media
- frontend/src/taskcenter/taskCenterClient.additive.test.ts :: keeps owner read failure %s unknown without fallback or raw text
- frontend/src/taskcenter/taskCenterClient.additive.test.ts :: rejects foreign captured scope before reading and rejects foreign returned scope
- frontend/src/taskcenter/taskCenterClient.additive.test.ts :: receipt history retains the existing captured actor session and branch transport

## Changed paths

- frontend/src/AppAuthorTaskNavigation.test.tsx
- frontend/src/AppAuthorTaskNavigation.additive.test.tsx
- frontend/src/delivery/DeliveryCenterPanel.test.tsx
- frontend/src/delivery/DeliveryCenterPanel.additive.test.tsx
- frontend/src/experimental/BranchManuscriptPanel.test.tsx
- frontend/src/experimental/BranchManuscriptPanel.additive.test.tsx
- frontend/src/experimental/ComicLayoutsPanel.test.tsx
- frontend/src/experimental/ComicLayoutsPanel.additive.test.tsx
- frontend/src/experimental/ExperimentalWorkbench.continuation.test.tsx
- frontend/src/experimental/ExperimentalWorkbench.continuation.additive.test.tsx
- frontend/src/experimental/InteractiveStoryPanel.test.tsx
- frontend/src/experimental/InteractiveStoryPanel.additive.test.tsx
- frontend/src/experimental/ModelBrokerPanel.test.tsx
- frontend/src/experimental/ModelBrokerPanel.additive.test.tsx
- frontend/src/experimental/MultilingualEditionsPanel.test.tsx
- frontend/src/experimental/MultilingualEditionsPanel.additive.test.tsx
- frontend/src/experimental/ProductionLineagePanel.test.tsx
- frontend/src/experimental/ProductionLineagePanel.additive.test.tsx
- frontend/src/experimental/ResearchLibraryPanel.test.tsx
- frontend/src/experimental/ResearchLibraryPanel.additive.test.tsx
- frontend/src/experimental/StorySimulatorPanel.test.tsx
- frontend/src/experimental/StorySimulatorPanel.additive.test.tsx
- frontend/src/experimental/StyleReviewPanels.test.tsx
- frontend/src/experimental/StyleReviewPanels.additive.test.tsx
- frontend/src/experimental/VoiceSubtitlePanels.test.tsx
- frontend/src/experimental/VoiceSubtitlePanels.additive.test.tsx
- frontend/src/experimental/WriterRoomPanel.test.tsx
- frontend/src/experimental/WriterRoomPanel.additive.test.tsx
- frontend/src/modelcenter/ModelCenterPanel.test.tsx
- frontend/src/modelcenter/ModelCenterPanel.additive.test.tsx
- frontend/src/prompt/PromptWorkspace.test.tsx
- frontend/src/prompt/PromptWorkspace.additive.test.tsx
- frontend/src/taskcenter/TaskCenter.test.tsx
- frontend/src/taskcenter/TaskCenter.additive.test.tsx
- frontend/src/taskcenter/taskCenterClient.test.ts
- frontend/src/taskcenter/taskCenterClient.additive.test.ts
- frontend/src/experimental/ProductionLineagePanel.tsx
- frontend/src/experimental/pristineReplayNavigation.tsx
- frontend/src/experimental/simulatorOwnerNavigation.ts
- frontend/src/experimental/StorySimulatorPanel.tsx
- frontend/src/experimental/ExperimentalWorkbench.tsx
- frontend/src/experimental/ResearchLibraryPanel.tsx
- frontend/src/taskcenter/taskCostReceiptClient.ts
- frontend/src/taskcenter/taskCenterClient.ts
- frontend/src/taskcenter/taskCenterTypes.ts
- frontend/src/taskcenter/TaskCenter.tsx
- frontend/src/taskcenter/useTaskCenter.ts
- frontend/src/taskcenter/useTaskCostReceipt.ts
- frontend/src/experimental/ProductionLineagePanel.navigationCompatibility.test.tsx
- frontend/src/experimental/pristineReplayNavigation.test.tsx
- frontend/src/experimental/simulatorOwnerNavigation.test.ts
- frontend/src/taskcenter/taskCostReceiptClient.test.ts
- frontend/src/taskcenter/TaskCenter.receiptCompanion.test.tsx
- frontend/src/taskcenter/useTaskCostReceipt.test.ts

## Evidence

/workspace/scratch/20a0022d2b33/ci-reconciliation-ui-extraction-20261016.json
/tmp/studio-ui-reconciliation/vitest.log
/tmp/studio-ui-reconciliation/vitest-results.json
/tmp/studio-ui-reconciliation/vitest-runtime.log
/tmp/studio-ui-reconciliation/vitest-runtime-results.json

## Final verification evidence

- /tmp/studio-ui-reconciliation/final-verification-results.json
- /tmp/studio-ui-reconciliation/vitest-retry-results.json
- /tmp/studio-ui-reconciliation/final-retry.log
- /tmp/studio-ui-reconciliation/final-typecheck.log
- /tmp/studio-ui-reconciliation/final-build.log
- /tmp/studio-ui-reconciliation/final-token-lint.log
- /tmp/studio-ui-reconciliation/final-verification-source-before.json
- /tmp/studio-ui-reconciliation/final-verification-source-after.json
- /tmp/studio-ui-reconciliation/protected-hash-proof.json

## Independent verification

- Independent reviewer passed 87/87 across six files, including all 15 Lineage integration and six pristine-gate cases. Default timeouts, one worker, no cache; 1,121 frontend source/config hashes remained fixed. The scoped pristine navigation proof was verified.
- Evidence: /tmp/dot-independent-reconciliation-ui-20261016.json and .log.
