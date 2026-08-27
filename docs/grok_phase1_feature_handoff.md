# Grok Phase 1 功能侧收口（给 Codex 合并）

> 日期：2026-08-28  
> 分支：`grok-phase1-feature-closure`（基于 `grok-phase1-acceptance`）  
> 操作者：Grok  
> 目的：把第一阶段窗口业务缺口补到功能侧，明天 Codex 只做合并与总结，不必再实现同一批能力。

## 先读这 8 行

1. **不要把 DesktopHost 窗口门禁写成 PASS。** DH-01 至 DH-08 仍是 `BLOCKED`，直到真实 Windows DesktopHost（构建 `0.7.0`，DLL SHA-256 `98F02E42A9E7A50CE94D6A748F3D226E869890396D1256AC8CEABCC81A08A740`）在人工窗口里跑完。
2. **当前版本不是 V1.0 正式发行物。** 仍是 `0.7.0` beta 工程版。
3. **不要用 Playwright / 后端 API / 启动截图替代窗口证据。**
4. **不要修改、删除或跳过四个既有 Python 基线缺陷：** 并发生成幂等性、visual continuity scene jump、user preference 返回字段契约、world rule payload normalization。
5. **不要进入第二阶段。** 本分支只收口 Phase 1 窗口诚实性：概览、研究资料、Agent `VALIDATED`、视频 fail-closed。
6. **确定性 Agent 不再是 `COMPLETED`。** 默认/deterministic 执行为 `VALIDATED`，文案「契约校验，未调用模型」，没有审核/应用到正文入口。`review`/`apply` 测试已改为 mock 的 `execution_mode=model`。
7. **未配置视频 Provider 时不得出现 `SUCCEEDED` 或 `placeholder://video/*`。** `DeterministicVideoProvider` 现在 `health_check=False` 且 `generate` 抛 `VIDEO_PROVIDER_NOT_CONFIGURED`。
8. **研究资料走 durable sidecar：** File 与 PostgreSQL profile 都是 `v1_capabilities/research.json`，不是 PostgreSQL 原生表。

## 相对 `grok-phase1-acceptance` 的功能变更

### DH-02 项目概览

- 窗口从 `WritingGoalPanel` 换成 [`frontend/src/novel/NovelOverviewPanel.tsx`](../frontend/src/novel/NovelOverviewPanel.tsx)。
- `GET /api/novels/{id}/overview` 现在返回：
  - 真实计数：章节、人物、地点、时间线、伏笔、世界规则、研究资料
  - `content.word_count`（章节 `word_count` 为空时回退正文长度）
  - `writing_goal`、`pending_items`、`recent_activity`
  - `placeholder: false`（禁止「服务尚未接入」伪装成已实现）
- 世界规则计数通过 `v1_capability_service.bind_lore` 读取 lore proposals，避免循环导入。

### DH-03 研究资料

- 窗口从 `CapabilityPlaceholder` 换成 [`frontend/src/novel/ResearchPanel.tsx`](../frontend/src/novel/ResearchPanel.tsx)。
- 已覆盖：新建、来源/状态/标签筛选、编辑保存、409 版本冲突、删除二次确认、小说隔离。
- API 客户端：`api.listResearch / createResearch / updateResearch / deleteResearch`。
- 路线图卡片改为「部分接入」，API 前缀改为 `/api/v1/novels/{id}/research`。

### DH-05 Agent 诚实状态

- [`app/services/agent_job_service.py`](../app/services/agent_job_service.py)：
  - terminal 集合加入 `VALIDATED`
  - deterministic execute → `VALIDATED`，`execution_label="契约校验，未调用模型"`，`model_called=False`，空 proposals/findings
  - `review`/`apply` 拒绝 deterministic / `VALIDATED`
- 前端 [`AgentTeamPanel.tsx`](../frontend/src/novel/AgentTeamPanel.tsx) / [`AgentJobDetail.tsx`](../frontend/src/novel/AgentJobDetail.tsx)：
  - 轮询/busy 把 `VALIDATED` 当终态
  - 不渲染审核/应用入口
  - 明确展示「空结果不是创作完成」

### DH-06 视频 fail-closed

- [`app/asset_providers.py`](../app/asset_providers.py)：`DeterministicVideoProvider` 不再返回 `placeholder://video/{task_id}` 成功。
- [`app/services/screenplay_service.py`](../app/services/screenplay_service.py)：
  - 创建 Motion Task 时写入可追踪首尾帧（`shot:` / `asset:` / 已有 http(s)）
  - 未配置真实 Provider 时任务保持 `PENDING` + `VIDEO_PROVIDER_NOT_CONFIGURED`
  - `generate` / attach / callback 拒绝 `placeholder://`
- 前端 [`MotionTaskWorkspace.tsx`](../frontend/src/novel/MotionTaskWorkspace.tsx) 不渲染 placeholder 视频，并展示配置缺失。

## Codex 合并时需要知道的测试契约变化

| 测试 | 变化 |
| --- | --- |
| `tests/test_phase6_agent_jobs.py` | 默认 deterministic 生命周期断言改为 `VALIDATED`；review/apply 走 `complete_model_job()` |
| `tests/test_phase1_feature_closure.py` | **新增**：overview / research 隔离冲突删除 / VALIDATED / motion PENDING |
| `frontend/src/novel/NovelOverviewPanel.test.tsx` | **新增** |
| `frontend/src/novel/ResearchPanel.test.tsx` | **新增** |
| `frontend/src/novel/AgentTeamPanel.test.tsx` | 期望 `VALIDATED`，且没有「采纳结果」「应用已审核修改」 |
| `frontend/src/novel/MotionTaskWorkspace.test.tsx` | 增加 placeholder 不渲染断言 |

聚焦验证（Linux 沙箱，2026-08-28）：

- `pytest tests/test_phase1_feature_closure.py tests/test_phase6_agent_jobs.py tests/test_p1_regression.py tests/test_phase1_video_runtime.py` → **40 passed**
- 唯一失败仍是既有基线缺陷 `test_visual_continuity_reports_scene_jumps`（缺 `TIME_JUMP_CUT`）。**未改该测试，也未改 `validate_visual_continuity`。**
- `vitest` 聚焦 NovelOverview / Research / AgentTeam / MotionTaskWorkspace → **9 passed**

四个基线缺陷测试不要改、不要 skip、不要 xfail。

## 建议合并方式

1. 从本分支 `grok-phase1-feature-closure` 向 `grok-phase1-acceptance`（或你们约定的集成分支）开 PR。
2. 不要 squash 掉 handoff 与测试契约说明。
3. 冲突时优先保留本分支的 Agent `VALIDATED` 与视频 fail-closed；不要把 `DeterministicVideoProvider` 的 placeholder 成功 URI 加回来。
4. 合并后更新总结：功能侧已收口，窗口门禁仍待 Windows 操作员。

## 明确未完成（不要在总结里写成已完成）

- DH-01 启动窗口可见 / WebView2 / loopback
- DH-04 正常关闭后重启持久化
- DH-07 单实例 mutex 回收
- DH-08 本轮 DesktopHost/Backend/PostgreSQL 日志审计
- 真实视频 Provider 配置后的 SUCCEEDED 路径（本阶段要求 fail-closed，不是假成功）
- 第二阶段能力（角色成长轨迹、视觉记忆、外部网络研究检索、真实模型创作闭环等）
