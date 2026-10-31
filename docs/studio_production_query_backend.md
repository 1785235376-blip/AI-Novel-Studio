# Studio Production 任务查询后端合同

范围：只解决 Production `G-AUD-1` 的 owner/operation 筛选与响应分页。
沿用 `GET /api/projects/{nid}/studio/production/jobs`（已有 `/api/v1` 别名同样适用），
不修改 TaskCenter `GET /api/novels/{nid}/experimental/workspace/tasks`，不宣称解决 `G-TC-1`。
不修改前端、SDK、正式 owner、权限体系、数据库结构或任务状态。

## 参数与兼容性

| 参数 | 缺省 | 支持范围 |
| --- | --- | --- |
| `owner` | 无筛选 | 精确 `image`、`audio`、`video`、`timeline` |
| `operation_id` | 无筛选 | 下列现有操作标识之一，精确匹配 |
| `limit` | 启用分页时 50 | 整数 1–100 |
| `offset` | 启用分页时 0 | 整数 0–1,000,000 |

操作标识复用原 `MediaOperation`，另含原 Timeline 的 `m9.timeline.multitrack`：

- `m5.image.t2i`、`m5.image.i2i`、`m5.image.cutout`、`m5.image.reference`、
  `m5.image.inpaint`、`m5.image.upscale`、`m5.image.composite`
- `m7.video.t2v`、`m7.video.i2v`、`m7.video.v2v`
- `m8.audio.speech`、`m8.audio.music`、`m8.audio.effects`、`m8.audio.trim`
- `m9.timeline.multitrack`

`owner` 是原返回项的执行 owner，不是输出资产类型，也不新增 `kind` 别名。
例如 Timeline 输出可能为 video/audio，但 `owner` 仍为 `timeline`。
两个筛选条件取交集；合法但不相容的条件返回空匹配集合，不扩大权限或猜测意图。
大小写、空串和两端空白均不归一化，非法枚举拒绝。

不传 `limit` 与 `offset` 时，严格保留原 envelope：

```json
{"items": [], "product_acceptance": "LOCAL_REQUIRED"}
```

仅传 owner/operation 筛选也保持上述形状。显式传入任一分页参数（含 `offset=0`）
才返回以下 envelope：

```json
{"items": [], "total": 0, "limit": 20, "offset": 0, "has_more": false, "product_acceptance": "LOCAL_REQUIRED"}
```

每项仍为原 `studio-production-job/1` 完整投影，字段和值不变。服务内部未传 query 的
调用仍返回完整原结果，尤其 Graph、Safe Batch、Audio Manifest 的发现与恢复路径，
不会隐式只返回前 50 条。原 graph/benchmark/batch server-only binding 参数保留。

请求示例：

```http
GET /api/projects/project-a/studio/production/jobs?owner=audio&operation_id=m8.audio.speech&limit=20&offset=0
X-Session-Token: <原有有效 Host 会话>
X-Branch-ID: <原有协作分支，仅适用时提供>
```

重复标量取最后一个值，沿用已有 Studio 查询线值约定：`limit=1.0` 和 `offset=0.0`
解码为整数，`1.5` 非法。未知查询参数延续旧路由忽略行为，不新增其他筛选能力。
不截断、不钳制非法参数。OpenAPI 显式列出这四个可选参数，实际解析延迟到原授权之后。

## total、排序与一致性

原顺序保持 `(created_at or "", id)` 降序。先完成各原 owner 的完整读取、回执验证、
actor/project/branch/incarnation 可见性，以及 Graph/Benchmark/Batch 准入和原投影，
再筛选、计数与切片。`total` 是本次成功读取并通过所有原准入、匹配筛选的任务数，
不是全局任务数、资产数、执行成功数或某 owner 的原始文件数。

`offset >= total` 返回空 items 和准确的本次 total，`has_more=false`。has_more 表示
本次匹配集合在当前页之后还有条目。原始无 query 调用与仅筛选调用不增加 total 字段。

这不是跨 owner 原子快照，也不是跨请求快照。三个原 owner 分别读取；读取期间或翻页间
任务增删/状态变化可能改变后续结果或页边界。没有 cursor、源版本 token 或稳定快照保证。
客户端切换项目/分支/筛选应回到 offset=0；采取任务动作仍须单条重读并使用原 CAS 合同。

## 安全与失败顺序

延续现有 `narrative_production_v2`、会话、成员资格、NOVEL `domain.read`、分支、
项目 incarnation、Host provenance 与 `NEUTRAL_STUDIO` 激活检查。
只有上述原检查通过后才解析新查询。非 packaged 协作环境的原 Host 拒绝规则不变，
本切片不让普通协作会话绕过 Host 限制，也不新增权限授权。

非法查询统一为 422 `EXPERIMENTAL_INVALID`，固定 message `STUDIO_PRODUCTION_QUERY_INVALID`，
不回显请求值、Pydantic input 或路径。拒绝访问与非法查询同时存在时保留原拒绝：
缺分支 400、无效/撤销会话 401、权限/成员资格/Host 拒绝 403、功能关闭或不存在项目 404。
未激活项目仍为原 422 `STUDIO_NEUTRAL_PROJECT_ACTIVATION_REQUIRED`，优先于新查询错误。
主应用统一 error envelope 与 `Cache-Control: no-store` 保持；成功响应仍有 nosniff。
所有原读后 guard 保留，查询筛选和分页之后再校验权限。最后 guard 到发出响应之间的
原并发窗口并未由本切片消除。

坏回执、失效绑定和 owner 容量错误不能被筛选或 offset 隐藏，也不会伪装成空列表。
私密 graph/benchmark/batch 任务不出现在独立 Production 列表和 total 中；带相应原
server binding 的内部调用仍执行各自既有准入。客户端 query 不可提供这些授权 binding。

## 存储与性能边界

- 仅分页响应项数有界，不新增索引、后台任务、内容读取、provider 调用或调度。
- image 仍整份 actor/project/branch JSON 读取、验证；原新建容量 200，不在 list 中截尾。
- audio 仍读取完整原状态和历史，保持已有线性遍历/重复 ID 验证；不截断历史。
- video/timeline 共享原 actor/project/branch/incarnation 目录；原新建上限 100。
  list 完整枚举目录，超过 100 时整请求拒绝 `STUDIO_TIMELINE_JOB_LIMIT`，不是返回前100。
  保留原失败且不返回 items/total，因此成功 total 不掩盖被截断的 video/timeline 尾部。
- 原 owner 读取/验证成本仍至少随完整当前队列增长；聚合排序为 O(N log N)，持有完整
  元数据投影。分页不等于 O(limit) 存储成本，也不新增统一 I/O、内存或墙钟预算。
- 查询不改任务源数据；原 owner 首次读取可能创建项目 incarnation/协调锁文件。
  零源写入断言以已初始化项目为基线，不把原锁文件误报为新任务写入。

## 验证边界

`tests/test_studio_production_query.py` 覆盖真实挂载 File/API image 队列、原 audio 队列、
video/timeline 原 receipt writer/reader 的合成 QUEUED 元数据、筛选交集、降序分页、
精确 total、空页/边界、内部完整结果、私密 binding、actor/项目/分支/incarnation 隔离、
原权限拒绝优先级、读中会话撤销、坏回执/容量 fail-closed、源字节不变与参数文档。
合成 video/timeline 元数据测试不代表真实任务入队/模型推理或输出已验收。

不声称前端已接入、TaskCenter 已分页、真实 provider/GPU、远端 CI、Windows Host、
PostgreSQL 端到端或完整后端全量测试通过。具体命令、退出码和本地结果随本次交付记录。

### 2026-10-25 本地验证记录

源码基线为 `4c5535481158de3ce7f0e7dbe5aa00d7058eccec`，在独立后端分支验证。
所有测试使用仓库 `.venv`、临时 File owner 和 `.runtime/production-query-20261025` 隔离目录。
未调用外部 provider，也未修改正式用户源数据。

| 阶段 | 结果 | exit |
| --- | --- | --- |
| 最初环境尝试 | collection 因继承的 XDG_DATA_HOME 指向不可写目录失败；隔离 XDG 后重跑 | 2 |
| 原产品代码 + 首批新增回归 | 18 failed / 1 passed，失败为缺少筛选、分页、非法查询校验 | 1 |
| 修改后首批回归 | 19 passed | 0 |
| 扩展 File/API 权限与 owner 回归 | 37 passed | 0 |
| 最终独立新增测试 | 41 passed，11.95 秒 | 0 |
| 新增 + 原 Production 兼容集 | 293 passed / 122 skipped，79.30 秒 | 0 |
| PostgreSQL 标记收集核对 | 122/415 collected，293 deselected；122 skip 均为原 PostgreSQL 专属用例 | 0 |
| `git diff --check` | PASS | 0 |

3 条 warning 为原模型 `schema` 属性命名和 Starlette/httpx deprecation，不是新增功能失败。
跳过 PostgreSQL 不是 PostgreSQL 通过，也不是全部后端测试通过。

运行环境（从仓库根目录）：

```sh
RUN="$PWD/.runtime/production-query-20261025"
export PROJECT_ROOT="$PWD" HOME="$RUN/home" LOCALAPPDATA="$RUN/localappdata"
export NOVEL_DATA_PATH="$RUN/data" TMPDIR="$RUN/tmp"
export XDG_DATA_HOME="$RUN/xdg-data" XDG_CONFIG_HOME="$RUN/xdg-config" XDG_CACHE_HOME="$RUN/xdg-cache"
export STORAGE_BACKEND=file CREDENTIAL_VAULT_BACKEND=memory
export CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK=true MOCK_PROVIDER=true
.venv/bin/python -m pytest tests/test_studio_production_query.py -q -rs \
  --junitxml="$RUN/focused-final.xml" --basetemp="$RUN/pytest/focused-final"
```

原代码红测命令是同一新增文件的 `-q`，`--basetemp="$RUN/pytest/before2"`。
聚合命令：

```sh
.venv/bin/python -m pytest \
  tests/test_studio_production_query.py tests/test_cloud_formal_canvas_node.py \
  tests/test_cloud_canvas_node_resume.py tests/test_cloud_canvas_node_observe.py \
  tests/test_cloud_canvas_queue_recovery.py tests/test_cloud_canvas_create_recovery.py \
  tests/test_cloud_canvas_node_job_observation.py tests/test_cloud_canvas_node_job_discard.py \
  tests/test_cloud_canvas_node_target_observation.py tests/test_cloud_canvas_node_target_view.py \
  tests/test_studio_canvas_video_bridge.py tests/test_studio_canvas_audio_return.py \
  tests/test_studio_canvas_audio_envelope.py tests/test_studio_canvas_video_audio.py \
  -q --basetemp="$RUN/pytest/compatibility"
```

同一文件集合以 `--collect-only -q -m postgres_backend_only` 核对原跳过用例。
本机日志与逐条退出码保存在上述隔离目录的 `before2.log`、`before2-exit.txt`、
`focused-final.log`、`focused-final-exit.txt`、`compatibility.log`、`compatibility-exit.txt`、
`postgres-collection.log`、`postgres-collection-exit.txt`。这些运行产物未加入源码。
