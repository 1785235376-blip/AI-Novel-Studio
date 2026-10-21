# PoemSeed Studio V2 · 工作区前端台账（W-P0-03）

> **[HERMIA-FE-20261022]** · Atlas W-P0-03 / §0.2 · 对齐 `LUMEN_WORKSPACE_ARCH.md` · `LUMEN_VIDEO_IA.md` · `LUMEN_MISSING_VS_REPO.md`  
> 基线分支：`work/hermia-frontend-refactor-20261022`  
> 源码根：`/workspace/hr/wt/frontend/src`  
> **不是**验收完成证明。不 push、不碰 main、不大搬家 `novel/**`。不覆写 Lumen 文档。

---

## 0. ModuleSwitcher 默认铬条（6 钮 · 用户+Lumen 终裁）

| 序 | id | 标签 | 主表面 |
|---|---|---|---|
| 1 | `NOVEL` | 小说 | 纯 Editor（`panel=write`）+ ChapterTree；**不**嵌媒体/NLE |
| 2 | `IMAGE` | 图片 | 图片工作区 |
| 3 | `VIDEO` | 视频 | **≠ EDIT**：镜头脚本 + 无限画布 + 内置导演台（`LUMEN_VIDEO_IA`） |
| 4 | `AUDIO` | 声音 | 声音工作区 |
| 5 | **`EDIT`** | **剪辑** | **NLE** `nle/**` / `StudioTimelineEditor`（已补 registry 缺项） |
| 6 | `ASSETS` | 资产 | 资产浏览器 |

源：`ui/moduleRegistry.tsx` → `STUDIO_MODULES`（仅 6）。  
深链保留：`STUDIO_MODULE_OVERFLOW` = CONTROL / PLUGIN / WORKFLOW（命令面板可达，**不进**默认铬条）。

## 1. 工作区边界（多工作区并列）

| 边界 | 规则 |
|---|---|
| 小说中区 | **禁止**嵌入 Image/Video/Audio/EDIT(NLE) 画布；媒体在各自 ModuleSwitcher 工作区 |
| EDIT ↔ VIDEO/AUDIO | EDIT 提升为顶层剪辑入口；VIDEO/AUDIO 独立工作室内仍可挂时间线（制作操作） |
| CONTROL / PLUGIN | 不从 ModuleSwitcher 移除；主控=模型中心，插件=`PluginManagerPanel` |
| IndependentStudio | `LocalStudioModule` 含 `IMAGE\|ASSETS\|VIDEO\|AUDIO\|EDIT`；EDIT 冷启动默认 `PRODUCTION` 视图 |

---

## 2. 能力台账（nle / CONTROL / PLUGIN / 缺口）

| ID | Name | Source path(s) | How opened today | Completeness | Gap / Notes |
|---|---|---|---|---|---|
| W-FE-01 | 剪辑 ModuleSwitcher | `ui/moduleRegistry.tsx` `EDIT` | ModuleSwitcher「剪辑」 | complete | 用户确认顺序后落地 |
| W-FE-02 | NLE 时间线壳 | `nle/TimelineWorkspacePanel.tsx` + 子面板 | EDIT → `ModuleWorkspaceRoutes` `EditNleShell`（只读空时间线）；独立工作室 → `StudioTimelineEditor` | partial | 路由壳只读；可写路径在 IndependentStudio |
| W-FE-03 | NLE 轨道/片段/字幕/导出 | `nle/TrackHeader*` `ClipInspector*` `Subtitle*` `ExportDelivery*` `timelineOps*` | 经 TimelineWorkspacePanel | complete（面板） | 依赖上游 draft/controller |
| W-FE-04 | Studio 时间线编辑器 | `creative/StudioTimelineEditor.tsx` + `useStudioTimelineEditor` | IndependentStudio 制作操作（VIDEO/AUDIO/EDIT） | complete | EDIT 默认进 PRODUCTION |
| W-FE-05 | 主控 CONTROL | `ModuleWorkspaceRoutes` `ControlWorkspace` · `AiControlCenter` · `ModelCenter` · `MediaProviderSettings` | ModuleSwitcher「主控」 | complete | 保持可发现 |
| W-FE-06 | 插件 PLUGIN | `novel/PluginManagerPanel.tsx` · `PluginInspector` | ModuleSwitcher「插件」 | complete | 保持可发现 |
| W-FE-07 | 图片/视频/声音模块 | `ModuleWorkspaceRoutes` IMAGE/VIDEO/AUDIO | ModuleSwitcher | complete | 与小说中区隔离 |
| W-FE-08 | 资产 ASSETS | `AssetLibraryPanel` / IndependentStudio ASSETS | ModuleSwitcher「资产」 | complete | — |
| W-FE-09 | 工作流 WORKFLOW | `WorkflowPanel` · `AgentQueuePanel` | ModuleSwitcher「工作流」 | partial | — |

### 「代码有入口、UI 图曾缺」已闭合

| 缺口（改前） | 现状 |
|---|---|
| `nle/**` 大量面板无顶层 ModuleSwitcher | **已挂** `EDIT`；路由壳 + 独立工作室制作操作 |
| 剪辑相对 VIDEO 淹没 | **已提升** EDIT 在 AUDIO 与 ASSETS 之间 |
| CONTROL/PLUGIN 是否挤掉 | **保留**在 ASSETS 之后 |

---

## 3. 与小说台账交叉

见 `/workspace/hr/NOVEL_FE_INVENTORY.md`：N-P0-02 冷启动 `panel=write`；版本恢复 H-P0-02；小说中区不嵌 EDIT。

