# TaskCenter File 协作游标：重建稳定切片

代码基线：`c2bb1d5e81dc7d15036c40a8aa9409e4c5bc71f6`。
候选代码冻结：`97ab69b40435b18b1b5b946ad0e73774aa6da103`。

## 可用范围

两条原 API 入口保持共用原授权、原 reader、原安全投影与有限窗口：
`/api/novels/{nid}/experimental/workspace/tasks`、`/api/v1/novels/{nid}/experimental/workspace/tasks`。

游标只支持两种互斥的非 packaged / 实际 File 原所有者模式：
1. 原 local / `semantic_import`，不携带 session、branch；不重新命名成协作。
2. collaboration / 单选 `agent_team`，窗口内只允许无 source 引用的原 team run。

协作必须有原 session、active membership、scope topology 与所选授权 grant 的生命周期证据；项目及 team 文档也必须已有可靠证据。读取不补建、不迁移旧文档。真实权限变更仍由原授权链处理。token 只绑定安全投影与私有承诺，不携带业务缓存、session 或私有正文。

新证据由原 identity、scope、authorization 与 ExperimentalStore 写入各自原文件，保留原锁、原补偿与原授权语义。Session commitment 绑定 resolver 实例和 token generation。Team reader 的原 recovery_required 投影被纳入核对。

## 明确不覆盖

- 混合来源、多 authority cursor、带 source 引用 team、PG、packaged 游标、托管部署/CI 与真实模型执行不支持或未运行。测试实际在 dot 原生云工作区执行，不是用户电脑。
- 不承诺全历史、全 ABA、未观察 grant 的短暂增删、外部备份回放或跨文件崩溃原子性。
- 不改 BOT 前端/SDK、不改 Work 资产引用查询/graph_api、不改音频版本。
- 旧新-owner 崩溃/多进程证据已丢失，未复用。本轮另建20例：8次 SIGKILL、4次双进程竞争（合计16个子进程）及8次进程内注入失败，全部新跑通过。它仅验证指定原文件写边界，不等于跨文件崩溃一致性、真实掉电或完整 HTTP 历史。原 local store process 测试另列。

## 恢复与证据

旧未发布本地实现及测试对象在当前工作区不可用；本轮从可验证的公开 c2bb 基线重建。旧测试数量不作为当前结果。
当前 fresh 候选挂载 HTTP：64 PASS，exit0；原 local48与协作16。新原所有者专项分别 identity7、scope/grant34，并各有原消费者回归。各组有重叠，不能累加为独立总数。
冻结97ab核心291 PASS，exit0，无外部 app 模块加载；首次240秒上限超时不计通过，900秒上限复跑终结通过。
独立外部24例通过（22+2不重叠）；新原所有者进程边界20例通过；原9文件安全/协作/媒体/Agent/导出/v1/制作查询回归198 PASS，exit0、无外部 app 模块加载。每组命令、日志、模块来源及结果见 verification.json 及原始证据。未运行项不记 PASS。

## 后续

先交付该稳定切片。第二个同模式来源必须先核对其实际 owner、原写边界与生命周期；当前没有可直接复用的可靠 mixed-source 承诺，不开放混合游标。
