# Artifact-loss recovery — new verification required

The earlier local bf0bbdb2d438b42cc1cb2474543684ea7fb5ab00 package (tree
5cce4d2d0468d5734530486d1e0c08546aac1f72) disappeared from the replaced/reset
shared environment before publication. Its original archive, logs and Git objects
were not recovered. Its historical scores are NOT evidence for this reconstruction.
No files below claim to reproduce those missing bytes or identifiers.

New reconstruction uses a full non-shallow clone, safe base e5d5e4cc18414222a9034af9a09a51bb48c26459,
donor f6473e307e9d0501a41dc46dd991645a437103d7, actual merge-base
31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f. Only donor app/tests delta is reapplied;
old donor evidence is not copied as fresh evidence.

The separately authorized request-boundary fix uses ContextVar token reset in
finally for budget and strict mode on every independent ASGI scope. It does not
increase limits, swallow failures, change reads, loosen same-request nesting or
change original lock machinery. Non-GET test-observer context is independently
cleared/restored to avoid attributing the following request's writes to an older
GET. Real GET-owned background work remains attributed.

Only exact local semantic_import + exports cursor support changes old 501
expectations. Collaboration pairs and other unsupported authorities retain
refusals. TaskCenter HTTP is not added to asset-only budgeting. Frontend, SDK,
Work integration branch and main are untouched.

Fresh verification and new hashes will be recorded after final freeze. Published
F37 unexplained refusals and Windows asset-list cursor503 remain unresolved.
Prior local historical undiagnosed409 and rewrite wait timeout cannot be
retroactively diagnosed from new passes. No full ABA, cross-worker or cross-owner
atomic snapshot, RSS/CPU/lock-wait hard limit is claimed.

## Additional original POSIX test-observer defect

The broadened first reconstruction run at14650cef completed the TaskCenter group
with496pass/12fail. All12 failures were original POSIX child-process lock spies
accepting only `handle`, whereas the safe base calls `_lock_file` with the
`initialize` keyword. Children raised TypeError before reaching commit barriers.
The frozen production lock method and this original test file matched e5.

New freeze d93034821efa4f064ac680b8bfdedef86faa3b0d (tree
b9c22586cad50ac7bfd76c9ab4fd727bac770544) changes only those2 test-spy lines:
accept keyword-only `initialize=True` and pass exactly that value to the original
lock. Production app tree remains775a084c75dd5cfd7ccf0189060b056bf8f1c309.
No barrier, assertion, timeout, original lock or test case was removed. The initial
failed run remains historical evidence; final groups are rerun at the new freeze.

## Execution overlap disclosure

The d930 groups run sequentially within their driver, but its early context,
resource and TaskCenter runs overlapped the finishing historical146 driver and/or
independent acceptance. They are not claimed globally exclusive. The historical
146 driver finished at approximately21:05UTC and independent99 had already
finished. Final d930 compound HTTP starts only after its preceding asset group
(approximately21:08UTC); no other test group owned by this worker/reviewer remains
running at that point. This is orchestration evidence, not proof of external
machine load or a resource-performance guarantee.
