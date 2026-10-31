# V2.0 能力补充报告（2026-10-31）

本报告汇总 V2.0.0 合并后（main `46ef2e12` 起）进行的能力补充批次。所有测试均为 Windows 11 + Python 3.11 + File/Windows 合成环境；真实 PostgreSQL、浏览器、真实模型/GPU、Windows 打包桌面、hosted CI、外部 NLE **仍 NOT_RUN**。本报告不是全能力验收通过证明。

## 1. 基线

- V2.0.0 主体合并：PR #51（`46ef2e12`，后端能力/安全硬化）、#52（`2d14f8c0`，全分支后端收尾）、#53（`d11c890c`，前后端对齐）、#54（`35253de6`，版本号 2.0.0）。
- 能力补充开始 main：`46ef2e12` / 报告生成时 main：`94abff88b66d37cd9ac164b9f3ee902145699cc9` / 最终验证于 main `12f03d9aed0ea23d829f2d44a00d1be71aec7a86`（报告合并前）。
- 所有补充批次经普通工作分支 + PR merge commit 合入 main，未强推/未删分支/未发布。

## 2. 补充批次

| # | PR | 合并 SHA | 能力 | 关键测试 |
|---|---|---|---|---|
| 1 | #55 | `9fd3524c` | 容量 admission 下沉到 `AssetLibraryService.create` 全部 16+ 调用方（手工导入/模型/遮罩/视频参考/生产产物等）；幂等重放不重复计费；失败残留计费 | 新增 5；容量组 75 passed |
| 2 | #56 | `6c00452a` | `capability_registry`（`v2-capability-registry/1`）：逐能力状态/证据/限制/真实环境边界 | 新增 4；组合 75 passed/1 xfailed |
| 3 | #57 | `dc571a66` | 音频历史写入启动对账门：旧进程账本 `reconciled_at` 过旧 → `AUDIO_HISTORY_CAPACITY_NOT_RECONCILED`，需重新 reconcile | 新增 1；容量/registry 组 81 passed |
| 4 | #58 | `bc73be0b` | Timeline `AUDIO_WAV_PCM24` 预设 + WAVE_FORMAT_EXTENSIBLE 有界解析/输出证明 | 新增 2；media/timeline 组 11 passed/1 skipped |
| 5 | #59 | `23e8c054` | Graph 三级媒体链：上游正式字节/digest 传递、第三级 UNKNOWN 栅栏/取消反例 | 新增 2；图组 19 passed |
| 6 | #60 | `51e0eca7` | 服务端 provider cost attestation（job/request/provider 绑定、sidecar、默认 UNKNOWN、损坏回退） | 新增 3；production/cost 组 80 passed/1 xfailed |
| 7 | #61 | `1b01cb6c` | 本地 VIDEO 时间线渲染到 `REVIEW_MP4`（真实 FFmpeg，无模型） | 新增 1；video/timeline/registry 组 14 passed |
| 8 | #62 | `898e6881` | Provider usage-only attestation：`USAGE_ATTESTED`（usage 可信、价格仍 UNKNOWN，后续价格 attestation 升级） | 新增 2；cost/registry 组 45 passed |
| 9 | #63 | `ac6cc6bf` | 容量写入覆盖矩阵 `project_capacity.write_entries`：admission/MEASURED_ONLY/NOT_CONNECTED/NOT_ACCOUNTED/MANAGEMENT_ONLY | runtime 18 passed；容量组 45 passed |
| 10 | #64 | `94abff88` | 项目 scope 文档（`experimental_v1`）归属计量：只读有界 `novel_id` 归属，接入 diagnostics/reconcile/admission 基线 | 新增 4；容量组 94 passed |

补充工作分支：`work/v2-capability-supplement-20261031`、`work/v2-capability-registry-20261031`、`work/v2-capacity-startup-gate-20261031`、`work/v2-graph-timeline-supplement-20261031`、`work/v2-graph-multinode-20261031`、`work/v2-cost-attestation-20261031`、`work/v2-video-capability-20261031`、`work/v2-usage-attestation-20261031`、`work/v2-capacity-coverage-20261031`、`work/v2-scope-doc-capacity-20261031`（均保留）。

## 3. 能力状态变化（相对 V2.0.0 合并时）

- **容量**：资产写入全调用方统一 admission；音频历史写入有启动对账门；scope 文档字节已归属计量；覆盖矩阵显式列出仍未接入的写入口。仍**非完整闭环**：scope 文档写入未 admission、导出/临时媒体/共享索引未计账、审批/撤权竞争/真实 PG/崩溃窗口未验收。
- **Graph**：三级媒体链字节/digest/UNKNOWN 栅栏已有合成证据；完整多节点未知恢复/真实模型仍 NOT_VERIFIED/NOT_RUN。
- **Timeline/VIDEO**：PCM16/PCM24 多轨音频导出、本地 VIDEO 轨到 REVIEW_MP4 渲染有真实 FFmpeg 证据；真实 NLE/模型视频/复杂多轨仍 NOT_RUN。
- **成本**：默认 UNKNOWN；provider adapter 可记录 priced/usage-only attestation，读取为 ATTESTED/USAGE_ATTESTED；真实 adapter/价格来源仍 NOT_INTEGRATED。
- **K1**：全能力 registry + 容量覆盖矩阵可机器读取；仍是状态读模型，不代表验收。

## 3.1 最终验证（2026-10-31）

在 main `12f03d9a` 上重跑合并后能力组：

- 命令：`python -m pytest tests/test_v2_capability_registry.py test_studio_runtime_capabilities.py test_provider_cost_attestation.py test_project_capacity_scope_documents.py test_project_capacity_create_coverage.py test_audio_history_capacity_accounting.py test_project_capacity_ledger.py test_project_capacity_diagnostics.py test_project_capacity_attribution.py test_project_capacity_admin_api.py test_graph_multinode_media_chain.py test_studio_timeline_audio_profiles.py test_studio_video_timeline_local_render.py -q`
- 结果：**96 passed**（Windows 11 / Python 3.11 / File 合成；无 skip/fail）。
- 状态：本组不覆盖真实 PG/浏览器/模型/打包桌面；相关环境仍 NOT_RUN。

## 4. 仍未完成 / 阻塞 / 产品决定

- **NOT_RUN**：真实 PostgreSQL（迁移 018–020、备份恢复、scope JSONB、崩溃窗口）、真实浏览器 E2E、真实模型/GPU/付费 Provider、Windows 打包桌面、hosted CI、外部 NLE、POSIX。
- **NOT_CONNECTED/NOT_ACCOUNTED**：项目 scope 文档写 admission、导出产物、临时媒体、共享查询索引。
- **BLOCKED**：PUBLISHING 独立审阅、Windows ACL/junction 探测（自动策略拒绝，未重试）。
- **PRODUCT_DECISION**：音频 canvas_return 目标/权限/审核语义、CJK 字体授权/随包字体、远程 frame provider 抓取策略、额度策略、历史产品线合并取舍。
- **UNKNOWN**：F37 的 37 次拒绝与 strict-warm 409 根因。
- **真实 provider adapter/价格来源**：未接入。
- **历史产品分支** `#36`–`#49`、`#26` 未合入 main。

## 5. 验证与证据

- 最终合并后能力组：96 passed（`Validation\backend-finalize-20261031\v2-capability-final-verify.log`）。

- 各批次测试日志位于本地 `D:\PoemSeed\Validation\backend-finalize-20261031\`（如 `v2-*-*.log`）；仓库内证据文档见 `docs/delivery/`。
- 关键组合：容量/registry/runtime 94 passed；cost 45 passed；graph 19 passed；video/timeline 14 passed；production/cost 80 passed/1 xfailed。
- 所有断言为合成/测试替身环境；不把上述数字当作真实模型/PG/浏览器/打包验收。

## 6. 回退

- 每批为独立 merge commit；可 `git revert -m 1 <merge-sha>`（#55–#64）或按提交逆序回退。
- 未改版本号（仍 2.0.0）、未发布、未创建 Release/Tag。
