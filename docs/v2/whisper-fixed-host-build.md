# V2 固定 Whisper Host：源码、构建与准入边界

本批提供实际 Windows native host、原 Model Center 生命周期驱动、原 AUDIO Registry 准入和原 Subtitle ASR adapter。源码完成不等于编译或推理验收：本轮没有执行 CMake、native host、Whisper、FFmpeg、测试或真实字幕工作流。

## 为什么不直接信任 upstream server

官方 whisper.cpp server 提供可改变当前模型的 `/load`，HTTP health 不携带足以证明本次模型加载的可信来源。因此本应用不会凭外部 server 的 health、日志文字、HTTP 返回模型 hash 或客户端元数据建立准入。

新 native host 只提供 `POST /inference`；不提供 load、模型路径选择、web UI、文件 URL、转换器或任意命令。Parent 通过继承的 stdin/stdout 匿名控制 pipe 传递一次封闭配置，HTTP 传输使用只由 parent 持有的 token、revision 与 PID。token 不进入 argv、路由快照或公开日志。

## 实际证明链

1. 原 Model Center 的可信 start 操作持续检查 Host 会话；配置文件和路径本身不启动进程。
2. Parent 锁定 executable、GGML model 与 FFmpeg decoder，验证 SHA256 和 Windows 文件身份，拒绝并发写入、替换及网络或链接路径。
3. 新 native host 用同一个拒绝 write/delete 的 CreateFileW HANDLE 计算实际模型 SHA256，经 `whisper_model_loader` 从该 HANDLE 初始化真实 whisper context；加载后再次核对 hash 和身份，并拒绝没有真实大块权重读取的空模型。
4. 只有初始化和 loopback bind 成功，native host 才向原私有控制 pipe 输出 nonce、revision、PID、实际 model SHA256、executable SHA256、文件身份及模型大小。
5. Parent 对照自己持有的 Popen、挑战 nonce、pin、文件身份和当前配置；通过后才注册原 durable Provider/Model UUID 和 AUDIO node。当前模型 loaded 的准入来源是原 owner 的真实私有 pipe，推理质量仍是 NOT_RUN。
6. 停止、进程退出、文件身份变化或 restart 立即撤销原 Registry route；Windows kill-on-close Job 和 parent pipe EOF 防止孤儿进程。旧任务的 route digest 包含原加载证明，禁止重新绑定和自动重放。

`OwnedWhisperHost.subtitle_adapter()` 返回当前原 `ModelRuntimeSubtitleAdapter`；未加载时失败，不能回退裸 server、内存身份、mock 或开发 token。TEXT Router 的行为保持原样。旧外部 adapter 的显式 /1 回调兼容入口不被此应用 owner 用于自动准入。

## 显式构建与打包入口

`scripts/build_whisper_fixed_host.ps1` 接受已有、干净的 offline whisper.cpp 1.8.2 checkout，固定 commit：

`4979e04f5dcaccb36057e059bbaed8a2f5288315`

另需明确的 CMake executable、全新且位于两个源码树之外、互不重叠的 BuildRoot 和 PackageDirectory，以及安装好的 Visual Studio C++ x64 工具链。脚本在构建前后核对固定 HEAD、根与所有递归 submodule 的 tracked/untracked/ignored 工作树均为空，以及 native 输入逐文件 hash 未变化；不自动 clean/reset。脚本关闭 ccache/sccache 发现，不下载依赖或模型、不执行模型、不开服务。它保存完整 license/源码内许可声明、native source hashes、构建版本和 executable pin。实际 compiler/toolset/Windows SDK 与 compile/link flags 通过生成的 CMake compiler metadata、cache flags 和 vcxproj 完整内容及 hash 记录在有界 manifest 中，状态 BUILD_METADATA_ONLY；本轮尚未生成这些实际构建证据。

当前显式打包 profile 是 `CPU_STATIC`，以静态 whisper/ggml/CRT、关闭动态后端及 OpenMP/BLAS 避免遗漏依赖。该 profile 不代表 GPU 验收。GPU profile 尚需单独固定 CUDA 构建输入和依赖，然后通过原 GPU 门禁，不能把 CPU 构建换个名称视为 GPU 能力。

原 `scripts/build_windows_application.ps1` 新增成对的可选参数：

- `WhisperHostPackageDirectory`
- `ExpectedWhisperHostSHA256`

缺少参数时保持原行为；显式提供时核对 binary、5 个封闭成员、完整 license 和逐文件 hash，再放入 `Application/Tools/WhisperFixedHost`。它不包含模型，不激活配置，不启动 host；provenance 明确为 PACKAGED_NOT_VERIFIED。

## Server-owned 配置与操作入口

V2 Host 配置调用 `install_fixed_whisper_host(center, generation_runtime, executable=..., executable_sha256=..., model_path=..., model_sha256=..., ffmpeg_path=..., ffmpeg_sha256=..., port=8178, threads=4, use_gpu=True)`。六个路径/pin 参数均必需；PORT 仅 numeric loopback。仅配置成功时原 Model Center 出现 `whisper-fixed-local`，通过原 Host session 的 start/stop API 操作。

HTTP runtime profile 无权替换固定模型、pin 或 argv。加载回执、token 和私有 pipe 由原 Model Center owner 持有。Opus 可以改变视图与操作排列，不能将观察、配置或 health 改写成 loaded 准入，不能自动启动模型、绕过会话或清除原验收门禁。

## 原验收门禁

后续统一验收必须分别记录 native 构建与依赖、Windows start/stop/restart、会话失效、中文路径、模型真实加载与 ASR 段时间戳、取消与迟到结果丢弃、V2 独立目录与 V1 不受影响，以及独立 GPU 实测。现有 M4/M5–M9 LOCAL_REQUIRED、失败 CI 证据和原 NOT_RUN 保留。

实现依据：[whisper.cpp 1.8.2 C API](https://github.com/ggml-org/whisper.cpp/blob/v1.8.2/include/whisper.h)、[upstream server](https://github.com/ggml-org/whisper.cpp/blob/v1.8.2/examples/server/server.cpp)、[固定版本 CMake](https://github.com/ggml-org/whisper.cpp/blob/v1.8.2/CMakeLists.txt)。上游阅读和 Git tag 核对是静态来源检查，不是运行证据。
