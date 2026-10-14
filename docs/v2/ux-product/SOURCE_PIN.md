# UX-PRODUCT source-pin 摘要（phaseN 式）

本文件给出每一批的**输入固定点**：提交、远端、验收 harness 修订号与收据、以及"检查期间源码是否变动"的标志。口径与 `docs/delivery/v2-development/` 下收据一致；**只有 `sources_changed_during_check=false` 的收据才绑定到该提交的内容**。

授权目录：`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`（分支 `feature/v2-narrative-platform`，PR #47 保持 Draft）。
`main` 固定为 `fed2404c8e30b44061b7139dced45b7f3301601c`（本工作包**从未**合并/发布/打标签）。

## 固定点

| 批次 | 提交 | 内容 | harness 修订 | 收据绑定 |
| --- | --- | --- | --- | --- |
| 环境修复 | `400b522` | 前端 `python3` 跨平台解释器解析（独立提交 + 回归） | — | 测试套件本会话直跑（修复前 20 failed → 修复后 22 passed） |
| 批次 1 | `68ad8ef` | UX-01 入口/意图/模式 + UX-02 任务中心/审核（67 文件） | r1 / r2 | `ux-product-{file,frontend,types,build,tokens,seam}-r{1,2}.*` |
| （Phase8 文档） | `9ba3d77` | QingJian 接入准备文档（**仅文档，未联调**） | — | — |
| 批次 2 | `3023f9e` | UX-03 素材复用 + UX-04 画布/节点（65 文件） | r3（树在变动，不绑定）/ **r4**（冻结） | `ux-product-*-r4.*`，`sources_changed_during_check=false` |
| CONTENT_POLICY 预留 | `bda534a` | `CONTENT_POLICY_FRAMEWORK: RESERVED`（复用既有偏好 owner，wire 冻结） | — | `ux-policy-reservation.json`（File 54 passed/43 skipped）、`ux-policy-reservation-pg.json`（真实 PG 6 passed/1 skipped，fresh 库、20 迁移、空库证明、正常停止） |
| 缺陷修复 | `b7af80a` | 分类器 `(undefined, undefined)` 误判 PRESENTATION（验证线独立发现） | — | `src/canvasops` 94 tests、`tsc -b` 0 |
| 批次 3 | `25b5042` | UX-05 导演/分镜 + UX-06 多轨剪辑（80 文件） | r5（树在变动，不绑定）/ **r6**（冻结） | `ux-product-*-r6.*`，`sources_changed_during_check=false`；直跑 storyboard+nle+studio+creative 292 tests |
| 批次 4 | 待提交 | UX-07 模型中心/存储 + UX-08 项目提示助手 | r7（预期） | 待生成 |

| 批次 4 | `9c1c646` | UX-07 模型中心/存储 + UX-08 项目提示助手 | r8（冻结核对）/ **r9**（`src/delivery` 尚缺 → `frontend` 如实 NOT_YET_AVAILABLE） | `ux-product-*-r8.*`（七项 PASS，`frozen=True`）；`40caee6` 提交收据 |
| 批次 5 | `ccb7585` | UX-09 统一导出与工程交接（14 文件）+ 集成 | **r10**（冻结，批次 5 源码树）/ **r13**（冻结，最终 HEAD） | r10：七项全 PASS，`failed=0 / pending=0`，`frontend` 首次覆盖**全部九个** UX 目录；r13（`1eb2e2c`）：七项全 PASS，`frontend` 30 files / **643 tests**，作为本工作包**最终**冻结收据 |
| 收口 | `1eb2e2c` | S 表更正（`500c90f`）、批次 4/5 文档与矩阵 | r13（冻结） | 见上 |

## 关于 r10 / r12 / r13 的核对与分歧（Lead 亲自核对）

- **Lead 核对结果**：磁盘上的 `ux-product-*-r10.json` **七条全部** `sources_changed_during_check=false`（`frozen=True`），head 均为 `ccb758`；`ux-product-*-r13.json` 七条同样全部冻结，head 为 `1eb2e2`。
- **与最终验证线的分歧**：该线报告"`ux-product-build-r10.json` 的 `sources_changed_during_check=TRUE`"。**我核对磁盘文件后不能确认该说法**——当前 r10 的 build 收据显示 `frozen=True`。可能原因是该线读到了被后续运行覆盖前的中间状态。按证据优先原则，本文件**不采纳**该未被复现的说法，但**同时**采纳其更具约束力的主张：**最终冻结集以 r13 为准**（它绑定最终 HEAD，覆盖面更全）。
- **r12**（7 条收据存在）与 r11 均**不用于验收**：其 head 跨越提交，无法证明单次冻结。

## 冻结口径

- **冻结 = 检查期间无源码写入**：harness 每条收据都记录 `sources_changed_during_check`；为 `true` 的修订（r3、r5）**保留但明确不绑定**，不用于验收。r9 的 `frontend=NOT_YET_AVAILABLE` 为**正确**记录（当时 `src/delivery` 尚未落盘），不降级、不改写。
- **最终验收 = r13**（绑定 `1eb2e2c`）。
- **已知流程缺陷（已归档）**：修订 8 存在**两次并发运行**互相覆盖同一批收据（任务书 §15.3 违规，由 Lead 调度造成）；存留的 r8 不是单次无争用结果。批次 4 验证线亦记录：`types` 检查在**热 tsbuildinfo** 下偏弱（同文件 esbuild 已报错而它 PASS），因此批次 5 集成使用 `tsc -b --force` 复核（0 错误）。
- **收据不可改写**：历史收据与日志不删除、不覆盖；新结论以新修订号追加。
- **基线保护**：工作树中长期存在 39–41 个**既有未跟踪文件**（`docs/delivery/v2-development/phase6-*`、catalog JSON、`.graphflow-cache/`、`graphflow-out/`），属基线，**未提交、未清理**；所有提交均使用**显式路径** `git add`，从未 `git add -A`/`.`。
- **本工作包禁止动作**：`git reset --hard`、`git clean`、force push、删除旧 worktree/clone、merge main、release、deploy、tag —— 全部未执行。

## 运行时固定点（可复用资源）

| 资源 | 位置 | 说明 |
| --- | --- | --- |
| 便携 PostgreSQL 16.15 | `D:\PoemSeed\Builds\studio-v2-host-5ed1cbee-20261011\Base\PostgreSQL\bin` | 任务书 16.2 要求先在 Tools/脚本/收据中寻找可复用便携 PG；**找到并复用**，故 PG 为 CONFIGURED 而非 `NOT_CONFIGURED`（Phase7 的 `NOT_CONFIGURED` 作为历史保留） |
| owned 集群数据 | `<worktree>\.runtime\pg-ux-product\data` | 占位端口 55432、trust 认证、循环回环；每次运行后正常停止 |
| 验收 harness | `scripts/run_ux_product_checks.py` | `--checks file,postgres,frontend,types,build,tokens,seam,regression`；退出码 0 全 PASS / 1 任一 FAIL / 2 无 FAIL 但有 SKIPPED/NOT_YET_AVAILABLE |
| 隔离运行器 | `scripts/run_v2_checks.py`、`scripts/run_v2_postgres_checks.py` | 隔离 `.runtime/v2-checks/<label>` 环境与源码快照；PG 运行器要求集群位于 `<root>/.runtime` 内、非特权端口 |

## 已知边界（随每批复核）

- 前端令牌检查 `scripts/check_ui_design_tokens.mjs` **只扫描 `frontend/src/ui`**，因此 `tokens` 检查的 PASS **不覆盖**新增 UX 目录的 CSS；新目录的"仅令牌、无原始颜色"由验证线逐目录扫描确认（此为既有缺口，非本工作包引入）。
- 托管 CI 因账户账单锁从未启动（0 步），记为 `BLOCKED_ACCOUNT_PLATFORM`，**不**计为通过。
- 浏览器/视觉与几何验收、真实 Windows 安装版、GPU/真实模型、真实渲染、真实项目迁移：均为 `LOCAL_REQUIRED` / NOT_RUN。
