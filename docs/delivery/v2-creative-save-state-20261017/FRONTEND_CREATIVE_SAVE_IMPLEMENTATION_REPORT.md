# Creative 文档保存状态实现记录

本轮基线为 `454ccd89499e3840d18622e8b6ec2669c17702c4`，最终实现源码 HEAD 为 `5c17750bd59c76ed4fb060716d61019151a3ef42`。**本轮指定 Creative 保存状态范围通过实现、冻结源前端检查及真实 File / PostgreSQL 浏览器验收。** 下述准备阶段 RED/GREEN 记录完整保留，冻结后的正式终态列于文末；不将组件模拟响应称为真实后端。本轮未请求模型执行，生产 Prompt adoption 保持关闭。

## 复现与原因

原画布徽章已经区分当前 `draft.dirty`、已保存版本和新草稿。旧截图中的“无未保存创作草稿”不能按“未保存”子串认定为 dirty。确认存在的问题是底栏混入小说正文的保存/正在打开章节状态，并用全部阶段的草稿数描述当前文档，缺少归属；另外，原 `change` 每次输入都设 `dirty=true`，真实编辑后精确恢复、等值数字编辑或可选字段恢复后仍提示未保存。

新增挂载还复现了两个边界：capabilities 先到、初始文档列表仍未返回时，可以通过原独立通用脚本入口发起真实 SAVE，而 loading 投影遮蔽 SAVE；clean 文档派生遇到不确定回执后，核对 A 期间可以从原列表打开 clean B，A 的迟到核对响应此前会成为 B 的替换候选。

## 最小实现范围

- `CreativeWorkspace.tsx` 继续持有唯一 drafts/base/dirty/blocked owner。比较原 `documentInput` 的完整可写投影，仅递归排序对象键；保留数组顺序、ID、正文、空白与所有实际可写字段。没有 base 的编辑草稿始终保留 dirty；blocked 不由相等比较解除。已有草稿的水合保护未改。
- 原 busy state 替换为单一 operation state（SAVE / VERIFY / DERIVE / RESTORE，加原 mode/draft 身份），busy 从它派生。实际当前操作优先于背景 list 状态，旧文档操作单列；真实 SAVE 才显示“保存中…”。原保存 CAS、实际服务端规范化回执更新 value/base、权限失败处理和退出保护保留。
- `checkServer` 只在原 mode 与原 draft 对象仍为当前时接收候选和通知。旧核对错误不覆盖 B 的错误；401/403 仍走原 deny。原 history 和跨 scope session 挂载隔离未改。
- 当前文档状态独立标注为 `role=status`、`aria-label="当前创作文档保存状态"`。其他阶段 dirty、blocked、改编草稿及制作草稿分别归属，不移除其退出保护。
- `App.tsx` 仅新增原连接/Tutor 内容的 `commonStatus` prop。NOVEL 仍使用原 `novelStatus`；其他 Creative 阶段不混入小说正文状态。原连接 authority guard、导航 intent owner 和 adoption 精确版本回读 fence 未改。
- `CreativeCanvas.tsx` 仅增加兼容可选 `saving` prop（缺省仍沿用 busy）及按钮标签消费；busy/disabled/edit guards、画布徽章、字段及布局均保留。

实际中文状态主合同为“当前分镜：已保存 · vN”“当前分镜：未保存更改 · 基于 vN”“当前分镜：保存中… · 基于 vN”“当前分镜：需核对保存结果 · 本地草稿保留 · 基于 vN”。其他阶段例为“其他阶段未保存：剧本（仅本页内存）”。新草稿、读取、权限拒绝及核对/派生/恢复均有独立状态。

## 保留的准备证据

所有原 runner receipt/log 位于 `docs/delivery/v2-development/<label>.json/.log`；Vitest 原 JSON 位于本目录。未覆盖或删除失败证据。

| 标签 | 结果 | 解释 |
| --- | --- | --- |
| creative-save-mounted-red-r1 | 3 passed / 9 failed | 原状态归属及编辑恢复 RED；其中 visual-target selector 另有重复匹配问题 |
| creative-save-mounted-green-r1 | 11 passed / 1 failed | 剩余为新增测试 selector 匹配原只读 inspector；收窄到实际 Canvas |
| creative-save-mounted-green-r2 | 12 passed | 首组修复验证 |
| creative-save-operation-red-r1 | 20 passed / 4 failed | 原 VERIFY/DERIVE/RESTORE/DirectorBusy 按钮错误显示 Saving |
| creative-save-operation-red-r2 | 20 passed / 5 failed | 新生产 callback 测试初始通用 API fixture 误返回环境结构；保留诊断 |
| creative-save-operation-red-r3 | 20 passed / 5 failed | 纠正新增 fixture 后，五种非 SAVE busy/dirty 均因保存按钮标签失败 |
| creative-save-owner-boundary-red-r1 | 20 passed / 7 failed | 加入实际 SAVE 被 loading 遮蔽和旧 VERIFY 候选污染 B 的 RED |
| creative-save-owner-boundary-green-r1 | 27 passed | 新 26 个完整原组件交互与 1 个生产 child callback 边界回归 |
| creative-save-related-green-r1 | 99 passed | 新 27 + 原 Creative/Canvas/adoption 回读与 App 连接/导航 72 节点 |
| creative-save-tsc-prepare-r1 | PASS | 原 TypeScript 项目检查 |

26 个主回归挂载原 CreativeWorkspace、Canvas、AppShell，并控制 API 响应时序。另 1 个生产 dirty 合同回归仅替换独立 production child 来送达其原 `onDirtyChange`，检查真实 host/Canvas 禁用与退出保护；不将其称为真实生产 UI 或后端验证。准备源码五文件 SHA、LF 字节和逐轮失败名称见 `mounted-red-green-prepare-evidence.json`。

## 边界

没有改旧测试、设计系统、共享 shell、canonical baseline、后端或 Prompt adoption gate。本记录不替代原回执，也不构成全 V2 release 声明。GraphFlow 使用本会话实际可用的 `gf_read` 做前置压缩与变更后定位；旧 `graphflow_index` 接口未暴露，不声称调用了该接口。

## 冻结源正式终态

冻结快照为 2310 路源码，canonical map SHA256 为 `783255e32b4a193965a8162becfe7df605eb76e99ee41b729f4fe28517999f9f`。四组原前端回执的前后完整字典均等于此快照、没有源码漂移，日志 SHA 已逐项复算；见 [frontend-verification.json](frontend-verification.json)。

| 正式检查 | 实际结果 |
| --- | --- |
| creative-save-src-final-r1 | 4269 passed、6 个原有 skip、0 failed；393 文件 |
| creative-save-build-final-r1 | TypeScript + Vite PASS |
| creative-save-visual-final-r1 | 原 canonical 视觉/几何 7 passed，未刷新 baseline |
| creative-save-tokens-final-r1 | PASS，52 文件 |
| creative-save-browser-file-final-r1 | 原外层 PASS；真实 Edge 9 passed，41.407 秒 |
| creative-save-browser-pg-final-r1 | 原外层 PASS；真实 Edge 9 passed，468.231 秒；新空库 OID 29705，原 20 migrations |

准备 27/99 节点没有再次加到完整前端统计。原捕获 HEAD 保持真实：File 为 `454ccd8`、前端四组为 `4571bda`、PG 为 `5c17750`，其源码字节匹配同一冻结快照；未改写原回执以伪装晚启动。

[frontend-preservation-review.json](frontend-preservation-review.json) 复算原 1118 test/gate 源、除授权 CreativeWorkspace 外的 60 adoption 源，以及原只读三源与 14 个视觉/DS/shell/config/spec/baseline 路径。所有预期原字节均匹配。六块原业务 guard 由独立候选 R2 审查确认 raw 保留；[protection-post-collection.json](protection-post-collection.json) 的 750 源 / 752 artifact 保护边界也没有差异。这些是保护与回归证据，不是新 V1 运行验收。

独立实际视察了 File/PG 全部 78 张 named 原 PNG，并从原 results.json 解码 18 份 evidence、核对 78 个 DOM 状态快照和 24 个保留的原 HTTP body SHA；具体图像、状态与限制见 [FINAL_FRONTEND_VISUAL_REVIEW.md](FINAL_FRONTEND_VISUAL_REVIEW.md)。普通生产 GET 的 adoption 能力始终 false，无进程内 True override；模型结果只记 `NOT_REQUESTED` / `NOT_INSTRUMENTED`。

正式浏览器采用原 LocalSessionBootstrap、原文档 API/CAS/存储与 UI。离线用例仅验证发送前的真实传输失败，没有声称提交后丢回执。File/PG 都证明实际 PUT 200 v2 与整页重开、其他阶段真 dirty 独立归属、真实 409 保留草稿、VERIFY A 的迟到候选拒绝及原 history 文档/范围隔离。迟到 VERIFY 后 B 页仍可留有 A 的历史派生 notice；B 的当前保存状态正确且没有候选覆盖入口，不能据此宣称全页历史提示已清理。

[final-runtime-cleanup.json](final-runtime-cleanup.json) 记录浏览器所属服务/worker 已停、PG `pg_ctl` exit 3、所属端口关闭；原视觉 Vite PID 86928 也由 Playwright 自动结束，5174 无监听，见 [frontend-visual-runtime-cleanup.json](frontend-visual-runtime-cleanup.json)。本实现 owner 未提交或推送，也未在冻结后修改产品源/测试。
