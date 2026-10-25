# TaskCenter 类型筛选、覆盖报告与游标依赖边界

本轮起点为 `ffe1937911cff32d4ebd4770b350674627501d3a`，
tree `447bfefcee8393b9b0907fe7daff2d5b044709da`。
实现分支为 `work/taskcenter-consistent-query-20261025`。

**交付是部分实现，不是完整的一致性游标交付。**
类型筛选、静态能力与明确拒绝路径已编写；独立进程内游标组件已编写，但未接入 HTTP。
实际 HTTP cursor 始终明确返回 501。执行结果以 delivery 目录的最终证据为准，
不得从源码、历史日志或本文件中的命令推断测试已通过。

## 接口与旧行为

两条入口共用原路由与原权限链：

- `GET /api/novels/{nid}/experimental/workspace/tasks`
- `GET /api/v1/novels/{nid}/experimental/workspace/tasks`

旧 `q`、`failed_only`、`limit`、`offset` 已在起点实现，不算本轮新增。
未传 `authority` 和 `page_mode` 时，保留原排序、原 envelope、旧 500 条上限及
原 limit/offset 解析；内部 diagnostics/search/preflight/writing-sessions 不隐式分页。
孤立 `cursor=unused` 继续按旧未知参数忽略。
无新增筛选时，路由向 service 传递的 keyword 仍只有原 limit/offset。

| 参数 | 新语义 |
| --- | --- |
| authority | 可重复，多值 OR；只接受原 reader authority 精确小写名称 |
| page_mode | 显式 `offset` 或 `cursor`；重复标量取最后一个 |
| cursor | 仅在 page_mode=cursor 时识别，保留长度 1–512；本轮不会签发 HTTP token |

authority 最多接收 64 个原始值（重复值也占输入上限），合法重复去重。
空值、大小写变化、空白填充、逗号拼接、非法值与空列表统一拒绝。
HTTP 多值采用 OpenAPI array / form / explode=true。
service keyword-only `authorities` 只接受 None 或非空 list/tuple of exact str，
拒绝字符串、集合、bool 和未知类型；名称同时核对静态合同与实际 registry。
参数顺序不改变原 reader 顺序。

名称来自以下原 authority；它们不是新媒体分类或执行能力：

```text
author_generation workflows semantic_import media agent_team audiobook
voice_direction agents exports images review_inbox audio_tts motion
subtitle_processing adaptation research_analysis visual_identity
```

- 仅传 authority：仍最多返回 500 项，增加完整有限匹配观察的 observed_total、
  source_truncated、coverage 与 capabilities。
- 传旧 limit/offset：原分页行为不变；只有同时传新参数才增加 capabilities。
- 显式 page_mode=offset：启用原分页，未指定 limit/offset 时使用 50/0；
  limit 最大 100、offset 最大 1,000,000，原整数线值习惯（例如 1.0）保留。
- 显式 page_mode=cursor：即使 offset=0 也禁止混用；其他合法参数经原授权后返回固定 501。
  空或超长 cursor、非法 limit、非法类型筛选等返回固定 422。
  本轮没有成功的 HTTP cursor、续页、失效或历史快照响应。

## 筛选与观察字段

筛选发生在原 reader 注册顺序上；选中 reader 仍调用原读路径，原 scope fence 与
安全投影不变。q 对安全 id + label + stage_label 做原 Unicode casefold 子串匹配，
failed_only 使用原 FAILED/UNKNOWN 规则。不得搜索正文、prompt 或私有路径。

| 字段 | 含义 |
| --- | --- |
| observed_total | 当前有限、已授权、安全且匹配筛选的投影条目数 |
| source_truncated | 选中源在原可见性规则下提供的截断提示 |
| has_more / next_offset | 仅针对本次观察匹配集合的原 offset 分页 |
| coverage.scope | 恒为 BOUNDED_AUTHORIZED_PROJECTION |
| coverage.completeness | 恒为 NOT_ASSERTED |
| capabilities | 静态实现支持，不能用作本次授权或可见 reader 报告 |

新参数响应中的静态 capabilities：

```json
{
  "authority_filter": {"supported": true, "operator": "OR"},
  "cursor": {"supported": false, "reason": "RELIABLE_LIFECYCLE_BINDING_UNAVAILABLE"},
  "cross_owner_atomic_snapshot": false,
  "full_history_query": false,
  "cost": "UNKNOWN"
}
```

最终页、空结果、source_truncated=false、unavailable=[] 都不证明全部历史可见，
也不证明没有隐藏任务。模型费用仍 UNKNOWN，不从任务数量推算实际花费。
原 403/404 reader 继续静默略过；其他失败只保留原静态 SOURCE_UNAVAILABLE。
不新增 denied/hidden count、内部扫描量、原始异常、私有路径或动态 reader 覆盖列表。
新参数的成功及本路由产生的 422/501 错误使用 no-store。

## 成功与拒绝示例

```text
GET /api/novels/{nid}/experimental/workspace/tasks?authority=semantic_import&authority=media&failed_only=true&limit=50&offset=0
GET /api/v1/novels/{nid}/experimental/workspace/tasks?authority=semantic_import
GET /api/novels/{nid}/experimental/workspace/tasks?page_mode=offset
```

示意空的显式 offset 响应（不包含任何隐藏 reader 信息）：

```json
{
  "items": [], "unavailable": [], "truncated": false,
  "executor": false, "refresh": "MANUAL", "automatic_retries": false,
  "observed_total": 0, "limit": 50, "offset": 0,
  "has_more": false, "next_offset": null, "source_truncated": false,
  "coverage": {"scope": "BOUNDED_AUTHORIZED_PROJECTION", "completeness": "NOT_ASSERTED"},
  "capabilities": {
    "authority_filter": {"supported": true, "operator": "OR"},
    "cursor": {"supported": false, "reason": "RELIABLE_LIFECYCLE_BINDING_UNAVAILABLE"},
    "cross_owner_atomic_snapshot": false, "full_history_query": false, "cost": "UNKNOWN"
  }
}
```

`page_mode=cursor` 的 detail 为：

```json
{"detail": {"code": "TASKCENTER_CURSOR_UNSUPPORTED", "message": "TASKCENTER_CURSOR_UNSUPPORTED"}}
```

新参数非法时的 detail 为：

```json
{"detail": {"code": "EXPERIMENTAL_INVALID", "message": "TASKCENTER_QUERY_INVALID"}}
```

上两例仅展示固定 detail；原全局错误 handler 仍附加 code/message/details/request_id。
原访问被拒时保留其原错误和优先级，不把 403/404 改成来源覆盖信息。
原 q/failed_only 的 FastAPI 校验顺序保留。OpenAPI 包含实际成功及未支持示例，
不发布虚构的成功 cursor 示例。

## 前端交接

本轮不改 Grok 前端或 SDK。接入方可使用 authority 和原 offset 模式。
必须向用户如实说明 offset 仍是逐次观察：翻页中任务变化可能改变页边界，
本轮尚未解决完整 HTTP 跨页一致性。项目、分支、会话或筛选变化时清空旧页并重读第一页。
501 应显示当前模式不支持；不得悄悄把 cursor 请求当成功 offset 续页。

未来可靠 cursor 接线完成后，固定 restart 错误必须清除全部旧页并从第一页读取，
不能合并旧、新观察。重读不得触发任务派发、模型请求、批量重跑或自动重试。
目前该 restart 合同仅存在于独立组件，不能当作已可调用的 HTTP API。

## 独立游标组件：已编写，未接线

`app/experimental/taskcenter_cursor.py` 只管理进程内有限元数据。
内部 `TaskCenterCursorEngine.page` 默认拒绝，`supported=True` 只能来自将来可信的内部适配，
不能作为 HTTP 参数开放。

默认 TTL 300 秒、容量 128 个观察；硬上限 TTL 900 秒、容量 1024、页大小 100、
observed_total 1,000,000。状态按 FIFO 淘汰，读取不续 TTL。
容量按观察而非每页 token 计，capacity=1 不会因自身翻页淘汰旧游标。
token 为随机 handle、非敏感位置及 HMAC，不含查询、任务、凭据、路径或摘要明文；
组件 token 上限 160 ASCII 字符，HTTP 的 512 只是保留输入上限。

每个状态只存 binding/query/projection 三摘要、页大小、观察数与固定 deadline。
不存任务，不代替权限或 owner。跨 binding、查询、集合、顺序、revision、公开截断证据变化，
过期、淘汰、冷启动或其他 worker 均要求重读。相同有效 token 重复读取不推进服务端指针。
末页也检查 TTL。继承到不同 PID 的实例直接拒绝，子进程须新建实例；
不操作可能继承的锁。时钟回退安全失效。无文件、凭据或其他持久状态。

所有生命周期 epoch 合成测试仅验证“调用者提供不同原证据后组件会拒绝”，
不能证明真实任务或权限 A→B→A 已被检测。

## 暂停的最小依赖与后续方案

1. 在原装配中注入可信 `capture(ctx)` / `revalidate(ctx, observation)` 观察端口，
   不通过全局新权限 registry 或 settings 路径猜测 owner。
2. 原项目身份可从核验实际 repository owner 的
   GenerationIdempotencyAuthority(...).owner 只读复用 existing_owner_only()/incarnation(nid)。
   缺 marker 明确拒绝 cursor；禁止 capture_new() 或查询创建 marker。
3. 原会话使用 TrustedSessionResolver.binding_generation(token)，并在原 resolve/authorize 前后重读，
   不能仅比较可复用的 ReadContext 字符串。
4. 协作 membership/grant/branch 需要原 owner 真正提供可重读、不可重放的生命周期观察；
   现有 updated_at 和最终状态摘要不能防撤权后原值恢复。
5. 每个支持的任务 reader 必须有可证明的原生命周期/revision 观察与完整有限安全投影重读能力。
   缺可靠证据的模式持续未支持；不能将私有计数器伪装成 owner incarnation。
6. 每页原授权 → 原身份观察 → 原 reader/scope fence → 再次原授权/身份 → 比较完整观察，
   不持有项目锁调用全部 reader。不能承诺跨 owner 原子快照或历史冻结。

本轮按用户边界暂停这些共享装配/owner 依赖，未修改 project_store、trusted_sessions、
membership、资产或任务 owner。不可把暂停依赖算作完整 M2/M5 通过。

## 扫描与验证

原 reader 每个最多中央检查 200 行，旧返回上限与原 owner 窗口不变。
semantic_import 原路径仍先读取/物化整个 scope 文档，再中央裁剪；
响应分页不等于数据库分页，逐页重读不承诺减少底层 I/O。

合成测量计划 N=0/3/199/200/201/2000，页大小 1/50/100；
记录实际 reader 调用、文件读取/字节、源行数、中央检查、耗时和 tracemalloc 峰值。
只在实际执行日志存在后填写样本；不编造性能数字。

最小定向命令（必须设置本任务临时 PROJECT_ROOT/NOVEL_DATA_PATH、HOME/XDG/TMP，
File storage、memory vault、MOCK_PROVIDER=true、ENABLE_CLOUD=false）：

```sh
python -m pytest tests/test_taskcenter_query_backend.py tests/test_taskcenter_consistent_query.py tests/test_taskcenter_cursor_independent.py -q
python -m pytest tests/test_taskcenter_query_measurements.py -q -s
```

真实 File/HTTP 测试仅使用临时合成数据，保留原成员/授权链；
业务文件快照覆盖隐藏文件、集合、inode/大小/mtime/hash，仅排除原确切锁目录。
独立审查自行提出跨上下文、读中撤权、ABA、截断和错误泄露反例。
真实 PostgreSQL、Windows 产品运行、真实前端/浏览器、真实模型不在本轮执行范围。
