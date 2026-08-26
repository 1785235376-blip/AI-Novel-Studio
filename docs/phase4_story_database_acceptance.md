# Phase 4 故事资料库验收门禁

统一执行命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_phase4_story_database.ps1
```

覆盖范围：

- 世界观概要读取、修改和持久化。
- 人物资料创建与编辑，包括身份、性格、目标、位置和状态。
- 地点资料创建与编辑，包括类型、规则、氛围和状态。
- 时间线事件排序，以及人物、地点和章节关联。
- 伏笔埋设、目标回收章节、状态及关联人物和事件。
- 人物关系类型、起止事件、状态和可信度。
- 文件与 PostgreSQL 仓储共用的服务/API 契约。
- DS-v1.0 Token 检查和前端生产构建。

阶段功能已分别通过容器化 PostgreSQL 的真实 API 创建、更新与回读验证。

`-SkipBuild` 仅用于本地快速复验；阶段退出必须运行包含生产构建的完整命令。
