# 音频资产历史与恢复：验收账本（M0 初版）

本账本的源码基线为 `b0c4d5bafb53fe02c8e4045c683d5579e8fe6c9d`，tree `a271c7c8921e9ba5a6d3227acda9ee5eb43d60c0`。除明确注明的历史证据外，以下是源码/合同检查，不是本轮测试通过证明。M0 冻结需要随独立复验更新；待决定事项不授权以宽松计费或跨项目共享填空。

## 合同来源及身份

- `docs/studio_workspace_identity_audio_history_contract.md` 定义当前资产 CAS、原 undelete、Timeline 与 Job 的区别，以及项目 incarnation 和原权限边界。`docs/delivery/STUDIO_V2_BACKEND_COMPLETION_LEDGER_20261028.md` A2、`studio-v2-unified-integration-20261027/LIMITS.md` 将完整音频资产历史恢复和项目历史计费列为未整合。
- 旧独立实现固定 `2e2fcb79209a3afc03dc7e443f5e1901ff233ee1` 的 `docs/audio_asset_version_history.md` 和 `docs/delivery/HERMIA_AUDIO_HISTORY_REVIEW_20261025.md` 为可复用设计及历史证据，不代表整支进入本基线。旧报告实证项目历史/失败 create 遗留未计费，以及原 query/cursor 兼容门禁 85 passed、1 failed；这些不是本轮结果。
- 原二进制和元数据 owner 为 `app/services/asset_library_service.py` 的 `AssetLibraryService`；Studio 项目与 incarnation 为原 `CreativeProjectStore` 及原 scope/owner lease，Studio 权限走既有 workspace/Host guards。音频 ProductionJob 是任务回执；Canvas/Timeline 历史分别是布局/编辑定义，均不能代替单资产历史。
- 资产 ID 标识同一资产；当前 `version` 是 metadata CAS revision，现有受支持入口没有原地替换已有资产二进制的新接口，新的生成/导入通常为新 ID。旧方案区分历史 sequence、原 CAS revision、canonical metadata digest、binary SHA-256 和 record digest；它们不可互换。历史绑定实际 project scope、branch、incarnation、资产及来源；私有候选的历史授权不能因当前资产公开而自动扩大。
- 现有 `update_metadata` 在允许字段或继承来源发生变化时递增当前 revision，无变化不递增；promotion、lineage/relationship、delete、undelete 等实际写入口须逐个检查是否保留历史。删除是软删除；原 restore 仅撤销软删除并递增 CAS，保持 ID 与字节。尚无通用音频二进制历史入口；内部 lineage history 不是完整资产历史。
- AUDIO Timeline schema 3 的恢复只恢复编辑定义为新的 Timeline 版本，要求固定 Asset ID/version/digest/kind 仍是当前可用正式资产；不会回滚素材或生成媒体。固定 pin 不得静默改指向。具体引用行为仍须按实现逐入口验证。

## 当前接口和 owner 边界

`GET /api[/v1]/projects/{nid}/studio/assets/{aid}` 与 `/download` 为当前资产读取；`POST .../assets/{aid}/restore` 是原 undelete，闭合模型仅接受 `expected_version`，不能增加历史目标后沿用旧含义。`GET .../production-contracts/runtime` 将 `audio_asset_history.version_history_read` 和 `version_restore` 标为 `UNAVAILABLE`。应用在 `app/main.py` 挂载 `/api` 与 `/api/v1`；新能力接线和两种入口的实际行为均须在固定源码验证。

旧 `2e2fcb` 曾实现 history list/detail/download 与只读 preview，confirm/resolve 授权后返回 `409 AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE`，尚无成功恢复；不能把那些旧路径当成本基线已挂载。旧实现的 store/authority、访问及反例可逐项审查复用，不能另设资产或权限 owner，也不能整支覆盖当前共享入口。

`IndependentWorkspaceService` 与 `AssetLibraryService.project_usage` 是原项目容量准入/统计路径：同 scope/branch/incarnation 的当前资产 size 计入，含软删除资产；原上限为 1,000 资产和 512 MiB。`StudioStorageAdmission` 检查同资产文件系统空闲空间并保留 64 MiB；这不是项目预约或跨应用磁盘预留。当前统计扫描可读的当前 metadata，历史、prepared、无可证归属残留不在其已证实范围；不能将该扫描等同实际存储总量。存储展示的当前行聚合与服务端 admission 还需分别核对权限与占用语义。

## 待决定与冲突

1. **恢复的采用/审核关系**：旧音频历史合同要求通过原 Asset owner 建立一个新的未审核 candidate，历史审核只作追溯，不能自动采用；本轮任务要求采用已有历史版本并生成可追溯的新当前版本。两者并非自然等价。用户已决定：恢复确认后直接生成可追溯的新当前版本，保留旧历史。不得伪造 Job、旧审核或绕过权限；写端仅在版本、计费、恢复和最终授权合同达到要求后开放。
2. **项目配额与引用/物理量（用户 2026-10-28 已决定）**：默认 512 MiB，有项目管理权限者可显式调整并持久化；当前、历史、候选、临时/prepared 及可归属失败残留按实际存储字节计入，同一资产同摘要对象只计一次，逻辑引用量单列，无法证明归属的孤儿只报告、不自动删除。调额不改变计量、去重、预留或对账规则；额度低于已占用加有效预留时显示超额，保留内容与读取下载，阻止新增预留但不取消已获预留；调高只重新检查额度，不触发模型或重跑。调额和预留必须共享并发保护并覆盖重启、撤权和竞争。实现和验证仍待完成；不得因此宣称当前 owner 已满足此规则。
3. **迁移触发**：旧分支合同的下次修改惰性捕获与本轮“迁移必须显式操作”不同；按本轮要求，GET 不迁移，迁移只能显式执行。旧资产先前未捕获的历史是缺口，不得从 Job、时间戳或 Timeline 补造。

容量规则补充：512 MiB 为默认值，项目管理员仍可调整。同一资产相同摘要仅在内容完整性已核验且实际复用同一个物理对象时只计一次，两份物理文件必须分别计量；写入须先预留，失败后仍占空间的对象继续计费，不能全部释放预留。启动后先对账再准许新增写入。无法证明归属的孤儿只报告、不自动删除；若影响项目用量判断，该项目暂停新增写入，仍允许读取和诊断。项目上限须覆盖同一 incarnation 的各分支，不能将各分支当成独立项目额度。

共享项目文档中的待审音频：持久占用计入音频字段及其专属元数据的实际编码字节；文档写入时还须预留整份临时文档的实际峰值。此决定不把非音频字段长期计入音频占用，也不授权忽略临时文档或失败残留。

## 环境与能力状态（本轮基线）

| 组合 | 实现边界 | 本轮验收 |
| --- | --- | --- |
| Windows + File project + File Asset，local | 原 owner 和当前读取存在；历史/恢复未完整接入 | **NOT_RUN**；上一轮 File 合成读取、音频混音及其固定 SHA 证据不等同本轮闭环 |
| Windows + File project + File Asset，协作 | 必须原 session、membership、branch、feature 和 incarnation guards；不能推断所有写入口已满足 | **NOT_RUN** |
| PostgreSQL project + File Asset，local/协作 | 项目使用原 PostgreSQL owner，资产仍为原 File owner；无需虚构 PG Asset store | **NOT_RUN**；可用性待检查，源码存在不是通过 |
| POSIX、跨机器/分布式共享文件系统 | 各环境及锁语义未证明；同机文件锁不能外推为分布式锁 | **NOT_RUN / 不承诺跨机器 exactly-once** |
| Windows ACL/junction 安全反例 | 上一轮隔离探测被自动审批以 `blocked by policy` 拒绝，命令未执行 | **BLOCKED / NOT_VERIFIED**；不得更换入口绕过 |
| 真实模型、GPU、浏览器、托管 CI | 本轮无需真实模型及前端重做；若未运行不得从服务或 HTTP 测试外推 | **NOT_RUN** |

## 可执行验收矩阵

每行完成时记录精确源码 SHA/tree、环境、测试清单、完整命令、退出码、超时与原始日志，并记录冻结前后源码哈希及模块来源。独立组与组合组有重叠不相加。测试未到终态或仅有 XML 不算通过。所有夹具使用脱敏合成数据。

| 阶段 | 必测行为及通过条件 | 基线状态 |
| --- | --- | --- |
| M1 不可变写入 | create 和全部原 metadata/promotion/lineage/relationship/delete/undelete 写路径，连续变更、无变化、实际文件与 digest/media 元数据一致、历史不可覆盖；同内容处理遵循已确认规则；并发 CAS 仅赢家提交；文件缺失/损坏/中断/重试无虚假成功 | **未整合 / NOT_RUN** |
| M2 容量 | 原 quota owner 对可归属已有、历史、候选、prepared、临时项预检与并发预留；两个单独可容纳而总和超限的写入最多容许额度内的提交；成功提交、失败/取消释放、重启对账；重试和恢复不重复扣费；无跨项目存在性泄露 | **规则待决定，未实现 / NOT_RUN** |
| M3 兼容/迁移 | 旧资产 GET 不写历史、不初始化锁、不改账本；显式迁移前后校验字节摘要与权限，重复操作幂等、CAS 冲突安全；缺字段、损坏索引、缺文件、未知格式拒绝或按既有合同读取，保留失败证据与可恢复办法；旧占用不得免费新增 | **旧当前读取部分存在；显式迁移未整合 / NOT_RUN** |
| M4 预检/确认/恢复 | 确认绑定 asset/project/scope/incarnation、current revision、目标 history identity/digest 和全部结果参数；重复请求、响应丢失、并发恢复/编辑；来源或目标变化、旧确认、撤权/会话 ABA、项目重建、伪造摘要、跨项目、缺文件与坏内容均 fail closed；提交窗口复核先于可用候选落盘；无需模型调用 | **未开放 / NOT_RUN；用户已确认直接生成新当前版本** |
| M5 崩溃协议 | 文档写明文件、版本索引、当前指针、quota/operation receipt 的真实提交顺序及原子边界；真实子进程在预留后、文件后、登记后、当前提交后中断并重启，判定已完成/未完成/补偿；不盲目重做或删除其他引用、未知归属孤儿只报告 | **未实现完整协议 / NOT_RUN** |
| M6 产物与查询 | 由原服务导入/生成合成音频，按实际能力覆盖 WAV/PCM/FLAC，测字节、摘要、解析、时长、采样率、声道与下载；列表/详情/当前/恢复前后重开及进程重启一致；固定/当前引用语义明确；两个 API 前缀分别实测 | **NOT_RUN**；不引入转码依赖或真实模型 |
| M7 独立与冻结 | 不同检查者编写并运行并发配额、幂等、源变化、旧确认、撤权、重建、缺文件、坏摘要及落盘窗口反例；实际修复保留撤修失败控制；固定源码分别跑音频专项、原音频/资产/任务/导出回归、IMAGE 回填/受限重跑、权限/只读/恢复反例，再运行适当组合组 | **NOT_RUN** |
| M8 交付 | 逐项标实现/未接线/未验收/不支持；列接口、实际存储平台、各固定 SHA 原始证据、提交与回退点；功能缺失、环境未验和已知缺陷分别登记 | **待交付** |

独立保留问题：历史 F 的 37 个拒绝和 warm 首屏间歇 409 根因 **UNKNOWN**；Windows 资产游标签名密钥等价安全实现未完成。不得因音频结果改变这些状态。任何公开上传前需另列目标分支及代码、测试、脱敏证据范围并取得明确批准；不改 main、不强推、不创建 Release。
