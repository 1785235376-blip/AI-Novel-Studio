# TaskCenter 生命周期／真实游标：M0 执行阻断检查点

日期：2026-10-26（Asia/Shanghai）。状态：**M0_EXECUTOR_BLOCKED / AUDIT_ONLY**。

本轮没有完成实际 HTTP 第一页或续页，也没有新增产品代码、生命周期持久写入、
迁移器、测试代码或另一套未接线组件。新授权已允许必要原 owner 端口；
当前阻断是执行能力，不是缺少修改 owner 的授权。

## 固定来源

- 固定提交：1587b57791cbdc3e46f0c09fedea83072e6a8d28
- 逐字核对 Git commit tree：826d0b2917720dacf72ecbccbf3f961b9172f5b9
- 旧分支远端 HEAD 仍为该固定提交。
- 对照基线：ffe1937911cff32d4ebd4770b350674627501d3a
- 新分支：work/taskcenter-lifecycle-cursor-20261025，从固定提交创建。
- 根 AGENTS.md、上轮接口说明和独立评审已读；完整固定 tree 只有根 AGENTS.md。
- 未建立云端 checkout，工作目录／未提交修改状态未能检查，不能声称干净工作区。
- 没有访问用户旧目录或使用用户本机执行后端；没有 reset、强推或改动 main。

## M0 实际结果

本轮首先请求最小命令 Get-Location，执行器在创建进程前返回：

```text
exec_command failed: CreateProcess {
  message: "Rejected(\"Failed to create unified exec process:
  exec-server rejected request (-32603): helper_unknown_error:
  setup refresh had errors\")"
}
```

独立审查单元复核同样失败。当前工具目录没有可调用的
cloud_environment.environment_status，也没有其他已绑定的云端 shell/Python 执行入口。
GitHub 原始 commit 和文件读取正常。

| 检查 | 本轮状态 |
| --- | --- |
| 固定 SHA/tree、GitHub 读取 | VERIFIED |
| 云端命令入口 | BLOCKED_BEFORE_COMMAND_EXECUTION |
| Python／仓库依赖探测 | NOT_RUN |
| 最小原测试 | NOT_RUN |
| scripts/verify_taskcenter_consistent_query.py | NOT_RUN |
| 本轮 HTTP／并发／双进程／强杀／性能 | NOT_RUN |
| 真实 PostgreSQL、Windows 产品、前端、模型 | NOT_RUN |

没有再次触发或重跑被锁定的 GitHub Actions，没有改 workflow、账号、安全设置或付费。
没有创建替代 Codex 云任务。原有 workflow 只匹配上轮不同分支，本次仅文档归档。

用户提供了另一云环境对上轮原版脚本的结果：基线原测试 65 通过、回归 198 通过、
旧基线上新增红测 12 项预期失败、候选定向 190 通过、回归 198 通过。
这些组有重叠，不能相加。本轮没有独立取得其原始日志，也没有重跑；
保留为用户提供的上轮外部验证，不把它写成本轮执行或 HTTP cursor 已完成。

## 实际工作单元

实际使用五个工作单元：原身份／项目／权限生命周期审计、选定任务原 store 审计、
HTTP 合同准备、独立对抗审计、负责人整合。没有并行修改共享产品文件。
各单元都只读固定 GitHub 源码；本检查点只提交审计与接口准备材料。

## 已找到的具体落点

最小候选仍是 File + 原开发 loopback local 单 principal + 无 token/branch +
现存合法项目 marker + 显式 authority=semantic_import。
这是**待实现／待验证的候选**，当前 HTTP 仍是 501。

1. 原 ExperimentalStore File transaction 只有一个 scope 文档替换提交点；
   可研究把原项目绑定与选定 collection 生命周期元数据放入同一文档，和业务变更一起提交。
2. task UUID/version 本身不能证明强 ABA。所有参与原 writer 都必须经过同一提交维护，
   且要处理跨实例同线程重入和提交前冲突；不能仅“持锁后 +1”。
3. 项目删除只退役 novels/nid 目录及权限／scope，**不删除 experimental_v1 scope 文档**。
   新游标首次读取也要核对文档属于原项目 incarnation，不能只绑定当前新 marker。
4. 缺元数据的旧文档继续旧 offset 行为；查询不创建 marker、不迁移、不修复。
   显式迁移也不能只凭相同 nid 把旧文档认领给新实例。
5. 整份 scope 文档代次会让其他未选来源影响 semantic 游标，存在侧信道风险；
   候选应只绑定已授权选定 source 的原生命周期。per-collection 也不能泛化到有逐行隐藏记录的 owner。
6. 原 HTTP 的初始 access、FastAPI 参数校验和全局 middleware 拒绝不全在 endpoint try 内；
   所有 no-store 路径必须分别实测，不能靠局部 catch 宣称覆盖。
7. 实际同文件 atomic replace 不等于跨文件事务，也不等于断电／满盘证明；
   原 atomic_write fsync 文件但没有父目录 fsync。物理故障仍 NOT_RUN。

详细入口、接口候选、反例和限制见 owner-http-preparation.md 与 independent-audit.md。

## 继续条件及未完成里程碑

M0 必须先在当前授权云执行器实际探测 Python、依赖并运行原测试／隔离验证脚本。
在此之前停止扩大量产代码；按用户 M0 条款只保留只读审计和接口准备。

| 阶段 | 当前状态 |
| --- | --- |
| M0 | 执行器阻断，未通过 |
| M1 | 固定源码生命周期审计／模式条件已准备，非运行证明 |
| M2 | 最小原 owner 端口候选已列出，未实现 |
| M3 | 真实 HTTP 成功闭环未实现／NOT_RUN |
| M4 | 协作与第二来源未实现 |
| M5–M8 | 错误／进程／崩溃／回归门槛已列出，全部 NOT_RUN |
| M9 | 仅本阻断检查点与审计已归档，不是产品交付完成 |

下一步所需是可用且符合用户云端限制的执行入口；不是再次扩大 owner 编辑权限，
也不是把原 501 文案改成 supported。恢复执行后应从 M0 实测继续，沿用原组件，
完成一个真实可用垂直切片再扩展。
