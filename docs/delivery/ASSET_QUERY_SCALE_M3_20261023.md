# M3 · 索引持久性、恢复与交接

承接 M2 commit `07c297692782596865f761c35d8bef54cd64b80f` / tree `bc748e48f604ee08f68c85f0649f3074aa780e12`。最终各阶段 SHA/tree、测试与状态见同目录 `ASSET_QUERY_SCALE_FINAL_20261023.md`；接口见 `docs/studio_asset_query_backend.md`。

## 已实现生命周期

- 唯一正式来源仍是 Asset owner 的 JSON/bin，索引范围由实际源根目录指纹及每项原项目 binding 隔离；查询每页重新授权，不缓存调用者权限。
- 派生格式版本1；冷重开执行 SQLite quick_check、表大小/列类型/单cell上限、全部派生列摘要及源 fingerprint 验证。热路径缓存仅在索引文件 identity 未变时使用；源每次仍前后 stat，普通原位改写也会失效。
- 缺失、旧格式、错误根范围、普通损坏在相同预算内重建。增量改写只重新读取变化的源 JSON，但依然核对整个源目录和完整候选集合。没有无限扫描回退。
- staging SQLite 事务完成、源版本检查、文件 fsync 后 atomic replace，正常完成再 fsync 派生目录。之前已提交索引不会被半成品替换；进程被杀后，下次请求忽略未发布 staging 并在预算内恢复。真实 SIGKILL 不是断电/文件系统损坏模拟，不据此承诺所有硬件故障均可恢复。
- 派生目录128 entries / 2 GiB，包含索引、残留staging/journal、未知普通文件与cursor key/identity；缺失key文件预留2名额/160 bytes。重建前另预留 staging+rollback journal 1 GiB及32 MiB journal开销余量。超限503，不删除历史中断证据。此为协作式容量预检和复核，不是操作系统物理配额。
- SQLite `max_page_count` 将 staging DB 限于512 MiB；过大的损坏cell在SQLite读取前有大小边界。SQLITE_FULL 统一表示容量预算不足，驱动无法可靠区分页上限和物理卷满，不伪装成空结果。
- 正式 `index.sqlite3` 从不原地写事务，故其 `-wal/-shm/-journal` 任一残留均明确503不可用；每次identity检查都复核，readonly immutable连接也不读取这类sidecar。不会绕过错误继续使用可能混合的索引。

源全目录上限与版本涵盖该 Asset 根目录的全部项目；不是只计当前匹配项。50,000项是结构上限，不是任何记录大小/硬件上都能在30秒完成的承诺。本次规模验收最多10,000项。30秒协作式执行预算在取得原资产租约后开始，不包括获取租约的等待，不能强制中断单次阻塞I/O。未设进程RSS硬上限，保留样本内存实测与该限制。

## 运维恢复流程

1. 先保存错误码及该独立工作分支commit；不公开原始目录、token、密钥或用户元数据。503不表示资产不存在，409要求从首页重启。
2. 普通缺索引/格式旧/损坏：正常已授权查询在预算内自动重建；不需要迁移正式Asset或项目数据。恢复不会增加或删除正式资产。
3. 超过数据或派生空间预算：保留现场，停止反复请求。由有权运维在正常维护窗口备份并核对正式源数据、派生索引及中断文件，处理容量或恢复配置后重试；本实现不自动扩容、不删证据、不默默提高预算。
4. canonical WAL/journal、非普通路径或私有目录权限不符：明确不可用，需运维调查后按正式备份恢复该派生目录。不要把未知sidecar合并进正式源。原子索引可再生，`cursor.key`/`cursor.identity` 应一起保留；key损坏或部分写入不自动更换。
5. 完全丢失key及identity会产生新的签名身份，旧cursor不能继续；仅丢其中之一或不匹配则明确不可用。客户端不应持久化cursor超过900秒，应处理422/409并重新发起当前已授权查询。

## 最小复现与真实验证

使用项目声明的 Python>=3.11 环境安装 `.[dev]`；本次实际环境与M0–M2主环境相同。所有测试仅创建云端临时合成File存储，真实路由组沿原应用中间件/会话/成员/授权链。

```bash
env PROJECT_ROOT="$PWD" NOVEL_DATA_PATH="$PWD/.runtime/asset-scale/bootstrap" \
  LOCALAPPDATA="$PWD/.runtime/asset-scale/appdata" MOCK_PROVIDER=true ENABLE_CLOUD=false \
  CREDENTIAL_VAULT_BACKEND=memory STORAGE_BACKEND=file \
  python -m pytest -q tests/test_studio_asset_query.py tests/test_studio_asset_query_authority.py \
  tests/test_studio_asset_query_indexed.py tests/test_studio_asset_query_cursor.py \
  tests/test_asset_query_cursor_codec.py tests/test_asset_query_index_recovery.py \
  tests/test_asset_library.py tests/test_asset_safety.py \
  --basetemp="$PWD/.runtime/asset-scale/final" --tb=short

python scripts/benchmark_asset_query.py --sizes 1000 10000
python scripts/benchmark_asset_query.py --cursor-only --sizes 10000
```

首条是最终回归命令；后两条是可复现实验命令，不要求重复运行已完成的全部基准。脚本只允许新建 `.runtime/asset-scale` 合成目录；36-byte内容、不清OS缓存、source-open与SQLite原生I/O分开，沿用M1测量限制。游标真实续页用前一响应token；第2/3页不会标成深游标页，未通过伪造token省略遍历过程。

最终上述完整回归命令：**191 passed, 3 warnings in 50.56s，exit 0**，覆盖最后的feature集合一致性检查；查询读期间功能可见集合变化时，旧offset/无分页也明确冲突，不返回混合total。独立检查者完成最终diff复核，无阻断。3个警告仍为既有httpx/Starlette弃用及两个schema字段命名。

真实 PostgreSQL：`NOT_RUN`；Windows游标key存储：当前明确不支持；前端集成和Hermia后续独立验收：`NOT_RUN`；受先前平台限制的媒体安全复验未重做。

独立生命周期组：**32 passed, 3 warnings in 48.23s，exit 0**。实际 Python audit 统计 **79个独立子进程（72个正常/固定错误响应，7次真实SIGKILL）**；样本每例1–3条。包括9 MiB损坏SQLite TEXT、真实WAL/rollback journal且主文件stat不变的warm拒绝、连续中断与空间预算、64 KiB测试页cap、冷重开/源原位和原子变化。预算故障只降低测试实例阈值；真实存储未被mock替换。对底层EIO的辅助注入测试另列M1，不把它称为真实磁盘故障。

### 新增游标规模实测

命令为上述 `--cursor-only --sizes 10000`，实际冻结tree `b900e44f2e730fd8afd12b4bdb05fc5a402b643e`，index模块SHA256 `5afefee9f895f5bc836dc7307a599c689cfb7717a97355728268620b759755d7`。每请求前后核对源码hash及实际import路径，防止旧工作副本混入。之后唯一应用变更是把既有最终feature集合复核扩展至旧offset/无分页路径，游标路径的复核顺序和读操作不变；该改动有最终综合回归覆盖，未伪称测量tree等于最终提交tree。

| 10,000项，页大小50 | 源/派生目录枚举 | 元数据读/内容读 | 秒 | Python峰值bytes | RSS KiB |
| --- | --- | --- | --- | --- | --- |
| 冷构建首页 | 3/4 | 10,050/0 | 13.924 | 34,559,301 | 250,516 |
| 热首页 | 2/2 | 50/0 | 2.410 | 7,800,657 | 250,516 |
| 真实第2页 | 2/2 | 50/0 | 1.904 | 7,797,916 | 250,516 |
| 低命中关键词+image，4项 | 2/2 | 4/0 | 1.061 | 7,756,288 | 250,516 |
| 无匹配，精确total=0 | 2/2 | 0/0 | 1.150 | 7,750,007 | 250,516 |
| 独立进程真实第3页 | 2/2 | 50/0 | 9.243 | 34,043,331 | 249,596 |

6场景全部200，total/每页合成文件名/页间无重复均有断言，内容读取与源写入全0。签名token仅存在0600临时fixture文件中，报告已检查不含token。SQLite文件20,377,600 bytes，派生目录总文件20,377,722 bytes（含key/identity）；文件大小不是SQLite原生I/O读取字节数。第2/3页并非深游标性能，未遍历200页来作额外性能宣称。M1表的枚举只计源目录，M3新增有界派生目录枚举在此单列。
