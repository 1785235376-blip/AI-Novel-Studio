# Creative 工作台保存状态 — 最终验收

2026-10-17（Asia/Shanghai）；基线 `454ccd89499e3840d18622e8b6ec2669c17702c4`。

**本轮指定保存状态问题已修复，真实 File/PostgreSQL + Edge 三视口验收通过。** 当前文档显示自身已保存版本、真实未保存更改或待核对结果，其他阶段草稿单独列出。生产 `PROMPT_ADOPTION_WRITE_ENABLED=False` 继续关闭；[PR #47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) 保持 Draft/open。完整 V2 仍为 PARTIAL，未 freeze/RC；托管账单锁单独记为 BLOCKED。

实现/清单 HEAD `5c17750bd59c76ed4fb060716d61019151a3ef42`。本报告与原始证据另作独立提交。选定最终检查的全部 2310 源均绑定冻结 map SHA `783255e32b4a193965a8162becfe7df605eb76e99ee41b729f4fe28517999f9f`，无运行中或当前源码漂移。

## 独立稳定切片

| 已提交并推送的提交 | 范围 |
| --- | --- |
| `4571bdaeee1b35e88fa19c032c3767a54be01d35` | fix(creative): bind save status to the current document and operation |
| `e0982471746a0da4ffb29c4427beb9ec6f28b4dc` | chore(ci): bind Creative save-state sources without changing frozen inventory |
| `5c17750bd59c76ed4fb060716d61019151a3ef42` | test(creative): verify real save state and late readbacks across File and PostgreSQL |

[发布审计](implementation-publication-audit.json) 核对原分支、PR、main 与 frozen refs，没有 merge 或修改生产配置。

## 原 owner 修复和因果证据

原截图里的“无未保存创作草稿”包含“未保存”子串，不能据此认定水合产生虚假 dirty。原当前画布徽章对全新空白草稿也已有“新草稿”。实际复现的缺陷是底栏混合小说正文、所有创作阶段与当前文档状态，等值输入和修改撤回仍保留 dirty，以及 VERIFY/DERIVE/RESTORE/制作操作被按钮误称为“保存中”。

修复由原 CreativeWorkspace draft/base/dirty、原 mutationLock 和原 Canvas 持有。完整原 documentInput 可写投影递归排列对象键后比较；保留字段、正文空白、Unicode 和数组顺序，不裁剪正文、不跳过 payload 字段。没有 base 的用户编辑仍是草稿；blocked 不因等值自动消失。成功保存使用真实回执的文档及版本作为 value/base；已有草稿（含显式新建的 clean 草稿）不被水合覆盖。

原 busy 状态改为单个带 kind/mode/原 draft 身份的操作描述，锁逻辑不变；只有实际当前 SAVE 显示“保存中”。当前操作优先于仍在读取的列表，跨文档操作单列。App 只增加 commonStatus 传递原连接/Tutor 内容；NOVEL 保留原正文状态。其他阶段、改编和制作草稿及离开保护继续存在，当前已保存不抹去其他真实未保存草稿。

新增实测发现 clean+blocked A 核对期间可从原列表打开 B，旧 A 的 GET 曾可挂到 B。checkServer 现在检查原 mode 与同一个 draft 对象，拒绝陈旧候选/错误；401/403 仍由原 deny 收权。原 adoption 回读 CAS、导航 entry/overview 与连接 guard 均逐字节保留。

准备阶段从原实现取得因果 RED；新增 27 回归通过，其中 26 为原完整 Creative/Canvas 交互，1 项明确替换制作子组件以验证 productionDirty 原 callback 契约。相关 99 项包含这 27 项，不与完整 suite 相加。所有失败/设置错误和后续回执保留，范围详见[实现报告](FRONTEND_CREATIVE_SAVE_IMPLEMENTATION_REPORT.md)与[独立审查](INDEPENDENT_IMPLEMENTATION_REVIEW.md)。

## 本轮真实验收

| 检查 | 实际结果 |
| --- | --- |
| File + Edge | 9 passed / 0 failed / 0 skipped / 0 flaky；[receipt](../v2-development/creative-save-browser-file-final-r1.json)。 |
| PostgreSQL + Edge | 新空库 OID 29705，原 20 迁移；9 passed / 0 failed / 0 skipped / 0 flaky；[receipt](../v2-development/creative-save-browser-pg-final-r1.json)、[PG 原始回执](../v2-development/creative-save-browser-pg-final-r1-postgres-runtime.json)。 |
| 完整 frontend/src | 4269 passed / 6 既有 skipped / 0 failed，393 文件；[JSON](frontend-src-final-r1.json)、[receipt](../v2-development/creative-save-src-final-r1.json)。 |
| 构建与原 UI 约束 | `tsc -b && vite build` PASS；原 canonical visual/geometry 7 passed，token 52 文件 PASS；[视觉复核](FINAL_FRONTEND_VISUAL_REVIEW.md)。 |
| 原 CI 清单自检 | 166 passed；[receipt](../v2-development/creative-save-ci-selfchecks-final-r1.json)。 |
| 双 collection | 15142 个原 literal pytest node、顺序、分类保持；2372 个 manifest 输入，新增 5 源。INVENTORY_ONLY，不是 15142 项测试执行通过。 |

File/PG 各在 1366×768、1440×900、1920×1080 使用真实 LocalSessionBootstrap 身份、原 API、列表和保存按钮。首开已保存 v1；等值数字和编辑撤回保持 clean 且无 PUT；真实空白/Unicode 编辑标记未保存；原 PUT expected_version=1 返回真实 v2 后，header/footer/完整 owner 回读/刷新均一致。待处理保存时重复点击、编辑和导航受原锁保护；当前 clean 文档与其他阶段真实 dirty 分开显示，离开仍需明确确认。

真实离线前置于请求派发，得到 ERR_INTERNET_DISCONNECTED；本地 draft/blocked 保留，owner 未变，恢复连接后经原核对和显式采用恢复。该案例**不是**服务端已提交后响应丢失。同一真实 actor 的独立 API 请求经原文档 owner 写入 v2，旧 v1 的原 derive 与 Save 分别收到真正 EXPERIMENTAL_VERSION_CONFLICT/409；本地草稿和服务端 v2 均保留，不能自动重试或覆盖，不冒称不同身份或不同进程的并发验收。

原 VERIFY GET A held 时从原列表开 B，放行的真实 A/v2 不挂入 B/v1，不能出现错误的显式采用按钮；原历史 GET 迟到也不改变 B 草稿或新 project/branch 的干净文档。时序调度只暂缓客户端原 request dispatch，随后无修改 route.continue 放行真实 HTTP，不称 hold 时后端已收到请求。没有 response mock、身份/store/DOM 注入。成功 SAVE 回执跨卸载等更强时序边界由 mounted 交互证据单列，不冒充浏览器全覆盖。

详细截图、原响应、完整文档回读与失败边界见[真实运行报告](CREATIVE_SAVE_STATE_RUNTIME_ACCEPTANCE_REPORT.md)。视觉复核也记录原 openDocument 保留的 A 派生操作历史 notice；B 的当前 footer/画布仍为已保存 v1，旧 A candidate/采用按钮被拒绝，不声称 B 全页没有先前操作文字。本轮普通 uvicorn app.main:app 从未 patch gate；各来源 capability 严格 False、无 adoption POST。显式 MOCK_PROVIDER=false；模型 NOT_REQUESTED，计数 NOT_INSTRUMENTED。File/PG 使用原 adapter，资产字节仍归原 File AssetLibraryService，不声称 PG blob。

## 保护、阻塞和保留

[来源审计](FINAL_SOURCE_PROVENANCE_REVIEW.md)、[统一 receipt 绑定](source-binding-final.json)、[Git 原字节](source-git-binding-final.json)和[manifest 原字节](manifest-source-git-binding-final.json)核对全部 2310 runner 源及 2372 manifest 输入。原 750 frozen test/gate、752 保护产物、1118 既有 test/spec/gate、旧导航测试/验收，以及未授权修改的 adoption 源保持；共享 App/CWS 的授权差异局限于本轮原 owner。六个保护 guard 原字节保留，不声称全 V1 app 源或 V1 runtime PASS。

原 9151 manifest SHA `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262` 未变。新 V2 manifest SHA `9d9b8157f1f342ff680e6119b4338a30332a1cec970d5cb00faa10fc01193aca`；只更新来源指纹，原 15142 rows/classification 不变。

托管 **BLOCKED_HOSTED_ACCOUNT_BILLING**：[独立回执](hosted-ci-implementation.json)保存实现 HEAD 的 3 个工作流原 job/账单注释，job steps 为空。本地通过不代替 hosted CI，未修改工作流或账户；解锁后需重跑最终 HEAD 托管检查。

自有 API/Vite/PG 与 canonical visual 服务已停止；[停止与保留审计](runtime-retention-final.json)。失败/通过日志、截图、profile、验证数据库及原 baseline worktree 都保留；未递归清理或宣称磁盘回收。原始字节见[evidence-manifest.json](evidence-manifest.json)。

本轮只建立指定 Creative 保存状态修复 PASS；历史 adoption/导航回执保留为历史，不冒称本轮重跑。完整 V2、生产 adoption、installer/clean-machine、真实模型/GPU 及 Canvas/Director/媒体/NLE/3D/Tutor 全链路未由本轮建立 PASS。生产 adoption 闸门继续关闭。

GraphFlow 使用可用 gf_read 压缩与复核变更；legacy graphflow_index 未提供，未声称调用成功，本地缓存保留。
