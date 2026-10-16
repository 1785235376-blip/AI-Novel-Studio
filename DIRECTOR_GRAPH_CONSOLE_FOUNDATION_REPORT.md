# Director Graph Console foundation — 2026-10-16

Status: **PARTIAL / bounded integration delivered**, not a full Director Workbench or release gate.
Starting HEAD: `045b865e5a003cac3333462d055f22099f6368d6` (PR #47 source).
Publication identity is the containing Git commit; this report does not claim a future commit hash.

The current source already had `director_plan`, `storyboard_plan`, version/digest pins,
typed `DIRECTOR_PLAN` ports and original workflow execution. The historical M0 missing
rows therefore were not a reason to create another Director or workflow owner.

## Delivered

- Selecting an existing `director_plan` in the actual Studio graph now offers an
  explicit expandable Console, rendering the existing `DirectorWorkspace`.
- The existing planning catalog verifies the bound document ID, mode, version and
  digest before and after the existing Director Workspace GET. Its projection's
  version/mode and the graph client's captured project/branch owner are also checked.
  The projection has no digest field: the two catalog reads use the original owner's
  monotonic revision contract. This is a display fence, not an atomic execution claim.
- Stale/hidden sources cannot silently adopt a new version. Replacing authority,
  node or source pin unmounts private output and local camera inputs. Collapse aborts
  the read. Original authority errors retain their exact code.
- No document, asset, job, version, review, permission or workflow owner was added.
  Expansion never submits graph runs or model work. The original editor's connection,
  deletion and saved-reference restrictions remain authoritative.
- `checkedStudioGraphDraft` exposes the existing input decoder for the separate
  Canvas recovery slice; it grants no execution or storage authority.

The required `.codex/skills/ai-novel-studio-ui/SKILL.md`, design system, protected
surface list, component and visual references were read; the canonical image workspace
reference was inspected. Existing primitives and inspector slots are reused. No shell,
tokens, core primitive or protected surface was edited.

## Evidence

| Check | Result / boundary |
| --- | --- |
| Focused + adjacent frontend | **138 passed**, 9 files (Director contract/component/client, production graph, graph client, revocation and workspace integration). |
| TypeScript | `pnpm exec tsc --noEmit`: **PASS** after correcting the new test spy's generic typing. |
| Vite | `pnpm exec vite build`: **PASS**, existing large-chunk warning retained. |
| Full frontend observations | First run **4159 passed / 6 skipped / 2 failed**. Durable r2 **4160 passed / 6 skipped / 3 failed**; source changed while another agent added recovery tests, so r2 is not a frozen-tree gate. The same two multiple-alert fixture failures reproduced alone; the additional Canvas checkbox race was handed to its owner. Root owns the subsequent stable integration gate. No assertion was weakened here. |
| Real File browser | **3/3 PASS**, installed Edge at **1366×768, 1440×900, 1920×1080**. `director-console-packaged-r9-all-viewports` contains JSON, JUnit, logs, screenshots and redacted network evidence. |
| Scrolled Console screenshots | Additional same-path **1/1 PASS** at 1440×900, `director-console-packaged-r10-scrolled`; authored visual goal/mood and lower colour/performance/empty-shot sections are visibly captured. Seven dimensions are asserted in the DOM; no one screenshot is claimed to show all seven. |
| Geometry | Real header 56 px, sidebar 248 px, inspector 340 px; no horizontal document overflow. This does not replace canonical pixel baselines. |
| PostgreSQL / model / GPU / installed DesktopHost | **NOT_RUN for this slice**. The bootstrap uses actual product source, not an installed-application acceptance. No inference quality or full V2 acceptance is claimed. |

The browser path uses the original **LocalSessionBootstrap** token exchange and
atomic initial-workspace provisioner, then the shipped password credential entry.
Project creation/activation uses the original authorized admin/Studio routes; the
browser opens that project normally. Canvas CJK/emoji text is cached, reloaded,
explicitly revalidated/restored and saved with HTTP 201. The Director graph then
expands the Console, saves, reloads, reopens and rejects an updated source without
changing its old pin. Owned projects are deleted with exact HTTP 204.

No response replay, route mock, fake actor/store injection, raw SQL, model dispatch
or graph execution is used. Network assertions verify no execution endpoint was
requested; no runtime model counter was instrumented. Early launcher receipts'
`model_calls: 0` was a declared scenario field, **not a measured inference counter**;
the reusable helper now explicitly records `NOT_REQUESTED` / `NOT_INSTRUMENTED`.
Pre-authentication 401 and unrelated legacy branch 409 console/network errors are
retained separately; the accepted new path has zero browser `pageerror` events.

## Retained failures and cleanup

All first failures remain in separately named receipt directories: missing Host
(401), missing packaged frontend distribution, pre-auth blank-entry availability,
incomplete explicit feature dependencies (404), and exact-label browser locator
mismatches. The latter use semantic textbox/combobox roles in the final spec,
while exact authored values, chosen document ID and source pins remain asserted.

Automatic approval review rejected the first compound Start-Process/development
session setup with a generic policy rejection. That action was not retried through
another wrapper: the completed path uses the original one-shot packaged bootstrap.
The later compound archive/recursive-cleanup command was also rejected before
execution despite bounded path checks. No rejected filesystem action was retried.

All launcher-owned backend processes stopped. The separately verified owned Vite
PID `53564` was stopped; no unrelated process was touched. The ten tiny owned test
profiles (69,171 recorded bytes) remain under `.runtime/director-console*`, including
failed state; evidence/logs/screenshots remain under `docs/delivery/v2-development`.
No disk-space reclamation is claimed. Explicit indexing is unavailable in this
session's exposed `gf_*` tool set; current source was reread through GraphFlow.

## Remaining entry point

The Console is read-only. Full vision/audience/duration/platform authoring, multiple
rich Director consoles, duplication/rollback and proposal adoption still need
original-owner contracts and focused acceptance. Existing saved-reference deletion
restrictions, Storyboard branches/transitions, 3D/pose/depth and other unimplemented
roadmap rows remain PARTIAL/MISSING. This integration does not turn them COMPLETE.

For this bounded real path, start an isolated Vite proxy to API port 8128 on frontend
port 5198, then run `python scripts/run_v2_director_console_browser.py --label <fresh-label>`.
The helper owns and stops its actual File backend; it does not provision a browser.
