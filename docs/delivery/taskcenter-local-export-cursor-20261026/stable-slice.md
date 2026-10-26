# TaskCenter：原 File/local exports 单源游标

基础为 Export 原所有者切片本地 `bfca25464d3f8329585ee9463f39ee52fb7ef00b`。
候选生产冻结 `1799b098f1f5b5639e151c66be21a175387cb047`，app tree `591cc74b70cf5546f6cf604d985e484f40c18567`。

## 支持范围

`GET /api/novels/{nid}/experimental/workspace/tasks` 与 `/api/v1/...`，显式
`authority=exports&page_mode=cursor`，仅非 packaged、实际 File、local-author、没有 session/branch header 的 local 模式。

原 local semantic_import 与 collaboration 无 source 引用 agent_team 两个已支持切片不变。
**没有新增 collaboration exports 或 mixed-source 游标。** 不把 local 模式重新命名为协作。

新原所有者方法 `ExportJobService.local_task_observation(novel_id)` 单次原子读取同一个已提交文档：
- 与原 `list` 共享六键 permission_context 严格过滤；local actor_id 必须仍为 None。
- 沿原 created_at/id 排序，先取原100条，再由原 TaskCenter 做 scope fence、q/failed_only 过滤。
- 仅绑定实际匹配安全投影的行 nonce 和原 source_truncated 语义；不绑定无关 actor、被过滤行、隐藏 tail 的 nonce。
- 已绑定空窗口可以返回空页；旧、缺失或缺可靠生命周期的文档不补建、不迁移，明确拒绝。

组合层核对原 ExportJobService 实例身份及路径、原 File novel/chapter/project incarnation，以及当前原 reader registry。
每次仍执行原 exports reader 与完整 TaskCenter reauthorization，包含返回前的最终复验。
读取不构造 ExportJobService、不触发 startup recovery/submit、不启动后台导出，不把观察证据当权限。

## 边界与未做事项

- 未改 `app/api.py`、`app/experimental/store.py`、前端/SDK、Work 资产引用查询/graph_api、音频或制作执行所有者；未合并另一分支。
- collaboration exports 的原逐条授权存在 branch-owned snapshot / PROJECT 级权限分支。现有 team 的 branch grant 证据不能替代它，因此没有强开支持。
- 队列原观察不是活跃 worker 独占协议，不承诺完整 ABA、外部备份回放防护、跨文件原子快照或掉电耐久性。
- 原100条 cap 的最后一页不是全历史；coverage 继续 NOT_ASSERTED。
- 使用 dot 原生云工作区与合成夹具，无付费资源、真实模型、用户导出、托管部署或 CI。

## 证据

测试先行：原 owner 缺接口5例预期失败；原真实 POST202 后两入口 cursor501 的独立基线失败。
首次候选中的两处测试假设（公开 snapshot_id 与私有 snapshot 混淆、假造 row.label 的 q 匹配）已纠正，不修改原投影规则。
最终冻结组、独立原调用链反例及其确切命令/退出码见 `verification.json` 与原始证据。分组有重叠，不求和。

最终冻结结果：TaskCenter组130 PASS；原export消费者/owner进程组96 PASS；独立挂载22 PASS。均exit0、无外部app模块混入，分组不累加。
