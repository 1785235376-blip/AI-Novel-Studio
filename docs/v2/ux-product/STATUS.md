# UX-PRODUCT 状态

**五个批次全部完成**：UX-01…UX-09 共 **125 个新文件**，九个 UX 目录全部落地、集成、冻结树验收（r10 七项全 PASS，`frontend` 覆盖九个目录）。
**最终提交**：见远端分支头（`ccb7585` 为第五批源码；本轮追加 S 表更正、收据与文档）。
**剩余工作**：仅"未完成/未覆盖"清单中的环境级动作（浏览器视觉与几何验收、真实 CPU 媒体管线 S10、真实导出/模型/GPU、Windows 安装版）与未来扩展（CONTENT_POLICY 完整框架、青简接入）。

**分支**：`feature/v2-narrative-platform`（PR #47 保持 OPEN / Draft）。
**提交链**：`400b522` 解释器修复 · `68ad8ef` 批次 1 · `3023f9e` 批次 2 · `bda534a` CONTENT_POLICY 预留 · `b7af80a` 分类器修复 · `25b5042` 批次 3 · `17cc869` S 矩阵/source-pin · `b2bb623` onEdit 修复 · `ec68a10` 验证发现归档 · `9c1c646` 批次 4 · `40caee6` r8 收据 · `9340e51` 状态 · `500c90f` S 表更正 · `ccb7585` 批次 5。
**基线保护**：39–41 个既有未跟踪文件属基线，**未提交、未清理**。

## 状态表（源码状态 ≠ 验证状态）

| 工作包 | 源码 | 位置 | 目录文件 | 实测 |
| --- | --- | --- | --- | --- |
| UX-01 入口/意图/模式 | IMPLEMENTED | `frontend/src/onboarding/` | 14 | 96 tests（含模式往返/默认/非法值） |
| UX-02 任务中心/审核 | IMPLEMENTED | `frontend/src/taskcenter/` | 15 | 同上 |
| UX-03 素材复用 | IMPLEMENTED | `frontend/src/assetbrowser/` | 18 | 88 tests |
| UX-04 画布/节点 | IMPLEMENTED | `frontend/src/canvasops/` | 10 | 94 tests |
| UX-05 导演/分镜 | IMPLEMENTED | `frontend/src/storyboard/` | 16 | 76 tests |
| UX-06 多轨剪辑 | IMPLEMENTED | `frontend/src/nle/` | 11 | 70 tests |
| UX-07 模型中心/存储 | IMPLEMENTED | `frontend/src/modelcenter/` | 13 | 99 tests |
| UX-08 项目提示助手 | IMPLEMENTED | `frontend/src/guide/` | 14 | 74 tests |
| UX-09 统一导出/交接 | IMPLEMENTED | `frontend/src/delivery/` | 14 | 55 tests |
| CONTENT_POLICY 预留 | RESERVED | `app/creative/content_policy.py` | — | File + 真实 PG 双后端 |

**集成挂载（全部增量、按需打开，既有入口一律保留）**：入口面板 → `START` 视图；任务中心 → `TASKS` 视图；素材浏览器 → `ASSETS` 视图；画布操作栏 → 既有图编辑器内；镜头工作区 → 创作模块导演/分镜检查器旁；剪辑工作台 → 既有 `StudioTimelineEditor` 内；模型中心/提示助手/导出交接 → studio `PRODUCTION` 视图按需按钮。

## 状态表（源码状态 ≠ 验证状态）

| 工作包 | 源码状态 | 验证状态 | 说明 |
| --- | --- | --- | --- |
| UX-01 入口/意图/模式 | IMPLEMENTED | PASS（组件/契约级） | `frontend/src/onboarding/` 14 文件；模式绑定 Studio 自有 resume owner |
| UX-02 任务中心/审核 | IMPLEMENTED | PASS（协议夹具级） | `frontend/src/taskcenter/` 15 文件 |
| UX-03 素材复用 | IMPLEMENTED | PASS（组件/契约级） | `frontend/src/assetbrowser/` 18 文件；只读、传参只传引用、删除只做影响报告 |
| UX-04 画布/节点操作 | IMPLEMENTED | PASS（纯函数 + 组件级） | `frontend/src/canvasops/` 10 文件；分组/注释/折叠为会话内呈现态 |
| 集成 | IMPLEMENTED | PASS | `IndependentStudioWorkspace.tsx`（START/TASKS 视图、模式开关、任务中心、素材浏览器）、`studioGraphEditorView.tsx` + `useStudioGraphEditor.tsx`（画布操作栏） |
| UX-05 … UX-09 | NOT_STARTED | NOT_RUN | 第三、四批 |

## 验证汇总（本批收据全部 `sources_changed_during_check=false`）

| 检查 | 结果 | 收据 |
| --- | --- | --- |
| File（后端持久化面） | PASS 48 passed / 42 skipped | `ux-product-file-r4` |
| Frontend（四个 UX 目录） | PASS 268 tests | `ux-product-frontend-r4` |
| 既有集成回归（studio + 画布 + 无障碍标签 + 关系 + 声明表单） | PASS 198 tests | `ux-product-regression-r4` |
| TypeScript / Build / Tokens / Seam | PASS ×4（build 2130 modules） | `ux-product-{types,build,tokens,seam}-r4` |
| 新面单测（本会话直接运行） | assetbrowser 88 + canvasops 93 + onboarding/taskcenter 96 = **277 passed** | 会话内 |
| **PostgreSQL（真实 owned cluster）** | PASS 14 passed / 8 skipped（批次 1 建立，本批无后端改动故复用） | `ux-product-pg` |
| 既有 `python3` 缺口回归 | PASS 22 tests（修复前 20 failed） | 提交 `400b522` |

## 本批修掉的真实集成回归

1. UX-04 顾问面板初版的无障碍名称（`起始输出端口`/`目标输入端口`）与既有下拉框冲突，导致 `StudioSelectLabels.test.tsx` 失败 → 改名为 `连接建议 · …`（UX-04 线自行修复，既有测试恢复全绿）。
2. 我（Lead）把控制器 `catalog` 联合类型传给操作栏时出现 TS2322 → 以带注释的窄化断言处理，并在视图里保留既有的端口选择控件（不删除既有可用控件）。
3. 我在批量 1 的会话中遗留了 `DECISIONS.md` 的条目串位（D11/D12 内容互串）→ 本批重排为 D10–D14 有序。

## 正在做什么

第三批按任务书第 15 节启动：UX-05（导演目标/情绪/风格/摄影与表演建议编辑与对比、镜头卡与画布共享同一镜头数据、顺序调整保留稳定 Shot ID、送往图片/视频/时间线先形成目标草稿）与 UX-06（素材区/主预览/属性区/多轨时间线布局、原整数/有理时间基、按需缩略图与波形、字幕轨、原播放缓存与导出回执）。仍按"两条产品写入线 + 一条验证线"，共享文件由主代理串行整合。

## 客观阻塞（不阻塞其余开发）

- **GitHub Actions**：账户账单锁，作业 0 步启动 → `BLOCKED_ACCOUNT_PLATFORM`；不重跑、不购买、不以"未启动"当通过。
- **本机最终验收**：Windows 安装版、GPU/大模型、重型渲染、真实项目迁移 → `LOCAL_REQUIRED`。
- **浏览器/视觉验收**：四个新 UX 面目前只有组件级（jsdom）验证；playwright 视觉/几何检查仍待做，明确计为 NOT_RUN。

## 保留的历史边界（本轮不改写）

V1 冻结内容、F00 INTEGRATED + 39 PARTIAL、独立复审 BLOCKED、M4 PARTIAL、M5–M9 LOCAL_REQUIRED、PoemSeed Local Interop 1.0 协议语义、QingJian 暂停状态。
