# Creative 保存状态最终前端与视觉复核

**本轮指定范围 PASS。** 对照基线 `454ccd89499e3840d18622e8b6ec2669c17702c4`、最终实现源码 `5c17750bd59c76ed4fb060716d61019151a3ef42` 和冻结的 2310 路源码，未在已审状态发现新的阻塞保存/状态归属问题。canonical source map SHA256 为 `783255e32b4a193965a8162becfe7df605eb76e99ee41b729f4fe28517999f9f`。本结论不是全 V2 release，也不涵盖任意未操作表单或模型能力。

## 正式检查与保护范围

| 原始检查 | 实际终态 |
| --- | --- |
| 完整 frontend/src | 4269 passed、6 retained skips、0 failed；393 文件 |
| TypeScript + Vite build | PASS |
| 原 canonical 视觉与 shell geometry | 7 passed；3 个基线比较、4 个几何尺寸，未刷新 baseline |
| 原 token guard | PASS，52 文件 |
| 真实普通 File Edge | 9 passed，41.407 秒；零 skip/flaky/retry |
| 真实普通 PostgreSQL Edge | 9 passed，468.231 秒；零 skip/flaky/retry；新空库 OID 29705、原 20 migrations |

[frontend-verification.json](frontend-verification.json) 记录四组前端 receipt/log SHA。逐项独立核对四组 before/after 完整源码字典均等于冻结快照，日志 SHA 正确。File/PG 两份原外层 receipt 均 PASS、exit 0，其完整 2310 路源码字典也逐项匹配 freeze、日志 SHA 正确；并非仅凭 Playwright 进度日志宣布 PASS。原捕获 HEAD 分别为 File `454ccd8`、前端 `4571bda`、PG `5c17750`，保持原值，没有伪装为同一时刻启动。

[frontend-preservation-review.json](frontend-preservation-review.json) 独立复算原 1118 test/gate 字节及除授权 CreativeWorkspace 外的 60 adoption 源。原只读 `PromptAdoptionPanel`、`PromptAdoptionDisclosure`、`promptAdoptionClient`，以及 14 个 DS、AppShell、tokens、原视觉 config/spec/baseline 路径均与基线 Git blob raw bytes 相同。App 是授权变更 owner，仅加一行 commonStatus；Canvas 只加兼容 saving prop 与标签消费，不改变徽章、disabled/edit guards、业务字段和布局。六块原连接/导航/adoption guard 的 raw 保留由 [独立候选 R2](INDEPENDENT_CANDIDATE_REVIEW_R2.json) 记录。原 [750 源 / 752 artifact 保护](protection-post-collection.json) 无差异；保护字节不等于新的 V1 runtime 验收。

## 实际图像与 DOM

实际独立查看 **78 张 named 原 PNG**，没有裁切或生成替代图。每个后端均为 13 状态 × 1366×768、1440×900、1920×1080。精确路径、像素尺寸、raw SHA 见 [visual-image-review.json](visual-image-review.json)。原同图 attachment 的重复副本不再另算。

| 每视口图像组 | File | PostgreSQL |
| --- | --- | --- |
| v1 clean、真实 dirty、held SAVE、v2 回执、刷新重开 v2、当前 clean + 其他剧本 dirty | 6 张 × 3 | 6 张 × 3 |
| offline 保留、VERIFY held、A 迟到不能附到 B、真实 CAS409、核对后保留本地 | 5 张 × 3 | 5 张 × 3 |
| A history 晚到不影响 dirty B、旧 scope history 不影响新项目/分支 clean C | 2 张 × 3 | 2 张 × 3 |

初始和刷新重开的文档标题、侧栏版本、画布徽章、inspector 来源及底栏当前保存版本吻合。真实 SAVE held 时画布保留未保存标记，按钮明确“保存中…”且输入禁用，底栏显示当前分镜保存中、基于 v1；HTTP200 后变为已保存 v2。其他阶段的真实剧本草稿由底栏独立点名，当前 B 的 saved v1 不会把它清掉。

故障和冲突图中，原警告区与底栏保留“需核对保存结果 / 本地草稿保留”。VERIFY 是核对状态，保存按钮仍禁用但名为“保存草稿”，没有把 GET 称作保存。A 的迟到候选没有出现在 B，B 的标题、内容及 saved v1 保持当前归属。history 晚到后，dirty B 的状态仍在；显式放弃并切换项目/分支后，C 的新范围与 saved v1 正确。

原 header、context bar、sidebar、inspector、timeline 和 footer 在三尺寸中保持布局关系。1366/1440 使用既有内部滚动，部分画布 toolbar、动作或画面正文在截图视区外；不能宣称这些字段全部在每张图可见。标题栏和 breadcrumb 的长范围名使用既有省略，完整身份/正文由原 DOM 与 owner readback 支持，不从裁切像素推断。1920 原本地 AI 卡显示“尚未检测”，没有据此声称模型可用。

另外从两个原 `results.json` **逐字解码 18 份 evidence**，独立核对 78 个 DOM footer 快照及 24 个保留的 HTTP200 raw body SHA。结果见 [File DOM](visual-dom-review-file.json) 与 [PG DOM](visual-dom-review-pg.json)。这些记录保留精确中文、emoji、正文首尾空白和换行；未把像素未显示的正文当作已见。

## 运行因果与保留限制

真实运行使用原 `LocalSessionBootstrap`、连接/项目/分支 UI、Creative 文档 owner/CAS，以及 File 或 PostgreSQL repository。PG 是 `v2_creative_save_browser_20261017_final_r1` 新空库、实际 `/health.storage=postgres`；不可变 asset owner 仍为原 File AssetLibraryService，不声称所有 asset blob 改存 PG。测试通过原 owner API 预置手工 v1，随后原 UI 编辑和保存；外部 v2 也是原 owner 的独立 API 请求，**不是第二 actor 并发授权验收**。

延迟仅暂停原客户端请求 dispatch，再原样 `route.continue()`；没有替换 response、URL、headers、body、身份或 React/store/DOM/localStorage。held 期间没有声称服务端已经收到请求。offline 用例为 `context.setOffline(true)` 导致发送前真实 `ERR_INTERNET_DISCONNECTED`，原 owner 未变；**不外推为提交成功后丢回执**。跨 scope 的 UI 显式确认放弃本地草稿，与 SAVE 期间原 busy 拒绝导航分开验证。mounted 的源规范化、精确 undo 等边界仍按各自回归证据表述，不把模拟 API 提升为真实运行证据。

所有后端保持原生产 `PROMPT_ADOPTION_WRITE_ENABLED=False`，真实读取 capability 为 false，无进程内 True override。launcher 明确 `MOCK_PROVIDER=false`，未请求模型执行；准确边界为 `model_execution=NOT_REQUESTED`、`model_counter=NOT_INSTRUMENTED`，不是经过计数的零调用声明。本轮不重做 adoption 成功写入、不证明生成、渲染、GPU 或媒体质量。

**明确保留的旧提示：** `late-verify-a-v2-cannot-attach-candidate-to-clean-b-v1.png` 中，B 页上方仍可见 A 先前 derive409 的历史 notice：“派生操作需核对服务端结果，请勿重复建立。”它由原 derive 当时写入，原 openDocument 不清除该 notice；不是迟到 GET 新增的 B 候选。B 当前 footer/Canvas 已保存 v1、A candidate 拒绝成立，没有由此把 A 覆盖到 B 的按钮链。本轮不声称全页没有 A 历史语言或原 Creative 所有状态 UI 均无缺陷。

全部 RED、selector/fixture 诊断、原 raw receipts、日志和旧轮证据保留。真实浏览器 cleanup 的 [最终回执](final-runtime-cleanup.json) 为 `pg_ctl` exit 3、PG stopped、8138/5208/50678 closed、无 listeners/owned workers；原视觉 Vite PID 86928 自动结束、5174 无监听，见 [前端视觉 cleanup](frontend-visual-runtime-cleanup.json)。本 owner 在最终源码冻结后没有修改产品源/测试、重复运行检查、提交或推送。
