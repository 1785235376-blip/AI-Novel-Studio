# 后端能力补齐记录（2026-10-30，仅后端）

本轮按用户指示“只做后端、补齐缺失能力，真实前后端验证等下一步指令”执行。固定起点为上一轮安全提交 `b49740d4`（tree 见提交记录），工作分支 `work/capability-completion-20261030`；原工作树 `D:\PoemSeed\AI-Novel-Studio` 保持 detached `5af9bfc4` 未动。

本文件按已有交付账本（`INTERFACE_COVERAGE.md` 的 G-* 缺口、`STUDIO_V2_BACKEND_COMPLETION_LEDGER_20261028.md`、`AUDIO_HISTORY_COMPLETION_LEDGER_20261028.md`、`PROJECT_CAPACITY_CLOSURE_LEDGER_20261030.md`、`CAPACITY_U16_CONTINUATION_20261030.md`、`BACKEND_SECURITY_CHECK_20261030.md` §7/§26.8）盘点“仍缺的后端能力”，并记录本轮补齐、已存在待验证、以及仍需单独设计/批准的部分。**本文件不是完整验收或发布证明**；真实浏览器、真实 PostgreSQL、真实模型、打包桌面均未在本轮运行。

## 1. 能力盘点与处置

| 能力（来源缺口 ID） | 本轮前状态 | 本轮处置 | 真实环境验证 |
| --- | --- | --- | --- |
| Windows 资产游标签名密钥（Q3-OPEN / 38 项 503） | OPEN：Windows 无 `dir_fd`/`O_NOFOLLOW`/`O_DIRECTORY`，游标能力整体 503 | **已补齐**：新增 current-user DPAPI 后端（sealed 32-byte key + 独立 identity marker，缺失/替换/损坏/中断/硬链接/reparse 一律 fail-closed，不静默轮换、不降级明文路径）；能力合同在 Windows 报告 `PRESENT/NOT_VERIFIED` | 本机 Windows File/HTTP 合成：原 38 项 503 的游标套件现 **49 passed**；桌面端到端仍 `NOT_VERIFIED` |
| 项目实例身份：同 id 删除重建检测（G-ID-1） | 受阻：列表只有 id，无实例标识 | **已补齐（后端字段）**：新项目创建时生成持久 `project_incarnation`；File 列表补 `created_at`；`GET /api/novels`、`GET /api/novels/{id}` 返回该字段；同 id 重建得到新 incarnation | File 合成通过；PG 代码同路径已补 `metadata_json.project_incarnation`，真实 PG `NOT_RUN` |
| 冷启动清理信号：项目关闭期间被删（G-PURGE-1） | 部分实现：客户端只能靠“列表变化”在一次会话内清理；冷启动无权威信号 | **已补齐（后端信号）**：新增有界、按 workspace 隔离的删除墓碑日志与 `GET /api[/v1]/projects/deletions?after&limit`；本地服务删除与协作/管理/打包删除端口均记录；删除权威性不受日志失败影响；日志损坏返回固定 503 而非伪装空页 | File/HTTP 合成通过（本地与共享 workspace 过滤、分页、损坏日志）；真实 PG/打包 `NOT_RUN` |
| TaskCenter 分页（G-TC-1 / G-AUD-1） | 报告称受阻（≤1000 无分页） | **基线已存在**：`app/experimental/taskcenter_cursor*.py` 与显式 bounded projection pagination 已在当前 HEAD 集成；本轮未改代码，仅复验 | `test_taskcenter_cursor_independent.py` 等 162 项套件通过（Windows/File 合成） |
| Studio production jobs 过滤/分页（G-AUD-1） | 报告称无 owner/operation 过滤、无分页 | **基线已存在**：`StudioProductionQuery` 已支持 owner/operation 过滤与 limit/offset 分页，路由在分页/过滤前完成全部原 owner 校验；本轮未改代码，仅复验 | `test_studio_production_query.py` 等套件通过 |
| 音频单资产不可变历史与显式恢复（G-AUD-5 / A2） | 未整合：恢复写端关闭，能力合同 `version_history_read/version_restore = UNAVAILABLE` | **本轮不实现**，保持 `UNAVAILABLE`。原因：账本要求覆盖全部 metadata/promotion/lineage/relationship/delete/undelete 写路径、容量预留/对账、恢复确认绑定与用户已决定的“直接生成新当前版本”采用语义；部分实现会制造虚假历史或绕过关闭门 | 未运行 |
| 统一项目容量计量/预留/对账（PROJECT_CAPACITY M1–M7） | NOT_COMPLETE：唯一生产路径仍是仅按当前 branch 元数据逻辑大小的 `project_usage`；写门保持关闭 | **本轮不实现**，不做部分接线、不放宽任何关闭门。原因：需要跨 owner 事务/锁、物理字节归属、持久预约与启动对账合同，且在 PUBLISHING 独立审阅仍 BLOCKED 的前提下不能宣称完成 | 未运行 |
| Studio 生产任务成本显示（G-AUD-7） | 恒为 UNKNOWN（前端显示“未知”） | **本轮不虚构**：没有 provider 上报的价格/用量事实时不生成数字；该能力需要各 provider 适配器上报契约后再补 | 未运行 |
| 音频 canvas_return 仅 LOCAL_FFMPEG trim（G-AUD-4） | 部分实现 | **本轮不改**：扩展“采用到哪里”的目标语义属于产品决定，且会影响既有审核/采用合同 | 未运行 |
| Windows ACL/junction、PUBLISHING 独立审阅 | BLOCKED / NOT_VERIFIED（上轮自动审查拒绝） | **未重试、未换入口**，状态保持 | 未运行 |

## 2. 新增/变更的后端接口与契约

### 2.1 `GET /api[/v1]/projects/deletions`

有界项目删除墓碑读接口，用于客户端冷启动时清理已不存在项目的本地视图状态（不是项目读取权限）。

- 查询参数：`after`（非负整数游标，默认 0）、`limit`（1..200，默认 100）。
- 本地模式（collaboration/packaged 关闭）：只返回本地单用户产生的墓碑（`workspace_id` 为空）。
- 共享/打包模式：必须提供有效会话；只返回调用者 workspace 的墓碑；无法解析 workspace 时固定 403 `PROJECT_DELETIONS_SCOPE_UNAVAILABLE`，不泄露其他 workspace 的项目 id。
- 成功响应：`{"contract":"project-deletions/1","items":[{"project_id","deleted_at","incarnation"}],"next_cursor":int|null,"has_more":bool}`。
- 日志损坏/不可读：503 `PROJECT_DELETIONS_UNAVAILABLE`（不伪装空页、不覆盖原文件）。
- 日志位置与格式：File 数据根 `runtime/project-tombstones.json`，`{"schema":"project-tombstones/1","items":[...]}`；最多保留 2048 条（裁掉最旧），使用既有 workspace 互斥锁串行追加、`atomic_write` 替换；只记录 id/workspace/incarnation/删除时间，不含任何项目内容。
- 写入点：本地 `NovelService.delete`；协作/管理/打包 `AtomicPathMutationPort.delete_project`。删除完成后写墓碑；墓碑写失败只记 warning，绝不回滚已完成的删除（删除仍是权威操作）。

### 2.2 项目实例字段

- `FileRepository.create_novel` 与 `PostgresNovelRepository._create_in_session` 写入 `project_incarnation`（新 uuid）。
- File `GET /api/novels` 列表新增 `created_at`、`project_incarnation`；`GET /api/novels/{id}` 直接返回持久元数据。
- 旧项目无该字段时保持缺省（不猜测、不迁移）；客户端应按“未知实例”处理。

### 2.3 资产游标签名密钥（Windows 后端）

- `app/windows_dpapi.py`：最小 DPAPI 封装（current-user scope，`CRYPTPROTECT_UI_FORBIDDEN`，不落明文、不回显）。
- `app/creative/asset_query_cursor.py`：`posix_signing_primitives_available()` / `windows_dpapi_available()` / 聚合 `signing_key_primitives_available()`；`load_signing_key` 按平台选择安全后端，两者都不可用时保持原 503 拒绝。
- Windows 布局：`cursor.key.dpapi`（sealed key，仅 DPAPI 可解）+ `cursor.identity`（`asset-query-cursor-key/1\n<sha256(key)>\n` 独立标识）；读取时校验普通文件/单链接/reparse、读取前后身份一致；缺失/不匹配/损坏/空/中断/硬链接/目录 reparse 均 fail-closed，且不自动重建。
- `GET /api/projects/{nid}/studio/production-contracts/runtime` 的 `asset_query_cursor.key_primitives` 在 Windows 现在为 `PRESENT`，`end_to_end` 仍为 `NOT_VERIFIED`（等待桌面验收，未夸大）。

## 3. 本轮验证（Windows · Python 3.11 · File 合成）

新增测试与专项：

| 范围 | 结果 | 日志 |
| --- | --- | --- |
| Windows DPAPI 密钥后端（往返/跨进程/篡改/替换/中断/硬链接/reparse） | 54 passed / 14 skipped（POSIX-only 项跳过） | `logs/cap-win-cursor-key.log` |
| 原 Windows 资产游标套件（此前 38 failed/503） | **49 passed** | `logs/cap-studio-asset-cursor.log` |
| 游标 codec + fail-closed + runtime capability + asset query | 56 passed / 1 skipped | `logs/cap-studio-asset-query.log` |
| 项目墓碑 + 实例字段（journal/服务/删除端口/HTTP 双别名） | 12 passed | `logs/cap-project-tombstones.log` |

相邻回归：

| 批次 | 范围 | 结果 |
| --- | --- | --- |
| A | 项目 marker/quota、application contracts、ordinary binding、协作 admin、项目路径持久化、phase4/5 剧本数据库、导入 | 116 passed / 2 skipped（`logs/cap-reg-a.log`） |
| B | TaskCenter 游标独立、Studio production query、音频历史只读状态、资产查询、runtime capability | 162 passed（`logs/cap-reg-b.log`） |
| C | 导出 jobs、agent jobs、harness audit、agent chat、cloud canvas 创建恢复 | 119 passed / 3 failed（**预存失败**：`test_agent_chat_api.py` 3 项在固定起点 `b49740d4` 同样失败，`logs/cap-baseline-agent-chat.log`；不是本轮回归） |
| D | phase1 closure、幂等契约、导入审阅、文档导出重开、打包初始工作区/桌面组合、协作内容 API/HTTP 边界 | 100 passed / 4 failed（**预存失败**：`test_import_ai_review.py` 3 项 + `test_phase1_feature_closure.py` 1 项在固定起点 `b49740d4` 同样 4 failed / 8 passed，`logs/cap-baseline-reg-d.log`；不是本轮回归） |

## 4. 未运行与边界

- 真实浏览器/前端、真实 PostgreSQL、真实模型/GPU、打包桌面会话：`NOT_RUN`（按用户指示等待下一步真实前后端验证指令）。
- Windows 桌面端到端游标验收：`NOT_VERIFIED`（能力合同如实保持该状态）。
- 容量关闭门、音频历史恢复写端、调额：保持关闭/未实现，未做任何放宽。
- Windows ACL/junction 与 PUBLISHING 独立审阅：保持 `BLOCKED`，未重试。
- 删除墓碑是客户端清理用的辅助信号，不是审计、配额或内容恢复来源；直接调用仓库层删除（绕过服务/端口）不会记录墓碑，已在代码注释与本文件声明。

## 5. 回退

- 生产改动：`app/creative/asset_query_cursor.py`、`app/windows_dpapi.py`（新）、`app/project_tombstones.py`（新）、`app/repository.py`、`app/repositories/postgres/novel.py`、`app/services/novel_service.py`、`app/application/persistence.py`、`app/api.py`（仅新增删除信号路由）。
- 测试改动：新增 `tests/test_asset_query_cursor_windows_key.py`、`tests/test_project_tombstones_and_incarnation.py`；更新 3 个既有测试以匹配“两个安全后端”契约。
- 整体 `git revert <本轮提交>` 可回退；未改 main、未创建 Release、未部署。
