# PoemSeed Studio V2 贡献与 PR 审核指南

适用于 [源码导航](README.md) 所记录的 V2 产品树。先读根 [AGENTS.md](../../AGENTS.md)，再看目标模块的原服务、调用方及相邻测试。基线未提供统一的 `CONTRIBUTING.md` 或 `CODEOWNERS`；本文整理贡献和人工审核入口，不建立新的权限机制或修改现有 owner。

## 先划定一个可审核的切片

在 PR 中写明实际基线 SHA、具体触发条件和改后行为、涉及文件、数据 owner、前后端契约、运行前置条件。一个模块名通常跨越视图、controller、client、API、领域服务和存储，按行为划分切片，避免把整个目录视为单人专有。

保留既有运行时合约；V2 不拆成可安装模块，第三方市场后置。新 UI 继续消费 AppShell 与 ModuleWorkspace。可见界面改动按 [UI 技能](../../.codex/skills/ai-novel-studio-ui/SKILL.md)、[设计系统](../ui/design_system.md) 和 [受保护表面](../ui/protected_ui_surfaces.md) 执行；系统级调整走既有 Design System Change Request。

## 按变更类型选择最低检查

下表是针对受影响行为的起点。补足新增风险涉及的反例；跨层变更同时覆盖对应各行。文档修正不需要为镜像实现而增加测试，也不因示例提到某个命令就运行整个产品验收。

| 变更类型 | 最低检查 / 应有证据 | 可从这些既有测试开始 |
| --- | --- | --- |
| 文档、导航链接、命令说明 | `git diff --check`；相对链接与文件存在；命令参数、工作目录、版本和环境变量对照实际脚本/manifest。区分示例、静态核对和真实执行结果。 | 本切片只需这些静态检查。不要为了检查文档而导入 `app.main`。 |
| 局部 UI、文案与可见布局 | 受影响组件测试；前端 lint/build。可见布局、焦点、导航或几何变化还需相关真实浏览器/视觉检查，按现有设计系统选择用例。 | [PromptEditorPanel.find.test.tsx](../../frontend/src/prompt/PromptEditorPanel.find.test.tsx)、[DirectorWorkspace.test.tsx](../../frontend/src/director/DirectorWorkspace.test.tsx)、[tests/visual](../../frontend/tests/visual)。 |
| controller、client、异步状态与导航 | 成功/失败、迟到响应、scope/会话切换、卸载、dirty、取消和 StrictMode；严格 DTO 拒绝错误或缺失字段。 | [PromptWorkspace.detailRace.test.tsx](../../frontend/src/prompt/PromptWorkspace.detailRace.test.tsx)、[IndependentStudioIdentity.regression.test.tsx](../../frontend/src/creative/IndependentStudioIdentity.regression.test.tsx)、[GraphDirectorRunOverview.test.tsx](../../frontend/src/creative/GraphDirectorRunOverview.test.tsx)。 |
| API / 请求响应契约 / 功能开关 | 隔离的真实 mounted API 用例，正常与拒绝路径；检查原父 router、依赖、别名、严格字段和 public/private 输出。涉及目录产物时协调原生成器与来源核对。 | [test_v2_independent_workspace_api.py](../../tests/test_v2_independent_workspace_api.py)、[test_surface_api_catalog.py](../../tests/test_surface_api_catalog.py)；仅检查关联端点不能替代全目录来源核对。 |
| 领域服务、Creative 文档或 Graph | 受影响原服务用例，加一条真实调用链/API 检查；覆盖 stale source、错误版本、幂等和原记录保留。 | [test_v2_creative_foundation.py](../../tests/test_v2_creative_foundation.py)、[test_v2_graph_text_assets.py](../../tests/test_v2_graph_text_assets.py)、[test_v2_graph_text_assets_api.py](../../tests/test_v2_graph_text_assets_api.py)。 |
| 权限、身份、scope、incarnation 或提交锁 | 开启需要的真实 collaboration runtime；覆盖跨 scope、撤权、会话变化、项目删除后重建、提交前再次拒绝、并发锁顺序，拒绝时无部分写入。 | [test_authorization_foundation.py](../../tests/test_authorization_foundation.py)、[test_collaboration_scope_api.py](../../tests/test_collaboration_scope_api.py)、[test_v2_authority_commit_leases.py](../../tests/test_v2_authority_commit_leases.py)。 |
| 存储、schema、迁移或恢复 | 受影响 File 与真实 PostgreSQL 的契约/并发证据；旧记录读取、冲突、事务原子性和新目标恢复。数据库未配置须明确报告，不能用 File 结果宣称 PostgreSQL 通过。 | [test_v2_independent_workspace.py](../../tests/test_v2_independent_workspace.py)、[test_branch_revision.py](../../tests/test_branch_revision.py)、[test_r2_backup_restore.py](../../tests/test_r2_backup_restore.py)；数据库迁移源见 [schema 说明](../../database/schema/README.md)。 |
| 媒体 Provider、job、Graph 执行与审核 | 原 job/API 测试；预览与发送分离，来源/版本/摘要、候选字节、超时/中断/重启、UNKNOWN、重复发送防护、明确审核和来源权限。涉及真实格式或执行器的改动还需对应小型实物检查。 | [test_v2_independent_media_job.py](../../tests/test_v2_independent_media_job.py)、[test_v2_image_runtime_owner.py](../../tests/test_v2_image_runtime_owner.py)、[test_v2_image_runtime_api.py](../../tests/test_v2_image_runtime_api.py)。 |
| 时间线、NLE、音频编辑或格式交换 | 受影响纯编辑操作和 controller/API；轨道锁、精确来源、时长边界、dirty/CAS、历史恢复及原 job。更改实际编码/渲染时补格式与字节证据。 | [timelineOps.test.ts](../../frontend/src/nle/timelineOps.test.ts)、[test_v2_timeline_trim_handoff.py](../../tests/test_v2_timeline_trim_handoff.py)、[test_v2_audio_editing_pipeline_api.py](../../tests/test_v2_audio_editing_pipeline_api.py)。 |
| 原生进程、Windows 文件、Host、OCR、模型生命周期 | 对应进程/文件边界与 API 拒绝用例；在受影响平台核对实际启动、停止、资源限制与中断。mock/协议测试与真实 Windows/原生/模型验收分别报告。 | [test_v2_media_probe_lifecycle.py](../../tests/test_v2_media_probe_lifecycle.py)、[test_local_host_session_recovery.py](../../tests/test_local_host_session_recovery.py)、[test_research_native_ocr_recovery_additive.py](../../tests/test_research_native_ocr_recovery_additive.py)。 |

### 已核对的检查命令入口

后端从 worktree 根运行，使用 [run_v2_checks.py](../../scripts/run_v2_checks.py)；它在导入前设置独立 profile，并保留命令、退出码、源码哈希和日志。`label` 只能用小写字母、数字和连字符，同一标签会重写同名回执，给不同开发者/检查分配唯一标签。

```powershell
$py = (Resolve-Path .venv\Scripts\python.exe).Path
$env:PYTHONUTF8 = '1'
& $py scripts/run_v2_checks.py review-workspace -- python -m pytest tests/test_v2_independent_workspace_api.py -q --basetemp .runtime/v2-checks/review-workspace/pytest -p no:cacheprovider

# 只有涉及真实协作授权的检查才加此开关；它必须位于 label 之前。
& $py scripts/run_v2_checks.py --collaboration-runtime review-authority -- python -m pytest tests/test_v2_authority_commit_leases.py -q --basetemp .runtime/v2-checks/review-authority/pytest -p no:cacheprovider
```

替换成受影响的现有测试文件与唯一标签。回执在 `docs/delivery/v2-development/<label>.json` 和 `.log`，临时数据在 `.runtime/v2-checks/<label>`；提交前核对生成物、私有信息及工作区 diff。测试文件名与断言仍需针对具体改动阅读，上述两条不是通用全套门禁。

前端命令同样从 worktree 根执行，具体脚本在 [package.json](../../frontend/package.json)，Vitest 配置在 [vite.config.ts](../../frontend/vite.config.ts)：

```powershell
pnpm --dir frontend exec vitest run src/creative/GraphDirectorRunOverview.test.tsx
pnpm --dir frontend lint
pnpm --dir frontend build
```

`lint` 当前运行设计 token 检查；`build` 执行 `tsc -b && vite build`。更改测试发现规则时用 `pnpm --dir frontend test:discovery`。jsdom 单测没有真实布局、CSS 和焦点模型，不能作为浏览器验收。视觉入口是 `pnpm --dir frontend test:visual`，其配置自行在 5174 启动 Vite，浏览器前置条件需另核对。Studio 真实浏览器入口 `pnpm --dir frontend e2e` 使用已安装系统 Edge/Chrome，要求事先启动应用；变量、数据写入与用例范围见 [e2e/README.md](../../frontend/e2e/README.md)。它不自动下载浏览器，也不能默认接入日常使用的实例。

真实 PostgreSQL 使用 [run_v2_postgres_checks.py](../../scripts/run_v2_postgres_checks.py)。调用前必须已有 `pg_ctl` 与本 worktree `.runtime` 下的专用临时集群；该脚本不下载、安装或初始化集群，会管理所指定集群的启动/停止并为 fresh database 应用迁移。命令模板如下，变量均须按实际资源赋值：

```powershell
# $py: 当前 worktree 的 Python 绝对路径。
# $pgBin: 已有便携 PostgreSQL bin；$pgData: 当前 worktree .runtime 下已有的集群。
# $pgPort: 已确认空闲端口；$pgDatabase: 唯一的 v2_ 前缀数据库名。
# $pytestBase: 当前 worktree 内已预先创建的独立测试目录绝对路径。
& $py scripts/run_v2_postgres_checks.py --pg-bin $pgBin --data $pgData --port $pgPort --database $pgDatabase --fresh-database review-workspace-pg -- $py -m pytest tests/test_v2_independent_workspace.py -q --basetemp $pytestBase -p no:cacheprovider
```

`--user` 是数据库连接角色，标签是位置参数；协作检查可在标签之前增加原 `--collaboration-runtime`。如果缺这些前置条件，记录缺项和未验证行为，不改成连接共享数据库或临时扩大权限。

## 跨模块契约审核

1. **读与执行分离。** 导航、目录、总览、预览不能隐式激活项目、创建 job、调用 Provider、注册或启用模型。对照 [只读生产操作契约](../v2/production-operation-contracts.md) 与 [真实生产执行](../v2/production-execution.md)。
2. **身份来自原授权链。** 沿 `app.main` 中间件、父 router 和原 `invoke`/guard 核对可信会话、成员权限、project/storyline/branch 及 incarnation。不要相信请求中自报的 actor，也不要把隐藏按钮当成后端权限检查。
3. **快照与提交必须一致。** 使用原 ID、version、digest、来源 kind 与 job 绑定；在发送、保存、发布和审核前重新核对。CAS 冲突应展示原候选/版本让用户选择，不自动合并、覆盖或重新生成。保留 `CreativeProjectStore` 的原事务和锁顺序。
4. **执行成功与人工批准分开。** SUCCEEDED、可下载文件、已发现模型、目录 action 和页面可见性都不能推导为已批准、可执行或已满足验收。审核绑定实际 job/version/request digest 与已查看 output digest。
5. **前端保持当前身份与意图。** 保留 epoch/Abort、卸载清理、dirty guard、同意失效和私有 Blob URL 释放。旧 scope 的响应不能清空新文档草稿、替换当前对象或维持旧权限；UI 采用动作继续走原 controller/client。
6. **隐私与模型路由继续由原 owner 决定。** 来源许可声明不能替代 cloud grant；间接父来源也要验证。不要新增 endpoint/密钥到公共 DTO、日志或 localStorage，不从本地发现推导自动启用/下载。参见 [source_privacy.py](../../app/source_privacy.py)、[net_safety.py](../../app/net_safety.py) 和 [模型 Provider 契约](../v2/model-provider-contracts.md)。
7. **兼容性从实际调用方核对。** 请求 DTO、严格解码器、功能依赖和 schema 版本要一起看；未知字段/状态保持明确拒绝或未知，不能映射成空列表、零成本、已批准或可重试。新 schema 不应改写旧 schema 的执行含义。

## 数据与不确定结果的恢复

HTTP 超时、取消请求、断开连接或进程退出不证明原操作未提交。先读取原 job / 文档版本与回执；UNKNOWN 保留 UNKNOWN，按原 owner 提供的 refresh/reconcile 恢复。不得换 request ID、重放 execute 或手工改状态来“修复”。时间线、Graph、漫画 handoff 和 OCR 的具体恢复入口各在原 owner 内，不能共享一套推测重试逻辑。可复用 [生产回执恢复说明](../v2/production-receipt-recovery-20261016.md)、[OCR 显式恢复](../RESEARCH_OCR_EXPLICIT_RECOVERY.md)、[漫画时间线恢复测试](../../tests/test_comic_timeline_handoff_recovery.py)。

文档历史 restore 应保留历史记录并走原版本检查；不能把历史正文直接覆盖成当前文件。更改 schema/存储时核对 [database/migrations](../../database/migrations)、原迁移调用及跨 backend 结果，不编辑已经发布的旧迁移来伪造新状态。

离线备份/恢复的事实以 [app/backup_restore.py](../../app/backup_restore.py)、[scripts/backup.ps1](../../scripts/backup.ps1) 和 [scripts/restore.ps1](../../scripts/restore.ps1) 为准：先停止应用和所有 writer，备份需显式 `-OfflineConfirmed`；恢复必须指定新的目录，PostgreSQL 使用新的目标数据库，校验 manifest/字节完整性后再启动。`restore.ps1 -Force` 已明确拒绝，不支持覆盖原数据。`-DatabaseUrlEnv` 传环境变量名，不把凭据写入命令或回执。不要只复制小说正文并宣称包含资产、修订、权限、任务与来源关系的完整恢复。

## 多人并发时的文件归属建议

这是对现有 owner 的协作建议，不等同于 `CODEOWNERS` 或新增审批权。开工时约定具体文件和行为，契约变动先对齐调用方；只在自己的 worktree 提交。共享文件按一位协调者一个合并窗口处理，其他切片给出必要的接线需求。

| 文件 / 边界 | 建议的分工方式 |
| --- | --- |
| `app/main.py`、`app/api.py`、`app/dependencies.py`、`app/experimental/api.py` | 各模块先在原领域文件内完成变更，装配接线由集成方统一核对，避免复制服务实例或丢失授权闭包。 |
| `frontend/src/App.tsx`、`ui/ModuleWorkspaceRoutes.tsx`、`ui/AppShell.tsx`、通用 token / primitives | 功能通过原插槽和模块 contract 提供内容；壳层由既有设计系统 owner 协调。不要各自重排共享导航。 |
| `app/creative/workspace_api.py`、`production_execution*.py`、`graph*.py`、`frontend/src/creative/studio*Client.ts`、共享 types / controller | 指定本轮具体文件 writer；请求/响应模型、能力与调用方一起审核，按原服务落盘，不创建并行 owner。 |
| `frontend/src/creative/useStudioTimelineEditor.ts` 与 `frontend/src/nle`、Prompt / Director 的共享 controller | 视图与纯操作 helper 可分片；共享 controller 的状态转移由同一协调者整合，复核 scope、dirty、CAS 与取消路径。 |
| `database/migrations`、公共 schema、`pyproject.toml`、`frontend/package.json` / lockfile | 先协调迁移顺序、接口和依赖理由；避免两个切片生成相互覆盖的迁移或独立重写 lockfile。 |
| `API_CATALOG*`、`UI_SURFACE_CATALOG*`、功能矩阵、根 README、CI 配置 | 交由集成方按最终产品树统一处理；复用原生成器和证据，不手改来源哈希或把历史 PASS 移给新树。本指南不修改这些文件。 |
| 测试与证据 | 共享 fixture 的更改需通知消费者；每个切片使用独立标签、端口、profile 与输出目录。保留原失败和 skip，报告新增结果所对应的准确源码。 |

## PR 作者与审核者清单

- [ ] 说明具体触发条件、改后行为、实际基线和文件范围；无附带重构、安装包拆分或市场能力扩张。
- [ ] 指明写入数据和执行动作的原 owner，列出调用方、请求/响应或 schema 的变化及兼容边界。
- [ ] 核对 feature gate、可信身份、scope/incarnation、撤权与提交前 recheck；拒绝不产生部分写入或来源泄漏。
- [ ] 核对 CAS、来源与输出摘要、幂等、dirty/异步竞态；恢复保留 UNKNOWN，不自动重放或覆盖。
- [ ] 涉及 UI 时复用原设计系统与 controller，并提供受影响的视觉/焦点/几何证据；受保护表面遵循既有流程。
- [ ] 按变更类型列出真实执行的命令、环境、源码版本、结果、skip 和失败；静态检查、File、PostgreSQL、浏览器、Windows、GPU/模型分别说明。
- [ ] 前置条件不足时准确标出未验证范围及阻断；不以本地单测或旧回执宣称完整产品验收。
- [ ] 迁移、旧数据和恢复风险有对应说明；未提交用户数据、凭据、模型权重或无关运行产物。
- [ ] 与其他切片核对共享文件和最终差异；检查 `git diff --check`，提交只包含授权范围。
- [ ] 提交与推送、整合、发布各自按任务授权进行；源码提交本身不改变 owner、CI 权限、分支保护或验收状态。
