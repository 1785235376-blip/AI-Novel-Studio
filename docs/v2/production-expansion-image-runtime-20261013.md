# Production Expansion 2：图片运行时与原审核链

日期：2026-10-13（Asia/Shanghai）。输入基线
`c911e549143d4b4187afc056079da30221aa1e97`，PR47保持Draft，不合并或发布。
本阶段仅深化Image；QingJian暂停，Video未进入。

## 实际代码

- 原ModelCenter／AssetProviderRegistry新增固定ComfyUI SD checkpoint、FLUX.1、Qwen Image配方。根据实际object_info的节点、输入／输出类型、枚举、loader组件与连接证明开放能力；缺组件、类型不符或组件歧义拒绝，不以模型名称授权，不下载或启动模型。旧最小SD/A1111注册保持原T2I公开形状。
- A1111普通扫描保留原探测次数。用户明确validate时读取已声明的OpenAPI元数据，只有闭合img2img／Mask输入证明才开放I2I/inpaint；已启用rich注册在扫描与dispatch重新核对该证明。配置列举不探测、不读凭据、不执行。原workflow_prerequisites报告保持旧一行；新固定配方另述并进入原scope指纹。
- 原ProductionExecution/ImageJob支持显式image_source、最多5个总图片输入、image_references的正权重及mask_source。所有来源必须对应同序原Asset ID／version／digest；重复、闲置、错序或其他owner拒绝。新字段未设置时省略，旧schema1/2/3、原参数默认值与请求身份保留。
- Comfy多参考图采用**WEIGHTED_PIXEL_INITIALIZATION**：权重进入实际ImageBlend归一化链后VAEEncode生成。它不是IPAdapter、原生多参考语义或人物一致性质量保证。I2I基图权重1，最多4个辅助参考；A1111只支持单图初始化，拒绝多参考而不忽略权重。
- Inpaint绑定原图及已有正式手工二值Mask，重查不可变作者origin／原图版本／摘要／scope／incarnation和实际PNG。沿用**白色保留、黑色重绘**，Comfy固定InvertMask→VAEEncodeForInpaint→ImageCompositeMasked；A1111固定反转、零blur及原图尺寸。原图不被覆盖，输出仍是原任务的私有候选，只有明确review才转为正式Asset版本。Mask仅支持原64–1024、8倍数的窄PNG范围。
- Mask来源检查覆盖原子入队、执行、发布、恢复及审核，最后提交再次检查asset_lineage权限。上传／元数据／prompt／history／下载前后复用原Host、注册及来源guard；撤权或不确定发送不自动重放。无任意workflow、文件路径、argv或凭据入口。
- 参数只按实际配方开放：Comfy非T2I使用输入尺寸，拒绝未实现的尺寸调整；FLUX cfg=1不宣称negative_prompt有效。steps、seed、denoising_strength按闭合范围进入实际采样。
- Graph新增明确选择的图片schema4：Asset→Reference→Prompt→ImageGeneration→原MediaReview→正式Asset。纯节点只持版本化来源与Prompt，不复制像素／创建资产；输出在原Asset authority下重新计算。保留原Workflow调度、24节点预算、CAS、请求摘要、审核和UNKNOWN恢复，没有第二队列。
- 超分仅有闭合`ReservedImageUpscaleInput`／adapter协议，原Graph目录明确`image_upscale_execution=false`。没有可执行operation或模型加载，不把占位当能力。

## 前端与Opus边界

原独立制作controller增加来源角色、权重、作者Mask选择和对应严格回执解码；原Graph editor必须明确读取图片目录、确认切换schema4，不自动迁移旧图或删除不兼容节点。改来源／权重清旧preview及同意；preview、create、execute、private candidate、review仍分别操作。原旧Graph标签9项保持，新schema4标签独立。

Opus可改`StudioMediaExecutionPanel`、`studioGraphEditorView`及布局；必须保留
`useStudioMediaExecution`、`useStudioGraphEditorController`、严格clients、Host传输、父级mutex、scope/Host generation、dirty/UNKNOWN、CAS与来源版本保护。原DS shell／tokens／primitives未改；新控件专业视觉验收尚未完成。

## 验证与失败保留

最终冻结源码验证结果见本阶段同名JSON摘要。原始日志、数据库、环境配置、主机路径与失败证据保留在私有本地目录，不随源码公开。

代码／测试输入tree：`6d101abef220e566b281b2983f390df79c866fd1`；1924个输入文件在各次最终检查前后哈希一致。工具为Python3.12.9、Node22.14.0、PostgreSQL16.15、FFmpeg8.1.2。

| 实际执行范围 | 最终结果 | 边界 |
|---|---|---|
| 30个相关模块，Windows File | 1126 passed / 4 failed / 357原适用性skip | 两个symlink前提、一个POSIX sysconf前提、首次Bash路径前提失败；完整FAIL保留。 |
| 相同范围，独立真实PostgreSQL | 1126 passed / 3 failed / 357原适用性skip / 1明确NOT_RUN | 一个已记录Windows symlink节点未执行；其余失败是scope symlink、sysconf、首次Bash前提。未改skip或门禁。 |
| 上述六个新增图片模块子集 | File、PG各136 passed / 49原profile skips，零失败 | 已包含在宽范围结果，不可相加；真实owner/PNG，模型HTTP为合成。 |
| 完整前端 | 2973 passed / 8原skip | 类型与Vite构建通过；原token guard52文件通过。 |
| 原metadata检查 | 44 passed / 2 Windows symlink前提失败 | 原两个断言在独立Linux环境分别通过，Windows失败不改判。 |
| 独立原始前提补充 | Linux先3项、另2项原断言通过；补齐Git Bash路径后原2项通过 | 范围重叠不汇总，不代替Windows或完整CI。 |
| 原Playwright shell保护 | 7 passed | 三模块原截图、四尺寸geometry；未更新批准基线，不代表新控件视觉验收。 |

PG数据库在应用迁移前证明为空，使用原20个迁移，检查后正常关闭自有cluster；未接触用户数据库。Linux补充前后Ubuntu均为Stopped，仅删除带marker的自有临时目录。原始运行回执与源hash保留。token检查本身PASS且来源未变；外层捕获曾撞到Vite瞬时配置文件，按原完整回执核对后收束，没有修改检查器或重跑制造绿色。

API为2219个实际mounted操作，清单13627个收集节点、原冻结9151完整保留；收集不等于通过。原生成器、旧测试断言、timeout、skips、CI gates、V1冻结manifest与Interop未改。新增生成文件与源码一并提交。原c911五个CI运行合计29 jobs均failure、runner_id=0、steps为空，未执行测试；新提交CI另行记录。

首次统一File为518passed／1failed／612setup-errors／356profile-skips，首次真实PG为518passed／1failed／611setup-errors／356profile-skips；缺少私有runner的pytest临时父目录导致setup与对应前提失败，未改产品断言。首次全前端2948passed／22failed／8原skip：20个Python命令前提、1个cwd前提、1个原Graph标签9项的真实兼容回归。运行环境和该标签实现修正后才重新冻结，不删除这些失败。

前期新测试的Asset scope、默认reference_only、CPU专属proof、缺basetemp与异常类型前提修正，及原prereq报告行数／额外探测次数回归均保留前后证据；原断言与超时未改。新发现的原子入队来源检查与审核最后lineage撤权问题通过代码修复和针对性用例覆盖。第一次覆盖清单刷新与API生成并发，捕获source drift并拒绝；后续按稳定输入顺序生成，不修改生成器或冻结基线。

## 仍未验收

Image整体**PARTIAL**，实际模型／质量／Windows／GPU均**NOT_RUN / LOCAL_REQUIRED**。合成HTTP与真实File/PG/CPU PNG检查不等于ComfyUI/A1111实际推理。没有模型安装／下载／权重加载、付费API或Windows最终安装验收。

原M4→M9门禁、F00 INTEGRATED＋39 PARTIAL、独立复审BLOCKED、历史PG/CI失败及V1.X/Local Interop1.0均保留。全产品、Router财务、专业UI、原生语义参考适配器、outpaint/repair及超分执行仍有缺口。此前c911 CI的runner未执行问题与新提交CI分别记录，不宣称完整CI通过。

固定配方来源：[FLUX官方教程](https://docs.comfy.org/tutorials/flux/flux-1-text-to-image)、[Qwen Image官方教程](https://docs.comfy.org/tutorials/image/qwen/qwen-image)、[官方Qwen模板](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image.json)。这些是配方依据，不是本机验收证明。
