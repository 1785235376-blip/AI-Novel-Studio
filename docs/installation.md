# V0.7.0 Engineering Installation

前置：Windows 11、WSL2、Docker Desktop、Ollama、Python 3.11+（仅本地开发）。复制 `.env.example`，设置独立密码，拉取 Manifest 中一个模型，运行 start.ps1。Dify 未包含在 Compose，避免复制并维护其庞大官方栈；应独立安装官方 Dify 后通过 HTTP 连接本服务。

---

## V2 工作区：已核实的本地校验运行器（2026-10-14）

上面那段历史说明**原样保留**，它描述的是 V0.7.0 的 Docker/WSL2/Dify 栈。下面的 V2
工作区不需要 Docker、也不依赖 Dify。**本节不表示安装或打包已被验证** ——
那些项目仍是 `NOT_RUN`。

本机已核实的事实：

| 事实 | 值 |
| --- | --- |
| 工作区 | `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` |
| 解释器 | `C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe` |
| 始终设置 | `PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1` |
| 便携 PostgreSQL | `..\Builds\studio-v2-host-5ed1cbee-20261011\Base\PostgreSQL\bin`（PostgreSQL 16.15） |

### 运行 Python 校验

`pytest` 必须经运行器；直接运行会以 `KeyError: 'PROJECT_ROOT'` 失败。

```powershell
python scripts/run_v2_checks.py <label> -- python -m pytest <files> -q `
  --basetemp .runtime/v2-checks/<label>/pytest -p no:cacheprovider
```

### 针对真实 PostgreSQL 运行

使用可复用的便携集群，**不**安装系统服务；运行器结束时会正常停止它，并保留数据库作为证据。

```powershell
python scripts/run_v2_postgres_checks.py `
  --pg-bin <便携 PG bin> --data <集群数据目录> `
  --port 55433 --database v2_<新库名> --fresh-database <label> `
  -- <python 绝对路径> -m pytest <files> -q --basetemp <已存在的目录> `
  -p no:cacheprovider
```

四个会导致**与产品无关**失败的点：`--user` 是数据库**连接角色**（默认 `postgres`），
不是标签；标签是**位置参数**（`[a-z0-9-]+`）；`--basetemp` 目录必须**预先存在**；
解释器必须写**绝对路径**（直接写 `python` 会 `[WinError 2]`）。

### 浏览器验收

`frontend/playwright.studio-release.config.ts` 使用**已安装**的浏览器通道
（`channel: msedge`），不下载任何东西 —— **不要**运行 `playwright install`。
Phase9 曾记录真实后端下 **8/8 通过**；那是历史，不是本次复验，而且它使用的端口 8100
现已被无关的厂商服务占用。

### 端口说明

8000 落在 Windows 排除端口区间（由 PID 4 占用），**不要**使用。8100 被
`GearLink_KBService.exe` 占用。8080 提供的是 **Strata** 本地模型服务，不是本应用的运行时。

### 未验证

安装、卸载、打包、DesktopHost 可信会话、GPU 与真实模型执行、真实媒体流水线均为
`NOT_RUN`。详见仓库根目录的 `PHASE10_RELEASE_HARDENING_REPORT.md`。
