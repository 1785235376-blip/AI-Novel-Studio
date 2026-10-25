# File / local / semantic_import 原 owner 观察端口审计

审计基线：`1587b57791cbdc3e46f0c09fedea83072e6a8d28`。范围只包括为 TaskCenter 原 owner 一致性观察准备接口；本文件不实施 owner 修改、不启用游标、不声明目标完成。

**状态：静态源码审计完成；实现、编译、File/HTTP 执行、并发、性能与回归全部 NOT_RUN。** 本轮 M0 命令执行器初始化失败；没有使用 Node 宿主执行、本地用户数据、Actions 或替代云任务。下面的端口与数据字段均为提案。

## 1. 检查范围与证据边界

通过 GitHub 连接逐文件读取固定 ref，检查了：

- `app/experimental/` 下 157 个 Python 文件。
- `app/` 根目录 116 个 Python 文件、`app/creative/` 下 108 个 Python 文件。
- `app/services/` 下 84 个 Python 文件；membership 模块首次读取失败后单独重读成功。
- 固定 tests Git tree 下 249 个 Python 文件的相关 owner 引用，以及下列关键测试的断言。
- 另读 `app/repositories/file/novel.py`、`scope.py` 和 `app/repositories/branch_manuscript.py`。

这是上述固定目录和字面调用的静态覆盖，**不是全仓全部外部 writer、所有运行时反射/别名调用、管理员工具或人工文件操作的穷举证明**。未扫描的其他 app 子包、仓外程序、操作系统恢复及手工复制可能绕过 owner。未执行任何测试。

关键源码 blob：

| 文件 | 固定 ref blob SHA |
| --- | --- |
| `app/experimental/store.py` | `892cba06eb3428d79d255a60878c2bffc8d9b926` |
| `app/experimental/common.py` | `aeebdd7328e53ac9a1dccf807663424753c5f9e5` |
| `app/experimental/imports.py` | `8dfbb8069f1e9da4395b944fa22b089124714cf3` |
| `app/creative/project_store.py` | `5c03cc6691e295bfe909c9682aa89401ed04f7f1` |
| `app/repositories/file/mutation_coordinator.py` | `15e48d756a1fd4957649efc1db66baa1288593b5` |
| `app/file_project_lifecycle.py` | `0563c672229a9ecd2a0499e95407e7fbfc4dbc52` |
| `app/project_retirement.py` | `ea4c7230545920d1a55413e9127e951b535606af` |
| `app/repository.py` | `51a5b828690aa9705383d3fabd5a0113d3af92b8` |
| `app/storage.py` | `03e6d5a37448de3095a5777f72fc4c3c8bd18b43` |
| `app/backup_restore.py` | `0aae897f57bec86fb05252f56af34693e4b06fe5` |
| `app/services/branch_manuscript_service.py` | `490b31f049e69ec90f7f607ffb2cf1fbf37bb47d` |
| `app/repositories/branch_manuscript.py` | `7a445d9bd5bff669617ff74090fa988758d9a66b` |

本文行号均指上述固定 ref。审阅入口：
[store.py](https://github.com/1785235376-blip/AI-Novel-Studio/blob/1587b57791cbdc3e46f0c09fedea83072e6a8d28/app/experimental/store.py)、
[imports.py](https://github.com/1785235376-blip/AI-Novel-Studio/blob/1587b57791cbdc3e46f0c09fedea83072e6a8d28/app/experimental/imports.py)、
[project_retirement.py](https://github.com/1785235376-blip/AI-Novel-Studio/blob/1587b57791cbdc3e46f0c09fedea83072e6a8d28/app/project_retirement.py)。

## 2. 现有文档、读取与唯一内部提交点

| 源码位置 | 已知行为 | 对一致性的意义 |
| --- | --- | --- |
| `store.py:40-50` | key 是 canonical `[nid, scope]` 的 SHA256；文件在 `data/experimental_v1/<key>.json` | 相同 public nid 与相同 local scope 重建会重用同一文档路径；key 不是实例身份。 |
| `store.py:53-64` | schema 1 文档含 novel_id/scope/collections；验证不要求 epoch/revision，且允许其他 top-level 字段 | 目前不存在可靠 File 文档 epoch 或文档 revision；未来附加字段仍须由原 owner 维护。 |
| `store.py:66-71` | 全量 read_text/JSON parse；缺文件返回逻辑 empty 文档 | 缺文件与物理存在的空旧文档不能仅凭返回 dict 区分。 |
| `store.py:79-86` | 实例本地 active 命中时返回未提交文档 deepcopy；否则持原 scope 锁读文件 | 通用 read 不是无条件“已提交事实”端口。 |
| `store.py:91-111` | 同实例同 scope 禁 nested；锁内读、yield、validate；canonical 变化才 atomic_write | 无变化/异常不提交；无磁盘重读 CAS；metadata 必须和业务集合一起原子提交。 |
| `common.py:74-86` | DomainService.list/get 先 novels.get，再原 store.read；list 校验全部行的 project/scope | semantic 查询应复用该 owner 校验，不得另建影子任务表或跳过原校验。 |

ExperimentalStore 类本身只有 read 与 transaction，没有 replace/delete/restore 公共入口。已扫描 experimental 目录中，对该 scope JSON 的唯一直接写点是 `store.py:109` 的 atomic_write。portable_projects 的 os.replace/unlink 用于自己的 portable artifact 文件，不是此 scope JSON；这不证明未扫描仓外代码不能改文件。

`app/storage.py:5-19` 在同目录创建临时文件、写入、flush/fsync 文件，再 os.replace，处理 Windows PermissionError 重试并清理临时文件。业务集合和观察 metadata 放在同一个 JSON 时可以复用同一替换边界；这不是跨文件、跨 owner 或断电恢复的原子性证明，也没有父目录 fsync 保证。

## 3. semantic_import 的真实身份和版本边界

- `imports.py:176-223` 的 create_job 仅接受 local，调用原 source 校验，186 行为 job 生成 UUIDv4；chunk ID 用 job UUID 等输入生成 UUIDv5。job/chunks 同一原 transaction 写入。
- `imports.py:148-150` 的 _record 初始 version=1；`153-167` 的 _touch 将行 version 加一，保留最多 50 个 history 项。
- `225-229` 的 jobs/job 只走原 DomainService.list/get，没有查询时修复、迁移或写入。
- 正常写入包括 _assert_fresh 标记 STALE（253）、process claim/completion/failure（363/398/420）、transition（438）、review_batch（493）、commit prepare/interrupted/completed（539/596/604）。这些均通过原 store.transaction。
- process 的 chunk claim/status 字段还会直接修改；不能只监听 job._touch 推断文档中的所有变化。
- 没发现 semantic_import 对外提供删除 job、按旧版本整体恢复 job 或指定 job UUID 的创建接口。这个事实仅限本次读到的 service；通用 store.transaction 允许其他原消费者改集合，文件恢复也能重放 UUID/version。
- 因此“UUIDv4 + 行 version”支持正常原 API 的身份/版本语义，**不能单独证明通用文件替换、旧备份恢复、任意重建同 ID 或任意 A→B→A 的不可重放性**。

## 4. 项目删除后同 ID 重建：第一页也必须拒绝旧文档

固定源码确认：

1. `repository.py:33-40` 在 novels/nid 创建新项目文件与章节 identity ledger；不建立 creative_project_v2 marker，也不清除 experimental_v1。
2. `repository.py:52-54` 委托 `project_retirement.retire_file_project`。
3. `project_retirement.py:68-93` 在授权→project→collaboration-scope 锁内，把 **novels/nid** 重命名为删除备份，退役授权/scope，再回收该目录。它不删 experimental_v1 下的 scope 文档。
4. `CreativeProjectStore._owner` 的原 File marker 在 novels/nid/creative_project_v2.json，随项目目录退役；现有 existing_owner_only 不创建缺失 marker。

反例：旧项目 P1 写入 semantic jobs，删项目但留下 scope JSON；创建同 nid 的 P2。仅在 token 中绑定 P2 当前 incarnation，随后从旧 scope JSON 读 jobs，会把旧任务错误地绑定到新实例。**光失效 P1 的旧 token 不够，P2 新第一页也必须检查文档的原 project 绑定。**

观察 metadata 至少要由原 owner 保存可信的原 project incarnation，并在 capture 与 revalidate 对照原生命周期端口。缺 marker、缺文档绑定、绑定不一致一律不能启用新游标；查询不能补 marker、初始化 epoch 或自动接纳旧任务。

旧文档若完全没有实例归属证据，显式迁移也不能从当前同名目录反推出这些旧行属于当前实例。应保持 unsupported 或另行开展明确的原数据归属审查；不能把给旧文件补 UUID 的操作描述成恢复了历史真实性。

## 5. 锁顺序、跨实例 nested transaction 和提交 CAS

`workspace_mutation` 的原线程锁按 resolved root + key 复用；_thread_state.depths 使同线程同 key 可重入。ExperimentalStore 的 _local.active 则只属于某一个实例。

可稳定构造但本轮未执行的反例：

1. Store A 与 B 指向同 root、同 scope。
2. A.transaction 读取磁盘 D/rev7 后 yield。
3. 同线程进入 B.transaction：全局 scope 锁可重入，但 B 看不到 A 的实例 active，所以读取磁盘 D/rev7。
4. B 写 D_B/rev8 并提交。
5. A 用自己的旧 D 写 D_A/rev8 并提交，覆盖 B；两次独立提交获得相同简单 `+1` revision。

当前 `store.py:108-109` 只比较 A 的 before/after 内存 canonical，没有磁盘原文档 CAS，因此存在上述 lost-update 窗口。仅加一个 counter 字段不能解决它。

提案：原 File transaction 提交前在原 scope 锁内重新读取**实际磁盘已提交状态**，CAS 最初捕获的“物理存在性 + 原文档内容/metadata”；不得用会返回 active 缓冲区的通用 read 来执行该 CAS。若内层已提交、发生迁移、删除/替换或 metadata 改变，外层必须安全拒绝，不自动重放业务 callback。

保护要求：

- 不能只比较业务 projection 或只比较 revision；保留旧文档的已提交指纹与 metadata。
- 即使外层开始时是旧无 metadata 文档，内层显式迁移后也不能被外层覆盖掉；提交端仍须检测当前受保护状态。
- 观察 metadata 是原 store 的保留字段。调用者 clear/update、篡改 revision、携入旧 metadata、删除 metadata 均不能决定提交身份。
- metadata 和业务集合只能通过原 atomic_write 同次提交；不建平行文件 owner。
- 同实例 nested 已拒绝；跨实例 nested 写入至少要在原提交端 CAS 拒绝 stale outer。若选择直接拒绝跨实例 nested，应由原协调器暴露统一事务上下文，不能依赖查询层私读各实例 _local。
- 原 CreativeProjectStore.transaction（188-205）在底层 scope transaction 内持 project lease 到提交，且会 document.clear/update(view)。新增 metadata 必须在这个真实包装路径仍受保护，不能靠每个消费者手工复制保留。

锁图的已知约束：

- ExperimentalStore scope 锁。
- CreativeProjectStore.transaction：scope → project；source_lease：持 scope，短暂查项目，不在 yield 持 project。
- workspace._asset_scope 明确禁止在 asset/project lease 内调用 ExperimentalStore（workspace.py:139-144）。
- project retirement：authorization → project → collaboration-scope。

不得持 project 锁再读全部 TaskCenter reader；不得把全局 authorization 重验塞进反向持锁区。候选 capture 应复用原 scope→短 project 身份检查，外层原授权仍在原边界重验。具体锁组合必须有执行器后并发实测。

## 6. 已提交观察、no-op 与迁移

原 read 在实例 active 命中时返回未提交 deepcopy（store.py:81-83）。新 observation 不能把其中未提交 epoch/行当成游标事实，更不能把 stamp 从磁盘取、行从 active copy 取再拼接。

候选端口只能二选一：

- 明确拒绝当前执行上下文已处于该 scope 的业务 transaction；检测须涵盖另一同 root store 实例的嵌套情形；或
- 原 owner 提供一次同源、只读的已提交捕获：行与 stamp 全从原锁内磁盘已提交文档读取，严格不借用 active 缓冲区。不得改变原普通 read 的既有内部调用语义。

迁移与只读要求：

- missing physical file、物理存在的 legacy empty 文档、含业务行的旧文档、损坏文档必须分开判断；公开错误仍固定安全。
- 原 read、查询、source_lease、无变化 transaction、失败 transaction 不初始化 epoch，不增加 revision，不产生业务文件。
- 旧文档启用必须是独立显式原 owner 迁移：dry-run/预期文档指纹/可信 project 绑定、原 scope 锁内 CAS、保留所有业务集合与旧行为。缺证据时迁移不应推断归属。
- CreativeProjectStore.source_lease 使用 raw transaction 并禁止 mutation；因此“进入 transaction 就 bump”会破坏原只读端口，必须禁止。
- 新文档可否在原业务创建提交时初始化，需要原 writer 提供创建前捕获的可靠项目实例并在提交时复验；普通查询不能承担该职责。
- 原业务 writer 若不参与观察 metadata 合同，该来源保持 unsupported，不能把缺少 marker/epoch 的模式标成可靠。

## 7. 其他 collection 变化和覆盖侧信道

同一 scope JSON 含大量不属于所选 semantic_import 的 collection。若 token 直接绑定整个文档 revision，隐藏或未选择的其他 collection 变化会导致重读错误，暴露不可见活动；这是范围扩大和侧信道风险。

建议分离：

- 内部 document revision/原文档指纹只用于原提交 CAS，不直接成为 cursor 的观察绑定。
- 对选中 collection 的生命周期/修改证明由原 store 提交端维护；query 只绑定已授权安全有限观察所需的部分。
- **collection-wide revision 也不是自动充分**：中央只检查前 200 行（ux.py），源可能全量返回更多。选中 collection 的未观察尾部、被拒绝行或私有字段的独立变化，仍可能通过统一 revision 引发 restart。必须明确这是否泄露本合同不允许的信息。
- 更细的原 row incarnation/revision 由原提交端维护并只为安全可见行提供证明，可以作为候选；删除再创建同 ID 必须获得新 incarnation。是否保留 tombstone、如何处理整集合替换、资源上限与旧文档迁移需要独立设计和测试。不能由 query 依据字符串/mtime/索引位置伪造。
- projected 集合、顺序、安全字段/revision 与有关权限变化仍应失效；未选择的 authority 不应因别的 collection 活动无故失效。

本轮不选择尚未验证的最终 epoch schema，也不宣称这些风险已经解决。

## 8. 恢复和外部文件写入：反重放保证的边界

`backup_restore.py:124-170` 要求离线确认并复制文件/校验；`250-280` 只恢复到原先不存在的新 destination，267 行 copyfile 原样复制，不调用 ExperimentalStore，也不重建观察 epoch。data_directory 的 inventory 可包含 experimental_v1 与项目 marker。

因此将旧备份连同 project marker、scope document 和 metadata 一起恢复，会重放它们的旧字节。文件内 UUID/counter/hash 无法证明“这份相同内容以前出现过又被回滚”。inode/mtime、字符串相等或随机给现读状态命名，不能充当持久反重放根。

进程内 cursor 引擎重启/新 worker 安全失效有助于拒绝原进程 token，但不能虚称这是原 owner 对外部恢复的不可重放证明。外部直接复制/管理员还原不是本文已覆盖的参与 writer；若没有独立可信恢复代次合同，必须如实保持保证范围或拒绝该模式，不新增平行凭据库。

## 9. 最小原 owner 端口提案（未实现）

| 原 owner 端口职责 | 最小要求 | 禁止替代方案 |
| --- | --- | --- |
| 显式 enable/migrate | 校验原文档指纹、可靠 project 绑定；锁内 CAS；维护保留 metadata | GET 自修复、缺 marker 自动创建、用当前 slug 猜旧行归属 |
| transaction commit 维护 | 在原同文件原子边界维护生命周期/修订；提交前真实磁盘 CAS；保护保留字段；no-op 不变 | 每 reader 自己递增、只在任务._touch挂钩、双文件提交 |
| capture_committed_collection | 已授权原 scope，真实 File/local；同源已提交行与生命周期证明；project binding 短重验 | 通用 read(active) + 独立磁盘 stamp 拼接、查询平行存储 owner |
| SemanticImportService.observe_jobs | 复用 jobs 的项目存在/行 scope 验证与原顺序；携原 owner proof，不扩大窗口 | 重建任务类别、绕过原 reader authority |
| revalidate_observation | 原授权前后与 scope fence，重读原事实；只比较授权有限观察有关证明；固定安全失败 | 缓存成为任务/权限事实来源、scope-wide隐藏活动列表 |

本轮用户已明确授权必要的原 owner 与装配 additive 生命周期端口；不是再次等待 owner 修改权限。以上仍为未实施的最小候选，必须先解除 M0 云执行器阻断并运行基线后再实施和验收。当前新 cursor 仍不得启用。

## 10. 共享消费者与回归范围

字面扫描命中 54 个 experimental 事务消费者、254 处 `store.transaction`，另 14 个 creative 文件。这是源码文本调用覆盖，不是 AST/动态调用穷举。

experimental：

`audience_review.py`, `audio_manifest.py`, `audiobook.py`, `change_impact.py`, `comic_layouts.py`, `comic_ora_staging.py`, `common.py`, `declarative_agents.py`, `declarative_model.py`, `embeddings.py`, `first_use.py`, `imports.py`, `interactive_story.py`, `local_ai_inspection.py`, `media.py`, `model_benchmark.py`, `model_benchmark_video.py`, `model_broker.py`, `multilingual_editions.py`, `multilingual_translation.py`, `narrative_judge.py`, `narrative_judge_model.py`, `offline_sync.py`, `offline_sync_production.py`, `planning.py`, `planning_model.py`, `portable_projects.py`, `production_lineage.py`, `project_forks.py`, `reader_preflight.py`, `research_library.py`, `research_library_api.py`, `review_adapter_jobs.py`, `review_adapter_projection.py`, `revision_intelligence.py`, `revision_intelligence_model.py`, `safe_batch_studio_image.py`, `safe_batches.py`, `story_graph.py`, `story_simulator.py`, `story_simulator_model.py`, `structured_forks.py`, `style_analysis.py`, `style_analysis_model.py`, `subtitle_processing.py`, `template_library.py`, `terminology_portability.py`, `ux.py`, `workspace_interaction.py`, `world.py`, `writer_room.py`, `writer_room_realtime.py`, `writing_focus.py`, `writing_sessions.py`。

creative：

`adaptation.py`, `adaptation_generation.py`, `ai_execution.py`, `director_binding.py`, `director_image_generation.py`, `generation.py`, `graph.py`, `graph_asset_inputs.py`, `graph_execution.py`, `project_store.py`, `proposals.py`, `service.py`, `storyboard.py`, `workspace.py`。

其他明确入口：

- `dependencies.py:142-146` 为 BranchManuscriptService 构建第二个同 root ExperimentalStore 实例，证明跨实例兼容并非虚构场景。
- `services/branch_manuscript_service.py` 的 fork/merge/snapshot 事务；`repositories/branch_manuscript.py:185,262` 的原分支写入。
- `chapter_identity.py:95-102` 读取 experimental_v1 作为既有引用证据；top-level metadata不能意外变成伪章节引用。
- `experimental/api.py:48+` 的 shared store 注入规划、世界、semantic import、团队、媒体、embedding、有声书以及后续能力；不能只回归 TaskCenter。
- CreativeProjectStore 包装的 creative、graph、director、production、timeline、prompt 等路径都需要 no-op/失败/恢复/跨实例合同回归；其中 source_lease 是特别敏感的只读路径。

已在固定 ref 确认存在、应纳入后续回归的精确文件（全部本轮 NOT_RUN）：

| 回归面 | 固定 ref 测试文件 |
| --- | --- |
| 原 TaskCenter、两前缀、授权与只读 | `tests/test_taskcenter_query_backend.py`, `tests/test_taskcenter_consistent_query.py` |
| 引擎前置合同，不等于真实 owner 支持 | `tests/test_taskcenter_cursor_independent.py` |
| 源扫描/响应分页测量 | `tests/test_taskcenter_query_measurements.py` |
| 真实 File fixture/实例与只读查询 | `tests/test_studio_asset_query.py`, `tests/test_studio_asset_query_authority.py`, `tests/test_studio_asset_query_cursor.py` |
| 多实例 creative 恢复/图读取路径 | `tests/test_cloud_canvas_create_recovery.py`, `tests/test_cloud_formal_canvas_node.py`, `tests/test_cloud_saved_canvas_pin.py`, `tests/test_asset_query_index_recovery.py` |
| 项目实例与历史合同 | `tests/test_studio_workspace_identity_history_contract.py`, `tests/test_ordinary_project_binding.py`, `tests/test_passive_generation_manager_binding.py` |
| 分支共用 store 与生成绑定 | `tests/test_export_jobs.py`, `tests/test_generation_idempotency_contracts.py`, `tests/test_phase7_adaptation_authorization.py` |
| 旧原子写/权限边界 | `tests/test_atomic_write_windows.py`, `tests/test_v056_atomic_persistence_integration.py`, `tests/test_v060_project_path_persistence.py`, `tests/test_collaboration_http_boundary_v056.py`, `tests/test_p0_security_regressions.py` |

新 owner epoch/migration/CAS 仍必须新增明确测试：missing 与 legacy empty 区分、跨实例 nested 失写反例、保留字段篡改、同文件 metadata+集合原子性、active dirty read、无变化/source_lease/异常零写、同 ID 项目重建第一页拒绝旧任务、任务删除重建与 A→B→A、旧备份重放保证边界、其他 collection/尾部隐藏活动不影响授权有限观察。现有引擎合成 epoch 测试不能代替这些原 owner 端到端证据。

## 11. 本单元交付结论

只完成固定 ref 的接口准备审计。产品实现、真实 owner 接线、安全游标启用、所有执行验收与性能结论均未完成。当前阻断是没有可用的获准云执行器；共享原 owner 生命周期与提交合同尚未实施并验证。不能据此把 M2–M9 标为完成。
