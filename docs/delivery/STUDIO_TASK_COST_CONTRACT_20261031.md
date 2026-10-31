# Studio 任务成本合同：显式 UNKNOWN（2026-10-31）

本轮针对任务要求中的“Studio 任务成本”：在缺少可信 provider 用量/价格/任务关联时，**返回显式未知，不伪造成本**。

## 实现

`app/creative/production_execution.py` 的 `ProductionExecutionService.view(row, owner)`（`studio-production-job/1` 公共投影）新增 `cost` 字段，所有 IMAGE/AUDIO/VIDEO/TIMELINE 生产任务一致：

```json
{
  "contract": "studio-job-cost/1",
  "state": "UNKNOWN",
  "currency": null,
  "estimated_microusd": null,
  "actual_microusd": null,
  "accounted_microusd": null,
  "trusted": false,
  "linkage": "NONE",
  "reason": "PROVIDER_USAGE_PRICE_TASK_LINKAGE_NOT_INTEGRATED",
  "fabricated": false,
  "decision_required": true
}
```

- 不发明 0、不把本地执行/未执行任务说成“已结算”，不返回估算值；
- 每次投影深拷贝，调用方修改返回 dict 不影响常量或其他任务；
- 现有 job 投影字段保持不变（additive），前端 wire 兼容测试与 production query 测试均通过。

## 测试

- `tests/test_studio_production_job_cost_contract.py`（6 passed）：四种 owner 均返回显式 UNKNOWN；三个金额字段为 null；`trusted/fabricated=false`；投影隔离；不出现伪造数值。
- 回归：`test_studio_frontend_alignment_v2.py` 10 passed/1 xfailed、`test_studio_production_query.py` 41 passed（与成本测试合计 57 passed/1 xfailed）——证明 additive 字段未破坏既有 wire/查询合同。

## 边界 / 未完成（产品决定）

- 真实 provider 用量、价格、任务→账本关联的可信合同**未实现/未验证**：需要各 provider 适配器上报结构化 usage、价格表/币种/峰谷与任务绑定，并定义重试/重复上报/缺失时语义；
- 音频 `canvas_return` 的采用目标/权限/审核语义未扩展（需产品决定）；
- 本地 provider 的“零成本”也不能由本层推断为可信 0，除非有明确本地成本证据合同；
- 真实 Provider 调用/真实 PG 未运行。
