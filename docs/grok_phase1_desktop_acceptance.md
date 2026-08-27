# AI Novel Studio Phase 1 DesktopHost 验收委托

## 范围

只验收第一阶段现有能力的真实性和 DesktopHost 窗口闭环，不实现新功能，不进入第二阶段。当前构建版本 `0.7.0`；DesktopHost DLL SHA-256：`98F02E42A9E7A50CE94D6A748F3D226E869890396D1256AC8CEABCC81A08A740`。

四个 Python 基线缺陷不属于本阶段回归，不要修改、删除或跳过：并发生成幂等性、visual continuity scene jump、user preference 返回字段契约、world rule payload normalization。

## 验收前提

- 使用当前源码构建，不使用历史 staging 快照。
- 使用全新隔离 runtime 和数据库；不要读取或修改用户 `.env`、用户数据库或真实凭据。
- 先关闭其他 AI-Novel-Studio/Backend/DesktopHost 实例，确认 named mutex 已释放。
- 记录 DesktopHost PID、后端 PID、数据库端口、工作区/用户/会话 ID、构建哈希和操作时间。
- 所有请求记录 URL、方法、状态码、脱敏响应摘要和 request ID；禁止输出 token、密码或 API key。

## DH-01 启动

启动当前构建。确认窗口可见、应用 ready、WebView2 初始化完成、bootstrap 成功、监听仅限 loopback。保存窗口截图、启动日志和退出码。

## DH-02 项目概览

从真实窗口选择测试工作区，进入或创建测试小说，打开“概览”。确认真实字数、章节数、人物/地点/时间线/伏笔/规则/研究资料计数、待处理项、近期活动和写作目标摘要。确认没有“服务尚未接入”伪装成已实现能力。保存截图和 overview 请求证据。

## DH-03 研究资料

在窗口中创建标题为 `Phase1 Desktop 验收资料` 的记录，设置来源类型、状态和唯一标签；筛选并找到它；编辑标题或摘要并保存；新建并删除另一条临时记录并确认二次确认；切换到另一小说确认无法读取或删除原记录。研究资料必须按 durable sidecar 边界验收：File 与 PostgreSQL profile 均使用 `v1_capabilities/research.json`，不是 PostgreSQL 原生表。保存每一步截图、实体 ID、请求和响应摘要。

## DH-04 重启持久化

保留 `Phase1 Desktop 验收资料`，正常关闭 DesktopHost，确认 DesktopHost/Backend/WebView2/PostgreSQL 退出且 named mutex 释放。使用同一隔离业务目录重新启动，进入同一小说，确认资料内容、版本和归属仍正确。保存重启前后截图、进程退出证据和读取请求。

## DH-05 Agent 诚实状态

从功能导航打开“Agent 团队”，选择确定性模式并运行任务。确认状态为 `VALIDATED`，显示“契约校验，未调用模型”，且没有审核或应用到正文入口。确认空结果不被显示为创作完成。保存任务详情截图和请求证据。

## DH-06 视频任务配置缺失

通过真实窗口准备合法剧本、章节、镜头、分镜和未锁定转场；Motion Prompt 非空且已保存；首帧和尾帧为合法、可追踪资产引用。创建 Motion Task，确认 POST 返回任务 ID，任务列表因 `motion-tasks-created` 事件刷新并显示 `PENDING`。在未配置视频 Provider 环境执行，确认显示 `VIDEO_PROVIDER_NOT_CONFIGURED` 或等价配置缺失；不得出现 `SUCCEEDED` 或 `placeholder://video/*`。记录剧本、转场、任务 ID、首尾帧、请求/响应和截图。

## DH-07 单实例回收

正常关闭后再次启动，再次正常关闭。确认无 `SingleInstanceError`，端口和互斥锁均正确释放。记录每次启动/退出码和 PID。

## DH-08 日志审计

审计本轮 DesktopHost、Backend 和 PostgreSQL 日志：不得包含凭据/密钥、`placeholder://video/*` 成功产物或未处理异常。记录日志路径和脱敏 grep/扫描摘要。

## 证据格式

为每项输出：

```json
{
  "step_id": "DH-02",
  "result": "PASS",
  "timestamp": "<ISO-8601>",
  "operator": "Grok",
  "desktop_host_pid": 0,
  "build_sha256": "98F02E42A9E7A50CE94D6A748F3D226E869890396D1256AC8CEABCC81A08A740",
  "entity_ids": {},
  "request_ids": [],
  "screenshots": [],
  "log_locations": [],
  "actual_result": "<observed result>"
}
```

结果只能使用 `PASS`、`FAIL`、`BLOCKED` 或 `NOT_RUN`。只有 DH-01 至 DH-08 全部 `PASS` 才能判定 DesktopHost 窗口门禁通过。不要把浏览器 Playwright、后端 API 或启动截图当作窗口业务证据。

## 输出报告

分别报告：DH-01 至 DH-08 结果、窗口截图目录、日志目录、构建哈希、退出码、runtime 清理结果、四个既有 Python 基线缺陷，以及是否满足第一阶段完成条件。明确当前版本不是 V1.0 正式发行物。
