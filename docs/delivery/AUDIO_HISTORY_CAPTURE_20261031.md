# 音频单资产不可变历史：批次 3 第一部分（捕获层，flag 保护）

本文件记录批次 3（音频历史/恢复）第一部分。**恢复写端仍未开放**，历史读取 API 未接线；所有能力由 `ENABLE_AUDIO_ASSET_HISTORY`（默认 **false**）保护，默认行为与历史基线一致。

## 1. 实现内容

| 组件 | 内容 |
| --- | --- |
| `app/services/audio_asset_history_store.py` | 从固定旧源码 `2acab55d2ef64ca76f2093e376bf6388af364282` 的原实现审查复用：`.audio-history/<asset_id>/{records,blobs}` 不可变记录 + 内容 blob、`audio-asset-history/1` 记录合同、sha256/版本/序列/parent 链校验、读取预算（8 MiB/5s/100 版本）、保留容量上限、reparse/非普通文件拒绝、硬链接式不可变写入、临时文件清理 |
| `AssetLibraryService._write_meta` | flag 开启且 `kind=="audio"` 时：先在原 asset-library 锁与 `workspace_mutation` 内准备记录/blob，再以当前 metadata 文件为唯一提交点写入 `_audio_history_head`；`fault` 注入点覆盖 blob 后、记录后、当前提交前后。flag 关闭时保持原 `atomic_write` 路径逐字不变 |
| 迁移策略适配 | **显式迁移**：当前合同禁止写入时惰性补造历史。旧未捕获音频资产在 flag 开启后的首次 metadata 写入返回 `AUDIO_HISTORY_CAPTURE_REQUIRED`，不写历史、不改当前 metadata；迁移入口留待后续显式操作 |
| `project_capacity_attribution` | 归属资产的历史目录 `.audio-history/<asset_id>` 按真实文件字节计入测量（`history_bytes/history_objects`，同一物理对象一次、reparse/不可读记 UNKNOWN），使历史字节进入容量对账而非被忽略 |

抓取覆盖同一 owner 的 `create` / `update_metadata`（含无变化不新增版本）/ `delete` / `restore` / `promote_owned` / text review 等经过 `_write_meta` 的路径；同内容 blob 只存一份。

## 2. 测试与证据（Windows · Python 3.11 · File 合成）

`tests/test_audio_asset_history_capture.py`（8 项）：
- flag 关闭：不创建历史目录、不写 head；
- 新建音频资产：1 条基线记录、版本/序列/parent、blob 摘要与正文一致；
- metadata 新 revision：追加第 2 条记录、parent 指向旧 head、同内容 blob 去重；无变化写入不新增版本；
- 旧未捕获资产（flag 先关后开）写入 → `AUDIO_HISTORY_CAPTURE_REQUIRED`，metadata 与目录均不变（GET 不迁移）；
- delete / restore：记录为第 2/3 个版本且链完整；
- 篡改历史记录 → 写入 fail closed，当前 metadata 保持不变；
- 既有只读历史路由对已捕获资产仍返回 `AUDIO_HISTORY_FORMAT_NOT_INTEGRATED`，GET 前后磁盘快照一致；
- 容量归属测量：`history_bytes` 等于历史目录真实文件字节，`complete=True`。

回归：音频历史状态/工作区身份历史/资产物理观测/资产查询/手工上传关闭/容量归属+诊断+管理+账本共 **135 passed**。

环境说明：`tests/test_audio_history_media_baseline_20261028.py` 的独立 fixture 在本机报 `KeyError: 'PROJECT_ROOT'`（该文件自有 fixture 的环境依赖，本轮未改动该文件），计为环境/夹具问题而非产品通过或失败原因。

## 3. 未完成 / 下一步

1. 历史读取 API（list/detail/download、分页与预算）与显式恢复（按用户决定生成可追溯新当前版本）尚未接线；当前只读路由保持 `AUDIO_HISTORY_FORMAT_NOT_INTEGRATED`/`UNAVAILABLE`。
2. 显式迁移入口（旧资产 → 基线历史）未实现；旧资产历史缺失按合同保留。
3. 恢复写端的授权/CAS/幂等/并发/崩溃窗口、容量预留与失败残留计费、跨 restart 对账仍未实现。
4. 历史 blob/记录写入尚未接入项目容量预留与提交协议；当前 flag 默认关闭，不能宣称容量闭环。
5. 真实 PostgreSQL、浏览器、真实模型与 Windows 打包桌面未运行。


## 4. 批次 3 第二部分：历史读取 API 与显式迁移入口（2026-10-31 续）

`ENABLE_AUDIO_ASSET_HISTORY` 开启时：

| 入口 | 行为 |
| --- | --- |
| `GET /api[/v1]/projects/{nid}/studio/assets/{aid}/history` | 已捕获资产返回 `coverage=CAPTURED`、`head`、`current_version`、按新→旧排列的不可变版本项（source-free `version_view`：version_id/asset_version/history_sequence/sha256/size/metadata 子集）与 `next_cursor=null`；未捕获旧资产返回 `UNCAPTURED` 空列表，**不写历史/不迁移**；沿用原查询合同：`limit` 1..50、非法 422、`cursor` 409 `AUDIO_HISTORY_CURSOR_UNAVAILABLE`；链长度超过 `limit` 时拒绝部分分页（同 409 cursor code，fail-closed） |
| `GET .../history/{version_id}` | 详情仅允许当前链内版本（链完整性校验后），不在链内 → 409 `AUDIO_HISTORY_VERSION_NOT_IN_CHAIN` |
| `GET .../history/{version_id}/download` | 返回历史内容字节（摘要/大小由记录与 blob 校验），带 `X-Asset-SHA256`/`X-Asset-Version`/`X-History-Version-Id` 响应头；媒体类型来自记录投影 |
| `POST .../history/migrate` | **显式迁移**：原写权限 + `commit_invoke` 授权租约 + expected_version CAS；校验当前正文摘要后把当前修订捕获为基线记录并写入 `_audio_history_head`；重复迁移 409 `AUDIO_HISTORY_ALREADY_CAPTURED`；flag 关闭 409 `AUDIO_HISTORY_UNAVAILABLE`；不增量伪造旧版本 |
| flag 关闭 | 保持原有只读状态：旧资产 `UNCAPTURED`，带 head 的资产仍 409 `AUDIO_HISTORY_FORMAT_NOT_INTEGRATED`；历史详情/下载/迁移 409 `AUDIO_HISTORY_UNAVAILABLE` |

读取路径均不迁移、不初始化历史目录；读取预算与记录完整性由 store 执行，返回前重新 `guard()`。三条新路径已加入 `is_independent_studio_route` 精确 GET/POST 允许清单（version_id 限 64 位小写 hex）。

验证：`tests/test_audio_asset_history_api.py` 8 项（两别名列表/顺序、limit/cursor/非法查询、详情/下载/未知版本、旧资产读取不迁移、显式迁移成功/重复/flag-off/stale CAS、allowlist）；音频历史全组（8 个既有 audio-history 套件 + 捕获 + 读取 + 容量归属 + 资产查询）**124 passed / 1 skipped**。

仍未完成：显式恢复（生成可追溯新当前版本）及其授权/CAS/幂等/并发/崩溃窗口、历史写入容量预留、取消/失败残留计费、真实 PostgreSQL/浏览器/模型验证。

## 5. 批次 3 第三部分：显式恢复生成可追溯新当前版本（2026-10-31 续）

`ENABLE_AUDIO_ASSET_HISTORY` 开启时新增：

- `POST .../assets/{aid}/history/{version_id}/restore/preview`（读权限）：返回 `studio-audio-history-restore-preview/1` —— 当前/目标版本投影、`restored_fields`、差异、`expected_new_version`、绑定 `restore_digest`（对 canonical plan 做 sha256：asset_id/incarnation/current_version/target version_id/target metadata_digest/restored_fields/review_inherited=false）。只读，不写盘、不迁移。
- `POST .../assets/{aid}/history/{version_id}/restore`（`commit_invoke` 写权限租约）：确认须携带 `expected_version` + `expected_restore_digest`；在 owner 锁内重新校验当前版本、目标仍在链内、目标与当前 sha256/size 一致、plan digest 未变，然后以当前 metadata 为基底应用 `restored_fields`，**版本 +1** 生成新当前版本，并由原 `_write_meta` 历史捕获路径追加新记录（parent=旧 head），写入 `_audio_history_restore_origin` 记录目标 version_id/digest/restored_fields/`review_inherited=false`/操作者/时间。旧链保持不变。
- 恢复字段范围（本批产品边界）：仅可逆展示/创作字段 `filename / parameters / character_id / scene_id`；`parameters` 中的特权键 `asset_lineage_v2`、`asset_relationships_v2` 被移除，不通过恢复绕过版本化谱系/关系写入。审批、评审、来源、source_asset_ids、内部标记、HEAD 状态**不从目标继承**；目标上的旧审核只作追溯。
- 失败/竞争语义：重复/丢失响应后的再次确认因版本已变为 409 `AUDIO_HISTORY_VERSION_CONFLICT`；plan digest 不符 409 `AUDIO_HISTORY_RESTORE_PLAN_CHANGED`；目标不在链内 409；未捕获资产 409 `AUDIO_HISTORY_UNCAPTURED`；flag 关闭 409 `AUDIO_HISTORY_UNAVAILABLE`。并发两个确认只有一个成功（另一个 409，链只 +1）。当前 metadata 提交前注入失败：metadata 不变、链不变，重试成功（已准备的不可达记录只计入容量，不暴露为历史）。

验证：`tests/test_audio_asset_history_restore.py` 7 项（preview 不写盘、确认生成新版本且保留旧链、非继承审核、stale/digest 反例、并发、flag/未捕获/未知目标、提交前崩溃恢复、allowlist）；音频历史+容量归属+资产查询+容量管理全组 **142 passed / 1 skipped**（日志 `batch3c-regression.log`）。

仍未完成：历史存量的容量预留/失败残留计费、恢复操作审计持久化（当前仅写入 asset metadata marker）、跨 owner/真实 PG 崩溃窗口、浏览器与真实模型验证。


## 6. 批次 2e：音频历史写入容量预留/结算（双 flag 保护，2026-10-31 续）

仅当 **同时** 开启 `ENABLE_AUDIO_ASSET_HISTORY` 与 `ENABLE_PROJECT_CAPACITY_ADMISSION` 时生效；默认关闭时行为与既有测试完全不变（历史写入不建/不读容量账本）。

- `AssetLibraryService._write_meta` 的历史分支在准备记录/blob 之前：要求 meta 具备 `_project_binding{novel_id,incarnation}`（缺失即 `AUDIO_HISTORY_CAPACITY_PROJECT_UNBOUND`）；读取 `data/runtime/project-capacity.json` 已对账快照——账本不存在/未对账 → `AUDIO_HISTORY_CAPACITY_NOT_RECONCILED`，UNKNOWN blocked → `AUDIO_HISTORY_CAPACITY_UNKNOWN_BLOCKED`，超额 → `AUDIO_HISTORY_CAPACITY_EXCEEDED`；均在任何历史字节落盘前 fail closed。
- 预留额度 = 512 KiB 记录上限 +（该内容 blob 尚不存在时）正文大小；TTL 300s、operation=`audio.history.commit`、绑定项目 incarnation。
- 当前 metadata 提交点成功后，按**历史目录实际增量**结算：`after_bytes - before_bytes`（仅新记录/新 blob，链上旧字节不重复计费）→ ledger `commit(actual)`；无增量则释放。
- 当前提交失败：仍先结算已准备记录/blob 的实际增量（残留继续计费，不会被释放成免费空间），再释放预留；结算异常不改变历史/当前提交语义，由 TTL + 下次显式对账兜底。
- 幂等/无变化 metadata 写入不产生历史增量 → 不增计费。
- `capacity_reconcile` 的 UNKNOWN 计数现在同时包含 assets 根目录不可归属的残留普通文件（`unattributed_files`），与 admission 的 UNKNOWN 判定一致。

测试：`tests/test_audio_history_capacity_accounting.py` 7 项——实际增量计费/审计、revision 只计新增记录（blob 去重）、未对账拒绝、超额拒绝且写前无副作用、UNKNOWN blocked 拒绝与恢复、当前提交前崩溃仍计费残留且无预留泄漏、双 flag 关闭时无账本行为。回归组合（音频历史全部套件 + 容量原语/诊断/归属/管理/admission + U16）：**151 passed / 1 skipped**。

边界：本批只覆盖历史记录/blob 写入的容量预留与结算；资产正文/metadata 主写入仍由各自的 admission/关闭门负责；真实 PostgreSQL/浏览器/模型未运行。

## 7. 批次 3 补充：恢复的权限/重建/并发反例（2026-10-31 续）

`tests/test_audio_history_restore_authority_races.py`（3 项，通过）：

- **项目重建**：预览后删除并同 ID 重建项目（incarnation 变化）→ 确认恢复返回 404/409，磁盘快照不变（旧资产/历史不可被新 incarnation 采用）。
- **恢复 vs metadata 编辑竞争**：同一 `expected_version` 下并发执行显式恢复与 metadata 编辑 → 恰好一个成功、另一个 409 `AUDIO_HISTORY_VERSION_CONFLICT`；历史链只追加 1 个版本（[4,3,2,1]），恢复标记仅在恢复成功时存在。
- **flag 关闭后预览**：预览接口返回 409 `AUDIO_HISTORY_UNAVAILABLE` 且磁盘无写。

本地模式边界说明：恢复写入口依赖原项目权限 + `commit_invoke` 的 commit authority/incarnation 复核，不依赖 local-mode 的 session token 作为授权来源；历史只读路由的 session 撤销语义仍由原 route 的 session guard 处理。\n\n协作模式补充（`tests/test_audio_history_collaboration_authority.py`，3 项通过）：在真实 collaboration scope/activation 下，预览后撤销 session 或停用成员，恢复与历史读取均 401/403 且不追加版本；仅有读权限（无 domain.write）的成员预览可读、确认恢复 401/403 且无写入。均通过既有原权限 owner fail closed，无需新增授权 owner。

