# Studio 资产查询后端交接

基线：`work/hermia-frontend-refactor-20261022` / `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`。
沿用现有 `GET /api/projects/{nid}/studio/assets`，未新增端点、资产写入接口、正式源数据迁移或身份体系；未修改前端、生成节点、任务队列与任务状态。

## 请求与兼容性

| 参数 | 默认值 | 真实支持范围 |
| --- | --- | --- |
| `q` | 无过滤 | 最多 255 字符；去首尾空白后，以 Unicode `casefold` 子串匹配 `filename`；空串/普通空白视为无过滤；C0/DEL 控制字符非法 |
| `kind` | 无过滤 | 精确匹配 `image`、`video`、`audio`、`model`、`text`、`prompt`，大小写敏感；空值/其他值非法 |
| `limit` | 分页时 50 | 整数 1–100 |
| `offset` | 分页时 0 | 整数 0–1,000,000 |
| `include_deleted` | `false` | 原有布尔参数；`true` 包含当前可见的已软删除记录 |
| `page_mode` | 不启用 | 显式 `cursor` 启用元数据游标；与任何 offset 互斥 |
| `cursor` | 首屏不传 | 仅游标模式可传；不透明、有签名、最多 2,048 ASCII 字符，固定 900 秒期限 |

`q` 与 `kind` 取交集。未启用游标且不传 `limit` 和 `offset` 时，保持原 `{ "items": [...] }` 契约，包括只传关键词/类型的情况。显式传入其中任一分页参数才返回 offset envelope；`offset=0` 也会启用分页。错误不会自动截断或钳制为合法值。

重复标量参数沿既有规则取最后一个值；分页线值沿 Pydantic 的整数解码规则，`1.0`/`0.0` 分别解码为整数 1/0，非整数 `1.5` 非法。关键词长度在去空白之前检查。以上规则不是新一轮额外收紧。

例如（沿用已有 Studio 传输层的认证与分支头）：

```http
GET /api/projects/project-a/studio/assets?q=cover&kind=image&limit=20&offset=0
X-Session-Token: <当前已有会话令牌>
X-Branch-ID: <当前已授权分支；仅协作模式需要>
```

无匹配时的完整成功正文：

```json
{"items": [], "total": 0, "limit": 20, "offset": 0, "has_more": false}
```

有匹配时 `items` 内仍是原 Studio 资产投影，含既有 `id`、`filename`、`kind`、`version`、`provenance`、`relationships` 等字段，不新造 `name`、`asset_type` 或 `tags` 字段。旧请求 `GET /api/projects/project-a/studio/assets` 保持只含 `items`。

## 分页与总量

- 沿用原 owner 的 `(created_at, id)` **升序**，相同创建时间以资产 ID 打破平局，重复请求在数据未变化时顺序一致。
- 先应用原有项目、分支、项目 incarnation、功能开关、私密 owner 与删除可见性，再过滤、计数和分页；`total` 是本次租约内全部匹配的可见资产元数据条数，独立于当前页长度。
- `offset >= total` 返回空 `items`，保留准确的 `total`，`has_more=false`。`has_more` 表示本次结果在当前页后是否还有条目。
- 这是当前项目/分支内完整的可见匹配集合；没有跨项目全库搜索，也不搜索资产内容、语义或统一标签。底层 `kind` 是自由字符串；六类枚举仅属于本次 Studio 查询合同，无类型筛选仍保留其他合法既有记录。
- 继承原 owner 对不可读/非法基础元数据、不可见记录的排除规则；`total` 不含这些记录，也不是磁盘文件数或可下载/已审批资产数。资产字节不可用时仍可能保留既有 `CONTENT_UNAVAILABLE` 投影；其他现有校验失败（如资产版本损坏）仍报错，不伪装为空结果。
- 单次索引协调/筛选/计数/投影共用原资产租约，读前后核对源版本。旧 offset 请求之间没有快照保证；新增/删除等变动可能移动页边界，刷新后从首项重新读取。

## M1 读取预算与派生索引

原 Asset owner 仍是唯一正式资产存储。其目录下 `.asset-query-index/index.sqlite3` 是可丢弃的元数据加速副本，不是权限或存在性凭证；每个候选仍走原 `_in_scope` 与 Studio 记录校验，返回项再经原 `get`。完整投影继续使用原 lineage/relationships。

冷构建读取全目录中的源 JSON；热查询仍执行前后两次有界目录枚举/stat，使用 `(dev, inode, mode, size, mtime_ns, ctime_ns)` 检测正常替换和原地改写。精确 total 必须流式检查全部匹配候选，而非 SQL 原始 COUNT。只保留当前页 ID；无分页按原合同保留全部返回项。索引没有把全库扫描成本变成 O(页大小)，也不承诺对恶意本机管理员伪造文件元数据的防护。

明确支持预算：目录最多 200,000 entries、50,000 个 JSON，单 JSON 1 MiB、源 JSON 合计 256 MiB，索引文件 512 MiB。单请求最多 100,000 次源元数据读取/512 MiB、10,000 次资产内容读取/256 MiB；30 秒为统一协作式执行预算，包含索引、候选和投影，不是强制中断阻塞文件 I/O 的墙钟 SLA。达到预算则整个请求 503 `ASSET_QUERY_BUDGET_EXCEEDED`，不返回部分 items/total，不无限扫描回退。旧接口格式与范围内结果含义不变；超大无分页请求也受明确预算约束。

索引缺失/格式旧/损坏时在相同预算内重建，异常或不安全路径返回 503 `ASSET_QUERY_INDEX_UNAVAILABLE`；查询期间发现相关版本变化返回 409 `ASSET_QUERY_RESTART_REQUIRED`。错误不带资产计数/标识/路径，仍遵循 M0 拒绝优先级与 no-store。SQLite 内部 I/O 不包含在 Python 源文件读取计数中；索引大小另行记录。完整投影关联的其他 owner 延续原读取机制，不承诺跨 owner 原子快照或统一内存上限；测量内存是样本实测值，不能外推为硬上限。

## 错误与安全边界

非法类型、超长/控制字符关键词、负数/越界/非整数分页及非法原有布尔参数：HTTP 422，`code=EXPERIMENTAL_INVALID`，固定 `message=ASSET_QUERY_INVALID`。局部校验不回显请求值、磁盘路径或内部异常。主应用仍使用既有统一错误 envelope（含 `detail`、`code`、`message`、`details`、`request_id`）。

M0 修复后，查询解码在原 `invoke` 的项目/权限/分支/功能检查之后运行；拒绝访问与非法查询同时出现时，保留原 400/401/403/404 拒绝状态，已获准读取的请求才进入上述 422 校验。原分支的 41 项通过未覆盖六种组合优先级回归，不等于这些组合也通过。首次访问项目可能沿现有机制初始化 incarnation/锁文件；零源写入测试以已经初始化并预热的项目为基线。

现有功能开关、会话、成员资格、`domain.read` 权限、分支和项目生命周期验证保持原义；未启用/不存在的资源及拒绝访问沿原 401/403/404 约定，协作模式缺少分支头仍为 400 `BRANCH_SCOPE_REQUIRED`。拒绝访问不是空素材库。查询不把调用者身份透传成新的私密资产授权，原列表隐藏的个人候选资产继续隐藏，计数也不暴露它们。响应保留 `Cache-Control: no-store`。

## M2 游标模式

`?page_mode=cursor&q=cover&kind=image&limit=20` 返回 `{items,total,limit,has_more,next_cursor,projection:"asset-metadata/1"}`；后续页保留相同规范化条件和 limit，添加 cursor。每项仅有 `id/filename/kind/media_type/size/sha256/version/created_at/updated_at/deleted_at`，缺失可选字段为 null。此明确的新投影不含 provenance/relationships，不读取资产内容；需要内容或完整关系时使用既有单资产接口。原无分页/offset 投影不变。

排序仍为 `(created_at,id)` 升序。token 绑定实际项目 incarnation/分支/调用者、条件、功能集合、排序/投影版本与资产源版本；不是权限凭证，每页重走原授权。稳定数据集遍历无重无漏；源插入/删除/重命名/类型变化或过期返回409 `ASSET_QUERY_RESTART_REQUIRED`，整页无 items/total；篡改、跨项目/条件/调用者复用返回固定422。版本覆盖整个资产根目录，其他范围变化也可能保守触发重启。前端收到409须丢弃token从首屏重启。

读前后核对源版本，不承诺跨owner原子快照。最后版本检查或最后权限guard之后到响应发出之间仍存在并发窗口。密钥在重建/重开时保留，缺少安全POSIX文件原语的平台明确503不可用。详细合同、key生命周期与验收见 `docs/delivery/ASSET_QUERY_SCALE_M2_20261023.md`。

## 前端接入与未完成项

当前前端严格解码 `{items}`，可继续使用原请求。后续接入分页时，需要由前端开发线先扩展解码器接受上述 envelope，再显式发送 `limit`/`offset`；用 URL 查询参数编码关键词，复用原传输层和当前项目/分支上下文。筛选条件或项目/分支变化后将 `offset` 置 0，空白关键词可省略。无需调用模型或写入接口。

本轮不含前端接线、标签/内容/语义/跨项目搜索。PostgreSQL 项目 owner 的端到端验证未运行；资产 owner 仍沿用既有 File 存储，没有正式 owner 数据迁移。云端 File 集成与回归结果见本分支交付记录。
