# HERMIA 前端重构交付记录 2026-10-22（切片 M0 + M1-1）

> 角色说明：本仓库前端执行者在平台显示名为 "Grok Bot / Hermia"（任务书称 "Grok bot"）。任务书中“Hermia 负责的后端/契约/联调/独立验收”实际由用户的另一助手 ChatGPT “Dot” 承担。本轮**未修改任何后端、数据库、权限、队列、生成执行器**。
> 代码注释标记：`[HERMIA-FE-20261022]`，可 `rg HERMIA-FE-20261022` 定位全部改动。

## 1. 模型与环境
- 模型：平台显示名 Grok Bot/Hermia；实际后端模型不可核实；未执行模型切换；未使用 Opus 5.5 声明；未接入任何额外付费服务。
- OS：Linux x86_64 (kernel 6.12, 云端 VM)；Node v20.19.2（**低于** package.json engines >=22.14.0，已记录偏差）；pnpm 10.6.5（经 corepack, COREPACK_HOME 指向本地可写目录）；锁文件 frontend/pnpm-lock.yaml，`--frozen-lockfile` 安装成功，未新增依赖。
- 测试工具：vitest 2.1.9 + jsdom 25 + @testing-library/react；Playwright 配置存在但本轮**未运行浏览器测试（NOT_RUN）**，未安装浏览器。无用户 Windows/GPU 实机验证。

## 2. 基线
| 项 | 值 |
|---|---|
| 仓库 | github.com/1785235376-blip/AI-Novel-Studio（**PUBLIC**） |
| 克隆 | 完整非浅克隆；LFS 跟踪文件 4 个；无子模块/bundle 使用 |
| 252e88fed697ac57dff76b5a4657c6de723906fa | **存在**；= origin/work/studio-v2-dual-canvas-public-20261021 HEAD；tree 2ab9e256650b08fc6b2ce57854326d43b1b0e25d；2026-10-21 17:03 +0800；origin/main(7b35e4cb) 是其祖先 |
| c09ce7f7e244a2922454b6db34e5f9fa735fbb7c（最近本地源） | **远端不存在，未取得** |
| c77ea8528190d36d9110f60c436211944627a70d（未发布候选） | **远端不存在，未取得** |
| 选用基线 | 252e88fe（唯一可核验对象，且为已公开范围）。**这只是公开投影基线，不等于最新本地成果**；因此本轮不做全量迁移，只做不依赖缺失源码的核心契约切片 |
| 工作分支/worktree | work/hermia-frontend-refactor-20261022，worktree /workspace/hr/wt；**仅本地提交，未推送**（仓库公开，推送即新增公开内容，需用户批准） |

## 3. 必读资料索引
| 资料 | 状态 | 结论/影响 |
|---|---|---|
| AGENTS.md | 已读（全文） | 必须遵循 DS-v1.0；保护面改动需 DESIGN SYSTEM CHANGE REQUEST |
| .codex/skills/ai-novel-studio-ui/SKILL.md | 已读（全文；references/ 未逐一读） | 不重设计 AppShell，不移动 ModuleSwitcher |
| docs/ui/design_system.md | 已读（全文） | token/间距/布局尺寸；共享 primitives 在 frontend/src/ui |
| docs/ui/protected_ui_surfaces.md | 已读 | GlobalHeader/ModuleSwitcher/ContextBar/AppShell/侧栏壳/Inspector 壳/StatusBar 受保护 → 本切片未触碰 |
| AI_NOVEL_STUDIO_V2_MASTER_ROADMAP.txt | **未取得**（仓库内无） | 需求 ID A/B/U/Graph/CONSOLE 无法逐项映射 |
| PoemSeedStudioV2_项目记忆与Hermia续开发_20261016.txt | **未取得** | 冻结决策/公开内部边界无法核对 |
| PoemSeed_Studio_V2_Release_Scope_20261019.txt | **未取得** | DIF-01~12、IMAGE-COMIC-01~20 无法映射 |
| Dot_Full_Gap_Backlog_20261019_r2.txt | **未取得** | — |
| Studio_V2_需求对照与剩余开发清单_20261019.md | **未取得** | 能力账本无法建立（M0 的能力清单为 BLOCKED） |
| FEATURE_MATRIX / FUNCTIONAL_SURFACE_MATRIX / STUDIO_UX_PRODUCT_REPORT | **未取得**（仓库内无） | — |
| docs/delivery/POEMSEED_V2_SIX_FRONTEND_SLICES_INTEGRATION_20261019.md | **在此基线不存在** | 远端有 work/v2-six-frontend-slices-integration-20261019 分支，未在本轮核对 |
| DSH 8f245118 缺陷证据 | **未取得** | 未合入任何 DSH 内容 |
| 前端包清单/锁文件/vite/vitest/playwright 配置 | 已读 | 见 §1 |
| 实际代码：ui/moduleRegistry.tsx、ui/FeatureLauncher.tsx、src/creative、src/canvasops 目录 | 部分读取 | 现有 registry 仅 11 行（模块名+图标），面板选择由 App.tsx(2475 行) 字符串 id 驱动 |

## 4. 本轮实现（M1-1：工作台核心契约）
新增目录 frontend/src/workbench/（纯新增，未改动任何现有文件，未被 App.tsx 引用 → 零行为变化）：
- lifecycle.ts：递增 epoch（A→B→A 产生新 epoch）、确认绑定（epoch+动作+目标+版本+输入摘要）、晚到回包守卫（§11.2）。
- actions.ts：类型化动作注册；执行时重查 lifecycle/权限/可用性/确认；同动作同目标 pending 去重；await 后再检查失效；IME/输入框快捷键守卫（§7.2）。
- panels.ts：面板契约（稳定 id、能力状态、singleton/per-object 实例化必须用稳定对象引用、停靠区、dispose 钩子）（§7.1）。
- layout.ts：布局 schemaVersion=2 + v1 迁移、损坏 JSON/未知版本回默认、按 user+project+projectInstance 作用域隔离、敏感键剔除、删除面板/删除对象丢弃、窄屏折叠、重置只删布局键（§7.1）。
- featureBridge.ts：把 FeatureLauncher 现有全部 id 1:1 注册为面板 + “打开”动作（旧入口=新面板 id），能力状态暂记 undetermined。
- demoExtension.ts：§7.4 扩展证明，devOnly，生产列表不可见。
- workbench.test.ts：10 个契约测试。

## 5. 验证证据（本轮实测）
| 项 | 命令 | 结果 |
|---|---|---|
| 新增契约测试 | npx vitest run src/workbench | PASS 10/10 |
| 类型检查 | npx tsc -b | PASS exit 0 |
| 生产构建 | pnpm build | PASS exit 0（chunk 体积警告） |
| 全量单元/组件 | npx vitest run | **FAIL exit 1**：850 文件中 39 失败，11018 用例中 153 失败、11 errors |
| 浏览器/Playwright/性能/1000 节点 | — | NOT_RUN |
| Dot 独立验收 | — | NOT_RUN |

全量失败判定为**基线既有问题**（本轮只新增未被引用的文件）。抽样原因：缺失夹具 tests/fixtures/v2_graph_note_numbers.json（公开投影缺文件的证据）、jsdom 无 canvas getContext、测试与源码漂移（FeatureLauncher.css.test 期望 'onSelect={setPanel}'、IndependentStudioWorkspace 找不到“上传资产”等）。注意：Node 20 与 engines 要求不符，也可能影响结果。失败文件：
- src/assetbrowser/AssetBrowserHost.comparison.test.tsx
- src/creative/DirectorSheetExport.additive.test.tsx
- src/creative/GraphDirectorImage.integration.test.tsx
- src/creative/GraphImageOutputStarter.additive.test.tsx
- src/creative/IndependentStudioGraphWorkspace.test.tsx
- src/creative/IndependentStudioHostExit.regression.test.tsx
- src/creative/IndependentStudioIdentity.regression.test.tsx
- src/creative/IndependentStudioManualMask.test.tsx
- src/creative/IndependentStudioReadFences.refresh.additive.test.tsx
- src/creative/IndependentStudioReadFences.test.tsx
- src/creative/IndependentStudioRelationships.test.tsx
- src/creative/IndependentStudioSequentialImport.test.tsx
- src/creative/IndependentStudioStoryboardHandoff.additive.test.tsx
- src/creative/IndependentStudioWorkspace.comic.test.tsx
- src/creative/IndependentStudioWorkspace.directorImage.additive.test.tsx
- src/creative/IndependentStudioWorkspace.navigation.additive.test.tsx
- src/creative/IndependentStudioWorkspace.storyboardEditor.additive.test.tsx
- src/creative/IndependentStudioWorkspace.test.tsx
- src/creative/StoryboardSheetExport.additive.test.tsx
- src/creative/StudioProductionGraphEditor.director.additive.test.tsx
- src/creative/StudioVideoGraphEditor.phase4.test.tsx
- src/creative/StudioVideoGraphEditor.providerMigration.test.tsx
- src/creative/graphCanvasLargeNotes.helpers.test.ts
- src/creative/studioComicBootstrap.capture.test.tsx
- src/creative/studioExecutionRecipeView.video.test.ts
- src/experimental/ComicLayoutsPanel.duplicate.test.tsx
- src/experimental/ComicLayoutsPanel.framing.test.tsx
- src/experimental/ComicLayoutsPanel.geometry.test.tsx
- src/experimental/ComicLayoutsPanel.layers.test.tsx
- src/experimental/ComicLayoutsPanel.test.tsx
- src/experimental/ComicLayoutsPanel.typography.test.tsx
- src/experimental/ComicPublicationPanel.epub.test.tsx
- src/experimental/ComicPublicationPanel.pageArchive.test.tsx
- src/experimental/ComicPublicationPanel.test.tsx
- src/experimental/VoiceSubtitlePanels.test.tsx
- src/nle/TrackHeaderSelection.additive.test.tsx
- src/prompt/PromptWorkspace.test.tsx
- src/ui/FeatureLauncher.css.test.ts
- src/ui/LocalAiBrowserJourneyContracts.test.tsx

## 6. 给 Dot 的后端/契约缺口（提议，非已实现）
1. 能力声明接口：每个面板/动作需服务端能力与权限快照（proposed: GET /api/v2/capabilities?project_id=，返回 {capability_id, status, permissions[], version}），用于替换 featureBridge 中的 undetermined。
2. 权限 digest：前端 lifecycle 需要一个可比较的 permission_digest（会话或项目级），权限变化时变动；或提供权限变更事件（SSE）。
3. 项目实例身份：layout 作用域需要稳定 project_instance_id（区分同一项目不同实例/恢复副本），请确认字段名与来源。
4. 动作幂等键：前端 pending 去重之外，所有执行/采用/恢复动作需确认是否接受 Idempotency-Key 头及 UNKNOWN 状态查询端点。
5. 布局服务端持久化（可选）：当前仅 localStorage；跨设备保留需提议接口，否则文档写明“换设备不保留”。
6. 缺失夹具：tests/fixtures/v2_graph_note_numbers.json 等在公开分支缺失，请提供或说明。

## 7. 新增扩展的接入点
- 新面板：在模块 register 函数中调用 PanelRegistry.register；新动作：ActionRegistry.register（surfaces 声明出现位置）。菜单/命令搜索通过 list(surface) 读取，无需逐个改。
- 节点类型/媒介适配：下一切片定义 NodeTypeRegistry（同模式），本轮未做。

## 8. 回退
本轮只新增文件：删除 frontend/src/workbench/ 与本文件，或 git revert 本提交即可；不影响任何数据。

## 9. 未完成/下一切片
- M0 能力账本：BLOCKED（需求资料未取得）。
- M1 真实任务链迁移：未开始（未启动后端；需确定首条服务可用的链路）。
- 建议下一切片：把 FeatureLauncher + 命令搜索接到 ActionRegistry（替换 App.tsx 中的字符串分支），并以“版本历史 → 恢复版本”这条已有链路做第一条真实接线，配合 Playwright 浏览器验证。


## 10. 续：H-P0-01 / N-P0-02（同夜）
- ActionRegistry 接入 FeatureLauncher + 侧栏「搜索功能」（不抢 AppShell Ctrl+K）。
- `novelActions.ts`：小说别名动作；打开 history/creation/story/check 等强制 `commitStudioModule('NOVEL')`。
- 冷启动已是 `studioModule=NOVEL` + `panel=history` → 同屏 ChapterTree + Editor + AiWriting + RevisionPanel（LUMEN_NOVEL_IA §3）。
- 盘点：`/workspace/hr/NOVEL_FE_INVENTORY.md`（≥15 行）。
- 门禁：`vitest run src/workbench` → 15/15 PASS；`tsc -b` PASS。
- 浏览器 E2E（hermia-workbench）因首页恢复/中断未计本夜正式 PASS；H-P0-02 恢复链代码路径在小说章节 `history` 面板，待补跑。
- 未 push；未改 Vera 原型 / Lumen 文档。

## § Atlas 0.2 slice · N-P0-02 / H-P0-02 / W-P0-03（本机）

- **N-P0-02：** 冷启动 `panel=write`；小说中区不嵌媒体/NLE；`editor`→`write`。
- **H-P0-02：** `revisionRestore` 绑定 lifecycle + 章节 CAS 字段；`ScopedRevisionHistory` 恢复前后 gate。
- **W-P0-03：** ModuleSwitcher `NOVEL→IMAGE→VIDEO→AUDIO→EDIT→ASSETS`（+CONTROL/PLUGIN/WORKFLOW）；EDIT→NLE 壳；台账 `/workspace/hr/WORKSPACE_FE_INVENTORY.md`。
- **不 push。**

## § W-P0-06 · EDIT CapCut 密度 + 小说右栏（本机）

- **EDIT：** `EditNleShell` 组合 `nle/**`（监视器·工具条·缩放·TimelineWorkspacePanel hero·媒体池·ClipInspector）；不对齐引擎大重构；VIDEO≠EDIT。
- **小说：** `NovelWriterDock`（Lumen §4.4）主 CTA + 大纲/角色/AI 默认可折叠展开；Editor 加宽；可经检视器收至 0；禁空 inspector。
- 测试：workbench + EditNleShell + ModuleWorkspaceRoutes。**不 push。**

## § Atlas 0.4 overnight · FL 可达 + EDIT 加厚（本机）

- Action 别名扩：`storyPlanning` / `pendingCanon` / `workflowSurface` + `novel.focus.*`（不编新 FL id）。
- FL `workflow` 文案 →「工作流编排」。
- EDIT：双监视器（源/节目）+ 更密时间线 CSS；小说右栏大纲可点章节。
- 门禁：workbench + EditNleShell + routes **42 PASS**。**不 push。**

## § IMAGE / AUDIO / ASSETS 轻量壳 + Vera 对照（本机）

- `MediaWorkspaceShells`：IMAGE 预览 hero · AUDIO 波形/送剪辑 · ASSETS 浏览器/引用 CTA。
- VIDEO / EDIT 保持独立路由；EditNleShell / NovelWriterDock CSS 向 Vera W-P0-05（`11_workspace_edit_timeline` · `10_novel_writer*`）靠拢。
- 门禁：workbench + MediaWorkspaceShells + EditNleShell + ModuleWorkspaceRoutes。**不 push。**

## § VIDEO 三层壳 + CONTROL/PLUGIN 命令可达（本机）

- `VideoWorkspaceShell`：① 镜头脚本（Screenplay）② 画布 MultimodalDirector video ③ 导演 CTA；显式送剪辑；≠ NLE。
- `workspace.open.control|plugin|workflow|…` Action + AppShell 命令「打开插件/工作流」。
- 门禁 41 PASS。**不 push。** 余下 FL 缺口（bible 独立 id 等）需产品拍板，不瞎编。


## § N-UX-03 / H-P1-01 / H-P1-02 / N-UX-01（第一波 · 小说优先）

> [HERMIA-FE-20261022] · 基线父提交 `64a8d6cb` · **不 push**

### N-UX-03（= UX-N-01）小说满宽写作台
- `NovelWriterDock`：CTA 状态机经 `decideNovelPrimaryCta`（采用 > 一致性 > 继续写 > 选章）；大纲/角色/AI 默认可折；禁留白。
- `AppShell` ContextBar：可选 `writingContext`（书名《…》· 章 · 保存态 · 点开 overview）；省略时 legacy 标记稳定。
- 检视器折叠：`studio-inspector-open` 持久化；默认展开（通宵策略）；`<1100` 仍强制收；收起后中区变宽 CSS。
- 未改右栏默认策略（N-UX-04）；continuity 实时计数暂诚实为 0（待 query）。

### H-P1-01 `layout.mode` basic|pro
- `useWorkbenchLayout` + `loadLayout`/`saveLayout`/`layoutKey` 唯一真源。
- Header「普通|专业」；`data-shell-mode`；命令 `layout.toggleMode` / `setMode.*` / `reset`。
- basic：FL `production` 默认折叠；VIDEO 导演层默认收；MiniMap 铬条 CSS 隐藏（命令仍可）。
- pro→basic：关闭创意工作台；若在 experimental/exec/director → 回 `write`，保留 selection。
- 铬条仍终裁 **6 钮**。

### H-P1-02 能力徽章禁假绿
- `capabilityBadge.ts` / `CapabilityBadge`：`undetermined`→「状态待核实」· tone≠success；`connected` 仅明确接通。
- 检视器 dock 上下文最小切口挂徽章；测覆盖映射与禁假绿。

### N-UX-01 小说 FL 缺口最小可发现
- **不编造**新 FL id；dock「故事规划」→ `story`；AI 旁路双入口文案 vs「工作流编排」；`onOpenWorkflow` 链既有 `workflow`。
- 命令别名昨夜已齐（`novel.focus.*` / `storyPlanning` / `pendingCanon`）。

### 门禁
- `vitest run src/workbench src/ui/EditNleShell.test.tsx src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx src/ui/ModuleWorkspaceRoutes.test.tsx src/ui/MediaWorkspaceShells.test.tsx` → **80 PASS**。
- **不 push**；未改 `app/`。

## § N-UX-02 / N-UX-05 / W-UX-01 / W-UX-04（第二波 · 小说优先再媒体）

> [HERMIA-FE-20261022] · 基线父提交 `867151b4` · **不 push**

### N-UX-02 AI 双入口澄清
- dock：旁路标「生成候选」；链「打开工作流编排（非旁路）」；`data-dual-entry="ai-vs-workflow"`。
- FL `workflow` hint：「编排面 · 非 AI 写作旁路」+ `feature-item--workflow` 边线；**不新 FL id**。

### N-UX-05 第一梯队发现性
- FL 顶条「第一梯队」：`story`/`check`/`creation`/`overview`/`history`（既有 id）。
- dock 同屏快捷钮；check 标明 Continuity + PendingCanon 同屏。
- 条目 T1 标记；生产组仍含 check。

### W-UX-01 IMAGE 壳向 IA
- 预览 hero 空选 CTA：新建生成 / 加参考 / 打开漫画。
- 漫画＝图片 › 子入口（toolbar + rail）；不升顶栏；专业画布仍折叠。
- ≠ VIDEO 三层 · ≠ EDIT NLE。

### W-UX-04 VIDEO 三层加厚
- Shot 卡条（壳向演示数据）在脚本层；画布 hero 加厚；导演入口可识别（basic 默认可收）。
- 「送去剪辑」→ 显式确认壳再切 EDIT；≠ NLE 冒充。

### 门禁
- 上述 vitest 子集 → **90 PASS**。
- **不 push**；未改 `app/`。

## § W-UX-02 / W-UX-03 / W-UX-05 / X-UX-01（第三波 · 媒体壳 + 诚实空态）

> [HERMIA-FE-20261022] · 基线父提交 `b54a75a1` · **不 push**

### W-UX-02 AUDIO 壳
- 波形/配音 hero + 播放头示意；Speech / AudioGen / AudiobookManifest 焦点钮。
- 「送去剪辑」→ 显式确认壳再切 EDIT；`data-nle-tracks="0"`；≠ NLE。

### W-UX-03 ASSETS 壳
- 浏览器 hero + 血缘/版本摘要；拖入＝引用 chip；空选诚实 CTA。
- 标明 ≠ IMAGE 生图台 · ≠ EDIT 媒体池主面。

### W-UX-05 EDIT NLE 密度再抛光
- 双监视器（源/节目）+ 入出点 + 吸附开关 + 轨/片段摘要；媒体池引用角标。
- **小切口**；复用 `nle/**`，不大拆；仍只读演示壳；≠ VIDEO 假轨。

### X-UX-01 空/错/载诚实文案
- 新 `WorkspaceHonestEmpty`：no_project / no_chapter / no_track / load_failed / loading / empty_library / empty_selection。
- 六工作区无项目空态改挂该组件；小说 dock 无章 / 空大纲标 `data-honest-kind`；禁假绿。

### 门禁
- 上述 vitest 子集 → **92 PASS**。
- **不 push**；未改 `app/`。
