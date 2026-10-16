# Adoption UI 隔离运行验收

最终 **File Edge 3/3、PostgreSQL 43/43、PostgreSQL Edge 3/3 PASS**。三组绑定同一份 **2301** 文件源码快照，运行期间无漂移；当前工作源码逐项一致。生产 literal `PROMPT_ADOPTION_WRITE_ENABLED = False` 保持不变。

| 最终组 | 结果 | 原始命令、日志及源码快照 |
|---|---|---|
| File，1366×768 / 1440×900 / 1920×1080 | 3 PASS，30.0s | [receipt](runner-receipts/r3-adoption-ui-browser-file-final-r3.json) / [log](runner-receipts/r3-adoption-ui-browser-file-final-r3.log) |
| PostgreSQL capability12 + bindings26 + original authorized4 + incarnation1 | 43 PASS，299.18s，39 deselected | [receipt](runner-receipts/r3-adoption-ui-combined-pg-final-r3.json) / [log](runner-receipts/r3-adoption-ui-combined-pg-final-r3.log) |
| PostgreSQL，同三视口 | 3 PASS，333.8s | [receipt](runner-receipts/r3-adoption-ui-browser-pg-final-r3.json) / [log](runner-receipts/r3-adoption-ui-browser-pg-final-r3.log) |

所有浏览器步骤均走原产品：真实凭证连接与项目选择、Prompt 创建、显式批准、来源修订读取、确认 checkbox、原“采用到当前镜头”按钮。监听该点击产生的原 POST 200；原 CreativeDocument 从 v1 到 v2，只有一条服务器生成 proof，主编辑器逐字显示中文、emoji、首尾空格与换行。整页刷新和重新打开后 owner 完全相同、来源固定 r1；原 UI 新增来源 r2 后不自动 repin。额外 HTTP 重放与 UI 成功分开：同 DTO `200/replayed=true` 无新版本或重复 proof；改变内容重用请求严格 `422 / EXPERIMENTAL_INVALID / PROMPT_ADOPTION_REQUEST_REUSED`，owner 完全不变。

六份 proof 均有真实原 `NovelService.characters` 记录绑定及 incarnation，`source_binding_contract=prompt-adoption-bindings/1`、`source_bindings_verified=true`、`WRITE_TIME_OWNER_LEASE`；这是写入时声明绑定检查，不外推当前全部依赖活性。原始附件逐字解码与 SHA256 见 [六份 proof 索引](final-browser-proof-index.json)，每视口确认前正文/批准/目标版本/checkbox与成功、重开、历史 pin 截图见 [30 张 PNG 索引](final-browser-screenshots.json)。未伪造响应、身份或 React 状态；`model_execution=NOT_REQUESTED`、`model_counter=NOT_INSTRUMENTED`。

每个后端的隔离进程启动前、退出后均重新启动普通原后端，真实 GET `write_enabled=false`、有效 POST 精确 `503 PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`，原 owner 前后 SHA256 相同。仅验收子进程在导入后、uvicorn 启动前将原 module boolean 内存值置 True；普通生产源/环境无开关修改。[File launcher](r3-adoption-ui-browser-file-final-r3/launcher.json)、[PG launcher](r3-adoption-ui-browser-pg-final-r3/launcher.json) 及各自 before/after-control.json 保留原事实；三份原 closed-gate harness/spec 与本轮起点逐字一致，见 [保留核对](original-closed-gate-harness-preservation.json)。此结果是隔离成功闭环，未授权生产开闸。

两个最终新库均从 template0 空库执行原 20 migrations，真实 PostgreSQL 16.15：回归库 OID **27042**、浏览器库 OID **27943**。项目、身份、授权及 experimental state 使用原 PG repositories；不可变素材仍由原 File Asset owner 保存，无 blob 替换/后端回退。各原 [回归 runtime](runner-receipts/r3-adoption-ui-combined-pg-final-r3-postgres-runtime.json) / [浏览器 runtime](runner-receipts/r3-adoption-ui-browser-pg-final-r3-postgres-runtime.json) 都记录 fresh、20 applied、server_stop=stopped、cleanup=completed。独立 [最终清理核对](final-runtime-cleanup.json) 确认 pg_ctl exit3、PG 不运行、8138/5208/50678 不可连接、无 owned worker/listener；库和 profile 保留。

先前失败均保留，不计为最终 PASS：smoke-r1 原全局 Character 路由带分支头、r2/r3/r4 locator 设置、r5 将原 422 错写为409；smoke-r6 单视口通过。PG browser final-r1 三视口失败暴露 scope breadcrumb 早于 overview 初始 IMAGE 恢复；新 spec 仅等待实际 IMAGE+原已加载 workspace 就绪再导航，不加 sleep/重复点击。该既有 overview 恢复仍可能覆盖提前导航，未在本轮修复。File final-r2 首次连接被旧 local inventory 带走（2 PASS/1 FAIL），原 App 新 guard 在所有自动恢复分支前核对实时 API 会话/范围与 store，mounted RED→GREEN 后本轮真实 File/PG 冷启动通过。旧 Entry/API/旧测试未改；所有 r1/r2 与 smoke 原 JSON/log、截图、runtime 见 [逐字镜像清单](runner-receipts-mirror.json)。旧 PG43/r1 只作历史证据。

完整源码绑定及关键文件 SHA256 见 [final-source-binding.json](final-source-binding.json)，canonical sorted compact map SHA256：`1f8bfabc61da1841f7edebcedc6c7a6a7e9455ca348c41a4c23496cb15a2df65`。原始日志与测试结果、数据库、profile 均保留；本子任务未提交或推送。
