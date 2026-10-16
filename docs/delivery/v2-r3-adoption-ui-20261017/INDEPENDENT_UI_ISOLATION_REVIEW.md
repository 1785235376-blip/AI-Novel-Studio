# 独立 UI 与隔离边界复核

复核日期：2026-10-17（Asia/Shanghai）。基准 HEAD：`679a88b635639fb680f56893a41857b4e79001ec`；复核对象包含其后尚未提交的 8 个 UI 实现/测试文件。仅审查源码与既有准备证据，本次没有修改源码、测试、gate 或提交。

**结论：前次发现的迟到回读覆盖较新 host 版本缺陷已在源码和组件回归层闭合；本次未发现新的 gate 或授权绕过。此结论不替代最终真实 File/PostgreSQL 浏览器验收。**

## 迟到回读修复

`PromptAdoptionWritePanel` 将不可变 `held.target.version` 随 `onCommitted(document, expectedTargetVersion)` 交给原 `StoryboardWorkspacePanel`，再交给真实 `CreativeWorkspace.onDocumentCommitted`。host 除原有 current、同文档、clean、unblocked 条件外，要求 `current.base.version === expectedTargetVersion`。不满足时明确抛错；不会静默拒绝后继续报告成功。

Panel 等待 callback 完成后才清除 pending 和显示成功。callback 抛错时保留已确认的 `pending.commit`，显示“服务端已确认提交，但当前镜头与来源回读尚未完成”；“重新核对采用结果”跳过 POST，仅重读 projection 与原文档。

两层回归均已核对：新 `CreativeWorkspace.adoptionCommitRace.test.tsx` 使用真实 host 状态及其原 production owner callback，先接受 clean v4，再送达旧 v3，断言抛错、保留 v4 和原画面提示词；新 Panel 用例断言 host 拒绝时无成功提示，再核对仍只有一次 POST。这些测试替身用于组件边界验证，不是实际浏览器证据。

## 准备证据核对

- [RED 原日志](frontend-host-cas-red-r2.log)：2 个 host 用例中 1 passed / 1 failed；修复前迟到回读没有抛错，失败证据保留。
- [GREEN 原日志](frontend-adoption-broader-r2.log)：23 个模块、264 passed，包含上述 host 与 Panel 回归；不据此汇总独立用例总数或声称完整产品验收。
- [准备回执 R2](FRONTEND_PREPARATION_RECEIPT_R2.json)：记录 TypeScript exit 0，关联 [原日志](frontend-adoption-tsc-r3.log)。该日志为空；退出码依据准备回执，而非凭空日志判定。
- 独立重新计算上述回执列出的 8 个源码/测试文件 SHA-256，**8/8 与当前候选文件完全相同**。

| 原日志 | 本次核对 SHA-256 |
| --- | --- |
| `frontend-host-cas-red-r2.log` | `34156a22ebd1b56bacaf709690a618b0dbf953d509c653dbfafaaa1484e5241a` |
| `frontend-adoption-broader-r2.log` | `71c54cd68558b560827e02bd238f0079b297a1573cfb5b9e96c399f51a41426c` |
| `frontend-adoption-tsc-r3.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## 生产 gate 与隔离 launcher

原 API 保持 `PROMPT_ADOPTION_WRITE_ENABLED = False`；相对上述 HEAD 无修改。GET 只有服务端布尔投影，客户端 absent/false 均关闭写入口；该投影不替代原 actor、scope、domain.read/domain.write 授权。POST 使用原 strict DTO 与原 atomic adoption owner，客户端不能提交正文或来源证明来代替它。

独立读取 [launcher](../../../scripts/run_v2_prompt_adoption_ui_browser.py) 后确认：它先检查源码是唯一 literal False；仅在显式创建的隔离子进程导入原 app 后，把该进程的模块内存值设为 True。没有新增产品环境变量开关或 endpoint，也没有替代身份 owner、响应 mock。隔离进程停止后重新启动普通生产进程；前后控制均要求 GET false、精确 503 `PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`、原文档 before/after 完全相同，并最终检查 gate 源字节未变。launcher 当前 SHA-256 为 `2b87d52a53bc41a38c299ffb9cd43c5e6ac2b42d43f20d6c723bcf14b5a5b7d8`。

以上是已存在的隔离控制设计和源码断言的审查结论，**不是本次执行成功声明**。统一冻结源上的最终 File/PG、真实浏览器、生产前后控制及视觉结果，由本轮主报告补录；本报告保持独立源码/组件证据边界。
