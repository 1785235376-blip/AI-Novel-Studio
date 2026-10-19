# PoemSeed Studio V2：普通图片 PAGE→Timeline 与 Host 安全退出限定归档

本目录仅追加归档，固定产品源码 **333f384a125068a4e7714b347f687f5dc2034123**；父源码为 afadce662a36972e46d60286a9e43fbce31fb6fa，源码树为 **89e5548014d64063cfa77bfe2e08c4a101dd6c3f**。归档分支目录外的源码树不是这一产品快照；请按恢复材料取得固定代码。

## 已验证范围

普通、已审核、未绑定 lineage/私有来源的 PNG/JPEG/WebP 图片可用于已审核 PAGE，明确选择、预览、确认后，经原 Asset/Timeline owner 建立未批准的 Timeline 草稿。原请求 ID 可在刷新并通过原 Host 入口重验后明确读回；两次打开原 Timeline 均保持同一记录。没有自动审核、模型调用、视频执行或隐式重发。

Host 身份失效前，原媒体、Timeline 及嵌套生产控制器的 UNKNOWN、原请求标识和安全作用域在清理前保留。离开需要独立 UNKNOWN 确认，未保存输入仍另行确认；忙碌、权限、ABA、晚到结果和重复应用保护保持。原审查者将原 UNKNOWN 反例逐字重跑转绿，已关闭 P2，未发现本限定范围的新阻断。见 [独立审查投影](INDEPENDENT_HOST_REVIEW.json)。

## 证据

- Host 窄修及相邻回归共355个不同用例通过。17个未修改 storyboard-editor 失败已在隔离 afad 基线复现，用例名和失败消息完全一致；未降低断言。原 TypeScript 配置与生产构建通过，保留原大 chunk 警告。
- 固定333f的原生产构建 + 原 app.main File 后端浏览器旅程通过：107次 API 调用、3次原 Host 验证、1次交接创建、按原 ID 恢复、2次原 Timeline 打开；无 API 拦截，pageerror为0。只使用新建合成普通图片和 PAGE。
- 后端更换为新进程后再审计：2张派生 PNG 与预览、磁盘、原 HTTP 下载逐字节一致；原合成来源像素、PAGE 内容/版本/审核状态未变；原请求与 Timeline 恢复一致，作用域文件 SHA256 未变。自建端口/进程均已关闭，其他在途服务未触碰。
- [真实链路结果](evidence/real-browser-333f/REAL_BROWSER_RESULT.json)、[网络证明](evidence/real-browser-333f/NETWORK_PROOF.json)、[新进程持久化/字节证明](evidence/real-browser-333f/PERSISTENCE_PROOF.json)、[六张截图总览](evidence/real-browser-333f/SCREENSHOT_CONTACT_SHEET.png)、[2110项源码及构建指纹](evidence/real-browser-333f/FIXED_SOURCE_SHA.json)。
- [日志](logs/)均有[原始/公开副本哈希](ORIGINAL_AND_SANITIZED_HASHES.json)。原始敏感 Host/session 记录及 trace 只留本地，不公开；网络投影明确省略认证请求/响应体，真实凭证值不进入公开文件。

## 代码与恢复

唯一外部 Git 前置为 **9b6809ea76ccd7915ecb2fe52a4f41bf179d2b35**。本目录保存精确333f及已验收后端65的 bundle、20提交代码/测试 mailbox、[逐提交来源映射](SOURCE_MAP.json)、[49个最终变更文件指纹](CANDIDATE_FINAL_FILES.json)及[恢复说明](RESTORE.txt)。Mailbox 用于审阅/等价源码恢复，不保证原提交 SHA；精确身份以 bundle 为准。

已在只拥有公开9b、无 alternates、初始不存在333f的新仓库恢复，严格 fsck 通过，183个新增对象集合精确匹配；完整物化并校验16224个跟踪文件的 Git blob，49个最终变更文件逐字节相同。见 [恢复核验](RESTORE_VERIFICATION.json)。恢复期间没有重跑355或全量测试。

## 保留边界

**这不是完整 V2 验收或正式 Release。** 保留17个本轮精确基线失败、历史18个相邻基线失败、Windows symlink1314阻断、11个平台skip与旧waveform基线失败，详见[失败/跳过/限制台账](FAILURES_SKIPS_AND_LIMITS.json)。PG、Studio/ORA/私有来源/lineage扩展、真实模型/GPU、外部编辑器以及新NLE切片均未验收。含IME P2的 **cb93855f067575595a3ee3845b6e05670e831e1f** 不在 bundle/patch 中。

不包含撤回的 owner-copy/binding-clearing WIP、模型、依赖、运行数据或NSFW专属后端增量。唯一远端写入范围是本次新 artifacts 目录；不变更 main、源码分支、PR、Tag 或 Release。
