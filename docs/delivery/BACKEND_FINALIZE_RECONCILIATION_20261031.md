# 全分支后端收尾：接手核验与独立后端线对账（批次 1）

本轮按“先只读、再选基线、分批实施”的要求接手 `1785235376-blip/AI-Novel-Studio` 的全分支后端收尾。本文件记录批次 1：远端/本地只读核验、独立后端线（#51 与 `work/hermia-backend-verified-20261030` 等）逐文件对账与安全整合、以及本批实施的测试证据与剩余工作。**本文件不是全产品验收证明**；真实 PostgreSQL、浏览器、真实模型、Windows 打包桌面与 hosted CI 的未运行项在最后一节单独列出。

## 1. 接手时的只读核验（开始时重新核验）

工作树：独立新工作树 `D:\PoemSeed\Worktrees\backend-finalize-20261031`，分支 `work/backend-finalize-20261031`（从 #51 头 `317da4cc` 新建）。未使用 reset/clean/stash/强推/删除分支；原工作树与其他 worktree 的未提交内容保持不动（清单见本机 `Validation/backend-finalize-20261031/local-worktree-dirty-state.txt`）。

| 对象 | SHA | tree | 关系核验 |
| --- | --- | --- | --- |
| `main` | `7b35e4cb4bd9efabe7cff54e67d7b24e8e469385` | `36bcb60e21dd5f248365c300f2d1d1ef545f2bc4` | 远端默认分支；本轮未改动 |
| PR #50 head | `395ac26dd2de3d473e56964dbeb9ac9806facb85` | `3e1457d440f9c28543405fb4ba7d683dfba22385` | 共同祖先 |
| PR #51 head（集成基线 A） | `317da4cc3c9b68d4f9e09e6222b4e110bad4e94b` | `677156be5750dc93ca5b3fc8bdae73dfd414472e` | 395ac26d 是其后代祖先（YES） |
| `work/hermia-backend-verified-20261030`（sibling S） | `d657b4242283fb9babba1fdb95239df2f9a78801` | `c72d8ed37c291e41a5a4612b835e2f959da983a2` | 与 A 分叉，merge-base = 395ac26d |
| 远端 heads | — | — | 共 **86** 个（不含 main/HEAD）；相对 A：**47 祖先 / 39 非祖先**（与交接快照一致） |

只读产物（本机，未入库）：`Validation/backend-finalize-20261031/` 下 `branch_inventory.json/.md`、`prs.json`、`reconcile_A_vs_S.json/.md`、`candidate_file_matrix.json/.md`、`conflict_diffs.txt`、`sibling_commits.txt`、三个候选分支的 diff/cherry 报告。分支逐条处置见入库文件 `docs/delivery/REMOTE_BRANCH_TRIAGE_20261031.md`（85 个非 main/HEAD heads 全表）。

## 2. 集成基线选择与依赖顺序

- **基线 = PR #51 `317da4cc`**。理由：它是本机与远端当前后端能力线（安全硬化 + 能力补齐 + capacity/claims 线）的最新汇合点，包含 47 个祖先分支的全部后端成果，且 PR #50 是其祖先；sibling S 只是从共同祖先分出的 2 个提交的独立发布候选。
- **整合方向 = A ← S 的缺失增量**，而不是反向合并：A 在 Export claim/恢复、请求预算上下文、TaskCenter 游标/期限、安全硬化和能力补齐上更新；S 在 export 产物完整性、VTT/OTIO 严格合同、PG migrations 018–020 与测试隔离上更新。两边都有新内容，故以 A 为基线逐文件三方对账，只取 S 的缺失增量，冲突按“保留 A 的新语义 + 采用 S 的独立修复”逐条合并（见第 3 节）。
- **依赖顺序**：测试隔离/迁移（018–020 + 显式 PG 选择）→ Export 完整性/取消 → VTT/OTIO 严格合同 → Canvas source-read 准入 → 证据文档。每批小提交，历史证据与代码分开。
- 未另造并行 owner/存储/权限：全部增量落在原 `ExportJobService`、原 production/timeline API、原 `AtomicPathMutationStore` 家族、原 `CanvasView` 授权路径、原 PostgreSQL migration runner 与原测试选择入口上。

## 3. 与 `work/hermia-backend-verified-20261030` 的逐文件对账

S 相对共同祖先 B(#50) 有 2 个提交（`2e52c747` 导出完整性重建、`d657b424` 综合 checkpoint），改动 199 个文件；A 相对 B 改动 184 个文件。三方分类结果：

| 分类 | 数量 | 处置 |
| --- | --- | --- |
| 仅 S 修改的文件（A 与 B 相同） | 181（其中后端/迁移/测试/脚本 **40**，证据文档 141） | 40 个后端/测试/迁移文件按 blob 逐字复制并核验：**40/40 byte-identical to S**；141 个文档作为历史证据入库 |
| A 与 S 都修改且内容相同 | 10（含 `export_execution_claim.py`、`taskcenter_cursor_http.py` 等 2 个后端文件） | 已等价，无需合并 |
| A 与 S 都修改但内容不同（冲突候选） | 8 | 逐条人工合并（见下表） |
| 仅 A 修改 | 166 | 保留 A（更新语义） |

8 个冲突文件的处置（保留 A 的新语义 + 采用 S 的独立修复）：

| 文件 | 判定 | 处理 |
| --- | --- | --- |
| `app/services/export_job_service.py` | A 有更新的 per-job claim / recovery / idempotent-create、`preserve_queued_on_pool_failure`；S 有产物完整性、跨进程取消观察、format 幂等冲突与大小上限 | 采用 S 的产物读取/校验/取消/format 修复，保留 A 的 claim/恢复/幂等语义；新增 `_canonical_format` 与 `EXPORT_IDEMPOTENCY_FORMAT_CONFLICT` |
| `app/creative/production_execution_api.py` | A 有更新的 invoker/authority 链；S 新增严格 OTIO transfer-preview 422 诊断且必须先复授权 | 保留 A 的 invoker，仅加 S 的 `ExactTimeMetadataMismatch` 捕获块 |
| `app/experimental/taskcenter_cursor.py` | 仅行尾差异 | 保留 A |
| `app/repositories/file/mutation_coordinator.py` | A 有更新的 cold-lock/严格只读协调；S 为旧版 | 保留 A |
| `app/creative/asset_usage_budget.py` | A 有更新的 bounded binary 预算接口；S 为旧版 | 保留 A |
| `app/creative/asset_usage_request.py` | A 有更新的 audio-history/storage 只读预算中间件；S 为旧版 | 保留 A |
| `tests/file_safety_http_server.py` | A 有 diagnostic context hook；S 新增非 GET 请求的 ContextVar reset | 两者合并（保留 A 的 hook + S 的 reset） |
| `tests/test_export_owner_independent_process.py` | 与 A 保留的 `_submit(..., **kwargs)` 签名对应 | 保留 A |

其他独立后端线的核查结论（逐文件矩阵与 `git cherry` 见本机 `candidate_file_matrix.md`）：

- **Export 恢复线**（`work/hermia-export-artifact-recovery-20261028` f332dc9b、`work/hermia-export-recovery-ownership-20261027` efd083c2、`work/hermia-export-integrity-rebuild-20261029` 2e52c747）：所有权/恢复/完整性增量已由 A 的 `export_execution_claim.py`（与 S 同 blob）+ 本轮 S 导出修复覆盖；各分支剩余差异逐条核对为旧版本（`export_job_service` 旧分支版、旧 canvas 变体、旧测试期望）。**特别核对**：`f332dc9b` 的 `tests/test_export_artifact_recovery_generator.py` 在 A(#51) 树中已存在且 blob `ac50f0f3` 与 f332dc9b 完全相同（S 未携带）；因此**无需补入**，也不是生产缺陷线索。
- **TaskCenter 线**（`hermia-taskcenter-single-reader-20261027`、`hermia-taskcenter-continuation-20261027`、`hermia-pagination-diagnostics-20261027`、`hermia-mixed-cursor-safety-20261027`、`taskcenter-local-mixed-cursor-20261026`）：回执/deadline/严格只读上下文/分页诊断已由 A（`taskcenter_cursor*` 与 S 同 blob 或等价提交）覆盖；`taskcenter-local-mixed-cursor` 经 `git cherry` 判定补丁在 A 已有等价提交，无独有后端增量。
- **Canvas adoption auth 线**（`work/hermia-canvas-adoption-auth-20261026` e5d5e4cc）：A 缺少其单点修复（空画布首次关联结果时应在写入前捕获 source-read 准入）。本轮已整合 `app/creative/canvas_view_api.py`（`requires_source_read=True` → 既有 `local_input=True` 语义）与 2 个独立回归套件 + 交付证据。
- **`work/hermia-backend-align-20261030`**：相对 A 的 app/tests/migrations 独有增量为 0（仅前端/docs），**不因分支名当作后端未完成项**。
- **`work/audio-asset-version-history-20261025`**：旧实现线索，本轮**未整合**；列入下一批“音频单资产历史/恢复”工作（见第 6 节）。
- 其余 30+ 历史产品分支（PR #36–#49 链、v2 前端切片、archive、prototype 等）按 `REMOTE_BRANCH_TRIAGE_20261031.md` 标注为“历史/待核对”，留待后续批次按模块和 PR 范围逐项核对；不批量合并旧 PR，不删除来源分支。

## 4. 批次 1 提交

| 提交 | 内容 |
| --- | --- |
| `9817d091` | feat(export): reconcile verified artifact integrity, claim ownership and cancellation |
| `2e7bdc27` | feat(storage): restore PostgreSQL migrations 018-020 and explicit test DB selection |
| `859f0b75` | feat(timeline): reconcile verified VTT/OTIO strict interop and transfer diagnostics |
| `4cafa761` | fix(canvas): capture source-read admission before an empty canvas association |
| `9ccd3d67` | docs(delivery): publish verified backend checkpoint evidence index |

## 5. 本批验证（Windows · Python 3.11 · File 合成；真实 PG/浏览器/模型未运行）

环境：Windows 11（本机），Python 3.11；`PYTHONUTF8=1`（Windows 默认 GBK 环境下读取含非 ASCII 的测试子进程输出所需，见下方预存失败说明）；ffmpeg/ffprobe 8.1.2 在 PATH；`opentimelineio==0.18.1` 作为仓库声明的可选依赖安装在隔离目录 `Validation/backend-finalize-20261031/pydeps`（未写入仓库、未改全局环境）；PostgreSQL 本机无实例，PG-only 用例按标记跳过。

| 测试组 | 结果 | 说明 |
| --- | --- | --- |
| Export 对账组（S 新 rebuild/取消/剩余 + A 既有 export jobs/owner/artifact/generator） | **144 passed / 7 skipped** | UTF-8 模式；7 skip 为 PG/symlink 环境门 |
| Canvas + VTT 对账组 | **93 passed** | 含 2 个 canvas 独立授权套件、5 个 VTT 套件 |
| OTIO 严格合同组（含 isolated otio 0.18.1） | **63 passed / 14 skipped** | skip 为 PG-only；无 otio 时该组为 collection error（已安装隔离依赖后通过） |
| PG/迁移/选择/harness/回归组 | **157 passed / 20 skipped** | 含 migration completeness、显式 PG 选择、backend mode harness、file-safety observer、taskcenter rebuilt、TaskCenter 游标独立、production query、audio history 只读状态 |
| S 修改的既有测试文件 | **29 passed / 9 skipped** | chapter concurrency、context、lore、v056 atomic、packaged PG migrations、G-05 系列、generation snapshot |
| 批次 1 最终组合选择（25 个文件组一次运行） | **457 passed / 27 skipped / 0 failed**（111s） | Validation/backend-finalize-20261031/batch1-final-combined.log；skip 为 PG-only 与符号链接环境门 |
| 总计 | 不将重叠用例相加；按组分别记录 | 未运行真实 PostgreSQL/浏览器/真实模型/Windows 打包桌面 |

**预存/环境失败（如实保留，未改断言、未加 skip 掩盖）**：

1. Export 组首次在默认 GBK 编码下运行出现 4 个 `UnicodeDecodeError`：测试子进程 `read_text()` 使用 locale 编码读取含非 ASCII 的 JSON。`PYTHONUTF8=1` 重跑后全部通过（属于 Windows 环境编码问题，非产品缺陷）。
2. `test_export_execution_claim_independent.py` 3 项依赖 Windows 符号链接/别名创建的用例在本机因 `WinError 1314` 权限失败（claim 语义用例通过）；同机无符号链接权限，`NOT_VERIFIED`，未删除测试。
3. S 的历史真实 PG 证据保留其精确范围：`1349026` 的 9 项真实 PostgreSQL 16.15 用例通过（独立实例、乱序/规范序重复、5,826 tracked hash 未变）；较早 `3139927` 的 34 项属于另一源码版本，**不与之相加**，也未在本轮重跑。本批未运行真实 PG。

## 6. 尚未闭环的后端工作（后续批次；不在本文件宣称完成）

1. **项目容量**：实际占用跨入口计量、持久预留、落盘转换、失败残留、跨 owner 事务/锁、崩溃恢复与启动对账、审批/授权/版本/额度并发、音频与共享文档写入口、调额 CAS/审计、U16 RUNNING claim 提前反例——均未实现；现有 `project_usage` 仅按当前分支元数据计量，写门继续 fail-closed。
2. **音频单资产历史与恢复**：未实现；`version_history_read` / `version_restore` 保持 `UNAVAILABLE`；需覆盖 metadata/promotion/lineage/relationship/delete/undelete 全部写入口、旧格式迁移、容量归属、授权/CAS/幂等/崩溃恢复，并按已确认产品决定“恢复生成可追溯新当前版本、保留旧历史”。
3. **Studio 任务成本与音频 canvas_return**：成本仍无可信 provider 用量/价格合同，继续返回未知；音频 canvas_return 当前范围未扩展（需采用目标/权限/审核语义的产品决定）。
4. **TaskCenter/资产查询/资源护栏**：有界分页与 Studio jobs owner/operation+offset 分页已在基线（本批复核，不重复计为未实现）；剩余 F37 的 37 次拒绝与 strict-warm 首屏 409 根因仍未解释（不得写成 37 个独立缺陷或以探索性通过关闭）；local mixed 范围之外的协作/PG/packaged 组合需逐项完成权限/分页/恢复合同。
5. **IMAGE/VIDEO/Graph/音频/Timeline**：按 `STUDIO_V2_BACKEND_COMPLETION_LEDGER_20261028.md` 继续核对 source-read 准入、提交窗口 Asset 复验、VIDEO 候选/审核/回填、多节点 Graph 上游产物/digest/失败传播/UNKNOWN 恢复、Timeline/音频采用与渲染完整性；已有合成媒体正证据不扩大为真实模型/完整图验收。
6. **历史产品分支与 issue**：PR #36–#49 源分支、issue #16（数据库备份恢复）、#18（Provider/凭据策略）、#17（行业导出与 CJK 字体）均需按当前候选重验；本轮仅在清单中标注，未实施。
7. **回归/安全**：issue #14 历史回归、#51 记录的 7 项预存失败、PR #49 的 D-20 顺序挂起与 D-17 间歇问题、motion frame 远程引用/DNS rebinding/endpoint 改配后的凭据行为、同 id 删除重建/撤权/并发/损坏数据/重启，均待后续批次按固定 SHA 复核。
8. **阻塞项保持**：PUBLISHING 独立审阅、Windows ACL/junction 探测仍 `BLOCKED`，未重试、未换入口。

## 7. 环境与证据边界、回退

- 已运行证据仅覆盖 Windows 11 + Python 3.11 + File 合成；真实 PostgreSQL、真实浏览器/前端、真实模型/GPU、Windows 打包桌面、hosted CI、外部 NLE 均为 `NOT_RUN`/`NOT_VERIFIED`。
- S 的 141 个证据文档与 30 个 canvas 证据文档按其记录的历史源码 SHA 保留，不升级为本集成提交的测试结果。
- 回退：`git revert 4cafa761 859f0b75 2e7bdc27 9817d091`（倒序）可分别回退各批；本分支未改 main、未删分支、未强推、未创建 Release。
- 分支与 PR：`work/backend-finalize-20261031`，Draft PR 见最终交付记录；批次 2 起继续按上述第 6 节顺序推进。

