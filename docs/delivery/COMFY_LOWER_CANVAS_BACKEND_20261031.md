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
- `GET` 无草稿返回 `version=0` 空图；`PUT` 需 `expected_version`，CAS 冲突返回 409 `{code:"LOWER_CANVAS_VERSION_CONFLICT", current_version}`；
- graph 校验：节点 ≤400、连线 ≤800、序列化 ≤1 MB、节点/边 id 唯一、端点存在、无自环；错误返回 400 字面 code；
- 响应始终带 `execution:"NOT_IMPLEMENTED"`；本接口不执行、不报价、不写资产。

## 未实现：run/execution

`POST .../runs`、`GET .../runs/{run_id}` 未提供。前端 CfGraph 当前只有节点结构（参数不可编辑，无 widget 值），无法构造可执行的 ComfyUI prompt；需前端补齐 params 后，在现有 provider recipe 授权/审核/成本/失败恢复合同上另行实现。不返回虚假 run_id、价格或状态。

## 验证

- `tests/test_comfy_lower_canvas_api.py`：10 passed（storage roundtrip/CAS/边界、proxy 白名单/headers/meta/503、路由挂载）；
- `tests/test_comfyui_node_library.py`：18 passed；
- 前端 merge 后 build PASS（Grok 分支合入 main）。
