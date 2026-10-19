# PoemSeed Studio V2 · 前两轮六项前端功能整合与定向验收报告

- 日期：2026-10-19
- 范围：仅整合前两轮六项局部前端功能并完成定向回归，不扩展产品能力。
- 结论：六项功能已共存于同一开发分支 `work/v2-six-frontend-slices-integration-20261019`；标准前端构建受 Windows 环境级 esbuild 临时文件权限问题阻断（BLOCKED_ENVIRONMENT）。

## A. 开发基线

| 项目 | 实际结果 |
|---|---|
| 仓库 | `1785235376-blip/AI-Novel-Studio`（本地 `D:\PoemSeed\AI-Novel-Studio`） |
| 第一轮交付分支 | `origin/work/v2-frontend-slices-20261019` |
| 第一轮最新 HEAD | `8c215aea9b219e64f5edde94ff9379514233194e` |
| 第二轮交付分支 | `origin/work/v2-frontend-slices-r2-20261019` |
| 第二轮最新 HEAD | `0af49f9f9a86cae0be10e8f73535fa031dfa5b7b`（与第二轮报告一致） |
| 第二轮历史报告起点 | `f4a5327866007efa0a6bd3261086114216955a7b` |
| 两轮共同祖先 | `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3`（PR47） |
| 两轮关系 | 第一轮不是第二轮祖先；第二轮相对第一轮多 476 个提交（两条独立产品线） |
| 实际产品树 | 第二轮交付树 `0af49f9f`（来源：Hermia 已验证产品线，经归档 bundle 恢复并核对 manifest/tree） |
| 归档 bundle | `origin/archive/verified-studio-v2-20261017-5a6f697`：`artifacts/verified-20261017/`（25,976,069 bytes / SHA256 `87f2e025…4789`）＋ 124 个增量 bundle；第二轮已核对 tree 与 manifest 一致 |
| 整合起始 HEAD | `0af49f9f9a86cae0be10e8f73535fa031dfa5b7b` |
| 新整合分支 | `work/v2-six-frontend-slices-integration-20261019` |
| 新 worktree | `D:\PoemSeed\Worktrees\studio-v2-six-slices-integration-20261019` |
| 整合结束 HEAD（三项整合提交后） | `942ff82a5cc190083e5bce9ccf9380f5d9b83b5f`（本文档提交后以远端分支最新 HEAD 为准） |
| 最终工作区状态 | CLEAN |

## B. 第一轮四个提交的真实关系

| 来源功能 | 原始 SHA | 父提交 | 存在于第二轮历史 | 第二轮产品源码 | 处理 |
|---|---|---|---|---|---|
| 模板库文字搜索 | `83987f0ce240053d14f26b1bcbbdfdd0824654b2` | `2b26b1b8` | 否 | MISSING（目标文件无搜索状态/输入/计数/提示） | 最小兼容移植 → `639d335b` |
| 配音片段下移 | `121850220edede16122c0ee151c12193361579f5` | `83987f0c` | 否 | MISSING（目标文件仅上移） | 最小兼容移植 → `ddd64780` |
| 模板库测试类型修复 | `b5c96d8881aa85ac75c3545b7cb4f414068a87d7` | `83987f0c` | 否 | 测试文件不存在 | 随 F01 提交一并带入（测试文件取自该修复版本，已含类型修复） |
| 互动故事可读路径 | `8c215aea9b219e64f5edde94ff9379514233194e` | `b5c96d88` | 否 | MISSING（目标组件无路径解析/步骤展示，helper 不存在） | 最小兼容移植 → `942ff82a` |

说明：四个来源提交本身均可访问、文件范围仅含对应组件/测试/helper；但因目标树对应组件版本更新（TemplateLibraryPanel 80→95 行、VoiceDirectionPanel 60→70 行、InteractiveStoryPreview 20→41 行，第二轮已验证线新增了个人简报、声音分配核对、回退复核等功能），未整文件覆盖，也未合并整条分支，只在目标结构上做最小兼容补丁。

## C. 六项功能状态

| 功能 | 初始状态 | 整合后状态 | 改动文件 | 提交 SHA |
|---|---|---|---|---|
| F01 模板库本地文字搜索 | MISSING | PASS | `frontend/src/experimental/TemplateLibraryPanel.tsx`（改）、`TemplateLibraryPanel.search.test.tsx`（增） | `639d335bd0f48b7c167f3798646f55a98868d5db` |
| F02 配音片段相邻下移 | MISSING | PASS | `VoiceDirectionPanel.tsx`（改）、`VoiceDirectionPanel.reorder.test.tsx`（增） | `ddd647801e27b5e0ec3106f34c016710c6c6ca01` |
| F03 互动故事可读路径 | MISSING | PASS | `InteractiveStoryPreview.tsx`（改）、`interactiveStoryPath.ts`（增）、`InteractiveStoryPreview.path.test.tsx`（增） | `942ff82a5cc190083e5bce9ccf9380f5d9b83b5f` |
| F04 有声片段待核对白筛选 | PRESENT（第二轮 `84fc3405` 祖先） | PASS（未改动） | 无 | 无（已存在，跳过移植） |
| F05 发布预检问题等级计数与筛选 | PRESENT（第二轮 `275ae902` 祖先） | PASS（未改动） | 无 | 无（已存在，跳过移植） |
| F06 互动故事历史版本摘要 | PRESENT（第二轮 `0af49f9f` 祖先） | PASS（未改动） | 无 | 无（已存在，跳过移植） |

## D. Git 提交来源映射

| 顺序 | 完整 SHA | Commit Message | 父提交 | 改动文件 | 来源 SHA | 补丁拆分 | 测试修复 | 已推送 |
|---|---|---|---|---|---|---|---|---|
| 1 | `639d335bd0f48b7c167f3798646f55a98868d5db` | `integrate(template-library): restore local text search` | `0af49f9f…` | 2 files, +194/−5 | `83987f0c…` | 是（目标文件更新，仅移植缺失 hunk） | 是（测试文件含 `b5c96d88` 类型修复） | 是 |
| 2 | `ddd647801e27b5e0ec3106f34c016710c6c6ca01` | `integrate(voice-direction): restore adjacent move-down` | `639d335b…` | 2 files, +168/−1 | `12185022…` | 是（目标文件更新，仅移植下移按钮与保护） | 否 | 是 |
| 3 | `942ff82a5cc190083e5bce9ccf9380f5d9b83b5f` | `integrate(story-preview): restore readable path` | `ddd64780…` | 3 files, +437/−2 | `8c215aea…` | 是（目标组件已重写，按目标结构接入只读路径区块与 helper） | 否 | 是 |

累计相对第二轮 HEAD 的产品 diff：7 files，+799/−8。除此之外仅新增本文档。

## E. 测试证据（本轮实际执行）

统一命令：在 `frontend/` 下执行
`node node_modules/vitest/vitest.mjs run <files> --reporter=dot`
环境：Vitest 2.1.9 / jsdom / Node v22.14.0。

| 检查 | 测试文件（PASS 数） | PASS | FAIL | SKIP | EXIT | 状态 |
|---|---|---:|---:|---:|---:|---|
| F01 专项 | `TemplateLibraryPanel.search.test.tsx`(10) + `DeclarativeTemplatePanels.test.tsx`(8) + `PersonalSkillBriefComposer.test.tsx`(17) + `TemplateCopyEditing.test.tsx`(3) | 38 | 0 | 0 | 0 | PASS |
| F02 专项 | `VoiceDirectionPanel.reorder.test.tsx`(10) + `VoiceDirectionPanel.continuation.test.tsx`(3) + `VoiceSubtitlePanels.test.tsx`(7) | 20 | 0 | 0 | 0 | PASS |
| F03 专项 | `InteractiveStoryPreview.path.test.tsx`(18) + `InteractiveStoryBacktrack.additive.test.tsx`(6) + `InteractiveStoryPanel.test.tsx`(13) | 37 | 0 | 0 | 0 | PASS |
| F04 专项 | `AudiobookPanel.needsReview.test.tsx`(10) | 10 | 0 | 0 | 0 | PASS |
| F05 专项 | `ReaderPreflightPanel.severity.test.tsx`(11) + `ReaderSessionPanels.test.tsx`(9) | 20 | 0 | 0 | 0 | PASS |
| F06 专项 | `InteractiveStoryHistory.summary.test.tsx`(18) + `InteractiveStoryHistory.test.tsx`(1) | 19 | 0 | 0 | 0 | PASS |
| 六项共存集中回归 | 上表 15 个测试文件一次执行 | **144** | 0 | 0 | 0 | PASS |

- 新增/移植测试：F01 10 项、F02 10 项、F03 18 项（共 38 项，均来自第一轮来源提交并原样通过）；F04/F05/F06 的专项测试为第二轮已提交文件（38 项）。
- 既有回归：68 项（模板/配音/互动故事相关第二轮既有套件）。
- 所有测试均在本轮实际执行；无失败、无跳过。

## F. 集中检查

| 检查 | 状态 | 实际证据 |
|---|---|---|
| TypeScript | PASS | `node node_modules/typescript/bin/tsc -b`，exit 0，无诊断 |
| UI Token | PASS | `node ../scripts/check_ui_design_tokens.mjs` → `UI token guard PASS (52 files)`，exit 0 |
| 标准前端构建 | **BLOCKED_ENVIRONMENT** | `node node_modules/vite/bin/vite.js build`，exit 1：`[vite:esbuild-transpile] remove C:\Windows\TEMP\esbuild-<hash>: Access is denied.`（esbuild`main.js:718`；2479 modules transformed 后失败；Vite 6.4.3 / esbuild 0.25.12 / Node v22.14.0）。与上一轮已知环境问题一致；同一错误在整合前的第二轮树上亦出现（2478 modules 后失败），**非本轮代码引起**。按任务要求未使用任何临时规避，未修改 ACL/安全软件/依赖源码/构建配置 |
| 完整前端测试 | NOT_RUN | 按约定后置 |
| 完整后端测试 | NOT_RUN | 按约定后置 |
| 端到端测试 | NOT_RUN | 按约定后置 |
| 完整 V2 验收 | NOT_RUN | 按约定后置 |

## G. 未完成与遗留问题

1. **标准前端构建**：BLOCKED_ENVIRONMENT（Windows 下 esbuild 子进程删除临时文件被拒绝），未修复；本轮未使用替代工具链，未修改系统环境。
2. **完整测试/验收**：NOT_RUN（按本轮约定）。
3. **上一轮功能在产品验证线中的纳入**：第一轮 F01/F02/F03 不在第二轮已验证产品树，本轮按任务要求仅做最小兼容移植，未合并第一轮分支；第一轮分支与第二轮分支均未被修改。
4. **归档/bundle 差异**：本轮沿用第二轮已完成的归档恢复与 manifest 核对；未重新写入归档，未修改归档分支。
5. **已知功能限制**：F03 路径展示为只读派生，不校验运行时条件/变量；F06 的“声明结局”不是可达结局统计；F05 零匹配不代表预检通过（界面已提示）。以上均与来源实现一致，不属于本轮回归。

## 现场保护

- 第一轮分支 `work/v2-frontend-slices-20261019` 未修改（HEAD 仍为 `8c215aea…`）。
- 第二轮分支 `work/v2-frontend-slices-r2-20261019` 未修改（HEAD 仍为 `0af49f9f…`）。
- Hermia 归档分支 `archive/verified-studio-v2-20261017-5a6f697` 未修改（HEAD 仍为 `dcc952bc…`）。
- `main` 未修改（HEAD 仍为 `7b35e4cb…`）。
- 未强推、未合并 main、未创建 Release/Tag、未重写历史。
- 其他 worktree 状态与开工时一致；仅既有未跟踪 `.graphflow/`、`build/` 保留，未清理。

## 产品状态声明

本轮仅表示 PoemSeed Studio V2 前两轮六项局部前端功能已经整合到同一开发分支。不代表 B03 全部完成、B07 全部完成、U11 全部完成、Studio V2 全部开发完成、完整测试通过或产品可以正式发布。
