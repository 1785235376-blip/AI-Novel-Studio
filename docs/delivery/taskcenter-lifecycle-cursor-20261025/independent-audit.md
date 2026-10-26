# TaskCenter 原 scope owner epoch：独立对抗审计与接口门槛

审计基线：`1587b57791cbdc3e46f0c09fedea83072e6a8d28`。  
固定 tree：`826d0b2917720dacf72ecbccbf3f961b9172f5b9`。  
结论：`M0_EXECUTOR_BLOCKED / READ_ONLY_AUDIT_ONLY / TESTS_NOT_RUN`。

本报告区分已从源码确认的事实、待实现设计风险和未来必须运行的反例。
没有实现或交付新的生产组件，没有迁移文档、修改业务存储或移动分支。
以下“必须通过”均为验收条件，不能读成已运行通过。

## 1. 执行器核实

本工作单元独立调用最小命令 `Get-Location`，在创建进程之前返回：

`exec_command failed: CreateProcess ... helper_unknown_error: setup refresh had errors`

当前工具清单没有 `environment_status` 工具。没有改用 Node 宿主、用户电脑、
Actions、旧任务环境或新 Codex 任务。单进程、双进程、强杀、回滚、性能、
真实 PostgreSQL、Windows、HTTP 运行验证全部 `NOT_RUN`。

固定 tree 完整递归返回 4710 项，`truncated=false`，仅有根 `AGENTS.md`。
已读取根规则。本文只使用固定 ref 的 GitHub 源码。

## 2. 已确认源码事实

| 位置 | 固定基线事实 |
| --- | --- |
| app/experimental/store.py | File scope 文档位于 root/experimental_v1/<scope-key>.json；key 由 nid 与 scope 的 canonical JSON 摘要产生，不是生命周期身份。 |
| ExperimentalStore.empty/_file_read | 物理缺失返回纯空文档；与真实存在但 collections 为空的 legacy 文档可能有相同 JSON 内容。 |
| ExperimentalStore.transaction | File 在原 experimental:<key> 跨进程锁内读取、yield、validate；最终 canonical 与初始不同才 atomic_write。当前没有 owner epoch。 |
| ExperimentalStore.read | read 不写文档；同实例同线程 active transaction 内返回未提交文档的 deepcopy。 |
| ExperimentalStore.transaction 的 PostgreSQL 分支 | 原事务内 INSERT ... ON CONFLICT、SELECT ... FOR UPDATE；更新 document 时一并 revision+1；没有独立提交新 owner 的必要。 |
| app/creative/project_store.py | transaction 采用 scope → project 顺序，并在底层 scope 提交结束前保留 project lease；_view deepcopy 顶层未知字段。 |
| CreativeProjectStore.source_lease | 使用 raw scope transaction 作为只读 lease，并拒绝 canonical 变化；不能因进入 transaction 就自动 bump epoch。 |
| app/project_retirement.py | File retirement 退役 novels/nid 目录及 scope/auth 关系，不清理 root/experimental_v1 scope 文档。 |
| app/storage.py | atomic_write 先同目录临时文件写入、flush、fsync(file)，再 os.replace；没有 fsync(parent directory)。 |
| app/backup_restore.py | 原 restore_directory 仅恢复到不存在的新目录，但 copyfile 原样复制备份字段，不重新生成 scope/project epoch。 |
| scripts/restore.ps1 | 旧脚本允许显式 -Force 后原样覆盖/合并文件，亦不会重建生命周期字段。 |
| app/repositories/file/mutation_coordinator.py | 原锁按 resolved root + key 协调；同线程重入会复用 lease，避免重复 OS 锁。 |

另一审计单元报告已读取固定 ref 下全部 157 个 app/experimental Python 文件，
检出 54 个直接 transaction 使用文件，未发现该目录内另一个 scope 文档物理写入口。
该全目录扫描清单由该单元负责；本工作单元没有冒称独立重新穷举了这 157 文件。
我独立读取并审查了上述原 owner、原子写、project lease、retirement、备份恢复和
generation owner 适配源码。动态扩展、外部脚本、直接文件/SQL 写入、猴子补丁与
未审计的其它目录 writer 无法从这一组源码穷举证明不存在。

PostgreSQL 另有现存区别：transaction 会先 INSERT ... ON CONFLICT；物理 missing 的
scope 即使 callback 最终无业务改动，也可能提交一个空 row。不能把 File 分支的
no-op 零文件写入外推到 PostgreSQL source_lease。新纯观察端口应调用 read 而非
transaction；将来若支持 PostgreSQL，首次初始化/legacy 规则必须另行验证。本轮
没有修改或验证该行为。

## 3. 确定风险一：跨实例同线程嵌套没有被原 guard 拦住

`_local.active` 属于每个 ExperimentalStore 实例。原 workspace_mutation 在
同 root、同 key、同线程中可重入，因此：

1. s1.transaction 读取 A 并持有 scope lease。
2. 相同 root/key 的 s2.transaction 仍可进入，读 A，提交 B。
3. s1 继续用旧副本提交 C，可以覆盖 s2 的提交。

原 guard 只拒绝同一实例的 nested transaction。跨进程锁本身不能证明所有
跨实例调用均按“不重叠事务”串行。此结论来自静态调用和锁结构，尚未动态执行。

若 epoch 仅取“开始时计数 + 1”，两次成功提交可复用计数，不能宣称提交严格单调。
每次 commit 随机 nonce 可避免该计数碰撞，但不能修复旧副本覆盖新数据。
候选接口至少需要以下一项经原 owner 实现并验证：

- 原 scope 锁内提交前重读物理原文档/metadata，CAS 拒绝与初始原文档不同的提交；
- 或在原协调机制内对同 root/key 的跨实例嵌套写统一拒绝。

不能用另一个平行业务存储记录“最近 epoch”补丁。特别要测试 s2 已提交、s1 后续
rollback 的情况，以及 source_lease 内跨实例写入：活动副本 canonical 未变化，
不等于磁盘从未被可重入 writer 改变。

## 4. 确定风险二：旧 scope 文档会跨同 ID 项目重建存留

项目 marker 位于 novels/nid，scope 文档位于独立 experimental_v1。
删除并重建相同 nid 后，旧 scope 文档仍可能存在。

仅将 cursor 绑定“本次取得的新 project incarnation”可以拒绝旧 cursor 续页；
它不能阻止新第一页从原 reader 读到仍留在旧 scope 文档中的任务。
scope-key 摘要、当前 slug、文件时间或新 marker 都不能证明这些旧行属于新项目。

候选 source lifecycle metadata 必须与原 project incarnation 建立可验证绑定。
已有无绑定 legacy 文档的显式迁移也不能只凭“有当前写权限 + 当前 nid 相同”
就宣称旧数据来自新实例。来源无法证明时，受保护 cursor 模式必须拒绝；
旧 offset 是否保留原行为应独立说明，不能把它写成完成旧历史归属迁移。

原 project identity 必须来自实际 repository owner，不能从 settings 猜 root/数据库，
也不能为查询创建 marker。既有 GenerationIdempotencyAuthority 的实际 owner 核实
方式可以作为接口复用参考，不能调用其 capture_new 替只读查询补建身份。

## 5. 设计风险：scope-wide epoch 会成为隐藏活动侧信道

如果一个 scope 文档总 epoch 随所有 collection 的写入变化，单独选择
semantic_import 的 cursor 也会被未选 source 或被拒 reader 的更新失效。
即使错误没有 reader 名称，调用者仍可通过重试结果观察其它来源的活动。

同一原子文档内的 per-collection revision/nonce 是缩小影响面的候选，尚非通用证明：

- global document revision 仅用于原 owner 内部提交 CAS，不应出现在 cursor 绑定、
  public coverage 或续页验证的无关比较中。
- 只绑定已经选择且本次经原 reader 授权的 source 证据，不能返回整个 collection
  epoch 表、拒绝列表或内部变更计数。
- 若所选 collection 本身含逐行隐藏数据，collection-wide epoch 仍会因隐藏行变更
  而失效。此时必须由原 owner 提供 visibility-aware observation，不能由中央猜。
- 对 local semantic_import，可在原 DomainService 对同 scope 全行校验且不做逐行
  隐藏这一前提上继续评估；不能外推为 exports、review_inbox 或全部 17 authority
  已有同样证明。
- 即使 token 没有绑定 global revision，第二次读取后若顺手要求 global revision
  未变，仍会保留上述侧信道。验证应比较相关 source 观察，不是全 scope 的活动。

必须反例：在相同已授权 semantic 投影的两组数据中，仅未选或 403 source 的
collection 发生新增、删除或 ABA；semantic cursor 的公开结果/错误应保持一致。
所选 source 内隐藏行的变更也应单独构造；没有原可见性证据的模式继续不支持。

## 6. 候选原 owner 端口的最小不变量

这些是接口门槛，不是已决定的实现：

1. 读取观察纯只读。物理 missing 不建文档，不生成假 incarnation；不能用
   empty(nid,scope) 中即时生成 UUID 的方式冒充一个已存在 owner。
2. 区分 missing、legacy-existing、protected-valid、protected-invalid。
   真实空 legacy 文件不等于不存在。
3. 普通 legacy read/查询/正常业务 transaction 不隐式迁移。旧写保留旧语义，
   新 cursor 仍不支持；显式迁移才在原 scope lease 内核验旧内容 CAS。
4. 新文档只在首次实际业务提交时初始化 metadata。只读 source_lease、pass、
   回滚及最终 canonical 不变的 transaction 不初始化、不 bump。
5. epoch 与相关业务文档只通过同一原子提交生效。不能分成业务文件与 epoch
   sidecar 两次提交，不能让 epoch 先公开而任务状态仍旧。
6. 受保护元数据由 owner 管理。调用者删除、回放或篡改保留字段不能原样提交；
   bool、负值、溢出、非法 nonce、重复 JSON key 与错误 schema 均需明确拒绝规则。
   不得悄悄修复损坏的 metadata 后继续接受旧 token。
7. cursor observation 不得采纳 active transaction 的未提交快照或 epoch。
   这种内部调用要明确拒绝，或使用经原 owner 证明已提交的独立观察端口。
8. collection 删除、同 ID task 删除重建、相关 schema/排序身份改变都要保留
   生命周期区分；不能只取最终任务内容 hash 或把版本重新从 1 开始当防 ABA。
9. 不在 project lease 里调用所有 reader。原 Creative 路径为 scope → project；
   若新迁移/retirement 加入 project → scope，会与现有 writer 构成反向等待。
   需要 project 与 scope 同时稳定的迁移应沿原 owner 的既有顺序设计短 lease，
   并单独核查授权 lease 顺序，不能任意套用嵌套 contextmanager。
10. 顶层元数据的保留不能破坏 CreativeProjectStore 的 deepcopy/clear/update、
    旧 JSON 格式、scope 校验、原集合限额或原调用方。必须实际回归验证。

## 7. 必须运行的双进程、强杀与回滚反例

| 反例/注入点 | 必须观察到的性质 |
| --- | --- |
| 两个独立 store 实例、两个进程对同 scope 并发改同 collection | 无重复提交 epoch、无静默丢更新；失去 CAS 的提交明确失败；不同 collection 的合并语义明确。 |
| s1 内重入 s2，同 root/key，同线程 | 不允许旧副本覆盖已提交新值；不能仅测两个不同 scope。 |
| 同实例 nested write | 继续原明确拒绝；外层异常不得留下内层独立提交。 |
| 显式迁移开始后另一个正常 writer 更新 legacy 文档 | 迁移 CAS 拒绝旧观察，不覆盖新数据；不能自动重取旧内容后冒充原确认。 |
| 业务 callback 抛异常、validate 失败、metadata 篡改 | 旧业务字节和旧 epoch 完整保留，无额外迁移文件；锁最终可重新取得。 |
| 临时文件创建后、部分写入时强杀 | 原文档仍可读且 epoch 与业务不分裂；孤儿 tmp 不被当成新 owner。 |
| 临时文件 fsync 后、replace 前强杀 | 原文档仍是旧配对；下次读取不得自动采用 tmp。 |
| replace 后、lease 释放前强杀 | 重开看到完整旧或新配对；不能出现新 epoch + 旧业务的混合结果。 |
| commit 完成后进程响应前强杀 | 原持久提交事实保留；重试必须按原 CAS/幂等合同处理，不能回退版本。 |
| 项目删除/同 nid 重建与迁移并发 | 旧 scope 不被贴上新 project incarnation；不死锁；旧 cursor 与新第一页边界分别验证。 |
| task A→B→A 两次真正提交 | 相关 source epoch 不回到旧值；同一次 transaction 内未提交的临时 A→B→A 不声称是持久历史事件。 |
| collection 清空/删除后重建相同 ID 与内容 | 原生命周期变化可区分，不能只做最终内容相等判断。 |
| 冷重开、独立进程续页 | 原 owner 证据来自持久原文档；进程 cursor 状态丢失只安全要求重读，不恢复缓存权限。 |
| 未选/被拒 collection 的写入 | 不通过相关 cursor 失效泄露隐藏来源活动。 |

原 atomic_write 的同文件 replace 结构可以作为“没有业务/epoch 双文件撕裂”的设计
依据，但这不是强杀测试结果。源代码没有 parent-directory fsync，不能从 file fsync
外推已证明断电持久性。进程 SIGKILL、Windows 进程终止、OS 崩溃、突然断电是不同
故障模型；后两项需要文件系统/数据库和实际故障验证，不能相互替代。

## 8. 旧备份重放：明确不可证边界

若旧备份把同一文档的业务内容、doc incarnation、source epoch 一并原样回滚，
且相同实例的 project marker 也保留/回放，则仅观察该原文档无法判断这是过去备份。
CAS 只能防并发覆盖，随机 nonce 只能区分由受控 owner 产生的新提交，不能识别
原样重放旧 nonce。mtime、inode 和字符串相等不是可靠的历史单调锚。

显式受控恢复端口可以在恢复提交时生成新的原 owner 生命周期；但原 backup_restore
当前原样复制字段，旧 PowerShell 路径还可显式覆盖。本轮不能声称已有通用备份
反重放。需要范围约束，或者未来在原 owner 内补上经授权的恢复生命周期合同。
不应为此暗中引入持久全局计数器、凭据或平行 registry。

## 9. 可证与不可证的交付表述

当前可报告：固定源码结构、入口/锁序风险、上述接口约束及反例设计；
执行器初始化失败这一实际观察。

当前不可报告：epoch 已实现、迁移已通过、所有 writer 已覆盖、双进程已安全、
强杀/断电已验证、旧备份无法重放、真实 HTTP cursor 已接通、性能或测试通过数。

没有 M0 运行基础前，交付应止于原 owner 接口准备与明确阻断，不把新的未接线组件
算成用户要求的完成品。
