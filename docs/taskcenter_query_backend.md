# TaskCenter 有限投影分页后端合同

范围：`G-TC-1` 的 bounded-projection 分页，沿用
`GET /api/novels/{nid}/experimental/workspace/tasks` 及 `/api/v1` 别名。
这不是 Production `/api/projects/{nid}/studio/production/jobs`，不修改它的 owner 或查询合同。
不修改前端、17 个原 reader、原执行/取消行为、认证、数据库或扫描窗口。

## 查询与兼容性

| 参数 | 未提供时 | 范围 |
| --- | --- | --- |
| `q` | 原空字符串 | 原 FastAPI 最长 160 字符 |
| `failed_only` | 原 `false` | 原 FastAPI 布尔解析 |
| `limit` | 已启用分页时为 50 | 整数 1–100 |
| `offset` | 已启用分页时为 0 | 整数 0–1,000,000 |

只有显式提供 `limit` 或 `offset` 才启用分页，包括 `offset=0`。
仅传 `q`、`failed_only` 不启用分页。未传分页时严格保留原 envelope：

```json
{
  "items": [],
  "unavailable": [],
  "truncated": false,
  "executor": false,
  "refresh": "MANUAL",
  "automatic_retries": false
}
```

原默认仍最多返回 500 个投影条目。原搜索索引、diagnostics、ReaderPreflight、
WritingSessions 调用不隐式变成第一页 50 条。service 原位置参数保持不变，
新 `limit`、`offset` 为 keyword-only 参数。

`q` 仍按 Unicode casefold 对安全投影的 `id + label + stage_label` 做子串匹配，
不 trim，不新增 prompt、标题正文、provider 或 model 搜索。
`failed_only` 仍仅匹配投影后的 `FAILED`、`UNKNOWN`；恢复标记和未识别状态的原映射保留。

新分页参数沿用已有标量查询线值习惯：重复参数取最后一个值，`1.0`/`0.0` 可解析为整数，
非整数小数、空字符串、超范围值拒绝，不钳制。`limit=bad&limit=1.0` 接受，
`limit=1&limit=bad` 拒绝。未知参数仍忽略，不新增 `page`、`page_size` 或 cursor 能力。
service 内部直接调用新参数要求真正的整数，拒绝 bool、float 和字符串。

## 分页响应

```json
{
  "items": [],
  "unavailable": [],
  "truncated": false,
  "executor": false,
  "refresh": "MANUAL",
  "automatic_retries": false,
  "observed_total": 0,
  "limit": 50,
  "offset": 0,
  "has_more": false,
  "next_offset": null,
  "source_truncated": false,
  "coverage": {
    "scope": "BOUNDED_AUTHORIZED_PROJECTION",
    "completeness": "NOT_ASSERTED"
  }
}
```

- `observed_total`：本次原有限 reader 结果中，经过原 scope fence、安全投影及
  `q`/`failed_only` 筛选后保留的投影条目数。不是全历史任务数，不叫 `total`。
  同一原对象可能出现在领域 reader 与 `review_inbox`，不跨 authority 去重。
- 分页作用于中央原 500 响应截断之前的有限聚合；可以访问已观察集合的第 501 条及以后，
  但不继续翻取原 owner、扩大每 owner 的前 200 行检查窗口或补读被过滤掉的历史。
- `has_more`：仅表示本次已观察匹配集合在当前页后还有条目。
- `next_offset`：仅在 `has_more=true` 时等于 `offset + 实际返回条数`，否则为 null。
  空集合或越界 offset 不产生循环下一页。
- `source_truncated`：沿用原源提示规则。某 reader 的前 200 行中至少有一条通过原
  scope fence 时，才采纳它的 `has_more`、非 null `next_offset` 或 `len(rows)>200`。
  可见性判断仍在 q/failed_only 之前，所以筛选为空也可 `source_truncated=true`。
- 分页模式的 `truncated = source_truncated OR has_more`。
  它不是旧的“总响应超过 500”标记，也不表示前页条目仍在后续页；最终页没有已知源截断时为 false。
  未启用分页时仍是原源截断提示 OR 匹配集合超过 500。
- `coverage.completeness` 始终 `NOT_ASSERTED`，包括最后一页、空页、
  `source_truncated=false` 和 `unavailable=[]`。false 仅表示原逻辑未观察到截断提示，
  不能反向证明完整历史或所有 owner 可用。

所有任务项保留原字段、revision、source/navigation、动作资格和 UNKNOWN cost。
顺序仍为 reader 注册顺序，加各 reader 原返回顺序，不新增时间排序或稳定快照。

## 为什么不提供全历史 total

原实现有独立且不统一的上游边界：

- author_generation 只查看 JobManager 最近 1000 个 ID，最多保留 200 条；
  只有额外已授权可见记录能建立 `has_more`，窗口外是否有匹配任务未知。
- workflows 最多 20 个定义，每个前 50 个 run，总最多 200。
- agents 只取第 1 页 100 条；exports 只取 offset=0、limit=100。
- voice_direction 最多 100 条；subtitle_processing 最多 200 条。
- adaptation 仅遍历最近 200 个 proposal，再最多返回 200 个 task，裸 list 不报告截断。
- review_inbox 的 `has_more` 还可能来自内部 unavailable，不代表存在可翻取的下一页。

中央另外只检查每个 reader 的 `rows[:200]`。其他原 owner 可能先物化更多历史再返回，
所以新增分页减少的是响应量，不承诺按页减少底层 I/O 或执行真正数据库分页。
不汇总原 owner 的 `total`，不把未支持的 `truncated` 字段新增为全量证明。
若要遍历全部历史或精确全历史计数，需要原 owner 另行提供权限感知的遍历/计数合同。

本次聚合不是跨 owner 原子快照，也不是跨请求快照。任务增删、状态、权限或 owner 顺序变化，
都可能改变后续页边界。筛选或项目/分支变化应重新从 offset=0 读取；任务动作仍由原 owner
单条重读、CAS、权限和执行确认合同约束。

## 安全与错误顺序

保留原全局 middleware 的开发 loopback、packaged bootstrap session、协作 trusted session，
再由原 route 检查 `workspace_tools_v2` 和 `_workbench_authorize(..., domain.read)`。
新分页参数在该 access 完成后解析，非法值返回固定、不回显输入的：

```json
{"detail":{"code":"EXPERIMENTAL_INVALID","message":"TASKCENTER_QUERY_INVALID"}}
```

原 q 长度与 failed_only 类型的 FastAPI 校验仍在 endpoint access 前；本切片不改变其旧顺序。
TaskCenter 不采用 Production 独立 Host provenance / NEUTRAL_STUDIO 门禁，也不新增绕过。

原 reader 自身权限及 `_task_in_scope` 保留，exports 的 permission_context 检查不变。
全局 reauthorize 仍在聚合开始、每个 reader 前、最终返回前，位于原 reader 异常捕获之外。
读中撤销全局成员资格仍拒绝整个响应，不能变成成功空页或部分成功。

原 owner 的 403/404 静默略过，401/其他错误保留静态 SOURCE_UNAVAILABLE。
完全不可见的行或隐藏源不能贡献 count、has_more、next_offset、动态覆盖统计或源截断提示。
不返回 hidden_count、denied_count、原始扫描计数、拒绝 owner 列表或原异常细节。

## 验证

新增 `tests/test_taskcenter_query_backend.py`，既包含聚合边界单元测试，也包含实际
app.main 挂载的 `/api`、`/api/v1`、真实 File 项目/成员资格/权限和原 semantic_import reader。
author_generation 与 adaptation 测试调用原投影函数验证其既有窗口，不声称全历史可达。
不调用 provider、模型或媒体执行器，不修改前端。

有效红测（49 例）：41 failed / 8 passed；失败为新增参数、字段与 OpenAPI 尚未实现。
首次环境尝试因 XDG 指向不可写 home 出现 setup 错误，隔离环境后才取得上述有效红测。
实现后首轮：49 passed；补齐原 fastapi 校验顺序、内部类型边界、真实读中撤权、
重复非法尾值及 packaged 保护后，独立切片最终为 **65 passed**。

第一次 10 文件合并回归（当时本切片 63 例）：**193 passed / 6 failed**，不是全绿。
6 个失败在原 collaboration/agent/export 测试，固定基线 `90c09981e7d9418c15eca4043338146aa5293549`
完整 git archive 到独立目录后，使用同 `.venv`、独立 cwd/PYTHONPATH、未修改 fixtures
复跑同 6 个 nodeid，全部同样失败：

| 原测试 | 基线与当前相同的异常/首个失败断言 |
| --- | --- |
| `test_collaboration_http_boundary_v056.py::test_collaboration_mode_allows_authorized_project_delete` | SimpleNamespace 缺少 `novels` |
| `test_phase6_agent_jobs.py::test_agent_job_review_accepts_without_applying_output` | reviewed_by 实际 `agent-job-test`，期望 `author-1` |
| `test_export_jobs.py::test_export_download_route_returns_attachment` | FakeExportService 缺少 `get` |
| `test_export_jobs.py::test_export_download_route_reports_not_ready` | FakeExportService 缺少 `get` |
| `test_export_jobs.py::test_export_lifecycle_routes_cancel_and_retry` | FakeExportService 缺少 `get` |
| `test_export_jobs.py::test_export_job_routes_apply_read_and_write_membership` | download 实际 404，期望 200 |

基线 collection hook 只核验加载证据，不替换方法：ux、ux_api、app.main 和上述三个测试模块
实际 `__file__` 均在独立 baseline-tree，SHA256 均与固定 git blob 相同；原 tasks 签名不含 limit。
独立审查另逐项比较 JUnit 的 6 个 nodeid 与 failure.message，均一致。
先前进程内替换试验仅保留为旁证，不用作最终基线结论。
不为这些既有失败扩大改动原 owner，不能将它们从合并回归结果中隐藏。

最终相同 10 文件合并复跑（本切片 65 例）：**195 passed / 6 failed**，31.35 秒。
最终 JUnit 的 6 个 nodeid 与 failure.message 再次逐字匹配上述固定归档基线。
新增 TaskCenter 65 例均通过，仍不能宣称全部合并回归通过。

验证日志和 JUnit 保存在 `.runtime/taskcenter-query-20261025/`：
`red-actual.log`、`focused-final.log/xml`、`compatibility.log/xml`、
`compatibility-final.log/xml`、`baseline-archive.log/xml`、`baseline-loaded-modules.json`。
独立审查另有 73 passed 边界探针，产品源码 SHA 未变，无 P1/P2 发现。

```sh
RUN="$PWD/.runtime/taskcenter-query-20261025"
export PROJECT_ROOT="$PWD" HOME="$RUN/home" LOCALAPPDATA="$RUN/localappdata"
export NOVEL_DATA_PATH="$RUN/data" TMPDIR="$RUN/tmp"
export XDG_DATA_HOME="$RUN/xdg-data" XDG_CONFIG_HOME="$RUN/xdg-config" XDG_CACHE_HOME="$RUN/xdg-cache"
export STORAGE_BACKEND=file CREDENTIAL_VAULT_BACKEND=memory
export CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK=true MOCK_PROVIDER=true ENABLE_CLOUD=false
.venv/bin/python -m pytest tests/test_taskcenter_query_backend.py -q \
  --basetemp="$RUN/tmp-focused-final" -o cache_dir="$RUN/pytest-focused-final"
```

合并回归使用同隔离环境，选择以下真实测试文件（不是全后端）：

```sh
.venv/bin/python -m pytest tests/test_taskcenter_query_backend.py \
  tests/test_collaboration_http_boundary_v056.py tests/test_packaged_local_session_bootstrap_v070.py \
  tests/test_p0_security_regressions.py tests/test_phase1_media_project_authorization.py \
  tests/test_phase6_agent_jobs.py tests/test_phase6_agent_authorization.py \
  tests/test_export_jobs.py tests/test_api_v1_alias.py tests/test_studio_production_query.py -q \
  --basetemp="$RUN/tmp-compatibility-final" -o cache_dir="$RUN/pytest-compatibility-final"
```

完整基线对照的源码准备方式：

```sh
PYTHON="$PWD/.venv/bin/python"
BASE="$RUN/baseline-tree"
mkdir -p "$BASE"
git archive 90c09981e7d9418c15eca4043338146aa5293549 | tar -x -C "$BASE"
cd "$BASE"
export PROJECT_ROOT="$BASE" PYTHONPATH="$BASE:$BASE/tests"
export NOVEL_DATA_PATH="$RUN/archive-baseline-data"
# 使用上述同一 Python 和其余隔离变量，执行表中六个原 test nodeid；不复制新测试或替换模块。
```

本合同交付仅为后端有限投影分页；未做前端分页接线、浏览器验收、PostgreSQL 验证或全后端测试。
