# 本地最小 CI 执行结果（LOCAL-01～05）

结果：**LOCAL_CI_PASS**（五步全部真实执行且 PASS；运行器 exit code 0）。

| 项 | 值 |
| --- | --- |
| 运行标识 | `20261019-final` |
| 运行时间（Asia/Shanghai） | 2026-10-19 09:47:45 → 09:53:32 |
| 运行时间（UTC） | 2026-10-19T01:47:45Z → 01:53:32Z |
| 运行时 Git HEAD | `d73423c79a4c0a5fe5c8bf9e696c5ae91565197a` |
| 分支 | `work/v2-local-ci-community-20261019` |
| 总耗时 | 346.8 s（约 5 分 47 秒），不含一次性环境准备 |
| 证据目录 | `docs/v2/engineering/evidence/local-ci/20261019-final/`（1,699,426 B，绝对主机路径已脱敏） |
| 命令集/边界 | [LOCAL_CI_MINIMUM.md](LOCAL_CI_MINIMUM.md) |

环境：Windows 11 24H2（10.0.26100）· Python 3.11.9，使用仓库 `.github/ci/python-constraints.txt`
固定依赖创建独立 `.venv`（fastapi 0.142.2 / pytest 8.4.2 / sqlalchemy 2.1.3 / reportlab 4.5.1 /
fonttools 4.59.1 / opentimelineio 0.18.1 / Pillow 12.3.0，`pip check` 通过）· Node 22.14.0 ·
pnpm 10.6.5（corepack，`frontend/package.json` 的 packageManager）· 系统 Edge（Playwright
`PLAYWRIGHT_CHROMIUM_EXECUTABLE`）· 无模型（`MOCK_PROVIDER=true`）· 云端关闭 · File 后端 ·
隔离 profile 位于 `<repo>/.runtime/local-ci/20261019-final`。

## 1. 分步结果

| 步骤 | 结果 | 耗时 | 真实执行的判定证据 |
| --- | --- | --- | --- |
| LOCAL-01 后端真实启动 | PASS | 8.8 s | `uvicorn app.main:app` 真实进程；`GET /health` → HTTP 200，响应体
{"status":"ok","version":"0.7.0","profile":"HYBRID"}；`version` 与 `release/version.json` 一致；进程退出、端口释放 |
| LOCAL-02 关键正确性 | PASS | 225.3 s | pytest JUnit：`tests=941`，`passed=473`，`skipped=468`，`failures=0`，`errors=0`（4 个代表文件：项目生命周期 / 结构化记录 CAS / pending-canon 审核候选不得静默提升 / 共享路由权限） |
| LOCAL-03 前端构建 | PASS | 68.0 s | Vitest 全量 `4307 passed`；`tsc -b && vite build` 退出 0；设计 token lint 退出 0 |
| LOCAL-04 真连通冒烟 | PASS | 32.5 s | 真实 uvicorn + File 持久化 + Vite + 系统 Edge；Playwright JUnit `tests=2`、`failures=0`、`errors=0`（`real File V2 authoring` 保存/重读/恢复旅程；`real HTTP File V2 lifecycle`） |
| LOCAL-05 清理恢复 | PASS | 12.2 s | `stale_ports=[]`、`leaked_processes=[]`、`runtime_removed=true`；删除本轮 `.runtime/local-ci/20261019-final` 共 51,056,527 B；保留证据 1,721,483 B |

合计 346.8 s。原始回执与 JUnit/logs/screenshots 见证据目录；回执自身记录 `head`、主机与工具链版本、
每步退出码/耗时/判定字段。

## 2. 失败/边界标注（不要误读）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 完整 File 后端套件 | 未包含于 LOCAL CI | 历史完整 File 运行约 1.5 万条；本快检是代表性切片，不代表完整回归通过 |
| 完整真实 PostgreSQL 套件 | `BLOCKED_ENVIRONMENT` | D-07：本 Windows 主机 PG 环境阻塞；只有历史代表性真实 PG 子集通过。LOCAL CI 不包含 PG |
| 真实媒体（FFmpeg）/ GPU / 本地模型 | `NOT_RUN` / `LOCAL_REQUIRED` | 本轮未调用模型与收费 API，未下载模型；Mock 不证明 AI 质量 |
| 真实浏览器全量 | PARTIAL | 仅执行 2 个真实旅程；`creative` 全量、visual/geometry、其他 live 族未在本轮执行 |
| Windows 安装/升级验收 | `NOT_RUN` | 属独立完整验收层（RELEASE_GATES G9） |
| 宿主 CI | `HOSTED_BLOCKED_NO_RUNNER` | GitHub Actions 历史上 runner 未真实启动；保留原 workflow，本地 PASS 不冒充宿主 CI |

补充说明：

- 健康路由以源码为准：权威路由是 `app/main.py` 的 `GET /health`；`/api/health` 不存在，结果中记为 null，不伪造。
- LOCAL-04 使用系统 Edge（本机未下载 Playwright Chromium）；corepack 按 `packageManager` 解析 pnpm 10.6.5，属于工具链解析，不是资源下载。
- 运行器首次 `--all` 试跑时，LOCAL-05 把运行器自身进程树误判为泄漏进程（自匹配缺陷），修复于 `d73423c7` 后复跑得到本结果；首跑证据归档于 `Engineering-Runs/local-ci-20261019/evidence-20261019-final-firstrun/`。
- 另有一次使用主机预装 Python 环境的完整 PASS 运行（依赖版本与 constraints 存在漂移），归档于 `Engineering-Runs/local-ci-20261019/evidence-20261019-final-globalenv/`；本文件报告的是约束固定 `.venv` 的权威重跑。

## 3. 证据索引（SHA256）

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| LOCAL_CI_RESULTS.json | 8799 | `3a5e45c236699607ef43eb2329f9e88785f2e7eea992c881c693c7abb8ef997d` |
| LOCAL-02-junit.xml | 296842 | `9eeb2dc90d6bfb570fbbf7d1f923c7803ecec7e48ec18edf16382374e24ac36f` |
| LOCAL-02-pytest.log | 2971 | `41d45998fcd3e6a72155dd7d9393a8ab0a56cd856858dd7d6494b6eaa0e85ccc` |
| LOCAL-03-vitest.log | 50177 | `142d9592c57875279349cead7796f55fe4d957875dbf1dbfa60dc37b86fe4904` |
| LOCAL-04-playwright.log | 1049 | `3a644806607d208aa422d64e6d441f35cf3635be2b63c6427fdcf970b8e8966a` |
| junit.xml（LOCAL-04 Playwright） | 2230 | `fcdc825c837158f93e680016eecefdef7c5685b55704316350b9278400880ec4` |
| REDACTION.md | — | 脱敏说明与逐文件原/新哈希前缀 |
| test-results/**.png / .json | 849,213 | 真实浏览器旅程截图与导出证据（见前述逐文件哈希） |

## 4. 如何复跑

在已准备依赖的机器上（见 [CONTRIBUTING.md](../../../CONTRIBUTING.md)）：

```powershell
python scripts/run_local_ci.py --step LOCAL-01
python scripts/run_local_ci.py --step LOCAL-02
python scripts/run_local_ci.py --step LOCAL-03
python scripts/run_local_ci.py --step LOCAL-04
python scripts/run_local_ci.py --step LOCAL-05
```

## 5. 结论

对 HEAD `d73423c79a4c0a5fe5c8bf9e696c5ae91565197a`：**LOCAL_CI_PASS**。
该结论不改变 [RELEASE_GATES.md](RELEASE_GATES.md) 的任何状态：V2 仍是 **NOT RELEASE_READY**，
宿主 CI 仍是 `HOSTED_BLOCKED_NO_RUNNER`，需求矩阵没有任何一行因本地快检被提升为 `ACCEPTED`。
