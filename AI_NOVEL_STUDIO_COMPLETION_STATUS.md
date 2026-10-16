# AI Novel Studio Completion Status

基线：PR45 `665817243cad59eef0d4140f17c2ea644f46971e` 的完整后继工作树，分支 `work/full-recovery-product-candidate`。历史版本选择详见 FULL_VERSION_MAP；不将 main 当最新产品。

| 领域 | 代码证据 | 测试与真实运行证据 | 状态 |
| --- | --- | --- | --- |
| Project → World → Character → Outline | 原 AIPlanning/CreationWorkbench + typed startup候选、premise、显式apply、World/Story/outline CAS | 核心16契约；真实run85a84385 stages01–04 | DONE |
| Chapter → Revision → Export | 原 generation/CAS/history/export owners；provider参数/取消/usage；上下文接入 | 原/新增provider transport、真实stages05/06/08/09/10、409与字节恢复/download | DONE |
| Project/Chapter/Character/Continuity Context | app/context.py、ContextService、File/PG novel sources，支持outline/Canon/timeline/relationships/批准世界规则；旧关系fallback与cloud privacy | core tests + 真实 Memory proposal→批准→Chapter Context回执 | DONE |
| Memory extraction | app/jobs.py接受新章触发原MemoryRunner；accepted version/hash、全组引文预校验、实际source-bound grammar、完整host schema验证 | 合成负例保留；真实32f3acd6…3提案与人工审核ACTIVE | DONE |
| Planner/Writer/Editor/Reviewer/Verifier | 原AgentRunner/AgentContext/AgentJob + additional_agents保持原六role契约；实际chapter_source、strict output/contexthash | core execution contracts；5个真实job均model_called/real | DONE，含实际本机UI调用 |
| 人物/时间/世界一致性 | app/review.py原生成后review接入人物state、明确ISO区间、批准world forbidden terms；File/PG timeline start/end保存 | core持久化检测与真实scan/context | DONE明确规则；自然语言推理范围PARTIAL |
| Version / CAS / History | 原保存/历史/restore/冲突owner；Windows锁初始化实装修复 | 原CAS跨进程29focused通过；真实PUT409、比较、restore新版本/原文hash | DONE |
| Provider / runtime | 原discovery/registry/model node；Local adapter真实计量、JSONgrammar/完整hostvalidator、truncated输出拒绝；旧OpenAI transport参数与取消 | provider focused，新local5tests，实际模型运行 | DONE本地；其他未配provider不能当真实验收 |
| 前端作品流程 | 原AppShell/FeatureLauncher/AIPlanningPanel/StoryDatabasePanel/AgentTeamPanel；无章节资料读写、世界摘要、模型选择、review/apply、原history/export | 前端1498pass/8原skip、visual15pass、lint42、production build；actualbrowser显式授权→真实Qwen Reviewer完成、解绑、3695bytes导出 | DONE，本机完整入口与实际UI验收 |
| 历史资产/PR恢复 | ALL_VERSION_MAP、完整Git后继、新branch、8旧独有commit patch、33exact-head artifact CRC/SHA验证 | PR36–45全部祖先保留、322历史commits/1431artifact索引 | DONE元数据/相关exact-headbytes；剩余历史artifactbytes未全部下载 |
| 双存储完整回归/最新候选包 | 原strict suite/reconcile/PG gate保持，sourcefreeze manifest；officialSDK/pinnedfont/approvedbase依赖补齐 | 本地过渡完整suite保留RED、Linux final与最新Windows package在进行 | PENDING |

每项代码路径和边界：[CORE_CHAIN_EVIDENCE](docs/delivery/full-recovery/CORE_CHAIN_EVIDENCE.md)、[PRODUCT_SURFACE_EVIDENCE](docs/delivery/full-recovery/PRODUCT_SURFACE_EVIDENCE.md)、[独立源/测试保护审核](docs/delivery/full-recovery/INDEPENDENT_SOURCE_REVIEW.md)。没有删除原9,116节点、旧skip dictionaries或失败证据。两路径fixture仅POSIX序列化；ZIP fixture仅真实恶意raw entry序列化；routing fixture仅在原SUT/原assert范围内限制import并在pytest报告前恢复，49原assert保留；visual原expect保留，两旧gold迁移有原PR45同图证据。三个strict guards不变。

可信local UI已完成；最终严格suite和candidatepackage仍在执行，结果确认后更新。

最终冻结第二版：9151节点（原9116+35），1567输入，source ce2fbe8ad342fe1969e8c26d729023f7b66352bed95113f98ffa4d847b3f764b。原V1生成器/清单已恢复PR45固定字节；原硬编码V1校验不变。第一候选3efa039的Interop RED和本机过渡INTERNALERROR全部保留，不能当最终全绿。实际AI/API/browser证明的application fingerprint为4b3b6a662294e324e31e8d068b17db886269eb865442bf5b10bdd606e4bd035e；此轮仅协议工具恢复、fixture清理和恢复材料清单修正，app实现未再改变。
