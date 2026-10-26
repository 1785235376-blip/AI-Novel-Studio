# TaskCenter：File/local 双来源游标

基于已发布单源切片的本地 `978059432a3dee2bd8ebee5645aafc7e13b4bbb8`（与远端 `31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f` 同树）。最终生产冻结 `c68857c59d50dfe90b8edc5e88e8de2cc81d5fc3`，app tree `7e357c95629c255854e4287e02c4c57777097573`。

## 支持范围

两个既有 `/api[/v1]/novels/{nid}/experimental/workspace/tasks` 入口，显式 cursor 模式，仅实际 File、非 packaged 的原 local 模式，同时选择 semantic_import 与 exports。别名/重复 authority 仍按原查询解析规则规范化；顺序使用原 reader registry，不采用用户参数或字典排序代替。

- 原 semantic_import 最多200条，原 exports 最多100条；先执行各自原授权/上下文/源窗口，再执行原 TaskCenter 安全投影与筛选。
- 聚合 observed_total 仅表示当前有界观察窗口，最多300，不是全部历史；source_truncated 保留原语义，coverage 仍不承诺全覆盖。
- 绑定 authority 限定的行标识/nonce、各源文档 incarnation（含空源）、原 reader 顺序、原根路径与项目 incarnation。只绑定实际选中安全行，不把无关 actor 或隐藏 tail 的行变化升级成全局失效 epoch。
- 复用已有查询引擎、单源组件与原 reader；聚合前、后及返回前重新观察，原授权检查保留。最终读取期间换 registry/原源实例会拒绝。
- `WorkspaceToolsService.tasks` 增加私有、默认 None 的 request-local observer，只记录实际选中 reader 本次处理完成与否，不添加公开参数或全局状态。混合游标拒绝缺失、重复、顺序/实例不匹配及失败回执。正常 offset 调用仍保留原403/404来源省略语义；observer 自身异常不吞成可用性诊断。

## 发现并关闭的问题

独立反例发现最终组件读取中 reader 顺序可改变，以及原聚合静默省略被拒绝空来源后仍可能签发游标。最终生产代码补充最终 registry 核对和**实际聚合调用**回执。只做单独前置探测不能证明聚合成功，故中间 `5349824` 被明确否决，未用于最终验收。最终用只在真实聚合栈内拒绝403/404、其它探测正常的空/非空来源反例验证，首屏501、续页409，避免把失败来源绑定进 token。

## 范围与限制

仅改五个生产文件：`app/experimental/api.py`、`taskcenter_cursor_http.py`、新增 `taskcenter_local_mixed_cursor.py`、`taskcenter_query.py`、`ux.py`。没有改 `app/api.py`、store、identity、scope、mutation coordinator、前端/SDK、Work资产引用/资源守卫、音频或制作执行所有者。没有合并 Work 新分支。

原单源200/100上限不变，其它模式不会因混合300上限扩大。collaboration 模式没有 exports 或混合支持；不把 local 重新命名成协作。观察不是跨所有者原子快照，不承诺完整 ABA、任意外部备份回放、掉电耐久性或活跃执行器独占权。旧无绑定生命周期的数据仍 fail closed；GET 不构造导出服务、不触发 startup recovery 或真实后台导出。

## 验证与证据解释

最终验收使用独立不可变 checkout `b00bf27525df9a8f2a8933ea4498cfc1b31596ad`（与 c688 app 相同），保存全部606个 app 文件的前后 SHA256、精确命令、exit code、JUnit 和已加载模块来源。独立45项在单独不可变克隆运行。各组有重叠，禁止加总。

`historical-evidence` 保存基线/早期候选以及两次旧900秒超时。旧运行期间实现目录发生变化，均不是最终验收；其中一次有未定位完整堆栈的 F。按测试位置推测的取消任务用例已在最终不可变198组通过，不能据此声称旧 F 的根因已定位。独立证据保留两次真实 RED、一次错误测试预期、所有中间及最终运行，不隐藏失败。

执行环境为 dot 原生云工作区和合成夹具。真实模型、付费资源、用户导出、托管部署、CI均 NOT_RUN。此切片独立交付，上传由父线程另行审核与取得授权。

最终结果：原安全/媒体/Agent/导出/API消费者组198 PASS；TaskCenter组312 PASS；独立组45 PASS（10+35不重叠）；另针对回执与精确聚合拒绝的先行20 PASS包含在TaskCenter组中。以上各组有重叠，不累加。均exit0，无超时，无外部app模块混入；最终app源码前后哈希相同。
