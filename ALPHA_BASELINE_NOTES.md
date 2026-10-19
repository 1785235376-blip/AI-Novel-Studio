# v0.1.0-alpha — 早期公开工程源码快照说明

> **这不是正式发布。** `v0.1.0-alpha` 是 GitHub 仓库早期公开工程源码快照的带注释 Git Tag 锚点：
> 功能不完整，**不是 V1.X RC1，不是 V2 正式版，也不是产品验收 PASS**。

## 1. 标签与精确提交

| 项目 | 值 |
| --- | --- |
| 标签名 | `v0.1.0-alpha`（annotated tag，非 lightweight） |
| 标签目标（本 Alpha 快照） | 提交本文件的 commit；用 `git rev-parse v0.1.0-alpha^{commit}` 核对精确 SHA |
| 许可证提交（main 上首次加入 `LICENSE` 的提交） | `a9016356d0ede797b1e870d7749eb24f05bfd462` |
| Tag 的 main 基线（加入许可证之前） | `fed2404c8e30b44061b7139dced45b7f3301601c`（Merge pull request #35 from 1785235376-blip/feature/provider-runtime-v2-host-hardware-inventory） |
| 远端仓库 | <https://github.com/1785235376-blip/AI-Novel-Studio> |
| 创建日期 | 2026-10-19（Asia/Shanghai） |

## 2. 本快照包含什么

- main 上已有的 **V0.7.0 Engineering Edition** 源码：FastAPI 后端、React + TypeScript + Vite 前端、DesktopHost/本地互操作源码、脚本、测试与文档。
- Apache-2.0 `LICENSE`、`NOTICE`、`LICENSING_AND_THIRD_PARTY.md` 与 README 许可说明（`LICENSE` 正文 SHA256 `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`）。

## 3. 本快照不包含什么 / 已知限制

- **V2 平台功能不在本快照中**。V2 仍在 `feature/v2-narrative-platform` 及后续 work 分支开发（PR #47 以 main 为 base；PR #48 以 V2 分支为 base），本 Tag 早于任何未来大型功能合并。
- V2 正式发布范围（原 Master Roadmap、DIF-01–12、IMAGE-COMIC-01–20）**未全部完成**，本 Tag 不改变任何一项的完成状态。
- 未创建 GitHub Release，未上传安装包，未启动正式发布流程。
- 仓库不含模型权重；本快照不包含任何真实模型推理或 AI 质量验收证据。
- 历史上 GitHub Actions 出现 runner 未真实启动（`runner_id=0`、`steps=0`）的情况，只能记为 `HOSTED_BLOCKED_NO_RUNNER`，不构成本 Tag 的 CI 通过证据。
- 独立的本地最小 CI（LOCAL-01～05）与社区文档在 `work/v2-local-ci-community-20261019` 分支交付，结果另行记录；它们不改写本 Tag 的“功能不完整 / 非验收”性质。

## 4. 与内部版本号的关系（版本政策）

- 仓库权威版本仍是 `release/version.json`：`0.7.0`（channel `beta`）；`pyproject.toml`、`app/__init__.py`、`frontend/package.json`、`.env.example` 与之保持一致，`scripts/validate_release_version.py` 继续强制该一致性（本 Tag 创建时已重新执行并通过）。
- 项目当前**不存在** `tag == version` 的 CI 门禁；本 Tag 是**源码快照/公开 alpha 锚点**，不是 `release/version.json` 的发布版本，因此不修改内部版本号，也不以 Tag 冒充正式发布记录。
- V2 正式发布仍须按 `docs/v2/engineering/RELEASE_GATES.md`（工程基线分支）与人工验收另行判定。

## 5. 测试边界

- 本 Tag 不附带新的验收测试证据；main 历史测试状态见 `docs/test_report.md` 及历史交付报告。
- 引用本 Tag 时不得表述为 `release`、`stable`、`production ready` 或“产品验收通过”。

## 6. 如何核对本 Tag

```bash
git fetch --tags
git cat-file -t v0.1.0-alpha        # 输出 tag，表示 annotated tag
git rev-parse v0.1.0-alpha^{commit} # 本 Alpha 快照的精确 commit SHA
git show v0.1.0-alpha --stat
git rev-parse v0.1.0-alpha^{commit}~1  # 许可证提交（a9016356d0ede797b1e870d7749eb24f05bfd462）
```