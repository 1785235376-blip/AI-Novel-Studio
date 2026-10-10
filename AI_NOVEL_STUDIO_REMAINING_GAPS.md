# AI Novel Studio Remaining Gaps

## 执行期间待关闭

- DONE（已关闭）：本机UI Agent可信身份入口；显式password验证和LOCAL_HOST绑定已实际运行Reviewer成功，解绑完成；原匿名401/团队隔离保持，身份切换立即清除旧缓存。没有静默注入请求头。
- PENDING：最新Windows Application/package。原本机旧basePython3.12.10与批准3.12.9不符，旧包缺当前pypdf及新增jsonschema。正在从已验证PR45恢复approvedbase、精确补全wheel/hash/许可并构建fresh源码包；旧PR45安装包不能当最新实现证据。
- PENDING：最后代码freeze后的严格File/PostgreSQL完整回归与source/outcomes/JUnit reconcile。目前Windows过渡suite故障和修复证据保留。Linux环境独立准备，不新增skip、不改原断言。

## 产品能力的实际边界

- PARTIAL：文学篇幅与节奏。真实生成1064汉字，超过提示700–900字，并较早透露毁城身份。Reviewer/Verifier有真实发现/建议；作者必须审核。不能把流程PASS称作文学质量PASS。
- PARTIAL：确定性一致性覆盖人物已死/失踪/年龄与秘密、显式world forbidden terms和ISO start>end；任意自然语言世界规则、全部时间表达/心理矛盾无法宣称完整自动检测。原Verifier提供模型检查，仍是建议。
- PARTIAL：新startup候选应用限定原local project scope；collaboration branch没有对应的项目World/Story跨域应用owner，因此新startupapply明确拒绝越界。已有collaboration/CAS/branch guard保留，不能把此边界称为支持全分支startup。
- PARTIAL：其他Provider未在本轮配置实际账户/本地服务。接口与回归保留；仅本机Qwen真实推理通过。8192上下文admission目前映射PROVIDER_UNAVAILABLE，错误分类还有改善空间；16k实际配置已跑通。
- PARTIAL：1431有效历史Actions artifacts全部索引，相关最新exact-head33个已完整恢复和校验；其余历史bytes正在实际下载与逐包digest/ZIP CRC验证，总索引约27.7GB；尚未完成前不能称每个artifact的内容都恢复。Git/code/docs/tests和有关旧独有commits已保留。
- BLOCKED仅环境：本机Windows无SeCreateSymbolicLinkPrivilege，原symlinktests不能创建fixture；Linux /proc原检查在Windows不存在，原ZIP路径问题已通过生产orig_filename拒绝和原断言不变的真实raw ZIP fixture修复、29/29通过。保留真实失败，不通过跳过或改断言伪造Windows fullgreen；最后Linux严格suite用于完整验证。

原DENY_ALL插件执行隔离、unsigned acceptance package和外部model配置等原产品边界保持。没有把旧Windows AppContainer prototype重新激活为生产执行能力，没有签名/公开release/合并main。

已关闭恢复过程缺陷：冻结V1 generator/parity-manifest精确回到PR45，原37 V1文件+26 shared-prep hash checker与184 Linux契约测试通过；scope正确的新runtime base原4876记录全保持，仅增加6wheel的210声明文件与1独立许可索引。新的最终完整suite/package仍在执行。单节点冷启动合成diagnostic曾因Pydantic延迟serializer import在全局forbidden补丁下失败；该RED保留，原routing完整43测试及原顺序2节点报告生命周期证明通过，不能将辅助冷诊断写成GREEN。
