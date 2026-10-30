# 当前候选验收：宽回归、issue #14/#16/#17/#18 重验（2026-10-31）

本文件把 issue #14（回归/基线登记）、#16（PostgreSQL 备份恢复）、#17（行业导出/CJK 字体）、#18（Provider/凭据策略）按**当前候选**重新取证。基线对照为 A = PR #51 `317da4cc`；当前工作分支 = `work/backend-finalize-20261031`。**未运行项与人类决定项单列，不继承历史结论。**

## 1. 宽回归（issue #14 证据，Windows 11 · Python 3.11 · File 合成）

命令（工作分支，UTF-8 模式）：
`python -X utf8 -m pytest <103 个 test_asset_library/test_asset_query/test_taskcenter/test_export_/test_audio_/test_project_capacity/test_studio_asset_query/test_studio_runtime/test_identity/test_collaboration 文件> -q -p no:cacheprovider --no-header`

- 结果：**1431 passed, 9 failed, 57 skipped, 1 error**（307s；日志 `Validation/backend-finalize-20261031/round10-broad-regression.log`）。
- **9 failed + 1 error 全部在基线 A=`317da4cc` 的独立 probe worktree 上同样失败**（同机同 Python，命令相同），即本工作分支引入的新失败为 **0**：
  - `test_asset_library.py` 2 项（旧 `/api/novels/{nid}/assets` 上传关闭后的旧期望）；
  - `test_audio_shared_flac_real_candidate.py` 1 项、`test_audio_shared_measurement_independent.py` 1 项（`AUDIO_CAPACITY_WRITE_UNAVAILABLE` 关闭门，基线同样失败）；
  - `test_collaboration_text_models_route.py` 2 项（mock provider 投影旧期望）；
  - `test_export_execution_claim_independent.py` 3 项（Windows 符号链接权限 `WinError 1314`，环境）；
  - `test_audio_history_media_baseline_20261028.py` 1 error（自备 fixture `KeyError: PROJECT_ROOT`，环境/夹具）。
- 该宽回归只覆盖本次改动周边（资产/查询/导出/音频/容量/身份/协作等 103 个文件），**不是全仓库测试运行**，也未运行真实 PG/浏览器/模型/打包桌面。
- probe worktree 运行后已删除，未改动 A 分支或 main。

## 2. issue #16：PostgreSQL 备份恢复

- 当前候选通过（本次运行）：`test_e2e_database_fixture_contract.py`、`test_postgres_test_selection_20261030.py`、`test_postgres_migration_completeness_20261030.py`、`test_packaged_postgres_migrations_v070.py`（合成/夹具层合同；详见宽回归日志）。
- 环境事实：本机无 `psql`/`pg_ctl`、无 PostgreSQL 服务；**真实隔离实例的建库/迁移校验/备份/新实例恢复 NOT_RUN**。
- 结论：E2E URL 合同与迁移完整性在夹具层有证据；issue #16 的“真实隔离实例备份恢复”保持 **NOT_RUN**，不以夹具证据替代。

## 3. issue #17：行业导出打包与 CJK 字体门

- 代码/路径存在并接线：`app/industry_export_formats.py`（screenplay/shot-list/storyboard 打包、manifest、资源清单、`allow_missing`/`require_all`、摘要与项目归属校验、确定性 zip）经 `novel_service` 导出格式（`screenplay-package`/`shot-list-package`/`storyboard-package`/`storyboard-html`）与 `export_job_service` 挂载。
- **本批新增验证**：`tests/test_industry_export_packages.py` 8 项通过——包内布局/manifest/来源版本/determinism、Fountain 文本、shot-list CSV（含公式注入中和）、storyboard 包内已验证资源与 package_path、缺失资源 inventory 与 `require_all` 403 语义、摘要/归属不匹配不入包、环境变量/密钥不进入产物、空场景 schema 拒绝。
- CJK 字体：`app/pdf_export.py` 已实现可选嵌入字体候选（应用 OFL 字体/环境路径/Windows CJK）与严格模式 `AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT`/`require_embedded_font`，无嵌入字体时抛 `PDF_CJK_FONT_NOT_EMBEDDED`；`test_pdf_export.py` 通过（宿主若已有 CJK 字体则严格模式用例按设计 skip，日志本次为通过）。
- **未完成/人类决定**：仓库未内置可分发的 OFL CJK 字体文件，字体选择/授权是法律/产品决定；在选定并发货前，严格嵌入发货门保持 **BLOCKED（人员决定）**，不能把 STSong-Light 兼容回退当作 release 通过。
- 备注：`test_phase8_screenplay.py` 1 项在当前候选失败，但已在 A 基线同样失败（`KeyError: 'scenes'` 旧夹具期望），非本批导出包装回归。

## 4. issue #18：Provider 身份与凭据策略

- 当前候选通过（本次运行）：`test_credential_provider_lifecycle.py`、`test_provider_routing_policy_v2.py`、`test_runtime_provider_status_contract.py`、`test_v061_credential_passthrough.py`、`test_credential_vault.py` 等（与 issue #17 测试同批共 137 passed、2 skipped；见 `round10-issue-tests.log`）。
- 名称/身份边界：`app/provider_runtime_v2_model_center_snapshot_bridge.py` 及 `model_center` bridge 保持“只读快照、不执行/不探测/不解析凭据”，既有测试通过；Mock 不被当作真实 Provider 的合同继续由原有状态测试覆盖。
- **真实 Provider 请求仍 NOT_RUN**：未配置真实 API key、未读取用户 `.env`/OS 凭据库（普通 CI 边界）；真实调用需要显式授权（Provider/模型/配额/请求上限/数据边界/日志脱敏）后另行执行。

## 5. 结论与边界

- 宽回归证据支持“当前工作分支在覆盖范围内未引入新失败”；不代表全仓库/全平台通过。
- issue #16 真实 PG 备份恢复、issue #18 真实 Provider 调用、issue #17 CJK 字体授权与打包发货门分别保持 **NOT_RUN / NOT_RUN / BLOCKED(人员决定)**。
- 历史 issue #14 的 registry 仍以固定 SHA+环境记录；本文件只补充本轮命令与结果，不把局部通过写成全产品验收。
