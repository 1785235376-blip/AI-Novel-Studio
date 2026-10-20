# B07 / DIF-10 / E2E-07 证据可信性加固报告（2026-10-20 第二轮）

状态：Hermia 复核指出的“上传回执被当成系统运行验证”风险**已用真实 mounted API 复现并修复**；
授权、跨项目/故事/revision/source-incarnation、幂等/冲突与旧证据失效语义均已实测。
修复代码 HEAD = `9c65bd82`，E2E 证据在干净树 HEAD = `2f368141` 重新生成（672 checks / 0 failed）；
证据提交 = `8438094a`。本报告只追加文档，最终交付 tip 见增量交付验证文件。

## 0. 执行前实际状态（未假定）

| 项 | 实测 |
|---|---|
| 原修复分支 | `work/v2-b07-fixes-20261020` @ `725ce9a1` / tree `ee03403a`，工作区 clean（与用户报告一致） |
| 原交付目录 | `D:/PoemSeed/Recovery/b07-delivery/B07_DIF10_E2E07_20261020/`（本轮不覆盖；新增独立子树） |
| 本轮分支 | 从 725ce9a1 新建 `work/v2-b07-evidence-trust-20261020`（独立 worktree，原分支/原目录/原证据未动） |
| 公开构建清单 | `packaging/public-build.json` 未修改；Hermia 的 16f0e8db 未合并，未触碰其工作区/后续提交 |

## 1. 已复现的真实风险（不是推测）

### 1.1 上传回执被升级为“系统运行 PASS”（真实漏洞）

- 复现（修复前，真实 mounted API）：`POST /api/novels/{nid}/experimental/interactive-stories/{sid}/export-verification`
  提交与导出产物摘要匹配、`checks: {TARGET_RUNTIME_EXECUTED: PASS, SAVE_RESTORE_VERIFIED: PASS}`、
  `commands: [{exit_code: 0}]`、任意 `log_sha256`（如 `'f'*64`）的回执；
  响应与 `export-targets` 随即报告 `artifact_evidence_status=PASS`、
  `runtime_claim=SAVE_RESTORE_VERIFIED`，导出包 `evidence` 也显示运行 PASS。
  修复前 `tests/test_r5_interactive_story_mounted.py` 自身就断言了这一错误行为。
- 根因代码路径（修复前）：
  - `app/experimental/interactive_export_contract.py::artifact_evidence`：任一精确绑定的 receipt
    即 `status='PASS'`，并把 receipt 自报的 runtime 等级写入系统 levels；
  - `app/experimental/interactive_story.py::record_export_verification`：只校验产物身份绑定，
    不区分“调用者声明”与“系统执行”；`_runtime_claim` 把 levels PASS 变成 runtime claim；
  - `app/experimental/interactive_story_api.py` 路由（`domain.review`）是合法人工入口，
    原设计把“可写权限 + 匹配摘要”当成执行证明。
- 结论：产物身份匹配只证明回执指向该产物，不能独立证明产物执行成功。

### 1.2 已正确防护 / 已实测无需重做的部分

- 只读用户写回执：路由仍是既有 `domain.review`；mounted 实测 viewer=403、匿名=401、
  其他分支=403（`PROJECT_SCOPE_FORBIDDEN`）。授权代码未改动。
- 跨故事回执：既有 `receipt.story_id != sid` 与无匹配导出记录会拒绝（422），本轮 mounted 复验通过。
- 跨项目：另一个 novel 的故事无法吸收本项目回执（422）；原故事在另一项目路径不可寻址（404）。
- source/incarnation 变化：既有 `_current()` 捕获摘要围栏使 `export-targets`/`export-verification` 返回 409；
  本轮复验通过，无需新增机制。
- 新版本继承旧 PASS：既有“latest export per target”逻辑已使新 revision = STALE_REVISION / UNVERIFIED；
  本轮补强了“旧回执在 revision 变化后重放”必须拒绝（见 2.2）。
- 同一产物重复导出身份：`_record_export` 以 story/target/revision/artifact/files digest 去重，
  本轮测试证明重复导出返回同一 `export_record_id`/sha256，证据不被复制。

## 2. 修复内容与提交

### 2.1 外部验收声明 vs 系统验证（提交 9c65bd82）

- 契约：新增 `verification_claim_digest`、`_claim_view`；`artifact_evidence` 只有
  `levels.GENERATED_ARTIFACT_VALIDATED=PASS` 是系统本地可证明的，runtime levels 恒为 NOT_RUN；
  绑定上传回执 → `status=EXTERNALLY_ASSERTED_PENDING`，附 `external_claims`、
  `latest_external_claim`、`asserted_levels`、`claim_trust=EXTERNAL_UNVERIFIED`、
  `system_verification=NOT_PERFORMED`、`policy=EXTERNAL_CLAIMS_NEVER_SET_SYSTEM_RUNTIME_LEVELS`。
  `ARTIFACT_EVIDENCE_STATUSES` 增加 `EXTERNALLY_ASSERTED_PENDING`；`PASS` 保留给未来可信服务端执行记录。
  契约文档新增 `verification_receipts=EXTERNAL_ACCEPTANCE_CLAIMS_NOT_SYSTEM_EXECUTION`、
  `system_runtime_verification=NOT_AVAILABLE_IN_THIS_PRODUCT` 等明确口径。
- 服务：`record_export_verification` 存储时写 `origin=EXTERNAL_SUBMISSION`、
  `trust=EXTERNAL_UNVERIFIED`、`system_verification=NOT_PERFORMED`、`claim_digest`；
  响应/导出/目标行均带外部声明来源；`runtime_claim` 保持 UNVERIFIED。
  **合法人工入口保留**：上传仍 200 保存并按来源展示，不删除、不全部改成失败。
- 未新增执行引擎、密钥、账户或权限；没有可信服务端执行记录就不伪造 PASS。

### 2.2 回执生命周期、并发与旧证据（同一提交 9c65bd82）

- 幂等：完全相同的声明重放 → 200 `status=IDEMPOTENT`，返回同一 `evidence_record_id`，不新增证据行。
- 冲突：同一产物 + 同一 verifier 但内容不同 → 409 `EXPORT_VERIFICATION_CONFLICT`，
  存储证据不被覆盖；不同 verifier 的声明允许并存并显式列出（仍全部是外部声明）。
- 旧 revision：声明 revision 必须等于当前 revision，否则 409 `EXPORT_VERIFICATION_STALE_REVISION`；
  事务内再次校验当前 revision（防止匹配后 revision/source 变化导致旧证据落新版本），失败回滚。
- 旧证据失效：新 revision → STALE_REVISION；重新导出新 revision → UNVERIFIED；
  旧回执重放 → 409；chapter/source 变化 → 409。
- `MAX_EVIDENCE` 限制保持；两次 `reauthorize()` 仍在事务内（撤权回滚既有测试通过）。

### 2.3 Studio UI（提交 520400a5）

- 新增外部声明展示：`EXTERNALLY_ASSERTED_PENDING` 警告态；系统等级列表标注“系统证据”，
  外部声明单独列表标注“声称 PASS（上传文本，非系统验证）”；来源含 verifier/verified_at/
  log_sha256 摘要与“上传文本，未经系统执行或复核”提示；runtime claim 仍 UNVERIFIED。
- 类型新增 latest_external_claim/external_claims/asserted_levels/claim_trust、
  RECORDED|IDEMPOTENT 状态与 verification.external_claim_only/system_verification。

### 2.4 E2E 证据与 harness（提交 2f368141、8438094a）

- harness 仍由自身真实执行 Godot 4.7/inkjs 2.3.2 并保留独立运行证据；提交回执后要求产品
  返回 `EXTERNALLY_ASSERTED_PENDING` + runtime NOT_RUN + claim UNVERIFIED；
  若产品出现 PASS 则记 `PRODUCT_ARTIFACT_OVERCLAIM` 直接不通过。
- 干净树 `2f368141` 重跑：`PASS_WITH_BLOCKED_ENVIRONMENT`，672 checks / 0 failed，exit 0；
  Godot/Ink 产品列均为 EXTERNALLY_ASSERTED_PENDING（runtime NOT_RUN），E2E 自身运行等级 PASS；
  仅 Ren'Py 环境缺失 2 项预期 unmet。旧证据中“产品 PASS”列已被本证据替换。
- 另修复 E2E 可重建 scratch 目录缺失导致的测试失败（`DEFAULT_SCRATCH.mkdir`），这是本轮
  “可重建临时产物被清理后测试仍可跑”的鲁棒性修复，不代表放宽任何断言。

## 3. 本轮实测（真实命令与结果）

| 范围 | 命令 | 结果 |
|---|---|---|
| 后端 B07 全量相关（含真实 Godot/Ink opt-in） | `python -m pytest tests/test_r5_interactive_story*.py tests/test_interactive_*.py tests/test_storyverse_ink_exchange.py tests/test_surface_freeze_media_engine_adapters.py tests/test_post_interop_interactive_history.py tests/test_interactive_membership_handoff.py tests/test_interactive_removal_handoff.py tests/test_b07_e2e07_journey.py -q -m "not postgres_backend_only"` | **292 passed, 0 failed** |
| mounted 反例 | `tests/test_interactive_export_verification_trust.py`（6 场景 × 2 prefix） | **12 passed** |
| 前端互动叙事 15 文件 | `pnpm exec vitest run <15 files>` | **159 passed** |
| 类型与构建 | `pnpm exec tsc -b` / `pnpm run build` | exit 0 / exit 0 |
| E2E-07（干净 2f368141） | `python scripts/b07_e2e07_journey.py all` | 672 checks / 0 failed / exit 0 / PASS_WITH_BLOCKED_ENVIRONMENT |

反例覆盖：伪造成功字段与任意日志摘要、read-only/匿名/其他分支、跨故事、跨项目、
revision 变化后重放、source incarnation 变化、重复提交幂等、冲突不覆盖、
正常外部声明保存并显示来源、已有历史证据可读、同一产物重复导出身份稳定。

## 4. 仍未验证 / 阻塞（如实保留）

- 系统级真实运行验证：产品没有可信服务端执行器，故上传声明永远不会变成系统 PASS；
  这是有意降级，不是把合法人工入口删除。未来若集成可信执行记录，可绑定后升级。
- Ren'Py 8.5.4 运行时/存档 = BLOCKED_ENVIRONMENT；Windows GUI、原生 C# Ink、媒体播放、
  PostgreSQL = NOT_RUN（未新增引擎/服务/权限）。
- public build 闭包由 Hermia 所有（本轮未改 `packaging/public-build.json`）；新增 Ink helper/schema
  的 whitelist 统一交给 Hermia，未触碰 App.tsx/ExperimentalWorkbench/共享路由/Graph/Director/Asset/锁文件。

## 5. 交付

- 原交付目录完全保留（366 文件）；本轮增量仅新增 `trust-hardening-20261020/` 子树
  （增量 bundle/patch/完整 UTF-8 TXT/校验表/本报告/新证据引用/复现命令）。
- 起点 `725ce9a1` → 本轮最终 tip；逐提交 patch、bundle、SHA256SUMS 与 clean-room replay 结果
  见该子树 `FIXES_DELIVERY_VERIFICATION.json` 与 `COVERAGE_AND_STATS.md`。
- 本轮可重建临时产物（E2E scratch、pytest 临时目录）已清理；保留唯一日志、原交付、源码、
  Git 历史与 Hermia 工作区。
