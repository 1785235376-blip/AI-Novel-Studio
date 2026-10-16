# AI-Novel-Studio V2 Codex 接管工程审计

审计日期：2026-10-13（Asia/Shanghai）。Production Expansion 开发审计，不是发布、完整 CI 或目标设备验收。本文提交前没有修改产品代码或执行模型。

## 1. 实际基线与证据等级

- 仓库 `1785235376-blip/AI-Novel-Studio`；唯一开发分支 `feature/v2-narrative-platform`。
- 本轮开始本地、远端及 PR HEAD 均为 `72765972b3bf81ba6959754c33b827294a63fb3f`，tree `142dedccf3c26c97a17d85bd61a9995ac33da809`。
- [PR #47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) 为 OPEN / Draft、base=main；正文摘要仍指较早 `c01bdc5`，不能代替实际 HEAD。
- 使用新的独立克隆；旧 dirty 工作区、固定 `5af9bfc` Windows 工作区与上一轮原始日志保留。不 reset、clean、stash、强制推送或改写历史。
- 核对 architecture、feature matrix 历史及追加条目、milestone history、`docs/v2/` 契约／交接文档，以具体代码、测试断言与来源明确的报告交叉判断，不按文件名猜测完成。GraphFlow 新根 context 成功；早期 context/plan transport 失败单独记录。
- 最新已提交阶段所选23模块：File **750 passed /14 skipped**，真实 PostgreSQL **762 passed /14 skipped**，重叠不能相加。API **2219 operations**；V2 **13364 collected nodes**，保留冻结9151。Windows原清单检查 **45 passed /2 symlink权限前提失败**；两项原断言在Ubuntu单独通过。[来源](docs/delivery/v2-development/nonwav-windows-integration-20261013.md)。
- `7276597` 自动 CI 共29jobs，runner_id=0、没有执行步骤，原注释确认账户账单锁；执行阻塞不是产品测试失败或CI通过。本审计未重跑CI。
- 本轮检查现有测试源码，不重新计为已执行。Windows最终安装、GPU压力、真实模型／质量／完整产品验收 **NOT_RUN / LOCAL_REQUIRED**。
- 丢失的 `1134f8de50ad68b9e1aad189cb422e256af64c6f` 未恢复，后续属重新实现；上轮集成的是核验后的 `f650255` 源码补丁，不宣称恢复Git对象。

## 2. 当前代码结构、owner 与 API 边界

未发现正式 CODEOWNERS/OWNERS；以下 owner 指实际写入 authority，不猜测个人维护者。UI系统owner按原设计系统规则。

| 领域 | 当前 authority / 入口 | 保留边界 |
| --- | --- | --- |
| Project/scope/权限 | 原 Novel File/PostgreSQL repositories、RepositoryBundle、CollaborationScopeService、AuthorizationService、trusted_sessions | 中性入口复用项目身份；不新增ProjectDB或权限系统。 |
| Creative 文档 | `app/creative/service.py`、`models.py`、`project_store.py` | SCRIPT/SCREENPLAY/DIRECTOR/STORYBOARD/PRODUCTION 沿原版本、历史、incarnation、CAS与来源审核。 |
| Asset/lineage | AssetLibraryService、原relationships和ProductionLineage投影 | 二进制、ID/digest/metadata version/quota/私有候选/promotion只由原owner写。 |
| Graph | `graph.py`、`graph_models.py`、`graph_execution.py`、`graph_media_execution.py` | 原WorkflowRun持有运行；旧schema1/2与显式schema3区分，不新增调度器。 |
| Text/route | JobManager、AuthorRequestPreparer、ModelBroker、Provider/runtime registries | preview、明确dispatch、预算／不明回执、review-before-apply不变。 |
| Image | ImageJobService、`studio_image_execution.py`、AssetProviderRegistry、ProductionExecutionService | 原modality owner，不把配置存在当Router已结算或真实推理。 |
| Video/Editing | VideoAssemblyService、`studio_video_execution.py`、`studio_timeline_*` | 同一时间线／任务／Asset／历史；不另造导出或NLE owner。 |
| Audio/subtitle | AudiobookService、`studio_audio_execution.py`、SubtitleTimelineService、固定Whisper lifecycle、MFA adapter | 默认未配置／未加载拒绝；无模拟身份、自动启动或付费fallback。 |
| 模型发现/准入 | LocalDiscoveryService、ModelCenterService、LocalDiscoveryBridge、RuntimeRegistry | 原registry，发现→验证→注册disabled→明确enable；元数据不是推理证明。 |
| UI | AppShell/ModuleWorkspace、`frontend/src/creative/` headless controllers | 视图不能代替Host/CAS/来源/确认/UNKNOWN/epoch/Blob清理。 |
| 青简预留 | `app/local_interop` / PoemSeed Local Interop1.0 | 原协议保留，代码不合并，本轮不推进青简。 |

独立 API 为 `/api/projects/{nid}/studio`，production与Graph沿 `workspace_api.py`、`production_execution_api.py`、`graph_api.py`，保留原`/api/v1` aliases。read/preview=`domain.read`，write/execute=`domain.write`，采用=`domain.review`；Host、flags、activation、scope/incarnation、来源/job CAS由服务端检查。providers是被动配置投影，不能健康探测／读取凭据／启动服务。operation catalog仅advisory，无execution grant；不暴露shell/私有路径/任意workflow入口。

## 3. 已实现工程与尚未完成模块

IMPLEMENTED只指相应有界执行代码存在，模块与验收另列。旧矩阵MISSING/NOT_RUN有历史来源，保留并追加当前观察。

| 模块 | 有实际代码的能力 | 当前缺口与状态 |
| --- | --- | --- |
| Creative/Asset | 无章节独立入口、原文档版本、素材导入/原字节导出、来源快照、人工审核、资产关系 | **PARTIAL**；完整StorageManager、迁移/代理缓存及成品验收未完成。 |
| Text/Screenplay | Text execution、saved Script、adaptation proposal/archive、Fountain/DOCX/Markdown/TXT、screenplay EPUB | M4 **PARTIAL**；真实质量/完整Host路径未闭合，原PG archive竞态失败保留。 |
| Graph | 保存/CAS/typed ports、位置/连线/pan/zoom/selection；schema3 media_generate/media_review/ASSET_REF、文字档案与timeline_export接实际owner | **PARTIAL**；无完整Prompt/Model/LoRA/Pose/Depth/Style/Storyboard节点群。旧ImageInfiniteCanvas是reference board，不是执行图。 |
| Image | configured T2I/I2I、原adapter调用、手工二值mask、CPU cutout、私有Asset/review；Comfy固定SD T2I/I2I模板 | **PARTIAL**；enabled discovery adapter到production有断点。AI inpaint/outpaint/repair/upscale、typedstyle、分层编辑/批量比较未闭环。FLUX/Qwen识别不等于模板执行。 |
| Director | structured notes、镜头/情绪/节奏/表演；原rule proposal与broker-backed coordinator、派生审核 | **PARTIAL**；scene_id必填，自动proposal依赖非空SCREENPLAY。Graph director_note是手工note，无完整scene-free模型导演台。 |
| Storyboard | stableID/编号、景别/构图/运镜/场景/声音、derive/CAS/history/export | **PARTIAL**；ShotCard.scene_id须对应scenes，无独立镜头asset/typedStoryboard节点/真实画面breakdown。 |
| Video | standalone T2V/I2V/V2V配置能力、来源、原异步task/refresh、私有输出/review、Graph接owner | **PARTIAL/LOCAL_REQUIRED**；I2V/V2V单素材，白模/动作/摄影机无独立验证映射。LTX/Wan/Hunyuan名称不是通过证据；cancel非remote abort。 |
| Audio | TTS/MUSIC/SFX、真实PCM WAV trim/gain/resample/mono-stereo证明；Whisper/MFA运行代码 | **PARTIAL**；FLAC/MP3交付、独立降噪/分离、多角色完整链未完成。async无polling保持UNKNOWN；模型加载/质量NOT_RUN。 |
| Editing | schema2 VIDEO/AUDIO多轨、图片片段、锁轨、裁剪/分割/移动/变速/混音/字幕、FFmpeg render/H.264/VP9export、OTIO/SRT/VTT loss确认导入、播放缓存代码 | 有界 **PARTIAL**；8轨每类4、30片段、600秒、1920x1080/60fps，字幕为captions；专用图片/字幕轨、完整waveform/proxy/专业操作欠缺。FCPXML/CMX EDL未实现、目标编辑器兼容 **BLOCKED**。 |
| ModelCenter | Ollama/LMStudio/ComfyUI/llama.cpp/安全根发现，位置/类型/能力/runtime/可选VRAM profile，原明确准入 | **PARTIAL**；启动可恢复Host-bound已有snapshot，freshscan仍原scope preview/confirm；unknown VRAM保持unknown，不全盘扫描/复制/重复下载。 |
| UI/UX | shared shell、Graph/素材/制作、Inspector、headless media/timeline/transfer/playback、局部高级折叠 | **PARTIAL**；不是完整专业桌面或全局simple/pro模式，保留Opus替换视图边界。 |

依据：`production_execution._binding/_parameters/_recipe/providers`、`discovery_bridge.LocalImageAdapter`、`discovery.validate/enable`、`asset_providers.ComfyUIImageProvider/Automatic1111ImageProvider`、`models.DirectorSceneNote/ShotCard`、`graph_models`、`studio_timeline_schema/edit/export`、`experimental/timeline_exchange`、`studio_audio_execution`。现有断言包括`test_local_ai_discovery*`、`test_r2_local_image_dispatch_guard`、`test_rebuild_image_transport`、`test_v2_creative_workflows`、manual_mask/cpu_cutout/graph/studio相关测试与独立工作区controller测试；本轮未重新执行。

## 4. 下一阶段开发计划：Image 原模型接入

先发布本审计，再实现第一条有界生产连接，不重复现有功能。

1. ModelCenter已验证、注册、明确启用的本地IMAGE adapter接原ProductionExecution→ImageJob→Asset→review。
2. 被动枚举原registry routes，不能调用会probe的`discovery.media_routes()`。
3. route绑定原registration identity/enable生命周期/runtime-model evidence；disable/re-enable ABA或配置/checkpoint变化使旧preview/job拒绝发送。
4. 原caller last-mile guard与delegate closed parameters、真实model remap、固定recipe、reference limits贯通。T2I-only Comfy evidence不自动开放I2I；无任意workflow、cloudfallback、新operation或Graph参数。
5. configured providers旧请求摘要兼容，原审核/UNKNOWN/来源权限/outputproof不变；不宣称统一Router财务结算完成。
6. 相关unit/API/File、必要fresh PG、UI consumer/types检查，保存源码hash及失败。里程碑完成执行完整CI；当前账单阻塞不绕过。Windows最终安装/GPU/真实模型另行授权。

随后按Image→独立Director→Storyboard→Video reference→Audio→Editing安全依赖继续；各模块无需从小说开始。AI maskedit/upscale/repair须真实支持adapter及执行验证。独立FLAC是后续Audio最小交付；MP3需lossy/encoder delay/padding证明，不能套WAV证明。M4→M9真实验收顺序、F00 INTEGRATED＋39 PARTIAL、独立复审BLOCKED不变。

## 5. 风险分析

- wrapper只补supports_dispatch_guard标志不安全；每次upload/send/poll/download须原准入身份与caller guard，无授权旁路。
- Comfy当前metadata validation只固定SD T2I六节点；文件名不证明FLUX/Qwen/I2I/任意workflow可执行。
- source检查保留Asset锁外，不能反转registry/job/source锁序或递归probe。
- 丢失发送回执、晚到结果保持UNKNOWN；无自动重放/换requestID/无限timeout/rerun-until-green。
- 原Host scope preview→confirm发现；扫描授权不等于register/enable/start/inference。凭据/stderr/私人路径/用户作品不公开。
- V1默认凭据/frozenassets、Graph1/2、configured默认摘要、original assertions/generators/frozen9151/历史证据不改。
- a40 CI cancelled/PG timeout/failed-call与新billing blocker保留；模块测试不能证明Windows/GPU/质量验收。

## 6. 文件修改计划与 Opus 边界

| 计划文件 | 目的/条件 |
| --- | --- |
| 本审计、FeatureMatrix、MilestoneHistory、docs/v2/CHANGELOG与README | 先提交只读审计；历史条目保留、追加观察。 |
| `app/model_center/discovery_bridge.py` | 原LocalImageAdapter的被动能力/身份绑定/明确guard/delegate方法。 |
| `app/creative/production_execution.py` | 原local registry枚举、binding/parameters/recipe连接、旧默认身份兼容。 |
| 必要时原discovery validation | 仅真实独立结构证据需要时追加，不自动放宽能力。 |
| 新`tests/test_v2_discovered_image_production*.py` | 零probe清单、remap/recipe、execute/review、Host/ABA/stale/CAS/UNKNOWN/legacy负例。 |
| 原frontend production client/controller相关测试 | 优先消费原响应形状，不改visible shell；必须新提示时再按UI skill/designsystem实施。 |
| Matrix/Changelog/README/脱敏阶段报告 | 记录实际源码/测试/发布SHA/剩余门禁，不上传原始log/DB/config。 |
| API/V2 inventory artifacts | 只用不变原生成器同步，不改冻结基线。 |

Opus可替换JSX/布局/token样式，继续调用useStudioMediaExecution、Graph及timeline editor/transfer/playback的命名动作和严格Host client；不合并preview/create/execute/review，不绕过dirty/CAS/epoch/UNKNOWN/Blobrevoke。受保护shell/主题/primitive系统修改遵循原DesignSystemChangeRequest。

本审计提交后才开始上述第一阶段。当前产品不因本文成为发布级。
