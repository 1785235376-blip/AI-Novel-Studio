# 本轮完整回归揭示的 Windows 实装问题与平台边界

日期：2026-10-07。本文件属于本机补充证据；不声称 hosted GitHub Actions 已通过。原产品测试断言、失败用例与 skip 规则均保留。

## 已实现修复

| 问题 | 实际原因与补全 | 原测试证据 |
| --- | --- | --- |
| 跨进程 File CAS 不等待锁，原四个 lifecycle race 失败 | Windows 字节锁同时禁止读取被锁字节；`mutation_coordinator._lock_file` 在锁前 `read(1)` 立即 PermissionError。改为 `os.fstat(fd).st_size` 检查是否需要初始化，原 msvcrt 锁与解锁不变。 | `verification/file-lifecycle-diagnostic.log/.xml` 四项 RED；`file-lifecycle-utf8-after.log/.xml` 原全部 lifecycle 加两项 index 共 29 passed，13.30s。 |
| Interop 合约生成字节不等于已登记原合约 | Windows 默认文本换行写出 CRLF；原 schema/TS/Rust 采用 LF。原 generator 所有写入明确 UTF-8 与 LF，parity key 采用 `as_posix`，重新生成只更新 generator 源文件摘要。 | `verification/file-platform-diagnostic.log/.xml` 原 byte-equality RED；`interop-worker-windows-after.log/.xml` 原完整 contracts + worker 206 passed，9.85s。原所有 schema、TS、Rust 字节未改。 |
| Worker 真实 exit 17 被记录为 None | Windows 管道 EOF 先于 process handle signaled；`_on_crash` 在 cleanup 前有限等待 0.1s 回收真实退出码，随后仍执行原 bounded owned-process cleanup。 | 同上 worker 原 `test_worker_crash` RED → 原完整 worker 测试 PASS；原 exit 17、FAILED、stderr 隐私断言不变。 |
| Windows native timeout 被 KeyError 覆盖 | `os.environ.copy()` 产生普通 dict，实际 key 为 `SYSTEMROOT`；原 cleanup 索引 `SystemRoot`。改为 Windows case-insensitive 查找，缺少来源时保留 tree NOT_VERIFIED 并执行原直接 owned handle cleanup，保持原 TimeoutExpired。 | `verification/file-native-verifier-diagnostic.log/.xml` RED；`file-native-verifier-after.log/.xml` 原完整 11 passed，2.89s，原 0.2s timeout 不变。 |

## 运行配置纠正

- 原 CI 只设置 `R2_TEST_FONT_FILE`。首次本机过渡 runner 额外全局设置嵌入字体 strict，干扰原刻意强制 CID fallback 的两项测试；最终环境恢复原 CI font profile。真实产品 PDF 验收的严格字体环境独立保留。
- Windows 默认 locale GBK 使部分原 `Path.read_text()` 读取实际 UTF-8 缓存、manifest 与脚本失败。最终本机 child profile 使用 `PYTHONUTF8=1`，没有改这些原断言。原 visual index、mounted author scopes、media actor 与 40-package manifest 的 focused 诊断回归通过：`file-lifecycle-utf8-after.*`、`file-mounted-diagnostic.*`（18 passed、16 原 opposite-PG skips，8.60s）。
- Coverage infrastructure 的原合成 manifest fixture 将 Windows `str(relative_path)` 写成反斜线。由资产代理仅更正 `as_posix()`，全部原 20 assertion AST 保留；`verification/coverage-harness-local.*` 原 152 passed / 1 failed 留 RED，`coverage-harness-portability-green.*` 153 passed 留 GREEN。原三个 strict guards 字节未改。

## 尚须在真实 Linux 环境执行的原测试

| 平台边界 | 原测试真实行为 | 状态与证据 |
| --- | --- | --- |
| Symlink privilege | Windows 不具备 SeCreateSymbolicLinkPrivilege，原 `symlink_to` 在调用产品验证前报 WinError 1314。 | `verification/file-symlink-diagnostic.*` 原失败保留；没有新增 skip，没有修改 Developer Mode。Linux 原生环境必须继续执行这些原测试。 |
| `/proc` | 原 worker isolation 用 `/proc/<pid>/environ` 与 `/proc/<pid>/cwd` 验证实际子进程，Windows 没有该文件系统。 | `verification/file-platform-diagnostic.*` 保留原平台失败；没有用合成环境替代。 |
| ZipInfo 与原 raw 反斜线输入 | Windows 标准库在构造 `ZipInfo` 时将 backslash filename 转换为 slash，原坏输入 fixture 可能尚未进入产品验证就被改变。 | `verification/file-native-verifier-diagnostic.*` 原不抛错失败保留。最终 raw-name 安全实现和精确 fixture 保存工作由资产代理记录，不在这里宣称通过。 |

## 完整回归边界

首次 Windows File 完整运行收集并分配全部 9,140 原序节点，未过滤、未跳 guard，原 20 分钟外限保留。运行开始后发生上述真实代码修复及 Memory/Provider 契约补全，因此其 source identity 已属于过渡证据，不能当最终候选通过。最终计数、外限状态和 raw coverage receipts 以 `candidate-backend-receipts/file` 的 `local-run.json`、`coverage.json`、`coverage-events.jsonl` 为准。

实际结果：1200.75s 达到原 1200s 外限后终止，process exit 1，`timed_out=true`。观测 6,306 个 unique nodes；call phase 为 4,405 passed、34 failed、1 skipped，另有 2 setup failures 与 2 teardown failures，共 36 个失败节点。未完成剩余节点，未产生最终 JUnit，coverage `complete=false`。`partial-events-summary.json` 只是原事件的分类摘要，不是补造的完整测试证据。

最终验证采用全新 WSL Ubuntu 24.04 原生 ext4 候选副本，复制实际源码字节且核对每个 source digest，原 Git history 留在主 Windows 工作树。Python 3.12.3、真实 ffmpeg/ffprobe 6.1.1、真实 PostgreSQL 16.15 只作为本机 Linux 补充证据；不等同于 hosted Python 3.12.9。uv 二进制来自 [官方 immutable release](https://github.com/astral-sh/uv/releases/tag/0.12.23)，校验其官方 SHA256。所有 Ubuntu 工具只下载并解包至本轮 runtime；没有安装系统包或修改已有数据库。
