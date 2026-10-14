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
- 模式字段 `interface_mode` 为可选：写入时合并进既有位置记录并保留 module/view/stage/graphId/runId；**没有有效记录时返回 false，绝不为了存模式而伪造一个位置**。
- 纯呈现：两种模式共用同一份项目、资产、任务、Graph 与草稿；切换不转换、不复制、不删除、不触发模型。

## D12 — 画布分组/注释/折叠只做会话内呈现态，不新增持久化图字段

- 事实：`studioGraphTypes` 的定义只有 `nodes/edges/viewport/(schema_version/title)`，没有分组、注释或折叠字段；本轮无法在不改动冻结图契约的前提下持久化它们。
- 裁决：UX-04 的 `LocalCanvasState`（`canvasops-local/1`）是**会话内**状态，随身份变化丢弃，绝不写入已保存创作图；非法输入失败关闭为空态并给出中文原因。真要持久化，必须由原 owner 做**有类型、向后兼容**的扩展（含迁移与测试），单独立项。
- 附加：自动布局是确定性纯函数、只改节点坐标；但**提交**必须走原控制器的 `change()` 才能进入既有 past/future 撤销栈——本轮的组合栏只提供只读预览与差异分类，不私自改图。
- 连接合法性**只有** `graphDraft.connectionIssue` 一个权威：新增建议面板只按目录声明做同类型预筛，随后逐行保存 `connectionIssue` 的原文与结论，绝不自行判定“可以连接”。

## D13 — 素材浏览器只读 + 传参只传引用

- 事实：`AssetLibraryService.public()` 会剥离 `_text_result_review`；关系投影只声明 ASSET/CHAPTER/SCREENPLAY 目标；`storage().physical_cleanup_available == False`。
- 裁决：
  - UX-03 面板**只读**：不写标签、不改许可、不物理删除；删除只做**影响范围报告**（`physical_delete:false`、`content_removed:false`、阻塞引用列出）。
  - 复审状态在 `public()` 下只能是 `UNREVIEWED`，除非调用方用 `workspace.asset_index()` 的行显式注入——不得凭空推断“已审”。
  - “送往图片/视频/分镜/时间线”只通过回调发出 `{asset_id, version, digest}`，**不执行目标模块**；实际绑定发生在目标工作区。
  - 镜头/节点/时间线归属在关系 owner 未声明时显示“未核实”，绝不用 ID 猜测。
  - 版本对比只用 owner 已披露的候选（无版本列表端点）。

## D14 — 第二批不新增后端契约

本批（UX-03 + UX-04）**没有**后端改动、没有数据库迁移、没有新增端点；因此 PostgreSQL 复验复用上一批的 owned cluster 即可，PG 收据 `ux-product-pg` 仍然有效，本批不重复启动。

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

## D15 — CONTENT_POLICY_FRAMEWORK: RESERVED（预留，不是实现）

- 目标：为未来的项目级内容策略框架预留扩展位；**不**实现 Mature/NSFW 模式、**不**新增审核系统、**不**改变当前用户流程。
- 落点：复用既有偏好 owner `WorkspacePreferences`，新增**可选** `content_policy: Literal['STANDARD','MATURE','RESTRICTED','CUSTOM'] | None = None`；缺省/历史值一律读作 `STANDARD`（`app/creative/content_policy.py::effective_content_policy`）。**不新建存储**。
- 两处必须的兼容性修正（否则会破坏旧项目）：
  1. 原 `_preference_view` 用 `row[key]` 遍历全部模型字段——一旦新增字段，**旧行会 KeyError**、新字段还会泄漏到现有 wire。现改为**冻结的 3 字段投影**（`intents/preset/custom_intent` + `version`）并用 `row.get`，因此旧项目照常打开、任何既有客户端收到的字节不变。
  2. `preferences()` 中 `content_policy` 为 `None` 表示"不修改"，从 payload 中剔除；否则一次无关偏好编辑会把已保存的策略静默重置。
- 预留接口（纯函数，仅供未来使用，今天没有任何行为读取它们）：`asset_policy_for`（资产继承来源项目策略；**不改动资产 owner、不加资产字段**）、`model_content_policy_support`（只读模型条目的可选声明，**永不过滤/启用/启动模型**）、`export_notice`（导出阶段的通知描述符，**不渲染、不阻塞导出**）。
- UI：本轮**不加**任何按钮/开关/设置项；未来位置为 Settings → Advanced → Content Policy。
- 安全边界：策略不是绕过安全限制的手段；未来仍需用户责任、平台规则、年龄限制与内容审核策略。
- 验证：`tests/test_v2_content_policy_reservation.py` — File 与**真实 PostgreSQL**（fresh 库、20 迁移、空库证明、正常停止）双后端通过；既有 Phase7 与 studio seam 套件同时回归通过（新增字段零回归）。
- 标记：`CONTENT_POLICY_FRAMEWORK: RESERVED`（**不是** IMPLEMENTED）。

## D16 — 第三批的集成方式（不新增第二引擎、不静默替换动作）

- **UX-05 按需打开**：镜头工作区初版直接挂在创作模块检查器内，挂载即读取，导致既有 `CreativeWorkspace.test.tsx` 2 项失败（不改既有测试）。裁决：改为**显式"按需打开镜头工作区"**——默认不读取、不产生重复 DOM/请求；这是与仓库既有"明确读取"风格一致的取舍。
- **UX-05 身份与顺序分离**：`shot_id` 是身份（owner 的 `shot_versions`），`number` 只是显示序号；重排保持身份并**如实报告**会失效的绑定，不声称连续性保证。
- **UX-06 挂在既有控制器内**：剪辑工作台渲染在 `StudioTimelineEditor` 的 Panel 内，消费**同一个**控制器与草稿；为传递显示用项目身份给 `StudioTimelineEditorProps` 增加**可选** `projectId`（向后兼容）。
- **UX-06 编辑只映射已接线语义**：`onEdit` 仅把 `clip.split` / `clip.duplicate` / `clip.move` 交给控制器既有函数；其余（trim/slip/remove/update）由 owner 支持但**尚未接线**，一律给出可见拒绝并说明原因，**绝不静默替换动作**或假装成功。
- **限额不可抬高**：`limitsNotice` 只读展示 owner 的真实限额，任何高于 owner 的输入都被拒绝并报告。
