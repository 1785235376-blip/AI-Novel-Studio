# 统一制作工作流投影（Phase 7）

`GET /api/projects/{nid}/studio/production/workflow` 是只读汇总投影：它把已有 7 个模块 owner 的当前事实收敛为一个工作流视图，供操作台显示"从哪开始、七个模块各处在什么状态、下一步的既有入口是什么"。顶层固定 `advisory_only=true`、`execution_authority=false`；读到该响应不授予执行、审核、权限、模型或发布资格。契约固定 `studio-production-workflow/1`，`schema_version=1`。

本阶段只新增一个变更操作，即 `POST .../workflow/intent` 对创意意图值的 CAS 写入；其余全部是读取。没有新的项目、素材、作业、队列、权限、模型注册表或版本 owner；没有模型执行、渲染、下载、安装或验收提升。同一个原 owner 仍是权威，本投影只是它的一个有界视图。

本页是 **Phase 7 工程线（line C）** 的契约与边界文档。后端（line A）与前端（line B）源码、本页所列新测试与浏览器验收尚未落地时，相关检查必须以 `NOT_YET_AVAILABLE` 记录真实原因，不得记通过；截至本页写作时两线已部分落地（line A 后端已落地并核对，line B 前端源码已落地但类型检查为红），实测结果与保留失败见 §6 与 [Phase 7 report](../../PHASE7_WORKFLOW_UX_REPORT.md)。

## 1. 冻结的端点与 DTO 契约

基础路径：`/api/projects/{nid}/studio/production/workflow`

| 方法 | 路径 | 权限 | 性质 |
| --- | --- | --- | --- |
| GET | `/api/projects/{nid}/studio/production/workflow` | `domain.read` | 只读投影，不创建、不推进、不提升 |
| POST | `/api/projects/{nid}/studio/production/workflow/intent` | `domain.write` | 唯一新变更；原 CAS 语义下的创意意图写入 |

GET 响应字段（冻结）：

| 字段 | 含义与边界 |
| --- | --- |
| `schema_version` | 整数 `1` |
| `contract` | 字面量 `studio-production-workflow/1` |
| `project_id` | 当前已授权项目 ID；与 `scope.novel_id` 一致，不一致必须拒绝 |
| `scope` | 原公开范围投影：`mode`、`novel_id`，以及存在的可选 `workspace_id`／`project_id`／`storyline_id`／`branch_id`；沿用 [production operation contracts](production-operation-contracts.md) 的 `PUBLIC_SCOPE_KEYS`，不返回 actor、principal 或 incarnation 值 |
| `advisory_only` | 固定 `true` |
| `execution_authority` | 固定 `false` |
| `generated_at` | 本次投影生成时间；不是作业或验收时间 |
| `project_start.state` | `NOT_STARTED` ｜ `READY` ｜ `STARTED`；中性入口的当前状态，不是项目生命周期 owner |
| `project_start.entry_kind` | 固定 `"NEUTRAL_STUDIO"`；由原 `IndependentWorkspaceService.activate` 保存的展示回执 |
| `project_start.incarnation` | 当前项目 incarnation 的投影，用于说明本响应属于哪一次绑定 |
| `project_start.has_creative_documents` | 是否已存在原 Creative 文档 |
| `project_start.start_action` | `{method, path, requires_original_host_session}`；描述性元数据，指向既有中性项目创建入口 `POST /api/experimental/projects`（激活动作另见既有 `POST /api/projects/{nid}/studio/activate`），不能当作执行链接 |
| `creative_intent.version` | 原偏好行的当前版本；从未保存时为 `0` |
| `creative_intent.values[]` | `{intent_id, label, selected, custom}`；`intent_id` 为小写稳定标识，由原 `CreativeIntent` 字面量派生，未选择项也返回 |
| `creative_intent.preset` | 当前实现额外返回的原 `WorkspacePreset` 值（冻结字段表未列，见 §1.1） |
| `creative_intent.editable` | 固定 `true`；可编辑不等于拥有权限，写入仍须 `domain.write` |
| `creative_intent.history_retained` | 固定 `true`；沿用原偏好历史 |
| `modules[7]` | 顺序固定为 `director, storyboard, image, video, audio, timeline, asset`；每项见下表 |
| `asset_overview` | `{total, by_kind{image,audio,video,text,other}, private_pending_review, reviewed}`；原 AssetLibrary 当前投影 |
| `dashboard` | `{stages_total:7, stages_started, stages_reviewed, open_reviews, blocked_stages[]}`；计数是当前投影，不是第二套状态机 |

`modules[]` 每项：`{id, label, status, document_count, asset_count, job_count, blocked_reasons[], owner, next_action}`。

- `status` 只允许 `NOT_STARTED` ｜ `PLANNED` ｜ `IN_PRODUCTION` ｜ `REVIEW_PENDING` ｜ `REVIEWED`。它是既有文档／资产／作业事实的投影，不代表里程碑验收，也不改写历史矩阵行。
- `owner` 命名下节列出的真实既有 owner；本阶段不新增 owner。
- `next_action` 是描述性元数据（方法／路径／权限域），沿用只读目录的规则：客户端不得把它变成执行、授权或自动重放。
- `blocked_reasons[]` 只报告既有阻塞原因，不创建新的阻塞状态机。

POST 请求体（冻结原文）：

```json
{"expected_version": 3, "values": [{"intent_id": "IMAGE_DESIGN", "label": "图像设计", "selected": true}], "note": null}
```

响应为递增版本后的 `creative_intent` 对象（与 GET 中同名字段同形）。错误：`409 PRODUCTION_WORKFLOW_INTENT_CONFLICT`、`422 PRODUCTION_WORKFLOW_INTENT_INVALID`、`403 CREATIVE_AUTHORITY_INVALID`／`CREATIVE_AUTHORITY_CHANGED`。

### 1.1 冻结原文与当前实现的差异（需 Lead 裁决，不自行改口径）

line A 已按上述契约落地 `app/creative/production_workflow_models.py:ProductionIntentUpdate`，与冻结原文存在三处可核对差异。本页只如实记录，不把任一版本说成已一致：

| 项 | 冻结原文 | 当前实现（已读源码） | 影响 |
| --- | --- | --- | --- |
| 请求体备注字段 | `note: string \| null` | 只接受 `preset: string \| null`（`max_length=32`），**没有 `note`** | `StrictModel` 为 `extra="forbid"`，客户端发送 `note` 会得到 `422`；需要 Lead 决定是补 `note` 还是把契约改成 `preset` |
| GET `creative_intent` 字段 | `version, values[], editable, history_retained` | 额外返回 `preset` | 只增字段；客户端必须容忍未知字段，或同步更新契约 |
| `values[]` 元素 | `{intent_id, label, selected, custom}` | GET 返回四项；POST 的 `ProductionIntentValue` 只接受前三项 | GET 的 `values[]` 元素**不能原样回传**到 POST（多余的 `custom` 会被 `extra="forbid"` 拒绝），line B 的编辑器必须显式重建请求元素 |

`intent_id` 线上形式为小写稳定标识（由原 `CreativeIntent` 字面量派生，实现见 `intent_catalog()`），而原 owner 存储的是大写字面量；`update_intent` 负责两侧映射。POST 的 `values[]` 上限为 11，`expected_version` 为严格整数或 `null`。

## 2. 已确认的接入点（不新增 router 工厂）

路由加入**既有** router 工厂 `create_independent_workspace_router`（[app/creative/workspace_api.py](../../app/creative/workspace_api.py)），由原应用装配并注册：

- `app/experimental/api.py:694` 调用 `create_independent_workspace_router(...)`；同一文件构造 `IndependentWorkspaceService`、`CreativeGraphService` 与 `ProductionExecutionService`。
- 协作准入由 `app/main.py:318-320` 调用 `is_independent_studio_route(method, normalized_path)` 决定，条件为 `narrative_production_v2` 已启用。
- 先例是同一工厂内的只读子路由 `app/creative/production_contract_api.py:create_production_contract_router`：它用 `invoke(nid, token, branch, "domain.read", view)` 取原权限、actor/scope 与 incarnation guard，并用 `service.project(nid, scope)` 核对 owner。

两点必须由 line A 显式处理，否则契约不成立。两点在当前工作区源码中均已核对落地：

1. **命中准入表（已落地）。** `is_independent_studio_route` 的 `production_patterns` 现已在 GET 分支接受 `workflow`、在 POST 分支接受 `workflow/intent`（`app/creative/workspace_api.py:30-31`），仍是闭合全匹配，未放宽为通配前缀。若缺少这一步，协作模式下这两个请求不会通过 `app/main.py:319` 的原准入。
2. **与旧目录的激活前提不同（已落实为投影语义）。** 只读目录在未激活时返回 `409 CREATIVE_STUDIO_ACTIVATION_REQUIRED`；工作流 GET 不设该前提，否则无法报告 `project_start.state=NOT_STARTED`：当前实现直接把未激活且无偏好行报为 `NOT_STARTED`、有偏好行但 `entry_kind != NEUTRAL_STUDIO` 报为 `READY`、已激活报为 `STARTED`。激活动作本身仍是既有路由 `POST /api/projects/{nid}/studio/activate`；`project_start.start_action` 指向的是既有中性项目创建入口 `POST /api/experimental/projects`（`workspace_api.py:126`，`requires_original_host_session=true`），不是激活路由，也不是执行授权。

工作流子路由经 `app/creative/workspace_api.py:253-255` 以 `create_production_workflow_router(workflow, invoke)` 装配进同一工厂，两个端点都通过原 `invoke` 取得 `domain.read`／`domain.write` 与 actor/scope/incarnation guard。

## 3. 7 个模块各自复用的既有 owner

下表路径与类名均已按当前工作区源码核对。前两列是投影响应中 `modules[].id` 与 `modules[].owner` 的**实际返回值**（`app/creative/production_workflow.py:MODULE_SPECS`）；后两列是该模块计数与状态事实背后真正被读取的既有 owner。全部为既有 owner，本阶段不新增同义实现。

| module（`id`） | 响应中的 `owner` 字符串 | 被读取的既有 owner（真实路径 + 类／函数） | 被投影的既有事实 |
| --- | --- | --- | --- |
| `director` | `DirectorService` | 文档：`app/creative/service.py:CreativeService`（`mode="DIRECTOR"` 的行、版本、CAS、history/restore）；提案与复审：`app/creative/proposals.py:DirectorProposalService`；本地模型相位：`app/creative/generation.py:DirectorModelCoordinator`；同名既有服务为 `app/experimental/director.py:DirectorService` | DIRECTOR 文档数、提案复审状态、模型相位回执 |
| `storyboard` | `StoryboardWorkspace` | `app/creative/storyboard.py:StoryboardWorkspace`（`approve`／`bind_image`／`image_request`／`video_request`／`bind_video`／`timeline_draft`／`timeline_create`／`adopt_video`／`director_advice`）；`mode="STORYBOARD"` 的文档由 `CreativeService` 持有 | Shot 版本与审批、正式图片／视频绑定、Timeline 底稿创建与采用回执 |
| `image` | `ImageJobService` | `app/services/studio_image_execution.py`（模块级 `create`／`get`／`list_jobs`／`change`／`cancel`／`reconcile`），经 `app/creative/production_execution.py:ProductionExecutionService` 的 image owner 分派；底层原 owner 为 `app/services/image_job_service.py:ImageJobService` | 图像作业、私有候选、人工复审与正式 Asset 提升；投影按 `kind="image"` 的资产与 `source_job_id` 计数 |
| `video` | `StudioVideoExecution` | `app/services/studio_video_execution.py:StudioVideoExecution`；渲染／拼接为 `app/services/video_assembly_service.py:VideoAssemblyService` | 持久 VideoJob、一次派发、刷新、取消、UNKNOWN、候选与复审；投影按 `kind="video"` 计数 |
| `audio` | `StudioAudioExecution` | `app/services/studio_audio_execution.py:StudioAudioExecution`（内部经 `app/services/audiobook_service.py:AudiobookService`） | 语音／本地音频作业、FLAC 交付证明、私有候选、复审与 Asset 提升；投影按 `kind="audio"` 计数 |
| `timeline` | `VideoAssemblyService` | 文档计数取 `mode="PRODUCTION"`（即 VideoPlan）的行；执行与持久化 owner 为 `app/creative/production_execution.py:ProductionExecutionService`（`TIMELINES = "creative_production_timelines_v2"`；`timeline_save`／`timeline_edit`／`timeline_history`／`timeline_restore`／`timeline_render`／`timeline_export`）与 `app/services/video_assembly_service.py:VideoAssemblyService`；字幕为 `app/experimental/subtitle_timeline.py:SubtitleTimelineService` | 版本化时间线、原子编辑、锁轨、history/restore、本地渲染／导出作业 |
| `asset` | `AssetLibraryService` | `app/services/asset_library_service.py:AssetLibraryService`（字节、版本、摘要、immutable origin）；Studio 聚合读取为 `app/creative/workspace.py:IndependentWorkspaceService.asset_index`（元数据专用，见下） | 资产总数／种类、待审与已审计数、项目级容量 |

模块计数与状态只来自上述 owner 的行：`document_count` 是 `CreativeService.list` 中该 mode 的行数，`asset_count` 是 `asset_index` 中该 kind 的行数，`job_count` 是其中去重后的 `source_job_id` 数。`asset_index`（`app/creative/workspace.py:249`）是只读聚合入口：它不逐资产打开 lineage／relationship 读取，`review_status` 只取 owner 自己保存的 `_text_result_review` 标记，媒体候选的复审属于作业级别、**不会**在资产聚合里被推断。

项目、范围与 incarnation 事实来自 `app/creative/project_store.py:CreativeProjectStore`（`store.key`／`store.incarnation`）与 `IndependentWorkspaceService.project`；`entry_kind="NEUTRAL_STUDIO"` 由 `IndependentWorkspaceService.activate` 写入原偏好行。因此 `project_start` 是对原激活回执的投影，不是新的项目状态 owner。

## 4. 只读投影与唯一的新变更

**读取（GET）** 只读取各 owner 的当前视图：不创建作业或运行，不派发模型，不批准／提升资产，不推进时间线，不写偏好版本，不缓存授权供后续使用。响应被读取不改变任何 owner 状态；`open_reviews` 也不是待办队列 owner。

**写入（POST /intent）** 是唯一新变更，落在既有偏好 owner 的原 CAS 语义上（`app/creative/workspace.py:IndependentWorkspaceService.preferences`，字段域见 `app/creative/workspace_models.py:WorkspacePreferences`）：

- `expected_version` 必须等于当前版本（从未保存时为 `0`），否则 `409`。成功写入后版本加一，旧值进入原历史（`MAX_PREFERENCE_HISTORY = 200`），因此 `history_retained=true`。
- `expected_version = null` 表示"调用者没有观察到版本"：只在当前版本为 `0`（尚无保存偏好）时创建；当前版本非 `0` 时必须 `409`，不得静默覆盖。这是本端点相对原 `PUT .../preferences` 的显式语义扩展，line A 必须在既有 `preferences()` 之上实现，而不是另写一套偏好存储。
- `values[]` 的 `intent_id` 取自既有 `CreativeIntent` 字面量集合，去重后最多 11 项；重复或非法值 `422`（原 owner 的 `CREATIVE_INTENTS_DUPLICATE` 等拒绝必须映射为该错误码，不得吞掉）。`label` 与 `note` 是投影／备注文本，不参与授权判断。
- `intents`／`preset`／`custom_intent` 只是展示偏好：`IndependentWorkspaceService.project` 已声明 `intent_is_permission=false`。本阶段不因为意图选择而改变模块可见性、权限或执行能力。

**权限与身份。** 两个端点都经原 `invoke`：`domain.read` 或 `domain.write` 重新校验、actor/scope 与当前 incarnation 复核。actor 变化、分支范围变化、incarnation 变化或权限撤销时抛 `403 CREATIVE_AUTHORITY_INVALID`／`CREATIVE_AUTHORITY_CHANGED`；`guard()` 在回调前后各执行一次，读到一半的权限变化不会返回旧事实。

## 5. 本阶段明确不声称

- **不执行模型。** GET 不调用任何 provider、executor、Broker、JobManager 或本机运行时；`next_action` 只是描述性元数据；本阶段不下载、不安装、不启动模型，不做 TTS／ASR／Whisper／视频模型推理。
- **不提升验收。** `modules[].status`、`dashboard` 与 `asset_overview` 都只投影既有事实。读到 `REVIEWED` 不等于里程碑通过，`reviewed` 计数不等于原 `APPROVED_FOR` 复审，`stages_*` 不是 M4→M9 的验收序列。历史矩阵行、M4 PARTIAL 与 M5–M9 LOCAL_REQUIRED 保持不变。`blocked_reasons` 当前只会由"存在待审私有候选"这一既有事实产生，不引入新的阻塞状态。
- **聚合不装作全知。** `asset_overview.private_pending_review` 只统计 owner 自己保存了文本结果复审标记的资产；媒体候选的复审在作业级别，聚合不会替它推断，因此该计数**不等于**待审媒体候选总数。`job_count` 是资产上 `source_job_id` 的去重数，不是队列长度。
- **不新增 owner。** 不新建项目／素材／作业／队列／权限／模型注册表／时间线 owner；不建立第二套运行状态机；`blocked_reasons[]` 不引入新的阻塞状态。
- **不授予执行权。** 顶层 `advisory_only=true`、`execution_authority=false` 是固定的，不因查询参数、客户端能力或已激活状态而改变。写入偏好同样不授予执行、审核或发布资格。
- **保留 LOCAL_REQUIRED 门禁。** Windows 安装版、launcher→PG→backend→C# DesktopHost 可信会话、GPU／真实模型质量、重型渲染、完整 CI 与浏览器验收仍为 `LOCAL_REQUIRED` / `NOT_RUN`；本页的静态实现与隔离测试不替代这些门禁。
- **不涉及发布。** 不合并 main、不打 tag、不发布 Release；V1 冻结内容、历史失败证据、F00 INTEGRATED + 39 PARTIAL、独立复审 BLOCKED 与 PoemQingJian 暂停状态原样保留。

## 6. 复现与验证命令

冻结检查器：`scripts/run_phase7_workflow_checks.py`（复用 `scripts/run_v2_checks.py` 的隔离 profile 环境与源码快照，收据同样写到 `docs/delivery/v2-development/phase7-workflow-<check>-r<N>.json`／`.log`）。

```powershell
# 计划与目标文件（不改动任何状态）
python scripts/run_phase7_workflow_checks.py --list

# 全部检查：file / postgres / frontend / types / build / tokens / seam
python scripts/run_phase7_workflow_checks.py

# 逐项
python scripts/run_phase7_workflow_checks.py --checks file
python scripts/run_phase7_workflow_checks.py --checks postgres --postgres-url "postgresql://127.0.0.1:5432/v2_phase7"
python scripts/run_phase7_workflow_checks.py --checks frontend,types,build,tokens
```

与检查器等价的直接命令（前端在 `<worktree>\frontend` 下用 corepack 固定的 pnpm 10.6.5）：

```powershell
python -m pytest -p no:cacheprovider -q tests/test_v2_production_workflow*.py
# STORAGE_BACKEND=postgres 时同上；无 TEST_POSTGRES_DATABASE_URL 时记为 SKIPPED / NOT_CONFIGURED
corepack pnpm exec vitest run src/production
corepack pnpm exec tsc -b
corepack pnpm run build
corepack pnpm run lint
```

`b`（PostgreSQL）在未配置 `TEST_POSTGRES_DATABASE_URL` 时记 `SKIPPED`，且被拒绝的非 loopback／非 `/v2_*` 数据库同样只记为未配置，不记通过。`a`／`c` 在 line A／line B 的源码尚未落地时记 `NOT_YET_AVAILABLE`，并写明缺失的具体路径与所属线；检查器退出码 `0`＝全部 PASS、`1`＝有 FAIL、`2`＝无 FAIL 但有 NOT_YET_AVAILABLE／SKIPPED。

本线最终一次全量实测（输入树**未冻结**，line A/B 仍在写入；同一批命令的结论在两线写入过程中多次翻转，任何数值都必须与其修订号和 `source_sha256` 一起读）：`file` **14 passed / 8 skipped / 0 failed**；`frontend`（`src/production`）**35 passed（5 文件）**；`types`（`tsc -b`）**PASS**；`build`（`pnpm run build`）**PASS**（2103 modules）；`tokens` **PASS（52 文件）**；既有 router/准入 seam **34 passed / 34 skipped**；`postgres` **SKIPPED / NOT_CONFIGURED**（本机无 server），故检查器退出码为 `2`（无 FAIL、有 1 项未配置）。类型/构建在 `r3`／`r4`、前端在 `r5` 曾为红，对应的 FAIL 收据全部保留，不做"重跑至绿"的改写。最终 pin 与数值由 Lead 在两线停止写入后重跑本 harness 生成。

pytest 一律使用 `-p no:cacheprovider` 且环境含 `PYTHONDONTWRITEBYTECODE=1`，仓库不产生 `__pycache__`／`.pytest_cache`。`pnpm run build` 沿用冻结脚本 `tsc -b && vite build`，输出只写 gitignore 的既有 `frontend/dist`，不写任何受版本控制的路径。本阶段不使用 dotnet。

## 7. 与既有文档的关系

- 只读目录与执行命令边界见 [production operation contracts](production-operation-contracts.md) 与 [production execution](production-execution.md)；工作流投影是它们的汇总视图，不是替代物。
- 前端消费与控制器的边界见 [studio workspace operations](studio-workspace-operations.md)：视觉重构可以重排 JSX／CSS，但必须继续消费原 controller／client、命名动作、Host、CAS、人工同意与私有 Blob 生命周期，不能把只读投影变成可调用命令。
- 当前事实同步追加在 [V2 feature matrix](../../AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md) 的只增章节；本阶段实际验证与保留失败见 [Phase 7 report](../../PHASE7_WORKFLOW_UX_REPORT.md)。
