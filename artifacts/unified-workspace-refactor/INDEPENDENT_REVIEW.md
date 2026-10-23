# [VERA-FE] M1 独立验收 — INDEPENDENT_REVIEW

- 对象：work/hermia-unified-workspace-20261023，6ba25ad7..7de42fe8（5aa20a4a 代码+测试，7de42fe8 文档/补丁）
- 方法：临时 worktree /workspace/hr/vera-wt-m1（7de42fe8 + patches/0001，仅在临时树应用），自起 vite 4399（独立 cache），Chrome/Playwright 真实交互；jsdom 探针 + 变异测试仅在临时树。结束后已停 vite、删除临时树。wt 未改动（本文件除外，未提交）。机器负载 0.7 左右。
- 时间：2026-10-22 17:40 左右（Asia/Shanghai）

## 结论：**MUST-FIX**

## 逐项对照
| ID | Hermia 自评 | Vera 结果 | 说明 |
|---|---|---|---|
| M1-01 拖动/浮动不出视口 | PARTIAL | PARTIAL | 浮动面板拖动真实浏览器有效，甩到极远处时保留 48px 可见（1366/1440/1920 下 x=vw-48）；停靠区内精确重排未实现，同意自评 |
| M1-02 缩放+最小/最大 | PASS | **FAIL（跨面板）** | 单面板 min/max 生效（outline 最小 180，inspector 最大 560，键盘 ±16）；但主区 minSize 320 没有生效，见 MF-2 |
| M1-03 拖到停靠区 | PASS | PASS | 真实拖动 tasks 到右边缘，drop-hint=right，停靠成功 |
| M1-04 重新停靠 | PASS | **FAIL（数据）** | 布局关系正确，但改停靠位置会重挂载面板内容，未保存内容丢失，见 MF-1 |
| M1-05 折叠保持状态 | PASS | PASS | 折叠/展开真实可用，内容不卸载 |
| M1-06 关闭/重新打开 | PASS | PASS | |
| M1-07 分屏 | PASS | PASS（有附带问题） | 单栏时第二个主区面板会被卸载，见 MF-1 |
| M1-08 恢复默认（确认） | PASS | PASS | |
| M1-09 刷新后保持 | PASS | PASS | 7 种视口/缩放组合刷新前后的停靠位置和宽度都一致 |
| M1-10 保存失败状态/焦点 | PASS | PASS | |
| M1-11 旧格式迁移 | PASS | PASS（偏离契约） | v2 迁移可用；但旧键 studio-inspector-* 会覆盖 v2 的停靠位置，见 N1 |
| M1-12~16 缺字段/未知面板/损坏/非法值/幂等 | PASS | PASS | 浏览器实测：坏 JSON、version 9、[]、null 都回退到默认布局，备份写入，原值保留，显示中文警告；部分数据中 size 99999→560，dock "moon" 被修正，ghost 面板保留，无 id 条目不崩 |
| M1-17 迁移中断不动原数据 | PASS | PASS | |
| M1-18 重置只动布局键 | PASS | PASS | |
| M1-19~25 关闭守卫 | PASS | PASS（仅 jsdom） | 代码审查：取消/放弃/保存并关闭、失败显示真实错误、迟到结果忽略，都正确。文案为中文，无原始代码。预览页占位面板没有注册脏状态，所以这些无法端到端验证 |
| VIEWPORT | NOT_RUN | 已实测；有一项失败 | 1366×768、1440×900、1920×1080 初始无溢出；1366 下把两侧拉到最大，主区宽度为 0，页面横向溢出（scrollWidth 1391） |
| ZOOM | NOT_RUN | PASS（DSF），CSS zoom 有问题 | DSF 1.25/1.5 结果与 1 完全一致；CSS zoom 1.5/2 时浮动面板被夹到视口外（innerWidth 未按 zoom 换算），见 N4 |
| E2E | NOT_RUN | 部分 PASS | ?uw=1 渲染正常，0 个控制台错误，0 个 /api 请求，没有非 GET 请求；不带 ?uw=1 时旧版应用正常（6 个模块标签，没有 dock-layout，没有非 GET 请求） |

tsc：应用补丁后仍是 6 个基线错误（App.tsx 行号 +7），没有新增。layout 单测：41/41 通过。

## 测试假阳性评估
- 几何 mock（root.getBoundingClientRect 固定为 1000×800）+ PointerEvent polyfill（extends MouseEvent）：结论在真实浏览器里成立，见上面的真实拖动结果。
- 变异测试 9/9 全部被测试杀死：去掉 minSize、去掉备份、保存前先关闭、去掉迟到结果保护、折叠时卸载、跳过脏检查、zoneFromPoint 左右互换、去掉 docks 白名单、resize 符号错误。测试有效。
- 盲区：没有任何测试覆盖“改停靠位置/切换主区面板时内容是否保留”，以及“多面板加起来的总宽度”。

## MUST-FIX
**MF-1 改停靠位置或切换主区面板会卸载内容，绕过未保存守卫，导致草稿丢失**
- 位置：frontend/src/workspace/layout/DockLayout.tsx:188-195。同一个面板会根据 dock 渲染到不同的父容器（左/主/右/底/浮动），React 因此重挂载。还有 :162-163 和 :181，单栏时 hiddenMain 不渲染，即被卸载。
- 复现（jsdom 探针）：inspector 内放一个有状态的 input，输入 "abc"，然后把「属性」停靠位置改为底部，input 值变成 ''。用「中间显示」切换主区面板，或把面板停靠到 main index 0，同样会卸载另一个面板，并且没有经过 dirty guard。
- 违反：契约 §1“Close unmounts content”（只有关闭才应该卸载，而且要经过守卫），以及“无数据丢失”。
- 建议：所有面板固定挂在同一个容器里，用 CSS 或 portal 定位；或者在卸载前走 requestClose 守卫。补充对应测试。

**MF-2 主区最小宽度没有生效，窄屏下主区被挤成 0，页面横向溢出**
- 位置：model.ts:56-60。maxSizeFor 只按单面板 60% 视口计算，没有扣除对侧面板和主区 minSize。DockLayout.css:.uw-main 设置了 min-width:0。
- 复现：1366×768，?uw=1，把大纲拉到最大（819），属性拉到最大（560），结果创作画布宽 0，scrollWidth 1391>1366。截图：vera-compare/m1/1366-squeeze.png
- 建议：resize 和 viewport 计算时，侧栏上限 = 视口宽 − 对侧宽 − 主区 minSize。

## Nits
- N1 persistence.ts:187-201：AppShell 的 studio-inspector-* 旧键会叠加到 v2 迁移结果上，强制改为 right 并采用旧宽度（实测 v2 中 inspector 为 left/300，结果是 right/560）。契约 §4 的顺序是回退链，不是叠加。
- N2 DockLayout.tsx:68-73：损坏数据回退后，只要点一下面板标题（focus 会改变 z），就会写入 v3 键，覆盖原始损坏值（有 ::backup，不算丢数据）。契约 §4.2 要求“首次用户布局变更”才写。焦点和 z 序不应算布局变更，或者应先确认。StrictMode 下加载本身不写（已验证）。
- N3 对话框：没有 Esc 关闭，没有焦点陷阱（aria-modal=true 但 Tab 可以跳出）。
- N4 只是用 CSS zoom 时，useViewport 用 innerWidth，夹取会出错。真实浏览器缩放会改变 innerWidth，影响小。
- N5 预览中执行画布默认隐藏，只能通过「中间显示」打开，入口不明显。
- N6 1366 首次加载有一个资源 404（控制台），复测没有出现，疑似 favicon/偶发问题。

## 证据
- 截图：/workspace/hr/vera-compare/m1/（43 张：每个视口的 initial/resized/collapsed/tasks-right/float，corrupt-*，legacy-no-uw，1366-squeeze）
- 数据：/workspace/hr/vera-compare/m1_check.json；脚本：m1_check.mjs、m1_squeeze.mjs
- 探针测试（只在临时树中跑过，已随临时树删除）：P1 redock 保留状态 FAIL；P2/P3 StrictMode 不覆盖、不写入 PASS；P4 focus 覆盖损坏原值 FAIL（N2）

---

## [VERA-FE] M1-fix 复审 (HEAD 42167577, 2026-10-23)

**结论：PASS（附 1 条非阻塞 nit，建议后续修）**

方法：在临时 worktree（固定于 42167577）里仅应用 patches/0001，自起 vite 4399 并使用独立 cache；用真实 Chrome 打开 `?uw=1`，测试规格为 1366x768 / 1440x900 / 1920x1080 / DPR1.25 / DPR1.5，另测 1024 / 800 / 600 宽。只发 GET 请求，/api 调用为 0。全量 vitest 在空闲时单独运行，此时已去掉 patch，代码与 42167577 原样一致。

| 项 | 结果 | 说明 |
|---|---|---|
| MF-1 重挂载丢数据 | PASS | 在 inspector 和 outline 的输入框里打字后，依次做重停靠（左/下/浮动/右）、拖动浮窗、把 outline 拖到右侧再拖回、split-h、单列、切换主面板、折叠再展开，文本全部保留，同一 DOM 节点始终 connected。单列模式下被隐藏的面板节点会暂时 detached，切回后仍是同一节点，React 状态不丢。 |
| MF-1 关闭仍走 dirty 确认 | 部分 | 占位面板没有注册 dirty source，所以点关闭会直接关掉、不弹确认框。守卫逻辑本身有 jsdom 用例（"explicit close still goes through the dirty guard"）覆盖。等接入真实编辑器时需要注册 dirty。 |
| MF-2 主区不被挤没 | PASS（nit） | 所有视口都没有横向或纵向溢出，持久化的超大值（5000）在加载时会被 clamp。nit：模型没有扣除 resize handle 和边框（约 12px），也没有扣除顶部工具栏，导致两侧拉满后主区实测宽 308px（目标 ≥320）；800x600 下把底栏拉满后主区高 196px（目标 ≥200）。600x500 时由于 minSize 冲突，320/200 本来就不可能满足，属可接受的退化场景。 |
| N1 inspector 旧键仅在无 v1/v2 时生效 | PASS | 有 v2 时保持 left/300，只有旧键时变为 right/400。 |
| N2 损坏数据不被覆盖 | PASS | 加载 "{bad" 后，点击、聚焦、Tab 都不会改写它；用户主动折叠后才写入 v3，备份仍保留 "{bad"。 |
| N3 对话框 | PASS | Tab 和 Shift+Tab 焦点都被困在对话框内，Esc 能关闭，焦点回到「恢复默认布局」。 |
| 无 `?uw=1` | PASS | 旧 UI 有 6 个模块 tab，没有 dock-layout，没有非 GET 请求，没有报错。仅首次加载出现一个 /favicon.ico 404，属既有 nit。 |

**改动的两处断言**：都合理。600px 下 320+340 已超出空间，outline 回落到 minSize 180；500px 下 inspector 回落到 minSize 240。两处都有注释说明。

**变异测试**：mA（host 不缓存）挂 12 个用例，mB（去掉 crossLimit）挂 2 个，mC（fitMain 改成空操作）挂 3 个，mD（回退 N1）挂 1 个，mF（去掉 Esc）挂 1 个。mE（把 focus 当作用户操作）存活，但它是等价变异：签名比较不含 z，所以不影响结果。

**tsc**：报错与基线相同，共 6 个。

**全量 vitest**：在 42167577 原样代码上运行，期间机器空闲，load 约 0.1。结果 307 失败 / 11296 总数，Identity 失败 8 个，调整后为 307，≤307，门禁通过。失败集合与 6ba25ad7 完全一致，没有新增失败，也没有修复项；总数多出的 51 个是新增的布局测试。因此不需要复跑可疑用例，也没有用掉重试机会。说明：第一次启动时 box 重启，那次运行没有产出，不计入结果；之后在临时 worktree 里用 wt 的 package-lock 执行 `npm ci`，再运行。

**证据**：`/workspace/hr/vera-compare/m1fix/`（截图）、`m1fix_check.mjs`、`m1fix_check.json`、`vitest-42167577.json`、`vitest-42167577.log`。临时 worktree 和 vite 均已清理。

---

## [VERA-FE] M1-s2 复审（HEAD cbf4a3ed，2026-10-23）

**结论：MUST-FIX**（(b) 与旧 UI、全量 vitest 均通过；(a)(c) 有 4 项必修）

方法：临时 worktree 固定在 cbf4a3ed（npm ci）。自建 vite 4399，使用独立缓存。真实 Chrome 测试 1366×768、1440×900、1920×1080，DPR 1.25/1.5，以及 1024/800 宽度。全程只读，未触碰 4299/8000，worktree 已移除。

### 必修（MUST-FIX）
1. **空停靠区的插入指示线覆盖整个布局**：拖到空的右/左/下区时，指示框为 [0,0,1366,768]，不透明的 `--zone` 覆盖层把整个 UI 遮住。原因是 `computeDrop` 查找 `[data-zone-box=zone]`，但只有 main 带这个属性，于是回退到根元素的 rect。证据：m1s2/empty-zone-right-empty-target.png。
2. **拖动中按 Esc 不能取消**：按 Esc 后松手，面板仍然落到左区。只有 pointercancel 能清除。
3. **「恢复默认布局」从不禁用**：已是默认布局时依然可点，也没有中文原因（reset 没有 `available()`）。需求里明确要求这一项。
4. **?uw=1 下没有 Ctrl+K 命令面板**：动作声明了 commandSearch surface，但预览挂载的是私有 registry，按 Ctrl+K 不出现面板，所以无法从命令面板触发这 4 个动作。

### 建议（非阻塞）
- 真实连按两次快捷键（两次 keydown 跨 tick）会执行两次：single 直接变成 split-v。去重只覆盖同一个微任务，「运行中」状态（aria-busy）几乎看不到。
- 冲突提示只在 jsdom 中可验证，而且显示原始 token「Mod+Alt+S」，应本地化为 Ctrl/⌘。当前默认快捷键与现有快捷键无冲突。UI 上也没有显示快捷键。
- 浮动面板无法用指针拖回停靠区（只能用停靠下拉框），也没有键盘排序方式（下拉框只能追加到末尾）。

### 验证结果
| 项 | 结果 |
|---|---|
| (a) 精确落点：右区 前/中/后、下区 左/右 | ✅ 落点与指示线一致，刷新后顺序保留，5 种配置均通过；MF-1 内容（输入值、DOM 节点）在每次移动后都保留；禁止区显示灰色指示和「这个面板不能放到左侧」，且不移动面板 |
| (a) 空区 / Esc / 浮动→停靠 / 键盘 | ❌ 见必修 1、2；建议 3 |
| (b) 全部拉满后 main ≥320×200 | ✅ 1366/1440/1920/1024/800 及两档 DPR 下 main 宽都是 320，高 264/316/388/236/200，无溢出；存储值 5000 被钳制。600×500 及 700–724 宽属于最小尺寸互相冲突、无法同时满足，可接受 |
| (c) 快捷键 S/C/O/0 | ✅ 均可用；reopen 禁用时显示「没有已关闭的面板」；input、textarea、contenteditable 中输入时不触发；同 tick 重复只执行一次；双击 reset 只出现一个对话框；无原始 ID |
| (c) reset 禁用 / Ctrl+K / 运行态 | ❌ 必修 3、4；建议 1 |
| 旧 UI（无 ?uw=1） | ✅ 6 个模块 + 设置（CONTROL/PLUGIN/WORKFLOW）共 9 页 × 普通/专业 = 18 页。与 42167577 对比，文本哈希和 DOM 计数 18/18 一致，无横向溢出；全部请求为 GET（0 个非 GET） |
| 变异测试 | ✅ 每项都被 layout+actions 测试捕获：dropIndex 恒返回末尾 → 2 失败；sideChrome=0 → 1 失败；bottomLimit 去掉 chrome → 1 失败；去掉输入守卫 → 2 失败；去掉 reopen 无关闭检查 → 2 失败 |
| Hermia 声明 | ✅ tsc 6 个错误；那 9 个文件为 98/98；LocalAiBrowserJourneyContracts 加载失败（缺 tests/e2e/v2-local-ai-*.spec.ts），在 6ba25ad7 上同样缺失，已复现，属既有问题 |
| 全量 vitest（单独运行） | ✅ 307/11319 失败，Identity 8，调整后 307 ≤ 307。失败集合与 42167577 完全一致（新增 0、消失 0），无可疑项，未重试。负载峰值约 10 |

证据：/workspace/hr/vera-compare/m1s2/（m1s2_check.json、empty-zone-*.png、legacy-42167577/、legacy-cbf4a3ed/），以及 vitest-cbf4a3ed.json。

---

## [VERA-FE] M1-s2fix 复审（HEAD 3b2e92d4 / 代码 e66d2f38，2026-10-23）

**结论：PASS**。上轮的 4 项 MUST-FIX 全部修复，附加项也成立，没有发现新的阻塞问题。

方法：临时 worktree 固定在 3b2e92d4（npm ci）。自建 vite 4399，使用独立缓存。真实 Chrome 测试 1366×768、1440×900、1920×1080，DPR 1.25/1.5。只读，未触碰 4299/8000；结束后已停 vite 并移除 worktree。

| 项 | 结果 |
|---|---|
| MF1 空区指示 | ✅ 左右空区的指示框是工具栏下方的窄条，例如 1366 下左区 [0,63,273,705]、右区 [1093,63,273,705]；底部空区为 [273,576,820,192]。均为半透明（alpha 0.14），不再回退到整个根区域；松手后落到指示的区里。不允许的面板显示灰色指示且不移动。5 种配置一致 |
| MF2 Esc | ✅ 停靠面板：按 Esc 后指示消失，松手顺序不变，内容保留。浮动面板：按 Esc 后回到起点（80,80），仍为浮动 |
| MF3 reset 禁用 | ✅ 默认时禁用，title 和说明都是「已经是默认布局」；改布局后可用；恢复默认后、或手动改回默认后再次禁用。默认状态下从命令面板执行会提示「无法执行：已经是默认布局」，不改变任何东西 |
| MF4 Ctrl+K | ✅ 打开命令面板并列出 4 个动作，分屏、折叠、重开、恢复默认都能执行，恢复默认会先弹确认框。在面板输入框里打字并按 Ctrl+Alt+S 不会触发快捷键 |
| 附加项 | ✅ 两次真实按键间隔 40ms 只执行一次；aria-busy 显示约 300ms，之后再按会正常执行。界面显示「Ctrl／⌘+K」，没有 Mod。浮动面板拖到右区会停靠，内容保留 |
| 回归 | ✅ 精确落点的指示线与最终位置一致，刷新后顺序保留。main 最小 320×200 与上轮一致（800×600 时为 320×200，600×500 属于最小尺寸互相冲突、无法同时满足）。旧 UI 18 页与 cbf4a3ed 文本哈希和 DOM 计数 18/18 一致。全部请求为 GET |
| 3 个旧测试的改动 | ✅ 合理：两处等待 320ms 是为了等过 MIN_BUSY_MS，一处先改布局是因为默认布局下 reset 会禁用，断言都没改；slice2 只把文案从 Mod 改成 Ctrl |
| 变异测试 | ✅ 改回根区域回退 → 1 个失败；去掉 Esc 处理 → 2 个失败；reset 恒可用 → 3 个失败；去掉 Ctrl+K → 2 个失败；MIN_BUSY_MS 改为 0 → 1 个失败 |
| 全量 vitest（单独运行） | ✅ 307/11332 失败，Identity 8，调整后 307 ≤ 307。失败集合与 cbf4a3ed 完全一致（新增 0、消失 0），无可疑项，未重试。跑前负载 0.8，峰值约 9.8 |

**命令面板显示原始 action id 的严重度：P3，非阻塞。** `CommandSearch` 用 `<small class="wb-command__id">` 显示 id，这段代码自 9fb6e9c0 就有；6ba25ad7 与 3b2e92d4 之间 `workbench/` 没有改动。旧 UI（不带 ?uw=1）点「搜索功能」打开的命令面板同样显示 49 条原始 id，例如「打开：故事资料库 | panel.open.story」。id 用 11px 灰字显示在每个中文名称下方，用户能看到。不在 M1 范围内，建议另开一个小项：去掉显示，但保留 id 参与搜索匹配（`matchesQuery` 已经包含 id）。另外，布局动作在命令面板里归在「壳·设置」组，建议归到「布局」组（nit）。

证据：/workspace/hr/vera-compare/m1s2fix/（fix.json、reg.json、*-empty-*.png、*-palette*.png、legacy-palette-rawid.png、legacy-3b2e92d4/），以及 vitest-3b2e92d4.json。

## [VERA-FE] M1-s3 复审 — HEAD e3b92bd6（只读；临时 worktree 已删除；证据 /workspace/hr/vera-compare/m1s3/）

**结论：MUST-FIX**（1 个 P2：保存的“成功”判定与声明不一致；其余项通过）

### 通过项
- **CommandSearch**
  - 在 ?uw=1（5 项）和旧 UI（49 项）里，`.wb-command__id` 都是 0，列表文本里也没有任何原始 id。
  - 按 id 搜 `panel.open.history`、`layout.reset`，以及 `open history`，都能命中。
  - 新增分组「布局」：?uw=1 中有 4 项；旧 UI 中 写作 37 / 媒体 5 / 布局 4 / 壳·设置 3。
  - 所有权表的例外合理：这是 Vera 提出的 P3 修复，只改了拥有该面板的组件，属于最小改动。
  - 改动的那条断言（layout.reset：壳·设置→布局）是本意内的重新分组，合理。
  - nit：旧 UI 的「布局」组实际装的是 普通/专业 模式切换（layout.setMode.*），名称略牵强；commandSearch.css 里的 `.wb-command__id` 规则已成死代码。
- **真实面板**（1366 / 1440 / 1920 / 1440@1.25，四档结果一致）
  - 「作品结构」复用 NovelStructureRail：3 章，选中联动正常。
  - 「章节属性」的章号、字数、状态（草稿）、版本与 GET 返回一致。
  - 改标题后出现脏标记；脏状态下切换章节会被阻止，并显示中文提示。
  - 停靠到 left / bottom / float / right 以及切换 split-h 后，草稿都还在、脏标记不丢。
  - 关闭时弹出确认框，三个按钮的行为：
    - 「取消」：草稿保留；
    - 「放弃修改」：面板关闭，不发写请求；
    - 「保存并关闭」：发出 1 次 POST 后关闭。
- **改名（Playwright 拦截，所有非 GET 都被 fulfill/abort，不会到达 8000）**
  - 请求为 `POST /api/chapters/73586d65:1/rename`，body `{"title":…,"version":2}`。
  - 返回新版本 3：显示「已保存（版本 3）」。
  - 409：显示「章节已被其他地方修改，请刷新后再改。」，保持脏状态。
  - 500 / 网络错误：显示「保存失败，请重试。」，保持脏状态。
  - 刷新只发 `GET /api/novels/73586d65/chapters`，显示「已刷新」。
- **旧 UI**
  - 18 页对比 3b2e92d4：结构 diff 为 0，文本 diff 为 0；像素只有 IMAGE 页一处 3px 竖条（滚动条或动画噪声）。
  - U4 快扫写请求为 0；全程 GET-only。
- **变异测试**（基线为 24/24 通过）

  | 变异 | 测试结果 |
  |---|---|
  | isDirty→false | 2 条失败 |
  | 409 分支失效 | 1 条失败 |
  | 不使用返回的新版本 | 1 条失败 |
  | 重新显示 id | 1 条失败 |
  | 从 matchesQuery 去掉 id | 3 条失败 |

- **Hermia 自报数字复核**：layout 120/120 ✔，tsc 6 ✔；regression 475 子集未单独复跑，由全量覆盖。

### MUST-FIX（P2）：只有返回新版本才算保存成功，代码并未实现
- InspectorPanel 只要拿到 2xx JSON 就算成功，没有校验返回的 version 是否大于提交时的 version。实测：
  - 返回相同版本：显示「已保存（版本 2）」，草稿被清空，脏标记消失，属于假成功。
  - 返回里没有 version：显示「已保存（版本 undefined）」，同样是假成功。
  - 返回 204：没有任何提示，保持脏状态，属于静默失败。
- 建议修复：
  - 要求 `saved?.version > input.version`，否则显示中文错误、保持脏状态；
  - 204 或异常响应也给出错误提示；
  - 补上这 3 个用例。
- IMPLEMENTATION_REPORT 里写的是 “success = server Chapter”，与 “new version” 的声明不一致。

### 文案 nit（S3，确认存在）
- 把「作品结构」停靠到右侧后，「章节属性」空态仍写「在左侧「作品结构」里选一个章节」。
- 建议改为不带方位，例如「在「作品结构」里选一个章节」。不阻塞。

### 全量 vitest（单独运行，机器空闲，load 约 1）
- 首跑：309/11344，Identity 8，调整后 309。新增 2 条失败：
  - GraphImageOutputStarter.additive「retires the sealed plan…」
  - StoryFactDownstreamImpact「…selected-A click after selection asset-B-ABA」

  两条各单独跑 3 次都通过，只剩基线中已有的 4 条失败。
- 重跑：308/11344，Identity 8。新增 1 条不同的失败：GraphDirectorImage.integration「protects IMAGE cost…」。
- 三条都在本轮未改动的文件里，且每次都不同，判断为环境抖动，与本改动无关。
- 但按规则，raw 308 仍超过门槛 307，记为门槛未严格达标（不归因于本次改动）。
- **App\* 问题**：6ba25ad7 / 42167577 / cbf4a3ed / 3b2e92d4 / e3b92bd6 五个版本的 App\* 失败都是 125 条，13 个文件逐个计数完全相同：

  | 文件 | 失败数 |
  |---|---|
  | AppAdaptationNavigation | 12 |
  | AppAuthorTaskNavigation.additive | 1 |
  | AppAuthorTaskNavigation | 10 |
  | AppBrokerRecovery | 4 |
  | AppDraftRecovery | 21 |
  | AppModuleNavigationIntent | 2 |
  | AppProductionReceiptNavigation | 2 |
  | AppRevisionHistory | 6 |
  | AppStorySourceNavigation | 9 |
  | AppStyleComparisonNavigation | 1 |
  | AppStyleDNANavigation | 20 |
  | AppWorkspaceResume | 33 |
  | AppWritingGoalRecovery | 4 |

  本轮没有新增或修复的 App\* 失败。

### 清理
- vite 4399 已停止；vera-wt-s4 已经 `worktree remove` 并 prune。
- 4299 与 8000 仍返回 200；wt 仅有未跟踪的 package-lock.json，未提交任何内容。

## [VERA-FE] M1-s3fix 复审 — HEAD 81a65eb8（代码 b7e98c69；只读；临时 worktree 已删；证据 /workspace/hr/vera-compare/m1s3fix/）

**结论：MUST-FIX**（仅 1 条测试缺口，属 P3、只需补测试；功能本身在浏览器里全部正确）

### 改名保存（Playwright 拦截全部非 GET，未触达 8000；1440 与 1366 两档结果一致）
每种情况都只发 1 次 `POST /api/chapters/73586d65:1/rename`。

| 拦截返回 | 「保存标题」按钮 | 「关闭」→「保存并关闭」 |
|---|---|---|
| 新版本（v3） | 「已保存（版本 3）」，非 dirty | 面板关闭 ✔ |
| 同版本 / 无 version / 204 / 空 200 / 非 JSON / 标题不符但版本更高 | 「保存没有确认，服务器未返回新版本，修改还在。」，保持 dirty、版本仍是 2 | 面板**不关闭**，弹窗写明「保存失败：…修改仍在面板里，没有保存」 ✔ |
| 409 | 「章节已被其他地方修改，请刷新后再改。」，保持 dirty | 不关闭 ✔ |
| 500 | 「保存失败，请重试。」，保持 dirty | 不关闭 ✔ |
| 网络失败 | 显示「…服务器未返回新版本…」，保持 dirty | 不关闭 ✔ |

nit（P3）：
- 网络失败也被归到“未确认”文案里，原因描述不准确。建议这种情况改回「保存失败，请重试」或「网络错误」。
- 关闭弹窗里的句末出现双句号「。。」。

### 附加项
- 空态文案：「作品结构」停靠到右侧后，显示「在「作品结构」里选一个章节…」，「在左侧」已去掉 ✔。
- 命令面板：
  - ?uw=1 共 5 项，分组为 写作 1 / 布局 4。
  - 旧 UI 共 49 项，分组为 写作 37 / 媒体 5 / 布局 1（layout.reset）/ 壳·设置 6（模式切换已回到这里）✔。
  - 两边 `.wb-command__id` 都是 0，没有原始 id 外露。
  - 按 `panel.open.history`、`layout.reset` 搜索仍能命中 ✔。
  - CSS 死规则已删除。
- 旧 UI 18 页对比 e3b92bd6：结构 diff 为 0，文本 diff 为 0；像素只有 IMAGE 页一处 3px 噪声（与上轮相同）。全程 GET-only。
- tsc 错误数为 6 ✔。相关测试 29/29 通过。

### 变异测试
| 变异 | 结果 |
|---|---|
| 去掉 `version > sent` 判断 | 1 条失败 ✔ |
| 去掉整个 version 判断 | 2 条失败 ✔ |
| 不调用 isConfirmedRename | 3 条失败 ✔ |
| **去掉 `c.title === i.title`** | **13/13 全部通过 ✘** |

**MUST-FIX（P3，只补测试）**：要补 1 个用例，即服务器返回版本更高但标题不同，应判为未确认、保持 dirty。原因：声明里的“title matches”目前没有测试守护，浏览器实测这一路径本身是正确的。

### 全量 vitest（单独运行，无 vite / 浏览器并发）
- 首跑：310/11347，Identity 9，调整后 309，超出门槛。新增失败如下：
  - GraphTextTemplateCapacity「refuses canonical overflow…」
  - Identity「delayed local file…」
  - StudioProductionGraphEditor.director「authors a director…」

  三条各隔离跑 3 次，结果分别为 3/3 通过、2/3 通过、2/3 通过，属于时有时无的抖动；src/creative 相对 3b2e92d4 没有任何改动。
- 重跑：309/11349，Identity 10，调整后 **307，门槛达标** ✔。超出的 2 条都是 Identity 抖动。
- 相对 e3b92bd6，之前那 2 条抖动已恢复。
- App\* 失败仍是 125 条，与之前各版本一致。

### 清理
- vite 4399 已停止；vera-wt-s5 已删除并 prune。
- 4299 与 8000 仍返回 200；wt 未提交任何内容。

## [VERA-FE] M1-s3fix2 复审 — HEAD 3490d0a7（代码 e1b91f25）

**结论：PASS**（附带 1 个 P3 文案小问题，不阻塞；门槛超 1 已确认是不可归因的 flaky）

- 变异测试（我自己跑，基线 16/16，恢复后 16/16）：
  - 去掉标题校验 → 标题不一致用例失败 ✔
  - 网络失败当成未确认 → 网络用例失败 ✔
  - 去掉句号清理 → 双句号用例失败 ✔
  - 新用例不是同义反复：mock 返回 `'别的标题'` 且版本 +1。
- 浏览器 1440 检查（所有非 GET 请求都被拦截，0 个页面错误）：
  - 正常保存：「已保存（版本 3）」，关闭前保存后面板关闭。
  - 标题不一致 / 版本相同：「保存没有确认，服务器未返回新版本，修改还在。」，仍是未保存状态，面板不关闭，没有「。。」。
  - 网络失败：「保存失败：网络错误，修改还在。」。
- tsc 6。
- 全量 vitest（单独跑，11352 个测试）：
  - 第 1 次：310 失败，Identity 10，调整后 308。多出的是 GraphDirectorImage.integration「protects IMAGE cost…」，单独重跑 3/3 通过。
  - 重试：308 失败，Identity 8，调整后 308。多出的是 StudioProductionGraphEditor.director.additive「authors a director in the canvas」，单独重跑 3/3 通过（M1-s3fix 时单独跑是 2/3）。
  - src/creative 没有改动。两次超出的都是不同的 flaky 用例，属于不可归因；严格按原始数字 308 > 307，门槛未达标。
- P3：网络失败后的关闭确认框前缀重复：「保存失败：保存失败：网络错误，修改还在。修改仍在面板里，没有保存。」。建议去掉重复前缀，并合并「修改还在 / 修改仍在」。
- 证据：vera-compare/m1s3fix2/

## M1-flaky (f8124581) [VERA-FE]

复审对象：f8124581（代码提交 7e96d0ba，tree 485ed7b5 已核对；f8124581 只在 7e96d0ba 上加了文档和日志，frontend/ 和 7e96d0ba 完全一致）。在临时 worktree 里 npm ci，单独起 vite 4399（独立缓存）。Playwright 拦截了全部非 GET 请求，记录到的写请求为 0。没有碰 :8000 mock、Hermia 的 :4299 和后端。证据在 /workspace/hr/vera-compare/m1flaky/。

**结论：按"三次全量取最好一次，调整后 ≤307"的规则判 PASS；按旧门槛（一次全量 + 一次重试）不通过。代码层面没有 MUST-FIX。**

1. **P3 关闭确认文案：通过**
   - 浏览器 1440，断网场景，弹窗正文正好是「保存失败：网络错误。修改仍在面板里，没有保存。」，前缀不再重复，也没有「修改还在」。
   - 测试用 toBe 断言整句。
   - 变异：把文案改回带「修改还在。」，测试按预期失败；还原后通过。
   - 备注（P4，不阻塞）：面板内的状态行仍是「保存失败：网络错误，修改还在。」，这次只要求改弹窗，这里没改。

2. **四个文件加 30s 超时：通过**
   - 和 3490d0a7 的 diff 只有一行注释加 `vi.setConfig({ testTimeout: 30000 })`，没有删改断言、步骤或 mock。
   - download-denied 用例：findBy 等待改为 10s，用例超时改为 30s，断言本身没动。

3. **产品改动 IndependentStudioWorkspace.tsx：通过**
   - 改法：首次 overview 到达时，如果带 requestedAssetId，就不再把 ASSETS 切成 GRAPH。defaultCanvasChosen 这个 ref 保证只判断一次，之后 requestedAssetId 变化不会再强制切视图。已保存的 resume 现场原本就跳过这个逻辑，不受影响。
   - 浏览器在 1366、1440、1920 三个宽度下，用路由打桩的独立项目 520adfa2 测试，只拦截读、不写：
     - 带资产深链：停在「素材工作区」，资产 reference.png 被读取并显示。
     - 不带资产：仍默认进「创作图」，和改前一致。
     - 无效资产 id：停在素材工作区，提示「记录不可用，或此功能尚未启用。」，页面没有崩。
     - 下载 403：显示「当前会话无权访问此项目」。
     - 深链之后切到「制作操作」再切回「素材工作区」，正常。
     - 浏览器后退、前进、刷新后都回到素材工作区。
     - 各视口都没有横向溢出，也没有 pageerror。
   - 变异：回退修复，download-denied 隔离跑 3/3 失败；带修复 3/3 通过。
   - 附带效果：IndependentStudioManualMask 在 3490d0a7 上 11 项失败，现在只剩 2 项。

4. **旧 UI（不带 ?uw=1）：通过**
   - 普通和专业两种模式共 18 页，文本 hash 和之前的 legacy 证据（m1s3fix/legacy-81a65eb8）18/18 一致，非 GET 请求 0。
   - P3 场景截图和 m1s3fix2 对照：只有弹窗文案按预期变了。

5. **全量 vitest 三次 + tsc**

   | 次 | 原始失败 | IndependentStudioIdentity | 调整后 |
   |---|---|---|---|
   | 1 | 308 | 8 | 308 |
   | 2 | 308 | 8 | 308 |
   | 3 | 307 | 8 | 307 |

   - 总数都是 11353。
   - 旧门槛：第 1 次 308，重试 308，不通过。
   - 三取最好：第 3 次 307，通过。
   - 各次多出的失败：
     - 第 1 次：PluginResourceDetail.additive「writing_presets only on explicit request」，隔离 3/3 通过。
     - 第 2 次：AppProjectStory「actual App navigation opens the project Story database」，隔离 3/3 通过。
   - 目标 flaky 用例在三次全量里全部通过，包括 download-denied。四个目标文件里剩下的失败是原有的，三次都一样。
   - tsc 6 个错误，和基线一致。

6. **新问题：环境漂移，需要跟进，不是这次提交引起的**
   - ComicLayoutsPanel（9 项）和 VoiceSubtitlePanels（1 项），共 10 项，现在稳定失败。
   - 报错是 "Unable to find role=img"，以及 jsdom Blob 的 "object.stream is not a function"。
   - 我同时在 3490d0a7 上重跑了一次全量：318 / ISI 8 / 调整后 318（上一轮是 308），这 10 项同样失败，Hermia 的 m1flaky-full-1/2 里也有。所以这是同一环境下两个版本共有的环境变化。
   - 同一环境下比较，f8124581 比 3490d0a7 少了约 10–11 个失败。
   - 但门槛余量其实是靠这次修好的 ManualMask 抵掉的，建议 Hermia 查清 ComicLayouts 的环境原因（jsdom/undici 的 Blob）。

7. **和 Hermia 证据交叉核对**
   - m1flaky-full-1/2 是 307 和 308，和我的三次一致。
   - REGRESSION_M1_FLAKY.md 说"相比基线修好 11 个"，但没提到这 10 个新出现的 ComicLayouts/Voice 失败，建议补上。

## M1-flaky2 (f3e0b496) — Vera 独立复核 [VERA-FE]

- 基线：HEAD f3e0b496，代码 dc1d4350，tree 26b512e4 已校验；临时 worktree /tmp/vera-m1f2，独立 vite :4399，所有非 GET 请求均被拦截，没有向 :8000 写入。相对 f8124581 只改了 novelPreviewPanels.tsx/.test.tsx 两个文件，没有 polyfill，也没有改 vitest setup/config。
- P4：浏览器 1440 实测，面板状态行逐字为「保存失败：网络错误。修改还在面板里。」（按钮保存与关闭确认两条路径一致）；P3 对话框文案「保存失败：网络错误。修改仍在面板里，没有保存。」未变。测试用 findByText 做全字符串精确匹配：变异（删掉末尾「。」）后 1 failed，恢复后 17/17 通过。✅
- Node 结论：engines 为 ">=22.14.0 <25"；Node 20.19.2 是 apt 版，没有内置 undici（process.versions.undici 为 undefined），用的是系统 undici 7.3.0。/tmp 下的 Node 22.14.0 二进制 sha256 与官方 tarball 一致，其内置 undici 为 6.21.1。ComicLayoutsPanel* 与 VoiceSubtitlePanels 共 9 个测试文件：Node 20 下 10 failed/78（object.stream is not a function），Node 22 下 78/78 通过。REGRESSION_M1_FLAKY.md 列出的 10 项与此一致。**确认**。
- 全量 vitest（raw / ISI / adjusted，ISI 按基线 8 计）：
  - Node 20：308/8/308，308/8/308（AssetLibraryPanel.navigation 有一次 file-load 失败，总数 11346），311/8/311。旧门槛（≤307，可重试一次）：❌；三次取最好（308）：❌。
  - Node 22.14：297/8/297，299/10/297，297/8/297。两种口径均 ✅。
- 抖动项：Node 20 并集比三次共有多 7 项，Node 22 多 2 项（都是 ISI）。这 7 项单独各重跑 3 次全部通过。单跑时 StudioProductionGraphEditor 和 ComicLayoutsPanel.geometry 各有 1 项失败，那是三次共有的固定失败，不属于抖动。ISI 单跑 3 次结果为 10/8/8，确实有抖动。
- 建议的 Node 22 新基线：三次共有的固定失败 298 项（297 个测试加 1 个 file-load 项 LocalAiBrowserJourneyContracts），清单见 vera-compare/m1flaky2/persistent-node22.json。
- tsc：Node 20 与 Node 22 都是 6 个错误，与基线和 Hermia 的 m1flaky2-tsc.log 完全一致。
- 交叉核对 Hermia 的 m1flaky2-full-node22-1：raw 302。我们的 298 项固定失败全部包含在内；多出的 4 项（CreativeWorkspace、IndependentStudioGraphWorkspace.presentation、ComicPublicationPanel、WorkspaceToolsPanel）在我们的三次运行中都没有出现，判断为抖动。Hermia 在 Node 20 下的 307/310/307 与我们的 308/308/311 同处一个区间。
- 结论：P4 通过，Node 根因确认。按旧门槛，Node 20 不达标（308 比 307 多 1，但多出来的只是抖动与环境差异，没有任何新的真实回归）。建议把门槛切换到 Node 22.14（符合 engines），以 297 adjusted / 298 项固定失败作为新基线，ISI 仍按 8 计，并允许重试一次。
- 证据目录：/workspace/hr/vera-compare/m1flaky2/。本节未提交。
