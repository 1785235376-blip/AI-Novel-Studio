# 项目容量与 U16 接续账本

固定起点为 `cb99745daf1c55a2ffa987c385e423f41e81c379`，tree `f8606510e62595c67eea64077608cc25743e2df1`。原工作树的 tracked、staged、非忽略 untracked 均干净，5806 个 tracked 文件与上轮冻结前后 SHA-256 清单一致；原 ignored 运行目录、缓存不删除，未宣称递归逐项检查。上轮报告及原账本持续有效，特别是对 PUBLISHING 后续独立审阅、Windows ACL/junction 的拒绝与 BLOCKED 边界。本轮不重试、转派或换入口绕过。

## 已实施的窄切片

- 原 Studio storage GET 的 `admission` 对尚未证明的项目 quota 返回 `UNAVAILABLE` 和 `available_import_bytes=null`，不再用当前可见分支的行大小声称可以导入，也不探测磁盘来填充未知项目额度。两 API 别名沿原授权、已有锁、只读约束；原字段形状及前端强制 measurement 字面量保留。ModelCenter 旧文案可能将这一状态误述为 assets 文件系统不可访问：此轮不改前端，不能说原因文案准确。本切片不是容量计量、预留或对账。
- 现有原 Windows 受限读取句柄核对正文完整性后，单资产内部观测可报告 `content_default_stream_stored_bytes`；合成稀疏、压缩和备用流文件验证。备用流、metadata 和整个对象的 `allocated_storage_bytes` 仍 UNKNOWN；`quota_admission=NOT_AVAILABLE`。在 owner helper 内，原主体权限租约须由调用方持有，native guard 的撤权测试不等于 helper 自行复验主体权限；未接 HTTP/配额，POSIX NOT_RUN。两个独立完整读取均计入同一预算，容量不足时安全拒绝。
- U16 含 VOICE_REDO 的新批次 preflight 保守关闭；旧纯语音批次 confirm 在原授权/版本检查后、写入前拒绝，事务内重查；语音 dispatch 在 claim 和 broker 预约前拒绝，并在原事务内再次检查版本及实际阶段；voice retry、promotion 在原 owner 副作用前拒绝。stop/reconcile 不被一律关闭，旧混合批次的合法非音频阶段保留。混合 Studio-image + voice 的新预检通过原 host/session/feature 与 scope 授权后拒绝，不为拒绝创建项目 marker；拒绝专用途径没有授予写 capability。

## 未闭合和限制

| 项目 | 状态 |
| --- | --- |
| 统一实际存储计量 | NOT_COMPLETE。当前 `project_usage` 只按当前 branch 元数据逻辑 size 计算。合成反例同一项目四份独立同摘要文件跨 branch 与 legacy：各 branch 返回 10/5 字节，正文总长度 20、metadata 长度 2488，另有 6 字节归属未知孤儿；这些是文件长度，不是分配量。共享 scope、临时、失败残留、索引及其他 owner 未统一核算。 |
| 项目持久预留、失败释放和启动对账 | NOT_IMPLEMENTED／NOT_RUN。`8099ee` 原型不覆盖所有 owner、共享文档和孤儿，且 `st_size` 不足以证明稀疏/压缩文件占用。不能把新单流观测或部分账本当写入准入；已关闭的写门继续关闭。 |
| U16 | PARTIAL。所列语音写前和事务版本复核可执行；旧混合批次 confirm、stop/reconcile 的共享 scope 写入仍未接统一容量。真实项目删除重建、跨 owner 原子性及实际额度预约并发未验证。部分反例使用显式来源检查桩或人工 gate 注入，不能称真实系统原先出现这些注入故障。 |
| 调额、历史与恢复 | 继续关闭；须先证明完整计量、并发预约、重启对账、原权限和审批安全。 |
| 平台 | 本轮仅 Windows File/Mock 合成夹具，POSIX、真实 PostgreSQL、浏览器与真实模型 NOT_RUN；Windows ACL/junction 仍 BLOCKED/NOT_VERIFIED。上轮 F37、warm 首屏 409、Windows 资产游标签名密钥问题继续独立保留。 |

未知归属孤儿不自动删除或认领。跨项目共享根的未知条目不应通过项目管理员的响应成功与否泄露给其他项目；未接线的聚合原型因此未合入。被拒的 PUBLISHING 审阅不能由其他测试代替；完整持久写入链依赖其安全验收的部分保持 BLOCKED。完整日志、最终固定源码哈希、测试列表和结果以本轮交付证据为准，重叠测试不累计。
