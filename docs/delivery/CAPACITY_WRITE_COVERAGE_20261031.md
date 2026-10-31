# 容量写入覆盖矩阵（2026-10-31）

`GET /api[/v1]/projects/{nid}/studio/production-contracts/runtime` 的 `project_capacity.write_entries` 给出逐入口容量 admission 覆盖，避免把“部分写入口已接入”误读为完整容量闭环。

| entry | flag off | flag on | 说明 |
|---|---|---|---|
| file_asset_create | UNAVAILABLE | ADMISSION_GUARDED_VIA_ASSET_CREATE | AssetLibraryService.create 全部 16+ 调用方统一 admission |
| studio_manual_import | UNAVAILABLE | ADMISSION_GUARDED | 路由 admission + `_capacity_admitted=True` |
| audio_history_commit | UNAVAILABLE | ADMISSION_GUARDED（双 flag） | 仅 capture/migration/restore 记录与 blob |
| project_scope_document | NOT_CONNECTED | NOT_CONNECTED | experimental_v1 scope 文档仍由原 owner，未接入统一账本 |
| export_outputs | NOT_CONNECTED | NOT_CONNECTED | 导出产物保留原配额 |
| temporary_media | NOT_ACCOUNTED | NOT_ACCOUNTED | FFmpeg/临时暂存由 storage admission 限制，不计项目账本 |
| shared_query_index | NOT_ACCOUNTED | NOT_ACCOUNTED | 共享派生索引/游标非项目所有 |
| limit_adjustment | MANAGEMENT_ONLY | MANAGEMENT_ONLY | lease+CAS+audit，不计量/不预留 |

只读、确定性、不写盘。真实 PG/崩溃/审批竞争仍 NOT_RUN；该矩阵不是容量完整验收证明。
