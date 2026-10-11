# Studio V2：前端 UI / UX 重构交接

本轮按用户授权继续实际后端工程和基础前端，已接入独立媒体命令与有界多轨审阅渲染；测试、构建与真实全流程验收暂缓。工作基于 `5ed1cbee41d549351637d04a894477750c3e08b2`。这些新增源码尚未经过本轮执行验证，不能据此认定 M4 或后续里程碑通过。M4 保持 PARTIAL，M5–M9 保持 LOCAL_REQUIRED；QingJian 暂停推进。

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

多轨表单支持原有界 VIDEO／AUDIO 轨道、片段裁剪／摆放、音量／静音与手工字幕。保存不渲染；明确核对时间线版本／摘要后，render 会实际进入原本地 FFmpeg 与 VideoAssemblyService，而不是只入队。它是有界审阅渲染，不是完整 NLE 或高质量导出。返回的 timeline job 经父级当前 client 绑定共享到媒体消费者，供用户明确读取候选／审核，不自动 GET、生成或采用。

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
- Graph 媒体节点、`ASSET_REF` 原子输入、完整 NLE、自动 ASR、自动音画对齐和高质量交付导出保持未接入；独立实际命令不自动扩大 Graph Router 的 TEXT 执行 allowlist。现有规划、有限拼接、OTIO 交换与新的有界多轨审阅渲染不能冒充完整剪辑器。
- 媒体／时间线控制器保留预览、route／recipe／source／job CAS、request ID 和一次明确发送／审核确认。网络、408/409/425/429、5xx 和非法成功回执不得重复发送；先读取原记录。显式 reconcile 仅原 lease 已结束后处理中断为 UNKNOWN，不重新调用 Provider／FFmpeg；视频 refresh 只查询已记录远端任务，异步音频没有 poll。`LOCAL_RESULT_DISCARD` 不声称远端 abort，保留原候选。
- 后端未来意图模型校验来源重复/冲突、轨道与完整来源快照、rational timing、尺寸/MIME/大小及作业/审核引用的一致性。JSON Schema 单独不能表达全部跨字段规则；形状一致不证明真实文件、路由、回执、权利或 scope。接入原执行 owner 前必须重新核对原门禁，不能从只读目录产生执行请求。
- PoemSeed Local Interop 1.0、冻结 V1、历史 PR、失败证据与 NOT_RUN / LOCAL_REQUIRED / BLOCKED 标签原样保留。

## 后续验证顺序

本轮只完成源码与静态复审，全部 tests、collect-only、typecheck、build、CI、Runtime、Windows／GPU／真实模型与全流程验收均为 NOT_RUN — USER_DEFERRED。新增的契约/恢复定位用例仅编写，不能记通过。GraphFlow 当前 context／plan／单文件 index 的尝试返回 Transport closed；沿已知锚点静态工作，不记工具成功。

工程和 UI 改动收束并恢复验证后，先做相关模块与权限/恢复/CAS检查，再刷新当前源码的 API catalog 与 V2 coverage manifest，跑里程碑 CI。独立修复提交 `776286f` 的 8 项 metadata 对应旧 `5ed1cbee` 快照，不能当作覆盖这批新 API／源码的最终元数据；冻结 V1 manifest 不改。

随后从最终实际远端 SHA 按原 Windows 脚本构建，经原 launcher → PostgreSQL → backend → DesktopHost 验证隔离、会话、重启与中文路径，完成真实 M4 Text Node → Router → Provider → 本地模型 → Asset → Version → Review。达到真实验收门禁后，依次推进 M5–M9 实际能力验收。
