# Whisper、强制对齐、播放缓存与交叉溶解

这是 Phase14 的源码实现记录，不是执行验收。按用户要求，本批没有运行测试、collect-only、导入、语法编译、typecheck、构建、CI、FFmpeg、Whisper、MFA 或 GPU；青简未推进。M4 PARTIAL、M5–M9 LOCAL_REQUIRED 及全部历史失败证据保留。

## 原字幕任务与可信模型生命周期

`app/model_center/whisper_runtime.py` 和 `native/local_whisper_host/main.cpp` 实现固定模型的实际加载／推理主机；原 Model Center 的显式启动收到真实私有 pipe 证明后，才注册原 AUDIO node。原 `SubtitleTimelineService` 的 lazy resolver 只消费该 owner 当前的实际 `ModelRuntimeSubtitleAdapter`，配置、health 和文件发现不构成准入。

未加载时目录保持 ASR NOT_CONFIGURED；停机、卸载、退出或重新加载撤销原 route。旧任务保存 adapter identity／模型 route，不能自动重绑。恢复须明确 cancel／resume 或另建任务。实际执行仍经原 DesktopHost 会话、scope、字幕 flags 和 AI 执行 gate，反复核对来源、任务 claim、adapter identity 与 model binding；结果必须带原私有模型加载来源和真实 ASR 时间戳证明，随后人工审核。

V2 服务器配置（绝对路径及小写 SHA256 均由受信任安装者提供；HTTP 无权提交或修改）：

```text
AI_NOVEL_PACKAGED_PROFILE=v2
AI_NOVEL_STUDIO_V2_SUBTITLE_FFMPEG=<可信 ffmpeg.exe>
AI_NOVEL_STUDIO_V2_SUBTITLE_FFPROBE=<可信 ffprobe.exe>
AI_NOVEL_STUDIO_V2_WHISPER_HOST=<固定主机 studio-fixed-whisper-host.exe>
AI_NOVEL_STUDIO_V2_WHISPER_HOST_SHA256=<实际发布二进制 SHA256>
AI_NOVEL_STUDIO_V2_WHISPER_MODEL=<已有 GGML Whisper 模型>
AI_NOVEL_STUDIO_V2_WHISPER_MODEL_SHA256=<独立核验的模型 SHA256>
AI_NOVEL_STUDIO_V2_WHISPER_FFMPEG_SHA256=<上述解码器 SHA256>
AI_NOVEL_STUDIO_V2_WHISPER_PORT=8178
AI_NOVEL_STUDIO_V2_WHISPER_THREADS=4
AI_NOVEL_STUDIO_V2_WHISPER_USE_GPU=0
```

可选值采用上述默认值；必填配置部分缺失直接拒绝，不降级。原 Model Center 的 `whisper-fixed-local` 使用原 start／stop 操作，固定配置只读。当前新增打包脚本是 CPU_STATIC，`USE_GPU=1` 不会使它成为 CUDA 包；GPU 依赖与能力仍须独立构建、固定并真实验证。完整构建与证明链见 [固定 Whisper 主机](whisper-fixed-host-build.md)。本批没有下载、构建或配置本机 Whisper 模型。

## MFA 实际声学强制对齐

`subtitle_alignment.py` 接入固定 MFA 3.3.7 的真实 `align_one`：完整运行时／发音词典／声学模型逐文件 SHA 固定 → 实际源媒体核对 → 单声道 16kHz PCM 解码 → 真实 MFA → 严格 long TextGrid 词／音素区间 → 原 cue ticks → 原 NEEDS_REVIEW／approve。

它不使用 ASR 分段或平均分词估计时间。已知限制明确拒绝：最多 8MiB／600 秒来源、32000 UTF-8 bytes／500 个空格分词词项、单音轨、无 OOV、无说话人归属；每词须匹配固定词典，中文需要明确空格分词。原始词文本与边缘标点保留；整数时间基向内量化，区间为零、越界或重叠即拒绝。质量／口型同步仍 NOT_RUN。

```text
AI_NOVEL_STUDIO_V2_MFA_RUNTIME_ROOT=<已有自包含 Python/Conda MFA 前缀>
AI_NOVEL_STUDIO_V2_MFA_MANIFEST=<前缀外部 studio-mfa-runtime/1 JSON>
AI_NOVEL_STUDIO_V2_MFA_MANIFEST_SHA256=<独立核验的 manifest SHA256>
AI_NOVEL_STUDIO_V2_MFA_DICTIONARY=<已有本地 .dict>
AI_NOVEL_STUDIO_V2_MFA_DICTIONARY_SHA256=<词典 SHA256>
AI_NOVEL_STUDIO_V2_MFA_ACOUSTIC_MODEL=<已有本地声学 .zip>
AI_NOVEL_STUDIO_V2_MFA_ACOUSTIC_MODEL_SHA256=<声学模型 SHA256>
```

`scripts/prepare_mfa_runtime_manifest.ps1` 可对明确提供的自包含 Windows 前缀生成完整文件 manifest，并只创建全新的外部文件，不运行或下载任何模型。须使用 `python.exe`、实际 `Scripts/mfa.exe` 的相对路径；拒绝 venv 委托、链接、缺文件、非 3.3.7 元数据及超限。生成 hash 本身不能建立来源信任，安装者仍须独立确认全部输入来源，再配置固定 pin。运行时也重新核对完整 inventory／SHA，不信任仅元数据版本。

执行只使用固定 Python `-I -B -m montreal_forced_aligner.command_line.mfa`，本轮私有临时目录、固定 flags、无 Postgres、无多进程／下载、有限超时。Windows 子进程在执行前加入 kill-on-close Job；任务取消、会话／来源改变停止本地执行并丢弃迟到结果。MFA 不创建第二个队列、数据库或凭据命名空间。本机运行时／词典／声学模型尚未配置或验证。

## 交互播放缓存

时间线保存后明确读取播放方案，核对并确认后才生成 H.264／AAC。稳定缓存 request ID 包含原 scope／incarnation／actor、exact timeline／sources／recipe 与实际编码器 SHA。原 VideoAssembly job 和不可变私有 Asset 是唯一持久 owner；相同请求已经存在或状态 UNKNOWN／失败时不重新编码。

原 playback-preview／build／attestation 复用 Host transport 和权限。复用浏览器字节前，后端重新经过原 candidate 的实际 bytes／version／digest／origin／scope／当前来源围栏；任务 GET 不替代该证明。浏览器 SHA 与测量字节数再次核对，最多两项／50MiB，会话／撤权／来源变化或检查失败撤销 Blob。明确播放、暂停、拖动及前后定位；无自动播放／批准。取消走原 owner 的 CAS；关闭传输不能冒称 FFmpeg 已取消。清缓存只清本会话 Blob，不删原任务与证据。

## 视频交叉溶解

schema 2 的 VIDEO clip 支持可选 `transition_out={kind:CROSS_DISSOLVE,to_clip_id,duration_ms}`。仅同轨紧邻两段、真实重叠恰好窗口、相同位置／尺寸／opacity、无独立 fades／静音、至少两帧且小于两段长度；链式交接窗口不能相撞。非法编辑在原 normalize／save／Graph author contract 拒绝，旧无 transition 字段的摘要保持原样。

原 FFmpeg 编译器实际对两源做统一 CFR／timebase、预乘 alpha、`xfade=fade`、反预乘与原轨道叠层；视频原声按同窗线性淡出／淡入，独立音轨混音保持。split 将 outgoing transition 移到右片段，duplicate 不复制关系，其余编辑须保留完整有效关系。OTIO native 投影明确记录 loss；Studio extension 可保存原关系，但不能称为 Resolve／Premiere 原生保真互通。

## Opus 的 UI／UX 边界与后续验收

播放视图为 `StudioTimelinePlaybackPanel`，行为独立于 `useStudioTimelinePlayback`；严格 DTO／原 transport 在 `studioTimelinePlaybackTypes` 和 `studioProductionClient`。Opus 可以更换视图、时间尺、拖放和视觉布局，须保留明确同意、父级互斥、UNKNOWN、原任务恢复／取消、候选字节证明、撤权清理和无自动播放／生成／审核。

这些新增源码尚未完成执行核验。后续从最终远端 SHA 统一做模块、权限、恢复、CAS 与完整 CI，再按原 launcher → PostgreSQL → backend → C# DesktopHost 完成可信会话、V2 隔离、重启／失效／中文路径／V1 不受影响，以及真实模型、Whisper/MFA、GPU、播放与成片质量验收。Windows ABI、native 依赖、内存容量、字幕质量及交叉溶解的帧／音频边界必须独立记录，不能从源码或 CPU build 推断通过。

其他未收束项（如 FCPXML／EDL 的原生互通和更广音频降噪／分离）仍保留缺口；本批不声称全功能或发布级验收完成。

固定实现依据：[MFA 3.3.7 CLI 与 module 主入口](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner/blob/v3.3.7/montreal_forced_aligner/command_line/mfa.py)、[whisper.cpp 1.8.2 C API](https://github.com/ggml-org/whisper.cpp/blob/v1.8.2/include/whisper.h)、[FFmpeg xfade](https://ffmpeg.org/ffmpeg-filters.html#xfade)。来源阅读不构成运行证明。
