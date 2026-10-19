# PoemSeed Studio V2 开发者源码导航

本入口按 `ca029891abc51265b2f483414316c30ddfdacd08` 的实际源码整理。后续阅读应先核对集成方提供的提交与本地 `git rev-parse HEAD`；仓库默认分支、历史报告中的分支名和验收数字不能代替当前产品树。本文提供文件入口与运行方法，贡献及审核要求见 [贡献与 PR 审核指南](contribution-review.md)。

V2 继续使用现有应用、服务及数据 owner；这里的“模块”是源码职责划分，不是可独立安装的产品包。第三方市场后置。下表的 owner 指运行时负责数据或操作的服务，不指定人员，也不改变仓库审核权限。

已有说明优先复用：[项目 README](../../README.md)、[V2 开发索引](../v2/README.md)、[V2 架构](../../AI_NOVEL_STUDIO_V2_ARCHITECTURE.md)、[工作区操作契约](../v2/studio-workspace-operations.md)、[当前范围核对](../v2/V2_SCOPE_RECONCILIATION_20261019_R2.md)。历史报告的结论只适用于其记录的源码和执行环境。

本目录已有专题说明，详细协议与阶段证据继续从原文阅读：

| 专题 | 复用入口与阅读顺序 |
| --- | --- |
| 导演 IMAGE V3 | [foundation](director_image_foundation_v3.md) → [本地 vision runtime](local_vision_runtime_v3.md) → [Job / Broker](director_image_jobs_v3.md) → [人审与采用](director_image_adoption_v1.md) → [mounted 工作流](director_image_mounted_v3.md)。前几份描述当时未挂载的阶段；当前是否挂载需核对最后一份及实际 router，不把历史限制直接当作当前结论。 |
| 本地读者对比 | [audience_review_local_v1.md](audience_review_local_v1.md)：原 NarrativeJudge / review owner、作者输入与估算的边界。 |
| 互动叙事 Ink 交换 | [storyverse_ink_exchange_v1.md](storyverse_ink_exchange_v1.md)：有限文本子集、原 InteractiveStoryService 与原来源/导出 owner，不代表完整 Ink 支持。 |

## 从入口追到实际写入

| 阅读顺序 | 文件入口 | 需要确认的职责 |
| --- | --- | --- |
| 后端装配 | [app/main.py](../../app/main.py)、[app/dependencies.py](../../app/dependencies.py) | FastAPI 生命周期、中间件、`/api` 与 `/api/v1` 别名、核心服务依赖。导入会初始化部分宿主与数据对象，先隔离运行环境。 |
| 功能装配与路由 | [app/api.py](../../app/api.py)、[app/experimental/api.py](../../app/experimental/api.py)、[app/creative/api.py](../../app/creative/api.py)、[workspace_api.py](../../app/creative/workspace_api.py) | 找到真正挂载的 router、父级授权回调和注入的原服务，不能只看一个端点函数。 |
| 领域与存储 | [repositories/factory.py](../../app/repositories/factory.py)、[experimental/store.py](../../app/experimental/store.py)、[creative/project_store.py](../../app/creative/project_store.py) | 核心 File/PostgreSQL 选择、扩展 scope 存储与 Creative 项目 incarnation 边界。未知 backend 会拒绝，PostgreSQL 不会静默回退到 File。 |
| 前端装配 | [main.tsx](../../frontend/src/main.tsx)、[App.tsx](../../frontend/src/App.tsx)、[ModuleWorkspaceRoutes.tsx](../../frontend/src/ui/ModuleWorkspaceRoutes.tsx) | 启动、会话与工作区选择、模块挂载和导航。进入某个页面不代表已获执行权限。 |
| 请求与交互 | [api.ts](../../frontend/src/api.ts)、[creative/client.ts](../../frontend/src/creative/client.ts)、[studioClient.ts](../../frontend/src/creative/studioClient.ts) 及相邻 client/controller | 先核对当前模块的客户端、严格 DTO 和状态控制器，再看 JSX。避免另起请求通道或重复保存领域状态。 |

## 模块与原 owner 地图

| 领域 / 前端入口 | 后端入口与原 owner | 修改时保留的边界 |
| --- | --- | --- |
| 小说编辑：[Editor.tsx](../../frontend/src/Editor.tsx)、[store.ts](../../frontend/src/store.ts) | [NovelService](../../app/services/novel_service.py)、[ChapterService](../../app/services/chapter_service.py)、[agent_job_service.py](../../app/services/agent_job_service.py) | 小说、章节、生成草稿与 Accept 由原核心服务写入；Creative 文档不会替代章节 owner。 |
| 协作、权限与修订：[CollaborationPanels.tsx](../../frontend/src/CollaborationPanels.tsx)、[RevisionPanel.tsx](../../frontend/src/RevisionPanel.tsx) | [collaboration_api.py](../../app/collaboration_api.py)、[membership_authorization_service.py](../../app/services/membership_authorization_service.py)、[trusted_sessions.py](../../app/trusted_sessions.py)、[document_revision.py](../../app/document_revision.py) | 实际身份、成员关系、scope、版本冲突和审计保持原链路；前端权限展示仅供提示。 |
| Creative / 独立工作区：[CreativeWorkspace.tsx](../../frontend/src/creative/CreativeWorkspace.tsx)、[IndependentStudioWorkspace.tsx](../../frontend/src/creative/IndependentStudioWorkspace.tsx) | [CreativeService](../../app/creative/service.py)、[IndependentWorkspaceService](../../app/creative/workspace.py)、[models.py](../../app/creative/models.py) | 文档、来源、激活入口与项目 incarnation；`NEUTRAL_STUDIO` 是原服务确认的项目入口类型。 |
| Bible / Prompt：[BibleWorkspace.tsx](../../frontend/src/bible/BibleWorkspace.tsx)、[PromptWorkspace.tsx](../../frontend/src/prompt/PromptWorkspace.tsx) | [BibleWorkspaceService](../../app/creative/bible_workspace.py)、[PromptWorkspaceService](../../app/creative/prompt_workspace.py)、[prompt_authoring.py](../../app/creative/prompt_authoring.py)、[prompt_adoption.py](../../app/creative/prompt_adoption.py) | 事实、Prompt 修订、独立草稿和显式采用分开；读历史正文不应改变当前选中版本或自动采用。 |
| 导演 / 分镜：[DirectorWorkspace.tsx](../../frontend/src/director/DirectorWorkspace.tsx)、[StoryboardWorkspacePanel.tsx](../../frontend/src/storyboard/StoryboardWorkspacePanel.tsx) | [director_workspace.py](../../app/creative/director_workspace.py)、[director_binding.py](../../app/creative/director_binding.py)、[director_lifecycle.py](../../app/creative/director_lifecycle.py)、[storyboard.py](../../app/creative/storyboard.py)，落回 Creative 原 owner | 目标、场景、镜头、候选与审核各有来源和版本；导演读投影不能生成另一套 run 或审批记录。 |
| Graph / Canvas：[useStudioGraphEditorController.ts](../../frontend/src/creative/useStudioGraphEditorController.ts)、[studioGraphEditorView.tsx](../../frontend/src/creative/studioGraphEditorView.tsx)、[useStudioGraphRunController.ts](../../frontend/src/creative/useStudioGraphRunController.ts) | [CreativeGraphService](../../app/creative/graph.py)、[graph_execution.py](../../app/creative/graph_execution.py)、[graph_media_execution.py](../../app/creative/graph_media_execution.py)、[canvas_views.py](../../app/creative/canvas_views.py) | 图定义、run、媒体 job、画布视图各守原 owner。画布位置与分组不能成为执行或采用证明。 |
| 图像：[useStudioMediaExecution.ts](../../frontend/src/creative/useStudioMediaExecution.ts)、[StudioMediaExecutionPanel.tsx](../../frontend/src/creative/StudioMediaExecutionPanel.tsx) | [ImageJobService](../../app/services/image_job_service.py)、[studio_image_execution.py](../../app/services/studio_image_execution.py)、[asset_providers.py](../../app/asset_providers.py) | 原 job、Provider 配置、私有候选和审核保留；生产层适配器不新增队列或凭据库。 |
| 音频：同一媒体 controller、[StudioTimelineEditor.tsx](../../frontend/src/creative/StudioTimelineEditor.tsx) | [audio_production_store.py](../../app/audio_production_store.py)、[AudiobookService](../../app/services/audiobook_service.py)、[studio_audio_execution.py](../../app/services/studio_audio_execution.py) | standalone 音频和扩展有声书入口需沿各自原调用链核对；不能把同名能力当成同一状态库。 |
| 视频 / 时间线 / NLE：[TimelineWorkspacePanel.tsx](../../frontend/src/nle/TimelineWorkspacePanel.tsx)、[useStudioTimelineEditor.ts](../../frontend/src/creative/useStudioTimelineEditor.ts)、[studioTimelineTypes.ts](../../frontend/src/creative/studioTimelineTypes.ts) | [ProductionExecutionService](../../app/creative/production_execution.py) 保存原 scope 中的可编辑时间线；[VideoAssemblyService](../../app/services/video_assembly_service.py)、[studio_video_execution.py](../../app/services/studio_video_execution.py)、[studio_timeline_export.py](../../app/services/studio_timeline_export.py) 执行原 job | 时间线保存、渲染、导出与人审分开；导入/导出格式见 [时间线与文本归档](../v2/text-archive-timeline-export.md)。 |
| 资产 / 3D 参考：[AssetBrowserPanel.tsx](../../frontend/src/assetbrowser/AssetBrowserPanel.tsx)、[StudioModelReferencePanel.tsx](../../frontend/src/creative/StudioModelReferencePanel.tsx) | [AssetLibraryService](../../app/services/asset_library_service.py)、IndependentWorkspaceService、[model_reference_glb.py](../../app/creative/model_reference_glb.py)、[model_reference_scene.py](../../app/creative/model_reference_scene.py) | 资产字节、版本、摘要与来源由原服务核对；GLB/场景参考能力不等于通用 3D 制作运行时。 |
| 漫画：[StudioComicPanel.tsx](../../frontend/src/creative/StudioComicPanel.tsx)、[StudioComicTimelineHandoff.tsx](../../frontend/src/creative/StudioComicTimelineHandoff.tsx) | [comic_layouts.py](../../app/experimental/comic_layouts.py)、[comic_ora.py](../../app/experimental/comic_ora.py)、[comic_timeline_handoff.py](../../app/experimental/comic_timeline_handoff.py) | 排版、ORA staging 与时间线 handoff 继续复用各自原 owner；恢复不应重新生成或重复创建时间线。 |
| 生产总览：[ProductionDashboard.tsx](../../frontend/src/production/ProductionDashboard.tsx) | [ProductionWorkflowService](../../app/creative/production_workflow.py) | 总览读取原模块状态，保存意图仍走原工作区偏好；不从统计推导候选已批准或执行可用。见 [生产工作流](../v2/production-workflow-phase7.md)。 |
| 任务 / 交付：[TaskCenter.tsx](../../frontend/src/taskcenter/TaskCenter.tsx)、[DeliveryCenterPanel.tsx](../../frontend/src/delivery/DeliveryCenterPanel.tsx) | [jobs.py](../../app/jobs.py)、各模态原 job owner、[ExportJobService](../../app/services/export_job_service.py) | 任务面板聚合不同 owner；定位、取消、候选审核和导出仍回原服务。见 [任务 owner 导航](../v2/task-owner-navigation-20261016.md)。 |
| 研究 / OCR：先从 [experimental/api.ts](../../frontend/src/experimental/api.ts) 和具体研究面板的调用查起 | [research_library.py](../../app/experimental/research_library.py)、[NativeResearchOCRCoordinator](../../app/experimental/research_native_ocr.py)、[research_ocr_execution.py](../../app/experimental/research_ocr_execution.py) | 来源导入、OCR job、候选文字、引用和 reviewed 导出各保留来源 pin；OCR 运行仍经原 broker/Host。 |
| 模型中心 / 本地发现：[ModelCenterPanel.tsx](../../frontend/src/modelcenter/ModelCenterPanel.tsx)、[localAiDiscoveryOwner.ts](../../frontend/src/localAiDiscoveryOwner.ts) | [ModelCenterService](../../app/model_center/service.py)、[discovery.py](../../app/model_center/discovery.py)、[discovery_authority.py](../../app/model_center/discovery_authority.py) | 发现、注册、启用、运行时可达与可执行分别核对；被动发现不能直接提升成 READY 或自动安装启动。 |
| DesktopHost / 互操作：[packagedHost.ts](../../frontend/src/packagedHost.ts)、[localHostSession.ts](../../frontend/src/localHostSession.ts) | [app/packaging](../../app/packaging)、[desktop-host](../../desktop-host)、[app/local_interop/host.py](../../app/local_interop/host.py)、[local_interop_desktop](../../local_interop_desktop)、[local_interop_protocol](../../local_interop_protocol) | 沿既有 Host、握手、会话与协议查找；参见 [V2 启动 profile](../v2/packaged-launch-profile.md)、[互操作安全](../../LOCAL_INTEROP_SECURITY.md)。 |

现有声明式资源入口是 [plugin_catalog.py](../../app/plugin_catalog.py)、[plugin_contracts.py](../../app/plugin_contracts.py)、[plugin_discovery.py](../../app/plugin_discovery.py)。阅读这些源码不代表 V2 要拆安装包、开放第三方市场或扩大资源执行权限。

## 常见改动先找哪里

| 想改的行为 | 首先阅读 | 继续追到哪里 |
| --- | --- | --- |
| 导演 run 总览、场景定位和查看进度 | [GraphDirectorRunOverview.tsx](../../frontend/src/creative/GraphDirectorRunOverview.tsx)、[directorRunOverview.ts](../../frontend/src/creative/directorRunOverview.ts)、[DirectorSceneScopePanel.tsx](../../frontend/src/creative/DirectorSceneScopePanel.tsx) | 原 graph run controller / client 与后端 CreativeGraphService；区分导航、预览和执行。 |
| Prompt 查找、历史正文、采用提示 | [PromptEditorPanel.tsx](../../frontend/src/prompt/PromptEditorPanel.tsx)、[PromptVersionHistory.tsx](../../frontend/src/prompt/PromptVersionHistory.tsx)、[PromptAdoptionPanel.tsx](../../frontend/src/storyboard/PromptAdoptionPanel.tsx) | 对应 Prompt client、`prompt_workspace.py` / `prompt_adoption.py`；先排除 scope、版本和迟到响应混入。 |
| 资产列表、过滤与 producer 展示 | [assetbrowser](../../frontend/src/assetbrowser)、[studioClient.ts](../../frontend/src/creative/studioClient.ts) | IndependentWorkspaceService、AssetLibraryService；展示文字不能替代 server-owned origin 或 owner 证明。 |
| NLE 选择、分割、移动、裁切 | [timelineOps.ts](../../frontend/src/nle/timelineOps.ts)、[clipSelection.ts](../../frontend/src/nle/clipSelection.ts)、[useStudioTimelineEditor.ts](../../frontend/src/creative/useStudioTimelineEditor.ts) | [studioProductionClient.ts](../../frontend/src/creative/studioProductionClient.ts)、`production_execution_models.py`、`production_execution.py`；最终保存必须核对原版本和来源。 |
| 新增图节点或媒体参数 | [graph_models.py](../../app/creative/graph_models.py)、[graph_image_nodes.py](../../app/creative/graph_image_nodes.py)、[graph_video_nodes.py](../../app/creative/graph_video_nodes.py) | `graph_media_execution.py` → ProductionExecutionService → 原模态 owner；同时查看相应 client 严格解码和参数 UI。 |
| 改“加载 / 无数据 / 拒绝 / 恢复”状态 | 当前模块 controller 与相邻回归测试 | 检查 `AbortController`、请求 epoch、项目/branch/会话 identity、卸载和 dirty guard；不要仅改空态 JSX。 |
| API 字段、路由或发现能力 | 实际挂载 router、请求/响应模型和相应 frontend client | [API_CATALOG.md](../../API_CATALOG.md)、[目录来源说明](../v2/current-api-catalog-20261018.md)；共享目录产物由集成方统一更新，不能手填历史验证结果。 |
| 壳层、token、通用控件或导航位置 | [design_system.md](../ui/design_system.md)、[protected_ui_surfaces.md](../ui/protected_ui_surfaces.md)、[UI 技能](../../.codex/skills/ai-novel-studio-ui/SKILL.md) | 复用 AppShell / ModuleWorkspace 合约。受保护设计系统调整走现有 Design System Change Request。 |

## 开发运行：先隔离，再导入应用

以下为 Windows PowerShell、自己的 worktree 根目录下的示例，端口需先确认空闲。这里只说明命令，不表示本文执行过依赖安装、应用或模型运行。工具要求来自 [pyproject.toml](../../pyproject.toml) 与 [frontend/package.json](../../frontend/package.json)：Python 3.11+；Node `>=22.14.0 <25`；pnpm `10.6.5`。已有 `scripts/dev.ps1` 使用较旧的 Node 提示和默认端口，多人开发时优先使用下面的隔离入口。

准备本 worktree 的依赖；pnpm 应已由开发环境提供：

```powershell
python -m venv .venv
$py = (Resolve-Path .venv\Scripts\python.exe).Path
& $py -m pip install -c .github/ci/python-constraints.txt -e '.[dev]'
pnpm --dir frontend install --frozen-lockfile
```

漫画、OTIO、字体构建、系统凭据集成等可选依赖分别声明在 `pyproject.toml` 的 `comic` / `otio` / `fontbuild` / `vault` extras；只按改动需要准备。FFmpeg、真实 PostgreSQL、系统浏览器、DesktopHost、模型运行时另有各自前置条件，普通 File/mock 编辑不要求安装或启动它们。

终端 A 使用原检查脚本的隔离环境函数，再导入 Uvicorn / 应用；这避免直接导入时触碰日常使用的宿主 profile：

```powershell
$py = (Resolve-Path .venv\Scripts\python.exe).Path
$env:PYTHONUTF8 = '1'
$env:FRONTEND_ORIGIN = 'http://127.0.0.1:5187'
$env:EXPERIMENTAL_FEATURES = 'narrative_production_v2'
@'
from pathlib import Path
import os
from scripts.run_v2_checks import isolated_environment
root = Path.cwd()
os.environ.update(isolated_environment(root, root / ".runtime/dev/api"))
import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8127)
'@ | & $py -
```

这个 helper 的实现在 [run_v2_checks.py](../../scripts/run_v2_checks.py)：为数据、Local/Roaming、用户目录与 XDG 路径分配独立目录，使用 File、memory vault、mock，关闭 cloud、packaged 与 collaboration runtime。该开发入口不能替代真实 Host、成员权限或媒体执行验收。它直接运行服务，不生成检查脚本的测试回执。

终端 B 同样从该 worktree 根开始：

```powershell
$env:V061_API_URL = 'http://127.0.0.1:8127'
Set-Location frontend
pnpm dev --host 127.0.0.1 --port 5187 --strictPort
```

页面为 `http://127.0.0.1:5187`，API 文档为 `http://127.0.0.1:8127/docs`。代理变量和端口配置见 [vite.config.ts](../../frontend/vite.config.ts)。停止前台服务用各自终端的 Ctrl+C；变更端口时同时调整 `FRONTEND_ORIGIN`、`V061_API_URL` 和浏览器测试目标。

功能开关由 [experimental/flags.py](../../app/experimental/flags.py) 的 `EXPERIMENTAL_FEATURES` 明确列出并校验依赖；没有 wildcard 开启。更多功能应按原依赖配置，不为绕过 401/403/404/409 而开启所有开关。独立工作区需要原 blank-project/activate 流程确认 `NEUTRAL_STUDIO`，不要靠页面深链接伪造激活。执行类功能按 [生产执行契约](../v2/production-execution.md)、[模型 Provider 契约](../v2/model-provider-contracts.md) 和 [V2 packaged profile](../v2/packaged-launch-profile.md) 准备原 Host 环境。

## 接下来

提交前按 [贡献与 PR 审核指南](contribution-review.md) 选择与改动相称的检查、说明跨模块契约与恢复行为，并协调共享文件。本文只新增开发者入口；根 README 的导航链接可由集成方在整合后单独决定。
