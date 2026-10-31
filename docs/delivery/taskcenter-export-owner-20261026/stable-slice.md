# Export 原所有者写入串行化与私有生命周期观察

本切片基于 TaskCenter 协作稳定切片本地 `0eb392f49eb57107905a226b092566cb42e620c5`。
候选生产代码冻结 `335fdd6ac6a7f1e350792eb2179d6c372ccb19c5`，app tree `6ee7fd97bf422d99a931d4672d0b07f81f650f60`。
唯一生产变更：`app/services/export_job_service.py`。无 API、游标、前端、资产引用、音频或制作所有者修改。

## 原问题与改动

独立原实现反例：两个进程同时调用原 `create`，实例级 RLock 无法防止读取旧全表再覆盖，造成已提交任务丢失；相同幂等键也可能返回不同逻辑任务 ID。两例真实子进程反例均已跑到预期失败，不是理论推测。

修复在原 ExportJobService 写边界复用既有 File `workspace_mutation` 协调器；没有新 TaskCenter 状态库、影子写锁或任务执行器。
原 JSON 文件仍保存原任务。新文件的原写边界额外维护私有同文件 metadata；`_read`、`get`、`list`、公开投影保留原 id→job 视图，隐藏 metadata，不添加任务字段。旧文件普通读写不迁移、不认证其生命周期。

私有 `binding_observation(job_ids)` 与 `revalidate_binding` 只提供所选已提交行的 incarnation/nonce。它们不授予权限、不绕过原 actor/scope/per-record 授权，不接入 HTTP 或多源游标。

`get`、`list`、观察方法只做原子文件读取；不创建 writer lock 或业务文件。无待恢复任务的 startup 保留只读兼容性。真实 recovery mutation 才使用原写入协调器。
比较使用原 JSON 序列化 roundtrip 后的规范值：保留数字对象键、tuple 等旧 JSON 强制转换，同时区分 bool/int、float/int 等真实 JSON 值变化。

## 明确边界

- 不开放 exports cursor，也不开放 mixed-source；后续仍需独立的原授权、project/source 生命周期和投影组合审核。
- 不改变 startup 对 running/queued 的原恢复策略；不是跨进程活跃 worker 独占协议，不保证不会把另一进程活跃任务视为待恢复。
- 验证只针对原文件写边界、锁释放与明确故障位置；不是跨文件事务、掉电耐久性、完整 ABA 或外部备份回放防护。
- 观察是私有原所有者接口，caller 仍必须做原授权。metadata/锁均不成为新的授权来源。
- 使用合成数据、stub executor/原测试夹具；没有用户任务、付费资源、真实模型或托管部署。测试在 dot 原生云工作区执行。

## 验证

最终冻结组及独立证据见 `verification.json`。中间候选结果不是最终冻结结果，分组有重叠，不相加。首次 race RED、保留的中间候选、规范值及只读兼容修复均在原始证据中区分。
