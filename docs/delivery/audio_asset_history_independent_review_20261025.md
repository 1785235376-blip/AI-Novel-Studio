# Audio Asset History 独立审核报告

审核日期：2026-10-25

基线：`11d8615cccb688462ff814d025b339e1b6eb0efe`

最终实现：`2e2fcb79209a3afc03dc7e443f5e1901ff233ee1`

审核方式：固定 SHA 源码及提交差异独立审阅；未修改生产代码、测试或持久数据，未独立执行测试。

**结论：已实现子集有条件 PASS；完整 M0–M7 为 PARTIAL。** 最终已读范围内没有尚未关闭的必修发现。历史恢复候选创建、确认提交、持久幂等回执及真实审核接入没有完成，不能宣称完整恢复功能通过。

## 已核实的实现边界

- 原 Asset owner 的直接 metadata 写入口已覆盖：create、review_text_result、update_metadata、promote_owned、delete、restore；lineage 经原 metadata 更新入口。原二进制写入仅在 create，没有新增同 ID 覆盖接口。
- 当前 metadata 中的历史 head 是唯一可见提交点。历史 record/blob 独立保存，未连接 head 的准备对象不作为历史呈现；原 create 异常清理原二进制不会删除独立历史 blob。
- 首次迁移只捕获可验证的当前状态；变更前完整 metadata 先被保存。缺失的更早版本明确为历史缺口，不从任务列表或时间戳伪造。
- 读路径验证历史链、metadata 摘要及版本连续性；下载验证选中历史 blob。写入在提交前检查链累计大小，避免成功提交随后无法读取的 head。
- 三个 owner 公共读取入口均复用或创建原 query budget。HTTP 另有请求体、metadata、来源遍历与时间限制；这些限制不能表述为所有文件读取共用一个单一的 8 MiB 总预算。
- 历史隐私按每个快照独立判断。来源旧 pin 必须先通过当前来源授权，再匹配其历史版本与摘要，并重新校验旧快照的 actor/scope；当前 formal 状态不会授权读取旧 private 快照。
- 原生成 private candidate 仅其 creator 可见，且校验原 production origin 的 actor、job、scope、incarnation 与 request digest。没有放宽原通用资产详情或审核入口。
- 路由最外层使用 existing_owner_only()，覆盖原 invoker 的首次 incarnation 读取；返回前重新核对权限、特性与来源。File 指纹包含原权限/身份文件状态；PostgreSQL 指纹纳入原授权表和 user/membership 的 xmin，覆盖支持的无 audit membership 更新路径。
- 恢复预览不颁发执行凭证，不创建候选或回执。confirm/resolve 经原授权后固定返回 admission-unavailable；代码中不存在隐藏的 create/promote 通路。Canvas、Timeline、Canon 与 pins 不被改写。

## 审核发现与关闭情况

| 发现 | 最终状态 |
| --- | --- |
| 写入未按读取链累计预算 admission，可能提交不可读 head | 已修：提交前按规范 record 实际字节累计检查 |
| 当前 metadata 的 owner 读取可能无界 | 已修：list/detail/content 全部覆盖原预算上下文 |
| PostgreSQL membership 支持无 audit 更新，原三表指纹漏掉该 ABA | 已修：纳入当前 user/membership 行及 xmin；仅源码验证 |
| 恢复预览直接复制嵌套 display 字段，可能泄露损坏 metadata | 已修：复用闭合投影，仅接受有界 scalar 文本，拒绝控制字符及 filename 路径分隔符 |
| 恢复写端无法同时满足原项目 quota 与严格禁止全库扫描 | 未冒充解决：写端明确关闭，完整恢复保持 PARTIAL |
| 原 Production review 不能接管历史新候选 | 未绕过：没有开放候选创建或审核 |

最终修复提交的反例断言已审阅：三个 owner reader 的超大 metadata 拒绝、两个 preview 嵌套字段拒绝，以及绑定真实项目 incarnation/owner lease 的双进程 CAS；没有通过削弱断言关闭发现。

## 验证证据与限制

协调执行方记录：新增反例修复前 **4 failed、1 passed**，修复后定向 **6 passed**；最终四个专项文件 **58 passed、3 warnings，exit 0**。本审核查阅了对应提交与测试变更，但未独立执行命令，因此这些数字属于执行证据，不属于审核者复跑结果。

两个原 query/cursor 案例仍返回 503；协调执行方已在固定原基线的新 detached worktree 重现同样失败，并定位原 index fsync 的 EBADF。这两项不计通过，不能据此宣称完整 query 兼容验收完成。

必须保留以下交付限制：

- 恢复写端、候选持久幂等恢复及审核接入未完成。
- 来源支持当前明确实现的 ASSET 范围；其他来源类型拒绝。
- 来源历史 pin 的证明是 metadata/版本证明，content_verified: false 不代表来源二进制已验证。
- 当前资产软删除期间历史读取不可用；原 undelete 仍保持撤销软删除的含义。
- 历史容量、版本上限或内容损坏会新增 audio delete/undelete 拒绝情形。
- cursor 使用进程密钥，重启后失效。
- 原 current metadata 原子写没有父目录 fsync，不能声称断电持久性；审核结论限于已实现的进程崩溃一致性。
- PostgreSQL 运行、物理磁盘耗尽、断电、真实 Provider/模型调用未验证，均为 **NOT_RUN**。
