# Test Report

覆盖 Context 人物选择、Cloud Secret 省略/脱敏、年龄冲突、死亡人物、Secret Leak、Provider 回退、原子写入和 Pending Canon 闭环。

> 以下 V0.1–V0.4.8.1 段落是历史记录，不是 live `origin/main` 的回归证明。较新的绑定结果见文末 Batch 2A.2 快照、Batch 2B-1 / 2B-1.1 与 Batch 2B-2；不要把任何固定 SHA 永久称为 current-main。


- PASS：全部 Python 文件 AST 语法校验。
- PASS：Context 只选择本章相关人物。
- PASS：LOCAL_ONLY Secret 原文从 Cloud Context 省略；REDACT_BEFORE_CLOUD 原文被约束占位符替换。
- PASS：年龄、死亡人物与提前泄密检查。
- PASS：Primary 不可用时回退 Local Provider。
- PASS：章节原子持久化、Summary 与 Pending Canon 文件生成。
- PARTIAL：捆绑 Python 未安装 pytest，故以无字节码等价断言脚本执行；正式环境仍应运行 `python -m pytest`。
- PARTIAL：Docker 重启、真实 Local/Hybrid、Dify、SQL dump restore/migration 因运行时依赖缺失未执行。

## V0.2/V0.3

- STATIC VERIFIED：新增 Python 文件 AST 通过；PowerShell 全部解析通过；前端必需结构存在。
- MOCK VERIFIED：Mock Streaming；生成完成前正文不变；Accept 后正文变更并产生 Pending Canon。
- PARTIAL：FastAPI 未安装，API 路由未做真实 ASGI 请求测试。
- PARTIAL：frontend node_modules 未安装，TypeScript/Vite/Vitest 未实际执行。
- NOT VERIFIED：Docker/PostgreSQL/Ollama/Cloud Provider/Dify。

## V0.4

- REAL VERIFIED：项目 Python 依赖安装；FastAPI 导入；TestClient health/novels 200。
- REAL VERIFIED：TypeScript 5.9.3 `tsc --noEmit`。
- LOCAL VERIFIED：Document round-trip、版本递增、409 冲突基础、History Restore、Job Repository。
- STATIC VERIFIED：全 Python AST、PowerShell parse。
- PARTIAL：pytest 8 项显示 100% 断言通过，但 runner 汇总后未退出并被外层超时终止。
- PARTIAL：Vite/Vitest 因沙箱拒绝 `.vite-temp` 写入而失败；依赖已经下载。
- NOT VERIFIED：Docker/PostgreSQL/Ollama/Cloud Provider。

## V0.4.5

- REAL VERIFIED：FastAPI TestClient 完整作者 API 流程。
- REAL VERIFIED：TypeScript type-check、Vite production build。
- REAL VERIFIED：Vitest 5/5。
- MOCK VERIFIED：Selection Rewrite→Draft→Accept→History→Pending Canon 编辑审批。
- NOT VERIFIED：真实 Ollama/Cloud、Docker/PostgreSQL、浏览器 E2E。

## V0.4.8.1 Repository Abstraction

- STATIC VERIFIED：Python AST、PowerShell、TypeScript。
- LOCAL VERIFIED：File Factory 共用 data root；postgres/unknown 不静默回退。
- LOCAL VERIFIED：旧 Path Context 与 ContextService 输出完全一致。
- LOCAL VERIFIED：Repository Contract 6/6 断言显示通过；pytest 仍有既知 teardown hang，外层超时终止。
- LOCAL VERIFIED：Services/Contracts 完整作者流程（Create→Save→Mock Rewrite→Accept→History→Pending→Approve→Restore）。
- PARTIAL：临时 Uvicorn HTTP 尝试超时，未作为通过证据。
- NOT VERIFIED：PostgreSQL Repository/Runtime（本阶段明确不实现）。

## Historical snapshot（safe maintenance 2026-08-28, `46bee8f`）

本段只记录本轮真实执行。数量绑定到基线 SHA、日期和环境，不能当作长期合同。

| 字段 | 值 |
| --- | --- |
| 基线 | `origin/main` `46bee8f4b57f0cc61d69746bf190a88a3fb3d733` |
| 日期 | 2026-08-28 |
| 环境 | Linux 隔离沙箱；Python 3.11.2；Node 22；`STORAGE_BACKEND=file` |
| 安装 | `uv pip install -e .[dev]`（未安装 `.[vault]`） |
| 隔离 | 仓库拥有的 run-scoped `--basetemp` / `TMP` / `TEMP` / `TMPDIR`：`.runtime/pytest-temp/safe-maint-20260828` |
| 未使用 | 用户系统 pytest 临时根、用户 `.env`、用户数据库、真实 Provider 密钥 |

### 命令与退出码

| 检查 | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 后端全量 | `python -m pytest -p no:cacheprovider --basetemp=<run-temp> -q -ra --tb=line` | 1 | 766 passed, 36 failed, 27 skipped, 0 xfail；21.46s |
| 前端 Vitest | `npx vitest run`（`frontend/`，仓库 `package.json` 的 `test` 脚本） | 0 | 376 passed / 89 files |
| TypeScript | `npx tsc -b` | 0 | 通过 |
| 前端 production build | `npx vite build` | 0 | 通过（`frontend/dist/`，不是安装包） |
| 版本一致性 | `python scripts/validate_release_version.py` | 0 | backend / frontend / environment / `release/version.json` = `0.7.0` / `0.7.0 Beta` |
| 工作区 whitespace | `git diff --check HEAD` | 0 | 本轮工作区相对 HEAD 无新增空白问题 |
| 历史 whitespace | `git diff --check <empty-tree> HEAD` | 2 | 既有 trailing whitespace / EOF 空行，未在本轮修改生产代码 |

### 已知基线失败（本轮仍失败；未改测试、未 skip/xfail）

这些是文档长期点名的四个 Python 基线缺陷，本轮隔离复现：

1. `tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission` — 并发生成幂等；全量套件中曾表现为竞态（本轮全量未列入 FAILED，隔离复跑失败，`len(created)==0`）。
2. `tests/test_p1_regression.py::test_visual_continuity_reports_scene_jumps` — 缺少 `TIME_JUMP_CUT`。
3. `tests/test_user_preference_service.py::test_preferences_are_explicit_and_separate` — 返回字段多出 `harness_enabled`。
4. `tests/test_world_rule_payload.py::test_world_rule_payload_normalizes_terms` — `forbidden` 字符串未拆成 `forbidden_terms`。

### 环境阻塞（不是本轮新业务回归）

- `novel_data/novels/sample_novel` 被 `.gitignore` 排除，干净克隆中 `tests/test_core.py` 及若干复制该夹具的测试报 `FileNotFoundError`。
- Linux 无 `socket.SO_EXCLUSIVEADDRUSE`；`tests/test_runtime_ownership_foundation_v070.py` 多项失败。Windows named mutex / Job Object 测试被 skip。
- `.[vault]` 未装导致 `KEYRING_NOT_INSTALLED`（`tests/test_packaged_control_pipe.py`）。
- 未配置 `TEST_POSTGRES_DATABASE_URL` / `DATABASE_URL`：PostgreSQL 合同 skip；`scripts/prepare_acceptance.py` 相关 v0.6.1 测试失败。
- `tests/test_v061_acceptance_lifecycle.py` 在 Linux 上得到 `UNSUPPORTED_PLATFORM` / `UNKNOWN_IDENTITY_FAIL_CLOSED`，需要 Windows 进程身份契约。

### 全量套件顺序污染（隔离复跑通过）

以下在全量 pytest 中失败，但单独复跑通过，属于既知全局 settings 污染，不记为新的独立产品缺陷：

- `tests/test_runtime_v03.py::test_non_mock_mode_preserves_real_deepseek_availability`
- `tests/test_runtime_v03.py::test_packaged_runtime_does_not_stand_in_mock_as_deepseek`
- `tests/test_phase1_feature_closure.py::test_packaged_generation_fails_closed_without_text_provider`

隔离复跑时 `tests/test_runtime_provider_status_contract.py` 为 7 passed。本轮没有对真实 DeepSeek/OpenAI 发出请求。

### 新失败

未确认新的独立产品回归。全量 36 个失败已归入：已知基线、环境阻塞、或顺序污染。需要一份持续维护的 baseline-failure registry（见 Issue 待办）。

### Skip / xfail

- xfail：0
- skip：27。主要原因：PostgreSQL 合同需要 `TEST_POSTGRES_DATABASE_URL`；Windows mutex/Job Object/Credential Manager；`Migration 004 is intentionally absent in Phase 1`。
- 前端 Vitest 本轮无 skip。

### 未执行

- Playwright visual / acceptance / p0 / v061
- 真实 PostgreSQL full suite、备份/恢复
- 真实 Provider 请求
- DesktopHost DH-01–DH-08 Windows 窗口证据
- GitHub Actions 仓库自有 CI（仓库无 `.github/workflows`）

本轮不把未执行写成通过，也不把环境错误写成业务失败。V1.0 / DH-01–DH-08 / Release Gate 状态未改变。

## Issue #14 Batch 2A（clean regression foundation, 2026-08-29）

本段只记录 Batch 2A 真实执行。数量绑定到 SHA `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9`。不是 V1.0 证明。逐项失败见 `docs/baseline_failure_registry.md`。

| 字段 | 值 |
| --- | --- |
| 基线 | `origin/main` `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9` |
| 日期 | 2026-08-29 |
| 环境 | Linux 隔离沙箱；Python 3.11.2；Node 22；`STORAGE_BACKEND=file` |
| 安装 | `uv pip install -e .[dev]`（未安装 `.[vault]`） |
| 隔离 | `.runtime/pytest-temp/batch2a-before` 与 `batch2a-after2` |
| 未使用 | 用户 `.env`、用户数据库、真实 Provider 密钥、真实 PostgreSQL |

| 检查 | 命令 | 退出码 | BEFORE | AFTER |
| --- | --- | ---: | --- | --- |
| 后端全量 | `python -m pytest -p no:cacheprovider --basetemp=<run-temp> -q -ra --tb=line` | 1 | 766 passed, 36 failed, 27 skipped, 0 xfail；23.41s | 798 passed, 4 failed, 27 skipped, 0 xfail；22.60s |
| 前端 Vitest | `npx vitest run`（`frontend/`） | 0 | — | 376 passed / 89 files |
| TypeScript | `npx tsc -b` | 1 | — | 三个既有 frontend 测试文件 unused `@ts-expect-error`；本批未改 frontend。该失败其后未能稳定复现 |
| Vite bundle（当时误标为 production build） | `npx vite build` | 0 | — | Vite 打包通过。canonical `pnpm run build`（`tsc -b && vite build`）未按该名记录 |
| 工作区 whitespace | `git diff --check HEAD` | 0 | — | 本批相对 HEAD 无新增空白问题 |

AFTER 仅剩四个 `PRODUCT_BASELINE` 生产缺陷（本批明确未修）：并发生成幂等、visual continuity `TIME_JUMP_CUT`、user preference `harness_enabled`、world rule `forbidden_terms`。夹具失败、settings 顺序污染、Linux/Windows 平台误分类已从失败计数中移除。该表中的 798/4 是实施会话单次聚合，不是唯一稳定 AFTER。

## Issue #14 Batch 2A.1（review P1 corrections, 2026-08-29）

独立 Reviewer 对 Draft PR #19 的两项 P1：Linux `AttributeError` 不当 PASS、全局 memory vault 掩盖生产默认选择。两项证据口径：798/4 不是稳定 AFTER；`npx vite build` 不能写成 canonical production build。

| 字段 | 值 |
| --- | --- |
| 基线 / PR HEAD before 2A.1 | merge-base `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9`；`da6fb6c6f92856df4ed4b099e3841bbc2040c9db` |
| 本轮测试提交 | `b711611af5a2d3a52e3b789366e6656ab172e26d` |
| `origin/main` | 已前移（PR #12 合入 `e4dd24a`）。本分支 **未** rebase 到该 tip，也未改 PR #12 |
| 端口 | 删除 Linux `AttributeError` 成功断言；Windows exclusive bind 在非 Windows 上 skip |
| Vault | 删除全局 `CREDENTIAL_VAULT_BACKEND=memory`；control-pipe 窄范围注入；`CredentialVault()` 默认请求 `auto` |
| 并发隔离 | 0 pass / 20 fail |
| 污染 predecessor+targets | PASS；targets ×10 = 10/10 |

| 后端全量 | passed | failed | skipped | xfail |
| --- | ---: | ---: | ---: | ---: |
| 2A 实施 AFTER | 798 | 4 | 27 | 0 |
| 独立 Reviewer HEAD | 799 | 3 | 27 | 0 |
| 2A.1 run 1 | 799 | 4 | 28 | 0 |
| 2A.1 run 2 | 799 | 4 | 28 | 0 |
| 2A.1 run 3 | 799 | 4 | 28 | 0 |

三次 2A.1 全量失败节点相同：并发生成幂等、visual continuity、user preference、world rule。`NEW FAILURES = 0` 只表示没有新的未分类独立回归。

| 前端检查 | 口径 | 2A.1 本轮 | 独立 Reviewer |
| --- | --- | --- | --- |
| Vitest | `pnpm exec vitest run` | 376 passed / 89 files，exit 0 | 376 / 89，exit 0 |
| Typecheck | `tsc -b` | exit 1，三文件 unused `@ts-expect-error` | exit 0 |
| Vite bundle | `vite build` | exit 0 | exit 0 |
| Canonical build | `pnpm run build` = `tsc -b && vite build` | exit 1 | exit 0 |

Typecheck 不是稳定基线。未改 frontend。Vite bundle PASS ≠ canonical production build PASS。未执行 Windows / PostgreSQL / Provider / DH-01–DH-08。V1.0 未发布。

## Batch 2A.2 base snapshot（PR #12 merged, SHA `e4dd24a`, 2026-08-29）

本段是 **Batch 2A.2 工作起点快照**，绑定 SHA `e4dd24a682d2338d3aaf9ffa6880cbb1e364e6ac`。不要把上面绑定 `46bee8f` / `d8174af` 的数量称作该快照，也不要把本段称作 live current-main。

独立 worktree 验证：Python 3.11.2；`uv pip install -e .[dev]`（未装 `.[vault]`）；`STORAGE_BACKEND=file`；`env -i`；run-scoped TMP/basetemp；未读用户 `.env`。前端：仓库 `frontend/pnpm-lock.yaml`，pnpm `--ignore-workspace`（既有 `pnpm-workspace.yaml` 无 `packages` 字段）。

| 检查 | 命令 | 退出码 | 结果 |
| --- | --- | ---: | --- |
| 后端全量 | isolated `python -m pytest -p no:cacheprovider --basetemp=<run-temp> -q -ra --tb=line tests` | 1 | 868 passed, 36 failed, 27 skipped, 0 xfail；25.50s |
| 前端 Vitest | `pnpm --ignore-workspace exec vitest run` | 0 | 394 passed / 89 files |
| Typecheck | `pnpm --ignore-workspace exec tsc -b` | 1 | unused `@ts-expect-error`：`Editor.typography.test.ts:2,4`、`ChapterTree.css.test.ts:2,4`、`FeatureLauncher.css.test.ts:2,4` |
| Vite bundle | `pnpm --ignore-workspace exec vite build` | 0 | `frontend/dist/` Vite 打包，不是安装包 |
| Canonical build | `pnpm --ignore-workspace run build`（`tsc -b && vite build`） | 1 | 被 tsc 挡住 |
| whitespace | `git diff --check` | 0 | 干净 |

868 − 766 = 102，对应 PR #12 三个 plugin 测试文件在本轮全部通过。36 个失败节点与历史 `d8174af` BEFORE 相同（夹具 / 顺序污染 / 平台 / 可选依赖 / DATABASE_URL 字符串 / 三个 PRODUCT_BASELINE）。并发生成幂等本轮聚合未列入 FAILED（flake）。Typecheck 不是稳定基线。Vite bundle PASS ≠ canonical production build PASS。

## Issue #14 Batch 2A.2（integration onto `e4dd24a`, 2026-08-29）

把 Draft PR #19（`407b74a`）用普通 `--no-ff` merge 合入当时的 Batch 2A.2 base `e4dd24a`。Merge commit `b15b58a`。相对该快照的 PR delta 只有 tests / fixtures / docs。PRODUCTION / FRONTEND / SCHEMA = 0（以 `e4dd24a` 为基准）。未改四个生产缺陷，未改 PR #12 生产代码。

| 字段 | 值 |
| --- | --- |
| Batch 2A.2 base snapshot | `e4dd24a682d2338d3aaf9ffa6880cbb1e364e6ac` |
| Pre-integration PR HEAD | `407b74a628db1ca26b7ced79647a563e64bc7cd7` |
| Merge | `b15b58a30f29f019c70cb33485619d78d59b8a3f` |
| 环境 | 全新 clean clone + 独立 main worktree；Python 3.11.2；pnpm 9.15.0 |
| 并发隔离 | 1 pass / 19 fail（20 次；不要挑最好结果） |
| 污染 predecessor+targets | PASS；targets ×10 = 10/10 |
| Plugin + conftest | 102 passed；正序 5/5；反序 5/5 |

| 后端全量 | passed | failed | skipped | xfail |
| --- | ---: | ---: | ---: | ---: |
| Batch 2A.2 base | 868 | 36 | 27 | 0 |
| Integrated run 1 | 901 | 4 | 28 | 0 |
| Integrated run 2 | 901 | 4 | 28 | 0 |
| Integrated run 3 | 901 | 4 | 28 | 0 |

三次集成全量失败节点相同：并发生成幂等、visual continuity、user preference、world rule。`NEW FAILURES = 0`。HEAD 比该快照多 1 个诚实 skip（Windows exclusive ports）。

| 前端检查 | 口径 | Batch 2A.2 base `e4dd24a` | Integrated HEAD |
| --- | --- | --- | --- |
| Vitest | `pnpm exec vitest run` | 394 / 89，exit 0 | 394 / 89，exit 0 |
| Typecheck | `tsc -b` | exit 1 unused `@ts-expect-error` | exit 1 同样三文件 |
| Vite bundle | `vite build` | exit 0 | exit 0 |
| Canonical build | `pnpm run build` = `tsc -b && vite build` | exit 1 | exit 1 |

Typecheck 不是稳定基线。未改 frontend。未执行 Windows / 真 PostgreSQL / 真 Provider / DH-01–DH-08。V1.0 未发布。Draft PR #19 当时保持 Draft，不合并，不关 Issue #14。

## Issue #14 Batch 2B-1 / 2B-1.1（generation idempotency, 2026-08-29）

结论仍是 **TEST_STATE_CONTAMINATION_RECLASSIFIED**，不是生产竞态。未改生产代码。未改 frontend。未关 Issue #14。未改 Issue #20。Batch 2B-1.1 只校正文档锚点。

快照：

| Snapshot | SHA |
| --- | --- |
| Task base / post-PR-19 main at work start | `01cc304e3df5357160f3c98b2ef50b0d9ddf8d95` |
| Implementation / evidence HEAD | `5e7ab893aa09db08d0d9566e65e0edeb0e3c46d7` |
| First-review main (PR #21 merged) | `47906bdde775d4ab9c7a07449c1f60f0e4e5d300` |
| First-review synthetic merge | `9f97c40c176bd5fd2a6f9a64bd4f4da7dd95ff2b` |
| Correction-start main (PR #23 merged) | `bc49b5d05ee934d948ab8784d52ba4481134ec0d` |

`bc49b5d` 只是本次文档校正开始时的 main snapshot，不是永久 current-main。`9f97c40` 不是 PR #23 之后的合并候选。

根因：目标测试固定 `Idempotency-Key: generation-race-unique`，`app.api._idempotency_store` 在 import 时指向仓库 `novel_data/idempotency.json`。第一次独立进程写入成功缓存后，后续进程 `jobs.create==0` 被误判为失败。缓存命中且不再 create 是正确幂等行为。

实现树（仅 `01cc304e` + `5e7ab89`）：

| 检查 | 结果 |
| --- | --- |
| 原测试 20 次独立进程（修改前） | 1 PASS / 19 FAIL；FAIL 时键已存在且 `created_len=0` |
| 全新 Store 并发 | 3×50、16×20、32×10 = 80/80 PASS |
| 持久化重放 | 返回缓存；`jobs.create==0` |
| 目标测试 20 次独立进程（隔离后，残留键仍在） | 20/20 PASS |
| 100-round fresh-store stress | 100/100 PASS（suite 内） |
| 后端全量 1 | 909 passed, 3 failed, 28 skipped, 0 xfail；27.14s |
| 后端全量 2 | 909 passed, 3 failed, 28 skipped, 0 xfail；24.27s |
| 算术 | 909 = 901 passing + 1 重分类并发节点 + 7 个新合同测试 |
| 收集规模 | task base 933；implementation HEAD 940 |

不要把 `909/3/28` 称作 PR #21、PR #23 或 live main 结果。该树上剩余三个 PRODUCT_BASELINE（未改）：visual continuity `TIME_JUMP_CUT`、user preference `harness_enabled`、world rule `forbidden_terms`。并发幂等节点不在 FAILED 集合。

首次独立审查（仅 `9f97c40`，parents `47906bd` + `5e7ab89`，PR #23 之前）：

| 检查 | 结果 |
| --- | --- |
| 后端全量 1 | 960 passed, 4 failed, 28 skipped, 0 xfail；27.42s |
| 后端全量 2 | 960 passed, 4 failed, 28 skipped, 0 xfail；25.49s |
| 收集规模 | first-review main 985；synthetic merge 992 |
| PR #21 / PR #22 文件重叠 | 0 |
| Plugin + idempotency 正序 / 反序 | 5/5 60 passed / 5/5 60 passed |
| PR #22 可归因 NEW FAILURES / SKIPS / XFAILS | 0 / 0 / 0 |

四个失败必须拆开：三个已知产品缺陷，加上 `tests/test_import_parsers.py::test_pdf_fallback_extracts_simple_literal_text`（`ENVIRONMENT-SENSITIVE BASELINE / INVESTIGATION REQUIRED`）。后者在 `01cc304e`、`47906bd`、`5e7ab89`、`9f97c40` 上相同出现，与残缺 PDF fixture 和审查环境中的 `pypdf` 行为有关；不是 PR #22 引入，不计入 PR #22 产品回归，本批未修、未开 Issue、不记录未证实的 pypdf 版本。不得写成四个剩余产品缺陷。PR #21 增加了 official declarative plugin pack 测试，因此不能要求该 merge 仍显示 `909/3/28`。

PR #23 之后（校正开始快照 `bc49b5d`）：

| 检查 | 结果 |
| --- | --- |
| PR #23 / PR #22 文件重叠 | 0 |
| Runtime 交互 / 新 synthetic-merge 全量 | `PENDING NEW INDEPENDENT RE-REVIEW` |

不得把 `960/4/28` 复制成 PR #23 后结果，也不得预测新计数。

Frontend delta = 0。工具链不确定性归 [Issue #20](https://github.com/1785235376-blip/AI-Novel-Studio/issues/20)，本批不修。

V1.0 / DH-01–DH-08 / 真 PostgreSQL / 真 Provider / Release = 未宣称通过。

## Issue #14 Batch 2B-2 — visual continuity TIME_JUMP_CUT

本段绑定任务基线 `9f210b7117c14d418a7f57d8976568cd5506125a`（PR #22 合并后的 main 快照）与实现 HEAD `47a080fae2c8e45d595c8ffe6a742492c77c5acd`。不是永久 current-main。证据见 `docs/issue14_batch2b2_visual_continuity_report.md`。

根因：helper 只在 `transition.upper()=="CUT"` 时报告 `TIME_JUMP_CUT`；缺省 / 空 / `None` 本就是产品默认剪切。service 只把原始 shots 交给 helper，既没有 scene 的 time，也没有 `screenplay["transitions"]`。

| 检查 | 结果 |
| --- | --- |
| 目标测试修改前 | FAIL；实得 `{LOCATION_JUMP, EMOTION_DISCONTINUITY}` |
| 目标测试修改后 | PASS |
| Helper 矩阵 / service 只读 enrichment | PASS |
| 定向 50 次 | 50/50，每次 12 passed |
| 后端全量 1 | 1024 passed, 2 failed, 28 skipped, 0 xfail；26.17s |
| 后端全量 2 | 1024 passed, 2 failed, 28 skipped, 0 xfail；25.38s |
| 收集规模 | 1054 |

剩余产品失败两个（未改）：

- `tests/test_user_preference_service.py::test_preferences_are_explicit_and_separate`
- `tests/test_world_rule_payload.py::test_world_rule_payload_normalizes_terms`

本环境未复现 PDF fallback。Issue #14 继续 OPEN。Issue #20 未改。Frontend / schema / migration = 0。V1.0 / DH / Release 未宣称通过。
