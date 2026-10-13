# V2 执行细节收束与剩余边界

本批继续实现后端与基本操作入口，所有测试、导入执行、类型检查、构建、CI、原生工具和模型调用均按用户要求 **NOT_RUN — USER_DEFERRED**。代码存在与发布验收分开记录；本文件不能证明所有历史功能已经完成或达到发布级。

## 原 owner 中新增的实际执行

- 原 Studio 时间线新增 transfer-preview、transfer-import、transfer-attachment：SRT／WebVTT 字幕和 OTIO 多轨转换均有具体转换代码。预览脱离持久状态；只有明确确认预览摘要、loss receipt、原版本及媒体快照后才原子写入原时间线。附件经原 Host transport 下载，不写任意用户路径，不抓取 OTIO 外部引用。
- 原多轨渲染器支持 schema 2 可选整数 crop；坐标是源编码像素，在显式裁切时先禁止自动旋转，核对实际源尺寸，再裁切与缩放。它不是已旋转预览图的坐标。超出实际来源拒绝执行。
- 原作者编辑支持可选 locked。锁轨不能删除、改片段、间接改画布或被 whole-save／restore／transfer 替换解锁；只能原 track.update 的独立 `{locked:false}` 操作解锁。锁不授予权限，也不代替原 scope／Host 门禁。
- Image／audio／video 在 publish 前保存实际输出摘要、字节数、类型；进程中断后显式 reconcile 只查同一个私有候选和来源证明，准确回填原待审核任务，不重发、不重新生成。旧记录没有该持久证明时继续 UNKNOWN。
- 审核失败仅在证明原候选未提升、version／digest／完整来源及 project binding 一致时补偿原 REVIEWING 预留；显式 reconcile 也可恢复中断留下的同一私有预留，即使原来源随后改变。该内部补偿不授予新的生成或审核权限；已提升或证据不明的状态保留并等待准确回执恢复。原失败证据不删除。
- 未记录候选版本的 publication recovery 只接受原私有创建版本 1；后续元数据编辑不能用当前版本为自己生成恢复证明。
- 候选读取核对 exact version／完整 origin／project binding／审核证明和实际字节；最终 image／audio／video／timeline queue 回执重读统一在 source／asset phase 外。取消后的原私有结果仍可检查，不构成重新采用或批准。
- 原 audio trim 使用原受控进程 guard、明确时限和超过上限的拒绝；取消／Host 或 Graph 失效可停止受控进程，迟到结果不能采用。
- 原字幕处理任务可执行受控 FFmpeg 烧录并保留实际编码／尺寸／帧率／声音／时长与字节证明，批准后才下载。原时间线已经支持字幕烧录，本适配器也使原独立字幕任务拥有具体实现。
- 原 Model Registry 新增 AUDIO node；whisper.cpp 适配器有真实音频解码、一次本地 multipart `/inference` 请求、严格 timed segments 校验、原队列审核及模型回执代码。没有可信模型准入时它仍不可执行。
- Phase14 新增固定 Whisper native host 的真实模型 HANDLE 加载与私有 pipe 证明、原 Model Center 生命周期和字幕 lazy resolver；未配置／未加载仍 NOT_CONFIGURED，实际推理质量仍 NOT_RUN。新增 MFA 真实声学强制对齐、原持久候选的明确交互播放缓存，以及双源视频交叉溶解。具体实现、配置和限制见 [媒体执行收束](media-execution-source-completion.md)。
- Graph 中断 REVIEWING 的维护沿原 run／node／job／版本／请求／候选／Host／incarnation 证明执行；旧 Graph 或来源变更不阻塞被证明未提升的私有占用释放。它只更新原 owner 回执，不推进节点、归档、发送或提升，不授予 stale 来源执行／审核权。前端恢复三字段必须由当前原 Host client 实际 GET 观察到。
- 前端支持明确选择本地 .otio／.srt／.vtt，经父级 mutex、容量、严格 UTF-8、保存版本／当前来源／client／epoch 校验后只读入本轮交换草稿；映射、预览、明确导入和附件仍分别操作。Opus 可替换对应视图而保留 headless 操作边界。

## 字幕运行配置

仅 `AI_NOVEL_PACKAGED_PROFILE=v2` 读取以下 server-owned 环境值：

```text
AI_NOVEL_STUDIO_V2_SUBTITLE_FFMPEG=<已安装并受信的 ffmpeg.exe 绝对路径>
AI_NOVEL_STUDIO_V2_SUBTITLE_FFPROBE=<已安装并受信的 ffprobe.exe 绝对路径>
```

必须同时明确配置，构造只校验工具位置与哈希、不启动进程；未配置保持 NOT_CONFIGURED。HTTP 只接收 adapter ID，不能提交可执行路径或 shell 参数。V2 processing HTTP 使用原 DesktopHost principal／会话 guard，默认 V1 配置与凭据保持原样。未设置、设置错误、编码器缺失与执行失败都不能记为“能力通过”。

ASR 使用原 `ModelRuntimeSubtitleAdapter`，由原固定 Whisper Host owner 的私有 pipe 实际模型加载证明授予 AUDIO Registry 准入，再按当前 route 懒读取到字幕任务。`/health`、本地文件发现、客户端自报哈希或单纯能访问 `/inference` 均不足以授予身份。应用默认 **ASR NOT_CONFIGURED**；V2 的 server-owned 固定路径／SHA 配置仅安装原生命周期 owner，显式原 Host start 成功后才能有当前 ASR adapter，不自动启动或下载。完整环境字段与 MFA 配置见 [媒体执行收束](media-execution-source-completion.md)。旧裸 server 的显式兼容回调不被应用用来自动准入。

## 尚未完成，不能用接口或本批源码冒称通过

- Whisper、MFA 强制对齐、交互播放缓存与 cross-dissolve 已有实际执行源码；native 构建、运行配置、模型加载／质量、Windows／GPU、交互与成片仍未执行验收，不能写成能力已通过。MFA 的中文输入须明确空格分词并匹配固定词典。
- FCPXML／EDL 的实际互通与更广音频转换／降噪／分离仍有缺口；上述历史需求须按实际原 roadmap 范围继续收束，不能被通用 schema 或模型 family 名称覆盖。
- Opus 5.5 后续仍可重构视图和 UX；原 headless 控制器、Host transport、CAS、dirty／UNKNOWN、loss confirmation 和原 owner 是操作边界，不可用 UI 重构绕过。
- 当前仓库历史 feature matrix 是需求对照快照，Master Roadmap 全文未在本批恢复时找到；不猜测缺失附件，也不改写历史状态来制造全功能封顶。

## 实际验收门禁保持

M4 仍 PARTIAL，M5–M9 保持 LOCAL_REQUIRED，按 M4→M9 顺序进行真实验收。Windows Application 构建、launcher→PostgreSQL→backend→DesktopHost、V2 数据／缓存／vault 隔离、重启／会话失效／中文路径／V1 不受影响、真实 GPU／模型完整闭环都必须以最终远端 SHA 的实际证据确认。

a40df115 历史 CI 29 jobs 的 20 success／5 failure／4 cancelled、两个 Cloud cancelled、PG 的终态 timeout 与取消分片 failed-call、File 不完整及严格汇总门禁失败原样保留。本批没有复现、删除断言、加无限超时或 rerun-until-green；F00 INTEGRATED＋39 PARTIAL、独立复审 BLOCKED、原 NOT_RUN 均不变。


## 后续图片运行时更新（2026-10-13；不改写上述历史NOT_RUN）

基线c911e549之后仅深化Image。固定配方、显式来源／权重／作者Mask、原任务／私有
候选／审核及图片Graphschema4已有实际执行源码；相关隔离测试恢复执行，结果见
[本阶段报告](production-expansion-image-runtime-20261013.md)及JSON。合成HTTP、
真实File/PG/PNG检查与实际Comfy/A1111模型效果分开，整体仍PARTIAL/LOCAL_REQUIRED。
超分仅保留闭合输入／adapter协议和不可执行标记，不能据此宣称超分已实现。
Opus可重构视图，必须保留原controllers、Host/CAS/来源版本/dirty/UNKNOWN/明确审核。
没有进入Video、QingJian、Windows最终验收、GPU压力测试或真实模型全面推理。


## Production Expansion Phase 2（2026-10-14）

上文仅预留超分的状态属于旧基线。本批新增实际已启用本地 Comfy 超分路径：原
Model Center 注册、固定配方、实际 PNG 尺寸/摘要证明、原 ImageJob 私有候选与
明确审核入库；源图 <=2048、目标 <=4096、2×/4×，不得当成真实模型效果验收。
Control 的 Depth/Pose/Edge/Mask/Layout 仍 RESERVED / NOT_CONFIGURED。
导演视觉目标/表演及分镜角色/情绪沿原 Creative 文档，明确逐导演调度派生镜头；
Graph 读取精确已保存文档，保留来源与隐私，连接 Style/Image/Review，不自动改稿。
独立导演/分镜手工创作无章节要求；原导演模型协调器仍要求章节锚点。模块 PARTIAL，
Windows/GPU/真实模型与 M4→M9 门禁不变，详见 [本批报告](../../DIRECTOR_STORYBOARD_IMAGE_PHASE_REPORT.md)。


## Phase4（2026-10-14）

新增原 Creative 历史镜头版本、相邻关系、导演建议、正式图片绑定与明确审核；已审核分镜可创建原 Timeline 图片底稿。schema5 是明确选择的视频图，沿原 VideoJob、ModelCenter、私有候选和人工审核。固定 Comfy LTX/Wan/Hunyuan 配方是有界执行源码，非真实模型质量证明；本地 V2V/视频参考条件与未知版本 NOT_CONFIGURED。实际输出尚未证明与配方尺寸/帧数完全一致。Timeline 未知创建保持独立围栏，Phase5 补持久化请求核对。File/PG 各616通过但各有1Windows权限前提失败；前端3167通过/8跳过；不能称完整CI或产品验收。原 M4→M9、F00、独立复审 BLOCKED 不变，Windows/GPU/真实模型 NOT_RUN/LOCAL_REQUIRED。


## Phase5（2026-10-14）

视频来源精确pin贯穿原任务/Asset；正式审核结果按原获批历史绑定镜头，元数据更新不伪造新的作者ShotVersion。原Timeline创建幂等/只读恢复、正式视频片段采用及完整last_edit effect证明已执行，不新建owner；实际范围超出已解码媒体会拒绝。Graph5新pin需bind_shot:true，旧无pin结果不能冒认新镜头归属。模型路径/文件大小观察仅旧授权扫描投影，不授运行资格；VRAM/模型总bytes未知。File/PG各317pass但各有2原Windows权限前提failure；frontend3250pass/8skip；metadata44pass/2failure，Linux4原断言单独pass。Hosted平台账户阻塞未执行，全产品/native/GPU/model与原M4→M9/历史失败保持原门禁。

## Phase6（2026-10-14）

原独立audio.trim明确FLAC有真实固定编码与STREAMINFO/实际PCM/frame/MD5/SHA证明，原WAV默认及Graph闭合身份不变；MP3和完整AUDIO-12仍未完成。原Timeline有正式素材原子加入/替换、当前普通edit_receipt及完整请求/效果UNKNOWN只读恢复。实际小CPU混音/render/export→私有→Review→正式Asset→重开已执行，不代表完整NLE/音频工具/模型质量/native验收。新SOURCE_EDIT发送前拒非零abs<1e-4，不舍入不改原后端摘要或一般草稿小数控制。File/PG各377pass/178skip；frontend3289pass/8oldskip；metadata44pass/2原Win1314失败保留。Hosted平台阻塞无执行；历史M4→M9、F00、独立review和Windows/GPU/model门禁不变。详见[报告](../../PHASE6_AUDIO_EDITING_REPORT.md)。
