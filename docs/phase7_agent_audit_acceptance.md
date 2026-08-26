# Phase 7 Agent Job 审计验收

Phase 7 完成 Agent Job 导出审计的查询与交付闭环：

- `GET /api/agent-jobs/audit` 支持分支权限校验、日期筛选、分页和倒序返回。
- `GET /api/agent-jobs/audit.csv` 使用同一可信会话与分支能力边界导出审计记录。
- 审计面板支持日期筛选、分页、摘要展开和 CSV 下载。
- 展示与导出字段仅包含操作者、事件目标、时间、结果数量和安全筛选摘要；不包含凭据、提示词、上下文正文或模型输出。
- 未授权会话返回 `401`，未知或越权分支返回 `403`。

验证命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_phase6_agent_foundation.ps1
```
