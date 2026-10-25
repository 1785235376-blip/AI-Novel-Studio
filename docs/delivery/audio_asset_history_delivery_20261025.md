# PoemSeed Studio V2：单音频不可变历史交付

日期：2026-10-25。整体状态：**PARTIAL_SAFE_READ_ONLY_DELIVERY**。

已实际落地原 Asset owner 的不可变快照、安全历史读取、当前授权的 ASSET 来源追溯与只读恢复预览。成功恢复写入仍关闭。最终专项 **58 passed、3 warnings、exit 0**；这不是完整 M0–M7 或全仓验收通过。

## 基线与分支

| 项目 | 实际值 |
| --- | --- |
| 仓库 | 1785235376-blip/AI-Novel-Studio |
| 固定起点 | 11d8615cccb688462ff814d025b339e1b6eb0efe |
| 固定 tree | 353b8669da72659da2ead4d9b34ac255504c077a |
| 原分支 | work/hermia-backend-contracts-20261025 |
| 独立功能分支 | work/audio-asset-version-history-20261025 |
| 最终实现代码 SHA | 2e2fcb79209a3afc03dc7e443f5e1901ff233ee1 |

起点的完整 Git commit/tree、远端 ref 与新工作区状态均已核实。从 GitHub 新建隔离副本，未读取用户旧任务或素材。额外基线对照也使用本轮新建、固定起点的 detached worktree。

## 分阶段提交和上传

以下均已普通 push 至自己的功能分支，并用 ls-remote 读回相同 HEAD；没有 force push、main 更新、合并、PR 发布或部署操作。

| 阶段 | SHA | 内容 |
| --- | --- | --- |
| M0 | a52c4ada89721fd6f922f170e5af3207d7a68d6d | owner/写入覆盖矩阵、锁序、恢复边界和文件归属 |
| M1–M2 存储切片 | 1c1c80b67184bb8091487882c08b4878ebb49c28 | 原 owner 中央捕获、独立不可变 bytes/metadata、唯一提交 head、初轮真实证据 |
| M3 与 M4 只读边界 | 1866465a8766c61020e10a420ceb2471f5c1d54a | 历史 API、来源 pin 授权、ABA、预算、只读 inspect 与写端拒绝 |
| 审核修复 | 2e2fcb79209a3afc03dc7e443f5e1901ff233ee1 | 所有直接 reader 预算、预览标量投影、真实项目 lease 多进程 CAS；58 项最终回归 |
| M7 交付文档 | 本文所在的后续文档提交 | 交付矩阵、独立报告、完整日志校验清单；不修改实现代码 |

由 5 个实际 6astra 工作单元负责 owner/store、只读权限/API、恢复协议、并发故障测试与独立审核；共享入口由总控整合。子单元的执行/写入工具曾挂起或失败，改为其提供代码、总控在同一 Work 执行环境代落盘和验证，未把失败工具调用算作实现。

## 逐里程碑状态

| 里程碑 | 状态 | 已完成及剩余范围 |
| --- | --- | --- |
| M0 | 已核查 | 原 owner 全部直接写入入口、非 HTTP 调用、原锁序；原二进制仅 create 新 ID |
| M1 | 已实现、File 已验证 | metadata revision / history_sequence / version_id / bytes digest 区分，绑定原项目实例和 scope；明确历史缺口 |
| M2 | 已实现、File 已验证 | 原 _write_meta 捕获，独立 bytes/record，current metadata head 唯一提交点，additive 懒迁移 |
| M3 | 部分实现、所列子集已验证 | list/detail/download、授权 ASSET pin、当前身份/权限/特性/实例复核；非 ASSET 和无可证旧 pin 拒绝 |
| M4 | 部分实现、写端受阻 | 真实只读 preview；confirm/resolve 固定 409，无 token、无候选创建、无审核或引用修改 |
| M5 | 部分实现 | metadata 的真实多进程 CAS、原 create 幂等、四阶段强杀/重启通过；恢复 operation journal/receipt 未实现 |
| M6 | 部分验证 | File/原 /api 挂载共 58 项通过；PG NOT_RUN；原 query/cursor 对照 2 项受阻 |
| M7 | 已完成子集审核和交付 | 独立审核已关闭发现；完整任务保持 PARTIAL，不是可发布的完整恢复实现 |

## 实现与兼容范围

完整契约见 [audio_asset_version_history.md](../audio_asset_version_history.md)。逐项证据见 [验收矩阵](audio_asset_history_validation_matrix_20261025.md)；独立判断见 [独立审核报告](audio_asset_history_independent_review_20261025.md)。

原 `/assets/{aid}/restore` 保持撤销软删除含义。没有重做 Timeline、Job 历史、Canvas 历史或前端。没有新增同 Asset ID 的二进制覆盖接口；不同原始生成/导入结果仍是新 ID。

唯一修改的既有共享挂载入口为 `workspace_api.py` 的 19 行精确 admission/router mount。必要原 owner 改动集中于 `asset_library_service.py`；其余生产逻辑为新增 audio history 模块。未修改前端、SDK、TaskCenter、Production 查询、Asset 查询索引、依赖锁或全局路由架构。

内部 server metadata 写入若没有预增 revision，原 owner 在同 current revision/head 下为真实变更分配下一 revision；相同 metadata 不增历史，陈旧 head/版本仍拒绝。原查询测试没有被改弱。

保存的历史 JSON 使用 .bin 文件名，继续经过原 admitted Windows reader。记录保存完整内部 metadata；公开投影不返回私有参数、prompt、内部 provenance 或未授权来源 ID。来源 trace 的 CURRENT/HISTORICAL_VERIFIED 指 metadata/pin 证明，并明确 content_verified=false。

现限制：100 个状态/Asset、128 MiB 保留空间、512 KiB/record、8 MiB/次链读取和五秒截止；current/source metadata 有独立预算。新分配保留原 64 MiB 磁盘安全余量，但这不是跨应用空间 reservation，也没有建立项目历史总配额。

容量/版本上限、当前 bytes 损坏可能新增 audio delete/undelete 拒绝；其原“软删除/撤销软删除”操作意义不变。当前资产软删除时 history 不开放，先走原 undelete。cursor 使用进程密钥，重启或跨 worker 要重新分页。

## 恢复写端为何关闭

1. 原项目 1,000 Asset / 512 MiB current-binary 配额依赖 project_usage 扫描资产目录。直接调用它不满足严格有界恢复；跳过它会绕过原配额。
2. 原 Production review 绑定真实 Job 的候选和 immutable context，无法合法接管新的历史恢复候选。历史 approval 不能复制为新批准。
3. 全局唯一 operation intent、提交回执及精确不确定提交恢复协议没有实现；没有用确定性 UUID 或临时 callback 冒充这些保证。

因此 preview 明示 admission_available、confirmation_available、review_path_available 均为 false，candidate.created=false，token/expiry 为 null。confirm/resolve 经当前授权后返回 AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE。后续必须先补原 owner 可维护的有界配额合同、真实审核路径和唯一 operation 提交协议，才能开放写端。

## 本轮实际验证

```text
python scripts/run_audio_history_tests.py -q tests/test_audio_asset_history_owner.py tests/test_audio_asset_history_http.py tests/test_studio_workspace_identity_history_contract.py tests/test_asset_library.py --basetemp=.runtime/audio-history-20261025/final-post-review-temp
```

结果：**58 passed、3 warnings in 28.07s，exit 0**。分为 25 项 owner、26 项 HTTP、7 项原身份/Timeline/undelete/Asset 兼容。验证用真实 File 持久化、原挂载 HTTP、原身份/成员/授权服务、新子进程和重建 owner。四处 os._exit 是真实进程强制终止；低空间测量使用 shim，未实际填满磁盘。

独立审核最后两个反例先得到 **4 failed / 1 passed**，修复后定向 **6 passed**，包含原项目 incarnation/owner lease 的跨进程 CAS。之后才运行上列最终 58 项。没有删除或放宽失败断言。

原查询对照命令：

```text
python scripts/run_audio_history_tests.py -q tests/test_studio_asset_query.py::test_pagination_total_stable_ties_and_boundaries tests/test_studio_asset_query_cursor.py::test_stable_cursor_traversal_has_exact_visible_total_and_allowlisted_projection --basetemp=<本轮隔离目录>
```

当前实现与全新固定原基线各 **2 failed**，均为原 ASSET_QUERY_INDEX_UNAVAILABLE 503；直接诊断捕获原 index fsync 的 EBADF。它们不计通过；没有跨保护范围修索引。全仓回归与完整查询兼容仍未完成。

PostgreSQL **NOT_RUN**：本轮检查的相关数据库环境变量均无配置；未修改凭据、安装数据库或虚构 PG-native Asset 存储。真实 Provider、模型、FFmpeg 媒体执行、物理磁盘耗尽、断电、浏览器/桌面整机验收均未运行。原 atomic current-file rename 没有父目录 fsync 保证，结论只覆盖进程崩溃，不能称断电持久性。

## 原始日志与校验

[证据目录](../evidence/audio_asset_history_20261025/)保留起点、环境探测、修复前失败、原基线对照及每轮结果。raw stdout/stderr 以 gzip 无损保存；[raw_log_hashes.txt](../evidence/audio_asset_history_20261025/raw_log_hashes.txt)是解压后原字节的 SHA-256。没有旧任务日志、用户素材、真实秘密或私有历史进入提交。

最后实现 SHA 之后只提交交付文档与校验清单；无需重复相同专项测试来增加“运行次数”。
