# TaskCenter 本轮交付与验收状态

**结论：PARTIAL_IMPLEMENTATION_NOT_ACCEPTED。当前 HTTP 一致性游标未实现可用接线，不能宣称 M0–M7 完成。**

已实际编写并上传类型筛选、静态能力与诚实覆盖报告、显式 cursor 安全拒绝、
独立进程内游标组件、File/HTTP 反例、测量与回归 runner。独立源码审查发现两项 P2，
修正后无未关闭 P1/P2；这不是测试通过或产品验收。

## 固定起点与分阶段提交

| 阶段 | 完整 SHA | tree |
| --- | --- | --- |
| 固定起点 | ffe1937911cff32d4ebd4770b350674627501d3a | 447bfefcee8393b9b0907fe7daff2d5b044709da |
| M0 来源与阻断记录 | 35798e5adb416d8e8c638c8abdcff11cbddce6f4 | 61c4cfe7fdb9201637d77b12d816aaa0f35f11c6 |
| 查询/组件与反例候选 | 47dfea63a5568a107dd48c1c5c4d2bed76b50514 | 403c22f9e7995e6969f771cae38d09d917ec3a6f |
| 交接/真实 File 反例/测量 | 6017104ab768bd38ed9a81aea677982af5925888 | a7945aef7b0c262717d3b35944da8bfdbfaa0623 |
| 最终代码与专用云 runner | d227d3e0c7a17eda47d9d456c33775d9b27dfe6a | aa58fc7ceb9cb241e0ce29176025ec3dd48cd200 |

本报告与证据在后续仅文档提交中归档；该提交的精确 HEAD/tree 由交付后的远端读回提供，
不在文件中伪造自引用哈希。分支为 work/taskcenter-consistent-query-20261025。
所有 ref 更新均为明确 expected_sha 的非强制前进；未改 main、未创建发布。

## 实际实现

- authority 取原 17 个 reader authority，多值 OR、精确小写、去重、不改注册顺序。
- 原 scope fence、安全投影、200 行中央检查、q/failed_only 规则与旧 envelope/500 上限保留。
- 新 authority-only 报告有限 observed_total；旧 offset 响应不隐式增加新字段。
- 静态 capabilities 与本次 coverage 分离；不返回动态拒绝源/隐藏数量。
- 显式 page_mode=cursor 经原授权后固定 501；不会静默返回不一致 offset 页。
- 独立组件有界 FIFO、固定 TTL、签名 token、重复读取、冷启动/不同进程安全失效，
  但没有接入 HTTP，也不能自行证明真实 owner/权限身份。
- OpenAPI/接口示例、前端接入与重新读取规则见 ../../taskcenter_consistent_query_backend.md。

## 两类实质阻断

第一类是原 authority 生命周期接口。project_store.existing_owner_only/incarnation 可只读复用，
trusted session 有 binding_generation；但当前协作 membership/grant/branch 没有覆盖所有变化的可靠单调观察，
部分任务 reader 也缺可证明的原生命周期/revision。updated_at、可复用 scope 字符串或最终状态摘要不能防 ABA。
按用户边界，没有修改共享装配或原 owner，而是暂停该依赖并提供最小端口方案。
故真正跨页变化、项目/权限 ABA 的产品闭环仍未交付。

第二类是执行器。标准 Work 命令入口初始化失败且无已确认绑定云 executor。
随后实际新增并推送了只限本任务分支、公开仓库标准 ubuntu-24.04 的只读 GitHub workflow，
没有 secrets/services/模型/付费 runner。GitHub 已接受并创建运行，
但 job 在测试前失败，没有步骤：

- Run: https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/40206566004
- Head: d227d3e0c7a17eda47d9d456c33775d9b27dfe6a
- Job: 121208653993，completed/failure，steps=[]，runner_id=0，runner_name 为空。
- 开始/结束：2026-10-25 23:21:44 / 23:21:46（Asia/Shanghai）。
- 日志获取返回 BlobNotFound；check 报告有一条 annotation，但可用接口无法取得正文。
- 具体平台原因 UNKNOWN；没有把历史账单问题当作本轮已证实原因。

这不是代码测试失败，也不是基线失败重现。状态是 BLOCKED_BEFORE_TEST_EXECUTION。
没有重跑风暴、换账号、付费、替代 Codex 任务或用户本机后端测试。

## 验收矩阵

| 里程碑 | 状态 |
| --- | --- |
| M0 | 固定源码与边界已核对；原测试/有效红测 NOT_RUN |
| M1 | 已编写，运行未验证 |
| M2 | 独立组件部分实现；真实 HTTP 接线 BLOCKED/UNSUPPORTED |
| M3 | 未接线组件已编写；资源/TTL/令牌测试 NOT_RUN |
| M4 | 已编写，运行未验证 |
| M5 | 真实 File/HTTP 和合成组件测试已编写，NOT_RUN |
| M6 | 独立静态复验完成；动态回归/规模测量 NOT_RUN |
| M7 | 源码/测试/接口/哈希/评审/真实调度失败证据已上传；完整验收包未形成 |

真实 PostgreSQL、Windows 产品运行、前端/浏览器、真实模型均 NOT_RUN。
没有本轮红绿测试数量、既有失败预算、性能或内存数字。旧文档历史测试结论不作为本轮结果。

## 证据文件与复现

- source-hashes.json：九个最终源码/测试/runner 文件的 Git blob 与 SHA256，非运行证据。
- ci-attempt.json：真实调度/check/job 与日志获取结果，非合成 pytest 日志。
- status.json：机器可读分阶段状态。
- independent-review.md：独立反例、两项 P2 修正和限制。
- m0-baseline.md：初始环境与来源记录，保留历史当时状态。
- scripts/verify_taskcenter_consistent_query.py：精确固定基线、原测试、单新测试红测覆盖、
  候选四文件、同九文件回归、收集 nodeid/失败消息/源码加载与前后哈希验证。
- tests/test_taskcenter_query_measurements.py：N=0/3/199/200/201/2000、limit=1/50/100 的
  真实 File 原读取包装；只有实际运行 -s 后才产生测量，不预填样本。

可用云 executor 恢复后，在本独立分支准备仅声明的 .[dev] 依赖，
使用本任务临时 File/MOCK/无 cloud 环境运行上述 verification runner；
读取所有 raw logs、JUnit、已加载源码哈希和 source-integrity 后再判断。
runner 的 accepted 仅表示定向通过与回归逐项未新增失败，不表示完整产品或 HTTP cursor 通过。
