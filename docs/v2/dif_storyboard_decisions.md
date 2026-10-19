# Storyboard 来源的保留与重建决定

“修改影响与选择性更新”中可以输入一个已保存的现代 Storyboard 文档 ID，读取当前作者在当前范围内可读的 Graph 直接引用，并沿用现有的预览、确认、保存与重开决定流程。没有正式资产时也可使用。

这里只覆盖已保存 Graph 中 `storyboard_plan.parameters.document_snapshot` 对这个文档的直接引用。`storyboard_prompt`、`storyboard_shot` 消费的端口、Timeline、资产血缘及其他间接关系不在此清单内。其他 owner 的覆盖保持 `NOT_EVALUATED`，未记录依赖保持 `UNKNOWN`。

一次来源观察最多返回 20 个目标；发现第 21 个目标时整次请求失败，不返回截断清单。Graph 目录继续使用原 owner 的最多 25 个图限制。每项决定使用 Graph 版本、定义/执行摘要、节点引用和项目 incarnation 绑定，显示名称不是稳定身份。

## 请求与权限

沿用 `/api` 与 `/api/v1` 下的以下接口，来源为 `{ "kind": "CREATIVE_STORYBOARD", "id": "<document-id>" }`：

- `POST /novels/{nid}/experimental/change-impact/query`
- `POST /novels/{nid}/experimental/change-impact/decisions/preview`
- `POST /novels/{nid}/experimental/change-impact/decisions`
- `GET /novels/{nid}/experimental/change-impact/decisions?source_kind=CREATIVE_STORYBOARD&source_id=<document-id>`

原 DIF 作者写权限仍然必需。Storyboard 受控文档读取、Graph 目录及每个 Graph 的读取分别经过原 owner 的 `domain.read`、可信 Host、scope 与 incarnation 检查。目录授权不能代替逐图授权；缺失 reader、缺失项目身份、权限撤销、Host 重绑或读取期间版本改变均拒绝整个观察。

`narrative_production_v2` 和原 DIF 功能链必须已启用：`change_impact_v2`、`temporal_story_graph_v2`、`world_character_engines_v2`、`asset_lineage_v2`。受保护 Graph 继续保留原有 Host 和执行能力开关检查。本功能不启用任何默认开关；schema7 的 `CREATIVE_GRAPH_CONDITIONS_V1` 与此入口无关，仍默认关闭。

## 保存边界

`KEEP` 和 `REBUILD` 只在既有 `change_impact_decisions_v2` 中保存意图。保存需要当前观察的选择、目标版本、预览摘要和独立 `request_id`；同一请求可核对重放，改动请求体不能复用旧 ID。每位作者在当前范围最多保留 25 份决定。

记录不会改动 Graph、Storyboard、成果锁、原稿、预检、任务或审核状态，不排队、不生成、不建立执行权限。真正重建仍需回到原模块重新预检、确认与审核。来源或目标改变后，旧决定显示为历史记录；项目 incarnation 改变后不会被新项目身份接管。

## 实现入口与检查

- [原 owner 读取适配](../../app/creative/impact_reads.py)：请求内 reader，保留原授权和版本检查，不缓存会话凭据。
- [有界观察契约](../../app/experimental/storyboard_impact_adapter.py)：严格投影、逐项身份比对、完整的 20 项边界。
- [原决定服务](../../app/experimental/change_impact.py)与 [API](../../app/experimental/change_impact_api.py)：复用既有存储、摘要、幂等与事务。
- [界面入口](../../frontend/src/experimental/StoryboardImpactDecisions.tsx)：复用 [原决定面板](../../frontend/src/experimental/ImpactDecisionPanel.tsx)，切换来源、权限范围或 client 时丢弃迟到的私有回包。

完整 Graph list/get 投影在 DIF 写事务开始前完成，避免重入原资产读取事务；提交边界由原 owner 的元数据与版本 fence 复核。不得将这些 reader 替换为仅凭小说写权限扫描原始 Graph/Timeline 存储的实现。

针对性 File 检查：

```powershell
python scripts/run_v2_checks.py dif-storyboard -- python -m pytest tests/test_dif02_storyboard_impact_api.py tests/test_dif02_storyboard_impact_adapter.py tests/test_dif02_storyboard_impact_business.py tests/test_r4_impact_decisions_additive.py tests/test_r4_impact_decisions_mounted_additive.py -q -m "not postgres_backend_only" -p no:cacheprovider
```

从 `frontend` 运行既有 `pnpm test -- src/experimental/StoryboardImpactDecisions.test.tsx src/experimental/ImpactDecisionPanel.test.tsx src/experimental/ChangeImpactPanel.test.tsx`，并运行原 TypeScript 与 UI token 检查。视觉检查遵守[既有设计系统](../ui/design_system.md)和[视觉基线流程](../ui/visual_baseline.md)。File 通过不能代替 PostgreSQL、真实模型或视频产品验收。
