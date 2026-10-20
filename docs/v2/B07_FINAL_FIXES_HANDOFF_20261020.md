# B07 / DIF-10 / E2E-07 最后三项修复报告（2026-10-20 第三轮）

结论：Hermia 6c857 复核指出的 F2（Ink 实际恢复入口可跳过绑定）、F3（负例准备错误
假 PASS）与 C1（725 旧格式相同回执重放误报冲突）均已在**真实交付入口、真实
B artifact 与真实数据形状**上修复；F1 与 ZIP 防护未回退。证据对应修复后代码 HEAD
`9ffa21df` / tree `98a97c1d`，E2E 在该干净树重跑 672 checks / 0 failed。
Ren'Py/Windows GUI/原生 C# Ink/媒体/PostgreSQL 仍未验收。

## 0. 固定起点与实际核对

| 项 | 实测 |
|---|---|
| 起点分支 | `work/v2-b07-evidence-trust-20261020` @ `6c8570c0120e78508f95067c66ce6aa14e93754d` / tree `56e1a6bc0b258555eb89b39d9473838110b8ef55`，clean |
| 是否已有后续修复 | 无；HEAD/tree 与用户给定完全一致，未发现可对照的更新提交 |
| 本轮分支 | 从起点新建 `work/v2-b07-final-fixes-20261020`，原分支/原提交/旧交付保留，未 reset、未 force push |
| 执行前磁盘 | D: 33.55 GB 可用 |
| 已读复核 | `dsh-trust-6c857-review-20261020/REVIEW.zh-CN.md` 全文；原反例脚本 `ink_independent_probe.mjs`、`test_independent_probes.py` 与相关 JSON |

## 1. F2：Ink 实际恢复入口的绑定绕过（已修复）

### 修复前（Hermia 原反例，本轮用同一脚本在真实 B artifact 上复跑）

- 交付 helper sha256 `6cdde4c34c24892941ca870b879224bb57342a3d880dfe99fecb6d15d6281e5d`。
- 真实 B artifact 编译摘要 `80ec9e2c…`；独立改变有效 token 后摘要 `e7163927…`（确实不同）。
- 结果：完整 expected 正确拒绝（`SAVE_ENVELOPE_ARTIFACT_MISMATCH`），但
  **省略 expected、`{}`、仅 `{storyId}` 三条路径全部 accepted=true**，并把旧 state
  载入不同编译产物；正常 post-choice 跨进程恢复仍 PASS。

### 修复后

- 交付 helper 改为强制完整 restore context：`storyId`、`revision`、
  `compiledArtifactSha256`、`targetFormatVersion`、`runtime {name,version,format}`，
  由调用者从**当前实际加载的作品/产物/runtime** 派生；helper 绝不从存档反填。
- 缺失/undefined/null → `SAVE_ENVELOPE_CONTEXT_REQUIRED`；空对象、缺字段、字段格式错误、
  runtime 缺 format → `SAVE_ENVELOPE_CONTEXT_INVALID`，均在 `story.state.LoadJson()` 之前。
- 不同作品/revision/编译产物/格式/runtime 继续明确拒绝；完整 context 的正常恢复不变。
- 迁移保留但明确标注 `migrated_from=UNBOUND_LEGACY_INK_STATE` 与限制说明，绝不标为已验证执行。
- 交付 bundle 的 runtime-pin/validation/README 暴露 `restore_context_required`、
  字段、错误码与“从当前产物派生”策略。

### 修复后同一 Hermia 反例（真实 B artifact + 新 helper sha `2024fe4a…`）

| 路径 | 修复前 | 修复后 |
|---|---|---|
| 省略 expected | accepted=true，旧 state 进入不同产物 | `SAVE_ENVELOPE_CONTEXT_REQUIRED`，未 LoadJson |
| expected={} | accepted=true | `SAVE_ENVELOPE_CONTEXT_INVALID` |
| 仅 storyId | accepted=true | `SAVE_ENVELOPE_CONTEXT_INVALID` |
| 完整 expected + 不同产物 | 拒绝 | 仍拒绝 `SAVE_ENVELOPE_ARTIFACT_MISMATCH` |
| 正常 post-choice 新进程恢复 | PASS | 仍 PASS（pid 不同，继续到同一结局） |

回归：`tests/test_interactive_ink_restore_context.py` 直接运行交付 helper 字节，
覆盖缺省/空/null/逐字段缺失/格式错误/跨产物/合法恢复，并断言失败路径
`loadJsonCalls=0`；不依赖 TypeScript 类型。

## 2. F3：verifier 负例假阳性（已修复）

### 修复前（Hermia 原反例复跑）

运行交付 verifier 对真实 B artifact：overall PASS，但最后一个负例
`different compiled artifact` 的 message 仍是
`tampered artifact digest did not change`，却被记 passed=true、actual_code 是
verifier 自己抛的预期码——准备失败被算成拒载成功。

### 修复后

- 负例准备与恢复判定严格分离：
  1. 用真实源码变异构造编译产物，要求源码确实变化、编译成功、摘要确实不同；
  2. 独立断言原摘要 ≠ 负例摘要，且负例产物可解析、可推进（`new Story` 加载）；
  3. 只有**实际调用交付 helper**（记录 `entry_called`）且 helper 因预期绑定不匹配
     拒绝（`actual_code === expected_code`），才记负例 PASS；
  4. 摘要未变化、构造失败、解析失败、脚本未执行、入口未调用、运行器崩溃/超时
     一律 `SETUP_ERROR`，整体验收 FAIL 或阻断，绝不记 PASS。
- 真实 B artifact 上现在：原摘要 `80ec9e2c…` → 负例摘要 `c5f9f5c8…`（确实不同、parse_ok=true），
  8 个负例全部 `setup_ok=true / entry_called=true / passed=true`，overall PASS。
- 新增测试专用故障注入 `--fault-negative-artifact-noop true`（故意让负例摘要不变）：
  verifier 返回 FAIL、exit 3、`save_restore_negative_setup`，负例记录
  `phase=SETUP_ERROR, setup_ok=false, entry_called=false, passed=false`——
  证明“摘要不变”不会被当成拒载 PASS。
- 回归：`tests/test_interactive_ink_verifier_negatives.py` 含正例与故障注入反例。

## 3. C1：725 旧格式相同回执的幂等兼容（已修复）

### 修复前（Hermia 原数据 + 本轮复现）

725 旧行没有 `claim_digest`；6c857 只按 `claim_digest` 判幂等、再按 verifier 判冲突，
因此完全相同的旧 receipt 重放返回 409
`EXPORT_VERIFICATION_CONFLICT: ... stored evidence was not overwritten`。
（Hermia 证据 `old-row-and-source-controls.json.legacy_identical_replay`；本轮在起点提交上
以临时 pytest 复现同码。）

### 修复后

- 对缺少 `claim_digest` 的既有行，从严格解码的已存 receipt 派生声明摘要用于比较；
  完全相同的旧声明重放 → `IDEMPOTENT`，返回同一 `evidence_record_id`，不新增记录。
- 真实不同声明仍返回 409 `EXPORT_VERIFICATION_CONFLICT`，不覆盖存储证据。
- 历史行不被静默改写/升级：不补写 claim_digest/origin/trust，`stored_row_rewritten=false`；
  响应明确 `evidence_record_audit.origin=LEGACY_RECORD_NO_ORIGIN`。
- 旧 revision、跨故事/跨 scope、撤权仍拒绝或标过期（沿用既有栅栏）。
- 兼容后旧记录即使曾带 PASS，仍只显示 `EXTERNALLY_ASSERTED_PENDING`、
  runtime levels `NOT_RUN`、runtime claim `UNVERIFIED`，不会恢复“上传=系统执行通过”。
- 回归：`tests/test_interactive_export_legacy_claim_compat.py` 8 项 + mounted API：
  旧格式相同重放、新格式相同重放、不同声明冲突、旧 revision、跨故事/跨 scope、
  兼容后 system runtime 仍 NOT_RUN；mounted 另测 viewer/其他分支 403。

## 4. 未回退的既有保证

- F1 外部声明模型保持不变：上传仍是 `EXTERNAL_SUBMISSION/EXTERNAL_UNVERIFIED`，
  `EXTERNALLY_ASSERTED_PENDING`、runtime NOT_RUN、claim UNVERIFIED。
- ZIP 有界读取、大小/路径冲突防护、显式目录记录、证据绑定与旧版本失效逻辑未重写、未删除。
- 未新增执行引擎、密钥、权限体系、付费调用或系统安全设置。

## 5. 本轮实测（命令 / 退出码）

| 范围 | 命令 | 结果 |
|---|---|---|
| 后端 B07 全量相关（含真实 Godot/Ink opt-in、本次新增回归） | `python -m pytest tests/test_r5_interactive_story*.py tests/test_interactive_*.py tests/test_storyverse_ink_exchange.py tests/test_surface_freeze_media_engine_adapters.py tests/test_post_interop_interactive_history.py tests/test_interactive_membership_handoff.py tests/test_interactive_removal_handoff.py tests/test_b07_e2e07_journey.py -q -m "not postgres_backend_only"` | **303 passed, 0 failed** |
| F2 交付 helper 反例 | Hermia `ink_independent_probe.mjs`（真实 B artifact，新 helper） | 省略/空/部分 = CONTEXT_REQUIRED/INVALID；完整跨产物拒绝；正常跨进程恢复 PASS |
| F3 正例 | 交付 verifier 真实 B artifact | PASS；负例摘要 80ec→c5f9 不同、parse_ok；8 负例 setup_ok/entry_called |
| F3 反例 | verifier `--fault-negative-artifact-noop true` | **FAIL / exit 3 / SETUP_ERROR**，绝不计拒载 PASS |
| C1 兼容回归 | `tests/test_interactive_export_legacy_claim_compat.py` | **8 passed**（含 mounted） |
| E2E-07（干净 9ffa21df） | `python scripts/b07_e2e07_journey.py all` | **672 checks / 0 failed / exit 0 / PASS_WITH_BLOCKED_ENVIRONMENT** |

前端本轮未改代码，未重复跑前端全量（上一轮 159 passed 仍属上一轮证据，不自动继承为本轮）。

## 6. 提交

| 提交 | 内容 |
|---|---|
| `01e38abb` | F2：交付 helper 强制完整当前产物 restore context；schema/runtime 文档/回归 |
| `2c848578` | F3：verifier 负例准备与拒载分离；真实不同产物、故障注入反例 |
| `9ffa21df` | C1：旧格式 receipt 派生 claim_digest，相同重放幂等、冲突仍拒绝、旧行不改写 |
| `9648919b` | E2E 证据在干净 9ffa21df 重跑并入库（672 checks / 0 failed） |
| 本报告提交 | 报告与交付引用（final tip 见交付验证 JSON） |

## 7. 未验收 / 保留项

- Ren'Py 8.5.4 运行时与存档 = BLOCKED_ENVIRONMENT；Windows GUI 可用性、原生 C# Ink、
  媒体播放、PostgreSQL = NOT_RUN（未新增引擎/服务/权限）。
- 项目删除重建/代次切换未做真实进程级验证；本轮只复验了章节 source 变化与 revision 栅栏。
- 真实多进程/PG 并发未专门压测；C1 幂等/冲突与事务内 revision 复检由 unit/mounted 回归覆盖。
- public build 白名单仍归 Hermia；本轮未改 `packaging/public-build.json`，未合并 c40+。

## 8. 交付与复验

原交付 `B07_DIF10_E2E07_20261020/` 与上一轮 `fixes-20261020`、`trust-hardening-20261020`
均未修改；本轮只在原交付下新增 `final-fixes-20261020/` 小型增量子树（增量 bundle、
逐提交 patch、完整 UTF-8 TXT、校验表、前后对照与本报告），不复制旧证据。
修复后代码 HEAD：`9ffa21df670b58cc1b518e2493c0663185d6236b` / tree `98a97c1d64d38251f7aea1c982014064d6928830`；
E2E 证据 head 即该提交（dirty=false）。最小复验：
```
python -m pytest tests/test_interactive_ink_restore_context.py tests/test_interactive_ink_verifier_negatives.py tests/test_interactive_export_legacy_claim_compat.py -q -m "not postgres_backend_only"
node scripts/verify_ink_current_artifact.mjs --bundle <INK_B_exported.zip> --vendor <inkjs_2.3.2_root> --report report.json
python scripts/b07_e2e07_journey.py all
```
