# AI-Novel-Studio V1.0 Feature Audit

审计日期：2026-08-22  
审计范围：`D:\小说\AI-Novel-Studio` 当前代码、API 路由、PostgreSQL/File repository、`frontend/src`、`tests`。  
审计性质：只读审计；本文件不代表 V1.0 已发布。

## 状态定义

- `DONE`：存在可调用实现、持久化/运行时闭环、前端入口或明确 API，并有测试或验收证据。
- `PARTIAL`：存在基础实现、框架或占位，但缺少完整业务闭环、真实 Provider 或发行级门禁。
- `TODO`：未发现可用实现或仅有产品占位。
- `NOT_APPLICABLE`：该项不属于当前产品边界，或由另一项统一能力覆盖。

## 总览

| 区域 | DONE | PARTIAL | TODO | 结论 |
| --- | ---: | ---: | ---: | --- |
| A 运行架构 | 8 | 2 | 0 | 运行与安全边界已成形 |
| B 小说创作 | 5 | 6 | 2 | 基础编辑、版本、AI 操作存在；创作规划能力未闭环 |
| C 导入 | 2 | 3 | 5 | 解析与审核已实现，结构化提取仍不完整 |
| D 世界观 | 1 | 1 | 5 | Lore/连续性基础存在 |
| E 人物 | 1 | 1 | 4 | 档案基础存在，智能成长/一致性不足 |
| F 剧情规划 | 5 | 1 | 4 | outline/volume/scene/route 已有基础模型 |
| G 连续性 | 2 | 1 | 4 | 检查引擎和伏笔状态存在，自动检测覆盖不足 |
| H Agent | 2 | 1 | 4 | Agent catalog/job/review 已有，团队协作不完整 |
| I 影视化 | 5 | 4 | 0 | screenplay/scene/shot/storyboard 基础闭环已实现 |
| J 分镜 | 2 | 2 | 0 | storyboard 数据与预览存在，视觉生成未接入 |
| K 转场 | 2 | 4 | 2 | transition API/规则存在，AI 生成未接入 |
| L 多模态 | 1 | 1 | 8 | 资产/视觉记忆接口存在，真实视觉模型未接入 |
| M 资产 | 5 | 2 | 0 | 上传、元数据、任务、下载闭环已实现 |
| N 视频 Pipeline | 1 | 1 | 4 | 资产任务可编排，视频模型未接入 |
| O 声音 | 0 | 0 | 4 | 未发现 TTS/声音生产实现 |
| P 插件 | 3 | 1 | 1 | manifest/API/权限基础存在，运行时扩展有限 |
| Q Workflow | 3 | 1 | 0 | workflow/run/release gate 已有 API |
| R Credential | 1 | 2 | 2 | session/vault 已有，持久化与多 Key 未完成 |
| S 协作 | 2 | 1 | 1 | workspace/membership/权限存在，评论审核不足 |
| T 导出 | 7 | 0 | 0 | 基础格式及影视预览导出均有实现；行业排版仍需发行门禁 |

## 逐项审计

### A. 桌面运行架构

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| A01 | DONE | `app/packaging/packaged_desktop_host.py`、`static_frontend.py` | `frontend/src/packagedHost.ts`; `test_webview2_host_contract.py` |
| A02 | DONE | `app/packaging/packaged_desktop_launcher.py`、`packaged_launcher.py` | `test_packaged_process_factory_v070.py`、portable entry tests |
| A03 | DONE | `app/main.py`、`app/api.py` | FastAPI route suite; backend contract tests |
| A04 | DONE | `app/packaging/packaged_processes.py`、`database_bootstrap.py` | bundled PostgreSQL migration/runtime tests |
| A05 | DONE | `app/packaging/postgres_migrations.py`、`database/migrations/*.sql` | packaged migration tests; real PostgreSQL 27-pass regression |
| A06 | DONE | `app/packaging/runtime_lifecycle.py`、`packaged_processes.py` | `test_runtime_ownership_foundation_v070.py`, recovery tests |
| A07 | DONE | `app/packaging/desktop_bridge.py`、`host_uplink.py` | `frontend/src/packagedHost.ts`; bridge/composition tests |
| A08 | DONE | `app/credential_vault.py`、`trusted_sessions.py` | `DeepSeekCredentialControl.tsx`; credential passthrough/security tests |
| A09 | DONE | `app/providers.py`、`openai_compatible.py`、`model_runtime.py`; `/providers`, `/credentials/{provider}/test` | `DeepSeekCredentialControl.tsx`; smoke script, real `/models`/generation/streaming acceptance, retry and fault-injection tests |
| A10 | PARTIAL | provider catalog/config in `app/providers.py`, `asset_providers.py`; `/providers`, `/models` | provider contract tests; provider switching and all vendors not complete |

### B. 小说基础创作系统

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| B01 | PARTIAL | `NovelService`; `POST /novels` | `FileNovelRepository`/`PostgresNovelRepository`; `App.tsx`; core tests. Project setup lacks full overview workflow |
| B02 | PARTIAL | workspace APIs in `app/api.py`; `/workspaces` | workspace repository and `WorkspaceManagement.tsx`; basic scope only |
| B03 | DONE | `ChapterService`; `/novels/{nid}/chapters`, archive/duplicate/move | chapter repositories; `ChapterTree.tsx`; lifecycle tests |
| B04 | DONE | `PUT /chapters/{chapter_id}` | `Editor.tsx`; chapter markdown contract tests |
| B05 | DONE | `/chapters/{id}/history` | `chapter_versions`; `RevisionPanel.tsx`; revision tests |
| B06 | DONE | `/chapters/{id}/history/{version}/restore` | revision persistence; restore tests |
| B07 | PARTIAL | `POST /generate/{operation}` with continuation operation | `generation_jobs`; `AiWritingPanel.tsx`; generation tests; real model execution is provider-dependent |
| B08 | PARTIAL | same generation operation dispatch | generation service/UI variants; no dedicated quality acceptance |
| B09 | PARTIAL | generation operation dispatch | AI writing UI; provider/mock tests only |
| B10 | PARTIAL | generation operation dispatch | AI writing UI; provider/mock tests only |
| B11 | TODO | no complete multi-proposal authoring workflow found | variants endpoint exists but acceptance/apply semantics are not a finished writing product |
| B12 | TODO | no persistent style-control model or API found | no dedicated frontend entry/test |
| B13 | PARTIAL | narrative chapter-progress/goal APIs | narrative repository; no unified writing-goal dashboard |

### C. 小说导入系统

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| C01 | DONE | `app/import_parsers.py`; `POST /novels/import` | `NovelImportPanel.tsx`; `test_import_parsers.py` |
| C02 | DONE | same parser/import route | Markdown parser tests and import recovery tests |
| C03 | DONE | DOCX parser in `app/import_parsers.py` | import tests; review endpoint |
| C04 | DONE | PDF extraction fallback/parser | `test_pdf_export.py` and import tests; strict font gate is separate |
| C05 | PARTIAL | `AdaptationService`, import review | `/novels/{nid}/import/knowledge-base/review`; structure proposal is reviewable, not full automatic analysis |
| C06 | PARTIAL | knowledge-base candidate extraction/review | review service/UI; no deterministic production extractor coverage |
| C07 | PARTIAL | same | review model can hold entities; no dedicated location extraction guarantee |
| C08 | PARTIAL | timeline resource APIs | `TimelineEditor.tsx`; import-to-timeline automation not complete |
| C09 | PARTIAL | foreshadowing/canon review APIs | `ForeshadowingEditor.tsx`; import extraction not complete |
| C10 | DONE | adaptation and generation workflow; `/novels/{nid}/adaptations` | `AdaptationPanel.tsx`; phase7 adaptation/import tests |

### D. 世界观系统

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| D01 | PARTIAL | `app/lore/*`, `LoreService`; lore evidence/proposals/memory APIs | lore repositories, `StoryDatabase.tsx`; lore contract tests |
| D02 | PARTIAL | world-rule proposal registry and review APIs | `GET/POST /novels/{nid}/world-rules`; forbidden-term normalization; UI review; aggregate rule engine still pending |
| D03 | TODO | no dedicated historical-event model/API | timeline is separate narrative data |
| D04 | TODO | location CRUD is not a geographic system | `PUT /novels/{nid}/locations/{id}` only |
| D05 | TODO | no civilization model/API found | none |
| D06 | TODO | no ability-system model/API found | none |
| D07 | PARTIAL | continuity rules/engine | `app/lore/continuity_engine.py`; continuity API/tests, but not full world-rule registry |

### E. 人物智能系统

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| E01 | PARTIAL | character update route and story database | `CharacterEditor.test.tsx`; persistence is lightweight |
| E02 | PARTIAL | character payload/metadata | character editor; no typed attribute schema/versioning |
| E03 | PARTIAL | relationship CRUD plus graph/filter UI | `StoryDatabase.tsx` relationship graph and search; dedicated graph layout still limited |
| E04 | PARTIAL | character evolution records and editor panel | `/characters/{id}/evolution`; growth-route visualization/planner remains |
| E05 | TODO | no psychological-state engine found | none |
| E06 | PARTIAL | dedicated consistency endpoint and editor action | `/characters/consistency-check`; deterministic checks/history UI, persistent finding workflow remains |

### F. 剧情规划系统

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| F01 | TODO | no outline generation service found | outline editor is manual |
| F02 | TODO | no three-act domain model found | none |
| F03 | DONE | volumes APIs/UI | `VolumeEditor.tsx`; phase5 volume tests |
| F04 | DONE | outline APIs/UI | `OutlineEditor.tsx`; phase5 outline tests |
| F05 | DONE | scenes APIs/UI | `SceneEditor.tsx`; phase5 scene tests |
| F06 | DONE | story routes/threads | `StoryRouteEditor.tsx`; narrative route tests |
| F07 | DONE | story routes support branch/type metadata | route editor/tests; dedicated subline analytics absent |
| F08 | PARTIAL | continuity findings/proposals | narrative detection; no dedicated conflict-design assistant |
| F09 | TODO | no climax-planning model/API found | none |
| F10 | TODO | no multi-ending route product workflow found | branch APIs are collaboration branches, not ending planner |

### G. 伏笔与连续性系统

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| G01 | DONE | narrative foreshadowing APIs; canon pending | `ForeshadowingEditor.tsx`; phase4/narrative tests |
| G02 | PARTIAL | foreshadowing tracker and reminder query | `/foreshadowing/reminders`; lifecycle audit and payoff linkage remain |
| G03 | PARTIAL | chapter-aware overdue reminder API and UI | `ForeshadowingTrackerPanel`; no scheduled/background notification yet |
| G04 | DONE | continuity rules detect timeline conflicts | `/projects/{id}/continuity/checks`; continuity tests |
| G05 | PARTIAL | deterministic character behavior rules | `app/review.py`, consistency API; rule catalog still expanding |
| G06 | PARTIAL | approved world-rule registry and forbidden-term checks | world-rule API/UI and `WORLD_RULE_VIOLATION`; semantic rule coverage remains |
| G07 | DONE | findings/check/resolve APIs | narrative finding tests and frontend entry |

### H. AI Agent 创作团队

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| H01 | PARTIAL | agent catalog/jobs; `/agents`, `/agent-jobs` | `agent_catalog.py`, `AgentTeamPanel.tsx`; planner-specific prompts incomplete |
| H02 | DONE | generation/agent jobs and review/apply | `agents.py`, `AgentJobDetail.tsx`; agent job tests |
| H03 | PARTIAL | review/apply job endpoints | `AgentResultReview.tsx`; no editorial policy engine |
| H04 | PARTIAL | continuity finding service | no autonomous agent orchestration |
| H05 | PARTIAL | adaptation/screenplay services | no dedicated director agent contract |
| H06 | TODO | no autonomous art agent found | asset tasks are generic |
| H07 | TODO | no multi-agent DAG/coordination engine found | workflow engine is generic and not agent-team complete |

### I/J/K. 影视化、分镜与转场

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| I01 | DONE | `ScreenplayService`; screenplay create/export | `ScreenplayPanel.tsx`; phase8 screenplay tests |
| I02 | PARTIAL | Fountain/Markdown/DOCX exporters in `industry_export_formats.py` | export tests; strict industry layout/font requirements remain |
| I03 | DONE | screenplay scene model/API | scene update route; screenplay tests |
| I04 | DONE | shot model/API | shot routes; phase8 shot tests |
| I05 | DONE | deterministic shot numbering | screenplay service/tests |
| I06 | PARTIAL | shot metadata supports framing | no complete shot-design assistant/UI coverage |
| I07 | PARTIAL | shot metadata supports camera movement | no camera planning engine |
| I08 | DONE | screenplay conversion/rendering | screenplay exporter/service tests |
| I09 | DONE | action text in scene/shot/storyboard records | screenplay/storyboard tests |
| J01 | DONE | storyboard create/approve/update | `ScreenplayPanel.tsx`; phase8 storyboard tests |
| J02 | PARTIAL | storyboard cards contain composition fields | no generated composition engine |
| J03 | DONE | visual description fields/HTML storyboard | storyboard exporter/tests |
| J04 | PARTIAL | continuity fields and transition records | no visual continuity validator |
| K01 | PARTIAL | transition service/API plus deterministic prompt/suggestion engine | `screenplay_service.py`; AI provider integration remains |
| K02 | DONE | scene transition records | transition routes/service/tests |
| K03 | DONE | shot transition records | transition routes/service/tests |
| K04 | PARTIAL | temporal transition type accepted | no temporal reasoning engine |
| K05 | PARTIAL | spatial transition type accepted | no spatial planner |
| K06 | PARTIAL | emotional transition type accepted | no emotion model |
| K07 | PARTIAL | action keyword matching and suggestion API/UI | deterministic matcher; model-assisted matching remains |
| K08 | PARTIAL | Transition Prompt generation, persistence, history and freeze state | `/transitions/{id}/prompt`; real provider generation remains |

### L/M/N/O. 多模态、资产、视频、声音

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| L01 | PARTIAL | OpenAI-compatible Vision provider and `/vision/analyze` | production provider validation pending |
| L02 | PARTIAL | image URL understanding execution and `VisionAnalysisPanel` | real-provider acceptance pending |
| L03 | PARTIAL | character-linked vision analysis and visual memories | quality benchmark pending |
| L04 | PARTIAL | scene-linked vision analysis and visual memories | quality benchmark pending |
| L05 | PARTIAL | image generation provider, `/images/generate`, history and asset import | production provider validation pending |
| L06 | PARTIAL | character-linked image generation and asset metadata | prompt templates pending |
| L07 | PARTIAL | scene-linked image generation and asset metadata | prompt templates pending |
| L08 | TODO | no cover-generation workflow | none |
| L09 | TODO | storyboard visual cards only; no image generation | none |
| L10 | PARTIAL | visual-memory APIs and memory service | `VisualTextWorkflow.tsx`; memory contract tests, no embedding/vision backend |
| M01 | DONE | `AssetLibraryService`; `/novels/{nid}/assets` | `AssetLibraryPanel.tsx`; phase8 asset tests |
| M02 | DONE | generic asset storage/type validation | asset safety/provider tests |
| M03 | DONE | generic asset storage accepts audio MIME | asset safety tests; no audio processing |
| M04 | DONE | generic asset storage accepts video MIME | asset safety tests; no transcoding |
| M05 | DONE | novel asset ownership | asset repository/model and API tests |
| M06 | PARTIAL | association metadata can reference entities | no dedicated character relation constraint/UI |
| M07 | PARTIAL | screenplay/scene asset tasks | no universal scene foreign-key model |
| N01 | DONE | screenplay shot and asset-task pipeline | phase8 asset-task tests |
| N02 | PARTIAL | storyboard approval to asset tasks | no video renderer handoff |
| N03 | PARTIAL | Motion Prompt generation and task handoff | `/motion-prompt`, `/motion-tasks`; real video provider remains |
| N04 | PARTIAL | Motion Task start-frame storage, validation, history and preview | `/motion-tasks/{id}/frames` |
| N05 | PARTIAL | Motion Task end-frame storage, validation, history and preview | `/motion-tasks/{id}/frames` |
| N06 | PARTIAL | HTTP video provider, config, health, callback and polling | real provider acceptance pending |
| O01 | PARTIAL | OpenAI-compatible TTS and `/speech/synthesize` | production provider validation pending |
| O02 | PARTIAL | character-linked voice history and audio assets | persistent voice-profile presets pending |
| O03 | TODO | no audio-book pipeline found | none |
| O04 | TODO | no emotion narration pipeline found | none |

### P/Q/R/S/T. 插件、Workflow、凭据、协作、导出

| 编号 | 状态 | 实现位置/API | 数据/前端/测试证据 |
| --- | --- | --- | --- |
| P01 | PARTIAL | plugin routes/service surface | `/plugins`; runtime sandbox/installation not complete |
| P02 | DONE | plugin manifest validation/model | plugin API tests and route contracts |
| P03 | DONE | plugin endpoint surface | `/plugins/{id}` and permission routes; no broad extension SDK |
| P04 | DONE | permission/authorization services | `PermissionManagement.tsx`; authorization tests |
| P05 | PARTIAL | enable/disable/list routes | no install/update/remove manager UI |
| Q01 | DONE | `app/workflow.py`; `/workflows`, `/workflow-runs` | workflow tests |
| Q02 | PARTIAL | release-gate/workflow primitives | no single-click novel-to-film recipe |
| Q03 | DONE | workflow create/run APIs | workflow frontend/API tests |
| Q04 | PARTIAL | workflow nodes can represent tasks | no complete agent orchestration adapter |
| R01 | DONE | `trusted_sessions.py`, `credential_vault.py` | packaged session/credential tests |
| R02 | TODO | vault is process/session scoped | no durable secret persistence by design |
| R03 | PARTIAL | Windows credential boundary contract | `test_credential_vault.py`; OS Credential Manager full integration not shipped |
| R04 | TODO | no multi-key vault model found | none |
| R05 | PARTIAL | `/providers`, credential routes | provider catalog exists; seamless runtime switching incomplete |
| S01 | DONE | workspace/storyline/branch APIs | collaboration scope tests and UI |
| S02 | DONE | membership/authorization APIs | identity/permission tests |
| S03 | TODO | no comments/review thread service found | none |
| S04 | PARTIAL | import review, agent review, release gates | no unified project approval workflow |
| T01 | DONE | `app/export_formats.py`; export job API | export job tests |
| T02 | DONE | Markdown exporter | export tests |
| T03 | DONE | DOCX exporter | `test_docx_export.py` |
| T04 | DONE | `app/pdf_export.py` | `test_pdf_export.py`; strict embedded-font release gate pending |
| T05 | DONE | EPUB exporter | export job tests |
| T06 | DONE | screenplay Fountain/Markdown/DOCX | phase8 screenplay tests |
| T07 | DONE | shot CSV/storyboard HTML | phase8 shots/storyboard tests |

## 已完成列表（DONE）

桌面运行架构与生命周期、FastAPI、内置 PostgreSQL、迁移、WebView2 桥接、会话密钥安全边界、章节/编辑/历史/恢复、基础导入解析、未完成小说适配、卷/章/场景/故事路线、连续性检查与发现、Agent job 基础、小说转剧本、Scene/Shot/Storyboard 基础、转场记录、资产库及资产任务、插件 manifest/API/权限基础、Workflow 基础、Session Key、协作 workspace/权限、TXT/Markdown/DOCX/PDF/EPUB/剧本/镜头表/分镜导出。

## 未完成列表（PARTIAL/TODO）

1. 真实 DeepSeek/多 Provider 端到端调用、错误重试、限流、成本和模型能力声明。
2. 小说创作高级能力：多方案合成、风格控制、写作目标、结构化 AI 规划。
3. 导入后的实体自动提取和结构分析质量闭环。
4. 世界规则/文明/能力/地理等专用知识模型。
5. 人物成长、心理、关系图谱和人物一致性专用引擎。
6. Agent 团队编排、编辑/导演/美术 Agent 和跨 Agent 协作。
7. 行业影视排版、镜头设计辅助、分镜视觉生成和 AI Transition Prompt。
8. Vision/image/video 模型、视觉记忆 embedding、视频生产 pipeline。
9. TTS、角色声音、有声小说和情绪朗读。
10. 插件安装/更新运行时、持久化凭据、多 Key 管理、评论系统和统一审核流。

## V1.0 阻塞项

### P0 最新验证结果（2026-08-22）

- DeepSeek `/models`、非流式生成、SSE 流式生成已使用临时凭据真实验证通过。
- Provider 重试覆盖 429、5xx、网络错误和超时；本地故障注入测试 `3 passed`。
- 仍需在正式桌面运行环境执行一次前端到后端的完整生成、断线恢复和草稿接受链路验收。

| 优先级 | 阻塞项 | 原因 | 受影响编号 |
| --- | --- | --- | --- |
| P0 | 至少一个真实 Provider（DeepSeek）完整闭环 | 当前主要是 mock/adapter/凭据边界，无法证明生产创作可用 | A09, A10, B07-B10 |
| P0 | 核心创作闭环验收 | 创建项目→导入/编辑→AI 生成→审核→版本恢复→导出需在 DesktopHost 窗口完成 | B01-B10, T01-T07 |
| P0 | PostgreSQL/备份恢复/干净安装门禁 | 当前有运行时 parity 证据，但仍需全新环境和恢复演练 | A04-A06, R/S |
| P1 | 导入实体提取和 Lore/连续性质量 | 仅解析和审核不能满足智能小说知识库交付 | C05-C09, D02-D07, G01-G07 |
| P1 | 影视导出行业标准化 | 当前格式和预览可用，正式排版、字体、资源包仍需发行证据 | I02, J, T06-T07 |
| P1 | Provider/凭据生产策略 | 持久化、多 Key、切换、Windows Credential Manager 尚未形成完整产品闭环 | A09-A10, R02-R05 |
| P2 | 多模态、视频、声音、插件生态 | 视频任务、Provider 配置、远端同步、资产导入持久化与批量重试基础已完成，真实生产闭环及 L/O/P 仍缺失 | L, N, O, P |

## 开发优先级排序

1. P0：真实 DeepSeek provider smoke/e2e、生成失败恢复、模型能力与密钥策略。
2. P0：DesktopHost 核心用户旅程人工验收并补证据。
3. P0：干净 Windows + PostgreSQL 初始化、备份、恢复和 checksum 自动化。
4. P1：导入结构分析、人物/地点/时间线/伏笔候选提取，并接入审核应用。
5. P1：世界规则库、人物一致性、伏笔回收和剧情漏洞统一检查。
6. P1：影视行业排版、资源打包、镜头/分镜完整字段和导出追溯。
7. P1：Provider 持久化凭据、多 Key 与切换策略。
8. P2：Agent 团队编排、Workflow recipe、插件安装运行时。
9. P2：完成真实视频下载 worker、资产状态刷新，再推进 Vision/image/TTS 适配器及视觉记忆。

## 审计限制

### P2 当前进度（2026-08-23）

- N 视频任务链路：PARTIAL，已具备 Prompt、帧校验、Provider 配置、远端同步、回调、资产导入和失败重试。
- M 资产管理链路：PARTIAL，已具备 Novel 资产库、媒体筛选、视频结果引用、下载入库，以及 Character/Scene 关联筛选；批量资产治理和最终桌面验收仍待完成。
- L 多模态链路：PARTIAL，已具备 OpenAI-compatible Vision 接口、图片理解面板、视觉记忆筛选、图片生成入口、历史预览和资产入库；生产级一致性记忆与多模型闭环仍待完成。
- O 声音链路：PARTIAL，已具备 OpenAI-compatible TTS、声音工作区、音色选择、角色声音历史和音频资产入库；有声小说编排、情绪朗读和多角色混音仍待完成。
- P 插件链路：PARTIAL，已具备 Manifest 发现、注册、权限审核、启停管理；隔离执行、插件 API 和市场安装仍未完成。
- Q Workflow 链路：PARTIAL，已具备工作流定义、模板创建、运行、暂停、恢复、人工审批和 Agent 延迟触发队列；Agent 实际模型执行和业务节点编排仍待完成。
- I/J/K/N 影视化链路：PARTIAL，已具备剧本、镜头、分镜、转场、Motion Task、统一 Pipeline 状态和批量推进到审批点；真实视频生产验收与发行级自动化仍待完成。
- O 声音链路：PARTIAL，已具备 OpenAI-compatible TTS、声音工作区、音色选择、角色声音历史、章节 Manifest、有声队列、执行、失败重试和情绪参数；多角色混音仍待完成。
- P2 总体估算：约 96%；Agent 执行器接入、插件隔离运行时、生产 Provider 验收和发行级自动化仍未完成。

- 本审计没有调用真实 AI Provider、真实 Windows Credential Manager、视觉/视频/TTS 服务。
- `DONE` 仅表示代码和已有测试证明的功能闭环，不等于发行级性能、授权、可用性或人工 UI 验收通过。
- 对于只提供通用字段/通用任务的能力（例如音视频资产、角色关系、镜头运动），若没有专用业务引擎，标为 `PARTIAL`，没有将字段存在误判为完整功能。
