# Production Expansion 1：原 Model Center 本地图片路线接入

日期：2026-10-13（Asia/Shanghai）。本阶段是开发提交，不是产品发布。
接管基线72765972，审计先提交并上传39a38ed8b90f0a0f74d2a16d245f6315b0f7a21e，
之后才修改产品源码。[接管审计](../../AI_NOVEL_STUDIO_V2_CODEX_HANDOVER_AUDIT.md)
列出原owner、当前API边界、全部模块缺口和后续顺序。

## 实际实现与保留边界

原ModelCenter已验证、注册并明确启用的本地IMAGE **T2I**，现在可以从原
`ProductionExecutionService.providers`选择并沿preview→原ImageJob入队→明确
execute→私有Asset候选→人工review→reopen。没有第二个registry、Project、Asset
或任务系统，没有新增production API、operation或Graph参数。

`LocalImageAdapter.studio_configuration`只读原注册状态；列举不probe、不读取凭据、
不启动Runtime。冻结注册快照、原wrapper/registry实例、enable生命周期/control epoch、
runtime/model evidence与原delegate类型/endpoint共同约束private binding。
disable、re-enable ABA、模型或配置变化使旧preview/job失效。同名已保存reference
与discovery route只在新追加tuple处去重，原configured列表顺序和请求身份不变。

原`LocalImageAdapter.generate`内容保留；原caller dispatch guard经dataclass
replace传入delegate。Production既有before_send重新比较binding/recipe，Comfy
prompt/history/download前后都保留此guard。单元负例证明history之后注册变化不下载，
下载期间注册变化或caller authority撤销不解码/返回结果，原PermissionError对象传播。
这不是远端事务原子性或原生Windows Host撤权验收。

public selection仍是原candidate ID；Comfy固定SD模板使用实际runtime checkpoint。
registration_digest仅保留private binding，不增加严格前端public DTO/recipe字段。
原configured provider binding/recipe、schema1/2与schema3闭合字段不变。

discovery目前只证明T2I结构：本阶段没有开放其I2I、FLUX/Qwen Image、AI mask
inpaint/outpaint、repair、upscale或任意workflow。已有configured I2I/手工mask/CPU
cutout照旧。没有cloud fallback、统一ModelRouter财务结算或付费调用。
源码子能力 **IMPLEMENTED / CONTRACT_VERIFIED**；Image整体 **PARTIAL**，真实
Windows/模型/质量 **LOCAL_REQUIRED**，不是M5验收通过。

## 实际验证与保留失败

Windows开发检查使用隔离Python3.12.9、原verification wrappers、合成模型HTTP，
实际PNG解码/原Asset owner；PG使用新空数据库、PostgreSQL16.15及20个原迁移。
既有模型只做有界只读目录元数据盘点；未下载、注册、启用、加载或推理。

| 实际执行 | 结果 | 范围/限制 |
| --- | --- | --- |
| 修复前新增unit RED | 13failed/3passed/2PG适用性跳过 | 缺失route/guard/parameter/recipe连接；原日志、源码与失败保留。 |
| 首次unit+mountedAPI | 27passed/18failed/30PG适用性跳过 | 18项因新增测试误设error/422响应header前提；旧产品路由/原测试未改。首次未到达断言另记。 |
| 修正新增前提并增加下载负例后的专项File | **48passed/30PG适用性跳过** | 78节点；明确queue/execute/private candidate/review、Host/CAS/严格DTO等。 |
| 12个相关原模块File | **506passed/1failed/192PG适用性跳过** | 原symlink fixture创建时报WinError1314，产品断言未执行，Windows失败保留。 |
| 12模块PG适用选择 | **506passed/192File适用性跳过/1deselected** | 该原symlink节点明确NOT_RUN（已知Windows权限前提），不声称完整12模块或CI通过。 |
| 原Linux补充断言 | **3passed** | Ubuntu24.04/Python3.12.3；同一原discovery symlink测试和2个原compact symlink测试；不是Windows结果。 |
| 新mounted frontend | **9passed** | 原workspace/controller/strict client/真实小PNG字节；HTTP为fixture，非真实模型。 |
| TypeScript | **PASS** | frontend源字节至本阶段最终状态不变；无visible UI或shell代码修改。 |
| 原API/manifest检查 | **19passed** | surface/discovery catalog和V2 manifest扩展；没有冒称原47整套当前Windows通过。 |

结果重叠，不能相加。PG集群为本轮独立资源，原数据库/作品未触碰；停止证据保留。
首次错误命令未启动测试，仅保留派生工具观察，不虚构原runner日志。离线venv依赖
准备失败与新增测试前提修正保存为私有证据，不写成产品失败或删去以制造绿灯。
旧Node依赖复用时Vitest写了128byte ignored
results cache；原代码、原报告和原测试证据未改，后续共享依赖执行关闭该缓存。

## 来源、清单与发布

代码/测试输入tree：`90b4a3681b57bc0b33ce850a3790136f35ec5fee`；最终5文件hash
与生成/测试绑定见[脱敏验证摘要](production-expansion-image-local-20261013.json)。
测试及后续检查期间2产品源码不变。文档/清单更新不变更这些执行输入；实际结束SHA
由push后Git remote/PR回执单独核对，不能自引用预先猜测。

不变原生成器同步4个API artifacts与V2 inventory：API **2219 operations，0added/
0removed**，app fingerprint `4d112a7d0a544d6ceee7deef60d9f8d0677d2f980d7dc57f7d02762dff4ca356`。
API Markdown/OpenAPI因接口不变而字节不变；JSON/detail反映新源码。
V2 **13442 collected nodes**，冻结9151保持原顺序/历史skip/外部门禁，新增计78。
收集不是执行通过。generator/baseline/原断言/V1冻结/Interop1.0没有改动。

GitHub前一727阶段29jobs的账户账单锁/runner0/空steps仍是执行阻塞；本阶段新SHA
的自动CI须实际核对，不能以此处本地通过替代。PR47保持Draft，无merge/release。
GraphFlow新root context曾成功，早期plan/index transport失败单独保留。最后incremental
index成功（8files/222symbols）；这不是全仓图谱或全部vector backfill完成的声明。

## 后续与 Opus

下一条Image子能力仍须实际adapter支持和独立执行闭环，不能把mask编辑当AI局部
重绘、目录发现当FLUX/Qwen推理或已有工作流当全部图片能力。Director的scene-free
节点/notes、Storyboard独立镜头、Video typed reference、Audio FLAC/MP3/denoise/
separation、Editing专用轨/proxy/FCPXML/EDL等缺口仍按审计推进。

本阶段没有改变Opus的接口：继续通过原`useStudioMediaExecution`、Graph及timeline
headless named actions/Host client；保留preview/create/execute/review分开、dirty/
CAS/epoch/UNKNOWN/Blob revoke。UI shell/token/primitives及设计系统ownership不改。
M4 PARTIAL、M5-M9原实际验收顺序、F00 INTEGRATED+39 PARTIAL与独立复审BLOCKED
保留。Windows最终安装、GPU压力、真实模型及完整成片/产品验收 **NOT_RUN**。
