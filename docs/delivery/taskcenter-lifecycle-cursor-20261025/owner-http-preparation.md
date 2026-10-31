# 原生命周期与 HTTP 接线准备（未实现）

固定提交：1587b57791cbdc3e46f0c09fedea83072e6a8d28。
本文是 M0 阻断下的只读接口准备；不表示已接线、已签发成功游标或已运行测试。

## 身份／权限审计结论

| 原 owner | 已有证据 | 不能据此声称的能力 |
| --- | --- | --- |
| CreativeProjectStore | existing_owner_only、incarnation、短 owner_lease；File UUIDv4 marker / PG novels.id | marker 缺失时 GET 补建；用当前 marker 自动认领旧 scope 文档 |
| TrustedSessionResolver | register/revoke 都递增 binding_generation；原 resolver identity | 只比较 generation 整数即可跨重建；local 随意 token 被原 authorizer 使用 |
| File identity owner | 原 authorization mutation lock，审计及非审计写入口 | updated_at 或 audit IDs 是完整不可重放身份 |
| File authorization owner | 原 role/permission save、retire、audit/revoke | 只 hook 新 HTTP/admin 路由即可覆盖所有撤权／恢复 |
| File scope owner | 原 collaboration-scope 锁，branch revision、link/retire | branch ID 或 revision 等于 branch incarnation |
| ExperimentalStore / semantic_import | 原同文件 atomic commit；UUID job / row version | 已有文档 epoch、任务完全 ABA、备份不可重放 |

精确身份入口：
- app/creative/project_store.py:63–127，GenerationIdempotencyAuthority:44–95 核验 actual repositories。
- app/trusted_sessions.py:27–64；resolver 重建时进程 binding 需安全失效。
- app/repositories/file/identity.py:34–139，包含 save/status 的非审计入口。
- app/repositories/file/scope.py:159–223，包含非审计 save/retire 与独立 audit。
- identity 补偿直接 write_bytes(before)，scope/persistence/retirement 也有直接恢复原字节；
  生命周期维护不能只放在高层 _write 后或 admin API。
- 原 project retirement 锁序为 authorization → project → collaboration-scope。
  原 CreativeProjectStore 写路径为 experimental scope → project。
  不可持有 project 锁再调用所有 reader，或在 scope 尾部临时补拿 authorization 锁。

## 最小可评估模式，而非当前可用模式

同时限制为 actual File、原开发 loopback local 单 principal、非 packaged、
非 collaboration、无 X-Session-Token、无 X-Branch-Id、
显式只选择 semantic_import、既有合法 marker、原 source 文档具有可信项目绑定及生命周期。

app/api.py:3847–3855 的原 local authorizer 只检查项目，然后返回 local-author/local_scope；
它忽略 token/branch。该候选模式的 session/member/grant 应标 NOT_APPLICABLE，
不能伪造 session epoch，也不能宣称跨浏览器会话隔离。

Packaged 原 bootstrap 发行集和 session generation 是可复用证据，但 packaged 强制 collaboration；
成员／grant／branch 生命周期缺口仍存在。semantic_import 的原创建入口也只接受 local。
本轮不在没有证据时把 packaged 或全部 17 个来源放行。

## 候选文件边界

| 文件/原 owner | 候选最小职责 |
| --- | --- |
| app/experimental/store.py | 同原子提交维护相关生命周期、保留字段保护、提交前 CAS、纯已提交观察 |
| app/experimental/imports.py | 复用原 jobs/list 与范围验证的观察端口 |
| app/experimental/api.py | 一个显式 dependency 注入，核验 actual store / original owner |
| app/experimental/taskcenter_cursor_http.py（仅候选） | 模式门禁、捕获/重读/复验、复用既有 engine、固定错误 |
| ux_api.py / taskcenter_query.py | 最小 HTTP 接线、严格白名单、公开静态支持条件和错误合同 |
| ux.py | 单 semantic 来源已有 authority-only 聚合可复用，初步无需重写 |

以上没有任何文件在本轮被修改，也没有创建这个候选新模块。

原 authority-only 聚合不传 limit/offset 时保留 500 条响应上限；
单 semantic 来源中央最多 200 行，因此可取完整当前有界安全投影。
必须检查 observed_total == len(items) <= 200，不能对 limit=100 的第一页签“全观察”摘要。

候选顺序：
原 access → 新参数/模式门禁 → 原短项目身份捕获 →
原选定 source 已提交生命周期与行同源观察 →
原授权和安全投影 → 相关 source / 项目复验及必要重读 →
复用既有 engine → 返回前原授权及相关身份最后复验。

生命周期证明必须真正由原 owner 提供；仅两次安全投影相同仍不能防 A→B→A。
不得使用 scope 全局活动代次、未授权 collection 计数或原异常作为公开信息。
不自动重试、不降级 offset、不持项目锁跨全部 reader。
实际重读次数和 I/O 需要以后实测，不能宣称变成数据库分页。

## HTTP 错误与缓存头边界

- 原鉴权 401/403/404优先；未支持条件或第一页缺可靠原身份固定501。
- 续页观察变化、过期/淘汰/进程重启或跨绑定复用固定409 TASKCENTER_CURSOR_RESTART_REQUIRED。
- 新非法参数／token shape 固定422，不回显查询、凭据或任务文本。
- 旧 offset 的参数、原 envelope、500 cap、内部 kwargs 与 diagnostics 调用必须保持。

当前 endpoint 的 access 在 try 外，FastAPI q/failed_only 校验更早：
仅给 injected Response 或局部 catch 加 no-store 不能覆盖这些路径。
候选应使用仅 TaskCenter GET 新 opt-in 生效的 APIRoute 包装：
包住原 get_route_handler，保留原 HTTPException status/detail/headers 并补 no-store；
对新 opt-in 的 RequestValidationError 采用固定不回显输入的错误。
原无新参数请求仍走旧合同。

全局 middleware 提前拒绝又在 APIRoute 外。若验收要求所有新增模式失败都 no-store，
必须列一个仅精确任务 URL/新 opt-in 的最小共享 middleware 改动与两个前缀测试，
不应声称局部 route wrapper 已覆盖它。

## 恢复执行后必须满足

1. 两前缀真实 File 成功第一页/续页/replay/末页，原授权链运行。
2. 项目删除重建后旧 token 失败，新第一页也不能误认旧 scope。
3. 相关任务持久 A→B→A、同 ID 重建、当前页外变化、TTL/容量/进程丢失均有真实反例。
4. 未选/拒绝来源、未授权行变动不贡献覆盖或生命周期侧信道。
5. 观察前/读取中/投影后/签发前/返回前确定性交错。
6. 原 File 业务全快照证明读取零副作用；双进程与强杀检验同文件提交。
7. M3 稳定后再讨论协作 epoch 和第二来源，而非全局打开。
8. GitHub Actions 账单阻断独立报告；当前无任何本轮运行结果。
