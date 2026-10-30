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

