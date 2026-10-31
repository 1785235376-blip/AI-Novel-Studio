# M0 · 查询拒绝优先级修复

固定起点 `8ecd7e80e8b706bc45d9e442647613dd041c1b90`，tree `7cf571603ce0db9ecd84950fed4c2ff396215fdd`；对照基线 `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed`。初始云端工作区干净。独立分支 `work/asset-query-scale-consistency-20261023`。

仅该资产 GET 接口的参数解码移入原 `invoke` 回调；授权、功能、项目及分支逻辑未复制。局部 OpenAPI 元数据保留参数说明但不提前执行查询校验。重复标量末值和 `1.0` 整数解码行为保留，原始关键词长度在 strip 前检查。

## 实际复现与验证

两套环境均满足项目声明范围。Python 均为 3.12.14，Pydantic 2.14.1、httpx 0.28.1：

| 环境 | 原 8ecd 六组合与两对照 | 修复后 |
| --- | --- | --- |
| FastAPI 0.161.1 / Starlette 1.9.0 | 6 failed, 2 passed，exit 1 | M0 + 原查询 + 原资产回归：49 passed，exit 0 |
| FastAPI 0.143.0 / Starlette 1.8.0 | 6 failed, 2 passed，exit 1 | 同八项：8 passed，exit 0 |

根因是部分 FastAPI 查询约束先于 `invoke` 执行，不归因依赖版本。六个反例均已保留为测试，每个同时有合法 `limit=1` 和非法换行关键词的拒绝对照。原 37/41 项通过与六组合失败分别报告；未观察到资产内容或 total 读取越权。

主环境命令（隔离解释器已按 `.[dev]` 安装）：

```bash
env PROJECT_ROOT="$PWD" NOVEL_DATA_PATH="$PWD/.runtime/asset-scale/bootstrap" \
  LOCALAPPDATA="$PWD/.runtime/asset-scale/appdata" MOCK_PROVIDER=true ENABLE_CLOUD=false \
  CREDENTIAL_VAULT_BACKEND=memory STORAGE_BACKEND=file \
  python -m pytest -q tests/test_studio_asset_query_authority.py tests/test_studio_asset_query.py \
  tests/test_asset_library.py tests/test_asset_safety.py \
  --basetemp="$PWD/.runtime/asset-scale/m0-final" --tb=short
```

另一环境在独立 venv 安装相同项目及上述 FastAPI/Starlette 固定版本，运行 `tests/test_studio_asset_query_authority.py`，独立数据根/basetemp。原版对照使用独立 8ecd worktree，没有覆盖工作分支。

独立检查者实际复跑 M0 八项与原查询 37 项：**45 passed, 3 warnings in 7.80s，exit 0**；未发现 M0 阻断。此结果不代替 Hermia 的后续独立验收。警告为既有依赖弃用及两个 schema 字段命名。

## 零写入范围与未运行项

测试使用临时真实 File 存储和原应用路由/会话/成员/权限链。对已初始化、预热锁后的源文件记录内容摘要、inode、大小与 mtime；拒绝请求、授权非法查询、合法查询均无源文件变化。锁文件及后续派生索引不是用户源数据，不将已有初始化机制误写成整个文件系统绝对零写。

真实 PostgreSQL、前端、用户整机、媒体安全复验：`NOT_RUN`。M1–M3 尚待后续阶段，不混入本提交的通过结论。每阶段完整提交和 tree 以最终阶段账本及 GitHub commit 元数据核对。
