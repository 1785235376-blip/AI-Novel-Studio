# Grok P0 作者诚实性收口（给 Codex 合并进 main）

> 日期：2026-08-28  
> 分支：`grok-p0-author-honesty`（基于 `origin/main` @ `c74b51f`）  
> 操作者：Grok  
> 目的：把审计里的 P0 诚实性补丁接到 **最新 main**，明天 Codex 只做合并与总结。

## 先读这 9 行

1. **不要把 DesktopHost 窗口门禁写成 PASS。** DH-01 至 DH-08 仍是 `BLOCKED`。Linux 沙箱不能跑 WinExe DesktopHost。
2. **当前版本不是 V1.0。** 仍是 `0.7.0` beta。
3. **不要用 Playwright / 后端 API / 启动截图替代窗口证据。**
4. **不要修改、删除或跳过四个既有 Python 基线缺陷：** 并发生成幂等性、visual continuity scene jump、user preference 返回字段契约、world rule payload normalization。
5. **不要进入第二阶段 / 不要扩多媒体范围。** 本分支只做作者侧诚实性：概览、研究资料、Agent `VALIDATED`、视频 fail-closed、章节连续性扫描、路线图诚实文案。
6. **确定性 Agent 不再是 `COMPLETED`。** 默认/deterministic 执行为 `VALIDATED`，文案「契约校验，未调用模型」，没有审核/应用到正文入口。
7. **未配置视频 Provider 时不得出现 `SUCCEEDED` 或 `placeholder://video/*`。**
8. **研究资料走 durable sidecar：** `v1_capabilities/research.json`。
9. **`ENABLE_CONTINUITY_RULES` 默认 false 不能让作者检查变成空操作。** 新接口 `POST /api/novels/{id}/continuity/scan-chapter` 读章节正文 + 故事资料库，始终跑禁词扫描、`deterministic_review` 和伏笔提醒。

## 为什么不从 `grok-phase1-feature-closure` 变基

`origin/main` 与 `grok-phase1-acceptance` / `grok-phase1-feature-closure` **没有共同 merge-base**。本分支是把同一批诚实性 diff **重新应用到** `origin/main`，再补章节扫描和路线图。Codex 请把本 PR 合进 `main`，不要再尝试 rebase 那两条验收分支。

## 相对 `origin/main` 的功能变更

### 项目概览

- 窗口从 `WritingGoalPanel` 换成 `frontend/src/novel/NovelOverviewPanel.tsx`。
- `GET /api/novels/{id}/overview` 返回真实计数、写作目标、待处理项、近期活动，`placeholder: false`。

### 研究资料

- 窗口从占位换成 `frontend/src/novel/ResearchPanel.tsx`。
- 新建 / 筛选 / 编辑 / 409 版本冲突 / 删除二次确认 / 小说隔离。

### Agent 诚实状态

- deterministic execute → `VALIDATED`，`execution_label="契约校验，未调用模型"`，`model_called=False`。
- `review` / `apply` 拒绝 deterministic / `VALIDATED`。

### 视频 fail-closed

- `DeterministicVideoProvider`：`health_check=False`，`generate` 抛 `VIDEO_PROVIDER_NOT_CONFIGURED`。
- Motion Task 保持 `PENDING`，拒绝 `placeholder://`。

### 章节连续性扫描（本轮新增）

- `POST /api/novels/{id}/continuity/scan-chapter`
- 主路径：当前章节正文 + characters/locations/timeline/foreshadowing + world-rules
- 始终：世界规则禁词、`deterministic_review`（死亡/失踪/年龄）、伏笔逾期提醒
- 仅当 `ENABLE_CONTINUITY_RULES=true` 时才跑规则引擎；关闭时 `engine_status=DISABLED`，但扫描本身仍是 `COMPLETED` 且 `placeholder=false`
- 窗口主按钮「检查当前章节」；JSON 粘贴收到 `<details>` 高级区
- 这不是模型评审，文案保持「契约校验，未调用模型」

### 路线图诚实文案

| 卡片 | 状态 | 诚实说明 |
| --- | --- | --- |
| 研究资料 | 部分接入 | sidecar CRUD，不读外网 |
| 角色成长 | 部分接入 | 手动记录；不自动抽取 |
| 音视频 | 部分接入 | 窗口已挂，fail-closed；Shot 未实现 |
| 插件 | 部分接入 | `execution_supported=false` |
| 工作流 | 部分接入 | `agent_task` 不执行模型 |
| 发布门禁 | 部分接入 | API 有，无独立窗口；DH 仍 BLOCKED |
| 资产派生 | 后端预留 | 派生/视觉记忆未实现 |

## 测试

| 测试 | 变化 |
| --- | --- |
| `tests/test_phase6_agent_jobs.py` | 默认 deterministic → `VALIDATED`；review/apply 走 `complete_model_job()` |
| `tests/test_phase1_feature_closure.py` | overview / research / VALIDATED / motion PENDING / **scan-chapter** |
| `frontend/src/novel/NovelOverviewPanel.test.tsx` | 新增 |
| `frontend/src/novel/ResearchPanel.test.tsx` | 新增 |
| `frontend/src/novel/ContinuityCheckPanel.test.tsx` | 新增：主按钮扫描当前章节 |
| `frontend/src/ui/CapabilityRoadmapPanel.test.tsx` | 新增：剩余卡片诚实文案 |
| `frontend/src/novel/AgentTeamPanel.test.tsx` | 期望 `VALIDATED` |
| `frontend/src/novel/MotionTaskWorkspace.test.tsx` | placeholder 不渲染 |

四个基线缺陷测试不要改、不要 skip、不要 xfail。

## 明确未完成

- DH-01 / DH-04 / DH-07 / DH-08 窗口证据
- DesktopHost DeepSeek 写作→生成→接受→版本→导出（本沙箱做不了窗口）
- 真实模型创作闭环、11 个 prompt stub、插件运行时执行、镜头生成
- 角色成长自动抽取、视觉记忆、外部网络研究检索
