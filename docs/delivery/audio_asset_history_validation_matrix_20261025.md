# 单音频资产历史验收矩阵（2026-10-25）

实现代码：`2e2fcb79209a3afc03dc7e443f5e1901ff233ee1`。整体结论 **PARTIAL**；以下只把实际执行或静态审核的范围记为完成。

| 项目 | 本轮实际证据 | 状态 |
| --- | --- | --- |
| 原 owner 写入归属 | 固定基线全仓 _write_meta/_meta_path/_bin_path 调用检索；原 owner 六个直接写入口，lineage 间接进入 | 已核查 |
| 原位二进制替换 | 原 owner 仅 create 写新 ID；未新增覆盖接口 | 已核查 |
| 不可变 metadata 与真实 bytes | File 快照、SHA-256、历史序号/原 revision 分离，独立 blob 与当前 head | 已实现、已验证 |
| 老资产迁移 | v7 首次 read 不回填；首次真实 write 捕获 v7/v8，sequence 1/2 | 已验证 |
| 未提交历史不可见 | 三个提交前异常点和四个实际 os._exit 点后重建 owner | 已验证 |
| 提交后不确定 ACK | after_current_commit 异常及真实子进程退出后仅一个已提交 head | 已验证（metadata 写入） |
| 跨进程 CAS | legacy owner 与真实 File 项目/incarnation/原 owner lease 两类竞争 | 已验证 |
| 同 key 重试 | 原 create 精确重试、变 payload 冲突、真实双进程同 key | 已验证（原 create）；未实现恢复操作回执 |
| 容量/预算 | 新链写前 admission、所有 direct reader 当前 metadata 上限、128 MiB/100 状态、原 64 MiB 余量 | 已实现、已验证；低空间为测量 shim |
| 物理磁盘填满 | 未填满环境磁盘 | NOT_RUN |
| 不可变文件损坏 | record/选中 blob 摘要损坏拒绝；缺失 blob 预览不可用 | 已验证 |
| 真实挂载 HTTP | 原 /api 前缀下 list/detail/download/preview/confirm gate | 已验证 |
| 私有历史晋升隔离 | 当前 formal 不能读取旧 private；creator 可读原私有 production-origin 候选 | 已验证 |
| 当前来源授权与旧 pin | 真正 lineage pin、old private pin 拒绝、未版本化声明不伪造 pin | 已验证（ASSET 范围） |
| 非 ASSET/旧非 audio pin | 无安全既有只读来源合同的情况直接拒绝 | 部分实现、明确限制 |
| 来源二进制 | trace 明示 content_verified=false，仅证明 metadata/pin | NOT_RUN（不冒称已验证） |
| 撤权与返回前重核 | 真权限撤销、返回前撤销、feature 返回前撤销 | 已验证 |
| 权限 ABA | 同 ID grant 重授、membership 无 audit 状态往返、同 token/session 重登记 | 已验证（File） |
| cursor 隔离 | actor、branch/asset、current head、项目重建 | 已验证；进程重启须重新分页 |
| 只读 inspect | 无候选/回执/owner 补建；nested metadata 拒绝；前后文件 bytes 相同 | 已验证 |
| 显式恢复写入 | confirm/resolve 固定 409 admission-unavailable | 受阻；未实现成功路径 |
| 审批和引用 | 预览和拒绝确认不创建候选、不执行、不审核、不改原文件；原 Timeline/undelete 合同回归 | 已验证该只读子集 |
| 恢复唯一 operation journal/receipt | 没有伪造可用回执或隐藏 mint 通路 | 未实现 |
| PostgreSQL 项目 + File Asset | 未配置数据库连接；原 PG 权限代码只静态审核 | NOT_RUN |
| 原查询索引兼容 | 2 项当前 503；全新固定基线也 503；原 fsync EBADF 对照日志 | 受阻；未修改保护切片 |
| 独立审核 | 1c1c80 → 1866465 → 2e2fcb 固定 SHA 逐轮审阅，两个最后发现已修 | 已完成子集审核，有条件 PASS |
| 整体 M0–M7 | 恢复写端、审核接入、PG、完整查询验收仍未完成 | PARTIAL |

最终命令和原始日志见交付报告。**58 passed、3 warnings、exit 0** 只指四个列明专项测试文件，不能外推为全仓/全部后端通过。未调用付费 Provider/模型，未做部署或发布。
