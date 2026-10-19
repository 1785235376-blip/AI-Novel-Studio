# 本地最小 CI 执行结果（LOCAL-01～05，round 2）

结果：**LOCAL_CI_PASS**（五步全部真实执行且 PASS；运行器 exit code 0）。
本轮在**干净环境**中重建依赖后复跑，作为权威证据。

| 项 | 值 |
| --- | --- |
| 运行标识 | `20261019-r2` |
| 运行时间（UTC） | `2026-10-19T03:55:43+00:00` → `2026-10-19T04:01:26+00:00` |
| 运行时 Git HEAD | `7e1ea003c975f585a26201e007f8e4a7872c7ee2` |
| 分支 | `work/v2-local-ci-community-20261019` |
| 总耗时（五步） | 351.9 s（约 5 分 52 秒） |
| 环境准备 | 31.5 s（重建 `frontend/node_modules` from lockfile + 新建 `.venv-repro` from constraints） |
| 证据目录 | `docs/v2/engineering/evidence/local-ci/20261019-r2/`（1,695,622 B，绝对主机路径已脱敏） |
| 命令集/边界 | [LOCAL_CI_MINIMUM.md](LOCAL_CI_MINIMUM.md) · [LOCAL_CI_COVERAGE_20261019.md](LOCAL_CI_COVERAGE_20261019.md) |

环境：Windows 11 24H2（`Windows-10-10.0.26100-SP0`）· Python `3.11.9`（clean venv），依赖按 `.github/ci/python-constraints.txt` 安装（PIP_CHECK_EXIT=0 No broken requirements found.）· Node `v22.14.0` · pnpm `10.6.5` · 系统 Edge（Playwright `PLAYWRIGHT_CHROMIUM_EXECUTABLE`）· 无模型（`MOCK_PROVIDER=true`）· 云端关闭 · File 后端。安装日志：PNPM_INSTALL_EXIT=0 Done in 1.8s using pnpm v10.6.5。

## 1. 分步结果

| 步骤 | 结果 | 耗时 | 真实执行的判定证据 |
| --- | --- | --- | --- |
| LOCAL-01 后端真实启动 | PASS | 9.2 s | `uvicorn app.main:app` 真实进程；`GET /health` → HTTP 200，`{"status": "ok", "version": "0.7.0", "profile": "HYBRID"}`；进程退出、端口释放 |
| LOCAL-02 关键正确性 | PASS | 228.9 s | pytest JUnit：`tests=941`，`passed=473`，`skipped=468`，`failures=0`，`errors=0` |
| LOCAL-03 前端构建 | PASS | 68.1 s | Vitest 全量 `4307 passed`；`tsc -b && vite build`；设计 token lint |
| LOCAL-04 真连通冒烟 | PASS | 35.8 s | 真实 uvicorn + File 持久化 + Vite + 系统 Edge；Playwright JUnit `tests=2`、`failures=0`、`errors=0` |
| LOCAL-05 清理恢复 | PASS | 9.9 s | `stale_ports=[]`、`leaked_processes=[]`、`runtime_removed=true`；删除本轮 runtime 55,093,758 B；保留证据 1,717,589 B |

## 2. 干净环境可复现性（round 2）

1. 删除并按提交的 `frontend/pnpm-lock.yaml` 重建 `frontend/node_modules`（`pnpm install --frozen-lockfile`，PNPM_INSTALL_EXIT=0 Done in 1.8s using pnpm v10.6.5）。
2. 新建 `.venv-repro` 并按 `.github/ci/python-constraints.txt` 安装 `-e .[dev]`（`pip check` 通过：PIP_CHECK_EXIT=0 No broken requirements found.）。
3. 用干净环境的解释器执行 `python scripts/run_local_ci.py --all --label 20261019-r2`，结果即上表。

Linux 状态：**NOT_RUN / BLOCKED_ENVIRONMENT**。本机存在 WSL Ubuntu-24.04（Python 3.12.3、git 2.43），但缺少 Node、且缺少 `python3-venv` 而安装需要 sudo 密码；因此没有伪造 Linux 结果，也未用 Windows 结果冒充 Linux。

## 3. 附加：真实 PostgreSQL 最小子集（D-07 修复验证）

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| 此前阻塞节点 ×3 个全新数据库 | 1 passed in 7.39s / 1 passed in 7.44s / 1 passed in 7.32s | Engineering-Runs/local-ci-round2-20261019/d07-node-1792379853-1..3.log |
| 整个 cross-process host 文件 | 1 passed, 1 skipped in 7.55s | d07-interop-file-1792379853.log |
| 连接口径（round-2 归档） | “1,210” = 累计插桩 `psycopg.connect` 调用次数（日志未归档）；“5” = 修复后 PG `log_connections=on` 的累计 “connection authorized” 行数 —— 两个不同指标，不再并列成前后对比 | round-2 PG 日志 |
| 同口径 round-3 复测（D-24 节点，真实 PG） | 未池化回放：173 次读取 / 466 次直连尝试 / 16.0 s FAIL；修复后：427 次读取 / 0 次直连 / **2** 个新建物理连接 / 825 次池借出 / 峰值并发 2 / 3.94 s PASS | [evidence/local-ci/20261019-r3-d24/](evidence/local-ci/20261019-r3-d24/) |
| 24 文件 curated PG 子集 | 27 个失败是 D-24 的共享前置障碍（仅代表性节点在 a517e0a2 上验证过“修复前已存在”）；round-3 修复后受影响文件 PG 变体 **28 passed / 27 skipped** | d07-curated-1792379853.log · round-3 evidence |

完整真实 PostgreSQL 套件（约 4.8k 条）本轮未整体重跑，仍是独立长跑门禁；D-24 保持 OPEN。

## 4. Skip 审计（round 2）

LOCAL-02 的 468 个 skip 已逐项分类：467 个 PostgreSQL 实现契约（PG-only 函数 = 0）与 1 个 Windows symlink 权限；无未知 skip。详见 [LOCAL_CI_COVERAGE_20261019.md](LOCAL_CI_COVERAGE_20261019.md)，可用 `python scripts/audit_local_ci_skips.py --junit <LOCAL-02-junit.xml> --fail-on-pg-only` 复现。

## 5. 证据索引（SHA256，脱敏后提交副本）

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| LOCAL_CI_RESULTS.json | 8,854 | `1309ea7a8c88a45726ae9f7a66c6f3f2f7ce5e57cd6ecc7076b43cf667af21d3` |
| LOCAL-02-junit.xml | 296,842 | `d5db9a070f1c09bf61d17ac6cb5d521531684efc04907ee17b57a1bd4b50e6c6` |
| LOCAL-02-pytest.log | 2,957 | `957edcd4bfecc1f4ee57da27431e725a0fd1de91c14f1674ad4fbc5d4df51a14` |
| LOCAL-03-vitest.log | 46,293 | `add1764e9c4b45f4054a023aae3a1cb1e9ce6e6cda182394949f28a38f675e91` |
| LOCAL-04-playwright.log | 1,049 | `4c43705ea44a9d50f8e5e8005cdeaafcc8f880c92e7ceb9d5cd6488aa8de991e` |
| junit.xml | 2,230 | `084f4199687bd57d7478743db0db590f722280614ee88e76810b635938c3f6c2` |

其余文件（Playwright `results.json`、真实浏览器截图等）一并提交；逐文件脱敏前后哈希见 `REDACTION.md`。

## 6. 结论

对 HEAD `7e1ea003c975f585a26201e007f8e4a7872c7ee2`：**LOCAL_CI_PASS**（File/前端/浏览器最小切片），附加真实 PG 验证显示 D-07 连接阻塞已修复。
该结论不改变 [RELEASE_GATES.md](RELEASE_GATES.md)：V2 仍是 **NOT RELEASE_READY**，宿主 CI 仍是 `HOSTED_BLOCKED_NO_RUNNER`，需求矩阵没有因本地快检被提升为 `ACCEPTED`。


> **证据版本与哈希说明（round-3 更正）**
>
> - 本文件上方的 SHA256 表对应 **round-2** 证据 `evidence/local-ci/20261019-r2/`，是本 PR 当前有效的 round-2 哈希表；round-3 未改动该目录。
> - 历史 **round-1** 证据位于 `evidence/local-ci/20261019-final/`；其中 9 个文件（`LOCAL-01-backend.log`、`LOCAL-02-junit.xml`、`LOCAL-02-pytest.log`、`LOCAL-03-build.log`、`LOCAL-03-design-tokens.log`、`LOCAL-03-vitest.log`、`LOCAL_CI_RESULTS.json`、`REDACTION.md`、`results.json`）在 round-2 被原位把 `<repo>` 替换为 XML 安全的 `[repo]`（D-22），因此这些文件的哈希已变化。
> - round-1 当时文档里记录的旧哈希描述的是**修复前副本**，不对应现在提交的内容；该说明**不适用于**上面的 round-2 有效哈希表。
> - round-3 的证据与哈希见 [evidence/local-ci/20261019-r3-d24/](evidence/local-ci/20261019-r3-d24/) 及其 `SUMMARY.md`；round-3 执行 SHA 为 `415cbcc2`。

## 7. Round-3（2026-10-19）：D-24 修复与定向回归

- 根因：PG 模式 `ExperimentalStore` 对每次元数据读取新建连接（单节点同代码复现：173 次读取 / 466 次直连尝试 / 16.0s FAIL；修复后 427 次读取 / 0 次直连 / 2 个物理连接 / 3.94s PASS）。
- 修复：`engine_for_url()` 进程级缓存的有界 SQLAlchemy 池 + `pooled_connection()`；事务语义保持 commit-on-clean-exit。
- 验证：代表性节点 2 个 fresh DB **PASS**（4.66s / 4.85s）；完整受影响文件 PG **28 passed / 27 skipped**（44.93s，原 27 failed/1 passed）；File 对照 **28 passed / 27 skipped**；D-07 连接风暴节点 **PASS**（6.42s）。
- closeout 补充：真实 PG 池回归文件 6 项 **PASS**（含“旧直连路径反例”——同一 50 次读取窗口下旧路径 50 次新建物理连接 / 0 次池借出被契约断言拒绝，池化路径 0 / 50 / 50 通过）；File profile 同文件 **6 skipped、exit 0** 记为 SKIPPED_NOT_APPLICABLE，不当作池行为 PASS。
- Skip 审计工具改为严格 module/class+参数配对，历史 LOCAL-02 JUnit 重审 **467/467 匹配、0 PG-only**；新增 8 条正/反例测试。
- 仍未完成：完整 PG/File 套件、D-20、D-17、Linux/宿主 CI；V2 仍 NOT RELEASE_READY。


## 8. Round-3 closeout 证据更正（2026-10-19）

- 旧证据 `20261019-r3-d24/verification-summary.json` 的 `junit`/`console` 已改为指向真实归档文件名（无归档的 console 置 null），原因见该目录 `CORRECTIONS.md`；`pool-regression-file` 由错误的 PASS 更正为 **SKIPPED_NOT_APPLICABLE**（原始恢复：5 skipped / 0 failed / exit 0）。

- 新增 `scripts/check_local_ci_evidence_index.py` 与回归测试：证据回执声明的文件缺失/越界/XML 损坏即失败。最终补丁同时检查 `verification-summary.json` 与 `LOCAL_CI_RESULTS.json` 两种回执；实测 **4 份回执（2+2）、35 条声明路径、0 缺失、0 越界、11 个 XML 全部良构、PASS**。此前“8 路径”来自仅扫描 verification-summary 的旧版本，已更正。

- 诊断源码/指标/存活的 post-fix 线程栈样例已归档到 [evidence/local-ci/20261019-r3-closeout/](evidence/local-ci/20261019-r3-closeout/)；**修复前超时线程栈无法恢复**（同一日志路径被后续运行覆盖），限制已在 `diagnostics/README.md` 说明。
- 本轮 execution SHA `5e278819`；交付提交仅追加文档/证据。


## 9. Round-3 Final Closeout（2026-10-19）

- 本轮仅修证据索引检查器：执行 SHA `1a042b28`，交付提交仅追加文档/证据。
- 检查器现在显式解析两种回执格式并校验：存在性、相对路径、证据根目录边界（拒绝 `../`、绝对路径、符号链接逃逸）、声明的与归档的 XML 良构性；合法历史回执（Round 1 与 Round 2 的 `LOCAL_CI_RESULTS.json`）兼容通过。
- 实测统计：全证据根 **4 份回执（2 verification-summary + 2 LOCAL_CI_RESULTS）/ 35 路径 / 0 缺失 / 0 越界 / 11 XML / PASS**；分目录报告 `r3-d24`（8 路径/6 XML）、`r3-closeout`（11/3）、`r2`（16/5）、`final`（16/5）均存在且通过。
- 测试：`tests/test_local_ci_evidence_index.py` 11 passed、1 skipped（Windows 无 symlink 特权）；本轮相关单测共 **39 passed / 1 skipped**。
- 旧“8 路径/2 份回执”的说法由仅扫描 verification-summary 的旧检查器产生，已在机器回执、SUMMARY 与缺陷表中明确更正；未改动历史测试结果。
- Round 3 工程质量专项到此结束；D-24 保持已修复，D-20/D-17/完整套件/Linux/宿主 CI 门槛继续保留，V2 仍 NOT RELEASE_READY。


- **XML fixture/statistics patch（执行 SHA `7c88f50f`）**：合法 XML 夹具改用显式 `write_xml()` 写入良构文档，坏 XML 负向测试保留；检查器新增 `declared_xml_paths_checked`（声明 XML 路径条目，重复计次）、`archived_xml_files_checked`（去重归档 XML 文件）、`xml_files_checked_distinct`（去重并集）、`xml_checked`（兼容别名，等于声明条目数，不是去重文件数）与去重后的 `xml_invalid` 来源。实测全证据根 **4 回执 / 35 路径 / 11 声明 XML 路径 / 13 去重归档 XML 文件 / 13 去重 XML / 0 无效 / PASS**；分目录 r3-d24 8 路径/6 XML、r3-closeout 11/3、r2 8/2、final 8/2。上一轮 §10 手填的“16 路径/5 XML”与未区分口径的“11 XML checked”已由实测值更正。
- 测试：`tests/test_local_ci_evidence_index.py` 14 passed / 1 skipped（symlink 特权缺失记为 SKIPPED，不记 PASS）；相关工程单测合集 42 passed / 1 skipped。无产品代码、D-24、D-07、完整 PG/File 套件、D-20/D-17、Linux 或宿主 CI 状态变化。
