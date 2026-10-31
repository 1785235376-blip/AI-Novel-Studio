# AI Novel Studio V2.0.0 发布说明（2026-10-31）

## 版本
- 产品版本：**2.0.0**
- 显示版本：V2.0（`release/version.json`，channel=`stable`）
- 一致性消费者：`pyproject.toml`、`app/__init__.py`、`frontend/package.json`、`.env.example`（`APP_VERSION`）、`README.md`、`docs/installation.md` 均由 `scripts/validate_release_version.py` 校验。

## main 合并内容
1. PR **#51**：Studio V2 后端能力补齐（Windows 游标密钥/项目删除信号）+ 安全硬化（merge `46ef2e12`）。
2. PR **#52**：全分支后端收尾（86 heads 核验/对账；Export/PG 018-020/VTT-OTIO/Canvas；容量账本/admission/历史写入计费；音频历史捕获-读取-迁移-恢复；运行时能力与 Studio 任务成本 UNKNOWN 合同；回归/安全复核）（merge `2d14f8c0`）。
3. PR **#53**：前端/后端对齐（frontend/UX/i18n 51 文件修正）（merge `d11c890c`）。

## 明确边界（不得写成验收通过）
- 真实验收 **尚未执行**：真实 PostgreSQL、真实浏览器/前端 E2E、真实模型/GPU、Windows 打包桌面、hosted CI、外部 NLE 均为 NOT_RUN；
- PUBLISHING 独立审阅、Windows ACL/junction 探测仍为 BLOCKED；
- CJK 字体授权、真实 Provider 授权、远程 frame provider 抓取策略、音频 canvas_return、额度策略等仍需产品/人员决定；
- 历史产品线（`#36`–`#49`、`#26` 等）未合入 main，保持原分支；`#47` 等仍为 DIRTY/超大分叉，合入会回退已验证的 V2 后端，未执行批量合并。
- 证据索引与逐分支状态见 `docs/delivery/BACKEND_FINALIZE_FINAL_REPORT_20261031.md`；历史合并回退：`git revert -m 1 <merge-commit>`。

## 2026-10-31 能力补充（V2.0 后）

### 容量 admission 覆盖全部 AssetLibraryService.create 调用方
`ENABLE_PROJECT_CAPACITY_ADMISSION` 开启时，容量 admission 从手工导入路由下沉到共享资产 owner `AssetLibraryService.create`：所有原始资产写入（模型 clady 参考、手工遮罩、视频参考帧、生产任务产物、prompt authoring、comic/portable/媒体/音频服务等 16+ 调用点）统一先 reconcile/UNKNOWN 拒绝/预留，成功后按实际 `bin+json` 字节 commit，失败先 reconcile 残渣再释放；手工导入路由传 `_capacity_admitted=True` 避免双重计费。默认 flag 关闭，默认行为不变。

测试：`test_project_capacity_create_coverage.py` 5 passed；容量组回归 75 passed；相关子组 71 passed（2 项旧 `/novels/{nid}/assets` 503 期望在合并前 main 同样失败，属于既有关闭门预存失败）。

未完成：非资产 owner 项目文件/导出/共享文档写入口、启动自动对账门、审批/撤权竞争、真实 PG/崩溃窗口；真实环境验收仍未执行。

### 能力补充：V2 全能力注册表（machine-readable）
`studio-runtime-capabilities/1` 新增 `capability_registry`（`v2-capability-registry/1`）：逐项列出小说/章节、剧本分镜、IMAGE、VIDEO、Graph、音频、音频历史、Timeline、导出、TaskCenter、资产查询、容量、成本、canvas_return、真实环境与阻塞项的状态、flag、证据与限制。默认状态下音频历史/容量为 `UNAVAILABLE_BY_FLAG`，真实 PG/浏览器/模型/打包桌面/hosted CI/外部 NLE 为 `NOT_RUN`，PUBLISHING/ACL 为 `BLOCKED`，F37 根因为 `UNKNOWN`。新增测试 4 项（只读/确定性、默认边界、flag 反映、形状与路径脱敏）；runtime capability 组合 18 passed。

### 能力补充：历史写入启动对账门
音频历史的容量预留（双 flag）读取账本 `reconciled_at`，要求不早于当前进程启动；重启后旧账本 stale → `AUDIO_HISTORY_CAPACITY_NOT_RECONCILED`，必须先显式 reconcile（或由 admission 重新对账）。admission 路径每次写前 reconcile，不受影响。新增测试 1 项，音频历史容量文件 12 passed；registry 的容量限制同步更新为 `startup_reconcile_gate:IMPLEMENTED_FOR_HISTORY_WRITES_ONLY`。

### 能力补充：Timeline 音频导出 PCM24 + WAVE_FORMAT_EXTENSIBLE 校验
时间线音频导出新增封闭 `AUDIO_WAV_PCM24` 预设（48 kHz/双声道/24-bit PCM，bitexact WAV），与既有 `AUDIO_WAV_PCM16` 并存；同一多轨混音/静音/gain/审批/正式资产回读链。FFmpeg 对 24-bit WAV 输出 `WAVE_FORMAT_EXTENSIBLE`，因此原始 `media_files.inspect_media` 与时间线输出证明新增有界 PCM WAV 解析（接受 classic PCM=1 与 extensible PCM sub-format，校验 RIFF/ fmt /data 边界、通道/采样率/位宽/帧数），不再依赖 Python `wave` 对 extensible 格式的拒绝。

测试：`tests/test_studio_timeline_audio_profiles.py` PCM16/PCM24 各多轨（440Hz+880Hz muted）真实 FFmpeg/FFprobe、字节数/编码/采样率/位宽/权限审批/正式资产读回 **2 passed**；相关 media/timeline/video 回归 11 passed/1 skipped（1 error 为 main 上同样存在的旧 fixture 预存错误）。

### 能力补充：Graph 三级媒体链与第三级 UNKNOWN 栅栏
新增 `tests/test_graph_multinode_media_chain.py`：三级 IMAGE 图（t2i → review → i2i → review → i2i → review），验证每级下游 preview 的 source snapshot digest 等于上一级已审核正式资产 digest、下游 provider 实际收到上一级正式落盘字节、最终正式资产 digest/字节可回读；第三级 provider 在 dispatch 后失败时 job 保持 UNKNOWN、不得重复 execute、无法生成第三级/review_c 输出，取消后仍不产生；图组回归 **19 passed**。registry `graph_multi_node_recovery` 证据增加该测试，limits 增加 `multi_level_media_chain:FILE_SYNTHETIC_VERIFIED`（真实模型/PG/完整未知恢复仍 NOT_RUN/NOT_VERIFIED）。

### 能力补充：Provider cost/usage attestation（服务端适配器合同）
新增 `app/creative/provider_cost_attestation.py`：真实 provider adapter 可在进程内为**一个已完成且精确绑定的 Studio 生产 job**记录 `studio-provider-cost-attestation/1`（job_id/owner/request_digest/provider/model/currency/actual_microusd/usage/pricing_version/source/attested_at 严格校验）。记录写入 runtime sidecar，`ProductionExecutionService._view` 读取并再次校验 job 绑定后，把 `studio-job-cost/1` 从 `UNKNOWN` 提升为 `ATTESTED`（trusted/actual/usage/pricing_version）；默认无 attestation 时仍为 UNKNOWN，损坏/超限/错绑 sidecar 一律回退 UNKNOWN。无 HTTP 写路由，只有原进程内 adapter 可记录，避免客户端伪造成本。

测试 `tests/test_provider_cost_attestation.py`：3 项（可信绑定/默认 UNKNOWN、错 request/provider/负金额/非法 source 拒绝且无 sidecar、损坏/超限/孤儿 sidecar 不冒充可信成本）；production/cost 组回归 **80 passed / 1 xfailed**。registry `studio_task_cost` 证据/limits 更新（real provider adapter 仍未接入；真实验收 NOT_RUN）。

### 能力补充：本地 VIDEO 时间线渲染（REVIEW_MP4）
新增 `tests/test_studio_video_timeline_local_render.py`：本机 FFmpeg 生成合成 MP4（红色画面 + 440Hz 音频）作为正式 video Asset，时间线 schema 2 单 VIDEO 轨（含 include_audio）经原 `timeline_save`/`timeline_export_preview`/`timeline_export` 渲染为 `REVIEW_MP4` 候选；FFprobe 校验 `mpeg4` 320x180、AAC 48kHz stereo、时长约 1s、哈希/正式资产字节一致、人工 review 后 APPROVED。**1 passed**，相关 media/timeline/video 组回归通过。registry `timeline_render_export` 证据增加该测试，limits 增加 `video_track_local_render:FILE_FFMPEG_VERIFIED`（真实模型视频/真实 NLE 仍 NOT_RUN）。

### 能力补充：Provider usage-only attestation（价格未知）
新增 `studio-provider-usage-attestation/1`：provider adapter 可只上报可信 usage（images/gpu_ms 等计数），不声明价格。job view 的 `studio-job-cost/1` 变为 `USAGE_ATTESTED`：`trusted=true`、usage/attested_at 可见、`actual_microusd/currency/pricing_version` 仍为 null、`decision_required=true`；若后续记录价格 attestation，则升级为 `ATTESTED` 并覆盖 usage-only 记录。错 job/request/provider/model、空 usage、负值等 fail closed；损坏/超限 sidecar 不升级。测试新增 2 项（usage-only 读取与价格升级、错绑/空 usage 拒绝）；cost attestation 文件 **5 passed**。

### 能力补充：容量写入覆盖矩阵（machine-readable）
`studio-runtime-capabilities/1` 的 `project_capacity.write_entries` 新增逐入口覆盖状态：asset create（全部调用方）/手工导入/音频历史写入的 admission 状态随 flag 变化；项目 scope 文档、导出输出标记 `NOT_CONNECTED`；临时媒体、共享查询索引标记 `NOT_ACCOUNTED`；调额标记 `MANAGEMENT_ONLY`。runtime capability 测试扩展为默认/flag 开两组断言，18 passed；registry 容量 limits 增加 `write_coverage:ADMISSION_GUARDED_ASSET_CREATE_ONLY`。

### 能力补充：项目 scope 文档容量归属（MEASURED_ONLY）
新增 `project_capacity_scope_docs.py`：对 `experimental_v1/*.json` 做有界、只读 `novel_id` 归属计量，接入 capacity diagnostics/reconcile/admission 基线；其他项目、损坏、超限（>8 MiB）或超时分别计数，超限/超时计 UNKNOWN 并阻塞新 reservation。容量写入覆盖矩阵将 `project_scope_document` 从 `NOT_CONNECTED` 提升为 `MEASURED_ONLY`（写入仍未接 admission）。测试 4 项；容量组回归 94 passed。

