# 服务端受限本地子调用

新增显式schema6 `creative-graph-local-subgraph/1`。一次有限的纯本地TEXT→DRAFT子调用复用原同scope事务、原Workflow运行状态和父级human_review，不新增执行引擎、子运行、调度器或模型/provider路由。**没有前端执行入口，不代表完整子图或V2完成。**

子图必须为当前保存的schema1，精确匹配版本与两种重算摘要；子图Save即使只改标题也使旧pin失效，不执行历史快照。服务端绑定incarnation/scope/actor/interface/规范化闭包摘要；整个子图仅允许关闭的纯本地白名单，深度1、一个调用、子≤16、父加子≤24，拒绝隐藏/禁用/循环依赖及不满足的必需输入。虚拟输入仅text_reference.text；输出经原端口校验，原存储/历史上限和有界receipt继续生效。

原domain.read与write/review权限在写入和审核全过程合并复检；实际guard与scope state用于Save/preflight/admission/execute/GET/展示/approve。源失效遮蔽派生输出与审核材料，保留原cancel/reject清理；观察到撤权即回滚原事务，不写未授权FAILED。子调用共用总5秒预算与父deadline的协作式前后检查，不宣称抢占取消。schema6缓存关闭；原request_id保持，响应未知先读原run，不自动重执行。DRAFT只进入原父级人工审核，不自动应用正文或调用模型。

源码 `3d14ade722814ea3b4472c1c166466597f3b53f5`→`494cf355a4057a977e736fee4bb39130881cd089`，树 `8dcd1b875f4dd87b4ac1bd8914ebe48de1a23495`。以已公开媒体组合3d14为基线，只接入原后端 `812910a117e4c392798720ba21669f88cd33ffe0` 的单提交8文件。原补丁字节/patch-id、8后端blob和16媒体blob全部一致，完整16289项树为两增量精确并集，无冲突或手改。媒体新增target_lufs仅在独立MediaExecutionParameters；Graph继续使用原MediaParameters和trim的in_ms/out_ms白名单，schemas1–5能力门禁未扩大。

独立安全审查5反例通过，无P1/P2；初次4过/1个snapshot缺少原interop导入的setup错误如实保留，仅修正快照并补跑未启动的API探针1过，无产品修复。作者原红例/失败及后续通过日志保留，旧27/12/61不重跑或相加。组合仅一次最小检查：真实File持久化/原人工审核/禁用cache1项，加schema6与LUFS/Graph边界门禁2项，**3过/1个PG参数筛除**。无前端改动，未重复TS/build/UI。

**PostgreSQL未验收**：无专用TEST_POSTGRES_DATABASE_URL，未换用其他数据库。Python静态类型检查未运行（仓库未配置工具）；此前8文件语法检查与运行时Pydantic版本/端口门禁证据保留。真实模型/GPU/付费API、完整E2E、跨scope、深层嵌套、历史执行、异步子运行和完整产品均不在验收范围。

仅在指定公开archive追加一个目录，预期父 `2f25ed1aaf4e5d585047d6fd310cb8c35fe3f68d`；不改main/源码PR/Tag/Release，不force。普通archive树不是最新产品源码；RESTORE.md说明唯一3d14前置依赖。公开下载后单独核验7文件哈希、恢复对象/全树与fsck。演示18913/5293、系统账户密钥计费及其他工作区未操作。
