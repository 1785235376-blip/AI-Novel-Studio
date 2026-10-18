# 距离完整 V2 还差多少：有界功能差距复核

复核时间：2026-10-18 17:07 UTC。源码：`eb1a52577bc9aa3e33933f782312fa8b29c5f92e`。本文件仅为只读代码/文档审计的交付物；本次未运行测试、修改产品源码、提交或推送。

## 结论

仍处于实质功能补齐阶段，尚未进入“只剩最终验收”的阶段。按下面明确划分的功能闭环，已核实至少 **13 组**开发/扩展缺口。这个数字是当前查实的下限，不是全部需求的总数，不代表等量工作，也不意味着 13 次提交即可完成。没有建立完整、加权、逐项功能验收的分母，因此不能据此给出全产品完成百分比或可靠完工日期。

依据为原 904 行 Master Roadmap（SHA256 `c4a8892d1c4a3b1398cc5a5496610294be31bf9c245d59be10f8f570991f7b74`）及 `frozen-product-anchor-20261016.txt` 的追加要求。源文件恢复与优先级见 [恢复核对](MASTER_ROADMAP_SOURCE_RECONCILIATION_20261018.md)。原文已读完，不再是缺失证据。

## 本轮已经补上的内容

- 有序多章节语义改编已经落地：最多 16 个来源、每个完整已保存章节最多 8,000 字符、总计最多 32,000 字符，保留顺序、逐章节版本/摘要/隐私和场次归属。不能再列为“多章节完全没有”。见 `app/creative/adaptation_models.py:24-43`、`adaptation_sources.py` 及 [改编合同](source-aware-adaptation.md)。
- Graph/Timeline 直接素材引用查询已经落地；只覆盖已保存图中的直接 asset_reference 和时间线片段引用，不等于递归后代或全局影响图。见 [直接引用说明](studio-direct-asset-usages-20261018.md) 与 `app/creative/asset_usages.py`。
- 此前独立音频时间线/WAV 混音、人工相机几何、基础视频调色、字幕样式、分层规划本地模型桥、Canon 精确来源标记均已有实现，不再列为整个功能缺失。具体边界见 [当前差距及后续更正](CURRENT_DEVELOPMENT_GAPS_20261018.md)、[规划/Canon/字幕报告](../delivery/v2-development/planning-canon-caption-wave-20261018.md)。
- 整合方确认当前波次原始收据：改编 PostgreSQL 190、直接引用 PostgreSQL 18、UI 193、TypeScript/Vite 与 PUBLIC/catalog 6。归档 `f7739d58bb68186117887172060ec1b17f75a14d` 已读回核验。这些是有边界的通过证据，不是功能完成率。

## 已查实的 13 组剩余开发闭环

“缺实现”指表内特定子功能缺少实现；“范围受限”指原功能存在但没有覆盖完整目标。两者均不是整模块从零开始。

| # | 剩余闭环与性质 | 已有基础及差距证据 |
|---|---|---|
| 1 | 专业画布的可复用执行子图、跨项目媒体精确重绑定：缺特定实现 | 显示分组、模板和同项目复制已经存在。执行节点注册表 `app/creative/graph_models.py:463-508` 无子图执行类型；`frontend/src/creative/graphProjectTemplates.ts:11-35` 明确限制当前项目/实例/身份/分支。参见 `docs/GRAPH_PROJECT_REFERENCE_TEMPLATES.md`。对应原 §7、冻结 P1-A。 |
| 2 | 导演直接分析图片/视频/3D，以及受众/平台/预算意图、声音/后期建议交接：范围受限 | 剧本/分镜语义导演、多个控制台、子导演草稿和人工几何已有。`app/creative/director_binding.py:41,68-69` 与 `director_transport_contract.py:53-118` 的源仅为 STORYBOARD/SCREENPLAY；`director_intent.py:52-76` 投影现有视觉字段，`graph_models.py:496-507` 的导演交接未覆盖完整音频/后期建议。对应原 §8、§11、冻结 P1-B/C。 |
| 3 | 图片扩图 Outpaint、可执行 LoRA/控制参数：缺特定实现 | T2I/I2I/参考/Inpaint/超分/抠图已有。`app/creative/production_execution_models.py:11-20,181-198` 是闭合操作/参数集；`app/services/studio_image_provider_recipes.py:13-26` 是闭合 Comfy 配方，不能靠填提示词代替 LoRA/控制执行。对应原 §10。 |
| 4 | 分镜图像缩略图及图文对比的完整 Shot Board：范围受限 | 镜头稳定 ID、字段、排序、CSV 和 Image/Video 交接已有。当前 `frontend/src/storyboard/ShotCard.tsx:19-57` 显示文本/徽标，未显示真实图片缩略图或图像比较。对应原 §12.2；这不否定现有文字镜头卡。 |
| 5 | 参考视频选段、关键帧选择/采样与时序条件预处理：缺特定实现 | 视频生成及 V2V 合同已有。`app/creative/production_execution_models.py:112-121,189-198,248-253` 的参考只含整段 source/purpose，视频参数无参考入出点/关键帧；音频 trim 字段不能算视频参考选段。对应原 §13.3。 |
| 6 | 从真实 3D 源提取/导出相机及最小 Blender/UE 交换：缺特定实现 | GLB 静态几何、材质检查和真实 CPU 白模/深度图已有。`app/creative/model_reference_scene.py:95-125` 只输出 mesh 几何；`model_reference_depth.py:1-3,82-83` 明确是诊断正交投影。人工 Director 相机几何并未替代 3D 源相机抽取。对应原 §16；不要求完整 DCC 或高级实时同步。 |
| 7 | Model Center 受控下载、暂停/恢复、完整性校验及失败清理：缺特定实现 | 发现、注册、复用、诊断已有。`frontend/src/modelcenter/ModelCenterPanel.tsx:121-124` 明确禁用下载/修复，原因是原 owner 无端点。对应原 §6.3、M3。不能把缺 GPU 视为这个代码缺口的原因。 |
| 8 | A07 视频基准执行和吞吐/显存/冷热启动测量：范围受限 | 文本/图片执行、证据和偏好已有。`app/experimental/model_benchmark.py:210-211` 拒绝 VIDEO_WORKFLOW；`:385-391` 仅给延迟等指标，吞吐/显存为空、冷热启动 NOT_MEASURED。测量实现与日后真机数值验收是两件事。 |
| 9 | 跨媒体制作清单/恢复、统一任务精确打开及安全批量执行接齐：范围受限 | 原制作回执/恢复已有，Studio 图片/视频任务已接入。`app/experimental/production_lineage.py:368-369` 将清单/重放限定为旧图片链；`frontend/src/taskcenter/studioProductionTask.ts:4-17` 仅 image/video；`app/experimental/safe_batches.py:33-55` 操作枚举未涵盖新 Studio Video/Graph/Timeline。新增直接素材引用不等于这三条执行/恢复链完成。对应 A13/U07/U16。 |
| 10 | 一般存储目录迁移、核验/中断恢复和可配置缓存配额管理：缺特定实现 | 真实磁盘准入、配额事实、便携导出缓存清理已有。`frontend/src/modelcenter/StoragePanel.tsx:22-25,57-94` 明示只读、无迁移清理；`ModelCenterPanel.tsx:123-124` 也禁用一般清理。原便携缓存清理不能代替一般目录迁移。对应原 §5、U14。 |
| 11 | 可在隔离环境恢复资产关系、Graph 与 Timeline 的整 Creative 工程包：缺特定实现 | 选定章节/引用媒体便携包与原离线备份已有。`app/experimental/portable_projects.py:43-44,94-100` 明确限制为当前章节和引用媒体，不复制工作流；`:438-464` 恢复章节/媒体。不能将原备份或文本图模板称为该整工程交付闭环。对应原 §19 完成标准、CORE_EXPORT。 |
| 12 | 普通正文 Canon 语义事实提取/重提取、模型语义导入及真实视觉一致性检查：范围受限 | Canon 精确版本来源和显式标记候选、真实导入解析/审查、视觉记忆与审核回执已有。`app/canon_extraction.py:1-13,47-50` 明确仅标记、semantic_extraction NOT_PERFORMED；`app/experimental/imports.py:3,60-93` 为本地启发式；`visual_identity.py:65` 和 `review_adapter_jobs.py:131,179` 的执行仍受 MOCK_ONLY 限制。这组含多个独立闭环，不是一个小补丁。 |
| 13 | B10 从本地选定章节交换扩展到更完整的资产/分支离线项目范围：范围受限 | 手动 JSON 文件交换、去重、三方冲突、CAS、墓碑和恢复已有。`app/experimental/offline_sync.py:28-33,60` 明确本地项目、最多20章、无资产/分支；`offline_sync_production.py:208-221` 仍将分支与生产传输标未配置。冻结跨端项目/B10需求仍需覆盖；原 §18/M10 延后生产云同步，所以不能把部署云服务或购买托管算作当前必须执行。 |

## 不混进上述开发数量的证据空白

- **PRIVATE Mature：** PUBLIC 灰色入口与专属后端物理隔离已有实现/打包证据。公开源码不能证明独立私有 Mature 运行时完成，也不能证明不可见私有分支没有实现。其专项实现和对应验收需独立证据。
- **其余完整矩阵：** A/B/U/FS/CORE 的逐条当前功能验收尚未形成完整分母。U04 多窗口等尚无完整实现证据；本次不靠全文搜索无命中就新增“已证实缺失”计数。B07 typed Godot 数据适配不自动等于可玩游戏，但也不能未经原需求核定就新增完整游戏产品阻断项。
- **容量限制：** 显示画布 1000 对象、执行 DAG 16/24 节点、有界来源等都是明确范围。不能一律视为漏洞或靠删预算完成要求；是否达标须分别对照需求和实测。

## 独立的最终验收层

1. 当前最终源码的真实浏览器交互、画布性能、中文输入/无障碍、多分辨率，以及五条自由入口和跨模块端到端；2V/2A/字幕实编、预览、输出、重开必须作为产品旅程核验。旧 CPU 媒体结果和旧 SHA 浏览器结果保留其证据价值，不升格为当前全产品通过。
2. 用户以后明确开启的 Windows 安装/启动/升级、真实 GPU/本地模型质量及目标资源档位；青简双客户端联调需对应客户端和授权。它们不是“云端再补几个测试”即可代替。
3. 当前候选包的各实际分发形态及 PUBLIC/PRIVATE 专项核验、完整回归和精确源码/包身份。PUBLIC wheel 通过不自动等于 Windows/Docker/installer/zip/sdist 全部通过；正式发布另需批准。

原附录明确延后的完整 DCC、自动绑定、Resolve 级调色、实时高级音频/声音克隆、生产云与实时协作，不凭名称缺席就另加成当前必做整套产品。

## 17:31 增量更正

产品源码 033a4f6a 已补第5组中的低分辨率真实采样参考帧闭环：正式 Video → 明确采样时间窗 → 实际解码帧/PTS → 人工确认 → 原 Asset owner 首次提交来源齐全的 Image → 原 I2V 交接。显示和保存均为最长边320px的相同PNG；不是高分辨率提帧、语义关键帧、动作/姿态/深度分析，也没有把选段偷偷应用到 V2V。故第5组从该子能力缺失变为部分补齐，不将整组划掉或直接把13改为12。已核验归档：50b4e54afc67694f3e7900efedc36145cc33c1de。详见 ../delivery/v2-development/video-reference-isolated-summary-20261018.md。

## 17:41 增量更正

产品 be9a7231 已补第7组的受控单文件传输机制及原 Model Center 入口：明确预览/确认、暂停/恢复/取消、完整性核验及仅本操作临时文件清理。此切片只具备受测 POSIX 机制，生产可信来源和目标目录仍为空，无配置加载/供应入口，Windows 明确拒绝执行。当前模型目录没有新增可下载项，因此第7组/M3仍未关闭。不得继续说“任何传输端点都没有”，也不能说“模型下载已经可用”。详见 ../model_center_controlled_transfers.md。
