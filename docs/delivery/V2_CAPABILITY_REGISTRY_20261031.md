# V2.0 能力注册表（2026-10-31）

`GET /api[/v1]/projects/{nid}/studio/production-contracts/runtime` 的 `capability_registry` 字段（契约 `v2-capability-registry/1`）是 V2 能力就绪状态的一处机器可读来源，等价于把此前的静态能力评估表放进原 Studio runtime 合同。

## 结构
- `real_environments`：真实环境状态（只允许 `NOT_RUN/BLOCKED/NOT_VERIFIED`）。
- `items`：`id, title, status, verification, gate, evidence, limits`。
- status 枚举：`IMPLEMENTED_VERIFIED_SYNTHETIC`（限定合成环境证据）、`PARTIAL`、`UNAVAILABLE_BY_FLAG`、`NOT_IMPLEMENTED`、`NOT_RUN`、`NOT_VERIFIED`、`BLOCKED`、`PRODUCT_DECISION`、`UNKNOWN`。
- verification 枚举：`FILE_SYNTHETIC/HTTP_SYNTHETIC/WINDOWS_SYNTHETIC/FILE_AND_HTTP_SYNTHETIC/NOT_RUN/NONE`。

## 当前边界（摘要）
- 真实 PostgreSQL、浏览器 E2E、真实模型/GPU、Windows 打包桌面、hosted CI、外部 NLE：`NOT_RUN`；
- PUBLISHING 独立审阅、Windows ACL/junction 探测：`BLOCKED`；
- 成本（真实 provider usage/价格/任务关联）、音频 canvas_return、历史产品线：`PARTIAL/PRODUCT_DECISION`；
- F37 的 37 次拒绝与 strict-warm 409 根因：`UNKNOWN`；
- 容量：已接入 `AssetLibraryService.create` 全调用方，但非资产写入口/启动对账门/审批竞争/真实 PG 仍未完成（`PARTIAL`，flag 默认关闭）。

本注册表是**能力状态读模型**，不是验收通过证明；任何 `IMPLEMENTED_VERIFIED_SYNTHETIC` 都只代表指定 File/Windows/HTTP 合成环境证据。
