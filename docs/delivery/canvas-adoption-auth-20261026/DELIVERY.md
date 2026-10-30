# Canvas image-node adoption authority repair

Status: PARTIAL. The bounded backend repair is implemented and frozen verification passed. No publication authorized or performed.

## Frozen starting point and ownership

- Backend integration: `457ea4a5a45ab13f351980665e053c5c77d15c82`, tree `ad5e7ff0db33998026b0016d9adb752e8e82f9c5`.
- Production-only repair: `b7b456efa51a8a69121027e40eac4fc05c05c463`.
- Production app tree: `cc826b709a03056d49553aad176980655f37f2f0`.
- Initial tests freeze: `b60d097b47448762fec3d344ba9ebfbb03804a85`. Final tests freeze: `838f4992e4fb6d166092dc28f8f575f31dbbed01`, tree `eb4a93f8f2531b3f1b4772b57ef9b8fa3869b6aa`. The independently assembled `25b93c6fb22e1889ef179f9ee5317920e7543719` has this identical tree.
- Frontend independently read: `fe4f55412299fadfada0354725b3ca46e418c46a`, tree `dd0910d4830c7106b3ec5e5a8f2b3529345a285f`. This frontend branch carries an older backend; it must not replace the backend integration checkout.
- Only production file changed: `app/creative/canvas_view_api.py`. No frontend, SDK, asset-query, TaskCenter, main, CI, Release or deployment changes.

## Root cause

`POST /projects/{nid}/studio/canvas-views/{vid}/image-node-result` first enters `graph_invoke` with `domain.write`. An initially empty canvas has no `image_node_origin`, so that graph admission captures write authority without its source-read grant flag. The route separately captures read authority, but this does not update the outer write guard's `source_read_authorized` closure.

After the service prepares the new formal origin in the original transaction, the outer guard observes the mapped source and rejects it with `CREATIVE_SUBGRAPH_SOURCE_READ_REQUIRED`. The route's safe error mapping presents `CREATIVE_CANVAS_IMAGE_NODE_FORBIDDEN`. The original guards and rollback must remain; bypassing the guard is not a valid fix.

The narrow repair passes the existing `local_input=True` argument on this one write admission. In the original graph invoker this means source read is required at admission, including the initially source-free target. It invokes the original read and write resolvers and retains repeated actor/scope/incarnation checks. It does not enable model execution, alter Host admission, rewrite grants, or change source pins.

## Evidence and security scope

A new positive test uses the original mounted app over actual loopback TCP, the original File owners, and a Mock PNG provider only. It does not manufacture an approved Job or Asset. On unmodified `457ea4a5` it fails at the image-node-result call with HTTP 403 after preview/create/execute/candidate/manual review succeeded. After the repair both `/api` and `/api/v1` pass, including exact retry without new business writes, original owner reconstruction, and saved canvas + approved Job readback. Each case calls the provider exactly once.

Nonpackaged/noncollaboration local Canvas metadata routes intentionally use the original `local-author` resolver without a required Host token. Missing or invalid tokens in that mode are not sufficient evidence of a bypass. Production execute/review still use their original valid Host gates. Collaboration mode must retain its original session, branch, membership and read/write checks. No new authentication policy is introduced here.

Original formal-node tests deliberately stop at QUEUED jobs and therefore did not cover successful first-origin association. The prior storyboard image-binding success is a different endpoint and did not prove canvas association.

Initial focused group: 4 passed, exit 0. Final immutable regression and independent counterexamples are reported separately; overlapping test groups must not be summed.

## Not claimed

- Browser integration against frontend fe4f5541, Windows, PostgreSQL, real model/GPU, or hosted CI were not run by this repair task.
- Collaborative Host-private model execution is not enabled or simulated to manufacture a positive collaboration pipeline.
- Work integration F's 37 prior query rejections and the old Windows asset-list cursor 503 are separate unresolved evidence boundaries; this repair does not claim to fix them.
- No main merge or production readiness conclusion.

## Verification iterations retained

- Initial test collection was blocked by the default read-only HOME identity path. No tests ran. Subsequent invocations explicitly used synthetic writable HOME/data paths; no system permissions or dependencies changed.
- Original expanded regression on initial frozen tests: 204 passed, 122 skipped (PostgreSQL), 122 setup errors, process exit 1. All 122 setup errors were the original fixture's missing PROJECT_ROOT prerequisite. This is not a passing aggregate. The follow-up environment review also found its LOCALAPPDATA/data/pytest-temp confinement requirements; a just-started incomplete retry was explicitly interrupted (130), not counted. Final regression uses the prescribed checkout .runtime directories.
- Final strong mtime+SHA focused TCP/reopen and local-contract group: 4 passed, exit 0. The receipt pins all application Python sources, compares before/after hashes, and records loaded app module paths.
- Independent final counterexamples: 38 passed, exit 0; production and test source hashes match final tree exactly. Its original process did not instrument loaded-module paths; the complete final rerun includes those tests with that instrumentation. Initial independent test-fixture corrections remain documented verbatim in evidence/independent/REVIEW.md.

## Final frozen outcome

Full nearby regression on `838f4992e4fb6d166092dc28f8f575f31dbbed01`: **364 passed, 122 skipped, process exit 0**, 826.08 seconds. PostgreSQL cases were explicitly skipped because no real test PostgreSQL URL was provided. This group includes the 4 focused and 38 independent cases; counts overlap and are not additive. No test failures or setup errors remained after using the original required synthetic runtime confinement.

The final source receipt records 600 application Python source hashes unchanged before/after, and the actual loaded application module paths with zero foreign application modules. The exact app tree is unchanged from the one-file production repair. The source checkout was detached and clean; reports were written outside it.

The supported result is first formal Canvas image-node association on File with the existing authority chain, original Mock PNG executor and actual TCP aliases, plus repeat/reconstructed-owner readback. It is not a real browser rerun or a full restarted server process test. Collaboration denials and late authority changes have separate mounted-route evidence, not an approved-model collaboration positive.
