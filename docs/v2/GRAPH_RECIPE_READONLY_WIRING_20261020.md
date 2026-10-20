# 原运行配方只读说明接线

保留作者提交 `38da1f16b3baab605a9463a904afea22a7c8546b` 的四个新文件历史。合并提交 `2a020a04e8beed24ff3e26c3df97e7878647d28b` 的另一亲为双参考图切片 `a164e827f8b9fe82d6b53e1b8215a2994ff3c460`。

本线在接线前独立读取固定 Git 对象，并用已通过中文双参考图 File 链路的原 Job.context.execution_recipe 核对真实 10 个 workflow 节点、LATENT/IMAGE 类型、失效时不读取内容、操作不匹配隐藏、HTTP 不补造步骤、未知端口保留 UNKNOWN。没有继承作者测试作为独立审核。

`StudioGraphMediaExecutionPanel` 只将原当前预览的 `production_preview.execution_recipe` 交给 `StudioExecutionRecipePanel`。原 Graph Job 窄投影不含配方，因此不会读出或补造该字段；原预览缺失时明确不可用。完整 ProductionJob 的 standalone 组件消费方式仍由原类型支持。

展示同时要求原 current 有效、运行非 stale、原图 ID/版本匹配运行、没有锁定或未知回执、当前节点操作与配方操作一致。原节点切换直接更换投影，不缓存旧配方。结构说明和原 JSON 明细共用该条件；缺失信息不表示通过。Job 状态、provider/model、来源及所有执行操作仍使用原面板和 owners。

配方中的编码、采样、解码只代表已提供结构，没有逐步骤执行回执。组件不创建、保存、执行、请求或轮询任务，不重新验证摘要，不修改运行合同。

针对真实原面板新增九项集成检查：正常预览、scope/图版本/stale/锁定/不确定/操作变化隐藏、节点切换、派发后窄 Job 与缺失预览。作者四文件 38 项专项也在组合环境复核。类型检查曾发现将窄 Graph Job 误当完整 ProductionJob 的错误，已按真实合同修正；原始失败日志保留。

这不是 Host、PostgreSQL、真实 provider/GPU 或完整 Windows E2E 验收。已审0574归档不包含38da、本接线或双画布新切片；归档线独立审包，本线不上传。
