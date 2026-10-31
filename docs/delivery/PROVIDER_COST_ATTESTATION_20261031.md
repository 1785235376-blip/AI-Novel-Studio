# Studio Provider Cost/Usage Attestation（2026-10-31）

## 能力
- `studio-provider-cost-attestation/1`：服务端 provider adapter 对**一个已完成 Studio 生产 job**的可信成本/用量声明；严格字段校验（contract/job_id/owner/request_digest/provider_id/model_id/currency/actual_microusd/usage/pricing_version/source/attested_at），无 HTTP 写路由。
- `ProductionExecutionService.record_cost_attestation(...)`：仅在原进程内、持原 job owner/guard 时记录；先绑定 job 的 request_digest/provider/model，再写 runtime sidecar。
- `studio-job-cost/1` 读模型：存在且绑定有效的 attestation → `state=ATTESTED, trusted=True, linkage=PROVIDER_ADAPTER/LOCAL_PROVIDER`，返回 actual/currency/usage/pricing_version；否则保持 `UNKNOWN`。
- 损坏/超限（>16 KiB）/错绑 sidecar 一律回退 UNKNOWN；不伪造成本。
- 默认无 attestation 的行为不变；真实 provider adapter 接入仍未完成（NOT_INTEGRATED）。

## 测试
`tests/test_provider_cost_attestation.py`（3 passed）：
1. 默认 UNKNOWN → 记录可信 attestation → 读取 ATTESTED/trusted/usage/pricing；
2. request/provider 错绑、负金额、非法 source、无权限 actor 被拒绝且不产生 sidecar；
3. 损坏/超限/孤儿 sidecar 不影响可信状态，仍为 UNKNOWN。

## 边界
真实 provider 价格/用量上报、真实 PostgreSQL/浏览器/模型验收仍 NOT_RUN；价格由 provider adapter 声明，不是平台自行推导。
