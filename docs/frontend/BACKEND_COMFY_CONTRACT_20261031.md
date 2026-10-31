# 下画布 ComfyUI 兼容 — 后端契约草案（仅文档，未实现）
负责人：KONG ZIMING（后端）。前端：Hermia 线 [HERMIA-FE-20261031 DUALCANVAS-COMFY]。本文件只是需求，后端代码只读核对过 /workspace/hr/be-d657 (d657b424)。

## 现状（只读核对结论）
- 后端只有内部 `ComfyUIImageProvider`（固定工作流配方，供正式生图），**没有**：object_info 代理、下画布图保存、下画布执行、执行状态/费用接口。
- 已核实（只读 be-d657@d657b424）：`app/model_center/discovery.py` 的 COMFYUI 探测分支已在内部调用 ComfyUI `GET /object_info`（与 `/system_stats` 一起，第 586 行，节点名截至 4096 个），但只用于模型发现/前置条件判断，未暴露为前端可用的 API；因此第 1 条可复用该内部读取实现，只需新增对外只读路由。
- `canvas-views` 只服务上画布（主线）。
- 因此前端下画布标为「仅本次会话 / 仅本机草稿 · 不会执行 · 未连接 ComfyUI」，不发任何请求。

## 需要的接口（建议）
1. `GET /api/comfy/object_info` → 原样透传 ComfyUI `/object_info`（可按白名单过滤节点），带 `source_version`、`fetched_at`。前端已有 `parseObjectInfo(info, 'imported')` + `mergeImported()`，可直接合并（PoemSeed 自有节点不会被覆盖）。
   - 错误：ComfyUI 未连接 → 503 `{code:'comfy_unavailable'}`；前端保持内置节点库。
2. `GET/PUT /api/projects/{id}/lower-canvas/{kind}`（kind=image|video），按 user/project/project_instance 作用域，乐观并发 `version`；body = 前端 `CfGraph {nodes:[{id,t,x,y,title}], edges:[{id,a,as,b,bs}]}`。
3. `POST .../runs/preflight` + `POST .../runs` + `GET .../runs/{run_id}`（本批已实现）→ preflight 生成 quote；dispatch 校验 quote 后同步执行本地 ComfyUI（/prompt → /history → /view），结果写入资产库，run 记录可读。仍不自动重试、不支持云端 ComfyUI；前端执行/确认 UI 尚待接入。
4. 产物图片存储：结果写入资产库（复用现有 assets），返回 asset_id，前端用「接入上画布」作为参考图快照。

## 数据约定
- 端口类型 = ComfyUI 大写类型（MODEL/CLIP/VAE/CONDITIONING/LATENT/IMAGE/MASK/CONTROL_NET/UPSCALE_MODEL/CLIP_VISION(_OUTPUT)/VIDEO…），`*` 通配，逗号并集；INT/FLOAT/STRING/BOOLEAN/combo 为 widget 不是端口。
- PoemSeed 节点（参考图/导演备注/分镜提示词/变体提示词/文本）输出 IMAGE/TEXT，只有它们能「接入上画布」。

## 后端实现状态（2026-10-31，KONG ZIMING）

已完成：

1. `GET /api/comfy/object_info`
   - 返回已保存 ComfyUI provider 的 `/object_info` 原始 JSON（前端 `parseObjectInfo()` 可直接解析）；
   - `?nodes=KSampler,SaveImage` 可选有界白名单；`?meta=true` 返回 `{object_info, source_version, fetched_at, provider_id, endpoint_origin, node_count, execution:"NOT_IMPLEMENTED"}`；
   - `source_version` / `fetched_at` 同时放在响应头 `X-Comfy-Source-Version`、`X-Comfy-Fetched-At`；
   - 未配置/不可达 → **503** `{"code":"comfy_unavailable"}`，前端保留内置节点库；
   - 只读：不提交 workflow、不执行节点；复用既有有界传输（禁 redirect、4 MiB、10 s）。
2. `GET/PUT /api/projects/{id}/studio/lower-canvas/{kind}`（kind=image|video）
   - 按项目 scope 存储 `{nodes:[{id,t,x,y,title,params?}], edges:[{id,a,as,b,bs}]}`；`params` 为 widget 值（string/int/float/bool，有界）；
   - `PUT` body `{expected_version, graph}`，版本冲突 → **409** `{"code":"LOWER_CANVAS_VERSION_CONFLICT","current_version":N}`；
   - 边界：400 节点 / 800 连线 / 1 MB；重复节点/边 id、缺失端点、自环 → 400 明确 code；
   - 响应带 `execution:"NOT_IMPLEMENTED"`；只存草稿，不执行、不报价、不写资产。

未实现（下一步）：

3. `POST .../lower-canvas/{kind}/runs` 与 `GET .../runs/{run_id}`：Convert to ComfyUI prompt、报价确认、执行状态、产物写资产库。阻塞点：前端节点参数尚不可编辑，CfGraph 没有 widget 值；需要前端补 params 后再实现真实执行与费用合同。当前后端不提供任何虚假执行/价格/状态接口。
4. 节点参数编辑（本批新增）：下画布选中节点后可编辑 INT/FLOAT/STRING/BOOLEAN/COMBO widget，值写入 `CfNode.params` 并随草稿持久化/同步；后端接受有界 params；仍未执行任何节点。
5. 前端 wiring 已接入（上一批）：
   - 真实账号/作品身份（`resolveWorkspaceIdentity().kind === 'real'`）时，`DualStack` 拉取 `GET /api/comfy/object_info`，用 `parseObjectInfo` + `mergeImported` 合并到节点库；503 时保留内置节点库；
   - 下画布草稿通过 `GET/PUT /api/projects/{id}/studio/lower-canvas/{kind}` 同步，携带 `X-Session-Token` / `X-Branch-Id`，使用 `expected_version` CAS；
   - 无身份仍保持 session-only（内存），不发任何请求；本地 localStorage 仍保留离线缓存；
   - 云端冲突/不可用时保留本机草稿并在状态栏标注，不覆盖；
   - 徽标从「未连接 ComfyUI」改为「云端草稿 · 不会执行 · 节点库只读」；仍不执行、不计费、不调用模型。
   - 测试：`comfyRemote.test.ts`（6）、`DualStack.remote.test.tsx`（1，mock fetch）；真实浏览器 mock 验证 importedCount=1 / lowerWrites>=1 / nonGet=0。

测试：`tests/test_comfy_lower_canvas_api.py`（10 passed），`tests/test_comfyui_node_library.py`（18 passed）。
