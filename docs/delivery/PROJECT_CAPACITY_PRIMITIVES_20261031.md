# 项目容量owner：批次 2 第一部分（计量/预留/提交/对账原语 + 只读诊断）

本文件记录批次 2 第一部分实现。**这不是项目容量闭环完成声明**：统一容量账本与预留/提交/对账原语已实现并有独立测试，但尚未接入任何生产写入口，所有既有写门（`PROJECT_CAPACITY_WRITE_UNAVAILABLE`、`AUDIO_CAPACITY_WRITE_UNAVAILABLE`）保持关闭，`admission` 仍为 `UNAVAILABLE`。

## 1. 新增代码

| 模块/入口 | 内容 |
| --- | --- |
| `app/project_capacity_measurement.py` | 项目归属根目录的**只读逻辑占用测量**：`st_size` 逻辑长度、同物理对象（同 `st_dev`/`st_ino`）只计一次、同摘要不同物理文件分别计数（从不按 digest 去重）、reparse/符号链接/非普通文件/不可读目录记为 UNKNOWN 且不跟随、结果显式标注 `allocated_storage_bytes=UNKNOWN`（未测分配量/稀疏/压缩）、不删除/不认领 |
| `app/project_capacity.py` | 持久容量账本 `project-capacity/1`：严格 schema 校验、损坏账本 fail-closed 不覆盖、跨进程 `workspace_mutation` 锁 + `atomic_write`、写后回读验证；`reserve`（先预留、并发串行、UNKNOWN_BLOCKED/incarnation/超限拒绝）、`commit`（实际落盘 bytes 从预留转换为已用，不得超过预留峰值）、`release`、`reconcile`（按实际测量校正已用、记录 UNKNOWN 阻塞）、`adjust_limit`（必须传入匹配 project+incarnation 的原管理 lease、CAS version、持久审计）、预留 TTL 过期回收、审计上限 32 条、`peek` 只读快照 |
| `GET /api[/v1]/projects/{nid}/studio/capacity` | **只读诊断**：返回逻辑测量、账本状态/快照、默认/生效额度、`admission=UNAVAILABLE`、`write_gate`；绝不初始化账本/锁、绝不预留、绝不开放写门；两种 API 别名结果一致；纳入 `is_independent_studio_route` 的精确 GET 允许清单 |
| `IndependentWorkspaceService.capacity_diagnostics` | 诊断实现：测量项目自有根 `novels/<nid>`；若账本文件存在则只读 `peek`；账本缺失/损坏分别如实返回 `NOT_INITIALIZED`/`UNAVAILABLE`，不创建文件 |

## 2. 账本规则与账本缺口映射

| 容量账本要求 | 本部分实现 |
| --- | --- |
| 先预留，落盘后预留转已用；不得重复计 | `reserve` → `commit(actual ≤ reserved)`；commit 后预留整条移除、只增加实际落盘量 |
| 失败但占空间保留实际占用 | 调用方可对失败残留单独 `commit`/`reconcile`；本模块从不因失败自动释放已提交 bytes（释放只针对未提交预留） |
| UNKNOWN 对象只报告、保留、不删除；该项目拒绝新增预留、读取保留 | `reconcile(unknown_objects>0)` → `blocked=True`，`reserve` 固定拒绝 `PROJECT_CAPACITY_UNKNOWN_BLOCKED`；测量模块不含删除/认领代码 |
| 调低额度不取消既有有效预留，只显示超额并拒绝新增 | `adjust_limit` 后 `state=OVER_LIMIT`，既有预留保留，`reserve` 拒绝 |
| 调额需原管理权限、CAS、持久审计 | `adjust_limit(lease=...)` 必须匹配 `{novel_id, incarnation}`；`expected_version` CAS；审计 `LIMIT_CHANGE` 持久 |
| 先对账再准许新增 | `reconcile` + `reconciled_at` 持久化；**尚未**在写入口强制“未对账不得预留”的门（见第 4 节） |
| 同物理对象按对象一次、两个物理副本不可按摘要合并 | 测量模块 `SAME_DEV_INO_COUNTED_ONCE` + `NOT_PERFORMED` digest dedupe，测试覆盖硬链接与同内容双文件 |
| 损坏/不可读状态不得报告成功 | 账本严格校验 + 写后回读；测试覆盖损坏账本不被覆盖 |

## 3. 测试与证据（Windows · Python 3.11 · 合成临时目录）

| 范围 | 结果 | 日志 |
| --- | --- | --- |
| 容量原语（预留/提交/释放/TTL/UNKNOWN/损坏/CAS lease/跨进程并发/杀进程/测量） | **21 passed** | `Validation/backend-finalize-20261031/batch2-capacity-tests.log` |
| 只读诊断（两别名、未初始化、持久账本、损坏账本、跨项目 403、路由允许清单） | **6 passed** | `Validation/backend-finalize-20261031/batch2-capacity-diagnostics.log` |
| 容量相邻回归（storage、asset query/cursor、quota authority、capacity projection、shared index、physical observation、audio scope/quota observation） | 见 `batch2-capacity-regression.log` | 同目录 |

覆盖的反例：超额预留、两次单独可容纳但合计超限、commit 超过预留、释放不释放已落盘字节、跨进程 4 竞争者仅 2 成功、预留进程退出后 TTL 到期回收且不计费、UNKNOWN 阻塞新增、损坏账本 fail-closed 且不覆盖、低额度下既有预留保留、CAS/lease 不匹配拒绝、测量不跟随 reparse 且前后目录内容不变。

## 4. 明确未完成（下一批继续）

1. **写入口接入**：`ProjectCapacityLedger` 尚未接入任何 `assets.create`/手工导入/模型产物/音频/共享文档/导出等真实写入；手工导入、旧上传、音频写门仍全部关闭，`admission` 仍 `UNAVAILABLE`。
2. **项目归属扫描范围**：当前测量只覆盖项目自有根 `novels/<nid>`；`assets/` 下按 `_project_binding` 归属的正文/metadata、临时/失败残留、共享 scope 文档、其他 owner 目录尚未纳入。接入前必须逐入口登记实际对象。
3. **启动对账强制门**：账本支持 `reconcile` 并记录 `reconciled_at`，但尚无“启动必须先对账才允许 reserve”的强制路径；需与各写 owner 的初始化/重启路径一起接线。
4. **审批/授权/版本竞争**：`adjust_limit` 已绑定原管理 lease 与 CAS，但尚无 HTTP 调额入口与审批竞争测试；写入门还需与项目 incarnation、撤权、重建并发测试。
5. **U16 RUNNING claim 提前写**：`safe_batches.py` 相关路径尚未证明“关闭门先于 RUNNING claim/预留”，也未加崩溃恢复测试（账本缺口原样保留）。
6. **跨 owner 原子性**：账本与 Asset/共享文档/Job 的事务不是一个数据库事务；需要提交顺序、补偿与真实子进程崩溃窗口测试后才能宣称崩溃恢复。

## 5. 回退

新增模块与路由均为增量：`git revert <本批提交>` 可完全移除；既有 `GET /studio/storage`、`project_usage`、写门与所有原测试未改动。

## 6. 批次 2 第二部分：资产归属测量 + U16 门/claim 顺序证据（2026-10-31 续）

### 6.1 新增 `app/project_capacity_attribution.py`

- 只按原资产 metadata 的精确 `novel_id` 归属；读取根目录有界 metadata（严格 JSON、单文件 1 MiB、扫描上限/截止时间），实际计 metadata 文件字节 + `<id>.bin` 正文实际字节，而不是 metadata 自报 size。
- 同物理对象（`st_dev`/`st_ino`）只计一次；不同物理文件即使内容/摘要相同分别计。
- 其他项目 metadata 只累计计数、**不返回任何 id/路径**；损坏/缺正文/不可读分别计数；reparse point 不跟随；共享派生目录（`.asset-query-index` 等）不扫描、不认领；只读、不删除。
- 读取 `assets_attribution` 已并入只读诊断 `GET /studio/capacity`：`combined.logical_bytes = 项目自有根 + 本项归属资产`，`allocated_storage_bytes` 仍为 `UNKNOWN`，`admission` 仍 `UNAVAILABLE`。

### 6.2 U16 关闭门先于 RUNNING claim / 崩溃恢复（合成 File 证据）

`app/experimental/safe_batches.py` 当前实现（本批复核，非本轮新增代码）：`confirm` 与 `dispatch` 在创建 batch claim、broker reservation、RUNNING/attempts 之前调用 `_require_stage_write_capacity`；`RUNNING` 且 claim 不在本进程 ACTIVE 集合时公开投影为 `UNKNOWN` + `BATCH_INTERRUPTED_RECONCILIATION_REQUIRED_NO_REPLAY`，只能由原执行器/`stop` 处理，不自动重放。本批新增 4 个定向测试覆盖：
1. 中断的 RUNNING/claim 投影为 UNKNOWN、attempts 保留、limitations 含“必须在原执行器对账”；
2. `stop` 将中断 RUNNING 改为 CANCELLED 且 claim 清空、attempts 不重放；
3. 关闭门拒绝时没有 claim/RUNNING/attempts/receipts/task_id/reservation_id，磁盘内容不变；
4. confirm 门拒绝时 batch 仍 PREFLIGHT、confirmed=False、items PENDING、无 claim。

边界：这是 File 合成顺序/恢复证据，不是 broker/真实授权/真实模型或跨机器证明；真实 PostgreSQL 下同一顺序测试仍归 NOT_RUN。

### 6.3 本部分测试

| 范围 | 结果 | 日志 |
| --- | --- | --- |
| 资产归属测量（归属、聚合计数、同物理对象、扫描上限、只读、诊断合并/跨项目不泄漏） | 6 passed | `Validation/backend-finalize-20261031/batch2-capacity-attribution.log` |
| U16 门先于 claim + 崩溃恢复（新增 4 项，连同既有 U16 套件） | 24 passed | `Validation/backend-finalize-20261031/batch2-u16-crash.log` |
| 容量原语+诊断+归属全组 | 33 passed | 同上 |

### 6.4 仍未完成（不变项）

写入口接入（所有容量/音频写门仍关闭）、启动对账强制门、调额 HTTP 入口与审批竞争、跨 owner 迁移/临时峰值预留、真实 PG/崩溃窗口与全产品验收仍 NOT_RUN。

## 7. 批次 2 第三部分：显式对账与调额 HTTP 入口（2026-10-31 续）

- `POST /api[/v1]/projects/{nid}/studio/capacity/reconcile`：显式对账操作（不是 GET、不写门）。服务端测量项目自有根 + 归属资产后，在**原 project owner lease** 下把 `used/unknown/incarnation/reconciled_at` 写入容量账本；返回测量明细与账本快照；`admission` 仍 `UNAVAILABLE`。未知/不可读/缺正文对象记为 UNKNOWN（阻塞后续新增预留），不删除、不认领；移走问题对象后可再次对账恢复 `OK`。
- `PUT /api[/v1]/projects/{nid}/studio/capacity/limit`：调额必须同时满足原 project/incarnation **management lease**（`project_management_lease`，本地模式原 workbench 权限、协作模式原成员/授权/拓扑/incarnation 观察）、ledger **CAS `expected_version`** 与持久审计 `LIMIT_CHANGE`（记录 previous/limit/incarnation/actor）。未对账项目拒绝（409 `PROJECT_CAPACITY_NOT_RECONCILED`）；降低到已用额度以下只把状态标为 `OVER_LIMIT`，不删除内容、不取消既有有效预留；无效请求体 422。
- 账本快照增加 `ledger_version`（只读观测，供 CAS 使用）；容量诊断 GET 同时返回该版本，但仍不初始化/不写账本。
- 两条路由均加入 `is_independent_studio_route` 的精确方法/路径允许清单（GET `/capacity` 不变，POST 仅 `/capacity/reconcile`，PUT 仅 `/capacity/limit`）。
- 测试：`tests/test_project_capacity_admin_api.py` 11 项（两别名、对账初始化/UNKNOWN 阻塞与恢复、CAS 陈旧版本、审计、降低额度 OVER_LIMIT、未对账拒绝、422、非项目 owner 409、非管理 token 拒绝、精确允许清单）；容量全组 44 passed；与 U16/storage/asset-query/authority 组合回归见 `batch2c-combined.log`。
- **仍未完成**：内容写入路径仍未接入容量预留/提交（所有容量/音频写门保持关闭，`admission=UNAVAILABLE`）；启动时自动对账尚未强制；跨 owner 临时峰值/失败残留/崩溃窗口未实现；真实 PostgreSQL 下同样测试仍 NOT_RUN。

## 8. 批次 2 第四部分：内容写入口容量预留/提交接线（flag 保护，2026-10-31 续）

新增 `app/project_capacity_admission.py` 与 `ENABLE_PROJECT_CAPACITY_ADMISSION`（默认 **false**）：

- 默认关闭时，Studio 手工上传仍返回既有 `503 PROJECT_CAPACITY_WRITE_UNAVAILABLE`，与历史关闭测试逐字一致。
- 显式开启后，`POST /api[/v1]/projects/{nid}/studio/assets` 走既有原资产 owner 写入，但写前必须由容量编排完成：测量项目根 + 归属资产并 `reconcile` 基线 → 存在 UNKNOWN/不可读 metadata/缺正文/根目录崩溃残留时拒绝（`PROJECT_CAPACITY_UNKNOWN_BLOCKED`）→ 预留 `incoming + 1 MiB metadata/staging 峰值`，TTL 900s → 写入成功后按实际落盘 `bin+json` 字节 `commit`，失败先重新对账把已落盘残留计入已用再释放预留。
- 幂等重试不重复计费；额度不足 409 `PROJECT_CAPACITY_EXCEEDED` 且不产生资源；损坏账本 fail-closed（409 `PROJECT_CAPACITY_LEDGER_UNAVAILABLE`，原文件不被覆盖）；并发导入在额度紧张时串行化，仅一个落地/或全部记账正确。
- `project_capacity_attribution` 增加根目录非 json/bin 普通文件（崩溃残留）的聚合计数 `unattributed_files/bytes`，作为 admission 的 UNKNOWN 阻塞信号；不返回、不删除。

验证（Windows · File 合成）：新增 8 项测试（flag off 关闭、正向往返与只计落盘、幂等、超额、未知残留阻塞/恢复、损坏账本、并发紧张额度、关闭时不写账本）全部通过；连同既有手工上传关闭/legacy/modelref/容量/U16 套件组合 **104 passed**。

边界：仅 `studio/assets` 手工导入接入了 flag 保护的 admission；模型引用、音频/共享文档、导出、图片/视频产物等写入口仍未接线（仍关闭）。flag 默认 false，未改变任何现有生产行为；真实 PostgreSQL/浏览器/真实模型未运行。

## 补充：孤儿音频历史目录的归属（2026-10-31 续）

对账扫描 asset 元数据之外，还会对 `assets/.audio-history/<asset_id>` 中**未被当前项目元数据匹配**的目录做有界归属探测：只读取 `records/` 下第一个小体积不可变记录（≤256 KiB，拒绝 reparse/非普通文件/超限/不可解析），若其 `metadata.novel_id` 或 `_project_binding.novel_id` 等于本项目，则整目录按 `unattributed_files/unattributed_bytes` 聚合计数（不暴露路径/资产 id），reconcile/admission 的 UNKNOWN 判定会阻塞新增写入；其他项目目录不归属，无不可变记录（只有 blob）或内容歧义的目录不被任何项目认领，避免跨项目误报。对应测试 3 项，容量组回归 70 passed。

## 补充：AssetLibraryService.create 全调用方统一接入（2026-10-31 续）

`ENABLE_PROJECT_CAPACITY_ADMISSION` 开启时，容量 admission 从“仅 Studio 手工导入路由”下沉到共享资产 owner `AssetLibraryService.create`：所有经由该 owner 的原始资产写入（Studio 手工导入、模型 clay 参考、手工遮罩、视频参考帧、生产任务产物、prompt authoring、comic/portable/媒体/音频服务等 16 个调用点）都会先 reconcile 原始 owner 计量、拒绝 UNKNOWN、预留正文+元数据峰值，成功后按实际 `bin+json` 落盘字节 commit；失败先 reconcile 残渣再释放。手工导入路由自身已有 admission，通过内部参数 `_capacity_admitted=True` 避免双重计费。

边界仍保留：非资产 owner 的项目文件、导出、共享文档、审批/调额竞争、启动自动对账门与真实 PG/崩溃窗口不在本批；flag 默认关闭，默认行为不变。

测试：`tests/test_project_capacity_create_coverage.py` 5 项（直接 create 计量/幂等不重复计费/失败释放且无残留/超额写前拒绝/默认关闭不建账本）；容量组回归 **75 passed**。

## 补充：历史写入的启动对账门（2026-10-31 续）

`AssetLibraryService` 在模块导入时记录进程启动时间。音频历史写入的容量预留（双 flag）在读取账本 `reconciled_at` 时要求它**不早于本进程启动**，否则返回 `AUDIO_HISTORY_CAPACITY_NOT_RECONCILED`——重启后旧进程留下的“已对账”账本不能直接用于新的历史写入；必须先显式 reconcile（或由 admission 写入重新对账）。这对“启动后先对账再准许新增写入”的合同补上了历史写入这一路径；admission 路径本来每次写前 reconcile，天然满足。进程内 reconcile 之后的写入不受影响；系统时间回退按 fail-closed 处理。

