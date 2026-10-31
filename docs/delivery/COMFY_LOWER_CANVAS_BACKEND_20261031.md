# ComfyUI 下画布后端接口（2026-10-31）

对应前端契约：`docs/frontend/BACKEND_COMFY_CONTRACT_20261031.md`。本批实现只读 `object_info` 代理与下画布草稿持久化；不执行 ComfyUI。

## 1. `GET /api/comfy/object_info`

- 从已保存且 `api_style=comfyui` 的 provider 读取原始 `/object_info`；无 provider/不可达返回 503 `comfy_unavailable`；
- `?provider_id=` 选择 provider（缺省取按 id 排序的第一个已保存 ComfyUI provider）；
- `?nodes=A,B,C` 白名单，最多 200 个、名字 ≤160；
- 默认 body = 原始 object_info JSON，头部带 `Cache-Control: no-store`、`X-Comfy-Source-Version`（SHA-256）、`X-Comfy-Fetched-At`、`X-Comfy-Provider-Id`；
- `?meta=true` body = `{object_info, source_version, fetched_at, provider_id, endpoint_origin, node_count, execution:"NOT_IMPLEMENTED"}`；
- 边界复用 `app/creative/comfy_node_library.py`：10s、4 MiB、禁 redirect、endpoint 校验；不写盘、不执行。

## 2. `GET/PUT /api/projects/{nid}/studio/lower-canvas/{kind}`

- `kind ∈ {image, video}`；通过原 studio invoker 做 `domain.read/domain.write` authority 校验；
- 存储于项目实验文档 collection `lower_canvas_v1`，image/video 各自一行：
  `{id, kind, version, graph, updated_at, updated_by}`；
- 节点可携带 `params`（widget 值）：仅 string/int/float/bool；最多 64 个 key、key≤80、字符串≤4096、总值≤12000；嵌套/超界/控制字符拒绝；无 params 的旧节点保持无该字段；
- `GET` 无草稿返回 `version=0` 空图；`PUT` 需 `expected_version`，CAS 冲突返回 409 `{code:"LOWER_CANVAS_VERSION_CONFLICT", current_version}`；
- graph 校验：节点 ≤400、连线 ≤800、序列化 ≤1 MB、节点/边 id 唯一、端点存在、无自环；错误返回 400 字面 code；
- 响应始终带 `execution:"NOT_IMPLEMENTED"`；本接口不执行、不报价、不写资产。

## 未实现：run/execution

`POST .../runs`、`GET .../runs/{run_id}` 未提供。前端已支持节点 widget 参数编辑并随草稿持久化/同步；但 CfGraph → ComfyUI API prompt 的映射、报价确认、状态轮询和产物回写仍需按现有 provider recipe 授权/审核/成本/失败恢复合同实现。不返回虚假 run_id、价格或状态。

## 验证

- `tests/test_comfy_lower_canvas_api.py`：10 passed（storage roundtrip/CAS/边界、proxy 白名单/headers/meta/503、路由挂载）；
- `tests/test_comfyui_node_library.py`：18 passed；
- 前端 merge 后 build PASS（Grok 分支合入 main）。

## 前端 wiring（2026-10-31）

- `DualStack` 仅在完整真实身份（actor + collaboration scope）下启用后端同步；无身份保持 session-only，不发送请求。
- `GET /api/comfy/object_info` → `parseObjectInfo(..., 'imported')` → `mergeImported`；PoemSeed 节点不被覆盖，503 时保留内置节点库。
- `GET/PUT /api/projects/{id}/studio/lower-canvas/{kind}`：首次加载云端草稿；本地已有草稿时本地优先并同步；`expected_version` CAS；409 冲突/不可用时保留本机草稿并显示状态，不覆盖服务端。
- 徽标：「云端草稿 · 不会执行 · 节点库只读」；仍未执行、不报价、不写资产。
- 测试：`comfyRemote.test.ts` 6 passed；`DualStack.remote.test.tsx` 1 passed；真实浏览器 mock：imported node=1、lowerWrites=4、nonGet=0、fails=0。


## 节点参数（widget）

- 前端下画布选中节点后显示参数编辑器（INT/FLOAT/STRING/BOOLEAN/COMBO），初始值来自 object_info default/choices；
- 参数写入 `CfNode.params`，随 node/edge 草稿一起保存到 localStorage、session store 和后端 `lower-canvas`；
- 后端 `LowerCanvasNode.params` 有界校验后原样返回；无参数的旧草稿保持兼容。

## 3. Run preflight / quote（本批新增）

`POST /api/projects/{nid}/studio/lower-canvas/{kind}/runs/preflight`（kind=image|video）：

- body `{expected_version, provider_id?}`；先核对当前下画布草稿版本（CAS），再从已保存的 ComfyUI provider 读取 `/object_info`；
- 只允许 `local=True` 的 ComfyUI provider（`LOWER_CANVAS_RUN_LOCAL_PROVIDER_REQUIRED`），避免云端任意节点执行；
- 将 CfGraph + params 转为 ComfyUI API prompt：
  - 节点/边/ID/输出节点/环/必填输入/端口类型/槽位全部校验；
  - widget 值按 object_info 类型/choices/默认值校验，未知参数拒绝；
  - 返回 `studio-lower-canvas-run-quote/1`：`quote_id`、`quote_digest`、draft_version、provider_id、node/edge/output 数量、`price.amount_micros=0`（本地无计费）、`expires_at`、`confirmation_required=true`；
- `execution:"NOT_DISPATCHED"`、`dispatch_contract:"NOT_IMPLEMENTED"`：**不提交 /prompt、不轮询 /history、不下载 /view、不写资产**。真实 dispatch 是下一批合同，需要显式确认 + 幂等 + 运行记录 + 资产回写。

测试：`tests/test_lower_canvas_runs_preflight.py` 12 passed（prompt 转换、参数/端口/环/版本/本地 provider/路由注册）。

## 4. Run dispatch / status / asset writeback（本批新增）

`POST /api/projects/{nid}/studio/lower-canvas/{kind}/runs`：

- body `{expected_version, quote_id, quote_digest, provider_id?}`；`quote_id` 必须来自 preflight 且未消费、未过期；同一 `quote_digest` 只启动一次；
- 通过后重新校验 draft/prompt，使用本地 ComfyUI 同步执行：
  - `POST /prompt`（一次，无自动重试）→ 有界 `GET /history/{prompt_id}` 轮询 → 对输出 `GET /view` 下载；
  - 结果限制：最多 32 张、单张 ≤16 MiB、总计 ≤64 MiB；仅 PNG/JPEG/WEBP magic；
  - 输出通过 `service.assets.create` 写入资产库，返回 asset ids/尺寸/SHA；
  - provider/asset 失败 → 生成 `status=FAILED` 的 run 记录（有界 error code），绝不伪造成功；
  - 进程/请求中断时 run 保持 RUNNING，可由 GET 查看；不提供虚假 COMPLETED。
- `GET /api/projects/{nid}/studio/lower-canvas/{kind}/runs/{run_id}` 返回 run 记录。
- 运行记录保存在 `lower_canvas_runs_v1`；quote 保存在 `lower_canvas_run_quotes_v1` 并标记 consumed。

测试：`tests/test_lower_canvas_runs_dispatch.py` 4 passed（成功/资产、失败无伪资产、stale quote、路由注册）；合并 run/preflight/lower-canvas/registry 组 36 passed。

## 5. 前端执行/确认 UI（本批新增）

- 下画布底部新增「运行…」按钮；仅真实身份且云端草稿 ready 时可用；
- 点击后先 flush 当前草稿 `PUT lower-canvas`，再 `POST .../runs/preflight`；
- 报价面板显示本地 ComfyUI、节点/连线数、0 标价、5 分钟确认窗口；必须点「确认运行」才 `POST .../runs`；
- 完成/失败面板显示 bounded error 或 asset ids；不自动重试；
- 草稿保存冲突/云端不可用时按钮禁用或提示，不伪造运行结果。
- 测试：`ComfyCanvas.run.test.tsx` 2 passed（报价确认、dispatch body、assets、ready gate）。

