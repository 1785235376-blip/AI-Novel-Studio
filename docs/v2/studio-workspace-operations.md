# Studio 制作操作与视图替换契约

此页包含 M4–M9 的只读制作目录，以及另经原 owner 命令入口接入的独立媒体和有界多轨消费者。已有操作继续由原服务、权限、版本校验和任务管理负责；Graph 媒体节点等未接入部分保持不可执行。目录 GET 不评价 Windows、GPU、模型质量或产品验收，也不授予执行权限；M4 保持 PARTIAL，M5–M9 保持 LOCAL_REQUIRED，M4→M9 的真实验收顺序不变。

## 已接入的消费者

`StudioWorkspaceOperationPanel` 使用原 `Panel`、`Button`、`Badge`、`StatusMessage`、`EmptyState` 与 tokens。父工作区仍提供原 AppShell；模块切换、主题、shell 几何和核心 primitives 未重新定义。操作者默认看到中文操作要求、来源版本、产物审核与缺项；服务类、方法、接口、机器码和结构字段收在高级展开区。

`studioWorkspaceOperationClient` 只通过注入的原 Studio transport 读取 `GET /api/projects/{id}/studio/production-contracts`。它没有 POST、执行、权限授予、自动安装、扫描、下载、模型启动或付费调用方法。Panel 的“打开素材工作区”和 M4“打开创作图”仅调用父级现有导航；父级必须包装原未保存输入保护。实际媒体和时间线使用独立 `studioProductionClient`；不能从目录 action path 直接调用或绕过该 client/controller。

读取控制器为 `useStudioWorkspaceOperations`。UI 美化可替换 JSX/CSS，同时继续消费该控制器 snapshot 和 `reload/selectStage`；不能把只读接口描述变成可调用命令。

## 响应与身份边界

契约固定为 `studio-production-operation-contracts/1`。客户端闭合校验顶层字段、22 个 operation IDs、阶段顺序、公开 scope 和相应项目/分支。顶层 `advisory_only=true`、`execution_authority=false`；每项 `execution_available=false`、每个动作 `execution_grant=false`。已有 owner 的描述并不证明可在 V2 图中执行。

operation 的 input/source/output/review requirements 描述原约束。`interface_schemas` 包含七个有界对象 schema：source snapshot、provider reference、rights、timing、tracks、operation intent、media result。六个 `interface_contracts` refs 固定绑定这些未来接口；provider reference 嵌入 intent。它们不是旧入口可接受 payload 的扩展，不能据此创建请求或 grant。客户端仅有界解析 schema 元数据，不执行 refs/defaults/URL/表达式，不生成执行表单。

接口不返回 actor、principal 或 incarnation。401/403、身份变化或父级 deny 会清除先前响应；404/409 为入口不可用，不自动 activate。过期响应由 identity/epoch/AbortController 与父级 `isCurrent/read` 拦截。换阶段只改本地选择，不重新 dispatch，也不代表前序验收通过。

## 数据与运行状态

制作面板的数据状态为 IDLE、LOADING、READY、EMPTY、ERROR、UNAVAILABLE、DENIED。只有一次成功读取后没有操作才显示 EMPTY；加载、权限失败、未读取和错误不冒充空数据。

执行状态继续读取原任务 owner。目录消费者不创建或提升执行状态；实际媒体／时间线消费者通过命名动作读取原回执并分别确认预览、创建、执行与审核。未知进度保持未知；取消请求不等于远端已取消；UNKNOWN 回执不自动重放。来源 stale 或 409 保留输入并重新核对，不能自动重生成。

文字图的批准需要原 can_review、当前 run version、output digest、已归档结果和明确人工核对。SUCCEEDED 不等于质量通过，也不表示正文已经改写。M5–M9 的原入口／剩余缺项由真实返回契约显示；规划时间轴、有界多轨审阅渲染与完整 NLE 分别标明能力边界。

## 独立媒体与时间线控制器

`useStudioMediaExecution` 持有有界草稿、当前配置、预览／本次同意、原创建 reservation／发送键、已读 job 与候选 Blob；`StudioMediaExecutionPanel` 仅渲染命名动作。9 项 MediaCommand 通过原 ImageJobService、AudiobookService 和 VideoAssemblyService 持久 owner 执行。Provider GET 可只读加载当前配置，不探测健康、不解析凭据、不启动 Runtime。闭合参数按所选 Provider 支持范围核验，不接受任意 JSON；来源绑定原 Asset ID／version／digest／kind。ComfyUI I2I 限一张且拒绝 width／height；本地音频截取限单来源／实际时长／120 秒，A1111 多参考与真实音频／视频能力仍需验收。

用户明确读取 preview 并确认 input/source/route/recipe digest，create 只入队；再点击 execute 才分派。云端必须本次明确同意及原全局／项目／来源政策同时有效。原 job 动作绑定 expected_version／request_digest；审核 checkbox 绑定 job ID／version 和候选 output digest，候选实际字节须通过 MIME／大小／SHA256 核对后才可显式 review。原 JSON 回执下载仅序列化刚读取的公开投影，不补写结果或验收。

云端来源继承沿原不可变 Studio Asset 来源与有证明的 legacy parent 快照核对原 owner；直接／间接文档须原 CLOUD_ALLOWED，最多 64 节点／16 层／200MiB。缺失／旧章节证明、新加父来源、循环、stale 和超限都阻止发送；作者 license 声明不授予 cloud grant。生成资产专用声明表单只编辑 license／operation，origin／parents／docs 保持原执行记录，不把 CREATIVE_DOCUMENT 映射成章节。

`useStudioTimelineEditor` 的 base／draft 与已读服务端 candidate 独立；`studioTimelineTypes` 闭合轨道／片段／字幕 shape，`StudioTimelineEditor` 渲染其命名动作。CAS 保存冲突先读，用户明确采用服务端版本或保留输入并基于原版本编辑。只有已保存且无 dirty 的确切时间线版本／摘要才能明确 render；render 会实际同步调用原有界 FFmpeg 并返回原 owner job，不是仅创建队列。最多 8 轨／30 段／10 分钟，VIDEO／AUDIO 各 4 轨；视频叠放、音频 gain／mute／mix 和手工字幕均有界。不是完整 NLE、自动 ASR、音画对齐或高质量导出。

父级绑定当前 client 的外部 timeline job 可供媒体消费者预览／审核；仅在没有 pending、身份仍当前时采用新版本，不覆盖正在编辑的媒体草稿、不自动 GET／generate／review。身份／client 替换、权限撤销、任务／版本／来源变化和卸载清空原候选 URL／审核同意，立即 revoke Blob，晚到响应不得再采用；关闭 transport 不表示 owner 已取消。

网络、408／409／425／429、5xx 或非法成功回执保留不确定状态，阻止相同版本重复发送并提供原任务读取核对。显式 reconcile 对 image／audio／video／timeline 都只在原 executor lease 结束后处理 RUNNING／SEND_RESERVED 为 UNKNOWN，不重发。视频 refresh 只查询原已保存远端 task；异步音频当前无 poll，继续 UNKNOWN。本地 discard 保留候选且不声称 remote abort。媒体 dirty 与时间线 dirty 纳入父级未保存导航保护；确认离开不取消后台任务。

实际后端、API 和输出边界详见 [production-execution.md](production-execution.md)。Opus 可重排这些 Panel／Editor JSX 和 token 样式；须继续消费原 controller/client、命名动作、Host、CAS、人工同意、导航与私有 Blob 生命周期，不能另造执行流。

## 图编辑器的无 JSX 控制器

`useStudioGraphEditorController` 保留原目录、草稿、撤销/重做、资产绑定保护、CAS 保存、保存不确定、确认导航、原服务版本比对、权限清除和 epoch 防过期响应。`studioGraphEditorView` 仅渲染这些状态与原动作；`useStudioGraphEditor` facade 保留 `{ content, inspector, dirty, discard }`，原消费者无需重新设计 shell。

可选 `requestedGraphId/requestedRunId/onSelectionChange` 只提供恢复定位。图恢复使用原 checked graph GET；运行恢复由原 GraphRunPanel checked run GET 处理。均核对 owner/scope，不能按标题猜测、创建记录、执行节点或调用模型。请求完成前的新草稿不会被恢复响应覆盖；effect cleanup 取消在途读取，并仅清除在途恢复标识，使 StrictMode 重挂载仍可完成只读恢复。已完成但失败的恢复不自动循环重试。

选择回调只报告当前 graph/run IDs，私有正文、Prompt、输出和凭据不由此持久化。父级 resume 是恢复提示，原后端仍决定记录是否可见和当前版本。

## 继续工程：运行、模型与偏好控制器

`useStudioGraphRunController` / `studioGraphRunView` 和 `useStudioGraphModelExecutionController` / `studioGraphModelExecutionView` 分离运行状态与 JSX；原两个 Panel 保留组件入口。控制器负责同面板读取/动作互斥、预检失效、创建请求捕获、UNKNOWN 只读核对、run/node/output 人工审核绑定，以及模型 route/preview/version/synthetic 一次调用确认。实际队列、Job、ModelBroker、权限和 receipt 均继续归原后端；控制器不成为第二套 owner。

`useStudioWorkspacePreferences` / `StudioWorkspacePreferencesForm` 保留原偏好字段与 expected_version。draft 与已读 base 分开；保存冲突和不确定回执先阻止新 PUT，通过原 GET 得到 candidate 后，用户明确采用或保留输入并基于该版本继续编辑。读取不是自动重放，相同值不是原请求完成证明；放弃输入不会把未知保存结果记为失败。

独立工作区 overview、存储查询与引用预览均拦截旧响应。资产预览仅在图绑定 version/digest/kind 一致时显示；STALE、UNAVAILABLE、READING 与图读取时状态分开。导航确认和服务端图采用在 handler 中再查同步在途状态与权限，视觉重构不能削掉这些检查。

图保存的非法成功响应也属于待核对状态；不能把 HTTP 200 单独当保存回执。图服务端候选的独立 epoch/Abort 避免两次核对乱序覆盖，人工采用绑定候选 id/version/definition_digest/execution_digest；编辑、撤销、重新选择与权限失效会清除候选确认。旧版本回退或同版本摘要变化被拒绝，不默默采用。

## 暂缓执行验证

按用户要求，此工程阶段所有 tests、collect-only、typecheck、build、CI、Runtime、Windows／GPU／模型与全流程验收均 NOT_RUN — USER_DEFERRED。新增 `studioWorkspaceOperationContract.test.ts` 为未来验证源码，尚未运行，不记通过。需要在整体工程完成、恢复验证后检查篡改授权字段、foreign scope、reserved 动作、重复 ID、schema 边界、媒体／时间线来源与 job CAS、中断／幂等／receipt、Blob 清理，以及图/运行恢复、未保存导航、权限撤销、StrictMode 取消与重开。独立修复提交 `776286f` 的 8 项 metadata 只是旧 `5ed1cbee` 快照；恢复验证后须用原工具同步当前 API catalog／独立 V2 coverage，冻结 V1 manifest 不改。QingJian 暂停推进。

本轮 GraphFlow context／plan／单文件 index 尝试返回 Transport closed；沿此前已知锚点静态工作，未将工具故障记为成功。原 Master Roadmap 的缺失附件内容没有推测；当前操作范围以仓库现有 owners、已知阶段指令及本轮明确授权为准。历史 PG／CI／F00 INTEGRATED + 39 PARTIAL／独立复审 BLOCKED 与 PoemSeed Local Interop 1.0 语义原样保留。
