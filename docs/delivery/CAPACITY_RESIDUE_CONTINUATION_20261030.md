# 容量、残留与 U16 接续账本

本轮起点 `5df5b2f464fc1d292ede03f9266157bd58a1f3c7`，tree `7717b35d5ff9d1de0e70057f30b122ed92589be8`。原工作树 tracked、staged 和非忽略 untracked 均无改动；5815 个 tracked 文件与上轮前后 SHA-256 清单一致。原 ignored 运行目录和缓存保留，未声称逐项检查。工作在新分支 `work/capacity-residue-closure-20261030` 的隔离树中进行。

上轮在最终源码的真实 File 子进程中人为中断：scope 临时文件 fsync 后、替换前退出；旧文档和临时残留均保留，后续原事务仍允许写入。这个失败不是自然事故或完整对账测试，也不证明残留属于特定 incarnation。原 `ExperimentalStore.transaction` 既用于写又用于只读 source lease，部分调用在 scope 提交前执行跨 owner 操作；不得只在提交后检查而称副作用前保护，也不能为堵截写入而取消读取。

`project_usage` 当前只统计当前 branch 的 metadata 逻辑大小；共享文档、跨分支、旧未绑定资产、元数据、临时文件、失败残留、未知孤儿及物理分配量没有统一核算。不得将此统计或 Windows 单默认流观测当成项目完整容量或写入预留。512 MiB 默认与管理调整遵循既有合同；调额入口仍须等待统一归属、计量、预留、对账和审批保护。旧关闭门和用户明确要求保留的读取、停止、诊断继续保留。

用户禁止重试上轮被安全审查拒绝的 PUBLISHING 后续独立审阅，也禁止 ACL/junction 探测；二者保持 BLOCKED，不通过代理、重述或其他入口绕过。跨机器锁、跨 owner 单事务和外部效果 exactly-once 均未证明。上轮 F37、warm 首屏 409、Windows 游标签名密钥问题继续独立登记。最终源码、实际执行的合成测试、失败控制、模块来源与前后哈希在后续交付报告中逐项列明；POSIX、PostgreSQL 或其他环境未执行则标 NOT_RUN。
