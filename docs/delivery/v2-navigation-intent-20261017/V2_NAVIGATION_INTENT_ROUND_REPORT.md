# V2 初始化早期导航竞态 — 最终验收

2026-10-17（Asia/Shanghai）；从 `87408f6881fd2dc2f22038c36643ed2e0a743f33` 继续。

**指定导航竞态已修复，真实 File/PostgreSQL 与 Edge 冷启动、刷新、快速切换验收通过。** 原 App overview 晚到不能再覆盖当前 entry 的用户明确模块选择。生产 `PROMPT_ADOPTION_WRITE_ENABLED=False` 继续关闭；[PR #47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) 保持 Draft/open，完整 V2 仍为 PARTIAL，未 freeze/RC。托管账单锁单独为 BLOCKED。

实现/清单 HEAD `7893cd027433e165b4035eac0f744c27cb93310a`。本报告及原始证据另作独立提交。所有选定最终检查绑定相同的 2305 个源码文件与冻结 map SHA `73cc97473c56824881b0274d19783152d161e7547680c0401009225058bf78da`，没有运行中或当前源码漂移。

## 稳定切片

| 已独立提交并推送的提交 | 范围 |
| --- | --- |
| `5f87b9dfa550cd870975cd5a24b89ef05a5d3236` | fix(v2): preserve explicit module intent during studio initialization |
| `7833ff75f8b907214696bbaed23e8a3ca1317a8c` | test(v2): exercise real navigation intent across File and PostgreSQL browsers |
| `7893cd027433e165b4035eac0f744c27cb93310a` | test(v2): bind navigation regression sources without changing existing inventory |

[发布审计](implementation-publication-audit.json) 核对原分支、PR 和保护 refs；没有 merge 或修改生产配置。

## 原 owner 修复

导航仍由原 App 的 `studioModule`、entry ref 与原 store 订阅持有。真实模块入口同步记录明确意图，包括已经选中 NOVEL 上的同值点击，以及“打开 V2 创作工作台”。自动默认、创建项目、本机 hint 不伪造用户点击。无明确选择时保留原 IMAGE 默认与合法本机 hint。

entry 绑定原 session、actor/workspace、project 与四个 scope ID，chapter 变化不重开意图周期。同连接首次 bootstrap actor 解析保留刚选模块及合法 callback，同时更新 transport epoch；真实身份替换和 A→B→A 更换 entry，拒绝旧 callback/响应。原 query invalidation prefix 保留，新增 key 只含 opaque instance/epoch，不放原始 token。requested asset 只传给来源 entry，避免跳过默认时沿用旧项目/branch 的 hint。

详见[实现与因果 RED/GREEN](FRONTEND_NAVIGATION_IMPLEMENTATION_REPORT.md)、[独立源码审查](INDEPENDENT_IMPLEMENTATION_REVIEW.md)。没有新增导航全局 store、权限、数据或持久化 owner；原 adoption/Review/CAS owner 未改。

## 真实验收结果

| 本轮检查 | 原始结果 |
| --- | --- |
| 新 mounted 回归 | 34 passed；相关 7 模块共 128 passed，包含这 34 项；最终独立 tsc PASS。 |
| 真实 File + Edge | 6 passed / 0 failed / 0 skipped / 0 flaky；[receipt](../v2-development/nav-intent-browser-file-final-r1.json)。 |
| 真实 PostgreSQL + Edge | 新空库 OID 28822，原 20 迁移；6 passed / 0 failed / 0 skipped / 0 flaky；[receipt](../v2-development/nav-intent-browser-pg-final-r1.json)、[PG 回执](../v2-development/nav-intent-browser-pg-final-r1-postgres-runtime.json)。 |
| 完整 frontend/src | 4242 passed / 6 既有 skipped / 0 failed，391 文件；[JSON](frontend-src-final-r1.json)、[receipt](../v2-development/nav-intent-src-final-r1.json)。 |
| 原构建、设计约束 | `tsc -b && vite build` PASS；原 canonical visual/geometry 7 passed、原 token 52 文件 PASS；[视觉复核](FINAL_FRONTEND_VISUAL_REVIEW.md)。 |
| 原 CI 清单自检 | 166 passed；[receipt](../v2-development/nav-intent-ci-selfchecks-final-r2.json)。 |
| 双 collection | 15142 个原 literal pytest node、顺序、分类保持；新增 4 个 source 路径，2367 个 manifest 输入。INVENTORY_ONLY，不是 15142 项测试执行通过。 |

File/PG 各覆盖 1366×768、1440×900、1920×1080：冷启动同值 NOVEL、刷新 IMAGE→VIDEO→NOVEL、无模块点击默认 IMAGE、跨 project 和 branch 切换。用户通过原连接与范围 UI 获取真实 LocalSessionBootstrap 身份，打开原 V2 工作台已保存分镜；晚到 overview 后顶栏选择、文档和范围保持正确，原 owner 回读不变。截图、原 response 正文/摘要、真实 DOM 状态及逐案例核对见[运行验收报告](NAVIGATION_INTENT_RUNTIME_ACCEPTANCE_REPORT.md)。

时序控制只暂缓**客户端原 GET dispatch**，点击后用无修改的 `route.continue()` 放行真实 HTTP200，未使用 response mock、身份/store/localStorage 注入；不声称 hold 时服务端已经收到请求。真实 browser 的点击发生在 bootstrap actor200 之后；actor 尚未补全时点击、parent ABA 的更强对抗边界由 mounted 原 App 回归单列证明。本机 saved hint 正控也只引用原本机 mounted reader，未冒称 authenticated browser 覆盖。

跨范围 held 的旧子工作区 GET 被原 owner 实际取消（ERR_ABORTED）；新的 parent GET 返回真实200。旧/新 owner 独立 readback 不冒充被取消的旧 callback 交付。没有等待默认 IMAGE 后再开始核心冷启动/刷新竞态，也没有用重试隐藏失败。

本轮 backend 全部是普通 `uvicorn app.main:app`，从未将 gate 置 True；每个真实来源范围的 capability 为严格 False，没有 adoption POST，原 CreativeDocument 前后不变。File/PG 的项目、身份、授权和文档使用原 adapter；资产字节仍属原 File AssetLibraryService，不称为 PG blob。显式关闭 mock provider；模型 NOT_REQUESTED，计数 NOT_INSTRUMENTED。

## 原字节保护和限制

[最终来源审计](FINAL_SOURCE_PROVENANCE_REVIEW.md) 与 [source 绑定](source-binding-final.json) 核对 2305 runner 源；[Git 原字节](source-git-binding-final.json) 和 [2367 manifest 输入](manifest-source-git-binding-final.json) 全部与实现 HEAD 相同。原 750 frozen test/gate、752 保护产物、1118 既有 test/spec/gate、61 adoption 源及原 connection guard 保留。不是全部 V1 app 源码或 V1 runtime PASS 声明。

原 9151 manifest SHA `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262` 未变；新 V2 manifest SHA `6f621dcf211c778b09f9ee3351cca511a18b605d0f6d161383816c60dc0ea269`。manifest 只更新来源指纹，不改变原 15142 rows 或分类。

托管 CI 为 **BLOCKED_HOSTED_ACCOUNT_BILLING**：实现 HEAD 的 3 个已触发工作流 job steps 为空，原 GitHub 注释明确账单问题；[独立阻塞证据](hosted-ci-implementation.json)。本地自检不代替 hosted CI，未修改工作流或账户。解除锁后仍需重跑最终 HEAD 托管检查。

原失败与中间证据全部保留；[首次 CI 命令启动错误](ci-selfchecks-launch-error-r1.json) 是 orchestrator 缺少 child Python 路径，尚未启动 pytest，修正后新编号 r2 通过，源码未改。mounted 的设置错误与真实因果 RED 在实现报告中分别注明，没有改写旧断言、旧测试或既有 skip。

自有 API/Vite/PG 已停止；[停止与保留审计](runtime-retention-final.json)。失败/通过回执、截图、profile、PG 数据库和先前 baseline worktree 保留，未递归删除或宣称回收空间。原始字节清单见[evidence-manifest.json](evidence-manifest.json)。

本轮只建立指定导航修复的 PASS；此前 adoption 成功写回执保留为历史，不冒称本轮重跑。完整 V2、生产 adoption、installer/clean-machine、真实模型/GPU 与既有 Canvas/Director/媒体/NLE/3D/Tutor 全链路未由本轮建立 PASS；[前轮既有边界](../v2-r3-adoption-ui-20261017/V2_R3_ADOPTION_UI_ROUND_REPORT.md) 保留。生产 adoption 闸门继续关闭。

首次证据暂存因 Windows Git 长路径限制失败，随后的两项索引检查也因尚未暂存而未通过；[记录](evidence-staging-error-r1.json)。仅启用仓库本地 `core.longpaths=true` 后重新暂存和核对，原文件路径/字节、产品/测试源码均不变，没有删图或重跑验收来掩盖该发布错误。

GraphFlow 使用可用 gf_read 压缩上下文；legacy graphflow_index 未提供，未声称调用成功，本地缓存保留。
