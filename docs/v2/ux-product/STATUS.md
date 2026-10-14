# UX-PRODUCT 状态

**当前批次**：第一批 **已完成**（UX-01 + UX-02 源码、集成、轻量验证、提交）。
**下一批次**：第二批 — UX-03（Asset Browser 素材复用）+ UX-04（无限画布与节点工作流）。

**分支**：`feature/v2-narrative-platform`（PR #47 保持 OPEN / Draft）。
**提交**：`400b522` 前端解释器可移植性修复 · `7474105`/`9ba3d77` 为 Phase7 与 Phase8 准备（本轮之前）。
**基线保护**：39 个既有未跟踪文件（36 个 `docs/delivery/v2-development/phase6-*`、`catalog-f19d*.json`、`.graphflow-cache/`、`graphflow-out/`）属基线，**未提交、未清理**。

## 状态表（源码状态 ≠ 验证状态）

| 工作包 | 源码状态 | 验证状态 | 说明 |
| --- | --- | --- | --- |
| UX-01 入口/意图/模式 | **IMPLEMENTED** | **PASS**（脚手架级） | `frontend/src/onboarding/` 14 文件 + `studioWorkspaceResume.ts` 模式/视图扩展；43 tests |
| UX-02 任务中心/审核 | **IMPLEMENTED** | **PASS**（脚手架级） | `frontend/src/taskcenter/` 15 文件；44 tests |
| 集成 | **IMPLEMENTED** | **PASS** | `IndependentStudioWorkspace.tsx`：3 个新视图入口 + 模式开关 + 两处挂载；既有回归 117 passed |
| 工程（harness/文档/矩阵） | **IMPLEMENTED** | **PASS** | `scripts/run_ux_product_checks.py`、`docs/v2/ux-product/*`、`STUDIO_UX_PRODUCT_REPORT.md` |
| UX-03 … UX-09 | NOT_STARTED | NOT_RUN | 第二至第四批 |

## 验证汇总（全部 `sources_changed_during_check=false`）

| 检查 | 结果 | 收据 |
| --- | --- | --- |
| File | PASS 48 passed / 42 skipped | `ux-product-file-r2` |
| **PostgreSQL（真实 owned cluster）** | PASS 14 passed / 8 skipped | `ux-product-pg` |
| Frontend（新面） | PASS 9 files / 87 tests | `ux-product-frontend-r2` |
| Frontend（含模式 owner） | PASS 10 files / 96 tests | 会话内运行 |
| 既有工作区集成回归 | PASS 10 files / 117 tests | 会话内运行 |
| TypeScript / Build / Tokens / Seam | PASS ×4 | `ux-product-{types,build,tokens,seam}-r2` |
| 既有 `python3` 缺口回归 | PASS 22 tests（修复前 20 failed） | 提交 `400b522` |

## 正在做什么

第一批已收口。第二批按任务书第 15 节顺序启动：UX-03 与 UX-04 各由一条产品写入线负责，验证线独立复核；共享文件（`IndependentStudioWorkspace.tsx`、受保护面、feature matrix）由主代理串行整合。

## 下一可执行项

1. UX-03：筛选/搜索/列表-网格共用选择、版本对比、素材送往目标模块时传递原 Asset ID/version/digest、来源新版本差异与影响范围预览（复用 `AssetLibraryService` 与 lineage/relationships）。
2. UX-04：节点搜索/分类/拖入/多选/框选、端口类型与拒绝原因、分组/注释/折叠/可撤销布局、区分布局变动与影响生成的变动（复用 `CreativeGraphService`）。
3. 第二批完成后同样出 harness 收据、更新 `STUDIO_UX_PRODUCT_REPORT.md`、feature matrix 追加、提交推送。

## 阻塞（准确记录，不阻塞其余开发）

- **GitHub Actions**：账户账单锁，作业 0 步启动 → `BLOCKED_ACCOUNT_PLATFORM`；不重跑、不购买、不修改账单，不以“未启动”当通过。
- **本机最终验收**：Windows 安装版、GPU/大模型、重型渲染、真实项目迁移 → `LOCAL_REQUIRED`（本轮不执行）。
- **PostgreSQL**：已从缺口转为可用（owned cluster，见上表）；仍属**开发**验证，不是安装版验收。
- 前端全量套件中两个 `python3` 依赖套件已修复；其余既有失败若出现将逐项记录，不做掩盖。

## 保留的历史边界（本轮不改写）

V1 冻结内容、F00 INTEGRATED + 39 PARTIAL、独立复审 BLOCKED、M4 PARTIAL、M5–M9 LOCAL_REQUIRED、PoemSeed Local Interop 1.0 协议语义、QingJian 暂停状态。
