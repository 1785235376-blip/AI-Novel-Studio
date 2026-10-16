# Phase 8 preparation — QingJian Interop

**Status: PREPARATION ONLY.** 本文是 Phase 8（QingJian Interop）的开工前置评估与执行计划。本阶段**未**修改 QingJian 仓库、**未**实现任何 adapter、**未**声称任何真实双产品验收。它只记录：两个仓库的真实基线、协议侧现状、真实 Desktop 源码的可定位 owner、仍为 `LOCAL_REQUIRED` 的门禁，以及无真实运行期时可推进的边界。

## 1. 两个仓库的真实基线

| 仓库 | 分支 | HEAD | 工作区 | 备注 |
| --- | --- | --- | --- | --- |
| Studio（本仓库） | `feature/v2-narrative-platform` | `7474105` (Phase7 已推送) | 本工作树，干净 | 协议侧 owner 在此 |
| QingJian | `work/v1-stabilization-20261010` | `a36231e` (`fix(tutor): keep immutable Python assignment targets unknown`, 2026-10-11) | `D:\PoemSeed\QingJian\QingJian-V1-Cloud-current-20261011`，已跟踪文件干净 | `origin = 1785235376-blip/QingJian-V1-Cloud.git` |

本会话**不写入** QingJian 检出（只读盘点）。

## 2. 协议侧现状（Studio 内，V1 冻结）

- `contracts/local-interop/v1/`：29 个严格 JSON Schema（含 `context-capsule`、`capability-negotiation`、`cancel-request/result`、`case-candidate`、`common`、`capability` 等），另有 `parity-manifest.json`。
- `local_interop_protocol/`（4 文件）、`local_interop_desktop/`（9 文件）、`interop-reference/`（4 文件）、`app/local_interop/`（9 文件）、`frontend/src/interop/`（16 文件）。
- 11 份顶层协议/安全/能力文档：`LOCAL_INTEROP_PROTOCOL_V1.md`、`LOCAL_INTEROP_SECURITY.md`、`LOCAL_INTEROP_CAPABILITIES.md`、`LOCAL_INTEROP_CONTEXT.md`、`LOCAL_INTEROP_TESTING.md`、`LOCAL_INTEROP_COMPATIBILITY.md`、`LOCAL_INTEROP_LIFECYCLE_LIMITS.md`、`LOCAL_INTEROP_CORRECTION_RECEIPT.md`、`LOCAL_INTEROP_TUTOR.md`、`LOCAL_INTEROP_QUICKSTART.md`、`LOCAL_INTEROP_REQUIREMENTS.json`。
- `LOCAL_INTEROP_REQUIREMENTS.json` 的 65 节矩阵状态分布：`DONE` 27、`CONTRACT_VERIFIED` 19、`PARTIAL` 最多集中在真实 Desktop 侧、`LOCAL_REQUIRED` 1、`MOCK_ONLY` 1。`historical_boundaries` 明确：**真实 Tutor Desktop 集成 LOCAL_REQUIRED；mock 结果不能用于认证**。
- 用户总开关与 `V1_ACCEPTANCE_MODE` 双重默认 OFF；16 个稳定能力中**没有**执行/凭据/项目写入授权。

## 3. 关键前置更新：真实 Desktop 源码**在本机已具备**

`QINGJIAN_DESKTOP_MAPPING_CHECKLIST.md` 开头写的是「Complete real QingJian Desktop source is not in the current Cloud repository」。**该表述对当前本机检出已过时**：`QingJian-V1-Cloud-current-20261011\desktop\` 下有 **2671 个文件**，其中：

| 子模块 | 文件数 | 与 interop 的关系 |
| --- | --- | --- |
| `desktop/core` | 27（Rust） | 全部映射目标的主要落点 |
| `desktop/main` | 30 | 应用生命周期、事件源 |
| `desktop/identity` | 4 | 身份/握手 |
| `desktop/memory` | 4 | Memory Gate 候选 |
| `desktop/observer` | 8 | 事件观察者 |
| `desktop/providers` | 20 | Model Scheduler / provider 元数据 |
| `desktop/review` | 12 | Verifier / 复审 |
| `desktop/ui` | 9 | 通知与设置 |
| `desktop/docs` | 569 | 含 `phase1/02_NAMED_PIPE_DESIGN.md`、`phase1/01_B2_IDENTITY_HANDSHAKE_DESIGN.md`、`phase1/03_THREAT_MODEL.md` |
| `desktop/tests` / `validation` | 339 / 1620 | 真实测试与验收材料 |

`desktop/core` 实际文件（已逐名读取目录）：`advisor_engine.rs`、`agent_system.rs`、`answer_verifier.rs`、`assistant_identity.rs`、`assistant_interface.rs`、`assistant_pipeline.rs`、`capability_system.rs`、`cloud_archive.rs`、`context_assembler.rs`、`context_system.rs`、`control_center.rs`、`conversation_session.rs`、`emotional_state.rs`、`identity_policy.rs`、`input_interface.rs`、`mode_system.rs`、`output_coordinator.rs`、`persona_core.rs`、`persona_runtime.rs`、`pipeline_runtime.rs`、`product_session_tests.rs`、`reasoning_core.rs`、`resident_runtime.rs`、`runtime_loop.rs`、`runtime_orchestration.rs`、`voice_output_coordinator.rs`、`web_research.rs`。

## 4. checklist 16 行 → 候选真实源码（已定位 / 未定位）

「已定位」= 在 QingJian 真实源码中检索到同名/近义 owner 文件，**尚未**逐行核对其公开契约与生命周期（Phase 8 第一步）。

| checklist owner | 候选真实源码（QingJian） | 定位状态 |
| --- | --- | --- |
| ContextSystem / Context V2 | `desktop/core/context_system.rs` | 已定位 |
| ContextAssembler | `desktop/core/context_assembler.rs`、`assistant_pipeline.rs` | 已定位 |
| Recall Gate | `desktop/core/runtime_orchestration.rs`；`assistant_identity.rs`/`capability_system.rs` 有 recall 相关命中 | 已定位（待精确定位 gate 本体） |
| Memory Gate | `desktop/core/assistant_identity.rs`、`assistant_interface.rs`、`reasoning_core.rs`、`runtime_orchestration.rs` | 已定位（待确定唯一 gate） |
| Tutor Orchestrator / QingJian Main | `desktop/core/assistant_pipeline.rs`、`resident_runtime.rs`、`runtime_loop.rs`、`desktop/main/src/main.rs` | 已定位 |
| Verifier | `desktop/core/answer_verifier.rs`、`desktop/review/` | 已定位 |
| Case DB / Case Gate | 检索 `CaseGate`/`CaseStore`/`solved_case`/`case_gate` **无命中** | **未定位**（真实缺口，不得臆造路径） |
| Model Scheduler | `desktop/core/advisor_engine.rs`、`runtime_orchestration.rs`、`desktop/providers/` | 已定位 |
| Desktop Settings | `desktop/core/control_center.rs`、`mode_system.rs`、`desktop/ui/` | 已定位（待定具体 config owner） |
| App Lifecycle | `desktop/main/src/main.rs`、`desktop/core/resident_runtime.rs`、`pipeline_runtime.rs` | 已定位 |
| Notification system | `desktop/core/output_coordinator.rs`、`voice_output_coordinator.rs`、`desktop/ui/` | 已定位（待定通知本体） |
| Deep Link / navigation | 仅 `cloud_archive.rs`/`input_interface.rs`/`main.rs` 泛命中，**无 scheme/deep-link owner** | **未定位** |
| Windows Host（pipe + OS identity） | `desktop/docs/phase1/02_NAMED_PIPE_DESIGN.md`、`01_B2_IDENTITY_HANDSHAKE_DESIGN.md`、`desktop/identity/` | 设计已具备，实现待定位 |
| Installer / signed binary | `desktop/packaging/`（6 文件）、`desktop/docs/phase1/03_B3_APPROVAL_RECORD.md` | 已定位 |
| Event producer owners | `desktop/observer/`（8）、`desktop/core/emotional_state.rs`、`desktop/main/src/main.rs` | 已定位 |

## 5. 仍为 LOCAL_REQUIRED 的门禁（mock 不可替代）

对应 `LOCAL_INTEROP_REQUIREMENTS.json`：§13 Windows Transport、§15 App Discovery、§16 Event Bridge、§32 Case 写入确认、§35 QingJian Adapter（真实 Desktop 组合）、§42 Session Identity（**缺少已安装产品/OS 用户的双向 attestation**）、§45 离线原则、§55 `MOCK_ONLY`、§62/§63 最终交付与验收。

理由（矩阵原文）：当前开发的 HTTP `ProductDescriptor` 是**自述**的，不是已安装产品/OS 用户身份；Windows SID ACL、命名管道、远程拒绝与真实双产品运行在本机未被执行。**Mock 结果不得用于认证。**

## 6. 无真实双产品运行期时可推进的范围（Phase 8 建议）

可在本仓库、不启动 QingJian 的前提下推进：

1. 按 §4 表把 16 行逐条**核对真实源码契约**（owner 路径、公开 API、生命周期、授权 owner），产出「已核对 / 未定位」清单；未定位项（Case Gate、Deep Link）保持未定位而不是补路径。
2. 用 QingJian 的真实 Rust owner 名称/契约**对照** Studio 侧 29 个 schema 与 16 个能力，找出真实字段缺口（只做契约对照，不改 QingJian）。
3. 补齐 matrix 中不依赖真实桌面的 `PARTIAL`：§15 有界发现、§16 直接事件源 vs 轮询的诚实标注、§32 预览/批准路径。
4. 刷新 `parity-manifest.json` 与 `LOCAL_INTEROP_REQUIREMENTS.json` 的**当前事实**（只增，不改历史状态），并保留矩阵既有的 `MOCK_ONLY`/`LOCAL_REQUIRED` 语义。
5. 复用 QingJian 的 `desktop/docs/phase1/02_NAMED_PIPE_DESIGN.md` 与 `01_B2_IDENTITY_HANDSHAKE_DESIGN.md`，把 Studio 侧已授权的 pipe/identity 参考实现与之逐条对照，标注一致/不一致（仍不声称真实运行）。

**必须等真实运行期**（不得 mock 替代）：Windows current-user SID ACL 实测、命名管道跨进程实测、真实双产品 handshake/attestation、撤销/重连/升级/过期、真实 Tutor 本地模型模式、安装版注册与签名证据。

## 7. 禁止项（继承 §61 与用户指令）

不合并 main、不 release、不打 tag、不部署、不 backport、不用付费 API、不使用真实稿件、不共享凭据、不安装模型、不自启动用户应用、不开公网/LAN 监听、不引入可执行插件、不在 mock 结果上声称真实双产品验收、不修改 QingJian 仓库（除非用户明确授权）。

## 8. 需要用户决策的前置

1. **QingJian 仓库是否纳入写入范围**：若 Phase 8 需要在 QingJian 侧落地 adapter，需要明确授权与基线条目（当前 `a36231e`，`work/v1-stabilization-20261010`）。
2. **真实双产品验收环境**：本机无 Windows 安装版双产品运行与 GPU/真实模型验收条件；需要用户明确交付目标（仅契约对照，还是包含真实管道运行）。
3. `Case Gate` 与 `Deep Link` 在真实 Desktop 源码中的 owner 尚未定位；若无其他分支/材料，应保持 `LOCAL_REQUIRED` 而不是补路径。

## 9. 风险

- **表述漂移风险**：checklist 的「Desktop 源码不在当前仓库」结论在本机已不成立；后续文档必须以本机检出为准并注明基线 SHA。
- **过度声明风险**：真实源码存在 ≠ 真实运行验收；矩阵的 `MOCK_ONLY`/`LOCAL_REQUIRED` 语义不得因源码盘点而升级。
- **两仓库基线漂移**：QingJian 与 Studio 各自独立版本化，协议版本是唯一耦合点；对照时必须记录两侧 SHA。
