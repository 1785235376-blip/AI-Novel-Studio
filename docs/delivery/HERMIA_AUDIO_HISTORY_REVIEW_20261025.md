# AudioAsset History 独立验收与后续 Work 交接

日期：2026-10-25。结论：**已实现只读历史子集有实测依据；完整恢复仍 PARTIAL；兼容门禁尚未全绿；本报告不是合并、发布或恢复写端开放许可。**

## 1. 固定对象与操作边界

| 对象 | 固定提交 |
|---|---|
| 独立验收交付 | `2acab55d2ef64ca76f2093e376bf6388af364282` |
| 实现代码 | `2e2fcb79209a3afc03dc7e443f5e1901ff233ee1` |
| 原基线 | `11d8615cccb688462ff814d025b339e1b6eb0efe` |
| 验收时主线比较对象 | `4fd956e461d3632b55a3b7e84a7ab344b8abc91f` |
| 本文档落盘前主线 | `d070c9f6354b76a1594e388cb0825fb280933c63` |

代码在普通 fetch 后建立的独立 detached worktree 中验收。原主树及其他任务工作树未被 checkout/reset。未修改交付源码、原测试、生产数据；未 merge、push、调用真实 provider、安装依赖或访问真实 PostgreSQL。

本次交接只新增本文及 [独立证据包](evidence/audio-history-independent-20261025/README.md)。没有为了打包再跑一遍测试，更没有把旧结果冒充为 d070 上的新结果。

证据包保留完整探针源码、失败与成功日志、固定基线对照、promotion 结果、命令和哈希；机器绝对路径已按 README 中公布的规则替换。未复制任何真实用户数据或 runtime 数据树。源码以 `.py.txt` 保存，不进入默认 pytest 收集。

## 2. 实际结果，分别计数，不相加制造总数

| 实际运行 | 结果 | 用途/限制 |
|---|---|---|
| 交付原58项＋作者环境此前阻断的2个query/cursor case | **60 passed、3 warnings，19.34s** | 作者58项在本环境独立重跑通过 |
| 原 query/cursor 两个整文件 | **85 passed、1 failed、3 warnings，13.43s** | 发现下述 kind 写契约冲突；不能称全绿 |
| 固定11d独立 archive，两个此前503 case＋kind case | **3 passed、3 warnings，9.33s** | 同环境归因对照 |
| reviewer-owned owner探针 | **13 passed，2.40s** | create异常、坏head/bytes、真实100state边界、相同metadata |
| 独立source-kind变化/metadata更新边界探针 | **2 passed、3 warnings，9.04s** | 实际源变化仍令cursor拒绝续页 |
| 小预算retained/orphan探针 | **5 passed，0.55s** | 字节计费、CAS、临时文件、目录护栏、跨UUID遗留 |
| 单独chain/orphan探针 | **1 passed，0.22s** | chain读取预算与retained预算区分 |
| 固定11d失败create保留量对照 | **1 passed，0.18s** | 区分原计费边界与新增history放大 |
| Production publish/promote＋已挂载history读取补验 | **1 passed、3 warnings，7.71s** | 真实服务写流程；不是mutation HTTP全链或真实provider |

首行两个query case也属于第二行；第三行是另一个源码树的对照。owner探针、quota探针中的场景也有语义重叠。**不合计为唯一测试覆盖总数。**

作者环境报告的两项503/EBADF在这里未复现。此环境的已知兼容失败是下一节的 `AUDIO_HISTORY_KIND_CHANGED`，不得继续照抄EBADF解释。

早期reviewer探针失败也保留：owner初稿误把“缺parameters字段→空对象”当作无变化；promotion初稿分别遇到隔离目录、feature设置和误判`AWAITING_REVIEW`状态。只修正reviewer-owned探针设置/错误预期，未改交付源码及原测试断言。详见证据包README和原日志。

## 3. 已证实发现 R1：中央内部kind写契约收紧，原兼容case未完成（P2）

原case：`tests/test_studio_asset_query_cursor.py::test_changed_asset_source_requires_restart_without_partial_result[kind]`。

- 原测试取得第一页cursor，然后把synthetic image的kind改成audio，经原 `_write_meta` 写入。
- 新 `asset_library_service.py:248–254` 将该调用送入history；`audio_asset_history_store.py:296–297` 因旧kind不是audio而抛 `AUDIO_HISTORY_KIND_CHANGED`。
- 因此测试在写入setup阶段失败，尚未执行原“409 `ASSET_QUERY_RESTART_REQUIRED`、不得返回部分结果”断言。
- 同一个未改case在固定11d、同解释器/文件系统环境通过。原两个整文件仍是85P/1F，不予豁免。

### 影响的准确边界

全app调用点搜索发现 `_write_meta` 仅由原Asset owner内部调用。`update_metadata`原有白名单不允许kind；Studio及旧上传接口是在**新create**时指定kind，没有找到公开的“修改既有Asset kind”写路径。因此这里没有证明公开kind更新回归，也没有证明cursor泄漏。

但这不意味着可以忽略既有源变化语义。额外探针在独立synthetic文件中用原 `atomic_write` 实际改变kind，随后调用原 `cursor_get` / `refusal` helper，完整保留409及不泄露断言，结果通过。说明**真实源变化仍被索引/cursor检测**；阻断点确实是中央内部写合同与旧测试注入方式之间的冲突。

### Work需要完成的最小闭环

明确并记录原owner的kind不可变边界，在不删除case、不降低409/no-partial-result断言的前提下恢复可执行的源变化覆盖，同时验证owner本身的kind拒绝规则。

不要因为这条测试使用private方法就直接略过；也不要为了变绿而允许历史kind任意改写。如果确有受支持的内部kind转换，先明确新audio基线、sequence、coverage及旧记录的完整性合同，再实施并验证，不能把非audio历史伪装成audio历史。

## 4. retained/orphan实证：单Asset有边界，项目级失败create放大确实存在

### 4.1 未连head的对象确实计入单Asset retained字节

`audio_asset_history_store.py:160–170` 的 `_usage` 枚举records/blobs目录内**所有普通文件**，不只计head可达对象，也不按`.bin`后缀过滤。`prepare`在196–199行按“既有usage＋新对象＋暂存余量”做字节admission。

小规模验证：
- 将retained上限降为6000B，4次head提交前故障留下5个records、共4320B。下一次写明确容量拒绝；current字节未变，可见链仍1state。
- 4次stale CAS新增文件/字节均为0。
- 127B `.prepared`临时文件＋251B未链接blob，usage精确增加378B，未变成可见历史。

**没有发现同一Asset靠prepared/orphan绕过retained字节上限。**

### 4.2 chain/state上限与retained上限各司其职

100states、8MiB chain读取上限只约束可达提交链；未提交对象由retained字节及目录项护栏约束。降低chain预算至2358B的探针中，全部record共3411B，但可达record仅786B，1state链仍可读取。这不是chain读取超额。

另将state常量降为2时，目录既有项护栏为6；实测第五次失败写入后共有7个文件，下次写被拒。原因是目录项检查发生在新增record之前。这是一项边界偏差，不是无界增长或retained字节超额；不要夸大，也不要称目录项上限是严格的写后6项。

### 4.3 同一失败create key会分配不同UUID，项目账本不收费

head未提交时，idempotency key尚未写入current metadata。下一次create会再分配UUID（`asset_library_service.py:677–680`）。原create异常清理仅移除无metadata提交的顶层current binary（702–708），独立history仍保留。

真实项目incarnation/owner lease下的小预算实测：
- 同一key连续4次head前失败，留下4个UUID目录，总4132B；每个目录都低于4096B单Asset上限。
- 顶层current JSON/bin均不存在，`project_usage`仍是0资产/0B。
- 再成功创建34B音频并soft-delete，`project_usage`是1资产/34B，而全部history已有6254B。

这不是“绕过单Asset128MiB”，而是**跨Asset ID、项目级history及失败create遗留没有总账**的具体表现。成功历史留存本身也在原项目current-binary账本之外。

### 4.4 原缺口与新增放大要分开

`project_usage`与11d原实现相同：扫描顶层`*.json`，对匹配当前项目binding的可读metadata累加current size；不排除soft-delete、不依actor可见性或feature隐藏。它不是磁盘全量计费，因此metadata-less binary/tmp从前就不在该账本内。

但固定11d对照证明：4次相同阶段的**普通异常**会清理所有current JSON/bin/tmp payload，没有history目录；新分支同阶段异常现在留下独立history。这条普通失败重试带来的新增保留量不能全部归咎于旧账本。旧create的hard-kill孤儿清理没有在此补验。

64MiB真实空闲磁盘reserve仍逐次生效，但不是项目quota、跨应用reservation或物理耗尽证明。本补验没有真实填盘，也没有把降低常量/此前disk-low shim称为物理耗尽通过。

### Work应覆盖的边界

后续有界admission必须覆盖：当前资产、已提交history、prepared对象、失败create跨UUID遗留及其幂等/回收归属。**只给restore入口加quota，或只统计head链，会遗漏这里已经证实的放大路径。** 不得通过盲删、任意孤儿接管或伪造operation receipt解决。

## 5. 隐私与真实promotion补验：未证实最初怀疑的泄漏

固定源码没有`create_owned`符号。真实Production publication调用原`assets.create`时同时传入`owner_actor_id`和`_initial_studio_result`；初次metadata/history提交前owner/origin已齐备。推广只在新revision清除private owner，旧snapshot仍按旧owner/scope鉴权。

后续1P补验实际运行：
1. 原Production service的preview/create/execute，进入真实原owner publish，观察初次create参数确有creator和origin。
2. 内存synthetic provider只返回自制WAV，无真实网络/模型调用。
3. private阶段，另一有read权限actor的history/list/detail/download均404且不回显隐私sentinel。
4. 原Production service review触发真实promote；另一actor仅看到新formal head，可下载匹配摘要的WAV；所有旧private版本detail/download仍404。
5. history读取走应用真实挂载HTTP；Production写流程是服务方法调用，不是mutation HTTP的端到端鉴权测试。

这补齐了此前“只静态检查真实publish/promote”的一个证据缺口。仍不能据此宣称任意provider、所有写入口、所有auth race或全平台均已验证。完整源码及synthetic结果见 `sources/test_promotion_probe.py.txt`、`results/promotion-report.json`。

## 6. 可认可子集与仍关闭的能力

目前证据支持File-backed的原owner不可变metadata/bytes快照、懒迁移、current-head唯一可见提交点、history list/detail/download、所实现的ASSET来源pin授权、只读restore preview。交付专项中的真实多进程CAS和四处进程强杀/重启已通过；强杀场景是update，另加的create场景是普通异常，不能混称。

当前confirm/resolve仍应保持授权后409 `AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE`。没有合法的新历史候选review路径、唯一operation intent/receipt及精确不确定提交恢复；preview无执行token、无candidate落盘、无自动批准、无Canvas/Timeline/Canon/pin改写。完整M0–M7没有通过。

必须继续披露：
- 项目级历史/失败create总量未计费。
- 真实100states下delete/undelete可能被拒；本次已测current不变。
- 当前soft-delete期间history不可读，需先原undelete。
- cursor进程密钥使重启/跨worker需重新分页。
- ASSET trace的`content_verified:false`不代表来源二进制已证明；非ASSET及不可证旧pin仍拒绝。
- current/source metadata与各history chain是分别有预算，不是全请求合计仅8MiB。
- PostgreSQL运行、真实provider、真实媒体外部执行、物理磁盘耗尽、断电、全仓回归均NOT_RUN；原current metadata无父目录fsync保证。

## 7. 与主线共享文件的比较

验收时11d与主4fd的这两个文件逐字节相同：
- `app/services/asset_library_service.py`：SHA-256 `8b1bb86c55abe02380d7d86705d397f7ded2ddcfd4c326fedf85632cb9ef66d0`。
- `app/creative/workspace_api.py`：SHA-256 `de228dcd038ff5aa0c88a21ca7710a0679531872093a59b5de6a88d624a72c93`。

因此固定交付相对当时主线的共享文件差异就是原owner142行切片、router/admission19行新增，合计152 additions/9 deletions。[精确diff](evidence/audio-history-independent-20261025/results/diff-vs-main-4fd.patch)已保存。此比较不等于把整条旧分支合进当前主线的许可；后续实现必须遵守新的Work任务书及当前共享入口归属。

## 8. 验收要求

Work应针对R1恢复完整兼容门禁，对项目history/失败create有界计费提供真实原owner证据，并按现有任务书补齐restore admission/review/operation协议；保持所有已知失败日志和负向断言。未完成前维持恢复写端关闭。

不得声称本报告发现了公开kind变更漏洞、旧private泄漏、单Asset retained无限绕过、物理填盘通过或完整恢复已完成。也不得仅凭本报告的通过项删除未通过门禁。后续新SHA须重新按受影响范围验证。
