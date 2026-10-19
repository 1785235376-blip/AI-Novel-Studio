# 架构总览（ARCHITECTURE）

本文件是**当前仓库架构的入口地图**，用于让新贡献者与审核者在一个页面内理解真实边界，
并指向唯一权威文档与源码。

- 权威顺序（冲突时以此为准）：**运行中的源码与真实测试/迁移证据** >
  \`docs/v2/engineering/requirements-traceability.json\` >
  \`docs/v2/engineering/*\` > 历史报告（\`AI_NOVEL_STUDIO_V2_ARCHITECTURE.md\`、
  \`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md\`、\`docs/delivery/*\` 等）。
- 本文件**不重复维护第二份架构真相**：组件细节、契约、状态机以链接文档/源码为准。
- 状态词表（固定）：需求 \`PLANNED / IMPLEMENTED / INTEGRATION_VERIFIED / ACCEPTED / BLOCKED\`；
  测试 \`PASS / FAIL / PARTIAL / BLOCKED / NOT_RUN\`。\`IMPLEMENTED\` 只表示 owner 源码存在；
  \`INTEGRATION_VERIFIED\` 需在该 SHA 上真实执行过集成/浏览器/媒体测试。

> 当前状态：**V2 尚未正式发布**。内部版本 \`0.7.0\`（\`release/version.json\`，channel \`beta\`）。
> \`v0.1.0-alpha\` 是早期源码快照锚点，不是正式版。完整发布门禁见
> [RELEASE_GATES.md](docs/v2/engineering/RELEASE_GATES.md)。

## 1. 总体组件关系

\`\`\`mermaid
flowchart TB
  subgraph Client["客户端"]
    UI["React 18 + TypeScript + Vite<br/>AppShell / ModuleWorkspace"]
    DESK["DesktopHost (.NET WebView2, 可选)<br/>受控管道 + 打包运行时"]
    TUTOR["Local Interop 允许的只读 Tutor 桥"]
  end
  subgraph Backend["FastAPI 后端（app/main.py）"]
    MW["Host / Session / Scope / CAS / fail-closed 中间件"]
    API["/api 与 /api/v1 路由"]
    SVC["领域服务<br/>services/ · creative/ · experimental/"]
    REPO["RepositoryBundle<br/>File 仓库 / PostgreSQL 仓库"]
    JOB["JobManager（单一 Job 路径）"]
    MC["Model Center + Provider Runtime<br/>发现/准入/预算/授权"]
    MEDIA["媒体执行<br/>图片 / 视频 / 音频 / 字幕 / 时间线交换"]
    COMIC["Image Studio → 漫画子能力<br/>comic_layouts 页面/分格/气泡"]
  end
  subgraph Data["数据与文件"]
    PG[("PostgreSQL<br/>已批准事实 / 事务")]
    MD["Markdown 正文<br/>原子写入"]
    ASSET["Asset 字节 + 版本 + 血缘"]
  end
  LOCAL["本地模型 Ollama / llama.cpp（可选）"]
  CLOUD["云端 Provider（默认关闭，需显式授权）"]

  UI -->|"HTTP /api"| MW --> API --> SVC
  DESK -.-> UI
  TUTOR -.->|"版本化能力协商（只读）"| API
  SVC --> REPO
  REPO --> PG
  REPO --> MD
  SVC --> JOB
  SVC --> MC
  MC --> LOCAL
  MC --> CLOUD
  MEDIA --> ASSET
  COMIC --> MEDIA
\`\`\`

## 2. 后端 / 前端边界

| 层 | 位置 | 职责 | 不负责 |
| --- | --- | --- | --- |
| 浏览器 UI | \`frontend/src/\`（React/TS/Vite；\`docs/frontend_architecture.md\`、\`docs/ui/design_system.md\`） | 输入、展示、草稿态、恢复提示、已有权限范围内的操作 | 不成为数据 owner；不自行判定授权/版本 |
| DesktopHost | \`desktop-host/\`（.NET/WebView2）、\`app/packaging/*\` | 打包进程边界、控制管道、启动配置 | 不绕过 Host/Session/权限门禁 |
| HTTP API | \`app/main.py\`、\`app/api.py\`、\`app/*_api.py\`、\`app/creative/workspace_api.py\` | 路由、Host/Session/Scope 门禁、DTO、错误分层 | 不直接写文件/数据库（经 repository 层） |
| 领域服务 | \`app/services/\`、\`app/creative/\`、\`app/experimental/\` | 单一权威业务规则、CAS、Job/Review 状态机 | 不新增第二套存储/队列 |
| 持久化 | \`app/repositories/\`（File/PostgreSQL）、\`app/storage.py\`、\`database/migrations/\` | 原子写、事务、迁移、恢复 | 不做业务判断 |
| Local Interop | \`app/local_interop/\`、\`local_interop_protocol/\`、\`contracts/local-interop/\` | 版本化只读上下文/受控动作 | 不是新的控制权威 |

资源/鉴权要点：Host 信任、可信 Session、项目 scope/角色、跨项目复用授权、云端出站同意、
凭据保险库（\`CREDENTIAL_VAULT_*\`）与 \`GET /api/release/readiness\` 聚合门禁；详见
[SECURITY_AND_ISOLATION.md](docs/v2/engineering/SECURITY_AND_ISOLATION.md)、\`docs/privacy_design.md\`。

## 3. 数据所有者（单一权威）

完整表格与测试证据见 [SINGLE_AUTHORITY_MAP.md](docs/v2/engineering/SINGLE_AUTHORITY_MAP.md) 与
[AI_NOVEL_STUDIO_V2_ARCHITECTURE.md](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md) §1。核心：

| 领域 | 单一 owner（源码） | 关键约束 |
| --- | --- | --- |
| 项目 identity/生命周期 | \`RepositoryBundle.novels\`、\`app/repositories/*\`、\`app/services/novel_service.py\` | 不新建"项目数据库"；中性项目可无章节 |
| 工作区/成员/分支/权限 | \`app/services/collaboration_scope_service.py\`、\`authorization_service.py\`、\`app/trusted_sessions.py\` | 服务端解析 actor/scope，提交前复核；intent 不授权 |
| 正文与修订 | \`app/services/chapter_service.py\` + File/PG chapter 仓库 | 资产只引用 chapter id/version/digest，不复制正文 |
| 创作文档 | \`app/creative/service.py\`、\`models.py\`、\`project_store.py\` | SCREENPLAY/DIRECTOR/STORYBOARD/PRODUCTION 既有修订/来源/历史/恢复 |
| 资产字节与元数据 | \`app/services/asset_library_service.py\` + asset lifecycle API | 单一 UUID、不可变字节、SHA256/大小、元数据版本 |
| 资产关系/血缘 | \`AssetLibraryService\` lineage + \`app/experimental/production_lineage.py\` | 记录父版本/digest；血缘不产生版权或分发授权 |
| Job / 生成 | \`app/jobs.py\` JobManager、\`agent_job_service.py\` | 取消/终态/UNKNOWN 不自动重放；图节点引用 Job |
| Review / 审批 | 统一 review inbox / finding / 审批适配器 | 候选不得静默提升为已批准事实 |
| Timeline / 导出 | \`app/experimental/studio_timeline*\`、\`video_assembly_service.py\`、\`timeline_exchange.py\` | 规划卡不是轨道；OTIO/SRT/VTT 交换有边界 |
| 漫画页/分格/气泡 | \`app/experimental/comic_layouts.py\`（挂在 Image Studio 下） | 文字气泡编辑不得改分格图片字节/资产版本 |
| 模型发现/启用 | \`app/model_center/*\`、\`provider_runtime_v2_*\` | 只读发现；不自动下载/启动；许可证前置审查 |
| 知识 / 世界 | \`app/experimental/world.py\`、\`story_graph.py\`、\`research_library.py\` | 证据/置信度；未审 AI 输出不得成为 canon |

## 4. 三类图，三种语义（不可混用）

来自 [AI_NOVEL_STUDIO_V2_ARCHITECTURE.md](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md) §2：

1. **Asset Relationship Graph（资产关系图）**：描述性 provenance。父关系在 asset owner 锁下测量；
   无调度权威；引用不建立版权或再分发许可。
2. **Creative Workflow Graph（创作工作流图）**：用户编写的执行依赖图。由既有 workflow host 拒绝环、
   快照定义并拥有 review/状态迁移；边目前是 source/target ID，完整 V2 typed media-port 契约仍需补齐，
   不得替换 host 或复制 JobManager。
3. **Knowledge Graph（知识图）**：带证据的虚构/研究知识（事实 vs 信念、时间有效性、假设）。
   不能当作媒体依赖图，也不能暗示未经审核的 AI 输出已进入 canon。

## 5. 版本、CAS、权限与云端授权

- 版本权威：\`release/version.json\`（\`0.7.0\` beta）+ \`app/packaging/versioning.py\`
  强制 \`pyproject.toml\`/\`app/__init__.py\`/\`frontend/package.json\`/\`.env.example\` 一致
  （\`scripts/validate_release_version.py\`）。Git 标签不是版本权威来源。
- CAS：章节/创作文档/结构化记录的版本冲突按 CAS 拒绝（\`tests/test_structured_record_cas.py\`、
  \`tests/test_screenplay_cas_history.py\` 等）；不是 last-writer-wins。
- 权限：项目 scope/角色/分支由服务端解析并在提交与响应前复核；跨项目复用资产必须通过同一授权
  （\`tests/test_shared_project_route_authority.py\`）。
- 云端：默认 \`ENABLE_CLOUD=false\`；出站 URL 校验、显式同意、预算/幂等/未知上游不重放
  （\`app/net_safety.py\`、ModelBroker、provider profiles、凭据保险库）。

## 6. 媒体执行流水线

输入（文本/剧本/Director 规划）→ 生成/渲染任务（图/视频/音频/字幕）→ **Review** →
私有候选 → 采纳为 Asset（字节 + 版本 + 血缘）→ Timeline/导出。真实产物用独立解析器校验
（ffprobe/PIL/zip + SHA256），Mock 只证明非模型业务行为。详见
[MEDIA_AND_COMIC_CONTRACTS.md](docs/v2/engineering/MEDIA_AND_COMIC_CONTRACTS.md)、
\`docs/experimental_production_lineage.md\`。

## 7. 来源、恢复与不可破坏的历史

- 下游资产/剧本/漫画页记录来源 identity + version + digest；源变更只把依赖视图标为过期，
  不重写已批准资产（\`app/experimental/change_impact.py\`）。
- 备份/恢复/迁移脚本：\`scripts/backup.ps1\`、\`restore.ps1\`、\`migrate.ps1\`；迁移文件是 schema owner。
- 原子写（\`app/storage.py\`）、事务、CAS 与重启恢复保证崩溃不损坏数据；UNKNOWN 上游只暴露恢复，
  不自动重放/重复计费。
- V1.X/RC1 冻结内容与用户数据必须保持；V1 契约见 \`V1_SCOPE_FREEZE.md\`、
  \`docs/v1_implementation_status.md\`。

## 8. Image Studio → 漫画（子能力归属）

漫画**不是**新的一级主模块：它是 Image Studio 下的子能力，页面/分格/气泡 owner 在
\`app/experimental/comic_layouts.py\`（+ 挂载 API），复用同一 Asset/Review/CAS/Timeline 权威。
完成度与缺口见 \`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md\` 的 IMAGE-COMIC-01–20 行与
\`docs/v2/engineering/MEDIA_AND_COMIC_CONTRACTS.md\`；本轮**没有** ACCEPTED 的漫画项。

## 9. 模块状态（入口级，不夸大）

| 能力 | 状态 | 证据/说明 |
| --- | --- | --- |
| File 后端项目/章节/创作文档/CAS/权限/审核 | IMPLEMENTED / INTEGRATION_VERIFIED（代表性测试） | 完整 File 套件存在历史 24 failed / 10023 passed 记录，失败均为专用 profile 用例；见 \`BASELINE_20261019_r1.md\`、\`TRIAGE_20261019_r3.md\` |
| 真实 PostgreSQL | PARTIAL / BLOCKED_ENVIRONMENT（完整套件） | D-07：Windows PG 环境阻塞；代表性真实 PG 子集 118 passed |
| 前端（Writer/创作工作台/UI 契约） | IMPLEMENTED；构建与 Vitest PASS | \`pnpm test/build/lint\`；设计系统 \`docs/ui/design_system.md\` |
| 真实浏览器旅程 | PARTIAL | 视觉/几何 15/15 历史 PASS；本地最小 CI 已真实执行 V2 保存/重读旅程（见 LOCAL_CI_RESULTS_20261019.md） |
| 本地模型/GPU 推理 | NOT_RUN / LOCAL_REQUIRED | 未授权模型、未调用收费 API |
| 云端 Provider | IMPLEMENTED（门禁+路由），默认关闭 | 需显式授权；本轮未调用 |
| V2 差异化能力 DIF-01–12 | 大多 PLANNED/PARTIAL | \`requirements-traceability.json\`；0 ACCEPTED |
| IMAGE-COMIC-01–20 | 部分 IMPLEMENTED/PARTIAL，其余 PLANNED | 同上；0 ACCEPTED |
| 宿主 CI | HOSTED_BLOCKED_NO_RUNNER | GitHub Actions 历史 runner 未真实启动；保留原 workflow |
| V2 正式发布 | NOT RELEASE_READY | 见 RELEASE_GATES.md §6 |

## 10. 继续阅读

- 工程基线与环境：[BASELINE_20261019_r1.md](docs/v2/engineering/BASELINE_20261019_r1.md)
- 运行手册（隔离环境、全部测试入口、PG、浏览器、媒体、清理）：[RUNBOOK.md](docs/v2/engineering/RUNBOOK.md)
- 执行/数据契约（DTO/schema/版本/图端口/状态机/CAS/幂等/取消/错误分层）：
  [EXECUTION_AND_DATA_CONTRACTS.md](docs/v2/engineering/EXECUTION_AND_DATA_CONTRACTS.md)
- 安全与隔离：[SECURITY_AND_ISOLATION.md](docs/v2/engineering/SECURITY_AND_ISOLATION.md)
- 媒体与漫画契约：[MEDIA_AND_COMIC_CONTRACTS.md](docs/v2/engineering/MEDIA_AND_COMIC_CONTRACTS.md)
- 需求追踪矩阵：[REQUIREMENTS_TRACEABILITY.md](docs/v2/engineering/REQUIREMENTS_TRACEABILITY.md)
- 缺陷台账：[DEFECTS_20261019_r1.md](docs/v2/engineering/DEFECTS_20261019_r1.md)
- 本地最小 CI：[LOCAL_CI_MINIMUM.md](docs/v2/engineering/LOCAL_CI_MINIMUM.md)
- 历史与需求来源：[AI_NOVEL_STUDIO_V2_ARCHITECTURE.md](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md)、
  \`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md\`、\`docs/v2/engineering/spec/SPEC-2026.10.19-r1.txt\`