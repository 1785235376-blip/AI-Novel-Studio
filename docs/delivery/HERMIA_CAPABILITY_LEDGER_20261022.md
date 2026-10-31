# HERMIA 能力账本（静态核对）— 基线 252e88fe

> [HERMIA-FE-20261022] 由 /workspace/hr/tools/ledger.py 生成。**仅静态证据**：后端 owner 文件是否存在、前端源码/测试中关键词命中文件数、后端 tests 命中数。关键词命中≠功能完成；所有条目“真实服务/目标环境/Dot 独立验收”均为 NOT_RUN。历史报告只作线索。

| ID | 需求 | 后端 owner（252e88fe） | 前端源码命中 | 前端测试命中 | 后端测试命中 | 实现状态（静态） |
|---|---|---|---|---|---|---|
| A01 | 剧情模拟 | app/experimental/story_simulator.py | 3: frontend/src/experimental/StorySimulatorPanel.tsx, frontend/src/experimental/ExperimentalWorkbench.tsx | 4 | 0 | PARTIAL（后端+前端源码存在） |
| A02 | Style DNA | app/experimental/style_analysis.py | 6: frontend/src/App.tsx, frontend/src/experimental/styleReviewClient.ts | 2 | 0 | PARTIAL（后端+前端源码存在） |
| A03 | Narrative Judge | app/experimental/narrative_judge.py | 4: frontend/src/experimental/NarrativeJudgePanel.tsx, frontend/src/experimental/NarrativeJudgeModelPanel.tsx | 5 | 0 | PARTIAL（后端+前端源码存在） |
| A04 | 语义故事图 | app/experimental/story_graph.py | 5: frontend/src/experimental/StoryGraphPanel.tsx, frontend/src/experimental/characterMindEvidence.ts | 6 | 0 | PARTIAL（后端+前端源码存在） |
| A05 | Character Mind | app/experimental/character_author_context.py | 4: frontend/src/experimental/StoryGraphPanel.tsx, frontend/src/experimental/characterMindEvidence.ts | 1 | 0 | PARTIAL（后端+前端源码存在） |
| A06 | 可解释 Model Broker | app/experimental/model_broker.py | 46: frontend/src/interop/navigation.ts, frontend/src/experimental/RevisionComparisonModelPanel.tsx | 37 | 3 | PARTIAL（后端+前端源码存在） |
| A07 | Model Benchmark | app/experimental/model_benchmark.py | 8: frontend/src/experimental/ModelBenchmarkPanel.tsx, frontend/src/experimental/ExperimentalWorkbench.tsx | 8 | 0 | PARTIAL（后端+前端源码存在） |
| A08 | Camera Grammar | app/creative/camera_language.py | 16: frontend/src/director/DirectorIntentPanel.tsx, frontend/src/director/directorWorkspaceTypes.ts | 3 | 0 | PARTIAL（后端+前端源码存在） |
| A09 | Asset Lineage | app/experimental/production_lineage.py, app/services/asset_library_service.py | 17: frontend/src/experimental/ExperimentalWorkbench.tsx, frontend/src/creative/useDirectorAuthorRecovery.ts | 20 | 3 | PARTIAL（后端+前端源码存在） |
| A10 | Research | app/experimental/research_library.py | 22: frontend/src/taskcenter/taskCenterTypes.ts, frontend/src/experimental/StoryGraphPanel.tsx | 14 | 2 | PARTIAL（后端+前端源码存在） |
| A11 | Revision Intelligence | app/experimental/revision_intelligence.py | 4: frontend/src/experimental/revisionIntelligenceClient.ts, frontend/src/experimental/ExperimentalWorkbench.tsx | 3 | 0 | PARTIAL（后端+前端源码存在） |
| A12 | OTIO/NLE Interop | app/experimental/timeline_exchange.py, app/services/studio_timeline_exchange.py | 118: frontend/src/director/directorWorkspaceTypes.ts, frontend/src/director/ShotCardPanel.tsx | 82 | 9 | PARTIAL（后端+前端源码存在） |
| A13 | Production Manifest | app/experimental/production_lineage.py | 41: frontend/src/experimental/TemplateLibraryPanel.tsx, frontend/src/experimental/ProductionReceiptReview.tsx | 35 | 14 | PARTIAL（后端+前端源码存在） |
| B01 | 模板库 | app/experimental/template_library.py | 4: frontend/src/experimental/TemplateLibraryPanel.tsx, frontend/src/experimental/ExperimentalWorkbench.tsx | 4 | 0 | PARTIAL（后端+前端源码存在） |
| B02 | Agent/Workflow SDK | app/experimental/declarative_agents.py, app/experimental/declarative_adapter_sdk.py | 8: frontend/src/novel/AgentTeamPanel.tsx, frontend/src/App.tsx | 11 | 0 | PARTIAL（后端+前端源码存在） |
| B03 | 声音导演 | app/experimental/voice_direction.py, app/experimental/audiobook.py | 2: frontend/src/experimental/ExperimentalWorkbench.tsx, frontend/src/experimental/VoiceDirectionPanel.tsx | 3 | 0 | PARTIAL（后端+前端源码存在） |
| B04 | 字幕对齐 | app/experimental/subtitle_timeline.py, app/experimental/subtitle_processing.py | 35: frontend/src/nle/TimelineWorkspacePanel.tsx, frontend/src/nle/timelineWorkspace.css | 19 | 2 | PARTIAL（后端+前端源码存在） |
| B05 | 多语言 | app/experimental/multilingual_editions.py | 10: frontend/src/experimental/TranslationMemoryPanel.tsx, frontend/src/experimental/ExperimentalWorkbench.tsx | 8 | 0 | PARTIAL（后端+前端源码存在） |
| B06 | 漫画/Webtoon | app/experimental/comic_layouts.py | 38: frontend/src/experimental/ComicPublicationPanel.tsx, frontend/src/experimental/comicAuthorArchiveClient.ts | 39 | 0 | PARTIAL（后端+前端源码存在） |
| B07 | 互动叙事 | app/experimental/interactive_story.py | 10: frontend/src/experimental/interactiveStoryPlayback.ts, frontend/src/experimental/ExperimentalWorkbench.tsx | 16 | 0 | PARTIAL（后端+前端源码存在） |
| B08 | Writer Room | app/experimental/writer_room.py | 5: frontend/src/experimental/styleReviewClient.ts, frontend/src/experimental/WriterRoomPanel.tsx | 2 | 0 | PARTIAL（后端+前端源码存在） |
| B09 | 项目分支合并 | app/experimental/structured_forks.py, app/experimental/project_forks.py | 16: frontend/src/experimental/branchComparisonReviewHelpers.ts, frontend/src/nle/timelineOps.ts | 10 | 0 | PARTIAL（后端+前端源码存在） |
| B10 | 离线同步 | app/experimental/offline_sync.py | 6: frontend/src/experimental/offlineSyncFile.ts, frontend/src/experimental/OfflineSyncReceive.tsx | 4 | 0 | PARTIAL（后端+前端源码存在） |
| U01 | 会话恢复 | — | 51: frontend/src/novel/WorkflowPanel.tsx, frontend/src/prompt/PromptEditorPanel.tsx | 26 | 1 | PARTIAL（仅前端源码定位） |
| U02 | 草稿/自动保存 | — | 40: frontend/src/collaborationGuards.ts, frontend/src/ConflictDialog.tsx | 58 | 1 | PARTIAL（仅前端源码定位） |
| U03 | 搜索/命令 | — | 1: frontend/src/App.tsx | 0 | 0 | PARTIAL（仅前端源码定位） |
| U04 | 专注/多窗 | — | 7: frontend/src/App.tsx, frontend/src/ui/AppShell.tsx | 4 | 0 | PARTIAL（仅前端源码定位） |
| U05 | 选区助手 | — | 0 | 0 | 0 | 无法判定（252e88fe 未定位；可能在未取得的 c09ce7f7/c77ea852 或归档 bundle） |
| U06 | 变更影响 | — | 42: frontend/src/experimental/executionImpact/ExecutionImpactPanel.tsx, frontend/src/creative/useStudioMediaExecution.ts | 30 | 0 | PARTIAL（仅前端源码定位） |
| U07 | 任务与审核中心 | — | 39: frontend/src/taskcenter/taskCenterTypes.ts, frontend/src/taskcenter/ReviewInbox.tsx | 19 | 0 | PARTIAL（仅前端源码定位） |
| U08 | 上下文/隐私预览 | — | 36: frontend/src/storyboard/storyboardWorkspaceContract.ts, frontend/src/experimental/styleReviewClient.ts | 40 | 16 | PARTIAL（仅前端源码定位） |
| U09 | 本地模型诊断 | — | 37: frontend/src/interop/client.ts, frontend/src/ui/ModuleWorkspaceRoutes.tsx | 29 | 10 | PARTIAL（仅前端源码定位） |
| U10 | 分场景引导 | — | 10: frontend/src/localAiDiscoveryApi.ts, frontend/src/AIEnvironmentSummary.tsx | 9 | 0 | PARTIAL（仅前端源码定位） |
| U11 | 出版审读 | — | 0 | 0 | 0 | 无法判定（252e88fe 未定位；可能在未取得的 c09ce7f7/c77ea852 或归档 bundle） |
| U12 | 错误解释/脱敏诊断 | — | 18: frontend/src/storyboard/PromptAdoptionWritePanel.tsx, frontend/src/storyboard/promptAdoptionClient.ts | 24 | 8 | PARTIAL（仅前端源码定位） |
| U13 | 中文输入/无障碍 | — | 39: frontend/src/prompt/PromptVariablesPanel.tsx, frontend/src/prompt/PromptEditorPanel.tsx | 52 | 0 | PARTIAL（仅前端源码定位） |
| U14 | 便携项目/迁移 | — | 18: frontend/src/delivery/deliveryCenter.css, frontend/src/delivery/deliveryTypes.ts | 20 | 4 | PARTIAL（仅前端源码定位） |
| U15 | 写作目标 | — | 4: frontend/src/api.ts, frontend/src/App.tsx | 6 | 0 | PARTIAL（仅前端源码定位） |
| U16 | 批量安全预检 | — | 43: frontend/src/taskcenter/taskCenterTypes.ts, frontend/src/taskcenter/taskCostReceiptHelpers.ts | 79 | 4 | PARTIAL（仅前端源码定位） |
| GRAPH-01 | 共享DAG与普通/专业UI | app/creative/graph_models.py | 23: frontend/src/canvasops/canvasOpsTypes.ts, frontend/src/canvasops/canvasOps.ts | 15 | 0 | PARTIAL（后端+前端源码存在） |
| GRAPH-02 | 平移/缩放/框选/拖动 | — | 36: frontend/src/experimental/reviewedGraphBrief.testFixture.json, frontend/src/nle/timelineOps.ts | 63 | 2 | PARTIAL（仅前端源码定位） |
| GRAPH-03 | 拖拽连线/类型端口/非法边说明 | — | 826: frontend/src/interop/client.ts, frontend/src/interop/useFloatingTutorPlacement.ts | 848 | 211 | PARTIAL（仅前端源码定位） |
| GRAPH-04 | 右键菜单与键盘命令搜索 | — | 2: frontend/src/ux.css, frontend/src/creative/GraphCanvas.tsx | 2 | 0 | PARTIAL（仅前端源码定位） |
| GRAPH-05 | 撤销重做/复制粘贴 | — | 22: frontend/src/Editor.tsx, frontend/src/experimental/CaptionTextReplace.tsx | 73 | 0 | PARTIAL（仅前端源码定位） |
| GRAPH-06 | 分组/注释/折叠/MiniMap/对齐 | — | 8: frontend/src/creative/graphCanvas.css, frontend/src/creative/MediaCardViewport.tsx | 11 | 0 | PARTIAL（仅前端源码定位） |
| GRAPH-07 | 键盘节点端口导航/错误定位 | — | 14: frontend/src/taskcenter/TaskCenter.tsx, frontend/src/creative/MediaCardViewport.tsx | 4 | 0 | PARTIAL（仅前端源码定位） |
| GRAPH-08 | 图版本/自动草稿/重开恢复 | — | 284: frontend/src/bible/bibleFixtures.testFixture.ts, frontend/src/bible/BibleDimensionRow.tsx | 385 | 19 | PARTIAL（仅前端源码定位） |
| GRAPH-09 | 模板导入导出/断开删除影响 | — | 87: frontend/src/style.css, frontend/src/bible/bibleWorkspace.css | 28 | 5 | PARTIAL（仅前端源码定位） |
| GRAPH-10 | 大图虚拟化/LOD 基准 | — | 1: frontend/src/creative/mediaCanvasGeometry.ts | 5 | 0 | PARTIAL（仅前端源码定位） |
| GRAPH-11 | 输入节点 | app/creative/graph_models.py | 437: frontend/src/interop/useFloatingTutorPlacement.ts, frontend/src/interop/LocalTutorIntegration.tsx | 429 | 21 | PARTIAL（后端+前端源码存在） |
| GRAPH-12 | 处理节点 | app/creative/graph_models.py | 37: frontend/src/taskcenter/taskCenterTypes.ts, frontend/src/api.ts | 44 | 49 | PARTIAL（后端+前端源码存在） |
| GRAPH-13 | 控制节点 | app/creative/graph_models.py | 145: frontend/src/director/DirectorIntentPanel.tsx, frontend/src/director/directorWorkspaceClient.ts | 145 | 22 | PARTIAL（后端+前端源码存在） |
| GRAPH-14 | 输出节点 | app/creative/graph_models.py | 208: frontend/src/storyboard/storyboardWorkspaceTypes.ts, frontend/src/storyboard/storyboardWorkspaceContract.ts | 179 | 43 | PARTIAL（后端+前端源码存在） |
| GRAPH-15 | 类型端口集 | app/creative/graph_models.py | 16: frontend/src/canvasops/ConnectionAdvisorPanel.tsx, frontend/src/canvasops/canvasOpsTypes.ts | 8 | 0 | PARTIAL（后端+前端源码存在） |
| GRAPH-16 | 无导演单节点/图执行 | — | 74: frontend/src/interop/LocalTutorIntegration.tsx, frontend/src/novel/AssetTaskExecutionPanel.tsx | 144 | 43 | PARTIAL（仅前端源码定位） |
| GRAPH-17 | 执行前预览成本隐私覆盖 | — | 68: frontend/src/experimental/declarativeAgentsClient.ts, frontend/src/experimental/ChangeImpactPanel.tsx | 102 | 7 | PARTIAL（仅前端源码定位） |
| GRAPH-18 | 依赖执行/有界并发 | — | 115: frontend/src/storyboard/storyboardWorkspaceContract.ts, frontend/src/storyboard/PromptAdoptionPanel.tsx | 182 | 48 | PARTIAL（仅前端源码定位） |
| GRAPH-19 | VRAM 冲突队列 | — | 13: frontend/src/localAiDiscoveryApi.ts, frontend/src/modelcenter/modelCenterContract.ts | 10 | 2 | PARTIAL（仅前端源码定位） |
| GRAPH-20 | 缓存绑定与失效 | — | 48: frontend/src/interop/chapterIds.ts, frontend/src/taskcenter/useTaskCostReceipt.ts | 69 | 12 | PARTIAL（仅前端源码定位） |
| GRAPH-21 | 局部重跑/暂停/重试/取消 | — | 105: frontend/src/interop/entry.tsx, frontend/src/storyboard/PromptAdoptionWritePanel.tsx | 194 | 20 | PARTIAL（仅前端源码定位） |
| GRAPH-22 | 真实进度/缺能力/错误导航 | — | 33: frontend/src/taskcenter/taskCenterTypes.ts, frontend/src/taskcenter/TaskStatusSummary.tsx | 42 | 16 | PARTIAL（仅前端源码定位） |
| CONSOLE-01 | 导演总控节点携带目标 | app/creative/director_intent.py | 8: frontend/src/creative/GraphDirectorStoryboardHandoff.tsx, frontend/src/creative/useStudioGraphEditor.tsx | 18 | 0 | PARTIAL（后端+前端源码存在） |
| CONSOLE-02 | 多目标来源化建议 | app/creative/director_intent.py | 16: frontend/src/storyboard/storyboardWorkspaceTypes.ts, frontend/src/storyboard/storyboardWorkspaceContract.ts | 35 | 1 | PARTIAL（后端+前端源码存在） |
| CONSOLE-03 | 折叠卡片/展开 Console | app/creative/director_intent.py | 3: frontend/src/creative/GraphDirectorCompareDeck.tsx, frontend/src/creative/StudioGraphDirectorConsole.tsx | 2 | 0 | PARTIAL（后端+前端源码存在） |
| CONSOLE-04 | 多导演/子导演 | app/creative/director_intent.py | 0 | 0 | 0 | PARTIAL（仅后端源码定位；前端入口未定位） |
| CONSOLE-05 | 提案→预检→审阅→回执 | app/creative/director_intent.py | 64: frontend/src/storyboard/storyboardWorkspaceTypes.ts, frontend/src/storyboard/storyboardWorkspaceContract.ts | 90 | 17 | PARTIAL（后端+前端源码存在） |
| CONSOLE-06 | 断开/移除导演影响 | app/creative/director_intent.py | 2: frontend/src/creative/GraphDirectorSourceImpact.tsx, frontend/src/creative/GraphDirectorConsole.tsx | 1 | 0 | PARTIAL（后端+前端源码存在） |
| DIF-01 | Story Kernel | — | 0 | 0 | 0 | 无法判定（252e88fe 未定位；可能在未取得的 c09ce7f7/c77ea852 或归档 bundle） |
| DIF-02 | Impact Engine | — | 42: frontend/src/storyboard/StoryFactUsagePanel.tsx, frontend/src/storyboard/StoryFactDownstreamImpact.tsx | 30 | 0 | PARTIAL（仅前端源码定位） |
| DIF-03 | Identity Studio | — | 0 | 0 | 0 | 无法判定（252e88fe 未定位；可能在未取得的 c09ce7f7/c77ea852 或归档 bundle） |
| DIF-04 | Semantic Rebuild | — | 8: frontend/src/Editor.tsx, frontend/src/experimental/changeImpactDecisionContract.ts | 9 | 0 | PARTIAL（仅前端源码定位） |
| DIF-05 | Scene Twin/3D | — | 21: frontend/src/creative/StudioModelDepthExport.tsx, frontend/src/creative/modelDepthWire.testFixture.json | 14 | 0 | PARTIAL（仅前端源码定位） |
| DIF-06 | Performance Director | — | 21: frontend/src/director/directorWorkspaceTypes.ts, frontend/src/director/directorWorkspaceFixtures.testFixture.ts | 23 | 0 | PARTIAL（仅前端源码定位） |
| DIF-07 | Studio QA | — | 0 | 0 | 0 | 无法判定（252e88fe 未定位；可能在未取得的 c09ce7f7/c77ea852 或归档 bundle） |
| DIF-08 | Model Lab | — | 8: frontend/src/modelcenter/modelCenterContract.ts, frontend/src/api.ts | 8 | 0 | PARTIAL（仅前端源码定位） |
| DIF-09 | 多模态 Style DNA | — | 6: frontend/src/experimental/styleReviewClient.ts, frontend/src/experimental/ExperimentalWorkbench.tsx | 2 | 0 | PARTIAL（仅前端源码定位） |
| DIF-10 | Storyverse | — | 10: frontend/src/experimental/interactiveStoryPlayback.ts, frontend/src/experimental/ExperimentalWorkbench.tsx | 16 | 0 | PARTIAL（仅前端源码定位） |
| DIF-11 | Audience Lab | — | 7: frontend/src/experimental/AudienceReviewPanel.tsx, frontend/src/experimental/audienceReviewClient.ts | 2 | 0 | PARTIAL（仅前端源码定位） |
| DIF-12 | Production Passport | — | 2: frontend/src/experimental/ProductionPassportSidecar.tsx, frontend/src/experimental/ProductionLineagePanel.tsx | 1 | 0 | PARTIAL（仅前端源码定位） |
| IMAGE-COMIC-01 | 子入口与独立项目 | app/experimental/comic_layouts.py | 38: frontend/src/experimental/ComicPublicationPanel.tsx, frontend/src/experimental/comicAuthorArchiveClient.ts | 39 | 0 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-02 | 工程层级 | app/experimental/comic_layouts.py | 23: frontend/src/experimental/ComicImageFramingEditor.tsx, frontend/src/experimental/comicOraClient.ts | 31 | 0 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-03 | 分集与分格策划 | app/experimental/comic_layouts.py | 0 | 0 | 0 | PARTIAL（仅后端源码定位；前端入口未定位） |
| IMAGE-COMIC-04 | 分格排版画布 | app/experimental/comic_layouts.py | 5: frontend/src/experimental/ExperimentalWorkbench.tsx, frontend/src/creative/StudioComicTimelineHandoff.tsx | 15 | 0 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-05 | 逐格生成与批处理 | app/experimental/comic_layouts.py | 64: frontend/src/taskcenter/taskCenterTypes.ts, frontend/src/taskcenter/ReviewInbox.tsx | 57 | 5 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-06 | 角色服装一致性 | app/experimental/comic_layouts.py | 188: frontend/src/interop/useFloatingTutorPlacement.ts, frontend/src/interop/LocalTutorIntegration.tsx | 219 | 48 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-07 | 构图姿态空间 | app/experimental/comic_layouts.py | 79: frontend/src/storyboard/PromptAdoptionWritePanel.tsx, frontend/src/storyboard/promptAdoptionClient.ts | 133 | 23 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-08 | 局部重绘/图层修稿 | app/experimental/comic_layouts.py | 44: frontend/src/storyboard/PromptAdoptionPanel.tsx, frontend/src/prompt/PromptWorkspace.tsx | 40 | 4 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-09 | 可编辑气泡对白 | app/experimental/comic_layouts.py | 10: frontend/src/experimental/ComicLayoutsPanel.tsx, frontend/src/experimental/comicLayers.ts | 26 | 2 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-10 | 拟声字与特效 | app/experimental/comic_layouts.py | 5: frontend/src/experimental/AudiobookPanel.tsx, frontend/src/api.ts | 2 | 0 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-11 | 线稿与上色 | app/experimental/comic_layouts.py | 1: frontend/src/creative/timelineTransferReviewHelpers.ts | 0 | 0 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-12 | 跨格连贯性检查 | app/experimental/comic_layouts.py | 39: frontend/src/director/directorWorkspaceTypes.ts, frontend/src/director/ContinuityPanel.tsx | 24 | 13 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-13 | 页漫/条漫双模式 | app/experimental/comic_layouts.py | 5: frontend/src/experimental/experimentalNavigation.tsx, frontend/src/experimental/ComicLayoutsPanel.tsx | 19 | 0 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-14 | 节奏与翻页 | app/experimental/comic_layouts.py | 36: frontend/src/storyboard/storyboardWorkspaceTypes.ts, frontend/src/storyboard/storyboardWorkspaceContract.ts | 27 | 1 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-15 | 图层与 ORA 交换 | app/experimental/comic_layouts.py | 191: frontend/src/interop/client.ts, frontend/src/interop/useFloatingTutorPlacement.ts | 265 | 64 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-16 | 多语言排字 | app/experimental/comic_layouts.py | 24: frontend/src/director/directorWorkspace.css, frontend/src/experimental/experimental.css | 5 | 0 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-17 | 局部重排重制 | app/experimental/comic_layouts.py | 1: frontend/src/experimental/workspaceResume.css | 1 | 0 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-18 | 导出与印刷 | app/experimental/comic_layouts.py | 7: frontend/src/experimental/ComicPublicationPanel.tsx, frontend/src/experimental/comicLayoutsClient.ts | 8 | 2 | PARTIAL（后端+前端源码存在） |
| IMAGE-COMIC-19 | 动态漫转接 | app/experimental/comic_layouts.py | 0 | 0 | 0 | PARTIAL（仅后端源码定位；前端入口未定位） |
| IMAGE-COMIC-20 | 漫画审稿 Agent | app/experimental/comic_layouts.py | 10: frontend/src/experimental/WriterRoomPanel.tsx, frontend/src/experimental/ModelBenchmarkPanel.tsx | 8 | 2 | PARTIAL（后端+前端源码存在） |

汇总：共 99 项；PARTIAL 94；无法判定 5

验证列：静态检查 PASS（文件存在）；单元/组件见全量测试日志；模拟接口/真实服务/目标环境/独立验收 全部 NOT_RUN。阻断：c09ce7f7/c77ea852 源码缺失 → 所有“无法判定”项。
