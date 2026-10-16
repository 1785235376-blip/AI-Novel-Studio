# Creative 保存状态真实运行验收

**File Edge 9/9、PostgreSQL Edge 9/9 PASS**。每组均为 1366×768、1440×900、1920×1080 三视口的三个独立节点；零 skip、零 flaky、零 retry。File/PG 原 runner、统一 freeze 和结束后的工作区 **2310** 个运行源码逐项相同，canonical source map SHA256 为 `783255e32b4a193965a8162becfe7df605eb76e99ee41b729f4fe28517999f9f`，无运行期间源码漂移。

| 原运行标签 | 结果 / Playwright 耗时 | 原 runner / 浏览器结果 |
|---|---|---|
| `creative-save-browser-file-final-r1` | 9 PASS / 41.407s | [receipt](runner-receipts/creative-save-browser-file-final-r1.json) / [log](runner-receipts/creative-save-browser-file-final-r1.log) / [results](creative-save-browser-file-final-r1/results.json) |
| `creative-save-browser-pg-final-r1` | 9 PASS / 468.231s | [receipt](runner-receipts/creative-save-browser-pg-final-r1.json) / [log](runner-receipts/creative-save-browser-pg-final-r1.log) / [results](creative-save-browser-pg-final-r1/results.json) |

使用原凭证连接 UI、LocalSessionBootstrap、真实 author/session/membership/roles、项目及分支。文档经原 Creative 手动文档 API 创建，未调用模型；打开、编辑、保存、核对、历史和切换均走原产品 UI。初次持久 v1 的 Canvas 徽章与 footer 同为已保存；同值输入、还原 base 后仍干净，增加真实尾空格会变 dirty。实际修改中文、emoji、首尾空格和换行后，点击原“保存草稿”，暂停尚未发出的原 PUT，此时 footer 精确显示“当前分镜：保存中… · 基于 v1”，保存按钮与输入禁用，原阶段/全局导航拒绝切换。释放原请求后真实 HTTP200、`expected_version=1`→v2；完整原 owner GET、单条历史、title/action 与 receipt 一致。刷新再打开仍为已保存 v2，完整 owner 不变。另一剧本阶段的真实本地编辑单独显示“其他阶段未保存：剧本（仅本页内存）”，没有因当前分镜干净而被清除。

故障节点先让真实浏览器 offline，再点击保存，原 PUT 严格观察 `net::ERR_INTERNET_DISCONNECTED`，原 owner v1 未变，本地文本与“需核对保存结果”状态保留。恢复网络后明确核对并选择服务端 v1。独立 API 请求经原文档 owner 使用原 PUT 提交 v2，UI 缓存 clean v1 的原“建立制作计划”因此真实返回 **409 / EXPERIMENTAL_VERSION_CONFLICT**。随后暂停原核对 GET A，显示“核对服务端版本中…”且保存按钮禁用但仍名“保存草稿”；打开同阶段 clean B v1 后释放 A 的真实 HTTP200/v2，B 的 title/body/已保存 v1 保持不变，无 A 候选或“使用核对后的服务端版本”按钮。返回 A 后真实编辑并点击保存，原 PUT `expected_version=1` 同样精确 409，本地草稿保留，完整服务端 owner 仍等于外部 v2；再次核对后选择保留本地草稿。

历史节点让原 A/history GET 暂停，打开 B 并真实编辑后释放 A 的真实 HTTP200；B 仍 dirty、原内容保留，无 A 历史弹层。再暂停原 B/history GET，通过原确认 UI 明确放弃 B 本地草稿并离开，选择另一个真实项目及新分支 C；释放旧 history 的真实 HTTP200 后，C 原正文、已保存 v1、branch breadcrumb 保持正确，无旧历史弹层。旧、新原 owner 的 project/branch/incarnation 与 overview 一致，完整文档仍等于各自原 v1。SAVE 期间的拒绝导航与 history 期间允许的显式切换分开验证，没有用状态注入制造不可达并发。

延迟只采用 **`request_not_dispatched_until_release` → 原 `route.continue()`**。原 URL、headers、body、response 均未替换；不声称 hold 时服务器已经收到请求。每个视口保留 4 个 scheduled 原请求，File/PG 合计 **24** 个真实 HTTP200 的原始 body、SHA256、scope/token 摘要和 hold→用户操作→continue→response 时间。offline 用例严格属于**请求派发前失败**，不外推为写入成功后响应丢失。顶部可能保留 A 早先 derive409 产生的历史 notice：“派生操作需核对服务端结果，请勿重复建立。”；它不是迟到 GET 新增的候选，B 的当前保存状态及内容未污染。本轮未声称全页面没有旧操作语言。

全部 runtime 都是普通 `uvicorn app.main:app`，没有隔离 True 进程或生产环境闸门。原 `PROMPT_ADOPTION_WRITE_ENABLED = False` 字节 SHA256 为 `a35c5a392fec0bc38446752e0c44cf79a3853edda7b5ce3fc40e2d58e78d8089`，前后保持；真实 capability 均 `write_enabled=false`。新 launcher 显式 `MOCK_PROVIDER=false`、cloud/fallback=false，未启用 development sessions，没有响应 fabrication、身份/React/store/DOM/localStorage 注入。仅采用真实网络时序 gate 与 offline 故障。`model_execution=NOT_REQUESTED`，`model_counter=NOT_INSTRUMENTED`；没有以未计数冒称调用计数为零。[File launcher](creative-save-browser-file-final-r1/launcher.json) / [PG launcher](creative-save-browser-pg-final-r1/launcher.json) 保存 ordinary 后端与真实 health storage 事实。

PG 由原 wrapper 建立独立 template0 空库 `v2_creative_save_browser_20261017_final_r1`，PostgreSQL 16.15，OID **29705**；启动前无同名库，空对象检查通过，原 **20** 个 migrations 全 applied、逐个原 SHA256 保留且与现有文件相同。PG launcher 独立查询同一 database/OID，并要求 `/health.storage=postgres`；真实原 project/identity/authorization/CreativeDocument repositories 读写，非 File fallback。不可变 asset owner 仍为原 File AssetLibraryService，未替换成 PG blob。本次结束仅通过原 DELETE204 清理各自创建的项目，原数据库、cluster、运行 profile、历史轮证据都保留。[PG runtime](runner-receipts/creative-save-browser-pg-final-r1-postgres-runtime.json) 记录 `server_stop=stopped`、`cleanup_status=completed`。

原 runner receipt 记录的 HEAD：File `454ccd89499e3840d18622e8b6ec2669c17702c4`，PG `5c17750bd59c76ed4fb060716d61019151a3ef42`。报告封存时 HEAD `5c17750bd59c76ed4fb060716d61019151a3ef42`；HEAD 字段不替代实际运行字节来源，期间的 source/清单/harness 稳定切片提交没有改变 freeze 中运行字节，以上逐项 source map 一致证明见 [security-runtime-source-binding.json](security-runtime-source-binding.json)。三份新增 source SHA256：

| 独立新增 source | SHA256 |
|---|---|
| `scripts/run_v2_creative_save_state_browser.py` | `1f41bbf11eb8608ee4db4504cac5d06d281b321c82f6ecd1cadee6e5b550ba62` |
| `frontend/playwright.creative-save-live.config.ts` | `e2dde17606c8c966c8cec26e09b052b927f42b36859c4b809e97a09ce58afe40` |
| `frontend/tests/e2e/v2-creative-save-live.spec.ts` | `fecf742eb37493238f121a1b54dae581830dcd70cf02340804e6739af44e9254` |

原完整 child 命令及隔离 profile 见两个 runner receipt；外层分别使用原 `run_v2_checks.py --collaboration-runtime creative-save-browser-file-final-r1 -- …` 与原 `run_v2_postgres_checks.py --pg-bin … --data .runtime/retirement-pg/data --port 50678 --fresh-database --database v2_creative_save_browser_20261017_final_r1 --collaboration-runtime creative-save-browser-pg-final-r1 -- …`，Python 均为已固定的 `D:/PoemSeed/Cache/Tests/expansion-20261013-97da10e1/venv/Scripts/python.exe`。没有重试、重跑或放宽 timeout。

独立 [final-runtime-cleanup.json](final-runtime-cleanup.json) 核对 `pg_ctl status` exit3、`postgres_running=false`，8138/5208/50678 均不可连接，`listeners=[]`、`owned_final_process_workers_remaining=[]`。launcher 自有 API/Vite 全 stopped。两组原 runner receipt/log 加 PG runtime 共 [五份逐字镜像](runner-receipts-mirror.json)、[18 份原附件解码及 330 项独立检查](final-browser-evidence-index.json)、[78 张原 PNG 索引](final-browser-screenshots.json) 可复核。[原九份 nav/adoption harness/config/spec 逐字未改](original-harness-byte-preservation.json)；本 runtime owner 未提交或推送。
