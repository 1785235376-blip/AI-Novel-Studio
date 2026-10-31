# AI Novel Studio V2.0.0 发布说明（2026-10-31）

## 版本
- 产品版本：**2.0.0**
- 显示版本：V2.0（`release/version.json`，channel=`stable`）
- 一致性消费者：`pyproject.toml`、`app/__init__.py`、`frontend/package.json`、`.env.example`（`APP_VERSION`）、`README.md`、`docs/installation.md` 均由 `scripts/validate_release_version.py` 校验。

## main 合并内容
1. PR **#51**：Studio V2 后端能力补齐（Windows 游标密钥/项目删除信号）+ 安全硬化（merge `46ef2e12`）。
2. PR **#52**：全分支后端收尾（86 heads 核验/对账；Export/PG 018-020/VTT-OTIO/Canvas；容量账本/admission/历史写入计费；音频历史捕获-读取-迁移-恢复；运行时能力与 Studio 任务成本 UNKNOWN 合同；回归/安全复核）（merge `2d14f8c0`）。
3. PR **#53**：前端/后端对齐（frontend/UX/i18n 51 文件修正）（merge `d11c890c`）。

## 明确边界（不得写成验收通过）
- 真实验收 **尚未执行**：真实 PostgreSQL、真实浏览器/前端 E2E、真实模型/GPU、Windows 打包桌面、hosted CI、外部 NLE 均为 NOT_RUN；
- PUBLISHING 独立审阅、Windows ACL/junction 探测仍为 BLOCKED；
- CJK 字体授权、真实 Provider 授权、远程 frame provider 抓取策略、音频 canvas_return、额度策略等仍需产品/人员决定；
- 历史产品线（`#36`–`#49`、`#26` 等）未合入 main，保持原分支；`#47` 等仍为 DIRTY/超大分叉，合入会回退已验证的 V2 后端，未执行批量合并。
- 证据索引与逐分支状态见 `docs/delivery/BACKEND_FINALIZE_FINAL_REPORT_20261031.md`；历史合并回退：`git revert -m 1 <merge-commit>`。
