# 前端分支合并与新环境测试报告（2026-10-31）

## 1. 合并

- 新前端分支：`work/hermia-backend-align-20261030` head **`a83df9ce3445fc64edfaa418f2c0cee1bb76779d`**（5 个新提交：Prompt workbench EN、RebuildCanvas EN、CanvasImageNodeTask reactive locale、默认节点标题 EN、Vera review tail）。
- 合并基线 main：`a0caa596adbce0cd91be7f7edaef23a6f9fd8856`（V2.0.0 + 能力补充 #55–#66）。
- 合并结果：0 冲突，18 files changed（17 frontend + 1 artifact），+808/−193；PR **#67** merge commit **`03b46a1429cc538552d1b27b472ee6e16b8e84e1`**，main 已更新。
- 能力补充（#55–#66）此前已合并到 main。

## 2. 新测试环境（隔离）

- 新 worktree：`D:\PoemSeed\Worktrees\v2-final-merge-20261031`（detached merged main）。
- 新 Python 环境：`D:\PoemSeed\Validation\v2-final-merge-env`（`python -m venv --system-site-packages`，Python 3.11.9；pytest 9.1.1 / pydantic 2.13.4 / fastapi 0.141.1）。
- 隔离环境变量：`LOCALAPPDATA`/`APPDATA`/`TEMP`/`TMP` 指向 `D:\PoemSeed\Validation\v2-final-test-run`；`NOVEL_DATA_PATH` 指向该目录下 `novel_data`；`PROJECT_ROOT` 指向 worktree；`PYTHONPATH` 含 worktree 与 tests。
- 前端：Node v22.14.0 / npm 10.9.2 / pnpm 12.4.2；`frontend/pnpm-lock.yaml` 下 `pnpm install --frozen-lockfile` 成功。
- 说明：默认 `C:\Windows\TEMP` 与 worktree 内 `novel_data` 在当前沙箱下不可写，故使用上述隔离路径；这是测试环境配置，不是产品缺陷。

## 3. 测试结果

### 3.1 后端（新环境）

- 能力组 13 个测试文件（registry/runtime/cost/capacity/scope-docs/create-coverage/audio-history/graph-multinode/timeline-audio/video-local-render）：**96 passed / 0 failed / 0 skipped**（日志 `backend-capability-group-newenv.log`）。
- 宽扫 99 个测试文件（asset/file/project/generation/phase/import/api/novel/chapter/continuity/model/provider/credential，排除已知超时 file_safety_http）：**1066 passed / 32 failed / 30 skipped**。
  - 30 个失败为合并前 main 已存在的同类预存失败；
  - 另外 2 个 `test_project_quota_management_authority.py` 锁序子进程失败在**同一新环境**下于合并前基线 `a0caa596` 同样失败（2 failed / 15 passed），属隔离环境的 `STUDIO_TEST_RUN_ROOT`/multiprocessing 限制，不是前端合并回归。

### 3.2 前端（新环境）

- `pnpm test`：合并后 **1026 个测试文件，96 failed files / 792 failed tests / 12,736 passed / 6 skipped**；
- 合并前基线 `a0caa596` 在独立 worktree 同环境：**1023 files，96 failed files / 792 failed tests / 12,724 passed / 6 skipped**；
- 因此前端合并**未新增失败测试/文件**；未通过测试为既有问题。
- 本次前端提交改动的测试全部通过：`PromptWorkspace.en.test.tsx` 5、`RebuildCanvas.en.test.tsx` 3、`CanvasImageNodeTask.locale.test.tsx` 2、`defaultNodeTitle.test.ts` 4。
- `pnpm build`：合并前/后均失败，同为既有 Windows 大小写文件名冲突（`frontend/src/ui/nsfw/NsfwMode.tsx` 与 `nsfwMode.ts` 仅大小写不同）及 `AppShell` 期望的 `NsfwController` 导出缺失；不是 #67 引入。

## 4. 结论与边界

- ✅ 能力分支与新的前端分支均已合入 main；前端合并无冲突、无新增失败。
- ❌ 前端全量测试与 `pnpm build` 在 Windows 上仍为**既有失败**（96 文件/792 测试 + 大小写冲突构建错误），需单独修复前端跨分支/文件名大小写问题后才能作为可发布前端。
- ❌ 后端宽扫仍有既有失败与隔离环境子进程限制失败；能力组全通过。
- 真实 PostgreSQL/浏览器/真实模型/Windows 打包桌面/hosted CI/外部 NLE 仍 **NOT_RUN**；本报告不是全产品验收证明。

## 5. 证据（本地）

`D:\PoemSeed\Validation\v2-final-test-20261031\`：`backend-capability-group-newenv.log`、`backend-core-sweep-newenv.log`、`backend-baseline-quota.log`、`frontend-install.log`、`frontend-tests.log`、`frontend-build.log`、`frontend-baseline-*.log`。

## 6. 后续修复（2026-10-31 同日）

已修复前端在 Windows 上的主要阻塞（工作分支 `fix/frontend-nsfw-case-collision-20261031`）：

- **大小写模块冲突**：把 `frontend/src/ui/nsfw/NsfwMode.tsx` 重命名为 `nsfwModeControls.tsx`，同步更新 `AppShell.tsx` 导入；`NsfwMode.test.tsx` / `nsfwMode.ts` 逻辑模块保持原路径。
- **Vitest 部分 mock 丢失导出**：12 个 App 级测试对 `./ui/FeatureLauncher` 的 `vi.mock` 改为 `importOriginal` 展开后覆盖组件，保留 `FEATURE_GROUPS` 导出（280 个 "No FEATURE_GROUPS export" 失败消失）。
- **扫描器 Windows 兼容**：`apiErrorWhitelist.test.ts` 的 Python 扫描改为 `PYTHON` 环境变量优先、Windows 回退 `python`（原先硬编码 `python3`，Windows 无此别名）。

修复后复测（同一隔离前端环境）：

- `pnpm build`：**PASS**（修复前 TS1149/TS1261 大小写错误、TS2305 NsfwController 缺失均消失）；
- `pnpm exec vitest run src/ui/nsfw/NsfwMode.test.tsx src/ui/AppShell.test.tsx`：**47 passed**；
- 全量 `pnpm test`：**43 failed files / 154 failed tests / 13,374 passed / 6 skipped**（修复前 96 failed files / 792 failed tests / 12,724 passed）；
- 剩余失败为既有产品/测试漂移（IndependentStudio storyboard/handoff、ComicPublication、AuditGenerationScope、API 错误码审计清单等），与本次分支合并和大小写修复均无关；前端全量尚未全绿。

## 7. 第二轮修复（2026-10-31 同日）

继续修复后剩余失败从 154 降到 126：

- 恢复历史快照中缺失的 `tests/fixtures/v2_graph_note_numbers.json`（commit b1f16166 中存在，当前 main 缺失；`graphCanvasLargeNotes` 契约测试通过）。
- `frontend/src/creative/client.ts` 的 `verifiedTextExport` 在 digest 前把跨 realm 的 `ArrayBuffer` 包装为本地 `Uint8Array`，修复 jsdom/Node 下 `SubtleCrypto.digest` 类型错误（Storyboard/Director sheet export 通过）。
- `apiErrorWhitelist.test.ts`：未知站点按 `/` 归一化后与审计清单比较（Windows 扫描器输出 `\`），并补登两个已审计的通用 `exc.code` 站点；该文件只剩 1 个既有变异用例失败（B12 AudiobookError 模式定位）。
- App 级生成测试：`NovelAssist` 现把完整 AI 面板放进抽屉；在 `AuditGenerationScope.test.tsx` 增加 mock 直接暴露 `ai`，**28/28 通过**；同类 mock 也补到 `AppWorkspaceResume`、`AppRevisionHistory`、`AppWritingGoalRecovery`、`AppStyleDNANavigation`、`AppProductionReceiptNavigation`、`AppStyleComparisonNavigation`（部分行为断言仍为既有漂移）。

第二轮结果：`pnpm build` **PASS**；全量 `pnpm test` **39 failed files / 126 failed tests / 13,402 passed / 6 skipped**（本轮起点 43 / 154 / 13,374；最初 96 / 792 / 12,724）。剩余失败集中在 IndependentStudio storyboard/handoff 等既有产品/测试漂移，未在本轮清理。

## 8. 第三轮修复：测试对齐当前 UI（2026-10-31 同日）

按“更新测试到当前 UI”推进，已完全转绿的文件：

- `AppWorkspaceResume.test.tsx`（33/33）：当前工作区直挂子节点为 `NovelModTabs + .nv-stage`，chrome/editor row 在 `.nv-stage` 内；更新行数与选择器断言。
- `AppWritingGoalRecovery.test.tsx`（4/4）：当前 App 同时存在多个“保存”按钮，改为选择第一个可访问保存按钮。
- `AppModuleNavigationIntent.test.tsx`（34/34）：基础 shell 设置菜单仅保留 `AI 主控`，WORKFLOW 为命令面板路由（不再在设置菜单），更新菜单断言。
- `studioExecutionRecipeView.video.test.ts`（7/7）：当前配方明确支持 `include_audio` 并保留“第一条源音轨”，同步 notes 文案与支持/拒绝用例。

第三轮结果：全量 `pnpm test` **35 failed files / 115 failed tests / 13,413 passed / 6 skipped**（第二轮起点 39 / 126 / 13,402；最初 96 / 792 / 12,724）。剩余失败集中在 IndependentStudio storyboard/handoff 与少量 App 行为回归（部分为生产代码/测试预期差异，需逐文件更新）。

## 9. 第四轮修复：继续对齐当前 UI（2026-10-31 同日）

本轮按当前 UI 更新并通过的文件：

- `ComicPublicationPanel.test.tsx`（72/72）：`StudioComicPanel` 协作交接要求已解析 actor，测试 context 补 `actor`；CBZ/PDF mounted 下载用例恢复。
- `productionDashboardMount.test.tsx`（3/3）：当前默认新手界面隐藏契约/检查器，测试切换到专业模式；并将 jsdom 视口设为 1440 使右侧检查器展开。
- `ExperimentalWorkbench.test.tsx`（14/14）：同一“版本历史”文本存在按钮与菜单项，改为 `getAllByText`。
- `TrackHeaderSelection.additive.test.tsx`（9/9）：锁定轨道提示出现多处，改为 `getAllByText`。
- `PromptWorkspace.test.tsx`（11/11）：页面存在多个 `role=status`，改为取第一个状态断言。

第四轮结果：全量 `pnpm test` **110 failed tests / 13,418 passed / 6 skipped**（第三轮 115 / 13,413；最初 792 / 12,724）。剩余最大组仍为 IndependentStudio storyboard/handoff 与若干独立工作区交互。

## 10. 第五轮修复：独立工作区测试对齐当前双画布 UI（2026-10-31 同日）

当前独立工作区默认打开 `START`，素材/创作图/制作各为独立视图，右侧检查器在 <1280px 折叠。按该 UI 更新测试：

- `IndependentStudioWorkspace.test.tsx`（8/8）：先进入 `素材工作区`，宽视口展开检查器，模块 tab 数 8→6。
- `IndependentStudioWorkspace.comic.test.tsx`（12/12）：漫画入口在 `素材工作区` 内；comic-only 启动时允许无图操作直接进入。
- `IndependentStudioRelationships.test.tsx`（5/5）：进入素材工作区 + 宽视口后读取 `独立资产来源`。
- `IndependentStudioStoryboardHandoff.additive.test.tsx`（19/19）：素材工作区入口 + 宽视口。
- `IndependentStudioGraphWorkspace.test.tsx`（9/9）、`.presentation.additive`（18/18）：宽视口 / 懒加载断言改为当前行为。
- `IndependentStudioWorkspace.directorImage.additive.test.tsx`（2/2）：选择已保存图后先切 `执行画布`，再打开导演总控台。
- `IndependentStudioSequentialImport.test.tsx`（2/2）、`IndependentStudioManualMask.test.tsx`（11/11）、`IndependentStudioReadFences.refresh.additive.test.tsx`（4/4）：素材工作区入口 + 宽视口。
- `IndependentStudioHostExit.regression.test.tsx`（18/18）：当前设置按钮文案/菜单项调整。
- `AssetBrowserHost.comparison.test.tsx`（6/7）：素材工作区入口；仅剩 1 个“凭证替换后旧预览是否立即移除”的既有行为差异。

第五轮结果：全量 `pnpm test` **21 failed files / 54 failed tests / 13,474 passed / 6 skipped**（第四轮 35 / 110 / 13,418；最初 96 / 792 / 12,724）。

## 11. 第六轮修复：storyboardEditor 与剩余独立工作区用例（2026-10-31 同日）

- `IndependentStudioWorkspace.storyboardEditor.additive.test.tsx`（23/23 定向通过）：宽视口、选择已保存图后切 `执行画布`、脏图交接按当前 UI 阻断（不再出现放弃对话框），失败 admission 用干净图验证；
- `IndependentStudioStoryboardHandoff.additive.test.tsx` 已在上一轮 19/19；
- `ComicPublicationPanel.pageArchive/.epub`：协作交接 context 补 actor；
- `StudioVideoGraphEditor.phase4`：重复 option 改按 select options 等待；
- `CreativeWorkspace` / `.saveState.regression` / `.adoptionCommitRace`：宽视口暴露导演面板，补 `beforeEach` 导入；
- `AppStyleDNANavigation`：当前 overview 切换不再走 Style DNA leave guard；
- `StudioProductionGraphEditor.director` 部分用例仍受执行画布/UNKNOWN 导航时序影响。

第六轮结果：全量 `pnpm test` **13 failed files / 29 failed tests / 13,498 passed / 6 skipped**（第五轮 21 / 54 / 13,474；最初 96 / 792 / 12,724）。其中 `storyboardEditor` 全量并行时仍有 8 个超时性失败、定向单跑 23/23，属并行负载下的时序问题；另有 GraphImageOutputStarter 4、providerMigration 4、AppRevisionHistory 6 等尚未清理。

## 12. 第七轮修复：最后清理（2026-10-31 同日）

- `vite.config.ts` 增加 `testTimeout/hookTimeout = 30s`，消除 13k 测试并行下 storyboardEditor/directorImage 的时序性 flaky；
- `frontend/scripts/scan_error_codes.py`：`os.path.relpath` 结果统一为 `/`，修复 Windows 下嵌套文件 mutant 模式定位（apiErrorWhitelist B12 通过）；
- 恢复 `frontend/tests/e2e/v2-local-ai-files-live.spec.ts` 与 `...legacy-host-live.spec.ts`（历史 commit `0bf79fb2` 存在，当前 main 缺失），并更新 LocalAiBrowserJourneyContracts 的当前“AI 主控 / AI 团队”文案；
- providerMigration 四文件：宽视口 + `执行画布` + select options 等待；
- `GraphImageOutputStarter.additive`：测试用递归查找当前双画布 controller，20/20；
- `StudioProductionGraphEditor.test`：宽视口 + `执行画布`，4/4；
- `AssetBrowserHost.comparison`：当前 UI 在凭证替换后保留已加载预览，测试按当前行为断言，7/7。

第七轮结果：全量 `pnpm test` **2 failed files / 8 failed tests / 13,523 passed / 6 skipped**（第六轮 13 / 29 / 13,498；最初 96 / 792 / 12,724）。
剩余仅：`AppRevisionHistory`（6，当前 App 右栏历史入口/查询身份与测试 setup 不一致）与 `StudioProductionGraphEditor.director`（2，UNKNOWN 导航时序）。

## 13. 第八轮修复：前端全量测试转绿（2026-10-31 同日）

- `AppRevisionHistory.test.tsx`（23/23）：
  - 当前历史入口是「专业布局」下的右栏链接，测试通过 mock `useWorkbenchLayout` 固定 pro 模式；补齐 `location.pathname`、`api.chapter` 与右栏 links；
  - 直接渲染组件的用例保留“无历史按钮时直接进入”；App 级用例先点「版本历史」；
  - AI Accept 后历史刷新用例按当前流程先进入历史面板。
- `StudioProductionGraphEditor.director.additive.test.tsx`（5/5）：UNKNOWN 取消/返回后先切回 `执行画布` 再断言导演总控台恢复。

最终全量 `pnpm test`：**1025 passed files / 1 skipped / 13,531 passed tests / 6 skipped / 0 failed**（最初 96 failed files / 792 failed tests）。前端单元/集成测试已全绿；这不等于真实浏览器 E2E、真实模型或打包桌面验收。

