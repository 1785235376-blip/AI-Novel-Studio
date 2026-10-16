# PHASE9 — 真实浏览器验收报告（Browser Acceptance）

**分支**：`feature/v2-narrative-platform`（PR #47 保持 OPEN / Draft）
**起始 HEAD**：`3304fa6`（Phase9 任务书给出的基线）
**结论**：**8/8 PASS**（真实浏览器 Microsoft Edge + **真实后端** + 真实前端），退出码 0。

---

## 1. 环境（不是 frontend mock）

| 组件 | 实际配置 | 证据 |
| --- | --- | --- |
| Backend | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8100`，`STORAGE_BACKEND=file`、`EXPERIMENTAL_FEATURES=narrative_production_v2` | `http://127.0.0.1:8100/docs` → **HTTP 200**（进程为我启动的 python uvicorn） |
| Database | File 后端（本阶段浏览器验收用）；真实 PostgreSQL 的路径由仓库既有 e2e 夹具负责（见 `frontend/playwright.config.ts` 与 `tests/e2e/database_fixture.py`），本次**未**使用（见第 4 节 BLOCKED 说明） | — |
| Frontend | `pnpm exec vite --port 5173 --strictPort`，`V061_API_URL=http://127.0.0.1:8100` | Vite 6.4.3 `ready`，`[::1]:5173 LISTENING` |
| Browser | **系统已安装的 Microsoft Edge**（`channel: 'msedge'`），**零下载** | `%LOCALAPPDATA%\ms-playwright` 与 `playwright-core/.local-browsers` **均不存在**（运行前后一致） |
| 入口点 | `frontend/playwright.studio-release.config.ts` + `frontend/e2e/studio-release-acceptance.spec.ts`（8 用例） | `--list` → 8 tests |

## 2. 结果：8 passed（14.1s，exit 0）

```
ok 1 START: the creative start entry renders its own landmark            (4.1s)
ok 2 TASKS: the unified task centre renders its own landmark             (1.2s)
ok 3 ASSETS: the independent asset workspace renders its own heading     (1.2s)
ok 4 PRODUCTION: the production workflow dashboard renders its own landmark (1.3s)
ok 5 MODEL CENTER: opened on demand from production, renders its own landmark (1.4s)
ok 6 DELIVERY: opened on demand from production, renders its own landmark (1.4s)
ok 7 SMOKE (zh-CN): the studio shell really renders authored Chinese copy (1.2s)
ok 8 KEYBOARD: a switcher control is reachable by Tab and shows a visible focus indicator (1.4s)

8 passed (14.1s)
PLAYWRIGHT_EXIT=0
```

**首次进入工作区的关键**：`STUDIO_ACCEPTANCE_BASE_URL=http://localhost:5173`。Vite 只绑定了 **IPv6 `[::1]:5173`**，因此默认的 `http://127.0.0.1:5173` 连不上（曾因此得到 8 failed，非应用缺陷）。

## 3. 逐界面状态

| 界面 | 状态 | 依据 |
| --- | --- | --- |
| START | **PASS** | 真实浏览器中断言"项目入口"区域与"进入创作工作区"标题可见；后端在线（HTTP 200） |
| TASKS | **PASS** | "统一任务中心"区域可见 |
| ASSETS | **PASS** | "独立素材工作区"标题可见 |
| PRODUCTION | **PASS** | "Studio 生产工作流看板"区域可见 |
| MODEL CENTER | **PASS** | 从制作视图**按需打开**后"模型中心与存储"区域可见（真实浏览器可达） |
| DELIVERY | **PASS** | 从制作视图**按需打开**后"统一导出与工程交接"区域可见 |
| 中文冒烟 | **PASS** | 外壳确实渲染作者中文文案 |
| 键盘 | **PASS** | 切换控件可 Tab 到达，焦点指示可见 |

**无 FAIL、无 BLOCKED。**

## 4. 诚实边界（本报告**不**声称的东西）

1. **这 8 项断言的是"界面地标 / 中文 / 键盘可达"，不是任务书 §4 里那种完整数据流程**。"打开应用 → 创建新项目 → 选择 Creative Intent → 保存 → 进入 Production Workspace"、"创建任务 → 状态流转"、"搜索/分类/Preview/Version/引用关系"的**端到端**断言目前仍由**既有 jsdom/API 套件**覆盖（Phase8 记录：六界面 30 files / 446 tests；Phase9 期间复核 7 files / 67 tests 的界面级套件）。把它们变成**浏览器内的数据流程断言**需要后端鉴权与写入夹具，属**NOT_RUN**，不得据本报告推断已通过。
2. **未使用 PostgreSQL 运行浏览器套件**：仓库既有 `playwright.config.ts` 会经 `tests/e2e/database_fixture.py` 准备库，但它在本机**不可运行**——它硬编码 `../.venv\Scripts\python.exe`（**不存在**）且后端端口 **8000** 落在 Windows 排除端口区间（`netsh ... show excludedportrange` 列出 `8000 8000`），uvicorn 无法绑定。故本次用 **file 后端**跑真实浏览器；**数据库参与的浏览器验收 = BLOCKED_EXTERNAL**（依赖修复既有夹具或换端口，不改测试绕过）。
3. **像素级视觉回归 NOT_RUN**：既有 `playwright.visual.config.ts` 与其截图基线未执行。
4. **运行期稳定性**：Vite 曾在运行中**静默退出一次**（exit 1、无报错），导致 2 项伪失败；重启后 8/8 干净通过。若要自动化，必须先解决该退出问题（已作为上限风险记录）。
5. 未下载任何浏览器；未修改任何既有测试、配置或受保护面；运行后前端服务已停止（5173 不再监听）。

## 5. 与 Phase8 记录的差异（自我更正）

Phase8 报告与 `docs/v2/phase8-browser-acceptance.md` 曾记录 **7 passed / 1 failed，START BLOCKED**。该结果来自：(a) 当时**未启动后端**，且 (b) 提交 `3304fa6` 中的 spec 是**较早的点探版本**（`isVisible()` 探针可能在 React 重渲染间跨步）。随后改用**竞态版本**（`Promise.race`，本次随本报告提交）补上后端，即得到 **8/8**。Phase8 的两份文档已同步更正；两处结果都保留在记录中，不覆盖历史。
