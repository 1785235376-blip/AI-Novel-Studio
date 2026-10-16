# UX-PRODUCT 计划（Studio 单产品用户体验补全）

本轮名称：**UX-PRODUCT**。范围：只做 Studio 自身，达到"独立产品可用"；QingJian 联动、Adapter、双产品运行与协议映射专项**全部暂停**（保留既有协议与未来接入边界，不删除、不升级）。
里程碑命名：本文件与 STATUS/DECISIONS 使用 **UX-01 … UX-09**；不改写、不重编号 Phase7/Phase8 与 M4 PARTIAL / M5–M9 LOCAL_REQUIRED 等历史记录。

## 1. 基线与授权

| 项 | 值 |
| --- | --- |
| 仓库 / 分支 | `1785235376-blip/AI-Novel-Studio` / `feature/v2-narrative-platform` |
| 授权开发目录 | `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` |
| 开工 HEAD | `9ba3d773268e2eca5951466dc53f6d606d28da15`（Phase8 准备文档提交） |
| PR | #47，保持 OPEN / Draft（不合并 main、不 release） |
| 交接基线未跟踪文件 | 39 个既有未跟踪项（36 个 `docs/delivery/v2-development/phase6-*`、`docs/delivery/.../catalog-f19d*.json`、`.graphflow-cache/`、`graphflow-out/`）——**属基线，禁止提交或清理** |
| 环境 | Python311（`scripts/dev.ps1`/检查脚本实际使用者）、frontend 经 corepack 使用 pnpm 10.6.5、.NET SDK 8.0.424 已就绪；**不升级**基础依赖 |

## 2. 工作包与场景映射

| 工作包 | 目标 | 主要原 owner | 覆盖场景 |
| --- | --- | --- | --- |
| UX-01 项目入口 / 创作意图 / 新手-专业模式 | 知道怎么开始，且不被向导绑住 | `POST /api/experimental/projects`、`WorkspacePreferences`（intents/preset/custom_intent）、`Layout.density` | S01, S02, S03, S13 |
| UX-02 统一任务中心 / 审核收件箱 / 恢复 | 找到全部任务与待审，知道下一步 | `WorkspaceToolsService.tasks` + `TaskReader`、`UnifiedReviewInbox` + inbox API、原取消语义 | S04, S05, S08, S09, S13 |
| UX-03 Asset Browser 与素材复用 | 找得到、比得了、可复用 | `AssetLibraryService`、`IndependentWorkspaceService.asset_index/list_assets`、lineage/relationships | S06, S07 |
| UX-04 无限画布与节点工作流 | 拖放、整理、理解节点 | `CreativeGraphService`、`app/creative/graph*.py` | S07, S02 |
| UX-05 导演与分镜工作区 | 接成好用的编辑空间 | `DirectorService`/`proposals.py`、`StoryboardWorkspace` | S06, S09 |
| UX-06 多轨剪辑 / 预览 / 交付 | 真正能剪 | `ProductionExecutionService` 时间线、`VideoAssemblyService`、`studio_timeline_*` | S09, S10, S11 |
| UX-07 模型中心与存储 | 看懂状态、理解缺口 | `LocalDiscoveryService`/`ModelCenterService`、存储/容量 owner | S03, S13 |
| UX-08 内置项目提示助手（**不接青简**） | 说清现状与可选下一步 | Phase7 workflow 投影、任务状态、资产关系、能力状态 | S13 |
| UX-09 统一导出 / 工程交接 / 缺项检查 | 知道导出什么、缺什么 | `ExportJobService`、`PortableProjectsService`、各模块导出 owner | S11, S12 |

## 3. 文件所有权（本批：UX-01 + UX-02）

**串行整合（仅主代理写）**：`frontend/src/creative/IndependentStudioWorkspace.tsx`、`frontend/src/App.tsx`、`frontend/src/novel/EntryExperience.tsx`、`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md`、共享路由/类型/`WorkspacePreferences`、`docs/v2/ux-product/**`。

| 线 | 负责文件 | 原 owner / 接口 | 依赖 | 集成条件 |
| --- | --- | --- | --- | --- |
| A（主代理，UX-01） | `frontend/src/onboarding/**`（新目录）、`tests/test_v2_studio_entry*.py`（如需后端） | `POST /api/experimental/projects`、`WorkspacePreferences`、resume/`Layout` | 无 | 主代理在 `IndependentStudioWorkspace.tsx` / `EntryExperience.tsx` 挂载 |
| B（子代理，UX-02） | `frontend/src/taskcenter/**`（新目录） | `GET …/tasks`、inbox `GET`/`batch`/`{domain}/{id}/{action}` | 只读现有接口 | 主代理在 `IndependentStudioWorkspace.tsx` 挂载 |
| C（子代理，验证线） | `docs/delivery/v2-development/ux-*`（收据）、`scripts/run_ux_product_checks.py` | 无产品写入 | A/B 落定 | 冻结输入树后独立运行 |

### 第二批（UX-03 + UX-04）

| 线 | 负责文件 | 原 owner / 接口 | 集成条件 |
| --- | --- | --- | --- |
| E（子代理，UX-03） | `frontend/src/assetbrowser/**`（新目录） | `studioClient` 资产列/详情（含 provenance+relationships）、`studioRelationshipsClient`、`AssetLibraryService` 行（版本/摘要/来源/审核标记） | 主代理在 `IndependentStudioWorkspace.tsx` 的 ASSETS 视图**增量**挂载（不动既有 `AssetLibraryPanel`） |
| F（子代理，UX-04） | `frontend/src/canvasops/**`（新目录） | `studioGraphTypes`（类型）、`graphDraft`（`connectionIssue` 是唯一合法性权威、`blankGraph`、`graphCatalogForSchema`）、`graphCanvasGeometry`（框选几何） | 主代理在既有 `studioGraphEditorView.tsx` 中**增量**组合（保留既有控件），并接 `catalog/draft/base/selected/past/future/editable/protectedNodes/kind/sourcePort/targetPort` 与 `addNode/connect/travel/setSelected/setKind/setSourcePort/setTargetPort` |
| G（子代理，验证线） | `docs/delivery/v2-development/ux-product-*`（收据）、扩展 `scripts/run_ux_product_checks.py` | 无产品写入 | E/F 落定后独立运行并逐条证伪 |

**第二批硬约束**：不新增持久化图字段（分组/注释/折叠只做**会话内呈现态**）；不新增第二套节点引擎或第二个资产库；不触受保护 shell；不提高既有节点/任务上限（触界时解释并建议拆分）。

规则：不同线不得并发写同一文件；共享文件由主代理串行整合；A/B 只在自己的新目录内创建文件。

## 4. 执行顺序（工程建议，按实际依赖调整并记录）

1. **第一批**：UX-01 + UX-02（入口/意图/模式 + 任务/审核中心）→ 一个完整可操作切片。
2. 第二批：UX-03 + UX-04。3. 第三批：UX-05 + UX-06。4. 第四批：UX-07 + UX-08 + UX-09。5. 第五批：跨模块回归与交付。

## 5. 验证计划

- 每切片：新增/修改范围的 pytest（File）＋ 前端 vitest（新目录）＋ `tsc -b`。
- 每集成批次：前端 build ＋ token lint ＋ 受保护 seam 回归（`tests/test_v2_independent_workspace_api.py`）＋ 准入回归。
- 涉及持久化/CAS/history：必须 File + PostgreSQL 双后端；PG 先按任务书 16.2 在 `Tools/`、既有脚本与历史 receipts 中寻找可复用便携 PG，确无则如实 `NOT_CONFIGURED`。
- 最终：冻结输入树后重跑，收据 `sources_changed_during_check=false`。
- 证据格式：实际命令、解释器、开始/结束时间、完整 SHA、exit code、pass/fail/skip 与适用范围；不同 backend / 重叠套件不相加。

## 6. 明确不做（本轮）

合并 main、release/tag、部署、backport、修改 QingJian、双产品联动、新增协议权限、付费服务/凭据、自动下载或加载大模型、用户 GPU 与真实项目迁移、安装版最终验收、`git reset --hard`/`clean`/force push/`git add -A`、未走设计变更流程推倒受保护 shell、把界面补全写成旧里程碑自动通过。
