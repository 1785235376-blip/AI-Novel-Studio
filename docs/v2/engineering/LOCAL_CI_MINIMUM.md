# 本地最小 CI（LOCAL-01～05）

版本：`LOCAL-CI-2026.10.19-r1`
适用范围：本仓库 V2 工程基线上的**开发者主动执行的分步测试命令集合**。

本文件定义命令、判定标准、证据位置和边界。真实执行结果（数量、耗时、退出码、SHA）记录在
[LOCAL_CI_RESULTS_20261019.md](LOCAL_CI_RESULTS_20261019.md)。

## 1. 定位与非目标

本地最小 CI 用于在没有云端 CI、没有 Docker、没有模型授权的情况下，对当前 Git HEAD 做
最小但真实可跑的工程验证，并把结果绑定到 SHA。

**它是**：分步 pytest / uvicorn / pnpm / Vitest / tsc / Vite / Playwright 命令与一个测试运行器脚本
`scripts/run_local_ci.py`。

**它不是**：

- 不是一键安装、一键启动、一键部署或 Docker Compose 替代品；本阶段不新增或重构任何部署入口。
- 不下载模型、浏览器或大型资源，不调用收费 API。
- 不代替完整 File 套件、真实 PostgreSQL 套件、真实媒体/GPU、Windows 安装验收或宿主 CI。
- 不因为本地 PASS 就把任何需求行提升为 `ACCEPTED`；发布门禁见
  [RELEASE_GATES.md](RELEASE_GATES.md)。

## 2. 结果词表（与需求状态分开）

| 结果 | 含义 |
| --- | --- |
| `PASS` | 该步真实执行完成且判定条件全部满足 |
| `FAIL` | 该步真实执行，存在失败/超时/判定不满足 |
| `PARTIAL` | 整体运行中有步骤被环境阻塞或部分完成（run 级汇总） |
| `BLOCKED_ENVIRONMENT` | 缺少必要环境（依赖、浏览器等）；**不是**通过，也不是产品缺陷 |
| `NOT_RUN` | 未执行 |

宿主 CI 状态单独记录：`HOSTED_PASS` / `HOSTED_FAILED_TEST` / `HOSTED_BLOCKED_NO_RUNNER`，
不得与本地结果混写。

## 3. 前置条件（已准备好依赖的机器）

- Python `>=3.11`（本仓库 `pyproject.toml`），建议按 [RUNBOOK.md](RUNBOOK.md) 安装：
  `python -m pip install -c .github/ci/python-constraints.txt -e ".[dev,fontbuild,otio,comic]"`
- Node `>=22.14 <25`；在 `frontend/` 内执行 `corepack pnpm install --frozen-lockfile`
- 可选：系统 Edge/Chrome（LOCAL-04 用；不会自动下载 Playwright Chromium）
- 本机已配置的 PostgreSQL / FFmpeg 对本最小 CI **不是必需**；它们属于独立的完整验收层。

无模型模式是受支持模式：`MOCK_PROVIDER=true`、`ENABLE_CLOUD=false`，运行器会在隔离 profile 中强制。

## 4. 分步命令

全部命令在仓库根目录执行；每一步都可单独调用，结果写入同一个 run receipt：

```powershell
python scripts/run_local_ci.py --step LOCAL-01   # 后端真实启动 + /health + 干净退出
python scripts/run_local_ci.py --step LOCAL-02   # 关键正确性切片（真实 pytest）
python scripts/run_local_ci.py --step LOCAL-03   # 前端 Vitest / tsc+vite 构建 / 设计 token
python scripts/run_local_ci.py --step LOCAL-04   # 真实后端 + Vite + 浏览器保存/重读旅程
python scripts/run_local_ci.py --step LOCAL-05   # 清理与残留检查
```

`--all` 只是按顺序执行上述五步（同一条命令集合，不是新能力）：

```powershell
python scripts/run_local_ci.py --all --label 20261019-a
```

退出码：`0` = 全部 PASS；`1` = 有 FAIL；`2` = 存在 BLOCKED_ENVIRONMENT/PARTIAL。

## 5. 判定标准

| 步骤 | 真实执行内容 | PASS 条件 |
| --- | --- | --- |
| LOCAL-01 | 隔离 profile 下启动 `python -m uvicorn app.main:app`，请求 `GET /health`（路由以 `app/main.py` 为准） | HTTP 200；JSON `status == "ok"`；`version` 与 `release/version.json` 一致；进程退出；端口释放 |
| LOCAL-02 | 以下代表的真实 pytest 切片（no model / no PostgreSQL）：<br>`tests/test_v2_creative_project_lifecycle.py`（项目创建/读取/生命周期）<br>`tests/test_structured_record_cas.py`（CAS 冲突）<br>`tests/test_surface_pending_canon_review.py`（审核候选不得静默提升）<br>`tests/test_shared_project_route_authority.py`（跨项目/越权拒绝） | pytest 退出码 0；JUnit 中 `failures == 0`、`errors == 0`、tests > 0；无超时 |
| LOCAL-03 | `pnpm run test`（完整 Vitest）、`pnpm run build`（`tsc -b && vite build`）、`pnpm run lint`（设计 token） | 三条命令退出码 0；Vitest 有真实 `Tests N passed` 计数 |
| LOCAL-04 | `playwright.v2-live.config.ts` 的 `v2-live-chromium` 项目，真实 uvicorn + File 持久化 + Vite + 系统浏览器；运行 `real File V2 authoring` / `real HTTP File V2 lifecycle` 两个旅程 | Playwright 退出码 0；JUnit 有测试且 0 失败 0 错误；浏览器真实启动 |
| LOCAL-05 | 检查本轮端口/进程是否残留；删除本轮 `.runtime/local-ci/<run-id>` 与浏览器旅程的 `.runtime/v2-live-browser/<run-id>`；保留证据目录 | 无残留端口/进程；本 run 的 runtime 目录已删除；日志/JUnit 保留 |

**快检范围声明**：LOCAL-02 是代表性快检，不是完整回归。它有意不包含完整 File 套件
（约 1.5 万条）、真实 PostgreSQL 套件（约 4,800 条 postgres-marked）、媒体/GPU/Windows 安装层。
这些层保留在 RUNBOOK 与 RELEASE_GATES 的完整验收中；本快检不改变它们的状态。

## 6. 证据与 SHA 绑定

- 证据目录：`docs/v2/engineering/evidence/local-ci/<run-id>/`
- 每步日志 + JUnit + 汇总 `LOCAL_CI_RESULTS.json`；receipt 记录 `head`（运行时的精确 Git SHA）、
  OS/Python/Node/pnpm 版本、每步耗时/退出码/判定字段。
- 隔离数据：`.runtime/local-ci/<run-id>/`（被 `.gitignore` 忽略，由 LOCAL-05 删除）。
- 证据只清理本轮自建目录；不删除用户目录、模型、RC1、历史证据或其他 worktree。

## 7. 现有工程入口的复用关系

| 现有入口 | 本 CI 的用法 |
| --- | --- |
| `scripts/run_v2_checks.py` | 复用其 `isolated_environment()` 隔离契约（PROJECT_ROOT/NOVEL_DATA_PATH/APPDATA/HOME/XDG/vault/cloud） |
| `scripts/run_windows_engineering_suite.ps1` + `windows_profiles.json` | 完整/分族 Windows 套件入口，保留不变；本 CI 不替代它 |
| `frontend/playwright.v2-live.config.ts` | LOCAL-04 直接复用该浏览器入口（本轮修复其 Windows 启服缺陷） |
| `.github/ci/python-constraints.txt`、`frontend/pnpm-lock.yaml` | 依赖版本权威；本地按此准备环境 |

## 8. 常见阻塞

| 现象 | 判定 | 处理 |
| --- | --- | --- |
| `frontend/node_modules` 缺失 | LOCAL-03/04 = `BLOCKED_ENVIRONMENT` | 在 `frontend/` 执行 `corepack pnpm install --frozen-lockfile` 后重跑 |
| 无系统浏览器且无 Playwright Chromium | LOCAL-04 = `BLOCKED_ENVIRONMENT` | 安装系统 Edge/Chrome 或设置 `LOCAL_CI_BROWSER_EXECUTABLE`；**不会自动下载** |
| 端口被占用 | 该步 FAIL（记录端口） | 释放端口后重跑；运行器每步选空闲端口 |
| PostgreSQL 未配置 | 不属于最小 CI 失败 | 记录 `BLOCKED_ENVIRONMENT` 于完整 PostgreSQL 层，不伪造通过 |
| 宿主 CI 无 runner | `HOSTED_BLOCKED_NO_RUNNER` | 保留既有 workflow，不用本地结果冒充宿主 CI |

## 9. 与发布门禁的关系

本文件只覆盖开发者快检。正式 V2 发布仍必须满足
[RELEASE_GATES.md](RELEASE_GATES.md) 的 G1–G12（含完整 File/PostgreSQL、真实浏览器、媒体、
模型、Windows 安装与用户验收）；本地 `PASS` 不能替代任何一条。
