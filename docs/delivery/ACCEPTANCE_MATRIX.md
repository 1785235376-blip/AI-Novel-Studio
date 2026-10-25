# ACCEPTANCE_MATRIX — t150u PoemSeed Studio V2 unified loop [HERMIA-FE-20261025 M10]
Code HEAD 10f3a1d5 (row 14 verified by Vera e217e061; V8/V8b test added) (branch work/hermia-unified-loop-20261025). Statuses: 已实现 / 已验证 / 部分实现 / 受阻 / 未运行.
Evidence types: mock (jsdom/vitest) · synthetic provider · real File/API · real browser · real provider · PostgreSQL · Windows.
"real browser" = Chromium (Playwright) against local vite :5391 + **mock backend** :5392; every non-GET was blocked unless explicitly armed; no model call.

| # | Item | Status | Evidence type | Evidence |
|---|---|---|---|---|
| 1 | Loop: task → detail → locate (honest "源节点不在画布") → execution canvas → return | 已验证 | real browser + mock | m5 `loop` ×3 vp; u3/u4 tests |
| 2 | Param preview → confirm step, cancelled; exactly 1 armed non-GET (preview), never execute | 已验证 | real browser | m5 `param` |
| 3 | Adopt: 读取结果 → 2-step confirm | 已验证 | real browser + mock | m5 `adopt` |
| 4 | Canvas restore: compare → impact → confirm | 已验证 | real browser + mock | m5 `restore` |
| 5 | Cold reopen restores layout; no stale "无本地存储" label (bug fixed repro-first) | 已验证 | real browser + mock | m5 `coldReopen`; m5-repro-storagelabel-before/after |
| 6 | Workset save, then pan + reload keeps workset/viewport | 已验证 | real browser | m5 `worksetPan` |
| 7 | Session-mode save message "仅本次会话有效" | 已验证 | real browser | m5 `sessionSave` |
| 8 | Identity after bootstrap (persistent mode, single bootstrap GET) | 已验证 | real browser + mock | m5 `identity`; int.bootstrap.test; m5-repro-bootstrap-before/after |
| 9 | Project A→B→A isolation (B "无权", A tasks return) | 已验证 | real browser | m5 `aba` |
| 10 | Corrupted real localStorage keys → safe defaults | 已验证 | real browser | m5 `corruption` |
| 11 | Revoked (401) state | 已验证 | real browser | m5 `revoked` |
| 12 | Unknown/503: "读取失败…不会自动重试" | 已验证 | real browser | m5 `unknown` |
| 13 | Project gone (404) | 已验证 | real browser | m5 `projectGone` |
| 14 | Purge of own viewprefs/layout keys when project leaves list (in-session) | 已验证（Vera e217e061）— 历史：Vera re-review of f6e535a3: 单次 200 [] 清空全部已见项目 → 已修 1681ea85（空列表不作证据 + 连续两次成功列表缺失才清理）；**未通过 at f778eaec**（realUser always null via sentinel projectId → purge never ran; earlier m5 projectGone was vacuous）；Vera e217e061 PASS（全量 294/293/293，浏览器 1366/1440/1920）；SHOULD-FIX V8/V8b 单测已补（出错保留旧 data 不算第二次观察） | mock + real browser | fix 35377d47; u1.purge.host.test (fails on f778eaec code, passes after; mutation realUser→null killed); m5 projectGone ×3 at 10f3a1d5 (FAIL on f778eaec code: m5-repro-purge-before-f778eaec.log); Vera vera-compare/final-f778eaec/purge.json, purge2.json; Vera vera-compare/purgeguard-e217e061/; u1.purge.guard.host.test V8/V8b test (mutants killed: m10/logs/purgeguard-v8-mut.log) |
| 15 | Purge after cold start (project deleted while page closed) | 部分实现 | mock (documented gap) | INTEGRATION_NOTES §M5-fix 3 |
| 16 | Audio filter 全部/图片/音频 over shared list + gap text | 已验证 | real browser + mock | m5 `audioFilter`; audio.panel.test |
| 17 | 试听候选: no read on mount, 1 GET on click, no autoplay | 已验证 | real browser (mock WAV) + mock | m5 `audioPreview`; audio.test |
| 18 | Audio detail via owner-generic get(owner,id) | 已实现 | — (code path) | G-AUD-2 |
| 19 | Audio review/adopt (only m8.audio.trim has canvas_return) | 部分实现 | mock | G-AUD-4 |
| 20 | Audio per-asset history (speech/music/effects) | 受阻 | — | G-AUD-5 (backend has canvas-level only) |
| 21 | Task list paging / owner filter | 受阻 | — | G-AUD-1, TaskCenter no paging (bounded ≤1000 client paging only) |
| 22 | Cost display | 部分实现 | mock | G-AUD-7 (backend UNKNOWN → "未知") |
| 23 | axe landmark-unique on #uw-panel-tasks (Vera P2) | 已验证 | real browser (axe-core) | m5 `axe`; m5-repro-axe-before (FAIL) / after (PASS); aria-required-children (章节 div) is pre-existing, P3 |
| 24 | Legacy TasksPanel no fabricated `uw-preview:` identity / empty-token read (Vera P2) | 已验证 | mock | u3.repro.test (it.fails → it, same assertions) |
| 25 | Layout at 1366×768 / 1440×900 / 1920×1080 | 已验证 | real browser | 48/48, shots |
| 26 | No unrequested writes (blocked=[] in every scenario) | 已验证 | real browser | m5-req-*.log |
| 27 | Full suite: tsc 0, build 0, vitest 0 NEW failures vs M0 | 已验证 | mock | full-f178ff84.* |
| 28 | Compare mode real split (currently sequential creative→execution) | 部分实现 | real browser | review/INTEGRATION.md #6 |
| 29 | resetAll exposed in UI | 部分实现 | mock | U1fix "可选 resetAll 接 UI 未做" |
| 30 | Same-id project recreation detection | 受阻 | — | no incarnation/created_at on Novel |
| 31 | Real backend API end-to-end | 未运行 | real File/API | — |
| 32 | Real provider / model output | 未运行 | real provider | no paid/automatic calls allowed |
| 33 | PostgreSQL-backed run | 未运行 | PostgreSQL | — |
| 34 | Windows run | 未运行 | Windows | — |

**Counts (34):** 已验证 21 · 已实现 1 · 部分实现 5 · 受阻 3 · 未运行 4.
