# 可重建便携导出缓存预算（U14 / STORE-05）

预算范围是**当前用户、当前项目 scope 的可核实重建便携导出缓存**。scope 沿用原项目、工作区、故事线和分支上下文；策略保存在原 scoped store 中，继续由便携项目 owner 管理。界面位于“项目便携与资源恢复 → 存储分类与清理预览”。

预算是建议值。保存预算、读取占用或采用计划均不删除文件，也不阻止继续导出。没有后台淘汰或全盘缓存扫描。正文、历史、回收站、正式资产、恢复输入、模型和媒体不属于预算回收目标。

## 策略与占用

首次读取返回 `{ "version": 0, "limit_bytes": null }`，不创建策略或缓存文件。上限使用非负整数字节数，最大 `9007199254740991`；`null` 表示未配置，`0` 是有效预算。每次保存使用 `expected_version` 做 CAS，包含改回相同数值的保存也递增版本。冲突返回 409，界面保留输入；刷新发现策略版本变化后，需要明确放弃旧输入并重新填写。

`storage.cache_budget.measurement` 将可核实字节与未知占用分开：

| 字段/状态 | 含义 |
| --- | --- |
| `MEASURED` / `bytes` | 本次成功校验的可重建导出缓存占用 |
| `UNKNOWN` / `bytes: null` | 存在无法读取或校验的相关导出记录；不是零字节 |
| `verified_reproducible_bytes` | 已核实的部分，与本次 `eligible` 字节和一致 |
| `unmeasured_records` | 无法核实的相关导出记录数；不向客户端暴露本机路径或异常详情 |
| `UNCONFIGURED` | 没有设置预算，不生成预算计划 |
| `WITHIN_BUDGET` / `OVER_BUDGET` | 完整测量且已配置预算时的比较结果 |

已确认不存在的缓存文件不产生占用。来源已变化、因而不能重建的旧导出不进入可清理候选，仍由原恢复分类保留；这份预算不代表它们或整个磁盘的大小。存在未知项时，超额与剩余超额均为 `null`，预算计划为空。原清理入口仍可在明确确认后处理独立核实过的候选。

## 回收计划与确认

计划只使用原 `storage.eligible` 候选：当前用户创建、`READY` 导出、当前来源仍授权且摘要一致、缓存内容 SHA-256 正确、可重建 manifest 一致。按创建时间、记录 ID 排序，从最旧记录开始，选到足以消除超额为止。每批沿用原清理请求的 100 条上限；`remaining_excess_bytes` 和 `complete` 明示是否还需下一批。

“采用预算回收计划（尚不清理）”只选择记录 ID。用户核对选定清单并勾选后，才向原清理入口提交 `record_ids`、`preview_digest`、`confirmed: true`，不提交目录或任意路径。也可明确选择最多 100 条已核实候选。

预览摘要绑定原 scope、用户、当前授权来源、可核实缓存、策略版本与测量结果。预算编辑、刷新或选集变化会撤销界面确认；服务端重新预览并核对摘要，在原删除前授权复核之外再次检查策略、来源与候选。策略修改后再改回、来源改变、候选字节改变等情况需要重新预览。成功清理只移除原 owner 管理的可重建 ZIP；原下载入口在来源仍有效时可以重建。

## 实现与 API

- [预算 DTO 与纯计划计算](../../app/experimental/portable_cache_policy.py)：不读写文件，不注册新缓存 owner。
- [原便携项目服务](../../app/experimental/portable_projects.py)：沿用 `_file`、来源/manifest/摘要校验、scope transaction 和显式清理。
- [原路由](../../app/experimental/portable_projects_api.py)：`GET` / `PUT /api/novels/{nid}/experimental/portable-projects/cache-policy`；PUT body 为 `expected_version` 和 `limit_bytes`。GET/PUT 成功响应均 `Cache-Control: no-store`，只返回策略版本与上限。
- [原面板](../../frontend/src/experimental/PortableProjectsPanel.tsx)：复用 captured client、共享写入锁和现有 UI primitives。读取 `GET .../storage` 的可选新增预算字段；旧响应不显示预算控件，无法核实的新预算响应停用清理确认。

功能开关 `experimental.portable_projects_v2`、可信本地 Host、原 domain.read/write 和分支权限继续生效。未改变 CI、CODEOWNERS、分支保护或共享 shell。

## 定向验证

在仓库根目录、已安装仓库所需 Python 依赖的环境运行；runner 为应用配置独立目录、memory 凭据后端、File 存储及离线 mock provider，所有删除场景只使用 pytest fixture：

```powershell
python -B scripts/run_v2_checks.py portable-budget-file -- python -m pytest tests/test_v2_portable_cache_policy.py tests/test_v2_portable_cache_policy_api.py tests/test_r4_portable_batches.py tests/test_r4_portable_maintenance.py tests/test_r4_portable_batches_mounted.py -q -m 'not postgres_backend_only' --tb=short --basetemp .runtime/v2-checks/portable-budget-file/pytest -p no:cacheprovider
```

前端在 `frontend` 目录使用已有锁定依赖：

```powershell
pnpm exec vitest run src/experimental/PortableProjectsPanel.test.tsx src/experimental/PortableProjectsBudget.test.tsx
pnpm exec tsc --noEmit --pretty false
pnpm exec vite build
```

后端测试覆盖策略持久化、用户/scope 隔离、并发创建 CAS、策略 ABA、来源在授权复核时改变、未知占用、100 条计划界限、原清理与 ZIP 重建及恢复输入保留。前端测试覆盖只读挂载、显式计划、精确 CAS body、冲突保留输入、迟到响应、失效确认与畸形预算停用清理。三种窗口尺寸的本地 fixture 检查用于验证布局和键盘操作，不代表真实用户数据清理或 PostgreSQL 验收；PG 应单独标明运行状态。
