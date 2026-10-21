# PoemSeed Studio V2 · 小说前端能力台账

> **[HERMIA-FE-20261022]** · Atlas N-P0-01  
> 基线：`252e88fe` · 分支：`work/hermia-frontend-refactor-20261022`  
> 源码根：`/workspace/hr/wt/frontend/src`（只读扫码）  
> 对齐：`/workspace/hr/LUMEN_NOVEL_IA.md`（第一梯队 · FL 缺口 · 四象限）  
> 交叉：`LUMEN_NOVEL_FLOW.md` · `ATLAS_TASKBOARD.md` §0.1  
> **不是**验收完成证明。不改产品码、不 push、不碰 main、不覆写 Vera 原型 / Lumen 文档。

---

## 0. 推荐默认小说落地路径

**作者感知路径（推荐）：**

1. ModuleSwitcher → **小说（NOVEL）**（冷启动已 `useState<StudioModule>("NOVEL")`）
2. 左栏 **ChapterTree** 选章 / 新建第一章
3. 中区 **Editor** 手写；同屏检视区 **AiWritingPanel** 生成 → 预览 → **采用草稿**（确认）
4. 设定：FL `story` → StoryPlanning / WorldBuilding / 各 `*Editor`
5. 质量：FL `check` → Continuity + Pending Canon
6. 版本：FL `history` → 恢复（章节上下文；H-P0-02）

**代码冷启动现状（已改）：** `panel` 默认 `useState("write")` —— 纯写作主面（下一步 CTA）；中区 Editor + 旁路 AiWriting 常驻；`history` 经 FL / Action 打开。**小说中区不嵌入**图片/视频/剪辑画布（Atlas §0.2）。

**N-P0-02：** NOVEL 落地 + ChapterTree + Editor/`write` + AiWriting；`history` 可开；媒体/NLE 走 ModuleSwitcher（含 EDIT）；**禁止大搬家 `novel/**`**。  
**H-P0-02：** `workbench/revisionRestore.ts` 章节作用域 confirm + lifecycle epoch（含 ABA）；挂在 `ScopedRevisionHistory.onRestore`。

---

## 1. FeatureLauncher id 缺口（对齐 LUMEN_NOVEL_IA §5.2）

组件真实存在、**无同名 FL id**（今晚不瞎编 id）：

| 组件 | 今日打开 | 缺口 |
|---|---|---|
| `ChapterTree` | App 左栏直挂 | 无 `panel.open.*`；侧栏常驻 |
| `Editor` | 中区写作壳；`safePanels` 含字面 `editor` 常映射到 `history` | 无独立创作面 FL |
| `AiWritingPanel` | 检视区旁路 | **无 FL id**；≠ FL `workflow`（标签「AI 写作流程」实为 Workflow 面） |
| `StoryPlanningWorkspace` | 嵌在 `story` 规划区 | 无独立 FL |
| `WorldBuildingDashboard` + 各 `*Editor` | 经 `story` 内 kind | 无独立 FL |
| `PendingCanonReviewPanel` / `FindingReviewPanel` | 嵌在 `check` | 无独立 FL |
| `bible/*` | 现多挂 `storyboard/StoryboardWorkspacePanel`；小说设定走 `story`/World* | 无小说主路径 FL；勿造第二套 Canon |
| `EntryExperience` / `FirstUsePanel` | 入口门 | 非工作台 panel |
| `WriterRoomPanel` / `WritingFocusPanel` | `experimental` + 旗标 tab | 实验；无生产 FL |

**文案张力（Lumen §7.2）：** FL `workflow` ≠ 旁路 `AiWritingPanel`。改文案 / 改映射 / 双入口 → 待 N-P0-02。

稳定 FL 组（不改字符串）：`create` / `production` / `collaboration` / `system`。  
`create`：`creation` · `story` · `overview` · `history` · `workflow`。  
`production` 含：`check` · `adaptation` · `screenplay` · `assets` · `exports` · `knowledge` · `research`。  
`featureBridge`：FL item id → `panel.open.<id>`（capability 暂 `undetermined`）。

---

## 2. 能力台账

图例：**Completeness** = complete / partial / experimental。  
**Tier** = T1 第一梯队（Lumen §2.1）/ T2 辅助同屏 / T3 次要或外出。

| ID | Name (zh) | Source path(s) | How opened today (App panel / FeatureLauncher) | Completeness | Notes for migration |
|---|---|---|---|---|---|
| N-FE-01 | 章节树 | `novel/ChapterTree.tsx` | **无 FL id**；App 左栏 `sidebar` 直挂（~L1331+）；`onSelect→setChapter` | complete | T1 常驻；迁 shell 区勿强造 FL；N-P0-02 须 NOVEL 落地后可见 |
| N-FE-02 | 正文编辑器 | `Editor.tsx`（TipTap） | **无独立 FL**；中区 `mainWorkspace`；`safePanels` 字面 `editor`→`write` 纯写作壳；冷启动 `write` | complete | T1 主创作面；解耦 panel=history 与编辑器主 Tab（Lumen §7.1） |
| N-FE-03 | AI 写作 / 候选 | `novel/AiWritingPanel.tsx`（+ `AiContextPreviewPanel` · `AuthorRequest*`） | **无 FL id**；检视区旁路（App ~L1739+）；生成/采用/放弃由 App 编排 | complete | T1；勿与 FL `workflow` 混；迁 Action 用 `ai.*` 而非假面板；采用须确认 |
| N-FE-04 | 故事规划 | `novel/StoryPlanningWorkspace.tsx` | **无 FL id**；嵌在 `story`→`StoryDatabasePanel` ~L2140 | complete | T1；继续经 `story` 内导航即可（Lumen §7.3） |
| N-FE-05 | 故事资料库 / 设定 | `novel/StoryDatabase.tsx` + App `StoryDatabasePanel`；`WorldBuildingDashboard.tsx`；`WorldRelationshipGraph`；`WorldTimelineView` | FL **`story`**；内 kind：outline/volumes/scenes/characters/world/locations/timeline/foreshadowing/relationships/story_routes | complete（world 段 App 标 partial） | T1；协作 scope 下部分编辑器禁用；单一 Canon |
| N-FE-06 | 大纲 / 卷 | `StoryDatabase.tsx` → `OutlineEditor` · `VolumeEditor` | 经 FL **`story`** 内 kind；规划区「编辑小说大纲」 | complete | T1；无独立 FL |
| N-FE-07 | 人物/场景编辑与伏笔 | `StoryDatabase.tsx` → Character/Scene/Location/Relationship/Timeline/Foreshadowing* | FL **`story`** 内导航 ~L2164–2183 | complete | T1；与 bible 分层互补 |
| N-FE-08 | Bible 契约面 | `bible/BibleWorkspace.tsx` · `CharacterBiblePanel.tsx` · `SceneBiblePanel.tsx` | **无小说 FL**；现挂 `storyboard/StoryboardWorkspacePanel` | partial | 设定属 T1，入口偏分镜；小说路径以 story/World* 为准；徽章「状态待核实」 |
| N-FE-09 | 一致性检查 | `novel/ContinuityCheckPanel.tsx` | FL **`check`** → Panel ~L1961 | complete | T1；Canon 批准/驳回须确认 |
| N-FE-10 | 待审 Canon / 发现审核 | `novel/PendingCanonReviewPanel.tsx` · `FindingReviewPanel.tsx` | **无 FL id**；嵌在 `check` | complete | T1；随 Continuity 迁移 |
| N-FE-11 | 创作方案与风格 | `novel/CreationWorkbenchPanel.tsx`（内嵌 `AIPlanningPanel.tsx`） | FL **`creation`** / **`comments`** → ~L1971 | complete | T1；「用于写作」→ writingInputs；N-P0-02 可作 AI 入口之一 |
| N-FE-12 | 版本历史 / 恢复 | App `RevisionHistory` · `RevisionPanel.tsx` | FL **`history`**；冷启动已改为 `write`（历史经 FL） | complete | T2；H-P0-02 挂小说/章节；确认+epoch；诚实标 API |
| N-FE-13 | 小说概览 | `novel/NovelOverviewPanel.tsx` | FL **`overview`** | complete | T2；「本书是什么」详情 |
| N-FE-14 | 导入与知识审核 | `novel/NovelImportPanel.tsx` | FL **`knowledge`** | complete | T2 |
| N-FE-15 | 研究资料 | `novel/ResearchPanel.tsx` | FL **`research`** | partial | T2；后端检索缺口见 Dot |
| N-FE-16 | 导出中心 | `novel/ExportPanel.tsx` | FL **`exports`** | complete | T3 外出 |
| N-FE-17 | AI 写作流程（工作流面） | `novel/WorkflowPanel.tsx` / VisualWorkflow | FL **`workflow`** 标签「AI 写作流程」 | partial | T3；**≠ N-FE-03**；文案/映射待拍板 |
| N-FE-18 | 智能改编 | `novel/AdaptationPanel.tsx` | FL **`adaptation`**；task 深链 | complete | T3；首期不升顶层 |
| N-FE-19 | 影视剧本 | `novel/ScreenplayPanel.tsx`（+ MotionTaskWorkspace） | FL **`screenplay`** | complete | T3；非写章前置 |
| N-FE-20 | Agent 团队 | `novel/AgentTeamPanel.tsx` · `AgentActivityCenter` · `AgentJobHistory` | FL **`agents`** | complete | T3 |
| N-FE-21 | 入口 / 首用 | `novel/EntryExperience.tsx` · `FirstUsePanel.tsx` | 无 novelId / 选作品门；非 FL | complete | T2 门；可不进 panel registry |
| N-FE-22 | 写作专注（实验） | `experimental/WritingFocusPanel.tsx` · `WritingReferenceRail` | `panel=experimental` + tab `writing_focus_v2`（旗标） | experimental | T3；勿默认抢首屏 |
| N-FE-23 | 写作室（实验） | `experimental/WriterRoomPanel.tsx` | `panel=experimental` + tab `writer_room_v2` | experimental | T3；今晚不大搬家 |
| N-FE-24 | 修订智能 / 选区重写（实验） | `experimental/RevisionIntelligencePanel.tsx`（用 novel AuthorRequest*） | `experimental` + `revision_intelligence_v2`；检视区按钮（旗标） | experimental | T3；需选区已保存 |
| N-FE-25 | 冲突与草稿恢复 | `ConflictDialog.tsx` · `drafts.ts` · GenerationRecoveryPicker | 保存冲突弹窗；生成恢复回流 | complete | 与版本恢复语义分离 |

**行数：25**（≥15）。第一梯队优先：N-FE-01…11（含 bible 入口 partial）。

---

## 3. App panel 字符串 ↔ 组件速查

| `setPanel` / FL id | 渲染 |
|---|---|
| `history` | `RevisionHistory` → `RevisionPanel`（需 chapter） |
| `story` | `StoryDatabasePanel`（StoryPlanning + WorldBuilding + *Editor） |
| `overview` | `NovelOverviewPanel` |
| `check` | `ContinuityCheckPanel`（+ Finding / PendingCanon） |
| `creation` / `comments` | `CreationWorkbenchPanel` |
| `knowledge` | `NovelImportPanel` |
| `research` | `ResearchPanel` |
| `workflow` | Workflow / VisualWorkflow（≠ AiWriting） |
| `adaptation` | `AdaptationPanel` |
| `screenplay` | `ScreenplayPanel` |
| `exports` / `assets` / `agents` / … | 对应外出面 |
| `experimental` | `ExperimentalWorkbench`（WriterRoom / WritingFocus / …） |
| （壳层，非 panel） | `ChapterTree` · `Editor` · `AiWritingPanel` |

`safePanels` 节选：`audiobook, overview, editor, creation, story, history, workflow, screenplay, assets, exports, knowledge, research, agents, diagnostics, settings`。

---

## 4. H-P0 / N-P0 接线对照

| 动作 / 入口 | 注册 | 落地 |
|---|---|---|
| `panel.open.history` 等 FL id | `featureBridge` → ActionRegistry | `legacySelectPanel`；打开小说面板时 `commitStudioModule('NOVEL')` |
| ChapterTree | 侧栏常驻 | NOVEL 模块下树可见 |
| AiWritingPanel | 检视区常挂 | 不搬迁 `novel/**` |
| Ctrl+K | AppShell 全局命令（受保护） | Feature 命令搜索仅侧栏，不抢快捷键 |

### N-P0-02 同屏验收（对照 LUMEN_NOVEL_IA §3）

| 象限 | 要求 | 冷启动证据（wt） |
|---|---|---|
| ① 本书是什么 | Context / overview | 默认 NOVEL；可 FL `overview` |
| ② 章节结构 | ChapterTree 左栏 | `studioModule===NOVEL` 时侧栏常挂 |
| ③ 现在写哪 | Editor + AiWriting | TipTap + 旁路 AiWriting 常挂 |
| ④ 下一步 / 历史 | 单 CTA + history | 默认 `panel='history'`；FL/命令经 ActionRegistry 且强制 NOVEL |

---

## 5. 本夜明确不做

- 不大型搬迁 `novel/**`
- 不覆写 Vera `PoemSeed_V2_HiFi_Prototype.html` / Lumen 文档
- 不 push、不碰 main、不编造新 FL id

---

## 6. 变更记录

| 时间（Asia/Shanghai） | 说明 |
|---|---|
| 2026-10-22 | [HERMIA-FE-20261022] N-P0-01：25 行台账 · 对齐 LUMEN_NOVEL_IA · FL 缺口表 · 推荐默认落点 · 保留 H-P0 接线对照 |


---

## 交叉：工作区台账

见 `/workspace/hr/WORKSPACE_FE_INVENTORY.md`（W-P0-03 · EDIT/nle/CONTROL/PLUGIN）。
