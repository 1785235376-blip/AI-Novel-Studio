# Navigation intent 真实运行验收

**File Edge 6/6、PostgreSQL Edge 6/6 PASS**，均为 1366×768、1440×900、1920×1080 三视口的两个独立节点；零 skip、零 flaky、零 retry。两组与冻结及最终工作源码的 **2305** 文件逐项一致，运行期间无漂移，canonical source map SHA256 为 `73cc97473c56824881b0274d19783152d161e7547680c0401009225058bf78da`。

| 原运行标签 | 结果 | 原命令、源码与日志 |
|---|---|---|
| `nav-intent-browser-file-final-r1` | 6 PASS，39.595s | [receipt](runner-receipts/nav-intent-browser-file-final-r1.json) / [log](runner-receipts/nav-intent-browser-file-final-r1.log) / [Playwright 原结果](nav-intent-browser-file-final-r1/results.json) |
| `nav-intent-browser-pg-final-r1` | 6 PASS，514.757s | [receipt](runner-receipts/nav-intent-browser-pg-final-r1.json) / [log](runner-receipts/nav-intent-browser-pg-final-r1.log) / [Playwright 原结果](nav-intent-browser-pg-final-r1/results.json) |

两个节点分别完成以下真实流程。核心节点在原凭证连接、项目选择及真实 bootstrap actor 200 后，保持当前有效 App parent overview GET 尚未发出，点击原“小说”同值标签并打开原 V2 分镜工作台；随后释放原请求，真实 200 后标签仍为 NOVEL，已保存分镜及 owner 保持不变。`page.reload()` 后同样在请求 held 期间点击 IMAGE→VIDEO→NOVEL，释放后保留最后意图。独立新 page 只使用前面真实连接 UI 自然保存的范围，不点击模块，真实 overview 后仍默认 IMAGE。各步骤保存原 DOM 的 `aria-selected`、创作文档文本和截图，没有先等 IMAGE 来绕过核心竞态。

跨 scope 节点通过原“返回项目列表”和原 Entry 卡片切换项目及分支。旧 `IndependentStudioSession.refresh` child GET 被真实 dispatch gate 暂停，scope 变化后由原 AbortController 取消，严格观察 `net::ERR_ABORTED`、无伪造旧 200；新 scope 的 parent GET 在明确 NOVEL 意图后真实返回 200，分支 breadcrumb、分镜文档和最后模块正确。旧、新 owner 均另用原授权及分支 header 发出独立 GET 200，原 `novel_id`、branch scope、project incarnation 与 overview 一致，完整文档仍为 v1。附件明确标记 `standalone_owner_readback` / `old_callback_delivery=false`。

延迟机制仅为 **`request_not_dispatched_until_release` → 原 `route.continue()`**；没有 URL、header、body 或 response 替换，不声称服务器在点击前收到请求。同一路径 gate 也保留额外 child、invalidation 和 hydration cancellation；只把选定且标记意图的 held 当前请求称为 scheduled App parent。bootstrap 本身未加定时 hold；浏览器点击发生在实际 actor 解析之后。before-actor 首次解析保留意图、parent ABA / cached callback、无会话 local saved hint 等因果边界由独立 [原 App mounted RED/GREEN](FRONTEND_NAVIGATION_IMPLEMENTATION_REPORT.md) 单列，不外推为本浏览器的 PG 旧回调交付证明。

全部后端都是普通 `uvicorn app.main:app`，原 LocalSessionBootstrap、session、identity、membership/roles、scope 与 stores；项目、分支和 CreativeDocument fixture 通过原 API 创建，结束后仅用原 DELETE 204 清理这些自有项目。生产 `PROMPT_ADOPTION_WRITE_ENABLED = False` 的原字节 SHA256 `a35c5a392fec0bc38446752e0c44cf79a3853edda7b5ce3fc40e2d58e78d8089` 未变，所有实际 Prompt adoption capability GET 为 `write_enabled=false`。没有进程内 True、生产开关、dev session、身份/React/store/DOM/localStorage 注入或响应 mock；新 launcher 显式 `MOCK_PROVIDER=false`、cloud/fallback=false。`model_execution=NOT_REQUESTED`、`model_counter=NOT_INSTRUMENTED`。[File launcher](nav-intent-browser-file-final-r1/launcher.json) / [PG launcher](nav-intent-browser-pg-final-r1/launcher.json) 保存这些运行事实。

PG 为原 wrapper 创建的独立 template0 空库 `v2_navigation_intent_browser_20261017_final_r1`，真实 PostgreSQL 16.15，OID **28822**；空对象检查通过，原 **20** migrations 全部 applied，原文件 SHA256 完整保留在 [PG runtime](runner-receipts/nav-intent-browser-pg-final-r1-postgres-runtime.json)。project、identity、authorization 和 CreativeDocument 使用原 PostgreSQL repositories；不可变素材 owner 保持原 File AssetLibraryService，无 PG blob 替换或 storage fallback。该 runtime 记录 `server_stop=stopped`、`cleanup_status=completed`。

独立 [final-runtime-cleanup.json](final-runtime-cleanup.json) 核对 `pg_ctl status` exit3、`postgres_running=false`、8138/5208/50678 均不可连接、`listeners=[]`、`owned_final_process_workers_remaining=[]`。原数据库、cluster、File/PG profile 保留。两次原 runner receipt/log 和 PG runtime 的 [五份逐字镜像](runner-receipts-mirror.json)、[12 份解码原附件及检查](final-browser-evidence-index.json)、[54 张原 PNG 索引](final-browser-screenshots.json) 均可复核；JSON 正文摘要已独立重算。完整当前源码 SHA256 与 File/PG/freeze 一致证明见 [security-runtime-source-binding.json](security-runtime-source-binding.json)。本子任务仅新增独立 launcher/config/spec 及证据文档，原两套 adoption harness/spec/config 未改，未提交或推送。
