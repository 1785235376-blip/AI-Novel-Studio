# Studio 资产查询后端交接

基线：`work/hermia-frontend-refactor-20261022` / `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`。
沿用现有 `GET /api/projects/{nid}/studio/assets`，未新增端点、迁移、写操作或身份体系；未修改前端、生成节点、任务队列与任务状态。

## 请求与兼容性

| 参数 | 默认值 | 真实支持范围 |
| --- | --- | --- |
| `q` | 无过滤 | 最多 255 字符；去首尾空白后，以 Unicode `casefold` 子串匹配 `filename`；空串/普通空白视为无过滤；C0/DEL 控制字符非法 |
| `kind` | 无过滤 | 精确匹配 `image`、`video`、`audio`、`model`、`text`、`prompt`，大小写敏感；空值/其他值非法 |
| `limit` | 分页时 50 | 整数 1–100 |
| `offset` | 分页时 0 | 整数 0–1,000,000 |
| `include_deleted` | `false` | 原有布尔参数；`true` 包含当前可见的已软删除记录 |

`q` 与 `kind` 取交集。不传 `limit` 和 `offset` 时，保持原 `{ "items": [...] }` 契约，包括只传关键词/类型的情况。显式传入其中任一分页参数才返回分页 envelope；`offset=0` 也会启用分页。错误不会自动截断或钳制为合法值。

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
- 这是当前项目/分支内的完整元数据扫描；没有跨项目全库搜索，也不搜索资产内容、语义或统一标签。底层 `kind` 是自由字符串；六类枚举仅属于本次 Studio 查询合同，无类型筛选仍保留其他合法既有记录。
- 继承原 owner 对不可读/非法基础元数据、不可见记录的排除规则；`total` 不含这些记录，也不是磁盘文件数或可下载/已审批资产数。资产字节不可用时仍可能保留既有 `CONTENT_UNAVAILABLE` 投影；其他现有校验失败（如资产版本损坏）仍报错，不伪装为空结果。
- 单次扫描/筛选/计数/投影共用原资产租约。不同请求之间没有快照或游标保证；新增/删除等变动可能移动页边界，刷新后从首项重新读取。此实现没有新增索引，也没有性能基准结论。

## 错误与安全边界

非法类型、超长/控制字符关键词、负数/越界/非整数分页及非法原有布尔参数：HTTP 422，`code=EXPERIMENTAL_INVALID`，固定 `message=ASSET_QUERY_INVALID`。局部校验不回显请求值、磁盘路径或内部异常。主应用仍使用既有统一错误 envelope（含 `detail`、`code`、`message`、`details`、`request_id`）。

现有功能开关、会话、成员资格、`domain.read` 权限、分支和项目生命周期验证保持原义；未启用/不存在的资源及拒绝访问沿原 401/403/404 约定，协作模式缺少分支头仍为 400 `BRANCH_SCOPE_REQUIRED`。拒绝访问不是空素材库。查询不把调用者身份透传成新的私密资产授权，原列表隐藏的个人候选资产继续隐藏，计数也不暴露它们。响应保留 `Cache-Control: no-store`。

## 前端接入与未完成项

当前前端严格解码 `{items}`，可继续使用原请求。后续接入分页时，需要由前端开发线先扩展解码器接受上述 envelope，再显式发送 `limit`/`offset`；用 URL 查询参数编码关键词，复用原传输层和当前项目/分支上下文。筛选条件或项目/分支变化后将 `offset` 置 0，空白关键词可省略。无需调用模型或写入接口。

本轮不含前端接线、标签/内容/语义/跨项目搜索、游标快照和性能优化。PostgreSQL 项目 owner 的端到端验证未运行；资产 owner 仍沿用既有 File 存储，没有数据库迁移。云端 File 集成与回归结果见本分支交付记录。
