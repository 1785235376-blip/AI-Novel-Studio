# V2 开发证据索引

本索引对应 [V2 开发交付报告](../../../AI_NOVEL_STUDIO_V2_FINAL_DEVELOPMENT_REPORT.md)，快照日期为 2026-10-09 08:49 UTC，99e3c63 五个托管 workflows 已全部终态。四模块代码检查点为 `d444901ab8e65a7296b559c890d758fc2e0dd10e`，[Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47)。首轮完整发布 commit 为 `fe4d2505ade9a161689313dea50555408ba4b511`，PR merge 为 `57503d7e354224398124211f8656fbbd0bb1ba40`；上一轮修复发布为 `99e3c636bc59f45f5faa4b7af84b80981f1ec2e5`，tree `b0595aaccb9c42437f3d61aaf209a61de94d584d`，PR merge `42d8355c00eb545d40ab503c4429315bb7eef74e` 具有同一 tree；历史本地源码验证绑定候选 tree `0b0971ad6574aafe7c2f72135f7317e5b0e43715`，最终发布 SHA 与其托管 CI 在 PR 47 维护，不能把最终包的新增步骤回填为代码检查点已执行的成果。

## 阅读规则

- `status:PASS` / `exit_code:0` 只表示该命令的结果，必须同时看 command、后端 profile、head、`sources_changed_during_check` 和原日志/JUnit。
- `source_sha256_before` / `source_sha256` 绑定执行时的实际工作树文件，不能只用 HEAD 代替精确源码身份。HEAD 相同不保证工作树相同。
- 不将不同 profile 的相同用例、基础设施自测、collect-only、HTTP 和浏览器成功数合并为“产品全部通过”。
- `INVENTORY_ONLY` / `tests_executed:false` 不是测试执行；PENDING、BLOCKED、失败与历史过渡记录保持原义。
- 历史 **39 PARTIAL + F00 INTEGRATED**、独立审查 **BLOCKED** 不变。

## 首轮 06:56 UTC 历史源码快照收据

| ID | 证据 | 已验证的结果及适用范围 |
| --- | --- | --- |
| E01 | [File JSON](cloud-final-backend-file.json) · [log](cloud-final-backend-file.log) · [JUnit](cloud-final-backend-file.xml) | 05:08:21–05:09:38 UTC；352 passed / 135 skipped；134 opposite-PG、1 native-Windows；13 个指定测试文件，非整库；运行期源稳定，06:56 UTC 当时 1,592 个 source 输入仍匹配 |
| E02 | [PostgreSQL JSON](cloud-final-backend-postgres.json) · [log](cloud-final-backend-postgres.log) · [JUnit](cloud-final-backend-postgres.xml) | 05:08:23–05:10:25 UTC；144 passed / 134 opposite-File skips；7 个指定测试文件，非整库；运行期源稳定，06:56 UTC 当时 source map 匹配 |
| E03 | [PG live runtime](cloud-final-backend-postgres-postgres-runtime.json) · [初始化](cloud-postgres-initialization.json) · [实际 SQL](cloud-postgres-live-sql.log) · [表数量及运行环境](cloud-postgres-runtime.json) | PostgreSQL 17.11，真实 loopback 数据库；20 migrations，51 表的现场 SQL；不能混称托管 PostgreSQL 16 |
| E04 | [首轮最终完整前端 JSON](cloud-frontend-complete-final.json) · [log](cloud-frontend-complete-final.log) · [JUnit](cloud-frontend-complete-final.xml) | 05:51:34–05:52:29 UTC；1,554 passed / 8 既有 opt-in skips，233 文件 passed / 2 skipped；运行期源稳定，06:56 UTC 当时 1,592 个 source 输入仍匹配 |
| E05 | [基础设施 JSON](cloud-v2-infrastructure-publication.json) · [log](cloud-v2-infrastructure-publication.log) | 05:09:08–05:09:13 UTC；170 passed；V2 manifest/runner 与原 suite/reconcile 自测；不计入产品总数；运行期及06:56 UTC 当时 source map 均稳定 |
| E06 | [依赖闭合 JSON](cloud-windows-dependency-closure.json) · [log](cloud-windows-dependency-closure.log) | 05:48:55–05:49:00 UTC；原 tests/test_r2_windows_base_inputs.py 29 passed；仅云端依赖/脚本测试，非 Windows 安装或 GPU |
| E07 | [最终 build/lint JSON](cloud-final-build-lint.json) · [log](cloud-final-build-lint.log) · [UI 说明](creative-workbench-ui.md) | git diff --check、tsc --noEmit、production build、token guard 42 files，exit 0；该收据没有 before-source snapshot，源稳定性另据 E04；保留 ExperimentalWorkbench 647.28 kB / App 775.04 kB chunk warning；非浏览器验收 |
| E08 | [完整 File 最终 JSON](cloud-backend-full-file-final.json) · [log](cloud-backend-full-file-final.log) · [JUnit](cloud-backend-full-file-final.xml.gz) | 05:49:10–06:03:47 UTC；6,174 passed / 3,253 skipped / 0 failed，4 warnings；9,427 nodes，867.55 秒；运行期源稳定，06:56 UTC 当时 1,592 个 source inputs 零差异；普通完整 pytest，未加载严格 CI gate |
| E09 | [较早完整前端 JSON](cloud-final-frontend.json) · [log](cloud-final-frontend.log) | 同样 1,554 passed / 8 skips，运行期稳定；后续两个 runner/selftest 基础设施输入变动，旧整份 source map 已非 06:56 UTC 快照零差异；以 E04 为 06:56 UTC 快照证据 |
| E16 | [File 固定字体 JSON](cloud-file-pinned-font-final.json) · [log](cloud-file-pinned-font-final.log) · [JUnit](cloud-file-pinned-font-final.xml) | 06:09:21–06:09:28 UTC；原 PDF/CJK comic 两项测试 2 passed，5.26 秒；1,592 source inputs 运行期及 06:56 UTC 当时均匹配；不改原完整 File 总数 |
| E17 | [File TCP JSON](cloud-file-tcp-final.json) · [log](cloud-file-tcp-final.log) · [JUnit](cloud-file-tcp-final.xml) | 06:08:57–06:09:28 UTC；原两进程 real-loopback TCP gate 2 passed，28.35 秒；1,592 source inputs 运行期及 06:56 UTC 当时均匹配；独立证据 |
| E18 | [完整 PG 最终 JSON](cloud-full-postgres-final.json) · [严格 reconciliation](cloud-full-postgres-coverage.json) · [原始两 shard 证据归档](cloud-full-postgres-evidence.tar.gz) | 6,151 passed / 3,276 精确获准 skips / 0 failed，9,427 节点；两 shards exit 0，原 postgres=2 reconciliation exit 0，PG 已停止；1,654 source inputs 稳定且 06:56 UTC 当时零差异；本地 dot 云端，不是 GitHub 或 monolithic PG 顺序等价 |
| E20 | [最终完整后端 JSON](cloud-full-backend-final.json) · [file=1/postgres=2 严格证明](cloud-full-backend-coverage.json) · [完整原始证据归档](cloud-full-backend-evidence.tar.gz) | PASS；File 6,176 passed / 3,251 精确获准 skips，PG 6,151 passed / 3,276 精确获准 skips，各 9,427 nodes；原独立 TCP 2/2 passed 单列；原 reconciler exit 0；1,654 source hashes 稳定，无 collection/validation errors；本地 dot 云端 |

E01/E02 的核心验证文件为 `tests/test_v2_creative_foundation.py`、`tests/test_v2_creative_workflows.py`、`tests/test_v2_task_router.py`，覆盖原子 File/PG、CAS、跨 scope、隐私/来源失效、撤权回滚、重复采用、历史恢复、模型 admission/预算/输出审阅、取消、重启不重放及正文禁止写入。完整命令与附加回归名单以 JSON 为准。

E04 的 8 个 skips 来自 `frontend/tests/localInteropRealHost.test.ts` 两项和 `frontend/src/experimental/ExperimentalWorkbench.http.test.tsx` 六项；它们是需单独启动真实 HTTP/Interop 环境的既有 opt-in cases。不能用缺省单元运行替代它们的独立执行结果。

E16 字体来自未修改的 `scripts/prepare_pdf_font.py`，保持原 OFL 和固定来源校验。实际 `R2_TEST_FONT_FILE` 为 `.runtime/full-postgres-20261009T060653/fonts/NotoSansSC-Regular.ttf`，派生字体 SHA256：`eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461`。E16/E17 四项补验单列，未新增 skip allowlist，也不改写 E08 的原始统计。

E08 的 3,253 skips 分为：2,988 opposite-PG、253 未配置真实/专用 PG 端点、7 Windows/native/凭据库、2 pinned font、2 独立 real-loopback subprocess gate、1 历史 Phase 1 migration 条件。这里只核对 JUnit 原因，不宣称严格 CI 已认可全部 skips。完整 File 命令没有加载 `postgres_gate` / `suite_coverage`；9,427 个普通 pytest 终态与 inventory 数量一致。后继 E20 已在全新隔离工作区独立完成本地严格 collection/shard/phase/JUnit/source/skip reconciliation；这不回填改变 E08 的原运行属性，也不代表新 SHA 的 GitHub CI 结果。

最终本地严格状态（2026-10-09 06:55 UTC）：**PASS**。原顺序 File profile 于 06:37:51–06:52:30 UTC 完成；两条原确定性 PG shards 分别于 06:10:59–06:35:35、06:11:09–06:33:32 UTC 运行，实际端口 55441 / 55442。三个执行均完整收集 9,427 节点，File 单进程执行原顺序，PG 按原确定性分配分别执行 4,702 / 4,725 节点，无重无漏。原 `coverage_reconcile.py --expected-shards file=1 postgres=2` 于 06:52:50 UTC 形成完整证明；所有 collection/validation errors 为空，独立 `sync-tcp.xml` 的 2 个原测试也获核对，不计入 profile 总数。

本地候选 Git tree 为 `0b0971ad6574aafe7c2f72135f7317e5b0e43715`，run identity 为 `local-cloud-pg-20261009T060653`；这是 HEAD 加精确本地候选内容的验证身份，没有以此创建新 commit。Python 3.12.14 / PostgreSQL 17.11，使用原未改动 gates、精确 additive manifest、固定字体和匹配的 pg_dump/pg_restore。各工作区 1,654 source hashes 运行前后一致且与 06:56 UTC 当时工作树零差异，主工作树源码与 manifest 未变，先前 PG 证据归档也未改写，PG 服务已停止。

该证明覆盖原严格 File 原顺序进程、PG 两分片及独立 TCP gate；不承诺单进程 PostgreSQL 全序交互等价，也不是 GitHub、native/GPU、真实模型或浏览器验收。此前普通 File 6,174、选定 PG 144、前端 1,554，以及独立字体 2 / TCP 2 passed 均保留各自证据，不合并为唯一用例总数。

## 真实 HTTP File 与浏览器边界

| ID | 证据 | 结论 |
| --- | --- | --- |
| E10 | [combined log](cloud-v2-creative-browser-run.log) · [JSON](cloud-v2-creative-browser/results.json) · [JUnit](cloud-v2-creative-browser/junit.xml) | 总体 4 failed / 3 passed；3 项真实 HTTP/File 生命周期、scope/cancel/stale-source、default-off 成功；4 项浏览器 case 在 page 创建前被 Chromium socket EPERM 阻断 |
| E11 | [进程重开 File](cloud-v2-creative-browser/file-reopen.json) | uvicorn 停止后独立 Python 进程重开 SCREENPLAY/DIRECTOR/STORYBOARD/PRODUCTION；Production v3，历史 v1/v2/v3；正文未变且仍 v1；无浏览器、无推理 |
| E12 | [早期 HTTP log](cloud-v2-creative-http-run.log) | 保留早期 2 passed / 1 failed；非法来源状态码 409 预期与 422 实际不符；不覆盖为成功。后继 E10 才有 3 HTTP 通过 |
| E19 | [headless-shell 结果](cloud-headless-shell-dependency/result.json) · [下载计划](cloud-headless-shell-dependency/download-plan.txt) · [安装 log](cloud-headless-shell-dependency/install.log) | 授权项目内官方 Playwright 1.62.1 / shell revision 1234、151.0.7922.34 下载依赖失败；官方 CDN 返回不可用 ZIP，内建重试后 exit 1，无 binary；没有新 UI/geometry 执行或截图，也未改安全设置/重试完整 Chromium；4 个浏览器测试/config source hashes 在 06:56 UTC 当时匹配 |

首轮云端本地尝试没有可批准的新增 V2 浏览器成功截图/几何/视觉基线；后续 fe4d250 托管运行实际产生了失败截图，见 E21。`frontend/playwright.v2-live.config.ts`、live spec 与新增 V2 live/fixture workflow step 已纳入最终发布包；fe4d250 的真实失败已保留，修复后的后继精确 SHA 仍须重新取得托管终态。

E18 归档 SHA256：`4479cfed0317c837edbf7daa69b1fecb1e391eb97153a30e9ece890bb8314f0b`。内含两份 `local-run.json`、实时 PostgreSQL/工具版本、原 command、完整 inventory/assignment/outcomes、JUnit、events、font manifest、原 V2 manifest 和 reconciliation log。已复核两个 JUnit 合计 6,151 passed / 3,276 skipped，assignment 无重无漏覆盖 9,427 节点；原始 PG 归档保持不变，后继完整 File/PG 合并证据另见 E20。

E20 完整归档 SHA256：`de7420ca3e1bb9e43c8037b66a4d18e2835ced73a8acf37182a2c74534494907`。已读取三个原始 `coverage.json` / `local-run.json`、JUnit 与 TCP XML，核对 File 6,176/3,251、PG 3,095/1,607 + 3,056/1,669、TCP 2 passed；三份 1,654 源摘要前后及 06:56 UTC 当时均相等。旧 PG 归档仍为原 `4479cf...4f0b`，无覆写。

## 清单 目录与源码身份

| ID | 证据 | 结论 |
| --- | --- | --- |
| E13 | [collection](cloud-v2-collection.json) | 9,427 nodes = 原 9,151 + 新 276；原节点相对顺序、历史 skip maps 保留；collect-only，未执行测试 |
| E14 | [manifest 校验](cloud-v2-manifest-verification.json) · [说明](../../../.github/ci/COVERAGE_V2.md) | `INVENTORY_AND_SOURCE_INTEGRITY_ONLY`；1,654 个 source inputs；原 Interop 413 nodes；未跟踪 fixture runtime 状态不冒充 source |
| E15 | [catalog 命令](cloud-final-api-catalog.json) · [log](cloud-final-api-catalog.log) · [staged tree 回执](catalog-0c1ccb2d4438.json) | 对 tree `0c1ccb2d4438060d59fddef9c0ba46b64023f47b` 生成本地 API catalog；只证明生成与 digest，不证明 GitHub 上传或发布 |

关键 SHA256：

- 原冻结 manifest：`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`
- 首轮 fe4 V2 manifest：`0e7752f63562b80dffeb6c058c0802c9f5df6b763a07c2a7a2d9f2d4d9419000`
- 首轮 fe4 `API_CATALOG.json`：`4753e96e246f45f4f7a69a651ecdeeef19934c88558a29d1e0662a21311c357e`

原 `coverage_manifest.json.gz`、`postgres_gate.py`、`suite_coverage.py`、`coverage_reconcile.py` 均与 e21075d 基线字节一致。E13 另有旧 launcher 测试单一 `-B` 迁移的 commit、原/新 digest 和严格说明，不是新增 skip 或历史审批。

## GitHub 托管证据

历史只读核对时间：2026-10-09 05:50 UTC。下列均为 d444901 对应的 PR runs；最终发布包新增的 workflow 改动不能回填到这些历史结果。最终 SHA 的托管状态单独由 PR 47 维护。

- [Cloud CI 37886802281](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802281)：failure。File [113678824993](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802281/job/113678824993) 和 PG shards 的 collection/execution step 被原 frozen source digest gate 拒绝；后端汇总 failure。File 的独立 TCP step success 不改变全量门禁失败。
- [Local Interop 37886802200](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802200)：failure。File [113678507808](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802200/job/113678507808) 与 PG contract step 同样记录 frozen digest mismatch，后续 reconciliation skipped。
- [Shared R123 37886802353](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802353)：success。实际为原 c6f2126 RED 的三个历史重现流程按设计完成，不能解释成 V2 全绿。
- [Frontend job 113678824914](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802281/job/113678824914)：success。仅覆盖当时实际列出的单元/类型/构建/token/geometry/既有 business browser steps，未含新增 V2 live/fixture step。
- [Windows Host job 113678824909](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802281/job/113678824909) 与 [fresh package job 113678824695](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802281/job/113678824695)：success。原 Host/native/packaging 合约、未签名内部包与 embedded Python/PG UTF-8 smoke；未包含本地新增 V2 Windows fixture step，没有用户 GPU/真实模型/安装交互验收。
- [Windows pipe reference job 113678507965](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37886802200/job/113678507965)：success，明确 `MOCK_ONLY`。

用户明确批准后，同一 `API_CATALOG.json` blob 重试已成功，GitHub blob SHA 为 `143950b8067307b05fd8ef59a643fd27654ebdb2`；其余目录 blobs 也已上传。这只记录上传准备已成功，最终分支发布 SHA 和对应 CI 以 PR 47 为准；E15 是目录生成回执，不是最终分支发布回执。

两份大型完整 File JUnit 以 `.xml.gz` 无损压缩发布，原始 `.xml` 在本地原样保留。索引 E08 和下方失败初跑的 JUnit 链接指向压缩版本；解压 bytes 已逐字节与原始 raw JUnit 核对一致。原/gzip SHA256、大小与验证结果见 [归档映射](cloud-full-file-junit-archives.json)。压缩不改变测试结果，也不删除失败或 skip。

## fe4d250 实际托管结果与有限修复

以下属于后续源码/托管执行，不能与 E01–E20 的 06:56 UTC 原候选身份混写；旧完整证明不因后续修复而失效，也不自动覆盖修复后的源。

| ID | 证据 | 结论与边界 |
| --- | --- | --- |
| E21 | [fe4 浏览器失败索引](ci-fe4d250-browser-failure/index.json) · [原始归档](ci-fe4d250-browser-failure/original-failure-evidence.tar.gz) | fe4d250 / PR merge 57503d7；真实 live 4 passed / 3 failed，mocked workbench 1 passed / 4 failed；原 frontend 达 25 分钟上限取消，后段 export/surface/branch 未到达；归档 SHA256 `c72b9ee3efb5f71879f069d92d65d20b0a75cb11f1a74deedae267c2acf15269` 已复核 |
| E22 | [入口修复完整前端 JSON](creative-entry-fix-full-frontend.json) · [log](creative-entry-fix-full-frontend.log) · [build](creative-entry-fix-build.log) · [lint](creative-entry-fix-lint.log) | 1,556 passed / 8 existing skips，234 files passed / 2 skipped；TypeScript/build/token guard 42 files 通过；保留 chunk warning；Vitest JSON 不是整工作树 source-before/source-after 证明 |
| E23 | [浏览器 CI 基础设施 JSON](cloud-v2-browser-ci-infrastructure.json) · [log](cloud-v2-browser-ci-infrastructure.log) · [JUnit](cloud-v2-browser-ci-infrastructure.xml) | 07:36:24–07:36:28 UTC，173 passed，运行期 source 稳定；原 frontend job byte-digest 回归、独立 25 分钟 fail-closed V2 job、bash 语法；不是新 hosted browser PASS |
| E24 | [重复同 ID HTTP/File 记录](creative-live-repeat/README.md) · [修复前身份](creative-live-repeat/before-fix/source-identity.json) · [第一版修复身份](creative-live-repeat/after-fix/source-identity.json) | 三项原 HTTP case 同服务器/同 title-derived IDs 各重复两次，修复前4 passed/2 failed，第一版后端修复后6 passed/0 failed；201/204/空库/文档数/正文/版本断言不弱化；身份记录区分事后捕获与重建的旧 Git blobs；不是浏览器或 PG 结果，最终 marker 的独立稳定后继见 E25 |
| E25 | [最终稳定 HTTP/File 身份](creative-live-repeat/final-stable/source-identity.json) · [log](creative-live-repeat/final-stable/run.log) · [JUnit](creative-live-repeat/final-stable/receipts/junit.xml) · [结果 JSON](creative-live-repeat/final-stable/receipts/results.json) | 最终 bounded marker 源码，三项原 scenario 各重复两次，6 passed / 0 failed / 0 skipped，14.8秒；config/spec/三个后端模块前后hash一致；HTTP/File only，不是浏览器/PG/推理；修复前及第一版记录不覆盖 |
| E26 | [代际隔离说明](creative-project-lifecycle.md) · [最终 File JSON](creative-lifecycle-final-file.json) · [log](creative-lifecycle-final-file.log) | 131 passed / 97 opposite-profile skips，72.24秒，运行期源稳定；UUID owner/marker、同标题重建、CAS/auth/branch/race、保留旧JSON值；最终真实 PG 后继见 E27 |
| E27 | [最终真实 PG JSON](creative-lifecycle-final-postgres.json) · [log](creative-lifecycle-final-postgres.log) · [实时 SQL 运行环境](creative-lifecycle-final-postgres-postgres-runtime.json) | 98 passed / 103 skipped，129.44秒；真实PG17.11、127.0.0.1:55432；运行期源稳定，服务正常关闭；E26/E27 的1,596源摘要于07:47UTC与当时工作树零差异；teardown精确验证自有owner/scope零残留 |
| E28 | [最终隔离基础设施 JSON](cloud-v2-closeout-infrastructure.json) · [log](cloud-v2-closeout-infrastructure.log) · [JUnit](cloud-v2-closeout-infrastructure.xml) · [catalog 生成](catalog-4ad3d21221dc.json) | 174 passed，运行期source稳定；staged catalog隔离于自有.profile并清除继承凭据/DB端点；2,043 operations，相对fe4新增0/删除0，fingerprint97fbdb…184888b；修复前host-home EROFS不是安全策略绕过 |
| E29 | [最终完整前端 JSON](cloud-v2-closeout-frontend.json) · [log](cloud-v2-closeout-frontend.log) · [JUnit](cloud-v2-closeout-frontend.xml) · [最终 build JSON](cloud-v2-closeout-build.json) · [log](cloud-v2-closeout-build.log) | 1,556 passed/8 existing skips，234 files passed/2 skipped，128.33秒；tsc/build/token/diff-check均PASS，保留chunk warnings；两份运行期源码稳定，source map各1,596输入于07:51核对一致 |
| E30 | [收尾 collection](cloud-v2-closeout-collection.json) · [先行 review](cloud-v2-closeout-collection-review.json) | INVENTORY_ONLY，tests_executed=false；9,449 nodes / 1,658 source inputs；全部旧fe4 9,427按原序保留，仅22新增lifecycle cases；原skip/external-gate maps不变，非完整执行通过；新manifest SHA256 `5b116d31c45b2fc9bc1434303be9b9e93beaef824f622d913b86b84be96e9e34` |
| E31 | [fe4 精确托管终态](ci-fe4d250-terminal.json) · [23 jobs 无损logs/metadata归档](ci-fe4d250-terminal-evidence.tar.gz) | 原fe4 5 runs全部终态；3 success/2 cancelled，23jobs中21 success/2 cancelled；4/4PG shards与4/4aggregate gates成功；两个Cloud整体由frontend cap取消，后段NOT_REACHED；archive SHA256 `7844b93342f580d508da1c04aace79eab3b9842902d4ac1a140e1ef8e3a71b19`及内部33份checksums均已核对；只证明fe4，不证明后继修复 |
| E32 | [原 catalog 测试 JSON](cloud-v2-closeout-catalog.json) · [log](cloud-v2-closeout-catalog.log) · [JUnit](cloud-v2-closeout-catalog.xml) · [最终 source gate](cloud-v2-closeout-source-gate.json) | 原3项catalog测试3 passed/3.25秒，运行期源稳定；最终1,658 hashes/0 errors，9,449 inventory、原9,427顺序/skip/external gates不变；369 app Python hashes与catalog相符，OpenAPI gzip较fe4不变；source gate不是完整执行证明 |

截至 07:50:26 UTC，fe4d250 全部五个原 workflows 已终态：两 Cloud workflow 整体 CANCELLED（frontend 25分钟cap），两 Interop / Shared R123 SUCCESS；23 jobs中21 SUCCESS、2 frontend CANCELLED。四条PG shards和四个独立aggregate gates全成功；push和PR各自File6,176/3,251精确skips、PG6,151/3,276精确skips，每profile9,427节点，独立TCP各2 passed，不相加为唯一总数。Windows有限范围仍为59原Host/packaging +3V2 fixtures，以及真实embedded Python3.12.9/PG16.15/UTF-8/dump-restore smoke，不是GPU/用户验收。精确run/job/artifact与NOT_REACHED由E31保存；这些结果不覆盖修复后的source。

已确认入口遮挡并完成受控位置修复，原 FeatureLauncher 不改。live fixture 只清理成功创建的自有 synthetic IDs，检查 case 间空库，保留业务断言/原生手势/原 timeout；重复同标题 HTTP 测试确认了删除重建后的 Creative 资产复活缺陷，代际隔离设计与最终 File131/97 已确认，最终真实 PG98/103 已确认，不以随机标题掩盖。原 frontend 整 job byte hash 为 `fbfe69540e4a9d5a48a43d1bc3d44c06e2909271c78c4fb932a5b0a687c04798`，恢复后以回归约束；新 V2 job 不占用原 job 25 分钟预算。最终修复 SHA 与托管结果仍由 PR47 维护。

catalog 首次失败仅在执行工具 traceback 中观察到 `OSError errno 30`、host-home `/home/agent/.local/share/AI-Novel-Studio`；没有独立落盘原始收据/log。E28 指向后续成功生成与隔离自测，不声称保留了不存在的首次原始文件。

代际隔离恢复边界：旧/unbound V2 rows 和 history 的 JSON 值保留；只读不改 scope bytes，新写入会重写 scope envelope。没有可靠 incarnation 的旧资产 fail closed，不自动迁移/rebind；删除 File marker 产生新身份，损坏 marker 报错。恢复需另行审阅 owner 证据，未新增恢复工具。

## 99e3c63 实际失败与第二轮限定修复

E21–E32 保留其原执行与源码身份；本次五个前端 source/test 文件已变化，不把旧整份 source map 宣称为当前工作树等价。旧本地完整后端与 fe4 的严格证明继续有效于各自原身份。

| ID | 证据 | 结论与边界 |
| --- | --- | --- |
| E33 | [99 浏览器原始证据说明](ci-99e3c63-browser-failure/README.md) · [source/artifact 身份](ci-99e3c63-browser-failure/source-identity.json) · [live JUnit](ci-99e3c63-browser-failure/receipts/live/junit.xml) · [mocked JUnit](ci-99e3c63-browser-failure/receipts/v2-creative-workbench.xml) | PR artifact 11602858790 / run 37902141902 / job 113726946074，真实 checkout 为 merge 42d8355c；live 5 passed / 2 failed（HTTP3 passed、UI2 passed/2 failed），mocked 5/5（含三尺寸 geometry）；28 份保留文件 hash 已核对，含 12 张未编辑 PNG；保存阶段截图不证明后续恢复/重开通过 |
| E34 | [readiness/叠层修复 JSON](creative-recovery-99e3c63-20261009.json) · [log](creative-recovery-99e3c63-20261009.log) | 08:11:15–08:13:35 UTC；TypeScript/Vite/token 42 files PASS，完整前端 1,567 passed / 8 existing skips，235 files passed / 2 skipped，Vitest 118.31 秒；1,597 source inputs 前后稳定，08:20 UTC 当时逐项零差异；保留 647.28/775.35 kB chunk warnings；不证明新 SHA browser PASS |
| E35 | [基础设施 JSON](creative-recovery-infrastructure.json) · [log](creative-recovery-infrastructure.log) · [JUnit](creative-recovery-infrastructure.xml) | 08:17:08–08:17:13 UTC；174 passed，1,597 source inputs 前后稳定，08:20 UTC 当时逐项零差异；独立于产品 suite，不计入总数 |
| E36 | [readiness 修复 source gate](creative-recovery-source-gate.json) | 08:20 UTC UI-only 检查点；SOURCE_AND_INVENTORY_VERIFIED_NOT_EXECUTION；1,659 hashes / 0 errors，9,449 后端节点与 99 完全同序，skip/external gates 不变；仅五个前端 source/test 文件变化；manifest SHA256 0093adc97d202dbb4bae5328226485c06d01daa2d58363e1d02f933ce7d82c1e；369 个 app Python、Catalog/OpenAPI bytes/fingerprint 不变 |

E33 原始 ZIP 为 24,361,394 bytes，SHA256 `94f0714b851b341f58f87d897c44b5f9f60295b128224d35cffd6ad3252b937f`。ZIP 与两份 raw trace ZIP 仅保存在 runtime，提交的 source-identity 保留其来源和 digest；仓库中的保留文件是实际原日志、JUnit/JSON、revision 和未编辑截图，不能声称整个 raw ZIP/trace 已随此索引交付。

[Production 重开失败](ci-99e3c63-browser-failure/screenshots/failure-production-reopen.png) 左栏仍为已保存 v3 / 2 场景，中央未命名/空标题/0 段；[Screenplay 重开失败](ci-99e3c63-browser-failure/screenshots/failure-screenplay-reopen.png) 左栏为已保存 v1 / 2 场景、中央为空。截图证明选取/载入不一致，源码及延迟读取回归进一步定位为初始 list 未完成时创建空草稿。已修复为当前 scope 的 list 成功后才初始化缺失阶段，保留显式新建、dirty/blocked 草稿、撤权与迟到 callback 防护。时间线只用局部 isolation 和既有 z-index token 修复 sticky header 叠层；不改共享壳体。新增 10 项 recovery 单元 + 1 项 CSS contract 已包含于 E34；另加 3 项 mocked header hit-test 后下次 suite 为 8 项，尚无其新 SHA 托管终态。原 live spec/业务断言/手势/timeout 未改变。

截至 08:20 UTC，99 的两次原 frontend、两 Interop、Shared R123、四 Windows jobs 均 SUCCESS。原 frontend 各自 1,556/8；旧 browser groups geometry9、real client2、Interop12、business2、R3 7、R4 63、export1、surface9、branch1 全部实际通过，fe4 的 NOT_REACHED 不再误写为 99 的缺失。Windows 仍仅 59 原 tests + 3 V2 fixtures、embedded Python3.12.9/PG16.15/UTF-8/dump-restore smoke。

99 的五个 workflows 已于 08:46 UTC 全部终态：3 SUCCESS / 2 FAILURE，25 jobs 为20 SUCCESS / 4 FAILURE / 1 CANCELLED。两个 Cloud 均 FAILURE；两个 failure 来自 V2 browser，另两个来自 PR backend precondition gates；唯一 cancelled 是 PR File/TCP。四条 PG shards 全部成功，各事件 shard-0 为3,100 passed/1,612精确skips/4,737deselected，shard-1为3,059/1,678/4,712deselected，合计6,159 passed/3,290精确skips，完整9,449节点。

Push File job113726928343 SUCCESS，完整6,190 passed/3,259精确skips/9,449节点 + 独立TCP2 passed；两个push严格aggregate gates实际SUCCESS，File和PG各9,449节点。PR File job113726946131的完整pytest同样6,190/3,259，但随后TCP step因原20分钟cap取消、没有终态。PR gates113742205784/113742205835因EXECUTION_RESULT=cancelled在reconciliation前失败，没有PR coverage artifacts。PR完整pytest和PG分片成功不能替代缺失的同事件TCP/aggregate；不以push结果回填。原两项 TCP 测试的有界编排修复已完成，独立收据见 E37–E38；E36 仅为其之前的 UI-only 检查点，不延伸为后续整份源码证明。

## 原 TCP 独立预算修复

| ID | 证据 | 结论与边界 |
| --- | --- | --- |
| E37 | [修复设计与历史 cap](ci-tcp-budget-20261009/README.md) · [精确证据规则](../../../.github/ci/TCP_EVIDENCE.md) · [最终基础设施 JSON](ci-tcp-budget-infrastructure-fixed.json) · [log](ci-tcp-budget-infrastructure-fixed.log) · [JUnit](ci-tcp-budget-infrastructure-fixed.xml) | 08:34:55–08:35:01 UTC；276 passed / 5.82 秒 = 原174 + 新102，1,599 source inputs 前后稳定，08:37 当时逐项相符；合成反例覆盖身份/依赖/源漂移、伪造/重复/中断/非success/非法JUnit/覆盖拒绝；不冒充产品或 hosted 执行 |
| E38 | [collection review](ci-tcp-closeout-collection-review.json) · [最终 collection](ci-tcp-closeout-collection.json) · [最终 source gate](ci-tcp-closeout-source-gate.json) · [受保护文件身份](ci-tcp-budget-20261009/source-identities.json) | 08:37:12 UTC；1,661 hashes / 0 errors；最终manifest df72d854d942b0759b9d02229c33523bb1dd11470dd95c5c12a405a73c9a66ab，9,449节点与99完全同序，skip/external gates精确不变；原TCP/live spec/冻结gate/prepare及369appPython/catalog不变；inventory/source only |
| E39 | [真实 loopback TCP JSON](ci-tcp-budget-real-loopback.json) · [log](ci-tcp-budget-real-loopback.log) · [JUnit](ci-tcp-budget-real-loopback.xml) · [原 validator / manifest 校验](ci-tcp-budget-20261009/real-loopback-validation.json) | 08:37:32–08:38:03 UTC；原两项分进程 TCP 2 passed / 0 skip/error/failure，28.04秒；runner 1,599 source inputs 前后稳定，另行最终 manifest 1,661项匹配；原 reconciler 接受精确 node JUnit；本地产品实际执行，不是 hosted producer/aggregate，独立于 profile 总数 |

原 PR File 完整 pytest 为 1,080.84 秒、workflow step 1,089 秒，随后 TCP 仅32秒便达原20分钟 cap。新增 `backend-tcp` job 独立10分钟，File原顺序单进程20分钟与两PG55分钟不变；原174基础设施留在File，新102项放入TCP job。两个原 Backend aggregates 要求全matrix与TCP `needs.result` 均精确success。producer检查checkout/tree/event/repo/run/attempt/manifest/dependency/source/实际安装包与原两节点JUnit；join只建立全新逐字节副本布局，关联独立TCP XML供原未改动reconciler验证，并保留下载原件/副本hash。不存在把旧取消receipt修好或跨run拼接，也不把独立TCP加入File唯一总数。实际新hosted producer/join尚待后继SHA；实际本地原两项 real TCP 已单独通过，见 E39；此结果不替代新 hosted producer 身份或 same-run join。

保留 [第一次 owned-profile infrastructure JSON](ci-tcp-budget-infrastructure.json) · [log](ci-tcp-budget-infrastructure.log) · [JUnit](ci-tcp-budget-infrastructure.xml)：275 passed / 1 failed / 5.94秒，合成fixture继承外围root导致JUnit classname带前缀，被原validator拒绝。仅新增fixture补最小pytest.ini；原产品和生产runner/validator不改。E37是修正合成fixture后的独立结果，不覆盖该失败。预算修复README的原artifact ZIP大小/digest是GitHub metadata，并非此修复检查下载ZIP后的独立hash证明。


## 99e3c63 精确托管终态

| ID | 证据 | 结论与边界 |
| --- | --- | --- |
| E40 | [99 全部托管终态 JSON](ci-99e3c63-terminal.json) · [25 份 job logs / metadata / strict receipts 归档](ci-99e3c63-terminal-evidence.tar.gz) | 08:46:21 UTC 观测，5 workflows 全终态（3 success/2 failure），25 jobs（20 success/4 failure/1 cancelled）；4/4 PG shards 成功，push两个strict gates成功；PR gates因File/TCP cancelled在reconciliation前失败；新修复不在此证据覆盖范围 |

E40 JSON SHA256 `adfb6cb9caaf4199647035dcbad8edf72fd066cc9ce62a95cf283d6faf5205fa`；归档 542,748 bytes，SHA256 `731df56f39bf7741fa60e3785081a8836031a630362a385dd5b153d40a2b3fa1`。已核对归档内部50份member hashes、25个job身份/终态、两个push strict reconciliation JSON及PR precondition失败log。原远端完整artifact binaries以ID/digest引用，不声称全部已下载并纳入此有界归档。

实际push证明为File6,190/3,259、PG6,159/3,290，每profile9,449节点，独立TCP2；PR同样完成File pytest与两个PG shards，但没有TCP终态/coverage artifact，两个aggregate正确FAIL。六个当前File/PG execution jobs的实际package receipts逐字节一致：38rows/709bytes，SHA256 `74cf563c7bc414940db61b6c9e84d500b0507b0b559590452b040b57a5738b12`。依赖相同不升级PR取消结果；历史fe4依赖对照分开保留，未跨run拼接测试/JUnit。


## 必须保留的失败与过渡材料

- [完整 File collection 失败](cloud-backend-full-file.json) · [log](cloud-backend-full-file.log)：exit 2，runner 测试迁移期间 ImportError，源变动 true。
- [完整 File 初跑](cloud-backend-full-file-stable.json) · [log](cloud-backend-full-file-stable.log) · [JUnit](cloud-backend-full-file-stable.xml.gz)：6,173 passed / 3,253 skipped / 1 failed，exit 1，源变动 true。名称含 stable 也不能当最终稳定收据。失败是 `.venv` 缺 pip；后续 ensurepip 25.0.1、E06 依赖闭合与 E08 独立完整重跑通过，没有覆写旧失败、环境问题或源变动记录。
- `phase1-foundation-red*`、`cloud-task-router*`、`creative-workflows-*`、`cloud-v2-authority`、早期 infrastructure/frontend receipts 均保留其原始状态。引用前须检查 commit、源变动与实际 command，优先使用 E01–E06 的相应稳定后继。
- 普通完整 File、完整前端、独立严格 PG 及最终 File/PG/TCP 合并严格终态已收入 E08/E04/E18/E20；fe4d250 真实终态、失败与有限修复见 E21–E32；99 浏览器实际失败和本次局部修复见 E33–E36，TCP 编排与实际本地执行见 E37–E39，99 完整托管终态见 E40；后继修复 SHA 的完整托管结果继续在 PR 47 记录。用户 Windows/GPU/真实模型/安装验收仍 NOT_RUN / LOCAL_REQUIRED。

发布后的精确 SHA 托管 CI 状态在已核验的 [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) 中维护；本索引是带时间戳的本地证据快照，不预写远端通过结论。本次任务完成后停止功能扩展，不进行本机 Windows 验收、合并或 Release。

生命周期首次 PG 失败 [receipt](creative-lifecycle-postgres.json) / [log](creative-lifecycle-postgres.log)：92 passed / 3 failed / 94 skipped / 4 errors，原因是新增回归 fixture 捕获旧 nid 的 teardown 问题。仅新 fixture 修正；已归档 [已知 synthetic 遗留快照](creative-lifecycle-failed-fixture-snapshot.json)，再做 [精确键清理](creative-lifecycle-fixture-cleanup.json) 并验证零残留。旧失败不重标成功。
