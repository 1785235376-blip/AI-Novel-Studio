# 后端安全检查与修复记录（2026-10-30）

本文件记录本轮有边界后端安全检查的入口清单、实际发现、修复、证据、未关闭边界和终态。所有结论只覆盖本机 Windows + File 合成环境；未运行的环境在文中显式标 `NOT_RUN`，被策略拒绝的事项标 `BLOCKED / NOT_VERIFIED`。

## 1. 固定起点核对

| 项目 | 实际结果 |
| --- | --- |
| 用户指定提交 | `2951a167cc7ff1fae171d9f514f55e6d2de568d8` |
| 本地是否已有该提交 | 否（最初本地不存在该对象） |
| 远端分支 | `origin/work/capacity-residue-closure-20261030` 精确指向 `2951a167`，其后 0 个提交 |
| tree | `aa774afbc89929ab62017e572c5c6dcdf941c020`，与要求一致 |
| 原工作树 | `D:\PoemSeed\AI-Novel-Studio` 保持 detached `5af9bfc4`；仅有未跟踪的旧 `build/`（2026-10-11 Python 构建产物，5.1 MB），未 reset/clean/stash |
| 本轮工作树 | `D:\PoemSeed\Worktrees\security-bounded-20261030`，新分支 `work/security-bounded-20261030`，未 push |
| 前驱账本 | `AGENTS.md`、`CAPACITY_RESIDUE_CONTINUATION_20261030.md`、`CAPACITY_U16_CONTINUATION_20261030.md`、`PROJECT_CAPACITY_CLOSURE_LEDGER_20261030.md` 已读；PUBLISHING 审阅与 ACL/junction 约束继续有效 |
| GraphFlow | `mcp__graphflow__graphflow_context` 调用超时（实际错误为工具超时），本轮不使用其上下文，未虚构图谱结论；其余静态/动态检查不依赖它 |

`main` 未修改，未强推、未创建 Release、未部署、未上传。所有新代码只在上述独立分支。

## 2. 检查范围、方法与边界

- **入口/数据流清单**：用 AST 静态扫描 10 个路由文件共 469 条路由，识别 77 条没有直接授权标记的处理器，再逐条人工核查（含装饰器依赖、工厂闭包、中间件归一化别名）。
- **动态合成探针**：TestClient 直连真实 mounted 路由；本机 `127.0.0.1` 合成 HTTP 监听器观察出站请求；只使用脱敏合成字节，不涉及真实项目数据、凭据或第三方网络目标。
- **静态扫描**：提交机密规则扫描 4664 个文本文件；路由/依赖授权静态扫描。
- **基线测试**：用户列出的 9 个专项测试文件在固定源码上实际执行。
- 详细原始日志位于 `D:\PoemSeed\Validation\security-bounded-20261030\`（基线日志、路由扫描 JSON、机密扫描 JSON、探针结果 JSON、源码前后 SHA-256）。

## 3. 入口/数据流安全清单（按优先级）

| 入口/数据流 | 信任边界 | 已有保护（核对） | 可能风险 | 验证方法 | 现状 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/*` 与 `/api/v1/*` 双别名 | HTTP 客户端 → 应用 | 同一 `api_router`、同一 `experimental_router` 对象分别挂载两前缀；中间件用 `_normalized_api_path` 归一化 | 别名授权 owner 漂移 | 读 `app/main.py:365-415`；受影响测试 | **通过（静态核对）** | `app/main.py` |
| 会话解析与撤销 | 客户端 token → actor | `TrustedSessionResolver.resolve` 每请求解析；`revoke` 增代并移除；packaged 用 `LocalSessionBootstrap.resolve_issued_session`（一次性 bootstrap、60s、origin/host/runtime-id 校验） | 撤销后旧 token 残留 | `test_pending_canon_review_boundary`（撤销后 401）；现有 bootstrap 测试 | **通过（Windows/File 合成）** | 提交 `a67c0045` |
| 项目作用域 API | session + 项目成员/授权 | `_shared_project_access`/`_authorize_novel_project`/`_authorize_media_novel` 逐路由项目/分支作用域；项目删除重建走原 scope/authorization owner | 跨项目、旧请求重放 | 路由扫描 + 现有 `test_studio_asset_query.py` 跨项目用例 + 本轮审批跨项目用例 | **通过（文件后端合成）**；真实 PG `NOT_RUN` | 第 4 节 |
| 审批提交（pending Canon review） | 项目 `domain.review` → 持久 commit | 项目 id + 版本 CAS + preview digest + 源章节/摘要 + operation id 幂等 + commit 前后 `check()` 复授权 + `project_operation` 锁 | 撤权/重建/重放竞态 | 新增独立 route 级测试（8 项） | **通过（File 合成）**；跨 owner 原子性与 PG `NOT_RUN` | 提交 `a67c0045` |
| 旧 `POST /pending-canon/{pid}/approve` | record 派生项目授权 | 依赖 `_shared_pending_review` 解析记录所属项目后授权；协作模式该路由被中间件关闭（501） | record 授权后 handler 只按 pid 批准 | 静态核对（协作模式不可达） | **通过（静态）**；本地模式无多用户边界 | `app/api.py:1761`、`app/main.py` |
| URL/资源地址导入（speech/image import、vision） | 客户端 URL → 服务端抓取 | `media_files.media_destination`：仅 http(s)、无 userinfo/fragment、解析一次并钉地址、拒绝 redirect/压缩/超长/截断 | 本机/私网/云元数据 SSRF | 合成探针矩阵：8 个受限目标 × 3 入口全部 400 且零 socket/provider 调用 | **通过（本机合成）** | 探针 `P1-*` |
| 旧 `net_safety` 边界函数 | 测试 → 函数 | `validate_outbound_url`/`fetch_outbound_bytes` 已无生产调用方 | P0 测试只守死代码路径，生产边界无回归 | 新增生产函数 `media_destination`/`fetch_media_bytes` 测试 | **已补测试** | 提交 `099cc2b7` |
| 供应商 endpoint 配置（asset/audio/video） | HTTP session → 服务端出站 | 配置期/刷新期新增受限地址拒绝；loopback/私网/公网 provider 保留 | 受限地址（云元数据、link-local、多播、保留段）成为服务端拨号目标 | `test_outbound_boundary_hardening.py`（HTTP 400 + 直连提交拒绝 + 手改配置不注册） | **已修复（防御性）** | 提交 `7874bae7` |
| 供应商 endpoint 凭据复用 | 同一 session → 既有凭据 | 端点与已存凭据没有绑定关系；适配器把 bearer 凭据发往当前配置 endpoint | 同一授权域内的凭据被发往后来改配的 endpoint | 静态核对；本机 wire capture 受本机 HTTP 客户端 502 影响 | **待验证（产品决策）** | 第 4.3 节 |
| 媒体/资产读取与下载 | session + 项目 + 资产 owner | `_scoped_asset` 摘要比较、`AssetLibraryService._load` 元数据完整性/摘要校验、`_identifier` 白名单、符号链接拒绝 | 路径穿越、跨项目资产、摘要替换 | 现有资产/查询测试 + 静态核对 | **通过（静态+现有测试）** | `app/services/asset_library_service.py` |
| 游标签名/作用域绑定 | 客户端 token → 游标 | HMAC 绑定项目/分支/incarnation/调用者/条件/源版本；每页重走原授权；固定 900s | 篡改/跨作用域/撤权复用 | 现有所列游标测试在固定源码执行 | **38 项 503（Windows 密钥缺失，已知）**；POSIX/PG `NOT_RUN` | 第 5 节基线 |
| 错误输出/日志/诊断 | 服务端 → 客户端 | `guard`/`capability_guard` 固定错误码；`structured_log` 白名单；`runtime_diagnostics` 只返回安全能力投影 | 绝对路径、堆栈、凭据泄露 | 13 条错误路径响应体扫描；机密规则扫描 | **通过（本机合成）** | 探针 `P5`、`secret_scan.json` |
| 容量写入关闭门 | 请求 → 资产/音频/项目配额 | 旧 `POST /novels/{nid}/assets` 统一 503 `PROJECT_CAPACITY_WRITE_UNAVAILABLE`；Studio 手工上传/模型引用同类关闭；音频历史 `ADMISSION_UNAVAILABLE`；额度管理入口关闭 | 未接线写入口绕过上限；跨项目计量泄露 | 现有容量/U16 测试 + 账本核对 | **关闭门保留；统一计量/预留/对账仍 NOT_COMPLETE** | 第 6 节 |
| 原有资产消费者（TaskCenter/导出/IMAGE 回填/受限重跑） | 各原 owner 授权 | 导出 `_authorize_export_record` 记录级复授权；IMAGE 回填走 `_authorize_media_novel` + 实际字节校验；受限重跑有独立 proof/审核闭包 | 消费者来源绑定漂移 | 现有导出/媒体/重跑测试；本轮未新增 | **现有证据保留；本轮未完整复验** `NOT_RUN` | `docs/delivery/STUDIO_V2_BACKEND_COMPLETION_LEDGER_20261028.md` |

## 4. 按严重程度排列的发现

### 4.1 已修复（防御性，外部请求边界）：供应商 endpoint 接受受限网络地址

- **触发条件**：持有有效 session/本机访问权的调用方 `PUT /api/asset-providers/{id}`、`PUT /api/audio/providers/{id}`、`PUT /api/video-providers/{id}/config`，把 endpoint 设为 link-local/云元数据/多播/未指定/保留地址（如 `http://169.254.169.254/v1`），随后该配置被注册并在列表/执行时被服务端真实拨号。
- **影响范围**：服务端出站请求可被配置到本机不应访问的地址；在协作/dev session 与多用户场景下属于全局配置越权类风险；packaged 单用户形态下同一本地用户已可支配本机，严重度显著降低。未定性为可利用远程漏洞。
- **修复前证据（合成）**：固定源码上 `PUT /api/asset-providers/custom` 对 `http://169.254.169.254/v1` 返回 200 并持久化；注册后 `GET /api/asset-providers` 触发真实出站探针（本机记录器收到 `GET /v1/system_stats`）。
- **修复**：新增离线安全的 `validate_provider_endpoint`（`app/net_safety.py`），在 asset/audio/video 配置保存、adapter 刷新/构造、手改配置注册处拒绝受限目标；loopback/私网/公网保持原合同；旧式十进制/十六进制/带尾点数字主机也被拒。**不做 DNS 查询**，保证离线保存行为不变。
- **修复后结果**：同一请求返回 400 `INVALID_PROVIDER_CONFIG` 且不写盘；`test_outbound_boundary_hardening.py` 44 项通过；既有 provider/凭证/媒体 129 项受影响回归通过。
- **提交**：`7874bae7`（生产代码）、`099cc2b7`（独立回归测试）。
- **剩余限制**：`待验证` —— 主机名在当前 DNS 下解析到受限地址未在配置期查询（DNS rebinding 类），以及已存凭据与 endpoint 的绑定关系（4.3）。

### 4.2 已补测试（覆盖缺口）：P0 测试守的是无生产调用方的函数

- **触发条件**：`tests/test_p0_security_regressions.py` 只调用 `app.net_safety.validate_outbound_url`，而该函数与 `fetch_outbound_bytes` 在固定源码中没有生产调用点；实际抓取入口是 `app.media_files.media_destination` / `fetch_media_bytes`。
- **影响范围**：生产抓取边界的回退（协议/端口/重定向/压缩/精确 origin）不会被这些 P0 断言发现。
- **修复**：新增独立测试把同一拒绝矩阵绑定到实际抓取函数，并覆盖 redirect、Content-Encoding、精确本地 provider origin、公网地址放行。
- **结果**：`test_outbound_boundary_hardening.py` 44 passed（本机合成 HTTP 监听器，仅 loopback）。
- **提交**：`099cc2b7`。

### 4.3 待验证 / 需产品决策：endpoint 改配后已存凭据的复用

- **事实（静态核对）**：`OpenAICompatibleImageProvider`/`HttpAudioProvider`/`HttpVideoProvider` 在构造时把 vault 中的凭据保存为 bearer 并发送到当前配置 endpoint；配置入口只需要“有效 session”而不要求 workspace.admin。`待验证`：同一写入者能否在不掌握凭据值的情况下，把另一用户已配置凭据发往新的公网 endpoint；本机 wire capture 受本机 HTTP 客户端 502 影响，未能取得真实请求头证据（`NOT_VERIFIED`，不是“未发生”）。
- **未修复原因**：绑定“凭据—endpoint”或要求管理员授权会改变既有权限 owner/API 合同，需用户明确决策；本轮不擅自改动。
- **建议**：要么在本机打包形态确认单用户信任模型成立并记录，要么在协作形态对 provider/credential 全局写入增加既有 `workspace.admin` 授权与终审时间点复核。

### 4.4 已独立验证通过的审批边界（File 合成）

- `POST /api/projects/{project_id}/pending-canon/{pending_id}/review` 及其 preview/recover 路由：匿名 401、只读 403、跨项目 403、撤权后 401、版本/预览摘要过期 409、operation id 复用 409、幂等重放不重复提交、项目删除重建后旧 pending 不被新项目采纳（404 且无 Canon 事实）。
- 提交：`a67c0045`；`test_pending_canon_review_boundary.py` 8 passed。
- 未覆盖：真实 PostgreSQL、跨 owner 一次事务原子性、跨机器锁、packaged Host 撤权（均 `NOT_RUN`）。

### 4.5 已验证的负结果（未发现问题的区域）

- 提交机密扫描：4664 个文本文件，196 条命中**全部为测试哨兵/合成值**（如 `sk-SENTINEL_NEVER_*`、测试 token），未发现真实凭据。
- 错误输出扫描：13 条错误路径响应体无绝对路径、Traceback、site-packages 标记。
- 返回媒体 URL 拒绝矩阵：`127.0.0.1`、`localhost`、`169.254.169.254`、`10.x`、`192.168.x`、`[::1]`、`file://` 及旧式数字主机全部拒绝，且探针证实无任何 socket/provider 调用。
- 双 API 别名：`/api` 与 `/api/v1` 使用同一 router/service/授权闭包（静态核对）。

## 5. 固定源码基线测试（修复前，同一提交）

命令（工作树根目录）：

```
python -m pytest tests/test_p0_security_regressions.py tests/test_studio_asset_query_cursor.py \
  tests/test_cloud_canvas_create_recovery.py tests/test_u16_mixed_host_authority_independent.py \
  tests/test_u16_mixed_preflight_independent.py tests/test_scope_residue_gate.py \
  tests/test_scope_residue_process_independent.py tests/test_project_quota_management_authority.py \
  tests/test_studio_capacity_admission_unavailable.py -q -p no:cacheprovider
```

结果：**94 passed, 38 failed, 2 skipped**（58.23s，exit 1）。38 个失败全部来自 `test_studio_asset_query_cursor.py`，均为 `503 ASSET_QUERY_CURSOR_UNAVAILABLE`：本机 Windows 缺少 `O_NOFOLLOW`/`dir_fd` 等安全文件原语，签名密钥守卫 fail-closed。这与账本登记的“Windows 资产游标签名密钥问题”一致，是**已知拒绝层复现，不是本轮新回归，也未修复**。其余 8 个文件全部通过。

## 6. 环境矩阵（本轮实际状态）

| 环境 | 状态 |
| --- | --- |
| Windows / 本机 Python 3.11 / File 后端 | **已运行**（基线 + 新增 + 受影响回归） |
| POSIX / Linux File | `NOT_RUN` |
| 真实 PostgreSQL | `NOT_RUN` |
| Mock provider | 作为合成替身使用（仅媒体/供应商探针，不替代真实模型结论） |
| 浏览器 / 真实前后端 | `NOT_RUN` |
| 真实外部网络目标 | `NOT_RUN`（只使用 loopback 合成监听器；未向任何第三方发送载荷） |
| Windows ACL / junction 探测 | `BLOCKED / NOT_VERIFIED`（上轮策略拒绝，未重试、未换入口） |
| Windows 游标签名密钥实现 | **OPEN**：38 项 503 复现；只读源码分析 + 合成失败复现已完成，等价安全实现未获用户确认，未替换现有机制 |
| 历史 F37（37 个未明拒绝） | `UNKNOWN`，继续独立登记；本轮未复现、未关闭 |
| warm 首屏间歇 409 | `UNKNOWN`，继续独立登记；本轮未复现、未关闭 |

## 7. 未关闭边界（与阻塞项）

1. **PUBLISHING 隔离发布原语的后续独立审阅：`BLOCKED`**。前驱 `bc316e1`；上轮自动安全审查返回 `Agent errored: This content was flagged for possible cybersecurity risk` 并中止。本轮未重试、未转派、未改措辞、未换入口；依赖该项的验收继续保持缺口，任何其他测试不能替代。
2. **Windows ACL / junction：`BLOCKED / NOT_VERIFIED`**。未尝试替代命令或入口。
3. **Windows 资产游标签名密钥：OPEN**。当前无符合“私密密钥 + 防替换”合同的 Windows 实现；不得降级到普通路径，不替换现有机制。
4. **审批跨 owner 竞争：部分未证明**。File 合成覆盖已列入 4.4；真实 PG 事务、跨 owner 原子边界、跨机器锁、外部效果 exactly-once 均 `NOT_RUN`/未证明。
5. **容量闭环：未完成**。统一物理计量、持久预留/失败释放、启动对账、跨项目归属与孤儿处理仍未闭环；调额、音频历史写入/恢复继续关闭；`project_usage` 仍只统计当前 branch 元数据逻辑大小。本轮未接线、也未放宽任何关闭门。
6. **供应商 endpoint 剩余风险**：主机名 DNS 解析到受限地址（配置期不做 DNS）与凭据—endpoint 绑定（4.3）标 `待验证`。
7. **历史测试债务**：旧 P0 测试与生产抓取路径不一致（4.2 已补），但未删除旧测试，避免改变既有验收口径。

## 8. 本轮提交、回退点与终态

| 提交 | 内容 | 生产影响 |
| --- | --- | --- |
| `7874bae7` | 供应商 endpoint 受限地址准入（6 个文件） | 有：缩小可接受配置范围 |
| `099cc2b7` | 独立出站边界回归测试（1 个文件 293 行） | 无 |
| `a67c0045` | pending Canon 审批边界独立测试（1 个文件 272 行） | 无 |

- 起点/回退点：`2951a167`（远端分支原 HEAD）。回退生产改动：`git revert 7874bae7`；两个测试提交可独立 revert。
- 变更范围：`app/net_safety.py`、`app/asset_provider_config.py`、`app/audio_provider_config.py`、`app/audio_providers.py`、`app/dependencies.py`、`app/api.py`（仅 VideoProviderConfigIn 校验）＋ 2 个新测试文件。
- 未修改：`main`、原工作树、既有 API 合同字段、权限 owner、只读行为、关闭门、凭据存储；未 push / Release / 部署。
- 最终冻结 HEAD/tree 与最终回归日志见交付答复及 `Validation/security-bounded-20261030/logs/`；本文件所在提交只增加文档，不改产品源码。

## 9. 是否适合进入下一轮安全验收

- **有条件适合**：本轮的固定起点核对、入口清单、出站边界修复与审批边界回归可以作为下一轮的基线；生产代码只改了一个防御性边界，未触及权限 owner。
- **仍不适合宣称生产安全完成**：PUBLISHING 审阅、Windows ACL/junction、游标签名密钥、审批跨 owner 原子性、容量闭环仍为阻塞/开放；持久写入链依赖被拒审阅的部分继续保持 `BLOCKED`。
- 下一轮建议优先顺序：① 被拒发布原语审阅的替代授权路径（需用户批准）；② 协作形态 provider/credential 全局写入授权（4.3）；③ 真实 PostgreSQL 下的审批/撤销/重建事务验证；④ 统一容量计量与预留；⑤ Windows 游标签名密钥等价方案（需用户确认后再替换）。
