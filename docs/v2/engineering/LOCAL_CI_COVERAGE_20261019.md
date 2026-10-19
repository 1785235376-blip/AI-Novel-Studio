# LOCAL-02 skip 审计与覆盖清单（2026-10-19 round 2）

本文件回答一个问题：**LOCAL-02 快检的 468 个 skip 是否遗漏了关键安全或数据一致性测试？**
结论：**没有遗漏测试函数**；468 个 skip 全部属于两类已标注契约（467 个 PostgreSQL 后端变体 +
1 个 Windows symlink 权限变体），没有未知 skip，也没有只以 PostgreSQL 变体存在的函数。
但必须同时说明限制：PG 变体的断言只在真实 PostgreSQL 层执行（本轮已修复 D-07 的无限阻塞并实测），
symlink 契约仍需 Linux/特权环境，当前宿主 CI 不可用，因此记为明确缺口而非通过。

## 1. 方法与证据

- 运行：LOCAL-02 四文件切片，隔离 profile，File 后端，无模型/无云，raw JUnit（未脱敏前）
- 分组命令：`python scripts/audit_local_ci_skips.py --junit <LOCAL-02-junit.xml> --fail-on-pg-only`
- 本清单只解释 skip 与执行覆盖面；不改变任何断言，也不会把 skip 计为 PASS

## 2. 执行数据

| 项 | 数量 |
| --- | ---: |
| 收集总数 | 941 |
| 实际执行并通过 | 473 |
| 失败 | 0 |
| skip | 468 |
| 未知 skip 原因 | 0 |

skip 原因分布（精确消息，未改写）：

| 次数 | skip 消息 | 分类 |
| ---: | --- | --- |
| 467 | PostgreSQL implementation contract; covered by the real PostgreSQL full suite | PG 后端变体 |
| 1 | WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE: hosted Linux CI covers the symlink identity contract | Windows 权限 |

按文件分布：

| 文件 | skip 数 |
| --- | ---: |
| `tests.test_shared_project_route_authority` | 422 |
| `tests.test_surface_pending_canon_review` | 32 |
| `tests.test_v2_creative_project_lifecycle` | 9 |
| `tests.test_structured_record_cas` | 5 |

## 3. PostgreSQL 变体：467/467 都有已执行的 File 对照

对每个被 skip 的 `...[postgres]` 节点，按去掉参数后缀的函数名匹配本轮实际执行的 File 节点：
**467/467 全部存在已执行的 File 对照，PostgreSQL-only 函数数为 0。**

含义与限制：

1. 快检没有把任何测试函数整体跳过——每个被跳过的函数都在 File 后端真实执行过一次。
2. 但同一函数内后端分支的 PostgreSQL 专属断言（例如真实行锁/事务/schema 行为）只有在 PG 层才执行；
   这些必须由真实 PostgreSQL 套件验证，不能用 File 对照代替。
3. D-07 曾让完整 PG 套件在 Windows 上无限阻塞。本轮已定位并修复该 hang 类（有界连接 + 有界重试），
   并在真实 PG 上重复验证了此前卡死的节点与代表性契约子集（见 `DEFECTS_20261019_r1.md` D-07）。

## 4. Windows symlink 权限 skip（1 项）

- 节点：`tests.test_v2_creative_project_lifecycle::test_file_corrupt_marker_fails_closed_without_reading_external_content[symlink]`
- 原因：默认 Windows 开发者会话没有 `SeCreateSymbolicLinkPrivilege`；测试以显式原因 skip，不删除契约。
- 覆盖归属：该 symlink identity/fail-closed 契约由具有该权限的 Linux/特权环境覆盖；当前宿主 CI 为
  `HOSTED_BLOCKED_NO_RUNNER`，因此本轮状态是 **GAP（未验证）**，不是 PASS。

## 5. 关键行为在 LOCAL-02 中的真实执行覆盖

按节点名分类统计（同一节点可属于多个类别；计数只统计实际执行节点，不含 skip）：

| 行为类别 | 执行节点数 | 代表性已执行节点 |
| --- | ---: | --- |
| 项目创建/读取/生命周期 | 169 | `tests.test_v2_creative_project_lifecycle::test_same_title_recreate_preserves_history_but_never_revives_it[file]`<br>`tests.test_v2_creative_project_lifecycle::test_delete_waits_for_inflight_commit_then_recreated_owner_is_empty[file]` |
| 保存与重读（含幂等重试） | 2 | `tests.test_surface_pending_canon_review::test_original_canon_approve_retry_terminal_edits_reject_and_save_are_idempotent[file-/api]`<br>`tests.test_surface_pending_canon_review::test_original_canon_approve_retry_terminal_edits_reject_and_save_are_idempotent[file-/api/v1]` |
| CAS 冲突/版本栅栏 | 55 | `tests.test_structured_record_cas::test_original_record_create_compare_swap_and_no_private_conflict_payload[file-characters-hero-payload0]`<br>`tests.test_structured_record_cas::test_original_record_create_compare_swap_and_no_private_conflict_payload[file-locations-harbor-payload1]` |
| 跨项目/越权拒绝 | 230 | `tests.test_v2_creative_project_lifecycle::test_recreated_api_cannot_read_or_mutate_old_assets_or_bypass_authority[file]`<br>`tests.test_v2_creative_project_lifecycle::test_first_access_from_independent_scopes_uses_one_identity[file]` |
| 审核候选不得静默提升 | 44 | `tests.test_surface_pending_canon_review::test_canon_preview_cas_source_fence_human_review_no_duplicates_restart[file-/api]`<br>`tests.test_surface_pending_canon_review::test_canon_preview_cas_source_fence_human_review_no_duplicates_restart[file-/api/v1]` |
| 失败回滚/撤权/损坏 marker fail-closed | 121 | `tests.test_v2_creative_project_lifecycle::test_unbound_pre_incarnation_rows_are_preserved_and_fail_closed[file]`<br>`tests.test_v2_creative_project_lifecycle::test_revoked_write_does_not_adopt_or_modify_unbound_history[file]` |

注意：这些是**节点名分类**（用于快速审计），不等于完整需求矩阵；正式验收仍以
`requirements-traceability.json`、`RELEASE_GATES.md` 与完整套件为准。

## 6. LOCAL-02 明确不覆盖的层（各自独立记录）

| 层 | 状态 | 说明 |
| --- | --- | --- |
| 完整 File 后端套件（约 1.5 万条） | 未在本轮运行 | `RUNBOOK.md` / `BASELINE_20261019_r1.md` |
| 完整真实 PostgreSQL 套件（约 4.8 千条） | PARTIAL | D-07 hang 类已修复；本轮运行代表性 PG 子集，完整套件仍需单独长跑 |
| 真实浏览器旅程 | PARTIAL | LOCAL-04 只跑 2 个真实旅程；creative-workbench 套件不在 LOCAL-02 |
| 真实媒体/FFmpeg | 未包含 | 独立媒体验收层 |
| 模型/GPU 推理 | NOT_RUN / LOCAL_REQUIRED | 未授权模型 |
| Windows 安装/升级 | NOT_RUN | RELEASE_GATES G9 |

## 7. 复现

```powershell
# 1) 生成带 skip 原因的原始 JUnit（隔离 profile）
python scripts/run_local_ci.py --step LOCAL-02 --label audit-skips

# 2) 审计 skip 分类；--fail-on-pg-only 会在出现 PG-only 函数时失败
python scripts/audit_local_ci_skips.py --junit docs/v2/engineering/evidence/local-ci/audit-skips/LOCAL-02-junit.xml --fail-on-pg-only

# 3) 可选：有可处置真实 PostgreSQL 集群时，运行同一批契约的 PG 变体
python scripts/run_v2_postgres_checks.py --pg-bin <PG bin> --data <owned .runtime cluster> --port 55432 \
  --database v2_local_ci_pg --fresh-database local-ci-pg -- python -m pytest -q tests/test_v2_creative_project_lifecycle.py \
  tests/test_structured_record_cas.py tests/test_surface_pending_canon_review.py tests/test_shared_project_route_authority.py
```

## 8. 后续

1. 完整 PG 套件在 D-07 修复后仍需一次单独长跑并绑定 SHA（当前不冒充通过）。
2. symlink 契约需要 Linux/特权 runner；宿主 CI 恢复后自动覆盖。
3. 若未来出现新的 skip 消息，`audit_local_ci_skips.py` 会以退出码 1 报出未知 skip。


## 7. Skip 审计工具的严格配对（round-3）

- 旧实现按裸函数名匹配对照，会丢失模块/类与参数身份；round-3 改为：同一 module/class、同一函数名、
  仅把首个 backend token 由 `postgres` 规范化为 `file`，其余参数必须完全相同，且对照节点必须在本轮
  **passed** 集合中。跨模块同名、参数不同、对照被 skip、其他 backend 均判为 PostgreSQL-only。
- 反例回归：`tests/test_local_ci_skip_audit.py`（1 条合法配对 + 7 条反例/边界：跨模块同名、参数不同、
  缺对照、对照被 skip、未知 skip、symlink 允许、失败节点）。
- 用新工具重审已提交的 round-2 LOCAL-02 JUnit：**467/467 合法配对、0 PostgreSQL-only、0 unknown skip**；
  历史 467 项的配对结论不变，只是配对证据从“同名”收紧为“模块+类+完整参数”。
