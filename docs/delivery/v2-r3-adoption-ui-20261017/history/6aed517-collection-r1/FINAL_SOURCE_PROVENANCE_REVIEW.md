# Final source provenance independent review

2026-10-17，Asia/Shanghai。独立审查绑定实现提交 `6aed517611117771d767eb275a54773b24ba0300`。本次只读取原文件、Git 对象及既有回执，重新计算哈希与集合关系；没有执行新测试、修改源码/测试/基线或提交。具体复算结果见 [审查明细](FINAL_SOURCE_PROVENANCE_REVIEW_DETAILS.json)。

**结论：绑定 `6aed517` 的源码来源、清单增量、冻结保护及 File55 / PG43 / FileEdge3 回执均核对通过。收集清单是 inventory，不是全部测试执行证明；PG 浏览器尚未作为最终 PASS 纳入本报告。**

时间边界：上述独立复算完成后，最终工作区检查观察到其他 owner 为 PG 浏览器初始化 readiness 修改了 `frontend/tests/e2e/v2-prompt-adoption-ui-live.spec.ts`。本报告的零差异结论属于已提交 `6aed517` 及当时记录的原字节快照，**不宣称该后续未提交 spec 已匹配旧源图或已通过重跑**。后续提交、更新来源绑定和 PG 浏览器终态由主报告单独补录。

## 源码与 Git

独立读取 HEAD tree，以当前文件的原始字节计算无过滤 Git blob 身份，并同时计算 SHA-256：

- [runner 绑定](source-git-binding-final.json) 的 **2300** 路径全部匹配当前文件、记录的 SHA-256、记录的 blob OID 和提交 tree；零差异，零换行归一化例外。
- [manifest 绑定](manifest-source-git-binding-final.json) 的 **2362** 路径全部匹配 manifest SHA-256 和提交 tree 原始 blob 身份；零差异。
- 本次快照的 V2 manifest SHA-256 为 `2f2d2bb16c6159579ba4d051dc139147e17cf821ddbe783985d4bb4069b0b1c2`，与 manifest 绑定和 collection delta 一致。

## Collection 与冻结保护

独立从本轮基准 `95420aa59acb4c196d92e7292df0744098f6d2ff` 读取旧 V2 manifest，再比较当前 manifest、两份完整 collection 原始 rows 和 [delta](collection-delta-final.json)：

- 旧 **15118** 个 literal node ID 的顺序和出现次数全部保留；当前 **15142**，仅新增 **24** 个，全部属于 `tests/test_v2_prompt_adoption_ui_capability.py`。
- 两次完整 collection rows 完全相同、exit 0、errors 为空，node 列表与当前 manifest 完全相同。旧 skips 和 external gates 未变。
- 原 **9151** 个节点按原序保留；原冻结 manifest 字节 SHA-256 仍为 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`。
- 重新读取既有审计明确列出的 **750** 个 frozen test/gate 路径及六组保护路径去重后的 **752** 个产物，当前原字节均与原选定 `045b865e` 审计值一致；保护产物也全部匹配当前 HEAD 原始 blob。与 [本轮保护回执](protection-final.json) 一致。
- 原 manifest 对 `tests/test_windows_portable_entry.py` 的单项差异仍是本轮前已审核的 `1b7ff50` 固定入口 `-B` 增量；没有把它误报成本轮改动，也没有改写冻结 manifest。其余冻结 test/gate 原 manifest 字节均匹配。

这些结论只证明所列源码/证据保留，不等于全部 V1 app 源码相同或重新通过 V1 runtime 验收。

## 最终回执抽核

| 范围 | 原始终态与日志 | 独立绑定结果 |
| --- | --- | --- |
| File 原 owner / capability / bindings | [55 passed、38 deselected、25.84s](../v2-development/r3-adoption-ui-bindings-file-final-r1.log)；[回执](../v2-development/r3-adoption-ui-bindings-file-final-r1.json) exit 0 / PASS | 2300 前后源图相同、无漂移、完全等于当前绑定；原日志 SHA 匹配 |
| 实际 PostgreSQL | [43 passed、39 deselected、308.64s](../v2-development/r3-adoption-ui-combined-pg-final-r1.log)；[回执](../v2-development/r3-adoption-ui-combined-pg-final-r1.json) exit 0 / PASS | 2300 前后源图相同、无漂移、完全等于当前绑定；原日志 SHA 匹配 |
| 实际 File / Edge UI | [3 expected、0 unexpected、0 skipped、0 flaky](r3-adoption-ui-browser-file-final-r1/results.json)，25.726s；[runner 回执](../v2-development/r3-adoption-ui-browser-file-final-r1.json) exit 0 / PASS | 2300 前后源图相同、无漂移、完全等于当前绑定；原日志 SHA 匹配 |

File55 与 FileEdge3 回执保留实际执行时 HEAD `69df94abd1604f32d397b991a6680d516edca59d`，没有改写为后续提交。其所有 2300 源路径的原始哈希与当前实现提交完全相同，因此有明确的字节绑定；PG43 回执 HEAD 就是 `6aed517`。不将上述不同范围相加宣称独立测试总数。

PG43 [原 PostgreSQL wrapper 回执](../v2-development/r3-adoption-ui-combined-pg-final-r1-postgres-runtime.json) 记录真实 fresh 数据库 `v2_r3_adoption_ui_20261017_final_r1`、OID **25264**、创建前不存在、迁移前对象数 0、20 项原迁移全部 applied、checks exit 0、server stopped、cleanup completed。

FileEdge3 的三个 `redacted-original-ui-adoption` 附件均独立解码核对：实际原产品按钮 POST200、首次 committed 且非 replay、目标版本精确 +1、目标 digest/source family/asset/revision/request ID 完全匹配原证明；原 owner 保存相同 proof、中文/emoji/首尾空白和换行逐字保留；实际 Character owner 来源快照含 incarnation；页面重开 owner 完全相同，家族新增修订后既有 pin 没有移动；每视口只有一次浏览器 adoption POST。附加 API 精确 replay 未产生新 revision。

File 的 [launcher 终态](r3-adoption-ui-browser-file-final-r1/launcher.json)、[生产前控制](r3-adoption-ui-browser-file-final-r1/production-before-control.json) 和 [生产后控制](r3-adoption-ui-browser-file-final-r1/production-after-control.json) 一致：生产 literal False、隔离子进程 HTTP capability True、普通进程前后 GET false + 精确 `503 PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`，同一原 owner 的 before/after 哈希相同；gate 源字节未变，所有自有进程已停。没有产品环境开关、开发身份或响应 mock。

本报告没有将尚未独立纳入终态的 PG 浏览器流程视为 PASS。已有 PG1366 刷新导航超时证据须保留；其初始化 readiness 排查和后续真实重跑结果由主报告分别记录。本次也没有独立重跑或据他人概述升级 full frontend、visual、build 或 hosted CI 的结论。
