# Studio V2 后端主线需求账本（M0 初版）

日期：2026-10-28。对照源码 `395ac26dd2de3d473e56964dbeb9ac9806facb85`，tree `3e1457d440f9c28543405fb4ba7d683dfba22385`。本账本是逐项工作清单，不是完整性或发布证明。此轮 M0 只读定位源码及已有报告，未执行任何测试。以下“已有报告”均指原报告指定的源码和环境，不自动升级为本轮验收；实现状态来自定位，不等于所有行为已验证。

## 口径与来源

- **源码存在**：定位到相关 owner 或入口；具体子能力仍需行为验证。**未整合**：来源明确但尚未证明进入本基线。**未实现/明确不支持**：有报告或代码明确记录；未定位时写 **待核实**，不猜成未实现。
- **既有证据**与**本轮验收**分列。环境为历史报告所述环境，不能外推到 PostgreSQL、真实模型、其他操作系统或本次 HEAD。这里的 owner 指现有代码职责归属，不推断人员。
- 主要权威输入：`studio-v2-unified-integration-20261027/DELIVERY.md`、`LIMITS.md`、`SOURCE_FREEZE.json`；较早的 `STUDIO_BACKEND_INTEGRATION_20261026.md`、`HERMIA_AUDIO_HISTORY_REVIEW_20261025.md`；旧需求库存 `HERMIA_CAPABILITY_LEDGER_20261022.md`。后者是静态 PARTIAL 清单，不能由源码数量推导完成度。相冲突时先核对源码与固定证据，不以旧报告覆盖新报告。
- 接口路径省略可由应用挂载的 API 前缀；双入口是否成立以对应固定源码实测为准。

## 能力与验收清单

| ID / 需要验收的能力 | 现有 owner / 入口 | 本基线源码及整合状态 | 既有证据与环境 | 本轮缺口 / 验收状态 |
|---|---|---|---|---|
| N1 小说、章节与版本；世界观、角色引用 | `app/services/novel_service.py`、`app/repositories/{file,postgres}/novel.py`；`app/creative/bible_api.py` | 源码存在；各实体跨后端版本关系待逐项核对 | `tests/test_phase4_world_summary.py` 等测试文件存在；未在本轮运行 | **NOT_RUN**：File/PG 创建、修改、重开、旧版本和并发冲突；核实章节到世界观/角色的精确引用合同 |
| N2 剧本、分镜、镜头及来源 pin | `app/creative/storyboard.py`、`storyboard_model.py`，Creative documents/shot 接口 | 源码存在；分镜内容 digest、镜头版本和视频/音频命令验证有明确入口 | `tests/test_phase8_storyboard.py`；旧 `STUDIO_BACKEND_INTEGRATION_20261026.md` 报告 File/HTTP/Mock 图像链 | **NOT_RUN**：剧本到镜头版本、历史与失效传播，以及跨项目/过期版本反例 |
| I1 IMAGE 单任务、候选、审核、回填与重开 | `app/creative/production_execution_api.py`、`canvas_image_node.py`，原 Image/Asset/Canvas owner；`/projects/{nid}/studio/production/{preview,jobs}` 和 job execute/candidate/review | 已整合单节点链；必须保留首次 source-read 准入和提交窗口 Approved Asset pin 复验 | `studio-v2-unified-integration-20261027/DELIVERY.md`：固定 `5eec654b`，Windows、File、真实 HTTP/Chromium、合成项目和 A1111 Mock；含响应丢失、重开、后端重启；不是实际模型验收 | **NOT_RUN**：本轮同源码独立复验、真实模型与 PG。原 Canvas 画布草稿和正式任务的边界仍需保留 |
| V1 VIDEO 原任务闭环 | `app/services/studio_video_execution.py`、`studio_video_provider.py`；`production_execution_api.py` 的 jobs/video execute/refresh/reconcile、`app/creative/storyboard.py` | 视频执行服务和路由源码存在；实际支持范围/接线需核对。统一交付明确记载 VIDEO 执行 unsupported，不可把源码存在等同产品闭环 | `DELIVERY.md`、`LIMITS.md`；`tests/test_studio_canvas_video_bridge.py` 为现有测试入口，尚未审定覆盖内容 | **未验收**：镜头/节点→校验→明确执行→真实可解析候选→审核→回填→重开；时长/帧率/尺寸、迟到回调、重复请求、授权、失败恢复和真实适配器。模型未授权时标 NOT_RUN |
| C1 创作画布与执行图连接 | `app/creative/canvas_image_node.py`、`canvas_video_task.py`、`graph_api.py` | IMAGE 正式单节点关联已整合；`LIMITS.md` 指本机上下图/连线为草稿，不能推断为完整图执行。Canvas video bridge 有源码，不代表 VIDEO 生成能力 | 固定 `5eec654b` 的 IMAGE 浏览器证据；`tests/test_studio_canvas_video_bridge.py` | **未验收**：画布保存版本到图运行、跨图/项目隔离、变更与重开；不要重做前端布局 |
| G1 图结构、端口、计划和运行 | `app/creative/graph_models.py`、`graph.py`、`graph_execution.py`、`graph_api.py`；`/projects/{nid}/studio/graphs`、`preflight`、`runs` | 源码和执行/预检接口存在；统一交付不声称完整多节点编排 | 相关源码及 `LIMITS.md`；历史报告不是本轮分支依赖验收 | **待核实/NOT_RUN**：节点目录与端口类型、环/缺输入拒绝、模板版本和执行参数隔离、分支 DAG 顺序 |
| G2 产物传递、失败与恢复 | `app/creative/graph_media_execution.py`、`graph_asset_inputs.py`、`graph_failed_retry.py`、`graph_api.py` 的 media preview/dispatch/execute/reconcile/review 与 `retry-local` | 源码存在，media review 与可用 ASSET_REF 有分离；完整多节点恢复与自动/显式边界未完成验收 | `LIMITS.md` 将完整多节点图编排列为未完成 | **NOT_RUN**：真实落盘上游产物及精确 digest 下游消费，失败传播、取消、超时、活 owner/未知外部结果恢复、局部重跑影响范围；不可把云内部步骤描述为可编辑 |
| A1 音频请求、执行、候选与采用 | `app/services/studio_audio_execution.py`、`audiobook_service.py`、`app/audio_production_store.py`；原 production jobs owner | 原音频 owner 与 Studio 适配源码存在；完整跨媒体统一合同待核对 | `tests/test_audio_production_api.py`、`tests/test_studio_canvas_audio_return.py`；测试文件存在不等于运行通过 | **NOT_RUN**：真实或合成媒体执行、审核及采用，撤权/来源变化/重启；实际 provider 需另列状态 |
| A2 音频不可变历史与显式恢复 | 原 Asset owner；历史候选来自 `HERMIA_AUDIO_HISTORY_REVIEW_20261025.md` 固定 `2acab55d`，不是整支纳入承诺 | **未整合完整恢复**；统一 `LIMITS.md` 明确恢复 PARTIAL、restore 写端关闭，兼容与项目历史容量计费 OPEN | 旧独立报告在其指定源码/环境有只读子集与失败记录：原 query/cursor 两文件 85 passed、1 failed；非本轮结果 | **未实现/未验收的恢复合同**：旧格式、项目级历史及失败 create 遗留计费、损坏/缺失、内容去重、CAS、落盘故障和重启；GET 不迁移；满足合同前保持关闭 |
| P1 跨 IMAGE/VIDEO/音频/图候选与来源 | 原 Production、Asset、Storyboard/Canvas 和 Graph owner；`production_execution_api.py` candidate/review/reconcile | 共有路由及原 owner 源码存在；跨媒体统一程度和跨 owner 原子边界待核实 | 固定 IMAGE 链有 Mock 候选、审核、采用及来源证据；不覆盖其他模态 | **NOT_RUN**：伪造摘要、跨项目、撤权、过期目标、并发采用、丢响应、幂等补偿和审核/模型/输入版本完整追溯 |
| T1 时间线、多轨、音量与编辑 | `app/services/studio_timeline_schema.py`、`studio_timeline_edit.py`、`studio_timeline_links.py`；production timelines API | 源码及编辑/历史/restore 入口存在；不能据此认为所有格式/轨道组合均支持 | `tests/test_phase4_timeline.py`、`tests/test_studio_canvas_video_audio.py` 为待核测试入口 | **NOT_RUN**：镜头采用到精确 timeline/source 版本、范围、轨道静音/增益、并发、失效、重开及历史恢复 |
| T2 渲染、混音、媒体导出 | `studio_timeline_render.py`、`studio_timeline_export.py`；production timeline render/export-preview/export | 源码和接口存在；具体编解码支持与限制待核对 | 统一交付未声明整体 VIDEO/时间线发布验收；GraphFlow 定位到固定 WAV profile 的前端合同，不等于后端已验证 | **NOT_RUN**：ffprobe/解码核对合成视频/音轨、时长/采样率/帧率及完整性；缺素材、源变更、取消、中断、写失败、重开分项验收 |
| E1 文本及文档导出、同机执行所有权 | `app/services/export_job_service.py`、`export_snapshot_authority.py`、`app/export_formats.py`、`app/pdf_export.py` | 导出 owner 源码存在；`efd083c2` 同机所有权修复是否已进入基线待以精确差异核对 | `tests/test_export_jobs.py`、`tests/test_docx_export.py`、`tests/test_pdf_export.py`；本轮均未运行 | **NOT_RUN**：活 owner、死亡恢复、取消/异常及并行任务；TXT/Markdown/JSON 恢复证据从 `f332dc9b` 精确核实；DOCX/PDF 各自检查内容，不以状态或一种格式代替其他格式 |
| Q1 TaskCenter、本地单来源及混合查询 | `app/experimental/taskcenter_query.py`、`taskcenter_cursor.py`、`taskcenter_local_mixed_cursor.py` 等 | 原查询/游标源码存在；最终统一报告称 local `semantic_import+exports` 有界支持，协作 exports/混合、任意组合及 PG/packaged 混合继续拒绝 | `DELIVERY.md` 和 `LIMITS.md`：固定 File 合成环境；原窗口分别 200/100，非无限查询 | **NOT_RUN**：`6787f85e` 真实读取回执及 `6b0db8e` 最终有效期复验的精确并入；首/续/末/空页在最终复验时过期的反例、拒绝不伪装空页、旧非分页语义 |
| Q2 资产预算隔离与严格读取 | `app/creative/asset_usage_request.py`、`asset_usage_read_mode.py`、`asset_usage_budget.py`；`app/services/asset_query_budget.py` | 相关 owner 源码存在；`6bced268` 精确增量是否已整合待核查 | `tests/test_studio_asset_usage_budget_guards.py` 等为测试入口；统一报告有 File 保护证据 | **NOT_RUN**：严格 GET→普通 GET/POST、嵌套、异常、取消及并发恢复；TaskCenter 默认不归入该预算合同 |
| Q3 三类资产分页诊断 | `app/creative/asset_query_cursor.py`、`asset_query_service.py`；原诊断来源 `048fe2a` | Windows cursor 503 和历史 F 37 拒绝根因均由统一 LIMITS 记录 OPEN；Hermia strict warm 首屏间歇 409 原因待核实 | `studio-v2-unified-integration-20261027/LIMITS.md`；`tests/test_studio_asset_query_cursor.py` | **UNKNOWN**：分别复现原条件并记录脱敏拒绝层、异常链、读取量、耗时、权限及来源变化；不提高预算或减少复验来掩盖 |
| S1 身份、scope、实例、授权与协作 | `app/services/authorization_service.py`、`membership_authorization_service.py`、`collaboration_scope_service.py`、`app/creative/project_store.py`；File/PG scope repositories | 既有 authority owner 存在；保留各自事务、生命周期、锁与 CAS | 统一交付报告原 owner/lifecycle、真实 HTTP 反例及指定 IMAGE 提交窗口保护；PG 未运行 | **NOT_RUN**：新工作针对成员撤权、同 ID 重建、source 在提交窗口变化、并发、两个 API 前缀及独立反例；不可绕过最终复验 |
| S2 存储、进程恢复与发布边界 | `app/repositories/file`、`app/repositories/postgres`、`app/creative/project_store.py` | File/PG 实现目录存在；本轮可用性及支持矩阵待核验 | 固定 `5eec654b` File 证据；统一报告 PG、其他 OS NOT_RUN | **NOT_RUN**：同固定源码的 File/PG、Windows/POSIX、进程/异常恢复；同机锁不宣称分布式 exactly-once |
| K1 机器可读能力、schema、错误码和迁移 | `app/creative/production_contracts.py`、`production_contract_api.py`、`graph_api.py` 的 catalog/model-capabilities/provider-contracts；`app/model_provider_contracts.py` | 部分能力入口存在；是否完整覆盖存储、模型、后端和受限操作待核实 | 相关源码、旧 capability ledger；无完整统一能力清单的本轮验收 | **NOT_RUN**：逐能力 supported/limited/unsupported、稳定错误码、请求/产物/审核/恢复样例与 V1.X 兼容；破坏性变更须另议 |

## 公开成果逐项整合队列

以下提交在任务输入中给出，**不能只因文件名或祖先关系相似就认定等价**；对每项核对实际差异、owner 与原测试，缺失时只接入精确增量。

| 原提交 | 目标 | 当前状态 |
|---|---|---|
| `6bced268539cee6938f346a27f945a9a290ee4f6` | 请求预算与严格只读上下文隔离 | 等价性待核对 |
| `6b0db8e6e5b003df72c9c6e0aa91ce6b60a4deeb` | TaskCenter 返回前有效期复验 | 等价性待核对 |
| `6787f85e9f4a2da4f5e7eefa89cf802083db0338` | 本地单来源实际读取成功回执，含上一项 | 等价性待核对，不重复整支覆盖 |
| `efd083c2b25a63a2aad3c0fc5415314d9dbc7ca3` | Export 同机执行所有权与恢复 | 等价性待核对 |
| `048fe2a12212df85c272cdc0741659498378d334` | 默认关闭的分页拒绝诊断 | 等价性待核对 |
| `f332dc9b6ae5942affc5cb08630cea8bf58ff255` | 原生 TXT/Markdown/JSON 产物恢复验收 | 测试/证据是否已并入待核对 |

未公开的协作 reader、共存整合和二进制恢复测试包均不假定存在。

## 冲突、范围和发布门禁

- 旧 `HERMIA_CAPABILITY_LEDGER_20261022.md` 含 99 项静态库存、实验能力及无法判定项，不将这些自动扩展成本轮冻结产品承诺；需由产品/owner 确认的超范围能力单列，不以测试数量计完成百分比。
- 保留原 IMAGE source-read 与 Approved Asset pin 两项修复；不整支覆盖旧 Canvas 或音频分支，不触碰前端布局/交互或未经 owner 核查的共享 SDK。
- 最终统一冻结须在同一固定源码独立复验 IMAGE、VIDEO、DAG、音频历史、TaskCenter/预算/导出、实际产物及权限/并发反例。Windows、POSIX、File、PG、浏览器、真实模型与 CI 分别记录；当前本轮均 **NOT_RUN**。
- 统一交付报告明确 main **NOT_READY**。本账本本身不授权部署、合并或公开上传。新功能包公开上传前需列明目标分支、代码、测试与脱敏合成证据并取得明确批准。

## 2026-10-28 本地切片进展（非最终冻结）

- 已在独立工作树依次提交请求上下文隔离 `a5afa95`、默认关闭的分页诊断 `e20d4af`、导出同机所有权 `777e231`、TXT/Markdown/JSON 恢复产物测试 `6cd9483`、TaskCenter 返回前期限及单来源实际读取回执 `47eace6`。各项来自指定公开提交的对应增量；原 IMAGE 两处修复未覆盖。
- 请求隔离独立对照：同一测试在 `395ac26` 为 18 failed / 2 passed，精确 `a5afa95` 为 20 passed。此证据只覆盖该切片。TaskCenter 新增定向测试 174 passed；旧混合及协作回归仍待确认。
- 导出 Windows 定向组 UTF-8 模式为 106 passed、9 skipped、3 deselected。符号链接测试因 WinError 1314 排除，POSIX SIGKILL 等场景未验收；同机锁不表示分布式 exactly-once。默认 GBK 下测试读取 UTF-8 文件的失败保留在本地证据。
- 资产列表原反例在 Windows、隔离 File/Mock 环境再次返回 503。`load_signing_key` 先检查目录相对 no-follow 安全原语；本环境 `os.open`/`os.stat` 不支持 `dir_fd`，且无 `O_NOFOLLOW` 和 `O_DIRECTORY`，因此该守卫必然拒绝。此为此次复现的直接拒绝层；尚无符合原私密密钥及防替换合同的 Windows 实现，保持 OPEN，不降级到普通路径。历史 F 37 与 Hermia strict warm 409 尚未复现，仍为 UNKNOWN，不能据此合并结论。
- 这些是开发切片结果，尚未在统一最终源码完成独立验收；真实模型、PostgreSQL、POSIX、完整浏览器及托管 CI 依然 NOT_RUN。

## 后续开发与验收记录（截至本地冻结前）

以下结果均是指定固定切片的限定环境证据，彼此有重叠，不相加当覆盖率；上文能力表对 `395ac26` 的描述保持历史口径。

- **Q1/Q2/E1 已整合、部分验收**：`47eace6` 加入 TaskCenter 末次期限复验及单来源实际读取回执，同一测试在其父版本为 115 failed / 59 passed、在该切片为 174 passed。`ed3a179` 修复导出 claim 异常后的显式幂等重试，另有独立审查发现并通过测试修复关闭线程池、任务已终态的竞态；争用时返回 queued 不保证已派发，持有者随后异常需再次重试或重启恢复。同机锁不代表分布式 exactly-once。
- **Q3 分别保留状态**：Windows 列表 503 在隔离环境复现，直接拒绝层是缺少签名密钥安全文件原语，未实现 Windows 等价安全后端；F 的 37 个历史拒绝在固定 F 的本轮尝试中未复现，UNKNOWN；strict warm 首屏 409 的原合成场景本轮带诊断通过，但运行过程中源码树发生其他开发变更，属于探索性结果，不覆盖原失败，根因 UNKNOWN。
- **V1 部分实证**：固定源码中的合成 provider 经两个真实 mounted API 入口完成预检、明确执行、实际 MP4 解码、候选审核和分镜回填；迟到结果在取消后被拒且不重发。它们不是实际模型、浏览器或真实进程重启验收。共享 SDK 对 VIDEO 非空 media_measurement 的解码兼容问题需要原 owner 协调；原 phase1 视频测试 4 项失败也在固定 `395ac26` 独立复现，不能计通过。
- **G1/G2 部分实证**：本地分支图执行、人工审核和 File owner 重建读回；另外两级 IMAGE 分支在审核后由下游读取上游真实落盘字节，逐项核对版本和摘要。下游响应丢失保留 UNKNOWN，明确读取和取消不自动重发。测试 provider 为确定性替身，媒体图局部重跑及真实进程恢复未验收。
- **A2 未整合**：旧音频头已从公开投影移除；只读无隐式迁移的 File owner 反例通过。隔离复现表明旧历史头经当前普通元数据更新后无法继续读取；现有项目计费不覆盖历史、prepared、不可归属失败残留。旧历史读取与恢复保持关闭。需要兼容性方案：绑定 project scope/incarnation 的持久预约、不可变版本、全部原写入口接线及故障恢复；不得以统一拒绝旧写入替代兼容。
- **T1/T2 部分实证**：File 双轨合成 PCM 通过原时间线/FFmpeg 导出，独立检查 1 秒、48 kHz、双声道及频率幅度，验证静音和约 -6.02 dB，审核后原资产读回。另验证缺失输入不产候选、不自动重播；取消和探测输出写失败会回收子进程。候选写盘失败、完整多轨恢复与其他格式未由此证明。
- **K1 部分实现**：新增独立 `GET /api[/v1]/projects/{nid}/studio/production-contracts/runtime`，通过原读权限、项目 scope/incarnation 与返回前 guard，声明游标签名原语 PRESENT/UNAVAILABLE 与端到端 NOT_VERIFIED/UNSUPPORTED、音频资产版本历史读/恢复 UNAVAILABLE、模型验收 NOT_EVALUATED。它不是覆盖所有存储、模型和操作的完整能力清单；原 ProductionCatalog schema 不变。两入口已测功能关闭、跨项目、项目重建及最终撤权反例。
- **环境**：Windows/File 与本机 FFmpeg 的限定合成测试有证据；POSIX、PostgreSQL、真实模型和最终浏览器链未运行。Windows 符号链接权限受限的三个测试未通过；默认 GBK 解码失败保留，显式 UTF-8 重跑不抹除原结果。GitHub Actions 无本轮实际运行证据，CI NOT_RUN。
