# 小说模块前端盘点（基线 252e88fe · [HERMIA-FE-20261022]）

> 用户优先级：小说是关键焦点。本清单对照 `/workspace/hr/wt`（= 252e88fe + 本分支 workbench 增量）静态路径，**不是**完成证明。

## 壳与入口
| 路径 | 作用 |
|---|---|
| `frontend/src/App.tsx` | NOVEL 主壳：panel 字符串切换、章节保存、FeatureLauncher、故事库挂载 |
| `frontend/src/ui/AppShell.tsx` | 全局壳 + **Ctrl+K 全局命令**（搜模块/检查面板；受保护） |
| `frontend/src/ui/FeatureLauncher.tsx` | 侧栏功能组：创作/制作/协作/系统；`story`/`history`/`workflow`/`check`… |
| `frontend/src/ui/moduleRegistry.tsx` | 模块钮含 NOVEL |
| `frontend/src/Editor.tsx` | TipTap 章节正文编辑器 |
| `frontend/src/workbench/*` | 本轮：动作/面板注册、命令搜索（按钮打开，不抢 Ctrl+K） |

## 章节 / 大纲 / 结构
| 路径 | 作用 |
|---|---|
| `frontend/src/novel/ChapterTree.tsx` | 章节树、排序、移出 |
| `frontend/src/novel/StoryDatabase.tsx` | OutlineEditor、CharacterEditor、Scene、Relationship、Timeline、Volume、WorldSummary、Foreshadowing、StoryRoute… |
| `frontend/src/novel/StoryPlanningWorkspace.tsx` | 规划并排工作区 |
| `frontend/src/novel/StoryRecordVersionEditor.tsx` | 故事记录版本 |
| `frontend/src/novel/WorldBuildingDashboard.tsx` | 世界观仪表盘 |
| `frontend/src/novel/WorldRelationshipGraph.tsx` / `WorldTimelineView.tsx` | 世界关系图 / 时间线 |

## 角色 / 圣经 / 设定
| 路径 | 作用 |
|---|---|
| `frontend/src/bible/BibleWorkspace.tsx` / `CharacterBiblePanel.tsx` / `SceneBiblePanel.tsx` | 角色/场景圣经 |
| `frontend/src/novel/CharacterAuthorPanel*`（测试旁） | 人物心智 A05 相关 UI |
| `frontend/src/novel/EntityAssetPanel.tsx` | 实体关联资产 |

## 一致性 / 写作 / Agent
| 路径 | 作用 |
|---|---|
| `frontend/src/novel/ContinuityCheckPanel.tsx` | 一致性检查 |
| `frontend/src/novel/AiWritingPanel.tsx` / `AiWritingVariants*` | AI 续写/改写 |
| `frontend/src/novel/AiContextPreviewPanel.tsx` | 上下文/隐私预览 |
| `frontend/src/novel/CreationWorkbenchPanel.tsx` | 创作方案工作台 |
| `frontend/src/novel/AdaptationPanel.tsx` | 智能改编 |
| `frontend/src/novel/ScreenplayPanel.tsx` | 影视剧本 |
| `frontend/src/novel/AgentTeamPanel.tsx` / `AgentQueuePanel.tsx` / `AgentResultReview.tsx` | Agent 团队 |
| `frontend/src/RevisionPanel.tsx` | 版本历史与恢复（H-P0-02 实链） |
| `frontend/src/prompt/PromptEditorPanel.tsx` / `usePromptWorkspace.ts` | Prompt 工作区 |

## 导入 / 导出 / 概览 / 引导
| 路径 | 作用 |
|---|---|
| `frontend/src/novel/NovelImportPanel.tsx` / `NovelOverviewPanel.tsx` | 导入与概览 |
| `frontend/src/novel/ExportPanel.tsx` | 导出 |
| `frontend/src/novel/EntryExperience.tsx` / `FirstUsePanel.tsx` / `onboarding/*` | 首次使用 |
| `frontend/src/novel/ResearchPanel.tsx` | 研究资料 |
| `frontend/src/novel/PendingCanonReviewPanel.tsx` | Canon 审核 |

## 与 IndependentStudio
`creative/IndependentStudio*` 是独立媒体工作室入口，**不是**小说正文主路径；小说主路径仍是 App + Editor + StoryDatabase。重构时不得把小说丰富度压成纯画布壳。

## 原型覆盖（HiFi）
`PoemSeed_V2_HiFi_Prototype.html` →「小说工作台」Tab：正文 / 大纲 / 角色 / 世界观 / 伏笔 / 一致性 / AI 写作，侧栏上下文与圣经入口；诚实标注已接通/部分实现。

## H-P0 接线
- `story` / `history` / `check` / `workflow` 等 FeatureLauncher id 经 `featureBridge` → ActionRegistry；命令搜索按钮可打开。
- 版本历史恢复：浏览器实链测 `hermia-workbench.spec.ts`（隔离 file + MOCK_PROVIDER）。
