# 历史/远端分支后端差异与处置（相对 A = #51 `317da4cc`）

本表由只读脚本 `all_heads_triage.py` 生成：对每个非祖先 head 取其与 A 的 merge-base，得到分支自身改动（app/、database/migrations/、tests/），再与 A 当前 blob 逐文件比较：`equal_to_A`（已同内容）、`missing_in_A`（A 无该路径）、`divergent`（两边都有但不同）。

**边界**：本表以 A = #51 `317da4cc` 为比较对象；当前集成分支 `work/backend-finalize-20261031` 已在 A 之上额外整合 sibling checkpoint、canvas 准入、容量与音频历史批次，因此上述部分 missing/divergent 行已由该分支处置（见各分支 disposition）。本表不把历史分支的旧证据当作当前候选验收；`divergent` 不等于缺陷，可能只是 A 更新后的旧版本，需看 `branch..A` 是否有后续提交。

| 分支 | head | merge-base | 后端 missing/divergent/equal | 处置 |
|---|---|---|---|---|
| `archive/verified-studio-v2-20261017-5a6f697` | `41b2e96e2a` | `fed2404c8e` | 3/135/223 | 历史归档快照，不作为缺失功能来源 |
| `cloud/continuation-20261003` | `f8c141c39a` | `fed2404c8e` | 0/7/1 | 历史产品线（PR #36，旧云路由/迁移/导出），未纳入当前候选；小额后端差异需按 PR #36 范围逐项核对（本表列出文件名） |
| `feature/plugin-runtime-phase2b-windows-sandbox` | `5cae6e0035` | `773b52e715` | 3/4/0 | 不整合：第三方可执行插件保持 DENY_ALL；AppContainer 原型不进入当前产品范围（见任务约束） |
| `feature/provider-runtime-v2-model-center-snapshot-bridge` | `797d183e59` | `8d52f3cb99` | 1/0/0 | 已由 A 的后续版本取代：分支的 `app/provider_runtime_v2_model_center_bridge.py` 是早期 bridge；A 已有更完整的 `provider_runtime_v2_model_center_snapshot_bridge.py` + 测试（命名/接口不同，非缺失修复） |
| `feature/v2-narrative-platform` | `a072cf907f` | `fed2404c8e` | 3/135/223 | 历史产品线 PR #47，待逐项核对 |
| `fix/a43-document-chapter-identity` | `6dc09ffc71` | `fed2404c8e` | 3/132/75 | 历史产品线 PR #44，待逐项核对 |
| `fix/shared-authority-stream-terminal-r123` | `2c5b4e2f43` | `fed2404c8e` | 2/137/47 | 历史产品线 PR #40，待逐项核对 |
| `grok-phase1-acceptance` | `ff1511a3a3` | `c74b51f5b1` | 0/0/0 | 历史快照（无 app/tests 增量） |
| `grok-phase1-feature-closure` | `48b0b46a89` | `c74b51f5b1` | 0/5/0 | 历史快照；小额后端差异为旧版实现，未纳入（本表列出文件名） |
| `work/audio-asset-version-history-20261025` | `2acab55d2e` | `11d8615ccc` | 6/2/0 | 已审查复用并适配（本分支批次 3）：复用/适配历史 store 与 source-free 投影；旧 service/API/restore 模块未照搬，读取/显式迁移/恢复以既有 workspace+asset owner 重新实现；旧实现的惰性补基线改为显式迁移 |
| `work/dot-astra-v1-rc-r2` | `1ad947e458` | `fed2404c8e` | 1/56/19 | 历史产品线 PR #37，待逐项核对 |
| `work/dot-usability-20261015` | `58bbaad113` | `fed2404c8e` | 3/138/213 | 历史产品线 PR #48，待逐项核对 |
| `work/feature-completion-surface-freeze` | `665817243c` | `fed2404c8e` | 3/107/134 | 历史产品线 PR #45，待逐项核对 |
| `work/full-recovery-product-candidate` | `edb3e8577c` | `fed2404c8e` | 3/103/143 | 历史产品线 PR #46，待逐项核对 |
| `work/hermia-backend-align-20261030` | `252848a7c6` | `fe4f554122` | 0/0/0 | 仅前端/docs（后端独有增量 0），不纳入后端收尾 |
| `work/hermia-backend-verified-20261030` | `d657b42422` | `395ac26dd2` | 3/13/2 | 已整合（本轮 branch 批次 1：40 个后端/测试/迁移文件逐字复制 + 8 个冲突人工合并；本表相对 A 的 missing/divergent 即该批来源） |
| `work/hermia-canvas-adoption-auth-20261026` | `e5d5e4cc18` | `457ea4a5a4` | 0/1/0 | 已整合（本分支批次 1：canvas source-read 准入修复 + 2 个独立测试） |
| `work/hermia-export-artifact-recovery-20261028` | `f332dc9b6a` | `457ea4a5a4` | 0/7/4 | 已吸收/等价（本分支批次 1 逐文件核对：增量已被 A claim 语义与 S 导出修复覆盖，剩余差异为旧版本） |
| `work/hermia-export-integrity-rebuild-20261029` | `2e52c74705` | `395ac26dd2` | 0/1/0 | 已整合（本分支批次 1：导出完整性/取消/产物校验经 S checkpoint 合并） |
| `work/hermia-export-recovery-ownership-20261027` | `efd083c2b2` | `457ea4a5a4` | 0/7/4 | 已吸收/等价（同上，export claim/ownership 为 A 基线已有） |
| `work/hermia-mixed-cursor-safety-20261027` | `6bced26853` | `457ea4a5a4` | 0/6/3 | 已吸收/等价（混合游标安全为 A 基线已有） |
| `work/hermia-nsfw-entry-20261030` | `e91806e482` | `fe4f554122` | 0/0/0 | 仅前端 |
| `work/hermia-pagination-diagnostics-20261027` | `048fe2a122` | `457ea4a5a4` | 0/6/3 | 已吸收/等价（分页诊断/请求预算上下文为 A 基线已有） |
| `work/hermia-taskcenter-continuation-20261027` | `6b0db8e6e5` | `457ea4a5a4` | 0/7/3 | 已吸收/等价（同上） |
| `work/hermia-taskcenter-single-reader-20261027` | `6787f85e9f` | `457ea4a5a4` | 0/6/4 | 已吸收/等价（TaskCenter 回执/期限/严格只读由 A/S 覆盖） |
| `work/hermia-unified-loop-20261025` | `c41410da2f` | `f6e535a38a` | 0/0/0 | 前端/文档为主 |
| `work/hermia-usability-onboarding-20261030` | `d6b291abfe` | `fe4f554122` | 0/0/0 | 仅前端 |
| `work/local-interop-desktop-prep` | `e58c72b041` | `fed2404c8e` | 2/143/52 | 历史产品线 PR #42，待逐项核对 |
| `work/local-interop-v1` | `bcd60afb96` | `fed2404c8e` | 2/141/50 | 历史产品线 PR #41，待逐项核对 |
| `work/post-interop-r4-r5-ux-continuation` | `ad1a90dced` | `fed2404c8e` | 2/131/67 | 历史产品线 PR #43，待逐项核对 |
| `work/post-v1-feature-forward-r3` | `d712ab81e9` | `fed2404c8e` | 2/74/24 | 历史产品线 PR #38，待逐项核对 |
| `work/post-v1-r4-r5-ux` | `c6f2126115` | `fed2404c8e` | 2/137/46 | 历史产品线 PR #39，待逐项核对 |
| `work/studio-comic-media-7bad-tests-20261023` | `36e4a685ab` | `fed2404c8e` | 8/75/408 | 历史大分叉（约 1.5 万文件），待按模块核对，不批量合并 |
| `work/taskcenter-local-mixed-cursor-20261026` | `f6473e307e` | `31b6cb56ba` | 0/2/3 | 已等价（git cherry：A 已有等价提交；无独有后端增量） |
| `work/v2-eng-baseline-20261019` | `b0917977b7` | `fed2404c8e` | 5/136/222 | 历史产品线中间基线（#49 基座），历史大分叉，待模块级核对 |
| `work/v2-frontend-slices-20261019` | `8c215aea9b` | `fed2404c8e` | 6/138/222 | 历史产品线前端切片，待模块级核对 |
| `work/v2-frontend-slices-r2-20261019` | `0af49f9f9a` | `fed2404c8e` | 3/86/360 | 历史产品线前端切片，待模块级核对 |
| `work/v2-local-ci-community-20261019` | `2b26b1b833` | `fed2404c8e` | 6/138/222 | 历史产品线 PR #49，待按 #49 报告逐项核对（含 D-17/D-20 遗留） |
| `work/v2-six-frontend-slices-integration-20261019` | `ee2cec6fa2` | `fed2404c8e` | 3/86/360 | 历史产品线集成，待模块级核对 |

## 小差异历史分支的逐文件核对（A 后续提交计数）

### `cloud/continuation-20261003` @ `f8c141c39a`
- DIVERGENT `app/api.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/industry_export_formats.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/migrate_file_to_postgres.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/repositories/postgres/novel.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/repositories/postgres/serialization.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/services/export_job_service.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/services/novel_service.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）

### `grok-phase1-acceptance` @ `ff1511a3a3`

### `grok-phase1-feature-closure` @ `48b0b46a89`
- DIVERGENT `app/asset_providers.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/dependencies.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/services/agent_job_service.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/services/screenplay_service.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）
- DIVERGENT `app/services/v1_capability_service.py`：`branch..A` 在该路径上有 0 个后续提交（A 无后续提交，需人工比对语义）

