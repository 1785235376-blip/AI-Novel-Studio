# 本地最小 CI 执行结果（LOCAL-01～05）

结果：**LOCAL_CI_PASS**（五步全部真实执行且 PASS；运行器 exit code 0）。

| 项 | 值 |
| --- | --- |
| 运行标识 | `20261019-final` |
| 运行时间（UTC） | `2026-10-19T01:58:07+00:00` → `2026-10-19T02:03:45+00:00` |
| 运行时 Git HEAD | `6afae9cae82430f09c547257528adccdf945dc0c` |
| 分支 | `work/v2-local-ci-community-20261019` |
| 总耗时 | 346.9 s（约 5 分 47 秒），不含一次性环境准备 |
| 证据目录 | `docs/v2/engineering/evidence/local-ci/20261019-final/`（1,702,277 B，绝对主机路径已脱敏） |
| 命令集/边界 | [LOCAL_CI_MINIMUM.md](LOCAL_CI_MINIMUM.md) |

环境：Windows 11 24H2（`10-10.0.26100-SP0`）· Python `3.11.9`，使用仓库 `.github/ci/python-constraints.txt` 固定依赖的独立 `.venv`（fastapi 0.142.2 / pytest 8.4.2 / sqlalchemy 2.1.3 / reportlab 4.5.1 / fonttools 4.59.1 / opentimelineio 0.18.1 / Pillow 12.3.0，`pip check` 通过）· Node `v22.14.0` · pnpm `10.6.5`（corepack，`frontend/package.json` 的 packageManager）· 系统 Edge（Playwright `PLAYWRIGHT_CHROMIUM_EXECUTABLE`）· 无模型（`MOCK_PROVIDER=true`）· 云端关闭 · File 后端 · 隔离 profile 位于 `<repo>/.runtime/local-ci/20261019-final`。

## 1. 分步结果

| 步骤 | 结果 | 耗时 | 真实执行的判定证据 |
| --- | --- | --- | --- |
| LOCAL-01 后端真实启动 | PASS | 8.8 s | `uvicorn app.main:app` 真实进程；`GET /health` → HTTP 200，`{"status": "ok", "version": "0.7.0", "profile": "HYBRID"}`；`version` 与 `release/version.json` 一致；进程退出、端口释放（`port_released=True`） |
| LOCAL-02 关键正确性 | PASS | 222.5 s | pytest JUnit：`tests=941`，`passed=473`，`skipped=468`，`failures=0`，`errors=0`（4 个代表文件：项目生命周期 / 结构化记录 CAS / pending-canon 审核候选不得静默提升 / 共享路由权限） |
| LOCAL-03 前端构建 | PASS | 71.0 s | Vitest 全量 `4307 passed`；`tsc -b && vite build` 退出 0；设计 token lint 退出 0 |
| LOCAL-04 真连通冒烟 | PASS | 33.7 s | 真实 uvicorn + File 持久化 + Vite + 系统 Edge；Playwright JUnit `tests=2`、`failures=0`、`errors=0`（`real File V2 authoring` 保存/重读/恢复旅程；`real HTTP File V2 lifecycle`） |
| LOCAL-05 清理恢复 | PASS | 10.9 s | `stale_ports=[]`、`leaked_processes=[]`、`runtime_removed=true`；删除本轮 runtime 共 55,093,742 B（local-ci 51,056,447 B + 浏览器旅程 4,037,295 B）；保留证据 1,723,073 B |

合计 346.9 s。原始回执与 JUnit/logs/screenshots 见证据目录；回执自身记录 `head`、主机与工具链版本、每步退出码/耗时/判定字段。

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
- LOCAL-04 使用系统 Edge（本机未下载 Playwright Chromium）；corepack 按 `packageManager` 解析 pnpm，属于工具链解析，不是资源下载。
- 运行器早期的 LOCAL-05 自匹配/浏览器 runtime 清理缺陷在 `d73423c7` 与 `6afae9ca` 修复；本文件报告的是修复后的权威运行。此前试跑证据归档于 `Engineering-Runs/local-ci-20261019/`。
- 另有一次使用主机预装 Python 环境的完整 PASS 运行（依赖与 constraints 存在漂移），仅作对照，本文件报告的是约束固定 `.venv` 的权威运行。

## 3. 证据索引（SHA256，脱敏后提交副本）

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| LOCAL_CI_RESULTS.json | 8,868 | `3c325d4341af32be72beac385271bca7a9822a35a9ac2d833b7f91c15027d956` |
| LOCAL-02-junit.xml | 296,842 | `937df0bfd736ced0f2a598c88d4e98687ed725484da3f826856e21796382cd18` |
| LOCAL-02-pytest.log | 2,949 | `048448a048a0ab416ed1043d66eb10536cb23e19475d6e432f769d1d27fc6b9f` |
| LOCAL-03-vitest.log | 52,027 | `be82ad95cdb2147a96f724dc6c6412a70e10ec68f1caca6a9fca7cb9b2ab5442` |
| LOCAL-03-build.log | 1,801 | `f005febf7c06d1cc7164943236bcc32e5025cee143fa0afa0dfd718a4c29b25d` |
| LOCAL-04-playwright.log | 1,049 | `d1d27405df51e0d8b0107ae657fe6b2dde9e186ead8cb3db79fd40e887382a25` |
| junit.xml | 2,230 | `8b1b4b5b414fe681ed71b71e45b1c7abce545f409f2a93271930b93ce71ea8bc` |

其余文件（Playwright `results.json`、`test-results/**.png` 真实浏览器截图、`.last-run.json` 等）一并提交；
逐文件哈希与脱敏前后前缀见 `REDACTION.md` 与下表：

证据文件总数：28（含 test-results 截图与浏览器结果 JSON）。

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

对 HEAD `6afae9cae82430f09c547257528adccdf945dc0c`：**LOCAL_CI_PASS**。
该结论不改变 [RELEASE_GATES.md](RELEASE_GATES.md) 的任何状态：V2 仍是 **NOT RELEASE_READY**，
宿主 CI 仍是 `HOSTED_BLOCKED_NO_RUNNER`，需求矩阵没有任何一行因本地快检被提升为 `ACCEPTED`。
