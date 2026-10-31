# M2 · 一致性元数据游标

承接 M1 commit `21d82b7138cd7d033c73a236b902caf164644284` / tree `c6bd8b0c1f2dbd9d4e4f110e15a3ad661df1fa0d`。本阶段继续沿原 `GET /api/projects/{nid}/studio/assets`，显式 `page_mode=cursor` 启用新模式，默认 `limit=50`，范围 1–100；与任何 `offset` 互斥。不改变无分页和 offset 的原完整投影。前端尚未接线。

## 请求及响应

```http
GET /api/projects/project-a/studio/assets?page_mode=cursor&q=cover&kind=image&limit=20
X-Session-Token: <已有会话>
X-Branch-ID: <协作模式当前分支>
```

```json
{"items":[],"total":0,"limit":20,"has_more":false,"next_cursor":null,"projection":"asset-metadata/1"}
```

有后续页时 `next_cursor` 是不透明字符串；后续请求保留相同规范化条件/limit，添加该 cursor。每项只包含 `id, filename, kind, media_type, size, sha256, version, created_at, updated_at, deleted_at`，缺失可选值为 null。不读取或输出 lineage/关系/内部参数，不把元数据摘要写成已通过字节完整性校验。需要原完整详情或内容时走既有单资产接口。

固定升序 `(created_at, id)`，按唯一 ID 决胜；`total` 是相同数据版本的全部可见匹配数量，不是剩余数量。稳定集合遍历无重无漏。发现源版本变化整页 409 `ASSET_QUERY_RESTART_REQUIRED`，前端丢弃旧 token 并从首屏重启；不返回混合 items/total。

## 版本、安全与并发边界

游标 HMAC-SHA256 绑定实际项目/分支/项目 incarnation、原调用者、规范化 q/kind/include_deleted/limit、排序/投影版本和功能集合；源版本覆盖整个资产元数据目录的 fingerprint。其他项目正常资产变动也可能保守触发重启，不暴露其数量或标识。权限每页重新走原 invoke，游标从不代替会话或授权；最终原 guard 仍检查项目/会话/权限。

900 秒固定期限从首页签发开始，续页不滑动延长。token 最多 2,048 ASCII 字符、认证后 payload 最多 1,024 bytes，限制键集合/类型、重复键与 JSON 复杂度；校验 MAC 后才解析 JSON。篡改、跨范围或条件复用为固定 422 `ASSET_QUERY_INVALID`；过期或相关源版本变化为固定 409 重启错误；均保留 M0 权限拒绝优先级和 no-store，不回显输入。

源版本读前后检查及原资产租约仅覆盖 Asset 元数据，不承诺跨 chapter/screenplay/job owner 原子快照，因此新模式使用明确的元数据投影。忽略锁的外部 writer 若在最后一次源检查后变更，及撤权发生在最后权限 guard 后，仍存在到响应发送之间的窗口。没有宣称彻底消除这些竞态。

独立签名 key 与 identity marker 保存在私有派生目录，重建索引保留它们；已初始化 key 丢失/变化/部分写入明确不可用，不静默轮换。完整丢失 key+marker 无法区分首次创建，重新创建身份后旧 token 不能验签。仅在具备安全 POSIX dir-fd/no-follow 原语的运行环境开放 key 文件操作，其他平台明确 503 `ASSET_QUERY_CURSOR_UNAVAILABLE`，不放宽系统设置。

## 验证记录

Python 3.12.14、FastAPI 0.161.1、Starlette 1.9.0、Pydantic 2.14.1、httpx 0.28.1。M0/旧查询/M1索引路由兼容性组 **53 passed, 3 warnings in 8.31s**。随后独立审查发现并修复末页查询中TTL过期、嵌套损坏元数据投影和原始cursor经自动trim绕过长度界限三处问题；补18项真实路由回归。

最终codec+真实File/原应用路由组 **101 passed, 3 warnings in 7.93s，exit 0**；另一独立检查者在独立临时存储复验同组 **101 passed in 8.96s**。两次是同一组101项的独立执行，不相加。含52项codec/key生命周期与49项路由验证。没有把初版83项通过当作三处新增边界已经验收。

```bash
# 带M0文档所列隔离环境变量，使用项目dev venv
python -m pytest -q tests/test_asset_query_cursor_codec.py tests/test_studio_asset_query_cursor.py \
  --basetemp="$PWD/.runtime/asset-scale/cursor-pytest" --tb=short
python -m pytest -q tests/test_studio_asset_query_authority.py tests/test_studio_asset_query.py \
  tests/test_studio_asset_query_indexed.py --basetemp="$PWD/.runtime/asset-scale/m2-compat" --tb=short
```

覆盖组合过滤/稳定遍历/空结果、插入/删除/重命名/类型变化、读中变化、撤销成员/授权及最后guard、项目重建、跨项目/分支/调用者/条件复用、篡改、过期、固定TTL、错误优先级；原始token空白/长度与损坏scalar投影均有真实路由验证。密钥POSIX冷重开及中断是独立进程，签名测试不冒充完整数据库测试。真实 PostgreSQL、前端集成、跨 owner 快照：`NOT_RUN`。
