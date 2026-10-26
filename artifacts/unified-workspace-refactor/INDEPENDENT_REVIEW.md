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

## M2-s1 (6b8a9642) — Vera 独立复核 [VERA-FE]

环境：临时 worktree /tmp/vera-m2s1 固定在 6b8a9642（代码 822b89ec，tree fcd2c214 已校验 ✓），复制未跟踪的 lock 后执行 npm ci；自建 vite :4399（独立缓存）；Playwright 拦截全部非 GET 请求；Node 22.14。未改业务代码，未提交、未推送；未触碰 :4299 和 :8000。全量运行前只按 PID 停止我自己启动的 vitest（当时没有残留），每次全量都设置了 timeout。证据目录：/workspace/hr/vera-compare/m2s1/。

**结论：PASS（无 MUST-FIX）**，有两项中优先级问题需要跟进。

### 1. 浏览器（1366/1440/1920，DPR 1.25/1.5，CSS zoom 0.8/1.25，共 7 组配置）
- 五个面板都有真实内容（大纲在左、创作在主区、检查器在右、任务在底部、执行画布在标签页里），占位为 0，无溢出，页面错误 0，写请求 0，类模型请求 0。请求只有 GET novels/chapters/tasks。
- 送到执行画布：未选中节点时禁用，并显示原因「先在创作画布选中一个节点」；选中后可用。防抖：间隔 100ms 点两次、双击、去掉 disabled 后间隔 50ms 强制点击，都只送出 1 次；间隔 450ms 点两次送出 2 次 ✓。
- 命令面板：送到执行画布在禁用时没有 aria-disabled，按 Enter 提示「无法执行：…」；可用时送出 1 次。打开执行画布、打开创作画布、打开任务都能用。
- 快捷键：Mod+Alt+E、Mod+Alt+I、Mod+Alt+T 都生效；快捷键也有防抖 ✓；输入框获得焦点时 E 不触发 ✓。
- N4：浮动面板在拖拽、resize 到 60%、CSS zoom 2、body zoom 1.6、浏览器缩放 175% 下，7 组配置全部 dock=float 且标题栏仍在视口内 ✓。
- N5：工具栏「执行画布」按钮和主区标签页都正常 ✓。
- 无 token 时的任务中心：显示 EXPERIMENTAL_FEATURE_DISABLED 和读取失败文案，不会自动重试。
- 已知限制（送出的节点在画面外）：uw 中复现，**旧版非 uw 画布（视频 › 专业 › 双画布）同样复现**（x=-180，宽 186，只露出 5.5px）。原因是 linkToExecution 把节点固定放在 x:-220，属于既有问题，不是本轮引入的。

### 2. 变异测试（mutations.log）
- 去掉 registry 去重、去掉选中条件、去掉 /z 换算、z=1：都能被测试抓到。
- **a1 去掉 delay(minBusyMs)、a2 minBusyMs=0：变异存活**。现有测试只覆盖同一 tick 内的去重，没有覆盖 300ms 窗口。

### 3. 旧 UI 18 页对比（vs m1s3fix/legacy-81a65eb8）
18 页对 18 页，diff 为空，uw 0，非 GET 0。控制台错误：本轮 18 条（都是 401）；基线 19 条（18 条 401 + 1 条 404），没有新增。

### 4. 全量 vitest（Node 22.14，3 次）
| run | raw | ISI | adjusted | total |
|---|---|---|---|---|
| 1 | 300 | 10 | 298 | 11365 |
| 2 | 297 | 8 | 297 | 11365 |
| 3 | 297 | 8 | 297 | 11365 |
- 门槛 (a) 三次取最好 297 ≤ 297：**PASS**。门槛 (b) 第 1 次 298 超出，重试一次得到 297：**PASS（用掉了重试）**。
- 加载失败的文件：src/ui/LocalAiBrowserJourneyContracts.test.tsx，三次都失败，已在基线内。
- 三次都失败的有 298 项，与 m1flaky2/persistent-node22.json（298 项）**完全一致**：没有新增，也没有修复。
- 不稳定项有 3 个，只出现在第 1 次：
  - IndependentStudioIdentity 中 2 项：单独重跑 3 次，有 1 次失败（8/8/10 failed，其中 8 项是基线内的稳定失败）。
  - TaskCenter.additive 中 1 项：单独重跑 3 次全部通过。
  - 本轮没有改动 src/creative 和 src/taskcenter，判断是既有的时序 flaky。
- tsc 6 个错误，与基线和 Hermia 的 m2s1-tsc.log 一致；src/workspace 和 src/workbench 测试 188/188 通过。

### 5. 交叉核对 Hermia 的结果
- full-node22：她的 1 = 297/8/297。她的 2 = 300/10/298，且 total 只有 11250，有 2 个文件加载失败（IndependentStudioGraphWorkspace.presentation、ComicPublicationPanel），看起来是环境或负载问题，在我的三次运行中都没有复现。她的 3 与报告一致。
- tsc 一致。
- 她的 browser json 是在 :4299 上跑的，没有拦截请求，所以只能作参考；她的浮动和 execNodes 结论与我的一致。
- overlap/ 和 pretypefix 日志按要求忽略。

### 问题（按优先级）
- 中：300ms 防抖窗口没有测试覆盖（a1/a2 变异存活）。建议加 fake-timer 测试：间隔 100ms 触发两次只执行 1 次，间隔 350ms 执行 2 次。
- 中/低：送出的节点在画面外（x:-220），uw 和旧画布都存在，是既有问题。建议放到视口内或送出后自动滚动到该节点。
- 低：layout.showPanel 不在命令面板里，也没有快捷键。
- 低：命令面板中禁用项没有标 aria-disabled。
- 低：任务中心加载时有 2 次 GET，和「只在切换时读取」的文案不一致（都是 GET，无害）。
- 低：Mod+Alt+T 之后焦点为 null。
- 低：IndependentStudioIdentity 有 2 项时序 flaky，需要关注。

## M2-s1fix (8adb5dec) — Vera 独立复核 [VERA-FE]

环境：临时 worktree /tmp/vera-m2s1fix 固定在 8adb5dec。注意：所给 tree fa0afbbf 是代码提交 98a9dead 的 tree；HEAD 本身的 tree 是 aa4d272a。98a9dead..HEAD 之间 frontend/ 无改动，所以被测代码就是 fa0afbbf ✓。复制未跟踪的 lock 后 npm ci；自建 vite :4399（独立缓存）；Playwright 拦截全部非 GET；Node 22.14。只按自己记录的 PID/PGID 停止进程（全量开始前没有我的 vitest 在跑），每次全量都加了 timeout。没有提交、没有推送，没有碰 :4299 和 :8000。证据目录：/workspace/hr/vera-compare/m2s1fix/。

**结论：PASS（无 MUST-FIX）**。有一个中优先级问题：送出第 4 个及以后的节点时，会与前面的节点完全重叠。

1. **300ms 防抖**（mutations.log，22 个相关测试，基线全部通过）：
   - 我自己的变异全部被抓到：去掉 show 的 delay、去掉 send 的 delay、两个都去掉、minBusy=0、去掉 registry 去重。
   - Hermia 的变异我全部复现：x=-220、去掉 aria-disabled、去掉 focus、把 useTaskCenter 回退到 6b8a9642，都被抓到。
   - 另外加了一个：把 Mod+Alt+P 置空，被 2 个测试抓到。
   - 存活的弱变异：去掉 microtask 里的 cancelled 判断（Hermia 的 no-microtask-dedupe 与此同类）。原因是 loaded.current 已经起到了去重作用。唯一的影响是：如果在一个 microtask 内切换了队列或过滤条件，过期的回调可能多发一次 GET。不会写数据，判定为低。
2. **送出节点的位置**（1366/1440/1920，uw 和旧版「视频 › 专业 › 双画布」都测了）：
   - 节点落在 world 坐标 (20, 20/90/160)，屏幕上是 (60, 60/130/200)，宽 186，全部完整在视口内 ✓。
   - 先缩放画布再送出：执行画布会重新挂载，视口回到默认值，新旧节点仍然都可见 ✓。副作用是用户调好的平移/缩放会丢失（这是既有行为）。另外，我脚本里的平移拖拽实际几乎没有生效（屏幕 x 只从 60 变到 29），平移前的状态等于没真正测到；但每次送出都会重置视口，所以送出后的结果不受影响。
   - **n%3 会重叠**：送 5 次时，第 4 个完全盖住第 1 个、第 5 个盖住第 2 个；送 6 次时，第 6 个盖住第 3 个（重叠 186×60，100%）。uw 和旧画布表现相同。建议按 floor(n/3) 做 x 方向偏移，或者给 y 加偏移。判定为中。
   - 旧双画布的其他部分没有变化：工具栏文字、两个 pane、送出后的提示文案都和之前一致；写请求 0，页面错误 0。
3. **layout.showPanel**：
   - 命令面板里有「显示面板（切到下一个主区面板）」，可用。执行后标签从 creative 切到 execution。
   - Mod+Alt+P 会在主区面板之间来回切换，不会打开对话框，URL 不变。
   - 在源码里搜索，这个组合键只被注册了一次。
   - 焦点在章节标题输入框时按下，不触发，焦点和输入框的值都不变 ✓。
4. **aria-disabled**：命令面板中 4 个不可用项（reset、reopenPanel、toggleCollapse、sendToExecution）都带有 aria-disabled="true" 和原因 title；可用项都没有这个属性 ✓。
5. **任务中心**：挂载时只发 1 次 GET（之前是 2 次）；关闭后用 Mod+Alt+T 重新打开，也是 1 次 ✓。
6. **焦点**：按 Mod+Alt+T 后，焦点落在 section[data-panel-id=tasks] 上 ✓。
7. **补丁复核**：
   - patches/m2s1fix-shared-nonentry.patch 与 `git diff 6b8a9642 HEAD` 中 DualCanvas.tsx、useTaskCenter.ts、CommandSearch.tsx 三个文件的改动逐字节一致。改动很小，都带 [HERMIA-FE-20261024 M2-s1fix] 标记，没有无关改动。
   - 对其他使用这些共享文件的地方的影响：
     - DualCanvas 也被 ImageRebuild/VideoRebuild 使用：只改变了送出位置。
     - useTaskCenter 也被旧 TaskCenter 使用：挂载时的读取推迟一个 microtask，旧 UI 18 页无差异，taskcenter 测试通过。
     - CommandSearch 也被 App 的旧命令面板使用：只多了 aria-disabled 和 title，是纯增量。
   - 判定为可以接受。
8. **旧 UI 18 页**（对比 legacy-81a65eb8）：
   - 18 页对 18 页，diff 为空，settings 相同，非 GET 为 0。
   - 控制台错误 18 条，全部是 401；基线是 19 条（多 1 条 404）。
   - 这 18 页不包含送出后的状态，所以送出位置的变化只在上面第 2 项里测了。
9. **全量 vitest**（Node 22.14，3 次）：

| run | raw | ISI | adjusted | total |
|---|---|---|---|---|
| 1 | 300 | 10 | 298 | 11375 |
| 2 | 297 | 8 | 297 | 11375 |
| 3 | 299 | 10 | 297 | 11375 |

   - 门槛 (a)：三次取最好 297 ≤ 297，**PASS**。
   - 门槛 (b)：第 1 次 298 超出，用一次重试后 297，**PASS**（重试已用掉）。
   - 加载失败的文件：只有 LocalAiBrowserJourneyContracts，三次都失败，属于基线。
   - 三次都失败的有 298 项，与 persistent-node22.json **完全一致**：没有新增，也没有修复。
   - 不稳定项：
     - IndependentStudioIdentity 的 2 项：在第 1、3 次全量中失败；单独重跑 3 次，每次都只有 8 项失败（全是基线里的稳定失败），这 2 项都通过了。
     - TaskCenter.additive 的 1 项：在第 1 次全量中失败，单独重跑 3/3 通过。它在 m2s1 也出现过，那时 useTaskCenter 还没改，所以不是这次改动引入的。
     - StudioModelCameraWorkspace：Hermia 的第 1 次全量里失败过，我单独重跑 3/3 通过。
   - total 比上一轮多 10 个测试，就是新增的 m2s1fix.test.tsx。
   - tsc 6 个错误，与 m2s1 和 Hermia 的结果一致；workspace/workbench 测试 198/198 通过。
   - 交叉核对 Hermia 的 m2s1fix 三次全量：298/297/297，与报告一致。

**问题（按优先级）**
- 中：送出第 4 个节点起会与前面的节点完全重叠（n%3），uw 和旧双画布都存在。
- 低：送出会重置执行画布的视口，用户的平移/缩放会丢失（既有行为）。
- 低：useTaskCenter 的 cancelled 判断没有测试覆盖（属于弱变异）。
- 低：IndependentStudioIdentity 有 2 项时序 flaky，继续观察。

## [VERA-FE] M2-s1fix2 + M3-s1（3520d679）

树哈希核对：73ac909c→a77e9964 ✓，2abedfb3→a9f1821e ✓；3520d679 只改文档和日志，没有前端改动。临时 worktree /tmp/vera-m3s1（detached），用未跟踪的 lock 跑 npm ci；自己的 vite 跑在 4399；Playwright 拦截全部非 GET 请求。证据在 /workspace/hr/vera-compare/m3s1/。

### M2-s1fix2（73ac909c）— PASS（附一条测试意见）
- 浏览器实测（m3s1/browser/check.json）：
  - uw 视图，1366 下执行画布 750×449：9/12/13 个节点重叠均为 0。9 个都在视口内，第 10 个起（第 4 列，世界坐标 x=638）出了视口。拖动平移可以看到。
  - uw 视图，1920 下执行画布 1304×761：12 个都在视口内。
  - 旧双画布（视频›专业›双画布），1366 下 594 宽：第 7 个起出视口；1920 下第 13 个出视口。重叠均为 0。
  - 没有自动滚动。
- 发送后保留平移和缩放（只针对 uw）：平移到 translate(-360,40) 后再发送，视图保持不变，第 13 个节点在视口内。旧双画布在发送时仍按原行为重置视图（key=rev，没传 initialViewport），符合预期。
- 测试改动的裁定：m2s1fix.test 把“每个节点都在视图内”改成了只检查前 3 个。m2s1fix2.test 补充了 9 个节点不重叠、在 750×449 内的断言。但没有任何测试断言“最新发出的节点可见或可达”，所以判为**断言被削弱**。建议补一条断言：最后一个送出的节点在视口内，或者送出后视图会自动跟随到它。
- 变异测试（m3s1/mutations.log）：
  - 删掉 useTaskCenter 的 `cancelled ||` → 被 useTaskCenter.m2s1fix2.test 抓到 ✓。
  - 列偏移改成 0 → 被 m2s1fix2.test 抓到 ✓。
- RebuildCanvas 新增的 3 个可选 props 默认值和旧行为一致。DualCanvas、ImageRebuild、VideoRebuild 都没有传这 3 个 props ✓。

### M3-s1（2abedfb3）— MUST-FIX（1 条，中等）
- 通过的项：
  - 两个画布选中节点后，都会显示「画布节点属性 · 创作画布/执行画布」。
  - 改名成功后提示“已保存到本机草稿（未同步服务端）”，画布标题同步更新，刷新后保持。
  - 注入 setItem 抛错 → “写入本机草稿失败（浏览器存储不可用或已满）。”，草稿保留，画布不变。
  - 注入读回不一致 → “写入后读回不一致，未保存。”，草稿保留。
  - 两个画布的选择互相独立。
  - 有脏草稿时：点选另一个画布的节点会被拒绝，属性面板保持不变，「回到章节属性」按钮被禁用。切换作品被拒绝，并提示 blocked。
  - 放弃后切换作品，属性面板回到章节属性。
  - 非 GET 请求 0 个，模型请求 0 个，没有 pageerror。
- **MUST-FIX**：切换作品时视口记忆没有被清空。
  - 实测：在雾港把执行画布平移到 translate(-360,40)，然后切到「空画布工作室」，新作品的执行画布仍是 translate(-360,40)（1366 和 1920 都复现）。
  - 原因：`vps.current = {}` 写在 useEffect 里。新 novelId 触发的那次渲染已经用旧的 vps 作为 initialViewport 重新挂载了画布。
  - 这与 IMPLEMENTATION_REPORT 第 153 行“切换作品会清空 viewport memory”的说法不一致。
  - 我加的变异“删掉 vps 重置”没有被任何测试抓到。
  - 建议：按 novelId 给 vps 分 key，或在渲染期同步重置；并补一条测试。
- 变异测试：
  - Hermia 的 5 个我都复现了：读回检查、共享选择、脏锁、忽略 initialViewport 共 4 个被杀。
  - “切作品保留 inspect”存活。我判断它的回退路径是真的：浏览器里干净切换后属性面板确实清空了，新画布挂载时会调用 onSelect(null)。所以它是等价变异体，接受。
  - 额外 2 个：guardSwitch 忽略 nodeDirty → 被杀；删掉 vps 重置 → 存活（就是上面那个 MUST-FIX）。
- 低优先级问题：
  - 选中节点时，面板标题仍然是「章节属性」。guardSwitch 的提示也说「章节属性」里有未保存的标题修改，实际是节点草稿。
  - 属性面板显示执行画布节点时，再点一次创作画布里那个已经选中的节点，面板不会切回去（选择没变化，就没有 onSelect）。必须先点空白处再点节点。
  - 在执行页签里发生的脏点选，没有看到 studioMsg 提示。提示只渲染在创作面板里。
- 规格：在 /workspace/hr/wt 的 docs/architecture 和 artifacts 里没有找到附录 A 的 M3 验收清单或 t117u（unified-workspace-contract.md 里没有 M3 条目）。只搜了本机，没有搜其他机器。IMPLEMENTATION_REPORT 和 BLOCKERS 也写了没找到。因此只能对照 brief 来核对。
- patches/m3s1-shared-nonentry.patch 与 `git diff 73ac909c 2abedfb3 -- RebuildCanvas.tsx UnifiedWorkspacePreview.tsx studioPreviewPanels.tsx` 逐字节一致 ✓。

### 回归
- 旧 UI 18 页对比 m1s3fix/legacy-81a65eb8：完全一致。
- 全量 vitest，Node 22.14，三次都设了超时：

  | 轮次 | raw | ISI | adjusted |
  |---|---|---|---|
  | 1 | 297 | 8 | 297 |
  | 2 | 299 | 10 | 297 |
  | 3 | 300 | 10 | 298 |

  - total 都是 11384（比上一轮 11375 多 9 = m3s1 的 7 + m2s1fix2 的 2）。
  - 门槛 (a)：三次最好为 297 ≤297 ✓。门槛 (b)：第一次就是 297 ✓。
  - 加载失败只有基线已有的 LocalAiBrowserJourneyContracts。
  - 三次失败的交集共 298 条，与 persistent-node22.json 完全相同，没有新增也没有消失。
  - flaky：
    - IndependentStudioIdentity 的 2 条（第 2、3 次），是已知问题。单独跑时该文件仍是基线的 8 条失败。
    - StudioCanvasVideoTask.integration 1 条（只在第 3 次出现，Test timed out in 5000ms）。机器负载 25–46，有别人的 vitest 在跑。单独跑 5 次：前 3 次是超时、失败、超时（外层 300s timeout），负载下降后第 4、5 次连续通过。不在改动范围内。
- tsc：6 个错误，与基线一致。workspace 和 workbench 测试 23 个文件、206 个用例全部通过。

## M4-s1 (ea856da7) [VERA-FE]

- 对象：分支 work/hermia-uw-m4-20261024，HEAD ea856da7，tree d1311067 已核对；基于 3520d679。临时 worktree 固定在 ea856da7，用 npm ci 安装，Node 22.14，vite 起在 4499；所有非 GET 请求都被路由拦截（拦到 0 次），页面错误 0。复审结束后已停 vite、删除并 prune 临时 worktree。证据在 /workspace/hr/vera-compare/m4s1/。
- **结论：PASS**（无 MUST-FIX）。

### 浏览器（?uw=1；1366/1440/1920，DPR 1.25/1.5，CSS zoom 1.25 @1366/1920）
- 跳到主区域：DOM 里它是第一个可聚焦元素；获得焦点后可见（top 6px，2px 实线描边）；按 Enter 后焦点进入 #uw-main（role=main，aria-label=主区域）。**但不打补丁时**，页面加载后焦点落在「搜索功能」，第一次按 Tab 到的是「执行画布」，按 Shift+Tab 才回到跳转链接（和 M4_REPORT 记的 PARTIAL 一致）。
- tablist：role=tablist（aria-label=中间面板）/role=tab 都对，aria-selected 跟着切换，roving tabindex 始终只有一个 0；→/← 循环、Home/End 都正确（快速连按也正确）；0 次写请求。
- 分割条（outline/inspector/tasks）：role=separator、aria-orientation、valuenow/min/max/valuetext（「N 像素」）、aria-controls 指向的元素都存在，并随方向键实时更新（每步 16px）；Home=min，End=valuemax，超出两端会被钳住；outline 拉到最大时主区 320 宽，tasks 拉到最大时主区高 239，都 ≥ 下限。拖动中按 Esc：270→恢复成 180。
- 焦点描边可见（tab、分割条、跳转链接）；7 种配置下 scrollWidth 都等于 clientWidth；主区最小 614×403（1366 + zoom 1.25）；1366 + zoom 1.25 下工具栏高 108px，换行正常，状态行在第二行。
- axe-core（只扫 dock-layout）：每种配置都只有 color-contrast（serious）×3，位置是 .nv-rail__h / .nv-rail__vol（作品结构面板里复用的旧组件，不属于本次改动）；M4 新增元素没有违规。
- 旧 UI（不带 uw、?mode=pro）：没有跳转链接，也没有 dock-layout，正常加载，0 写请求、0 错误。本次 diff 没有动 src/workspace 以外的源码。

### 裁定：aria-pressed → aria-selected
判定为**规格变更，强度不变，不算断言变弱**。理由：组件确实改成了 role=tab，aria-selected 才是正确的语义；三处旧测试仍然逐个 tab 断言 true/false 和切换后的值，其他断言一字未改（已对 3520d679 做 diff）。变异「删掉 aria-selected」时，这 3 条旧测试加 m4s1 共 4 条全部失败，证明它们仍然有效。

### 初始焦点补丁 patches/m4-s1-commandsearch-initial-focus.patch
只在临时 worktree 里应用过（可以干净 apply）。打补丁后：加载时焦点在 BODY，第一次按 Tab 就到「跳到主区域」；命令面板打开后焦点进输入框，按 Esc 关闭后焦点回到「搜索功能」触发按钮（回焦行为保留）；workspace/workbench/rebuild 三个目录 286/286 通过，CommandSearch 两个测试文件都通过。旧 App 首页不渲染 CommandSearch，补丁只去掉了挂载时抢焦点。**建议应用**，并补一条测试（挂载时不抢焦点 + 关闭后回焦），目前没有测试覆盖这两点。是否正式应用由 Hermia 或用户决定。

### 变异
- 删 aria-selected：抓到（4 条失败）
- 方向键失效：抓到
- 删 Esc 恢复：抓到
- 删跳转链接：抓到
- 删 roving tabindex：抓到
- 补充：去掉循环（→ 到末尾停住）**存活**；去掉 tab 的 Home/End **存活**（浏览器实测都正常，只是没有测试锁住）。

### 测试
- 目标子集（Node 22.14）：42 个文件，286/286 通过；tsc 6 个错误，和基线一致。
- 全量 vitest：**本轮未跑（PENDING）**，等 M5 合并后由 Hermia 统一跑，按现行门槛复核。

### 和 Hermia 证据对照
logs/m4s1-browser.json 的 15 种配置和我的结果一致：无横向溢出，主区 ≥320×200，Shift+Tab 回到跳转链接，分割条每次 →→ 是 248→280，End=valuemax，Esc 能恢复，0 次非 GET。截图 21 张和日志对得上。说明：她的脚本只是记录非 GET 请求，没有拦截；我这边是拦截的，结果同样是 0。

### 问题（按优先级）
- P2：不打补丁时初始焦点在「搜索功能」，跳转链接不是加载后的第一个 Tab 停点 → 应用上面的补丁并补测试。
- P3：tab 的循环和 Home/End 没有测试锁住（两条变异存活）→ 补两条断言。
- P3：只有当前选中的 tab 带 aria-controls；面板是 role=region，没有 aria-labelledby 指回 tab；分屏时两个 tab 可能同时 aria-selected=true，但 tablist 没有标 aria-multiselectable。建议补齐或在 contract 里写明。
- P3：跳转链接获得焦点时会盖住左上角的「搜索功能」按钮，这时用鼠标点不到它（只在获得焦点的那一刻发生）。可以把链接往右挪，或在失焦时立即收起。
- P3（不属于本次改动）：作品结构面板里旧组件 .nv-rail 有 3 处颜色对比度不足（axe serious）。

## [VERA-FE] M5-s1（abfe866a）

- 基线 3520d679，HEAD abfe866a，tree a976e97d ✓；代码 diff 仅 frontend/src/workspace/（另有 M5_REPORT.md 文档）✓
- 环境：临时 worktree /tmp/vera-m5s1，Node 22.14，vite :4399，所有非 GET 拦截（rename 由 route mock 应答，未转发）；证据 vera-compare/m5s1/

### 浏览器（1366，route mock）
| 项 | 结果 |
|---|---|
| beforeunload 干净时 | 本组件未挂监听（基线 1 个为页面其它来源），dispatch 不 preventDefault ✓ |
| 变脏 | 监听 +1，preventDefault=true，close(runBeforeUnload) 弹 beforeunload 对话框 ✓ |
| 放弃修改后 | **监听仍挂着**（计数不降），但 handler 内 isDirty 判定→不拦截；功能等价，属“仅脏时挂载”未严格满足（LOW，见下） |
| 乱序：A→B→A，B 的旧响应 4s 后回 STALE 数据 | 雾港大纲不出现 STALE ✓（query key 按作品隔离）；回到 B 时才显示其自身数据 ✓ |
| 慢保存 3s 中途继续编辑 | 输入框保存中可编辑；保存后值保留"来信XY"、仍脏、提示 已保存（版本 3），版本更新 ✓ |
| 脏时切换作品 | 被拦截并提示 ✓ |
| 写挂起 >20s | 20.0s 出现「保存超时…不确定是否已保存。修改还在面板里…」(role=alert)，草稿保留、仍脏、beforeunload 仍生效，未宣称成功/失败 ✓ |
| 读挂起 >15s | 显示「读取超时：服务器长时间没有回应，请稍后重试。」✓；但同时显示「还没有章节。」空态，易误导（LOW） |
| 模型调用 / 非 GET 透传 | 0 / 0 ✓ |

### 变异（src/workspace 基线 172/172）
- Hermia 11 个：M2,M4–M9,M11 杀死；M3、M10 存活（同报告）。**M1（删除 host 的 tracker.update 项目切换标 stale）在我这里存活，与 M5_REPORT“M1 已杀”不符。** 原因：m5s1.test.tsx 中 stale 用例只测 LifecycleTracker/ActionRegistry 单元，未经 host 接线。
- 自加：V2 总是挂载且总是拦截→杀；V2b 总是挂载但 handler 判脏→存活（与上面浏览器观察一致）；V3 章节保存无条件清草稿→杀；V4 节点保存无条件清草稿→存活；V5 isLatest 恒真→杀；V6 写超时标为 read→存活（等价，UI 文案由 instanceof 决定）。
- 裁定：M3 接受（当前流程等价）；M10 接受（等价）；M1 不接受。

### 运行
- 定向子集（workspace/workbench/rebuild/taskcenter）：57 文件 477/477 ✓；tsc：6 errors（与基线一致）✓
- 全量：待合并后跑（pending）

### 结论：MUST-FIX
1. 【MUST】补 host 级测试：发起动作→切换作品→断言 stale（使 M1 被杀），并更正 M5_REPORT 中 M1 的记录。
2. 【LOW】useBeforeUnloadGuard 放弃修改后监听未卸载（dirtyNow 快照在 inspectorDirty ref 更新前计算，之后无 store 通知）；补“监听挂载数”测试（V2b）。
3. 【LOW】节点检视器条件清草稿无测试（V4）；读超时时不应同时显示“还没有章节。”

## M3-s1fix (8563bd54) — [VERA-FE] 独立复核

结论：**MUST-FIX**（P1：真实浏览器里发送后自动平移从不生效）

- 代码树：310840ef tree 88358e6a；`git diff 310840ef 8563bd54 -- frontend` 为空（8563bd54 只改文档）。临时 worktree /tmp/vera-m3s1fix，vite :4499，所有非 GET 请求都被拦截（writes=[]，无模型请求）。
- **1 按 novelId 记视口：PASS**（uw，1366/1920）。在 A 平移后：创作画布 translate(-260,40)，执行画布 translate(-320,40)。切到 B 时两块都是默认 translate(40,40)；切回 A 时两块都恢复为 A 的值。B 自身的平移也是独立保存的。变异“去掉按 novel 分桶”（读、写各一处）都被杀。
- **2 发送后显示最后一个节点：FAIL（P1）**。1366/1920 下先把执行画布平移到 translate(-320,40)，再发送 1/6/12 次，tf 始终不变，最后节点不在视口内（1366 s1 lastInView=false，s6 false）。放大到 1.1 并平移开后再发送，1366 下第 13、14 个节点在视口外，tf 不变。
  - 根因（临时插桩 console 证实，已还原）：执行画布在切到执行 tab 时挂载，revealLast=true，但 mount-only useLayoutEffect 读到的 svg getBoundingClientRect 是 **0×0**（面板此时尚未布局），于是命中 `!r.width` 提前 return，之后不再重试。
  - jsdom 单测 mock 了 rect，所以测不出这个问题。变异“reveal 永不执行”和“去掉平移”在单测中都被杀，但真实 UI 等同于这两个变异。
  - 建议：在 ResizeObserver 或首个非零尺寸时执行一次 reveal（一次性），并加一个 rect 先为 0 后为非零的测试。
  - 不跳动：tab 往返（未发送）时 tf 不变 ✓。但这一项因为 reveal 从不触发而无从验证；修复后需复测“手动平移后切 tab 是否被 revealExec 拉回”（revealExec 只在换作品或保存视频后才复位，存在跳动风险）。
  - 旧 DualCanvas（1366）：12 次发送后 tf 保持 (40,40)，与 M3-s1 时一致，不受影响 ✓。
- **3 低优先级项：PASS**。标题显示为 `节点「新文本输入」属性`。先选执行节点，再点已选中的创作节点，检查器切回创作画布节点 ✓。执行 tab 中脏状态下改选会显示 uw-inspector-blocked：“节点「参考 · 新文本输入」有未保存的修改…”，属性面板保持原对象；点“放弃”后提示消失，可以正常改选 ✓。
- **4 Hermia 的工作**：8 个变异我自己重跑全部被杀（m3s1fix.test.tsx 共 5 个测试；她日志中的“(12)”与报告第 174 行的 5 不一致，P3）。IMPLEMENTATION_REPORT 第 153 行已更正 ✓。第 155 行仍写“发送保持视口”，已过时（P3）。patches/m3s1fix-shared-nonentry.patch 与 RebuildCanvas diff 完全一致；DualCanvas、ImageRebuild、VideoRebuild 都不传 revealLast，重复点击上报是幂等的，默认行为不变 ✓。
- **5 测试**：子集 workspace/rebuild/taskcenter 50 个文件 420/420 ✓；tsc 6（基线）✓；旧 UI 18 页与 legacy-81a65eb8 逐字节对比 18/18 SAME ✓（401 与基线相同）。**全量 vitest：PENDING（合并后跑）**。
- 证据：/workspace/hr/vera-compare/m3s1fix/（browser/check.json、probe.json、blocked.json、截图、mutations.log、subset.log、tsc.log、legacy/run）。

## M5-s1fix (937448a0) — [VERA-FE] 独立复核

结论：**MUST-FIX（仅补测试，P2）**。行为全部正确，但“当前项目刷新失败必须报错”没有测试守护（变异 V9 存活）。

- 树：937448a0 tree 7347a568 ✓。临时 worktree /tmp/vera-m5s1fix，vite :4499，非 GET 全部拦截（passNonGet=[]，model=[]）。
- **1 宿主级 stale 测试：PASS**。测试 render 真实的 `<UnifiedWorkspacePreview/>`（QueryClientProvider），只 stub 了 fetch，没有 mock 掉 host、tracker 或 actions。流程：n1 刷新挂起 → 切到 n2 → n1 迟到 → 断言无 已刷新/刷新失败/STALE，且仍为 n2。变异 M1（去掉 tracker.update）现在被杀 ✓。M5_REPORT 第 20 行已更正 M1（承认之前误报为 killed）✓。
- **2 stale 失败静默丢弃：行为可接受**。只有 epoch 变化（换项目，A→B→A 也会递增）时才返回 stale；当前项目自己的失败仍然是 `error`。浏览器验证：
  - 当前项目刷新 500 → 显示 alert「读取失败，请稍后重试。」和 status「刷新失败，请重试」，章节列表保留 ✓。
  - 雾港刷新 3s 后 500，期间切到 空画布工作室 → 无「刷新失败」，仍停在 520adfa2 ✓。
  - 小风险（可接受）：A 发起刷新 → 切 B → 切回 A，旧请求的失败会被丢弃；但切回 A 时 query 会重新读取，读取本身的错误仍由 alert 显示。
  - **缺口（P2，需补）**：变异 V9「把 error 也当 stale 丢弃」在 src/workspace/state 18/18 全部通过，存活。请补一个宿主级测试：当前项目刷新失败 → 断言出现「刷新失败，请重试」。
- **3 低优先级项：PASS**。
  - beforeunload（浏览器计数 add−remove，页面基线为 1）：干净 1 → 脏 2 → 放弃后 1（M5-s1 时为 2）✓；慢保存期间继续输入，保存后仍为 2 并拦截（还有新草稿）。新测试也是按 add/remove 计数 ✓。
  - 我之前存活的变异 V4「节点保存总是清草稿」现在被杀 ✓。
  - 读取超时与 500 都不再显示「还没有章节。」；空的成功读取仍显示「还没有章节。」✓。
  - P3：变异 V10「只要有 errKind 就隐藏章节列表」存活。浏览器中刷新失败时列表保留是正确的，但没有测试锁住这一点。
- **4 变异**（src/workspace/state，基线 18/18）：Hermia 的 M1、V2b、V4、V7、V8 全部被杀；我的 V2b（总挂监听、处理器内判脏）和 V2c（不再重算脏状态）被杀；V9、V10 存活（见上）。浏览器复跑 m5s1：
  - 乱序响应：无 STALE 泄漏 ✓
  - 慢保存期间编辑：输入保留为 来信XY 且仍为脏、版本 3、切换被拒 ✓
  - 写入超时：20.0s 显示「保存超时…不确定是否已保存」，草稿保留 ✓
  - 读取超时：14.9s 显示「读取超时」✓
  - 模型调用 0 ✓
- **5 测试**：子集 workspace/rebuild/taskcenter/workbench 57 个文件 481/481 ✓；tsc 6（基线）✓。**全量 vitest：PENDING（合并后跑）**。
- 证据：/workspace/hr/vera-compare/m5s1fix/（browser/check.json + 截图、mutations.log、mut.py、subset.log、tsc.log）。

## [VERA-FE] M4-s1fix（ae916e14）

- HEAD ae916e14，tree a3998e4d ✓；对比 ea856da7：代码改动仅 CommandSearch.tsx、DockLayout.tsx/.css，测试新增 CommandSearch.m4s1fix.test.tsx、m4s1fix.test.tsx，修改 m4s1.test.tsx 1 处（正则）。
- 环境：临时 worktree /tmp/vera-m4s1fix，Node 22.14，vite :4399，非 GET 全部拦截（0 次触发），单浏览器串行；证据 vera-compare/m4s1fix/

### 1. CommandSearch 初始焦点
- 补丁与 patches/m4-s1-commandsearch-initial-focus.patch 代码一致（仅注释标签 M4-s1→M4-s1fix 不同）✓
- 浏览器（1366/1440/1920/zoom1.25）：加载后焦点在 body，首个 Tab 到「跳到主区域」；打开面板焦点进输入框，Esc 后回到「搜索功能」按钮 ✓
- 旧 App（进入小说→展开「更多」）：加载不抢焦点，打开→输入框，Esc→触发按钮；与 ea856da7 基线行为一致 ✓
- 两个新测试的变异（去掉 wasOpen 守卫 / 去掉焦点恢复）各自被对应测试杀死 ✓

### 2. 标签顺序
- 浏览器 1366/1920：逆序依次点击各标签，DOM 顺序始终为 creative,execution（配置顺序）✓；←(首→尾回绕)、→(尾→首)、End、Home、↑、↓ 全部落到正确标签 ✓
- 变异：恢复按面板顺序渲染、去右回绕、去左回绕、去 Home、去 End → 全部杀死 ✓

### 3. ARIA
- 每个 tab 有 id=uw-tab-*、aria-controls=uw-panel-*；可见主面板 aria-labelledby="uw-tab-X uw-panel-title-X"，引用均存在；侧栏面板只指向自身标题 ✓
- aria-multiselectable：单屏无此属性，split-h 时 =true 且两个 tab selected，回单屏后消失 ✓
- 注意（LOW）：单屏时未显示面板的 tab 也带 aria-controls，指向不在 DOM 的 id（ARIA 允许但不理想，axe 未报）
- axe（1366/1920，单屏+分屏，dock-layout 范围及整页）：与 ea856da7 基线完全一致——范围内仅 .nv-rail color-contrast×3（已知）；整页另有 document-title/html-has-lang/page-has-heading-one/region×4，基线同样存在。无新增 ✓
- 自加变异：multiselectable 恒真、tab 去 id、labelledby 去掉 tab、删除 labelledby → 杀死；**labelledby 指向错误 tab（main[0]）→ 存活**（见裁定 5）

### 4. 裁定：跳过链接遮挡 —— 可接受
- 聚焦时位置：1366/1440/1920 为 [8,67,95,96]；zoom1.25 为 [10,110,118,146]（1366）/[10,104,118,140]（1920）
- 覆盖：左面板标题「作品结构」文字 + 「折叠」按钮左缘约 4px（按钮 [91,67,135,92]）；采样 5 点仍可点 3/5（zoom1.25 为 4/5）。不覆盖「搜索功能」。
- 仅在跳过链接自身聚焦时出现，焦点移走即隐藏；「折叠」仍可 Tab 到达且大部分区域可点击。被聚焦元素本身未被遮挡（符合 2.4.11）。无不可达控件 → 可接受。建议（LOW）：left 偏移或把 top 再加 ~28px 以完全避开标题行。

### 5. 裁定：面板名断言 精确→正则 —— 弱化断言
- 新写法 `new RegExp(s.title)`：未锚定的子串匹配，不再钉住 tab 与标题。实证：变异 V13（labelledby 引用 main[0] 的 tab）全部测试通过。
- 建议改为精确拼接：多标签主区 `${tabTitle} ${s.title}`（如「创作画布 创作画布」），其它面板 `s.title`；或锚定正则 /^创作画布 创作画布$/。

### 6. 其它
- 对比 ea856da7 的测试差异：除上述正则外无其它放宽；新增 5 个测试。
- Hermia 7 个变异全部复现为杀死。
- 定向子集（workspace/workbench/rebuild）：44 文件 291/291 ✓；tsc：6 errors（基线）✓；全量：合并后跑（pending）。
- 模型请求 0（旧 App 仅 GET /api/text-models 列表读取）。

### 结论：PASS（附裁定 5 的弱化断言，建议合并前改为精确名称）

## M3-s1fix2 (1916ea1b) — [VERA-FE] 独立复审：PASS

- 范围：代码提交 edf7576e；edf7576e..1916ea1b 不触碰 frontend（diff 为空）。证据：/workspace/hr/vera-compare/m3s1fix2/（脚本 m3s1fix2_browser.mjs 为 Vera 自写，改自 m3s1fix_browser.mjs，未使用 Hermia 脚本；全部非 GET 被拦截，writes=[]、model=[]、errs=[]）。
- 1 发送揭示（Chrome，起点 translate(-320,40)）：1366/1920 × k=1/1.1，发送 1/6/12/13 个节点后最后节点均在视口内，scale 不变，仅 x 最小平移（例 1366 k1：-320→-4→-4→-90→-296，节点贴边距 16px 左右；节点已可见时不动）。
- 2 手动平移后不回拉：1366 k1 平移到 translate(404,40) 后，切 tab、窗口 1200/1100 缩放再还原、切作品 520adfa2 再切回、视频节点保存（"已保存到本机草稿"，execRev 重挂载）及其后切 tab，变换均保持 translate(404,40)。
- 3 无跳动：默认视图连续发送 3 个（均可见），translate(40,40) 不变。
- 4 存活变异"已揭示则跳过"：判定为等价。ResizeObserver 在首次成功揭示的同一回调内同步 disconnect，effect 仅挂载时运行；StrictMode（main.tsx 已启用，浏览器验证即在 StrictMode dev 下）重放 effect 时外层 `!revealPending.current` 守卫已拦截，且第一次的 RO 已在 cleanup 中断开。无行为差异。
- 5 rAF 回退：addInitScript 删除 window.ResizeObserver（页面确认 hasRO=false），发送 1/12 均正确揭示，手动平移后切 tab 不回拉。
- 6 Hermia：自行复现 5 个变异 + 额外"去掉尺寸检查"：一次性不等待尺寸 3 失败、宿主不清 flag 1 失败、无 rAF 1 失败、RO 回调失效 2 失败、去尺寸检查 3 失败、守卫移除 8/8 通过（等价，同上）。patches/m3s1fix2-shared-nonentry.patch 与 edf7576e 的 RebuildCanvas diff 逐行一致。RebuildCanvas 其他使用方（VideoRebuild、ImageRebuild、DualCanvas）未传 revealLast/onRevealed，默认行为不变；旧 DualCanvas 1366 实测与 M3-s1fix 基线一致（发送后 translate(40,40)）。P3 文档：IMPLEMENTATION_REPORT 第 155 行已加更正说明；m3s1fix 变异日志 "(12)" 已解释（5+7）。均已修复。
- 7 测试：workspace/rebuild/taskcenter 423/423（首轮 1 个 TaskCenter.receiptCompanion 偶发失败，单独 3 次均过，整轮重跑 423/423，与本改动无关）；tsc 6（基线）；旧 UI 18 页对比 legacy-81a65eb8 18/18 一致；全量套件待合并后运行。

## [VERA-FE] M4-s1fix2（9f2a04e4）

- HEAD 9f2a04e4，tree 32b85cff ✓；对比 ae916e14：代码仅 DockLayout.tsx（aria-controls 条件化）、DockLayout.css（聚焦跳过链接居中）；测试改 m4s1.test.tsx、m4s1fix.test.tsx。
- 环境：临时 worktree /tmp/vera-m4s1fix2，Node 22.14，vite :4399，非 GET 全拦截（0 次），单浏览器；证据 vera-compare/m4s1fix2/

### 1. 面板名断言
- m4s1.test.tsx：精确名称（labelledby 以 uw-tab- 开头时为「标题 标题」，否则为标题）；m4s1fix.test.tsx 分屏用例锚定 ^<tab> <header>$ ✓。浏览器实测名称：创作画布 创作画布 / 执行画布 执行画布 / 作品结构 / 章节属性 / 任务，与断言一致。
- 上轮存活的 V13（labelledby 指向 main[0] 的 tab）→ 现被分屏用例杀死 ✓；另加 V13b（tab 与标题顺序互换）、V10（去掉 tab）→ 杀死 ✓

### 2. aria-controls 仅指向已渲染面板
- 浏览器 1366/1920：单屏 creative→uw-panel-creative、execution 无 aria-controls；分屏两者都有；切回单屏恢复。页面上所有 aria-controls 全部可解析，无悬空 id ✓
- 变异：恒有 aria-controls / 恒无 / 条件取反 → 全部杀死 ✓。上轮“仅已选 tab 带 aria-controls”导致 82 个失败的变异，现即为正式实现，基线 218/218 干净通过 ✓
- 测试变化说明：“每个 tab 都有 aria-controls”改为“仅已选 tab 有”，并新增“未选 tab 必须无 aria-controls”——属规格变更，非放宽。

### 3. 跳过链接居中
| 视口 | 矩形 | 中心偏移 | 完全可见 | 覆盖交互控件 | 下方网格采样 | Enter 后焦点 |
|---|---|---|---|---|---|---|
| 1366 | [639,67,727,96] | 0 | ✓ | 无 | 无 | main-zone ✓ |
| 1440 | [676,67,764,96] | 0 | ✓ | 无 | 无 | main-zone ✓ |
| 1920 | [916,67,1004,96] | 0 | ✓ | 无 | 无 | main-zone ✓ |
| 1366 zoom1.25 | [629,110,737,146] | 0 | ✓ | 无 | 无 | ✓ |
| 1440 zoom1.25 | [666,110,774,146] | 0 | ✓ | 无 | 无 | ✓ |
| 1920 zoom1.25 | [906,104,1014,140] | 0 | ✓ | 无 | 无 | ✓ |
- 加载焦点在 body，首个 Tab 到跳过链接 ✓

### 4. 其它
- 对比 ae916e14 的测试差异：无其它放宽。
- 定向子集（workspace/workbench/rebuild）：44 文件 293/293 ✓；tsc：6 errors（基线）✓；全量：合并后跑（pending）。
- axe 1366：范围内 color-contrast×3（.nv-rail，已知）；整页 document-title/html-has-lang/page-has-heading-one/region×4——与 m4s1fix 基线完全一致，无新增 ✓

### 结论：PASS

## M5-s1fix2 (834b8588) — [VERA-FE] 独立复核

结论：**PASS**

- 树：834b8588 tree be1ee435 ✓。相对 937448a0 只改了 m5s1.test.tsx（+8，新增 1 个测试）、M5_REPORT/INDEPENDENT_REVIEW（文档），以及 novelPreviewPanels.tsx 中的一行 JSX 注释（运行逻辑不变）。
- 新测试 render 真实的 `<UnifiedWorkspacePreview/>`，只用 `fetch.mockImplementationOnce` 让下一次章节读取返回 500，host、tracker、actions 都没有被 mock。断言：出现「刷新失败，请重试」，不出现「已刷新」，「雾港·第一章」仍在列表中 ✓。
- 变异（src/workspace/state，基线 19/19）：
  - P2 V9「刷新 stale||error 都丢弃」→ 新测试失败（被杀）✓
  - P3 V10「只要有错误就隐藏章节列表」→ 新测试失败（被杀）✓
  - 变异后均已用 git checkout 还原。
- 子集 workspace/rebuild/taskcenter/workbench 57 个文件 482/482 ✓；tsc 6（基线）✓。代码未变，所以不重跑浏览器。**全量 vitest：PENDING（合并后跑）**。
- 证据：/workspace/hr/vera-compare/m5s1fix2/（diff.patch、mutations.log、subset.log、tsc.log）。

## Merge (6652a661) — [VERA-FE] 独立复审：PASS

- 树：HEAD 6652a661 的 tree 为 299022d2（已核对）。证据：/workspace/hr/vera-compare/merge-6652a661/。
- 1 合并保真（三方，共同基点 3520d679，见 fidelity.txt）：frontend 下 19 个变更文件里，17 个与唯一修改它的已批准分支逐字节相同（M3=1916ea1b，M4=9f2a04e4，M5=834b8588；68cabfa3、b5771aa1 的 frontend 与已批准提交相同）。只有两处不同：UnifiedWorkspacePreview.tsx（M3 和 M5 都改过，git merge-file 出现 4 处冲突）和 m5s1.test.tsx（只有 M5 改过，合并后改了一行定位器）。
  - UnifiedWorkspacePreview.tsx 逐行复核（uwp-auto-vs-merged.diff），M3 和 M5 两边都完整保留：
    - M3：按作品分开记的视口 vpOf/setVpOf；revealExec/onExecRevealed；视频保存时清 flag；inspector 标题 specs/dirtyName；pickBlocked 提示。
    - M5：anyDirty（含 drafts）；DraftStore/useBeforeUnloadGuard；tracker.update 用的 useLayoutEffect；CanvasNodeInspector 和 InspectorPanel 都传了 drafts；onSettled 跟随最新选择。
    - 冲突处理：M5 的 vps 简化版和 vps.current={} 被 M3 按作品记忆的版本取代，这是有意的，也是正确的。拦截判断统一用 anyDirty() 加 M3 的具名提示。
    - 只有一处纯外观问题：M5 的 nodeDirtyRef 那一行插在了 M3 注释和它所注释的代码之间，不影响行为。
    - LatestGate、刷新失败的处理在 novelPreviewPanels.tsx、async.ts 里，这两个文件等于 M5 版本。
  - INDEPENDENT_REVIEW.md：1916ea1b、a9fb7471、68cabfa3、b5771aa1 四个已提交版本的每一行和每个小节都原样保留在合并版中（diff 无删除行）。
- 2 m5s1.test.tsx 定位器裁定：等价。
  - 新正则 /^「节点「.+」属性」停靠位置$/ 首尾都锚定。getByLabelText 遇到多个匹配会直接抛错，测试通过即说明只匹配到一个元素。
  - 这一行之外的所有断言没有变化。
  - 语义没有变：这一步之前已经 pick('c1')，节点检查器显示的是 c1。在 M5 分支上，同一个属性面板因为没有 M3-s1fix 的改名，仍然叫「章节属性」；合并后按节点命名。被重新停靠的始终是同一个 inspector 面板（DockLayout 的 aria-label=`「${spec.title}」停靠位置`），测试流程没有变。
- 3 Chrome（合并构建，端口 4499，所有非 GET 请求被拦截，nonGet、model、errs 全部为空）：
  - M3：1366 和 1920、k=1 和 1.1，从 -320 起发送 1/6/12/13 个节点，最后一个节点都在视口内，缩放不变，平移最小（1366 k1：-320→-4→-4→-92→-298）。手动平移到 402 后，切 tab、调整窗口大小、切作品 B（显示默认 40）再切回 A（恢复 402）、视频保存，都不回拉。节点已可见时不跳动。没有 ResizeObserver 时 rAF 回退正常。旧 DualCanvas 行为不变。
  - M4（1366、1440、1920，以及 125% 缩放）：
    - 首次按 Tab 落在跳转链接上。
    - tablist 方向键、Home、End 全部正确，单屏和分屏下 aria-controls 都没有悬空引用。
    - 三个分隔条：方向键每次 ±16，Home/End 到最小/最大值；拖动中按 Esc 恢复到原值（180→297→180）。
    - 旧 UI 的 /api/text-models 是 GET 请求，与 M4-s1fix 基线一致。
  - M5（1366 和 1920）：
    - 乱序的过期响应被丢弃（停留在雾港，stale=false）。
    - beforeunload 只在有未保存修改时挂上，放弃修改后摘除。
    - 写入挂起 20 秒后提示「保存超时……不确定是否已保存」。
    - 当前作品刷新失败时显示「刷新失败，请重试」，原列表保留；非当前作品的刷新失败静默丢弃。
    - 与 m5s1fix 基线一致。cleanClose 的报错是关页后的 waitForTimeout 造成的，基线中也有。
  - 旧 UI 18 个页面与 legacy-81a65eb8 对比，18/18 一致。
- 4 变异（在 workspace/rebuild/taskcenter/workbench 子集上跑，全部被杀死）：
  - M1 tracker.update 不递增 epoch：8 个失败。
  - M5 P2 将 stale||error 都丢弃：1 个失败（刷新失败测试）。
  - M4 labelledby 指向错误的 tab：1 个失败。
  - M3 去掉揭示前的尺寸等待：3 个失败。
  - M3 去掉按作品的视口键：1 个失败（A→B→A 测试）。
- 5 子集 502/502；tsc 6（基线）。
- 6 全量 vitest（Node 22.14，三次串行，每次超时 1500 秒，启动前确认没有其他 vitest 在跑）。总数 11423，每次都有 1 个文件加载失败（在基线内）。adjusted = raw − ISI + 8，8 是基线中的 ISI 数：

  | 轮次 | raw | ISI | adjusted |
  |---|---|---|---|
  | 1 | 297 | 8 | 297 |
  | 2 | 299 | 10 | 297 |
  | 3 | 305 | 10 | 303 |

  - 判定：(a) 三次中最好的为 297，≤297，PASS；(b) 第 1 次即 297，≤297，一次重试内 PASS。
  - 三次都失败的有 298 项，与 persistent-node22.json 完全相同，没有新增的持续失败。
  - 有 8 项不在基线内、只在部分轮次失败，单独各重跑 3 次：
    - 6 项 3/3 通过。
    - 2 项 ISI 用例各为 2/3 通过，它们本来就在 m1flaky2 的 node22 已知 flaky 列表中。
    - 全部与 workspace 改动无关。

## M6 (c3939f22) — [VERA-FE] 独立复核

- 范围：HEAD c3939f22 / tree 98089ce1；Node 22.14；Vite :4499；所有非 GET 请求一律被拦截（fulfill 409），实际记录 0 次写请求；未连接 :8000，未碰 :4299。
- **结论：MUST-FIX（测试缺口，小改即可）**。运行时行为全部通过。
- 浏览器（uw 面板：任务中心 + 审核收件箱）：REQ500 / DISABLED404 / 未知 code / HTML502 / 网络中断 → 可见文本、title、aria 均无原始 code；data-error-code 与实际 code 完全一致（STUDIO_REQUEST_FAILED / EXPERIMENTAL_FEATURE_DISABLED / VERA_UNKNOWN_CODE / STUDIO_NETWORK_FAILED）；文案为本地映射的中文。FORBID403 走来源级聚合提示，也没有 code。旧 UI 的任务中心入口在 /?novel= 下没有走到（落到了 uw 引导页），这一点记为局限。
- 变异测试（src/taskcenter，183 个用例）：TaskList 显示原始 code → 1 个失败 ✓；TaskList 去掉 data-error-code → 1 个失败 ✓；全部映射成同一句 → 2 个失败 ✓；去掉兜底 → 1 个失败 ✓；**ReviewInbox 显示原始 code → 0 个失败 ✗；ReviewInbox 去掉 data-error-code → 0 个失败 ✗**。MUST-FIX：ReviewInbox 的 problem 渲染需要补上与 TaskList 对称的断言。
- TaskCenter.test.tsx 断言变更的裁定：可以接受，属于规格变更（code 用 toBe 精确比较）。但文案断言用的是 toContain('请求未完成。')，只是子串匹配，IMPLEMENTATION_REPORT 称其为 “stricter” 有夸大。建议改为 toBe('请求未完成。请核对输入与连接状态。')。
- 数字：subset 503/503；tsc 6 个错误（与基线相同）；旧 UI 18 页文本与 merge 轮 18/18 完全一致；完整 vitest 三次 adjusted 297/297/298（raw 297/299/298，ISI 8/10/8），共 11424 个用例，持久失败交集 298 条，与基线相同；flake（ISI 2 条、receiptCompanion）单独各重跑 3 次，3/3 通过。
- 矩阵：算术正确（87/98）。有争议的条目见 vera-compare/m6/matrix-disputes.md：S2-3 和 M1-01..25 的引用有误；Hermia 的浏览器日志全部未做拦截；M2-06 应为 PASS，B9 的说法有误。
- 其他：nodeDirtyRef 是纯移动 ✓；m6 patch 与 git diff 完全一致 ✓；P3：e2c9d292 的 author 字段写成了 Vera；README 中的行数有小偏差。

## M6-fix (0bf7bdeb) — [VERA-FE] 独立复核

- 范围：HEAD 0bf7bdeb / tree 1b73c3ac ✓；Node 22.14；本轮没有改产品代码，所以没有开浏览器和 Vite；未连接 :8000，未碰 :4299。
- **结论：PASS**（下面只有 P3 级的文档小问题）。
- diff c3939f22..HEAD：只改了 TaskCenter.test.tsx（测试）和 artifacts/ 下的文档与日志，产品代码零改动 ✓。
- 新增的 ReviewInbox 测试：data-error-code 用 toBe('STUDIO_REQUEST_FAILED')；alert 的 textContent 用 toBe('请求未完成。')，因为 fake client 的 message 就是这一句，所以这是 span 的完整文本（完整长句只出自真实 client 的映射）；可见文本中不含 code ✓。TaskCenter.test 也改为对 span 全文 toBe('请求未完成。') ✓；"stricter" 的说法已在 IMPLEMENTATION_REPORT 中更正 ✓。
- 变异测试（src/taskcenter，184 个用例）：ReviewInbox 显示原始 code → 1 个失败 ✓；ReviewInbox 去掉 data-error-code → 1 个失败 ✓；ReviewInbox 改成 "message · code" → 1 个失败 ✓；TaskList 的两项变异仍然会失败 ✓。M6 的 MUST-FIX 已关闭。
- 数字：subset 504/504（63 个文件）；tsc 6 个错误（与基线相同）；taskcenter 文件夹跑了 7 次，其中 6 次 184/184，第 3 次有 1 个失败（失败用例名当时没有记录下来）；receiptCompanion 单独跑 3/3 通过，推定是已知的 receiptCompanion flake。
- 矩阵：按文件本身重新计数，PASS 87 / PARTIAL 7 / BLOCKED 2 / NOT_RUN 1 / FAIL 1 = 98，87/98 = 88.8% ✓。变化是 M2-06 PARTIAL→PASS、GATE-M6 NOT_RUN→PASS、M4-05 和 M1-ZOOM PASS→PARTIAL，所以 PASS 净增 0。P3：FINAL_HANDOFF 把 M2-06 写成 "NOT_RUN→PASS"，实际原来是 PARTIAL。争议表逐项都已处理：S2-3、M1-01..25 的引用、M2-03、M2-07、M2S-07 已更正；GATE-M6 引用的 297/297/298（raw 297/299/298，ISI 8/10/8，11424 个用例）正确，所引证据路径都存在。
- BLOCKERS：B9 已更正 ✓。B11 由表下注释给出理由（我在 c3939f22 跑过完整 suite）✓。P3：B11 表格行本身仍写着 "NOT_RUN"。
- patches：m6 patch 与 `git diff e2c9d292..HEAD -- frontend/src/taskcenter` 字节一致，可以反向应用 ✓。README 的行数与我按"整行精确匹配"方法重数的结果全部一致（0001 6/6、11/19；m3s1 20/33；m3s1fix 6/18；m6 2/2、2/2、20/20、10/10、17/17）✓。我在 M6 轮报的 7/7、12/19 用的是另一种方法，口径不同，不算错误。
- 提交署名（仅作记录）：52f0a548 的 author 是 Vera (review)，committer 是 Hermia；内容与我的 M6 追加字节一致 ✓。P3：IMPLEMENTATION_REPORT 说 e2c9d292 的 committer 也是 Vera，这与 git 记录相符。
- 证据：/workspace/hr/vera-compare/m6fix/。

## [VERA-FE] 视图工作集 M0–M5 独立复核（ee350ece，基线 51ff02b2，2026-10-24）

**结论：MUST-FIX（2 项）**。门禁全部通过，写安全与脏草稿矩阵通过；问题在于新建视图对话框的焦点管理，以及 M3 宿主测试没有真正守住 viewport 记忆接线。

### 门禁
- tsc 0，build 0；核心 67 文件 527/527（比 Hermia 记录的 66/526 多出 vw.m3host）；新增视图测试 18/18 通过。
- 完整 vitest 跑三次（Node 22.14，forks，maxWorkers=3）：raw 294/293/293，ISI 8/8/8，adjusted 294/293/293。规则 (a) 三次取最好 ≤297：PASS；规则 (b) ≤297、允许一次重跑：PASS（三次都 ≤297）。
- 相对 persistent-node22（298）没有新的持续失败。唯一不在基线里的失败是 PluginResourceDetail.additive 的 writing_presets 用例，三次里只出现 1 次，属偶发。vw.m2m4、vw.m3host、viewPreferences.vw 三次全部通过。

### 浏览器（自起 vite 4399；Playwright 拦截所有非 GET 请求；1366/1440/1920 三个宽度结果一致）
- 非 GET 请求 0 次，pageerror 0 次，没有写入 viewprefs 键（layout.v3 本来就会写，已有文档说明）。加载时不抢焦点。
- 视图对话框：打开后焦点在名称输入框，标注「仅本次会话」，重名和空名都会被拒绝，保存/应用/重命名/删除正常，Ctrl+Alt+V 能打开，对话框内 axe 0 违规。
- M2 矩阵：应用工作集时如果要关闭脏面板，会被拦下，布局和草稿都不变；改停靠位置或转浮动时草稿保留；脏状态下切换小说会被拦下。
- M3：A→B→A 切换时每部小说各自保留 viewport；重置回到默认并提示「仅本次会话」；刷新后回到默认。冷恢复标 BLOCKED：预览没有真实 scope，我试过「平移并保存工作集→刷新」，按设计会回到默认。
- M4：Ctrl+Alt+N/B/L 能循环切换并返回；输入中和 IME 组合时不触发；目标面板已关闭时给出说明且焦点不动；有 reduced-motion 规则。焦点指示只是 1px inset 阴影，偏弱（P3）。
- 页面级 axe：.nv-rail 有 color-contrast 问题，属已有问题，归 Design System Owner。

### MUST-FIX
1. **WorkspaceViewsPanel.tsx 对话框（role=dialog、aria-modal=true）没有焦点陷阱。** 复现：打开「视图」→ 连按 Tab 4 次，焦点离开对话框；或在第一个控件上按 Shift+Tab，焦点落到背后的「视图」按钮。另外提交重命名后焦点掉到 body。这两种情况下 Esc 都关不掉对话框，因为 Esc 只在卡片内部生效。仓库里 DockLayout.tsx（约 85–100 行）的对话框已经有 Tab 陷阱，这里属于回退。修法：照搬 Tab 循环；Esc 挂到 document 或 overlay 上；重命名后把焦点还给该行或输入框；关闭时把焦点还给触发按钮。
2. **vw.m3host.test.tsx 守不住 M3 接线。** 变异：把 UnifiedWorkspacePreview.tsx:98 的 onCreativeVp 改成空操作，该测试仍然通过。DBG 显示切 tab 后变换仍是 translate(-260,40)：面板的 DOM 被移出后又接回，RebuildCanvas 实际没有重挂载，所以这个测试验证的不是适配器。需要补一个真正会重挂载的宿主用例（小说 A→B→A，或 revision+1 以后），要求去掉 setViewport 接线后用例失败。

### 变异（12 个：抓住 9 个，存活 3 个）
- M3-noremember 存活：见 MUST-FIX 2。
- M1-placeholder（从 PLACEHOLDER 里删掉 'preview'）存活：单测只用 local/preview/preview 这一组 scope，'local' 一个就够命中。建议补一个只含 preview 的 scope 用例（P3）。
- M3-persistlocal 存活：占位符检查还在，所以这个变异与原代码等价，不算缺口。

证据：/workspace/hr/vera-compare/vw-ee350ece/（tsc/build/core/full1-3 的 log/json、analyze.py、browser.json、probe2.json、shots/、mutations.txt）。本节未提交。

## [VERA-FE] VW fix1 复核（76f868b3，2026-10-25）

**结论：PASS**。上一轮的 2 项 MUST-FIX 已经修好，测试和浏览器实测都确认了。还剩 2 个焦点行为没有测试守护，记为 P2 后续，不阻塞。

### 门禁
- tsc 0，build 0。核心测试 68 个文件，538 个用例中 537 通过。唯一失败的是 TaskCenter.additive 的回执用例，它和完整测试同时运行，处在资源争抢下；单独重跑 4/4 通过，判为偶发。视图测试 29/29 通过。
- 完整 vitest 跑三次：raw 294/293/293，ISI 都是 8，adjusted 294/293/293，总数 11460。规则 (a)（三次取最好 ≤297）PASS；规则 (b)（≤297，允许重跑一次）PASS。没有新的持续失败。唯一不在基线里的失败是 PluginResourceDetail.additive，只在第 1 次出现（和上一轮相同）。
- vw.fix1dialog、vw.m3host、vw.m2m4、viewPreferences.vw 三次全部通过。

### 变异（15 个：抓住 13 个，存活 2 个）
- 抓住：删掉 image 的 setViewport；同时删掉 image 和 video 的 setViewport；onCreativeVp 改成空操作；vpOf 不读适配器；去掉 Tab 循环；去掉 Shift+Tab 循环；去掉 document 上的 Esc；去掉卡片内的 Esc；关闭后不回触发按钮；去掉初始焦点；重命名提交后不回该行；删除确认时焦点不放到「取消」；从占位 scope 里删掉 'preview'。
- 存活（P2）：① 重命名点「取消」后不回该行的重命名按钮；② 删除确认点「取消」后不回该行的删除按钮。浏览器里这两项行为都正确，只是 fix1dialog 没有对应断言，建议各补一条。

### 浏览器（4399；拦截非 GET；1366/1440/1920 三个宽度结果一致）
- 非 GET 请求 0 次，pageerror 0 次，没有 viewprefs 键，对话框内 axe 0 违规。页面级 axe 只剩 .nv-rail 的 color-contrast（3 个节点），是已有问题。
- 对话框焦点：
  - 打开时焦点在输入框；连按 15 次 Tab 和 15 次 Shift+Tab 都留在对话框内。
  - Esc 在卡片内、在 body 上都能关闭；用 Esc 或「关闭」按钮关闭后，焦点回到「视图」按钮。
  - 重命名提交或取消后，焦点回到该行的重命名按钮。
  - 删除确认时焦点在「取消」；取消后焦点回到该行的删除按钮，视图没有被删。
  - 重命名以后 Esc 仍能关闭。
- M3：A→B→A 时 A 的平移恢复为 (-160,90)，B 为默认；切 tab 后保持；重置回默认；刷新后回到默认（只在本次会话保存）。
- M2 脏状态矩阵、M4 都和上一轮一致，通过。焦点环已是 2px inset。

证据：/workspace/hr/vera-compare/vw-fix1-76f868b3/。本节未提交。

## [VERA-FE] U1 M0+M1+M2 独立复核（U5；8996f553，契约 1cde722b，基线 a167022b，2026-10-25）

**结论：MUST-FIX（3 项）**。证据：`/workspace/hr/vera-compare/u1-8996f553/`。

- 工程：npm ci / tsc / build 均 0；workspace/workbench/rebuild/taskcenter 556/556；workspace/state 48/48；u1.identity 16/16 ×3。
- 全量三次（Node 22.14）：调整后 293/293/293（基线 persistent 298），两条规则（三取最佳 ≤297、允许一次重跑 ≤297）均通过；无新增持续失败。receipt companion 三次全部通过 → 偶发。
- 浏览器（vite 4399，拦截非 GET=0，pageerror=0；1366/1440/1920）：会话模式身份文案正确、不写任何 `poemseed.workspace*` 键（含 local::preview），重载回默认；注入真实身份后 ABA 正确（B 默认、回 A 恢复视口与停靠）；布局损坏 → 默认布局 + `::backup`、原字节保留；viewprefs 损坏字节保留；配额/存储 getter 抛错不崩溃并降级为会话。axe 仅 color-contrast:3（旧问题）。

MUST-FIX：
1. **同 key 丢失更新**：`prefs` 与 `layoutPrefs` 两个适配器在同一真实 scope 各自整体写同一 key。复现：真实身份下保存工作集「工作W1」→ 平移画布 → 存储变为 `{"viewports":{"image":{"x":-160,"y":70}},"worksets":[]}`，工作集被抹掉；冷重开后工作集列表为空（u1.json S2.docAfterPan / cold_afterInject）。
2. **会话模式无法保存工作集且文案错误**：`?uw=1` 默认（无身份）下点保存 →「项目已经切换，这次修改没有保存。」，列表为空（s1probe.log）；配额失败时同样报此错误文案但实际保留在内存（S5）。根因 `setWorksets` 在会话/写失败时返回 false，`viewActions.commit` 统一抛"项目已经切换"。
3. **冷重开视口不恢复 / 真实身份在预览中不可达**：`?uw=1` 下 App 直接返回 UnifiedWorkspacePreview，bootstrap（setCollaboration）只在 LegacyApp 中运行，actor 永远为空，真实身份路径在真实页面不可达（评审请求也承认仅 mock/jsdom）。即便注入身份，已存 viewport (-160,70) 在冷重开后仍显示默认 (40,40)（身份晚到不重新应用 initialViewport），停靠位置可恢复。

变异：租约不退役(4 失败)、占位 actor(1)、缺 instance(1)、拒绝 v0(1)、损坏不保护(1) 均被杀死；**存活**：future-version 被接受、setWorksets 去掉 isCurrent 检查 → 需补测试（P2）。

已知缺口判定：删除后同名重建/不复活依赖服务端新 id，无 incarnation、项目消失无主动清理 —— 任务书要求"删除后同名重建、不复活"，当前仅通过不同 id 单测覆盖；如服务端保证新 id 则可接受为 P2，但需在文档中明确依赖并加一条"同 id 重建"行为说明，非本轮阻断。其他 P2：resetAll 未接 UI；身份 scope 在 collabScope.projectId≠novelId 时混拼；真实模式工作集按项目而会话模式按布局。

## [VERA-FE] 集成复核（U5；575501b9 = U1+U2+U3+U4 集成，2026-10-25）

**结论：MUST-FIX（上轮 U1 的 3 项均未修复，集成新增部分本身 PASS）**。证据：`/workspace/hr/vera-compare/int-575501b9/`。

- 工程：npm ci / tsc -b / build 均 0。全量三次（Node 22.14）调整后 292/293/293（基线 298），两规则均通过；无新增持续失败；唯一偶发为 ISI 文件 IndependentStudioIdentity.regression（1/3）。TaskCenter.additive、m2s1fix、studioPreviewPanels、u1.identity、u1.purge、u3.* 三次全过。
- 上轮 MUST-FIX 浏览器复现（u1.json、s1probe.log），8996f553..575501b9 无 U1 修复提交：
  1. 共用 key 覆盖：保存工作集后平移 → `worksets:[]`，冷重开列表为空 —— 仍在。
  2. 会话模式保存工作集 →「项目已经切换，这次修改没有保存。」且列表为空；配额失败同样误报 —— 仍在。
  3. ?uw=1 无 bootstrap（actor 恒空，任务面板显示「未接通」即其直接后果）；注入身份后冷重开视口仍为默认 (40,40)，已存 (-160,70) 未应用 —— 仍在。
- GATE_INT 两个旧测试改动裁定：**规格变化，不是削弱断言**。原断言依赖伪造 `uw-preview:` 身份读取，违反任务书"不伪造身份"；新版保留"恰好一次 GET、全部 GET"并新增"请求头无 uw-preview"；无身份不读取由 u3.tasks「not-connected … no read」覆盖，浏览器实测无身份时零任务请求（仅 /api/novels 与 chapters）。capability 增加 results/history=partial 与面板实际一致。P2：`studioPreviewPanels.tsx:55` 仍残留 `uw-preview:${novelId}` 身份字符串（旧 TaskCenterPanel 路径，未挂载），建议删除。
- 集成冒烟（int.json，1366/1440/1920）：非 GET=0，pageerror=0，无横向滚动；面板 outline/creative/inspector/results/history/tasks；结果/历史显示诚实空态 int-*-empty；有身份时任务与 production jobs 均为 GET、无 uw-preview 头。axe：color-contrast（旧）+ **新增 landmark-unique:#uw-panel-tasks**（P2）。
- 清理（purge.json）：注入身份后列表移除项目 B → 仅删除本人 B 的 viewprefs/layout 键；他人键与画布草稿保留。缺口（P2）：ProjectPresence 只在本次会话内比较，项目在会话外被删除后冷开不会清理。
- 变异（mutations.log）：purge 不校验用户(1 失败)、任务读取回退为每次挂载一次(2)、身份接受空 actor(1) 均被杀死；purge 覆盖画布键 / 首个列表 / 失败读取三条为等价或无害变异。

## [VERA-FE] U5 最终整体复审 — f778eaec（2026-10-25，Asia/Shanghai）
结论：**MUST-FIX ×1**（清理回归），其余通过。证据：/workspace/hr/vera-compare/final-f778eaec/。worktree /workspace/hr/vera-final（detached，package-lock 未提交）；Node 22.14；tsc 0 / build 0。f178ff84→f778eaec 仅文档与证据。

### (1) U1 三项复验 + P2（真实 Chrome，vite :4399，页面级 route mock，非 GET 全部 abort）
- U1-1 共享键丢失更新：**已修**。pan 后存储文档保留 worksets，冷重开列表仍在（u1.json）。
- U1-2 会话保存文案/配额：**已修**。「（仅本次会话有效，关闭页面后不保留）」；配额失败「…但没能写入本机存储（可能已满）…」。
- U1-3 ?uw=1 bootstrap 真实身份 + 冷重开视口：**已修**。仅写 studio.session/scope、不注入 actor：bootstrap GET 恰好 1 次，actor=u-m5 来自服务端；uw-identity=real；冷重开 translate(-160,70)、停靠 left、工作集「冷W」恢复（fin.json，1440）。
- 任务面板：有会话时已接通（3 行，非「未接通」）；无身份时仍「未接通」且零任务请求（正确）。
- P2 三项：uw-preview 身份字符串/请求头已消失；landmark-unique 已消失；purge 文档已补。axe 剩余 color-contrast(4) + aria-required-children(1，div[aria-label="章节"]，修复前就有)。P3：报告只写了 color-contrast 是旧问题，aria-required-children 没提。
- 三个视口：非 GET 0，pageerror 0，无横向滚动。

### MUST-FIX：会话内清理回归（矩阵第 14 行）
UnifiedWorkspacePreview.tsx:134 用哨兵 projectId '\u0001' 调用 resolveWorkspaceIdentity。U1fix 新增 scope-mismatch 检查后，collabScope 带 projectId 时一律返回 session，所以 realUser 恒为 null，清理永不执行。复现（purge.json / purge2.json）：actor vera-u5，项目 B 从 /api/novels 消失并强制 refetch。B 已从下拉框移除，但本人 B 的 viewprefs/layout 键仍在；int-575501b9 这些键会被删除。变异 P1（realUser 直接返回 null）**存活**：u1.purge.test 只测纯函数，没有覆盖接线。修复建议：用不带哨兵的方式取 userId（例如直接用 actorId 加 collabScope 的 workspace），并补一个宿主级测试（项目从列表消失后断言本人键被删）。

### (2) 全量 ×3（调整数 = raw − ISI + 8，基线 298）
run1 raw 295 / ISI 10 → 293；run2 294 / 8 → 294；run3 293 / 8 → 293。规则 (a) 三次最优 293 ≤297、规则 (b) 单次 ≤297：都 **PASS**。三次都失败的条目里没有基线之外的新项。抖动项：ISI ×2、TaskCenter.receiptCompanion ×1（各只出现 1 次）。套件级失败 = src/ui/LocalAiBrowserJourneyContracts.test.tsx（ENOENT tests/e2e/v2-local-ai-files-live.spec.ts），已在基线中以 `<file load>` 计入，**不是新失败**。

### (3) 音频冒烟 + 变异
三个视口：全部/图片/音频筛选正确（3/1/1）；文本中无原始 id；「试听候选」挂载时 0 次读取，双击也只发 1 次 candidate GET；blob 播放器 paused、无 autoplay。
变异（mut.json，范围 src/workspace，357 例）：future-version 被接受 / setWorksets 去掉 isCurrent / 去掉 lease 检查 / autoplay / 挂载即读取 / 去掉 MIME 检查 / filterByMedia 写错，**全部被杀**。去掉 inflight 守卫存活：busy 时按钮 disabled 起到同样作用，属等价变异，P3。清理接线变异存活（见上面的 MUST-FIX）。

### (4) ACCEPTANCE_MATRIX 34 行
重新计数与表中一致：已验证 21 · 已实现 1 · 部分实现 5 · 受阻 3 · 未运行 4；DELIVERY_REPORT 中的数字与矩阵一致（48/48、293+1 套件级、NEW 0）。所列证据文件都存在（m5-run/m5-req ×48/shots 96/full-f178ff84.*/repro before-after）。争议行：
- **第 14 行**（清理，已验证）：引用的是我在 575501b9 的 purge.json，旧 HEAD 的证据；在 f778eaec 上已回归 → 应改为「部分实现/未通过」，修复后再验。
- **DELIVERY_REPORT 分阶段表**写「Vera PASS 575501b9」：**不对**。575501b9 的结论是 MUST-FIX（U1 三项仍在），通过的只有集成代码本身。
- 第 23 行：landmark-unique 的结论成立，但 aria-required-children 没有说明（P3）。
- 其余各行的分类与证据相符；第 15、19、22、28、29 行的「部分实现」和 20、21、30 行的「受阻」理由都成立。

## [VERA-FE] 独立复审 work/hermia-default-ui-20261025 @ 99edf71a（2026-10-25，未提交）
结论：**MUST-FIX（1 项）**，其余 P0 声明经前后对比确认成立。
- 已确认：无裸 ID（ws1/s1/b1/audio-wav-project 消失，三宽度无 uuid/hex）；普通模式无「部分实现/未接通」徽章；章节查询 undefined 根因修复（bare/slow/garbage 前 queryUndefined=true，后=false）；问助手白话卡片+重试；Cmd-K id 列改为人话提示；资产 500 单一 alert+重试；无写请求（关闭助手的 POST cancel 基线同样存在）。
- **MUST-FIX P0-3 单屏单状态未完成**：章节接口 500（或慢加载 6s）时，左栏/章节列显示「章节暂时读不到，请稍后重试。」/「正在读取章节…」，同时中间卡片显示「当前还没有打开的章节/在左侧新建或选择章节」，右侧检查器显示「未选择章节」及主按钮「在左侧选择或新建章节」（aside.workspace-inspector .nv-assist__next .nv-btn--primary）。错误/加载与空态 CTA 并存。位置：App.tsx 小说空卡片、检查器 nv-assist 下一步。证据 shots/probe_500.png、probe_slow.png。
- P2：折叠「更多」内 div.novel-error 含原始文本「无法加载章节：Error: {"detail":"boom"}」；章节按钮 button.nv-chapters__ch 带 aria-selected（axe aria-allowed-attr critical，因章节现在能加载而暴露，非新写代码）；问助手按钮字体与正文不一致。
- 测试缺口（变异存活）：Cmd-K 恢复 id 列、失败时仍显示新建章节、rail 徽章不分模式、App 层 simple 接线、写作台/版本徽章门控 —— 均无测试捕获。被捕获：chapterList→items、scopeLabel 回退 id、资产错误态、Cmd-K 专业项隐藏。
- PortableProjectsPanel.assetRelations：单独 3/3 通过 9/9，本分支未改 src/experimental，判偶发成立。
- 证据：/workspace/hr/vera-compare/dui-99edf71a/

## [VERA-FE] 独立复审 work/hermia-i18n-20261025 @ 391f47d8（2026-10-25，未提交）
结论：**MUST-FIX（1 项，布局）**，功能面通过。
- 通过：默认中文（无 studio.locale 时 html lang=zh-CN，壳层中文文本与切回后逐字一致）；切 EN 即时生效无刷新，localStorage studio.locale=en，刷新后保持，html lang=en；非法值 fr 回退 zh-CN；无裸 key；1366 隐藏搜索文案/设置文字无溢出；无写请求；axe 中英一致无新增。
- 变异全部被捕获：回退返回裸 key、不设 html lang、不持久化、默认改 en。
- **MUST-FIX 布局重叠**：EN 下 1440 与 1920，头部搜索框文案「Search features, chapters, commands」被截断并压在「Ctrl K」徽标下方（文字与 kbd 重叠）。复现：4499 起本分支→跳过引导→点 EN→看头部搜索框。位置：src/i18n/i18n-en.css `.global-search>span` 省略号未给 kbd 让位（AppShell.tsx:746），或缩短 en.ts:42 文案。证据 shots/en_1440.png、crop_search_1440.png。
- 说明（非阻塞）：仅壳层翻译，正文/助手/引导仍中文，属声明范围内。
- 证据：/workspace/hr/vera-compare/i18n-391f47d8/

## [VERA-FE] 独立复审 work/hermia-default-ui-i18n-20261025 @ 625114c9（2026-10-25，未提交）
结论：**MUST-FIX（3 项）**。全量三次 raw 295/293/293，校正 293/293/293，新增持久 0，两条门规均通过；tsc/build 0；定向 71/71。merge 两边改动均保留（DUI 的普通模式隐藏专业项、chapterList、scopeLabel 变异与 i18n 的裸 key 回退、html lang 变异均被捕获）。
1. **a11y 回归（本提交引入）**：global-search 去掉 aria-label 后，EN 且宽度 <1440 时 i18n-en.css 隐藏 span，按钮可访问名只剩「Ctrl K」。AppShell.test 选择器从 `[aria-label="搜索功能、章节或命令 Ctrl K"]` 放宽为 `button.global-search`，断言丢失「名称=可见文本」约束；变异「删除可见文本 span」存活，「en overflow.aria.pro 改回旧文案」也存活。建议：用 getByRole('button',{name:...}) 断言名称，并在窄屏 EN 时保留 aria-label 或用 visually-hidden 文本。位置：AppShell.tsx:775-783、AppShell.test.tsx:~393、i18n-en.css。
2. **P0-3 单屏单状态仍未修复**（中/EN 均复现）：章节 500/慢加载时，左栏报错/加载中，同时中间显示空态、右侧主按钮「在左侧选择或新建章节 / Select or create a chapter on the left」。证据 shots/zh_1440_500.png、en_1440_500.png。
3. **EN 头部搜索文案压在 Ctrl K 上**（1440/1920，沿自 i18n）：shots/en_1440_bare.png。
- P2：EN 下仍有「已保存/保存/当前正在写」等未译 UI 文本；axe 中/EN 1440 仅 heading-order、landmark-unique（moderate）。
- 证据：/workspace/hr/vera-compare/duim-625114c9/

## [VERA-FE] 复审 c37ef1b0（2026-10-25 14:45 北京时间）— 结论：MUST-FIX（1 项）
证据：/workspace/hr/vera-compare/duim-fix-c37ef1b0/
- tsc 0；build 0；定向 10 文件 92 测试全过。
- 全量 ×3（低负载、串行错开，load 4–5）：adjusted 293 / 296 / 294，两条口径（三取优 ≤297；≤297 允许重试一次）均通过。仅 ISI 为已知抖动；LocalAiBrowserJourneyContracts ENOENT 属基线。
- 浏览器（4499，zh/EN × 1366/1440/1920 × 普通/专业，章节 bare/500/slow；非 GET 请求数 0）：
  - 上轮 MUST-FIX①：500 与 slow 在普通和专业模式下，中区都只呈现一个 data-desk-state（error 或 loading），无“继续写”/下一步/新建，也没有混合状态。✅
  - 上轮②：EN 全部宽度无遮挡。但 **zh 专业模式 1366 下 span 与 Ctrl K 重叠**（截图显示“搜索功能、章节或命令K”），这是新的 MUST-FIX：修复只覆盖了 i18n-en.css，zh 窄屏 + 专业模式（专业更多 等项更宽）没有处理。
  - 上轮③：窄屏 EN 的可访问名为完整的 "Search chapters, commands Ctrl K"。✅
  - axe：只有 heading-order 和 landmark-unique（moderate，与之前相同）。
- 变异 21 个：17 个被捕获。存活 4 个：
  - B6（中区原始错误）和 C1/C2（Cmd-K id 列在普通模式显示）：没有单测守护，浏览器验证目前正确，记为 P2 测试缺口；
  - E1/E2（CSS）：jsdom 无法覆盖，由浏览器覆盖。
- 裁定（1）SourcePrivacyControl 在「更多」中露出 {"detail":"nf"}：**P2，不阻断本合并**，但要另立跨模块任务。
  - 理由：它只出现在折叠的「更多」里，不在默认视图；问题也不是本分支引入的。
  - 根因是共享的 apiErrorView（src/api.ts:85）：detail 为字符串时会回落到原始 body，61 个非测试文件都受影响。
  - 建议在 apiErrorView 层统一改为白名单/i18n 文案，原文只放进专业模式的技术详情。
- 裁定（2）EN 1440 专业模式搜索框省略号：没有重叠，可访问名完整，**但没有 title/tooltip**，不满足接受条件；给 button.global-search 加上 title 等于完整文案后即可接受（P2，可与 MUST-FIX 同批）。

## [VERA-FE] 复审 53bd9f1e（2026-10-25 15:50 北京时间）— 结论：PASS（附 2 项既有 P1 跟进）
证据：/workspace/hr/vera-compare/duim-fix2-53bd9f1e/
- tsc 0；build 0。
- 全量 ×3：串行执行，开跑时 load 0.6–4.9。adjusted 为 293 / 294 / 293，两条口径都通过（ISI 每轮 8，ENOENT 属基线）。
- 浏览器（4499，共 40 格，非 GET 请求数 0）：
  - zh/en × 普通/专业 × 1366/1440/1920 的 12 格：span 与 kbd 的矩形全部不相交，kbd 都在按钮内；title 为完整文案；可访问名完整。上轮 zh 专业 1366 的重叠已修复（shots/cmp_pro_zh_1366.png）。
  - DPR 1.25/1.5 抽测（1366/1440）：均无相交。
  - 1280 抽测：同样无相交。
- 头部其它布局：与 c37ef1b0 截图逐像素对比，差异只在搜索框内部，EN 头部像素完全相同。所有格都没有页面横向滚动。
- 一屏一态（1440 下 500/slow，普通与专业）：只有一个 data-desk-state，无下一步/主按钮。✅
- 1366/1440 窄屏可访问名没有回归。✅
- axe：只有 heading-order 和 landmark-unique（moderate，与之前相同）。
- 变异 B6、B6b、C1、C2、T1（去掉 title）、T2（title 改为截断文案）：6/6 全部被捕获。
- 既有问题（非本次引入，像素对比已证实，建议另开 P1）：
  1. ≤1360px 时 protoShell.css 对所有语言的 span 使用 display:none，导致 1280 下可访问名只有 "Ctrl K"。title 不参与可访问名计算，应改为视觉隐藏（clip）。
  2. 专业模式在 zh 1366 / EN 1366、1440 / 1280 下，头部超出视口，"设置"按钮被裁切或完全不可见（header 有 overflow，但页面没有横向滚动）。

## [VERA-FE] 复审 work/hermia-fe-contracts-20261025 @ fa2fa0f4（基于 02bbff08 + 8877b216）— 结论：MUST-FIX

环境：临时 worktree /workspace/hr/vera-fec（变异/浏览器在 /workspace/hr/vera-fec-mut），Node 22.14，npm ci（lock 未跟踪），vite 4599 独立缓存，Playwright 拦截全部非 GET。证据：/workspace/hr/vera-compare/fec-fa2fa0f4/。

- tsc 0，build 0；相关 34 文件 290/290。
- 全量三次：raw 293/293/294，ISI 8/8/8，调整 293/293/294（≤297）；规则 (a)(b) 均通过。按名新增仅 run3 的 PortableProjectsPanel.assetRelations 1 项，单独重跑 3/3 通过，判偶发。
- u1.purge.host「host purges own keys…」归因：与 incarnation 改动无关。fa2fa0f4 未改 projectPurge.ts 和该测试（两者的改动都来自 8877b216）；该测试里 overview 返回 404，不会 setIncarnation，realKey 不变。在 8877b216 与 fa2fa0f4 上单跑各 10/10 通过，各 4 路并行 ×3 轮（12 次）也全部通过；本人全量三次中 0/3 失败。Hermia 日志里的失败是最后那个 waitFor（默认 1s）超时，属于负载下的时序偶发，来自 8877b216 的测试。
- 契约核对（对照 origin/work/hermia-backend-contracts-20261025）：TaskCenter 分页的 7 个键、coverage、next_offset、truncated=source_truncated||has_more 与 ux.py 一致；Production 的 owner/operation_id 白名单、limit 1–100、offset ≤1e6、has_more 语义等价；overview 的 project.incarnation 形状一致；Timeline history/restore 的四个字段一致。
- **MUST-FIX 1（行为）**：incarnation 变化后，旧项目的 viewport 会被写回。原因是 realKey 带上 incarnation 后会触发重挂载，重挂载把内存里的旧 viewport 写回了刚清理过的 viewprefs。jsdom 探针 3/3 复现（viewprefs(own) 里仍有 x:7）。浏览器在 1366/1440/1920 下也复现：A 下平移到 (-160,70)，切到 B 后重载，ledger 已更新为 B，但画布仍是 translate(-160,70)，viewprefs 里还是旧值。去掉 realKey 中的 incarnation 后探针变成 null，说明问题就出在这次改动。u1.incarnation.host 只断言了 layout，没有断言 viewprefs，所以没发现。修复后请补上 viewprefs(own) 为 null 或为默认值的断言。
- **MUST-FIX 2（测试守护）**：以下变异存活：M1 去掉 truncated 等式；M3 去掉 next_offset 算术（taskCenterPaging 的测试其实声称覆盖了这一点）；M5 任意 422 都回退；M7 去掉 production 的 has_more 校验；M8 部分分页键被当成未分页；M12 realKey 不带 incarnation；M14 无身份也读 overview（代码本身正确，我的探针已验证不会发请求，但没有测试守护）。被杀死的有：M2/M4/M6/M9/M10/M11/M13/M15。首轮 M7/M14 的“杀死”其实来自 receiptCompanion 偶发，定向重跑后确认存活。
- P3：后端允许 offset 超过 observed_total（返回空页），前端的 `offset + count > observed` 会把这种情况判为无效。列表在两次加载更多之间缩短时，加载更多会报错，但已显示的行会保留。
- 浏览器：三个视口下都是 0 个非 GET、0 个 pageerror；默认界面正常加载。

## [VERA-FE] fe-contracts fix1 复审（839434a4）— 结论：PASS

证据：/workspace/hr/vera-compare/fec-fix1-839434a4/（tsc.log、build.log、mutations.log、inc2.json/inc2.mjs、shots/、probe.log、u1-purge.log、full1-3、analyze.log）

- 构建：tsc=0，build=0。
- 浏览器复现（端口 4599，mock 仅 GET，非 GET=0，pageerror=0），1366/1440/1920 三个宽度结果一致：
  - 在 A 下平移后冷重开（同一 incarnation）：视角恢复为 translate(-160,70)，工作集仍在。
  - 换到 B 后重载：视角为默认 translate(40,40)，本人的 viewprefs 被重置，worksets=[]。worksets 清空属于设计内的本人清理。
  - 他人的 viewprefs（x:7 和工作集）完好。
  - 上轮的 MUST-FIX 已关闭。jsdom 探针 2/2 通过（上轮为失败）。
- 旧键与孤儿键：fix1 只改了内存 adapter 键 `k`（新增 `\0${incarnation}`）。localStorage 键形状 viewPrefsKey、workspaceLayoutKey、incarnationLedgerKey 都没变，所以不会产生孤儿键，也不需要迁移。overview 加载前后 k 会切换一次，但已存数据会从 storage 重新读取，不会丢（冷重开时工作集保留已验证）。
- 变异：我重跑了 M1–M20（M1–M18 加补充的 M7b、M19、M20），并按测试名确认，排除了 receiptCompanion 抖动。
  - 被杀 19 个：M1–M13、M15–M20。其中 M16（adapter 键去掉 incarnation）、M20（不传 incarnation）、M12 由 u1.incarnation.host 杀死；M17、M18（TC P3 两个方向）、M19（生产 P3）由 paging 测试杀死。
  - 存活 2 个，均不阻断：
    - M14（overview 读取去掉 realUser 守卫）：在无身份时 taskCtx 也为空，这个测试场景下属于等价变异，新测试并没有真正区分出 realUser 守卫。建议补一个“有 token、但非 real 身份”的用例。
    - M7b（has_more 改用 offset+items.length）：只在服务端返回不一致的短页时才有区别。可选补一条用例。
- P3：TC 和生产两侧，offset ≥ total 时空页合法，非空页拒绝；UI 在列表收缩时保留已显示的行，不报错。
- U1/purge 回归：u1*/purge* 共 8 个文件、43 个测试，连跑 3 次全部通过。
- 全量 3 次（Node 22.14）：raw 293/292/293，ISI 8，adjusted 293/292/293，按名称计新增持久失败 0。阈值 297，规则 (a) 和 (b) 都通过。

## Vera 复审 @ 097ce4b3（2026-10-25，未提交）

**结论：MUST-FIX（2 项），其余 PASS。** 证据：/workspace/hr/vera-compare/duim-097ce4b3/

### 全量 ×3（Node 22.14，起跑 load 1.06）
- run1/2/3 raw 293/294/295，ISI 6/6/6 → adjusted **295/296/297**；两种规则都 ≤297，**PASS**。
- 和 53bd9f1e 三轮失败的并集对比，新增的只有单轮出现的创作区时序 flaky：run2 有 1 条（ISI.regression），run3 有 2 条（ComicTimelineHandoff / TimelineSelectionDuplicate），每轮不重复，跟本次改动无关。

### MUST-FIX-1：真实后端信封仍会把原文泄露到普通模式
- 原因：后端 app/main.py:99 的 unified_http_error 遇到字符串 detail 时，会把同一段文本复制进 `message`，同时带上 `code:"HTTP_<n>"`。structuredMessage 会把 `raw.message` 当成结构化文案。
- 浏览器内对 `/src/api.ts` 实测，普通（basic）模式下：
  - `{"detail":"Not found: /home/u/SECRET-T4.key","code":"HTTP_404","message":<同上>}` → 界面显示 `Not found: /home/u/SECRET-T4.key`；
  - 500 的 `KeyError(...) at /srv/app/api.py:547` 也原样显示；
  - 同时 message_source=server，所以专业模式下也拿不到 technical。
- 白名单只对 mock 形态生效（无 message 字段的 text/plain、`{"detail":"nf"}`、422 数组、html），这些都已正确显示友好文案。
- 后端约有 67 处 `HTTPException(4xx, f"...{exc}")`。
- 建议修法：`typeof raw.detail==='string' && raw.message===raw.detail`（或 code 匹配 `/^HTTP_\d+$/`）时按 fallback 处理；可另加 UNSAFE 内容过滤（路径、Traceback、Error(）。补一条真实信封的测试。

### MUST-FIX-2：1100 宽度头部仍然溢出
- 1100×800：zh 下「打开设置」right=1113>1100；en 下「EN」被挤出视口。四种组合（zh/en × 普通/专业）头部都有 scrollWidth>clientWidth。
- 页面本身没有横向滚动，但按钮被裁切，Tab 聚焦到的按钮落在视口外。
- Hermia 的证据矩阵没有 1100 这一档。1280/1366/1440/1920 以及 DPR 1.25/1.5 全部通过。

### 头部（其余）PASS
- span/kbd 不相交；clip 档 span 是 position:absolute 1px（不是 display:none）。
- 可访问名称完整，例如 `搜索功能、章节或命令 Ctrl K`、`Search chapters, commands Ctrl K`。
- 专业模式「更多」可用 Tab 到达，Enter 能打开（4 项），方向键可移动；普通模式没有折叠项。
- axe 只有 heading-order、landmark-unique（moderate），与之前一致。

### apiErrorView 调用方（65 个非测试文件）
- 依赖统计：message 61、status 44、code 21、technical 6、details 4。
- 没有调用方对 message 做内容匹配；status/code/details 都没变，没有调用方丢失必要信息。409 冲突（promptClient、App.tsx:2683 actual_version）和重试逻辑不受影响。
- 注意：rebuildApi/useModelCenter 只采用含 CJK 的 message，所以 en 下会退回中文通用句（已有问题）。AssetsRebuild 在 en 下的错误文案也是硬编码中文（已有问题，P3）。
- P2：technical 只在 3 个面板（AssetLibrary/Export/NovelImport）渲染，其余调用方在专业模式下也看不到技术详情。

### contracts.test「500 text/plain」
- 期望从 `服务暂时不可用` 改为友好文案，并新增断言 message_source=fallback、raw_text=原文。这是收紧，不是放宽；W1/W3/W6 都能杀死。

### fe-contracts 合并
- taskcenter 相对 3e72db70 只把字面量换成 i18nT('fc.*')，逻辑不变。
- zh/en 各 40 个 fc./err. 键，没有缺失，代码用到的 19 个 fc 键在 en 中都存在；taskcenter 测试全绿，F1 变异被杀。

### 变异（基线 267/267 通过）
- 被杀 11/13：W1–W6、W9、H1–H3、F1。
- 存活两项：
  - W7（raw_text 不截断）：缺少截断测试，P3；
  - W8（AssetLibrary 不渲染 technical）：P2，建议补渲染断言。

---

## [VERA-FE] 复审 work/hermia-default-ui-i18n-20261025 @ f703b17e（efe629f0 MF1 / 911cbf71 MF2 / f703b17e P3）

- 方法：临时 worktree /workspace/hr/vera-duim2（detached f703b17e），自起 vite 4499（结束已按 PID 停），Chrome/Playwright 真实注入；变异在 /tmp/vera-duimf70-mut（已删）。未写 8000、未碰 4299。
- 时间：2026-10-25 17:20–17:55（Asia/Shanghai）
- 证据：/workspace/hr/vera-compare/duim-f703b17e/（inject.json、regex-bypass.txt、header-matrix.json、axe.json、mutations.log、full{1,2,3}.json、gate.py）

### 结论：**MUST-FIX**

MF2（头部）已修好；MF1 只修了 `call()` 一条路，**下载类接口 `downloadCall()` 仍把服务端原文直接当 message**，普通模式可见 Traceback/路径；另外过滤规则对相对路径、SQL、Errno 等可绕过。

### MUST-FIX
**MF-1 `downloadCall()` 完全绕过 MF1（P0）**
- 位置：frontend/src/api.ts:150 起 `downloadCall`，`message: raw?.message ?? detail?.message ?? detail?.detail ?? (body || ...)`，没有走 structuredMessage / message_source / raw_text。
- 影响：api.exportDownload / assetDownload / agentJobsExport / agentJobAuditExport / downloadAudiobookChapter / audiobookSubtitles。其中 ExportPanel 的下载失败用 `ExportError → apiErrorView` 展示，AssetLibraryPanel/AssetInspector 下载失败同理。
- 复现（浏览器注入，普通模式，apiErrorView 输出）：500 text/plain `Traceback SECRET-N /home/u/.env` 原样显示；`<html>nginx…</html>` 原样显示；真实信封 `{"detail":"Traceback… File \"/srv/app/api.py\"…","code":"HTTP_500",…}` 原样显示。共 15 种注入全部泄露（inject.json → download.basic_*）。
- 建议：downloadCall 的错误构造复用 call() 的同一段（structuredMessage + friendlyHttpMessage + message_source + rawTextOf），并补一条“下载 500 text/plain 普通模式不显示原文”的测试。

**MF-2 “安全”判定是黑名单，真实后端的 str(exc) 可绕过（P1）**
- 位置：api.ts `UNSAFE_SERVER_TEXT`。带业务 code 的 dict detail 本来就走结构化 message，后端有大量 `{"code":…, "message": str(exc)}`（如 INVALID_PROVIDER_CONFIG api.py:1139、ASSET_INTEGRITY_FAILED asset_lifecycle_api.py:36、IMAGE_EDIT_INVALID api.py:2500、INVALID_WORKER_CONFIG api.py:2965、EXPERIMENTAL_INVALID experimental/common.py:63 等）。
- 普通模式实测仍显示（call 路径）：`[Errno 2] No such file or directory: 'config/providers/x.toml'`、`UNIQUE constraint failed: assets.sha256`、`./data/novels/x.json`、`/data/poemseed/x.db`（/data 不在前缀表）、UNC `\\server\share`、3000 字长文本（message 不截断）、`invalid literal for int() with base 10`。能拦住：Windows 盘符、/home 等前缀、XxxError 名、Traceback、0x 地址、html。
- 建议（任选其一）：普通模式只对“已知业务 code 白名单”或 CJK 文案原样展示，其余走友好文案并把原文放 technical；或至少补：任意 `[\\/]` 分隔的路径段 / 带扩展名的文件名、`Errno`、`constraint`、`SELECT|INSERT|UPDATE … FROM|INTO`、`invalid literal`、`~/`、UNC，并对 message 设长度上限（如 200 字，超出转 technical）。

### 偏离裁定（code=HTTP_n + dict detail + message 安全时保留 message）
- **有条件接受。** 后端 unified_http_error 对无 code 的 dict detail 会生成 `HTTP_<n>`，message 取 `detail.message || detail.detail`。全仓扫描 app/：目前**没有**无 code 的 dict detail 抛出点，所以这一分支当前不会被真实后端触发，保留 message 不会误丢也不会多泄露。
- 但有一个漏洞：若将来出现 `{"detail": str(exc)}`（无 code），message 就是 str(exc) 回显，实测 `invalid literal for int()…` 在普通模式原样显示。要求：当 `raw.message === d.detail`（即 dict 内 detail 字段回显）时与字符串 detail 同样处理，只保留显式的 `d.message`。安全判定本身的问题见 MF-2。

### 已验证通过
- call() 路径：字符串 detail 回显（HTTP_n）、500 text/plain、html 502 在普通模式均为友好文案；专业模式 technical 可见（截断 500）；正常业务文案未误丢：VERSION_CONFLICT 409（含 expected/actual_version）、无 code dict 安全文案 409、REVISION_LOCKED 409 全部保留（inject.json summary.lost=[]）。409 调用方（assetBrowserClient、LocalTutorIntegration、useTaskCenter 等）只读 code/details/已净化的 problem.message，行为不变。
- 头部矩阵：zh/en × 普通/专业 × 1024/1100/1180/1280/1366/1440/1920 × DPR 1/1.25/1.5 共 84 格：scrollWidth=innerWidth、头部 scrollWidth≤clientWidth、无交互项出视口、无祖先裁切、无子块重叠、无无名按钮、Tab 焦点全在视口内（header-matrix.json，84/84 ok）。检测器自检：1024 en 专业注入加宽样式后 hsw 1360、7 个按钮出视口，能报出。
- 搜索按钮可访问名在所有格均含完整文字（“搜索功能、章节或命令Ctrl K” / “Search chapters, commandsCtrl K”），之前 ≤1360 只剩 “Ctrl K” 的 P1 已消失。
- P3：rbError 英文界面不再混中文（变异 P3a/P3b 被杀）。contracts.test.ts 未改动，“500 text/plain” 断言未放松。

### 变异（mutations.log，20 个）
- 被杀：W7 不截断、W8a/b/c 三个面板不渲染 technical、N1 pick 不过滤、N8、H4 ≤1180、H5 ≤1060、H7 搜索收图标、P3a、P3b。W7/W8 上轮存活，本轮已补上。
- 存活（P2 测试缺口）：N2 去 Traceback、N3 去 Windows 盘符、N4 去异常名、N5 去 /home 等前缀（每条规则单独删掉都没测试失败）；N6 去“字符串 detail 回显丢弃”与 N7 互为冗余，单删各自存活；N9 rawTextOfObj 不取 message；H6 ≤1180 kbd 不隐藏。建议每条过滤规则各一条用例，N6/N7 各一条独立用例。

### axe
- zh/en × 普通/专业 × 1366：heading-order(moderate)、landmark-unique(moderate)，与之前一致，无 serious/critical 新增。
- 1024：`aria-hidden-focus`(serious) 1 处 —— `#workspace-inspector` 带 aria-hidden=true 但内含可聚焦元素。本轮提交只改头部 CSS，不是本轮引入，记 P2，建议单独任务处理（隐藏时加 inert）。

### gate（adjusted = raw − ISI + 8；基线 297）
| 运行 | raw | ISI | adjusted | 基线外非 ISI 失败 |
|---|---|---|---|---|
| full1 | 293 | 8 | 293 | 0 |
| full2 | 295 | 10 | 293 | 0 |
| full3 | 294 | 8 | 294 | 1（StudioTimelineBasicColor.additive “preserves applied color and blocks duplicate saves after CONFLICT”，full1/full2 均通过，判为偶发 flaky，P2 观察项） |
| Hermia task8-full.json | 295 | 10 | 293 | 0 |
- (a) 三次最优 ≤297：通过（293）；(b) 允许一次重跑 ≤297：通过（首跑即 293）。LocalAiBrowserJourneyContracts ENOENT 在基线内。Hermia 的 task8 数据复核一致（295 raw，ISI 10，按名字比对基线外非 ISI 为 0）。

### 其他
- 5472 端口 pid 3521797：`node …/wt-dui/frontend/node_modules/.bin/vite --host 127.0.0.1 --port 5472 --strictPort`，cwd /workspace/hr/wt-dui/frontend，14:58:40 启动，父进程是 pid 53（sand-exit-watch 守护，即原父 shell 已退出被收养）。环境变量 CURSOR_CONVERSATION_ID=sand-subagent-ef853e69-…，是某个子任务启动的；npm 版 node 22.14。Vera 的复审从不使用 5472 端口、也不在 wt-dui 起 vite，按端口约定判断不是 Vera 的复审进程，更像 Hermia 侧（wt-dui 是她的工作树）的子任务遗留。未杀。
- 未提交；未提交 frontend/package-lock.json；未碰 main。

---

## [VERA-FE] 独立复核 @ 620963bf（work/hermia-default-ui-i18n-20261025，复核 8b8779ac + 620963bf）

结论：**MUST-FIX**（1 项 P1：真实后端 str(exc) 仍在普通模式直出）。inert / H6 / 门禁 / 变异覆盖均 PASS。
证据目录：`/workspace/hr/vera-compare/duim-620963bf/`

### 1. 真实浏览器下载失败（ExportPanel / AssetLibrary / AssetInspector，普通 + 专业）
- 方法：Playwright + mockBackend，route 注入；上轮 15 种注入 + 按 `app/main.py:99 unified_http_error` 复刻的真实信封（`{detail,code,message,details,request_id}`）。默认 UI 资产模块是 AssetsRebuild（无下载按钮），AssetLibraryPanel / AssetInspector 不可达，故经 vite deps 在 live 页内挂载真实组件（见 dl-lib.mjs）。结果：download-ui.json、download-ui-lib.json、shots/。
- 上轮 15 种注入 + forbidDetail：ExportPanel、AssetLibrary 普通模式全部只显友好文案 ✅；专业模式 technical 可见且 ≤500 ✅；合法文案保留 ✅。
- **P1 泄露**：`INVALID_ASSET_REQUEST`（asset_lifecycle_api:42，ValueError/TypeError → str(exc)）与 `INVALID_CAPABILITY_REQUEST`（api.py:603，KeyError → `'SECRET-R'`）普通模式直出原文，如 `unsupported operand type(s) for +: 'int' and 'SECRET-Q'`。
- AssetInspector：始终固定文案「资产下载失败…」，专业模式也无 technical（P2，无泄露，默认 UI 不可达）。

### 2. 设计裁定：枚举规则 + 200 字上限 **不成立**
- app/ 扫描：带 str(exc) 且不在 RAW_MESSAGE_CODES 的 code：WORKBENCH_INVALID、PLANNING_INVALID、INVALID_ASSET_REQUEST、ASSET_IDEMPOTENCY_CONFLICT、INVALID_CAPABILITY_REQUEST、CREATION_RECORD_NOT_AVAILABLE（含 FileNotFoundError）、IMPORT_AI_REVIEW_INVALID、SOURCE_PRIVACY_REVIEW_REQUIRED、EXPERIMENTAL_SOURCE_STALE，以及动态 exc.code（AudiobookError voice_direction_api:42、DocumentProjectionError api.py:549/1265）。`{code, detail:str(exc)}` 形式（FORBIDDEN、AGENT_JOB_*）由 echo 规则拦住 ✅。
- 短绕过（<200 字，bypass-probe.txt）普通模式**全部可见**：KeyError `'title'`、TypeError 文案、`__init__() got an unexpected keyword argument`、`too many values to unpack`、`data/x`、`uploads/abc`、`'secrets.toml'`、`no such table/column`、`database is locked`、pg foreign key、`10.0.3.7:5432`、`http://127.0.0.1:11434`、`OPENAI_API_KEY=sk-…`、`$HOME`、`"novel_42.sqlite"`、`/etc missing`、`/secret.db`、`..\..\secret.db`、`math domain error`、带 token 的 dict repr。仅 json `line 1 column` 被拦。
- 误杀：`比例需在 1/2.5 之间`、`Terror theme…`、`请选择 JSON/YAML.zip 文件`、`Each line 2…` 被当原文丢弃（P2）。
- VERSION_CONFLICT / PLANNING_VERSION_CONFLICT / 普通英文文案保留 ✅。另：后端 VERSION_CONFLICT 不带 message（只有 current），本就走友好文案，"纯白名单会误杀 VERSION_CONFLICT" 的论据不成立。
- 要求（二选一）：(a) 把上述全部 str(exc) code 纳入 RAW_MESSAGE_CODES，并加契约测试扫描 app/ 中 `str(exc)`/`detail=str(` 的 code 断言全部在集合中；(b) 反转为白名单：仅已知携带字面文案的 code 显示 server message。同时修复上述误杀。

### 3. 变异（mutations.log，13 个测试文件 240 用例）
- 全部 CAUGHT：W7（两处截断）、W8a/b/c、N1–N9、R1–R8（逐条删规则 + relPath 分支）、L1/L2/L3（长度上限去除、+1、2000）、C1/C3、E1、D1（downloadCall 回退）、D2（call 不净化）、I1（去 inert）、I2（inert 恒加）、H6。
- SURVIVED（P3）：C2（只认顶层 code，忽略 detail.code）、E2（echo 条件去掉 `dict.message!==raw.message`）。
- apiErrorSanitizer.test.ts：27 处 expect 经 it.each 展开为 120 用例，变异证实确有断言力 ✅。

### 4. axe / inert（axe-inert.json，1024×768 与 1366×900，普通/专业）
- aria-hidden-focus 消失 ✅；剩余仅 heading-order / landmark-unique（moderate，既有）。
- inert 只在隐藏时存在（aria-hidden=true ⇔ inert=true）；可见时 inert=false、可聚焦、Tab 能进入（27/33 次）；隐藏时 Tab 0 次进入 ✅。来回切换状态正确；React 18.3.1 渲染 `inert=""` 有效且无 warning。
- 头部抽查：无横向滚动、无 kbd 重叠；1024 的 ov 项为 sr-only 裁剪元素，符合预期。

### 5. 全量门禁（Node 22.14，adjusted = raw − ISI + 8，基线 298 / adj 297）
- run1：raw 295，ISI 10，adj 293；新增非 ISI 失败 0
- run2：raw 293，ISI 8，adj 293；新增 0
- run3：raw 294，ISI 8，adj 294；新增 1，为 TaskCenter receiptCompanion（已知 flaky）
- (a) 三次取最好 293 ≤ 297 **PASS**；(b) 允许重跑 1 次，run1 即 293 ≤ 297 **PASS**
- task9-full.json：raw 293，ISI 8，adj 293，新增非 ISI 失败 0。
- LocalAiBrowserJourneyContracts ENOENT 为基线既有。

### 6. 其他
- 5472 无监听 ✅。未触碰 4299 / 8000；vite 仅用 4499，已按 PID 关闭；临时变异 worktree 已移除。

## [VERA-FE] 独立复审 @ e471dc76（work/hermia-default-ui-i18n-20261025，复审上轮 620963bf MUST-FIX）

**结论：PASS**（无 P0/P1；下列 P2/P3 建议后续跟进，不阻塞）。证据：`/workspace/hr/vera-compare/duim-e471dc76/`。

### 1. 白名单安全性（LITERAL_MESSAGE_CODES，50 个）
- 独立扫描 app/ 每个 code 全部出处（wl.txt、wl-occurrences.txt），含跨行 EXPORT_*、PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED、REALTIME_VERSION_OR_SOURCE_CONFLICT、WORKFLOW_* 多行构造：所有 HTTPException 出处 message 均为字面量 ✅。
- 间接路径：CANON_RECOVERY_REQUIRED 经 FindingReviewConflict 产出 `{code,current}`，message 回落为 code，前端跳过；IMAGE_EDIT_PROVIDER_UNSUPPORTED 的 ValueError 在内部重映射为 IMAGE_PROVIDER_REQUEST_FAILED；SPEECH_PROVIDER_UNAVAILABLE / SPEECH_SYNTHESIS_FAILED 以 AudiobookError 抛出，构造参数是字面量，因此 api.py / voice_direction_api.py 中通用的 `{'code':exc.code,'message':str(exc)}` 处理器当前输出也是字面量。其余动态 `exc.code` 发射点不含白名单 code。白名单与 RAW_MESSAGE_CODES 交集为空。**当前名单安全。**
- 契约扫描健壮性：在临时 worktree 中做后端变异，结果见 backend-contract-mutations*.log。
  - 能抓住：同行 str(exc)、msg 变量、跨行 f-string、.format、%、函数构造、repr、删除唯一出处、K1、K4。
  - 漏网：
    - B7：字面量后换行再 `+ str(exc)`；
    - B8：隐式拼接 `("x"\n f"{exc}")`；
    - B12：`AudiobookError("SPEECH_SYNTHESIS_FAILED", 变量)` 经通用 str(exc) 处理器流出；
    - K2/K3：双出处 code 中有一处 message 写在 code 前，或用 `dict(code=,message=)` 跨行。
  - B9/B10 能抓住，只是因为 PLANNING_VERSION_CONFLICT 恰好只有一个出处。B13（新增 str(exc) code 但不进名单）按设计会回落为友好文案，安全。
  - **P2-1**：regex+500 字符窗口的护栏较脆，尤其对动态 exc.code 路径（B12）无感知。建议改为 Python ast 扫描：解析 HTTPException/JSONResponse 的 dict，以及自定义异常类构造与 str(exc) 处理器的映射。
- **P3-1**：部分白名单文案是英文（如 "export cancelled"、"expected_version must be a non-negative integer"），会原样展示给中文用户。

### 2. 浏览器注入（vite 4399，Playwright + mockBackend）
- 覆盖 call() 路径（页内 import /src/api.ts，调用 api.adminWorkspaces + apiErrorView）、ExportPanel、AssetLibraryPanel、AssetInspector（后两者默认 UI 不可达，按上轮方式在 live 页内挂载真实组件），普通 + 专业两种模式。共 81 例/模式：
  - 上轮 15 例异常，另加：403 detail、白名单 code 带路径、detail.code-only、HTTP_n+detail.code；
  - 22 条短绕过 × {INVALID_ASSET_REQUEST, 无 code}；
  - 9 个指定 code 加 AUDIOBOOK_*/DOCUMENT_PROJECTION_* 动态 code 和 HTTP_400；
  - 4 条合法文案 + PLANNING_VERSION_CONFLICT 文案（顶层 + detail.code 两种形态）+ VERSION_CONFLICT 无 message。
- 结果（browser-inject.json、browser-inject2.json、shots/）：
  - 4 个面板 × 普通模式：75 ok + 6 legit-ok，**0 泄露** ✅。
  - 专业模式：74 例 technical 可见，6 例 legit-ok，VERSION_CONFLICT 显示友好文案；technical 段最长 500（截断生效）✅。
  - 「比例需在 1/2.5 之间」「Terror theme…」「请选择 JSON/YAML.zip 文件」「Each line 2…」原样显示 ✅。
- 上轮 P2（AssetInspector 专业模式无 technical）已修复：现为「资产下载失败…｜技术详情：<原文≤500>」，白名单 server 文案原样显示 ✅。

### 3. 测试断言改动与 E2 裁定
- **E2：等价，裁定可删。** 被删子句 `dict.message!==raw.message` 只在 dict.message===raw.message===dict.detail 时起作用；此时 top 被置为 undefined，再由 pick(dict.message) 取回同一字符串，输出不变。变异 E2r（恢复该子句）存活，与等价结论一致。
- 4 个测试文件中，「合法文案保留」改为「非白名单 code 不显示」与规格变更一致，不属放水 ✅。但「文案保留」与长度上限现在只由 PLANNING_VERSION_CONFLICT 一个 code 覆盖：
  - WL1b/WL1c（从名单删除 UNSUPPORTED_PROVIDER / CHAPTER_REQUIRED）存活。
  - **P3-2**：删除名单项方向是 fail-safe（只丢文案，不泄露），但建议参数化覆盖全部 50 个 code，或至少再加一个 code，并覆盖 detail.code / HTTP_n 形态。
- **P2-2（覆盖回退）**：N6、N7、N8、C1 上轮能抓住，本轮存活。
  - N6、N7、C1：在白名单前置后为等价或死代码。
    - N6/N7：字符串 detail 或 HTTP_n 无 dict 时取不到 code，直接 return。
    - C1：两名单不相交，第 133 行 RAW 检查为死代码，可删，或改成测试断言两名单不相交。
  - N8（去掉 message===code 跳过）不等价：CANON_RECOVERY_REQUIRED 在白名单内且后端 message 回落为 code。推断变异后普通模式会显示裸 code「CANON_RECOVERY_REQUIRED」（不是泄露，但属于体验退化），当前无测试守护。建议补一个用例。

### 4. 变异（mutations.log 47 项 + mutations2.log 3 项；前端在临时 worktree 中做，已丢弃）
- 白名单类：
  - CAUGHT：WL1（删 PLANNING_VERSION_CONFLICT）、WL2/2b/2c（加 str(exc) code / SOURCE_PRIVACY_REVIEW_REQUIRED / VERSION_CONFLICT）、WL3（忽略名单）、WL3b（无 code 放行）、C2（去 detail.code 回退）、C2b（HTTP_n 不让位）。
  - SURVIVED：WL1b、WL1c，见 P3-2。
- 其余 CAUGHT：W7、W8a/b/c、N1–N5、N9、R1、R3–R7、L1–L3、C3、E1、D1、D2、I1、I2、H6、AI1–AI3。
- relPath 模式本轮已变，R2/R8 按新模式重跑并新增 R9（回退为旧的误杀正则），均 CAUGHT。
- SURVIVED：N6、N7、N8、C1、E2r，见第 3 节。

### 5. axe / header 抽查（axe.json 即 axe-inert.json、axe.log）
- 1024/1100/1280/1440 × 普通/专业：仅 moderate 级 heading-order / landmark-unique（与上轮一致），无 serious/critical。
- inspector 隐藏时 inert + aria-hidden，Tab 进入次数为 0；展开后可聚焦。header 搜索框 span/kbd 无重叠，无水平滚动。

### 6. 全量门禁（Node 22.14，--pool=forks --maxWorkers=3，串行错峰，起跑前查 uptime）
- 基线 persistent-node22：raw 298，adj 297。
- full1/2/3：raw 293 / 293 / 293，ISI 8，adj 293 / 293 / 293，新增非 ISI 失败 0。suiteErr 仅 LocalAiBrowserJourneyContracts ENOENT（基线既有）。
- (a) 三次最好 ≤297 ✅；(b) 允许一次重跑 ≤297 ✅（三次均达标）。

### 7. 其他
- 未触碰 4299 / 8000（8000 只经 vite 代理被动 GET，且非 GET 均被 abort）。vite 仅用 4399，已按 PID 关闭；临时 worktree vera-duim3-mut 已移除；未提交、未推送。

---

## [VERA-FE] 独立复审：fbe029c4（work/hermia-default-ui-i18n-20261025，e471dc76 PASS 之后的跟进）

**结论：PASS**（无 P0/P1；P2/P3 列为后续跟进，不阻塞）。证据目录：`/workspace/hr/vera-compare/duim-fbe029c4/`。

### 1. 后端变异与 AST 扫描器
- 真实扫描（scan-real.json）：literal 294 / dynamic 164 / 白名单 50；WL∩dynamic=∅，WL−literal=∅。
- 扫描器能检出（变异被杀）：str(exc)、变量传 message、.format、%、%-tuple、join、三元、隐式拼接、dict()、helper 函数、变量中转的字面量（保守判为 dynamic）、Call(**kw)、子类 super("CODE", str(e))、super(code=,message=)、detail 键、删除唯一字面量站点。
- 新增 code 用 str(exc) 且不在白名单：契约不报。这是正确且安全的，因为普通模式不显示非白名单 message。
- 扫描器在测试中真实执行：execFileSync("python3")。
- 无 python3 时（no-python.log）：整个 apiErrorWhitelist.test.ts 在 collect 阶段报 `spawnSync python3 ENOENT`，不会静默通过。但这表现为 suite 级失败，692 个用例会从失败计数中消失。

### 2. 三个 code 裁定
- **AUDIO_PARAMETER_UNSUPPORTED**：所有站点都是字面量（api.py:2521、studio_audio_execution.py:259/268、audiobook_service.py:217），文案有用（例如“只支持 0.5 到 2.0 倍语速”）。现在不在白名单，用户只能看到通用 HTTP 文案，丢失了可操作的提示。**建议加入白名单，或补 err.code 专属友好文案。**
- **IMAGE_PROVIDER_REQUEST_FAILED**：api.py:2477 是字面量“图片服务请求失败，请检查地址、模型和服务状态”，可操作。job error_code 属于另一通道。**建议加入白名单，或补专属文案。**
- **TEXT_PROVIDER_NOT_CONFIGURED**：不是纯字面量，经 ModelRuntimeError 以 `exc.safe_message` 透出（api.py:953/2189/3821）。memory_agent.py 会传内部 token 作为 message，扫描器看不到 Enum code。**维持不进白名单是正确的**，可补 err.code 友好文案。
- 另外：jobs.py:770 `ModelRuntimeError(INVALID_REQUEST, str(exc))` 现在之所以安全，仅因为 RuntimeErrorCode 均不在白名单。今后不得把它们加入白名单。
- 以上三者目前都没有 err.code 条目，回落到 HTTP 状态文案。

### 3. err.srv.* 映射
- SERVER_LITERAL_EN 17 条，zh/en 各 17 个 key，集合一致；en 值与后端英文原文逐字一致，zh 值全部是中文译文。
- 浏览器实测（srv.mjs → browser-srv.json，vite 4399）：zh-CN 与 en 各 51 例（17 code × call/exportDownload/assetDownload）全部通过。近似文本（大小写/空白变化）和非白名单 code 均不替换、不泄露原文。
- UI 挂载 AssetLibraryPanel：zh 显示中文译文，en 显示英文。
- P3：zh 文案“expected_version 必须是非负整数”和 PRECONDITION_REQUIRED 的文案含有字段名，普通用户看到的是开发者术语。
- P3：en 语言下，NovelImportPanel、ExportPanel、AssetLibraryPanel 的“代码：”“请求 ID：”“详情：”标签硬编码为中文，未走 i18n。

### 4. N8 修复与列表不相交断言（vmut.log，真实 vitest）
- 被杀：WL1b、WL1c（靠 size==50 断言）、N8a（两个判断都删）、C1a、S1（去掉精确匹配，52 个失败）、S2（关闭映射）、Z/Z2（删除 zh/en 的 err.srv key）。
- 存活：
  - WL1d：等量替换白名单成员。参数化用例直接遍历实现自己的 WL，没有独立的期望清单。P2。
  - N8b：只删 trim 分支。P3。
  - N8c：只删 out===code。与 trim 分支等价，可忽略。
  - S3：err.srv key 缺失时回落到 code。P3。
  - S4：大小写不敏感匹配。P3。

### 5. 扫描器盲区（P2，回归防护，当前无泄露）
- 以下写法不产生 dynamic 标记：`**dict` 展开、基础 dict 展开、`body["message"]=str(exc)`、dict.update、`code=…, **{message}`。
- code 经类属性、常量变量、exc.code、Enum .value 或 f-string 给出时，扫描器看不到。
- 在多站点 code（KNOWLEDGE_REVIEW_SOURCE_EMPTY，api.py:2035/2047）上，以上 9 种全部存活。真实 vitest 中 mK2（2035 处 `**base`）结果为 692 passed。此前看似被杀的变异，实际只是被 Hermia 的 withMutant 模式断言拦下，不是契约在起作用。
- P3：literal 集合混入环境变量和常量名（DATABASE_URL、Q4_K_M 等），削弱了“WL⊆literal”的意义。

### 6. 浏览器注入与 axe
- inject：81 例 × 路径 × basic/pro，统计与 e471dc76 完全一致。
  - basic 模式下 call、ExportPanel、AssetInspector 各为 75 ok + 6 legit-ok，**0 泄露**。
  - AssetLibrary 在 inject 里显示 "no button"，AssetInspector/pro 显示 NO-TECH，都是旧 harness 的已知限制。
- inject2：AssetLibrary/AssetInspector 的 basic 与 pro 全部通过，bad=0。
- axe：无 critical/serious，只有 heading-order、landmark-unique（moderate，与上轮相同）。inert 和焦点行为正常。

### 7. 全量门禁（Node 22.14，`--pool=forks --maxWorkers=3`，与上轮和 task11 的口径一致）

基线 persistent-node22：raw 298，adjusted 297。三次运行错开启动，启动时 load 分别为 0.61、3.73、4.11。

| 运行 | raw | ISI | adjusted | 基线外的非 ISI 失败 |
|---|---|---|---|---|
| full1 | 293 | 8 | 293 | 0 |
| full2 | 293 | 8 | 293 | 0 |
| full3 | 294 | 8 | 294 | 1（creative/StudioDiscoveredImageProduction，负载下超时，属已知 flaky） |
| task11-full | 293 | 8 | 293 | 0 |

- 规则 (a) 三次取最好 293 ≤ 297：**通过**。规则 (b) 允许一次重试：三次均 ≤ 297，**通过**。
- suiteErr 只有 LocalAiBrowserJourneyContracts ENOENT，与基线相同。
- --maxWorkers=3 与 task11、e471dc76 口径相同，可以直接比较。

### 建议跟进
- P2：补齐扫描器对 dict 展开、下标赋值、update、Enum/Attribute code 的识别。
- P2：为白名单提供独立的期望清单，以杀掉 WL1d。
- P3：给 AUDIO_PARAMETER_UNSUPPORTED、IMAGE_PROVIDER_REQUEST_FAILED 补白名单或 err.code 文案。
- P3：缺少 python 时给出显式失败，而不是 suite 消失。
- P3：本地化“代码/请求 ID/详情”标签。
- P3：补 N8b、S3、S4 的断言。

清理：自起的 vite（4399，PID 33515/33489）已按 PID 停止；临时 worktree vera-duim2-mut 已删除；/tmp/vera-nopy 已删除。未提交、未推送、未碰 main/8000/4299。

---

## [VERA-FE] 独立复审 · work/hermia-default-ui-i18n-20261025 @ 73819989（d9fcaa08 + 73819989，对比 fbe029c4）

**结论：PASS**（无 MUST-FIX）。证据目录：`/workspace/hr/vera-compare/duim-73819989/`

### 1. 契约变异（真实 vitest，临时 worktree 改 app/，跑 apiErrorWhitelist.test.ts；cmut.log）
"contract=Y" 表示 `contract holds on the real app/` 本身失败。

| 变异 | 结果 | 真实契约失败 |
|---|---|---|
| mK1 `**{message}` 展开 / mK2 `**base`(api.py:2035) / mK3 `body['message']=` / K6 `dict.update` | KILLED | Y |
| mI1 类属性 code / mD1 常量 code / mD3 真 Enum `.value` / D4 f-string code / mD2 `exc.code` | KILLED | Y |
| F1 `.format` / F2 `%` / KW1 `Call(**kwargs)` / KW2 `code=, **{message}` | KILLED | Y |
| IH1 子类 `super().__init__(code,str(e))` / IH3 子类 kw super / H1 helper 返回 dict | KILLED | Y |
| **IH2 二级继承类属性 code** | 只有 Hermia 内置变异因文本变化失败 | **N（盲区）** |
| **P1 位置参数反序 `ApiErr(str(exc), CODE)`** | 同上 | **N（盲区）** |
| WLdyn AUDIO_PARAMETER_UNSUPPORTED 改走 `_error(str)` / WLdyn2 IMAGE_PROVIDER_REQUEST_FAILED 改 f-string | KILLED（3 failed） | Y |
| NEW 新增非白名单 str(exc) code | 存活（预期，不违约） | N（正确） |
| 前端 WL1d 删一个补一个 / WL1d' 只删 / N8b / S3 / S4 / S1 | 全部 KILLED | — |

- 误报：真实扫描得到 literal 189、dynamic 204、unknown 32。DATABASE_URL、Q4_K_M、OPENAI_API_KEY、HOME 都不在 literal 和 dynamic 里。WL 共 52 项，与 dynamic 交集为 ∅，没有缺字面出处的项。
- 缺 python3：PATH 只留 node 时，721 个测试里有 36 个失败。首条是 `python3 scanner is available`，报 `spawnSync python3 ENOENT`。失败是显式的，不再是 0 test。证据：no-python.log、nopy.json。

### 2. 两个新白名单 code
- AUDIO_PARAMETER_UNSUPPORTED 的四个 HTTP 出处都是字面量：studio_audio_execution:259/268、audiobook_service:217、api.py:2521。
- IMAGE_PROVIDER_REQUEST_FAILED：api.py:2477 是字面量。image_job_service:172 和 screenplay_service:838 只作 job error token，不在 HTTP 错误包络路径上，可以接受。

### 3. 中文回归（matrix-new/base.json，336 组 × 2 版本）
- 矩阵：zh × normal/pro × 1024/1100/1280/1366/1440/1920 × DPR 1/1.25 × 6 个模块。heads、status、btnText 和 body 全文与 fbe029c4 **逐项完全一致**，问题字段（hs/hdrOut/clipped/offscreen/ov/noName/keyLeak）也一致。
- 没有英文或 key 泄漏，也没有新增溢出或重叠。
- 运行时切换：在 1366 下 normal/pro × 6 模块，中→EN 的结果与直接以 en 加载一致，EN→中 后与原中文一致，差异为 0，lang 正确（locale-switch.json）。tz 不响应式的风险没有复现。

### 4. 英文抽查
- 55 个 key 中英都有，zh 值没有改动。2 个 en 值含 CJK。
- 没有 noName 和 keyLeak 问题。header 里的 "Settings" 在 pro 1024 下越界（VIDEO/EDIT），base 已经如此。

### 5. 普通模式泄漏与 axe
- 浏览器注入（inject.mjs，ExportPanel/AssetLibrary/AssetInspector/call × basic/pro）的计数与 fbe029c4 完全相同，basic 下泄漏为 0。
- axe 输出与上一轮逐行相同，没有 critical 或 serious，只有 heading-order 和 landmark-unique 两项 moderate。

### 6. 全量（Node 22.14，--maxWorkers=3，三轮错峰；基线 raw 298 / adj 297）
| 轮次 | total | raw | ISI | adj | 基线外（非 ISI） |
|---|---|---|---|---|---|
| full1 | 12577 | 293 | 8 | 293 | 0 |
| full2 | 12577 | 295 | 8 | 295 | 2（StudioCanvasVideoTask 为 creative/* 已知抖动，u1.purge.host 已知抖动） |
| full3 | 12577 | 293 | 8 | 293 | 0 |

suiteErr 只有 LocalAiBrowserJourneyContracts（基线内）。规则 (a) 三取最好 293 ≤ 297，PASS；规则 (b) 允许一次重跑，三轮都 ≤ 297，PASS。注：run1 期间与变异和矩阵并行，负载约 12，仍然达标。

### 发现（按严重度）
- **P2（英文暴露的既有布局缺陷，不是本轮回归）**：IMAGE/AUDIO 空态左栏在 1024/1100 下被挤到约 30px，文字逐字竖排，并与右侧面板重叠。fbe029c4 的中文和英文都已存在（shots/base-zh-CN-normal-1024-AUDIO.png 等）。英文按钮更长，因此 offscreen 从 4 增加到 20（New generation / Write a line / Import from assets）。建议另开布局修复。
- **P3**：扫描器有两个盲区，即 IH2 二级继承类属性 code 和 P1 位置参数反序。app/ 中目前没有这两种写法，属于理论风险，建议补 AUDITED 规则或测试。
- **观察（非 MUST-FIX）**：英文 UI 仍有大量中文残留，例如各模块标题、编辑工具栏（播放/切割/入点）、资产类型、空态文案。这是粗翻范围内的问题，没有发现会导致误操作的错译。

## [VERA-FE] 独立复审 @ 4b1b82d8（窄屏布局修复，基于 73819989）：MUST-FIX

证据：`/workspace/hr/vera-compare/duim-4b1b82d8/`（matrix-new/base.json、analysis.txt、range-*.json、axe-*.json、cssmut.log、full1-3.json、isi1-5.json、shots/）。
对照：同一脚本跑 73819989（4499）与 4b1b82d8（4399），只读 GET mock，非 GET 全部拦截；未写 8000，未碰 4299。

### 结论
竖排问题已修好，>1200 宽度零变化，axe 和全量 gate 都通过。但 en 的 VIDEO/EDIT 在 1201–1268（普通）/1201–1244（专业）宽度下「设置」仍在视口外，正好落在本次 ≤1200 断点之上，判 MUST-FIX。

### 已确认修好
- 竖排：矩阵 zh/en × 普通/专业 × 1024/1100/1101/1180/1200/1201/1280/1366/1440/1920 × DPR 1/1.25 × 6 模块，共 480 格。逐字竖排从 64 格降到 0；空态按钮越界从 36 格降到 0（en IMAGE/AUDIO 的 New generation / Import from assets 等）。≤1100 时网格变成 IMAGE/AUDIO/ASSETS `784px 240px`、VIDEO `1024px`，不再有 0 宽列。1100/1101 两侧都正常。
- >1200 不变：1201/1280/1366/1440/1920 共 200 格，可见元素几何签名、按钮文本、正文和网格列与 73819989 逐项相同，0 差异。
- 1024 只剩图标的搜索框：可访问名完整（zh「搜索功能、章节或命令」，en「Search chapters, commands」），不再只有 Ctrl K。点击能打开命令面板并聚焦输入框，Ctrl K 也能打开。
- axe：zh/en × 普通/专业 × 1024/1100/1201/1366 × 6 模块，serious/critical 新旧都是 0。
- 旧 CSS（73819989 的三个 CSS 文件）下，narrowLayout.css.test.ts 失败，属实。

### MUST-FIX
- **MF-1（P1）en VIDEO/EDIT 在 1201–1268 宽度下「设置」越出视口。** 逐像素扫 1180–1366：普通模式 1201–1268 有 36 个宽度越界，专业模式 1201–1244 有 44 个，按钮在右边被截掉（见 shots/new-en-normal-1201-VIDEO.png）。原因是这两个模块顶栏多了「导出」等工具。73819989 时越界范围是 1181–1268，本次只修了 ≤1200 这段。这是旧问题，我在 73819989 的矩阵里没测 1201–1279，所以漏了。zh 和其他模块没有这个问题。
  修法建议：顶栏断点提高到 ≥1280，或者改成不依赖断点的方案：设置按钮 `flex:none`，搜索框和模块分段可以收缩，或者工具区溢出后收进「更多」。另外加一个浏览器级断言：在 1201/1240/1268 宽度下，en VIDEO/EDIT 的设置按钮 right ≤ innerWidth。

### P2
- **≤1200 规则块放在 ≤1180 和 ≤1060 之后，同等优先级下把它们覆盖了。** 结果是：
  - ≤1060 的分段按钮 `padding:6px 5px` 被改回 9px，`gap:5px` 被改回 6px；
  - ≤1180 的搜索框 `width:32px` 被 `flex:0 1 200px; min-width:96px` 覆盖。zh 在 1024–1200 变成 200px 宽（73819989 是 32px 图标），zh 专业 1024 是 132px。
  现在没有溢出，但之前的收紧白做了，所以 en 窄屏余量变小。同一个块里 `.global-header{gap}` 还写了两遍（8px 后又写 6px）。建议把 ≤1200 块移到 ≤1180 之前，或者合并。
- **narrowLayout.css.test.ts 只对 CSS 文本做正则匹配。** CSS 变异 12 个：杀死 4 个（M2/M3 断点改为 900、M9 顶栏断点改为 1000、旧 CSS）；存活 8 个：
  - M1/M4：后面追加覆盖，把 0 宽列加回来；
  - M5：重新显示左栏；
  - M8：后面追加 nowrap；
  - M10/M11/M12：顶栏 gap/padding/搜索框加大，设置按钮被挤出；
  - M7：只调换声明顺序（无害，正确存活）。
  另外 M6 只改空白（无害）却让测试失败，属于误报。这个测试证明不了布局结果，尤其是「设置在视口内」这一条，它只检查 `gap:8px` 这个字面值。建议用 Playwright 在 1024/1100/1201/1268 宽度下断言网格列数、设置按钮的 right 和 scrollWidth，CSS 文本测试只作辅助。
- **≤1100 隐藏左栏后，没有别的入口能打开它（旧问题）。** 1101 有、1024 没有的入口：IMAGE 的「漫画制作」子入口；ASSETS 的类型筛选（全部/图像/音频/视频/文档）；VIDEO 的场景/镜头树和素材引用。窄屏下这些功能就进不去了。建议加一个抽屉或折叠按钮。

### P3
- Ctrl K 提示从 ≤1180 隐藏扩大到 ≤1200（1181–1200 也看不到），影响不大。pro 顶栏「导出」未翻译，Hermia 已知。

### 全量 gate（Node 22.14，`--pool=forks --maxWorkers=3`，开跑时负载约 4–5）
- run1/2/3：raw 293/293/293，ISI 8/8/8，adjusted 293/293/293。不在基线里的非 ISI 失败为 0；suite 级失败只有基线里已有的 LocalAiBrowserJourneyContracts ENOENT。narrowLayout 三次都是 4/4 通过。
- (a) 三次最优 adjusted 293 ≤297：通过。(b) 允许一次重跑 ≤297：通过（首跑就满足）。基线是 298/adjusted 297。
- **ISI.regression 多出的 2 条：** 我在独立进程里单跑这个文件 5 次，失败数是 8/10/8/8/8。基线是 8。第 2 次多出的 2 条是「cannot submit a delayed local file after the project returns to its original value」和「admits a newly mounted owner after the old instance was permanently invalidated」，没有负载时也会偶发。本次只改了 CSS，jsdom 逻辑不受影响，判为已知 ISI 时序不稳定，和本次改动无关。

### 清理
临时 worktree（vera-l-base、vera-l-mut）已删除。自己的 vite（4399/4499）已按 PID 结束，包括子进程。本段未提交。

---

## [VERA-FE] 窄屏布局第二轮复审 @ 5e279fb6（范围 4b1b82d8..5e279fb6）— 结论：PASS（附 P3 建议）

证据目录：`/workspace/hr/vera-compare/duim-5e279fb6/`（mx.mjs / nav.mjs / navkbd.mjs / p3.mjs / nlmut.sh 及其输出）。

### 上轮问题关闭情况
- P1 en VIDEO/EDIT 设置按钮越界：已关闭。独立矩阵 8736 行（zh/en × normal/pro × 6 模块 × DPR 1/1.25 × 1024–1370 每 2px，另加 1061/1101/1181/1201/1269/1281/1440/1920）0 违规：设置按钮 right ≤ 视口、无横向滚动、顶栏无重叠/越界、无竖排挤压、搜索框高度 28–29、可访问名完整；非 GET 请求 0。
- P2 ≤1200 块顺序覆盖：已关闭（≤1200 块已移除，≤1280 → ≤1180 → ≤1060 降序；CSS 测试断言降序）。
- P2 CSS 测试只做文本匹配：已关闭（新增真浏览器 narrowLayout.browser.mjs，见下）。
- P2 ≤1100 左栏隐藏无替代入口：已关闭（IMAGE/ASSETS/VIDEO 新增 `select[data-narrow-nav]`）。
- P3 1181–1200 Ctrl K 丢失：见 P3 裁定。

### ≥1281 宽屏对照 73819989
- 2304 行几何签名对比：IMAGE/VIDEO/AUDIO/EDIT/ASSETS 全部 0 差异。NOVEL 384 行出现差异（inspector 折叠 + context-bar CTA 位移），已证实是矩阵顺序造成的假象：完整矩阵先跑 1024 窄屏，inspector 自动折叠后保持折叠状态。用与基线相同的“直接从 1281 进入”路径重测 NOVEL 96 行，差异为 0；该区间也没有改动 inspector 相关代码。
- 搜索框高度修复对宽屏的影响：逐项核对，≥1281 时搜索框宽高与 kbd 显示均与基线一致，无影响（修复只作用于 ≤1280）。

### 窄屏入口
- ≤1100 显示，1101 及以上 0 个可见。zh/en × normal/pro 均验证：切换条目/漫画、资产按类型过滤（图像只显示 2 张图片）、专业模式回收站、镜头选择都生效；与左栏双向同步（窄屏选择后加宽，左栏选中项一致；宽屏在左栏选择后缩窄，select 同步）。
- role=combobox，标签正确（zh：切换视图或素材 / 资产类型 / 选择镜头；en：Switch view or item / Asset type / Pick a shot）。Tab 可达，ArrowDown 可改值，键盘改值后左栏同步。
- 观察（不判错）：en 下选项文本仍含中文（素材名、“镜头 n”）；漫画页 h2 为中文；option value 用中文 key（仅内部使用）。

### P3 裁定：可接受
- zh 在 1181–1280 保留 Ctrl K 提示；en 下 kbd 被视觉隐藏（clip 成 1px），但可访问名仍是 “Search chapters, commands Ctrl K”，Ctrl+K 在所有宽度都可用。
- 建议（P3）：加 `aria-keyshortcuts="Control+K"`；title 中目前没有快捷键信息。

### narrowLayout.browser.mjs 有效性
- 在 4b1b82d8 上：240 组合，44 违规，exit 1。在 5e279fb6 上：0 违规，exit 0；AXE=1 时 1024/1366 的 serious/critical 为 0。
- 变异结果：

| 变异 | 结果 |
|---|---|
| M0 不改 | 存活 0（正确） |
| M1 后置覆盖重新引入 0 宽列 | 杀死 120 |
| M2 image 断点 1100→900 | 杀死 24 |
| M3 video 断点 1100→900 | 杀死 8 |
| M4 第二个 media 块恢复 0 1fr | 杀死 8 |
| M5 左栏重新显示 | 杀死 24 |
| M6 只改空白（良性） | 存活（正确，非误报） |
| M7 声明重排（良性） | 存活（正确） |
| M8 空态按钮后置 nowrap | **存活** |
| M9 顶栏断点 1280→1000 | 杀死 14 |
| M10 ≤1280 块 gap40/padding60 | **存活**（搜索框可收缩吸收，设置按钮未越界，属可接受存活） |
| M11 设置按钮 padding 40 | 杀死 10 |
| M12 搜索框 min-width 400 | 杀死 140 |
| M13 设置可收缩 + 搜索不收缩 | 杀死 12 |
| M14 窄屏入口断点 1100→1000 | 杀死 24 |
| M15 zh 1181–1280 也隐藏 Ctrl K | 杀死 60 |
| M16 搜索框高度塌成 6px | **存活** |

- 接线：vitest 的 include 是 `*.test.*`，`npm test` 就是 `vitest run`，仓库里也没有 CI 配置，所以这个脚本只能手动运行。脚本固定高度 800，没有 DPR 维度。

### 发现（按严重度）
- P1：无。
- P2：无。
- P3-1：browser 测试没有断言搜索框高度（M16 存活），本轮修复的回归没有被测试覆盖。建议断言 `.global-search` 高度在 24–40。
- P3-2：没有断言空态按钮换行（M8 存活）。
- P3-3：narrowLayout.browser.mjs 没接入 vitest/CI，没有 DPR 1.25 维度。
- P3-4：en Ctrl K 建议加 aria-keyshortcuts。
- P3-5：IMAGE 漫画视图中窄屏入口消失（仍可经“生成/图片画布”按钮返回）。

### 门禁（Node 22.14，三次全量，基线 raw 298 / adj 297）
| 运行 | raw | ISI | adj | 非基线非 ISI 失败 |
|---|---|---|---|---|
| full1 | 295 | 10 | 293 | 0 |
| full2 | 293 | 8 | 293 | 0 |
| full3 | 293 | 8 | 293 | 0 |

- (a) 三次取最好 293 ≤ 297：通过。(b) 允许重跑一次 ≤ 297：通过（每次都 ≤ 297）。
- 唯一的 suite error 是基线已有的 LocalAiBrowserJourneyContracts ENOENT。
- 注：full1 与浏览器矩阵并发，负载偏高，但结果与 full2/3 一致。
- 交叉核对 /workspace/hr/duim3：293/293/293，与 Hermia 的说法一致。

---

## [VERA-FE] 复审 work/hermia-default-uw-port-20261025 @ ca8bdac0（base 73819989）— 2026-10-25

**结论：MUST-FIX**（1 个 P0，2 个 P1）。证据：`/workspace/hr/vera-compare/uwport-ca8bdac0/`（假后端 fakeBackend.mjs:4698，vite:4599；全程未写 8000、未碰 4299）。

### P0
1. **有真实身份时重开不回到上次章节，还会把记录覆盖成第 1 章。** 已存 ch-003，冷启动后落在 ch-001，lastpos 被改写成 ch-001。原因：章节列表先于 bootstrap actor 到达，此时 `useLastChapter` 的 identity 还是 session，`pickChapter` 回落到首章，store 随后有了 chapterId；actor 到达后 `if (chapterId) return`，再由 rememberChapter 用真实 key 写入 ch-001。延迟实验（reopen-race.json）：bootstrap 晚 2.5s → 回落；chapters 晚 → 正确落在第 3 章；不加延迟 → 回落。单测只覆盖纯函数，没有覆盖这个竞态（变异测试无法杀死）。修复方向：identity 还没确定（actor 未到）时不要 pick，也不要 remember。

### P1
2. **"仅本次会话"在主界面从不显示。** App.tsx 丢掉了 `useLastChapter` 的返回值，`LAST_POSITION_TEXT` 没有渲染的地方；只有无身份时抽屉内部有会话提示。
3. **抽屉不能滚动。** `.dui-tasks-drawer` 用 fixed + 居中，没有 max-height，也没有 overflow。1366×768 下读取结果和历史并展开对比后，「恢复这个版本…」跑到视口外点不到（Playwright 提示 outside of viewport）。1920×1080 下可以完成。
4. **焦点陷阱缺失。** 打开后 Tab 到第 9 下焦点逃到 body，Shift+Tab 同样会逃出。焦点逃出后 Esc 不再关闭（esc.mjs）。不过有 role=dialog + aria-modal，焦点在抽屉内时 Esc 能关闭，关闭后焦点回到「任务与结果」按钮。

### P2
5. EN 界面下「任务与结果」按钮和整个抽屉仍是中文（硬编码，没有走 i18n）。
6. axe 只有 moderate 级：heading-order、landmark-unique，没有 serious/critical。

### 通过项
- **采用（adopt）**：确认前 0 次写入；取消后 0 次写入；双击确认只发出 1 次 PUT，带 expected_version/digest/incarnation/expected_card；作品 v1→v2；Canon/设定 0 次写入，写入设定按钮为 disabled。
- **恢复（restore）**：取消 0 次写入；确认后只有 1 次 POST …/restore，追加出 v3，历史为 [1,2,3]，旧版本保留。
- **异常**：409/500（JSON 与纯文本 traceback）/断连/403，在 normal 和 pro 两种模式下，adopt 和 restore 各测一遍，共 20 例：都只写一次，没有自动重发；断连和 500 显示「不确定，请重新读取」（UNKNOWN 语义）；均未泄露原始错误（faults.json）。
- **U1 老问题**：lastpos key 为 `poemseed.default.lastpos.v1::user::project::instance`，与 prefs 和其他 `poemseed.*` key 不冲突；无身份时不写 storage；200 [] 不清空其他设置；已删除的章节回落到首章；切换用户时隔离；没有伪造的身份。
- **StrictMode**：dev 浏览器中任务列表能加载；快速开关 12 次再加延迟刷新后，不会卡在「正在读取任务」，也没有 pageerror。
- **1024/1366/1920 × zh/en × normal/pro**：无横向溢出，没有多种状态同时显示（P0-3 未复现）。
- **变异测试（8/8 全部被测试杀死）**：去掉 StrictMode 修复、无身份时持久化、复活已删除章节、跳过恢复确认、跳过采用确认、写 Canon、去掉恢复前的新鲜度校验、去掉 Esc。所有变异均已还原，git status 干净。
- **全量（Node 22.14，三轮，开跑前 load 约 1.8–2.3）**：raw 293/294/293，ISI 8/9/8，adjusted 293/293/293；与基线相比无新增失败；LocalAiBrowserJourneyContracts ENOENT 在基线里已有。规则 (a) 三取最好 ≤297：PASS；规则 (b) 允许重试 1 次 ≤297：PASS。

### 未覆盖
- 浏览器内切换项目（proj-b）没有实测。只做了代码审查：抽屉的 key 含 novelId，换项目会重挂载；lastpos key 含 project。

---

## [VERA-FE] 第三轮前端独立复验 — f7174b6b（2026-10-25，UTC+8）

**结论：MUST-FIX**。证据目录：`/workspace/hr/vera-compare/uwport-f7174b6b/`。环境：vite 4599，假后端 4698。8000 没有写入，4299 没有碰过。

### 必须修复
1. **[P1] identity 失败后恢复会覆盖真实记录**（recover.json "online"）。复现步骤：bootstrap 失败一次 → 以会话模式落在 ch1 → online/focus 触发 refetch 并成功 → u-m5 的 lastpos 由 ch3 被覆盖成 ch1。另外，失败后切到 B 账号，B 的键也会被写入 ch1。建议二选一：
   - 带 token/scope 的 bootstrap 出错时也算 pending；
   - 只有在当前真实身份下完成过 pick，或用户显式导航之后，才允许写入。
2. **[P1] 抽屉内确认 adopt/restore 后焦点丢到 body**。确认按钮被卸载后，Tab/Shift+Tab 第一下就离开了陷阱。Esc 还能关闭抽屉，焦点也会回到触发按钮。其余情况下 Tab/Shift+Tab ×30 都留在抽屉内：刚打开、选中任务后、confirm 打开时。

### 其他问题
- [P1 测试缺口] App 层门控没有单测。M4（门控恒 false）、M5（删 isLoading 项）、M6（删 mismatch 项）、M7（删会话提示）、M10（删 document 级 Esc 监听）这 5 个变异全部存活。hook 层和陷阱相关的变异（M1–3、M8、M9、M11、M12）都被测试杀掉。
- [P2] 会话中途从 A 切到 B，A 的 ch3 会写进 B 的键（actor 变化时 chapterId 没有重置）。
- [P2] 英文 UI 的抽屉里，TasksPanel/ResultsPanel/HistoryPanel 还有 17 行中文。
- [P3] bootHang 期间页面显示"未打开章节"，没有 loading 也没有超时提示。boot 6s 期间先显示入口卡片，没有显式的加载态。

### 竞态表（1366，已存 ch3）
| 场景 | 落点 | lastpos 写入 |
|---|---|---|
| 无延迟 | ch3 | 1× ch3 |
| boot 0.5s | ch3 | 1× ch3 |
| boot 2.5s | ch3 | 1× ch3 |
| boot 6s | ch3 | 1× ch3 |
| chapters 2.5s | ch3 | 1× ch3 |
| chapters 6s + boot 2.5s | ch3 | 1× ch3 |
| boot 500 | ch1 + 会话提示 | 0 |
| bootDrop | ch1 | 0 |
| bootHang 30–35s | 不打开章节；resolve 后 ch3 | resolve 后 1× ch3 |
| actorB（无记录） | ch1 | 只写 u-b |
| 无 identity | ch1 + 会话提示 | 0 |
| **失败 → online 恢复** | **ch1** | **u-m5 被写成 ch1 ✗** |

### 通过项
- 会话提示：zh 为"· 章节位置：仅本次会话"，en 为"· Chapter position: this session only"。只在没有 identity 时显示。
- 抽屉滚动：1366×768、1024×768、1280×720 三个尺寸下，都能滚到恢复按钮，并用真实点击完成恢复（1 次 POST，生成 v3）。
- axe 没有 serious/critical，只有 moderate（heading-order、landmark-unique）。
- 回归：
  - adopt/restore：确认前 0 写，取消 0 写，双击只有 1 个 PUT；Canon 0 写。
  - 20/20 故障场景：无泄漏，显示 UNKNOWN，不重发。
  - StrictMode 不卡死，0 个 pageerror。
  - U1 reopen 隔离正确。
  - 溢出矩阵 12 格全部无横向溢出。

### 门控（adj = raw − ISI + 8；基线 298 / adj 297）
| run | raw | ISI | adj | 基线外的新失败（非 ISI） |
|---|---|---|---|---|
| 1 | 294 | 9 | 293 | 0 |
| 2 | 293 | 8 | 293 | 0 |
| 3 | 293 | 8 | 293 | 0 |

(a) 三次取最好 293 ≤ 297，通过。(b) 允许重试一次，同样通过。三次都有 suite 错误 `LocalAiBrowserJourneyContracts.test.tsx`，它不在基线外的新失败里。

### Hermia 的 2 个新失败（每个单独跑 5 次，分支 f7174b6b vs 基线 73819989）
- ISI "admits a newly mounted owner…"：分支 1/5 失败，基线 0/5。整个文件稳定有 8 个失败。这条属于 ISI 文件内部的时序抖动，已经由 ISI 扣减覆盖，不阻塞，但建议跟踪。
- u1.purge.host "left the list"：分支 0/5，基线 0/5。三次全量跑也都没有复现，判定为高负载下的偶发失败，不阻塞。

## [VERA-FE] 第四轮前端独立复验 — uw-port @ 2ed4c99c（范围 f7174b6b..2ed4c99c）

**结论：PASS**（上一轮的 MUST-FIX 全部关闭；新发现都是 P2/P3，留待下一阶段处理，不阻塞）。
证据：`/workspace/hr/vera-compare/uwport-2ed4c99c/`（vite 4799 + 假后端 4698；8000/4299 在路由层拦截，guard=[]）。

### 上轮 MUST-FIX 复现重放
- P1 bootstrap 失败 → 联网 refetch：u-m5 恢复到第 3 章，写入的是 ch-003，**没有**被覆盖成 ch1（recover.log）。✅
- P1 确认采用/恢复后焦点：落在抽屉标题 `dui-tasks-home`，Tab 留在抽屉内（focus.json）。✅（Shift+Tab 见 P2-1）
- P1 App 层 gate 单测：逻辑已抽到 lastPosGate 并有单测，M4–M6 被杀；App.tsx 的接线仍无测试（见 P2-2）。✅（降为 P2）
- P2 A→B：B 拿到 ch-001，A 的 ch3 没写进 B 的 key（ab.json）。A→B→A→B 往返：各自回到自己的记录，没有串写（nr.json aba）。✅
- P2 英文抽屉中文：运行时残留从 17 行降到 5 行（列表态只剩 1 行，是用户数据的任务名「封面与分镜」）；静态统计三个面板含中文的行共 51 行，44 行已用 z() 包裹，未包裹 2 行（覆盖率约 94%）。只作观察项。
- P3 加载态：2s/6s 显示 loading，10s 显示 timeout，12s bootstrap 成功后 15s 回到第 3 章，提示消失（nr.json late）。失败时显示 failed，联网恢复后提示消失（failRecover）。✅
- Esc、关闭按钮、焦点归还给触发按钮、Tab/Shift+Tab 循环 25 次都留在抽屉内、抽屉滚动/max-height（a11y.log）、「仅本次会话」提示（单测 M7 被杀）：都正常。

### 新发现（都留待下一阶段）
- **P2-1** 焦点停在抽屉标题（确认采用/恢复之后）时按 Shift+Tab，焦点会跳出模态框，落到背后的「任务与结果」触发按钮上（focus.json restoreShiftTab inDrawer=false）。原因：trapTab 认为标题在抽屉内（inside=true），但标题不等于 first，所以没有 preventDefault。再按一次 Tab 会被 document 级拦截拉回来，Esc 也仍然有效，所以评为 P2。
- **P2-2** App 层接线没有测试：M4b（App identityPending=false）、M4c（isError 传 false）、M7b（App 不渲染 lastPosStatus）都存活。
- **P2-3** 会话已经成功之后，如果某次后台 bootstrap 重取失败（例如窗口重新聚焦时网络抖动），状态栏会在会话中途显示 failed；这期间手动点的章节（ch4）属主 key=null，联网恢复后也**永远不会被记住**，下次打开会回到 ch2（nr2.json bgFailClick4/bgRecovered）。没有串写，但「上次位置」会丢。
- **P3-1** bootstrap 永久失败时不会自动打开任何章节，编辑器为空，需要手动点章（点了可以正常编辑，不写记忆）。行为安全，但首屏是空的。
- **P3-2** 焦点在 body 时按 Esc 关闭抽屉，焦点落到「Expand sidebar」，没有回到触发按钮（抽屉内按 Esc 时是正常的）。
- **P3-3** M2（写入时的 pending 判断）存活：被属主规则覆盖了，近似等价变异。M20（关闭后 document 监听器泄漏）存活：panel 为 null 时这个监听器不会拦截 Tab，危害很低。
- 关闭抽屉后在页面其他地方按 Tab/Shift+Tab 不会被劫持（defaultPrevented=0）。

### 变异（DefaultTasksDrawer / useLastChapter / lastPosGate 三个测试文件，共 21 个用例）
被杀：M1 M3 M4 M5 M5b M6 M7 M8 M9 M10 M11 M12 M13 M14 M15 M16 M17 M18 M19 M21（20 个）；存活：M2 M4b M4c M7b M20（5 个）。详见 mutations.txt。

### axe
zh/en、basic/pro、1024/1366/1920 下只有 moderate 级的 heading-order 和 landmark-unique，与上一轮相同；没有 serious/critical。

### 全量 gate（Node 22.14，三次独立运行）
| 运行 | raw | ISI | adjusted |
|---|---|---|---|
| 1 | 293 | 8 | 293 |
| 2 | 295 | 10 | 293 |
| 3 | 295 | 10 | 293 |
基线 298/297。(a) 三次中最好 293 ≤297 ✅；(b) 允许重跑一次 ≤297 ✅（三次都 ≤297）。三次都没有基线之外的非 ISI 失败。

### Hermia 未确认点
- LocalAiBrowserJourneyContracts：整个套件在文件加载阶段报 ENOENT（`tests/e2e/v2-local-ai-files-live.spec.ts` 不存在），与基线 persistent-node22.json 中的 `<file load>` 条目以及 m1flaky2 日志里的报错完全相同。**属于基线。**
- esc.mjs 里 closebtn 超时：**是我的脚本问题，不是回归**。脚本用 /Tasks/ 选到的是页头的 rb-trigger 按钮，抽屉根本没有打开，所以抽屉里的关闭按钮不存在，click 一直等到超时。改用 `status-bar__action[aria-haspopup=dialog]` 重测后，关闭按钮能关闭抽屉，焦点也回到了触发按钮（nr.json keys.closeBtn）。

---

## [VERA-FE] 独立复核：work/hermia-theme-dualcanvas-20261026 @ 03e8034a（base f8d76863）

证据目录：`/workspace/hr/vera-compare/dualcanvas-03e8034a/`（Node 22.14，playwright-core + Chrome，GET-only mock，非 GET 一律 abort 计数）

### 结论：有条件通过 —— 1 项 MUST-FIX（阻断，修复一行），其余可后续

### MUST-FIX
- **P1【阻断】VIDEO 镜头树选中态丢失（深色 / 浅色、普通 / 专业均受影响）**。VideoRebuild 把 `.mw-tree` 按钮从 `aria-selected` 改成了 `aria-pressed`，但 `imageRebuild.css:19` 的选择器仍然是 `.mw-tree>button[aria-selected="true"]`。结果是选中项的背景 rgb(30,58,64) 和强调色 rgb(77,184,196) 都没了。深色与 base 的像素对比：VIDEO 差 7416 px（bbox 10,469–165,517），IMAGE 和 EDIT 为 0。修法：选择器改为（或追加）`[aria-pressed="true"]`。证据：`theme-diff.txt`、`dark-*.png`。

### P2
- 确认条是内联的 `role=group`，不是 dialog：打开、取消、确认之后焦点都掉到 BODY，Esc 也关不掉。键盘 Enter 可以打开「接入上画布…」。建议焦点移到确认按钮，关闭后还给触发按钮，并支持 Esc。
- 上画布 key 不按身份区分（`poemseed.rebuild.canvas.<kind>.<P>`）：A→B 切换后，B 能看到 A 的上画布。这是 base 就有的行为，不是本分支引入的，记录在此。
- 测试有效性：`themeDualCanvas.browser` 没有接入 vitest 或 CI（package.json test = `vitest run`，没有 .github，也没有任何引用）。这条测试不覆盖接入、确认、快照、身份。

### P3 / 观察
- 「仅本次会话」期间加的节点，身份迟到后会被静默丢弃（不会覆盖 A，正确），建议给个提示。
- 身份翻转后壳层回到普通模式（base 就是这样）。
- 残留的硬编码 hex 多数是 var() 回退值或漫画内容色。EditNleShell 渐变里的 #1a1a22 / #12141c 在浅色下可以再看一下。
- 英文界面里夹杂中文，仅作观察。

### 已验证通过
- 隔离（image + video）：不确认、取消都不改上画布；确认会复制出 ↑ 副本并分配新 id，之后两边独立（快照）；没有 undo/redo，Ctrl+Z/Y 不跨画布；生成显示为不可用，没有可点的执行按钮；非 GET = 0。下画布调色板只有补充类节点。
- 身份：A→B→A 没有串写（u-a=2，u-b=1）；刷新保留；无身份时显示徽标、不写 dualcv key、刷新即清空；迟到的身份不覆盖已有数据。
- 普通模式：IMAGE/VIDEO/EDIT/AUDIO 都没有挂载 DualStack。
- 深色：除上面的 P1 外，其余模块计算样式 diff 为 0（pro 下新增的 dstk 元素除外）。主题实时切换正常（EDIT 和画布双向都对）。
- 窄屏 narrowLayout 8 个宽度：new 和 base 都是 192 组合 / 0 违例，uw-port 没有回退。
- axe：两种主题下 serious/critical 均为 0（themeDualCanvas 60 行全部通过；base 上 28 fail，Hermia 报的是 32，差异可能来自 D 项）。

### 变异表（unit = DualStack 等 vitest；browser = themeDualCanvas.browser）
| 变异 | unit | browser |
|---|---|---|
| M1 自动接入 | KILLED | survived |
| M2 引用而非快照（复用 id） | **survived** | survived |
| M2b 就地改输入对象 | KILLED | survived |
| M3 去掉确认 | KILLED | survived |
| M3b 取消也接入 | KILLED | survived |
| M4 key 去掉 userId | KILLED | survived |
| M4b 无身份也写 LS | KILLED | survived |
| M5 生成可用 | KILLED | survived |
| M6 浅色 --cv-bg 回填深色 | KILLED | KILLED |
| M7 下画布全调色板 | KILLED | survived |
| M8 普通模式也挂 DualStack | **survived** | survived |
| M9 上下共用 key | KILLED | survived |
建议补两条测试：断言接入后 id 不同（针对 M2），断言普通模式不挂载 DualStack（针对 M8）。

### 全量门禁（adj = raw − ISI + 8，阈值 ≤297；baseline 298 / adj 297）
| run | raw | ISI | adj | 新增失败（非 ISI、不在 baseline） |
|---|---|---|---|---|
| 1 | 293 | 8 | 293 | 0 |
| 2 | 293 | 8 | 293 | 0 |
| 3 | 293 | 8 | 293 | 0 |
(a) 三次取最好 = 293 ✅；(b) 一次重试内 ≤297 ✅。LocalAiBrowserJourneyContracts ENOENT 是 baseline 就有的失败。

---

## [VERA-FE] 独立复核：双画布 × 真实后端联调（work/hermia-dualcanvas-integration-20261026 @ 7c964d66，tree 9448db4c；后端只读 8ea45399）

**结论：MUST-FIX（阻塞，1 项）**。证据目录：`/workspace/hr/vera-compare/dci-7c964d66/`

### 发现（按严重度）
- **P1 MUST-FIX（阻塞）**：普通模式下 IMAGE/VIDEO 的 `.rcv` 宽度为 0，在 1024/1099/1100/1180/1279/1280/1366/1370/1920 九个宽度上都能复现（`rcv-size.json`、`af.json`、`af-*-normal.png`）。根因是 6024748c 在 RebuildCanvas.tsx 里给 `.vid-canvas-host` 加了一层 flex 包裹，而该容器是 `align-items:center`，子画布没有被撑开。专业模式正常（rcv = 视口宽度）。
- **P2 待确认**：专业模式 DualStack 的高度从 247/163 变成了 320/320。各宽度下都没有出现横向溢出（offN=0），需要设计确认这是否是预期改动。
- **P2 后端（转交后端负责人，不阻塞前端）**：image-node-result 返回 403 是后端缺口。commit 阶段会重新判定 `source_read_required`，但准入只给了写权限。反事实验证：设 `local_input=True` 后返回 200。另外，错误重映射把所有 403 合成了同一个 code；反事实中无 token 的请求也返回了 200。
- **INFO**：应用壳目前没有 en 切换入口，lang 恒为 zh-CN，所以 en 验证不适用，不算回归。

### 已完成项
- 5de20d4d 修复的 VIDEO 高亮：深色 VIDEO 像素差为 0，7c964d66 上没有回归。
- 自起后端 + vite 跑通了 preview → create → execute → candidate → review 全链路；回填这一步因上述 403 失败，反事实后端（CF）上回填成功。

### 反例表
测试方式：真实后端 4698 / 反事实后端 CF 4697，前端经 vite。并发全部用 deferred/route 拦截，没有用 sleep 做同步。
| 组 | 用例 | 结果 | 反向验证 |
|---|---|---|---|
| a 解析严格 | A1–A7（单测） | PASS | M1：把 exact() 改成恒真后 A1、A2 变红；M2/M2b：去掉 source_snapshots 或互斥键检查后 A4 变红 |
| b 不重复派发 | B1 连点、Enter、双击 → create 1 次、execute 1 次；B2 跨标签页；B3 超时不重发；B4 响应丢失后离线再上线不重发；B5 中途切换模块 | PASS | M3、M3b、M3c（去掉 busy/sentActions、按钮 loading、canAction）仍为绿；M3d 再禁用 consumeImpact 后 **B1 变红，出现 5 次 execute**。说明有纵深防御，一次性 impact token 是最后一道 |
| c 不误回填 | C0 正对照成功；C1–C8 篡改 asset_id、digest、project_id、job_id、incarnation、scope、版本不前进、未知字段 → 都判为待核对，无泄露，backfill 只有 1 次；C9 候选字节被篡改 → 不进入 review；C10、C11（单测） | PASS | C10：去掉 novel_id 检查后变红；M4/M4b：去掉 client 和 assertSavedImageNode 中的 asset/pin 校验后 **C1 仍为绿**。还有其他层兜底（推测是 record()/checkedCanvasDefinition 的结构与 reference_states 校验），记为纵深防御，单层反向验证未能变红 |
| d 撤销/过期/迟到/换身份 | D1 401、D2 403、D3 409 → 不进入候选态、不重试；D4 换身份后迟到的 200 不被采用；D5 换身份在派发前就拦截（弱）；D6 review 返回 403 → 不回填 | PASS | — |
| e 不自动执行 | E1 读取、选择、保存空白、preview、刷新都不产生写请求；E2 入队后刷新或开新标签页不产生写请求 | PASS | — |
| f 回归 | 主题：axe wcag2a/aa 在深/浅 × 普通/专业 × NOVEL/IMAGE/VIDEO 共 12 组下都是 0 违规；窄宽 1024–1370 无横向溢出；<1100 时“任务”抽屉能打开，Esc 关闭后焦点回到触发按钮；双画布隔离：非 GET 请求 0 次 | PASS，**rcv 宽度 0 除外（P1）** | — |

所有临时改动都在临时 worktree vera-dci-ce 里做，已还原并删除该 worktree。

### 门禁（基线 raw 298 / adjusted 297；adjusted = raw − ISI + 8）
| 轮次 | raw | ISI | adjusted | 不在基线中的失败 |
|---|---|---|---|---|
| 1 | 295 | 10 | 293 | 0 |
| 2 | 293 | 8 | 293 | 0 |
| 3 | 295 | 9 | 294 | 1 个 TaskCenter.receiptCompanion（已知 flaky） |
(a) 三次取最好 293 ≤ 297 ✅；(b) 一次重试内 ≤ 297 ✅。

阻塞项：P1。

---

## [VERA-FE] 复验 be3f67b0（tree 142f2436，同分支）

**结论：PASS。** 上一轮的 P1 已修复，不再阻塞。另有 P2 一项：仓库测试里没有 rcv 宽度断言。
证据：`/workspace/hr/vera-compare/dci-be3f67b0/`

### 1. diff 核对
- 用 cmp 比对了 880f694b 里的复审段和我本地未提交的版本：完全一致。
- 7c964d66..be3f67b0 一共改了两个文件：INDEPENDENT_REVIEW.md（+39 行）和 RebuildCanvas.tsx（1 行，`fix.diff`）。
- RebuildCanvas.tsx 这一行除了声称的 alignSelf stretch / flex 1 1 auto / width 100% / minWidth 0，还多加了一个 `data-rcv-wrap` 属性。这个属性不影响样式（INFO）。

### 2. rcv 尺寸（`rcv9-*.json`、`rcv9-compare.txt`、`s-*.png`）
- 范围：9 个宽度 × 普通/专业 × IMAGE/VIDEO，深色主题全覆盖；浅色在 1024 和 1366 两个宽度抽样。共 44 组，全部 rcv>0，没有越界，没有横向滚动。
- 专业模式：和 7c964d66 的尺寸完全一致。
- 普通模式：和 f8d76863（接入 DualStack 之前）的尺寸完全一致。例如 1366 下 IMAGE 是 1366×525，VIDEO 是 1190×320。
- 7c964d66 在普通模式下宽度全部为 0，证实修复前确实有问题。
- 非 GET 请求数为 0。

### 3. f 组回归（`af.json`）和 b1/e1 抽查
- axe 深/浅 × 普通/专业 × NOVEL/IMAGE/VIDEO 共 12 组，0 违规。
- 1024–1370：rcv 宽度等于视口宽度，没有溢出。
- “任务”抽屉：Esc 能关闭，焦点回到触发按钮。
- 双画布非 GET 请求数为 0。
- 在真实后端上重跑 B1 和 E1：都 PASS，请求序列和上一轮一致。

### 4. 反向验证
- 在临时 worktree 里去掉这次的 flex 修复后，rcv 检查有 22 组变红，正好是全部普通模式的组合（22/22）；专业模式不受影响。
- **P2**：这次没有把 rcv 宽度断言加进仓库测试，`tests/m5/themeDualCanvas.browser.mjs` 只检查了亮度和节点数。建议补一个“普通模式 rcv 宽度大于 0”的断言。

### 5. 门禁（基线 298/297；adjusted = raw − ISI + 8）
| 轮次 | raw | ISI | adjusted | 基线外失败 |
|---|---|---|---|---|
| 1 | 292 | 8 | 292 | 0 |
| 2 | 293 | 8 | 293 | 0 |
| 3 | 294 | 8 | 294 | 1 个 u1.purge.host（单独跑 5 次失败 1 次，是 flaky；这次的 diff 没有碰到它） |

- (a) 三轮最好 292 ≤ 297 ✅；(b) 一次重试内 ≤ 297 ✅。
- 补充：第 1 轮额外报了 studioComicBootstrap.capture 套件错误，之后两轮没有出现。
- 第 2 轮最初那次跑的时候 box 被挂起（loadavg 采样在 15:18→15:25→15:37 之间断档），那次作废并重跑；表中的第 2 轮是重跑后的结果。

### Hermia 第 3 轮的 5 个基线外失败
单独跑的设计：每个文件跑 5 次，共 5 种条件。
- be3f67b0：负载中（load 2.4–5.3）、空负载（1.98–5.47）、重压（8 个 CPU 占满，load 最高 9.94）。
- 7c964d66 对照：负载中（4.97–6.79）、空负载（1.36–2.53）。
- 一共 125 次运行，基线外失败 0 次。
- 我自己的三轮全量里，这 5 个也全部没有出现。

Hermia 第 3 轮（14:28–14:46）的情况：
- 这几个文件的耗时异常长：StoryboardImageHandoff 287 秒，IndependentStudioWorkspace 304 秒，AppModuleNavigationIntent 237 秒，DeclarativeTemplatePanels 234 秒。它们都集中在 14:29–14:39 同时运行；她第 1 轮里最长的文件也只有 118 秒左右。
- 失败的形态都是 5000ms 超时，或者超时之后的级联查找失败。
- 她没有留连续的负载日志，只记了每轮开始时的负载，第 3 轮开始时是 2.30。
- 结合我这边观测到的 box 挂起断档，推断她那一轮也是环境停顿（挂起或卡顿），不是代码问题。
- 补充：这次的 diff 只改了 RebuildCanvas.tsx 包裹层的样式，这 5 个测试都不会走到这段代码。

| 测试 | 判定 |
|---|---|
| AppModuleNavigationIntent（delayed overview，超时 5809ms） | flaky（环境停顿），不是回归。另外两条“工作流/主控”的失败在基线里本来就有，在 7c964d66 上同样失败 |
| StoryboardImageHandoff.additive | flaky（耗时 275 秒，超时），不是回归 |
| DeclarativeTemplatePanels | flaky（超时），不是回归 |
| PortableProjectsPanel.assetRelations | flaky（找不到元素，是被停顿拖慢后的级联），不是回归 |
| ImageQueuePanel.execute.independent | flaky（超时），不是回归 |

所有临时 worktree（old/pre/mut/be）已删除。
