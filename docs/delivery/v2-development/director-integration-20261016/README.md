# Director/canvas integration checkpoint

Integrated the preserved local `479a9b18ed9dddc0651e1f211035b9327bc0c57a` history into Codex `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3` in an isolated own-cloud worktree. Common ancestor: `045b865e5a003cac3333462d055f22099f6368d6`. Neither parent branch nor main was reset. No push or hosted workflow was triggered.

Seven textual conflicts were composed individually. Original App navigation intent, Creative save operation identity, guarded adoption readback, incarnation-bound local graph recovery and pinned read-only DirectorWorkspace survive alongside the preserved editable director, source-impact preview, original storyboard derivation and canvas presentation features. No protected shell/token redesign. Codex lifecycle/security changes and production prompt-adoption literal False are untouched.

## Actual checks

- TypeScript: `node frontend/node_modules/typescript/bin/tsc --noEmit --incremental --tsBuildInfoFile /workspace/scratch/20a0022d2b33/studio-director-integration-verification/tsconfig.tsbuildinfo -p frontend/tsconfig.json`, exit 0.
- Focused frontend: Vitest `--no-cache --maxWorkers=2 --minWorkers=1` against 13 graph/director/recovery/App/save-state/adoption files, 154 passed, exit 0. Full result retained in `ui-focused.log`.
- Wider frontend: same options against `src/creative src/canvasops src/director`, 2209 passed / 1 failed in 117 files, exit 1. Original `IndependentStudioReadFences.test.tsx:43` fails because a new asset-read request immediately changes the relationship panel key and collapses its disabled form. Independent reviewer reproduced this unchanged failure on exact preserved `479a9b1`: 6 passed / 1 failed. No assertion was removed or weakened. Follow-up repair is required; this checkpoint is not fully green.
- Original File owner persistence: 91 passed, 10 PostgreSQL cases deselected, exit 0. The exact safe test selection and source hashes are in `../director-integration-file.json`; source hashes did not change during execution. Covers graph annotations, groups, nesting, view preferences, notes, copy/CAS/reopen and director→storyboard source pins/reopen. No lifecycle/security tests were run.
- Vite build: exit 0, retained existing large-chunk advisory. UI token guard: 52 files, exit 0.
- Independent reviewer: App author-task, production-receipt and style-comparison navigation, 3 files / 14 passed. Counts overlap where appropriate and are not a product acceptance total.

Browser/geometry not rerun because the prior own-cloud socket EPERM block remains unlifted. Historical Codex browser receipts do not establish browser acceptance for this integrated source. PostgreSQL, real models, GPU/Windows and hosted CI were not run. Shared dependency package contents were reused read-only via individual local links; Vite temporary configuration and caches stayed within this new worktree. No dependencies were installed.

All append-only historical feature-matrix sections and the frozen product attachment are preserved. The frozen attachment and raw test logs retain their original trailing blank lines; no source whitespace errors remain.

## Relationship refresh correction

The inherited failure is repaired without changing its original assertions. Request `selectionEpoch` still advances synchronously; only the relationship view's render key is held during `readingAsset`, so the original form remains visibly disabled while the current asset read is pending. On success, same-version completion or failure, the new epoch remounts old relationship/reference state. Asset ID/version, host/project identity and revocation fences remain independent.

The original failing suite now passes, including two added same-version/failure completion cases. The related selection (`IndependentStudioReadFences`, `IndependentStudioRelationships`, `AssetReferenceInspection`, `AssetRelationshipsPanel`) passed 38 tests in 4 files, exit 0. The pre-fix failed receipt is retained next to the corrected receipt. This is targeted verification; the earlier broad failure remains a historical result until the wider suite is rerun.
