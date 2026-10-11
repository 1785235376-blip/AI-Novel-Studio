# Studio V2 独立媒体执行与多轨审阅渲染

本批在 `5ed1cbee41d549351637d04a894477750c3e08b2` 的后续源码中接入实际命令、原任务持久存储、Provider 分派、真实媒体字节校验、私有候选与人工审核。这里记录源码行为，不宣称这些路径已经执行通过。全部测试、collect-only、typecheck、build、CI、Windows、GPU、Runtime 和真实模型验收为 **NOT_RUN — USER_DEFERRED**；M4 仍为 **PARTIAL**，M5–M9 验收仍为 **LOCAL_REQUIRED**，顺序保持 M4 → M9。QingJian 暂停推进。

## 原 owner 与操作范围

`app/creative/production_execution.py:ProductionExecutionService` 负责衔接原项目、来源、权限与媒体 owner，不创建第二套队列或调度器。命令模型在 `production_execution_models.py`，路由在 `production_execution_api.py`。

| 独立操作 ID | 实际持久 owner 与适配 | 输入与当前边界 |
| --- | --- | --- |
| `m5.image.t2i` | 原 `ImageJobService.for_actor`；`studio_image_execution.py` | 明确 Provider／模型、Prompt 与该 Provider 支持的参数；原 `AssetGenerationRequest.dispatch_guard` 负责最后一刻分派校验。 |
| `m5.image.i2i` | 同一原 ImageJobService | 原 Asset 图片版本／摘要与有界已核验字节，通常 1–5 张，但实际 Provider 限制优先。ComfyUI 仅 1 张，I2I 不接受 width／height；A1111 多参考的上游生成语义尚未验收。 |
| `m7.video.t2v`、`m7.video.i2v`、`m7.video.v2v` | 原 `VideoAssemblyService` 的独立 actor／scope／incarnation 任务存储；`studio_video_execution.py` | 原 VideoProvider 的真实能力与配置门禁；I2V／V2V 各绑定一个对应 Asset 快照。已有远端任务可显式 refresh；不自动重新提交。 |
| `m8.audio.speech`、`m8.audio.music`、`m8.audio.effects` | 原 branch／actor `AudiobookStore` 与 `AudiobookService`；`studio_audio_execution.py` | 原 AudioProvider 的 TTS／MUSIC／SFX 能力与最后一刻分派 guard；要求同步得到可核验完成音频。异步未完成回执保存原任务 ID／状态后保持 UNKNOWN，当前没有远端音频查询协议。 |
| `m8.audio.trim` | 同一原音频 owner；原 FFmpeg | 仅一个已保存音频 Asset，起止毫秒位于实际来源时长内，片段最多 120 秒；输出 PCM S16LE WAV／48kHz／立体声。无 Provider、云端授权或 Prompt。 |
| `m9.timeline.multitrack` | 原 `VideoAssemblyService.create_studio`；`studio_timeline_render.py` | 保存版本化时间线，确认版本／摘要后显式本地渲染；有界视频叠放、音频混音与手工字幕，输出仍先私有再人工审核。 |

这 9 项 MediaCommand 现另由显式 schema 3 的 [Graph 媒体执行与原子输入](graph-media-execution.md) 接入原 WorkflowRun。原文字图的队列、ModelBroker、Router、GraphTextAssets、审核与结算仍由原 owner 负责；schema 1／2 的资产引用保持原阻塞。后续源码已接入 schema 3 文字档案，以及独立多轨的原子剪辑、版本恢复和明确编码导出，详见 [文字档案与多轨导出](text-archive-timeline-export.md)。自动 ASR／音画对齐和跨剪辑软件往返尚无实现或验收。

## 可信会话、权限与隐私

所有实际命令、读取、候选和时间线入口都经过原 workspace `invoke`、项目激活／scope／incarnation 检查，以及原 `require_host_session` 和 `model_host_authority` 的可信 Host 绑定；仅 `NEUTRAL_STUDIO` 可进入。不能用开发 token、模拟身份、关闭认证或内存凭据替代 DesktopHost。

读取／预览要求 `domain.read`，入队／执行／本地丢弃／reconcile／时间线保存渲染要求 `domain.write`，采用候选要求 `domain.review`。Provider 操作还复核原 AI execution 开关。配置清单仅返回已配置参考、支持参数与 `CONFIGURED_NOT_VERIFIED`，不健康探测、不启动 Runtime、不读取凭据；可见配置不等于模型已运行。

云端路径须同时满足原全局 `settings.enable_cloud`、本次 `allow_cloud`、原项目来源政策和文档的云端允许政策；Prompt／参考素材均属于本次发送范围。Provider／模型／endpoint／route digest 和执行 recipe 在预览、创建与实际发送时重新匹配。返回结果的获取与发布同样保留当时的原策略和来源检查。无付费 fallback、自动换模型或自动换工作流。授权说明只是作者声明，不冒充权利验证回执。

`_cloud_sources` 还沿原不可变 Studio Asset 的来源快照和有证明的 legacy parent snapshot 继承隐私，并从原 owner 重新核对版本／摘要。直接与间接 CREATIVE_DOCUMENT 都须原 `CLOUD_ALLOWED`；最多 64 个身份节点、深度 16、Asset 总量 200MiB。缺失证明、旧 chapter 来源尚无原云端授权证明、新加父来源、循环、过期快照或超限均 fail closed。作者 license／operation 声明不能给来源新的 cloud grant，不能把旧章节来源改写成 CreativeDocument 授权。这段检查在分派前、原 Asset／job lease 之外执行，不修改历史 provenance。

原 packaged V2 profile 的独立数据、缓存与固定 `AI-Novel-Studio-V2/provider/` Windows 凭据命名空间保持既定边界；本批没有 V1 凭据读取、枚举、迁移或覆盖路线。V1 默认路径、冻结资产与 PoemSeed Local Interop 1.0 语义保持原样。

## 命令与原回执

API 基础路径为 `/api/projects/{nid}/studio/production`，原父路由另保留 `/api/v1` alias；alias 不降低权限或 Host 要求。

| 方法／相对路径 | 实际动作 |
| --- | --- |
| `GET /providers` | 只读已配置 Provider／模型与参数参考。 |
| `POST /preview` | 校验 `MediaCommand` 与来源，形成绑定输入、路线和 recipe 的预览；不创建任务、不调用 Provider。 |
| `POST /jobs` | `MediaCreate(command, reviewed_preview_digest)`；重算预览并核对用户确认摘要，仅保存 QUEUED 原任务。 |
| `GET /jobs`、`GET /jobs/{owner}/{jid}` | 读取当前 actor／scope／incarnation 的原记录；不重放。 |
| `POST /jobs/{owner}/{jid}/execute` | 9 项媒体操作显式执行；独立 `owner=timeline` 使用原 render/export 入口。Graph 绑定时间线只能从原 Graph `/media/execute` 执行已确认的同一个 QUEUED job，不能借独立入口再次渲染。 |
| `POST /jobs/video/{jid}/refresh` | 核对已有原远端视频任务；仅原 Provider 支持的查询，不重新生成。 |
| `POST /jobs/{owner}/{jid}/reconcile` | 原执行 lease 已结束后核对中断状态并保留 UNKNOWN，不调用 Provider 或重排任务。 |
| `POST /jobs/{owner}/{jid}/cancel` | owner 允许状态下丢弃本地结果采用权，保留记录与候选；时间线可沿原 lease/queue CAS 取消，执行 guard 终止本地渲染进程；不证明远端计算已停止。 |
| `GET /jobs/{owner}/{jid}/candidate` | 原授权下读取实际候选字节，响应 `no-store`、Asset 版本与 SHA256；不返回远端媒体 URL。 |
| `POST /jobs/{owner}/{jid}/review` | 绑定原 job version、request digest 与已查看 output digest，显式调用原 `AssetLibrary.promote_owned`。 |
| `GET /timelines`、`GET /timelines/{tid}` | 当前 actor 的原版本化时间线读取。 |
| `POST /timelines`、`PUT /timelines/{tid}` | `TimelineSave`；新建 expected_version=0，更新核对原版本。 |
| `POST /timelines/{tid}/render` | `TimelineRender(expected_version, reviewed_timeline_digest, request_id)`；实际同步有界渲染并保存原任务／私有候选，不是仅入队。 |

媒体动作的 `MediaJobAction` 同时携带 `expected_version` 和 `expected_request_digest`；`MediaReview` 另携带 `reviewed_output_digest`。请求 ID、原来源快照、Provider 绑定及请求摘要共同约束幂等。来源为原 ASSET 或 CREATIVE_DOCUMENT 的确切 ID／版本／摘要；基础 UI 当前只选 Asset。服务端必须从原 owner 取得来源并校验字节，客户端快照不是授权证明。

公开任务 `studio-production-job/1` 包含原 job ID／owner／version／status、request ID／digest、receipt digest、候选 Asset ID／版本／digest／kind、来源和可选时间线快照、已确认 `command`、精简 `provider` 与 `execution_recipe`。Provider 投影仅 provider_id／model_id／local／route_digest；不公开 endpoint、secret、actor、incarnation 或执行 token。审核后的 `approved_asset_version` 与原候选版本分别保留。`product_acceptance=LOCAL_REQUIRED`、`automatic_replay=false` 不因成功回执而升级。

`studio-execution-recipe/1` 是已绑定的接口／参数／模板记录，包含 recipe digest 与 `automatic_fallback=false`。支持的随机 seed 在预览中由原 request ID 固定，TTS 默认语速在此明确；ComfyUI 使用原内置模板，I2I 的 `VERIFIED_SOURCE_UPLOAD_RECEIPT` 只是预览中的符号，实际 LoadImage 文件名来自原已核验 upload 回执。它不伪造远端工作流结果。用户可下载刚读取的公共任务 JSON；该文件不是新运行、模型质量或产品验收证据。

## 来源 CAS、私有候选与不确定状态

原来源版本／摘要在分派、结果发布和人工审核前重新核对；时间线还绑定原文档版本／摘要。结果发布持有原 scope source lease，再进入原 Asset／项目临界区，并由短暂原 job guard 核对当前尝试。候选通过原 Asset quota、媒体类型、实际字节大小／SHA256、owner、scope／incarnation、required feature 与不可变 `_studio_result_origin` 检查；通用参数或客户端 provenance 不能替代此 server-owned 记录。

创建仅 QUEUED，媒体 Provider 真正发送前记录原发送 reservation／attempt；成功的实际字节经原媒体校验器进入私有候选，通常到 AWAITING_REVIEW，再由人工明确采用。SUCCEEDED／APPROVED 不表示 Router 已结算、GPU 已运行或质量通过。

发送或发布以后无法确认结果，保留 UNKNOWN／原回执，不自动重发。RUNNING／SEND_RESERVED 的显式 reconcile 必须排除仍持有 lease 的原 executor；它只处理本地中断记录。远端视频只有保存了原 task ID 且 Provider 支持查询时才可 refresh。音频异步没有 poll owner，因此保持 UNKNOWN；不能把重新 execute、换 request ID 或无限加超时当恢复方式。

UI 在网络、408／409／425／429、5xx 或非法成功回执后保留原 reservation／发送键并阻止重复动作，先读取原 job 核对；读取相同值不证明旧请求完成。取消是 `LOCAL_RESULT_DISCARD`，保留原候选并提示远端可能继续，不声称 remote abort。

## 原审阅规格与增强多轨实现

以下为旧无 schema_version 时间线的保留规格。显式时间线 schema 2 的图片／变速／透明度／淡入淡出／原视频声音、原子编辑、原历史恢复，以及 export-preview/export 的 H.264/AAC MP4、VP9/Opus WebM 真实执行另见 [增强剪辑与编码导出](text-archive-timeline-export.md)。旧 normalize 输出／定义摘要与原 render 请求保持，新增导出不自动取代原审阅动作。

`normalize_studio_timeline` 接受严格闭合的毫秒 DTO；最多 8 轨，其中 VIDEO／AUDIO 各最多 4 轨、总共 30 段、时长最多 600000ms，至少一轨 VIDEO。轨道 ID／order 和 clip ID 唯一；同一 Asset 的多次使用必须快照一致。VIDEO 同轨不得重叠，不同 VIDEO 轨按 order 叠放；AUDIO 可重叠并按 gain_db／muted 混音。源 in_ms／out_ms 再对实际媒体时长核对。

画布上限 1920×1080、1–60FPS、偶数尺寸；默认 1280×720／24FPS，支持有界 x／y／width／height 视频摆放。字幕是手工字面文字与时间范围，最多 500 条、每条 1000 字符、合计 32000 字符；不接受执行表达式或外部路径，不是自动转录或 Caption document 适配。

原 FFmpeg 只处理已验证字节写入的临时本地文件，外部 URL／脚本不是输入；总来源上限 200MiB、渲染 timeout 120 秒，输出受原 Asset byte limit。实际 profile 为 MPEG-4 视频、AAC／48kHz／立体声 MP4，按输出上限调整码率。视频和音频都经原媒体校验器并核对时长，渲染后重新读原来源快照。此实现是有界审阅渲染，未宣称高质量成片、完整 NLE、GPU 编码、字幕字体可用或真实 Windows FFmpeg 执行已通过。

## UI 分工与后续证据

`StudioMediaExecutionPanel`／`useStudioMediaExecution` 提供闭合参数输入、配置选择、显式预览／确认／入队／执行、原任务读取、已核验候选 Blob、本地图片／音视频控件、输出审核与 JSON 回执下载。`StudioTimelineEditor`／`useStudioTimelineEditor`／`studioTimelineTypes` 提供轨道／片段／手工字幕表单、base／draft／server candidate、CAS 保存、明确 render 与原任务恢复；媒体面板可采用父级已返回且绑定当前 client 的 timeline job 做预览／审核，不自动 GET 或生成。候选 URL 在身份、任务／版本、权限、来源变化和卸载时立即清空／revoke；Abort 仅阻止晚到响应采用，不等于取消真实 owner。

`StudioAssetDeclarationForm` 接入生成结果的原 source_task_id：只编辑作者 license／operation，origin、父资产与文档快照只读，保留原 parent_asset_ids 并提交 chapter_ids=[]，不把 CREATIVE_DOCUMENT 映射成章节。声明不改变真实生成来源或审核；手工输入继续使用原共享 AssetLineageForm。

Opus 可以替换 Panel／Editor JSX 与 token 样式，继续消费命名 controller actions 与严格 client；不能绕过确认、Host、source/job CAS、UNKNOWN／幂等、dirty 导航保护或 Blob 清理。详见 [UI/UX 交接](opus-ui-ux-handoff.md)。只读 [operation catalog](production-operation-contracts.md) 仍为 advisory，入口描述从不授予执行权限。

恢复验证后，先检查相关权限／参数／来源／CAS／中断与 UI 生命周期，再用原工具同步当前 API catalog 与独立 V2 coverage，随后做里程碑 CI。独立 metadata 修复提交 `776286f` 的 8 项文件对应旧 `5ed1cbee` 快照，不能覆盖这批新 API／源码。原 a40df PostgreSQL 失败、取消／不完整 CI 与新 5ed source-bound 失败记录保持原样；F00 INTEGRATED + 39 PARTIAL、独立复审 BLOCKED、冻结 V1 manifest 与历史报告不改。实际 Windows 包构建及 launcher → PostgreSQL → backend → DesktopHost → M4 真实 Text 闭环仍需最终发布源码上的独立证据，之后依序验收 M5–M9。

Phase12 将显式 schema 3 `timeline_export` 接到原 TIMELINES 和 VideoAssemblyService：闭合剪辑与 source_1…8 绑定先在 detached DTO 预览；确认后与 Graph claim 同事务保存原时间线历史，然后仅入队原 owner。独立保存／编辑／同步 render/export 的原请求与摘要保持；原队列明确 execute 使用其不可变 context／profile。Graph runtime 读执行快照与原 edit receipt，来源、取消、图或会话变化均拒绝旧结果。候选／人工入库／中断恢复沿原 owner，ADMISSION_UNKNOWN 不重复剪辑，UNKNOWN 不重新渲染。完整参数、锁序、竞态处理和未执行边界见 [Graph 时间线实际执行链](graph-media-execution.md#graph-时间线实际执行链phase12)。
