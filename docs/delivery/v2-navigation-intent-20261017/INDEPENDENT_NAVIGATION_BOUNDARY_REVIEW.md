# Navigation intent: independent baseline and boundary review

2026-10-17，Asia/Shanghai。阶段：**BASELINE / PLAN REVIEW ONLY**；尚未审定本轮实现、运行 collector 或接受新的 runtime 结果。基准为 `87408f6881fd2dc2f22038c36643ed2e0a743f33`。

## 已核对的基线

- [Git / REST 回执](BASELINE_REFS.json)：本地 HEAD、远端 feature ref、`refs/pull/47/head` 与 REST PR47 head 均为 `87408f6`；PR47 为 Draft/open。main 为 `fed2404c8e30b44061b7139dced45b7f3301601c`，冻结 ref 为 `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0`。未重审此前临时传输对象。
- [raw 保护基线](protection-baseline.json)：750 frozen test/gate 源码、752 保护产物均零差异；9151 原 manifest SHA-256 仍为 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`。既有 portable-entry `-B` 历史迁移保留。该审计只证明所列字节保留，不是 V1 runtime 验收。
- 原 ignored audit helper 仅在内存中替换输出目录与 round base；[复用回执](audit-helper-reuse.json) 记录其原 SHA、精确替换及原文件未变，未覆盖旧报告。
- [原 V2 manifest 快照](baseline-coverage-manifest-v2.json.gz) 与 [清单基线](V2_MANIFEST_BASELINE.json)：15142 个有序 pytest node、2363 个源路径，原字节 SHA `ceacc0cb2f100dde23ce07a76dd086d27ae3eafbafc1b2499b97a0425a1dc405`；classification SHA `e7e543708b0ac8ebd1f81f77262a4afa6503d222af2b2e0ad9e71d6a749754d6`。本轮新增 TS 回归/harness 可以增加 source 路径，不应改变这些既有 pytest rows、分类、skips 或 external gates。
- [Adoption 源码基线](ADOPTION_SOURCE_BASELINE.json) 保存 61 个既有相关源路径的原 SHA，捕获时零差异；另以 [全部既有 test/gate 基线](EXISTING_TEST_GATE_BASELINE.json) 补充保护原 V2 清单中的旧测试。新增独立回归不应改写旧测试或原 adoption 入口。

## 对原 App intent 方案的独立边界评估

当前缺陷是原 App 一次性 overview 默认落点晚于用户显式模块点击，随后覆盖已选择的模块。修复应仍由原 App 持有导航意图，不新增项目、权限、资产或持久化 owner。

拟议的完整身份至少包括 session/actor、project、workspace/storyline/branch；每次身份转换还需要新的对象或 epoch，避免 A→B→A 复用旧 query 或旧回调。显式点击即使选择已是当前值的 NOVEL，也必须同步记录意图。旧身份回调及迟到、错误项目的 overview 不能消耗或修改当前身份的初始化状态。原 query prefix invalidation 必须保留；query 身份与其 client 捕获的 session/scope 必须一致。

同一身份无显式意图时仍应维持原默认 IMAGE / 合法 saved hint；显式导航标记只由原真实导航入口设置，自动默认、创建项目和 hint 不应反过来伪造用户点击。建议独立 mounted 回归明确覆盖同值点击、快速连续选择、无点击默认正控、项目/branch/actor 隔离以及 ABA 的旧响应和旧回调。此段是方案边界评估，不是实现已通过的声明。

## 真实 GET 时序验收的口径

已与 root/security 对齐：使用精确的原 `GET /api/projects/{nid}/studio` **request-dispatch gate**，在浏览器暂缓 dispatch 后通过原 UI 点击模块，再 `route.continue`，由原 backend 返回真实 HTTP200 与原 body。它不是 response mock；应记录 release 前请求尚未发到 server，不声称 server 在点击前已收到请求。无需引入 CDP、proxy 或第二 runtime owner。

回执应证明精确请求/branch/身份哈希、hold 与真实点击先后、释放后原 HTTP200/body digest、身份未变化以及所选 tab 保持。无点击默认 IMAGE、同值 NOVEL 和快速最后意图需要分别验证，不能借用旧 adoption helper 预等默认 IMAGE 的流程来替代本缺陷验收。auth browser 不读取本地 saved hint；该正控应在 mounted 测试单列，不能注入 localStorage 冒充。跨 scope 的子工作区 GET 可以单独验证其原 owner，但必须标明 origin，不冒充原 App overview 的 ABA 验证。所有 held 请求及自有进程应在 finally 中释放/清理。

所有旧失败、历史报告、原基线字节均保留。待产品/新回归/harness 统一源码冻结后，再运行原 pinned runner 的两次完整 collection、更新 additive manifest、核对原 166 CI selfchecks 和新 HEAD 原字节绑定；此时不宣称新的 File/PG/browser 或最终产品 PASS。
