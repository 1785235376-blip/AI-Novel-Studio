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
