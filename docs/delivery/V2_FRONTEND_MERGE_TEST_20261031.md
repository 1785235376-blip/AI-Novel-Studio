# 前端分支合并与新环境测试报告（2026-10-31）

## 1. 合并

- 新前端分支：`work/hermia-backend-align-20261030` head **`a83df9ce3445fc64edfaa418f2c0cee1bb76779d`**（5 个新提交：Prompt workbench EN、RebuildCanvas EN、CanvasImageNodeTask reactive locale、默认节点标题 EN、Vera review tail）。
- 合并基线 main：`a0caa596adbce0cd91be7f7edaef23a6f9fd8856`（V2.0.0 + 能力补充 #55–#66）。
- 合并结果：0 冲突，18 files changed（17 frontend + 1 artifact），+808/−193；PR **#67** merge commit **`03b46a1429cc538552d1b27b472ee6e16b8e84e1`**，main 已更新。
- 能力补充（#55–#66）此前已合并到 main。

## 2. 新测试环境（隔离）

- 新 worktree：`D:\PoemSeed\Worktrees\v2-final-merge-20261031`（detached merged main）。
- 新 Python 环境：`D:\PoemSeed\Validation\v2-final-merge-env`（`python -m venv --system-site-packages`，Python 3.11.9；pytest 9.1.1 / pydantic 2.13.4 / fastapi 0.141.1）。
- 隔离环境变量：`LOCALAPPDATA`/`APPDATA`/`TEMP`/`TMP` 指向 `D:\PoemSeed\Validation\v2-final-test-run`；`NOVEL_DATA_PATH` 指向该目录下 `novel_data`；`PROJECT_ROOT` 指向 worktree；`PYTHONPATH` 含 worktree 与 tests。
- 前端：Node v22.14.0 / npm 10.9.2 / pnpm 12.4.2；`frontend/pnpm-lock.yaml` 下 `pnpm install --frozen-lockfile` 成功。
- 说明：默认 `C:\Windows\TEMP` 与 worktree 内 `novel_data` 在当前沙箱下不可写，故使用上述隔离路径；这是测试环境配置，不是产品缺陷。

## 3. 测试结果

### 3.1 后端（新环境）

- 能力组 13 个测试文件（registry/runtime/cost/capacity/scope-docs/create-coverage/audio-history/graph-multinode/timeline-audio/video-local-render）：**96 passed / 0 failed / 0 skipped**（日志 `backend-capability-group-newenv.log`）。
- 宽扫 99 个测试文件（asset/file/project/generation/phase/import/api/novel/chapter/continuity/model/provider/credential，排除已知超时 file_safety_http）：**1066 passed / 32 failed / 30 skipped**。
  - 30 个失败为合并前 main 已存在的同类预存失败；
  - 另外 2 个 `test_project_quota_management_authority.py` 锁序子进程失败在**同一新环境**下于合并前基线 `a0caa596` 同样失败（2 failed / 15 passed），属隔离环境的 `STUDIO_TEST_RUN_ROOT`/multiprocessing 限制，不是前端合并回归。

### 3.2 前端（新环境）

- `pnpm test`：合并后 **1026 个测试文件，96 failed files / 792 failed tests / 12,736 passed / 6 skipped**；
- 合并前基线 `a0caa596` 在独立 worktree 同环境：**1023 files，96 failed files / 792 failed tests / 12,724 passed / 6 skipped**；
- 因此前端合并**未新增失败测试/文件**；未通过测试为既有问题。
- 本次前端提交改动的测试全部通过：`PromptWorkspace.en.test.tsx` 5、`RebuildCanvas.en.test.tsx` 3、`CanvasImageNodeTask.locale.test.tsx` 2、`defaultNodeTitle.test.ts` 4。
- `pnpm build`：合并前/后均失败，同为既有 Windows 大小写文件名冲突（`frontend/src/ui/nsfw/NsfwMode.tsx` 与 `nsfwMode.ts` 仅大小写不同）及 `AppShell` 期望的 `NsfwController` 导出缺失；不是 #67 引入。

## 4. 结论与边界

- ✅ 能力分支与新的前端分支均已合入 main；前端合并无冲突、无新增失败。
- ❌ 前端全量测试与 `pnpm build` 在 Windows 上仍为**既有失败**（96 文件/792 测试 + 大小写冲突构建错误），需单独修复前端跨分支/文件名大小写问题后才能作为可发布前端。
- ❌ 后端宽扫仍有既有失败与隔离环境子进程限制失败；能力组全通过。
- 真实 PostgreSQL/浏览器/真实模型/Windows 打包桌面/hosted CI/外部 NLE 仍 **NOT_RUN**；本报告不是全产品验收证明。

## 5. 证据（本地）

`D:\PoemSeed\Validation\v2-final-test-20261031\`：`backend-capability-group-newenv.log`、`backend-core-sweep-newenv.log`、`backend-baseline-quota.log`、`frontend-install.log`、`frontend-tests.log`、`frontend-build.log`、`frontend-baseline-*.log`。
