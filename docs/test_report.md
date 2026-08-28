# Test Report

覆盖 Context 人物选择、Cloud Secret 省略/脱敏、年龄冲突、死亡人物、Secret Leak、Provider 回退、原子写入和 Pending Canon 闭环。

> 以下 V0.1–V0.4.8.1 段落是历史记录，不是 current `main` 的回归证明。当前结果见文末「Current main（safe maintenance 2026-08-28）」。

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

## Current main（safe maintenance 2026-08-28）

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
| TypeScript | `npx tsc -b` | 1 | — | 三个既有 frontend 测试文件 unused `@ts-expect-error`；本批未改 frontend |
| 前端 production build | `npx vite build` | 0 | — | 通过（`frontend/dist/`，不是安装包） |
| 工作区 whitespace | `git diff --check HEAD` | 0 | — | 本批相对 HEAD 无新增空白问题 |

AFTER 仅剩四个 `PRODUCT_BASELINE` 生产缺陷（本批明确未修）：并发生成幂等、visual continuity `TIME_JUMP_CUT`、user preference `harness_enabled`、world rule `forbidden_terms`。夹具失败、settings 顺序污染、Linux/Windows 平台误分类已从失败计数中移除。新 skip/xfail = 0。
