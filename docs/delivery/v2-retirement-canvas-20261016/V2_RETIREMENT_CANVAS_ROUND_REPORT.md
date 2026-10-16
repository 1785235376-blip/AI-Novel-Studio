# V2 本轮实现与验收报告 — 2026-10-16

整体状态：**PARTIAL，未建立 V2 freeze / release candidate**。本轮实际实现了项目退休与
旧授权清除、文本创作图本地恢复、Graph 中的只读 Director Console，并通过真实 File、
PostgreSQL API 与 Chromium 流程验证。没有把模型发现、适配器、清单数量或历史报告当成新验收。

实现 HEAD：`62d4aaf621eb7663e37d2ad88f2f9c64db9095f9`。本报告及最后一批原始证据由其后的文档提交发布；
最终发布 HEAD 以交付消息和 Git 为准。

## 远端与基线

- 仓库：`1785235376-blip/AI-Novel-Studio`；原 PR [#47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47)
  仍为 Draft / OPEN，继续使用 `feature/v2-narrative-platform`。
- 已 fetch 所有远端分支、tags、PR refs，并完成 unshallow；选择真实远端
  `045b865e5a003cac3333462d055f22099f6368d6`，相对 main 为 ahead 348 / behind 0。
- `origin/main` 为 `fed2404c8e30b44061b7139dced45b7f3301601c`，本轮未修改。
- 用户列出的 11 个 SHA 全部存在且可从 feature / PR #47 到达；无 discrepancy。
  完整 refs、命令和原工作目录状态见 [remote-audit.json](remote-audit.json)。
- 原目录 `D:/PoemSeed/AI-Novel-Studio` 保持 detached `5af9bfc40abc305154a1a35e50f5e8e47c1c1322`；
  原有 `build/` 保留。实现位于独立 worktree；没有 reset、force push 或重写历史。

## Completed：有边界的已验证实现

1. **Project retirement / incarnation isolation**：沿用原 Novel、Scope、Authorization owners。
   PostgreSQL 在同一事务清除 novel、项目级 role/permission、binding、storyline/branch；
   File 在原项目租约与跨进程授权/作用域锁内提交或补偿。保留 workspace 角色、membership、
   无关项目与授权审计历史。原始负向案例断言 exact `403 PROJECT_SCOPE_FORBIDDEN`，
   同时有新 incarnation、新作者 `201/200` 与旧数据/Asset 不可见的正反控制。
2. **创建与连接原子性 / 历史 orphan**：normal 与 audited creation 复用原 mutation port。
   同 workspace 的旧 orphan authority 在新 owner 建立时退休；foreign binding 精确拒绝为 400。
   link/create 失败补偿后无公开 orphan；失败前状态可供合法重试。拒绝向不存在的原 owner 发放权限。
3. **并发写边界**：授权发放、scope parent 验证与保存持有原项目租约；audited mutations 在
   原提交边界前后重验同一个 actor 和 active membership。测试覆盖延迟 grant、DELETE、scope write、
   跨进程无关写不被 rollback 覆盖，以及最终检查点撤权后的 scope/audit rollback。
4. **清理失败行为**：完整未变的树可恢复并重新抛出清理异常；部分物理删除后不恢复损坏 owner
   或旧授权，保留隐藏 reclaim 残留与失败日志。成功 PROJECT 通知仅在组合创建提交后发出。
5. **Canvas 文本草稿恢复**：已挂载到现有 Studio；按 actor/workspace/project/storyline/branch/
   incarnation 隔离。恢复前重读 overview 和保存版本/digest，明确确认后恢复；不隐式写服务端或调用模型。
6. **Director Graph participant 基础**：已有 `director_plan` 节点直接打开原 DirectorWorkspace 的
   只读投影。加载前后验证原文档 version/digest、scope 和 projection mode；变更、撤权或 owner 替换
   后隐藏旧内容。折叠取消请求并丢弃局部状态。没有新增 workflow、Asset、版本或权限 authority。

细节与原始回执：[P0 report](P0_RETIREMENT_REPORT.md)、
[scope/orphan followup](SCOPE_ORPHAN_FOLLOWUP_REPORT.md)、
[Director foundation](../../../DIRECTOR_GRAPH_CONSOLE_FOUNDATION_REPORT.md)。

## 验证结果

| Gate | 本轮结果与证据 |
| --- | --- |
| File：退休、orphan、scope、权限基础回归 | **62 passed**，47 PG cases deselected；`scope-orphan-file-r3` |
| File：冻结生命周期、额外 IO/通知、锁顺序 | **32 passed**；`retirement-io-lock-pinned-final`，pytest 8.4.2 |
| 真实 PostgreSQL：退休 + scope/orphan + 原始 defect | **48 passed**，47 File cases deselected；`retirement-scope-pg-final`，PostgreSQL 16.15、新库、原 20 migrations |
| Frontend 全量 | **4,163 passed / 6 skipped / 0 failed**，385 文件通过、1 文件跳过；`frontend-full-r4.{json,log}` |
| Frontend focused | Canvas 98、Director 相邻回归 138 项通过；属于组件/客户端测试，不替代 browser |
| TypeScript / Vite | **PASS**，`npm run build` 执行 `tsc -b && vite build`；`frontend-build.log` |
| 原有 Chromium visual / geometry | **7 passed**；`frontend-visual-geometry-r4.log`，未更新任何 baseline |
| 最终真实 File browser | **3 passed**，1366×768 / 1440×900 / 1920×1080；`director-console-integrated-final-r2` |
| 原 interop / UI token guards | 原 interop 检查通过；UI token guard **52 passed**；保留默认编码失败记录 |
| CI 增量清单 | **INVENTORY_ONLY**，14,910 collected，未执行测试；全部 9,151 frozen IDs 顺序保留、14,225 原增量 IDs 保留 |
| Hosted CI 最终发布 HEAD | **NOT_RUN**，本地回执不代表 GitHub checks 已通过 |
| 真实 PG browser | **NOT_RUN**；PG 本轮验收为真实 API/owner 测试 |
| Windows installer / clean-machine | **NOT_RUN / LOCAL_REQUIRED**；源工作目录运行不能替代安装包验收 |
| 真实模型 / GPU inference、生成质量 | **NOT_RUN / LOCAL_REQUIRED**；浏览器场景未请求模型，runtime model counter 未插桩 |

测试回执在 `../v2-development/`，本目录保存前端、保护审计与清单证据。最终 File/PG 的
before/after 源码哈希和当前源码相等，见 [final-source-and-browser-binding.json](final-source-and-browser-binding.json)。
早一轮 PG 29 项和 File 248 项的回执属于较早检查点，保留但不代替最终候选验收。
跳过、deselection 和 collection 均不计为通过。

浏览器采用原 LocalSessionBootstrap 与 packaged 初始 workspace 流程、真实身份和真实 File API，
无 dev session registry、响应 mock、store 注入或手工 SQL。覆盖 CJK/emoji 草稿自动保存、reload、
显式恢复、服务端 201 保存、Director add/save/expand/reopen、原文档变化后的拒绝复用；零 page errors。
最终首轮重启遗漏 `V061_API_URL`，请求误经默认代理，失败证据完整保留；修正隔离代理后全三视口通过。

## Partial / Missing / Blocked / NOT_RUN

- **PARTIAL — Infinite Canvas / GRAPH-01～22**：本轮交付文本草稿恢复基础及原图控制器挂载，
  不是完整 infinite canvas。分组、注释、完整媒体/external-reference 恢复、模板、命令搜索、
  大图虚拟化、资源调度等完整验收没有在本轮建立；不因本轮未动就宣称原有实现缺失。
- **PARTIAL — Director / CONSOLE / DIR**：Graph 中的只读原文档 Console 已实现；完整 create/
  duplicate/connect/disconnect/delete/review/rollback、A/B proposals 与 authoring 工作台仍需独立验收。
- **PARTIAL — R3**：本轮关闭项目退休/orphan 与选定 scope race 路径；没有建立所有路由的
  actor/session/membership ABA 或撤权并发证明。当前 guard 检查点不等于 membership row 租约贯穿 commit。
  Prompt authoring/adoption 的现有实现须继续沿原 Asset/Review owners 验证，不能重建。
  当前 production adoption gate 保持关闭：`PROMPT_ADOPTION_WRITE_ENABLED=False`，授权请求返回
  `503 PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`；已有 `_write`、`adopt_atomic`、File/PG 服务测试与
  六例 Prompt browser spec，不能再沿用旧文档中的 “authoring NOT_RUN”。本轮未重新验收后者运行凭证。
  旧测试关于 `project_scope` 无跨序列锁的说明已过时，当前 owner 已持 `workspace_mutation` 跨越 yield。
- **MISSING / UNVERIFIED 本轮增量**：Storyboard Canvas、Image/Video/Audio 的完整图集成、独立 NLE
  `EDIT-16` 全链、3D foundation、Tutor、storage/VRAM scheduling、internal Mature 隔离执行链
  未由本轮完成或验收。各项原有状态继续以 source/test matrix 为准。
- **BLOCKED 保持**：voice cloning/person imitation、D3-05 不开放。Standard content policy 仍 RESERVED；
  本轮无 Mature/NSFW 执行 route、provider、开关或 bypass 增量，未修改 Standard policy。
- **BLOCKED 的单项检查**：Windows symlink case 遇 WinError 1314，缺少创建符号链接权限；保留 FAIL，
  未通过 skip、放宽断言或任意 4xx 冒充通过。

## 保护与限制

- 750 个 frozen test/gate source、752 个选定保护 source/artifact 均保持与本轮基线的原始字节一致。
  frozen 9,151 manifest SHA256 保持 `6457dd4c…040262`；仅原 extender 更新 additive manifest。
  frozen branch `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0` 未变。
  证明范围是源文件/证据保护，不是 V1 runtime 或新 release 认证。
- feature 相对 main 已存在的 UI 差异属于选定基线；没有把整个 feature UI 宣称与 main 字节一致。
  本轮没有改 protected shell、ModuleSwitcher、Design System tokens 或 visual baseline。
- 本轮 evidence 目录使用有界 `-text` 规则保留捕获字节。staged blob 核对发现 6 份较早本轮收据仍被
  旧换行过滤影响，已仅对本轮目录重新应用规则；原始字节和 SHA256 保留。核对前的失败记录为
  `evidence-byte-check-before-renormalize.json`，最终逐文件 Git blob/原始字节结果在 changed-files manifest。
- File 使用补偿与原跨进程锁，**不宣称 power-loss ACID / crash-recovery 完成**；隐藏 reclaim 残留需后续存储回收。
- 本地草稿限 schema 1/2 文本图，媒体、分组、注释及外部 reference 不在恢复承诺内；多标签冲突检测
  不等于跨标签原子事务。Director pin checks 是只读保护，不代表执行与版本变化原子提交。
- GraphFlow 已使用可用的 `gf_read` 获取上下文；当前仅暴露 gf_read/edit/exec/macro，未暴露
  graphflow_index，无法声称已执行显式索引刷新。

## Changed files / 提交

逐文件清单、原始 SHA256 和 evidence 文件见 [changed-files-and-evidence.json](changed-files-and-evidence.json)。
主要实现 owners 为 `app/project_retirement.py`、原 Novel/Scope/Authorization repositories/services、
`AtomicPathMutationPort`、`collaboration_admin.py`、`runtime_events.py` 与 `workspace.py`；前端变更
集中在现有 `frontend/src/creative/` 图客户端、controller、恢复 UI、Director Console 和真实 browser harness。
新增测试全部增量添加；冻结 File lifecycle 测试未修改。

已分阶段提交并 fast-forward 推送至 PR #47 原分支：

1. `cd5e8ed30bf4776078c2df5597df9db97b45344d` — project retirement。
2. `5666d53269d7029dced08129ae21a2ef47d9c59c` — incarnation-bound text graph recovery。
3. `8f50e76af590f76da4714c651d2b9573dde7087f` — Director Console 原图集成。
4. `62d4aaf621eb7663e37d2ad88f2f9c64db9095f9` — historical orphan / scope leases / audited reauthorization。

## 资源保留与下一入口

本轮启动的 API、Vite、PostgreSQL 已停止；端口观察、D: 空间前后读数与保留列表见
[final-runtime-retention.json](final-runtime-retention.json)。没有宣称释放磁盘空间。通过与失败日志、
截图、数据库/profile 及 baseline regression worktree 均保留。

自动审批复核拒绝了临时目录/worktree 清理，仅返回通用 `blocked by policy`；未通过其他删除路径绕过。
因此保留这些临时资源，核心提交与验收不受阻。

下一精确入口：`app/creative/prompt_adoption_api.py:adopt_prompt` 与
`app/creative/prompt_adoption.py:PromptAdoptionService.adopt_atomic`，继续核验当前保留的
`source_bindings_verified=False`，生产 gate 保持关闭直至真实验证成立。配套入口为
`tests/test_round3i_http_adoption.py`、`tests/test_round3i_adoption_concurrency.py`，补齐跨进程、
真实生产路由与撤权边界；并核验原 `AssetLibraryService.delete` 的私有 Prompt 删除→tombstone 流程，
不能仅由已有服务 tombstone 推导真实作者 API 已通过。复用现有 `prompt_authoring.py:_write` 的
CAS/幂等与 `frontend/tests/e2e/prompt-workspace-acceptance.spec.ts`。
再沿既有 Graph/Asset/Job/Review owners 扩展 Storyboard/媒体能力，本轮不进入 final freeze。
