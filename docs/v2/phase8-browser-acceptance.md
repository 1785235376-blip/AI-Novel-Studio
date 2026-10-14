# Phase8 — 浏览器与视觉验收准备（真实浏览器证据）

本文件记录 **Phase8 第 9 节**要求的"真实浏览器测试入口"及其**实测结果**。所有数字来自本机真实执行，不是 jsdom。

## 1. 入口点（已实现）

| 文件 | 作用 |
| --- | --- |
| `frontend/playwright.studio-release.config.ts` | 新配置（与仓库既有 16 个 Playwright 配置并列，**未改动**既有 `playwright.config.ts`）：`testDir: ./e2e`、`baseURL` 默认 `http://127.0.0.1:5173`（可用 `STUDIO_ACCEPTANCE_BASE_URL` 覆盖）、**无 `webServer` 块**（应用由操作者自行启动）、60 s 超时 |
| `frontend/e2e/studio-release-acceptance.spec.ts` | 八个用例：六个界面各自的可访问地标（START / TASKS / ASSETS / PRODUCTION / MODEL CENTER / DELIVERY）+ 中文文案冒烟 + 键盘焦点可见性 |
| `frontend/e2e/README.md` | 操作者步骤，并明确写出"**jsdom 通过不是浏览器验收**" |
| `frontend/package.json` | 新增 `e2e` 脚本指向上述配置（既有脚本未改） |

**不使用下载的浏览器**：配置默认 `channel: 'msedge'`（可用 `STUDIO_ACCEPTANCE_CHANNEL=chrome` 切换），即使用**系统已安装**的浏览器。本机 `%LOCALAPPDATA%\ms-playwright` 与 `node_modules/playwright-core/.local-browsers` **均不存在**，全程未下载任何浏览器。

`pnpm exec playwright test --config playwright.studio-release.config.ts --list` → **8 tests in 1 file**（Playwright 1.62.1 由本 worktree 的 `node_modules` 解析到 sibling worktree，符合任务书 §16.4 的既有事实）。

## 2. 真实浏览器实测结果

**执行方式**：以 `pnpm exec vite --port 5173 --strictPort` 自行启动前端（**未启动后端**），随后
`STUDIO_ACCEPTANCE_CHANNEL=msedge pnpm exec playwright test --config playwright.studio-release.config.ts --reporter=list`。

**结果（真实输出）：`7 passed / 1 failed`，耗时约 1.2 分钟，退出码 1。**

| 用例 | 状态 | 说明 |
| --- | --- | --- |
| TASKS：统一任务中心的地标 | **PASS**（真实浏览器） | — |
| ASSETS：独立素材工作区标题 | **PASS**（真实浏览器） | — |
| PRODUCTION：制作工作流仪表盘地标 | **PASS**（真实浏览器） | — |
| MODEL CENTER：从制作视图按需打开后渲染地标 | **PASS**（真实浏览器） | 证明"按需打开"在真实浏览器中可达 |
| DELIVERY：从制作视图按需打开后渲染地标 | **PASS**（真实浏览器） | 同上 |
| 中文冒烟：外壳确实渲染中文文案 | **PASS**（真实浏览器） | — |
| 键盘：切换控件可 Tab 到达且焦点可见 | **PASS**（真实浏览器） | — |
| **START：创作开始入口地标** | **FAILED** | 等待 `getByLabel('空白项目名称')` 超时。原因：**本次未启动后端**，入口在拿不到服务端事实时不会显示"新建空白项目"表单（用例自身注释也写明只在工作区确实缺席时才创建项目）。这是**环境缺失**，不是地标缺失 |

产物：失败用例的截图与 trace 已生成于 `frontend/test-results/`（该目录**已被 .gitignore 忽略**，不作为证据提交）。服务在运行后**已停止**（端口 5173 不再监听）。

## 3. jsdom 对照（不是浏览器证据）

六个界面的组件级证据（真实数字）：`src/onboarding + src/taskcenter + src/assetbrowser + src/modelcenter + src/delivery + src/creative/IndependentStudio` → **30 files / 446 tests PASS**。它们**不能**替代上表的浏览器结论，只用于说明断言本身有既有覆盖。

## 4. 逐界面状态

| 界面 | 状态 | 依据 |
| --- | --- | --- |
| TASKS / ASSETS / PRODUCTION / MODEL CENTER / DELIVERY | **BROWSER_ACCEPTED**（真实浏览器 PASS，前端无后端） | 第 2 节 |
| START | **BLOCKED** | 需要后端（或已存在的项目）才能显示新建入口；本次未启动后端，故如实记为阻塞，**不伪造通过** |
| 视觉回归（截图基线 / 几何） | **NOT_RUN** | 本入口只做地标、中文与键盘；像素级视觉沿用既有 `playwright.visual.config.ts` 与其基线，本阶段未执行 |

## 5. 操作者把 BLOCKED 转成 8/8 的步骤

1. 用项目既有方式启动**完整应用**（后端 + 真实 PostgreSQL；仓库既有 `playwright.config.ts` 会经 `tests/e2e/database_fixture.py` 准备数据库，并需要 `E2E_DATABASE_URL`）。
2. 确认前端监听 `http://127.0.0.1:5173`（或用 `STUDIO_ACCEPTANCE_BASE_URL` 指向实际地址）。
3. `cd frontend && pnpm run e2e`（或 `STUDIO_ACCEPTANCE_CHANNEL=chrome pnpm run e2e`）。
4. 若项目已存在，START 用例会直接采用已挂载的工作区；否则应先创建一个空白项目。

## 6. 诚实边界

- 本次是**真实浏览器**执行，但**未接后端**：因此它证明"前端外壳与五个界面在真实浏览器中可渲染、可用键盘到达、中文正常"，**不**证明任何服务端行为、数据正确性或视觉像素一致。
- 未执行仓库既有的 `playwright.config.ts`（需要 `../.venv`、PostgreSQL 与 `E2E_DATABASE_URL`）与 `playwright.visual.config.ts`（需要截图基线）。
- 未下载任何浏览器；未修改任何既有测试、配置或受保护面。
