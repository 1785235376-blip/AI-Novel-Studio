# UX-PRODUCT 裁决记录

只记录本轮真正必要、且会影响后续实现的裁决。历史裁决（Phase7 的 note/preset 等）不在此重开。

## D1 — 新手/专业模式绑定 Studio 自有视图定位 owner（`Layout.density` 不可达，已修正）

- 初始判断：既有 `app/experimental/ux.py::Layout.density`（`normal|advanced`）可作为模式落点。
- **核实后修正**：该 owner 的服务端路由是 `/api/novels/{nid}/experimental/workspace/resume`，其中 `access()` 强制 `require_flag('workspace_tools_v2')`，交互段还要求 `workspace_interaction_v1`；这两个开关**不在 Studio 路径启用的标志集**（`narrative_production_v2`、`asset_lineage_v2`）内，且 Studio 前端当前完全不调用该端点。
- 裁决：模式改绑 **Studio 自有的本地视图定位 owner** `frontend/src/creative/studioWorkspaceResume.ts`（`schema=1`、字段白名单、per-project key），新增可选 `interface_mode: 'NOVICE' | 'PROFESSIONAL'`：
  - 向后兼容：旧记录无该字段仍有效；含非法值的记录判 `INVALID` 而不是采用。
  - **默认保持今天的完整界面（`PROFESSIONAL`）**：新增一个呈现模式**不得**改变既有用户的界面或隐藏他们已在用的功能。新手模式是**显式选择**（入口面板或模式开关）。初版曾把新手设为默认，导致 28 个既有测试因“创作图”按钮被隐藏而失败——该失败与修正均保留在记录中。
  - 跨项目记录不被采用；非法值判 `INVALID`。

## D10 — 入口面板放在独立的“创作开始”视图，不自动覆盖素材视图

- 事实：初版把“创作开始”面板自动渲染在素材视图，与既有 `StudioWorkspacePreferencesForm` 同时渲染“图片设计”等意图标签，触发既有测试的重复元素错误。
- 裁决：新增 `START` 视图并在既有视图按钮行提供“创作开始”入口；面板只在该视图渲染（首次进入空项目时才激活控制器）。
- 理由：① 不修改任何既有测试或其断言；② 不打扰已有工作流；③ 同时比自动插入更易发现，且与既有按钮行风格一致。
- 同理，任务中心以 `TASKS` 视图入口接入，不在素材视图里抢占版面。

## D11 — 模式与视图枚举的兼容性

- `StudioWorkspaceView` 增加 `START`、`TASKS`；旧记录只含 `ASSETS|GRAPH|PRODUCTION` 仍有效；未知视图判 `INVALID`（不静默降级）。
- 模式字段 `interface_mode` 为可选；写入时不伪造位置（无有效记录时 `rememberLocalStudioInterfaceMode` 返回 false，模式随下一次位置写入一起保存）。
  - 即时持久化：`rememberLocalStudioInterfaceMode` 合并进既有记录并保留 module/view/stage/graphId/runId；**没有有效记录时返回 false，绝不为了存模式而伪造一个位置**。
  - 纯呈现：两种模式共用同一份项目、资产、任务、Graph 与草稿；切换不转换、不复制、不删除、不触发模型。
- 理由：不为补一个呈现开关而扩大功能标志或新增第二偏好存储；`normal|advanced` 的语义差异（新手=任务卡/主操作，专业=节点/参数/Inspector/来源详情）由前端渲染实现即可。
- 验证：`frontend/src/creative/studioWorkspaceResume.test.ts` 8 passed（含新增 5 项：往返、默认值/未知项目、非法值拒绝、合并保留其余字段、不伪造位置）。

## D1b — 模式切换的原始备选（记录以便日后重新评估）

若后续 Studio 路径正式启用 `workspace_tools_v2` + `workspace_interaction_v1`，可将模式迁到服务端 `Layout.density` 以获得跨浏览器一致；届时应作为独立变更（标志启用 + 迁移 + 双后端测试）而不是顺手改动。

## D2 — 任务中心与审核收件箱复用既有 owner，不新增第二队列/审核系统

- 事实：`WorkspaceToolsService.tasks`（`projected_task` 已统一 safe code、把非 `STAGES` 状态归为 `UNKNOWN`、保留 provider/model 脱敏标识）与 `UnifiedReviewInbox`（domain/status/stale/search、`allowed_actions`、`batch_actions`、`batch_semantics='PER_ITEM_CHECKPOINT'`、`unavailable[]`）均已存在并有 API。
- 裁决：新界面只做**只读聚合 + 原命名动作**（读取/取消/预览候选/审核/恢复/重建）；不发明状态、不伪造进度百分比、不承诺全有或全无的批量。
- 理由：任务书 6.2/6.4/6.11 明确要求保留 owner 原生语义与逐项结果。

## D3 — 创作意图沿用 Phase7 已裁决契约

- `POST …/workflow/intent` 只接受 `preset`（无 `note`）；GET 的 `values[].custom` **不得**原样回传 POST，请求元素必须显式重建。
- `expected_version=null` 仅表示"原意图行尚不存在"；项目激活后必须提交实际读到的版本。
- 任何新字段都必须走原 owner 的类型 + 持久化 + 迁移 + 测试，不得用未知 JSON 键或复制响应对象绕过。

## D4 — 偏好类写入保持"整体替换 + CAS"语义

`PUT …/studio/preferences` 与 `POST …/workflow/intent` 均为带 `expected_version` 的整体替换。新增字段一律带默认值并保持向后兼容；客户端必须发送它打算保留的字段。冲突返回 409 并重新读取，不做盲目重试。

## D5 — 界面分区复用 `Layout.section`

`Layout.section` 已含 `'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'`。任务中心与"继续/引导"分区绑定该字段，不自建第二套视图定位存储；本地草稿视图定位继续沿用 `frontend/src/creative/studioWorkspaceResume.ts`。

## D6 — PostgreSQL 缺口按任务书 16.2 处理

先在授权目录、既有测试脚本与历史 receipts 中确认是否存在可复用的便携 PostgreSQL；存在则在本轮独立临时目录/新库/进程级端口内运行原迁移与必要开发测试并保留身份、空库、正常停止证据；确无则如实 `NOT_CONFIGURED`，**不**安装系统数据库服务、不改防火墙、不以两个端口关闭就断言整机无环境。

## D7 — 前端 `python3` 缺口用仓库既有跨平台解析修复

先同源对照确认原因，优先复用仓库已有的解释器解析/测试启动配置，让测试调用已核实解释器；必要修复**独立提交并加回归**。不删除用例、不新增跳过、不改预期断言、不复制/改名 Python 可执行文件、不全局改 PATH。

## D8 — QingJian 全面暂停

不修改 QingJian 仓库、不启动青简、不做双产品运行；UX-08 的助手只使用 Studio 自身确定性数据，青简入口保留**隐藏/禁用**扩展位，不得显示"已连接"或虚构导师建议。

## D9 — 受保护 UI 面不变

`GlobalHeader`、`ModuleSwitcher`、`ContextBar`、`AppShell` 布局、`LeftSidebar`/`RightInspector` shell、`StatusBar`、主题 token 与核心 primitives 为受保护面；本轮只作为消费者复用。确需系统级变更时按 `docs/ui/design_system.md` 的 Design System Change Request 流程，并先继续不依赖该变更的功能。
