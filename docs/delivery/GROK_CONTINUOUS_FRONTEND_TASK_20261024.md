# 给 Grok 的连续前端任务书：构建收口与可恢复视图工作集

独立复验已完成；此提示词供用户自行转发。没有向Grok发送消息或启动外部任务。

请继续你已经完成的统一工作区前端线，持续实现下面这一组有产品价值的工作。每个稳定切片完成后自动推进下一项，不必逐阶段等我再次催促；有具体阻断时只停受影响的操作，继续能独立完成的部分。

本轮目标是“可恢复的个人视图工作集与键盘工作连续性”：用户能够命名保存并显式切换工作区视图，在合法 scope 下冷重开恢复画布平移缩放，使用键盘回到工作位置。它保存的是界面偏好，不能冒充作品、画布图、任务或正式资产已经保存。

固定起点：仓库 `1785235376-blip/AI-Novel-Studio`，提交 `51ff02b2622e6f992f7729702bf4bbb79b1a09a6`，tree `f4cf078bffad5675a305fd74781cae9abde22dbd`。先核对实际对象、HEAD、工作区和远端，保留已有变更，不 reset，不强推。建议新工作分支 `work/grok-view-worksets-20261024`；若同名远端已存在，先核对其来源和已有工作后接续，不覆盖。不要合并云 production/recovery 工作，也不要改 main、发布产品或更换默认入口。

先读 AGENTS.md、`.codex/skills/ai-novel-studio-ui/SKILL.md`、相关 UI references、`docs/ui/design_system.md`、`docs/ui/protected_ui_surfaces.md`、`docs/architecture/unified-workspace-contract.md` 以及目标验收矩阵/交接资料。复用现有 tokens、primitives、ActionRegistry、DockLayout、DraftStore 和 v3 layout codec。

## M0：按实际独立结果收口必修项

独立复验事实（不能改写成全部通过）：

- 固定源码 `51ff02b2622e6f992f7729702bf4bbb79b1a09a6`；Node24.19.0、pnpm10.6.5、TS5.9.3、Vitest2.1.9、Vite6.4.3；三manifest逐字节匹配冻结环境。原Node22严格复现NOT_RUN
- 核心参数 `vitest run src/workspace src/workbench src/rebuild src/taskcenter --pool=forks --maxWorkers=2 --minWorkers=1`：实际63文件/504例，首轮503P/1F。失败是 `TaskCenter.additive.test.tsx:72` 的费用companion读取，预期 `1.000001 USD（1000001 micro-USD）` 未显示；单文件一次必要复验4/4P。首次失败保留，不宣布已知flaky或已修
- `npx tsc --noEmit -p .` exit2六错；标准 `corepack pnpm build` exit1，停在tsc-b，Vite未运行
- 共同基线 `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed` 同环境复现六条同诊断/同源语句（App仅+7行）；属于既有3条生产、3条测试类型债，无新增类型诊断。费用失败测试/receipt相关blob相同，但一般task controller有变动，未做同命令基线运行，不能用源码相同直接证明运行等价
- Node24单轮正常结束712.293秒，910文件11425例：11106P/313F/6skip(JSON pending)，57失败文件含1个缺失fixture收集错误。无同环境full基线，313尚未完整归因，不能都算Grok新回归，也不能套Node22历史297门槛；费用case在full中4/4P。144首错误属于FeatureLauncher mock缺FEATURE_GROUPS分组，另LocalAiBrowserJourneyContracts缺live-spec路径（共同基线也无该文件）；这些只是分类，不是新增归因
- 本轮已确认必须修复的缺陷及精确可改路径：必须修复下列六条已在共同基线复现的类型诊断并使标准构建通过；另对费用回执用例作有证据的生命周期诊断，不能先认定新回归或只靠重跑/放宽等待追绿

优先复用已公开的最小补丁，避免重复制作：云分支已有 `0a3a9eb72bbbd5416a010958018a8b8c86f71b74`（https://github.com/1785235376-blip/AI-Novel-Studio/commit/0a3a9eb72bbbd5416a010958018a8b8c86f71b74），含这些类型/调用修复及少量相关测试。先读该提交7条路径及当前Grok差异，核对原合同后只移植相应最小块；若选择单提交移植也必须检查全部7路径并定向复验，不盲目整并云分支、不带入其它正式production/recovery提交。必要的 `AppBrokerRecovery.test.tsx`、`rebuild/image/ImageRebuild.canvasQueue.test.tsx`、`ui/handoffSmoke.ts` 仅允许该公开修复涉及的最小兼容/fixture更新，不扩展到正式任务实现。

费用case尚无确认根因：用可控deferred响应/卸载/ABA/显式读取/后续失败保留原信息的反例验证，不能为了写“修复”发明产品问题。全量旧mock/缺fixture若要处理，先给最小同环境基线对照和真实因果，只修授权边界内必要测试合同；不得补一个伪造live媒体spec、删断言、改生产假export或重跑被限制的媒体验收。否则保留明确owner/未验边界，继续大块前端，不把910文件旧债全塞成无限M0。

先修上述已确认且在授权边界内的缺陷，保留反例，定向复验后自动继续 M1–M5。不将一次孤立复验通过叫作 flaky，不修改失败门槛、删除反例、放宽权限或用类型断言掩盖真实合同。旧Node22规则为 adjusted = raw failed - IndependentStudioIdentity failures +8，best-of-three adjusted≤297，是历史允许失败门槛，不是全绿结论，不能直接套用Node24。M0类型与标准build必须实际通过；在修正源码的精确核心集通过、费用生命周期有确定性反例/诊断后自动继续大块，不用等待用户逐阶段批准。全量未分类旧失败不能随便归为本轮新错，也不能把没跑/中断记为通过。

允许的 M0 最小例外只有这些调用/类型点：

1. `frontend/src/App.tsx:1970:80` TS2554：`acceptGeneratedDraft()` 缺必需参数。查原合同并传真实当前参数，不用占位值绕过来源/确认；不改默认入口、AppShell或云节点回调。
2. `frontend/src/creative/GraphCanvas.tsx:577:31` TS2339：readonly string[]上的 `contains`。按真实 DataTransfer types 合同作最小兼容修复，保留已有拖放判断与反例，不把类型诊断夸成已证实运行崩溃。
3. `frontend/src/ui/ModuleStartGate.tsx:43:21` TS2339：`ImportMeta.env` 类型。允许按公开补丁新增/复用 `frontend/src/vite-env.d.ts` 的 `vite/client` 类型引用，复用项目已有Vite类型能力，不用any/ignore，不变更实际入口逻辑，也不为此新增依赖。
4. `frontend/src/ui/handoffSmoke.xUx10.test.tsx:60:7/207:13/232:11` TS2322：StudioModule宽于WorkspaceModule。正确约束测试输入，保留所有真实覆盖；不删用例或排除类型检查。
5. 费用用例仅在精确反例和因果证据需要时修改 `TaskCenter.additive.test.tsx`、generic `useTaskCenter`/receipt消费层的最小行。不得改正式 `StudioProductionTasks`、原owner、费用API/口径或自动读取策略；不能删金额断言、任意增大超时或换弱fixture。

除此以外 App.tsx、creative、taskcenter、rebuild、全局ui的保护继续有效。对范围外基线错误给准确证据和 owner 请求，不自行扩成重构。

## M1：一个合法作用域的视图偏好适配器

新增一个前端消费层适配器，接受原 host owner 提供的真实 `LayoutScope`（user/project/projectInstance）、`StorageLike`、`isCurrent` 和持久化能力。这是界面偏好的消费合同，不是新增后端权限，绝不能从布局scope推导生产/审核权限。复用现有 v3 layout 序列化/归一化，不另造布局状态 owner 或迁移引擎。

新持久化能力缺真实 actor/project instance/授权时，明确禁用。不能继续把 `local/preview/preview` 或猜测的 actor/incarnation 当作身份写入。可用的会话内能力必须明确标注，绝不能伪称可冷恢复。

只允许存界面几何、命名工作集元信息和每画布 viewport；不得存 prompt、正文、草稿、graph/node 数据、Job/Asset 关联、凭据、token 或授权信息。旧 v3/legacy key 保持原兼容规则，不能静默覆盖未知新版本、迁移失败原文或清空整个 localStorage。

验收：真实注入 scope 的 A/B/A、实例改变、跨消费者隔离；存储拒绝/配额/损坏/未来格式；读取失败保留会话视图；旧 callback 不得把偏好写到新项目。没有合法 scope 时零新增持久化写入。

可改：新 `workspace/state/viewPreferences.ts`、`useViewPreferences.ts`、配套新测试；host 接线由唯一集成人改 `UnifiedWorkspacePreview.tsx`。

## M2：真正的命名视图工作集

增加多个用户命名的 UI 视图工作集，可保存、显式应用、改名和删除。复用 DockLayout 原 reducer、归一化与 ActionRegistry，让按钮、快捷键和命令搜索走同一执行与重复点击保护。

工作集只包含布局几何、面板开关/折叠、分屏和位置。应用前通过原 dirty guard 拦截会关闭脏面板的操作；取消、失败或重复点击不能丢草稿、触发业务保存或误报成功。未知面板通过原 codec 保留。限定合理数量/大小，处理重名、空名与删除确认。

有合法 M1 scope 时保存浏览器偏好；没有时可以完成明确标为“本次会话”的工作集，持久保存按钮禁用并解释原因。不要为了完成名义持久化而发明身份。

验收：两个不同工作集保存/应用；脏章节及节点标题在切换、取消、redock、失败后保留；多项目及卸载晚回包；所有视图操作不产生任何生产、审核、模型或后端写请求。

可改：新 `workspace/layout/worksets.ts`、`panels/WorkspaceViewsPanel.tsx`、`actions/viewActions.ts` 和新测试；`DockLayout.tsx` 仅增加必要消费接口，禁止重写已有布局合同。

## M3：viewport 冷重开与局部重置

现有 viewport 仅在 `UnifiedWorkspacePreview` 的项目 useRef 中，本轮把它接到同一个 M1 偏好适配器。复用 `initialViewport/onViewport`；按合法项目/实例和画布 kind 分开，在画布初始化前选择匹配视图，不先闪现另一个项目的 pan/zoom。

增加当前画布视图的显式重置和准确恢复状态。只恢复平移/缩放等偏好，不恢复节点/任务选择，不读取 graph 内容，不自动执行或审核，不把 UI 偏好恢复叫作内容保存。校验有限数值及合理缩放范围；失败保持会话视图。重置只动这项偏好，不清 layout/legacy/business/recovery key。

验收：同 scope 冷重开、两画布隔离、A/B/A、换实例、损坏及存储失败；不触发额外生产请求。纯注入 fixture 只能证明适配协议，未有真实 host scope 的产品冷恢复必须写 BLOCKED/PARTIAL，不能包装成已完成。

可改：M1 新模块、`panels/studioPreviewPanels.tsx` 的 viewport props 适配、唯一集成人的 `UnifiedWorkspacePreview.tsx`、新定向测试。不要改共享 RebuildCanvas 或正式 CanvasView owner；确有缺接口给 owner 提案。

## M4：显式键盘回到工作位置与新交互可访问性

增加“回到上次工作面板”和上一/下一可见面板的明确命令。通过既有 ActionRegistry/快捷键冲突检查，暂存稳定 UI control identity，目标不存在时退回可聚焦的原 panel region。仅在用户明确调用时移动焦点；初始挂载、冷偏好加载、切项目或晚回包不抢焦点。

保证新增工作集对话框、错误/禁用原因、状态消息、reduced-motion 与键盘流程可用。既有 tablist、splitter、dirty dialog、skip link 和布局迁移已完成，直接复用；不要为扩大任务重新制作。

复用原 tokens/primitives，不增加颜色或间距体系。legacy `.nv-rail` 的对比度或任何 AppShell/全局 token 变更必须给 Design System Owner 精确请求；不能用全局覆盖规避其所有权。

验收：关闭、重开、redock、折叠、目标消失与项目 ABA 的焦点回退；不在输入或 IME 时抢快捷键；按钮/快捷键重复触发语义相同。组件级 reduced-motion/a11y 证据与浏览器证据分开。已被拒绝的浏览器/沙箱动作不得重试或绕过；没有合法浏览器能力就记 NOT_RUN，继续独立实现和组件验证。

可改：新 `workspace/state/panelFocus.ts`、新 a11y 测试；必要 DockLayout 消费适配由集成人统一落地。`workbench/CommandSearch.tsx`/CSS 只在新增消费接线确有需要时最小修改，不重构 registry 或全局 shell。

## M5：能力说明与稳定交接

界面准确区分：本机 graph 草稿、会话视图、已保存浏览器 UI 偏好、尚未接通的任务能力。TasksPanel 原空 token 不代表授权；只有原 auth/task owner 提供合法 transport/session 后才能接，否则保持 unavailable 解释，不读取或伪造 token，也不改正式任务入口。

维护本轮新增验收账本，每项区分 IMPLEMENTED / 软件协议测试 / 真实 host 接线 / 浏览器未验 / owner 阻断。不能把方案、统计、author 字段或粘贴 review 当作验收。

每稳定切片冻结源码后运行受影响定向测试、`corepack pnpm exec tsc --noEmit -p .` 和标准 `corepack pnpm build`；M0必须另跑上面的63文件核心选择，后续复用必要定向集，独立复核后提交、正常推送已授权工作分支并回读 SHA。最终按上述固定快照与实际同环境控制做一次有意义的组合/全量验证，保留 raw failure identities 和环境差异，不反复跑不受影响大套件或挑最好一次冒充全绿。公开交接只留必要脱敏资料，不上传原始私密日志或本地历史。

## 并行和文件所有权

实际启动 3–4 条有产出工作线，并行前先约定接口：

1. 偏好 codec/作用域与测试：M1 新 state 文件。
2. 工作集模型、视图 UI、actions 与测试：M2 独有文件。
3. 焦点/a11y 与独立审查：M4 新模块和新测试，不抢共享入口。
4. 集成人负责 `UnifiedWorkspacePreview`、DockLayout 和必要共享调用点；处理各线最小补丁、固定源码验证与提交交接。

共享文件只许一位写入者。审查者先独立设计反例，再审最终实现；依赖未准备好时做自己的纯模块/测试/合同，不空开占位或重复制作。

## 必须由原 owner 提供的合同

- Host/session/project owner：真实偏好 scope、project instance、持久化策略和 current lease。没有就禁止新持久写入，不能猜。
- Auth/task owner：合法只读 transport/session 与权限；没有就保持任务能力不可用。
- Design System Owner：受保护 rail、tokens、AppShell 或默认入口改动的明确决定。原 AppShell 和 ModuleSwitcher 保持不动。
- Canvas/Job/Asset/Review owner：服务端 graph、正式任务来源、审核采用和保存合同。本轮全部不实现、不代理，也不碰云 production/recovery 和 browser hints。
- 交接源：上述M0实际复验和精确类型调用点为边界；结果变化用新固定源码和原始证据说明，不私自扩大可改区域。

遇到权限、安全、scope 合同、已有平台拒绝或运行资源阻断，写清具体动作、目标、原因、已完成事项及是否执行/未知，只停受影响动作。继续其他阶段；不要每个阶段结束就等用户确认，不把持续推进扩成无关功能。

仅云端 GitHub 源码。不得读本地旧包，不改 backend、main、默认入口，不强推、不发布，不新增凭据、不安装新来源依赖、不改锁、不付费调用模型/GPU，不重复受限媒体安全复验，不绕过浏览器沙箱。交付后给真实 SHA、验证范围和剩余合同边界。
