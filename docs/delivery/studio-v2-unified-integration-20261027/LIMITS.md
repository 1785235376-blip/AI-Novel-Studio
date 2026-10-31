# 范围、失败与未运行项

以 [DELIVERY.md](DELIVERY.md) 和 [SOURCE_FREEZE.json](SOURCE_FREEZE.json) 为当前结论；M0、M1–M3 文档保留当时状态，不覆盖最终冻结结果。

- PASS 范围：原 File 模式 A+B+C 集成；IMAGE 单节点 preview/create/execute/candidate/review/正式回填/重开/重启；真实前后端/HTTP/Chromium、确定性本地 Mock provider。显式审核控件由自动化模拟用户确认，不是 AI 图像质量验收。
- TaskCenter local 混合仅 semantic_import+exports，原 import200/export100 有界窗口保持。协作 exports/混合、任意组合、PG/packaged 混合继续拒绝；300 是观察上限，非无限查询能力。
- Windows 资产列表稳定游标在最终冻结点仍返回503；此组1失败/1控制通过，明确 OPEN。资产引用/预算成功不能替代此项。
- 前端全量 C329失败、c479集成297失败，各只跑一次；最终build及119受影响测试通过。最终全量未再跑，跨语言scanner输入有后端变化，不伪称全量绿或所有输入等价。
- 项目列表清理确认的通知合并窗口在C同样复现，OPEN。保留原始新增失败观测和双向instrumentation，未以重跑通过抹掉失败。
- F37个历史未明拒绝的根因仍OPEN；G及本轮通过不说明它已解决。
- 旧PR47/48不同/缺失内容已逐路径库存，仍有协调工作；不整体纳入，不称全部过时。测试发现guard/manifest和音频/public/director历史测试待适配。
- 音频历史恢复PARTIAL，未整支合入，不开restore写端，兼容及项目历史容量计费待修。
- 本机上下图与连线是草稿；正式IMAGE为单节点任务关联。VIDEO执行unsupported，完整多节点图编排/Studio V2整体发布未完成。
- 本次授权环境为全新隔离Windows目录。Docker/psql不存在；PG、容器/其他操作系统及真实模型/GPU未运行。未动用户本地GPU、旧项目、真实素材。
- 浏览器身份为真实local-session接口验证后的合成Host显式绑定，非正常登录UI验收；种入本机合成图是测试准备，不将其宣称为未保存草稿冷恢复。权限撤销/actor延迟/来源变更另由真实HTTP与owner反例覆盖；不称每项都在浏览器重复。
- 三代理显式gpt-6-astra配置获接受，额度中断后恢复；服务端模型ID/主会话模型切换不可独立核实，未宣称切换成功。
- GraphFlow要求context/plan/index接口不可用；实际可用gf_read已用于新目录，未宣称index完成。
- Hosted Actions零run或旧零steps失败均NOT_RUN，不是CI通过。未手动触发付费CI、增购、部署、Release或合并main。

main准备度 NOT_READY。采用/回退只通过新的正常提交/PR；不reset、force push、删原分支或改写共享历史。
