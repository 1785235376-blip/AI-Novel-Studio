# 社区与 Alpha 交付交接（2026-10-19）

本文件汇总本轮综合工程化任务（许可证 + Alpha Tag + 本地最小 CI + 社区基建 + 缺陷修复）的
**实际结果、证据链接、人工待决策项与剩余问题**。不取代 [RELEASE_GATES.md](RELEASE_GATES.md)、
[BASELINE_20261019_r1.md](BASELINE_20261019_r1.md) 或需求矩阵；V2 仍未正式发布。

## 1. 仓库与权限边界

- 仓库：<https://github.com/1785235376-blip/AI-Novel-Studio>（public，默认分支 `main`，本轮开始时无分支保护/无 ruleset/无 tag）
- 本轮开始基线：`main` = `fed2404c8e30b44061b7139dced45b7f3301601c`；V2 开发分支 `feature/v2-narrative-platform` = `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3`；工程基线 `work/v2-eng-baseline-20261019` = `b0917977b7dd0e1ba092e3c6ec11b98fed0a4005`
- 授权范围：仅 LICENSE/许可说明的 `main` 窄范围提交 + 在含许可证的 `main` 快照上创建 annotated `v0.1.0-alpha` Tag；其余工程成果全部走独立分支/Draft PR，不合并 `main`。

## 2. 已完成事项

### 2.1 许可证（main）

- 许可证：**Apache License 2.0**（SPDX `Apache-2.0`），标准正文 11,357 B，SHA256 `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`
- 权利依据：仓库 Git 历史提交均来自 `1785235376-blip` 或其自动化 Agent；首次提交 2026-08-26；未虚构法定名称（版权行使用可核对的 GitHub 账户标识）
- 边界文档：[LICENSING_AND_THIRD_PARTY.md](../../../LICENSING_AND_THIRD_PARTY.md)：用户作品（`novel_data/` 未入库）、模型权重、字体（Noto Sans SC OFL 1.1，字体二进制不入库）、第三方依赖按各自许可证，均不在本项目许可证覆盖范围内
- 依赖兼容性审查：后端/前端直接依赖均为 MIT/BSD/Apache-2.0/ISC/LGPL-3.0（仅 psycopg 为 LGPL，作为独立库使用），未见被复制进仓库的第三方源码
- main 提交：`a9016356d0ede797b1e870d7749eb24f05bfd462`（LICENSE/NOTICE/许可边界/README 许可说明）
  <https://github.com/1785235376-blip/AI-Novel-Studio/commit/a9016356d0ede797b1e870d7749eb24f05bfd462>
- GitHub 许可证识别：`gh repo view --json licenseInfo` 返回 `{"key":"apache-2.0","name":"Apache License 2.0"}`

### 2.2 Alpha 锚点（main）

- Tag：`v0.1.0-alpha`（**annotated**，tag object `17a9e056d0ae5c265c90f919e40812464d38cbf8`）
- Tag 目标：`7b35e4cb4bd9efabe7cff54e67d7b24e8e469385`（main；许可证提交之后，早于任何未来大型功能合并）
  <https://github.com/1785235376-blip/AI-Novel-Studio/tree/v0.1.0-alpha>
- 说明文档：[ALPHA_BASELINE_NOTES.md](../../../ALPHA_BASELINE_NOTES.md)：功能不完整，**不是 V1.X RC1、不是 V2 正式版、不是产品验收 PASS**；无 GitHub Release、无安装包、无 force push、无覆盖既有 tag
- 版本政策：内部权威版本仍为 `release/version.json = 0.7.0`（channel `beta`）；`scripts/validate_release_version.py` 在 Tag 快照上重新执行通过；仓库**不存在** `tag == version` 门禁，因此不以 Tag 篡改内部版本、不制造正式发布记录

### 2.3 本地最小 CI（独立分支 / Draft PR #49）

- 入口：[LOCAL_CI_MINIMUM.md](LOCAL_CI_MINIMUM.md) + `scripts/run_local_ci.py`（LOCAL-01～05，分步命令；非一键安装/启动/部署）
- 实际结果：**LOCAL_CI_PASS**（round-2 干净环境复跑），运行时 HEAD `7e1ea003c975f585a26201e007f8e4a7872c7ee2`，五步总耗时 **351.9 s**；证据与复现见 [LOCAL_CI_RESULTS_20261019.md](LOCAL_CI_RESULTS_20261019.md)
- 明细与证据：[LOCAL_CI_RESULTS_20261019.md](LOCAL_CI_RESULTS_20261019.md)；证据目录 `docs/v2/engineering/evidence/local-ci/20261019-final/`（JUnit/logs/真实浏览器截图，绝对主机路径已脱敏）
- 覆盖：真实 uvicorn + `/health`（8.8 s）；pytest 941 tests / 473 passed / 0 failed（222.5 s）；Vitest 4307 passed + `tsc -b && vite build` + 设计 token（71.0 s）；真实 uvicorn+File+Vite+系统 Edge 的 2 个保存/重读旅程（33.7 s）；清理与残留检查（10.9 s，无残留端口/进程、删除本轮 runtime 55,093,742 B）

### 2.4 缺陷修复 D-21（真实、可复现）

- 现象（修复前，Windows 真实复现）：live Playwright 配置的 webServer 命令 `... 2>&1 | tee<log>` 在 `cmd.exe` 报 `'tee' is not recognized`，`Process from config.webServer was not able to start. Exit code: 255`，0 个测试执行 → 阻塞 LOCAL-04
- 根因：配置层使用 POSIX shell 语法；Playwright 在 Windows 用 `cmd.exe`。同一配置缺省还指向 POSIX-only `.venv/bin/python`
- 修复：`frontend/local-ci-server-command.ts`（平台感知的日志重定向与解释器解析），`playwright.v2-live.config.ts` 与 `playwright.independent-live.config.ts` 复用；未改断言/skip/超时/产品行为
- 回归：`frontend/tests/localCiServerCommand.test.ts` 4 tests PASS（包含在 LOCAL-03 全量 Vitest 中）；两 config `--list` 可加载（14 / 18 tests）；LOCAL-04 真实旅程 2 passed
- 记录：[DEFECTS_20261019_r1.md](DEFECTS_20261019_r1.md) D-21（含复现命令、修复文件、回归证据）

### 2.5 社区基建（独立分支 / Draft PR #49）

| 交付物 | 路径 | 验证 |
| --- | --- | --- |
| 贡献指南 | [CONTRIBUTING.md](../../../CONTRIBUTING.md) | 按真实源码/脚本编写；Windows 为实测，Linux/macOS 明确标注 THEORETICAL_NOT_RUN |
| 架构总览 | [ARCHITECTURE.md](../../ARCHITECTURE.md) | 组件关系 Mermaid、单一权威、三类图语义、版本/CAS/权限、媒体流水线、Image Studio → 漫画归属、模块状态 |
| Bug Issue Form | `.github/ISSUE_TEMPLATE/bug_report.yml` | PyYAML 真实解析 + 结构校验 PASS（必填 SHA/OS/复现/实际/预期/数据影响/脱敏确认） |
| Feature Issue Form | `.github/ISSUE_TEMPLATE/feature_request.yml` | 同上（场景/缺口/期望/影响模块/验收/兼容/资源预算） |
| Issues 配置 | `.github/ISSUE_TEMPLATE/config.yml` | 关闭 blank issue，提供安全私下报告与文档入口 |
| 模板校验 | `scripts/validate_issue_templates.py` | 无 PyYAML 时 BLOCKED、有 PyYAML 时 PASS/FAIL；本轮实跑 PASS |
| README 入口 | [README.md](../../../README.md) | 社区入口 + 本地 CI 手工步骤 + 已知限制 + Alpha 说明 |

## 3. 独立分支与人工审核

- 分支：`work/v2-local-ci-community-20261019`（基于 `origin/work/v2-eng-baseline-20261019`，15 commits：`4e130e5e`、`38835e78`、`a93ad4b1`、`154d5c36`、`d73423c7`、`602744c7`、`1e83a2ca`、`6afae9ca`、`a517e0a2`、`29525179`、`a6b0da6e`、`36fe7f34`、`0a375bbf`、`a6630f51`、`7e1ea003`）
- Draft PR：**#49** <https://github.com/1785235376-blip/AI-Novel-Studio/pull/49>（base `work/v2-eng-baseline-20261019`，draft，未合并）
- 未做：未合并 `main`、未删除分支、未修改 required checks/CI 政策、未创建 Release、未发布 V2、未新增 Docker Compose/一键启动/一键部署

## 4. 明确未执行 / 阻塞项（不要误读为通过）

| 项 | 真实状态 | 说明 |
| --- | --- | --- |
| 完整 File 后端套件 | 未在本轮重跑 | 历史完整运行约 1.5 万条；LOCAL-02 只是代表性切片 |
| 完整真实 PostgreSQL 套件 | BLOCKED_ENVIRONMENT（D-07） | 当前 Windows 主机 PG 环境限制；仅历史代表性 PG 子集通过 |
| 宿主 CI | HOSTED_BLOCKED_NO_RUNNER | 历史 Actions runner 未真实启动；保留原 workflow，本地 PASS 不冒充 |
| 真实浏览器全量 | PARTIAL | 仅 2 个真实旅程通过；creative 全量/visual/geometry/其他 live 族未执行 |
| independent-live 浏览器族（M3/M4/M4-B） | 未执行 | 仅验证其 config 可加载（18 tests 可发现） |
| 本地模型/GPU/真实 AI 质量 | NOT_RUN / LOCAL_REQUIRED | 未授权模型，未调用收费 API，未下载权重 |
| 真实媒体（FFmpeg 产物） | 未在本轮重跑 | 属完整媒体验收层 |
| Windows 安装/升级验收 | NOT_RUN | 属 RELEASE_GATES G9，需用户机器与授权 |
| Linux / macOS 开发环境说明 | 理论可用，未实测 | CONTRIBUTING 已如实标注 |
| V2 正式发布 | NOT RELEASE_READY | DIF-01–12、IMAGE-COMIC-01–20 等仍未完成，见 RELEASE_GATES |

## 5. 剩余工程问题（建议下一轮处理）

1. **PG 完整套件**（D-07）需要在干净 Windows/Linux runner 上复现并确认是否纯环境问题。
2. **D-10 / D-17 / D-20** 仍是 OPEN/HARNESS：creative-workbench 浏览器套件前置条件、Windows 撤销时序间歇失败、interop universe 全套件挂起；建议加 pytest-timeout/faulthandler 仪器化定位。
3. **宿主 CI 恢复**：需要可用 runner/账户；恢复后用同一 LOCAL-01～05 映射到 hosted job，并保留真实 run URL。
4. **独立浏览器族**：把 independent-live 的 M3/M4/M4-B 套件纳入可执行矩阵并在真实主机上执行。
5. **Issue 模板校验的依赖**：`scripts/validate_issue_templates.py` 需要可选的 PyYAML；是否把它加入 dev 依赖由人工决定（本轮未改 pyproject）。
6. **main 分支保护**：当前 `main` 无分支保护/ruleset；是否启用 required checks/保护由项目所有者决定（本轮未改动）。

## 6. 复跑与核对命令

```powershell
# 本地最小 CI（分步；在已准备依赖的 worktree 中）
python scripts/run_local_ci.py --step LOCAL-01
python scripts/run_local_ci.py --step LOCAL-02
python scripts/run_local_ci.py --step LOCAL-03
python scripts/run_local_ci.py --step LOCAL-04
python scripts/run_local_ci.py --step LOCAL-05

# 许可证 / Tag 核对
git fetch --all --tags
git cat-file -t v0.1.0-alpha                 # tag（annotated）
git rev-list -n 1 v0.1.0-alpha               # 7b35e4cb…
git show origin/main:LICENSE | Select-Object -First 3

# Issue 模板校验（可选：python -m pip install pyyaml）
python scripts/validate_issue_templates.py
```

## 7. 清理与磁盘

- LOCAL-05 已删除本轮 runtime 数据 55,093,758 B；证据保留 1,717,589 B（脱敏后提交 1,695,622 B）
- 仅删除本轮自建、路径受控的目录；未删除用户数据、模型、RC1、历史证据或其他 worktree
- 保留的独立工作目录（`<workspace>/Worktrees/`）：工程基线、许可证/main、本分支，以及本轮之前已存在的其他 worktree

## 8. Round-2 quality special（2026-10-19）

- **LOCAL-02 skip 审计**：468 个 skip = 467 PostgreSQL 契约 + 1 Windows symlink；PG-only 函数 0；清单见
  [LOCAL_CI_COVERAGE_20261019.md](LOCAL_CI_COVERAGE_20261019.md)。
- **D-07 修复**：定位为无界同步连接风暴（单测试 1,210 连接）+ Windows error 487；改为复用 SQLAlchemy 池
  （commit-on-exit 语义保持）+ 有界连接/重试；此前阻塞节点 3/3 PASS、interop 文件 PASS、连接数 5。
  完整 PG 套件仍待长跑；curated 子集中的 27 个失败是既有 D-24（non-fix 回归），保持 OPEN。
- **D-10**：在 b0917977 上 8/8 通过两次 → CLOSED / NOT REPRODUCIBLE。**D-17**：24 passed/24 skipped，未复现，
  保持 MITIGATED。**D-22/D-23**：证据 XML 脱敏与 GBK 输出崩溃已修复并有回归测试。
- **干净环境复现**：重建 node_modules 与 .venv-repro 后五步全 PASS（见结果文档）；Linux/WSL 实测 =
  NOT_RUN（缺 Node 与 python3-venv 且无 sudo 密码），未伪造。
- **D-24（新，OPEN）**：PG 模式下 M4 mock graph-text worker 的 terminal hook 不触发（27 个 [postgres] 节点）；
  在 a517e0a2 上同样复现，阻塞完整 PG 套件，需要下一轮仪器化。
