# Phase 6 Creative Agent 基础验收

统一执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_phase6_agent_foundation.ps1
```

本阶段建立六类结构化角色：策划、作家、编辑、连贯性、导演、美术。每个角色公开职责、工具白名单、输出契约和作者确认策略；API 只返回目录元数据，不返回凭据或系统提示词。

统一 Agent 上下文包按角色裁剪数据，并携带章节版本、来源清单、目标环境、上下文哈希和隐私过滤结果。美术 Agent 不会收到正文写作上下文；云端 Writer 上下文继续使用现有隐私策略。

覆盖：后端目录契约、敏感信息不泄露、角色级上下文裁剪、云端隐私过滤、Agent 团队界面、DS-v1.0 Token 检查和前端生产构建。

Agent 团队界面现已提供完整 Job 操作入口：作者可选择 Agent、执行模式和可用文本模型，填写任务说明后创建并启动任务；界面轮询并展示 `QUEUED`、`WORKING`、`COMPLETED`、`FAILED`、`CANCELLED` 状态，并提供取消、失败重试、结果审核和受控应用操作。模型选择只引用 Provider/模型标识，不接触或显示任何 API 密钥；真实模型调用仍需显式配置并不会由界面静默触发。

Agent Job 生命周期记录角色、章节版本、上下文哈希、Provider、模型、状态与结构化输出。当前执行器是确定性本地契约验证器，不发起真实模型调用；同一已完成任务不能重复执行。

结构化结果必须从 `COMPLETED` 经过作者显式审核进入 `ACCEPTED` 或 `REJECTED`。审核记录审核人、说明、时间和输出哈希，并明确标记 `applied: false`；本阶段采纳只确认结果，不会自动修改大纲、场景或正文。已决任务不能再次审核，未完成任务不能提前审核。

受控应用器只执行作者审核时选定的白名单动作：`outline.update`、`volume.upsert`、`scene.upsert`。应用前会重新校验输出哈希，应用后保存每项动作的写入前后快照、操作者和时间。未知动作、输出篡改和重复应用均会拒绝；正文覆盖不在白名单内。

Agent Job 支持显式 `deterministic` 与 `model` 执行模式。模型模式必须指定 Provider 和模型，复用统一文本模型节点，并验证返回 JSON 的 schema、Agent ID 与上下文哈希。无效结构或模型错误会进入 `FAILED` 并记录错误码；不会静默切换为确定性结果或其他 Provider，`fallback_used` 保持 `false`。

Phase 6.1 增加 Agent Job 历史查询与界面：`GET /api/agent-jobs` 支持按小说、Agent、状态筛选及分页，结果按更新时间倒序返回，并保留失败原因、审核记录和 `retry_of` 重试链路。Agent 页面顶部提供历史列表、筛选器和分页控制；历史只读展示，不会绕过审核或触发任务执行。

Phase 6.2 增加 Agent 筛选和时间范围筛选（`created_after`、`created_before`），筛选变化会重置分页并纳入查询缓存。历史条目可打开只读任务详情，查看执行模式、目标环境、Provider/模型、上下文哈希、结构化输出、错误信息、审核记录和应用快照；详情不会提供执行、审核或应用旁路。

Phase 6.3 增加 Agent Job CSV 导出：`GET /api/agent-jobs/export.csv` 沿用小说、Agent、状态和时间范围筛选，导出任务元数据、状态、执行模式、Provider/模型、错误码和重试来源。导出明确排除凭据、系统提示词和完整上下文正文，前端导出按钮复用当前筛选条件。

Phase 6.4 审计前置条件：导出审计必须使用可信会话解析出的 `ActorContext`、授权 scope 和现有 `AuditService`，不得使用默认作者或伪造主体。当前 Agent Job legacy 路由尚未接入会话/权限上下文，因此本阶段暂不写入无主体审计事件；待 Agent Job 路由完成统一授权迁移后，再启用导出人、筛选条件摘要、时间和结果数量的审计记录。

可靠性生命周期支持异步启动、状态轮询、取消、超时和失败重试。超时记为 `FAILED/TIMEOUT`，取消记为 `CANCELLED`；迟到的模型结果不能覆盖这些终态。重试创建新的任务 ID 并记录 `retry_of`，仅 `FAILED` 或 `CANCELLED` 可重试，已完成任务不可取消或重试。
