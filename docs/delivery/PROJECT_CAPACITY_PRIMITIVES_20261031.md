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
