# AI Novel Studio V2 开发交付报告

证据快照：2026 年 10 月 9 日 06:56 UTC。当前结论是 **V2 主要开发模块已实现，云端完整 File/PostgreSQL 严格合并验证与完整前端回归通过；最终发布 SHA 与其托管 CI 结果在 PR 47 单独维护**。本报告记录实际代码、执行结果和未完成项；文件名中的 FINAL 不代表全量通过、可合并或可发布。

最终本地严格证明为 **File 6,176 passed / 3,251 精确获准 skips**、**真实 PostgreSQL 6,151 passed / 3,276 精确获准 skips**；两个 profile 各完整收集 **9,427 节点**，原 `file=1/postgres=2` reconciliation **PASS**，原独立 TCP gate **2/2 passed**。完整前端为 **1,554 passed / 8 既有 opt-in skips**，独立基础设施自测 **170 passed**。不同 profile 与独立 gate 不相加为唯一产品用例总数。

本次完整后端证明使用 dot 云端 Linux、Python 3.12.14、真实 PostgreSQL 17.11；三个执行工作区的 1,654 个源码输入稳定且与当前工作树一致。这不是 GitHub Actions 结果，不声称单进程 PostgreSQL 全序交互等价，也不替代新增 V2 浏览器、真实模型或用户 Windows 安装验收。此前普通完整 File **6,174 passed / 3,253 skipped** 及所有失败/补验收据保留为独立历史证据。

## 1 交付身份与范围

- 仓库与分支：`1785235376-blip/AI-Novel-Studio`，`feature/v2-narrative-platform`。
- V2 foundation 基线：`e21075d10801a60bdcb4282a6d5ce8068be21503`；此前独立 V2 基线提交为 `1b7ff50a7e64742916bc64730df884cea819b379`。
- 四模块代码检查点：[`d444901ab8e65a7296b559c890d758fc2e0dd10e`](https://github.com/1785235376-blip/AI-Novel-Studio/commit/d444901ab8e65a7296b559c890d758fc2e0dd10e)，[Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47)。本轮没有合并、创建 Release、部署或修改 main。本地快照核对时 PR 为 draft、未合并；`mergeable:true` 只表示 GitHub 合并冲突判定，不是 CI 通过或合并批准。
- 本次开发和本地验证使用 dot 的云端 Linux 工作区；没有连接或操作用户电脑，没有执行付费模型调用。
- 最终发布包包括四模块代码、新增 V2 coverage manifest、runner/CI 配套修改、更新后的 API catalog、live-browser 检查、报告及原始证据。源码验证绑定候选 tree `0b0971ad6574aafe7c2f72135f7317e5b0e43715`；最终发布 commit SHA 与其托管 CI 结果由 PR 47 维护，不能把最终发布包的新增步骤回填为 d444901 已执行的成果。
- 用户已明确批准原上传步骤；同一 `API_CATALOG.json` blob 重试成功，GitHub blob SHA 为 `143950b8067307b05fd8ef59a643fd27654ebdb2`，其余目录 blobs 也已上传。这是发布准备过程的上传记录，单凭 blob 成功不能推出分支更新或 CI 通过；最终发布身份以 PR 47 记录的精确 SHA 为准。
- `narrative_production_v2` 服务端默认关闭，前端按真实 capabilities 显示入口；`V1_ACCEPTANCE_MODE` 继续禁止实验能力。原 NOVEL / IMAGE / VIDEO 全局壳体及小说正文写入责任保留。

历史结论原样保留：**39 PARTIAL + F00 INTEGRATED，独立审查 BLOCKED**。本轮开发没有重新分类、重开或替代该审查；V1.X、RC1、PoemSeed LocalInterop 1.0 的历史资产和证据不被本报告覆盖。原 [功能矩阵](POST_INTEROP_FEATURE_MATRIX.md) 与 [历史延续报告](POST_INTEROP_R4_R5_CONTINUATION_REPORT.md) 的字节仍与本轮基线一致。

## 2 已实现的模块与使用边界

### 2.1 本地 AI 环境发现

扩展原 `HardwareInventory → LocalDiscovery → ModelCenter → RuntimeRegistry → Routing`，没有建立第二套模型注册表。

- 增加类型化 `AIEnvironmentReport`。环境摘要 GET 受 host session 保护，只读取最近一次用户主动触发的扫描结果，不因打开页面自行扫描。
- 在已知 loopback 端点只读探测 Ollama、LM Studio、ComfyUI，并保留既有 Automatic1111、llama.cpp 路径。普通发现流程不要求用户先填写端口；固定端口探测不能保证发现所有自定义安装。
- Windows 扫描使用固定的常见模型目录、明确配置的目录及受支持的环境变量。它不是全盘搜索，也不递归扫描整个用户主目录。
- 识别 GGUF、Safetensors 头和 Diffusers 元数据；不反序列化 tensor、不导入模型类、不运行模型附带代码、不自动加载权重。
- 使用全局目录项、文件数、深度、根目录数、元数据/响应大小和时间预算；支持取消、异常隔离、部分结果，拒绝符号链接与 Windows reparse point。达到预算会保留受限状态，不能宣称扫描完整。
- 复用 CPU、GPU、显存与内存清单。CUDA / DirectML 仅报告可取得的系统组件存在证据；不能由 DLL、驱动条目、服务响应或模型名称推出模型可加载、GPU 可用或推理成功。
- 保留 `Detect → Validate → Register → Enable → Launch` 的显式边界。发现不会安装运行时、修改 provider 注册状态、自动启用或启动模型。
- 报告明确 `BACKEND_HOST`。本次云端 localhost 与云端硬件信息不代表用户电脑。

实现入口：[discovery_environment.py](app/model_center/discovery_environment.py)、[discovery.py](app/model_center/discovery.py)、[discovery_api.py](app/model_center/discovery_api.py)、[discovery_types.py](app/model_center/discovery_types.py)。

### 2.2 创作资产与阶段流转

扩展 `app/creative`，使用原 scope-atomic File/PostgreSQL 存储。用户界面有 Novel、Screenplay、Director、Storyboard、Production 五种模式；其中 Novel 嵌入原正文编辑器，其他阶段是独立创作资产。新增 `DIRECTOR`、`PRODUCTION`，保留旧 `VIDEO_PLANNING` 兼容。

- Screenplay 保存场景、地点、时间、人物、动作、对白、情绪和章节来源。也可明确选择独立剧本；“从已保存章节建立场景”只是带标签的文字脚手架，尚未完成自动改编。
- DirectorNotes 独立排序并引用稳定 scene ID，包含景别、机位、运镜、节奏、情绪、表演和场面调度。
- Storyboard 保存稳定 shot ID、镜头顺序及 lens、lighting、environment、sound 等结构字段。前移/后移不会更换镜头身份。
- Production 保存从已保存分镜派生的有序制作片段、时长和输出设置，支持增加、删除、调整顺序与编辑。
- 服务端支持已保存 Screenplay/Director → Storyboard、Storyboard → Production 的结构化派生。来源文档版本和 digest 由服务端绑定，记录 `STRUCTURED_DERIVATION`、`model_called:false`。
- 创建、保存、归档、JSON 导出、历史查看、审阅后的历史恢复均走实际 API 和原存储。派生与恢复不会写入小说正文或上游文档。

这里交付的是可编辑的创作与制作规划资产。Storyboard 中的镜头卡不等于已生成图片，Production 时间线不等于已渲染视频或音频。

实现入口：[models.py](app/creative/models.py)、[service.py](app/creative/service.py)、[api.py](app/creative/api.py)。

### 2.3 导演建议与可选模型执行

规则辅助路径可离线生成透明、可编辑的待审建议，明确标记 `RULE_ASSISTED`、`model_called:false`、`HUMAN_REVIEW_REQUIRED`。规则不能从小说文字可靠推断人物实际空间、视线、摄影机位置或表演质量，相关假设需人工核对。

可选模型路径复用原 `AuthorRequestPreparer → ModelBroker → JobManager`：

1. 由用户选择本地 TEXT route，要求已知零费用、`LOCAL_ONLY`、最大费用 0，禁止隐式云端回落。需要 narrative、broker、author-context 三个功能开关及 host session。
2. 在精确输入预览后核对 `reviewed_preview_digest`。输入只使用指定剧本，不隐式附带自动 context、风格或计划；原 author coordinator 仍要求一个有效来源章节锚点。
3. 调度前先持久化 admission，再由原 Broker 预留预算与核对 route/price/budget 版本。重复点击只能读取已有回执，未知 admission 不自动重放。
4. 输出限制为 128,000 UTF-8 bytes、180 秒执行截止，并严格验证 JSON schema、scene ID、顺序和来源。来源摘要、模型/版本、参数、路线指纹、job、输入输出摘要和费用回执保留为 provenance。
5. 采用建议需要再次核对指定输出摘要并明确审阅，创建新的 DIRECTOR 文档。原通用 generation accept 对 V2 origin 返回 `CREATIVE_DRAFT_ONLY`，不能把导演 JSON 写入正文。

这证明执行链与审核边界已经接线并受测试约束；本轮模型测试使用合成/Mock 执行结果，没有真实用户模型的创作质量或吞吐证据。

实现入口：[proposals.py](app/creative/proposals.py)、[generation.py](app/creative/generation.py)、[jobs.py](app/jobs.py)。

### 2.4 能力任务预检

在原 ModelBroker 增加任务类型映射：Novel writing、Screenplay adaptation、Director notes → TEXT；Frame analysis → VISION；Storyboard image → IMAGE；Video clip → VIDEO；Dialogue audio → AUDIO。

预检默认 `LOCAL_ONLY`、费用上限 0，不自行执行。VISION 只使用原 ResearchLibrary 实际注册且具备对应 operation 的 provider，VIDEO 只读取原媒体 registry。缺少可用实现、route 或 operation 时返回 `NO_LEGAL_ROUTE`，不会用 TEXT、检测到的文件或虚构 provider 冒充对应能力。预算、来源、权限和 route 变化会使旧预检失效。

这些任务名称表达合法路由需求，并不表示已新增六套模型执行器。实际图像、视频、音频制作继续依赖原 provider 与授权流程。

实现入口：[model_broker.py](app/experimental/model_broker.py)、[model_broker_api.py](app/experimental/model_broker_api.py)。

### 2.5 五模式创作界面

沿用既有 AppShell、ModuleWorkspace、设计 token 和公共组件。在 NOVEL 内提供显式 V2 入口、阶段切换、真实资产浏览、结构化编辑区、建议/模型预检侧栏与制作序列。

- Novel 保持原正文编辑器和保存责任；切换模式不会销毁正文编辑器，也不会将派生 JSON 写回正文。
- 四种结构化模式分别保留草稿；模式切换保留草稿，离开页面时提供继续编辑、明确丢弃与 JSON 草稿导出。
- 草稿在页面内存中，保存后才持久化。页面关闭、刷新或进程退出前未保存的内容不能承诺自动恢复。
- 保存冲突或未知写入回执时，保留并锁定草稿，要求先核对服务端结果；不会在不确定是否成功时自动再提交。
- 身份或 scope 变化会卸载旧工作区，迟到的读取、写入回执与导出不能重新填回已撤权内容。
- 未配置模型、无 host authority、功能关闭、过期来源、检测未运行/受限等状态均有明确呈现。

界面实现与测试说明：[creative-workbench-ui.md](docs/delivery/v2-development/creative-workbench-ui.md)。

## 3 权限 并发与恢复保证

### 3.1 权限与来源

每条 Creative 请求使用原授权解析器及 `domain.read` / `domain.write`，固定 actor、novel 和 branch scope；返回成功内容及私人错误投影之前再次验证权限。模型路径额外要求 host session。提案绑定创建者，跨 actor、项目或分支访问不回退到其他 scope/mainline。

章节版本、隐私/审阅状态以及递归上游文档的版本和 SHA256 digest 必须仍匹配。上游修改、归档、撤权或损坏绑定会使依赖链 fail closed；读取、写入、历史、导出和审阅均受此限制。来源链有深度和访问数量上限，拒绝循环与伪造输入；客户端不能自行注入服务端 `source_documents` 证据。

### 3.2 CAS 与原子性

所有变更核对正整数 `expected_version`。File 使用原跨进程 workspace lock 与 scope 文档原子替换；PostgreSQL 使用原数据库事务和 row lock。文档、历史及提案采用结果在同一 scope 事务中提交，事务内重查来源与权限；撤权导致整组写入回滚。独立 writer 并发保存或同时采用同一提案时，只允许一个合法版本提交，不静默覆盖。

历史恢复不是改写旧版本：先审阅目标历史快照，再以当前 `expected_version` 创建一个新的 DRAFT revision，保留 `restored_from_version`。当前与目标历史的来源都必须有效，不能借恢复把过期章节或旧分支重新绑定为有效来源。

### 3.3 取消 撤权与重启

V2 job origin 在公共读取、流式增量及完成路径重查当前授权和依赖开关。取消、撤权、过期来源或超过输出/时间边界后，迟到结果被隐藏或丢弃；终态和会计回调仍由原 JobManager/Broker 管理。功能关闭后的恢复取消仍可通过原 Broker 的受限取消路径终止已存在作业。

已保存创作资产可以在进程重启后重新打开；这与模型执行恢复是两件事。模型 job 的活跃授权闭包不能从持久化结果恢复；重启、缺失 job 或未知 admission 会显示 `UNKNOWN_NO_AUTOMATIC_REPLAY` / `MODEL_UNAVAILABLE`，不自动重新执行、不再次占用预算，也不能直接将旧输出导入为已审核结果。需要核对原作业与费用回执，再由用户决定下一步。

原子存储依据：[store.py](app/experimental/store.py)。对应回归覆盖见证据索引中的 foundation、workflow、router suites。

## 4 实际验证结果

### 4.1 当前可采用的执行证据

| 检查范围 | 环境和实际结果 | 证据与限制 |
| --- | --- | --- |
| 最终完整后端严格合并验证 | **File 6,176 passed / 3,251 skips；PG 6,151 passed / 3,276 skips；独立 TCP 2 passed** | `cloud-full-backend-final` / `cloud-full-backend-coverage`；原 file=1/postgres=2 reconciler exit 0，全部精确 skip 校验通过；每 profile 9,427 nodes；本地云端，非 GitHub |
| V2 foundation、workflow、router、catalog、发现安全及 Broker 选定回归 | 云端 File：352 passed，135 skipped | `cloud-final-backend-file`；其中 134 为相反 PostgreSQL profile，1 为真实 Windows native；运行期间源稳定 |
| V2 foundation、workflow、router、catalog 与 Broker 选定回归 | 真实 PostgreSQL 17.11：144 passed，134 skipped | `cloud-final-backend-postgres`；134 为相反 File profile；运行期间源稳定；不是整库 PostgreSQL suite |
| 原两分片严格完整 PostgreSQL | **6,151 passed / 3,276 精确获准 skips / 0 failed** | `cloud-full-postgres-final` / `cloud-full-postgres-coverage`；两 shards 均 exit 0，原 reconciler exit 0；实际 Python 3.12.14 / PG 17.11；本地 dot 云端的独立 PG 证明，后继合并结果另列 |
| 完整前端单元套件 | 233 test files passed、2 skipped；1,554 passed、8 skipped | `cloud-frontend-complete-final`；8 为既有真实 HTTP/Interop opt-in，不是新增豁免；运行期间源稳定，当前 source map 匹配 |
| CI manifest、runner 与原 coverage 自测 | 170 passed | `cloud-v2-infrastructure-publication`；单独基础设施用例，不能计入产品测试总数；运行期间源稳定 |
| 原 Windows 依赖闭合回归 | 云端 Python：29 passed | `cloud-windows-dependency-closure`；仅依赖元数据/脚本合约，不是 Windows 执行；运行期间源稳定 |
| 最终直接构建与 token 检查 | git diff --check、TypeScript noEmit、Vite production build、token guard 42 files 均通过 | `cloud-final-build-lint`；命令 exit 0，但没有运行前 source snapshot，源稳定性另据完整前端回执；Vite 仍有大于 500 kB chunk 的警告 |
| 实际 HTTP 与 File 创作生命周期 | 后续 combined run 中 3 passed | lifecycle、scope/cancel/stale source、default-off；无需 Chromium 的 HTTP 检查，不能记为浏览器通过 |
| 服务关闭后独立进程重开 File | passed | 四种结构化资产、Production version 3、history 1/2/3，正文仍为 version 1 且未变；不是模型恢复 |
| File 原 pinned-font 条件补验 | **2 passed**，5.26 秒 | `cloud-file-pinned-font-final`；原 PDF 嵌入与漫画可读文本/overflow 检查；实际固定字体，源稳定，未新增 skip 例外 |
| File 独立 real-loopback subprocess gate | **2 passed**，28.35 秒 | `cloud-file-tcp-final`；原两进程 TCP 同步/冲突/撤权/重放检查；源稳定，独立于普通完整 pytest |
| 较早普通完整 File 重跑 | **6,174 passed / 3,253 skipped / 0 failed**，4 warnings | `cloud-backend-full-file-final`；05:49:10–06:03:47 UTC，867.55 秒；普通完整 pytest 的 9,427 节点全部产生终态，运行期间源稳定；未加载严格 CI gate |

较早普通完整 File、选定 File/PostgreSQL、基础设施和最新完整前端 `cloud-frontend-complete-final` 的 1,592 个 source 输入均已与当前工作树逐项复核，零差异，且各自运行期间源稳定。最新前端重跑于 05:51:34–05:52:29 UTC 完成。较早 `cloud-final-frontend` 运行后曾有两个基础设施输入变化，因此保留为历史材料，不用它的旧整份 source map 替代最新回执。

完整 File 的 3,253 个 skips 按 JUnit 原因分组为：2,988 个 opposite-PostgreSQL 合约、253 个需真实/专用 PostgreSQL 端点而本次未配置的检查、7 个 Windows/native/凭据库检查、2 个未准备 pinned font 检查、2 个要求独立 real-loopback subprocess gate 的检查，以及 1 个历史 Phase 1 migration 条件。此分组保留该次普通运行的实际跳过原因。后继严格 File 在准备固定字体的新隔离工作区中重新执行，以 6,176 passed / 3,251 skips 通过原严格 reconciliation；这是新的执行证据，不是把补验数字手工加回旧统计。剩余 Windows 等条件仍按其实际边界解释。

两项补验收据均记录 1,592 个 source inputs，运行前后稳定且与当前工作树匹配。固定字体由未修改的 `scripts/prepare_pdf_font.py` 按原 OFL 与 pinned-source 校验流程准备；实际 NotoSansSC-Regular.ttf 派生 SHA256 为 `eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461`。

最终 Vite build 保留 ExperimentalWorkbench 647.28 kB、App 775.04 kB 的非阻断 chunk-size warning，没有将构建描述为无警告，本轮没有为消除该警告引入打包重构。

真实 PostgreSQL 使用官方 Debian **17.11** 二进制，在工作区 `.runtime` 中解包并以普通用户运行，没有系统安装或复用用户/生产库。实际 SQL 验证版本、数据库和 loopback `127.0.0.1:55432`；初始化记录包含 20 个既有 migration，另有实际 51 张表的 SQL 记录。服务与测试在同一命令生命周期内运行并于结束时关闭。GitHub 托管 CI 的 PostgreSQL **16** 与本次本地 17.11 必须分开报告。

最终本地严格状态（2026-10-09 06:55 UTC）：**PASS**。原顺序 File profile 于 06:37:51–06:52:30 UTC 完成；两条原确定性 PG shards 分别于 06:10:59–06:35:35、06:11:09–06:33:32 UTC 运行，实际端口 55441 / 55442。三个执行均完整收集 9,427 节点，File 单进程执行原顺序，PG 按原确定性分配分别执行 4,702 / 4,725 节点，无重无漏。原 `coverage_reconcile.py --expected-shards file=1 postgres=2` 于 06:52:50 UTC 形成完整证明；所有 collection/validation errors 为空，独立 `sync-tcp.xml` 的 2 个原测试也获核对，不计入 profile 总数。

本地候选 Git tree 为 `0b0971ad6574aafe7c2f72135f7317e5b0e43715`，run identity 为 `local-cloud-pg-20261009T060653`；这是 HEAD 加精确本地候选内容的验证身份，没有以此创建新 commit。Python 3.12.14 / PostgreSQL 17.11，使用原未改动 gates、精确 additive manifest、固定字体和匹配的 pg_dump/pg_restore。各工作区 1,654 source hashes 运行前后一致且与当前工作树零差异，主工作树源码与 manifest 未变，先前 PG 证据归档也未改写，PG 服务已停止。

该证明覆盖原严格 File 原顺序进程、PG 两分片及独立 TCP gate；不承诺单进程 PostgreSQL 全序交互等价，也不是 GitHub、native/GPU、真实模型或浏览器验收。此前普通 File 6,174、选定 PG 144、前端 1,554，以及独立字体 2 / TCP 2 passed 均保留各自证据，不合并为唯一用例总数。

### 4.2 保留的失败与过渡结果

- `cloud-backend-full-file` 在开发期 collection 阶段遇到 `tests/test_v2_check_runner.py` ImportError，exit 2，且运行期间有源变更。它不是完整 suite 结果。
- `cloud-backend-full-file-stable` 实际为 **6,173 passed / 3,253 skipped / 1 failed**，exit 1；尽管名称含 stable，收据明确 `sources_changed_during_check:true`。失败是原 `test_real_locked_metadata_closes_windows_dependency_markers` 导入 `pip._vendor.packaging` 时，uv 创建的 `.venv` 内没有 pip。
- 后续仅在该虚拟环境通过 Python `ensurepip` 补入 pip 25.0.1，没有为使测试通过而改写旧断言。原 29 项依赖测试已稳定通过；随后独立的 `cloud-backend-full-file-final` 完整重跑通过，结果见上表。它是新的稳定源码/环境证据，不将此前失败、缺 pip 或源变化记录重标为通过。
- `cloud-v2-creative-http-run.log` 的早期 HTTP 运行是 **2 passed / 1 failed**，因为非法来源的状态码预期 409、实际 422；保留原日志。后续 `cloud-v2-creative-browser-run.log` / `results.json` 才证明三个 HTTP 检查全部通过。
- 开发期 `creative-workflows-*`、`cloud-v2-authority` 及部分 router/前端过渡收据可辅助定位实现过程，但存在并发源变更或更早代码身份，最终结论采用上表的相应稳定后继证据。

### 4.3 浏览器证据边界

本地 Chromium 在创建页面之前因 `process_singleton_posix.cc:297: socket() failed: Operation not permitted` 退出。combined run 总体是 **4 failed / 3 passed**：4 项需浏览器的 V2/default-off UI 流程未能执行，3 项真实 HTTP/File 检查通过。不能把总体写为全绿，不能宣称已批准 V2 截图、几何布局或视觉基线。

随后已在授权的项目内尝试原锁定 Playwright **1.62.1** 的官方 `chromium-headless-shell` 依赖路径（revision **1234**，version **151.0.7922.34**）。官方 CDN 下载的归档无法解压，安装器报告 0 MiB 与缺失 ZIP central-directory signature，内建重试后 exit 1，`binary_ready:false`。没有 headless-shell UI/geometry suite 执行或新截图，没有改安全设置，也没有重试完整 Chromium。此依赖失败没有解除原浏览器阻塞；详见 [结果](docs/delivery/v2-development/cloud-headless-shell-dependency/result.json)、[下载计划](docs/delivery/v2-development/cloud-headless-shell-dependency/download-plan.txt) 和 [原安装日志](docs/delivery/v2-development/cloud-headless-shell-dependency/install.log)。

已编写的 V2 Playwright fixture geometry 和实际 File/API 浏览器旅程仍需在允许启动 Chromium 的授权环境运行。d444901 历史托管 frontend job 的成功属于其当时原有 step 范围；最终发布包新增的 V2 browser step 不包含在该历史成功中。

## 5 CI 清单与发布状态

### 5.1 增量清单保持原门禁

新增 `.github/ci/coverage_manifest_v2.json.gz` 与原 frozen manifest 分开保存。原 9,151 节点及相对顺序、原历史 skip maps 保留，新增 276 节点，总计 **9,427 collected nodes**；Interop 仍为原 413 节点范围。新增节点没有新增 skip 例外。

原 `coverage_manifest.json.gz`、`postgres_gate.py`、`suite_coverage.py`、`coverage_reconcile.py` 的字节均与本轮基线相同。V2 generator 记录新增 source identity，继续使用原完整 collection、分片、JUnit/phase、源码 digest、真实 PostgreSQL 与严格 unexpected-skip 校验。不会在 CI 中自动重新生成并接受漂移后的 manifest。

唯一显式登记的旧测试迁移来自本轮开始之前的 V2 基线提交 `1b7ff50...`：`tests/test_windows_portable_entry.py` 的固定 launcher 预期增加 `-B` 再 `-I`。原/新双 hash 和逐字节单一替换规则保存在 collection receipt；这不是历史审查的批准。

本地 manifest 验证为 `INVENTORY_AND_SOURCE_INTEGRITY_ONLY`，`tests_executed:false`；1,654 个 manifest source 输入与 runner 收据的 1,592 个输入使用不同范围，不能混为同一个计数。生成的未跟踪 fixture lock / chapter identity 状态不被误当成 source，Git-tracked fixture 与历史来源仍保留。

### 5.2 四模块检查点 d444901 的历史托管结果

下列历史结果于 2026-10-09 05:50 UTC 通过 GitHub 只读接口核对，属于 d444901 的 PR-triggered runs，不能代表最终发布包的精确 SHA：

| Workflow 或 job | 实际状态 | 可得出的结论 |
| --- | --- | --- |
| [Cloud CI 37886802281](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802281) | failure | File 和两条 PG shard 在 frozen source digest gate 失败，后端汇总门禁失败；没有形成完整后端通过证据 |
| [Local Interop V1 37886802200](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802200) | failure | File/PG strict contract step 因同一 frozen source digest gate 失败；后续 reconciliation 未完成 |
| [Shared R123 37886802353](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802353) | success | 原 c6f2126 RED 重现流程按设计完成；不是 V2 产品全绿 |
| Cloud CI `Frontend / unit-type-build-tokens` | success | 原有单元、类型、构建、token、geometry 及已列出的业务浏览器 steps 成功；没有新增 V2 live/fixture steps 的成功记录 |
| Cloud CI 两个既有 Windows jobs | success | Host 编译/native 合约，fresh base/未签名内部验收包、embedded Python 与 PostgreSQL UTF-8 recovery smoke；不含 V2 用户安装、GPU、模型或交互桌面验收 |
| Local Interop `Windows current-user pipe reference (MOCK_ONLY)` | success | 分进程传输参考实现的 Mock 合约成功，不是用户目标应用验收 |

Cloud File job 日志及 Interop File job 日志都明确记录 `frozen product test/source digest differs`，包括 API catalog、V2 改动的应用入口/Broker/发现及基线 launcher 文件。失败说明现有严格门禁仍在拒绝把新 source 冒充冻结 V1；它不能当作后端测试已经执行完成，也不能被本地选定回归覆盖为成功。

最终发布包包括 additive manifest、CI 切换和新增 V2 Windows fixture step。新 Windows step 仅检验固定目录、系统组件真实标签和环境 GET 会话边界；**本地快照截点尚未取得最终发布 SHA 下该 step 的托管终态**。发布后按精确 SHA 核对所有受影响 workflow，结果由 PR 47 维护；不以本地通过或旧 job 成功预填新结果。

## 6 已知限制与下一阶段

1. **保留已完成的本地严格证明。** File 原顺序进程、PG 两分片、独立 TCP 及 file=1/postgres=2 reconciliation 已全部完成；完整前端也已通过。保留先前失败及独立补验，不删除 skip、不改旧测试以掩盖问题。剩余交付只继续本次已授权发布与对应 CI 核对。
2. **完成本次授权发布与托管验证。** 本次交付范围为将有效代码、修复、基础设施、目录、检查、报告与证据发布到 V2 分支，并在 PR 47 记录最终 SHA、CI 和剩余边界；按精确 SHA 核对 File、两条 PostgreSQL shards、Interop、前端和适用 Windows jobs。完成本任务后停止功能扩展；不执行本机 Windows 验收、合并或 Release。
3. **补 V2 真实浏览器证据。** 在允许 Chromium 的授权环境执行新增 V2 live workflow 与几何检查，核对 default-off、未保存草稿、冲突/取消、权限变化、历史恢复和正文不变。没有新证据前保持 BLOCKED/未验证边界。
4. **真实 Windows 本机验收需要单独授权。** 本轮用户安装、升级、交互窗口、输入法、用户目录模型发现、GPU/驱动与本地模型启动均为 **LOCAL_REQUIRED / NOT_RUN**；不能由托管 Windows 合约代替。
5. **真实模型质量仍为 NOT_RUN。** 需要选定并验证可用模型，另行评测剧本/导演建议质量、中文长文本一致性、吞吐、延迟、显存峰值及多模态输出。检测到格式或可选 route 不足以证明模型适配。
6. **恢复与规模限制仍明确。** 未保存草稿仅在页面内存；模型未知 admission 不自动重放；创作文档/提案和历史有容量上限。导演模型路径暂需来源章节锚点，独立剧本可继续手工编辑及规则建议。
7. **制作端到端能力继续分层验收。** 当前分镜和制作是规划层；渲染、TTS、字幕、媒体合成及真实 target application 联调需分别证明，不能由任务路由标签推定完成。

## 7 证据入口

完整的命令、时间、退出码、源码摘要、源码漂移标记、JUnit 和原日志位于 [V2 开发证据索引](docs/delivery/v2-development/cloud-v2-evidence-index.md)。阅读顺序建议：当前终态执行 → source integrity → GitHub 对应 SHA → 失败/受阻历史。没有终态或不能绑定正确 source 的材料不作为最终通过依据。

两份大型完整 File 原始 JUnit 以 `.xml.gz` 无损压缩随证据发布，本地原 `.xml` 保留；解压后与原始 bytes 完全一致，原/gzip SHA256 对照见 [归档映射](docs/delivery/v2-development/cloud-full-file-junit-archives.json)。

发布后的精确 SHA 托管 CI 状态在已核验的 [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) 中维护。本报告为带时间戳的本地证据快照，未预写尚未获得的远端 CI 结果。
