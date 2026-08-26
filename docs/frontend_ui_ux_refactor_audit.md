# AI Novel Studio 前端 UI/UX 重构审计

日期：2026-08-23  
范围：`frontend/` 与 `desktop-host/` 的桌面创作工作区体验  
阶段：Phase A 审计，未修改生产 UI 代码

## 设计读取

这是面向长时间写作与影视化生产的桌面生产力工作区，使用者需要高密度信息、稳定的键盘操作和可预测的面板布局。视觉方向应为克制的编辑器工作台：中性底色、单一强调色、低动效、高可读性；不采用营销页、渐变光晕或装饰性卡片堆叠。

本次参考了 `design-taste-frontend`、`impeccable`、`shadcn` 与 `ui-ux-pro-max` 的审计规则。`ui-ux-pro-max` 的本地设计系统检索已执行，结果被作为约束参考；Design MD Collection / VoltAgent awesome-design-md 未在仓库中发现，标记为 `DEFERRED`，不伪造引用。

## Architecture Audit

### 当前结构

- `frontend/src/main.tsx` 负责入口、路由式页面选择、QueryClient 和懒加载。
- `frontend/src/ui/AppShell.tsx` 已提供全局头部、模块切换、上下文栏、Sidebar/Main/Inspector 三栏和状态栏。
- `frontend/src/ui/primitives.tsx` 提供 Button、IconButton、Badge、Panel、EmptyState 等基础组件。
- `frontend/src/ui/tokens.css` 与 `frontend/src/ui/ui.css` 提供现有设计 token 和 Shell 样式。
- `frontend/src/App.tsx` 约 1,590 行，包含状态协调、API 调用、模块路由和多个业务面板实现，是当前主要的可维护性风险。
- 小说、资产、视觉、音频、剧本、工作流和插件面板已经按文件拆分，且存在对应测试。
- `desktop-host/AI.NovelStudio.DesktopHost` 是真实 .NET 8 Windows DesktopHost；WebView2 运行和 packaged host 相关代码位于宿主工程及 `frontend/src/packagedHost.ts`。

### 分类

| 区域 | 决策 | 依据 |
|---|---|---|
| `AppShell.tsx` 三栏壳 | KEEP + REFACTOR | 已覆盖核心桌面布局，但缺少面板尺寸持久化、窄窗口行为和完整语义状态 |
| `primitives.tsx` | KEEP + EXTEND | 有基础 API，应补充 loading、tooltip、separator、dialog/confirm 和统一尺寸契约 |
| `tokens.css` | REFACTOR | token 已集中，但颜色、字体和尺寸命名不完整，编辑器与 UI 字体耦合不够清晰 |
| `ui.css` | REFACTOR | Shell 与历史样式混合，局部选择器覆盖较多，需分层为 foundation/shell/editor/module |
| `App.tsx` | SPLIT | 编排与业务面板混杂，先抽出模块配置、scope/status、novel workspace orchestration，再动视觉 |
| `src/novel/*` 面板 | KEEP | 业务边界清晰、已有测试；迁移时只替换共享 primitives 和布局契约 |
| `main.tsx` | KEEP | 入口职责稳定；仅在增加错误边界或可访问加载状态时小幅调整 |
| 后端 API/模型 | KEEP | 本次 UI 重构不改变合同 |
| DesktopHost | KEEP + AUDIT | 需以真实 packaged 运行验证窗口尺寸、WebView2 缩放、postMessage credential channel |

## UX Audit

### 已有优点

- 模块切换使用 tab 语义并显示当前模块。
- Inspector 支持折叠，Escape 可关闭。
- 全局搜索入口预留 `Ctrl + K`，但当前为 disabled，属于未完成交互。
- UI primitive 已集中处理 focus-visible、按钮变体和状态徽章。
- 大部分复杂工作流已经有独立面板，适合渐进迁移。

### 主要问题

1. `App.tsx` 的条件分支重复创建 `AppShell`，模块之间的 Sidebar/Inspector/status 契约不统一。
2. Inspector 仅支持开关，不支持宽度拖拽、宽度记忆和面板级折叠状态。
3. 全局搜索是禁用输入，没有打开搜索、结果、空态和快捷键闭环。
4. 模块 tab、icon button、树节点的最小点击尺寸和 tooltip 规则未形成统一契约。
5. loading、error、empty、dirty/saving/saved 状态在不同面板中表达不一致。
6. 桌面窄窗口只通过媒体查询隐藏搜索并覆盖 Inspector，缺少明确的移动/窄桌面降级策略。
7. 编辑器、树、Inspector 的滚动容器较多，未定义焦点移动和滚动锚定规则。

## Human Factors Audit

- 写作主路径应保持：章节树 → 编辑器 → AI/检查 Inspector；次要媒体和生产面板不得抢占主编辑区。
- AI 结果必须与原文形成可比较的 diff/方案选择，而不是直接覆盖；现有变体面板应保留并统一入口。
- 保存状态必须始终可见，冲突和失败必须在发生位置附近提供恢复动作。
- 键盘优先级：模块切换、搜索、保存、AI 操作、Inspector 开关；所有 icon-only 操作需有可见 tooltip 和 aria-label。
- 长文编辑区使用编辑器字体与 UI 字体分离，正文行宽、行高和滚动位置需稳定。
- 动效采用低强度短过渡，并尊重 `prefers-reduced-motion`。

## Visual / Design System Audit

当前 token 已使用冷中性背景和蓝色单一强调色，方向适合生产力工具；但仍存在以下问题：

- `Inter` 与 `Noto Serif SC` 是硬编码回退链，缺少字体角色 token 的完整定义与加载策略。
- 间距、圆角、阴影和 z-index 已集中，但组件中仍有直接像素值和历史 class 并存。
- `.ui-panel`、`.panel`、`.workspace`、`.inspector` 等多套容器样式并行，容易产生边框、背景、圆角不一致。
- 颜色状态已有语义 token，但对比度、暗色模式和 disabled 状态尚未形成自动检查。
- 图标库为 `lucide-react`，当前已是项目既有依赖；本轮不更换图标库，避免无关迁移。
- 不应新增渐变背景、装饰性 orb、过度圆角或卡片嵌套。

## Desktop Shell / Runtime Audit

- 真实宿主工程为 .NET 8 Windows DesktopHost + WebView2，不能把浏览器开发态表现视为最终桌面表现。
- 需在最终重构后验证 1280×720、1440×900、1920×1080 与高 DPI 缩放下的三栏最小宽度、滚动和 Inspector 覆盖层。
- packaged credential channel、host ping 和恢复/关闭生命周期属于既有合同，本轮只验证入口可用，不改协议。
- DesktopHost 目录存在 `WebView2ControllerProbe`，属于诊断工程，不能混入产品运行路径。

## Test Coverage Audit

- `frontend/src/ui/AppShell.test.tsx`、`src/App.test.tsx` 及小说面板测试覆盖了主要渲染和交互回归。
- 当前缺少统一 Shell 的键盘导航、Inspector resize、tooltip、窄窗口和 reduced-motion 视觉回归测试。
- `npm run build` 已通过；后续每个迁移阶段应继续执行 TypeScript、build、Vitest 和桌面 smoke test。

## Deferred Items

- Design MD Collection / VoltAgent 资料库：本地未发现，`DEFERRED`。
- 不在本轮实现真实视频模型、插件沙箱、TTS 混音、embedding 或新的业务 API。
- 不修改后端、数据库 Schema、credential 协议或模型行为。
- 不重写整个 `App.tsx`；仅按职责边界渐进拆分。

## Recommended Migration Order

1. **Foundation**：整理 token 层、组件状态契约、焦点/tooltip/最小尺寸规则，保持现有视觉方向。
2. **Shell orchestration**：抽出 `moduleRegistry`、scope/status 适配器和统一 `WorkspaceLayout`，减少 `App.tsx` 重复分支。
3. **Editor ergonomics**：稳定编辑区宽度、章节树键盘操作、AI diff/变体入口、保存状态和冲突恢复。
4. **Secondary interfaces**：统一资产、视频、音频、工作流、插件面板的标题、空态、错误态和操作区。
5. **Desktop/accessibility**：拖拽调整 Inspector、持久化布局、窄桌面降级、高 DPI、键盘与 reduced-motion 回归。
6. **Visual polish**：在结构稳定后再做颜色、密度、动效和细节抛光，并执行视觉快照验收。

## 当前结论

状态：`PARTIAL`。现有 UI 已具备可工作的桌面 Shell 和较完整业务入口，但还未达到可持续扩展的 V1.0 前端架构。下一步应从 Foundation 与 Shell orchestration 开始，完成后再进行 Grok 二次审计和最终桌面验收。

## Phase B Progress

已完成的结构性改造：

- 共享 primitives 增加 loading、Spinner、Tooltip、Separator、StatusMessage。
- token 增加控件高度、focus ring、动效和 Inspector 宽度边界。
- 模块注册表统一管理 7 个创作模块及其图标/名称。
- 模块切换支持 roving tabindex、方向键、Home/End 和焦点回移。
- Inspector 支持 280-480px 拖拽宽度、本地记忆和窄窗口覆盖模式。
- 非小说模块抽出到 `src/ui/ModuleWorkspaceRoutes.tsx`，小说主编辑流程保持原入口。
- 新增 Shell 与模块路由回归测试，相关测试通过。

待完成：

- 清理 `App.tsx` 中迁移保护用的不可达旧模块分支。
- 为 Inspector 拖拽和布局记忆增加专门测试。
- 修正既有 AI 写作测试与当前四参数调用契约的不同步。
- 完成桌面宿主下的高 DPI、窗口尺寸和视觉回归。

## Verification Note

- 前端 `npm test`：41 个测试文件、145 个测试通过（含 Inspector 调宽回归）。
- 前端 `npm run build`：通过。
- `npm run lint`：`UI token guard PASS (19 files)`。
- DesktopHost 编译尚未执行成功，当前执行环境未安装可用的 .NET SDK；需在正式 Windows 桌面验收机上运行既有打包/验收脚本。

## V0.6 P0 / Phase 1 Progress (2026-08-24)

本节更新并 supersede 上述旧的 Verification Note；旧数字保留作为历史记录，不代表当前工作区状态。

### P0：左侧功能启动器

- `frontend/src/ui/FeatureLauncher.tsx` 保留既有 panel ID、`setPanel` 回调和 `studio-feature-groups` localStorage key；新增分组浮层、选中态、外部点击/Escape 关闭、焦点回移、Tab/方向键/Home/End 导航。
- `frontend/src/App.tsx` 将章节树包入独立 `.sidebar-chapter-scroll`，功能启动器固定在 Sidebar 底部；章节数量不再推动功能入口离开可视区域。
- `frontend/src/ui/FeatureLauncher.css` 使用 Sidebar 定位上下文和内部 max-height/滚动容器，没有 `position: fixed`、`100vw` 或改变正文三栏宽度的 grid mutation。
- `frontend/src/ui/primitives.tsx` 的 Tooltip 不再用 `aria-hidden` 包住交互控件；这是为浮层按钮可访问性做的最小 DCR，未改变 Button API。

### Phase 1：AI Context Preview

- 前端入口：`frontend/src/novel/AiWritingPanel.tsx` Inspector 内的 `AiContextPreviewPanel`。
- 真实主 API：`GET /api/agents/{agent_id}/context-preview`，通过现有 `AgentContextService.build` 读取角色契约、章节版本、ContextService writing context、Story DB sections、source manifest 和 context hash。写作方式映射为 `writer` / `editor` / `planner`，刷新时发送当前章节、trim 后的附加要求和 local/cloud target。
- 真实补充来源：`api.writingGoal`（当前写作目标）、`api.resource(novel, "canon")`（仅本地目标读取已确认 Canon）、`api.worldRules(novel, "APPROVED")`（仅本地目标读取已批准世界规则）。云端目标不会直接拉取未经筛选的 Canon/World Rules；缺失内容显示“未配置”，不伪装为已注入。
- 来源状态来自查询结果：`已读取`、`无相关数据`、`未配置`、`加载中`、`加载失败`、`权限不足`。主 Context 请求失败时只显示错误与重试，不绘制假卡片。Lore Memory、Context Pack V2 的缺失状态反映现有 `ENABLE_LORE_CONTEXT` / `ENABLE_CONTEXT_PACK_V2` 运行时开关。
- 所有新增样式复用 DS token、Panel 外壳和 Badge/EmptyState/StatusMessage/Spinner/Button；没有新增后端路由、数据库字段、Provider 或 Mock 数据。

### 当前验证

- Frontend：`frontend/` 下 `npm test` 通过（44 个测试文件、158 个测试），`npm run lint` 与 `npm run build` 均通过；Phase 1 覆盖 loading/empty/success/error/permission/target 参数测试。
- Backend：Agent Context 定向测试 3 passed；Lore/Context 合同回归 5 passed、2 skipped（跳过项均因本机没有 real PostgreSQL）。全量 pytest 在当前执行时限内未完成，已知两项既有回归仍单独失败，详见交付报告，不把全量结果写成通过。
- DesktopHost P0 正式验收：`D:/小说/.desktop-v1-acceptance-p0-20260824-r9`；标准本地运行时 verifier 返回 `application_ready=true`、`desktop_host_started=true`、`public_listeners=0`、`secret_exposure=0`。证据覆盖 1280×720、1440×900、1920×1080、120 DPI、浮层滚动/选择/Escape/焦点回移。
- DesktopHost Phase 1 正式验收：`D:/小说/.desktop-v1-acceptance-p1-20260824-r10`，由 ASCII staging 的正式 launcher 启动；verifier 返回 `application_ready=true`、`frontend=true`、`desktop_host_started=true`、`public_listeners=0`、`secret_exposure=0`、`exit_code=0`。真实工作区入口和 1920×1080 高 DPI 窗口证据已留存。

### 已知限制 / Deferred

- Playwright P0 E2E 脚本依赖本机 PostgreSQL `127.0.0.1:5432`；当前环境未启动该服务，因此不能把该套浏览器 E2E 标为通过。Vitest、lint、build 和正式 DesktopHost verifier 不受此阻塞。
- Windows DesktopHost 的正式打包在 Unicode 工作区路径下可能触发 Postgres cluster 初始化的路径编码问题；验收脚本使用 ASCII staging 目录完成验证，这是打包工具链限制，不是前端数据流程变更。
- Phase 2 Generation Workflow 时间线、Phase 3 世界观 Dashboard 及后续模块保持 Deferred；本次不扩大底层功能范围。

## Phase 2 Generation Workflow Progress (2026-08-24)

- 新增的四阶段时间线只映射既有 generation Job 与前端审核流程，不推断后端未暴露的模型内部阶段。
- `job_id` 创建是“上下文已接收 / 可追踪计划已建立”的完成边界；`GENERATING / COMPLETED / FAILED / CANCELLED` 和候选轮询结果驱动草稿阶段；ready 与 accept/reject 动作驱动作者审核阶段。
- 恢复态继续使用 sessionStorage 中的最小可恢复元数据和正式 Job 查询，不持久化凭据或生成内容。
- 视觉复用 DS-v1.0 token、Badge、Button、StatusMessage 与 Lucide 图标；没有新增颜色、卡片体系或装饰性容器，并支持 reduced-motion。
- 前端完整回归为 45 files / 165 tests，lint、build、Impeccable detector 均通过。Phase 2 `r12` 正式 DesktopHost 运行时 verifier 通过；真实 Provider 驱动的交互态视觉矩阵待补证，Phase 3 保持 Deferred。

## Phase 3 World Building Dashboard Progress (2026-08-24)

- 新总览是既有 Story Database 的读取与导航层，不引入新的事实来源或前端持久化。
- 关系、时间线、伏笔使用独立视图和语义化列表；状态切换保持稳定高度与键盘焦点，样式全部复用 DS-v1.0 token、Badge、Button、EmptyState、Spinner、StatusMessage 和 Lucide 图标。
- 伏笔合同缺少完整的后续出现章节数组，界面明确展示关联事件与目标章节，不推断实际出现位置。
- 当前验证：46 files / 169 frontend tests，lint/build/detector 通过，后端资源合同 3 passed。Phase 3 `r13` DesktopHost verifier 通过；Phase 4 保持 Deferred。

## Phase 4 Story Planning Workspace Progress (2026-08-24)

- 规划区保持 Operate 模式的紧凑层级，不创建嵌套卡片；卷、章节和场景使用语义化 tree/group/list，并提供键盘焦点。
- 所有数据均来自既有 Service/API。无章节级人物变化聚合时显示真实缺失状态；协作运行时不展示不可用的本机排序能力。
- 章节拖拽具有保存中、成功、失败刷新回滚和 409 冲突文案；一次只移动相邻位置，以保持文件/PostgreSQL 两种后端的既有 ID 语义，不维护前端伪顺序。
- 当前验证：47 files / 172 frontend tests，lint/build 通过；detector 对新增规划文件无命中，扫描共享 `novel.css` 时保留 4 条既有 side-tab warning。后端 8 passed / 1 skipped，Phase 4 `r15` DesktopHost verifier 通过。

## Phase 5 Visual Context Progress (2026-08-24)

- 图片模块加入上下文确认区，使用紧凑的只读字段和复选框，不引入新的事实来源或模拟资产。
- 视觉上下文 detector 无命中；测试、lint、build 通过，r16 DesktopHost verifier 通过。

## Phase 6 Capability Status Center Progress (2026-08-24)

- 六个非小说模块共享统一能力状态面板，提供真实加载、失败和刷新状态。
- 视频明确区分 Pipeline 已具备与 Shot 生成未实现；插件执行能力遵循 runtime 返回值；Workflow 无项目时不伪造可用状态。
- detector 无新增命中，测试/lint/build 通过，Phase 6 r17 DesktopHost verifier 通过。

## Phase 7 Agent Activity Center Progress (2026-08-24)

- Agent 活动采用列表式操作界面，突出状态与错误恢复，不使用模拟时间线或定时阶段。
- 输入/输出摘要只读取 Job 返回值；缺失字段显示未记录，失败和重试关系保留原始数据。
- detector 无新增命中，相关测试、lint、build 通过，Phase 7 r18 DesktopHost verifier 通过。

## V0.6 Final Audit（2026-08-24）

- 50 个前端测试文件、176 项测试通过，token lint 与 production build 通过。
- 11 项后端定向回归通过，1 项因真实 PostgreSQL 未启动跳过。
- r18 正式 DesktopHost 最终 verifier 通过；未使用浏览器开发页替代桌面验收。
- 新增 Phase 5-7 界面 detector 无命中；共享旧样式 warning 已记录并保留 Deferred。
