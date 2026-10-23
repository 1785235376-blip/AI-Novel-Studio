# PoemSeed Studio V2 资产查询 · 最终交接

已连续完成 M0–M3 后端实现、真实验证、独立审查及分阶段GitHub上传；未改前端、图片生成节点、任务队列/状态、公共授权框架或main，未force-push/发布Release。仓库公开范围已核对；上传仅代码、合成测试、脚本和汇总文档，未上传凭据、用户数据、临时存储、cursor key/token或原始运行日志。

独立分支：[`work/asset-query-scale-consistency-20261023`](https://github.com/1785235376-blip/AI-Novel-Studio/tree/work/asset-query-scale-consistency-20261023)。起始工作区干净，从固定起点建立，没有覆盖原资产分支。正式owner仍为 `AssetLibraryService`，Studio适配器为 `IndependentWorkspaceService`；授权仍走原 `invoke`，查询校验位于其内。

## 提交账本

| 阶段 | 完整commit | 完整tree |
| --- | --- | --- |
| 固定起点 | `8ecd7e80e8b706bc45d9e442647613dd041c1b90` | `7cf571603ce0db9ecd84950fed4c2ff396215fdd` |
| M0 | [`677cae6241e0de5abf1510a8916e91e4574626c1`](https://github.com/1785235376-blip/AI-Novel-Studio/commit/677cae6241e0de5abf1510a8916e91e4574626c1) | `5048adea7bca22086a1448d9526eade902f0f14a` |
| M1 | [`21d82b7138cd7d033c73a236b902caf164644284`](https://github.com/1785235376-blip/AI-Novel-Studio/commit/21d82b7138cd7d033c73a236b902caf164644284) | `c6bd8b0c1f2dbd9d4e4f110e15a3ad661df1fa0d` |
| M2 | [`07c297692782596865f761c35d8bef54cd64b80f`](https://github.com/1785235376-blip/AI-Novel-Studio/commit/07c297692782596865f761c35d8bef54cd64b80f) | `bc748e48f604ee08f68c85f0649f3074aa780e12` |
| M3，最终应用源码 | [`b6bc11bba23d93d7a593e688ebad6d3e873880d3`](https://github.com/1785235376-blip/AI-Novel-Studio/commit/b6bc11bba23d93d7a593e688ebad6d3e873880d3) | `3b408ebfe11b3b380cf13477c5941ce6a903e060` |

对照基线 `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`。每阶段上传后均通过GitHub读回远端HEAD及tree，使用expected SHA保护分支更新。最后的文档收据提交仅新增本账本并校正历史措辞，应用源码/测试与上表M3相同；收据的最终SHA/tree由GitHub该提交元数据与最终交付回复提供。

## 验收结果

实际主环境：Python 3.12.14 / FastAPI 0.161.1 / Starlette 1.9.0 / Pydantic 2.14.1 / httpx 0.28.1，符合项目依赖声明。

| 验证 | 实际结果 |
| --- | --- |
| M0固定起点六组合+两对照 | 6 failed / 2 passed；主环境与FastAPI0.143.0/Starlette1.8.0均复现 |
| M0修复 | 主环境49 passed；另一环境8 passed；独立检查45 passed |
| M1 | 原回归49 passed；新真实索引路由组8 passed |
| M2最终 | codec+路由101 passed；另一独立检查同101项通过，未相加 |
| M3独立恢复 | 32 passed /48.23s；实测79个独立进程，含7次SIGKILL |
| 最终合并组 | **191 passed, 3 warnings in 50.56s，exit 0** |
| File与SQLite派生索引 | 真实临时存储、原应用路由及原owner；已验证 |
| 辅助故障注入 | EIO、时钟、降低预算、安排真实文件变更；已验证，但非真实硬盘故障 |
| 模拟PostgreSQL / 真实PostgreSQL | **NOT_RUN / NOT_RUN**，没有以SQLite冒充PostgreSQL |

原作者41项通过与新增六组合失败分别保留，未宣称已有读取越权。上述阶段测试有重叠，不将不同运行次数累加为测试覆盖数。最终命令、环境变量、最小复现及恢复流程见 [M3记录](ASSET_QUERY_SCALE_M3_20261023.md)；M0另一依赖环境仅用于拒绝优先级复验，不代表全套M1–M3已在该版本复跑。

## 兼容性与性能结论

沿用同一GET端点。旧无分页仍 `{items}`，旧offset仍 `{items,total,limit,offset,has_more}`；关键词只匹配真实filename，六种kind精确筛选，稳定 `(created_at,id)` 升序。新增 `page_mode=cursor` 显式采用 `asset-metadata/1` 标量投影，带准确可见total及有签名next_cursor；每页原授权，源版本变化整页409重启。前端应先增加对应解码器再启用新模式，本分支未修改前端。

10,000条、页50：M1热offset元数据读取 **20,100→150**、耗时 **4.778→1.836s**；精确total空页 **20,000→0次源JSON读取**，耗时 **3.673→1.449s**。仍扫描索引候选并前后枚举源目录，不能说精确total零成本。冷构建 **9.350→10.555s**、旧无分页 **21.486→22.386s**，略慢而非全面提速。

M3游标热50条：50次源元数据读取、0次内容读取，源/派生目录各2次枚举，2.410s，Python峰值7,800,657 bytes。冷构建和跨进程重开独立测量，不拿热成绩代替冷成本。样本每项36-byte内容，最多10,000条，不外推大型媒体或50,000条实际延迟。完整内存/RSS、低命中/多kind/深offset/冷重开表见 [M1](ASSET_QUERY_SCALE_M1_20261023.md) 与 [M3](ASSET_QUERY_SCALE_M3_20261023.md)。

性能有独立冻结tree及每请求源码hash证据。M3性能版本之后仅把feature集合终检从cursor扩展至offset/无分页；cursor读取行为相同，其余app与脚本逐字相同，但未把旧offset耗时宣称为该终检加入后的重新实测。一次工作副本与暂存快照不符的测量已作废保留，并在有效测量中增加hash/import核对。

## 实现状态与限制

| 状态 | 范围 |
| --- | --- |
| 已实现且验证 | M0拒绝优先级；组合查询/准确可见total；有界索引；原接口兼容；签名绑定游标与原权限复核；冲突拒绝；跨进程持久/恢复；无源数据写入 |
| 部分实现，明确边界 | 精确total仍O(匹配候选)，源核对O(全目录)；30秒协作式预算不是墙钟SLA；未设进程RSS硬上限；旧完整投影不具跨owner快照 |
| 平台范围 | File在云端Linux真实验证；安全POSIX密钥原语缺失时游标503不可用，Windows未开放/未验收 |
| NOT_RUN | 真实/模拟PostgreSQL、断电/硬件故障、前端接入、Hermia后续独立验收；先前受平台限制的媒体安全复验未重做 |
| 交付阻塞 | 无GitHub上传阻塞；上述范围外项未以测试通过替代 |

最后源版本检查/权限guard之后仍有到响应发出之间的竞态窗口，不承诺完全消除并发窗口；跨owner原子快照未实现。目录/读取/字节预算超限明确503，不静默漏项或伪造total。索引可再生，签名key与identity应保留；无正式owner数据库迁移。

## 改动文件

- 后端适配：`app/creative/workspace.py`、`workspace_api.py`、`workspace_models.py`、`asset_query_service.py`、`asset_query_cursor.py`。
- 原owner的查询限定读取计量及独立派生模块：`app/services/asset_library_service.py`、`asset_query_budget.py`、`asset_query_index.py`。
- 新验证：`tests/test_studio_asset_query_authority.py`、`test_studio_asset_query_indexed.py`、`test_studio_asset_query_cursor.py`、`test_asset_query_cursor_codec.py`、`test_asset_query_index_recovery.py`。
- 基准：`scripts/benchmark_asset_query.py`。
- 交接：`docs/studio_asset_query_backend.md`，以及本目录 `ASSET_QUERY_SCALE_M0_20261023.md`、`ASSET_QUERY_SCALE_M1_20261023.md`、`ASSET_QUERY_SCALE_M2_20261023.md`、`ASSET_QUERY_SCALE_M3_20261023.md`、本文件。
