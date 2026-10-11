# Graph 媒体执行与原子资产输入

本批从 `4a4a9df1e59217f249a4e1f90c863729aefc1ea8` 继续接入源码执行逻辑。按用户要求，测试、测试收集、导入检查、typecheck、构建、API／Runtime／模型调用、CI 与真实全流程验收均为 **NOT_RUN — USER_DEFERRED**。M4 仍为 **PARTIAL**；M5–M9 仍为 **LOCAL_REQUIRED**，按 M4 → M9 验收。代码上传不构成发布验收，PR #47 保持 Draft。

## 原状态 owner

`CreativeGraphMediaRuntime` 是原 `WorkflowRun` 与 `ProductionExecutionService` 的衔接层。预览、发送意图与回执保存在原 actor／scope／incarnation 绑定的 Graph run 内；实际任务仍属于原 ImageJobService、VideoAssemblyService 或 AudiobookStore／AudiobookService。没有新的队列、调度器、凭据库或动态执行注册。

新增显式 `schema_version=3`：最多 24 个节点、4 个媒体生成节点，运行历史最多 80 项。旧 schema 1／2 的定义、16 节点／20 历史上限与资产引用阻塞行为保持原样。媒体节点和 schema 3 资产输出不复用其他运行的缓存，也不并行或自动重试。

| 节点／端口 | 源码行为 |
| --- | --- |
| `asset_reference → ASSET_REF` | 原 Asset ID／version／digest／kind 与真实文件内容核验；拒绝私有候选、删除、过期、不同 scope／incarnation 的来源。 |
| `media_generate → MEDIA_CANDIDATE` | 可接作者 TEXT 与操作要求的 ASSET_REF；仅显式预览、入队、执行。候选绑定原 job ID／version／request digest 与原 Asset 四字段。 |
| `media_review → ASSET_REF` | 唯一对应生成节点的候选，显式审核原 job/version/request/output digest，再由原 AssetLibrary.promote_owned 入库；正式资产版本才可下传。 |

媒体配置是闭合 DTO：操作、明确 Provider／模型、Prompt、该操作允许的参数、allow_cloud 与作者许可说明。九项操作为 T2I、I2I、T2V、I2V、V2V、speech、music、effects、trim；具体参数、Provider 能力与原媒体 owner 边界见 [独立媒体执行](production-execution.md)。I2I／I2V／V2V／trim 需要对应类型的一个来源，trim 仅本地，禁止 Provider／模型／Prompt／TEXT／云端输入。

预检要求生成与审核一一对应；私有候选没有 ASSET_REF 类型，不能连接到下游生成节点。保存／创建运行／执行前置节点均不会自动发送媒体请求。原 TEXT Router allowlist 不扩展为媒体 dispatch。

## 原子来源与任务授权

`GraphAssetInputs` 按原 raw scope → Asset → Project 顺序进入临界区，沿 CreativeProjectStore 的当前 incarnation 视图合并原集合，Asset／Project lease 保持到 raw scope commit 完成。原资产读取仍由 AssetLibrary 校验内容 SHA256。封装不持有新的资产状态，也不在 Provider／网络调用期间保持 Graph 写事务。

实际发布／审核沿原 Production source lease：先在原 scope 文档内纯校验保存图、运行、节点与任务绑定，再进入原 Asset／Project lease 核对 Graph 原输入、已审核输出及本次 Production 来源。该阶段不反向读取或开启 scope 事务；原 job guard 最后核对当前尝试。来源、定义、权限、incarnation、取消状态或期限变化均拒绝采用结果。

服务器生成闭合 `creative-graph-media-binding/1`，绑定原 run／graph／node、图与运行摘要、输入、预览版本、命令和 actor／scope／incarnation。绑定进入原请求摘要、原任务 context 及不可变结果 origin。HTTP 请求不能提交这个字段。独立媒体列表过滤 Graph 绑定任务；其独立 get／execute／review／candidate 等入口拒绝采用，不能借其他面板绕过 Graph 检查。

可信 Host、原会话、项目激活、权限、原执行开关、云端与来源政策仍由原服务核对。V1 凭据和默认路径不读取、枚举、迁移或覆盖；V2 原固定命名空间保持。PoemSeed Local Interop 1.0 不改语义。

## 显式操作与恢复

基础路径：`/api/projects/{nid}/studio/graph-runs/{rid}`，原 `/api/v1` alias 保留同等门禁。

| 方法／相对路径 | 动作与凭据 |
| --- | --- |
| `POST /media/preview` | `expected_version`＋`node_id`；保存原输入、路线与 recipe 预览，不创建媒体任务。 |
| `POST /media/dispatch` | 另核对 `reviewed_preview_digest`；原节点 claim 与入队意图先持久化，再仅创建原 QUEUED job。 |
| `POST /media/execute` | run/node CAS＋`expected_job_version`＋`expected_request_digest`；先持久化一次发送意图，再由原 owner 明确执行。 |
| `GET` 原运行 | 只读当前原 job 回执与版本，不 poll、reconcile、adopt 或创建任务。 |
| `POST /media/refresh` | 已知 job 需完整 job CAS；视频只查询保存的原任务。失联入队用 run/node CAS 查询原绑定并明确采用原 job，不重建。 |
| `POST /media/reconcile` | 原 lease 结束后记录中断并核对同一个 job，不重新发送或执行。 |
| `GET /media/candidate/{node_id}` | 原授权读取实际候选文件，no-store、原版本及 SHA256；前端自行核验 Blob。 |
| `POST /media/review` | `node_id` 为 media_review 节点，完整 run/job CAS＋候选 output SHA；原入库后完成原 Graph 审核节点。 |
| `POST /reject` | 当前媒体审核节点与候选 SHA 精确绑定，原工作流驳回后丢弃本地采用权。 |
| `POST /cancel` | 原 Graph durable fence 先完成，再显式丢弃绑定原任务的本地结果采用权；不声称 remote abort。 |

媒体预览／入队／执行／refresh／reconcile 需 domain.write；候选及运行读取需 domain.read；审核／驳回需 domain.review。任务和前端动作均保留 UNKNOWN 与一次发送意图。失联、非法成功回执或版本冲突不自动重发、不换 request ID 或扩大 timeout。

原 owner 入库成功但 Graph 审核提交回执未知时，读取原 run/job 后可明确再次确认同一候选，收敛原 Graph 完成；不再次调用模型。异步音频仍无原远端查询协议，UNKNOWN 保留。取消保留原记录与候选，提示远端可能继续。暂停／恢复不允许在原媒体节点 WORKING 时进行，也不重置原运行期限。

原 run 的 `model_called`／`external_calls` 保持原 TEXT Broker 口径；媒体调用事实另看逐节点的原媒体 job 回执。RUNNING／SEND_RESERVED 或目录元数据不能写成 Provider 成功、GPU 调用或完整验收。

## 前端与 Opus 边界

`studioGraphClient` 验证 schema 3、原媒体公共回执和候选响应；`useStudioGraphMediaExecution` 保存准确同意、发送键、未知状态和私有 Blob 生命周期；`StudioGraphMediaExecutionPanel` 只提供替换得了的视图。原 Graph run controller 仍统一持有动作排他与运行选择，媒体面板不能私自覆盖原 run。

节点编辑采用有限操作／参数控件，保存图不执行。运行面板提供预览、仅入队、明确执行、原记录读取、候选核验、审核／驳回与取消。确认、待处理或未知状态进入原导航保护；身份、权限、run/job/asset 版本变化与卸载清空私有候选并 revoke URL。Opus 可重排 JSX 与 token 样式，继续消费命名控制器和严格 client；AppShell／原权限／CAS／一次发送／人工审核边界保持。

## 保留的未完成项

- Schema 3 的 `ModelDispatch.archive_result=true` 已沿原 GraphTextAssets／GraphAssetInputs 接入文字私有档案与真实 human_review 节点审核，混合媒体执行也复核档案证明；原 schema 2 路径保持。详见 [文字档案与剪辑导出](text-archive-timeline-export.md)。
- 独立多轨时间线已接原子编辑、原版本历史恢复、显式 schema 2 图片／变速／淡入淡出／视频声音混音和 H.264/VP9 编码导出。原 25MiB／轨道／时长门禁保持；Graph timeline node、自动 ASR／音画对齐和跨软件往返仍未实现，不能冒充验收完成。
- 当前源码 API／V2 coverage metadata 待恢复验证后由原工具同步；历史 `776286f` 的 8 项 metadata 只对应旧 `5ed1cbee` 快照，冻结 V1 manifest 不变。
- a40df 的原 PostgreSQL failed-call、终态超时、取消与不完整 CI、F00 INTEGRATED＋39 PARTIAL、独立复审 BLOCKED 和历史 NOT_RUN／LOCAL_REQUIRED 原样保留。Windows／原 vault／WebView2／GPU／真实模型全流程仍需最终源码上的证据。
