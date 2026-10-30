# Motion frame 远程引用与云端审批信任边界（当前候选复核，2026-10-31）

历史 issue/交接项要求：先确认 motion frame 远程引用的**真实调用链与信任模型**，再判断是否存在“改 endpoint 后凭据/内网访问”风险，不得把未证实风险写成已确认提权。本文件记录当前候选（`work/backend-finalize-20261031`，`a70c5dde` 之后）的代码事实与新增加证据。

## 1. 代码事实（调用链）

1. 客户端只能通过 `PUT .../motion-tasks/{id}/frames` 写入 `start_frame/end_frame`；`is_traceable_frame` 仅接受 `http(s)` URL 或 `asset:/shot:/storyboard:` 引用（`app/services/screenplay_service.py`）。
2. 执行时 `ScreenplayService.execute_motion_task` → `resolve_motion_frame`（`app/media_frames.py`）：
   - URL 含 userinfo/fragment/缺 host → 拒绝；
   - **IP 字面量或 `localhost`** → `media_destination(url, provider.endpoint)` 走共享出站目的地守卫（解析 DNS、拒绝 link-local/multicast/unspecified/非 global，且本地服务只允许配置的精确 origin）；
   - **普通公网域名** → 直接作为不透明 `REMOTE_REFERENCE` 返回，`content_verified=false`；**后端不解析 DNS、不发起 HTTP 请求、不附加任何凭据**；
   - `asset:` 引用 → 经原 Asset owner 校验项目/branch/隐私策略后转 data URL（本地 provider 不需要额外云隐私审批；跨网络 provider 要求 `privacy_level=CLOUD_ALLOWED`）。
3. 云端执行前必须通过 `_require_motion_review`：审批摘要 `cloud_approval_request_sha256` 绑定 **provider endpoint、provider_id/model_id、prompt、start/end frame、constraints、媒体 owner（screenplay/novel/branch/actor/owner/workspace）**；endpoint 或任一绑定字段变化 → `VIDEO_CLOUD_PROMPT_REVIEW_REQUIRED`，在 provider 边界前失败。
4. 本地 provider（loopback/private，且排除 link-local/unspecified 等）不要求云端审批；远程引用仍是原样字符串交给 server-side 已注册 provider。

## 2. 新增证据（`tests/test_motion_frame_remote_reference_security.py`，10 项通过）

- 公网远程引用是**不透明引用**：monkeypatch `socket.getaddrinfo` 为“一调用即失败”，解析仍成功 → 证明后端**无 DNS/网络调用**；返回对象仅 `{kind: REMOTE_REFERENCE, content_verified: false}`。
- 拒绝带 userinfo/fragment/缺 host 的 URL。
- loopback URL 必须与配置的本地 provider 精确 origin 一致；换端口冒充本地 provider 被 `OutboundURLRejected` 拒绝。
- `media_destination` DNS-rebinding 反例：公网域名在检查时解析到 `10.0.0.9` → 拒绝；解析到 public IP → 通过。证明出站守卫按解析结果裁决。
- `provider_is_local` 边界：127.0.0.1/localhost/私网 = local；公网/`169.254.169.254` = 非 local。
- 云端审批摘要绑定：endpoint/model/frame/constraint/prompt/media-owner 任一变化 → digest 变化且执行前拒绝；无关 status/error 字段不改变摘要。
- 未审批/被降级/伪造 prompt/provider/model/request 摘要的任务全部 fail closed；本地 provider 跳过云审批。

## 3. 风险结论（不夸大）

- 当前后端自身不 fetch 远程 frame URL，因此**未发现后端侧 SSRF/DNS rebinding/凭据外带路径**；出站目的地守卫对本地/IP 目标有 rebinding 防护证据。
- **残留边界**：普通公网 URL 会作为引用转发给 server-side 视频 provider，provider 自身如何抓取该 URL、是否携带 provider 凭据属于 provider 适配器/外部网络边界，本项目未证明也未声称其为提权；若要彻底禁止，需要产品决定“远程 frame 是否允许 provider 侧抓取”，或把远程引用限制为显式白名单/本地代理。该决定点保留。
- 本次未运行真实 video provider/真实网络；上述均为 File/单元合成证据。

## 4. 未完成/决定点

1. 远程 frame 是否允许 provider 侧抓取、是否需要域名白名单/本地转存：产品与安全决定点（当前为不透明引用）。
2. 真实 provider 的抓取行为、DNS rebinding 于 provider 侧、凭据隔离属外部边界，NOT_RUN。
3. 若未来后端需要代为抓取远程帧，必须先复用 `media_destination` 并补重定向/逐跳校验/凭据隔离测试，当前代码不做该动作。
