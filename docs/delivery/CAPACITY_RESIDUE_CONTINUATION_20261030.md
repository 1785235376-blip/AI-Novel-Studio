# 容量、残留与 U16 接续账本

本轮起点 `5df5b2f464fc1d292ede03f9266157bd58a1f3c7`，tree `7717b35d5ff9d1de0e70057f30b122ed92589be8`。原工作树 tracked、staged 和非忽略 untracked 均无改动；5815 个 tracked 文件与上轮前后 SHA-256 清单一致。原 ignored 运行目录和缓存保留，未声称逐项检查。工作在新分支 `work/capacity-residue-closure-20261030` 的隔离树中进行。

上轮在最终源码的真实 File 子进程中人为中断：scope 临时文件 fsync 后、替换前退出；旧文档和临时残留均保留，后续原事务仍允许写入。这个失败不是自然事故或完整对账测试，也不证明残留属于特定 incarnation。原 `ExperimentalStore.transaction` 既用于写又用于只读 source lease，部分调用在 scope 提交前执行跨 owner 操作；不得只在提交后检查而称副作用前保护，也不能为堵截写入而取消读取。

`project_usage` 当前只统计当前 branch 的 metadata 逻辑大小；共享文档、跨分支、旧未绑定资产、元数据、临时文件、失败残留、未知孤儿及物理分配量没有统一核算。不得将此统计或 Windows 单默认流观测当成项目完整容量或写入预留。512 MiB 默认与管理调整遵循既有合同；调额入口仍须等待统一归属、计量、预留、对账和审批保护。旧关闭门和用户明确要求保留的读取、停止、诊断继续保留。

## 本轮窄实现和边界

- 原 File scope 事务及默认 `source_lease` 在 Windows 本地固定盘上、原 scope 锁下，以一次按该 scope 原 `atomic_write` 临时命名前缀过滤的查询检查疑似残留；发现时在回调前拒绝，提交前再次核查，不读取、认领、收费或删除该对象。真实子进程 fsync 后退出、重启读取、默认租约中原资产写入、两个协作进程活跃临时文件串行均有合成测试。未知其他命名、其他 owner 与跨机器未覆盖；非 Windows 保留原行为且 NOT_VERIFIED，UNC/网络映射/非固定盘拒绝，根祖先重解析身份与 ACL/junction 依然 NOT_VERIFIED。
- 普通资产 GET/下载保持；经审计的私有候选读取使用受限 scope observation，但该标志不是跨 owner 副作用的强制沙箱。STYLE 旧章节读取可能懒迁移，在残留时不能安全假定纯读，故显式拒绝并保留 `EXPERIMENTAL_SCOPE_UNRECONCILED`，不误报普通 stale；其派生读取在该异常状态暂不可用。其他未经审计的派生读取可能保守拒绝，不能称全部读取均验通过。
- U16 含原 Studio image 的批次 stop 沿原 host/session 和项目授权租约，再以 scope→project 原锁顺序核验冻结 image incarnation 及原 CAS，并持有原项目身份至 File scope 替换结束；保留非 image 路径及语音关闭门。缺 marker 不创建，旧来源不可见仍优先隐藏。Packaged host 和非 File image stop 继续明确不支持；真实 File/合成源、两 API 别名、项目删除重建、会话撤销与子进程反例的范围应按原日志分别记载，不能外推跨机器或真实模型。
- 原模型参考 GLB 手工导入未接项目容量，现沿原 feature/域授权后拒绝新增，已有 GLB 读取保留；FastAPI 原有有界请求/JSON 校验仍先于 handler，不能称授权先于所有 body 解析。
- 四个现有 File 项目身份 marker 校验合并为原 owner 的同一严格 schema/UUID 验证函数；旧格式不迁移、不增加字段、不同 owner 的原错误契约保留。中间候选的 None sentinel 比较引入来源绑定回归，已另提交修复并保留原版／中间／修复对照；这不是原生产缺陷，也不是持久预约实现。

本轮没有实现统一项目物理计量、持久预约、额度与预留转换、启动对账或跨 owner 崩溃恢复。上面的 scope 名称门仅阻止一类明确时序的进一步写，不证明项目已核算、孤儿已归属或全部写入口已关闭。调额和音频历史恢复仍关闭。

用户禁止重试上轮被安全审查拒绝的 PUBLISHING 后续独立审阅，也禁止 ACL/junction 探测；二者保持 BLOCKED，不通过代理、重述或其他入口绕过。跨机器锁、跨 owner 单事务和外部效果 exactly-once 均未证明。上轮 F37、warm 首屏 409、Windows 游标签名密钥问题继续独立登记。最终源码、实际执行的合成测试、失败控制、模块来源与前后哈希在后续交付报告中逐项列明；POSIX、PostgreSQL 或其他环境未执行则标 NOT_RUN。
