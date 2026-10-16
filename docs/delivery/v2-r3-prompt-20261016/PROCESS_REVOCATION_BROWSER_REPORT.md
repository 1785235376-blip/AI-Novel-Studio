# R3 跨进程撤销与真实浏览器验收

本轮限定范围本地验收 **PASS**：File 跨进程 24 项、真实 PostgreSQL 103 项，以及 File/PostgreSQL 各 3 个 Edge 视口。生产 `PROMPT_ADOPTION_WRITE_ENABLED=False`，真实采用路由仍精确返回 `503 PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`；整体 R3 不能据此标记为全部完成。

| 最终运行 | 实测结果 | 原始回执与日志 |
|---|---|---|
| File 独立进程 | 24 passed，24 deselected，215.34s | [JSON](../v2-development/r3-prompt-process-file-final-r3.json)、[log](../v2-development/r3-prompt-process-file-final-r3.log) |
| PostgreSQL 合并组 | 103 passed，99 deselected，1355.06s | [JSON](../v2-development/r3-prompt-combined-pg-final-r3.json)、[log](../v2-development/r3-prompt-combined-pg-final-r3.log) |
| File Edge | 3 passed，15.5s | [JSON](../v2-development/r3-prompt-browser-file-final-r4.json)、[launcher](browser-file-final-r4/launcher.json)、[Playwright](browser-file-final-r4/playwright.log) |
| PostgreSQL Edge | 3 passed，2.4m | [JSON](../v2-development/r3-prompt-browser-pg-final-r1.json)、[launcher](browser-pg-final-r1/launcher.json)、[Playwright](browser-pg-final-r1/playwright.log) |

103 项包含新增跨进程 24、私有生命周期 48、来源绑定 26，以及原有授权 HTTP 4、项目实例重建 1。原始 JSON 保存完整命令参数、运行隔离环境、前后源码摘要和退出码；[toolchain](validation-toolchain.json) 记录 Python 3.12.9、pytest 8.4.2、psycopg 3.3.6、Node 22.14.0。

每个跨进程用例都使用原始身份、成员关系、角色/权限仓库和 `LocalSessionBootstrap`，由独立 OS 进程提交写入和撤销，仅在原始持久化边界设置 IPC 屏障。4 种操作（create/revise/delete/adopt）×3 种撤销×2 种顺序均覆盖。先撤销时精确拒绝且原始文档与资产字节摘要不变；先写入时提交成功后撤销。48 组均继续复用写入进程的**同一枚原始会话凭证**，得到精确 `403 PROJECT_SCOPE_FORBIDDEN`，并完成另一真实授权用户的写入/读取正向检查。

File 证据包含当前持有者 `HELD` 与等待者 `WAITING` 的同路径原始 OS 锁记录：24 组中 8 组等待 project-lifecycle、16 组等待 authorization-store。PostgreSQL 24 组由真实 `pg_stat_activity` 的 `Lock` 等待及 `pg_blocking_pids` 确认持有者。见 [File 汇总](file-process-summary.json)、[PG 汇总](pg-process-summary.json)、[File 原始目录](process-file-final-r3)、[PG 原始目录](process-pg-final-r3)。进程测试通过原始挂载 ASGI 路由调用，真实 TCP 页面流程由独立浏览器组验证；这里不声称跨进程共享原始内存会话注册表。

浏览器使用同一个新增启动器、原始打包 bootstrap 与共享 Prompt 验收入口，无响应替换。1366×768、1440×900、1920×1080 均完成页面新建、精确 Unicode/空白正文、不可变历史修订、正文比较、私有删除后不可读历史、重复删除和私有 restore 精确 404。**DELETE 是真实浏览器 HTTP 操作，产品目前没有 Prompt 删除按钮**；不将它描述为按钮流程。删除后服务端正文为 metadata-only tombstone；已加载的本地草稿可能仍在编辑器内，不声称清除了客户端已有内容。`model_execution=NOT_REQUESTED`，`model_counter=NOT_INSTRUMENTED`，不构成模型/媒体闭环验收。

[浏览器结构化汇总](browser-acceptance-summary.json) 保存真实 API 状态与页面几何；[全部截图路径及 SHA256](browser-screenshot-paths.json) 包含两后端各三视口的两修订和 tombstone 共 12 张截图。PostgreSQL 三张 tombstone 截图已逐张目视检查，原有顶栏、导航与历史保留，修订 2 显示“已删除 / 不可读”，修订 1 仍在。原有浏览器规范及共享入口与基线字节一致，见 [保护审计](protected-browser-source-audit.json)。

PostgreSQL 使用原始仓库保存项目、身份、授权及 experimental 状态；不可变资产字节/元数据继续由原始 **File AssetLibraryService** 持有，没有 PG blob 替代或 File 数据库降级。两份数据库均为 loopback 50678 上新建的空数据库，并执行原有 20 个迁移：

| 用途 | 数据库 | OID | 终态 |
|---|---|---|---|
| 合并回归 | `v2_r3_prompt_20261016_final_r3` | 23468 | retained，server stopped，cleanup completed |
| 浏览器 | `v2_r3_prompt_browser_20261016_final_r1` | 24389 | retained，server stopped，cleanup completed |

原始 runtime：[合并](../v2-development/r3-prompt-combined-pg-final-r3-postgres-runtime.json)、[浏览器](../v2-development/r3-prompt-browser-pg-final-r1-postgres-runtime.json)；[服务日志](postgres-runtime) 原样保留。[独立清理检查](final-runtime-cleanup.json) 确认 `pg_ctl status` 退出 3、无服务器运行，端口 8138/5208/50678 均无监听，无本轮进程测试 worker 遗留；两启动器同时记录 API/Vite 子进程已停止。只停止本轮拥有的进程，数据库和证据保留。

四组最终运行的 2,290 份源码前后摘要完全相同，并与最终工作区逐项一致，差异 **0**。源码集合规范化 SHA256 为 `6e2ae8c5feb5672a0a4b8c273cea61ee539e464624bdfc7690392a3d1b35f55c`；算法为对排序、紧凑 JSON source map 的 UTF-8 字节计算 SHA256。见 [完整源码证明及精确命令](final-source-provenance.json)，各原始 receipt 中另存完整 source map。运行中 HEAD 发生提交变化，验收依据实际相同的源码字节。

| 本子任务新增源码 | SHA256 |
|---|---|
| `tests/test_v2_prompt_process_revocation.py` | `9f950759d06f07e0dbc2927f4ce812ec58210a479305e275f2e476233b87661c` |
| `scripts/run_v2_prompt_r3_browser.py` | `83a7c384dd4a871d11fa880b9e3c6ecee7ee34c8388e51bc5a26deba37d0c74d` |
| `frontend/playwright.prompt-r3-live.config.ts` | `d4bfb90bd1422738fed650a3161f9414f6557fbe305a9a82ee139c38a90afccf` |
| `frontend/tests/e2e/v2-prompt-r3-live.spec.ts` | `6ee8e331cd394186f8ca3c0dfcd4d89eae79fce90d3cd5bcc901ac836cceee9d` |

失败证据保留：[初次 File smoke](../v2-development/prompt-process-file-smoke-r1.json) 缺少功能开关导致 501；[初次浏览器 smoke](../v2-development/prompt-r3-browser-smoke-r1.json) 错选已批准共享资产，其原有 restore=200；File r2 的观测器错误等待后续授权锁，已改为证明真实首个争用锁；PG r1/r2 为修正观测器及冻结源码而受控中断的诊断运行，原始 FAIL 回执未改写，也未充当完成数。见 [File r2 原始失败](diagnostic-file-witness-r2)、[PG r1 中断说明](r3-pg-diagnostic-interruption.json)、[PG r2 中断说明](r3-pg-diagnostic-interruption-r2.json)、[原始回执副本](check-receipts)。隔离子进程内开放采用仅用于底层写入契约测试，普通浏览器生产开关始终关闭。

本子任务没有修改冻结 750 测试、原有受保护浏览器规范或 CI gate。最终验收期间没有应用/测试/启动器源码修改；本报告只给出上述本地真实运行范围的结论。
