# 远端分支逐条核对清单（86 heads）

- 基线 #51: `317da4cc3c9b68d4f9e09e6222b4e110bad4e94b` tree `677156be5750dc93ca5b3fc8bdae73dfd414472e`
- 共同祖先 #50: `395ac26dd2de3d473e56964dbeb9ac9806facb85`；sibling: `d657b4242283fb9babba1fdb95239df2f9a78801`；main: `7b35e4cb4bd9efabe7cff54e67d7b24e8e469385`
- 统计：86 heads；#51 祖先 47，非祖先 39

| 分支 | SHA | tree | 与#51 | 独有后端文件(app/tests/migr) | PR | 处置 |
|---|---|---|---|---|---|---|
| archive/verified-studio-v2-20261017-5a6f697 | 41b2e96e2a | 167781d9a2 | +527/-590 | 358/430/3 | - | 历史归档快照，不作为缺失功能来源 |
| cloud/continuation-20261003 | f8c141c39a | 547a8068e8 | +3/-590 | 8/21/0 | #36D/OPEN | 历史快照/PR #36 范围，待按当前候选逐项核对 |
| feature/plugin-runtime-phase2b-windows-sandbox | 5cae6e0035 | 98aa3c0b5c | +5/-628 | 7/2/0 | #26D/OPEN | 原型/不支持：第三方可执行插件保持 DENY_ALL；不整合 AppContainer 原型 |
| feature/provider-runtime-v2-model-center-snapshot-bridge | 797d183e59 | 04e042d359 | +1/-609 | 1/1/0 | #31D/CLOS | 待核对（下一批）：Provider Runtime V2 快照桥，与 A 中已有 provider_runtime_v2_* 的精确关系未定 |
| feature/v2-narrative-platform | a072cf907f | 2535c23d7b | +375/-590 | 358/430/3 | #47D/OPEN | 历史产品线 PR #47，待逐项核对 |
| fix/a43-document-chapter-identity | 6dc09ffc71 | e65156c19b | +169/-590 | 207/240/3 | #44D/OPEN | 历史产品线 PR #44，待逐项核对 |
| fix/shared-authority-stream-terminal-r123 | 2c5b4e2f43 | ffe874c3bd | +144/-590 | 184/195/2 | #40D/OPEN | 历史产品线 PR #40，待逐项核对 |
| grok-phase1-acceptance | ff1511a3a3 | c025647a83 | +1/-704 | 0/0/0 | - | 历史快照，待核对是否被后继覆盖 |
| grok-phase1-feature-closure | 48b0b46a89 | 1d8b2691b8 | +2/-704 | 5/2/0 | #1/CLOS | 历史快照，待核对是否被后继覆盖 |
| work/audio-asset-version-history-20261025 | 2acab55d2e | 3f543bdc85 | +5/-434 | 8/2/0 | - | 未整合（下一批）：音频单资产不可变历史/显式恢复；该分支为旧实现线索，需按 AUDIO_HISTORY 账本补齐全部写入口、容量/授权/CAS/恢复合同后再开放 |
| work/dot-astra-v1-rc-r2 | 1ad947e458 | c973a2b9aa | +21/-590 | 75/88/1 | #37D/OPEN | 历史产品线 PR #37，待逐项核对 |
| work/dot-usability-20261015 | 58bbaad113 | 124ec1705e | +367/-590 | 351/425/3 | #48D/OPEN | 历史产品线 PR #48，待逐项核对 |
| work/feature-completion-surface-freeze | 665817243c | ff53a8f3f9 | +174/-590 | 241/269/3 | #45D/OPEN | 历史产品线 PR #45，待逐项核对 |
| work/full-recovery-product-candidate | edb3e8577c | 32aeeaf846 | +176/-590 | 246/273/3 | #46D/OPEN | 历史产品线 PR #46，待逐项核对 |
| work/hermia-backend-align-20261030 | 252848a7c6 | b9435b03fd | +33/-340 | 0/0/0 | - | 仅前端/测试（用户提示已核对：相对基线 app/tests/migrations 增量 0），不纳入后端收尾 |
| work/hermia-backend-verified-20261030 | d657b42422 | c72d8ed37c | +2/-150 | 15/40/3 | - | 已整合（本轮 Export/TaskCenter/VTT-OTIO/PG 对账批次，40 文件逐字等同核对） |
| work/hermia-canvas-adoption-auth-20261026 | e5d5e4cc18 | 37966a1b96 | +1/-325 | 1/2/0 | - | 已整合（canvas source-read 准入修复 + 2 个独立测试） |
| work/hermia-export-artifact-recovery-20261028 | f332dc9b6a | bb8d3ccdd2 | +5/-325 | 11/25/0 | - | 已吸收/等价：后端增量已由 S checkpoint 与 A 基线覆盖；差异文件逐条核对为旧版本（export_job_service 旧分支版、canvas 旧版、测试旧期望） |
| work/hermia-export-integrity-rebuild-20261029 | 2e52c74705 | f3eb900f5d | +1/-150 | 1/1/0 | - | 已吸收：其两个提交是 S checkpoint 的前驱（2e52c747 祖先关系），导出完整性修复整体保留 |
| work/hermia-export-recovery-ownership-20261027 | efd083c2b2 | 78cdf349da | +4/-325 | 11/24/0 | - | 已吸收/等价：export claim/ownership 由 A 基线（export_execution_claim 与 S 同 blob）+ S 恢复产物完整性覆盖 |
| work/hermia-mixed-cursor-safety-20261027 | 6bced26853 | 3c9a3c2684 | +2/-325 | 9/18/0 | - | 已吸收/等价：混合游标安全与请求上下文由 A 基线覆盖 |
| work/hermia-nsfw-entry-20261030 | e91806e482 | f490b5443c | +13/-340 | 0/0/0 | - | 仅前端 |
| work/hermia-pagination-diagnostics-20261027 | 048fe2a122 | 85266f1336 | +3/-325 | 9/21/0 | - | 已吸收/等价：分页诊断与请求上下文隔离已由 A 基线覆盖（taskcenter_cursor_http 与 S 同 blob） |
| work/hermia-taskcenter-continuation-20261027 | 6b0db8e6e5 | 0ab5011f58 | +4/-325 | 10/23/0 | - | 已吸收/等价：同上 |
| work/hermia-taskcenter-single-reader-20261027 | 6787f85e9f | 94f8987514 | +5/-325 | 10/25/0 | - | 已吸收/等价：TaskCenter 回执/期限保护由 A 基线与 S checkpoint 覆盖；差异文件为旧分支版本 |
| work/hermia-unified-loop-20261025 | c41410da2f | 75d4e7cc28 | +6/-403 | 0/0/0 | - | 前端/文档为主（无后端文件独有增量） |
| work/hermia-usability-onboarding-20261030 | d6b291abfe | 62cd41ba20 | +21/-340 | 0/0/0 | - | 仅前端 |
| work/local-interop-desktop-prep | e58c72b041 | af58460531 | +154/-590 | 195/204/2 | #42D/OPEN | 历史产品线 PR #42，待逐项核对 |
| work/local-interop-v1 | bcd60afb96 | 97d1952b7f | +151/-590 | 191/199/2 | #41D/OPEN | 历史产品线 PR #41，待逐项核对 |
| work/post-interop-r4-r5-ux-continuation | ad1a90dced | fd32163d45 | +164/-590 | 198/229/2 | #43D/OPEN | 历史产品线 PR #43，待逐项核对 |
| work/post-v1-feature-forward-r3 | d712ab81e9 | 19180ad000 | +52/-590 | 98/100/2 | #38D/OPEN | 历史产品线 PR #38，待逐项核对 |
| work/post-v1-r4-r5-ux | c6f2126115 | eb80a9fa5f | +139/-590 | 183/192/2 | #39D/OPEN | 历史产品线 PR #39，待逐项核对 |
| work/studio-comic-media-7bad-tests-20261023 | 36e4a685ab | 7dd49e8944 | +1085/-590 | 488/754/3 | - | 历史大分叉（约 1.58 万文件差异），与当前线分叉；按模块逐项核对属后续批次 |
| work/taskcenter-local-mixed-cursor-20261026 | f6473e307e | 9aad85d79c | +1/-411 | 5/10/0 | - | 已等价：git cherry 显示补丁在 A 中已有等价提交；矩阵无独有后端增量 |
| work/v2-eng-baseline-20261019 | b0917977b7 | aaac944983 | +381/-590 | 360/441/3 | - | 历史产品线中间分支（#49 基座），待逐项核对 |
| work/v2-frontend-slices-20261019 | 8c215aea9b | bad6bff417 | +409/-590 | 363/447/3 | - | 历史前端切片分支，后端范围待核对 |
| work/v2-frontend-slices-r2-20261019 | 0af49f9f9a | 77dffa005b | +851/-590 | 446/670/3 | - | 历史前端切片分支，后端范围待核对 |
| work/v2-local-ci-community-20261019 | 2b26b1b833 | b6dc7c4337 | +405/-590 | 363/447/3 | #49D/OPEN | 历史产品线 PR #49，待逐项核对（其报告含 D-17/D-20 遗留项） |
| work/v2-six-frontend-slices-integration-20261019 | ee2cec6fa2 | 11db472bf8 | +855/-590 | 446/670/3 | - | 历史前端切片集成分支，后端范围待核对 |
| cloud/canvas-task-20261023 | 4c55354811 | 3a0e7f822e | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| feature/model-center-phase1 | 334c681a26 | 18132badf2 | 祖先 | 0/0/0 | #27/MERG | 已包含于基线（祖先，无需另整合） |
| feature/model-center-phase2a-runtime-control | 02c4bc4cde | 0db6f7ea64 | 祖先 | 0/0/0 | #28/MERG | 已包含于基线（祖先，无需另整合） |
| feature/official-declarative-plugin-packs-v1 | 4b2cd1e5e8 | 53f4e62c38 | 祖先 | 0/0/0 | #21/MERG | 已包含于基线（祖先，无需另整合） |
| feature/plugin-runtime-foundation-phase1 | 7db2aa1cc0 | 84ba812a7c | 祖先 | 0/0/0 | #23/MERG | 已包含于基线（祖先，无需另整合） |
| feature/plugin-trust-signing-foundation | 45d8849076 | 58caf8a5ed | 祖先 | 0/0/0 | #29/MERG | 已包含于基线（祖先，无需另整合） |
| feature/provider-runtime-stable-identity-foundation | ea39475661 | 4d962f78b1 | 祖先 | 0/0/0 | #32/MERG | 已包含于基线（祖先，无需另整合） |
| feature/provider-runtime-v2-authoritative-snapshot-bridge | e994e7e5c1 | 4583ca62c8 | 祖先 | 0/0/0 | #33/MERG | 已包含于基线（祖先，无需另整合） |
| feature/provider-runtime-v2-contract-foundation | 1c2d0520fc | 41c1c98917 | 祖先 | 0/0/0 | #30/MERG | 已包含于基线（祖先，无需另整合） |
| feature/provider-runtime-v2-host-hardware-inventory | ad38ac70d2 | 361d7b5d25 | 祖先 | 0/0/0 | #35/MERG | 已包含于基线（祖先，无需另整合） |
| feature/provider-runtime-v2-runtime-requirements-authority | 7e24be1765 | 2b8c5ec157 | 祖先 | 0/0/0 | #34/MERG | 已包含于基线（祖先，无需另整合） |
| fix/p0-clean-regression-foundation | db5cabcc5c | c7791e6970 | 祖先 | 0/0/0 | #19/MERG | 已包含于基线（祖先，无需另整合） |
| fix/p0-generation-idempotency-root-cause | 0ba1f1f23c | d84dbeab39 | 祖先 | 0/0/0 | #22/MERG | 已包含于基线（祖先，无需另整合） |
| fix/p1-visual-continuity-time-jump-cut | cb7ec7fdee | d32acc8fe8 | 祖先 | 0/0/0 | #25/MERG | 已包含于基线（祖先，无需另整合） |
| work/asset-query-backend-20261023 | 8ecd7e80e8 | 7cf571603c | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/asset-query-scale-consistency-20261023 | 0563e561a5 | c907db8801 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/asset-usage-query-20261026 | c6ec952904 | d3d39ce5db | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/asset-usage-resource-guards-20261026 | 856d1ed334 | d6c8057a05 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/capability-completion-20261030 | 317da4cc3c | 677156be57 | 祖先 | 0/0/0 | #51D/OPEN | 已包含于基线（祖先，无需另整合） |
| work/capacity-residue-closure-20261030 | 2951a167cc | aa774afbc8 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/file-backend-safety-integration-20261026 | 457ea4a5a4 | ad5e7ff0db | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/grok-view-worksets-20261024 | a167022b0f | 592d333c6d | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-backend-contracts-20261025 | ffe1937911 | 447bfefcee | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-default-ui-20261025 | 02bbff087a | ca11fb9bba | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-default-ui-i18n-20261025 | 048c5ebb3c | 919584210c | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-default-uw-port-20261025 | 34eb95c7f2 | 4cc7207d5c | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-dualcanvas-integration-20261026 | fe4f554122 | dd0910d483 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-fe-contracts-20261025 | 3e72db70f6 | 9eac310e5e | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-frontend-refactor-20261022 | 6ba25ad7a4 | 4193b3c22c | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-i18n-20261025 | e8b4076842 | 24e846700e | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-loop-audio-20261025 | a14e8c02e5 | 6f14ebe827 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-loop-u1fix-20261025 | 93a1e35149 | efea6b0353 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-loop-u2-20261025 | c50a8d94d2 | 73ba9fb9ed | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-loop-u3-20261025 | 99a522aa85 | 1f80149cb7 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-loop-u4-20261025 | a0a56101a5 | 8d5b4fd548 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-theme-dualcanvas-20261026 | 03e8034a41 | ebbffb2f89 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/hermia-unified-workspace-20261023 | 51ff02b262 | f4cf078bff | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/security-bounded-20261030 | b49740d47c | 4186cea05c | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/studio-backend-integration-20261026 | 8ea4539981 | 3372d4742f | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/studio-v2-dual-canvas-public-20261021 | 252e88fed6 | 2ab9e25665 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/studio-v2-unified-integration-20261027 | 395ac26dd2 | 3e1457d440 | 祖先 | 0/0/0 | #50D/OPEN | 已包含于基线（祖先，无需另整合） |
| work/taskcenter-consistent-query-20261025 | 1587b57791 | 826d0b2917 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/taskcenter-export-owner-20261026 | 3e027e8b2d | 23079a7d58 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/taskcenter-lifecycle-cursor-20261025 | c2bb1d5e81 | 64647fd30f | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/taskcenter-local-export-cursor-20261026 | 31b6cb56ba | fc6f7e5510 | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
| work/taskcenter-rebuild-20261026 | 692c2c6657 | bdbf527b6f | 祖先 | 0/0/0 | - | 已包含于基线（祖先，无需另整合） |
