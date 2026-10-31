# 项目 scope 文档容量归属（MEASURED_ONLY，2026-10-31）

## 能力
- `app/project_capacity_scope_docs.py`：只读、有界扫描 `experimental_v1/*.json`（≤20k 文件/≤8 MiB 每文件/≤20s），解析顶层 `novel_id`，仅归属当前项目；同物理对象去重；其他项目/损坏/超限/超时分别计数，超限或超时记 UNKNOWN。
- 已接入 `capacity_diagnostics`、显式 `capacity_reconcile` 与 `CapacityAdmission.measure`：scope 文档字节计入项目 capacity used，UNKNOWN 阻塞新 reservation。
- `project_capacity.write_entries` 中 `project_scope_document` = `MEASURED_ONLY`：文档写本身尚未走 admission；不声称已完成 scope 文档写入闭环。

## 测试
`tests/test_project_capacity_scope_documents.py` 4 项：项目/他项目/损坏/缺失归属、超限 UNKNOWN、diagnostics/reconcile 包含文档字节、资产 admission 将已有 scope 文档计入基线；容量组回归 94 passed。

## 边界
真实 PG scope 文档存储（JSONB）未纳入该 File 路径；scope 文档写 admission、并发/崩溃窗口、审批竞争仍 NOT_RUN/NOT_VERIFIED。
