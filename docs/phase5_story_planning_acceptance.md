# Phase 5 剧情规划验收门禁

统一执行命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_phase5_story_planning.ps1
```

覆盖范围：

- 小说主题、故事前提、结构、三幕内容、主要冲突与高潮。
- 卷顺序、创作目标、摘要、章节范围和状态。
- 场景顺序，以及卷、章节、地点、人物关联。
- 场景目标、冲突、结果和生命周期状态。
- 原剧情、结局 A/B、隐藏路线和其他剧情分支。
- 路线父子关系、分歧章节、共享基线截止章节和无效父路线拒绝。
- 文件与 PostgreSQL 仓储共用的服务/API 契约。
- DS-v1.0 Token 检查和前端生产构建。

默认情况下 Docker 不可用只会产生警告，便于离线开发环境执行逻辑门禁。阶段发布前应运行严格模式：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_phase5_story_planning.ps1 -RequireDocker
```

严格模式要求 Docker 引擎可用；随后还需完成容器重建和 PostgreSQL 真实 API 回读验证。

`-SkipBuild` 仅用于本地快速复验，不能作为阶段退出结果。
