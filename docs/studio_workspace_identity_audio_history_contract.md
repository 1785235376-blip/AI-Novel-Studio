# Studio 项目实例与音频历史：现有后端合同

审计基线：`4c5535481158de3ce7f0e7dbe5aa00d7058eccec`。对照前端交接提交 `f778eaec77e5cbda4c29766ced51455816180066` 的 `docs/delivery/INTERFACE_COVERAGE.md`（G-ID-1、G-AUD-5）。本增量仅补合同说明和真实 File/HTTP 合同测试，不修改生产 owner、权限、身份、前端或持久数据格式。

## 结论与对接点

- **G-ID-1 不是“后端没有 project incarnation”**。原 Studio overview 已公开权威 `project.incarnation`。旧 `Novel` 前端类型、bootstrap 或可重用项目 ID 本身不提供这项保证，不应从 workspace/storyline/branch 或 `created_at` 推造实例 ID。
- **G-AUD-5 需要区分三种历史**：音频 Timeline 编辑历史与恢复已有；单 Audio Asset 的通用旧版本快照/历史二进制恢复没有；ProductionJob 列表是多次任务的当前持久回执，不是一个任务或资产的完整版本链。
- CanvasView history 记录卡片布局和资产 pins；恢复画布不重新生成音频，也不恢复 Asset 的历史 metadata/binary。不能把它、Timeline history 或 Job 列表命名为通用“音频资产版本历史”。
- G-AUD-4 的 `canvas_return` 仍遵守原 LOCAL_FFMPEG trim 来源绑定；本增量不扩大到其他音频操作。

## 1. 原项目实例：已有可用字段

`GET /api/projects/{nid}/studio`

响应中的相关字段如下（UUID 为格式示例，实际值必须来自本次服务器响应）：

```json
{
  "project": {
    "id": "project-slug",
    "title": "Project title",
    "incarnation": "file:11111111-1111-4111-8111-111111111111",
    "entry_kind": "NEUTRAL_STUDIO"
  },
  "capabilities": {"can_mutate": true, "can_review": true}
}
```

这里只展示身份字段及部分响应字段；省略了完整 preferences/capabilities，消费方应以实际响应为准。核心依据：

- `app/creative/workspace.py:74–92`：同一原 owner lease 下读取项目和 incarnation，返回 `project.incarnation`。
- `app/creative/workspace_api.py:284–297`：原 `domain.read` 路由；`can_mutate`、`can_review` 是当前能力提示，不是未来操作授权。
- `app/creative/project_store.py:79–123`：File marker 位于可删除项目目录中的 `creative_project_v2.json`；缺失时按原初始化规则生成 UUID4。PostgreSQL 读取原 `novels.id` UUID，不建第二套 owner。
- `app/project_retirement.py:62–107`：File 删除退役整个原目录；PostgreSQL 删除原 Novel 行。重建相同 slug 产生新 owner。`app/repositories/postgres/models.py:29–37` 的主键默认 UUID4。
- `app/creative/project_store.py:129–149`：原 scope document 仅投影当前 incarnation 的数据，旧绑定不会被新 owner 接管。

对接时把 incarnation 与真实 actor/scope 和相关对象版本一起使用，重新打开或恢复持久草稿前重新读取。incarnation 是身份比较值，不是会话 token 或权限凭证。删除期间 GET 可返回 404；权限拒绝/网络错误并不证明删除，不得据此把未知状态伪装成已删除。现有接口不是持久 tombstone/event feed，不能声称提供关闭应用期间的完整删除事件追踪。

**首次读取边界**：原 overview/invoke 可按既有规则初始化 File marker，因此不能宣称它对全新项目“零文件写入”。专用观察路由的 `existing_owner_only()` 才明确拒绝补建 identity；本次不改变二者语义。

**Production 投影边界**：generic `ProductionJob`（`production_execution.py:739–775`）、Timeline record（`:1480–1517`）和 Timeline history envelope（`:1942–1948`）目前不含通用顶层 incarnation。不能假设每个 Job 的 command 都包含 Canvas capsule。应从授权 overview 取得当前项目实例；特定 Canvas capsule/observation 的 incarnation 只适用其原合同。无需为了 G-ID-1 新建身份 registry 或改变通用 Job 合同。

## 2. 音频 Timeline：已有编辑历史和恢复

音频使用原 Timeline owner，显式 `schema_version: 3`、`media_kind: "AUDIO"`，不是第二个音频编辑存储。`app/services/studio_timeline_render.py:69–78` 进入原 normalizer；`studio_timeline_schema.py:16–25,48–55` 限定 schema 3 和 AUDIO 轨。

现有路由均位于 `/api/projects/{nid}/studio/production`：

| 操作 | 路由 | 作用 |
| --- | --- | --- |
| 创建 / 更新 | `POST /timelines` / `PUT /timelines/{tid}` | 保存编辑定义；更新使用 `expected_version` |
| 读取 | `GET /timelines/{tid}` | 当前 Timeline record |
| 历史 | `GET /timelines/{tid}/history` | 原有历史定义，不含当前定义 |
| 恢复 | `POST /timelines/{tid}/restore` | 核对当前版本与摘要，恢复旧定义为新版本 |

路由依据：`app/creative/production_execution_api.py:537–576`。旧版本由原 `change_row` 保存，见 `app/experimental/common.py:23–49`；不增加第二套历史记录。

历史响应形状：

```json
{
  "timeline_id": "original-timeline-id",
  "current_version": 2,
  "items": [
    {
      "id": "original-timeline-id",
      "novel_id": "project-slug",
      "title": "Audio edit",
      "version": 1,
      "timeline_digest": "<original SHA-256>",
      "timeline": {
        "schema_version": 3, "media_kind": "AUDIO", "duration_ms": 100,
        "tracks": [{
          "id": "dialogue", "kind": "AUDIO", "order": 0, "role": "DIALOGUE",
          "muted": false, "gain_db": 0.0,
          "clips": [{
            "id": "clip-one", "start_ms": 0, "in_ms": 0, "out_ms": 100,
            "speed_num": 1, "speed_den": 1, "muted": false, "gain_db": 0.0,
            "fade_in_ms": 0, "fade_out_ms": 0,
            "source_snapshot": {
              "id": "original-audio-asset-id", "kind": "ASSET", "asset_kind": "audio",
              "version": 1, "digest": "<original Asset SHA-256>"
            }
          }]
        }]
      },
      "created_at": "<original timestamp>",
      "updated_at": "<original timestamp>",
      "branch_id": null
    }
  ]
}
```

这是字段示意，不是可提交测试数据。`items` 为逆序旧版本；刚创建的 v1 返回空 `items`。读取当前定义应调用 GET record，而非从历史猜“最新”。原记录还可按其来源包含已验证的 edit/transfer/source receipts。

恢复请求的四个字段来自当前记录和选中的旧版本：

```json
{
  "expected_version": 2,
  "reviewed_timeline_digest": "<current SHA-256>",
  "restore_version": 1,
  "restore_digest": "<selected historical SHA-256>"
}
```

模型：`app/creative/production_execution_models.py:635–639`。实现：`production_execution.py:1942–1972`。成功产生 v3，v1/v2 历史不覆盖；每个引用的 Asset ID/version/digest/kind 必须仍为当前可用正式资产（`:1860–1878`）。旧 Asset pin 已过期或删除会拒绝恢复，不能通过恢复 Timeline 回滚素材。恢复只保存定义，不入队、渲染、审核或采用。原历史上限 100 个旧版本、25 个 Timeline 和集合字节限制仍有效。

## 3. 单 Audio Asset：没有通用历史版本回退

`GET /api/projects/{nid}/studio/assets/{aid}` 读取当前资产 metadata。其 `version` 是原 Asset 的 CAS revision，不等于可遍历的二进制版本库。

`POST /api/projects/{nid}/studio/assets/{aid}/restore` 只接受：

```json
{"expected_version": 2}
```

它撤销软删除、保留相同资产 ID/字节/SHA，并使当前 metadata version 递增，例如 v1 → 删除 v2 → 恢复 v3。**不是**恢复至 v1。额外 `restore_version` 不属于闭合请求模型，会被拒绝。依据：`workspace_models.py:140–141`、`workspace_api.py:536–546`、`asset_library_service.py:1323–1344`。

通用 metadata 更新只写当前 metadata 并递增 version（`asset_library_service.py:1137–1160,1241–1249`）；资产建立时也没有通用历史快照集合（`:553–556`）。lineage annotation 内部 history（`:1312–1320`）仅是来源声明历史，不是完整资产版本。当前没有 `/studio/assets/{aid}/history` 或按历史版本读取/回退 binary 的路由。

若产品真正需要完整单音频资产版本链，应另行确定“版本”的对象和恢复语义，再在原 Asset owner 内设计存储/迁移、权限/来源可见性、CAS、旧 pin 与容量合同。本增量不冒充实现该能力，也不从多个 Job 按时间猜测同一资产版本链。

## 4. ProductionJob：已有任务回执，不是状态事件历史

- `GET /api/projects/{nid}/studio/production/jobs`：原各类任务的当前持久回执列表。
- `GET /api/projects/{nid}/studio/production/jobs/audio/{jid}`：当前原 AudioJob 回执。
- 通用投影包含 `owner`, `id`, `novel_id`, `branch_id`, `version`, `status`, `attempt`, `request_id`, `request_digest`, `receipt_digest`, `sources`, `output_candidate`, `approved_asset_version` 等；不把 version 当作可回放状态历史。
- `app/services/studio_audio_execution.py:594–624` 保留/读取当前实例的各次原任务；`:632–647` 更新单行回执；`:865–869,1066–1071` 的 generations 按 job_id 替换而非追加所有中间状态。
- legacy `/novels/{nid}/audiobook/jobs` / speech-generations 不能替代 Studio 原 owner。`app/audio_production_store.py:94–100` 明确从 legacy 读取投影中排除 Studio rows。

## 5. scope、权限与验证边界

所有 Studio 路由保留原 feature/actor/project/branch/domain guards。`workspace_api.py:191–219` 在操作前后核对授权 scope 与 incarnation；Production 还要求原 Host session/principal（`production_execution_api.py:149–178`）。Timeline 仅其 `created_by` actor 可读，scope/incarnation 必须一致（`production_execution.py:1828–1838`）；共享模式需原真实分支和相应权限，不制造本地 fallback。读取不是执行或审核授权。

已有专项证据（测试源码存在不等于本次全部运行）：

- `test_studio_asset_query.py:225–233`：同 ID 重建不接管旧 Asset。
- `test_studio_asset_query_cursor.py:185–195,244–277`：重建/跨 scope cursor 拒绝、每页及返回前重核 membership/read revocation。
- `test_studio_canvas_audio_return.py:401–414`：原 AudioJob 不在另一个/重建项目执行；该 fixture 同时声明 File/PostgreSQL 参数，不代表本次跑过 PostgreSQL。
- `test_cloud_canvas_queue_recovery.py:286–316`：撤销并以同 token/相同字段重登记的 Host ABA 拒绝旧请求。原 epoch 实现在 `trusted_sessions.py:27–46`、`model_center/discovery_authority.py:69–92`。
- `test_cloud_canvas_create_recovery.py:221–236,283–339`：Canvas 定义 A→B→A 仍以递增版本拒绝旧恢复观察，以及真实 read grant 撤销/返回前撤销。不能外推为任意数据库原地篡改都已覆盖。

本次新增 `tests/test_studio_workspace_identity_history_contract.py`：通过原挂载 HTTP 路由和临时 File owners 验证 overview 实例稳定/同 ID 重建变化、schema 3 AUDIO history/restore 新版本、旧 Asset pin 拒绝恢复、原 Host 撤销、Asset restore 的软删除语义及闭合请求。合成 WAV 只用于原资产存储/完整性读取，没有 FFmpeg、媒体 probe、模型、外部 Provider、浏览器、PostgreSQL 或原生桌面验收；本增量也不实现 Asset 全版本存储或通用删除事件流。

### 本次定向结果（2026-10-25）

原隔离 `.venv`、File backend，测试数据与 XDG/LOCALAPPDATA 均指向独立 `.runtime/identity-history/`。最终 **13 passed, 3 warnings in 6.43s**：新增 5 项，加上上列 Asset 重建、cursor 重建、cursor read revocation 两种时机、Host token ABA、Canvas definition ABA、Canvas read 撤销与返回前撤销共 8 项。测试文件 AST 解析与 whitespace 检查通过；`git diff --check` 通过。没有 commit/push。

本次没有重跑整个库，也没有运行 `test_studio_canvas_audio_return.py` 的 CPU/File/PostgreSQL 测试；该文件在上文只作为已存在的源码覆盖说明。没有将其声明为本次通过证据。
