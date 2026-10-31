# M0 execution and fixed-source gate

Date: 2026-10-26, Asia/Shanghai. Execution used the existing Windows local Work
environment, Python 3.11.9 and installed test dependencies. Three explicitly
selected `gpt-6-astra` agents handled production integration, HTTP compatibility
and independent adversarial tests; the coordinator handled Windows recovery,
measurement, final receipts and publication. Core production files had one writer.

The first minimal shell/Python execution succeeded. The first original test
command was `python scripts/run_studio_backend_tests.py
tests/test_studio_asset_usage_budget.py -q`: 6 passed, 3 existing warnings,
9.32 pytest seconds, process exit 0. No pre-process setup-refresh failure was
reported. This initial smoke result is a gate, not the final frozen acceptance.

## Fixed inputs, history and isolation

| Input | Actual remote HEAD and local commit | Actual tree |
| --- | --- | --- |
| A: work/asset-usage-resource-guards-20261026 | 856d1ed3341fe0c24df1daff9a8bc1242c260e6c | d6c8057a0595d93eab6d3799787226faf660e834 |
| B: work/taskcenter-local-export-cursor-20261026 | 31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f | fc6f7e5510313e0e334b07efaae99127a895d568 |

Both exact remote branch refs were read before fetching. Local repository
`rev-parse --is-shallow-repository` returned `false`. The actual merge-base is
`ffe1937911cff32d4ebd4770b350674627501d3a`. Ancestry checks for both
`692c2c6657bf28d43a36278e0225dc76f3d2694a` and
`3e027e8b2d79490249b6cae49d5583ddcdc63fc6` against fixed B returned exit 0.
They were not reapplied. The ordinary merge has exactly fixed A and B as parents.

The new integration branch is
`work/file-backend-safety-integration-20261026`, initially created at fixed A in
its own worktree. Tests and independent verification used separate worktrees
and detached fixed commits. The original checkout had untracked `build/`; it
was preserved. No reset, clean, stash, history rewrite, force push, original
branch update or frontend/SDK edit was used. No unpublished mixed-source code
was inspected or incorporated. All data are repository fixtures or temporary
synthetic records; no existing user novel/project data were searched.

Required Work handoff instruction:

> 若拿到的是浅克隆，先补足远端提交历史再计算 merge-base；不要把浅边界显示的“没有父提交”误判成两条线无共同祖先，也不要直接强制合并。

## Environment and honest evidence boundaries

No new dependency, permission, paid API, model invocation, deployment, release,
account/network/security setting change or hosted Actions rerun was needed.
POSIX, PostgreSQL, browser/frontend, GPU and real model execution remain NOT_RUN.
Windows abrupt termination means TerminateProcess, never SIGKILL.

GraphFlow skill was read and compressed context attempted before code
exploration. The configured MCP exposed only gf_read/gf_macro/gf_exec/gf_edit,
not the old graphflow_context/graphflow_plan/graphflow_index names. Context
results had insufficient relevant anchors; planning and later refresh returned
Transport closed. Exact fixed-ref file/symbol diffs were used and the unavailable
index refresh is reported as NOT_RUN.

The existing Windows asset-list cursor failure was reproduced independently on
fixed A before integration: `tests/test_studio_asset_query_cursor.py -q -x`
returned exit 1 with `503 ASSET_QUERY_CURSOR_UNAVAILABLE`. It remains separate
from the asset-usage pagination and the supported TaskCenter single-source
cursors. Its baseline log is archived by the HTTP tester.
