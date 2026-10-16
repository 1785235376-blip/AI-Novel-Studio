# Final source provenance independent review

2026-10-17，Asia/Shanghai。独立审查绑定最终实现提交 `db1f687108fac6e45a577196494dfac01cc63aca`：原 App 修复 `2d96d90`、browser readiness `71d0b1c`、additive manifest `db1f687`。本次只读取原文件、Git tree 与既有回执，重新计算原字节哈希和集合关系；没有新跑产品测试、修改源码/测试/基线或提交。具体复算值见 [审查明细](FINAL_SOURCE_PROVENANCE_REVIEW_DETAILS.json)。

**结论：2301 / 2363 源绑定、collection 增量、750 / 752 冻结保护，以及 final-r3 File55、CI166、FileEdge3、PG43 和 PGEdge3 回执均独立核对通过。两个最终 PG 范围均已等待外层 runner / wrapper、生产后控制及清理终态后才纳入 PASS。**

## 源码与 Git

独立读取 HEAD tree，用当前文件的无过滤原字节计算 Git blob 身份，并同时计算 SHA-256：

- [runner 绑定](source-git-binding-final.json) 的 **2301** 路径全部匹配当前文件、记录的 SHA-256、记录的 blob OID 和提交 tree；零差异，零换行归一化例外。
- [manifest 绑定](manifest-source-git-binding-final.json) 的 **2363** 路径全部匹配 manifest SHA-256 和当前提交原始 blob 身份；零差异。
- V2 manifest SHA-256 为 `ceacc0cb2f100dde23ce07a76dd086d27ae3eafbafc1b2499b97a0425a1dc405`。新增的唯一源路径是 `frontend/src/AppLocalEntryAuthorityRace.test.tsx`；App、该新回归与 browser spec 的原字节分别匹配冻结的 `ede1d8ad…`、`72aaa0c9…`、`c08ca758…`。

## Collection 与冻结保护

独立从本轮基准 `95420aa59acb4c196d92e7292df0744098f6d2ff` 读取旧 V2 manifest，再比较当前 manifest、final-r3 两份完整 collection 原始 rows 和 [delta](collection-delta-final.json)：

- 旧 **15118** 个 literal node ID 的顺序与出现次数全部保留；当前 **15142**，只新增 **24** 个，全部属于 `tests/test_v2_prompt_adoption_ui_capability.py`。新增 TS mounted 回归增加前端源码，不增加 pytest inventory 节点。
- [first](collection-first.json) 与 [confirmation](collection-confirmation.json) 的原始 rows 完全一致、exit 0、errors 为空，node 列表与当前 manifest 完全相同。旧 skips / external gates 未变。collection 仅是 inventory，不是 15142 项测试全部执行证明。
- 原 **9151** 个节点按原序保留；原冻结 manifest SHA-256 仍为 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`。
- 重新读取既有审计明确列出的 **750** 个 frozen test/gate 路径及六组保护路径去重后的 **752** 个产物，原字节全部与原选定 `045b865e` 审计值一致；752 个保护产物也全部匹配当前 HEAD 原始 blob。与 [本轮保护回执](protection-final.json) 一致。
- 对原冻结 manifest 的唯一历史 test 差异仍是本轮前已审核的 `tests/test_windows_portable_entry.py` 固定入口 `-B` 增量（`1b7ff50`）；没有把它当成本轮改动，也没有改写冻结 manifest。

这只证明所列源码/证据保留，不等于全部 V1 app 源码相同或重新完成 V1 runtime 验收。

## 当前可接受的 final-r3 回执

| 范围 | 原始终态 | 独立绑定 |
| --- | --- | --- |
| File 原 owner / capability / bindings | [55 passed、38 deselected、25.41s](../v2-development/r3-adoption-ui-bindings-file-final-r3.log)，[回执](../v2-development/r3-adoption-ui-bindings-file-final-r3.json) exit 0 / PASS | 2301 前后源图相同、无漂移、完全等于当前绑定，原日志 SHA 匹配 |
| 原 CI 自检 | [166 passed、6.32s](../v2-development/r3-adoption-ui-ci-selfchecks-final-r3.log)，[回执](../v2-development/r3-adoption-ui-ci-selfchecks-final-r3.json) exit 0 / PASS | 同上；CI 脚本测试通过不等于托管 CI 已执行 |
| 实际 File / Edge UI | [3 expected、0 unexpected、0 skipped、0 flaky](r3-adoption-ui-browser-file-final-r3/results.json)，29.954s，[runner 回执](../v2-development/r3-adoption-ui-browser-file-final-r3.json) exit 0 / PASS | 同上 |
| 实际 PostgreSQL 原 owner / capability / bindings | [43 passed、39 deselected、299.18s](../v2-development/r3-adoption-ui-combined-pg-final-r3.log)，[runner 回执](../v2-development/r3-adoption-ui-combined-pg-final-r3.json) exit 0 / PASS | 同上，原 wrapper 最终 PASS、server stopped、cleanup completed |
| 实际 PostgreSQL / Edge UI | [3 expected、0 unexpected、0 skipped、0 flaky](r3-adoption-ui-browser-pg-final-r3/results.json)，333.813s，[runner 回执](../v2-development/r3-adoption-ui-browser-pg-final-r3.json) exit 0 / PASS | 同上，独立第二 PG 库的 wrapper 与清理均终态成功 |

两次 collection runner 回执也独立通过相同源图和日志哈希检查。File55 / CI166 / FileEdge3 与两次 collection 回执保留实际运行时 HEAD `6aed517`；当时工作区已包含冻结修复。PG43 / PGEdge3 的实际运行时 HEAD 为 `db1f687`。没有改写这些字段。每个源文件的实际 SHA-256 与最终提交完全相同，形成明确的字节绑定。不将不同范围相加宣称独立测试总数。

FileEdge3 与 PGEdge3 的实际 `redacted-original-ui-adoption` 附件分别逐个解码核对，每个视口各 **15** 项边界均通过：原产品按钮 POST200、首次 committed 且非 replay、目标版本精确 +1、目标 digest/source family/asset/revision/request ID 与原证明一致；正文 SHA-256 独立重算吻合，中文/emoji/首尾空白和换行逐字保留；原 owner 保存同一 proof，真实 Character 来源快照含原 owner、租约标记与 incarnation；页面重开 owner 完全相同，家族新增修订没有移动既有 pin；每视口只有一次浏览器 adoption POST，附加 API 精确 replay 没有新增 revision。

File 的 [launcher 终态](r3-adoption-ui-browser-file-final-r3/launcher.json)、[生产前控制](r3-adoption-ui-browser-file-final-r3/production-before-control.json) 和 [生产后控制](r3-adoption-ui-browser-file-final-r3/production-after-control.json) 一致：生产 literal False，隔离子进程 HTTP capability True；普通进程前后 GET false + 精确 `503 PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`，同一原 owner 的 before/after 哈希相同；gate 源字节未变，所有自有进程已停止。没有产品环境开关、开发身份或响应 mock。

PG 的 [launcher 终态](r3-adoption-ui-browser-pg-final-r3/launcher.json)、[生产前控制](r3-adoption-ui-browser-pg-final-r3/production-before-control.json) 与 [生产后控制](r3-adoption-ui-browser-pg-final-r3/production-after-control.json) 也逐一通过相同断言；三个普通/隔离 backend 的 health storage 均明确为 postgres，数据库 identity 与原 wrapper 同名且 OID 一致。并非以 Playwright 内层 `3 passed` 单独推断整个流程成功。

PG43 的 [原 wrapper](../v2-development/r3-adoption-ui-combined-pg-final-r3-postgres-runtime.json) 证明 fresh 库 `v2_r3_adoption_ui_20261017_final_r3`、OID **27042**；PGEdge 的 [原 wrapper](../v2-development/r3-adoption-ui-browser-pg-final-r3-postgres-runtime.json) 证明另一 fresh 库 `v2_r3_adoption_ui_browser_20261017_final_r3`、OID **27943**。两个数据库创建前均不存在、迁移前对象数均为 0，20 项原迁移全部 applied 且每项 SHA-256 独立复算与当前源字节一致；最终 status PASS、checks exit 0、server stopped、cleanup completed。

两个 PG 原 runner 日志 SHA-256 也独立吻合：PG43 为 `51d778c8cb6820704aa1af64f213f228bd504ce551fc1daf8dd0f9e5a738a67c`，PGEdge 为 `3094f9824521d02c458d93e148fd1695f737e085b1eab8022de9c5db3aa00806`。其 2301 源图在运行前后相同、无漂移且完全匹配最终 Git 绑定；本次复核再次读取当前 2301 路径，哈希仍全部一致。

## 失败历史与结论范围

旧 [PG browser-r1](r3-adoption-ui-browser-pg-final-r1/results.json) 为 3 unexpected；旧 [File browser-r2](r3-adoption-ui-browser-file-final-r2/results.json) 为 2 expected / 1 unexpected，均保留，未改名为成功。前者暴露原 NEUTRAL 模块初始化晚到导航边界，spec 现等待真实初始 Image/IndependentStudio 就绪；后者暴露真实连接过程中原 local auto-resume 抢开本机小说，原 App 权威一致性 guard 与独立 mounted RED/GREEN 见 [因果报告](ENTRY_CONNECTION_RACE_REPORT.md)。没有仅靠延时或抹除控制项目回避该实际 App 缺陷。

旧 6aed 快照的 14 文件与 c08ca 准备快照的 10 文件分别存于 [旧档索引](history/6aed517-collection-r1/archive-index.json) 和 [准备档索引](history/c08ca758-collection-r2/archive-index.json)，全部归档原字节再次核对未变；旧报告与失败证据仍可追溯。

本次最终 PG 成功来自上述 final-r3 的新数据库、完整终态及独立哈希/证明检查，没有借用旧快照 PG43 的成功。结论限于所列 source provenance、原 owner/API 与隔离 UI 成功流程；生产写入 gate 仍保持 False。本报告不据他人概述升级 full frontend、visual、build 或 hosted CI 结论，也不把未请求的模型执行表述为经过计数器测量的零调用。
