# B07 / DIF-10 / E2E-07 修复轮报告 (2026-10-20)

状态：Hermia 复核发现的四类缺陷已**实际修复并提交**；修复代码 HEAD = `cd140a39`（tree `d0aeedd5`），
E2E 证据已在干净树该 HEAD 重新生成（648 checks / 0 failed / PASS_WITH_BLOCKED_ENVIRONMENT）。
本文件所在提交只追加文档，不改变已生成证据对应的代码 HEAD。

## 0. 执行前实际状态（未假定 Hermia 给出的 HEAD）

| 项 | 实测值 |
|---|---|
| 实际 HEAD | `6232f9d7c2c8fbc6dde6e26c1d9dfb631efbc1fe`（与 Hermia 一致） |
| 实际 tree | `bb4f71227790c61ccc914b90fdff208f0e548078` |
| 未提交修改 | 无（clean） |
| 磁盘余量 | D: 36.3 GB 可用 |
| 修复分支 | `work/v2-b07-fixes-20261020`（从 6232f9d7 新建，保留全部历史，未 reset/未 force push） |
| 原交付目录 | `D:/PoemSeed/Recovery/b07-delivery/B07_DIF10_E2E07_20261020/`（本轮只新增 `fixes-20261020/` 子树，旧文件未重打包） |

## 1. 缺陷 → 修复 → 提交映射

### 1.1 运行证据被错误继承

- 原缺陷（已复现）：新故事首次导出，服务响应与 manifest 直接继承 Godot/Ink 的全局
  `TARGET_RUNTIME_EXECUTED=PASS / SAVE_RESTORE_VERIFIED=PASS`。
- 修复：
  - 契约层拆分 `historical_evidence`（适配器/固定模板历史）与 `artifact_evidence`
    （当前作品/revision/产物摘要/目标/运行时绑定证据）。
  - 新增 `VerificationReceipt`（schema `poemseed-interactive-export-verification/1`）：
    绑定 story_id、revision、spec/source digest、target_id、target_format_version、
    artifact_sha256（确定性 ZIP SHA256）、files_digest、runtime name/version/format，
    并带命令、退出码与 log hash。
  - 服务新增导出产物登记（`interactive_story_target_exports`）与回执登记
    （`interactive_story_target_evidence`）集合；新路由
    `POST /{sid}/export-verification` 只接受与**本服务真实导出过的**产物完全绑定的回执。
  - `export-targets` / `export-preview` / `export` 响应分别给出
    `historical_evidence`、`artifact_evidence(status, levels, matched_receipt, stale_receipts,
    export_record)`；`runtime_claim` 只由当前产物证据产生，无匹配回执即 `UNVERIFIED`。
  - 生成的 manifest 不再写入 `runtime.evidence`，改为 `runtime.historical_evidence` +
    `runtime.current_artifact_evidence.status=UNVERIFIED_AT_GENERATION`（附回执绑定要求）。
  - 预览摘要不再受引擎探测/已记录证据影响（`e8a4ae63`），同一故事同一 revision 的
    预览与重复导出保持可复现。
  - Studio UI 分栏展示"模板/适配器历史验证"与"当前产物验证"，后者显示
    UNVERIFIED/NOT_EXPORTED/STALE_*/PASS 与原因。
- 提交：`4f655c15`（契约+服务+API+客户端+UI+回归）、`e8a4ae63`（预览摘要稳定性）。
- 回归（新增 `tests/test_interactive_export_evidence_binding.py`，16 项全 PASS）：
  新故事首次导出不得 PASS；合法回执绑定当前产物后 PASS 且可重复导出保持 PASS；
  跨作品复用回执拒绝；修改后旧修订证据 STALE_REVISION；旧摘要/错误目标/错误格式/
  错误运行时/非法回执/篡改回执拒绝；缺失证据 UNVERIFIED；撤权回滚证据写入。
  另在 `test_r5_interactive_story_mounted.py` 增加真实 HTTP 往返：合法回执 200 且
  targets 行变 PASS；不同故事/错误摘要 422。

### 1.2 ZIP 与文件集合边界

- 原缺陷（已复现）：
  1. `read_zip_safely` 接受 8,388,609 字节单文件（>8 MiB），只在读完后再看总量；
  2. `read_zip_safely` 接受 `A.txt` 与 `a.txt`；
  3. `normalize_files` 接受 `a` 与 `a/b` 的文件/目录前缀冲突；
  4. 解压前不检查声明大小/累计预算，可能先分配过多内存。
- 修复：
  - 统一的 `check_path_set`：大小写不敏感碰撞 + 文件/目录前缀冲突（生成与读取共用）。
  - `read_zip_safely` 在读取前检查条目数、每项声明大小、声明累计预算、加密标志与路径；
    读取时以 64 KiB 分块并对实际字节做每项/累计上限校验，声明大小不符立即拒绝；
    压缩输入本身也有上限；`package_export_zip` 生成后立即用硬化的读取器回读自检。
  - `normalize_files` 同步加入大小/冲突/前缀校验。
- 提交：`c82fa991`（边界与有界读取 + 定向回归）。
- 回归（新增 `tests/test_interactive_export_zip_boundaries.py`，23 项）：8 MiB 精确值通过、
  8,388,609 拒绝；A.txt/a.txt；a + a/b（双向）；重复条目；穿越/绝对/保留名；声明大小撒谎；
  加密标志；分块读取预算直接单测；压缩输入上限；正常导出 ZIP 回读一致。
- 另修复 ZIP 工具互操作：导出 ZIP 现在写入显式目录记录，Godot 验证器/测试的容器遍历
  跳过目录记录（`497fa19f`）；Ink 验证器可直接接受导出的 ZIP（见 1.3）。

### 1.3 Ink 存档绑定

- 原缺陷（已复现）：verifier 固定 `saveAt=0`；存档是裸 `state.ToJson()`，
  同一 state 可加载进不同摘要的编译产物；交付物里没有实际存档入口。
- 修复：
  - 交付物新增真实入口 `ink/player/save_envelope.mjs`（零依赖 ESM，纯 JS SHA-256 +
    规范 JSON）与 `ink/player/save-envelope.schema.json`；runtime-pin.json 与
    validation.json 都以 sha256 绑定该 helper，并写明 legacy 策略。
  - 存档为版本化封套：schema `poemseed-ink-save-envelope/1`，绑定 story_id、
    revision、compiled_artifact_sha256、target_format_version、runtime(name/version/format)，
    `integrity=sha256(canonical-json(schema,binding,save))`，大小上限 2 MiB。
  - 恢复前依次校验结构、integrity、绑定（故事/修订/编译产物摘要/格式/运行时）、
    typed 变量快照；错误码可读：SAVE_ENVELOPE_STORY_MISMATCH、
    SAVE_ENVELOPE_REVISION_MISMATCH、SAVE_ENVELOPE_ARTIFACT_MISMATCH、
    SAVE_ENVELOPE_FORMAT_MISMATCH、SAVE_ENVELOPE_RUNTIME_MISMATCH、
    SAVE_ENVELOPE_INTEGRITY_INVALID、SAVE_ENVELOPE_STATE_INVALID；
    旧无绑定存档明确抛 LEGACY_SAVE_ENVELOPE_REQUIRED，迁移需显式调用
    `migrateLegacySaveEnvelope`（不接受隐式信任）。
  - verifier 改为 import **交付的** player helper（测试与交付入口不漂移）：
    在真实选择（变量已改变）之后保存 → 新进程恢复 → 继续到结局逐 step 对齐；
    额外证明"同一 state 加载进不同编译产物"被拒绝；8+ 负例矩阵；ZIP 直接输入
    （Windows bsdtar 限制时使用 .NET 解压后备）；单步 witness 才报
    NOT_APPLICABLE_SINGLE_STEP（同时仍做初始状态恢复与全部负例），不静默 PASS。
- 提交：`3d750de6`。
- 回归：`tests/test_interactive_ink_current_artifact.py` 11 项（含 3 项 opt-in 真实
  inkjs 2.3.2 运行：主作品、loop step-cap、ZIP 直接输入），全部 PASS；
  旧 `INKJS_2_3_2_TYPED_TEXT_SUBSET` 适配器输出仍由 golden SHA-256 冻结。

### 1.4 最终提交的验收证据重绑

- 原 588 checks 是 `933fea14` 上的结果，不能代表 6232f9d7 或修复后 HEAD。
- 修复后从**干净树** HEAD `cd140a39` 重跑 `python scripts/b07_e2e07_journey.py all`：
  - 648 checks / 0 failures，exit 0，`PASS_WITH_BLOCKED_ENVIRONMENT`；
  - Godot 4.7 与 inkjs 2.3.2 的 runtime/save-restore PASS 均来自本轮导出的真实产物；
  - 每个目标都通过真实 mounted API 记录绑定回执，再回读 `export-targets` 必须显示同一
    artifact_sha256 的 `artifact_evidence_status=PASS`；错误目标回执被 422 拒绝；
    同一产物重复导出保持 PASS；
  - E2E 证据新增 "product bound artifact" 列，且若运行 PASS 没有对应产品绑定证据，
    会作为 blocking unmet 拒绝整体 PASS（已实际生效）。
- 提交：`cd140a39`（harness+证据生成逻辑）、`5613739d`（在干净 CD140A39 上生成的证据入库）。

## 2. 统计口径校正（Hermia 指出 67 / 366 / 20）

原始交付统计的正确值以实测命令为准：

| 指标 | 原报告 | 实际 | 说明 |
|---|---|---|---|
| 改动文件数（b8371a48..6232f9d7） | 66 | **67** | 原报告在最后两个交付提交（HANDOFF、delivery 脚本修正）之前统计。实测 `git diff --name-status b8371a48 6232f9d7`：67 行 = 新增 57 + 修改 10 + 删除 0。分类明细以该命令输出为准，不在此重复归类。 |
| 交付目录文件数 | 365 | **366** | 递归文件数 366。其中 362 个被根 `SHA256SUMS` 覆盖，剩余 4 个是元数据表自身：根 `SHA256SUMS`、`DELIVERY_VERIFICATION.json`、`baseline/SHA256SUMS`（起始归档原始 6 文件校验表）、`git/SHA256SUMS`（git 子树校验表）。此前的 365 是在加入 `DELIVERY_VERIFICATION.json` 之前的值。 |
| 目标 ZIP 数 | 21 | **20 个目标 ZIP + 1 个归档证据 ZIP** | `artifacts/e2e07` 16 个（4 scope × 4 目标：Godot/Ink/RenPy/legacy）+ `artifacts/journey-target-projects` 4 个（旅程目标包的便于取用副本，与前者内容相同、路径不同）= 20 个目标 ZIP；`baseline/studio-v2-cloud-authoring-b8371a48-tests-evidence-sanitized.zip` 是起始基线归档证据，不是目标作品。因此 `.zip` 文件总数为 21。 |
| 校验覆盖关系 | 未说明 | 已说明 | 根 `SHA256SUMS`：362 条，覆盖除上述 4 个元数据文件之外的全部文件；`git/SHA256SUMS`：104 条，覆盖 git 子树 107 个文件中的 104 个（不含 `git/SHA256SUMS`、`git/delivery-manifest.json`、`git/RESTORE.md`）；`baseline/SHA256SUMS`：起始归档自带的 6 条原始校验。三张表作用域不同，**不是同一张表覆盖全包**；`DELIVERY_VERIFICATION.json` 记录根表 362 条的实际重算结果、bundle verify 与 clean-room replay 结论。 |
| git am 回放 | 声称可复原 | 更正 | `git am` 回放只保证**内容/tree** 一致（tree 相等已验证），不保证提交 SHA 相同；保留精确提交身份必须使用 `git/bundles/*.bundle`（含原始提交作者/时间/消息）。 |
| 分线 patch | 未说明 | 已更正 | 分线 patch（contract/ui/renpy/godot/ink/e2e）各自从基线起算，含重复历史；**不得把全部分线 patch 与 integration patch 依次应用**。恢复只用 integration 全量 patch 或 bundle。 |

修复轮增量统计（6232f9d7..修复最终 tip）：实测 38 个文件 = 新增 4 + 修改 34 + 删除 0。
修复轮交付子目录 `fixes-20261020/` 的文件与校验关系见该子目录的 `COVERAGE_AND_STATS.md`；
原交付的 67 文件与根目录旧文件均保留未动。

修复轮增量统计（6232f9d7..修复最终 tip）：38 个文件（新增 4、修改 34、删除 0），
其中 app 代码 8、tests 12、docs 10、frontend 3、scripts 3、其它 2。
原交付的 67 文件不受影响（旧目录保留）。

## 3. 修复轮测试总账（实际执行）

| 范围 | 结果 |
|---|---|
| 后端 B07 全量（交互/契约/ZIP 边界/证据绑定/三目标/E2E/挂载/冻结回归，opt-in 真实 runtime 开启） | **274 passed, 0 failed** |
| 前端互动叙事 15 测试文件 | **157 passed** |
| TypeScript + 生产构建 | `tsc -b` exit 0；`vite build` exit 0 |
| Ink pinned runtime（opt-in） | 主作品/loop step-cap/ZIP 直入 3 项 PASS |
| Godot 真机（headless） | 64 checks / 0 failures，两进程 save/restore PASS（沿用既有可信安装，未新增引擎） |
| E2E-07（干净 HEAD cd140a39） | 648 checks / 0 failed / exit 0 / PASS_WITH_BLOCKED_ENVIRONMENT |
| public build 白名单 | 27 passed / 3 failed，**均非本轮缺陷**：2 项为基线 17 个既有未审文件漂移，1 项为 Windows symlink 权限；本轮**未修改** `packaging/public-build.json`（Hermia 独占） |

## 4. 仍未验证 / 阻塞（继续如实保留）

1. Ren'Py 8.5.4 运行时与存档：本机无引擎，TARGET_RUNTIME_EXECUTED / SAVE_RESTORE_VERIFIED = BLOCKED_ENVIRONMENT；只有静态/结构证据。
2. Windows GUI 实际操作可用性：所有目标 NOT_RUN（headless 自动化不等于 GUI 验收）。
3. 原生 C# Ink runtime：NOT_RUN（只验证社区 JS port）。
4. 媒体播放：仅 manifest 引用，不打包不播放。
5. PostgreSQL：无授权 DSN，未运行。
6. public build 闭包：Hermia 所有；本轮新增 2 个待入白名单文件（见 §5）。

## 5. 尚需 Hermia 整合/处理

- `packaging/public-build.json` 新增 2 个文件（本轮新增、Hermia 独占该清单，我们未修改）：
  - `app/experimental/interactive_targets/ink/player/save_envelope.mjs`
  - `app/experimental/interactive_targets/ink/player/save-envelope.schema.json`
  另有基线既存 17 个文件漂移（与本专项无关，见原 HANDOFF §8）。
- 不需要 Hermia 修改 `App.tsx` / `ExperimentalWorkbench` / 共享路由 / 依赖锁 / Graph/Director/Asset 保护区。
- 未整合 Hermia 的 c40 分支，未触碰其工作区。

## 6. 恢复/复验

修复轮增量交付见 `fixes-20261020/`（从原交付 HEAD 6232f9d7 到修复 final tip 的
逐提交 patch、增量 bundle、完整 UTF-8 补丁 TXT、SHA256SUMS、RESTORE.md 与统计说明）。
两种恢复方式：
- 在原交付 HEAD 上应用增量：`git checkout 6232f9d7 && git am --3way <fixes TXT 提取出的 mbox>`；
- 或基于 b8371a48 应用"原交付全量补丁 + 修复增量补丁"（按各自 TXT 顺序，不要混用分线 patch）。

复验命令：
```
python -m pytest tests/test_interactive_export_evidence_binding.py tests/test_interactive_export_zip_boundaries.py \
  tests/test_interactive_ink_current_artifact.py tests/test_b07_e2e07_journey.py -q -m "not postgres_backend_only"
cd frontend && pnpm run build
python scripts/b07_e2e07_journey.py all        # 需 Godot 4.7 与 inkjs 2.3.2 vendor；缺失项会如实 BLOCKED
```
