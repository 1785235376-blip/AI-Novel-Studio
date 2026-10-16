# Phase 6 — Audio Studio / Editing Studio 扩展报告

## 实际基线与状态

基线为 `a590bad645a9e230cc70c2122dfb1cca624a9d65`，来自已推送的 Phase 5。既定分支为 `feature/v2-narrative-platform`，PR #47 保持 Draft。此次新增的是原系统上的独立 FLAC 交付、正式素材编辑操作和后期链路证明；这些有界子能力为 **IMPLEMENTED**，完整 Audio / Editing 与产品仍为 **PARTIAL**。

后端检查输入 tree：`fc78b1c986f29f7d36b7931616c4f7a606879f70`；前端最终检查输入 tree：`f19d9cf53363d9f9dfea744e878d4b38a11b6d19`。后端镜像含基线前端，两棵测试树分别记录。[脱敏摘要](docs/v2/phase6-audio-editing-20261014.json)保存 20 个源码、测试与合成 fixture 的 blob 哈希。最终 commit 与远端 SHA 在 PR #47 和私有 publication receipt 核对，不在自身提交内虚构未来 SHA。

## FLAC 已落实到原执行 owner

原独立 `m8.audio.trim` 新增明确选择 `output_format: "FLAC"`，其他操作拒绝该参数。未设置或 null 时完全省略，原 WAV 请求、preview、recipe 和请求摘要身份保留。Graph 的参数边界不新增此项，也不开放原独立 gain/rate/channel 控制。

固定执行使用 FLAC、signed 16-bit、compression level 5，并沿用原增益、8,000–96,000 Hz 和单/双声道处理。FLAC 对处理后的 S16 波形做无损编码；增益、重采样或声道转换仍可能改变输入波形。没有另建导出体系、任务队列或 Asset owner。

实际输出证明沿原 Job、私有 Candidate、人工 Review、正式 Asset 和持久恢复保存。证明包含原九字段和 `total_samples / decoded_pcm_bytes / streaminfo_md5 / decoded_pcm_sha256`，严格区分 FLAC 与原 WAV。

- 首个唯一 34-byte STREAMINFO、有界 128 个 metadata blocks / 1 MiB framing，以及有效 S16/rate/channel/sample-count 必须成立；零未知样本数或 MD5 被拒绝。
- 原受控进程执行 20 秒 ffprobe 与 30 秒实际 PCM 解码；解码到私有文件，不进入 1 MiB stdout 捕获，也不以 `-ar/-ac` 修正错误输出来冒充证明。原裁剪编码时限仍为 50 秒。
- 实际 PCM 字节数等于 samples × channels × 2，MD5 与 STREAMINFO 一致；另保留 PCM SHA256 与编码输出 SHA256，Asset 身份仍用 SHA256。输出文件在原生操作前后核对字节与摘要。
- 最终接受的编码数据和解码 PCM 均受原 25 MiB 上限。`-fs` 是原生进程侧保护，不能描述为零超出临时写入的保证。
- 时长来自实际样本数，容差最多一个解码样本；不把 WAV 的 ±2ms 或此证明套用于尚未实现的 MP3。

上述格式依据与实际解码分开：[RFC 9639 §8.2](https://www.rfc-editor.org/rfc/rfc9639.html#section-8.2)、[FFmpeg FLAC encoder](https://ffmpeg.org/ffmpeg-codecs.html#flac-2)。metadata 不是成功证明，必须通过真实受控解码。解析错误不吞取消异常；源探测在 Asset 锁外，取消/来源/Host guard 沿原 owner。原 publication UNKNOWN 可以明确恢复既有候选，不重复编码。原始 stderr、私人路径和临时 PCM 不进入 API 或公开报告。

## 原 Timeline 操作与 UNKNOWN

原 `/edit`、CAS、锁轨、source snapshot、history 与 restore 保持。新增前端操作明确选择正式 Video/Audio/Image Asset，精确绑定 ID/version/digest/kind；可创建轨道并在同一原批次插入首片段、插入已有轨道或替换既有片段来源。空 `track.insert` 与 `clip.insert` 在同一批次，失败整体 rollback，不留下空轨或部分历史。私有候选不能作为正式来源，范围由原 owner 校验。

原 `_timeline_view` 只在当前普通 `last_edit` 有效时投影五字段 `edit_receipt`：request_id、request_digest、input_version、input_digest、output_digest。当前版本必须为 input+1、当前 digest 必须为 output。历史行不变成当前确认；restore 清除当前普通回执。没有新 API、journal 或幂等系统。

前端 source-edit seam 在发送前核对来源和完整请求；回复或只读 GET 必须证明原 fullbody SHA、输入版本/摘要、输出摘要及完整 track/clip effect，才解除 UNKNOWN。丢失回复不自动 POST 重放。原 Host/client/epoch、来源变更、迟到结果、dirty、父级 mutation mutex 与旧 embedded client 无新方法的原路径继续保留。

复审发现 JS/Python 对极小小数的 JSON 摘要表示差异。仅新增来源操作在发送前拒绝非零绝对值小于 `1e-4` 的数值；不舍入或改写 body，普通 `-3.5` 保持并与原 Python fullbody SHA 对照。原后端摘要/normalizer 和一般时间线草稿的小数控制不改变。Opus 后续必须保留此明确输入边界，不能发送已知无法核对的请求。

## 实际 CPU 后期链

新集成测试调用原执行器和实际 FFmpeg，不使用模拟成功的 renderer：

`合成 WAV → 原 FLAC trim → Private Candidate → 明确 Review → 正式 Audio Asset v2 → 原 Timeline 原子插入 → 实际默认 MP4 render / 明确 H264 export → Private Candidate → Timeline Review → 正式 Asset v2 → 新实例重开`。

一秒 64×64 / 10fps 的合成蓝色视频与 440Hz 音频混合。独立解码验证十帧实际画面、48000Hz 双声道非静音 PCM、帧/样本范围与 SHA，并核对原候选、批准后下载及重开字节。音频裁剪实际区间为 100–900ms、22050Hz mono；fade 和混音沿原 Timeline。

测试还覆盖 stale Asset/CAS、锁轨、批次 rollback、真实编码完成后的来源变化/取消、publication 中断 UNKNOWN、同 ID 不重渲染、明确 reconcile 原候选，以及 mounted API 的迟到 Host 撤权/ABA/rebind 拒绝。Audio 新专项在 probe/decode 各阶段使用实际受控睡眠子进程验证终止、回收和私有目录清除；它不是 GPU/model 取消验收。

## 实际验证与保留证据

各组有重叠，不相加；收集数量不是执行通过数量。

| 检查 | 实际结果 | 证明边界 |
| --- | --- | --- |
| 冻结后端 File | 377 passed / 178 applicability skipped / 0 failed | 17 个直接相关模块；原断言未改 |
| 同一冻结后端真实 PostgreSQL | 377 passed / 178 applicability skipped / 0 failed | fresh 独立 loopback DB、原 migrations；正常停止 server，证据 DB 保留 |
| 四个新增后端模块子集 | 各 profile 52 passed / 44 applicability skipped | 已包含在上述结果中，不相加 |
| 最终整套前端 | 3289 passed / 8 原有 skipped / 0 failed | P2 修复后的冻结源码；39 新 cases 已包含 |
| 类型 / build / design tokens | 通过；令牌检查 52 文件 | 原检查器未改；build 是前端生产构建 |
| 原 shell / geometry 浏览器快照 | 7 passed，未更新原快照 | 不是新专业工作区 UX 或原生 DesktopHost 验收 |
| 原生成清单检查 | 44 passed / 2 failed | 原 Windows symlink 安全权限前提 WinError1314，失败与断言保留 |
| 原 API / coverage 生成器 | 2243 API operations / 14225 collected nodes | 全部 9151 冻结节点/顺序保留；无 removed operation，INVENTORY_ONLY |

同源码的 Phase 5 Linux 四项原 symlink 断言已通过；本阶段逐文件核对相关原源码相同，作为前阶段补充证据引用，没有重跑或回填为 Windows 成功。Python 3.12.9、Node 22.14.0、FFmpeg/ffprobe 8.1.2、PostgreSQL 16.15 沿已确认的隔离工具。测试不访问用户数据库、作品或模型。

保留全部开发失败：Audio R1/R2 的新 API fixture setup 缺口与 DEVNULL stdout 新测试前提错误，仅修正新增测试；杀进程、时间、清理和不发布断言保留。Editing R1/R2 的首次回复与 GET 派生状态前提，以及 R3 旧 fixture 捕获 owner/Timeline leases 404 均保留，原 renderer 未因此改写。Frontend 首轮两项真实 omitted track defaults 缺口与三项新 fixture 时序缺口、首次类型错误、复审数值 P2 均有私有修复前后证据。根代理 R1 前端 3285 pass/8 skip 对应 P2 修复前源码，不能替代最终 R2 3289 的输入树。

GraphFlow context 已使用；plan/index 的未返回或 Transport closed 回执保留，不声称索引成功。源码冻结和独立测试不依赖此工具成功。

## 尚未完成与交付边界

基线 Phase 5 的 29 个 Hosted jobs 均 runner_id=0、没有执行步骤，账户/平台阻塞诊断私有保留，不是产品测试结论。最终新 SHA 的 Hosted CI 在提交后另行核对，不预报通过，不重跑或弱化门禁。

MP3、完整 AUDIO-12、完整独立音频编辑器/Audio Canvas、更广 provider/降噪分离效果、专业 NLE 和外部剪辑软件互通仍按原矩阵 **PARTIAL / NOT_RUN / LOCAL_REQUIRED**。本批没有运行真实 TTS/ASR/Whisper/MFA、LTX/Wan/Hunyuan、RTX5080 推理或重型渲染。

Windows 最终 Application 安装、launcher→PG→backend→C# DesktopHost 可信会话、V2 vault/数据/缓存隔离、重启/失效/中文路径/V1 不受影响仍 **NOT_RUN / LOCAL_REQUIRED**。隔离 mounted test 的模拟 Host/凭据配置不代表该验收，也不修改产品认证边界。

Opus 可重构 Canvas、Inspector、Preview、素材操作面板及布局；原 controller/client、父级互斥、Host/来源/CAS/UNKNOWN、完整回执/效果和明确 Review 必须保留。新增 `StudioTimelineSourceEditPanel`、`useStudioTimelineSourceEdit` 和 `studioTimelineSourceEditContract` 是视图与操作的边界，不能让 UI 自行授予权限或审核。

不推进青简；V1 冻结内容、旧测试/证据、PoemSeed Local Interop1.0、历史 F00 INTEGRATED＋39 PARTIAL、独立复审 BLOCKED 与 M4→M9 实际验收顺序保留。源码提交不是发布或全产品验收。
