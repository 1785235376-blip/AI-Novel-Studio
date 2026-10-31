# AI Novel Studio V2.0.0 发布说明（2026-10-31）

## 版本
- 产品版本：**2.0.0**
- 显示版本：V2.0（`release/version.json`，channel=`stable`）
- 一致性消费者：`pyproject.toml`、`app/__init__.py`、`frontend/package.json`、`.env.example`（`APP_VERSION`）、`README.md`、`docs/installation.md` 均由 `scripts/validate_release_version.py` 校验。

## main 合并内容
1. PR **#51**：Studio V2 后端能力补齐（Windows 游标密钥/项目删除信号）+ 安全硬化（merge `46ef2e12`）。
2. PR **#52**：全分支后端收尾（86 heads 核验/对账；Export/PG 018-020/VTT-OTIO/Canvas；容量账本/admission/历史写入计费；音频历史捕获-读取-迁移-恢复；运行时能力与 Studio 任务成本 UNKNOWN 合同；回归/安全复核）（merge `2d14f8c0`）。
3. PR **#53**：前端/后端对齐（frontend/UX/i18n 51 文件修正）（merge `d11c890c`）。

## 明确边界（不得写成验收通过）
- 真实验收 **尚未执行**：真实 PostgreSQL、真实浏览器/前端 E2E、真实模型/GPU、Windows 打包桌面、hosted CI、外部 NLE 均为 NOT_RUN；
- PUBLISHING 独立审阅、Windows ACL/junction 探测仍为 BLOCKED；
- CJK 字体授权、真实 Provider 授权、远程 frame provider 抓取策略、音频 canvas_return、额度策略等仍需产品/人员决定；
- 历史产品线（`#36`–`#49`、`#26` 等）未合入 main，保持原分支；`#47` 等仍为 DIRTY/超大分叉，合入会回退已验证的 V2 后端，未执行批量合并。
- 证据索引与逐分支状态见 `docs/delivery/BACKEND_FINALIZE_FINAL_REPORT_20261031.md`；历史合并回退：`git revert -m 1 <merge-commit>`。

## 2026-10-31 能力补充（V2.0 后）

### 容量 admission 覆盖全部 AssetLibraryService.create 调用方
`ENABLE_PROJECT_CAPACITY_ADMISSION` 开启时，容量 admission 从手工导入路由下沉到共享资产 owner `AssetLibraryService.create`：所有原始资产写入（模型 clady 参考、手工遮罩、视频参考帧、生产任务产物、prompt authoring、comic/portable/媒体/音频服务等 16+ 调用点）统一先 reconcile/UNKNOWN 拒绝/预留，成功后按实际 `bin+json` 字节 commit，失败先 reconcile 残渣再释放；手工导入路由传 `_capacity_admitted=True` 避免双重计费。默认 flag 关闭，默认行为不变。

测试：`test_project_capacity_create_coverage.py` 5 passed；容量组回归 75 passed；相关子组 71 passed（2 项旧 `/novels/{nid}/assets` 503 期望在合并前 main 同样失败，属于既有关闭门预存失败）。

未完成：非资产 owner 项目文件/导出/共享文档写入口、启动自动对账门、审批/撤权竞争、真实 PG/崩溃窗口；真实环境验收仍未执行。

### 能力补充：V2 全能力注册表（machine-readable）
`studio-runtime-capabilities/1` 新增 `capability_registry`（`v2-capability-registry/1`）：逐项列出小说/章节、剧本分镜、IMAGE、VIDEO、Graph、音频、音频历史、Timeline、导出、TaskCenter、资产查询、容量、成本、canvas_return、真实环境与阻塞项的状态、flag、证据与限制。默认状态下音频历史/容量为 `UNAVAILABLE_BY_FLAG`，真实 PG/浏览器/模型/打包桌面/hosted CI/外部 NLE 为 `NOT_RUN`，PUBLISHING/ACL 为 `BLOCKED`，F37 根因为 `UNKNOWN`。新增测试 4 项（只读/确定性、默认边界、flag 反映、形状与路径脱敏）；runtime capability 组合 18 passed。

