# AI Novel Studio 产品验收

验收日期：2026-10-07，Asia/Shanghai。指定输入：一个失忆者在废弃城市寻找过去身份，最终发现自己曾经毁灭城市。

## 真实运行结果

DONE：本机 Qwen3.5-9B-Q4_K_M.gguf / llama.cpp 实际 HTTP 推理，原 Local AI discovery → metadata validation → explicit enable → normalized runtime → 原作品 owners。MOCK_PROVIDER=false、ENABLE_CLOUD=false、无云端 fallback。模型已存在于本机，未下载替代权重。本次独立服务 context_size=16384，RTX 5080；API 127.0.0.1:8051、前端 127.0.0.1:5209。metadata 的 verified=false/DEGRADED 是“尚未由 discovery 探测推理”的历史语义；真实生成证据来自各实际 job execution_mode/用量/正文，未篡改 metadata 验证状态。

成功 run `85a84385-a0ed-4211-9e43-5d841b9aff26`，作品 `f4b8c9ee`，实际章节 `f4b8c9ee:2`。16 个串行验收阶段全部 PASS，累计阶段耗时 92.25s。后续人工 Memory 审批与真实 Chapter Context 读取单独 PASS，0.196s。原续写 owner 会新建下一章，因此保留原空起始章并以实际新章 ID/version 后续修改，不伪造“续写覆盖第一章”。

| 阶段 | 状态 | 实测秒 |
| --- | --- | --- |
| 01-project | PASS | 1.429 |
| 02-world | PASS | 7.015 |
| 03-characters | PASS | 5.133 |
| 04-outline | PASS | 6.827 |
| 05-chapter | PASS | 8.341 |
| 05b-memory-extraction | PASS | 11.292 |
| 06-ai-revision | PASS | 9.194 |
| 07-consistency | PASS | 0.064 |
| 08-version-save-compare-conflict | PASS | 0.053 |
| 09-history-restore | PASS | 0.038 |
| 10-export | PASS | 0.322 |
| 11-agent-planner | PASS | 14.714 |
| 11-agent-writer | PASS | 6.229 |
| 11-agent-editor | PASS | 6.271 |
| 11-agent-reviewer | PASS | 7.19 |
| 11-agent-verifier | PASS | 8.138 |
| 12-memory-human-review-context（独立后续验证） | PASS | 0.196 |

原世界材料明确 apply 后进入 World/locations/经批准 Lore rules；角色通过原 Story owner 新建；大纲通过原 outline CAS。候选生成不直接成为事实。章节和改写来自实际本机模型。Consistency 使用实际作品上下文并返回 findings；成功的扫描不等于对所有自然语言规则的完备证明。CAS 过期 PUT 明确 HTTP409；历史恢复逐字校验原正文、产生递增版本。Markdown export 实际 download3695bytes，包含恢复后的原文并记录 SHA256。

原续写采纳自动触发 Memory，实际 job `32f3acd6-dbe9-5b91-8cf4-42d26ab1ce2d` COMPLETED/real，生成3个 source-bound PENDING proposals（2个CHARACTER_MEMORY、1个EVENT）。后续通过原 approve-memory API 明确人工批准1个真实提案；正式 memory ACTIVE、原 Chapter Context 返回该 memory ID。其余提案保持待审核。五个 Agent 的 actual execute 皆 COMPLETED/model_called=true/provider_execution_mode=real，严格 schema/agent/context_hash 保持，不把契约校验模式当推理。

主证据：[完整成功回执](docs/delivery/full-recovery/verification/product-acceptance/85a84385-a0ed-4211-9e43-5d841b9aff26-receipt.json)；[Memory 人工审核回执](docs/delivery/full-recovery/verification/product-acceptance/85a84385-a0ed-4211-9e43-5d841b9aff26-12-memory-human-review-context.json)；[实际导出正文](docs/delivery/full-recovery/verification/product-acceptance/85a84385-a0ed-4211-9e43-5d841b9aff26-novel.md)。每阶段另有完整JSON，不含凭据。

## 失败记录与修复

保留全部早期 live-model receipt：OUTLINE 字段错误嵌套被原严格schema拒绝；提示增加record.outline形状。Memory 首先复述schema、其次返回不完整JSON、再次改写引文，均未生成正式记忆；现在原 runtime schema参数进入本地生成，wire grammar 保留shape/ref/enum，完整 bounds 在host jsonschema与原typed validators执行，实际引文枚举绑定accepted source，model不可伪造证据。原完整schema没有放宽。llama.cpp使用的schema wire形状参照[官方JSON Schema例子](https://github.com/ggml-org/llama.cpp/blob/master/examples/json_schema_pydantic_example.py)；本项目的source-bound枚举和host完整bounds校验是本次实现，并非该例子替项目证明。历史输出均留在独立 run IDs。

五Agent第一次真实 admission 被8192窗口拒绝（8493–9116输入tokens），runtime记录PROVIDER_UNAVAILABLE；实际16k服务后全部成功。这是容量配置与错误分类边界，不删除真实上下文来换取通过。验收脚本原export大小写poll bug及重启窗口connection-refused也留RED，并与产品实际成功导出区分。

## 内容质量与证据边界

PARTIAL：生成正文1237 Unicode字符、1064汉字，超过本次提示700–900字；它也较早给出了毁城身份线索/确认。功能链可运行，严格篇幅/悬念节奏不能视为通过。Reviewer/Verifier产生真实建议，由作者决定是否采纳。本文不把JSON/流程PASS当作文学质量保证。

前端无章节 World/Character/Outline、本机正文、历史预览/冲突/确认、导出与角色可达性已有真实browser evidence；本机可信Agent会话入口已通过实际UI验证：password显式输入→原token验证→LOCAL_HOST绑定；Reviewer任务4953fb9c-6fdc-4cee-bf1a-e43d9c7be26b真实Qwen COMPLETED/model_called=true，随后显式解绑。绑定后网络失败0、JS错误0、无横向溢出，实际Markdown下载3695bytes。匿名请求401为负向控制，保留原团队隔离。证据为[真实页面回执](docs/delivery/full-recovery/REAL_AUTHORIZED_PRODUCT_BROWSER.json)及[实际Agent画面](docs/delivery/full-recovery/real-authorized-product-agent.png)。最新Windows package/严格完整两backend结果仍在完成，见最终状态报告。fixture-based unit/visual/CI 是代码回归证据，不属于上述真实模型验收。
