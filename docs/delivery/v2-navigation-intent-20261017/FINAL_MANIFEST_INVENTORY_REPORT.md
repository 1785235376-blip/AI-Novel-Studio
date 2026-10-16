# Final navigation manifest inventory

2026-10-17，Asia/Shanghai。基准 `87408f6881fd2dc2f22038c36643ed2e0a743f33`。状态：**INVENTORY_ONLY / SOURCE_PROTECTION_PASS**；完整 HEAD 原字节绑定按 root 要求延后，尚不将本报告升级为最终 File/PG/runtime 或全部 pytest 执行证明。

原 pinned Python 3.12.9 / pytest 8.4.2，经原 `run_v2_checks.py` 调用原 `extend_v2_coverage_manifest.py`，完成两次独立完整 `--collect-only`：

- [first 原报告](collection-first.json) 与 [first 原 rows](collection-first-rows.json.gz)；原 runner [JSON](../v2-development/nav-intent-collection-final-r1.json) / [log](../v2-development/nav-intent-collection-final-r1.log)。
- [confirmation 原报告](collection-confirmation.json) 与 [confirmation 原 rows](collection-confirmation-rows.json.gz)；原 runner [JSON](../v2-development/nav-intent-collection-confirmation-r1.json) / [log](../v2-development/nav-intent-collection-confirmation-r1.log)。

两次 exit 0 / errors 空，完整 rows 完全一致，也与基准 874 的原始 rows 完全相同。全部 **15142** literal node IDs、出现顺序与 backend classifications 保留；本轮新增、删除、重排节点均为 **0**，旧 skips / external gates 完全不变。classification SHA-256 保持 `e7e543708b0ac8ebd1f81f77262a4afa6503d222af2b2e0ad9e71d6a749754d6`。底层报告中的 `5991 new_nodes` 是相对原冻结 9151 的累计历史增量，不是本轮新增。

Additive V2 manifest 源路径从 **2363** 增为 **2367**，仅新增以下四项；已有路径只改动本轮授权的 App：

- `frontend/src/AppModuleNavigationIntent.test.tsx`
- `scripts/run_v2_navigation_intent_browser.py`
- `frontend/playwright.navigation-intent-live.config.ts`
- `frontend/tests/e2e/v2-navigation-intent-live.spec.ts`

新 manifest SHA-256 为 `6f621dcf211c778b09f9ee3351cca511a18b605d0f6d161383816c60dc0ea269`；2367 项工作区源 SHA 全部匹配。原 manifest 快照、详细零节点增量和当前源审计分别见 [基线](V2_MANIFEST_BASELINE.json)、[delta](collection-delta-final.json)、[源审计](SOURCE_PROVENANCE_AUDIT.json)。两 collector 原源码未编辑，新增文件由原递归/根目录规则自动纳入。

两次 runner 前后源图均为 **2305**、彼此一致且无漂移，compact-sorted canonical SHA-256 为 `73cc97473c56824881b0274d19783152d161e7547680c0401009225058bf78da`。其原日志 SHA 已独立实算匹配；实际执行 HEAD 字段保留 `5f87b9d`，不伪改为未来提交。新 mounted **34** 个组件节点、browser **6** 个实际用例和本节 **15142** inventory 节点分别计量，不能互相替代。

[final raw 保护审计](protection-final.json) 复用原 ignored helper，仅内存替换输出目录与基准为 874，原 helper 和旧报告字节未改：750 frozen test/gate、752 保护产物零差异；9151 原 manifest SHA 仍为 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`。Adoption61 与全部旧 test/spec/gate1118 逐字节不变。App 是授权修改目标；其原 local connection guard 单独比较，与 874 原 **2117 bytes** 完全相同，SHA `cf09275f969550d59515fb34a3613f4264359599d8d7b00daeb39770d7eed0fa`。

原 CI 自检 [final-r2 JSON](../v2-development/nav-intent-ci-selfchecks-final-r2.json) / [log](../v2-development/nav-intent-ci-selfchecks-final-r2.log) 的 PASS、2305 源图无漂移及日志 SHA 另行核对通过；它是原 166 自检范围，不能当作 hosted CI 已执行或 15142 pytest 全执行。先前遗漏 Python 的 r1 启动错误由原 owner 保留，不以 r2 覆盖。

此时不执行 commit/push，也不在三新 browser 文件与 manifest 尚未统一提交前声称完整 HEAD 绑定。真实 File/PG gate、DOM、取消及清理终态另由独立 runtime QA 记录；旧失败与历史报告均保留。
