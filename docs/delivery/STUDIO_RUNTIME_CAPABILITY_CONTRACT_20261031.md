# Studio 运行时机器可读能力合同（K1 扩展，2026-10-31）

本文件记录批次 4 第一部分：在既有 `GET /api[/v1]/projects/{nid}/studio/production-contracts/runtime`（`studio-runtime-capabilities/1`）上，把本工作分支新增的**音频历史、项目容量、U16 批次门**能力以严格封闭 schema 暴露给客户端/运维诊断。合同仍为只读、无写副作用，且只声明服务端边界，不宣称端到端验收通过。

## 1. 新增合同字段

### 1.1 `audio_asset_history`
- `gate`: `"ENABLE_AUDIO_ASSET_HISTORY"`（唯一 gate 名）
- `enabled`: bool（服务端实时开关，默认 false）
- `capture / version_history_read / version_detail / version_download / explicit_migration / version_restore`: `ENABLED` 或 `UNAVAILABLE`
- `record_contract`: `"audio-asset-history/1"`；`restore_contract`: `"audio-asset-history-restore/1"`
- `restore_semantics`: `"NEW_TRACEABLE_CURRENT_VERSION_REVIEW_NOT_INHERITED"`
- `legacy_reads_migrate`: 固定 `false`（GET 不迁移）

### 1.2 `project_capacity`
- `gate`: `"ENABLE_PROJECT_CAPACITY_ADMISSION"`；`admission_enabled`: bool（默认 false）
- `ledger_contract`: `"project-capacity/1"`；`measurement`: `"LOGICAL_FILE_LENGTH_NOT_ALLOCATED"`；`allocated_storage_bytes`: `"UNKNOWN"`
- `content_admission`: `FLAG_GATED` 或 `UNAVAILABLE`
- `explicit_reconcile`: `"EXPLICIT_OPERATION"`；`limit_adjustment`: `"MANAGEMENT_LEASE_CAS_AUDIT"`
- `unknown_objects`: `"REPORT_ONLY_BLOCKS_NEW_RESERVATIONS"`
- `error_codes`: 稳定错误码列表（EXCEEDED / UNKNOWN_BLOCKED / VERSION_CONFLICT / NOT_RECONCILED / LEDGER_UNAVAILABLE / RESERVATION_UNKNOWN / COMMIT_EXCEEDS_RESERVATION）

### 1.3 `u16_batches`
- `gate_before_claim`: `"IMPLEMENTED_FILE_SYNTHETIC_ONLY"`（关闭门先于 RUNNING claim/attempt/receipt/reservation；仅 File 合成证据）
- `interrupted_running_claim`: `"UNKNOWN_NO_REPLAY"`
- `real_postgres` / `real_broker`: `"NOT_RUN"`

原有字段（`asset_query_cursor`、`model_inference_acceptance`）保持不变；schema 仍为封闭结构（未知字段/非法字面量被拒绝）。

## 2. 验证

- `tests/test_studio_runtime_capabilities.py` 扩展为 14 项：默认关闭时新能力全部 `UNAVAILABLE`/`enabled=false`；打开两个 flag 后对应字段实时变为 `ENABLED`/`FLAG_GATED`；读取前后磁盘快照不变（无写副作用）；两 API 前缀结果一致；成员撤权、项目重建、特性关闭仍 fail-closed；新增封闭 schema 反例（`version_restore="AVAILABLE"`、`content_admission="OPEN"` 被拒绝）。
- 回归组合（运行时能力 + 容量管理/诊断/归属 + 音频历史读取/恢复 + production query + storage）：**102 passed**。

## 3. 边界/未完成

- 该合同只反映服务端 flag 与已实现边界；`ENABLED` 不等于真实 PostgreSQL/浏览器/真实模型/打包桌面验收通过。
- 未增加任何写路径或放宽关闭门；默认 flag 仍为 false。
- 历史写入容量预留/失败残留计费、恢复审计持久化、真实 PG/broker 运行仍为 NOT_RUN。

## 补充：V2 全能力注册表（2026-10-31 续）

`GET /api[/v1]/projects/{nid}/studio/production-contracts/runtime` 在原有能力字段之外新增 `capability_registry`（`v2-capability-registry/1`），用同一原读权限/项目 activation/最终 guard 返回机器可读的 V2.0 能力就绪清单：

- `real_environments`：`real_postgres`、`real_browser_e2e`、`real_model_gpu_provider`、`windows_packaged_desktop`、`hosted_ci`、`external_nle` 均为 `NOT_RUN`；`publishing_review`、`windows_acl_junction_probe` 为 `BLOCKED`。
- `items`：每项含 `id/title/status/verification/gate/evidence/limits`；status 枚举限定为 `IMPLEMENTED_VERIFIED_SYNTHETIC / PARTIAL / UNAVAILABLE_BY_FLAG / NOT_IMPLEMENTED / NOT_RUN / NOT_VERIFIED / BLOCKED / PRODUCT_DECISION / UNKNOWN`。
- 音频历史与项目容量按 flag 实时反映为 `IMPLEMENTED_VERIFIED_SYNTHETIC/PARTIAL` 或 `UNAVAILABLE_BY_FLAG`；成本、canvas_return、历史产品线等明确标为 `PARTIAL/PRODUCT_DECISION`，F37/warm-409 标 `UNKNOWN`。
- 只读、确定性（无时间戳/随机值）、不写盘、不改变既有 capability 字段；不把合成证据提升为真实环境通过。

## 补充：容量写入覆盖矩阵（2026-10-31 续）

`runtime` 合同的 `project_capacity.write_entries` 现在逐项列出容量 admission 覆盖状态：
- `file_asset_create`：`ADMISSION_GUARDED_VIA_ASSET_CREATE`（flag 开）/`UNAVAILABLE`（默认），覆盖 `AssetLibraryService.create` 全部 16+ 调用方；
- `studio_manual_import`：`ADMISSION_GUARDED`/`UNAVAILABLE`；
- `audio_history_commit`：双 flag 时 `ADMISSION_GUARDED`（仅记录/blob）；
- `project_scope_document`、`export_outputs`：`NOT_CONNECTED`（仍由原 owner/配额管理）；
- `temporary_media`、`shared_query_index`：`NOT_ACCOUNTED`；
- `limit_adjustment`：`MANAGEMENT_ONLY`（lease+CAS+audit，不计量）。
该矩阵只读、确定性、不写盘；默认 flag 关闭时所有 admission 项显示 `UNAVAILABLE`，避免把能力合同误读为已开启。

