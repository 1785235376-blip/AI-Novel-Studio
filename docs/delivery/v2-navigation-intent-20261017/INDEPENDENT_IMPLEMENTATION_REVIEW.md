# Independent navigation implementation and harness review

2026-10-17，Asia/Shanghai。基准 `87408f6881fd2dc2f22038c36643ed2e0a743f33`。状态：**SOURCE_REVIEW_PASS / RUNTIME_PENDING**。本次只读审查实现与新增验收 harness；没有修改产品/旧测试/collector、启动 runtime、运行测试或 commit/push。

## 原 App owner 的边界

当前候选未发现阻断性源码缺陷。意图仍由原 App ref 与原导航 setter 持有，没有第二数据/权限/持久化 owner：

- 身份复用原 `revisionStoreIdentity`，去除 chapter，仅保留 session、actor ID/workspace、project 与 scope 四 ID。原 store 同步订阅会观察每次转换，因此同一 React batch 内 A→B→A 也更换 entry 对象；旧 callback 即使字符串回到 A，也因对象不同而拒绝。
- 同 token/project/scope 的首次 unknown→known actor 补全保留原 entry 对象、explicit/applied 与同 entry callback，只递增 epoch 刷新捕获的 client。known actor A→B、session/scope/project 改变仍创建新对象，不能借 hydration 例外跨真实身份。
- 同值 NOVEL 点击同步标记 explicit，原壳、ModuleWorkspace、IndependentStudio、CreativeWorkspace、原 interop/search 和打开 V2 工作台入口均走原统一 handler。自动 default/hint/create 仍由原 owner 自动处理，不伪造显式点击。
- query 保留原 invalidation prefix，再以 opaque `useId` / epoch 隔离；原始身份只留 ref，不把 bearer token 加入 query key。client memo 与 entry/epoch 同步刷新。错误 project overview 不消耗当前 applied；有 explicit 时不再应用晚到默认。
- `requestedStudioEntry` 以 entry 对象约束原 requested asset，只向当前 entry / project 透传。同项目跨 branch、跨 project、ABA 的旧 hint 不会因新 entry 跳过 default 而混入；当前 entry 的合法 asset 仍保留。创建项目仍调用原 setter，只调整记录 origin 的顺序以绑定新 entry。

App 是本轮授权修改目标，不要求整个 App 原字节不变。独立提取并比较原 local connection authority guard：与 874 基线 **2117 bytes 完全相同**，SHA-256 `cf09275f969550d59515fb34a3613f4264359599d8d7b00daeb39770d7eed0fa`。原 adoption 61 源基线实际不含 App；61 源与 1118 个既有 test/spec/gate 在本次检查时均保持原字节。

## 新 runtime harness 的真实性边界

新增 launcher 只启动原 `uvicorn app.main:app`、Vite 与现有 Edge。身份由原 `LocalSessionBootstrap`、原 initial-workspace 和原连接/项目/branch UI 取得；File 或受原 wrapper 约束的 loopback fresh PG 使用原 adapter。显式 `MOCK_PROVIDER=false`，没有模块 gate True、产品 env 开关、开发会话注册或身份/store/localStorage 注入。

`DispatchGate` 精确匹配原 GET、项目、branch、token，暂缓 client dispatch；真实 UI 点击后用无 URL/body/header override 的 `route.continue()`，原 backend 返回真实状态与正文。原始 response body 及 SHA、真实 DOM tab/document 只读记录可供终态重算。没有 `fulfill` / response 伪造，也不宣称 hold 时 server 已收到请求。

cold/reload 案例等待真实 bootstrap actor200 与只读 render barrier，再在 held parent overview 下点击；它**不声称**覆盖 actor 尚未补全时的点击，该边界由原 App mounted 回归单列。无点击新 page 是独立默认 IMAGE 正控；快速选择验证最后 NOVEL。auth browser 不读取本地 saved hint，未注入本地 hint 冒充。

跨 project / branch 案例明确 hold 的是原 `IndependentStudioSession.refresh` 子 owner GET，并要求原取消 `net::ERR_ABORTED`，新 parent GET 真200。随后独立 API readback 是旧/新 owner 读取，不冒充取消后的旧 callback 交付；原 App parent ABA 由 mounted 回归覆盖。`finally` 释放所有 gate、关闭自有 page、经原 admin owner 删除项目并附 cleanup 结果。ordinary capability 必须 False，没有采用 POST。

这些是静态设计与实现检查，尚不等于 File/PG/browser 已运行成功。34 mounted 节点、6 个 browser list 节点和 15142 pytest inventory 是不同证据范围，不能混用。

## Collector source readiness

原两 collector 无需编辑：`scripts` 递归纳新 launcher，`frontend` 根纳 config，`frontend/tests` 递归纳 live spec，`frontend/src` 递归纳新 mounted 测试。静态 inventory 为 runner **2305** / manifest **2367** 源；没有运行 pytest collection，预期原 **15142** literal nodes / order / classifications 不变。

原 collector SHA 保持 874：`run_v2_checks.py` 为 `64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5`；`extend_v2_coverage_manifest.py` 为 `337466ae33d15b2aafaeb15f2191ccdb0c65b22274e1b4d98ba10501dd30135e`。

本次审查候选 SHA-256：

| 路径 | SHA-256 |
| --- | --- |
| `frontend/src/App.tsx` | `ab211c5c61014ab617fcd3e320a03cfd7b92467f419ce9bf45e0ae5b78200bf3` |
| `frontend/src/AppModuleNavigationIntent.test.tsx` | `99bd7e33b7595eae8638cb8cc9ae7994d55380fd8a59106b648731c433f5e710` |
| `scripts/run_v2_navigation_intent_browser.py` | `396340b8d09f2225a51877bcba08d06013739d638cc8b123736e0dfd6ca288c9` |
| `frontend/playwright.navigation-intent-live.config.ts` | `e55ff4ec391ac0b6858b2d2ff191cdeac50c806839c1b9c4a3cc75877318a536` |
| `frontend/tests/e2e/v2-navigation-intent-live.spec.ts` | `59a63c11cbfa9c10fdbc754850e93dbd0f2c7aacf5d7ebd22d5d0315e8aaab48` |

统一冻结后才运行原 runner 双 collection 并更新 additive manifest；旧报告/失败不覆盖，最终 HEAD 绑定、166 CI selfchecks 与真实运行终态另录。
