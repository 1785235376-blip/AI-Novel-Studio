# 资产查询后端交付记录 · 2026-10-23

结论：`ASSET_QUERY_BACKEND_VERIFIED_FILE`。云端真实 File 存储与原应用路由验证通过；不代表 PostgreSQL 或用户整机验收。

## 基线与范围

- 仓库：`1785235376-blip/AI-Novel-Studio`（GitHub 元数据确认 public）。
- 基线：`work/hermia-frontend-refactor-20261022` / `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`，云端初始工作区干净。
- 同时核对的 `main`：`7b35e4cb4bd9efabe7cff54e67d7b24e8e469385`；本轮未修改它。
- 交付分支：`work/asset-query-backend-20261023`，从上述 V2 基线独立创建；不覆盖其他开发分支。
- 仅读取 GitHub 源码，在云端新建临时数据和隔离 Python 环境；未读取用户本地旧任务数据，未启动用户本机开发或测试。

已有 Studio 入口只有 `include_deleted` 与 `{items}`，因此在同一路由补齐 `filename` 关键词、六类 `kind` 筛选与显式分页。无分页请求保持原协议，授权及资产 owner 不变。未修改前端、生成节点、任务队列/状态或公共基础设施；无数据库迁移。

## 改动文件

| 文件 | 用途 |
| --- | --- |
| `app/creative/workspace_models.py` | 有界 Studio 查询参数合同 |
| `app/creative/workspace_api.py` | 原 GET 路由接参；仅该路由的安全校验错误 |
| `app/creative/workspace.py` | 原 owner 隔离后组合过滤、同租约计数与稳定分页 |
| `tests/test_studio_asset_query.py` | 临时真实 File owner + 原 app.main 挂载路由集成测试 |
| `docs/studio_asset_query_backend.md` | 请求/响应、分页/错误、前端接入及限制 |
| `docs/delivery/ASSET_QUERY_BACKEND_20261023.md` | 本交付记录 |

## 验证

云端 Python 3.12.14；FastAPI 0.161.1、Starlette 1.9.0、Pydantic 2.14.1、httpx 0.28.1、pytest 8.4.2。依赖按仓库 `.[dev]` 安装，没有修改依赖清单。

从仓库根目录运行（`python` 为安装 `.[dev]` 的隔离解释器）：

```bash
env PROJECT_ROOT="$PWD" \
  LOCALAPPDATA="$PWD/.runtime/asset-query/appdata" \
  NOVEL_DATA_PATH="$PWD/.runtime/asset-query/bootstrap" \
  MOCK_PROVIDER=true ENABLE_CLOUD=false CREDENTIAL_VAULT_BACKEND=memory STORAGE_BACKEND=file \
  python -m pytest -q \
  tests/test_studio_asset_query.py tests/test_asset_library.py tests/test_asset_safety.py \
  --basetemp="$PWD/.runtime/asset-query/final-pytest" --tb=short
```

实际结果：**41 passed, 3 warnings in 8.91s，退出码 0**。其中新增集成 37 项、原有回归 4 项。警告来自已有 Starlette 测试客户端弃用和两个既有 schema 字段命名；没有以跳过或 mock 存储替代通过。

覆盖组合过滤、Unicode 字面子串、255 字边界、六种真实类型、空关键词、创建时间顺序和 ID 平局、连续页/总量/默认值/空页/上界、19 组非法输入固定安全 422、损坏临时元数据排除，以及真实项目/分支/会话/成员/权限/特性/私密 owner/项目重建隔离。测试只替换服务的临时真实存储实例，原路由、中间件、会话解析与权限判断仍执行。

基线对照：在独立云端 worktree 的原始 `6ba25ad` 上复制同一测试文件，运行：

```bash
python -m pytest -q tests/test_studio_asset_query.py \
  -k 'combined_filename_kind_filter or name_search_is_unicode_casefold_literal_substring or pagination_total_stable_ties_and_boundaries or invalid_query_returns_fixed_safe_error' \
  --basetemp="$PWD/.runtime/asset-query/red-pytest" --tb=short
```

使用相同隔离环境变量，实际 **22 failed, 15 deselected, 3 warnings in 9.18s，退出码 1**（预期红灯）：原版忽略查询参数、没有分页字段，也未拒绝非法新参数。未将这次对照宣称为产品测试通过。

## 公开范围与未完成项

仅六个列明文件进入交付；新增数据均为测试合成内容或文档占位符。定向敏感信息扫描与人工 diff 审查无命中；不上传运行目录、缓存、凭据、用户内容、环境文件或原始临时存储。独立审查未发现阻断问题。

PostgreSQL 项目 owner、GitHub Actions、用户整机与前端端到端验证本轮未运行。无前端接线；分页客户端需按接口文档显式接入新 envelope。无跨请求快照、标签/内容/语义/跨项目搜索和性能基准。总量是原 owner 判为可见的匹配元数据条数，不能解读为可下载或已审核数量。推送及远端 HEAD 读回信息以本次任务最终交接为准。
