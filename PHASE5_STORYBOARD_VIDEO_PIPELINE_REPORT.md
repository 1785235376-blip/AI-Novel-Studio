# Phase 5 — Storyboard Production Pipeline / Video Runtime 接续报告

本文记录实际源码、隔离测试和保留失败。Windows、GPU、真实模型及完整产品验收未执行；发布源码不改变原验收门禁。

## 1. 输入与状态

- 仓库：`1785235376-blip/AI-Novel-Studio`。
- 分支：`feature/v2-narrative-platform`。
- 原已推送 Phase 4 基线：`8e4f028680f885d7bc9e040609c5c1b5d2a48e13`。
- 本阶段后端隔离验证输入 tree：`18f7a30f49c2aa21d5246e90297eea9abbda534b`。根代理冻结 19 个后端源码、测试及必要 fixture 文件，并确认前后 SHA manifest 一致。
- 前端完整检查输入 tree：`724858468676a19c17dbb723afec6d4f660ebb1b`；后端独立镜像含基线前端，两棵测试树分别记录，不冒称单一全量测试树。最终提交与远端回执在 PR #47 和私有 publication receipt 核对，不在自身提交内虚构未来 SHA。
- PR #47 保持 Draft；不合并 main、不发布 Release。V1 冻结内容、旧测试、历史失败证据及 PoemSeed Local Interop 1.0 语义保留。青简没有在本阶段推进。
- 状态：本报告所列有界子能力为 **IMPLEMENTED**；完整 Storyboard / Video / Editing 模块仍为 **PARTIAL**，M4→M9 的真实产品门禁保持。

## 2. 实际落实的原 owner 路径

本阶段接通的是原系统上的明确操作：

`已审核 Storyboard → 正式图片引用 → Timeline 创建底稿 → 明确 Video 请求 → 原 VideoJob → 私有 Candidate → 人工 Review → 正式 Asset → 历史 Shot 绑定 → 重新审核 Storyboard → 明确采用到原 Timeline Clip`。

上述每一步均独立。创建底稿或准备 Video command 不启动模型，不自动派发或渲染；用户也可以继续使用独立 Video Studio。没有新增 Project、Asset、模型注册表、任务队列、权限系统或 Timeline owner。

主要原 owner：

- `CreativeService` / 原 CreativeProjectStore：文档、审批、CAS、完整历史及 Shot revision。
- `ProductionExecutionService`：原媒体预览、请求身份、来源/权限/route 检查、候选与审核；原 TIMELINES collection、timeline_edit/history/restore。
- `StudioVideoExecution` / `VideoAssemblyService`：原持久 VideoJob、一次派发、刷新、取消、UNKNOWN、候选及 Review。
- `AssetLibraryService`：原私有/正式资产、精确版本、字节摘要与 immutable origin。
- `CreativeGraphService` / 原媒体 runtime：原 run/node、输入、工作流审核与正式结果。
- 原 Model Center discovery/bridge/registry：显式发现、注册、启用与 route 权限。只读文件观察不授予执行资格。

## 3. Shot 作者提示与完整输入证明

原 `ShotCard` 新增可选 `video_generation_hint`，最多 4,000 字符；未设置或 null 时不进入序列化，旧默认 Shot 和旧请求身份不被隐式扩容。

原 `MediaCommand` 新增可选：

```json
{
  "storyboard_shot": {
    "document_snapshot": {"id": "...", "version": 1, "digest": "..."},
    "shot_id": "...",
    "shot_version": 1,
    "shot_digest": "..."
  }
}
```

只允许原 `m7.video.*` 使用；必须精确对应原 `CREATIVE_DOCUMENT` source。该字段不接受 caller 自报 `approved`，服务端核对原当前 Storyboard、真实审批、Shot ID/revision/digest。完整 pin 进入原 context/request digest、保存 command、VideoJob receipt，以及原 Asset `_studio_result_origin`。生成、恢复、候选读取和审核使用同一 exact origin；没有把历史任务输入改写为之后的当前文档版本。

Video 请求准备只返回原闭合 command，支持 T2V / I2V。提示词来自作者 Shot 字段与可选 hint；完整 prompt 上限 16,000 字符，超限拒绝而不截断。时长读取 Shot 的原整数时长，显式参数冲突被拒绝。I2V 必须使用当时绑定的正式图片 ID/version/digest，不能以另一张图替代原输入。

## 4. 历史视频绑定与版本语义

只有原任务已经 APPROVED、正式 Asset 版本与摘要、原 Review/Job/immutable origin 均一致时，才能绑定到 Shot。Job pin 为精确 `id / version / request_digest / receipt_digest`；新 Job ID 沿原 Name 的非空、有界及控制字符规则。

每个 Shot 的可选 `video_result` 保存正式 Asset、任务原 `source_shot` 和 Job pin。源 Storyboard 快照来自当前或原保留历史，必须在该历史版本真实获批，且 Shot ID/revision/digest 与当前未改 Shot 一致。

- 绑定增加文档版本并撤销当前 Storyboard approval，要求明确再次审批。
- 绑定或再次审批不修改 ShotCard，因此不会仅因文档 metadata 更新增加 ShotVersion。
- 作者修改 Shot 字段会产生原 Shot revision，并移除该 Shot 的旧视频绑定；未修改 Shot 的引用保持原样。
- 已审核 Graph 视频也走同一原 VideoJob/Asset 路径。服务端从原 Job context 取得 Graph binding，核对原 actor/scope/incarnation、saved run、approved execution/review node、正式输出及原 Job 回执；不接受 caller 自报 Graph authority。
- Graph source 因绑定/重新审批而显示旧文档 pin stale 时，已正式审核结果按原历史及 immutable approval 证明使用，不把 masked get_run 结果当作新的生成或审核授权，也不对旧 run 自动 reconcile/replay。

## 5. Legacy Graph 身份保持

已发布 schema 5 的旧 Video node 默认不添加新的 Shot 归属证明。新增可选 `bind_shot: true` 是明确 opt-in；未设置/None 保持旧规范参数、完整 command、prompt、request digest 的原始身份。

原基线 fixture 的实际字节/摘要兼容回归覆盖该行为。新 opt-in 要求真正的 Shot 输入并保存精确 pin。历史已审核 Video 即使能作为普通正式 Asset 使用，也不能被冒认成新 `storyboard_shot` 的结果；缺少该输入证明时明确返回 `CREATIVE_STORYBOARD_VIDEO_SOURCE_PIN_REQUIRED`。

Graph 继续使用原 schema、预算、run/node 状态及 Review owner。没有自动升级旧图或把旧结果补成新的来源证明。

## 6. 原 Timeline 创建幂等、读取与 UNKNOWN

保留旧 `timeline-draft` 请求与行为。新增明确 `timeline-create`，要求固定 request_id；创建 Timeline、原 storyboard_origin 与新 creation receipt 在同一个原事务保存，失败整体回滚。

创建回执绑定 document ID 与完整规范化请求；actor/scope/incarnation 的隔离依赖原 Timeline 行不可由 caller 改写的 `created_by / scope / project_incarnation` 及原 `_owned_timeline` 检查，**不声称请求 digest 单独包含这些 owner 字段**。

- 相同 owner 下的同 ID / 同完整请求返回原创建证明，不再新建、计数或生成。
- 同 ID / 不同完整请求是明确 409 冲突；多条匹配或损坏证明拒绝。
- 只读 `timeline-creations/{request_id}` 供丢失回复后的 UNKNOWN 核对；不根据内容相同推断成功，也不自动 POST 重试。
- `creation_snapshot` 仍为创建 v1，返回的当前 Timeline 可以已经 v2+。校验保留原 history 中的创建来源，不把当前编辑误报成未修改的创建底稿。
- 跨 actor 读取、project 删除/重新创建后不能借用原回执；事务 rollback 有专项证明。

## 7. 正式视频采用与完整操作回执

视频采用明确请求原 document/Shot/Timeline CAS、固定 request_id、clip ID、已绑定的正式 Video Asset 与 Job pin、in/out 和 include_audio。

实际 Video source 探测、必要 audio stream 解码以及原任务 queue 读取均在 Asset phase 外。之后进入原 `scope → Asset → project` writable phase，仅核对精确 metadata/字节/历史 Shot 映射、审批、锁轨及原 owner 来源，再调用原 `timeline_edit` 的 `clip.update`。没有在 Asset 锁内递归探测或重新打开另一个 scope transaction。

范围必须落在**实际可解码媒体时长**内；不因 Shot 请求时长或模型 recipe 的帧补齐而伪造实际输出时长，不静默裁切到上限。

原 Timeline 行保存有界 adoption receipt，绑定完整采用请求及原 `last_edit` 的 input version/digest、request digest、output digest 与实际 clip effect。相同 request_id 但文档/Shot/Job 等完整语义改变时，即使 clip operations 恰好相同，也拒绝 409，不重写旧证明。

该 proof 只在当前原 edit 完全匹配时投影为当前 settlement，供 UNKNOWN 精确读取。后续其他编辑或 restore 保留历史，不能把历史采用回执冒认为当前操作已确认。未证明的 UNKNOWN 继续受限，不自动重放。

## 8. Model Center 观察边界

既有 `VIDEO_GENERATION → VIDEO` task capability 沿用；没有第二套 Model Registry。新 video observations 仅投影已经由原授权扫描得到的结果，读取投影不再探测、扫描、读取凭据、启动 runtime 或下载模型。

精确 loader filename 与当前显式配置 roots 中的有界有效文件观察可以关联；嵌套同 basename 不冒认精确 loader 路径。多个精确候选保持 AMBIGUOUS，取消/扫描不完整/移除授权根/非法路径/坏 header 等保持未知或未观察。

记录的是观察文件路径及实际文件 bytes；`WEIGHT_FILE` 与 `INDEX_METADATA` 分开。Diffusers index 大小不是完整模型大小。`model_total_bytes` 和 `required_vram_bytes` 保持 null，未确认的 runtime 加载路径继续 `runtime_path_verified:false`。文件关联不提升注册、启用、兼容或可执行资格；原启用/route guard 仍负责实际准入。

## 9. API 增量与阈值

新增五个原 Creative router 操作，沿原受信 Host/权限 invoker 挂载到既有 aliases：

| 方法 | 原 documents 下的相对路径 | 实际动作 |
| --- | --- | --- |
| POST | `/{rid}/shots/{shot_id}/video-request` | 只准备原 Video command，不派发 |
| POST | `/{rid}/shots/{shot_id}/video-binding` | 原 APPROVED Job/正式 Asset 的历史 Shot 绑定 |
| POST | `/{rid}/storyboard/timeline-create` | 固定请求身份的原 Timeline 原子创建 |
| GET | `/{rid}/storyboard/timeline-creations/{request_id}` | 原创建证明的只读核对 |
| POST | `/{rid}/shots/{shot_id}/timelines/{tid}/video-adoption` | 实际探测后明确采用原 clip |

原图、Asset、生产任务、取消、刷新、审核 API 继续使用原入口。完整 OpenAPI/API catalog/coverage 计数：原生成器实际生成 2243 API operations / 14129 collected nodes，保留全部 9151 冻结基线节点；收集不代表执行通过，不得推测数量或修改生成器/冻结基线来消除差异。

主要有界范围：

- 原 Shot duration：1–600 秒；本地 Comfy 视频 recipe 接受的范围更窄，不能用 Shot schema 的上限表示模型能力。
- 原三个已验证结构 recipe：LTX-Video 0.9.5、Wan 2.2 TI2V-5B、Hunyuan Video 1.0 T2V。LTX/Wan 为有限 T2V/I2V，Hunyuan 此配方仅 T2V；没有假定任意家族/模型版本兼容。
- 本地固定 recipe：宽高 64–1024 且为 32 的倍数，1–10 秒、1–30 fps、9–241 帧，frame pixels ≤268,435,456；LTX stride 8，其余 stride 4。该结构预算不证明实际 GPU 峰值显存或推理性能。
- 只取固定 SaveWEBM 输出节点的一个 VP9 WebM；candidate ≤25 MiB。来源 first frame 的既有上限为 2048 像素边长。
- Timeline draft 最多 30 个选定 Shot、总长 ≤600,000 ms，宽 16–1920、高 16–1080、fps 1–60；画布还受原 normalizer 的偶数尺寸等规则限制。
- 原 Timeline collection ≤25、history ≤100，scope/Asset/输出容量限制不放宽；局部媒体/队列、history 仍有各自更窄上限。
- 请求 ID 使用原 100 字符有界格式；版本均需严格正整数及原 CAS，未知字段不授予权限。

## 10. 实际验证与保留失败

各组测试有重叠，**不得相加**。下面选定后端检查也不是完整产品测试节点全部执行。

| 证据层 | 实际结果 | 范围与限制 |
| --- | --- | --- |
| 冻结后端 File | 317 passed / 2 failed / 137 profile skips | 根代理独立冻结 19 文件输入；两失败为原 Windows symlink 权限前提 WinError 1314，原断言和失败保留 |
| 冻结后端真实 PostgreSQL | 317 passed / 2 failed / 137 profile skips | 同一冻结输入；同样两 Windows 前提失败，不能称完整 backend 全绿；不是新增 SQL 产品失败 |
| 原 Graph opt-in/兼容专项 | 15 兼容/闭合检查＋3 CPU 管线检查通过 | T2V/I2V：原 Graph Job→私有候选→Review→正式 Asset→历史绑定→再次审批→clip 采用→精确重试→创建 v1/当前 v2 核对→重新打开；另验证实际 0.5 秒媒体拒绝 1000ms 范围 |
| 子代理 Storyboard File 开发专项 r3 | 64 passed / 63 profile skips | 新两模块与原 Phase 4 Storyboard 两模块；不是最终全量树证明 |
| 子代理最终新增边界 r4 | 2 passed / 1 profile skip | 最后明确 legacy SOURCE_PIN_REQUIRED / 默认遗漏边界 |
| 新前端合同两文件 | 49 passed / 0 failed / 0 skipped | 精确 mounted File 捕获＋transport unit；原始 API/CPU 与真实模型证据分开 |
| 子代理 TypeScript | 通过 | 开发预检查，正式冻结后完整前端结果由根代理填写 |
| 正式完整前端/类型/构建/令牌/浏览器检查 | 3250 passed / 8 原有 skipped；类型、构建、52 文件令牌、7 原 shell/geometry 快照通过 | Source unchanged；未更新原快照，shell 检查不代表新工作区专业 UX 或原生 Windows 验收 |

根代理确认测试拥有的 fresh 专用 loopback PostgreSQL cluster 正常停止，验证数据库与失败/源码证明保留；没有访问用户真实数据库/作品。

保留的阶段失败与修复：

1. 后端子代理 r1 的 2 个新增 reopen 测试直接读 Asset owner、未进入原 project_scope；修正新增测试调用方式，原失败仍保存。业务管线在当轮已执行，没有更改原测试或降低断言。
2. 根代理 Graph r1 的 3 个 setup errors 来自遗漏新 basetemp 前提；正确隔离环境后执行，不将原 setup failure 删除或改称产品 PASS。
3. 新前端合同测试首次 TypeScript 的 5 个 typing errors 仅在新增测试；修正可选 JSON 字段的类型访问和 inert transport-unit context。
4. 新控制字符回归确实发现 JobPin decoder 接受非法 ID；UI owner 修复新 resource parser，保留 48 pass / 1 fail 的原始 r3 JSON，最终 49 pass。没有删除断言或修改旧 fixture 来制造绿色。
5. 原两个 Windows symlink 安全权限前提失败仍在最终 File/PG 结果中。独立 Linux 原四项断言单独执行：4 passed；原断言/源码不改，移除自有 native 临时目录，不能回填成 Windows 成功。

## 11. Hosted CI 与未执行能力

根代理对基线 `8e4f028...` 的新 Hosted CI jobs 已核对：29 个 job 均 `runner_id=0`、没有执行步骤。账户/平台运行阻塞的原始诊断私有保留；本报告不公开相关账户原文。该终态不能归因为产品测试断言失败，也不能报 CI 通过。本阶段最终 SHA 的 CI 状态：提交后在 PR #47 与私有 publication receipt 单独核对；本报告不提前宣称 hosted CI PASS；不无限重跑，不弱化门禁。

明确未完成/未验收：

- **NOT_RUN / LOCAL_REQUIRED**：Windows 最终 Application 安装、launcher→PG→backend→DesktopHost、V2 vault/缓存/数据隔离、会话失效/重启/中文路径/V1 不受影响的最终验收。
- **NOT_RUN / LOCAL_REQUIRED**：实际 LTX/Wan/Hunyuan 推理、RTX 5080 显存/性能/质量、重型渲染、真实视频参考控制效果和模型依赖组合。
- Comfy 本地 recipe 不执行 V2V 或 reference-video 语义控制；原明确配置 HTTP Provider 的既有 V2V seam 与 role metadata 不证明动作/风格/摄影机控制质量。
- 本地取消是原 `LOCAL_RESULT_DISCARD`，不声称远端计算已停止。UNKNOWN 保持一次派发与明确恢复；没有自动重发或悄悄创建后继任务。
- storyboard hint/Camera/情绪是作者输入与建议，不自动覆盖用户，不保证模型遵从或角色/服装连续性。
- 已审核正式结果的历史采用不授予 stale 原文档新的生成/审核/云端上传权限；原来源 privacy、Host、feature、owner/incarnation、route 与 egress 检查保持。
- Model Center 的路径/文件大小观察不证明模型已加载，不给出猜测显存，也不自动下载安装。
- 专业 Storyboard/Video UX 仍是有界基础；本阶段不能表示完整 NLE、全部 Audio 后期能力、外部剪辑软件互通或完整影视产品已经完成。

## 12. Opus 重构边界与最终填写项

Opus 可以替换 Canvas、Shot 卡片、Inspector、Preview、列表和工作区布局。原 headless controller、Host transport、parent mutation mutex、client/epoch/late response fence、dirty/UNKNOWN、保存/来源 CAS、固定请求身份、精确 recovery proof、明确 Review 与 Asset owner 必须保留。UI 不得根据表面内容一致自动解除 UNKNOWN 或替用户审批/采用。

原始日志、数据库、环境、私人路径与账户诊断不公开；[源码/脱敏摘要](docs/v2/phase5-storyboard-video-pipeline-20261014.json)记录 52 个源码/测试/fixture blob 哈希和实际回执摘要。独立 PostgreSQL 已正常停止并保留 evidence database；File/PG 和开发专项有重叠，不相加。原生成器、冻结 manifest、旧断言和 skip 门禁不变。

Phase 6 已授权自动接续独立 FLAC 交付与原多轨后期操作；这不是 M8/M9 产品验收通过。全部测试使用隔离数据、合成 transport 和必要真实 CPU 媒体，不启动真实模型、付费 API 或用户作品。

完整 Image / Director / Storyboard / Video / Audio / Editing、历史 F00 INTEGRATED＋39 PARTIAL、独立复审 BLOCKED 及原各项 NOT_RUN/LOCAL_REQUIRED 不被本批有界源码和测试重分类。
