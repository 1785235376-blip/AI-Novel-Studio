# B07 / DIF-10 / E2E-07 互动叙事专项 · 统一交接报告 (2026-10-20)

状态：**IMPLEMENTED + INTEGRATION_VERIFIED**；目标运行时证据 **Godot 4.7 = PASS、inkjs 2.3.2 = PASS**，
**Ren'Py 8.5.4 = BLOCKED_ENVIRONMENT（本机无引擎）**。本报告不声明 PoemSeed Studio V2 整体可发布。

---

## 1. 起始产品基线恢复与核对

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/1785235376-blip/AI-Novel-Studio（本地 D:/PoemSeed/AI-Novel-Studio，原 worktree 未被修改） |
| 指定产品基线 | b8371a48816b852176d45151eb9a0e3618a32c07 / tree d1abbaaf64d7fd95535ad75ea2470fa288a35579 |
| 指定归档提交 | 88fe0e10cd4c8c3892c5c3108056057133c4c46f（archive/verified-studio-v2-20261017-5a6f697，fetch 后从 dcc952bc 前进到 88fe0e10） |
| 归档目录 | artifacts/2026-10-20-studio-v2-cloud-authoring-reviewed-b8371a48/ |
| 归档前置提交 | 9ce5e243f925f6fb5141046758045c59b1dca46f（经 RESTORE.md 依赖链恢复） |

真实执行结果（全部 PASS，非推断）：

1. 从 archive 分支 149 个归档 batch 中提取 149 个 *.bundle（85.4 MB），在独立 Git 数据库 D:/PoemSeed/Recovery/b07-restore-20261020/recovered.git 中迭代 fetch，恢复整条 reviewed chain；目标 bundle studio-v2-9ce5e243-to-b8371a48.bundle 在前置 9ce5e243 到位后 fetch 成功（顺序 1 次失败、重试成功，未重复应用）。
2. SHA256SUMS 6 个文件哈希全部匹配（含 bundle 172907839598d694…、evidence zip 346ced9e97b34b7d…）。
3. git bundle verify：bundle okay，ref b8371a48 / prerequisite 9ce5e243 明确。
4. 恢复后 git cat-file -t b8371a48 = commit，tree 精确等于 d1abbaaf…；rev-list --count b8371a48 ^9ce5e243 = 6（4 个原始 feature 提交 + 2 个仅集成 merge），changed paths = 20。
5. git fsck --strict --no-dangling：PASS。
6. 归档包内校验器 verify_package.py artifact recovered.git 输出：
   {"status": "PASS", "product_tip": "b8371a48816b852176d45151eb9a0e3618a32c07", "product_tree": "d1abbaaf64d7fd95535ad75ea2470fa288a35579", "commits": 6, "source_commits_retained": 4, "file_mappings": 20, "new_objects": 60, "payloads": 5, "evidence_entries": 66, "fsck": "PASS"}
7. 隔离工作区：D:/PoemSeed/Worktrees/studio-v2-b07-baseline-20261020（产品 clone，2.35 GB，git 对象与原仓库共享，未污染原仓库）。未执行 reset / git clean / force push / 合并 main；未触碰用户主 worktree 与 Hermia 分支。

## 2. 最终集成与提交映射

最终集成分支：work/v2-b07-integration-20261020
本报告提交后的最终 tip 见同目录 git/delivery-manifest.json 的 integration.tip（本报告提交之前为 c359019b）。

| 线 | 分支 | 起始 | 最终 tip | 提交数 |
|---|---|---|---|---|
| 共享契约 (Lead) | work/v2-b07-contract-20261020 | b8371a48 | 3752b925 | 3 |
| A 前端 | work/v2-b07-ui-20261020 | e46a634d | 68917830 | 5 |
| B Ren'Py | work/v2-b07-renpy-20261020 | e46a634d | 634e7c20 | 3 |
| C Godot | work/v2-b07-godot-20261020 | e46a634d | ce010008 | 7 |
| D Ink | work/v2-b07-ink-20261020 | e46a634d | 7977071c | 8 |
| E2E/样例/证据 | work/v2-b07-e2e-20261020 | e46a634d | ccdbd4af | 8 |
| Lead 收尾 | — | — | — | b23b1333(可选字段)、91f08eae(packaging)、c359019b(证据+EVIDENCE_OVERRIDES)、本 HANDOFF 提交 |

集成方式：在独立集成 worktree 中按「契约 → 目标适配器 → runtime → 专项测试 → 前端 → E2E」顺序 git cherry-pick（全部 clean，无 ours/theirs 覆盖，无冲突丢弃）。
git diff --shortstat b8371a48..HEAD：66 files changed（全部为本轮新增/修改，未覆盖 Hermia 共享文件）。

### 文件所有权（本轮实际）

- Lead/共享契约：app/experimental/interactive_export_contract.py（新）、interactive_story.py、interactive_story_api.py、frontend/src/experimental/interactiveStoryClient.ts、packaging/public-build.json、scripts/build_b07_delivery.py、tests/test_interactive_export_contract.py、文档。
- A：frontend/src/experimental/InteractiveStory*.tsx / interactiveStory*.ts / interactiveStory.css 与其测试（16 文件）。
- B：app/experimental/interactive_renpy_export.py、app/experimental/interactive_targets/renpy/**、tests/test_interactive_renpy_project_export.py。
- C：app/experimental/interactive_godot_export.py、app/experimental/interactive_targets/godot/**（7 个非 .py 模板 + 审计清单）、scripts/verify_godot_interactive_runtime.py、tests/test_interactive_godot_runtime_export.py、Godot 证据。
- D：app/experimental/ink_export.py（新增 surface，旧 adapter 输出字节冻结）、app/experimental/interactive_targets/ink/**、scripts/verify_ink_current_artifact.mjs、scripts/prepare_inkjs_test_dependency.py、Ink 测试与证据。
- E2E：scripts/b07_e2e07_journey.py、tests/test_b07_e2e07_journey.py、docs/v2/b07-e2e07-20261020/**、E2E 证据。
- 未改动：App.tsx、ExperimentalWorkbench.tsx、ModuleWorkspaceRoutes.tsx、app/api.py、app/experimental/api.py、Graph/Director/Storyboard、Asset/权限/生产 owner、U16/Audio、缓存预算、lockfile/package.json。

## 3. 已完成真实功能

- 共享导出契约：Target Descriptor / 13 项能力词表 / 兼容性与损失报告 / 已授权 Story Snapshot / 确定性 manifest+source-receipt / 安全相对路径与确定性 ZIP / 有界引擎探测 / 7 级独立证据等级；旧目标 ID 与旧多目标导出包语义保留。
- Studio：规划节点创建互动故事、编辑（对白/角色/变量/条件/选择/结局/资产引用/图谱记录）、服务端权威试玩与回退、结局 witness 导航、历史版本内容 diff、审核/批准/归档/恢复/来源重绑定、目标选择/损失确认/单目标下载。
- RENPY_8_5_4_PROJECT_V1：完整 Ren'Py 项目导出（script/options/screens.rpy + README + acceptance witness），受信任子集 simulator 与 play() 全路径对齐；本机无引擎 → 仅 BLOCKED 运行证据。
- GODOT_4_RUNTIME_PROJECT_V1：完整 Godot 4 项目（project.godot/main.tscn/固定 runtime/typed story/witness），受限 typed AST 解释器，两进程存档/恢复与 7 类篡改拒绝；真实 Godot 4.7 headless 运行 PASS。
- INK_2_3_2_CURRENT_ARTIFACT_V1：当前导出 Ink 作品的 pinned inkjs 2.3.2 编译/运行/跨进程 state 恢复；旧 Ink 目标输出字节冻结。
- E2E-07：真实 mounted Studio API 旅程（规划→创建→编辑→试玩→审核→批准→export-targets→export-preview→export ZIP）+ 目标运行时逐 step 对齐 + save/quit/restore。

## 4. 每个目标的真实运行等级（独立记录，不自动升级）

| 目标 | SOURCE | SCHEMA | FIXTURE | ARTIFACT | TARGET_RUNTIME | SAVE_RESTORE | WINDOWS GUI |
|---|---|---|---|---|---|---|---|
| RENPY_8_5_4_PROJECT_V1 | PASS | PASS | PASS | PASS | BLOCKED_ENVIRONMENT | BLOCKED_ENVIRONMENT | NOT_RUN |
| GODOT_4_RUNTIME_PROJECT_V1 | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN |
| INK_2_3_2_CURRENT_ARTIFACT_V1 | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN |
| RENPY_8_5_4_TEXT_MENU_SUBSET (legacy) | PASS | PASS | PASS | PASS | BLOCKED_ENVIRONMENT | BLOCKED_ENVIRONMENT | NOT_RUN |
| GODOT_4_DATA_ADAPTER (legacy) | PASS | PASS | PASS | PASS | NOT_RUN | NOT_RUN | NOT_RUN |
| INKJS_2_3_2_TYPED_TEXT_SUBSET (legacy) | PASS | PASS | PASS | PASS | PASS | PASS | NOT_RUN |

Godot：Godot_v4.7-stable_win64_console.exe --version → 4.7.stable.official.5b4e0cb0f；默认模式 verifier 64 checks/0 failures；E2E artifact 模式对 4 个 scope 的原始导出 ZIP 执行，逐 step 与 play() 全等。
Ink：pinned inkjs 2.3.2（sha512 与 PIN 一致），4 cases 跨进程恢复 PASS。
Ren'Py：引擎探测 NOT_INSTALLED（PATH/env/python 模块/受限目录扫描），未安装任何引擎。

## 5. E2E-07 证据与样例（真实执行）

- 命令：python scripts/b07_e2e07_journey.py all → exit 0，PASS_WITH_BLOCKED_ENVIRONMENT，588 checks / 0 failures，blocking unmet = 0。
- 证据：docs/v2/B07_DIF10_E2E07_EVIDENCE_20261020.json（1.4 MB，含命令、exit code、ZIP SHA256、逐 step、save/restore、未满足项）与同名 .md；样例记录 docs/v2/b07-e2e07-20261020/**。
- 三份可重复样例（真实 API 创建，非 mock）：A 基础线性（1 结局/2 case）、B 条件分支（3 结局/6 case，含初始禁用路线与条件赋值差异）、C 复杂边界（循环+max_steps=6 STEP_CAP_REACHED、中文/全角/引号/换行/[ ] { } 〖 % 🙂 é、存档场景）。
- 外部交付（原始导出 ZIP、解包项目、runtime report，225 文件 / 4.78 MB）：D:/PoemSeed/Recovery/b07-delivery/e2e07/。
- 旅程关键产物（最终证据 SHA256）：legacy 多目标包 67422984…；Godot ZIP f9af5fac9be01a8c…（14 files）；Ink ZIP 2d08c8288f1ae2d9…（7 files）；RenPy ZIP 62474093deb61715…（7 files）。
- 确定性：同故事同 revision 重复导出 ZIP SHA256 完全一致（样本与旅程均有 deterministic_repeat 记录）。

## 6. 测试总账（本轮实际命令与结果）

| 范围 | 命令 | 结果 |
|---|---|---|
| 后端 B07 全量 | python -m pytest tests/test_r5_interactive_story*.py tests/test_interactive_*.py tests/test_storyverse_ink_exchange.py tests/test_b07_e2e07_journey.py ... -m 'not postgres_backend_only' | 215 passed, 15 skipped, 0 failed |
| 前端互动叙事 | pnpm exec vitest run <15 files> | 15 files / 155 tests PASS |
| TypeScript + 生产构建 | pnpm run build | PASS（tsc -b exit 0；vite built；仅既有 >500 kB chunk 警告） |
| Godot 真实运行时 | python scripts/verify_godot_interactive_runtime.py | 64 checks / 0 failures / exit 0 |
| Godot 外部产物模式 | python scripts/verify_godot_interactive_runtime.py --artifact <zip> --report <json> | 4 scope PASS（bundle integrity 先于运行） |
| Ink 当前产物 | node scripts/verify_ink_current_artifact.mjs --bundle <unpacked bundle> --vendor <inkjs 2.3.2> | PASS（compile/runtime/cross-process restore） |
| E2E-07 | python scripts/b07_e2e07_journey.py all | exit 0，588 checks，0 failures |
| public build 白名单 | python -m pytest tests/test_public_build_profile.py | 27 passed / 3 failed（均为既有问题，见 §9） |
| 我们新增文件白名单 | python scripts/public_build.py --source . | 仅剩既有 17 个基线漂移文件（见 §9） |

已执行的定向回归包括旧 Export 包字节/结构、旧目标 ID、契约校验、CSP/路径穿越/ZIP 篡改、权限撤销、IME、CAS、迟到响应、来源失效等。

## 7. 交付物

- Git 补丁（逐提交完整 --binary --full-index）：git/patches/{contract,ui,renpy,godot,ink,e2e,integration}/*.patch。
- 完整 UTF-8 补丁 TXT（无损，含全部 mbox 与二进制 base85 段）：git/B07_DIF10_E2E07_FULL_PATCH_20261020.txt。
- 增量 Git bundle（base b8371a48 → 最终 tip，含 git bundle verify 记录）：git/bundles/*.bundle。
- SHA256SUMS、RESTORE.md、delivery-manifest.json：git/（另有顶层汇总 SHA256SUMS）。
- 本交接报告：B07_DIF10_E2E07_HANDOFF.md。
- 证据与样例：本报告同目录 evidence/（复制 E2E/Godot/Ink/RenPy/契约摘要）与 artifacts/e2e07/（225 个真实导出物/解包项目/runtime report）。
- 真实目标项目 ZIP（旅程 + 样例 A/B/C 的 Godot/Ink/RenPy）：artifacts/e2e07/**/exports/**。

## 8. 对 Hermia 的最小接口需求

B07/DIF-10/E2E-07 本体不需要 Hermia 修改任何共享文件：互动故事面板沿用既有 ExperimentalWorkbench 挂载；新增 POST /{sid}/export-targets 路由在既有主线程所属 router 内注册；无外层路由/App.tsx 变更需求。

需要 Hermia/发布 owner 处理的是既有基线漂移（与本轮无关，restored b8371a48 即存在）：packaging/public-build.json 缺少 17 个已在产品树中的文件（app/creative/graph_conditions_catalog.py、app/creative/graph_failed_retry.py、app/creative/graph_local_conditions.py、app/creative/graph_local_subgraph.py、app/creative/impact_reads.py、app/creative/storyboard_video_timeline.py、app/experimental/comic_timeline_handoff.py、app/experimental/portable_cache_policy.py、app/experimental/storyboard_impact_adapter.py、app/services/asset_bounded_file_windows.py、app/services/comic_page_origin.py、app/services/comic_page_source_reads.py、app/services/studio_audio_denoise.py、app/services/studio_audio_loudness.py、app/services/studio_image_composite.py、app/services/studio_image_cutout_webp.py、app/services/studio_timeline_links.py），导致 tests/test_public_build_profile.py 的两个 actual-repo 用例在基线上即失败。本轮只把 B07 的 18 个新文件加入白名单，未越权加入既有未审文件。

## 9. 仍未满足的验收要求（诚实记录）

1. Ren'Py 8.5.4 运行时/存档：本机无引擎（probe_engine = NOT_INSTALLED），TARGET_RUNTIME_EXECUTED / SAVE_RESTORE_VERIFIED = BLOCKED_ENVIRONMENT；已有可运行项目 ZIP 与 acceptance/witness.json，需在有 Ren'Py 8.5.4 的机器上解压、launcher 打开、按 witness 走路径后由验收人升级。
2. WINDOWS_USABILITY_VERIFIED：所有目标 = NOT_RUN。Godot 仅 headless 自动化执行，未做真实 GUI 交互/字体渲染/输入验收。
3. 原生 C# Ink runtime：NOT_RUN；只验证社区 JS port（inkjs 2.3.2），未冒充原生。
4. 媒体：仅 manifest 引用，不打包/不播放（已列入 capabilities/losses）；完整视觉小说媒体渲染为 PARTIAL。
5. PostgreSQL：无授权 DSN，未运行；文件后端证据不可冒充 PG。
6. public build 既有问题：17 个基线未审文件漂移（见 §8）；另有 test_symlinks_fail_before_copy 因 Windows 当前账户无 symlink 权限 OSError（环境限制，基线上同样失败）。
7. 不声明整个 V2 可发布；不创建正式 Release/Tag。

## 10. 下一次恢复开发步骤

1. 依赖：git；Python 3.11（pydantic 2.13 / fastapi / pytest）；Node 22 + pnpm；Godot 4.7（可选，跑 runtime 验收）。
2. 取得基线 b8371a48（按归档 RESTORE.md 链；本交付假设目标仓库已有该 commit）。
3. 应用本轮补丁（推荐）：
   cd AI-Novel-Studio
   git fetch origin && git checkout -B b07-interactive b8371a48816b852176d45151eb9a0e3618a32c07
   git am --3way B07_DIF10_E2E07_FULL_PATCH_20261020.txt
   git rev-parse HEAD   # 应等于 delivery-manifest.json 的 integration.tip
4. 或使用 bundle：
   git bundle verify bundles/b07-interactive-*.bundle
   git fetch bundles/b07-interactive-*.bundle <tip>:refs/heads/b07-interactive && git checkout b07-interactive
5. 后端验证：
   python -m pytest tests/test_r5_interactive_story.py tests/test_interactive_export_contract.py tests/test_interactive_renpy_project_export.py tests/test_interactive_godot_runtime_export.py tests/test_interactive_ink_current_artifact.py tests/test_b07_e2e07_journey.py -q -m 'not postgres_backend_only'
6. 前端：cd frontend && pnpm install && pnpm run build；pnpm exec vitest run src/experimental/InteractiveStoryPanel.test.tsx
7. 真实目标 E2E（需要 Godot 4.7 与 inkjs 2.3.2 vendor；缺一项目标会被如实标 BLOCKED）：
   set POEMSEED_GODOT_BIN=D:/GameDev/Godot/Godot-4.7-stable/Godot_v4.7-stable_win64_console.exe
   python scripts/b07_e2e07_journey.py all    # exit 0 => PASS_WITH_BLOCKED_ENVIRONMENT
8. Ren'Py 真机验收（如果有引擎）：解压 renpy-*.zip 到新空目录，用 Ren'Py 8.5.4 launcher 打开，按 acceptance/witness.json 走路径。

## 11. 资源与清理

- 保留：完整 Git 对象/分支（含各线原始提交）、本轮正式导出样例、patches/bundle/UTF-8 TXT/SHA256SUMS、失败与阻塞证据、用户未提交修改、其他 Agent worktree。
- 清理（详见交付目录 CLEANUP.md）：仅删除本轮临时 smoke 目录与解包缓存；删除开发 worktree 释放空间前已确认所有分支/提交仍在共享对象库中且补丁/bundle 已生成。
- 未删除模型、正式项目、历史归档或用户文件；未对未知目录做递归删除。

---
本报告由 DSH Lead 在集成分支上生成；所有 PASS 均有对应命令与证据文件，无法本机运行的项保持 BLOCKED/NOT_RUN。
