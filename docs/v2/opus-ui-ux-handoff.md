# Studio V2：前端 UI / UX 重构交接

按用户授权继续实际后端工程和基础前端：独立媒体／有界多轨之后，从 `4a4a9df1e59217f249a4e1f90c863729aefc1ea8` 接入显式 Graph schema 3 媒体与原子资产输入。测试、构建与真实全流程验收暂缓。这些新增源码尚未经过执行验证，不能据此认定 M4 或后续里程碑通过。M4 保持 PARTIAL，M5–M9 保持 LOCAL_REQUIRED；QingJian 暂停推进。

## 先读的文件

1. `AGENTS.md`、`.codex/skills/ai-novel-studio-ui/SKILL.md`。
2. `docs/ui/design_system.md`、`docs/ui/protected_ui_surfaces.md` 与对应 canonical reference。
3. `AI_NOVEL_STUDIO_V2_ARCHITECTURE.md` 中的原 owner 关系、三类图、存储和迁移边界。
4. `docs/v2/production-operation-contracts.md`、`docs/v2/production-execution.md`、`docs/v2/studio-workspace-operations.md`。
5. `docs/v2/ai-execution.md`、`text-execution-receipts.md`、`text-result-assets.md`。

当前仓库的里程碑历史与报告是可核对依据；未找到的原始附件不能补写或猜测。

## 可以直接接手的代码边界

| 目的 | 实际文件 | 操作边界 |
|---|---|---|
| 工作区入口与权限围栏 | `frontend/src/creative/IndependentStudioWorkspace.tsx` | 现有 AppShell 内容消费；未保存导航保护、身份/分支切换与晚到响应隔离 |
| 制作阶段视图 | `StudioWorkspaceOperationPanel.tsx` | 仅显示与导航，M4–M9 切换不执行任务 |
| 制作阶段控制器 | `useStudioWorkspaceOperations.ts` | 单一只读 GET；loading/error/denied/unavailable/empty 分开，撤权清空私有投影 |
| 契约类型、校验与客户端 | `studioWorkspaceOperationTypes.ts`、`studioWorkspaceOperationContract.ts`、`studioWorkspaceOperationClient.ts` | 不把 API 描述转换成自动执行表单，不把 advisory metadata 当权限或实时模型能力 |
| 图编辑逻辑与视图 | `useStudioGraphEditorController.ts`、`useStudioGraphEditor.tsx` | 控制器保留草稿、撤销、CAS、资产绑定保护；视图沿用原消费者接口 |
| 运行控制器与视图 | `useStudioGraphRunController.ts`、`studioGraphRunView.tsx`、`GraphRunPanel.tsx` | facade 保留每图/版本生命周期；控制器内校验状态、人工审核、互斥操作与不确定回执，不以 JSX 的 disabled 作为唯一门禁 |
| 模型操作控制器与视图 | `useStudioGraphModelExecutionController.ts`、`studioGraphModelExecutionView.tsx`、`GraphModelExecutionPanel.tsx` | 原 WorkflowRun / JobManager / Router 持有任务；本地确认绑定运行版本、预览摘要、原路由和测试适配器选择 |
| 独立媒体视图与控制器 | `StudioMediaExecutionPanel.tsx`、`useStudioMediaExecution.ts` | 9 项闭合 MediaCommand；预览确认、仅入队、明确执行、原回执核对、私有候选摘要／Blob 校验和人工审核分别操作 |
| 多轨视图、控制器与类型 | `StudioTimelineEditor.tsx`、`useStudioTimelineEditor.ts`、`studioTimelineTypes.ts` | base/draft/server candidate、轨道／片段／手工字幕、CAS 保存、准确时间线版本／摘要确认后显式渲染，不把网络取消等同停止 FFmpeg |
| 交互播放视图、控制器与类型 | `StudioTimelinePlaybackPanel.tsx`、`useStudioTimelinePlayback.ts`、`studioTimelinePlaybackTypes.ts` | 明确方案／同意／一次原渲染、原 candidate attestation、实际 Blob SHA、原任务读取／取消、有限 LRU 与同步撤权隐藏；视图不持有授权 |
| 固定 Whisper 生命周期消费 | `frontend/src/ui/ModelCenter.tsx` | 原 Host context start／stop，服务器固定配置只读，实际私有模型加载证明与质量未验收分别展示 |
| 实际媒体／时间线客户端 | `studioProductionClient.ts` | 原捕获 Host transport；严格 project/branch、公有 job/recipe/source 投影、命名动作与原版本／request/output digest |
| 生成资产声明表单 | `StudioAssetDeclarationForm.tsx` | 有 source_task_id 时仅编辑 license／operation；origin、原父资产／文档快照只读，保持原 parent_asset_ids，chapter_ids=[]；手工资产仍用原共享表单 |
| 偏好控制器与表单 | `useStudioWorkspacePreferences.ts`、`StudioWorkspacePreferencesForm.tsx`、`studioWorkspacePreferences.ts` | 原 expected_version 保存；冲突或回执不确定时先读取，再人工采用服务端值或保留输入，不自动覆盖/重试 |
| 恢复定位 | `studioWorkspaceResume.ts` | 本地作者仅记项目/模块/子视图/阶段/图与运行 ID；服务端重读后才采用 |
| Model Center 来源说明 | `frontend/src/ui/LocalAiDiscovery.tsx` | 未确认、本地来源与已确认远程来源分开；显示文字不改变后端接入门禁 |
| 后端制作契约 | `app/creative/production_contracts.py`、`production_contract_api.py`、`workspace_api.py` | `/api/projects/{nid}/studio/production-contracts` 复用原 scope、incarnation、flag、授权围栏；没有新调度器或执行入口 |
| 后端实际制作入口 | `app/creative/production_execution.py`、`production_execution_models.py`、`production_execution_api.py` | 与 advisory catalog 分离；原 ImageJobService／AudiobookService／VideoAssemblyService 持有真实任务，Host／原执行与云端／来源策略负责授权 |

前端表中未加目录前缀的文件均在 `frontend/src/creative/`。可以替换模块内容 JSX 与其 token 样式，保留控制器、严格类型和原动作调用。不要用视觉重构改变后端 owner、请求参数或状态含义。

本轮继续把动作可用条件落实到控制器中。重构时调用 snapshot 中的命名动作，不另行调用底层 client 来规避校验。运行选择/预检 GET 与运行动作在当前面板互斥；明确创建重试捕获原 request ID，并核对同一图版本、预检摘要和目标。审核勾选绑定 run version、node ID 与 output digest，切换运行或晚到响应不能延续旧勾选。

模型调用确认绑定当前 run version、preview digest、route/provider/model/synthetic 与人工 synthetic 选择。路由变化、权限/dirty/locked 变化会使确认失效；UNKNOWN 没有自动派发或重放。提供方匹配仍是只读建议，不加入执行授权。关闭传输请求只阻止旧响应采用，不表示后台任务已取消；取消仍走原 owner 动作。

偏好编辑拥有独立 base/draft。overview 的晚到读取不能覆盖输入；保存回执需符合提交内容与原递增版本。409 与传输/5xx/非法成功响应分别记录为冲突或结果不确定，后续 PUT 在人工核对前阻止。服务端值相同只证明当前读取值，不冒充原请求回执。UI 可重排核对区，须保留“采用服务端偏好”和“保留输入并基于此版本编辑”的显式选择。

图节点的资产预览核对绑定 version、digest 与 kind；当前资产已变化时不把新版本显示为原绑定。图读取时的引用状态与再次核对的当前状态分开，核对不改绑定。确认导航、采用服务端图版本和放弃草稿在执行时重查同步 activity fence，不能仅依赖按钮 disabled。

## 操作者能看到的入口

独立项目保留“素材工作区”“创作图”，新增“制作操作”。阶段目录展示输入、来源版本、产物与审核要求；其 GET 永远不执行或授权。该页的独立媒体和时间线消费者另通过真实命令入口调用原 owner，仍可回到原素材／创作图入口。

媒体表单有 T2I／I2I／T2V／I2V／V2V／语音／音乐／音效／本地截取 9 项操作，Provider／模型来自只读配置参考，参数按当前 Provider 支持范围显示并校验；没有任意 JSON 编辑或配置发现即启用 Runtime。来源选择绑定确切 Asset 版本／摘要。云端发送需本次明确同意并经过原全局与来源政策；recipe 预览可核对实际接口、默认参数与原内置工作流。创建仅入队，执行须另一次明确动作。ComfyUI I2I 仅一张参考并拒绝尺寸参数，A1111 多参考语义未实际验收；异步音频无 poll，保持 UNKNOWN。

多轨表单支持有界 VIDEO／AUDIO 轨道、分切／移动／复制、图片叠层、精确有理变速、片段音量／静音／淡入淡出与手工字幕。保存不渲染；原 render 保留审阅规格，新增 export 经保存版本／来源／编码预览摘要确认后进入原本地 FFmpeg 与 VideoAssemblyService，支持明确 H.264 MP4 或 VP9 WebM profile。返回的 timeline job 经父级当前 client 绑定共享到媒体消费者，供用户明确读取候选／审核，不自动 GET、生成或采用。输出仍受原 25MiB／120 秒边界约束，原生编码与成片质量尚待真实验收。

任务详情使用原公共 `command`／`provider`／`execution_recipe`／来源与结果摘要；用户可以下载当前已读 JSON，不能在前端补写模型调用、结果、rights 或验收回执。候选只能来自原 API 实际字节和核验过的 Blob 本地 URL；身份、任务／版本、权限、来源变化、卸载时立即清空并 revoke，音视频不自动播放。更换 JSX 仍须执行 controller 命名动作，不直接绕过到 client。

`StudioAssetDeclarationForm` 已接入原独立工作区：原生成任务来源和父资产／文档快照只读，作者只能修改许可与操作说明，并以原 parent_asset_ids、chapter_ids=[] 提交声明，避免把 CREATIVE_DOCUMENT 当章节。声明不改变原生成来源或补写审核；手工导入继续用原 AssetLineageForm。

重新打开时仅恢复已保存定位，并通过原 owner 的 GET 核对图和运行。失效、无权限或不匹配的 ID 显示读取问题；不自动创建替代对象，不恢复预览勾选、不提交任务、不重放 UNKNOWN 请求。已保存版本发生变化仍需用户核对；保存不等于执行，批准不等于写入正文或质量验收。

导航定位不保存 Prompt、正文、模型结果、会话 Token 或凭据。协作/已认证会话不读取本地作者的记录。草稿仍由原组件保留，不能以恢复定位替代草稿持久化。

## 不能随换皮改变的行为

- AppShell、ModuleSwitcher、ContextBar、StatusBar、主题 token 与核心 primitive 继续受 DS-v1.0 保护；系统级变更走仓库 Design System Change Request。
- 来源版本/digest、项目 incarnation、原身份/分支、expected_version、idempotency request 与人工审核摘要保持原含义。
- UNKNOWN 回执只允许明确核对，不自动重试；取消请求与已取消终态区分。未读取不显示空数据，读取失败不显示已保存或已完成。
- 原 Owner 的成功不自动升级为 Router 已结算、真实 GPU 调用或产品验收。模型元数据、目录发现、Mock 和 CPU 运行分别记录。
- API Provider 执行仍按既有门禁；不加入付费 fallback、模拟身份、开发 token、关闭认证、内存凭据或 V1 凭据访问。
- 云端授权还继承原不可变 Asset 来源和有证明的 legacy parent 版本／摘要；直接／间接文档须原 CLOUD_ALLOWED，64 节点／16 层／200MiB 有界，缺失／旧章节证明、新父来源、循环／stale 都 fail closed。作者声明不产生 cloud grant；UI 不能靠修改 license／origin／parent 绕过后端。
- Graph 媒体与 `ASSET_REF` 仅在显式 schema 3 接入；保留原 WorkflowRun、媒体 owner、原子来源、候选审核、UNKNOWN 与一次发送边界。schema 3 文字档案已沿原 owner 接入，真实对应 human_review 节点批准／驳回，档案仍私有且不构成整图验收。原 schema 1／2 和 TEXT Router allowlist 不自动扩展。Graph timeline node 已沿原剪辑／导出 owner 接入；固定 Whisper Host 的原 AUDIO 模型加载准入和 MFA 的真实声学强制对齐源码已补齐，默认未配置／未加载继续 NOT_CONFIGURED，不能自动启用或假定完成音画／口型对齐。详见 [文字档案与剪辑导出](text-archive-timeline-export.md)、[执行细节与剩余边界](source-completion-boundaries.md) 和 [媒体执行收束](media-execution-source-completion.md)。
- 媒体／时间线控制器保留预览、route／recipe／source／job CAS、request ID 和一次明确发送／审核确认。网络、408/409/425/429、5xx 和非法成功回执不得重复发送；先读取原记录。显式 reconcile 仅原 lease 已结束后处理：不明派发为 UNKNOWN，能确证原私有 publication 或未提升 REVIEWING 的才恢复待审核；不重新调用 Provider／FFmpeg。视频 refresh 只查询已记录远端任务，异步音频没有 poll。`LOCAL_RESULT_DISCARD` 不声称远端 abort，保留原候选。
- 后端未来意图模型校验来源重复/冲突、轨道与完整来源快照、rational timing、尺寸/MIME/大小及作业/审核引用的一致性。JSON Schema 单独不能表达全部跨字段规则；形状一致不证明真实文件、路由、回执、权利或 scope。接入原执行 owner 前必须重新核对原门禁，不能从只读目录产生执行请求。
- PoemSeed Local Interop 1.0、冻结 V1、历史 PR、失败证据与 NOT_RUN / LOCAL_REQUIRED / BLOCKED 标签原样保留。

## 后续验证顺序

本轮只完成源码与静态复审，全部 tests、collect-only、typecheck、build、CI、Runtime、Windows／GPU／真实模型与全流程验收均为 NOT_RUN — USER_DEFERRED。历史新增的契约/恢复定位用例仅编写，不能记通过。Phase10 的 GraphFlow 状态保留在原报告；本批 Phase11 的 context／plan 返回 Transport closed，索引结果另按真实回执记录，不把失败工具请求写成成功。

Graph 媒体的可替换视图为 `StudioGraphMediaExecutionPanel`，行为在 `useStudioGraphMediaExecution`、原 `useStudioGraphRunController` 与 `studioGraphClient`。原节点编辑器提供有限参数控件；运行选择和排他仍由原父控制器持有。Opus 可重排这些视图，须保留 run/node/job CAS、候选实际字节核验、source 审核、未知回执恢复和导航保护。

时间线增强视图继续在 `StudioTimelineEditor`，`useStudioTimelineEditor` 保留编辑／本地撤销重做／保存／导出预览／明确同意／一次发送和 UNKNOWN 原任务查询恢复。`studioTimelineExportTypes` 与严格 Production client 校验真实 recipe、源快照、预览 digest 和原任务；实际 `media_measurement` 与计划 profile 分开显示。Opus 可以完善时间尺／拖放／参数交互，但不能在换皮时自动生成任务、替换原 request_id、隐式升级旧时间线或将候选直接视作已审核交付。

工程和 UI 改动收束并恢复验证后，先做相关模块与权限/恢复/CAS检查，再刷新当前源码的 API catalog 与 V2 coverage manifest，跑里程碑 CI。独立修复提交 `776286f` 的 8 项 metadata 对应旧 `5ed1cbee` 快照，不能当作覆盖这批新 API／源码的最终元数据；冻结 V1 manifest 不改。

随后从最终实际远端 SHA 按原 Windows 脚本构建，经原 launcher → PostgreSQL → backend → DesktopHost 验证隔离、会话、重启与中文路径，完成真实 M4 Text Node → Router → Provider → 本地模型 → Asset → Version → Review。达到真实验收门禁后，依次推进 M5–M9 实际能力验收。

Phase12 的 Graph 时间线基础表单沿 `StudioGraphTimelineNodeEditor`／`studioGraphTimelineContract`、原 graph editor controller、Graph client 与媒体运行 controller。保存节点参数不执行；显式读取时间线不生成，确认 dispatch 才提交原剪辑并仅入队，execute 才导出，media_review 才入素材库。8 个输入只绑定已有片段，作者编辑与绑定共 40 项；时间线 ID／base version／digest、剪辑证明、final version、profile、实际来源和 job CAS 均由原服务保存与核对。Opus 可以换时间尺、拖放与视图，但不能把这些动作合成自动导出、用任意 JSON／文件路径扩大输入、重建 UNKNOWN job 或采用未审核候选。原 DS shell 与单一 owner 边界保持。

Phase13 新增 `StudioTimelineTransferPanel`／`useStudioTimelineTransfer`／`studioTimelineTransferTypes`：只读预览、明确媒体映射、loss 确认、原 CAS 导入与摘要验证附件分别操作。未确定导入保留原 request ID／版本／预览／输入；只读原 timeline 的安全 transfer_receipt 准确匹配后才清除 UNKNOWN，不因内容恰好相同而认定成功。Transfer 与父时间线编辑互斥，dirty／UNKNOWN 阻止导航和整份保存；附件 URL 随 scope／timeline／来源变化或卸载撤销。Opus 可换映射表、字幕编辑器和布局，保留 headless controller 的命名动作。

轨道可通过原 `track.update` 的独立 locked 字段明确锁定／解锁；整份保存、恢复和导入不能替它解锁。像素 crop 使用未旋转源编码尺寸，表单不能把预览布局坐标直接当源像素。字幕处理只在 V2 显式 host 配置原生工具后启用烧录，并由原 DesktopHost session／principal 反复授权；配置或源码存在不等于真实运行通过。

交换草稿支持明确选择单个本地 .otio／.srt／.vtt 文件：headless controller 在父级 mutex 内做大小和严格 UTF-8 校验，再核对 client／epoch／保存版本／格式／方向／内容／当前素材，才载入本轮私有草稿并清除旧映射与确认。OTIO 上限 2 MiB，字幕上限 192000 bytes。文件选择不自动识别映射、预览、导入、写文件或读取外部媒体；Opus 可重构文件入口与编辑区，保留这些动作的独立性。

Graph 的 `review_recovery` 三字段只授予原 REVIEWING 私有预留的明确维护入口。stale／终态／暂停 run 可核对并释放被证明未提升的占用；不能执行、批准、推进节点或重新发送。控制器只接受当前原 Host client 实际观察到的原 run／node／job／version／request 证据，masked 回执不恢复候选、Prompt 或执行权限。保持原 run 视图与 client 严格解码，详见 [Graph 媒体执行](graph-media-execution.md)。

Phase14 的播放缓存经原 export/job/private Asset owner；稳定 request ID 由服务器实际版本／来源／工具 SHA 构造，不创建第二队列。复用旧 Blob 前也需原 candidate attestation；后端拒绝／撤权／来源变更立即撤销本会话字节，不清除 UNKNOWN 原请求身份。读回执与取消可在长时间 BUILD 中显式操作，但仍互斥且不重发。视图可重构时间定位、按钮和视频外观，不可自动生成／播放／审核；dirty／UNKNOWN 与原父级导航保护保持。

交叉溶解关系位于 VIDEO clip 的 `transition_out`，由原 schema／edit／Graph author 操作及实际双源 FFmpeg 渲染共同处理；表单不自动移动片段或清除用户 fades 来凑合法结果。两片段须真实重叠等于指定窗口且保持同一几何／opacity。OTIO 预览明确给出关系与 loss，不能用 Studio extension 的回读承诺外部 NLE 原生保真。Whisper Host 固定配置及 MFA 运行时／词典／声学 pin 由 server-owned 配置持有，前端不接收绝对路径、任意 argv、token 或动态模型替换；源码／loaded 状态／真实质量三个层次分别记录。

## Reconstructed standalone CPU cutout surface

Existing independent IMAGE production panel now offers source PNG + saved
authored-mask selection, bounded local CPU preview, explicit job creation and
execution, private candidate display and separate explicit review. No provider,
model, prompt or cloud consent is part of this operation. It is not a Graph action.
Keep exact ordered input snapshots and immutable mask lineage; source/mask
changes invalidate prior preview/review consent. Recovery controls cover UNKNOWN,
REVIEWING and cancelled lost-publication receipts without automatic replay.
The original workspace semaphore retains global mutation exclusion until both
execution and its narrow exact-job GET/CAS cancellation control settle. Preserve
identity ABA redaction, late-response fences, uncertain-send states and disabled
review after cancellation. Visual rearrangement must not collapse explicit
preview/create/execute/review or manufacture success from a late response.
Backend format is narrow8-bit noninterlaced PNG64–1024 multiple8, no ancillary
chunks; native browser/Windows visual acceptance is still unverified.
