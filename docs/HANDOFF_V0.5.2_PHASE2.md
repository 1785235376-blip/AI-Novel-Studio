# AI-Novel-Studio 开发交接文档

更新时间：2026-08-09  
项目路径：`D:/小说/AI-Novel-Studio`  
当前版本：`V0.5.2 Phase 2 Context Intelligence Layer`

## 给下一会话的直接指令

继续开发现有项目 `D:/小说/AI-Novel-Studio`。不要新建项目，不要重构现有架构，不要修改 Migration 001-005，不要改变 API ID、Chapter Accept、Canon 权限或 Lore Approval 流程。先阅读本文、`docs/v0.5.2_phase1_lore_context_report.md` 和 `docs/v0.5.2_phase2_context_intelligence_report.md`，然后检查工作区实际文件与测试状态。未经用户明确要求，不要进入 V0.5.3。

## 当前稳定基础

- File/PostgreSQL 双后端
- PostgreSQL Runtime：REAL VERIFIED
- Context Pack File/PostgreSQL：MATCH
- Browser Author Flow：REAL VERIFIED
- Evidence、Lore Proposal、Proposal Evidence Relation
- Character Memory、Memory Snapshot
- Memory Agent（只创建 Proposal，不自动批准）
- Lore Context Feature Flag，默认关闭
- Context Intelligence Layer

## V0.5.2 Phase 1 已完成

- `LoreMemoryView`
- 内部 `ContextEnvelope`
- ACTIVE Character Memory 定向检索
- short / medium / long memory
- Evidence summary
- Token budget
- Cloud privacy filtering
- `ENABLE_LORE_CONTEXT=false`
- 只有 Writer Agent 能收到 `lore_memory`
- PENDING/REJECTED Proposal 不进入 Context
- File/PostgreSQL Lore Context 输出一致

关键文件：

- `app/lore/context_view.py`
- `app/services/context_service.py`
- `tests/test_lore_context_contract.py`
- `docs/v0.5.2_phase1_lore_context_report.md`

## V0.5.2 Phase 2 已完成

### Context Intent

`app/lore/context_intelligence.py` 新增：

- `ContextIntentType`
- `ContextIntent`
- `ContextIntentAnalyzer`
- 支持 CHAPTER_WRITE、CHAPTER_REWRITE、CHAPTER_REVIEW、CONTINUATION、WORLD_BUILDING、CHARACTER_DEVELOPMENT
- 使用规则和现有实体名称/slug，不依赖 LLM

### Retrieval Intelligence

- `MemoryRetrievalReason`
- 每条被选 Memory 包含 reason、confidence、related entities、source IDs、priority score
- 确定性排序公式包含实体相关性、时间接近度、剧情相关性、Proposal confidence、recency
- 相同分数按 Memory ID 稳定排序
- 排序后再应用 token budget

### Conflict Detection

- `ContextValidationReport`
- 只报告潜在冲突，不修改 Canon、Memory、Character 或 Timeline
- 当前主要覆盖显式 Character State 冲突
- 更广泛 Continuity 规则留待 V0.5.3

### Context Snapshot

- `ContextSnapshot`
- canonical JSON hash：对象忽略 key 顺序，数组保留顺序
- 保存 Context payload、Context hash、Canon/Memory/Character/Timeline version、prompt version、model
- File/PostgreSQL 都支持幂等快照
- Writer Generation 完成后记录快照
- 未修改 Chapter Accept

关键文件：

- `app/lore/context_intelligence.py`
- `app/lore/context_view.py`
- `app/services/context_service.py`
- `app/services/context_snapshot_service.py`
- `app/jobs.py`
- `tests/test_context_intelligence.py`

## Database

新增：

- `database/migrations/006_context_intelligence.sql`
- `database/rollbacks/006_context_intelligence.down.sql`

Migration 006 新增：

- `context_intents`
- `context_validation_reports`
- `chapter_context_snapshots`
- schema version `0.5.2-context-intelligence`

PostgreSQL 16 隔离数据库已真实执行并确认表存在。Migration 001-005 未修改。

注意：当前独立 `context_intents` 和 `context_validation_reports` 表属于后续查询/审计预留；Phase 2 将完整 Intelligence 结果随 Context Snapshot 保存，尚未增加独立 API。

## 最近验证结果

- AST：`AST_OK 82 files`
- 主要回归：`40 passed, 1 skipped`
- 最终本地 Context Intelligence：`10 passed, 2 skipped`
- Writer Job → Snapshot 受控集成：`1 passed`
- PostgreSQL Migration 006：REAL VERIFIED
- File/PostgreSQL Context Snapshot：REAL VERIFIED
- 原有 Context Backend Compare：MATCH
- `ENABLE_LORE_CONTEXT=false`：PASS，旧 Context Pack 无新增字段

跳过项是未配置真实 PostgreSQL 环境时的条件跳过；在设置 `TEST_POSTGRES_DATABASE_URL` 并准备隔离数据库后，对应真实测试已通过。

## 已知问题

1. `tests/test_jobs_v03.py::test_generate_accept_requires_explicit_commit` 使用固定约一秒轮询窗口。本机单独运行时 Job 仍处于 `GENERATING`，因此该旧异步测试未计为通过。新快照调用已通过独立、确定性的受控 Writer 集成测试。
2. 工作区 `.pytest_cache` 无写权限，pytest 会输出 cache warning，但不影响断言。
3. Conflict Detection 当前是保守规则集，不应宣称已经覆盖完整 Timeline、Relationship、Location、Canon Rule 或 Knowledge Boundary。
4. Entity Resolution 当前使用 name/slug 精确匹配和 active characters，不处理复杂别名或歧义。
5. 不要将 Context Validation Report 当成 Authoritative Fact。

## 严格安全边界

- AI 输出不得直接成为 Authoritative Fact
- Memory Agent 只能创建 Lore Proposal
- 不得自动批准 Proposal
- 不得自动写入 Canon
- 不得自动修改 Character 或 Timeline
- PENDING/REJECTED Proposal 不得进入 Writer Context
- LOCAL_ONLY Evidence/Memory 不得发送 Cloud
- Conflict Detection 只能报告
- 保留 `ENABLE_LORE_CONTEXT=false`

## 尚未实现

- Lore UI
- Vector Search / Embedding / Neo4j
- LLM Intent Classification
- 完整 Continuity Engine
- Alias Resolution
- Context Intent/Validation 独立查询 API
- 自动剧情规划

## 环境与验证命令

项目 Python：`.venv/Scripts/python.exe`

本地定向测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_context_intelligence.py tests/test_lore_context_contract.py -q
```

准备真实 PostgreSQL 隔离库：

```powershell
.\.venv\Scripts\python.exe tests/e2e/database_fixture.py prepare
$env:TEST_POSTGRES_DATABASE_URL = (.\.venv\Scripts\python.exe tests/e2e/database_fixture.py url)
```

真实回归：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_context_backend_compare.py tests/test_context_intelligence.py tests/test_lore_context_contract.py tests/test_lore_contract.py tests/test_lore_service.py tests/test_lore_postgres_contract.py tests/test_memory_contract.py tests/test_memory_agent_contract.py tests/test_repository_contracts.py -q
```

清理隔离数据库：

```powershell
.\.venv\Scripts\python.exe tests/e2e/database_fixture.py cleanup
```

由于 `.pyc` 写权限可能失败，AST 验证应使用 `ast.parse()`，不要使用会写 `__pycache__` 的 `compileall` 作为唯一静态验证。

## 下一阶段建议

等待用户明确授权后进入 `V0.5.3 Continuity Foundation`。开始前先只做 Gap Analysis，重点设计：

- Timeline conflict rules
- Relationship continuity
- Location consistency
- Canon rule dependency
- Character knowledge boundary
- Conflict severity and evidence traceability

不要在分析阶段修改代码或扩展 Lore 权限。

## 最终状态

V0.5.2 Phase 2 Context Intelligence：PASS  
Breaking Changes：NO  
Default Context Compatibility：PASS  
Lore Safety：PASS  
Context Reproducibility：PASS
