# AI Novel Studio Full Recovery Report

恢复日期：2026-10-07（Asia/Shanghai）。仓库：`1785235376-blip/AI-Novel-Studio`。本报告将原历史成果、当前新增实现、当前运行证据分开记录；尚未完成的最终回归和构建明确标记为 PENDING。

## 当前候选与历史关系

Latest Product Development Baseline 选择原 PR45 精确 head `665817243cad59eef0d4140f17c2ea644f46971e`，原 tree `ff53a8f3f9f1b704c4ac08784f3e2feaff49e4d8`。当前追加开发分支为 `work/full-recovery-product-candidate`，工作目录为 `D:\小说\AI-Novel-Studio-Latest-Product`。

新增候选已提交为 `3efa0393861c0dcddab7bd74e6d12e5ec483e7b1`，Git tree 为 `764aa6e3373aa39103919ac01faaebf15a9373ae`；[Draft PR46](https://github.com/1785235376-blip/AI-Novel-Studio/pull/46) 的 base 保留原 PR45 分支。当前严格清单绑定 1,523 个实际源输入，source fingerprint 为 `7bdd12fc2e2eed8acd0410f8dc059bdad01651ed1a02eab26f6a1c70dac1cb62`。原 PR45 SHA 仅代表历史基线，不代表新增实现。

恢复时 `origin/main` 为 `fed2404c8e30b44061b7139dced45b7f3301601c`，只有 138 个可达 commit。PR45 保留 312 个原 commit，比 main 多 174 个。PR36–44 的每个 head 均为 PR45 的真实 Git 祖先；PR37 虽然 GitHub base 为 main，其代码祖先仍包含 PR36；PR38–45 保留原逐级 stack。原 PR 的 base/head、Draft 与未合并状态没有重写。

全库恢复快照包括 322 个可达 commit、28 个真实 origin 分支、39 个 PR，以及 6 个也已被 PR45 包含的本地 branch head。没有 tag 或 GitHub Release。基线保留 2,439 个 tracked 文件、docs 下 618 个 blob，以及原测试、迁移、历史交付报告。

完整逐版本能力/代码/历史测试/是否纳入/理由见 [AI_NOVEL_STUDIO_FULL_VERSION_MAP.md](AI_NOVEL_STUDIO_FULL_VERSION_MAP.md)。GitHub 插件原元数据、每 PR commit/run、Git ref/commit/doc inventory 均保存在 `docs/delivery/full-recovery/`；本次没有只检查 main。

## PR45 之外的原成果

四个 origin 分支不属于 PR45 的祖先。其 8 个独特原 commit 已保留为完整 Git format patches，并且 Git 对象与原 remote ref 已恢复。没有将重复或被替代实现重新开发。

| 原分支/PR | 恢复内容 | 当前选择 |
|---|---|---|
| PR26 `feature/plugin-runtime-phase2b-windows-sandbox` | 5 个独特 commit；Windows AppContainer 原型，15 个文件、2,293 行新增，包含 463 行原测试 | 源码/历史完整归档；未接入最新生产运行链。最新 SDK 的 DENY_ALL/Owner 契约已有后续实现，原型尚无当前完整原生接入证据，不宣称该原型已产品化 |
| PR31 `feature/provider-runtime-v2-model-center-snapshot-bridge` | 1 个独特 commit、3 个文件、981 行新增 | 原实现已归档。选择已进入 main/PR45 的 PR33 authoritative snapshot bridge，架构与测试覆盖更完整 |
| `grok-phase1-acceptance` / PR1 `grok-phase1-feature-closure` | 1 个独特文档 commit 与 1 个独特实现 commit | 已归档。选择 PR2 重应用及其后续连续性/打包 fail-closed 实现；原 handoff 文档明确记录替代关系 |

两个 detached worktree 的历史 trial merge commit，与 GitHub PR33/PR34 真 merge 的 tree 完全相同，不能算作丢失的新实现。对应精确 tree 比较保存在 `local-merge-tree-equivalence.json`。所有原 patch 在 `historical-patches/`；没有删除或重置原工作树。

## Artifacts：索引与实际字节的范围

GitHub Actions 全量元数据索引恢复了 1,431 个 artifacts，快照时均未过期，合计 27,707,456,636 bytes。`actions-artifacts.json` 保留其 ID、所属 run、SHA256、大小和原下载 API URL。**这不等于已经下载全部 27.7 GB 历史字节**；除下述 PR45 最新相关归档外，其他 1,398 个历史 artifact 正在另一个隔离资产目录 `D:\小说\AI-Novel-Studio-Recovery-Assets\all-history` 恢复。最终下载、digest 与 CRC 数量尚待独立 receipt，不预先标记成功。

PR45 精确 head 相关 33 个最新归档已全部下载，合计 494,906,047 bytes，存放于 `D:\小说\AI-Novel-Studio-Recovery-Assets\pr45-6658172`。每个归档均与 GitHub digest 比对且通过 ZIP CRC 完整性检查；完整 receipt 为 `pr45-artifact-verification.json`，可复现脚本为 `recover_latest_artifacts.py`。

其中 exact-head unsigned Windows acceptance package 的 artifact ID 为 `11469458461`，归档 162,669,240 bytes，SHA256 为 `c0f8e9541a43599de6066161935ac131fb1ddc5257a314604b0e84c395ddf4ed`。PR merge package 也已单独校验。**这些是旧 PR45 包，不是当前新增代码的最终包。**

## 恢复的历史 CI 证据

PR45 旧正文仍写 PENDING，但本次读取原 GitHub API 和原始归档确认 7 个 run 均 attempt 1 完成。Cloud push 对应 exact head，Cloud PR 对应 merge `78929348e0ad7c232a039749d425e6293e4d6df9`，两者 tree 均为原 PR45 `ff53a8f...`，各 8 个 jobs 成功。

| 精确原源码的历史证据 | 重新读取原始 JUnit/strict proof 的结果 |
|---|---|
| File 全量 | 5,969 passed / 3,147 skipped，9,116 节点 |
| 真 PostgreSQL 16 两分片联合 | 5,945 passed / 3,171 skipped，9,116 节点联合覆盖 |
| 后端严格 proofs | 四份均 complete；Python 3.12.9；原 manifest SHA256 `87c017723b9987ee0fbf5349203ab14b31a0f63af29758a0d6f5f9499307e5d6` |
| 前端 | 1,455 passed / 8 原 optional skipped；96 个 browser journeys |
| Windows Host / 原生 smoke | 59 passed；11 个 smoke commands 全 exit 0 |
| Interop | 每个事件、每个 backend 345 passed / 68 skipped |
| 覆盖守卫 / 独立真实 TCP | 153 passed / 2 passed |

原 Cloud run：[push 37593331209](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593331209)、[PR 37593337560](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37593337560)。原始测量摘要见 `pr45-historical-ci-measurements.json`。

两份 A43 RED wrapper 成功的含义是重现旧基线缺陷；其 JUnit 各有一个 expected failure，不能算产品测试通过。R123 wrapper 同理。旧失败 checkpoint/正文原样保留；没有把后来修复重标为当时成功。上述历史 CI 也不证明当前新增源码、真实 AI 文学质量、交互 WebView2、签名/完整安装验收，或单体 PostgreSQL 交互等价。

## 当前新增实现与独立读代码审查

当前补全沿用原 Novel/Lore/Repository/Generation/Provider Owner。代码证据与详细运行矩阵另见主控的 `AI_NOVEL_STUDIO_COMPLETION_STATUS.md`、`AI_NOVEL_STUDIO_PRODUCT_ACCEPTANCE.md`、`AI_NOVEL_STUDIO_REMAINING_GAPS.md`；这些文件的最终结论优先于本报告中的 PENDING 项。

| 当前改动 | 真实代码接缝 |
|---|---|
| Project premise → WORLD / CHARACTERS / OUTLINE 提案、审核与 apply | `app/services/ai_planning_service.py`、`app/ai_planning_api.py`；原 Owner 持久化、严格模型实例校验、运行 version CAS、context/outline digest、partial receipts 与重试幂等 |
| Context / Memory | `app/context.py`、`app/services/context_service.py`、`app/services/agent_context_service.py`、`app/lore/memory_agent.py`；真实章节/世界/角色/连续性 context、source/version/hash、隐私投影与撤销校验、引用证据约束 |
| Reviewer / Verifier 与生成一致性 | `app/agents.py`、`app/agent_catalog.py`、`app/services/agent_job_service.py`、`app/review.py`、`app/jobs.py`；可执行角色、生成后的三类实际检查和当前版本记忆入队 |
| Provider / Local Runtime | `app/providers.py`、`app/model_center/discovery_bridge.py`；参数传递、调度前重授权、取消、stream usage、只保留真实报告 token usage、已安装本地运行时发现/注册/启用 |
| 产品入口 | `frontend/src/App.tsx`、`api.ts`、`novel/AIPlanningPanel.tsx`、`AgentTeamPanel.tsx`、`CreationWorkbenchPanel.tsx`；前提创建、无章节资料入口、world/character/outline apply、额外审核角色、写作目标 |
| 可复现启动 / 真 HTTP 验收 / API catalog | `scripts/run_latest_product.py`、`full_recovery_acceptance.py`、`refresh_product_api_catalog.py` |

独立 source review 跟踪了 prepare → context snapshot/hash → dispatch authorization → strict model validation → review → apply → 原 Owner 写入 → retry receipt，而非仅阅读文档。审查发现并修复了空 canonical relationship collection 覆盖旧连续性状态、project metadata privacy 未纳入 startup context hash、额外 Reviewer/Verifier 未显示于 UI 三项问题。

随后真实模型验收暴露了 OUTLINE 嵌套结构及 Memory instance/schema 指令歧义；提示词已窄修，严格 schema 不放松。Windows 实测也定位并窄修 File 锁读取、worker EOF 与自然退出竞态、Windows verifier 环境变量大小写等问题。contract generator 的 UTF-8/LF/POSIX 修改曾使 Windows focused 测试通过，但新 hosted CI 原 frozen V1 checker 拒绝其 source hash；最终选择恢复 PR45 的 generator/parity 两个原 Git blob，保留 frozen contract 与失败证据，明确该 canonical generator 的原 Linux 工具边界。原断言和原 checker 不变，对应 RED/GREEN 日志保存在 `verification/`。`jsonschema` 已加入基础运行依赖，避免仅 dev 环境可执行严格模型校验。

独立聚焦审查曾得到 55 passed / 7.21 秒，但属于最终 freeze 前的辅助验证，不能替代新源码完整回归。完整审查记录见 `INDEPENDENT_SOURCE_REVIEW.md`，核心/产品表面 Owner 的新证据分别见 `CORE_CHAIN_EVIDENCE.md` 与 `PRODUCT_SURFACE_EVIDENCE.md`。

## 原测试与守卫保护

原 PR45 coverage gzip 已逐字节归档为 `PR45_BASELINE_COVERAGE_MANIFEST.json.gz`。新 generator 两次 fresh、unfiltered collect 必须精确顺序/后端分类一致；原 9,116 节点必须完整 subset 且保持相对顺序；原 skip dictionaries 和外部真实 TCP gate 保持不变。完整 File/PG 仍运行原 `suite_coverage`、`coverage_reconcile`、`postgres_gate`，三守卫与 PR45 字节完全相同。

允许的机械 portability 例外仅包括 catalog source key `relative_to(ROOT).as_posix()` 和独立 selftest synthetic key `relative_to(tmp_path).as_posix()`。分别 18 / 20 个原 assertion AST 完全相同。原覆盖自测 152 passed / 1 Windows RED 原样保留；窄修后 153 passed / 7.41 秒，不删失败、不放宽 source/collection/JUnit 验证。

原产品测试/fixture 共 743 个文件，当前审计 737 个 Git blobs 相同；6 个明确例外为上述 catalog test、Windows archive fixture、provider routing fixture、原 visual spec 和两张 Windows gold。Windows archive fixture 只改实际 ZIP serialization，参数与全部断言保持原样；原始恶意 backslash bytes 与 `orig_filename` 可验证，生产检查更严格地拒绝 raw backslash。原 28 passed / 1 RED 保留，修复后原 29 tests 全通过。provider routing fixture 原来全局禁止 `__import__` 的 patch 直到 pytest teardown 才恢复，Python 3.12 原报告器创建 Path 时触发其禁止导入断言，导致完整回归 INTERNALERROR；现在仅用 monkeypatch.context 把原 guard、原 route call 和原两条断言包住，调用与断言期间保持原禁止语义，在报告器运行前恢复。全部原 assertion AST/参数/节点不变，生成器强制精确完整旧/新 body 匹配。原 visual spec 的 19 个 expectation lines 全部按原顺序保留，并增加几何断言至 36 个；原 unit source 未改。两张 gold 原始精确 PR45 文件、实际旧 hash 和新几何证据单独归档于 `visual-history-geometry/`，不宣称旧 gold 原样通过。详细 receipt 为 `original-test-preservation.json`；CI selftest 例外另计，不在上述 743 个 product files 中。

当前 frontend 独立最终结果为 1,498 passed / 8 原 skipped（比原增加 43 tests）；build/lint 成功，15 visual tests 成功。证据边界是本机独立运行，与上述历史原 CI 区分。

首轮完整后端为 TRANSITION_1：其运行期间真实验收又触发源码修复，旧 fingerprint 不证明最终 candidate。原 manifest/失败/源码漂移证据保留。首轮全局 PDF strict/font 环境也干扰了旧 CID 负例；最终 contract runner 恢复原 CI 的 `R2_TEST_FONT_FILE`，加 `PYTHONUTF8=1`，原 PDF 断言不改。真实独立产品 PDF 验收仍单独使用严格嵌入字体设置。Windows symlink 等实际权限/平台失败必须如实记录，不能新增 skip 消除。

最终 manifest 已完成：两次完整 collection 均为 **9,151 节点（原 9,116 + 新增 35）**，顺序/后端分类完全一致；原 skips 字典 SHA256 保持 `08393a038bb12bc6ea8a71f17e251842fbc69194b4830486893366d00162f5c3`。冻结原/新增 test sources、app、CI infrastructure、protocol generator/版本化 contracts、scripts、packaging locks、`pyproject.toml`、frontend src/tests/config/实际 `pnpm-lock.yaml`、API catalog 和 prompts；共 1,523 个输入，manifest SHA256 `7e03e639ce4cd99230bcfe18efcf7703f5fd939f4e83ace2308b4284b38d49f9`。全部输入工作树 bytes 与 Git index bytes 相同，clean Git archive 的相同输入也零 mismatch。receipt 分别为 `candidate-source-index-verification.json`、`candidate-clean-git-archive-proof.json`。

Windows 首轮 File 到达原 20 分钟容量上限，完整 collection 但没有完整 JUnit/receipt；全部失败与 incomplete status 保留，不算 final pass。最后完整 File/真实 PostgreSQL 16.15 两分片回归及 JUnit/receipt reconciliation 正在新建 WSL Linux ext4 环境执行：**PENDING**。实际源字节导出 2,467 个文件后全部 SHA 验证一致。首个 PostgreSQL 隔离工具闭包遗漏 `libLLVM-17.so.1`，原迁移 019 成功、020 触发 JIT 加载失败；原 RED 日志保留，恢复官方动态库后重新完整迁移，不关闭 JIT、不修改原 migrations。Windows/Python 3.11 和 WSL/Python 3.12.3 本机证据均不冒充 hosted GitHub/Linux/Python 3.12.9。新 PR46 的原 hosted Cloud/Interop workflows 也已启动，结果 **PENDING**。

## 官方构建材料与可运行入口

原 pinned CJK font 与完整 OFL 许可已从验证后的 exact-head PR45 包恢复，未复制系统字体，未改变 pin：

- `NotoSansSC-Regular.ttf`：10,595,932 bytes，SHA256 `eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461`。
- `OFL.txt`：4,388 bytes，SHA256 `1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9`。
- 路径：`.runtime/full-recovery/fonts/`，含原 manifest，原 `prepare_pdf_font.verify_font` 校验通过；receipt 为 `pdf-font-recovery.json`。

已从 [Microsoft 官方 .NET 8 下载信息](https://dotnet.microsoft.com/en-us/download/dotnet/8.0)及官方 release metadata 恢复固定 SDK 8.0.424，隔离目录 `.runtime/full-recovery/dotnet-sdk-8.0.424/`。完整 285,090,820-byte ZIP 的官方 SHA512 匹配、5,140 members CRC 验证、实际 `dotnet --version` 为 8.0.424；未修改系统 SDK，未降低 `global.json` pin。首次截断下载被严格拒绝，原 RED 与精确 206 byte-range 补尾 receipt 保留。依赖 restore 已完成；完整源/URL/hash 在 `dotnet-sdk-recovery.json`。

实际检查发现本机早期 acceptance 目录使用 3.12.10 且缺少 jsonschema，不能作为最新 approved base。已从 verified exact PR45 包恢复真正 3.12.9 Application，重新逐 SHA256 验证原 4,876 个 base 文件。沿原 wheel install/严格 hash/metadata/license/closure 规则保留 27 个原 wheel 记录，追加 pypdf 6.19.0、jsonschema 4.26.0、jsonschema-specifications 2025.9.1、attrs 26.1.0、referencing 0.37.0、rpds-py 2026.9.1。每个新 wheel 的 PyPI official hash、METADATA、完整许可均验证，33 个依赖闭包匹配 Windows/CPython 3.12.9；所有与 CI constraints 同名的 pins 相同，没有降级或浮动。

新 base `.runtime/full-recovery/windows-base-final` 的实际 isolated Python import/schema probe 通过，原 `verify_windows_base.py` 原生 smoke **PASS**：10 commands 全通过，33 个实际安装版本逐项匹配、PostgreSQL 16.15、pgcrypto、custom dump/restore、UTF-8 往返成功。receipt 为 `windows-extended-base-native-smoke.json`，另有原 exact-base/新 runtime dependency receipts。它证明新 runtime 材料可运行，仍不能替代新源码 Application 与交互用户验收。

新 Windows Application/package 已按真实候选 SHA `3efa039...` 完成 fresh build。内部 ZIP 为 169,258,663 bytes，SHA256 `fe6f491edf41e7b7681200eb6d50701635836f02e72d04b0897c309fbff537ff`；5,999 个 package inventory 文件、390 个 backend 文件与 15 个 frontend dist 文件全部 hash/size 正确，ZIP CRC 与逐 entry bytes 正确，全部 backend bytes 对应该候选实际 source。官方 SDK 8.0.424 / Python 3.12.9 / PostgreSQL 16.15；使用原 CI 相同的 `-SkipIExpress`，没有生成 setup EXE 或宣称公开签名发行。精确 receipt 为 `candidate-package-verification.json`。

实际 packaged native RuntimeLifecycle 在 fresh userdata 中启动真实 PostgreSQL、全部原 packaged migrations 和后端，health HTTP200/version0.7.0、前端 index 和实际 assets HTTP200/逐 bytes 等 staged、受保护 `/api/v1/agent-jobs` 匿名 HTTP401、原两个 native child 退出/owner STOPPED：**PASS**，见 `candidate-package-backend-probe.json`。没有模拟 host authentication/取出 bootstrap secret，没有 WebView2 交互；交互 DesktopHost 产品验证仍 **PARTIAL**。

原 post-package `verify_windows_base.py` 的 base inventory 曾报 Launcher hash 不符，根因是**本次恢复 helper 错误扩大 runtime base scope**，不是生产 packager 问题：原 PR45 4,876 条 base entries 仅包含 Runtime、PostgreSQL、Licenses 与 PREREQUISITES，无 Launcher；初次 helper 却把 3 个旧 Launcher 文件计入了 base 重算。该 RED、旧 base、第一次诊断均保留。已仅修恢复 helper，不修改生产 packager 或原 verifier：原 4,876 条完整 entry/hash 原样保留且新 wheel install 后再次验证，只加入 6 个官方 wheel 的 210 个声明 runtime 文件和单独 license index。新 scoped base 共 5,087 条 entries、无 product source payload；原 10-command native smoke 再次 **PASS**，见 `recovered-base-scope-diagnosis.json`、`windows-scoped-base-native-smoke.json`。曾准备的 production composition proposal 已撤回并标 UNADOPTED，不能误报为生产实现。最后新包将基于此正确 scoped base 再跑原 11-command verifier。

hosted frozen V1 checker 触发上述 generator/parity 恢复，因此 `3efa039...` 严格清单、Linux full runs 和 package 当前标记 **TRANSITION_2**，不能代替恢复后的最后候选身份与验证。`TRANSITION_2_COVERAGE_MANIFEST.json.gz` 及原 provenance 留存。最终新 SHA 下 package/manifest/回归结果仍 **PENDING**。`build_candidate_application.ps1` / `package_candidate_application.ps1` 每次要求正确 fingerprint，fresh 输出和绝对删除目标 containment，重新生成当前 frontend/backend/DesktopHost，不把旧 unsigned 包当作新包。

源码产品启动：使用已安装、授权用于本次用途的真实本地 GGUF 与 llama-server，运行 `scripts/run_latest_product.py --model-file <已有模型> --llama-executable <已有运行时> --license-reviewed`；默认后端 `127.0.0.1:8051`，模型 endpoint `127.0.0.1:8091`，独立 product-data，MOCK_PROVIDER=false、无云 fallback。前端设置 `V061_API_URL=http://127.0.0.1:8051` 后在 frontend 运行 dev/preview，当前浏览器入口 `http://127.0.0.1:5209`。本地 session material 存于 ignored runtime 目录，报告不披露 token。

用户给定“失忆者/废弃城市/曾毁灭城市”案例的完整项目 → 世界 → 角色 → 大纲 → 章节 → AI 修改 → 一致性 → 保存/历史恢复 → 导出真实性、耗时与结果，由 `scripts/full_recovery_acceptance.py` 写 raw receipts。主控已确认真实本地模型 API run `85a84385...` 完整十步、五个 Agent 及人工 Memory approve → Context **PASS**；当前浏览器身份入口已实际password验证/LOCAL_HOST绑定后启动Reviewer成功，完成解绑与真实下载；其证据见REAL_AUTHORIZED_PRODUCT_BROWSER.json。最终源码与交互产品结论由 `AI_NOVEL_STUDIO_PRODUCT_ACCEPTANCE.md` 给出，不把这一 API 成功自动当作全部 UI/安装/hosted gates 完成。

## 交付状态

| 状态 | 本报告负责范围 |
|---|---|
| DONE | 全分支/PR/commit/doc/report 盘点与版本地图；原历史关系/源码保留；非祖先独特源码恢复；全部 artifact 元数据与 33 个 latest exact-head 归档完整性；原历史 CI 重测量；原测试保护审计；官方 pinned font/SDK 恢复与 fresh build 准备 |
| PARTIAL | 新候选 PR46 已提交，严格最终 manifest 与真实 API/浏览器流程已有证据；完整两 backend 回归/独立 reconciliation、hosted CI 和 fresh Windows 包仍待最终实测；其他历史 artifact bytes 正在全量恢复 |
| BLOCKED | 不以文档/Mock/旧包替代最终证据。最终运行中实际平台/权限、模型格式、容量或 hosted gate 限制如存在，将在 remaining gaps 中逐项记录；当前不虚构全部完成 |
