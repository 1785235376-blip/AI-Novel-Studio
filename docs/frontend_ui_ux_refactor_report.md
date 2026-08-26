# AI-Novel-Studio V0.6 前端 UI/UX 重构报告

日期：2026-08-24  
范围：`frontend/` 小说工作区、AI Inspector、`desktop-host/` 正式验收路径  
阶段：P0、Phase 1 已完成；Phase 2 Generation Workflow 代码与自动化已完成

## 结论

V0.6 本轮把两个最影响创作主路径的能力做成可验证闭环：左侧章节树与功能入口现在拥有独立滚动/定位上下文；AI 写作生成前可以主动刷新一次与当前写作方式、章节、附加要求和隐私目标对应的真实上下文预览。没有新增数据库结构，没有绕过 Service/Repository，也没有用静态演示数据填充空态。

## 真实数据与代码边界

| 体验 | Service / API | 前端入口 | Feature Flag |
|---|---|---|---|
| 左侧功能浮层 | 既有 panel state 与 localStorage，不改业务 API | `App.tsx` → `FeatureLauncher` | 无 |
| AI 角色上下文 | `AgentContextService.build`；`GET /api/agents/{agent_id}/context-preview` | `AiWritingPanel` → `AiContextPreviewPanel` | 无 |
| ContextService 扩展内容 | `writing_context` 内的 Lore/Narrative/Policy/Pack 字段 | Context Preview 来源行 | `ENABLE_LORE_CONTEXT`、`ENABLE_NARRATIVE_CONTEXT`、`ENABLE_CONTEXT_PACK_V2` |
| 写作目标 | `NovelService`；`GET /api/novels/{id}/writing-goal` | “当前写作目标”来源行 | 无 |
| 已确认 Canon | `NovelService.data_set`；`GET /api/novels/{id}/canon` | “已确认 Canon”来源行（local target） | 无 |
| 已批准世界规则 | Lore repository；`GET /api/novels/{id}/world-rules?status=APPROVED` | “世界规则约束”来源行（local target） | 既有 Lore 配置 |

写作方式与后端角色的映射为：续写/改写 → `writer`，润色 → `editor`，头脑风暴 → `planner`。刷新按钮是显式查询边界，输入框变化不会逐字触发网络请求；查询 key 包含小说、章节、角色、指令、目标和刷新序号。

## P0 交互与可访问性

- 章节区 `.sidebar-chapter-scroll` 只负责章节列表纵向滚动。
- `FeatureLauncher` 使用左侧栏作为定位上下文，浮层向上展开且有独立 max-height/滚动。
- 入口保留所有既有 feature ID、面板回调和分组记忆 key；选择入口不会关闭或改变业务面板状态。
- 打开后聚焦当前入口（没有当前入口时聚焦第一项）；关闭时回到启动按钮。
- 浮层支持外部点击、Escape、再次点击、Tab 焦点圈、方向键、Home/End；启动按钮和分组按钮提供 aria 状态及 Tooltip。
- `Tooltip` 的交互子树不再被 `aria-hidden` 隐藏，避免屏幕阅读器看不到可操作启动器。

## Phase 1 Context Preview 状态模型

预览面板只渲染 API 返回的值。每一行来源会显示：

- `已读取`：返回了非空数组、对象、字符串或数字；
- `无相关数据`：服务明确返回空值；
- `未配置`：可选 Context/Lore/Pack 能力未出现在响应，或云端安全目标拒绝展示未经筛选的关联资料；
- `加载中`：该来源仍在读取；
- `加载失败`：请求失败，可重试；
- `权限不足`：API 返回 401/403。

主上下文请求失败时不会显示“已读取”的来源卡片。Cloud target 不直接读取未经筛选的 Canon/World Rules，也不展示可能包含本地隐私的名称摘要；`privacy_omissions` 只显示数量和安全策略说明。空态均指向现有章节树、故事资料库、概览、Lore 审核或一致性检查入口。

## 验证记录

### Frontend

在 `D:/小说/AI-Novel-Studio/frontend`：

- `npm test`：通过（44 个测试文件、158 个测试，包含 P0 与 Phase 1 状态测试）；
- `npm run lint`：`UI token guard PASS`；
- `npm run build`：TypeScript 与 Vite production build 通过；
- Impeccable layout detector：新增 P0/Phase 1 文件结果为 `[]`。

Phase 1 新增 `AiContextPreviewPanel.test.tsx` 覆盖成功、loading、空/未配置、403 权限错误、operation/instruction/target 参数和无演示数据断言。

### Backend

使用仓库虚拟环境运行：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_phase6_agent_context.py -q
```

结果：3 passed。该测试继续验证角色范围、契约版本/hash、云端 privacy omission 和未知角色错误；本轮没有削弱或替换后端测试。

补充的 Lore/Context 合同回归为 5 passed、2 skipped；跳过项的原因是验收环境未启动 real PostgreSQL。全量 pytest 收集到 640 项，但在当前约 60 秒执行窗口内未完成；中止前暴露的两项既有失败为 generation variants 并发幂等断言和 P1 visual-continuity `TIME_JUMP_CUT` 断言，均不由本轮 UI/Context Preview 代码触发。

### DesktopHost

P0 正式验收包及证据目录：

- `D:/小说/.desktop-v1-acceptance-p0-20260824-r9`
- [1440×900 shell evidence](D:/小说/.desktop-v1-acceptance-p0-20260824-r9/p0-final-shell-1440x900.png)
- [1440×900 overlay evidence](D:/小说/.desktop-v1-acceptance-p0-20260824-r9/p0-final-overlay-1440x900.png)
- [1440×900 Escape/focus evidence](D:/小说/.desktop-v1-acceptance-p0-20260824-r9/p0-final-escape-1440x900.png)

标准本地 verifier 的关键结果：`application_ready=true`、`frontend=true`、`desktop_host_started=true`、`public_listeners=0`、`secret_exposure=0`、`exit_code=0`。矩阵证据覆盖 1280×720、1440×900、1920×1080 与 120 DPI。

Phase 1 最终包及证据目录：`D:/小说/.desktop-v1-acceptance-p1-20260824-r10`。同一正式 launcher 已进入真实小说工作区；可查看 [1920×1080 工作区证据](D:/小说/.desktop-v1-acceptance-p1-20260824-r10/p1-novel-workspace-1920x1080-clean.png) 和 [1440×900 入口证据](D:/小说/.desktop-v1-acceptance-p1-20260824-r10/p1-shell-1440x900.png)。P1 verifier 关键结果仍为 `application_ready=true`、`frontend=true`、`desktop_host_started=true`、`public_listeners=0`、`secret_exposure=0`、`exit_code=0`；正式 launcher 的窗口测量为 120 DPI。

## 已知限制与后续

- P0 Playwright E2E 依赖本机 PostgreSQL `127.0.0.1:5432`，当前服务未启动，因此该套 E2E 保持 blocked；不能把它写成通过。
- Unicode 工作区路径下的 DesktopHost 打包工具可能在 Postgres cluster 初始化阶段遇到编码问题；正式 verifier 使用 ASCII staging 目录完成了本地 host 验证。这是打包工具链限制，不是前端数据流程变更。
- Phase 2 生成时间线已进入代码与自动化完成状态；Phase 3 世界观 Dashboard、Phase 4 剧情规划及后续媒体/Agent Activity Center 保持 Deferred。本报告不把已有接口存在描述成已完成产品能力。

## Phase 2 Generation Workflow（2026-08-24）

- `GenerationWorkflowTimeline` 将既有生成闭环显示为“读取创作上下文 → 建立生成计划 → 生成章节草稿 → 作者审核”。
- 状态来源限定为真实请求边界：提交请求、后端返回 `job_id`、generation Job 的终态、多候选轮询结果、现有 accept/reject 动作；没有用计时器推进展示阶段。
- 既有 `generationRecovery` 在应用恢复后继续查询原 Job，时间线显示“已恢复任务”；恢复失败沿用真实错误与 retry API。
- 多候选允许成功方案继续审核，并为失败方案提供定向重试；单候选复用既有 Review 重试，避免重复控件。
- Review 继续连接现有 preview/diff、接受、拒绝、Revision/版本校验和冲突处理。接受前不改正文；接受后由现有 API 和章节刷新进入保存/版本流程。
- 未新增 API、数据库结构、Provider 绕行或 Feature Flag。本阶段是现有正式体验的产品化展示，默认启用。
- 自动化结果更新为 45 个前端测试文件、165 个测试通过；lint、production build、Impeccable detector 通过。
- 正式 DesktopHost `r12` 运行时通过：应用、前端与 DesktopHost 均启动，监听仅限 loopback，敏感信息暴露为 0，退出码为 0。因未注入真实 Provider 凭据，交互态桌面视觉矩阵仍待补证。

## Phase 3 World Building Dashboard（2026-08-24）

- 故事资料库顶部新增世界观总览，复用已有角色、关系、时间线、伏笔和地点查询，不重复发起或拼接模拟请求。
- 关系视图解析真实角色名称、关系类型、起始事件与状态；时间线按 `sequence` 排序并保留 `DISPUTED` 等冲突状态；伏笔视图区分首次章节、目标章节、关联事件和解决状态。
- Dashboard 记录点击后进入既有 Relationship/Timeline/Foreshadowing Editor，仍由原 Service 与 mutation 保存。
- 数据为空不生成角色或事件，单来源失败不会把其他来源伪装成失败；提供 loading、empty、error 与跳转操作。
- 前端完整回归 46 files / 169 tests，lint、build、Impeccable detector 通过；三组后端资源合同测试共 3 passed。
- Phase 3 `r13` 正式 DesktopHost verifier 通过：应用、前端与宿主启动成功，仅监听 loopback，`secret_exposure=0`，`exit_code=0`。

## Phase 4 Story Planning Workspace（2026-08-24）

- 新增故事规划层级视图，直接组合既有大纲、卷、章节、场景、时间线和伏笔数据；空字段显示“未记录”，不生成规划内容。
- 章节摘要展示能被当前合同证实的目标、冲突、事件、伏笔、场景与状态；章节级人物变化没有聚合接口，界面明确标记未记录。
- 左侧章节树在本机模式支持相邻章节拖拽，复用既有 move API。保存失败后刷新恢复服务端顺序；协作模式因后端禁用 move 而隐藏拖拽。
- 完整回归为 47 files / 172 tests，lint/build 通过；后端定向回归 8 passed / 1 skipped。r15 正式 DesktopHost verifier 全部通过。

## Phase 5 Visual Context（2026-08-24）

- 图片工作区新增只读 Visual Context，复用既有小说、角色、地点、卷、场景、章节与资产查询。
- 用户可逐项确认是否纳入实际生成提示词；不会静默写入 Canon，也不把未配置 Provider 当作可用能力。
- 新增状态覆盖空项目、加载、错误和无关联资产；r16 正式 DesktopHost verifier 通过。

## Phase 6 Capability Status Center（2026-08-24）

- 非小说模块统一显示图片、视频、声音、资产、插件和 Workflow 的真实能力状态。
- 状态来源为既有健康检查、Provider、插件运行时和 Workflow API；未实现能力明确标注，不以接口存在替代生产可用。
- 状态中心测试、lint、build 和 r17 DesktopHost verifier 通过。

## Phase 7 Agent Activity Center（2026-08-24）

- Agents 入口新增 Agent Activity Center，读取现有 Agent Job Runtime，显示任务状态、来源、输入/输出摘要、时间、错误及重试关系。
- 确定性 Agent 文案限定为规则校验；既有 Job 历史、任务创建、审核、重试和应用流程保持不变。
- 测试、lint、build 和 r18 DesktopHost verifier 通过。

## V0.6 Final Acceptance（2026-08-24）

- 前端全量回归：50 files / 176 tests passed。
- 后端定向回归：11 passed / 1 skipped；跳过项为真实 PostgreSQL 环境依赖。
- 最终 packaged DesktopHost r18 verifier 通过：应用、前端与宿主启动，loopback-only listeners，secret exposure 0，exit code 0。
- V0.6 产品化阶段完成；Phase 8+ 保持 Deferred。
