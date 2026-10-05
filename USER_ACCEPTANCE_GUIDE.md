# R2 本机验收手册

仓库：1785235376-blip/AI-Novel-Studio；工作分支：`work/dot-astra-v1-rc-r2`；审阅入口：[Draft PR #37](https://github.com/1785235376-blip/AI-Novel-Studio/pull/37)。用户本机验收尚未运行。

## 交付状态先核对

以 PR 最新的最终 SHA、CI 回执和 `docs/delivery/dot-astra-rc-r2/RELEASE_READINESS.md` 为准。工程版本保留 `0.7.0 Beta`，没有升级为正式 1.0，没有合并 main、发布 Release 或部署。

当前仓库提供源码、迁移、可复现验证/打包入口，以及 CI 生成的内部 DesktopHost 编译工件。一个独立的 Host EXE 不是完整安装包：Python/PostgreSQL/工具与授权清单构成的 BaseApplication 基础发行目录，本轮环境没有可核验的完整副本。完整安装器构建/安装/卸载验收因此仍有明确阻塞。不能把历史 EXE 或只编译出的 Host 当作本轮已验收软件。

## 安全准备

1. 只使用新的空目录，例如 `C:\AI Novel R2 验收\Data`；不要指向原作品、原 PostgreSQL 库或旧安装的运行目录。
2. 使用合成文字和自己有权使用的图片、声音、视频。不要用私人原稿测试外发限制。
3. 模型凭据由你在受支持的 DesktopHost/OS 保险库流程中输入；不要放到源码、URL、普通配置或截图中。
4. 第一次启动不配置模型，也应该能够手工写作、保存、重开。未配置的 AI/媒体能力应显示原因。

## 可复现工程入口

开发/验收人员可从精确分支提交准备隔离环境；普通用户的完整安装包入口必须等打包门禁完成后再使用。

- Python 3.12，安装 `python -m pip install -c .github/ci/python-constraints.txt -e ".[dev,fontbuild]"`
- Node 22.14.0、pnpm 10.6.5；在 `frontend` 执行 `pnpm install --frozen-lockfile`
- 设置全新的 `NOVEL_DATA_PATH`、隔离 HOME/XDG、`STORAGE_BACKEND=file`、`ENABLE_CLOUD=false`、`MOCK_PROVIDER=false`。未配置真实模型是正常状态。
- 后端：`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- 前端：在 `frontend` 执行 `pnpm dev --host 127.0.0.1`，按输出打开本机地址。
- 自动化开发测试可显式设置 `MOCK_PROVIDER=true`；界面会标明模拟执行。模拟结果不能用作真实模型验收。

Windows 打包继续复用 `scripts/package_windows_acceptance.ps1`，提供已核验的 BaseApplication、新输出目录、同轮 Host publish 目录、.NET/Node/Vite 路径及 VerifiedFontDirectory。脚本要求新输出目录，记录实际源码 SHA、运行时版本和摘要。字体通过 `python scripts/prepare_pdf_font.py --output <新的字体目录>` 准备；它下载固定官方来源、核验哈希、生成 Regular 实例并携带完整 OFL。

## 功能验收

每项记录 PASS / FAIL / BLOCKED / NOT_RUN、提交 SHA、环境和复现步骤。

1. 创建小说与章节，输入中文、英文、标点和多段正文。保存后重开，内容与版本保持一致。另行检查中文输入法、粘贴、撤销/重做。
2. 导入合成 TXT/Markdown/DOCX/PDF。检查分章和候选的来源位置，修改候选并保存；重开仍可继续。拒绝或取消选择不能写入正式资料。
3. 知识接受发生部分故障时，界面显示已完成/总数并保留检查点；再次操作不会重复写已完成项。已改变的目标必须人工核对。
4. 在“创作方案与风格”保存风格、三幕/冲突/高潮/结局或世界结构草稿，关联真实人物/地点/章节。编辑、比较、批准、归档、恢复历史为新草稿，再重开核对。
5. 在展开的 AI 结构化方案区，从明确规则/三幕标记生成本地候选；缺失项应说明。配置真实模型后可生成待审建议。保存只生成草稿，不能自动成为 Canon 或正文。
6. 选择授权模型进行写作，查看 Draft、Diff，再明确采用。采用前正文不变；重复采用不重复写入。关闭/重开、取消和失败均保留合理的可恢复状态。
7. 制造第二客户端/标签页版本冲突。双方内容必须保留；手工解决仍以新版本为前提。历史恢复产生新当前版本，不删除旧版本。
8. 在“正文隐私”审核当前章节版本。默认/未知仅本地；正文改变、切分支、撤销审核后，尚未发送的云请求必须被拒。独立 LOCAL_ONLY 知识/秘密不因正文授权而放宽。已经发出的内容不能撤回。
9. 评论绑定章节版本，回复、解决和重新打开留有操作者记录。正文改变后标为过期锚点；切工作区/项目/分支不能看见别处记录。
10. 新建导出任务后关闭窗口，重开“导出中心”，找到同一 job/snapshot，下载后核对其仍是创建时内容。资源缺失、超限或摘要变化必须明确失败。用目标剧本/办公软件抽查 Fountain、DOCX、PDF、EPUB。
11. 剧本审核后通过“新草稿修订”修改；原批准版和资产保持。并发编辑应返回 409，缺版本前提应提示更新；核对镜头顺序、时长、机位和导出一致。
12. 图片任务生成、取消、失败重试、比较和批准入库；资产删除可恢复，缺失引用能发现。视觉参考是有来源的元数据检索，未声称具备 embedding 语义一致性。
13. 视频首尾帧只能选当前授权资产。远端提示词须单独审核，旧回调/取消后的结果不能污染新任务。基础合成输出为静音预审 MP4，非完整混音成片。
14. 音色档案、分段有声章节队列、顺序/时长清单和音频导出。原文或策略改变后旧任务不得越权外发。无 ffmpeg/ffprobe 或不支持的 Provider 能力应明确不可用。
15. Workflow 的提交、工作中、完成、失败、人工审批分开显示；未完成的 Agent 不得让下游提前成功。拒绝审批和取消后不继续写正式内容。
16. 插件清单/声明式包可检查管理权限与回滚；第三方代码执行仍禁用，不能以普通进程冒充沙箱。

## 备份恢复

先退出所有本项目写入进程，再确认离线状态。不要一边写作一边备份。

`python -m app.backup_restore backup --source <项目根目录> --data-directory <实际运行数据目录> --destination <新的备份目录> --app-version 0.7.0 --offline-confirmed`

`python -m app.backup_restore verify --backup <备份目录>`

`python -m app.backup_restore restore --backup <备份目录> --destination <新的空恢复目录>`

PostgreSQL 使用环境变量名参数 `--database-url-env` 指向专门的隔离数据库连接；不要把 DSN 放到命令行、工单或截图。恢复目标数据库/目录必须全新，工具不覆盖旧库、不执行 `--clean`。详见 `docs/backup_restore.md`。

## 失败时保全作品

停止重复点击写入操作。保留当前草稿、冲突窗口、任务 ID/快照 ID、版本号和脱敏错误码。不要删除运行目录、数据库或清空日志。先制作离线备份，再在另一个目录重现。只清理本轮拥有的进程和目录，不停止别的 Python、PostgreSQL 或 WebView2 实例。

交互 Windows/WebView2、真实保险库、实际 GPU/模型、安装升级卸载保留数据以及最终使用体验，必须分别验收；API、浏览器和托管原生契约不能替代这些项目。
