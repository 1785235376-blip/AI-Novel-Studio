# V2 开发证据索引

本索引对应 [V2 开发交付报告](../../../AI_NOVEL_STUDIO_V2_FINAL_DEVELOPMENT_REPORT.md)，快照日期为 2026-10-09 06:56 UTC。四模块代码检查点为 `d444901ab8e65a7296b559c890d758fc2e0dd10e`，[Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47)。最终发布包包含 CI/目录配套修改、检查、报告及本目录证据；源码验证绑定候选 tree `0b0971ad6574aafe7c2f72135f7317e5b0e43715`，最终发布 SHA 与其托管 CI 在 PR 47 维护，不能把最终包的新增步骤回填为代码检查点已执行的成果。

## 阅读规则

- `status:PASS` / `exit_code:0` 只表示该命令的结果，必须同时看 command、后端 profile、head、`sources_changed_during_check` 和原日志/JUnit。
- `source_sha256_before` / `source_sha256` 绑定执行时的实际工作树文件，不能只用 HEAD 代替精确源码身份。HEAD 相同不保证工作树相同。
- 不将不同 profile 的相同用例、基础设施自测、collect-only、HTTP 和浏览器成功数合并为“产品全部通过”。
- `INVENTORY_ONLY` / `tests_executed:false` 不是测试执行；PENDING、BLOCKED、失败与历史过渡记录保持原义。
- 历史 **39 PARTIAL + F00 INTEGRATED**、独立审查 **BLOCKED** 不变。

## 当前主要执行收据

| ID | 证据 | 已验证的结果及适用范围 |
| --- | --- | --- |
| E01 | [File JSON](cloud-final-backend-file.json) · [log](cloud-final-backend-file.log) · [JUnit](cloud-final-backend-file.xml) | 05:08:21–05:09:38 UTC；352 passed / 135 skipped；134 opposite-PG、1 native-Windows；13 个指定测试文件，非整库；运行期源稳定，当前 1,592 个 source 输入仍匹配 |
| E02 | [PostgreSQL JSON](cloud-final-backend-postgres.json) · [log](cloud-final-backend-postgres.log) · [JUnit](cloud-final-backend-postgres.xml) | 05:08:23–05:10:25 UTC；144 passed / 134 opposite-File skips；7 个指定测试文件，非整库；运行期源稳定，当前 source map 匹配 |
| E03 | [PG live runtime](cloud-final-backend-postgres-postgres-runtime.json) · [初始化](cloud-postgres-initialization.json) · [实际 SQL](cloud-postgres-live-sql.log) · [表数量及运行环境](cloud-postgres-runtime.json) | PostgreSQL 17.11，真实 loopback 数据库；20 migrations，51 表的现场 SQL；不能混称托管 PostgreSQL 16 |
| E04 | [最新完整前端 JSON](cloud-frontend-complete-final.json) · [log](cloud-frontend-complete-final.log) · [JUnit](cloud-frontend-complete-final.xml) | 05:51:34–05:52:29 UTC；1,554 passed / 8 既有 opt-in skips，233 文件 passed / 2 skipped；运行期源稳定，当前 1,592 个 source 输入仍匹配 |
| E05 | [基础设施 JSON](cloud-v2-infrastructure-publication.json) · [log](cloud-v2-infrastructure-publication.log) | 05:09:08–05:09:13 UTC；170 passed；V2 manifest/runner 与原 suite/reconcile 自测；不计入产品总数；运行期及当前 source map 均稳定 |
| E06 | [依赖闭合 JSON](cloud-windows-dependency-closure.json) · [log](cloud-windows-dependency-closure.log) | 05:48:55–05:49:00 UTC；原 tests/test_r2_windows_base_inputs.py 29 passed；仅云端依赖/脚本测试，非 Windows 安装或 GPU |
| E07 | [最终 build/lint JSON](cloud-final-build-lint.json) · [log](cloud-final-build-lint.log) · [UI 说明](creative-workbench-ui.md) | git diff --check、tsc --noEmit、production build、token guard 42 files，exit 0；该收据没有 before-source snapshot，源稳定性另据 E04；保留 ExperimentalWorkbench 647.28 kB / App 775.04 kB chunk warning；非浏览器验收 |
| E08 | [完整 File 最终 JSON](cloud-backend-full-file-final.json) · [log](cloud-backend-full-file-final.log) · [JUnit](cloud-backend-full-file-final.xml.gz) | 05:49:10–06:03:47 UTC；6,174 passed / 3,253 skipped / 0 failed，4 warnings；9,427 nodes，867.55 秒；运行期源稳定，当前 1,592 个 source inputs 零差异；普通完整 pytest，未加载严格 CI gate |
| E09 | [较早完整前端 JSON](cloud-final-frontend.json) · [log](cloud-final-frontend.log) | 同样 1,554 passed / 8 skips，运行期稳定；后续两个 runner/selftest 基础设施输入变动，旧整份 source map 已非当前零差异；以 E04 最新重跑为当前证据 |
| E16 | [File 固定字体 JSON](cloud-file-pinned-font-final.json) · [log](cloud-file-pinned-font-final.log) · [JUnit](cloud-file-pinned-font-final.xml) | 06:09:21–06:09:28 UTC；原 PDF/CJK comic 两项测试 2 passed，5.26 秒；1,592 source inputs 运行期及当前均匹配；不改原完整 File 总数 |
| E17 | [File TCP JSON](cloud-file-tcp-final.json) · [log](cloud-file-tcp-final.log) · [JUnit](cloud-file-tcp-final.xml) | 06:08:57–06:09:28 UTC；原两进程 real-loopback TCP gate 2 passed，28.35 秒；1,592 source inputs 运行期及当前均匹配；独立证据 |
| E18 | [完整 PG 最终 JSON](cloud-full-postgres-final.json) · [严格 reconciliation](cloud-full-postgres-coverage.json) · [原始两 shard 证据归档](cloud-full-postgres-evidence.tar.gz) | 6,151 passed / 3,276 精确获准 skips / 0 failed，9,427 节点；两 shards exit 0，原 postgres=2 reconciliation exit 0，PG 已停止；1,654 source inputs 稳定且当前零差异；本地 dot 云端，不是 GitHub 或 monolithic PG 顺序等价 |
| E20 | [最终完整后端 JSON](cloud-full-backend-final.json) · [file=1/postgres=2 严格证明](cloud-full-backend-coverage.json) · [完整原始证据归档](cloud-full-backend-evidence.tar.gz) | PASS；File 6,176 passed / 3,251 精确获准 skips，PG 6,151 passed / 3,276 精确获准 skips，各 9,427 nodes；原独立 TCP 2/2 passed 单列；原 reconciler exit 0；1,654 source hashes 稳定，无 collection/validation errors；本地 dot 云端 |

E01/E02 的核心验证文件为 `tests/test_v2_creative_foundation.py`、`tests/test_v2_creative_workflows.py`、`tests/test_v2_task_router.py`，覆盖原子 File/PG、CAS、跨 scope、隐私/来源失效、撤权回滚、重复采用、历史恢复、模型 admission/预算/输出审阅、取消、重启不重放及正文禁止写入。完整命令与附加回归名单以 JSON 为准。

E04 的 8 个 skips 来自 `frontend/tests/localInteropRealHost.test.ts` 两项和 `frontend/src/experimental/ExperimentalWorkbench.http.test.tsx` 六项；它们是需单独启动真实 HTTP/Interop 环境的既有 opt-in cases。不能用缺省单元运行替代它们的独立执行结果。

E16 字体来自未修改的 `scripts/prepare_pdf_font.py`，保持原 OFL 和固定来源校验。实际 `R2_TEST_FONT_FILE` 为 `.runtime/full-postgres-20261009T060653/fonts/NotoSansSC-Regular.ttf`，派生字体 SHA256：`eeb06b8a64fd04a2744d95579db1571b51027cda61ed78c62e4b730791525461`。E16/E17 四项补验单列，未新增 skip allowlist，也不改写 E08 的原始统计。

E08 的 3,253 skips 分为：2,988 opposite-PG、253 未配置真实/专用 PG 端点、7 Windows/native/凭据库、2 pinned font、2 独立 real-loopback subprocess gate、1 历史 Phase 1 migration 条件。这里只核对 JUnit 原因，不宣称严格 CI 已认可全部 skips。完整 File 命令没有加载 `postgres_gate` / `suite_coverage`；9,427 个普通 pytest 终态与 inventory 数量一致。后继 E20 已在全新隔离工作区独立完成本地严格 collection/shard/phase/JUnit/source/skip reconciliation；这不回填改变 E08 的原运行属性，也不代表新 SHA 的 GitHub CI 结果。

最终本地严格状态（2026-10-09 06:55 UTC）：**PASS**。原顺序 File profile 于 06:37:51–06:52:30 UTC 完成；两条原确定性 PG shards 分别于 06:10:59–06:35:35、06:11:09–06:33:32 UTC 运行，实际端口 55441 / 55442。三个执行均完整收集 9,427 节点，File 单进程执行原顺序，PG 按原确定性分配分别执行 4,702 / 4,725 节点，无重无漏。原 `coverage_reconcile.py --expected-shards file=1 postgres=2` 于 06:52:50 UTC 形成完整证明；所有 collection/validation errors 为空，独立 `sync-tcp.xml` 的 2 个原测试也获核对，不计入 profile 总数。

本地候选 Git tree 为 `0b0971ad6574aafe7c2f72135f7317e5b0e43715`，run identity 为 `local-cloud-pg-20261009T060653`；这是 HEAD 加精确本地候选内容的验证身份，没有以此创建新 commit。Python 3.12.14 / PostgreSQL 17.11，使用原未改动 gates、精确 additive manifest、固定字体和匹配的 pg_dump/pg_restore。各工作区 1,654 source hashes 运行前后一致且与当前工作树零差异，主工作树源码与 manifest 未变，先前 PG 证据归档也未改写，PG 服务已停止。

该证明覆盖原严格 File 原顺序进程、PG 两分片及独立 TCP gate；不承诺单进程 PostgreSQL 全序交互等价，也不是 GitHub、native/GPU、真实模型或浏览器验收。此前普通 File 6,174、选定 PG 144、前端 1,554，以及独立字体 2 / TCP 2 passed 均保留各自证据，不合并为唯一用例总数。

## 真实 HTTP File 与浏览器边界

| ID | 证据 | 结论 |
| --- | --- | --- |
| E10 | [combined log](cloud-v2-creative-browser-run.log) · [JSON](cloud-v2-creative-browser/results.json) · [JUnit](cloud-v2-creative-browser/junit.xml) | 总体 4 failed / 3 passed；3 项真实 HTTP/File 生命周期、scope/cancel/stale-source、default-off 成功；4 项浏览器 case 在 page 创建前被 Chromium socket EPERM 阻断 |
| E11 | [进程重开 File](cloud-v2-creative-browser/file-reopen.json) | uvicorn 停止后独立 Python 进程重开 SCREENPLAY/DIRECTOR/STORYBOARD/PRODUCTION；Production v3，历史 v1/v2/v3；正文未变且仍 v1；无浏览器、无推理 |
| E12 | [早期 HTTP log](cloud-v2-creative-http-run.log) | 保留早期 2 passed / 1 failed；非法来源状态码 409 预期与 422 实际不符；不覆盖为成功。后继 E10 才有 3 HTTP 通过 |
| E19 | [headless-shell 结果](cloud-headless-shell-dependency/result.json) · [下载计划](cloud-headless-shell-dependency/download-plan.txt) · [安装 log](cloud-headless-shell-dependency/install.log) | 授权项目内官方 Playwright 1.62.1 / shell revision 1234、151.0.7922.34 下载依赖失败；官方 CDN 返回不可用 ZIP，内建重试后 exit 1，无 binary；没有新 UI/geometry 执行或截图，也未改安全设置/重试完整 Chromium；4 个浏览器测试/config source hashes 当前匹配 |

当前没有可批准的新增 V2 浏览器截图/几何/视觉基线。`frontend/playwright.v2-live.config.ts`、live spec 与新增 V2 live/fixture workflow step 已纳入最终发布包；本地快照尚未取得最终发布 SHA 下这些步骤的托管终态。

E18 归档 SHA256：`4479cfed0317c837edbf7daa69b1fecb1e391eb97153a30e9ece890bb8314f0b`。内含两份 `local-run.json`、实时 PostgreSQL/工具版本、原 command、完整 inventory/assignment/outcomes、JUnit、events、font manifest、原 V2 manifest 和 reconciliation log。已复核两个 JUnit 合计 6,151 passed / 3,276 skipped，assignment 无重无漏覆盖 9,427 节点；原始 PG 归档保持不变，后继完整 File/PG 合并证据另见 E20。

E20 完整归档 SHA256：`de7420ca3e1bb9e43c8037b66a4d18e2835ced73a8acf37182a2c74534494907`。已读取三个原始 `coverage.json` / `local-run.json`、JUnit 与 TCP XML，核对 File 6,176/3,251、PG 3,095/1,607 + 3,056/1,669、TCP 2 passed；三份 1,654 源摘要前后及当前均相等。旧 PG 归档仍为原 `4479cf...4f0b`，无覆写。

## 清单 目录与源码身份

| ID | 证据 | 结论 |
| --- | --- | --- |
| E13 | [collection](cloud-v2-collection.json) | 9,427 nodes = 原 9,151 + 新 276；原节点相对顺序、历史 skip maps 保留；collect-only，未执行测试 |
| E14 | [manifest 校验](cloud-v2-manifest-verification.json) · [说明](../../../.github/ci/COVERAGE_V2.md) | `INVENTORY_AND_SOURCE_INTEGRITY_ONLY`；1,654 个 source inputs；原 Interop 413 nodes；未跟踪 fixture runtime 状态不冒充 source |
| E15 | [catalog 命令](cloud-final-api-catalog.json) · [log](cloud-final-api-catalog.log) · [staged tree 回执](catalog-0c1ccb2d4438.json) | 对 tree `0c1ccb2d4438060d59fddef9c0ba46b64023f47b` 生成本地 API catalog；只证明生成与 digest，不证明 GitHub 上传或发布 |

关键 SHA256：

- 原冻结 manifest：`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`
- 本地 V2 manifest：`0e7752f63562b80dffeb6c058c0802c9f5df6b763a07c2a7a2d9f2d4d9419000`
- 本地 `API_CATALOG.json`：`4753e96e246f45f4f7a69a651ecdeeef19934c88558a29d1e0662a21311c357e`

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

## 必须保留的失败与过渡材料

- [完整 File collection 失败](cloud-backend-full-file.json) · [log](cloud-backend-full-file.log)：exit 2，runner 测试迁移期间 ImportError，源变动 true。
- [完整 File 初跑](cloud-backend-full-file-stable.json) · [log](cloud-backend-full-file-stable.log) · [JUnit](cloud-backend-full-file-stable.xml.gz)：6,173 passed / 3,253 skipped / 1 failed，exit 1，源变动 true。名称含 stable 也不能当最终稳定收据。失败是 `.venv` 缺 pip；后续 ensurepip 25.0.1、E06 依赖闭合与 E08 独立完整重跑通过，没有覆写旧失败、环境问题或源变动记录。
- `phase1-foundation-red*`、`cloud-task-router*`、`creative-workflows-*`、`cloud-v2-authority`、早期 infrastructure/frontend receipts 均保留其原始状态。引用前须检查 commit、源变动与实际 command，优先使用 E01–E06 的相应稳定后继。
- 普通完整 File、完整前端、独立严格 PG 及最终 File/PG/TCP 合并严格终态已收入 E08/E04/E18/E20；本地快照截点尚未取得最终发布 SHA 的托管 CI 与新增 V2 browser 终态，后续在 PR 47 记录。用户 Windows/GPU/真实模型/安装验收仍 NOT_RUN / LOCAL_REQUIRED。

发布后的精确 SHA 托管 CI 状态在已核验的 [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) 中维护；本索引是带时间戳的本地证据快照，不预写远端通过结论。本次任务完成后停止功能扩展，不进行本机 Windows 验收、合并或 Release。
