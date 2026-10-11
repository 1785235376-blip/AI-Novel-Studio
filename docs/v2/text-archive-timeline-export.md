# Schema 3 文字档案与多轨剪辑导出

本批输入是 `d9be1c3d826612927d98d3b14d4a973b6fa875ab`。这里只记录源码实现，测试、导入检查、类型检查、构建、Runtime／原生 FFmpeg／模型／GPU 调用与真实全流程验收均 **NOT_RUN — USER_DEFERRED**。青简保持暂停；PR #47 保持 Draft。M4 PARTIAL、M5–M9 LOCAL_REQUIRED 和原 M4 → M9 验收顺序不变。

## 原 owner 上的文字档案

显式 Graph schema 3 的 `ModelDispatch.archive_result=true` 使用原 GraphTextAssets、原 ModelBroker/Router、原 WorkflowRun 和原 AssetLibrary 文字归档与审核。输入、模型路线、原 Broker 作业、run/node、来源 incarnation、字节摘要与原执行回执保留既定绑定，HTTP 客户端不能构造这些服务端证明。

原文字候选仍是 actor-private 的 text result，不被当作图片／音视频 ASSET_REF。原 human_review 批准／驳回投影到同一文字档案 owner；读取、恢复、取消与媒体 Graph 投影共同保留 `asset_output` 和原 stale／UNKNOWN 语义，不自动发送或重新创建资产。已完成文字输出被媒体节点采用之前，原档案与文本路线证明也要核对，不能只装饰 GET 回执。

Schema 3 的实际文字到媒体连接为 `text_generate.draft → human_review.draft → human_review.reviewed_draft → media_generate.draft`。只有原 human_review 完成准确输出摘要的批准后，才在同一 WorkflowRun 写入 reviewed_draft、原审核出处与 cache receipt。媒体运行复核同一个模型 draft、已成功的原审核节点及 APPROVED 私有文字档案；draft 与 TEXT 输入互斥。schema 1／2 的 human_review 输出仍为空。当前 text_reference 是原 TEXT 透传，没有 CreativeDocument 来源证明，不能凭节点名称补造文档授权；实际媒体 Asset 来源仍继承原不可变出处与云端政策。

Schema 3 使用原 GraphAssetInputs 的 raw scope → Asset → Project phase 覆盖档案 ensure、原工作流完成／审核及原 scope commit，不嵌套第二个 raw transaction。路线准备在 lease 外，lease 内仅核对原已保存来源、回执、资产元数据和真实文字字节。旧 schema 2 的原归档行为保持。

## 原子时间线编辑

原时间线集合 `creative_production_timelines_v2`、原历史、原 actor/scope/incarnation 和原 VideoAssemblyService 任务继续负责持久化。没有新增队列、调度器、凭据库或客户端文件路径执行能力。

`TimelineEdit` 接收准确 `expected_version`、`reviewed_timeline_digest`、稳定 `request_id` 与 1–40 项闭合操作，操作 JSON 最多 128000 字节。一个批次在脱离原状态的副本上完成，再校验最终 DTO 与原资产字节；原 scope → asset → project 临界区内一次提交。中途失败不提交部分编辑，最后一个相同请求的失联回执可返回原已保存版本。

| 操作 | 真实变更 |
| --- | --- |
| `canvas.update` | 时长／画幅／FPS；只有明确 `schema_version=2` 才升级增强时间线。 |
| `track.insert/remove/update/reorder` | 新空轨（需同批插入片段再保存）、明确删除片段确认、静音／增益／角色、完整唯一轨道排序。 |
| `clip.insert/update/move/duplicate` | 确切原素材快照、裁剪与位置；移动／复制只允许同类型轨，保留作者指定稳定 ID。 |
| `clip.split/trim/slip/remove` | 分切、源入出点调整、滑移与可选同轨波纹裁剪／删除。变速分切要求精确整数毫秒，不悄悄舍入；图片两段各自从零计显示时长。 |
| `caption.insert/update/remove` | 有界手工字幕；索引绑定已确认时间线版本，不接受脚本或外部字幕路径。 |

时间线仍最多 8 轨、VIDEO/AUDIO 各 4 轨、共 30 段、10 分钟、1920×1080／60FPS。旧无 schema_version 的规范化输出、时间线摘要和原 render 请求定义保持。显式时间线 schema 2 增加图片叠层、画面透明度、0.25–4 倍有理变速、片段静音／增益／淡入淡出、明确采用原视频声音、PRIMARY/OVERLAY 和 DIALOGUE/MUSIC/EFFECTS 角色。VIDEO 同轨不能重叠，跨 VIDEO 轨按 order 叠放；多个 AUDIO 片段按原 gain/mute 混音。角色标签不伪造来源或模型结果。

历史 GET 只读取原保存版本；restore 将确切版本／摘要在原来源仍有效时恢复为一个新版本，不回退原 version、不改写或删除原历史。

## 明确编码和实际导出

导出为 `export-preview → 用户确认 preview_digest → export`。预览只核对保存图、素材、输出预算和 recipe；不会探测 Runtime、调用 FFmpeg 或生成结果。实际 export 复核相同时间线、profile、来源与预览摘要后调用原 VideoAssemblyService 的同一个持久任务 owner。

闭合 profile 为 `{preset, video_bitrate_kbps?, audio_bitrate_kbps?, crf?}`，画幅/FPS 来自已保存时间线：

| preset | 实际编码 |
| --- | --- |
| `REVIEW_MP4` | 保留原预算驱动的 MPEG-4/AAC MP4 审阅规格，只允许 preset 字段。 |
| `DELIVERY_H264_MP4` | 原生 libx264/AAC MP4，默认 4000/192kbps、CRF20，固定视频码率上限和 faststart。 |
| `DELIVERY_VP9_WEBM` | 原生 libvpx-vp9/Opus WebM，默认 2000/128kbps、CRF30。 |

交付 profile 保留作者选择的码率上限和 CRF。预计输出加封装余量超出原 **25MiB 单资产上限**时预先拒绝，不悄悄降低码率；最终实际字节仍要满足原 Asset quota 和容量许可。原 120 秒执行时限保留，不能把超时当成功。

FFmpeg 只读取服务端已核验字节写入的临时本地文件，compiler 生成闭合滤镜与编码参数，不接受任意 filter、脚本、可执行文件、外部 URL 或输出目录。执行时核对实际 encoder 是否存在；缺失就失败，没有编码 fallback。原媒体验证与真实 ffprobe 核对编码、容器、画幅、FPS、像素格式、48kHz 立体声音轨与时长，不能用计划参数冒充测量值。

结果先保存原私有候选；候选读取在原 scope／asset phase 复核当前时间线、来源字节、原作业版本和确切候选版本／SHA256，时间线或来源已变化则拒绝旧结果。原 `review` 明确采用后才成为正式资产，已批准结果核对原批准版本与出处。下载沿原候选或已审核 Studio asset download，不开放任意服务器路径写入。完成编码、保存候选、人工审核与发布验收分别记录。

原任务取消在原 source/asset lease 下完成 durable queue CAS，周期执行 guard 可终止本地 native process；不声称远端模型取消。lease 中断后 reconcile 可精确找回已发布但回执未记录的原私有候选，核对原 idempotency key、source、origin、输出摘要和真实字节后恢复原任务，不能重新渲染、promote 或建立替代任务。无可靠候选时仍为 UNKNOWN。

时间线审核先在同一 source／asset phase 核对保存版本、素材与私有候选，再预约 REVIEWING、调用原 promote 和写回原作业；已过时输入不会先留下不可取消的审核预约。明确失败且资产仍是确切未 promote 私有版本时恢复原待审状态；已持久 promote 但作业回执中断时只允许原出处／批准版本的准确恢复，不把不确定审核变成可丢弃结果。

## 路由与权限

基础为 `/api/projects/{nid}/studio/production`，原 `/api/v1` alias 同等门禁。原可信 Host、会话、project activation、scope/incarnation 和 domain 权限不改变。

| 方法／相对路径 | 权限及行为 |
| --- | --- |
| `POST /timelines/{tid}/edit` | domain.write；TimelineEdit，原子有界编辑。 |
| `GET /timelines/{tid}/history` | domain.read；原 actor 历史。 |
| `POST /timelines/{tid}/restore` | domain.write；TimelineRestore，当前与目标版本／摘要均明确。 |
| `POST /timelines/{tid}/export-preview` | domain.read；TimelineExportPreview。 |
| `POST /timelines/{tid}/export` | domain.write；TimelineExport 另带 request_id／reviewed_export_digest；实际同步渲染。 |
| `POST /jobs/timeline/{jid}/cancel` | domain.write；原 job version/request digest。 |
| 原 `/render`, `/candidate`, `/review`, `/reconcile` | 继续原 owner／CAS／人工审核；不自动重发。 |

## Opus 可重构边界及验收

`studioTimelineTypes`／`studioTimelineExportTypes` 与原严格 Production client 负责 DTO／回执核验；`useStudioTimelineEditor` 负责本地编辑、撤销／重做、明确保存、导出预览／同意、一次发送与 UNKNOWN 恢复。JSX 继续消费控制器命名动作和 DS primitives，Opus 可重排视图，不绕过权限、来源、version/digest、request ID、真实候选 Blob、人工审核和导航保护。

原冻结 V1、PoemSeed Local Interop 1.0、历史报告、PG failed-call／终态超时、取消或不完整 CI、F00 INTEGRATED＋39 PARTIAL、独立复审 BLOCKED 保持。当前 API/V2 coverage metadata 待恢复验证后由原工具同步，冻结 V1 manifest 不改。

本批实现有界多轨剪辑和上述真实编码导出路径，尚未取得 Windows、原 vault/WebView2、GPU／模型、真实 FFmpeg、中文字体／路径和最终成片质量的运行证据。自动 ASR／音画对齐、Graph timeline node 与跨软件往返不属于本批实现，不能把它们记为验收完成。
