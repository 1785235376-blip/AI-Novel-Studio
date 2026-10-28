# PoemSeed Studio V2 统一集成交付

报告日期：2026-10-28，Asia/Shanghai。此报告接续历史 M0 checkpoint；用户随后明确授权“仅在全新隔离目录克隆 GitHub 并用合成数据验证”。此前 M0 的 BLOCKED 是当时环境状态，不是本交付的当前结论。

本轮已交付 A+B+C 的可运行集成候选，修复首次 IMAGE 正式回填 403，以及独立反例发现的资产提交窗口陈旧关联。所有操作位于新目录 `D:\PoemSeed-Unified-20261027-94f1c72e`。没有读取本地旧项目、旧任务或真实素材，没有付费模型调用或 GPU 推理。未合入 main，未部署、发布 Release、删除原分支或重写共享历史。

## 源码与采用位置

分支：`work/studio-v2-unified-integration-20261027`；[Draft PR #50](https://github.com/1785235376-blip/AI-Novel-Studio/pull/50)，目标 main。

最终受测源码 **`5eec654b0bbcbeb5355a640a5c5109d703ab1cbf`**，完整 tree **`136628f86ad6c2ada0d29962170d16942688acc1`**。独立干净检出 `final-verification-5eec654b` 在测试期间未修改；根 tree、子树与输入锁定见 [SOURCE_FREEZE.json](SOURCE_FREEZE.json)。之后交付提交仅追加本目录文档、原始证据及摘要；PR 记录普通 push 后读回的完整发布 HEAD/tree。最终发布与冻结点的受测路径差异为零，校验记录随证据发布。

| 稳定切片 | 完整提交 | 行为与来源 |
| --- | --- | --- |
| A 起点 | `457ea4a5a45ab13f351980665e053c5c77d15c82` | 已有资产保护、TaskCenter 合并保持原样；G→A app/tests/scripts/frontend tree 相同 |
| B 唯一增量 | `f02ff272ecbef9bdc007c4b28cca2d47b08f8ecc` | 精确 cherry-pick -x `f6473e307e9d0501a41dc46dd991645a437103d7`；不重复祖先合并 |
| A+B TCP 契约 | `7387dd1f6a45e2ee755b0268885617c9b7ff7085` | 原 A 测试仍期待已支持组合 501，红灯后改为真实分页/回执/零写断言，其他拒绝保留 |
| C 常规合并 | `9c01565800931bd1ef49e9949a65e130f754b349` | 真实 merge C `fe4f55412299fadfada0354725b3ca46e418c46a`，保留双方历史和 owner |
| 首次回填权限 | `c479995fb976044782eac200775e3990083f3902` | 原 graph invoker 显式预先获取 source read；真实权限在提交阶段继续复核 |
| 布局验收适配 | `8612b1d0506ce18b6772c0393cecf1ddc5f9bf23`、`bc0fa26b5adf01f953c83b1e66623b5d05074b57`、`9d40f648ace454fa66d4ac7b8bff68a3612b8660` | 原浏览器矩阵支持高度参数、声明内 Playwright、禁用 GPU；不改产品 UI |
| 真浏览器闭环 | `9a2db14338ea00ac9ad2c99ae4945755bb405dae`、`766b5cac5ce130ebd312d9d6ce56250c8607b48a` | 显式执行/审核/采用，UNKNOWN 读取恢复、关闭重开和后端重启、上下文和历史双 API 断言 |
| 提交前资产复核 | `5eec654b0bbcbeb5355a640a5c5109d703ab1cbf` | 原资产 owner 合法重入后再次核验同一 proof；变更则 409，Canvas 不写、合法资产更新保留 |

A/B/C/main 最后一次远端读回仍为任务指定完整 SHA，无浮动输入混用。完整 M0 继承、差异、G 冻结对应见 [M0_REMOTE_CHECKPOINT.md](M0_REMOTE_CHECKPOINT.md) 与 [M0_REMOTE_EVIDENCE.json](M0_REMOTE_EVIDENCE.json)。M0 的历史暂缓语句只描述当时，不替代本报告。

## 冲突与 owner

七个前端冲突均有文件/符号决策：[M2_CONFLICTS.md](M2_CONFLICTS.md)。C 相对共同祖先没有后端 app/root scripts 改动，因此常规合并保留 A+B 后端；未用 C 覆盖后端。主要语义为 C 的主题/国际化/双画布/分页过滤与 A 的身份 epoch、来源 fencing、TaskCenter retirement/discard 兼容。独立核对 26 个保护符号保持 A 原实现。自动合并产生的重复绑定造成一次 TS2451，去重后构建通过，失败日志保留。

生产修复仅在原 Graph/Canvas owner：不另建 Asset/Production/Review/TaskCenter/Export/身份/权限系统。没有 `local_input=True` 强制、token 忽略、scope 放宽、403 吞掉或自动审核。

首次 403 来自空 Canvas 外层写闭包未先获取 source-read，而首次 origin 插入使其提交复核变为需要 read。显式 requirement 修复同一闭包。独立资产反例则在 `change_row` 后合法调用原 `Asset.update_metadata`：v2→v3 后旧版仍保存 v2 pin。新提交前复核阻止该同线程重入窗口；跨线程仍由原租约串行化，未声称跨线程可突破锁。

## 真实 IMAGE 链与范围

**真实前端＋真实原应用 File 持久化＋真实 HTTP＋独立 Chromium＋本地确定性 A1111 Mock provider**。浏览器自动化模拟用户逐步确认；不是付费模型或真实 AI 质量验收。

最终冻结版正常链与独立响应丢失链均完成：创建合成项目和正式空画布→准备参数与影响范围→明确确认→原任务入队→明确执行→私有候选读取→明确审核采用→原节点回填 200→关闭浏览器重开→停止原后端进程、以同一 File 数据启动新进程并重新读取。

正常与 loss 各三阶段都通过。每条链 provider 仅调用一次；flow 的 execute/review/image-node-result POST 各一次；两次重开阶段各零写请求。连点执行未二次派发。loss 在真实服务器提交 200 后中断回包，界面保持 UNKNOWN，无成功提示或自动重发；显式读取并选择原记录后恢复。保存 v1→v2；精确核对初建 Canvas id/version/digest、项目实例/scope、原 Job/version/request digest、正式 Asset id/version/SHA、节点坐标与来源，三阶段历史及资产元数据一致；相关 Canvas/Job/Asset/history 均核对 `/api` 与 `/api/v1`。

实际后端导入日志中，两进程所有应用路径均来自最终检出；无旧目录应用模块。截图、HTTP JSON、Mock 调用、进程日志、退出码和前后源码 SHA 在 M6 archive。

验收使用 Vite dev 服务、通过真实 `/api/local-session` 后显式绑定合成 local-host 身份，并为测试种入合成本机图草稿；不声称正常登录 UI 或未保存草稿冷启动能力已验收。正式 IMAGE 为单节点原制作任务/审核/关联；本机图的提示词、连线、上下画布仍是草稿。VIDEO 执行明确 unsupported，双画布可见不等于完整图执行编排。

## 验证结果

命令、原始 stdout/stderr、退出码、耗时、JUnit/JSON、模块来源和前后哈希均随各 archive 保留。历史切片详见 [M1_M3_VALIDATION.md](M1_M3_VALIDATION.md)。组间有重叠，不累加为唯一总数。

| 固定版本/组 | 实际结果 |
| --- | --- |
| A+B `7387dd1f` | TCP 4、File 150、TaskCenter 357、owner/lifecycle 187、Windows process 26，各独立组均 PASS，无 timeout |
| A+B+C+权限修复 `c479995f` | 新真实 IMAGE/权限/重启 28 PASS；原 Canvas 保护 52 PASS；API/身份/旧接口兼容 144 PASS |
| 最终 `5eec654b` 同版本后端组合 | 805 PASS，45 文件；exit0，无fail/error/skip/timeout；Pytest641.62s，进程644.789s，源码哈希及前后clean一致 |
| 最终独立反例 | 5 PASS：原资产提交窗口、跨线程租约、双并发/重放仅一次历史、actor 变更 before/commit |
| 权限修复反向 | 独立 mutation 检出仅撤两 app 文件，原正向两 API 各以 403 失败，200 预期保留 |
| 资产复核反向 | 独立及仓库最小反例各以 200/陈旧关联落盘失败；最终检出未改 |
| 最终标准前端构建 | PASS，exit 0，50.000s |
| 最终受影响前端组 | 10 文件 119 PASS，0 fail/skip/collection error；exit 0，13.656s |
| 布局矩阵 `9d40f648` | 124 条 PASS，0 fail；真实 React/Chromium＋合成只读 browser-mocked API，非执行验收 |
| Windows 资产列表 | 最终 `5eec654b` 1 FAIL（503 ASSET_QUERY_CURSOR_UNAVAILABLE）、1 原签名控制 PASS；OPEN |

布局覆盖 1366×768、1024×768、1440×900、1920×1080，深浅主题、普通/专业、IMAGE/VIDEO、下画布独立与普通 `.rcv` 宽度>0。相关产品源码在最终版本未改。初次浏览器依赖错误及预览 Origin 配置拒绝都保留为开发失败；修正启动配置后重跑，没有关闭来源校验。

TaskCenter 支持仍限实际 File、非 packaged、原 local 的 semantic_import+exports。真实聚合成功回执、最终 registry 核验、authority/实例/生命周期、空源、200/100 原窗口和旧 offset 保留；协作 exports/混合、任意组合、PG/packaged 混合仍拒绝。GET 无 ExportJobService 构造、启动恢复或导出执行。最终 10 个 TCP 子进程回执记录 296 次 GET，零业务/命令/严格只读写入及严格设施创建；仅两个普通模式原有锁字节初始化写入。最终组合重跑原 357 项，包括独立实际聚合 403/404、最终 registry 重排、空/非空源拒绝、同 ID 不同 authority、来源替换、项目重建与窗口上限；未以独立前后探测替代真实回执。

### 前端全量基线

同一环境各跑一次，保留完整失败，未重复全量增加通过次数：

| 版本 | 文件 | 断言 | 命令状态 |
| --- | --- | --- | --- |
| C `fe4f5541` | 951 pass / 54 fail / 1 skip | 13110 pass / 329 fail / 6 skip | build 0；Vitest exit1，662.156s |
| 集成 `c479995f` | 955 pass / 51 fail / 1 skip | 13144 pass / 297 fail / 6 skip | build 0；Vitest exit1，690.203s |

按相对路径＋fullName＋重复项序号比较：296 共同失败、33 原失败通过、1 新增失败观测，无丢失 suite/test ID。新增 A 的 ImageRebuild.canvasQueue 两例通过。共同失败 283 完整签名一致；13 变化为 3 选择器差异、4 随机节点 ID、6 异步栈。共同收集错误是引用缺失 Playwright 文件，零断言；6 项 HTTP 测试未启动后端而跳过，未计通过。

唯一新增观测 `u1.purge.host` 已在 C 的透明 instrumentation 复现：两次成功查询被 React 合并通知，漏掉第二次缺失观察；owner/关键依赖 11 路径同 blob。原 C 单项通过、集成单项失败，以及 C instrumentation 失败/集成 instrumentation 通过都保留。分类为既有通知合并窗口 OPEN，不叫集成引入，也不以复跑抹掉失败。其他失败包括 FeatureLauncher mocks、Windows python3 ENOENT、缺 fixture、旧选择器，未统称 flaky。

最终与 c479 的 2166 个直接前端文件及 22 共享 fixture 字节一致；最终 build 和 119 例为最终 HEAD 实测。跨语言 scanner 会读取后端，而最终 Canvas 提交复核有变化，因此不把上述等价证明扩大为全部跨语言输入一致。**最终全量未再次运行；没有全量全绿声明。**

## 旧 PR 与暂缓项

完整路径清单在 LEGACY_FINAL archive。PR47 REST 实际只返回 3000/8054 项，已拒绝将它当完整差异，改用补足历史后的本地 merge-base 与完整 Git diff；未使用 unrelated-histories。

| 项目 | 最终处理 |
| --- | --- |
| PR47 `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3` | open Draft，仍 dirty；完整 8054 路径逐 blob 对比：884 相同、386 不同、6784 同路径缺失（大量历史证据）；不整支合并、不判全部过时。其中变更运行时路径 1145：826 相同、319 不同、0 同路径缺失；完整缺失/差异明细见 JSON |
| PR48 `58bbaad11360330d51f49fc2bb78a955a26469f0` | open Draft，目标 feature/v2-narrative-platform；112 路径最终 31 相同、64 不同、17 同路径缺失，逐项清单保留 |
| 已重命名成本回执 helper | taskCostReceipt.ts 的同 blob 存在 taskCostReceiptHelpers.ts，视为继承，不当作功能丢失 |
| 仍缺 test-discovery guard/manifest | 两文件有价值但库存已变化，暂缓适配；不能盲恢复旧 manifest 或运行带准备副作用的 Playwright list |
| 音频/public-build/director 等旧测试与需求文档 | 缺路径和不同内容均列出供 owner 后续协调；未盲补与未声称替代覆盖齐备 |
| 音频 `2acab55d2ef64ca76f2093e376bf6388af364282` | PARTIAL；不纳整支、不开放 restore 写端，容量计费/兼容项 OPEN |
| PR49 | 相关 CI/PG 工程，非本统一候选，不整支合入 |

## OPEN、NOT_RUN 与 main 判断

**统一代码整合 PASS；IMAGE 浏览器回填与重启恢复 PASS（真实前后端＋Mock）；File 保护与本地混合游标组合 PASS；前端构建 PASS，受影响 119 PASS，全量基线仍 FAIL。main：NOT_READY。**

具体未就绪依据：当前 Windows 资产列表游标 503；前端已知大组失败和缺收集文件；既有列表缺失通知合并窗口；候选 F 的 37 个原因未明拒绝仍无根因解释（G/本轮通过不等于修好）；旧 PR 差异协调和暂缓测试仍有 OPEN。没有发现需要伪装成 flaky 的新增确定性回归。

PG/容器数据库工具缺失，未做 PG 验收；不支持的 packaged/协作混合能力继续拒绝；无真实 AI 质量、本地 GPU、完整 VIDEO/多节点图编排、音频完整恢复或整体 Studio V2 发布通过声明。部分浏览器负向场景由原单元/真实 HTTP 反例覆盖，未声称每种权限撤销都在 UI 中重复跑过。GraphFlow context/plan/index 指定接口未暴露，仅 gf_read 可用；不宣称已完成 index。

三位子代理按用户要求以 gpt-6-astra 配置获编排工具接受，曾遇账户额度错误后恢复；没有独立服务模型 ID，也没有主会话切换控制，因此不宣称已核实主模型切换。Python 3.11.9、Node22.14.0、pnpm10.6.5、新隔离 Chromium；详细依赖冻结随 ENVIRONMENT archive。

Hosted Actions 的实际状态另留证；此前输入及已发布切片为零 run，旧 PR 的失败 run 为零 runner/零 steps，均非 CI PASS。未主动触发付费 workflow 或增购额度。

## 采用、继续与回退

采用时以 PR50 固定源码 `5eec654b` 为审核单位，先修上述明确 OPEN 并补需要的环境验收，再由用户决定 main 合入。不要合入 main 来替代验收。

回退不重写共享历史：回退提交前资产复核用新 `git revert 5eec654b`（会重现已记录缺陷，仅用于分析，不能作为可发布修复）；回退首次 source-read 修复用新 revert `c479995f`（正向重现403）。撤 C 集成需审核 merge mainline 后 `git revert -m 1 9c015658`，再处理依赖切片；撤 B 用 revert `f02ff272` 并同步恢复对应支持范围/测试。保留原分支和 evidence。不得将已知有缺陷的回退点称为通过版本。

## 证据索引

最终 [后端摘要](evidence/FINAL_BACKEND.json)、[浏览器正常链](evidence/FINAL_BROWSER_POSITIVE.json)、[独立 loss 链](evidence/FINAL_BROWSER_LOSS.json)、[最终前端](evidence/FINAL_FRONTEND.json)、[全量精确差集](evidence/FRONTEND_COMPARISON.json)、[独立前端发现](evidence/FRONTEND_INDEPENDENT_FINDINGS.json)。

[回填截图](evidence/screenshots/positive-saved.png)、[重启读回](evidence/screenshots/backend-restart.png)、[UNKNOWN 截图](evidence/screenshots/lost-response-unknown.png)。详细命令/日志/源哈希在下面的包内；每包都含 CONTENTS_SHA256.json，并逐 payload 读回验证。依赖 symlink、node_modules、Git 和缓存排除，原始测试/配置/日志/状态保留。

| 原始证据包 | 范围 | SHA/字节数 |
| --- | --- | --- |
| [M1_COMBINED.zip](evidence/M1_COMBINED.zip) | A+B 与真实 TCP | [1350486 bytes](evidence/M1_COMBINED.json) / `ffda8d74775c1f0b17aaf98cfa2dc834bebe865804a1dfcac9755a54fbbb40c4` |
| [M3_FROZEN.zip](evidence/M3_FROZEN.zip) | 首次403红/绿及权限 | [2876568 bytes](evidence/M3_FROZEN.json) / `1b3d2a61a7d08d5bd3292e67deaa2354d8fd28e3f822a4eea8ba38e68118fcb8` |
| [C_FRONTEND_BASELINE.zip](evidence/C_FRONTEND_BASELINE.zip) | 固定C全量 | [1526080 bytes](evidence/C_FRONTEND_BASELINE.json) / `5b0e9340ef39015ff23926ea913a9981ef154e507cb15e8782fcb5589b8308b6` |
| [ENVIRONMENT_M2.zip](evidence/ENVIRONMENT_M2.zip) | 环境、安装、构建失败及修正 | [10340 bytes](evidence/ENVIRONMENT_M2.json) / `05ef32ac6d371e1d07744968dcd8b9615260d612d1c56d3e75022f40face6d78` |
| [LEGACY_FINAL.zip](evidence/LEGACY_FINAL.zip) | 旧PR完整Git库存，REST截断记录 | [293950 bytes](evidence/LEGACY_FINAL.json) / `d66d85a038a94ade8883349f3796536a5613fa37cb1b8b86776a5d62a475a66d` |
| [M4_DEVELOPMENT.zip](evidence/M4_DEVELOPMENT.zip) | 开发失败、正常/loss及首轮独立检出 | [7969413 bytes](evidence/M4_DEVELOPMENT.json) / `a1f6c464ffa37357b4468e301a0a7d400c5ae17c48b40a22ff76ecca69b070cd` |
| [M5_REGRESSION.zip](evidence/M5_REGRESSION.zip) | 全量对照、instrumentation、布局、API144与已知503 | [10821471 bytes](evidence/M5_REGRESSION.json) / `f80c55c0bfef6b2d0d480b41662864957dac0c5f0d24b3f70b6a37a9cecebf27` |
| [M6_FINAL.zip](evidence/M6_FINAL.zip) | 最终805/119/浏览器/独立5例/修复反向/已知503 | [5976370 bytes](evidence/M6_FINAL.json) / `15804546dfecd6f08e1591a56e9edb613dd413e8c422784bf45dd75028a6dace` |
