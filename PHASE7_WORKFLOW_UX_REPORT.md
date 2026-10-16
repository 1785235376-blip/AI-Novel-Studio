# Phase 7 — Production Workflow + UI/UX Consolidation 报告

本文记录实际源码、实际执行的隔离检查、保留失败和仍未满足的门禁。Windows、GPU、真实模型、浏览器/视觉与完整产品验收**未执行**；发布源码不改变原验收门禁。line A（后端）与 line B（前端）并行实现，由 Lead 提交；本文件由工程线（line C）维护。

## 实际基线与状态

- 分支 `feature/v2-narrative-platform`；本阶段起点 commit `345ea18d269ee9a8b777ed18060ea7e51ea8c848`（`feat(v2): add proven FLAC delivery and timeline source editing`，即已推送的 Phase 6）。工作树：`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`。
- line A 在本次工作期间落地统一工作流投影源码（`app/creative/production_workflow.py`、`production_workflow_models.py`、`production_workflow_api.py`，并在 `app/creative/workspace_api.py`、`app/creative/workspace.py` 内接入）；对应后端测试 `tests/test_v2_production_workflow.py`、`tests/test_v2_production_workflow_api.py`。**已读源码核对**，不是转述。
- line B 在本次工作期间落地合并 UI 源码 `frontend/src/production/`（16 个文件：types／contract／client／controller／views／tokens 与 5 个 `*.test.ts(x)`）。其 5 个 vitest 文件 35 个用例、`tsc -b` 与生产构建均通过（`frontend-r6`／`r7`、`types-r7`、`build-r7`）；在此之前的 `types-r3`／`r4`、`build-r3`／`r4` 与 `frontend-r5` 曾为红，过程收据保留（见"保留失败"）。浏览器/视觉验收仍 **PENDING_LINE_B**。
- 状态：统一工作流投影的只读投影与唯一意图变更为 **IMPLEMENTED / 源码已核对**；line B 视图源码为 **IMPLEMENTED / basic source UI**，其单元与挂载测试、类型检查与生产构建在最终快照中通过，浏览器/视觉验收 **PENDING_LINE_B**；PostgreSQL 真实验收 **NOT_CONFIGURED**（本机无 server）；完整产品、完整 UI/UX 与 M4→M9 验收仍 **PARTIAL / LOCAL_REQUIRED**。
- **契约差异待裁决**：实现与冻结文本在请求体 `preset`/`note`、GET 额外 `preset`、以及 `values[]` 的 `custom` 字段上有三处差异，见 [phase 文档 §1.1](docs/v2/production-workflow-phase7.md)；本线只记录，不改口径。
- **输入树未冻结。** line A/B 在我执行检查期间仍在写入源码，因此收据的 `source_sha256` 与 `sources_changed_during_check` 记录的是**实际观测**，不是一次冻结输入的证明。最终 pin 必须在 Lead 提交、两线停止写入后重跑本 harness 生成。

## 本线交付物

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| [docs/v2/production-workflow-phase7.md](docs/v2/production-workflow-phase7.md) | 新增 | 阶段设计/契约文档：投影的 WHAT、7 个模块的既有 owner、冻结端点/DTO、只读与唯一新变更、CAS/冲突语义、明确不声称项、验证命令 |
| [AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md](AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md) | 只增修改 | §30 新增 E27–E29 证据索引；CORE-01/CORE-03/CORE-04 行**追加**当前事实（历史状态与证据 ID 原样保留）；尾部新增 Phase 7 只增章节 |
| [scripts/run_phase7_workflow_checks.py](scripts/run_phase7_workflow_checks.py) | 新增 | 阶段验收 harness：(a) File pytest (b) PostgreSQL pytest (c) `src/production` vitest (d) `tsc -b` (e) `pnpm run build`，外加密闭 seam 与 token lint；复用 `scripts/run_v2_checks.py` 的隔离环境/源码快照与 `scripts/pytest_temp_isolation.py` 的临时目录规则 |
| [PHASE7_WORKFLOW_UX_REPORT.md](PHASE7_WORKFLOW_UX_REPORT.md) | 新增 | 本文件 |
| `docs/delivery/v2-development/phase7-workflow-*-r*.json` / `.log` | 新增 | 逐检查收据与原始输出（沿用 phase6 收据结构：command／status／exit_code／isolated_environment／head／source_sha256／log_sha256） |

## 统一工作流投影（line A 已落地，逐条读源码核对）

`GET /api/projects/{nid}/studio/production/workflow`（`domain.read`）把 7 个既有模块汇总为一个只读视图：`schema_version=1`、`contract="studio-production-workflow/1"`、`advisory_only=true`、`execution_authority=false`、`scope`（原公开范围子集）、`project_start`、`creative_intent`、`modules[7]`（固定顺序 `director, storyboard, image, video, audio, timeline, asset`）、`asset_overview`、`dashboard`。`modules[]` 的 `document_count`／`asset_count`／`job_count`／`status` 与 `asset_overview`／`dashboard` 全部由既有行实时算出（`app/creative/production_workflow.py:151-198`）。

`POST /api/projects/{nid}/studio/production/workflow/intent`（`domain.write`）是**唯一**新变更，落在原 `IndependentWorkspaceService.preferences` 的 scope-atomic CAS 与保留历史上；`expected_version=null` 只在当前版本为 0 时创建，否则 `409 PRODUCTION_WORKFLOW_INTENT_CONFLICT`，越界/重复 `422 PRODUCTION_WORKFLOW_INTENT_INVALID`。

准入与装配（已核对）：`is_independent_studio_route` 现已在 GET 分支接受 `workflow`、POST 分支接受 `workflow/intent`（`app/creative/workspace_api.py:30-31`），仍是闭合全匹配；工作流子路由经同一工厂 `workspace_api.py:253-255` 装配；协作准入仍由 `app/main.py:319` 的 `narrative_production_v2` 判定。

**契约差异（PENDING_LEAD_DECISION）。** 当前实现与冻结文本有三处可核对差异，本线只如实记录、不自行改口径：① 请求体只接受 `preset`（`production_workflow_models.py:35`），冻结文本写的是 `note`——`StrictModel` 为 `extra="forbid"`，客户端发 `note` 会得到 `422`；② GET 的 `creative_intent` 额外返回 `preset`（只增字段）；③ GET 的 `values[]` 元素含 `custom`，而 POST 的元素模型只接受 `intent_id/label/selected`，**GET 的元素不能原样回传**，line B 必须显式重建请求元素。细节见 [phase 文档 §1.1](docs/v2/production-workflow-phase7.md)。

## 原 owner 复用（不新增 owner）

| module | 响应中的 `owner` | 被读取的既有 owner（真实路径） |
| --- | --- | --- |
| `director` | `DirectorService` | `app/creative/service.py:CreativeService`（DIRECTOR 文档）、`app/creative/proposals.py:DirectorProposalService`、`app/creative/generation.py:DirectorModelCoordinator` |
| `storyboard` | `StoryboardWorkspace` | `app/creative/storyboard.py:StoryboardWorkspace` + `CreativeService`（STORYBOARD 文档） |
| `image` | `ImageJobService` | `app/services/studio_image_execution.py`（经 `app/creative/production_execution.py:ProductionExecutionService`）→ `app/services/image_job_service.py:ImageJobService` |
| `video` | `StudioVideoExecution` | `app/services/studio_video_execution.py:StudioVideoExecution`、`app/services/video_assembly_service.py:VideoAssemblyService` |
| `audio` | `StudioAudioExecution` | `app/services/studio_audio_execution.py:StudioAudioExecution` → `app/services/audiobook_service.py:AudiobookService` |
| `timeline` | `VideoAssemblyService` | `app/creative/production_execution.py:ProductionExecutionService`（`TIMELINES`）、`app/services/video_assembly_service.py:VideoAssemblyService`、`app/experimental/subtitle_timeline.py:SubtitleTimelineService` |
| `asset` | `AssetLibraryService` | `app/services/asset_library_service.py:AssetLibraryService`、`app/creative/workspace.py:IndependentWorkspaceService.asset_index`（元数据专用聚合） |

没有新增项目、素材、作业、队列、权限、模型注册表或时间线 owner；`project_start` 是对原激活回执的投影，`creative_intent` 落在原偏好行，`asset_index` 只读原资产行且不逐资产打开 lineage/relationship。聚合不装作全知：`asset_overview.private_pending_review` 只统计 owner 自己保存了文本结果复审标记的资产，媒体候选复审是作业级别、聚合不推断。

## 实际执行的检查

各检查输入树不同、互相重叠，不相加。收据：`docs/delivery/v2-development/phase7-workflow-<check>-r<N>.json`／`.log`（每条含 command、status、exit_code、isolated_environment、head、逐文件 `source_sha256` 与 `log_sha256`）。所有结果绑定 commit `345ea18d269ee9a8b777ed18060ea7e51ea8c848`。

| 检查 | 实际命令（logical） | 实际结果 | 收据 | 证明边界 |
| --- | --- | --- | --- | --- |
| (a) File 后端聚焦 pytest | `<python> -m pytest -p no:cacheprovider -q tests/test_v2_production_workflow.py tests/test_v2_production_workflow_api.py` | **PASS**，`14 passed, 8 skipped, 1 warning in 4.15s`，exit 0 | `phase7-workflow-file-r4.json` | 只覆盖 line A 新增的两个测试模块；8 skipped 来自 fixture 的 postgres 参数化；不等于完整 File 套件 |
| (b) 同一测试的 PostgreSQL 后端 | 同上，`STORAGE_BACKEND=postgres` + `TEST_POSTGRES_DATABASE_URL` | **SKIPPED / NOT_CONFIGURED**（`TEST_POSTGRES_DATABASE_URL` 未设置，本机无 PostgreSQL server）；未执行即未通过（`postgres-r3`／`r4`／`r5` 结论一致） | `phase7-workflow-postgres-r5.json` | 需要具备 loopback `/v2_*` 库的环境重跑 |
| (c) 前端新目录 vitest | `corepack pnpm exec vitest run src/production`（cwd=frontend） | **PASS**，`Test Files 5 passed (5)`／`Tests 35 passed (35)`，exit 0 | `phase7-workflow-frontend-r7.json`（`frontend-r3` 1 文件 12 用例、`r4` 4 文件 32 用例、`r5` 2 failed/33 passed 全部保留） | 走查覆盖契约、client、controller、dashboard 与"挂载进原 Studio 工作区"；vitest 不做类型检查，仍需 `tsc -b`／build 配合判断 |
| (d) 类型 | `corepack pnpm exec tsc -b`（cwd=frontend） | **PASS**，exit 0 | `phase7-workflow-types-r7.json`（`types-r3`／`types-r4` 的 FAIL 保留） | line B 修复其测试文件的类型构造与收窄后通过 |
| (e) 构建 | `corepack pnpm run build`（=`tsc -b && vite build`，cwd=frontend） | **PASS**，exit 0：`✓ 2103 modules transformed`、`✓ built in 3.78s` | `phase7-workflow-build-r7.json`（`build-r3`／`build-r4` 的 FAIL 保留） | 构建实际产出；输出只写 gitignore 的 `frontend/dist` |
| 设计令牌（附加） | `corepack pnpm run lint`（cwd=frontend） | **PASS**，`UI token guard PASS (52 files)`，exit 0 | `phase7-workflow-tokens-r4.json` | 冻结检查器 `scripts/check_ui_design_tokens.mjs` 未改 |
| 既有 router/准入 seam（附加，非新 Phase 7 测试） | `<python> -m pytest -p no:cacheprovider -q tests/test_v2_independent_workspace_api.py` | **PASS**，`34 passed, 34 skipped in 15.10s`，exit 0 | `phase7-workflow-seam-r4.json` | 证明本阶段扩展的既有工厂/准入在 HEAD 仍成立 |

**最终快照（同一轮全量运行）。** 上表最后一次全量运行的组合为 `file-r6` / `postgres-r5` / `frontend-r7` / `types-r7` / `build-r7` / `tokens-r4` / `seam-r4`：**除 `postgres` 为 SKIPPED / NOT_CONFIGURED 外全部 PASS**，检查器退出码 `2`（无 FAIL、有 1 项未配置）；`--checks tokens` 单独重跑返回 `0`，`--checks postgres` 返回 `2`，退出码语义已实测。

**修订号必须与输入树一起读。** 同一批命令的结论在两线写入过程中多次翻转，每一次都绑定当时的输入树：`types`／`build` 在 `r1`／`r2`（尚无 `src/production` 测试）为 PASS，`r3`／`r4`（line B 落入测试文件）为 FAIL，`r5` 起（line B 修复类型构造与收窄）为 PASS；`frontend` 的用例数从 `r3` 的 1 文件 12 用例、`r4` 的 4 文件 32 用例、`r5` 的 5 文件 35 用例（2 failed）增长到 `r6`／`r7` 的 5 文件 35 用例全通过。任何一次都必须与收据里的 `source_sha256` 一起读，不能相加或互相替代。(a) 的 `file-r4`／`file-r5`／`file-r6` 与 `seam-r2`／`seam-r3`／`seam-r4` 收据的 `sources_changed_during_check=true`。本轮输入树**未冻结**。

**未运行。** PostgreSQL 真实验收（b 的实体）、浏览器/视觉与 geometry 快照、`pnpm test` 全量前端套件、仓库级生成清单检查、Windows/GPU/真实模型/重型渲染、完整 CI、以及任何真实产品验收均 **NOT_RUN**；本阶段不访问用户数据、不下载模型、不启动 Runtime。

**环境观察（复现须知）。** `frontend-r5` 的失败栈把 testing-library 解析到相邻工作树 `D:\PoemSeed\Worktrees\studio-v2-native-diagnostics-20261011\frontend\node_modules\.pnpm\...`，即本工作树的 `frontend/node_modules` 不是自包含的（依赖被链接到另一工作树的 pnpm store）。这不改变本次结果，但复现时应确认依赖解析路径，或在干净安装后重跑。

## 保留失败（未删除、未改写）

1. **`file-r1` = NOT_YET_AVAILABLE。** 该次运行时 `tests/test_v2_production_workflow*.py` 尚未落地，harness 如实记录缺失路径与 `LINE_A` 依赖，不记通过。
2. **`file-r2` = FAIL，13 个 fixture ERROR（harness 缺陷，非产品失败）。** harness 未复用仓库既有的 pytest 临时目录隔离规则，pytest 把 `tmp_path` 落到 `C:/Windows/Temp/pytest-of-admin/...`，而 `tests/test_v2_production_workflow_api.py:48` 断言 `tmp_path` 必须位于 `<root>/.runtime` 内。修复为直接复用 `scripts/pytest_temp_isolation.py` 的 `pytest_temp_root`／`pytest_environment`（向被检查进程设 `TMP`／`TEMP`／`TMPDIR`），随后 `file-r3`／`file-r4` PASS。`file-r1`／`file-r2` 的收据与日志原样保留。
3. **首次 harness 运行在控制台编码处中断。** 输出 vite 的 `✓` 时 Windows GBK 控制台抛 `UnicodeEncodeError`，当时 `types`／`build` 已 PASS 但 `tokens`／`seam` 未执行。修复为 UTF-8 reconfigure 加安全 `emit()`；`types-r1`／`build-r1` 收据保留。
4. **`types-r3`／`build-r3`／`types-r4`／`build-r4`／`frontend-r5` 的 FAIL 全部保留，且不因后续转绿而删除。** 类型失败的演化：`types-r3` 为 `productionWorkflowContract.test.ts` 构造了契约类型中不存在的 `workspace_id`／`branch_id`（`TS2353`/`TS2339`）；`types-r4` 为 `productionWorkflowClient.test.ts` 在 `ApiError | ProductionWorkflowIntent`（及 `ApiError | ProductionWorkflowProjection`）联合类型上直接访问 `problem`／`message` 而未先判别收窄（8 × `TS2339`）；`build-r3` 记录 11 处、`build-r4` 记录 `TS2349: This expression is not callable. Type 'ApiError' has no call signatures.` 1 处；line B 修复后 `types-r5` 起 PASS。`frontend-r5` 的失败来自新增的挂载套件 `productionDashboardMount.test.tsx`（2 个用例报 `Found multiple elements with the text of: 图片设计`——挂载后的界面里同名可访问标签命中多个 `checkbox`），line B 修复后 `frontend-r6`／`r7` 全通过。这些先红后绿的过程**不被抹掉**，也不把任一次绿灯说成曾经一直绿。
5. **非本线产生的中间态收据保留。** `docs/delivery/v2-development/phase7-workflow-file.json`（无修订号后缀）由 line A 侧运行 `scripts/run_v2_checks.py` 产生，记录当时 `3 failed, 11 passed, 8 skipped`；本线未改动、未覆盖它。
6. **不清理他人写入物。** 本线所有 pytest 均带 `-p no:cacheprovider`，收据环境含 `PYTHONDONTWRITEBYTECODE=1`。工作期间树中出现的 `__pycache__`／`.pyc`（`app/**`、`tests/**`）由其他并发进程产生且已被 `.gitignore` 忽略；为避免干扰仍在运行的 line A/B，本线未删除它们。
7. **本线自身的两次 harness 缺陷均已修复并留证**，但它们只影响 harness，不改变任何被检查源码；line A/B 的产品源码在本线中**未被修改**。
8. **两条收据的等价重记（如实披露）。** 为实测检查器退出码语义，`--checks postgres --revision 5` 与 `--checks tokens --revision 4` 各运行了一次，因而同名收据 `phase7-workflow-postgres-r5.*` 与 `phase7-workflow-tokens-r4.*` 被同检查的等价重跑覆盖（状态与结果完全相同：`SKIPPED / NOT_CONFIGURED` 与 `PASS (52 files)`；命令与隔离环境一致，仅时间戳与 `log_sha256` 变化）。除此之外所有收据均为只追加，未覆盖或删除任何历史文件。

## 尚未完成与交付边界

- **PostgreSQL 真实验收未执行（NOT_CONFIGURED）**：本机没有 PostgreSQL server，`TEST_POSTGRES_DATABASE_URL` 未设置，harness 如实记 `SKIPPED / NOT_CONFIGURED` 并说明理由，不记通过。真实 PG 检查（原 migrations、fresh /v2_* 库、正常停机）仍需在具备 server 的环境执行。
- **line B 已完成本轮的源码与单元/挂载验证（PENDING_LINE_B 收窄为浏览器验收）**：`frontend/src/production/` 的 5 个 vitest 文件 35 个用例全通过（`frontend-r6`／`r7`），`tsc -b` 与 `pnpm run build` 通过（`types-r7`／`build-r7`）。仍未执行的是浏览器/视觉（playwright）验收、geometry 快照与 Opus 视觉重构，以及把该 UI 接进原 AppShell 后的真实打包版行为。
- **LOCAL_REQUIRED（原样保留）**：Windows 安装版 Application、launcher→PG→backend→C# DesktopHost 可信会话、V2 vault/数据/缓存隔离、重启/失效/中文路径/V1 不受影响、GPU 与真实模型质量、重型渲染、完整 CI 与 M4→M9 顺序验收。
- **BLOCKED_ACCOUNT_PLATFORM（原样保留）**：hosted CI 在账号/平台阻塞下的历史状态不由本阶段改写；本阶段未重跑 hosted 检查、不预报通过、不弱化门禁。
- **M4 仍 PARTIAL，M5–M9 仍 LOCAL_REQUIRED**；V1 冻结内容、F00 INTEGRATED + 39 PARTIAL、独立复审 BLOCKED、PoemSeed Local Interop 1.0 语义与 QingJian 暂停状态不变。本阶段不做发布、不打 tag、不合并 main。
- **PENDING_LINE_A_LINE_B**：按 phase 5/6 约定，`docs/v2/phase7-*-20261014.json`（逐文件 blob 哈希的 source-pin 证据）必须在两线停止写入、输入树冻结后由冻结输入树生成。当前工作树仍在被 line A/B 写入，本线不生成该文件、也不假造 blob 哈希。
- 本报告不代替 **Lead 的最终收口**：提交 SHA、远端收据、PR 状态与 hosted 结果由 Lead 在提交后核对。

## 复现命令

```powershell
python scripts/run_phase7_workflow_checks.py --list
python scripts/run_phase7_workflow_checks.py                     # 全部检查
python scripts/run_phase7_workflow_checks.py --checks file,types,build,tokens
python scripts/run_phase7_workflow_checks.py --checks postgres --postgres-url "postgresql://127.0.0.1:5432/v2_phase7"
```

退出码：`0` 全部 PASS；`1` 有 FAIL；`2` 无 FAIL 但有 `NOT_YET_AVAILABLE`/`SKIPPED`。pytest 一律 `-p no:cacheprovider` + `PYTHONDONTWRITEBYTECODE=1`，临时目录复用 `scripts/pytest_temp_isolation.py` 的规则（`<root>/.runtime/pytest-temp/<run_id>`），仓库不产生 `__pycache__`/`.pytest_cache`。前端命令在 `frontend` 下经 corepack 固定的 pnpm 10.6.5 执行；`pnpm run build` 沿用冻结脚本，输出只写 gitignore 的既有 `frontend/dist`，不写受版本控制的路径。

---

## Lead 收口：契约裁决、跨端集成与冻结树验收

本节由 Lead 在 line A/B/C 全部停止写入后追加，是本节之前所有「PENDING_LEAD_*」项的收口。

### 1. §1.1「冻结文本 vs 实现」的裁决（Lead 决定，不再重开）

| 分歧项 | 裁决 | 依据 |
| --- | --- | --- |
| POST 请求体字段 | **只接受 `preset`，没有 `note`** | 复用的既有 owner `WorkspacePreferences` 没有 note 字段；持久化 note 需要在共享 scope 行上加未类型化键、或新建第二个存储，直接违反本阶段「复用单一既有 owner、不新增第二存储」的约束。`extra="forbid"` 下客户端发送 `note` 得到 `422` 是**预期严格行为**，不是缺陷。 |
| GET 额外字段 `creative_intent.preset` | **保留且必需** | 它是 owner 的真实字段。wire 形式为 7 个大写字面量之一（BLANK/TEXT/IMAGE/VIDEO/AUDIO/EDITING/MIXED）；POST 接受任意大小写并归一化为 owner 字面量。 |
| GET `values[].custom` 而 POST 元素不含该键 | **故意不对称，不修** | GET 是**目录投影**，POST 是**请求**。客户端必须显式重建请求元素（`productionWorkflowIntentRequest` 只接受 `intent_id/label/selected`），不得把响应体直接回灌为请求。 |
| `expected_version: null` 语义 | 「尚无已保存的意图行」；`POST /studio/activate` 已把偏好行建到 version 1，故**激活之后**客户端必须提交它刚读到的版本，该处的 null 正确地 409 失败 | 实测复现：`scripts/emit_phase7_workflow_fixture.py` 首版以 null 提交即收到 `PRODUCTION_WORKFLOW_INTENT_CONFLICT`（`current.version=1`）。 |

### 2. Lead 追加的跨端集成证据（在 A/B/C 交付之外）

| 文件 | 作用 |
| --- | --- |
| `scripts/emit_phase7_workflow_fixture.py` | 用**真实服务**导出投影：File 后端、已激活的中性工作台、一次真实保存的意图（v2 / EDITING）、一张真实导入的 PNG。隔离根在 `.runtime/phase7-fixture/`，除夹具本身外不写受版本控制的路径。 |
| `frontend/src/production/fixtures/productionWorkflowProjection.real.json` | source-bound 真实夹具（非手写）。 |
| `frontend/src/production/productionWorkflowRealProjection.test.ts` | 7 项断言：用**前端严格解码器**校验真实后端载荷，并断言 scope 不匹配 / 未知键拒绝的 machine code。任何一侧字段漂移都会让该测试失败，而不是留到浏览器里失败。 |

因此前端用例数由 35 增至 **42**（6 个文件），`tsc -b` 与 `pnpm run build` 仍为 exit 0。

### 3. 冻结树验收（两线全部停止写入后重跑；`sources_changed_during_check=false`）

| 检查 | 命令（节选） | 结果 | 收据 |
| --- | --- | --- | --- |
| File (a) | `pytest tests/test_v2_production_workflow*.py` | **PASS 14 passed / 8 skipped** | `phase7-workflow-file-r7` |
| PostgreSQL (b) | 同上 + `STORAGE_BACKEND=postgres` | **SKIPPED / NOT_CONFIGURED**（本机无 PG 服务，5432/54329 端口关闭；**不是 pass**） | `phase7-workflow-postgres-r6` |
| Frontend (c) | `pnpm exec vitest run src/production` | **PASS 6 files / 42 tests**（含 Lead 跨端真实载荷用例） | `phase7-workflow-frontend-r8` |
| TypeScript (d) | `pnpm exec tsc -b` | **PASS exit 0** | `phase7-workflow-types-r8` |
| Build (e) | `pnpm run build`（冻结脚本） | **PASS exit 0**，2103 modules | `phase7-workflow-build-r8` |
| Token lint | `pnpm run lint` | **PASS** UI token guard 52 files | `phase7-workflow-tokens-r5` |
| 既有 router/准入 seam | `pytest tests/test_v2_independent_workspace_api.py` | **PASS 34 passed / 34 skipped** | `phase7-workflow-seam-r5` |
| 回归：workspace / router | `pytest tests/test_v2_independent_workspace_api.py tests/test_v2_storage_admission.py` | **PASS 48 passed / 48 skipped** | `phase7-workflow-regression` |
| 回归：生产路由准入（对应 Lead 修改的 `is_independent_studio_route`） | `pytest tests/test_v2_storyboard_workspace_api.py tests/test_v2_audio_wav_controls_api.py tests/test_v2_cpu_cutout_api.py tests/test_v2_manual_mask_api.py` | **PASS 120 passed / 120 skipped** | `phase7-workflow-admission-regression` |

harness 汇总：`failed=0`、`pending=1`（仅 PostgreSQL），runner 退出码 `2`（无 FAIL、存在 NOT_CONFIGURED），符合其既定语义。上一节所述「输入树未冻结」的限制由本节重跑消除：上述全部收据均为冻结输入树产物。

### 4. 未完成与不声称的边界

- **PostgreSQL 未运行**：本机没有 PostgreSQL（无服务、无 `psql`/`docker`），PG 分支为 `NOT_CONFIGURED`，**不视为通过**。
- **浏览器/视觉/几何验收未执行**（playwright/visual/geometry）；Opus 视觉细化、接进原 AppShell 后的真实打包 shell 行为未做。
- **LOCAL_REQUIRED 原样保留**：Windows 安装版、launcher→PG→backend→DesktopHost 可信会话、GPU 与真实模型质量、重型渲染、完整 CI、M4→M9 顺序验收。
- **BLOCKED_ACCOUNT_PLATFORM 原样保留**：GitHub Actions 账单锁使 hosted 作业 0 步启动失败；本阶段不预报 CI 通过。
- **V1 冻结内容未改**：未合并 main、未 release、未删除历史证据、未下载模型、未执行真实 Windows 验收。PR #47 保持 Draft。
- **与本阶段无关的既有失败**：全量前端 vitest 的 20 项失败全部落在 2 个依赖 `python3` 的既有套件（本机只有 `python`，`spawnSync python3 ENOENT`），未修改、未掩盖。
- **环境观察**：本工作树 `frontend/node_modules` 非自包含（解析到兄弟工作树 `studio-v2-native-diagnostics-20261011` 的 `.pnpm` 存储）；不影响本轮结论，但干净安装是更强的复现前提。
- 提交 SHA、远端分支头与 PR #47 状态由 Lead 在提交后核对，不写进本文件（避免自指）。
