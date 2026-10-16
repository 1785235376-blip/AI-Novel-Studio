# CURRENT_EXECUTION_STATE — Round 3 completion (R3-R → R3-W → R3-U → R3-I → R3-GATE → R4)

**Updated:** 2026-10-15 (Round 3 completion task book `DSH_ROUND3_COMPLETION_AND_ROUND4_CONTINUATION.txt`)

## Repository / baseline

| Item | Value |
| --- | --- |
| Repository | `1785235376-blip/AI-Novel-Studio` |
| Development directory | `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` (**`D:\PoemSeed` is a container, not a repo**) |
| Branch | `feature/v2-narrative-platform` — in sync with `origin` |
| **HEAD (full)** | `1bce019f492a7e23b06f221f17ed49cf07d7f475` |
| Task-book baseline | `1bce019f492a7e23b06f221f17ed49cf07d7f475` → **exact match, no forward commits to integrate, no rebase needed** |
| `main` | `fed2404c8e30b44061b7139dced45b7f3301601c` — untouched |
| PR #47 | `OPEN`, `isDraft: true`, head `1bce019…` |
| Tracked dirty | **0** |
| Untracked | **51** = 49 under `docs/delivery/v2-development` (historical `phase6-*` receipts + this session's `round3-probe-*` diagnostics) + `.graphflow-cache/` + `graphflow-out/`. **Nothing cleaned.** |
| Protected | sibling clones, `D:\PoemSeed\AI-Novel-Studio` snapshot, QingJian, user's original project — observed only |

No `reset --hard`, `git clean`, force push, ref repair, ACL change or PATH rewrite was run.

## Environment (checked live, not assumed)

| Component | State |
| --- | --- |
| Python / Node / pnpm | `3.11.9` / `v22.14.0` / `12.4.2` (as declared by the repo) |
| **Port 8080** | **held by pid 15392 — the user's Strata server. NOT started by me; never stopped.** |
| **Port 8100** | held by pid 11804 (unrelated) — not mine |
| Ports 8110 / 5432 / 55433 / 5173 / 4173 | **free** (checked live) |
| PostgreSQL | portable cluster `D:\PoemSeed\Builds\studio-v2-host-5ed1cbee-20261011\Base\PostgreSQL` (16.15); checkout-owned cluster `.runtime/pgdata-v2-phase14a` **initialised and stopped**, ready for `run_v2_postgres_checks.py` |
| Isolated runner | `scripts/run_v2_checks.py` (needs explicit `--basetemp` under `.runtime`); `scripts/run_v2_postgres_checks.py` takes positional `label` |

## Sub-phase ledger

| Sub-phase | Status | Evidence |
| --- | --- | --- |
| Baseline verification | **DONE** | this file |
| R3-R read-contract fixes | **DONE (R3-R-08 PARTIAL)** | `ROUND3R_READ_CONTRACT_REPORT.md`; repro **26 failed / 3 passed**; fix **197 passed / 60 skipped / exit 0**; PG **100 passed / exit 0** |
| **§3 read follow-up** | **DONE** | `ROUND3S_READ_FOLLOWUP_REPORT.md`; repro `round3s-repro-r1` **3 mismatches**; fix `round3s-read-followup-r1` **154 passed / exit 0**; PG `round3s-read-followup-postgres` **83 passed / exit 0** |
| **R3-W dedicated authoring** | **DONE** | `ROUND3W_AUTHORING_REPORT.md` / `_DECISIONS.md` / `_HANDOFF.md`; File `round3w-authoring-r10` **202 passed / 60 skipped / exit 0**; real PostgreSQL `round3w-authoring-postgres` **79 passed / exit 0**. D1 fixed (prompt-specific whitelisted 409); D2 confirmed a test-contract error (`head_asset_id` vs `asset_id`). |
| R3-U Prompt Workspace | **PARTIAL** — data layer + U1/U2 done, **React UI NOT_RUN** | `ROUND3U_STATUS.md`. U1 `ddd56ca` (pending-snapshot safety, 33 frontend tests). U2 `e622d12` (narrow revision-body read, 7 backend tests + 115 regression). |
| R3-U3 React UI + browser acceptance | `NOT_RUN` | **next action** — see below |
| R3-I production application | `NOT_RUN` | — |
| R3-GATE | `NOT_RUN` | — |
| R4 asset relationship view | `NOT_RUN` | — |

## R3-U breakpoint (resume here)

> **CURRENT AUTHORITATIVE STATE — 2026-10-15, after `2e0cd43`.** Earlier sections in this file
> (including any `1bce019` HEAD reference or "R3-W NOT_RUN") are historical records, not the
> current status.

**Pushed and verified on `feature/v2-narrative-platform`:** R3-U1 `ddd56ca` · R3-U2 `e622d12` ·
R3-U3-A `8c0c1e8` · R3-U3-B `95ffb59` · R3-U3-C1 `54487af` · R3-U3-C2-P0 `76008c4` ·
**R3-U3-C2-P0-C `f7b43dc`** · **R3-U3-C2-P0-I `2e0cd43`**.
Frontend: **81 tests pass**, `tsc --noEmit` exit 0, `vite build` OK. 0 tracked dirty. PG stopped.

### Done this round

* **P0-C (reproduced, then fixed):** the single shared `epoch` served refresh / selectFamily /
  submit / rebase / compare, so a concurrent read discarded a genuine 201 and the draft hung at
  "正在提交…". Reads now have independent lifetimes (`libraryEpoch` / `detailEpoch` /
  `compareEpoch`) and the **write is bound to `project|branch|actor` + `request_id`**, never to an
  epoch. A failed follow-up list read no longer regresses a confirmed save, and a draft found in
  `SUBMITTING` on remount is reconciled via `reconcileStashed` to "outcome to be verified"
  (keeping the original request id and snapshot) instead of hanging. Host transport stability is now
  a performance follow-up, not a correctness dependency.
* **P0-I (measured, then fixed in the UI):** with a real File service and real routes, a revision
  marked `redacted:true` is masked in Library/Detail while `…/revisions/{asset_id}/body` still
  returns it `COMPLETE` (unauthorised authors get nothing from any route). The owner's authorised
  read contract and the generic download route were **not** changed. The default compare UI now
  checks each selected revision's own flag and refuses with an explanation. **R3-R-08 stays
  `PARTIAL`** — a display mask is not an access-control claim.

### Next concrete action — R3-U3-D (NOT_RUN)

Stand up a temporary, isolated localhost acceptance service (never the user's Strata on 8080, never
port 8100) with real File + real PostgreSQL backends; run Playwright against the genuinely rendered
React app at **1366×768 / 1440×900 / 1920×1080** with screenshots and console-error evidence. jsdom
and fixture replay must not be presented as browser acceptance. User path: Studio → ASSETS → Prompt
工作台 → create P1 → read back → save revision 2 → compare real text → create P2 (must be a
different family) → invalid JSON/seed → unsaved-draft warning → 409 rebase → delayed POST with
refresh/compare/rerender → masked/preview/deleted states → permission isolation → NOVICE/
PROFESSIONAL share one draft.

**Only after D may** `ROUND3U_PROMPT_WORKSPACE_REPORT.md`, `_DECISIONS.md` and `_HANDOFF.md` be
generated. `ROUND3U_STATUS.md` (PARTIAL) remains authoritative until then.

### Still NOT_RUN / PARTIAL (must not be reported as PASS)

`real refresh draft-text restore` **PARTIAL** (the marker only warns; no plaintext is written to
browser storage) · `cross-process concurrency` **NOT_RUN** (R3-GATE must retest
`_asset_scope → project_scope → workspace_mutation`, whose `with` does span the `yield`) ·
`write-time binding target verification` **NOT_RUN** · `private-revision deletion / tombstone`
**NOT_RUN** (owner `delete()` has no `actor_id`) · real browser acceptance **NOT_RUN**.


### R3-U3-A / B — done (real producer contract + snapshot freeze)

* `scripts/capture_prompt_contract_fixture.py` captures the **real** backend JSON into
  `frontend/src/prompt/__fixtures__/`; `promptProducerContract.test.ts` decodes those files, so a
  decoder that disagrees with the producer fails in CI rather than in the browser.
* Confirmed mismatches fixed: library envelope (`required_fields`, `purposes`, `origins`,
  `binding_kinds`) and service envelope (`project_id`, `scope`, `generated_at`, `asset_owner`,
  `bible_owner`); bindings group-level + row-level `verification` and row `kind`; the real contract
  literals `studio-prompt-library/1` / `studio-prompt-detail/1` (were one wrong constant
  `prompt-library/1`), now validated and rejected when unknown.
* `readRevisionBody(familyId, assetId)` + strict decoder added — the U2 route had no caller.
* Pending snapshot now deep-copies all four binding arrays; the session store copies on write and
  read.

### Remaining — R3-U3-C and R3-U3-D

1. `frontend/src/prompt/PromptWorkspace.tsx`, `usePromptWorkspace.ts`, and Library / Editor /
   History / Compare / Binding child components, consuming the verified `promptTypes` /
   `promptContract` / `promptClient` / `promptDraft`. **Do not** reimplement asset saving in a
   component or add a second owner.
2. Mount in `IndependentStudioWorkspace` via the existing ASSETS view or tool-panel slot, with a
   visible Prompt workspace entry. Do not create a component without mounting it, and do not touch
   the AppShell / ModuleSwitcher / protected surfaces (`docs/ui/protected_ui_surfaces.md`).
3. Editor must disable inputs while `isInputLocked(draft)`, guard double submit, keep invalid
   parameter JSON / seed in the draft with an explanation, default hand-written drafts to `MANUAL`
   (never claim `AI_GENERATED`), show `KNOWN`/`UNKNOWN` bindings with their source, and use a
   persistent `aria-live` status rather than a transient toast.
4. Compare via the real `/revisions/{asset_id}/body`; unavailable/redacted/deleted fields must read
   "cannot compare this field". Reuse `StudioInterfaceMode` for NOVICE/PROFESSIONAL — no second mode.
5. New CSS under `frontend/src/prompt/` uses DS-v1.0 tokens only and must be self-verified
   (`check_ui_design_tokens.mjs` only walks `frontend/src/ui`).
6. Then component tests → `tsc` → `vite build` → Playwright at 1366x768 / 1440x900 / 1920x1080
   against a localhost test service, **never the user's Strata on 8080**.

**Only after that may** `ROUND3U_PROMPT_WORKSPACE_REPORT.md`, `_DECISIONS.md` and `_HANDOFF.md` be
generated. While R3-U3-C/D are unfinished, `ROUND3U_STATUS.md` (PARTIAL) stays authoritative.

**Still `NOT_RUN`:** real browser acceptance · real refresh draft restore (PARTIAL by design — the
marker only *detects* a lost draft; text is never written to browser storage) · cross-process
concurrency · write-time reference verification · the U2 tombstone branch against a real deleted
revision (blocked: `delete()` has no `actor_id`).
| R3-I production application | `NOT_RUN` | — |
| R3-GATE | `NOT_RUN` | — |
| R4 asset relationship view | `NOT_RUN` | — |

## Next exact action (resume point) — R3-U

Operable Prompt Workspace per `ROUND3W_HANDOFF.md`: create, edit a **local** draft, save a revision,
version history, version compare, bind characters/scenes/shots/reference assets, show unverified
references, handle `409` without discarding the draft, and recover after offline/refresh/reopen.
Save happens **only** on explicit user confirmation.

Constraints: `docs/ui/design_system.md` + `docs/ui/protected_ui_surfaces.md` + the
`ai-novel-studio-ui` skill (read from `.codex/skills/ai-novel-studio-ui/SKILL.md` if it is not in the
skill menu); reuse tokens/primitives/AppShell; no protected-surface change; no second system.
`check_ui_design_tokens.mjs` only walks `frontend/src/ui`, so new module CSS must be self-verified.
Then frontend tests + TypeScript + production build, then commit/push R3-U alone.

## Hash ledger (kept deliberately distinct — §2 of the directive)

| Role | Value |
| --- | --- |
| **baseline_sha** | `1bce019f492a7e23b06f221f17ed49cf07d7f475` (Round 3 data projection) |
| **last verified remote commit (before this sub-phase)** | `f83cadbe8eb61ced886460a1c2e2fe5c36e4da21` (R3-R) |
| **current sub-phase** | §3 bounded read-contract follow-up — committed locally, pushed to the dev branch |
| **source snapshot tested** | `app/creative/prompt_asset.py`, `app/creative/prompt_workspace.py` as modified in this sub-phase; digests are in the runner receipts (`round3s-read-followup-r1.json`) |
| **next concrete action** | R3-W (see below) |

A report cannot contain the hash of the commit that includes it; the commit record is the publication
identity and the runner receipts are the source pin.

## Round 3 status (honest)

Round 3 has delivered: the prompt-source audit, a read-only library/detail/context projection (3 GET
routes), the R3-R read-contract repairs, and the §3 follow-up. It is **still not a complete Prompt
Studio**: there is **no authoring route** (`ManualAssetImport.kind` is `image|video|audio` only) and
**no Prompt Workspace UI**. Those are `NOT_RUN`, not renamed into Round 4.

## Decisions in force (task book §0 + directive §4)

1. Dedicated Prompt create/revision entry reusing `AssetLibraryService`; **do not** widen
   `ManualAssetImport`.
2. No `PromptDatabase`, no second asset/version/review/queue system.
3. **Forbidding AI auto-overwrite ≠ forbidding the user to edit/save/revise.**
4. Browse = latest readable; a saved revision records the **actually adopted** source version +
   digest and must not silently drift. Source change ⇒ STALE, never an automatic rebind.
5. **R3-R-08 stands as PARTIAL by decision:** the authorised raw-asset download contract is
   unchanged; masking is never called confidentiality; the cross-route security claim stays PARTIAL
   until cross-route tests establish its scope.
6. Preserved: `main` untouched, PR #47 Draft, V1 frozen, QingJian untouched, Content Policy
   `RESERVED`, user's Strata untouched (pid 15392 on 8080 — not mine, never touched), no model
   download, no paid API, no final Windows/GPU acceptance.

## Next exact action (resume point)

**R3-W — dedicated Prompt authoring** (directive §5). Nothing is in flight; the follow-up sub-phase is
committed and pushed.

1. **Map the real call sites first** (directive §5 preamble): `AssetLibraryService.create` /
   `update_metadata` / `annotate_lineage` / `promote_owned`, the lock order and
   `workspace_mutation` boundary, `IndependentWorkspaceService._asset_scope` binding, and how
   `actor` reaches them. "The payload fits the allow-list" proves **shape compatibility only** — it
   does not prove atomicity, immutable revisions, provenance integrity or concurrency safety.
2. Add strict DTOs (e.g. `app/creative/prompt_authoring_models.py`): create + revision requests
   accepting only documented user-editable fields (text, negative prompt, purpose, provenance
   category, model preference, non-executing parameters, seed, selected bindings, change note/reason,
   `request_id`, expected head identity). **Reject** client-supplied `approved_at`, reviewer,
   authority fields, receipts, `model_called`, output provenance and internal owner/binding markers.
   Preserve whitespace/newlines/CJK/emoji — no generic `.strip()` on creative content; measure actual
   UTF-8 bytes against the existing limits.
3. Thin authoring adapter over the existing owner. Allocate `revision` inside the existing
   project-binding mutation lease; no process-local lock claimed as cross-process safety; never hold
   a storage lock across a model or external call.
4. Routes: `POST /projects/{nid}/studio/prompts` and
   `POST /projects/{nid}/studio/prompts/{family_id}/revisions`, added to the closed admission
   allow-list in `app/creative/workspace_api.py`; keep `/prompts/context` registered before the
   variable family route; the three GETs stay read-only.
5. Idempotency and failure: same actor/scope/`request_id` + same request ⇒ same result; same
   `request_id` + changed payload ⇒ conflict; injected failure after bytes / metadata / lineage /
   response must be recoverable exactly once via the original request identity, with no duplicate
   asset and no fabricated success.
6. Tests T01–T09 (directive §5.4) on File **and** real PostgreSQL; then commit/push R3-W alone.

**Known constraints found so far (design around them):**
the `update_metadata` allow-list is `{source_job_id, provider_id, model_id, parameters, approved_at,
character_id, scene_id, source_asset_ids}` — the prompt payload fits inside `parameters` plus
`character_id`/`scene_id`/`source_asset_ids`, so **no owner change is required yet**; and the asset
owner's reads require the **actor**, so a private draft is invisible to an anonymous read
(confirmed by test).

## Stop reason (if the session ends here)

The §3 follow-up is complete and committed; R3-W onward is `NOT_RUN`. Any stop is a **session/tool
budget** limit — not a product blocker, and not a claim that work is running in the background.




<!-- V2-RETIREMENT-CANVAS-20261016 -->
## 2026-10-16 — Project retirement + Canvas/Director foundation 最新检查点

本节为 append-only 当前事实；早期记录保留，旧 `authoring NOT_RUN` 与旧 lock 描述不作为当前结论。
实现 HEAD `62d4aaf621eb7663e37d2ad88f2f9c64db9095f9`，后续仅发布报告与原始证据。PR #47 原分支 fast-forward 推送，main/frozen refs 未改。
完整逐文件、失败/通过回执、范围与下一入口见 [docs/delivery/v2-retirement-canvas-20261016/V2_RETIREMENT_CANVAS_ROUND_REPORT.md](docs/delivery/v2-retirement-canvas-20261016/V2_RETIREMENT_CANVAS_ROUND_REPORT.md)。

| 项目 | 当前结论 |
| --- | --- |
| Project retirement / incarnation isolation | 本轮指定缺陷已实现并通过真实 File/PG：项目级授权/binding/scopes 随原 owner 退休；新 incarnation 不继承旧授权；exact 403 与合法新作者 201/200 均有控制。 |
| Cross-workspace / orphan / scope races | 同 workspace 历史 orphan 在原创建事务清除；foreign binding exact 400、无公开 orphan；原 owner 租约覆盖 scope validation/save；audited mutations 原边界前后重验 actor/membership。不是所有路由的撤权/ABA 并发证明。 |
| Canvas / GRAPH | PARTIAL foundation：现有 Studio 挂载、schema 1/2 文本图本地恢复、incarnation/version/digest 复核与显式恢复；媒体/外部引用/分组注释恢复及完整 Infinite Canvas 未建立验收。 |
| Director / CONSOLE / DIR | PARTIAL foundation：原 director_plan Graph 节点打开原 DirectorWorkspace 只读投影，前后 pin 校验、stale/revocation 拒绝、collapse/expand/reopen 已验证；完整 authoring/决策/review/rollback 未完成。 |
| Prompt / R3 | authoring 的创建/修订/CAS/幂等实现已存在；production adoption gate 仍关闭，503 PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED。继续原 Asset/Review owner，不能重建。 |
| 真实 File | scope/retirement/orphan/权限基础 62 passed；冻结生命周期/额外 IO/通知/锁顺序 32 passed。 |
| 真实 PostgreSQL | 最终稳定源码组合 48 passed，47 File cases deselected；PostgreSQL 16.15、新空库、原 20 migrations、实例已停止。 |
| Frontend / tsc / build | 4163 passed、6 skipped、0 failed；tsc -b 与 Vite build PASS。 |
| Browser | 原 Chromium visual/geometry 7 passed；真实 File Canvas+Director 最终三视口 3 passed，无响应 mock/dev session registry。 |
| 冻结保护 | 750 frozen test/gate sources、752 选定保护 artifacts 与基线原字节相同；9151 manifest 不变。增量清单14910为 INVENTORY_ONLY，不是测试通过数。 |
| 高级功能 / release | Storyboard/媒体图/NLE EDIT-16/3D/Tutor/storage/internal Mature 完整增量与全 V2集成未由本轮交付；整体 PARTIAL，非 freeze/RC。 |
| NOT_RUN / LOCAL_REQUIRED | hosted 最终 HEAD CI、真实 PG browser、Windows installer/clean-machine、真实模型/GPU inference。既有 Prompt browser spec 存在，本轮未重新审计其运行回执。 |

下一精确入口：`app/creative/prompt_adoption_api.py:adopt_prompt` 与
`PromptAdoptionService.adopt_atomic`，在真实原路径证明 write-time binding（当前
`source_bindings_verified=False`）、私有 Prompt 删除→tombstone、跨进程/撤权并发及 R3 browser gate；
production adoption gate 在验证成立前保持关闭。复用现有 `_write`、File/PG 服务测试及 Prompt browser spec。
原 `AssetLibraryService.project_scope` 当前已持 `workspace_mutation` 跨越 yield，不能沿用旧测试说明断言它无跨序列锁。

原始失败记录全部保留；本轮 API/Vite/PG 已停止。自动审批复核阻止临时目录/worktree 清理，保留 profile、
PG 数据与 baseline regression worktree，未通过其他删除路径绕过，也未宣称回收磁盘空间。


<!-- V2-R3-PROMPT-20261017 -->
## 2026-10-17 — R3 Prompt 后续最终检查点

本节追加当前事实，早期记录及失败回执保留；取代上节 R3 write-time binding、私有 tombstone、跨进程撤权与 PG browser 未完成的状态。
从 `618affbca0aaf20d5bc669d697d8e2b1abb9b3fa` 继续；五个独立实现/清单/字节包装切片均已逐个推送 PR #47 原分支，
实现 HEAD `f7fd63a1fff3c0ec7fa88c9c111676f9539a41a5`，本节与原始证据另作独立提交。PR 仍为 Draft，main/frozen refs 未改。
完整结论、原始回执、失败与边界见 [R3 最终报告](docs/delivery/v2-r3-prompt-20261016/V2_R3_PROMPT_ROUND_REPORT.md)。

| 项目 | 当前结论 |
| --- | --- |
| Adoption write-time binding | 原 `GraphAssetInputs.phase` 内解析并验证 Character/Scene/目标 Shot/引用与输出 Asset，原 project/asset/Creative 租约覆盖提交。新提交凭证为 `prompt-adoption-bindings/1`、`source_bindings_verified=True`；是写入时快照，不代替审批或执行权限。 |
| Private Prompt / tombstone / retry | 原 AssetLibrary/lifecycle 持 actor；删除保留不可变字节和旧 revision，tombstone 继续作为 CAS head/请求记账；完成 replay 严格绑定路由和前驱；失败恢复绑定服务器首次 origin，旧来源不明请求 fail-closed。 |
| Cross-process revocation | File 24 passed、真实 PG 24 passed；create/revise/delete/adopt × 三类撤权 × 两种提交顺序。实际共享原 OS lock / PG `pg_blocking_pids` holder-waiter 证明，原已发 session 撤权后精确403、合法新作者正控制。不是所有路由或跨进程 session registry 的保证。 |
| 真实 File 最终组 | 私有84、bindings43、authority74、授权/scope55、独立进程24 passed；各组有重叠，不相加为唯一覆盖数。 |
| 真实 PostgreSQL 最终组合 | 103 passed、99 deselected，新空库 OID23468；原20 migrations，源码无漂移，数据库保留、服务已停止。 |
| 真实 Edge 浏览器 | File 三视口3 passed，另一个全新 PG 库 OID24389三视口3 passed；原 LocalSessionBootstrap/HTTP，无 response mock。实际UI创建/修订/版本比较，真实浏览器HTTP删除后验证UI tombstone/history；没有删除按钮成功写声明。 |
| Production adoption | `PROMPT_ADOPTION_WRITE_ENABLED=False` 继续关闭；真实浏览器请求为503 `PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`。后端正向 adoption 仅在显式隔离测试内启用，不因此开放生产。 |
| Frontend / CI self-check | src 4163 passed、6 skipped；tsc/Vite build PASS。225项既有V2 ID模块/CI自检通过，UI token guard52文件通过。全目录Vitest误收集三个既有Playwright suite的失败保留。 |
| 字节与 frozen | 2290 runner源码、2352全V2清单输入与实现HEAD raw bytes相同；750 frozen test/gate sources、752保护产物与9151 manifest原字节不变。不是全部V1 app源码或V1运行验收声明。 |
| 增量清单 | 15118项、208新增、一个显式V2参数ID稳定迁移，双次字面ID/顺序收集一致；`INVENTORY_ONLY`，不是15118通过。 |
| Hosted CI | BLOCKED：GitHub账户billing issue，job未启动/steps为空；不记产品测试失败，也不记hosted PASS。 |
| 总体 V2 / release | PARTIAL；完整Canvas/Director/媒体/NLE/3D/Tutor等既有边界保留。生产adoption UI成功写、全V2集成、Windows installer/clean-machine、真实模型/GPU不由本轮建立PASS。 |

后续入口：解除外部账户账单锁后重跑最终 HEAD 托管 CI，并继续既有全 V2 产品验收；生产 adoption 闸门仍关闭。
原始失败/中断、截图、profile、PG数据库和先前保留baseline worktree均保留；自有API/Vite/PG已停止，不宣称回收磁盘空间。


<!-- V2-R3-ADOPTION-UI-20261017 -->
## 2026-10-17 — R3 adoption UI 隔离成功写检查点

本节追加当前事实，保留早期历史。隔离 adoption UI 成功写已通过；生产常量仍为 literal False。
基线95420aa，稳定切片已逐个提交并推送 PR #47 原分支，实现/清单 HEAD `db1f687108fac6e45a577196494dfac01cc63aca`；本节与证据独立提交。
PR保持Draft，main/V1 frozen refs未动，完整V2仍PARTIAL，非freeze/RC。
原始证据和限制见[R3 adoption UI 最终报告](docs/delivery/v2-r3-adoption-ui-20261017/V2_R3_ADOPTION_UI_ROUND_REPORT.md)。

| 范围 | 当前结论 |
| --- | --- |
| 原 owner/UI | 原 Storyboard 新增显式读取/审批/确认/采用；原Asset/Review/adopt_atomic/Creative CAS复用。成功回读原文档及固定来源、同步host，迟到回读不能覆盖已接受新版本。 |
| 闸门 | GET write_enabled是能力而非授权；普通后端前后False/精确503/owner不变。仅验收子进程内存True，无产品开启入口。 |
| 真实 File/PG | File55 passed；新空PG库OID27042，原20迁移，43 passed；各组有重叠。 |
| 真实 UI | File/PG Edge各3视口通过：真实POST200、单版本/单proof、真实Character快照、正文同步、刷新重开、幂等及来源r2后仍pin r1。PG浏览器另新库OID27943，原20迁移。 |
| 前端 | src4208 passed/6 skipped/0failed，tsc/build PASS，原visual7 PASS、token52文件PASS。 |
| 清单/冻结 | 双collection15142=原15118+24，INVENTORY_ONLY；2301运行源码/2363清单输入绑定实现HEAD。166原CI自检PASS。750 frozen test/gate、752保护产物、9151 manifest原字节不变。 |
| 原连接/既有限制 | File r2连接界面被迟到本机列表切走，已在原App自动恢复补身份一致性guard并先RED后GREEN。PG r1刷新重开失败保留；晚到overview覆盖早期导航仍未修复，final-r3只建立启动完成后的闭环。原摘要裁切/上游不可读限制保留。 |
| Hosted/总体 | GitHub账单锁使job steps为空，单独BLOCKED；完整V2 PARTIAL。生产adoption、全V2集成、installer/clean-machine、真实模型/GPU未建立PASS。 |

自有API/Vite/PG已停止，失败/通过回执、截图、profile和数据库保留。上一轮跨进程24/PG103仅历史证据。
后续需解除外部账单锁并重跑最终HEAD托管CI，继续原全V2验收；生产adoption闸门继续关闭。


<!-- V2-NAVIGATION-INTENT-20261017 -->
## 2026-10-17 — 初始化早期导航竞态修复检查点

本节追加事实并保留全部历史。基于87408f6，原App晚到overview覆盖用户模块选择的问题已修复；此前“仍未修复”的记录为旧状态。
稳定切片逐个提交并推送PR #47，实现/清单HEAD `7893cd027433e165b4035eac0f744c27cb93310a`；本节和原始证据独立提交。
PR仍Draft/open，main/V1 frozen refs未动，完整V2仍PARTIAL、非freeze/RC。生产adoption literal False继续关闭，本轮普通后端未patch gate。
详见[最终导航验收](docs/delivery/v2-navigation-intent-20261017/V2_NAVIGATION_INTENT_ROUND_REPORT.md)。

| 范围 | 当前结果 |
| --- | --- |
| 原App owner | 同值NOVEL/真实Creative入口也记录intent；首次actor解析保留当前选择，真实身份/范围与ABA隔离旧callback；旧asset hint不跨entry。原连接guard不变。 |
| 真实File/PG Edge | 各6 passed/0skip/0flaky，3视口覆盖冷启动、刷新、快速切换、默认IMAGE与跨project/branch；PG新空库OID28822、原20迁移。 |
| 时序真实性 | 精确原GET client dispatch held→真实UI点击→continue原200；跨scope旧子GET真实abort，standalone owner readback另记。before-actor点击/parentABA/localhint仅mounted证明。 |
| 前端 | 新34mounted、相关128包含新34；完整src4242 passed/6既有skip/0failed，391文件；tsc/build PASS、原visual7 PASS、token52文件PASS。 |
| 来源/清单 | 2305 runner源、2367manifest输入与HEAD raw bytes绑定；双collection15142原rows/order/classification保持，INVENTORY_ONLY；166原CI自检PASS。 |
| 冻结保护 | 750 frozen test/gate、752产物、9151manifest、1118既有test/gate、61adoption源和原connectionguard原字节保留；不是全V1 runtime声明。 |
| Hosted/总体 | GitHub账单锁使job steps为空，单独BLOCKED；完整V2 PARTIAL。生产adoption、installer/clean-machine、真实模型/GPU及原全链路边界继续保留。 |

自有API/Vite/PG已停止，所有失败/通过证据、profile与数据库保留；未递归清理或宣称磁盘回收。待账单锁解除后重跑最终HEAD hosted CI；生产adoption闸门继续关闭。


<!-- V2-CREATIVE-SAVE-STATE-20261017 -->
## 2026-10-17 — Creative 保存状态修复检查点

本节追加事实并保留全部历史。基线454ccd8；当前保存版本、未保存/待核对与其他阶段草稿已在原owner内分别显示；等值/撤回编辑、非SAVE假保存中及旧VERIFY候选跨文档窗口已修复。
稳定切片逐个提交并推送PR #47，实现/清单HEAD `5c17750bd59c76ed4fb060716d61019151a3ef42`；本节与原始证据独立提交。PR仍Draft/open，main/V1 frozen refs未变；完整V2 PARTIAL、未freeze/RC，生产adoption literal False继续关闭。
详见[最终Creative保存状态验收](docs/delivery/v2-creative-save-state-20261017/V2_CREATIVE_SAVE_STATE_ROUND_REPORT.md)。

| 范围 | 本轮结果 |
| --- | --- |
| 原owner | 完整可写内容比较保留空白/Unicode/数组顺序；当前SAVE/VERIFY/DERIVE/RESTORE分开；其他草稿和原退出/权限保护保留。旧导航与adoption CAS guard原字节保留。 |
| 真实File/PG Edge | 各9 passed、0skip/0flaky，三视口；首开v1、真保存CASv2/readback/刷新、离线保稿、真409与显式核对、旧VERIFY/历史读回隔离。PG新空库OID29705、原20迁移。 |
| 前端 | 新27回归（26完整原UI、1制作callback替换契约），相关99含新27；完整src4269 passed/6既有skip/0failed，393文件；build、原visual7和token52 PASS。 |
| 来源/清单 | 2310 runner源、2372manifest输入与HEAD raw bytes绑定；双collection15142原rows/order/classification保持，INVENTORY_ONLY；原CI自检166 PASS。 |
| 保护/边界 | 原750 frozen tests/gates、752产物、9151manifest、1118旧test/gate保持；不是全V1 runtime或旧全链路重跑声明。离线发生在派发前，不冒称已提交响应丢失。 |
| Hosted/总体 | 原GitHub账单锁使job steps为空，独立BLOCKED；完整V2 PARTIAL。生产adoption、installer/clean-machine、真实模型/GPU与原全链路边界继续保留。 |

自有验收服务已停；所有失败/通过证据、profile与数据库保留，未递归删除或宣称空间回收。待账单锁解除后重跑最终HEAD hosted CI；生产adoption闸门继续关闭。
