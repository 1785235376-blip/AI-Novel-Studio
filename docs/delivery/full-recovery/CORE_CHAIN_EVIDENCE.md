# AI Novel Studio 核心调用链补全证据

日期：2026-10-07（Asia/Shanghai）。起点：PR #45 `6658172`，共同恢复工作树。本文仅记录本轮核心后端工作，整体验收与真实本地模型运行由主控代理另行汇总。

## 结论与证据边界

DONE：已有 Project → World → Character → Outline → Chapter → Revision → Export owners 保留；本轮补上原来缺失的 seed → typed AI planning → human apply → original World/Story/Outline owners，真实运行时代码路径可以使用已登记模型。通用生成现在接收作品世界、角色、大纲、Canon、时间线、关系以及经批准且有有效证据的世界规则。生成完成持久化人物、明确世界规则词项、明确时间区间冲突的检查结果。Planner/Writer/Editor/Reviewer/Verifier 都有实际模型 Job 路径与确切输出契约；Reviewer/Verifier 获得实际章节全文。

DONE：`continue` 接受新章曾提前返回而不触发 Memory Agent；本轮补上实际新章 ID/version 的独立提取入队。Memory Agent 在任何 evidence/proposal 写入前，校验每个引文确实存在于所选 accepted chapter version，并在模型返回后重新核对输入源。提取结果仍为 PENDING；原人工批准 Memory owner 才能建立正式记忆。模型不自动修改 Canon。

PARTIAL：下述自动化测试的模型输出是明确的合成 adapter fixtures；它们验证实际 File/PostgreSQL storage、原 CAS、数据恢复/引用、模型 prompt/dispatch 调用链及失败隔离，不能作为真实模型内容质量或完整产品验收。此文件没有把 fixtures 的 `execution_mode` 参数当作真实模型运行证据。真实产品验收请引用主控代理产生的独立 live-model receipts。

PARTIAL：确定性一致性检查覆盖人物死亡/失踪/年龄、秘密提前揭露、明确 forbidden_terms 世界规则以及有效 ISO 时间区间 start > end。任意自然语言世界规则、全部叙事时间表达和全部人物心理矛盾不属于确定性规则的保证范围；可执行 Reviewer/Verifier 提供独立模型建议，仍需人工审核。

## 本轮补全与原 owner

| 功能 | 原缺口 | 补全实现 | 可验证行为 |
| --- | --- | --- | --- |
| seed → 世界 | AIPlanning 必须有现有正文，不能从想法生成正式世界材料 | `app/services/ai_planning_service.py` 与原 `creation_workbench_service.py` 增 `WORLD` + premise、typed world summary/rules/locations 候选 | `MODEL` 调用原 normalized runtime；未批准不写原 world/Story；明确 apply 后写原 Novel metadata、Story locations、Lore WORLD_RULE + approval evidence |
| seed → 角色 | 原角色域只能手工输入 | 同一 AIPlanning owner 的 `CHARACTERS` typed 候选 | apply 通过原 `NovelService.save_story_record` + digest/version CAS 新建角色，不替换整表、不覆盖手工角色 |
| seed → 大纲 | AIPlanning 仅保存 PLOT 草稿，不能进入原大纲 | 同一 owner 的 `OUTLINE` 完整 THREE_ACT typed 候选 | apply 前核对 project context snapshot/hash；原 File/PostgreSQL outline owner 增原子 digest CAS；保留原 outline 未被覆盖的扩展字段 |
| AIPlanning 审批 | 缺乏源和目标绑定的正式应用入口 | 原 `/novels/{nid}/planning-runs/{rid}/candidates/{cid}/apply` | run version CAS、project context hash（包含影响 egress 的原 metadata privacy）、dispatch locality/authority/source checks、真实 `execution_mode == real` 要求、显式人工应用、逐项 durable receipt、部分失败保留且明确重试 |
| 世界摘要 | 混用 long_term_summary | 原 Novel metadata 新 `world_summary`、独立 privacy 字段 | 旧作品保留原摘要；生成的新 world summary 默认 LOCAL_ONLY；原 NovelUpdate 可编辑 |
| Project/Chapter Context | 原 context sources 没有 outline/Canon/timeline/relationships；active_characters 为空时无角色 | `app/context.py`、`repositories/file/novel.py`、`repositories/postgres/novel.py` | 原上下文包含域材料；没有显式活跃名单时使用已知角色；空 canonical relationships 不丢弃旧 story_state relationships |
| Context Privacy | 新域材料可能绕过原隐私过滤 | 原 `cloud_safe_context` + `ContextService._sources` | 未许可记录不进入 cloud；世界规则仅 APPROVED 且 evidence ACTIVE、同作品，privacy 继承所有原证据 |
| Context Policy/V2 | Policy 与 V2 实际输入没有 Canon/世界规则/时间线、角色只有 ID | 原 `ContextService` policy/pack adapter | 已批准世界规则/Canon 为 AUTHORITATIVE、时间为 CONSTRAINING；V2 读取实际角色记录和时间线，保留原 flags/budget/隐私契约 |
| Editor 连续记忆 | 原非 writer prompt 直接丢弃所有 supporting memory | 原 `AgentRunner` 增 source-bound supporting projection | Editor/reviewer 基于 novel_id/chapter 的已解析上下文使用 `continuity_memory`；原直接调用 legacy raw `lore_memory/context_policy` 隔离测试不变 |
| Reviewer/Verifier | Reviewer 只是 continuity 目录语义，Verifier 不可执行；Agent context 没有章节文本 | 原 catalog 增 `additional_agents`、`resolve_agent`、原 AgentContext/AgentJob service，`prompts/verifier/system.md` | 保留 v1 原六角色 catalog；新增两个可执行角色；`chapter_source` 正文/version/hash 绑定并受隐私控制 |
| Agent 真实输出契约 | prompt 仅列 key，模型猜不到要求的 schema value | 原 `AgentJobService._execute_model` | 输出 JSON schema + 明确 `schema/agent_id/context_hash` exact values 传给模型；原 validator 严格保留 |
| 生成后一致性 | 原生成后只检查人物/秘密；world/time 只有独立 API | 原 `app/review.py`，已有 `JobManager._run` 调用不改架构 | 全部普通 generation `issues` 经原 generation persistence 保存 world/time findings；扫描 API 复用同一个 world evaluator |
| 时间数据真实存储 | 原 timeline payload 的 start/end 可能被丢弃 | 原 TimelineEventIn、structured CAS field set、File/Postgres story owners | start_time/end_time 可由原时间 API 写入，取回后进入 context 和生成检查 |
| accepted → Memory | 新章接受 early return，Memory 引文可编造 | 原 `app/jobs.py`、`app/lore/memory_agent.py` | 实际新章节 ID/version 入队；提取全部引文先验证；再次解析 accepted source 和作品 Context 确保推理期间未漂移 |

## 原安全与兼容约束

- 原六角色 catalog v1、直接非 writer raw memory 隔离测试、所有既有测试/skip 均保留。
- 原用户 opt-out/reduced scope、character viewpoint、branch-only manuscript fences 不被绕过。新的 startup → original project domain 应用目前限定 local project scope；collaboration branch 原来没有对应项目域应用 owner，明确拒绝越界。
- WORLD/CHARACTERS/OUTLINE 必須 premise 与 MODEL 模式；原 STYLE/PLOT 等仍必须现有 source chapter。结构化假结果、来源漂移、云端未许可源、迟到结果、已取消任务和重复 apply 均拒绝。
- `mock_standin` 候选可以被检视为测试结果，不能通过新 apply 进入正式 Story/World/Outline owners。
- 人工 apply 的多 owner 操作没有宣称为一个跨 owner 分布式事务。每项原 owner receipt 保留；后续失败记录 `application.status=FAILED`，已完成项不擦除，明确重试才能继续；作者漂移会阻断。
- Memory 仅使用原经验证 loopback `LocalTextAdapter` 或明确 dev mock fixture；不改原无云端 fallback/不自动批准边界。未登记真实本地 route 时原独立 extraction job 记录 NOT_CONFIGURED。

## 自动化证据

| 运行 | 结果 | 模型来源 | 证据 |
| --- | --- | --- | --- |
| 本轮新核心 File 契约（含最后隐私撤销回归） | 16 passed，4.79s | 合成 adapter/spy；原 File repository 与 services 实际执行 | `CORE_CHAIN_FILE_FINAL.log`、`CORE_CHAIN_FILE_FINAL.xml` |
| 新核心真实 PostgreSQL 16.4 契约 | 15 passed，1 expected File-only skip，5.06s | 合成 adapter/spy；本机实际 PostgreSQL，全部迁移，原 PG repository 实际执行 | `CORE_CHAIN_POSTGRES.log`、`CORE_CHAIN_POSTGRES.xml` |
| 既有与新核心 focused 联合回归（最后一项隐私回归之前） | 160 passed，20 expected skips，19.99s | 大部分合成模型/纯规则；不代表真实外部模型验收 | `CORE_CHAIN_FOCUSED.log`、`CORE_CHAIN_FOCUSED.xml` |
| 首次 PG fixture RED | 4 passed、1 skip、10 setup errors | 首个固定项目 ID 被后续测试重用，与 PG 持久项目发生 FileExistsError | `CORE_CHAIN_POSTGRES_INITIAL_RED.log/.xml`；改为每测试独立 UUID 后重跑，原失败保留 |
| 重复 PG fixture RED | 13 passed、1 skip、2 failures | 两个固定合成 generation ID 在第二次运行绑定到新作品；原 PG generation identity guard 正确拒绝 | `CORE_CHAIN_POSTGRES_REPEAT_RED.log/.xml`；合成 job ID 改为绑定每测试唯一作品后重跑，原 guard 与断言保留 |

`tests/test_full_recovery_core_chain.py` 覆盖：seed 全链进入原 owner、已有手工角色保留、world evidence 人工批准、actual Context 使用世界/大纲/角色/规则、旧 source requirements、dispatch 前/approval 后漂移、schema 不合法、mock apply 拒绝、部分应用故障与明确重试、原 outline/run CAS、cloud 隐私、项目 privacy 在 prompt 捕获与实际 dispatch 之间撤销、五 Agent actual execution path/prompt contract、Editor supporting memory、人物/世界/时间生成检查持久化、legacy relationship fallback、新章 Memory 实际版本入队与编造 Memory 引文全组拒绝。

此文件没有声称真实模型质量、可执行桌面安装包、全部 feature flags、collaboration branch 的新 startup apply 或任意自然语言一致性均已完成。相应运行状态以最终 `AI_NOVEL_STUDIO_PRODUCT_ACCEPTANCE.md` 与 `AI_NOVEL_STUDIO_REMAINING_GAPS.md` 的实际证据为准。

## 完整回归后续补全与运行边界

Windows 完整原序 File 过渡运行严格收集并分配 9,140 nodes，未过滤、未跳原 coverage/PG guards，但在原 1,200s 外限终止（1200.75s，exit 1，timed_out=true）。仅观测 6,306 unique nodes；4,405 call passed、34 call failed、2 setup failed、2 teardown failed，36 个失败节点；没有完成剩余节点，没有最终 JUnit，coverage complete=false。这段运行期间后端继续修复，不能当最终候选通过。原 `candidate-backend-receipts/file` 全部 log、coverage events、身份与过渡 source manifest 保留。

该运行完成三个实际 Windows 问题的修复：跨进程 File 字节锁初始化不能读取另一进程已锁定字节；worker EOF 后须有限回收实际退出码；native owned-PID timeout cleanup 必须按 Windows 语义查找 copied environment 的 SystemRoot。原 assertion/timeout/安全边界保持。原 focused 验证分别为 29 passed（lifecycle/index，13.30s）、206 passed（当时完整 contracts/worker，9.85s，generator 随后撤回）、11 passed（全部 native verifier，2.89s），对应 `verification/file-lifecycle-utf8-after.*`、`interop-worker-windows-after.*`、`file-native-verifier-after.*`。详细 RED/GREEN 与运行配置、WinError1314、`/proc`、ZipInfo raw-name 边界见 `WINDOWS_RUNTIME_FIXES.md`。

更正：上述 Interop generator 变更随后被原 hosted Desktop V1 frozen checker 拒绝，已完全撤回。该工具及 parity-manifest 是冻结 37-file 合约的成员，不能通过更新 generator hash 规避冻结。最终两文件精确恢复 PR45 原 blob（generator `b5ef94a...`、manifest `77c1f82...`），原硬编码 hash/assert 均保留。恢复后原 checker 37 V1 + 26 shared 文件 PASS，Linux 原 contracts 184 passed（14.77s）。此前 Windows 206 passed 保留为被撤回实现的 focused 证据，不代表最终 generator 支持 Windows。

本轮另建立实际 WSL Ubuntu 24.04/Python 3.12.3、原生 ext4 临时隔离目录和全新 loopback PostgreSQL 16.15，两数据库与独立 socket；ffmpeg/ffprobe 6.1.1、pg_dump/pg_restore/postgres 实际运行成功。所有 native 工具仅下载和 portable 解包，未安装系统包/未触碰既有数据库。Linux 原 strict coverage infrastructure 自测 153 passed（30.68s，`verification/coverage-harness-linux.log/.xml`），属于基础设施证据，不扩大产品测试计数。最终 File/PG 未过滤完整执行及字节等同 copy-proof 应另引用最后候选 native receipts；本段不预先宣称完整产品套件通过。

首次 native freeze `3efa039...` 的实际 2,467-file 副本及 1,523 manifest inputs 全 SHA 相等，原 153 infrastructure selftests 以该源再次 PASS（2.69s），真实双进程 TCP gate 2 passed（29.55s）。完整 File 在 350.516s 因原测试的全局 import monkeypatch 与 Python 3.12 coverage hook 交互 INTERNALERROR，未完成，raw 与原 copy-proof 在 `transition-2-native` 保留。该源又撤回上述不合法 generator 变更并待 package provenance 源修复，因此明确标为 TRANSITION_2_INCOMPLETE，不归为最终完整 suite PASS；最终 native 回归须绑定下一真实 source freeze。

原 `test_host_absent_does_not_import_initialize_or_collect` fixture 已仅将原依赖移除、两项禁用 patch、SUT call 与两项原断言放入 `monkeypatch.context()`，在 call-report 前恢复 import；禁止 Host 初始化/导入的原 SUT guard 不变。完整原 routing file 43 passed（2.67s）；两个原序节点用原三 strict plugins 的最小 diagnostic manifest 2 passed（2.13s），明确属于 fixture 生命周期诊断，不是完整产品 receipt。全文件原 49 assertion AST 与三个 strict guards 字节完全相同。单节点冷启动的 Pydantic lazy serializer import RED 同样保留，没有以 warm-order focused 证据宣称任意单节点冷启动 PASS。下一完整未过滤产品 suite 应以原顺序验证。
