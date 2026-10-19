# 贡献指南（CONTRIBUTING）

感谢参与 AI-Novel-Studio / PoemSeed Studio。本项目是**本地优先**的长篇小说生产系统：
PostgreSQL 保存已批准事实，Markdown 保存正文，本地/云端模型只是可替换计算能力。

本文件只描述**当前真实存在**的工程入口与规则；没有经过实测的系统会在对应小节明确标注。
本阶段不提供 Docker Compose 或任何一键安装/一键启动/一键部署方案（统一在 V2 功能完成后处理）。

- 许可证：[LICENSE](LICENSE)（Apache-2.0）；边界与第三方声明见 [LICENSING_AND_THIRD_PARTY.md](LICENSING_AND_THIRD_PARTY.md)
- 架构入口：[ARCHITECTURE.md](ARCHITECTURE.md)
- 工程规范与运行手册：`docs/v2/engineering/README.md`、`docs/v2/engineering/RUNBOOK.md`
- 本地最小 CI：[docs/v2/engineering/LOCAL_CI_MINIMUM.md](docs/v2/engineering/LOCAL_CI_MINIMUM.md)
- 缺陷台账：`docs/v2/engineering/DEFECTS_20261019_r1.md`
- 发布门禁（未发布，仅定义）：`docs/v2/engineering/RELEASE_GATES.md`

## 0. 当前阶段（务必先读）

- **V2 尚未正式发布**。README 内部版本仍是 `0.7.0`（V0.7.0 Engineering Edition，
  `release/version.json` channel `beta`）。
- Git 注释标签 `v0.1.0-alpha` 只是**早期公开工程源码快照锚点**，不是 V1.X RC1、不是 V2 正式版、
  也不是产品验收 PASS。详见 [ALPHA_BASELINE_NOTES.md](ALPHA_BASELINE_NOTES.md)。
- V2 功能开发持续进行（`feature/v2-narrative-platform` 及其 work 分支）。**不要**冻结 feature 分支、
  关闭 PR #47/#48、重置工作树或改写他人分支。
- V1.X / RC1 的已冻结数据与契约不可破坏（见 `V1_SCOPE_FREEZE.md`、`docs/v1_implementation_status.md`）。

## 1. 提交 Issue

使用 GitHub Issue 模板（`.github/ISSUE_TEMPLATE/`）：

- **Bug report**（`bug_report.yml`）：必须给出提交 SHA、操作系统、实际结果/预期结果、最小复现步骤、
  脱敏日志、是否涉及数据损坏。
- **Feature request**（`feature_request.yml`）：必须给出用户场景、当前缺口、期望能力、影响模块、
  可验收标准、兼容性与资源预算。
- 非公开安全问题不要发 Issue，见第 7 节。

不要在 Issue/PR 中粘贴 API Key、凭据、真实小说正文、个人绝对路径或数据库连接串。

## 2. 分支与 Pull Request 策略

当前远端事实（2026-10-19 核对）：`main` 是默认分支，历史上存在一组级联的 Draft PR；
PR #47 以 `main` 为 base（head: `feature/v2-narrative-platform`），PR #48 以该 V2 分支为 base。

规则：

1. **不要**直接把功能代码推到 `main`；`main` 的功能合并由项目所有者决定。
2. 从**当前**目标分支切出短生命周期分支：`feature/<域>-<主题>`、`fix/<缺陷ID>-<主题>`、
   `work/<任务>-<日期>`、`docs/<主题>`；分支名只用小写字母、数字、`-`、`/`。
3. 不要 rebase/重写他人分支或已推送历史；不要 force push；不要删除他人分支或 worktree。
4. 级联 PR 需要说明上下游关系（base/head、依赖哪个 PR、合并顺序），并在描述中写明"不合并 `main`"。
5. 一般改动以 Draft PR 提交人工审核；只有项目所有者可以决定合并、required checks、分支清理与发布。

## 3. Commit 与 PR 内容规范

沿用仓库既有 Conventional Commits 风格（示例来自真实历史）：

```text
fix(scope): close legacy project authority and scope races
test(runtime): allocate loopback ports for owned-process fixtures
docs(engineering): record complete round-2 File-suite re-run and cleanup
feat(v2): add saved screenplay EPUB and explicit starter guides
```

- 一个提交表达一个可验证的意图；不要混入无关格式化或锁文件噪声。
- PR 描述至少包含：变更动机、影响模块/数据契约、复现或验收步骤、实际执行的命令与结果、
  未执行/被阻塞项、回滚方式。
- 新增/修改行为必须带回归测试；修复缺陷要先能复现失败，再修复，并给出修复前后证据。
- **禁止**为了让门禁变绿而删除测试、放宽断言、加无理由 skip/xfail、修改冻结哈希或伪造日志。
- 提交前本地自检（至少）：

```powershell
python scripts/run_local_ci.py --step LOCAL-01
python scripts/run_local_ci.py --step LOCAL-02
python scripts/run_local_ci.py --step LOCAL-03
python scripts/run_local_ci.py --step LOCAL-04
python scripts/run_local_ci.py --step LOCAL-05
```

（缺浏览器/依赖时对应步骤会明确 `BLOCKED_ENVIRONMENT`，不允许写成 PASS。）

## 4. 最小复现与测试要求

- Bug 修复 PR 必须包含：失败复现命令、根因说明、修改代码位置、修复后同命令通过证据。
- 测试分类保持仓库既有约定：`@pytest.mark.file_backend_only` / `postgres_backend_only` /
  `vault` / `vault_keyring_integration`；不要把 PG 契约悄悄改成 skip。
- 隔离环境：后端 pytest 必须在隔离 profile 下运行（`scripts/run_local_ci.py` 已内置），
  不要用真实用户 `novel_data`、RC1 工作区或其他 worktree 做测试。
- 完整验收层（不在最小 CI 内）：完整 File 套件、真实 PostgreSQL 套件、真实媒体/FFmpeg、
  真实浏览器全家、Windows 安装/升级、GPU 推理。这些层的 PASS/FAIL/BLOCKED 状态见
  `docs/v2/engineering/BASELINE_20261019_r1.md`、`TRIAGE_20261019_r3.md`、`DEFECTS_20261019_r1.md`。
- 无模型模式（`MOCK_PROVIDER=true`）是受支持路径；Mock 只能证明非模型业务行为，**不能**声称 AI 质量通过。

## 5. 代码风格

### 后端（Python）

- Python `>=3.11`，文件开头 `from __future__ import annotations`；类型标注与 dataclass 优先。
- 保持单一权威：Project/Novel/Chapter/Asset/Job/Review/Timeline/Model Center 各自 owner 不复制；
  不要把 DTO 或投影变成第二存储（见 `docs/v2/engineering/SINGLE_AUTHORITY_MAP.md`）。
- 版本/CAS 冲突必须是 CAS 语义；未知上游状态不得自动重放/重复计费。
- 文件读写显式 `encoding="utf-8"`（Windows CJK locale 缺陷来源）；生成契约使用 `newline="\n"`。
- 不新增不必要的第三方依赖；需要新依赖时在 PR 中说明许可证与体积，并更新
  `.github/ci/python-constraints.txt`。

### 前端（TypeScript / React）

- `strict` TypeScript；`pnpm run build`（`tsc -b && vite build`）必须通过。
- **UI Design System 强制**：先读 `docs/ui/design_system.md` 与 `docs/ui/protected_ui_surfaces.md`；
  复用 AppShell / ModuleWorkspace / 设计 token，不新增颜色或任意间距，不复制组件。
- 受保护的共享 NOVEL / IMAGE / VIDEO shell 与 V0.5.7 协作/冲突/修订/fail-closed 行为必须保持。
- 系统级 UI 变更需提交 `DESIGN SYSTEM CHANGE REQUEST` 并附视觉回归证据。
- 运行：`cd frontend; corepack pnpm test; corepack pnpm build; corepack pnpm lint`。

## 6. 开发环境（人工分步）

> 以下命令按操作系统分列。**本仓库本轮只在 Windows 11（10.0.26100）上实测过**；
> Linux/macOS 标注为 THEORETICAL_NOT_RUN_IN_THIS_ROUND，需在真实机器上验证后才可写成"已支持"。

### 6.1 Windows 11（本机实测）

依赖：Python 3.11+（实测 3.11.9）、Node `>=22.14 <25`（实测 22.14.0）、
pnpm 10.6.5（由 `frontend/package.json` 的 `packageManager` 决定，通过 corepack 调用）、
Git；可选：系统 Edge/Chrome（浏览器测试）、FFmpeg、PostgreSQL 16（完整 PG 验收）。

```powershell
# 1) 进入独立工作目录（不要用生产 checkout / 别人的 worktree）
cd D:\PoemSeed\Worktrees\v2-local-ci-community-20261019

# 2) Python 依赖（新建虚拟环境，避免污染全局环境）
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -c .github/ci/python-constraints.txt -e ".[dev,fontbuild,otio,comic]"
python -m pip check

# 3) 前端依赖（corepack 会使用 packageManager 指定的 pnpm 版本）
cd frontend
corepack pnpm install --frozen-lockfile
cd ..

# 4) 分步测试（见 docs/v2/engineering/LOCAL_CI_MINIMUM.md）
python scripts/run_local_ci.py --step LOCAL-01
python scripts/run_local_ci.py --step LOCAL-02
python scripts/run_local_ci.py --step LOCAL-03
python scripts/run_local_ci.py --step LOCAL-04
python scripts/run_local_ci.py --step LOCAL-05

# 5) 退出与清理
deactivate
# LOCAL-05 已删除 .runtime/local-ci/<run-id>；如需彻底清理本工作目录的本地环境：
Remove-Item -Recurse -Force .runtime      # 只删本工作目录下自建运行时数据
```

说明：如果 `.venv` 里的解释器与系统 Python 不同，可用
`$env:V2_PYTHON = ".\.venv\Scripts\python.exe"` 指定浏览器/后端测试用的解释器。

### 6.2 Linux（THEORETICAL_NOT_RUN_IN_THIS_ROUND）

```bash
# 依赖：python3.11+, node 22.x, corepack, git；可选 ffmpeg / postgresql-16 / chrome/edge
cd /path/to/AI-Novel-Studio
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -c .github/ci/python-constraints.txt -e '.[dev,fontbuild,otio,comic]'
python -m pip check
cd frontend && corepack pnpm install --frozen-lockfile && cd ..
python scripts/run_local_ci.py --step LOCAL-01
python scripts/run_local_ci.py --step LOCAL-02
python scripts/run_local_ci.py --step LOCAL-03
python scripts/run_local_ci.py --step LOCAL-04   # 需系统浏览器或 Playwright Chromium
python scripts/run_local_ci.py --step LOCAL-05
deactivate
rm -rf .runtime                               # 仅清理本仓库自建运行时数据
```

### 6.3 macOS（THEORETICAL_NOT_RUN_IN_THIS_ROUND）

```bash
# 依赖：python3.11+（如 brew install python@3.11）、node 22.x、corepack、git
cd /path/to/AI-Novel-Studio
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -c .github/ci/python-constraints.txt -e '.[dev,fontbuild,otio,comic]'
python -m pip check
cd frontend && corepack pnpm install --frozen-lockfile && cd ..
python scripts/run_local_ci.py --step LOCAL-01
python scripts/run_local_ci.py --step LOCAL-02
python scripts/run_local_ci.py --step LOCAL-03
python scripts/run_local_ci.py --step LOCAL-04   # 需 Chrome/Edge 或 Chromium
python scripts/run_local_ci.py --step LOCAL-05
deactivate
rm -rf .runtime
```

需要额外可信环境才能跑的层：真实 PostgreSQL（`BLOCKED_ENVIRONMENT` 时不要伪造成 PASS）、
真实 FFmpeg 媒体验证、真实浏览器全量旅程、Windows 安装/升级验收、GPU/本地模型执行。

## 7. 隐私与安全

- 安全漏洞请**私下**报告：通过 GitHub 仓库 Security 页的私有漏洞报告入口（如果已启用）或直接私信
  仓库所有者（GitHub 账号 `1785235376-blip`）。不要在公开 Issue 中披露利用细节、凭据或用户数据。
- 提交 Issue/PR/日志前脱敏：API Key、token、DATABASE_URL、真实小说正文、个人绝对路径、主机名。
- 仓库不包含用户小说与模型权重；不要把它们提交进 PR。
- 素材与第三方资源：提交字体、图标、模板、测试媒体、模型或代码片段时必须在 PR 中说明来源与许可证，
  并更新 [LICENSING_AND_THIRD_PARTY.md](LICENSING_AND_THIRD_PARTY.md)。无法确认授权的素材请勿提交。

## 8. 贡献者版权

提交 Pull Request 即表示：

1. 你有权提交该内容（原创，或已获得兼容授权并在 PR 中声明）；
2. 你同意该贡献按本仓库的 **Apache-2.0** 许可证（见 [LICENSE](LICENSE)）授权使用、修改与再分发；
3. 你理解项目不要求 CLA，但贡献记录会保留 Git 作者信息。

## 9. 提交前检查清单

- [ ] 变更真实运行过（附命令与结果），不是"应该可以"。
- [ ] 没有破坏单一权威、Project/Asset/Job/Review/Timeline/Model Center 边界。
- [ ] 没有削弱权限/存储/CAS/fail-closed 行为。
- [ ] 没有影响 V2 并行开发（未冻结/未改写他人分支）。
- [ ] 未新增不必要依赖，未新增 Docker/一键启动/一键部署内容。
- [ ] Windows 与非 Windows 说明准确，标注了实测/理论。
- [ ] 没有无法清理的临时文件或残留服务。
- [ ] 已更新相关文档（架构/运行手册/缺陷台账/许可边界）。
