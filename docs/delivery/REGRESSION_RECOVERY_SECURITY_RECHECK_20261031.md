# 回归/恢复/安全复核：生命周期重建与 PR #49 D-17/D-20 调查（2026-10-31）

本文件覆盖交接要求中的“同 ID 删除重建、撤权、并发提交、损坏数据、异常退出/重启复核”，以及 PR #49 遗留 D-17/D-20 在**当前候选**上的适用性调查。基线对照为 A = PR #51 `317da4cc`；当前分支 `work/backend-finalize-20261031`。

## 1. 生命周期/重建/恢复定向组（当前候选，Windows 11 · Python 3.11 · File 合成）

命令：`python -X utf8 -m pytest tests/test_u16_mixed_stop_recreate.py tests/test_generation_restart_recovery.py tests/test_identity_binding_rebuild.py tests/test_taskcenter_lifecycle_http.py tests/test_taskcenter_store_lifecycle.py tests/test_v061_acceptance_lifecycle.py tests/test_cloud_canvas_create_recovery.py tests/test_asset_query_index_recovery.py tests/test_audio_asset_history_restore.py tests/test_project_capacity_ledger.py tests/test_u16_crash_claim_recovery.py -q`

- 结果：**223 passed, 1 failed, 6 skipped**（75s；日志 `Validation/backend-finalize-20261031/round12-lifecycle-recovery.log`）。
- 唯一失败 `test_u16_mixed_stop_recreate.py::test_mixed_stop_file_owner_orders_actual_child_process_recreation`：合成子进程未创建 ready 文件（`child failed before entering the project operation`）。该失败在 **A=`317da4cc` 独立 probe worktree 上同样失败**（19 passed / 1 failed），属**预先存在的子进程夹具/环境问题**，不是本工作分支引入；未删测试、未放宽断言。probe worktree 用后删除。
- 该组覆盖：U16 混合停止/项目重建顺序、生成重启恢复、身份绑定重建、TaskCenter 生命周期（HTTP/store）、验收生命周期、画布创建恢复、资产查询索引恢复、音频历史恢复崩溃窗口、容量账本跨进程/重启、U16 崩溃 claim。

## 2. PR #49 D-17 / D-20 适用性调查

PR #49（`work/v2-local-ci-community-20261019`）文档定义：

| 编号 | 原描述 | 原触发文件 |
|---|---|---|
| D-17 | prompt-process revocation 在 Windows 重负载下间歇失败（P3，MITIGATED/INTERMITTENT；专用 profile 24/24 通过） | `tests/test_v2_prompt_process_revocation.py` |
| D-20 | 完整测试套件在 interop universe 边界挂起（P3，OPEN/HARNESS；单文件 11/11 通过，全套件 17% 挂起） | `tests/test_post_interop_shared_universe.py` |

当前候选调查结果：
- 上述两个测试文件**不在当前 #51-line 基线中**：`git ls-tree origin/work/v2-local-ci-community-20261019:tests` 含这两个文件，而当前分支 `tests/` 无 `test_v2_prompt_process_revocation.py`、`test_post_interop_shared_universe.py`（PR #49 的 V2/local-interop 产品线未合并进当前候选）。
- 因此 D-17/D-20 在**当前候选不可复现、不可判定为已修复**；本文件只记录其“历史分支特定 harness 缺陷、当前候选不适用”，不关闭、不宣称 PASS。
- 当前候选有自己的撤销/恢复类覆盖（如 identity binding rebuild、collaboration 撤权、U16 停止重建、generation restart recovery、asset query index recovery 等），但这些**不等价于** PR #49 的 D-17/D-20 场景；不得用其通过替代原编号结论。
- 若未来合并 V2/local-interop 线，应重新引入这两个文件并按原 RUNBOOK（pytest-timeout/faulthandler、完整套件固定 SHA）复测。

## 3. 边界

- 全部为 Windows/File 合成证据；真实 PostgreSQL、浏览器、真实模型、Windows 打包桌面未运行。
- 未执行完整全仓库测试套件；本节是定向组，不是全产品验收。
- 未修改产品代码（调查未发现本分支引入的回归；唯一失败为基线已有的子进程夹具问题）。
