# STUDIO_UX_PRODUCT_REPORT

**本轮**：UX-PRODUCT —— Studio 单产品用户体验补全（**不是** QingJian Interop）。
**批次**：第一批（UX-01 项目入口/创作意图/新手-专业模式 + UX-02 统一任务中心/审核收件箱）。
**日期**：2026-10-14（Asia/Shanghai）。
**分支 / PR**：`feature/v2-narrative-platform` / #47（保持 OPEN · Draft）。
**开工 HEAD**：`9ba3d773268e2eca5951466dc53f6d606d28da15`（Phase8 准备文档）。
**本轮提交**：`400b522`（前端解释器可移植性修复）、`<UX 批次提交见远端分支头>`（见下文提交清单）。

QingJian 联动、Adapter、双产品运行与协议映射专项本轮**全部暂停**；未修改 QingJian 仓库（其检出仍为 `a36231e`，干净）。PoemSeed Local Interop 1.0 协议语义与未来接入边界**未删除、未升级、未重新解释**。

---

## 1. 用户在第一批之后能做什么

| 能力 | 用户操作 | 走哪一个原 owner |
| --- | --- | --- |
| 知道怎么开始 | 工作区内点“创作开始”：**继续项目 / 空白开始 / 按创作意图开始**，可跳过意图，可在同一处切换新手/专业 | `GET /api/novels`（项目列表）、`POST /api/experimental/projects`（空白项目）、`GET/PUT /api/projects/{nid}/studio/preferences`（意图） |
| 表达创作意图 | 多选 + 自定义文案 + 跳过；界面明示“只影响推荐，不是权限，不限制模块，不触发任何生成”；采用建议布局只写偏好 | 同上（既有偏好行，带 `expected_version` CAS） |
| 新手 / 专业模式 | 一键切换；新手模式收起“制作操作契约/阶段/来源详情”并提供一键展开；两种模式共用同一份项目/素材/任务/图/草稿 | Studio 自有视图定位 owner（本地、有类型、per-project） |
| 找到全部任务与待审 | 工作区内点“任务中心”：任务队列 + 审核收件箱两个页签，按模块/状态/仅失败过滤 | `GET …/experimental/workspace/tasks`、inbox `GET`/`batch`/`{domain}/{id}/{action}` |
| 看懂状态 | 排队/准备/执行/等待审核/失败/取消中/已取消/UNKNOWN/来源过期/不可用分别展示；无进度时显示“进度未知（原服务未提供已完成/总数）”；执行完成与审核结果分开 | 原任务服务的原生状态；`projected_task` 对集合外状态一律 `UNKNOWN` |
| 正确恢复 | UNKNOWN 的首选动作是查询同一原任务；取消后台任务与取消传输分开，未确认终止时显示“取消请求已发送/待确认”；**没有**自动重试与自动重放 | 原 `actions`/`revision` 事实；`automatic_retries:false` |
| 审核候选 | 收件箱展示候选预览、输入摘要、来源版本与结果差异；采用/驳回绑定实际候选版本（`expected_version`）；重复提交同一版本本地即拒绝 | `UnifiedReviewInbox`（`DOMAIN_SERVICE` 审批权、`PER_ITEM_CHECKPOINT` 批量语义） |

**未接入**：UX-03…UX-09（第二批及以后）。本轮不声称任何模块达到完整产品验收。

## 2. 交付物（源码状态）

| 工作包 | 源码状态 | 位置 |
| --- | --- | --- |
| UX-01 入口/意图/模式 | **IMPLEMENTED** | `frontend/src/onboarding/`（14 文件）+ `frontend/src/creative/studioWorkspaceResume.ts`（模式与视图枚举，向后兼容扩展） |
| UX-02 任务中心/审核 | **IMPLEMENTED** | `frontend/src/taskcenter/`（15 文件） |
| 集成 | **IMPLEMENTED** | `frontend/src/creative/IndependentStudioWorkspace.tsx`（唯一被改的既有工作区文件：新增 3 个视图入口、模式开关、任务中心与创作开始挂载） |
| 工程 | **IMPLEMENTED** | `scripts/run_ux_product_checks.py`（验收 harness）、`docs/v2/ux-product/{PLAN,STATUS,DECISIONS}.md`、本报告、feature matrix 追加 |
| 无关但阻塞开发的既有缺陷 | **FIXED**（独立提交） | `frontend/vitest.setup.ts` + `frontend/vite.config.ts`（`python3` 缺口） |

**未新增任何第二 owner**：没有第二个项目库、意图存储、任务队列、审核系统、模型清单或时间线；模式落在 Studio 自有视图定位 owner；意图落在原偏好行。

## 3. 验证（验证状态，与源码状态分开）

收据：`docs/delivery/v2-development/ux-product-*.json|log`。全部 `sources_changed_during_check=false`。

| 检查 | 命令（节选） | 结果 | 收据 |
| --- | --- | --- | --- |
| File | `pytest tests/test_v2_production_workflow*.py …` | **PASS** 48 passed / 42 skipped | `ux-product-file-r2` |
| **PostgreSQL（真实）** | 项目自带 `scripts/run_v2_postgres_checks.py`（owned cluster） | **PASS** 14 passed / 8 skipped，exit 0 | `ux-product-pg` |
| Frontend（新面） | `pnpm exec vitest run src/onboarding src/taskcenter` | **PASS** 9 files / 87 tests | `ux-product-frontend-r2` |
| Frontend（新面 + 模式 owner） | 追加 `src/creative/studioWorkspaceResume.test.ts` | **PASS** 10 files / 96 tests | 本次会话直接运行 |
| **既有工作区集成回归** | `pnpm exec vitest run src/creative/IndependentStudio` | **PASS** 10 files / 117 tests（修复前曾 28 failed） | 本次会话直接运行 |
| TypeScript | `pnpm exec tsc -b` | **PASS** exit 0 | `ux-product-types-r2` |
| Build | `pnpm run build`（冻结脚本） | **PASS** exit 0 | `ux-product-build-r2` |
| 设计令牌 | `pnpm run lint` | **PASS** UI token guard 52 files | `ux-product-tokens-r2` |
| 受保护 seam | `pytest tests/test_v2_independent_workspace_api.py` | **PASS** 34 passed / 34 skipped | `ux-product-seam-r2` |
| 既有 `python3` 缺口回归 | 裸跑两个既有套件 | **PASS** 2 files / 22 tests（修复前 20 failed / 2 passed） | 提交 `400b522` 说明 |

### PostgreSQL 缺口已闭合（16.2 的结论得到证实）

“两个端口关闭”**不等于**整机没有可用环境。复用既有便携运行时 **PostgreSQL 16.15**（`D:\PoemSeed\Builds\studio-v2-host-5ed1cbee-20261011\Base\PostgreSQL\bin`），在**本工作树内** `.runtime/pg-ux-product/data` 一次性 `initdb`，再用项目自带 runner（owned cluster：数据必须在 `<root>/.runtime`、loopback、非特权端口）启动/停止：

- fresh 库 `v2_uxproduct`、`database_created=true`、20 个迁移全部 `applied`
- `empty_before_migrations.is_empty=true`（迁移前无任何对象）
- `startup_ownership=confirmed`、`server_stop=stopped`、`cleanup_status=completed`
- 结果 `14 passed / 8 skipped`，**exit 0**；收据 `docs/delivery/v2-development/ux-product-pg.json`（PASS）

未安装系统数据库服务、未改防火墙、未扫描整盘。

### `python3` 缺口（16.3）已修复并独立提交

两个既有套件用 `process.env.PYTHON || 'python3'`，而 `python3` 是 Linux/CI 默认（CI 的 Frontend unit suite 跑在 ubuntu-24.04）。本机只有 `python`。第二个独立原因：Windows GBK 控制台管道编码（`旅人`→`鏃呬汉`）。修复 = `frontend/vitest.setup.ts`（仅在 `PYTHON` 未设或指向不存在的路径时按平台回退，并设 `PYTHONUTF8=1`）+ `vite.config.ts` 的 `test.setupFiles`。**未改任何测试文件、断言、用例或 skip；未复制/改名解释器；未改 PATH。** 回归：裸跑 22 passed（此前 20 failed / 2 passed）。

## 4. 保留失败与自我纠正（未删除、未改写）

1. **默认模式选错并造成既有回归**：初版把新手模式设为默认，导致 `IndependentStudioGraphWorkspace` 等既有测试找不到“创作图”按钮，**28 个既有测试失败**。定位后改为**默认保持今天的完整界面**（`PROFESSIONAL`），新手模式改为显式选择；回归降到 11。
2. **入口面板与既有偏好表单标签冲突**：初版把“创作开始”面板自动渲染在素材视图，与既有 `StudioWorkspacePreferencesForm` 同时渲染“图片设计”等标签，触发既有测试的重复元素错误（剩余 1 failed）。**未改既有测试**，改为把入口面板放进独立“创作开始”视图（同时更好发现）。回归 **117 passed**。
3. **入口控制器挂载即发请求**：初版 `active` 过宽，在既有测试中产生额外请求（11 failed 的一部分）。收紧为“仅创作开始视图且项目为空时激活”，正常会话零额外请求。
4. 上述三次失败与修复过程均保留在本轮会话与收据历史中；后续收据不覆盖早期结果。

## 5. 明确未做 / 不声称

- **未执行**：用户 Windows 安装版最终验收、GPU/大模型推理、重型渲染长测、真实项目迁移、正式 RC/发布、双产品联动验收。
- **未接入**：UX-03…UX-09（后续批次）。
- **UX-08 的“项目提示助手”与青简入口**：本轮未实现；未来入口只保留隐藏/禁用位置，不显示“已连接”。
- **诚实的模型边界**：任务中心测试使用**协议夹具**，不是活后端往返；PG 验收覆盖的是 Phase7/批次的持久化面（workflow/意图），不是全部任务 owner 的 PG 行为。
- **既有遗漏不由本轮“消失”**：MP3、完整专业剪辑、模型兼容矩阵、3D/白模参考、研究/交付等历史缺口仍需按功能矩阵核对。
- **GitHub Actions**：账户账单锁，作业 0 步启动 → `BLOCKED_ACCOUNT_PLATFORM`；不重跑、不购买、不以“未启动”当通过，也不把本地专项验证称作完整 CI。

## 6. 数据迁移与兼容风险

- `WorkspacePreferences`（意图）**未改结构**；入口读的是既有 `GET /studio/preferences` 投影（`{version,intents,preset,custom_intent}`），写的是同一行 + `expected_version` CAS。
- Studio 本地视图定位记录**新增可选字段** `interface_mode` 与两个新视图值（`START`/`TASKS`）：旧记录仍有效，非法值判 `INVALID`，默认保持今天的界面；不会为存模式而伪造位置。
- 无数据库 schema 迁移；无资产/任务/Graph 数据改写。

## 7. 下一可执行项

1. 第二批：UX-03（Asset Browser 复用体验）+ UX-04（无限画布/节点工作流），按同一并行规则（两条产品写入线 + 一条验证线，共享文件由主代理串行整合）。
2. 给 `START`/`TASKS` 视图补浏览器级小范围检查（playwright 可选）。
3. 持续把每批次证据写入 `docs/delivery/v2-development/ux-product-*`，并在最终冻结输入树后重跑 harness。
