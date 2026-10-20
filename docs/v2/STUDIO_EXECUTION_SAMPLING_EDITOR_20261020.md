# 下层执行流程：原Graph图片采样编辑首片

本片基于固定8e55，新增下层采样表单，仍由原Graph命令、历史、CAS保存、运行及ImageJob执行。没有第二DAG、存储、队列或客户端。只读执行配方说明仍为说明，不代表完整内部工作流编辑器。

## 操作

1. 在独立Studio的创作图打开图片图v4，选择 `image_generate` 节点，操作为文生图。提示词连接及唯一媒体审核节点仍使用原图。
2. 通过原节点服务配置明确选择已存在的本地Comfy配置；在“执行流程 · 图片采样配置”核对本节点配置。不根据手填ID推断能力，不创建配置或安装模型。
3. 填写采样步数steps、种子seed，例如37与424242。未应用输入仅留在当前会话，阻止旧配置保存或运行。留空明确省略该参数，具体默认值以原服务编译配方为准。
4. 点击“应用采样参数到原图草稿”。只更新所选原节点的两项参数，进入原图一步历史，可撤销、重做。服务商、模型、云许可、授权备注、其他参数、来源pin和连接保持原值。
5. 明确保存创作图，再重新读取。保存使用原expected_version CAS，不创建任务；不确定保存仍保留原冲突/回执核对流程。
6. 重新核对运行范围和真实配方。创建原运行后，原计算步骤、媒体预览、许可确认、入队、一次执行、候选核对与审核入库仍分别操作。Graph预览及原Job必须接收保存后的相同配置。

首片以当前配置目录已声明steps/seed的本地固定Comfy文生图配方为边界，识别既有SD checkpoint、FLUX与Qwen Image recipe_id。首条完整File验证使用SD checkpoint；其他模型不因此获得真实推理验收。steps为1至150整数，seed为0至2147483647整数。服务端仍核对具体节点能力与范围，不会忽略不支持参数后继续发送。

云API、未知配方、非文生图或未核对配置不能通过该表单获得内部编辑能力。编码器、加载器、采样算法/调度器与解码节点仍由原固定配方提供，不可在这里新增、替换或连线。

## 失效与原执行边界

表单绑定原身份、图/节点、已核对配置及同步写入代次。草稿/选择/权限A→B→A均不能复活旧Apply。未应用输入先明确放弃再继续核对新来源；已应用内容走原Graph草稿和历史。未决执行由原owner锁住编辑；UNKNOWN保留已发送意图，不自动重发。

编辑前的运行回调同时检查实时未应用表单、原草稿对象及单调mutation epoch。应用后必须重新核对；原Graph版本及来源pin仍由服务端复核。此表单不绕过原授权、隐私、成本或云许可确认。

## 本片验证与限制

新增前端目标覆盖纯参数边界、来源/授权保留、云和未知能力拒绝、原owner应用与一步撤销/重做、CAS保存重开、预检失效、同批ABA与执行未决不重发。TypeScript helper实际产生Python fixture，不能用手写JSON替代生产者。

原File Graph/预览/原ImageJob测试检查新配置37/424242与真实编译KSampler输入、合成Comfy请求一致；旧预览在保存新版本后被拒；合成丢回复产生UNKNOWN且第二次调用被拒，POST总数仍为1。合成Transport不是模型实跑。

原AppShell与真实React组件在1366×768、1440×900、1920×1080的NOVEL/IMAGE/VIDEO共9个几何样本验证共享壳56/44/32、无页面横向溢出或覆盖；图参数应用、撤销、重做、保存和重开走实际owner，模型/运行动作0。没有更新像素基线，没有真实Host/GUI或安装后E2E验收。

真实模型/GPU、PG/并发、Host、Windows安装E2E及全产品发行仍未验。没有重跑全仓测试、生产全量构建、安装、权限变更、push、main、Release或上传；Library403保持停止。

## 单列新增前端源文件及接线

- `frontend/src/creative/studioGraphRecipeParameters.ts`
- `frontend/src/creative/useStudioGraphRecipeParameters.ts`
- `frontend/src/creative/StudioGraphRecipeParameterPanel.tsx`

接线仅在原 `useStudioGraphEditorController.ts` 与 `studioGraphEditorView.tsx`。无需App、全局路由或ExperimentalWorkbench补丁。PUBLIC清单未编辑；现有后端PUBLIC/Docker合同不接收frontend路径，前端源交付由统一整合者另核对。

## 后续同范围：原配方记录值回显

完成首片后，原只读配方说明补充已记录的INT/FLOAT/BOOLEAN标量，例如KSampler.steps、seed、cfg、denoise和潜空间尺寸。0和false是已提供值，不当作缺失；只有已知类的已知端口、类型相符且数值有限/整数安全时显示。文字提示词、未知端口、非有限数及黑盒云内部内容不因此展开。

回显明确标为“配方记录值”，保留“执行未验证”，不把结构声明升级成推理PASS，不改变只读props或赋予新执行能力。显示来源仍是原预览/Job已校验的execution_recipe，未知或过期时依原owner隐藏。该小片增加5个专项用例，并复验受影响的38个原说明测试；不是重新运行全量产品测试。

下一步若要编辑cfg、sampler_name、scheduler或内部编码/解码组件，当前固定图片配方构建器尚未开放这些命令字段，需要原适配器参数白名单、能力目录及共享生产契约的协调变更；本前端独占切片不会伪造这些可编辑能力。
