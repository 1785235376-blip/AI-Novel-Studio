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
- **修复**：新增独立测试把同一拒绝矩阵绑定到实际抓取函数，并覆盖 redirect、Content-Encoding、精确本地 provider origin、公网地址放行，以及 image-job 参考 URL 的创建前护栏。
- **结果**：`test_outbound_boundary_hardening.py` 45 passed（本机合成 HTTP 监听器，仅 loopback）。
- **提交**：`099cc2b7`、`ce3950ce`（image-job 参考 URL 用例）。

### 4.3 已自审定性：endpoint 改配后已存凭据的复用（受支持信任模型内接受，不升级为漏洞）

- **事实（静态核对）**：`OpenAICompatibleImageProvider`/`HttpAudioProvider`/`HttpVideoProvider` 在构造时把 vault 中的凭据保存为 bearer 并发送到当前配置 endpoint；配置入口只需要“有效 session”而不要求 workspace.admin。本机 wire capture 受本机 HTTP 客户端 502 影响，未取得真实请求头证据（`NOT_VERIFIED`）。
- **自审结论（2026-10-30 续做）**：在仓库当前支持的两个运行形态里，这个行为不构成越权：
  1. **packaged 形态**：只有一个 launcher 签发会话的受信本地 principal（`LocalSessionBootstrap`），provider/credential 全局配置对其本就可信；session gate 防的是浏览器/其他本地进程无 token 驱动后端，不是防同一受信用户改配。
  2. **development / collaboration 形态**：`create_runtime_session_resolver` 的注释明确称 dev sessions 为 “explicitly insecure developer sessions”；该形态仅本机 loopback，本来就没有多用户权限边界。
  因此**不新增 workspace.admin 要求、不绑定凭据与 endpoint、不改权限 owner**；登记为受支持信任模型内的残余风险，若将来支持多用户协作/局域网部署必须重新评估（见 10.2）。
- **同类残余**：供应商主机名 DNS rebinding（配置期不做 DNS）同属上述信任模型内的残余；已在准入层拒绝字面受限地址，`NOT_VERIFIED` 保留。

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
| Windows 游标签名密钥实现 | **OPEN**：38 项 503 复现；只读源码分析与合成拒绝层复现完成；fail-closed 回归已补（提交 `ce3950ce`）；等价 DPAPI 方案仅建议，未获批准未实施，现有机制未替换 |
| 历史 F37（37 个未明拒绝） | `UNKNOWN`，继续独立登记；本轮未复现、未关闭 |
| warm 首屏间歇 409 | `UNKNOWN`，继续独立登记；本轮未复现、未关闭 |

## 7. 未关闭边界（与阻塞项）

1. **PUBLISHING 隔离发布原语的后续独立审阅：`BLOCKED`**。前驱 `bc316e1`；上轮自动安全审查返回 `Agent errored: This content was flagged for possible cybersecurity risk` 并中止。本轮未重试、未转派、未改措辞、未换入口；依赖该项的验收继续保持缺口，任何其他测试不能替代。
2. **Windows ACL / junction：`BLOCKED / NOT_VERIFIED`**。未尝试替代命令或入口。
3. **Windows 资产游标签名密钥：OPEN**。当前无符合“私密密钥 + 防替换”合同的 Windows 实现；不得降级到普通路径，不替换现有机制。只读分析、拒绝层复现与 fail-closed 回归已完成（见 10.1）；等价 Windows 方案仅作为待批准建议，未实施、未验收。
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
| `ce3950ce` | 游标密钥 fail-closed + 图片任务参考 URL 回归（2 个文件 123 行） | 无 |
| `8493d1ab` | 本地响应安全头（1 个生产文件 + 1 个测试文件） | 有：仅新增响应头 |
| `1021e67f` | 归档成员遍历边界回归（1 个测试文件 126 行） | 无 |

- 起点/回退点：`2951a167`（远端分支原 HEAD）。回退生产改动：`git revert 7874bae7 8493d1ab`；四个测试提交可独立 revert。
- 变更范围：`app/net_safety.py`、`app/asset_provider_config.py`、`app/audio_provider_config.py`、`app/audio_providers.py`、`app/dependencies.py`、`app/api.py`（仅 VideoProviderConfigIn 校验）、`app/main.py`（仅新增响应头中间件）＋ 4 个新测试文件 ＋ 交付文档。
- 未修改：`main`、原工作树、既有 API 合同字段、权限 owner、只读行为、关闭门、凭据存储；未 push / Release / 部署。
- 最终冻结 HEAD/tree 与最终回归日志见交付答复及 `Validation/security-bounded-20261030/logs/`；本文件所在提交只增加文档，不改产品源码。

## 9. 是否适合进入下一轮安全验收

- **有条件适合**：本轮的固定起点核对、入口清单、出站边界修复与审批边界回归可以作为下一轮的基线；生产代码只改了一个防御性边界，未触及权限 owner。
- **仍不适合宣称生产安全完成**：PUBLISHING 审阅、Windows ACL/junction、游标签名密钥、审批跨 owner 原子性、容量闭环仍为阻塞/开放；持久写入链依赖被拒审阅的部分继续保持 `BLOCKED`。
- 下一轮建议优先顺序：① 被拒发布原语审阅的替代授权路径（需用户批准）；② 协作形态 provider/credential 全局写入授权（4.3）；③ 真实 PostgreSQL 下的审批/撤销/重建事务验证；④ 统一容量计量与预留；⑤ Windows 游标签名密钥等价方案（需用户确认后再替换）。

## 10. 续做自审记录（2026-10-30，用户授权“自行审核解决”）

### 10.1 Windows 资产游标签名密钥：只读分析、拒绝层复现与等价方案（未实施）

只读探针（本机 Windows / Python 3.11.9，合成临时目录，不读真实项目数据、不做 ACL/junction 探测）实际结果：

```
platform: win32
os.open in os.supports_dir_fd: False
os.stat in os.supports_dir_fd: False
has O_NOFOLLOW: False
has O_DIRECTORY: False
signing_key_primitives_available: False
load_signing_key refused: AssetQueryCursorUnavailable ASSET_QUERY_CURSOR_UNAVAILABLE
files created: none
```

- **直接拒绝层**：`asset_query_cursor.load_signing_key` 在 `signing_key_primitives_available()` 为 False 时立即抛 `AssetQueryCursorUnavailable`，不 `mkdir`、不打开任何路径、不创建密钥/身份文件，也不降级到普通路径。
- **上游表现**：资产列表游标模式返回固定 `503 ASSET_QUERY_CURSOR_UNAVAILABLE`；用户列出的游标测试 38 项失败即该拒绝层复现，不是新回归。
- **本轮新增回归**（提交 `ce3950ce`，`tests/test_cursor_key_fail_closed.py`）：锁定“缺原语必须 fail-closed、不得创建降级文件”；同时覆盖 32 字节密钥类型/长度、跨绑定重放、篡改签名、过期不滑动续期。该测试不声称 Windows 密钥后端已实现。
- **等价方案（仅建议，需另行批准后实施与验收）**：在现有 Windows 句柄/身份体系上，用 DPAPI（`CryptProtectData`，当前用户 scope）保护 32 字节随机密钥 blob，与独立身份 marker 分离存放；身份 marker 用 HMAC 绑定密钥摘要与版本；读取时沿用既有 Windows 受限句柄、reparse-point 拒绝、文件大小/身份对照和主体权限；密钥丢失/不一致一律拒绝并保留人工修复路径，不自动替换、不静默重建。未实现原因：需新增/确认 Windows 凭据保护路径与依赖、需要真实 Windows 验收，且属于替换现有安全机制，超出本轮“只读分析 + 合成复现 + 等价方案”授权。
- **未验证**：DPAPI 等价方案在打包 Host、真实 ACL、重启/轮换/删除重建下的行为；POSIX 路径仍 `NOT_RUN`。

### 10.2 provider/credential 全局写入：接受为受支持信任模型内残余风险

- 结论与理由见 4.3：packaged 单受信本地 principal；development/collaboration 明确为 insecure dev sessions，仅本机 loopback。不是多用户权限边界，故不改权限 owner、不新增管理员门槛、不做凭据—endpoint 绑定。
- **重新评估触发器**：若将来支持真实多用户协作、局域网/远程访问或把 dev sessions 用于非本机场景，必须在开放前补 `workspace.admin`（既有权限 owner）与终审时点复核，并重新验证 provider/credential 全局写入。
- DNS rebinding 同一结论：准入层已拒绝字面受限地址；主机名解析到受限地址仍 `NOT_VERIFIED`，属于同一信任模型内残余。

### 10.3 外部请求边界补充回归与工具限制

- 新增 `test_outbound_boundary_hardening.py::test_image_job_reference_url_is_fenced_before_job_creation`：mounted image-job 路由在创建持久任务/调用 provider 之前拒绝 `169.254.169.254`、`127.0.0.1`、`[fe80::1]` 参考 URL，且不回显目标地址（提交 `ce3950ce`）。
- `hindsight_*` 记忆工具本轮实际返回 `401 ... API key required`（未配置凭据），未使用其内容，也未虚构记忆结论。
- GraphFlow `graphflow_context` 仍超时；本文件所有结论来自源码、固定源码测试与本机合成探针。

## 11. 第二轮续做（2026-10-30）：浏览器响应头、归档路径边界、预存失败分类

### 11.1 已修复（浏览器侧边界，防御性）：全局安全响应头

- **触发/风险**：本地 loopback 服务此前只在资产下载等少数响应上设置 `X-Content-Type-Options: nosniff`；其余 API、静态前端、以及“路由前”的 loopback/session 拒绝响应没有嗅探、Referer、framing 边界。对本机 Localhost 应用属于纵深防御，不改变任何 API 字段或权限。
- **修复**：`app/main.py` 增加最外层 `security_response_headers` 中间件，对每个响应 `setdefault`：`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`、`X-Frame-Options: DENY`；已有更严格值的路由（如下载）不被覆盖。注册在最后，因此早于路由的 401/403/501 拒绝响应也带 header。
- **证据**：`tests/test_security_headers.py`（3 passed）覆盖成功响应、路由 404、以及“路由前”的 `403 LOCAL_RUNTIME_LOOPBACK_REQUIRED` 三种路径；受影响主中间件样本回归 74 passed（另 4 项为下文预存失败）。
- **提交**：`8493d1ab`。

### 11.2 已验证（文件访问，负结果 + 回归锁）：归档成员路径穿越

- **审查结论**：交付包与可移植项目读取均为**纯内存读取**，不存在 `extractall` 到磁盘的路径；成员名经过独立路径校验：
  - `interactive_export_contract.read_zip_safely`：要求声明前缀、`safe_bundle_path`（拒绝 `/`、`\\`、`:`、`.`/`..`/空段、Windows 保留名、超深路径）、大小写碰撞/文件-目录前缀冲突、加密标志、声明与实际大小/总量上限；
  - `portable_projects.read_archive`：成员名必须匹配 `manifest.json` 或 `media/aNNNN.<ext>` 严格白名单，拒绝重复、反斜杠、NUL、绝对路径、`.`/`..`、符号链接、加密、非 STORED/DEFLATED、压缩比与展开上限，并要求 manifest 声明且摘要一致；
  - `comic_ora_import.preview_ora` / `comic_author_archive.decode`：同样按固定成员白名单/结构校验读取，无磁盘解包。
- **未发现可在本机合成的 zip-slip 或路径逃逸**；`待验证`：其他平台、真实第三方归档、以及未来新增解包调用点。
- **新增回归**：`tests/test_archive_member_traversal_boundary.py`（29 passed）覆盖穿越/绝对/冒号/保留名/点段/大小写碰撞/文件-目录冲突/符号链接/重复成员/未声明 payload，并记录 Windows 与 POSIX 对反斜杠成员的安全差异（Windows 标准库归一化为嵌套路径、POSIX 直接拒绝，两种结果都不能逃出声明根）。
- **提交**：`1021e67f`。

### 11.3 预存失败分类（不是本轮回归）

用独立临时工作树在**固定起点 `2951a167`** 上复跑下列 4 项，结果与当前 HEAD 完全一致（同样失败），确认与本轮改动无关，另行登记为测试债务/环境限制：

| 测试 | 失败原因 | 分类 |
| --- | --- | --- |
| `test_phase1_feature_closure.py::test_motion_task_stays_pending_without_provider_and_rejects_placeholder` | `KeyError: 'transitions'`（该功能夹具与当前数据形状不一致） | 预存测试债务 |
| `test_plugin_discovery_security.py::test_symlink_escape_is_rejected` | `WinError 1314`（当前 Windows 账号无符号链接权限，测试无法造夹具） | 环境限制（`NOT_VERIFIED`） |
| `test_asset_library.py::test_asset_upload_list_metadata_and_download` | 旧上传路由现返回 `503 PROJECT_CAPACITY_WRITE_UNAVAILABLE`，旧测试仍期望 200 | 关闭门导致的预存测试债务（**不放宽关闭门**） |
| `test_asset_library.py::test_concurrent_asset_upload_with_same_key_is_single_resource` | 同上，`KeyError: 'id'` | 同上 |

不通过改测试期望或放宽门禁来“修绿”；这些项保持为已知债务，容量闭环后再处理。

### 11.4 第二轮提交与变更

| 提交 | 内容 | 生产影响 |
| --- | --- | --- |
| `8493d1ab` | 本地响应安全头（`app/main.py` + 3 项测试） | 有：仅新增响应头 |
| `1021e67f` | 归档成员遍历边界回归（1 个测试文件 126 行） | 无 |

- 第二轮新增生产改动仅一个中间件；未触碰权限 owner、API 字段、关闭门；仍未 push/Release/部署。
- 最终 HEAD/tree 与第二轮验证日志见交付答复与 `Validation/security-bounded-20261030/logs/`。

## 12. 第三轮续做（2026-10-30）：真实 PG 环境核查、Local Interop 覆盖缺口、插件/身份套件回归

### 12.1 真实 PostgreSQL：`NOT_RUN`（环境不可用，未安装任何新依赖）

只读核查本机结果：`Get-Service *postgres*` 无服务；`psql`/`pg_isready`/`postgres`/`initdb` 均不存在；`docker` 不存在；`TEST_POSTGRES_DATABASE_URL`/`DATABASE_URL` 未设置；5432 无监听。安装 PostgreSQL/Docker 属于新增系统依赖，未执行。因此真实 PG 下的审批/撤权/重建事务验证继续 `NOT_RUN`，不拿 File/Mock 结果替代。

### 12.2 已补覆盖缺口：Local Interop 桥此前没有任何测试

- **事实**：全仓库 grep `local_interop` 只在实现/SDK/`app/main.py` 挂载处出现；`tests/` 下没有任何测试文件引用 `/api/local-interop` 或 `LocalInteropHost`。这是一个真实的安全面覆盖缺口（该面承载会话、权限、handoff/审批流）。
- **审查结论（静态）**：实现本身防护很强——`SafeRoute` 只接受 `request.client.host == "127.0.0.1"`、query 参数只允许 `session_id`/`after`、请求体 96 KiB 上限、无通用 RPC；Host 侧有 permission generation/owner 绑定、`provider.authorize` 指纹复核、响应发送前 guard、SSE 每帧复核、flag 默认关闭、撤销即清会话与授权。
- **新增独立回归**：`tests/test_local_interop_security_boundary.py`（13 passed，真实 router + 真实 `LocalInteropHost` + 合成 provider，无真实项目数据）覆盖：双别名 loopback 传输（默认 TestClient 对端被 403 `TRANSPORT_ERROR`）、query 凭据/未知参数拒绝、超大 body 413、固定错误形状、无通用 RPC、flag 关闭时变更 403、只读 status 也要求 Host actor、关闭 flag 后 owner 被撤销。
- **仍未覆盖**：完整 connect / SSE / handoff / 审批流、packaged Host 会话、真实浏览器 peer —— 这些需要 packaged Host/浏览器夹具，保持 `NOT_RUN`；本测试不声称 interop 全链路安全。

### 12.3 插件信任与身份/授权套件回归证据

- 运行 `test_plugin_contract_v1`、`test_plugin_signature_policy`、`test_plugin_trust_contracts`、`test_plugin_catalog`、`test_official_declarative_plugin_packs`、`test_plugin_discovery_security`、`test_authorization_foundation`、`test_identity_membership`、`test_stable_identity_foundation`、`test_identity_binding_rebuild`：**271 passed / 2 failed**（531.78s）。
- 2 个失败均为 Windows 符号链接权限限制（`WinError 1314`：`test_plugin_catalog::test_good_plus_symlink_invalid_is_partial`、`test_plugin_discovery_security::test_symlink_escape_is_rejected`），与 11.3 中同类失败一致，属环境限制 `NOT_VERIFIED`，不是产品回归。
- 静态补充：插件安装只接受声明式 JSON bundle（无代码执行、无 ZIP 解包），`validate_declarative_relative_path` + `resolve_plugin_file` 拒绝绝对/盘符/UNC/反斜杠/`..`/编码变体/符号链接逃逸，并在解析后做 root containment 复核；未发现路径逃逸。

### 12.4 第三轮提交

| 提交 | 内容 | 生产影响 |
| --- | --- | --- |
| `6e797d40` | Local Interop 安全边界独立测试（163 行） | 无 |

- 第三轮**没有生产代码改动**；只补覆盖与核查证据。仍未 push/Release/部署，未触碰禁止项。

## 13. 第四轮续做（2026-10-30）：Local Interop 会话/撤权/handoff 全链路回归

- **新增** `tests/test_local_interop_session_boundary.py`（5 passed）：用仓库自带的冻结协议对端 `SyntheticDesktopPeer`（MOCK_ONLY，不开 socket、不读业务存储）注入 Host transport，让**真实 `LocalInteropHost`** 完成：
  1. connect → HELLO → capability negotiation → session 建立，会话绑定 owner/scope；
  2. handoff 必须 `explicit_click=True`（否则 403 `PERMISSION_DENIED`），成功时返回既有 Studio 路由；
  3. 按单项同意撤销 `deep_link`：映射 capability 被移除，撤销同意优先于 capability 检查返回 403；后续会话 capability 门也拒绝；
  4. provider 授权指纹变化（授予/成员变更等价）→ 当前会话被撤销（403 + 移出 sessions、进入 closed_sessions）；
  5. provider 显式拒绝授权 → 当前会话被撤销；
  6. 同一 owner 重连只替换该 owner 的旧会话（旧会话 401 `SESSION_REVOKED`）；
  7. 运行中关闭功能开关 → owner 会话被撤销且后续请求 403。
- **未覆盖**：真实桌面 peer、打包 Named Pipe 传输、SSE 事件流/standing metadata 事件投递、tutor/verifier 往返、真实浏览器——仍 `NOT_RUN`，本测试不声称 interop 全链路安全。
- **提交**：`a3231035`；无生产代码改动。

## 14. 第五轮续做（2026-10-30）：Interop 事件同意与 Tutor/Verifier 结果边界

- **新增** `tests/test_local_interop_events_guidance_boundary.py`（3 passed），仍用冻结合成对端 + 注入 transport（事件对象由注入 transport 精确回执，因为冻结 peer 没有 EVENTS 操作），让真实 `LocalInteropHost` 完成：
  1. **上下文预览是 Tutor 请求的前置且单次有效**：未确认的 ask 403 `CONTEXT_NOT_AUTHORIZED`；已消费的 preview 重放 409 `CONTEXT_STALE`；capsule 内容级别在预览阶段为 `NONE`；
  2. **Tutor 文本不能变成 Host 的 VERIFIED 结果**：guidance 必须 `LOCAL_ONLY`，Verifier 用**新鲜 Host 状态**重新评估，对端 prose/`AUTHORITATIVE` 标签不构成证据，结果保持 `UNKNOWN`；
  3. **事件订阅必须显式确认 preview 且持有 standing consent**：未确认 403；确认后 `subscription_active=True` 且有 grant；撤销 `standing_metadata_events` 后 grant 立即清空，旧 grant 与旧 request binding 均 403 `PERMISSION_DENIED`；
  4. **最小化诊断预览会暂停更宽的 standing grant**，且诊断预览要求 `diagnostics.read` capability。
- **未覆盖**：真实 peer/命名管道传输、浏览器端 SSE 消费、真实上传/案件流——`NOT_RUN`。
- **提交**：`f116b2d9`；无生产代码改动。

## 15. 第六轮续做（2026-10-30）：Interop 取消/断开收据 + 安全相邻独立套件回归

- **新增** `tests/test_local_interop_cancel_disconnect_boundary.py`（4 passed，冻结合成对端 + 注入 transport）：
  1. 同一 owner 重复占用同一 in-flight `request_id` → 409 `CANCELLED`，原请求不受影响；
  2. `cancel` 对未知请求返回固定收据，会话参数受 owner 会话门约束；
  3. `disconnect_revoke` 先撤销本地授权再做对端往返：报告 `revoked/subscriptions_stopped/pending_cancelled/standing_grants_cleared`、`transport_disconnected=True`、`peer_disconnect_acknowledged=True`、`status=DISCONNECTED`，会话进入 closed_sessions 且旧 token 请求 401；重复断开保持幂等且不虚报；
  4. 同步 `disconnect` 返回固定收据、撤销会话，但不声称对端状态；未知会话 id 只返回与调用者 owner 投影绑定的收据，不泄露跨 owner 信息。
- **安全相邻独立套件回归**（15 个既有独立/反例套件，含上传关闭门、资产使用/查询授权、U16 stop 来源隐私、范围残留模型上传、图片叶重跑 HTTP、音频历史 collab、存储观测、生成 worker 授权、Studio 独立集成）：**164 passed / 0 failed**（122.48s）。
- **未覆盖**：真实 peer ACK/真实命名管道断开、浏览器 SSE 断开、跨 owner（合成 provider 只有单一 actor）会话取消 —— `NOT_RUN`。
- **提交**：`f1c6b8f4`；无生产代码改动。

## 16. 第七轮续做（2026-10-30）：原有资产消费者跨项目/跨分支隔离矩阵

- **新增** `tests/test_legacy_asset_consumer_isolation.py`（3 passed，复用既有真实 mounted 路由 + File rig + 真实会话/成员/授权）：
  1. **跨项目**：无该项目授权的会话访问对方项目的 `/api/novels/{nid}/assets`、`/api/assets/{id}`、`/download`、`DELETE`、`/image-jobs`、`/exports`、`/novel/export` 均 403，响应不出现对方资产名，且对方资产未被删除；协作模式下已禁用的 legacy 媒体路由保持 fail-closed（403/501）；对象存在性通过 owner-scope `_load` 核对；
  2. **同项目跨分支**：别的分支的资产在列表中被隐藏；按资产 id 读取/下载/删除均 404（不泄露存在性），且未被删除；
  3. **分支授权不是项目级媒体权限**：只有 BRANCH scope `domain.read` 的会话访问项目级 legacy 资产/图片任务返回 403；不显式选分支的导出列表按项目级判定 403；显式 `branch_id` 的导出列表保留既有“分支级导出”合同并返回 200（这是既有设计，不是放宽）。
- **未覆盖**：真实 PostgreSQL、浏览器、真实媒体/模型；导出作业创建与下载的来源绑定（本轮只验证列表/项目级授权入口）——`NOT_RUN`。
- **提交**：`d80aa67a`；无生产代码改动。
