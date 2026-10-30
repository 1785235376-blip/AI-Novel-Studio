# 项目容量统一计量：M0 基线与验收账本

本账本固定于 `a79237f6082501e44f1162d0860993c7b9348ba1`，tree `35b2656aad9f5434736577003c8e09d2c5c33bbe`。以下标记的是源码和已有证据核对，不代表本轮生产容量链已通过。任务要求的不可变音频历史写入、迁移和恢复仍关闭；原资产 `restore` 仅撤销软删除。沿用原 `AssetLibraryService`、`ExperimentalStore`、`CreativeProjectStore`、TaskCenter 和授权 owner；不设平行的资产或权限系统，也不把未接生产的隔离账本叫做现有唯一计费账本。

## 已确认的计费合同

- 默认项目上限 512 MiB；项目管理权限者最终可显式调整、持久化与审计，但 M5 在统一计量、预留、对账和审批保护通过前关闭。
- 当前、历史、候选、临时和失败残留：有可证明项目／incarnation 归属者按实际存储字节计费；逻辑引用量另列。只有同一资产内、校验实际内容完整且指向同一物理对象的相同摘要才能计一次；两份物理文件不能按摘要消重。跨项目不得泄露对象存在性。
- 先预留，落盘字节从该预留转换为已用量；**不能同时将同一批字节计入已用量和完整预留**。旧文件、新临时文件、元数据、候选转正式的共存峰值必须覆盖。失败且对象仍占空间时保留实际占用，不把全部预留释放成免费残留。
- 未证明归属且影响计量的对象为 UNKNOWN：报告、保留、不自动删除；该项目不接受新增预留，仍允许读取、下载和诊断。调低到已用加有效预留以下只显示超额、拒绝新增，不取消既有有效预留；调高不自动生成或重跑。
- 共享音频 scope 文档：音频字段及其专属元数据按原 `canonical` UTF-8 实际编码字节计入；改写必须额外预留整份新临时文档的实际峰值。不可把长期保留的非音频字段算成音频内容，也不能将共享物理文档对每个项目重复全额收费。

## 原写入路径与现状

各行“中断”是源码可见的边界或历史实验，不是本轮端到端恢复通过。`project_usage` 与 `MAX_PROJECT_BYTES` 当前仍是生产路径，隔离原型尚未接管。

| 入口与原 owner | 实际对象与当前归属证据 | 当前计量、预留和提交 | 中断后与本轮任务 |
| --- | --- | --- | --- |
| `app/api.py:2049` 旧 `POST /novels/{nid}/assets`，两 API 别名，`AssetLibraryService.create` | assets 根临时、`<id>.bin`、`<id>.json`；旧入口通常无 `_project_binding` / incarnation；创建后可再 `update_metadata` | 先原项目授权再直接 create，没有原 `project_scope` 或项目配额预留；旧 V1 读取依赖原可见性 | 直接补 Studio 绑定会让 V1 读取不可见，旧未绑定资产不能凭同名猜当前 incarnation；须由原 owner 提供容量上下文或明确关闭新增，读取保留。现为 **未接统一链**。 |
| `workspace.py:555` Studio 手工导入；`workspace.py:466,629` 模型/遮罩导入及 `creative/video_reference.py` | 原资产 File 正文、metadata 与临时；`_asset_scope` 经 scope key/branch/incarnation、asset lock 和原 project lease | scope 内使用 `project_usage` 按当前 metadata 大小及固定常量检查；`StudioStorageAdmission` 只看同盘空间和 64 MiB 安全余量，没有持久并发预约 | 本机锁串行不等于跨 owner 事务；预留、真实峰值和崩溃对账未接统一 owner。 |
| `production_execution.py` 生产音视频/图片结果、`text_assets.py`、`adaptation_assets.py`、`prompt_authoring.py` | 新资产正文/metadata、任务或 proposal 原回执 | 多处直接 `assets.create` 或自行使用固定额度；任务／审批 idempotency 与最终来源检查各归原 owner | 保留任务和原权限；不能因音频改动扩大图重跑。各实际写点须接同一额度，不得让任一原路径继续绕过。 |
| `AssetLibraryService.create`，`asset_library_service.py:251` | `mkstemp` 正文、flush/fsync、`os.replace` 到 `.bin`，随后 `_write_meta` 落 `.json`；scope binding 仅在原 scope 内存在 | 现有元数据 CAS、来源/幂等和媒体校验需保留；无项目持久预约 | 正文发布后元数据前的真实子进程退出曾留无索引 bin；现有 `project_usage` 可显示 0。此为旧 create 的具体缺口，不是历史恢复验收。新增链须有持久 operation 身份、实际文件归属与幂等补偿。 |
| `AssetLibraryService._write_meta` / `update_metadata` / `review_text_result` / `promote_owned` / `delete` / `restore` | 原 `.json` 与 `atomic_write` 的同目录完整临时文件；软删除正文仍存在 | 原版本/权限检查继续有效，但没有对 metadata 新旧共存预留；`atomic_write` 本身仅文件 fsync + replace，未证明断电目录持久 | 生命周期、lineage、relationships、审批均可能增长 metadata；不能只接 create 或按净变化预约。异常清理已知临时与硬中断残留分别处理。 |
| `experimental/audiobook.py:561,610` 合成/音频候选，`review:480`、`_approve_mix:516` | File scope 文档中 `audio_v2_mix_proposals` 的 Base64、专属 metadata 和复制的 history；`ExperimentalStore` 文件路径由 `[nid, scope]` 哈希决定 | 原 `store.transaction` 在 scope 锁中保存 canonical 整文档；用户确认候选字段按 UTF-8 实际编码量，临时预留整份新文档；现有纯测量、预检和诊断未接配额 | 旧候选行未绑定项目 incarnation；TaskCenter lifecycle 的 project identity 不能单独证明音频行归属。缺损/旧无绑定必须 UNKNOWN，不能用只读快照放行。审批先 scope、再资产 owner，跨 owner 无一次事务。 |
| `experimental/media.py:962` 原媒体候选 | 原 proposal 文档保存 Base64 等；此实现目前是图片候选，不能冒充音频 | 项目总额度若覆盖此写入，须通过同一计量 owner；不扩展媒体图重跑 | 项目其他写入口不接入即可能绕过上限；分项目/对象归属待原 owner 证明。 |
| `services/studio_audio_execution.py:919-960` 音频裁剪/转码 | 系统临时目录的 source、candidate，以及 FLAC/MP3 inspection 和 loudness 中间对象；可能不同卷 | 当前 `TemporaryDirectory` / inspection owner 与 ffmpeg 不向项目容量 owner 预留；实际文件有独立生命周期 | 普通返回清理不证明硬中断后的对象归属和残留已计量。不可关闭项目读取，亦不能借新依赖或模型调用替代实测。 |
| `experimental/comic_ora_staging.py`、`comic_timeline_handoff.py`、`project_forks.py`、`portable_projects.py` | 多资产、预分配 ID、原 receipt 与 staged/orphan 物理对象 | 既有流程有逐资产持久回执及部分恢复；部分仍使用固定项目容量 | 必须复用原 receipt，不能将一次批处理描述成单事务，不能让同一孤儿被旧回执和新预约重复计费。只做容量必要接线。 |
| `asset_query_index.py:183,225,321,389` 原查询索引 | assets 下 `.asset-query-index`、SQLite、staging/journal、cursor 相关文件；共享派生存储 | 原目录预算不是项目 quota；原检查允许未知普通文件，已有合成 extra table、trailing bytes 可通过查询 | 索引目录未知来源须可解释诊断、保留、不认领/不删除；不能简单忽略或当某项目的已验证文件。不得替换/重建 cursor 签名密钥以绕过 Windows 限制。 |
| `workspace.py:781` `GET .../studio/storage` | 当前可见 scope rows、trash 和固定 512 MiB 常量 | 返回值不是跨分支真实物理占用，也不是已确认项目额度；历史 status 和 `audio_scope_snapshot` 只观测并明确 audio row binding UNVERIFIED | GET 不迁移、不初始化持久设施、不改账本；需要对账须明确操作，不能以此只读观测扣费或放行。 |
| `collaboration_admin.py:66` 原 PROJECT 管理权限 | 原 session、membership、authorization、workspace/project identity | 已有项目管理权限 owner；仅 branch 的 `domain.write` 不等于 PROJECT 管理；主线适配器目前未接额度 | 上限设置只有容量和审批前置通过后开放，沿原 CAS/权限/审计和相同并发域；真实 PG 未验。 |

路径梳理还应包含 `app/api.py` 语音/图片导入、`services/audiobook_service.py`、`image_job_service.py`、`screenplay_service.py`、`video_assembly_service.py`，以及关系、lineage、prompt、voice、漫画审核等 `_write_meta` 间接调用。既有静态盘点 `work/audio-quota-write-path-audit.md` 不证明插件或动态回调已穷尽；接线时必须逐入口登记。API 两种别名按现有挂载合同分别测试，不把 File/Mock 证明扩写成浏览器或 PG 通过。

## 项目归属与共享文档决定项

`ExperimentalStore.key(nid, scope)` 和顶层验证绑定一个公开 `nid` 与 scope；目前没有证据证明同一合法文件同时具有两个不同顶层 `nid`，不能先假定事实。另一方面 `CreativeProjectStore` 明确保留同一 scope 中旧 incarnation 的 Creative 行，且通用 scope 文档可含音频以外 collection；TaskCenter lifecycle 只覆盖其指定 collection，不能为音频行背书。

**条件性待决定项：若核查证实同一物理文档包含多个项目或多个项目 incarnation 的可归属对象，持续保留的共享结构字节及改写期间整份临时副本由哪些项目承担、如何避免重复收费？** 当前合同只明确单个音频字段/专属 metadata 和整个临时峰值，没有为多项目共享结构给出分配方法。确认前暂停该实际共享对象的相关写准入；保留只读诊断和其他不依赖该规则的工作。不得根据行数、字符长度或任意比例推定，也不得默认跨项目复用免费。若实际验证范围内始终是单一有效项目，则在明确此条件下继续，不以不存在的多项目事实阻塞独立工作。

## M0–M7 验收及当前状态

| 阶段 | 可验收条件 | 基线状态 |
| --- | --- | --- |
| M0 路径/归属 | 按上表逐一核对实际 owner、真实对象、持久归属、预留、提交和中断分类；共享结构多项目规则缺失时明确决定项 | **本账本为源码与已有证据核对；多项目实际分配待证实/决定**。 |
| M1 统一计量与预留 | 原上传及全部相关写入口统一接原 owner；实际占用与预留余额明确转换；同机跨进程/跨分支竞争、同物理对象与两份文件、紧额度/元数据临时峰值、UNKNOWN 均实测 | **未接线/未验收**；隔离容量分支 `8099ee4263078d3f35a44acf4b8a9f6410242771` 的算术和 97 项定向结果仅证明受限原语；不能把它与主线误作同一提交。 |
| M2 提交与对账 | 用真实子进程分别在预留后、文件后、文档替换后和状态提交后中断；按 operation/identity 分辨已完成、待完成、人工 UNKNOWN；保留所有未证明文件 | **未实现完整跨 owner 协议/NOT_RUN**；某些隔离原语窗口有证据不代表整体通过。 |
| M3 审批竞争 | 最终提交时持有效原授权/会话、项目 incarnation、源/目标版本和摘要及有效额度；审批与编辑/取消/审批/调额/撤权/重建竞争，幂等或明确补偿 | **未闭环/BLOCKED 部分**；隔离审批实验默认关闭，受控并发红控仍存在；不得用重复读声称原子性。 |
| M4 共享文档与产物 | 在真实归属规则明确后，新建/修改/审批/拒绝/重开走同一容量链；WAV/PCM/FLAC 字节、解析、摘要和峰值；不同物理对象、失败残留、跨项目和撤权 | **纯字节测量与合成 File 音频有先前证据，生产容量接线/NOT_RUN**。 |
| M5 调额 | 上述前置通过后，PROJECT 管理权限、CAS、持久审计，调高/降低、重启/撤权和并发预约；低于用量加有效预约不删除、不取消 | **入口关闭/NOT_RUN**；主线权限适配与 project scope 检查不是可用调额。 |
| M6 最终冻结 | 实际可执行组件的 5 条验收线在同一 HEAD/tree 运行：物理字节、紧额度/崩溃、审批竞争、调额/超额读取、原消费者；命令、清单、前后源码哈希、模块来源、exit/timeout/原始日志；重叠不累计 | **本轮 NOT_RUN**。上一轮 `a79237f` File/Mock 40 文件组 426 passed/4 skipped，消费者 232 passed/76 deselected，固定来源见上轮报告；不能推导本轮完整容量通过。 |
| M7 交付 | 精确 HEAD/tree、阶段提交、变更范围、可恢复 bundle/patch、原始日志和分项状态；发布前另列目标与范围并获明确批准 | **待实施**；未知、未接线、未验、阻塞分别记录；不改 main、不上传、不强推、不 Release。 |

## 固定禁止项与证据边界

上一轮被自动安全审查中止的具体操作，是对 **隔离发布原语 PUBLISHING 修复版本** 的后续独立审阅任务：检查 branch/scope/request identity、原 create metadata、授权租约和响应丢失，并计划重跑原红控及真实子进程反例；该任务当时未固定新的目标 SHA，相关隔离前驱为 `bc316e1`，不是一个已获准的全仓库安全扫描。自动审查给出的理由为可能涉及网络安全风险，任务中止；本轮 **不得重试、转派、更换措辞或入口绕过**，依赖它的独立验收保持 BLOCKED。此前 Windows ACL/junction 探测被自动审批以 `blocked by policy` 拒绝、未执行；同样 BLOCKED / NOT_VERIFIED，不尝试替代命令。

本轮以后的验证要单独记录运行设备、真实环境和终态；未执行的 File/Windows、POSIX、PG、浏览器或真实模型分别标 NOT_RUN，不能用 Mock 或其他项目证据替换。上轮 F37、warm 首屏 409、Windows 资产游标签名密钥问题继续独立保留，不因本账本更新而关闭。历史 F37 和 warm 首屏根因目前为 UNKNOWN。
