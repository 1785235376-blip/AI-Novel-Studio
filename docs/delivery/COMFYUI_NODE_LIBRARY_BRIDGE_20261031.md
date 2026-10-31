# ComfyUI 节点库只读桥接（2026-10-31）

## 背景与边界

Studio 画布的节点库是**封闭的可执行目录**（`_DEFINITIONS`、schema 1–7、受限执行适配器）。ComfyUI 的 `/object_info` 暴露任意自定义节点，直接并入执行目录会破坏权限、来源、审核和可复现性边界。

本批次实现的是**只读节点元数据桥接**：

- `GET /api/projects/{nid}/studio/graphs/comfyui-node-library?provider_id=...`
- 读取已保存且 `api_style=comfyui` 的 provider 配置，调用其 `/object_info`；
- 返回标准化节点描述，供后续画布“外部节点库”UI 充盈展示；
- **不注册可执行 Studio definition、不提交 workflow、不执行节点**；
- 需要项目 `domain.read` 权限，与 Graph 目录读取同一 authority 边界。

## 契约 `studio-comfyui-node-library/1`

```json
{
  "contract": "studio-comfyui-node-library/1",
  "source": "COMFYUI_OBJECT_INFO",
  "provider_id": "localcomfy",
  "available_providers": ["localcomfy"],
  "endpoint_origin": "http://127.0.0.1:8188",
  "observed_at": "…",
  "node_count": 2,
  "ignored_nodes": 2,
  "truncated": false,
  "nodes": [
    {
      "node_class": "KSampler",
      "definition_id": "comfyui.KSampler.<hash8>",
      "display_name": "KSampler",
      "category": "sampling",
      "description": "…",
      "output_node": false,
      "deprecated": false,
      "inputs": [
        {"name": "model", "type": "MODEL", "required": true, "has_default": false},
        {"name": "seed", "type": "INT", "required": true, "has_default": true, "default": 42},
        {"name": "sampler_name", "type": "COMBO", "required": true, "has_default": false,
         "choices": ["euler", "dpmpp_2m"]}
      ],
      "outputs": [{"index": 0, "type": "LATENT", "name": "samples", "is_list": false}],
      "studio_type_hints": ["MODEL", "INT", "CHOICE", "LATENT"]
    }
  ],
  "compatibility": {
    "contract": "studio-comfyui-node-compatibility/1",
    "purpose": "NODE_LIBRARY_METADATA_ONLY",
    "execution": "NOT_CONNECTED",
    "studio_executable": false,
    "requires_explicit_workflow_mapping": true
  },
  "limits": {
    "max_nodes": 2000,
    "max_inputs_per_node": 128,
    "max_outputs_per_node": 32,
    "max_choices": 128,
    "max_response_bytes": 4194304,
    "timeout_seconds": 10,
    "cache": "NONE_LIVE_READ_ONLY"
  }
}
```

## 安全与失败语义

- provider 必须已在 `asset-provider-config` 保存且 `api_style=comfyui`；未保存/禁用 → `COMFYUI_PROVIDER_NOT_CONFIGURED` / `COMFYUI_PROVIDER_DISABLED`（409）。
- endpoint 经 `validate_provider_endpoint` 校验；拒绝 userinfo、fragment、异常 scheme 等 → `COMFYUI_ENDPOINT_REJECTED`（409）。
- 使用既有 `_LocalImageTransport`：禁止 redirect、只访问已批准 origin、逐块限制原始/解压后字节。
- `/object_info` 读取超时 10s、上限 4 MiB、最多 2000 节点、每节点 128 输入/32 输出/128 choices、所有字符串有界并去除控制字符。
- 响应只暴露 `scheme://host:port`（不含 query/credential）；不写盘、不缓存、不执行。
- 直接输入只暴露标量原始类型的 `default`；模型/文件/URI 等默认值不返回，避免泄露本地路径或凭据。
- 失败码：`COMFYUI_NODE_LIBRARY_UNAVAILABLE`（网络/HTTP/超时）、`COMFYUI_NODE_LIBRARY_INVALID`（JSON/结构非法）、`COMFYUI_NODE_LIBRARY_TOO_LARGE`、`COMFYUI_NODE_LIBRARY_LIMIT_INVALID`。

## 逐步兼容路线

1. **本批（已完成）**：只读元数据导入 + 类型/端口/choices 描述 + `studio_type_hints`，作为节点库的“外部节点”数据源。
2. **下一批（未实现）**：为受控节点类建立显式 `ComfyUI node class → Studio workflow step` 映射白名单，先支持 `LoadImage → image_generate`、`SaveImage → image_review` 等少量闭环；所有映射需经过 provider 授权、来源/隐私、审核、成本和失败恢复合同。
3. **UI 集成（未连接）**：画布节点面板增加“ComfyUI 外部节点”只读分组；不可拖入执行画布，直到第 2 步映射完成。

真实 ComfyUI provider、真实自定义节点、真实执行均 **NOT_RUN**；本功能仅提供可审计的节点库元数据，不代表可执行扩展市场。
