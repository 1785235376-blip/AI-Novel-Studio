# R3 adoption UI 隔离成功写验收

2026-10-17（Asia/Shanghai）；从 `95420aa59acb4c196d92e7292df0744098f6d2ff` 继续。

**指定的 adoption UI 成功写闭环已通过真实 File、PostgreSQL 与 Edge 验收。** 生产 `PROMPT_ADOPTION_WRITE_ENABLED=False` 保持关闭；[PR #47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) 仍为 Draft，完整 V2 为 PARTIAL，未 freeze/RC。托管账单锁单独记录为 BLOCKED。

最终实现/清单 HEAD 为 `db1f687108fac6e45a577196494dfac01cc63aca`；最终报告和原始证据另作独立提交。补齐启动就绪和原连接竞态修复后，以下最终运行均使用相同的 2301 份运行源码，逐字节一致；旧 `6aed517` 与中间快照的运行/失败保留为历史，不混作当前源码通过回执。

## 已逐个提交并推送的切片

| 提交 | 范围 |
| --- | --- |
| `679a88b635639fb680f56893a41857b4e79001ec` | feat(prompt): expose closed adoption write capability to existing UI |
| `2216af12089a8df8f96e8fbe31c92ed1f27ab953` | feat(prompt): add guarded adoption UI with owner readback |
| `69df94abd1604f32d397b991a6680d516edca59d` | test(prompt): prove isolated adoption UI writes through real owners |
| `6aed517611117771d767eb275a54773b24ba0300` | test(v2): pin adoption UI sources and additive capability coverage |
| `2d96d904a59d4403e2125b05f78b0b4c3c7c4adc` | fix(ui): preserve pending workspace connection during local resume |
| `71d0b1ca69e642315781b72a5dcecc2d0682fa27` | test(prompt): await original studio startup before adoption navigation |
| `db1f687108fac6e45a577196494dfac01cc63aca` | test(v2): bind adoption entry regression and browser readiness sources |

[实时实现发布审计](implementation-publication-audit.json) 核对 PR/ref；main 与 V1 frozen refs 未改。

## 原 owner 与真实 UI

新增面板位于原 Storyboard 工作区，复用原 `createPromptClient`、Asset approval、adoption POST、`GraphAssetInputs.phase`、`adopt_atomic` 与 CreativeDocument CAS。没有新增 Prompt、版本、Review、授权或持久化 owner；原只读 PromptAdoptionPanel/Disclosure/client 的产品与测试字节保留。

用户核对保存的目标版本/摘要，读取真实来源家族和完整修订正文，单独审批，再次读取获批修订，勾选确认后采用。POST 仅传原闭合 DTO 的 ID、修订、摘要、目标 CAS 与 request_id，不传正文或客户端凭证。UI 同时要求原 host 可写和原 GET 返回严格布尔 `write_enabled=True`；缺字段或 False 时关闭写入口，能力字段不授予 viewer 写权。

成功必须回读原 CreativeDocument 和 adoption 投影，核对单次版本增加、正文精确相同、固定来源 identity/digest/result_version 与仍生效状态，再更新原 host 的 documents/base/value 和原 controller。未知响应只重试同一 DTO/request_id；已确认提交但回读失败后仅重新核对，不重复 POST。

独立复核发现并修复迟到回读覆盖新版本的窗口：原 host 回归先 RED，再要求当前 clean/base.version 仍等于提交前目标版本才接受回读；否则抛错、保留新版本、不显示成功。详见[实现及 RED/GREEN](FRONTEND_ADOPTION_IMPLEMENTATION_REPORT.md)、[独立 UI 复核](INDEPENDENT_UI_ISOLATION_REVIEW.md)。

## 隔离闸门与成功写闭环

仓库常量始终为 literal False。仅新验收启动器明确启动的独立后端子进程在导入原应用后、uvicorn 前将内存布尔值置 True；无产品环境变量、header/query/body 或常驻配置的开启入口。

每个 File/PG 浏览器启动器在前后分别启动未 patch 的普通后端，真实 GET 为 False、POST 精确 503 `PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`、原 owner 状态不变，中间才运行隔离 True 子进程。这些是本地关闭控制，未宣称生产部署或生产成功写开放。

两后端各三个 Edge 视口（1366×768、1440×900、1920×1080）通过真实 UI 创建手工 Prompt，绑定原 NovelService 的真实 Character，单独审批/确认，再由产品按钮发出一次 adoption POST 200。原文档增加一个版本、一条证明，主编辑器逐字同步中文、emoji、换行及首尾空白；整页刷新/重开恢复原文档与 r1 固定来源。UI 创建来源 r2 后，目标保持 r1 并显示有更新版本。

真实证明含 `prompt-adoption-bindings/1`、`source_bindings_verified=True` 和真实 CHARACTER owner/version/incarnation/digest。该标记仅证明提交时声明绑定经原租约检查，不代表当前所有依赖仍有效、额外审批或可渲染。原 DTO 附加 replay 为 200/无重复；改变同请求时，原 owner 精确返回 422 `EXPERIMENTAL_INVALID` / `PROMPT_ADOPTION_REQUEST_REUSED`，原文档不变。

身份来自原 packaged LocalSessionBootstrap，没有 response mocks、伪造 dev-session 注册表或注入本地文档状态。项目/身份/授权/experimental 使用原 File 或 PostgreSQL owner；PG 场景的资产字节和 metadata 仍由原 File AssetLibraryService 保存，不称为 PG blob。浏览器未请求模型或任务执行；模型计数未仪表化，模型结果为 NOT_REQUESTED，计数为 NOT_INSTRUMENTED。

完整控制、证明、截图与解码凭证见[真实运行报告](ADOPTION_UI_RUNTIME_ACCEPTANCE_REPORT.md)。

## 最终原始结果

各组存在重叠，不累加为唯一覆盖数。固定 Python 3.12.9 / pytest 8.4.2，沿用原 run_v2_checks/run_v2_postgres_checks。

| 范围 | 结果与回执 |
| --- | --- |
| 真实 File capability、bindings、并发、HTTP/router | 55 passed，38 deselected；[receipt](../v2-development/r3-adoption-ui-bindings-file-final-r3.json)。 |
| 真实 PG capability12、bindings26、原授权/incarnation5 | 43 passed，39 deselected；[receipt](../v2-development/r3-adoption-ui-combined-pg-final-r3.json)。 |
| 真实 File Edge 三视口 | 3 passed；[receipt](../v2-development/r3-adoption-ui-browser-file-final-r3.json)。 |
| 真实 PG Edge 三视口 | 3 passed；[receipt](../v2-development/r3-adoption-ui-browser-pg-final-r3.json)。 |
| 全 frontend/src | 4208 passed，6 skipped，0 failed；[receipt](../v2-development/r3-adoption-ui-src-final-r4.json)、[完整 JSON](frontend-src-final-r4.json)。 |
| TypeScript / Vite | 原 tsc -b 与 build PASS；[receipt](../v2-development/r3-adoption-ui-build-final-r3.json)，原 large-chunk warning 保留。 |
| 原视觉/几何 | 7 passed，三模块 baseline、四 shell 视口，未更新 baseline；[receipt](../v2-development/r3-adoption-ui-visual-final-r3.json)。 |
| 原 UI token guard | 52 个 frontend/src/ui 文件 PASS；[receipt](../v2-development/r3-adoption-ui-tokens-final-r3.json)，不扩大解释范围。 |
| 原覆盖清单/对账/增量自检 | 166 passed；[receipt](../v2-development/r3-adoption-ui-ci-selfchecks-final-r3.json)。 |

PG 合并库 `v2_r3_adoption_ui_20261017_final_r3`（OID 27042）与浏览器库 `v2_r3_adoption_ui_browser_20261017_final_r3`（OID 27943）分别是迁移前无应用对象的新空库，原生 PostgreSQL 16.15，各执行原 20 migrations。原始运行耗时见各日志。

[前端命令/日志绑定](frontend-verification.json)、[视觉独立复核](FINAL_FRONTEND_VISUAL_REVIEW.md)、[来源独立复核](FINAL_SOURCE_PROVENANCE_REVIEW.md) 保留独立验证边界。旧跨进程24/PG103属于上一轮历史，本轮未重跑，不冒充同源码通过数。

## 精确源码与冻结保护

- 2301 份运行源码与最终实现 HEAD raw bytes 相同，无 EOL 例外；[Git 绑定](source-git-binding-final.json)。全部最终成功回执严格比对同一完整 source map、原日志 SHA、无运行中漂移，见[source-binding-final.json](source-binding-final.json)。
- V2 清单全部 2363 个源码输入与工作区 SHA/Git raw blobs 相同；[全清单绑定](manifest-source-git-binding-final.json)。
- 两次独立完整 collection 的字面 ID、顺序与分类相同：15142 = 原15118原样保留 + 新capability24；原 skips/external gates 不变。[delta](collection-delta-final.json)。这是 INVENTORY_ONLY，未称15142通过。清单 SHA `ceacc0cb2f100dde23ce07a76dd086d27ae3eafbafc1b2499b97a0425a1dc405`。
- 750 个 frozen test/gate 源码、752 个保护产物及原9151 manifest 字节不变；[保护审计](protection-final.json)。9151 SHA `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`；不扩大为全部 V1 app 源码或 V1 运行验收。

## 失败证据与限制

首次 PG 浏览器 r1 的三个视口均已完成真实采用写入/主编辑器同步，随后在整页刷新重开时失败。原 App 的 overview 成功后默认恢复 IMAGE，可覆盖此前已允许的早期模块导航。该既有产品启动竞态仍未修复；新增 spec 等待真实 IMAGE tab selected 和原独立工作区加载完成，再导航 Novel，不增加 sleep/retry、不弱化重开断言。最终 r3 三视口建立的是启动完成后的采用闭环，未建立任意初始化时机的导航可靠性。旧失败日志/截图/数据库原样保留，spec 差异见[startup-ready-harness-delta.json](startup-ready-harness-delta.json)。

随后 File r2 为2 passed/1 failed：首冷启动在凭证连接后、选协作项目之前，被原父页面迟到的本机作品列表自动切走，尚未进入采用。原 Entry recover 先改变全局 API 会话，Studio store 尚未接纳完整 scope，原 local 自动恢复因此借用了连接中身份。已在原 App 自动恢复入口补会话/范围一致性检查，覆盖所有自动选择分支；没有改 Entry 全局行为或创建授权旁路。新增 mounted 回归先 RED 后 GREEN，真实 File/PG 最终运行另验证完整连接与采用。详见[连接竞态报告](ENTRY_CONNECTION_RACE_REPORT.md)。

原只读 adoption inspector 的长64hex摘要有横向裁切；完整固定来源由 DOM 与解码 JSON 校验，未宣称截图全部可见。1920 截图诚实保留原上游 Director 不可读状态，本夹具源于 Screenplay，不代表全部依赖有效或渲染就绪。

初次 capability 新 fixture 残留旧 store phase cache，修复只在新增测试隔离设置；准备12passed含并行源码漂移，不计最终通过。原 host CAS 红测与修复记录保留。六次 File smoke 前五次失败保留：项目全局 Character 错带 branch header、breadcrumb/tab/隐式 label 定位错误、把原422拒绝误期望409；第六次1视口通过仅作准备，最终采用新冻结回执。

全 src 首次进程 cwd 错留仓库根，--root frontend 未修正原夹具相对路径，产生 ENOENT。失败 JSON/receipt 原样保留，修正验证命令 cwd 后重跑；没有修改原产品/测试来规避。

托管 CI 单独为 **BLOCKED_HOSTED_ACCOUNT_BILLING**：该实现 HEAD 的 3 个已触发工作流 job 的 steps 为空，原 GitHub 注释明确账单问题；[证据](hosted-ci-implementation.json)。本地166自检不替代最终 HEAD 托管 CI，未改工作流、账单或账户。

完整 V2、生产默认采用成功写、installer/clean-machine、真实模型/GPU 及既有 Canvas/Director/媒体/NLE/3D/Tutor 全链路未由本轮建立 PASS。生产 adoption 闸门继续关闭；外部账单锁解除后仍需重跑最终 HEAD 托管 CI。

自有 API/Vite/PG 已停止；[停止与保留审计](runtime-retention-final.json)。失败/通过回执、截图、profile、PG 数据库及先前 baseline worktree 均保留，未做递归清理、未宣称回收磁盘。原始字节总清单见[evidence-manifest.json](evidence-manifest.json)。

本会话 GraphFlow 可用 gf_read/gf_edit/gf_exec/gf_macro，已用压缩上下文；旧 graphflow_index 未提供，未声称执行该接口，本地缓存保留。
