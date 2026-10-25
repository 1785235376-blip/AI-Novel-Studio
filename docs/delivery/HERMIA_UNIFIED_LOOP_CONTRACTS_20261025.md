# [HERMIA-FE-20261025] Contracts & file ownership — unified loop (t150u M1–M10)

Branch: `work/hermia-unified-loop-20261025` (from verified `a167022b0f12b2df1a725ffae596066686b7d5b9`).
Shared contract file (types only, owned by 总控): `frontend/src/workspace/contracts/index.ts`.

## Actual execution mode (honest)
The platform runs one 总控 executor that may launch additional executor subagents in separate worktrees
(`/workspace/hr/wt-loop-u<N>`, branches `work/hermia-loop-u<N>-20261025`) — this is real parallelism of processes
on one box, not separate bots. Vera (separate agent) is the independent reviewer (unit 5). No implementer is
the sole acceptor of its own work.

## Shared entry files — 总控 only, minimal wiring patches
`src/App.tsx`, `src/workspace/UnifiedWorkspacePreview.tsx`, `src/IndependentStudioWorkspace.tsx`, `src/api.ts`, `src/store.ts`,
`src/workspace/layout/DockLayout.tsx`, `src/workspace/contracts/**`, any SDK/controller/route/scheduler file.
Units deliver a hook/component + a wiring note; 总控 applies the 1–5 line wiring.

## Units
| Unit | Milestones | Owns (create/modify) | Reads only |
|---|---|---|---|
| U1 身份与恢复 | M1, M2, M9 storage parts | `src/workspace/state/identity*.ts`, `scopeLease*.ts`, `viewPreferences*.ts`, `useViewPreferences.ts`, `workspaceRestore*.ts`, `src/workspace/layout/persistence.ts` | store.ts, api.ts bootstrap |
| U2 窗口与交互 | M6, M10 | `src/workspace/registry/**`(new), `src/workspace/actions/**`, `src/workspace/layout/` except DockLayout/persistence, `src/workspace/panels/WorkspaceViewsPanel*`, `src/workbench/**` (additive) | contracts |
| U3 任务与双画布 | M3, M4, M7 | `src/workspace/tasks/**`(new), `src/workspace/panels/TasksPanel*`, `src/workspace/params/**`(new) | taskcenter/*, creative/studioProductionClient.ts, studioGraphClient.ts (no edits) |
| U4 结果与历史 | M8, M9 | `src/workspace/results/**`(new), `src/workspace/history/**`(new) | creative/*, assetbrowser/*, api.ts versions |
| U5 独立测试与审核 | all | `artifacts/unified-loop/review/**`, Vera review appends | everything |

## Rules for every unit
- Consume existing owners/SDK (`taskcenter/taskCenterClient.ts`, `creative/studioProductionClient.ts`, `creative/studioGraphClient.ts`, `creative/studioCanvasViewClient.ts`); never edit their validation, never add endpoints.
- Every async result is bound to a `ScopeLease` (contracts) — late responses after identity/project/client/permission change are dropped.
- No auto model calls, no auto enqueue/execute/adopt/review/Canon writes; production writes only via original entry + explicit confirm bound by `bindConfirmation` (workbench/lifecycle.ts).
- Cost: `TaskCenterCost.state` is always `UNKNOWN` in the contract (taskCenterContract.ts:200–204) → UI says 未知, never a number.
- No raw ids/codes on screen (data-* attrs only). Annotate `[HERMIA-FE-20261025 <unit>-<slice>]`.
- Evidence typed: mock / synthetic-provider / real-file-api / real-browser / real-provider / postgresql / windows.
