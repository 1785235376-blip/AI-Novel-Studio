# R3 Prompt 后续实现与真实验收

2026-10-17（Asia/Shanghai）；从 `618affbca0aaf20d5bc669d697d8e2b1abb9b3fa` 继续。

**当前状态：本轮指定 R3 后续的真实 File、PostgreSQL 与 Edge 验收通过；托管 CI 因账户账单锁 BLOCKED。** 生产 `PROMPT_ADOPTION_WRITE_ENABLED=False`；PR #47 仍为 Draft，完整 V2 仍为 PARTIAL，不是 freeze/RC。

实现与包装 HEAD：`f7fd63a1fff3c0ec7fa88c9c111676f9539a41a5`。后续提交只发布本报告和原始证据。历史报告、失败与中断回执均保留，本报告给出当前结论。

## 独立提交与原 owner

以下五个切片已逐个提交、逐个 fast-forward 推送到 [PR #47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) 的原分支：

| 提交 | 实现 |
| --- | --- |
| `49e2daa510878346b6dcaa05394dc512af00efd6` | 私有 Prompt 删除、tombstone CAS、完成请求的目标绑定、失败后重试的不可变来源标记。 |
| `89c6b50dec0bfc16c09a3944963f38a35b59e622` | adoption 在原 owner 租约内验证全部声明的 write-time bindings。 |
| `51473a9f9c5ddd8e3ad0493bd7ee1f2b25c6283a` | 原身份/授权/项目 owner 的提交栅栏、会话锁顺序修复、真正独立进程并发测试及 File/PG 浏览器启动器。 |
| `f8e97b167cb77c96d2885d0256e9a1083127e863` | 一个既有 V2 参数 ID 稳定化及增量清单更新；全部输入和断言保留。 |
| `f7fd63a1fff3c0ec7fa88c9c111676f9539a41a5` | 两个既有源文件的 Git 字节包装修复；工作区运行字节不变。 |

没有新建 Prompt 数据库、版本 owner、Review owner 或授权账本。

### Adoption write-time binding

`app/creative/prompt_adoption.py` 在既有 `GraphAssetInputs.phase(writable=True)` 中解析 Character、Scene、Shot、reference/output Asset。故事记录复用 `NovelService.data_set` 与 Bible scope 规则；shot 使用目标 storyboard 内的原 document-number 投影，兼容的原始 shot ID 也只能属于该目标；Asset 使用原 actor-aware 读取和内容校验。

原项目/资产/Creative 事务租约一直覆盖最终文档提交。缺失、归档、跨项目/分支、歧义、损坏或其他作者的私有目标统一拒绝，不回显目标正文。本次新提交的成功凭证记录 `prompt-adoption-bindings/1` 和 `source_bindings_verified=True`。该字段证明写入时的可见性与绑定快照，不代替审批、执行权限或之后的存活性；已结算 replay 保留历史凭证。

详细范围与早期失败见 [BINDING_IMPLEMENTATION_REPORT.md](BINDING_IMPLEMENTATION_REPORT.md)。

### 私有删除、tombstone 与恢复身份

`AssetLibraryService.delete` 与原 Workspace lifecycle 传递服务器解析的 actor。删除只写原 `deleted_at`/version，返回同一已验证行的原 lineage 投影；不可变 `.bin` 和旧 revision 保留。其他作者、错误分支保持 404，只有读取权限保持精确 403；仍私有的 Prompt restore 保持原 404 行为。

原 Prompt authoring 把 tombstone 纳入请求与 family 记账：已删除请求不能重生，已删除最新 revision 仍是 CAS head，不回落到旧版本续写；整个 family 删除后不能复用原 family。已完成 replay 必须匹配原 CREATE/REVISE 路由、family、前驱与预期 revision。

首次原 Asset metadata 同时存入服务器专用 `_prompt_write_origin`，绑定原操作、分配的 family、目标及完整请求摘要。正文写入后失败，只允许原身份恢复到同一 asset/family；改变请求得到 409，原字节不变。标记不通过 HTTP DTO 开放，也不出现在 public 投影。旧的、未完成且没有此标记的写入返回 `PROMPT_REQUEST_ORIGIN_UNVERIFIED`，保留字节，不能凭文件名猜测来源。

详见 [PRIVATE_PROMPT_IMPLEMENTATION_REPORT.md](PRIVATE_PROMPT_IMPLEMENTATION_REPORT.md)。

### 撤权提交栅栏与锁顺序

Prompt authoring/adoption 和 metadata lifecycle 在原 owner 中持短提交租约。File 沿用 authorization → project 顺序；PostgreSQL 沿用 project → authorization advisory lock 顺序。File membership/审计写加入原 authorization-store 租约，工作区 create/provision/rename 修正为同一顺序。没有把存储锁放到模型或外部调用上。

原 Session resolver 的 binding mutation 栅栏与短 registry read 锁分开。复核曾在旧实现稳定复现四种 resolver/Asset 死锁；四项红测保留，修复后原七项加新四项共十一项通过。该 resolver 仍是进程内注册表；跨进程撤权证明来自共享 File/PG 的真实 membership、role、permission owner，不能外推成跨进程 session registry 或所有路由的 ABA 保证。

独立进程测试覆盖 create/revise/delete/adopt × 三种撤权 × 两种提交顺序。File 记录实际持有与等待的同一原 OS 锁路径，PG 要求服务端 `pg_blocking_pids` 指向原 holder。撤权后留存原会话再次请求，精确 403，并有合法新作者正控制。adoption 的成功写只在显式隔离测试进程临时启用，常驻浏览器后端开关始终为 False。

## 最终验证

使用固定 Python 3.12.9 / pytest 8.4.2、原 `run_v2_checks.py` 与 `run_v2_postgres_checks.py`。各组有重叠，不把表中计数相加为唯一覆盖数。

| 范围 | 结果与原始回执 |
| --- | --- |
| File 私有生命周期、原 API 与原失败恢复 | 84 passed，82 PG deselected；[receipt](../v2-development/r3-private-file-final-r3.json)。 |
| File adoption bindings 与原并发/HTTP/router | 43 passed，26 PG deselected；[receipt](../v2-development/r3-bindings-file-final-r3.json)。 |
| File 原 authoring、身份、last-admin、工作区和 11 租约测试 | 74 passed；[receipt](../v2-development/r3-authority-file-final-r3.json)。 |
| File 原授权、scope、项目退休回归 | 55 passed，47 PG deselected；[receipt](../v2-development/r3-authorized-file-final-r3.json)。 |
| File 独立进程最终撤权组合 | 24 passed，24 PG deselected；[receipt](../v2-development/r3-prompt-process-file-final-r3.json)。 |
| 既有 V2 ID 模块与 CI 自检 | 225 passed；[receipt](../v2-development/r3-schema-id-module-ci-final.json)。 |
| File Edge 真实三视口 | 3 passed；[receipt](../v2-development/r3-prompt-browser-file-final-r4.json)。 |
| PostgreSQL 最终组合 | 103 passed，99 deselected（新 98 项与原授权/incarnation 5 项）；[receipt](../v2-development/r3-prompt-combined-pg-final-r3.json)。 |
| PostgreSQL Edge 真实三视口 | 3 passed；[receipt](../v2-development/r3-prompt-browser-pg-final-r1.json)。 |
| 前端 src / tsc / build | 4163 passed、6 skipped；`tsc -b` 和 Vite build PASS；[原始记录与失败边界](frontend-verification.json)。 |
| 原 UI token guard | PASS，范围仅 `frontend/src/ui` 的 52 个文件；[receipt](../v2-development/r3-ui-token-final.json)。 |

最终 PostgreSQL 组合使用 `v2_r3_prompt_20261016_final_r3`（OID 23468），浏览器使用另一个新库 `v2_r3_prompt_browser_20261016_final_r1`（OID 24389）；两库均在迁移前证明无应用对象，分别应用原 20 migrations。组合运行 1355.06 秒，完成全部 24 个 PG 跨进程撤权用例，其 holder/waiter 证据要求真实 `pg_blocking_pids`。File/PG 均为 create/revise/delete/adopt × 三种撤权 × 两种提交顺序；详见 [最终进程与浏览器报告](PROCESS_REVOCATION_BROWSER_REPORT.md)。

PostgreSQL 使用原生 16.15、loopback 新空库与原 20 migrations；原架构中项目、身份、授权与实验状态使用 PostgreSQL，Asset 字节/metadata 仍由原 File `AssetLibraryService` 持有，不伪称 PG blob 存储。

浏览器使用安装的 Edge、原 LocalSessionBootstrap 与真实 HTTP；没有 response mocks/dev-session registry。原 UI 实际创建/修订、读回两版、比较正文；删除通过真实浏览器 HTTP 发出后检查原 UI tombstone/history，未声称存在未实现的删除按钮。生产 adoption 请求精确返回 503 `PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`。已载入编辑器的本地草稿可以保留；新服务器 body 读取不可用，不声称擦除了浏览器内存。浏览器没有请求模型执行，后端模型计数未仪表化，不作模型/GPU 验收。

## 字节、清单与冻结边界

- 原 9151 manifest SHA-256 保持 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`。750 frozen test/gate sources 和 752 保护产物原字节不变；[当前审计](protected-v1-source-audit.json)。这不是“全部 V1 app 源码未变”或 V1 运行验收声明。
- 增量清单 15118 项，实际新增 208 个用例。旧 V2 的一个 `object()` 地址 ID 显式迁移为 `opaque-object`，其他旧项与原顺序保留；两次独立收集的字面 ID/顺序完全一致。清单为 `INVENTORY_ONLY`，不是 15118 项通过；[delta](additive-collection-delta-final.json)、[ID 字节/AST 证明](graph-schema-stable-id-migration-proof.json)。
- 两个既有 CRLF 输入由精确 `.gitattributes` 路径保留；默认三项 whitespace 检查保留并识别 CR 行终止符，原 CI 检验逻辑、跳过策略未放宽。[EOL 证明](EOL_SOURCE_BYTE_PRESERVATION_REPORT.md) 明确区分：`persistence.py` 在原 app-source map 中，但其语义差异早于本轮，两条路径均不属于上述 750/752 保护集合。
- 运行器的 2290 个源码输入逐字节对应最终实现 HEAD；V2 manifest 全部 2352 个输入也逐字节对应 HEAD，无 EOL 例外；[runner/Git 绑定](source-git-binding-final.json)、[全清单/Git 绑定](manifest-source-git-binding-final.json)。最终十份成功回执与源快照的严格交叉核对另见 [source-binding-final.json](source-binding-final.json)。

## 失败、中断和未验收边界

早期私有删除红测、请求重绑红测、binding 损坏样本的测试设置错误、四项真实 resolver 死锁红测、File 锁观察点过窄的辅助探针失败、错误运行环境/测试路径，以及全目录 Vitest 误收集三个既有 Playwright 脚本的失败全部保留。后者有 4197 tests passed，但三个 suite 失败；本报告只把明确的 `src` 重跑记为前端 PASS。

两次旧 PG 组合因独立发现缺陷/探针修正而受控中断，保留原非零 receipt、partial log、数据库和独立 interruption 说明；进度点不是完成计数。没有删除失败、修改既有测试的业务断言或添加缺服务 skip 使结果变绿。

托管 CI 为 **BLOCKED：GitHub account billing issue，job 未启动、steps 为空**。当前实现 HEAD 的三个工作流原始注释见 [hosted-ci-implementation-head.json](hosted-ci-implementation-head.json)。本地 CI 自检不代替托管最终 HEAD CI。

常驻 production adoption 开关保持 False；生产 adoption UI 成功写、全 V2 集成、Windows installer/clean-machine、真实模型/GPU 不由本轮建立 PASS。完整 Canvas/Director/媒体/NLE/3D/Tutor 等既有 PARTIAL 边界保留。后续托管验证入口是解除账户账单锁后重跑最终 HEAD；不能据本轮隔离测试直接宣布 release。

自有 API/Vite/PG 均已停止，端口与资源保留状态见 [runtime-retention-final.json](runtime-retention-final.json)。原始证据的精确字节清单为 [evidence-manifest.json](evidence-manifest.json)。本轮不做递归文件清理，保留原回执、截图、验证 profile、PG 数据库与先前保留的 baseline worktree，不宣称回收磁盘空间。

独立最终复核见 [HEAD_SOURCE_AUTHORITY_FINAL_REVIEW.md](HEAD_SOURCE_AUTHORITY_FINAL_REVIEW.md)，实现提交与保护分支的实时发布核对见 [implementation-publication-audit.json](implementation-publication-audit.json)。本次会话提供的 GraphFlow 接口只有 `gf_read/gf_edit/gf_exec/gf_macro`，已用可用压缩读取；`graphflow_index` 未提供，未声称执行该接口，保留本地缓存。
