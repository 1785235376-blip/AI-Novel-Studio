# Independent Canvas Association Authority Review

## Scope and code reviewed

Baseline: 457ea4a5a45ab13f351980665e053c5c77d15c82.
Production patch: b7b456efa51a8a69121027e40eac4fc05c05c463 (independently applied as 90c3df6).
Only production change: `app/creative/canvas_view_api.py` passes `local_input=True` to the outer write invocation for `image-node-result`, plus explanatory comments.

The existing flag makes `source_read_required` true before the callback and causes `graph_invoke` to capture both original read and write permissions. It does not enable model execution, bypass Host checks, grant permissions, rewrite actor identity or disable final reauthorization. The existing nested route read guard remains. This is preferable to setting `source_read_authorized=True` arbitrarily or deleting the commit-time source-read check.

An initial empty canvas has no `image_node_origin`. The old request captured write-only graph admission even though the route separately called a read invoker. Creating the origin changed the graph's source-read classification inside the asset transaction, and its original write guard rejected the now-source-bearing canvas. The separate route read guard did not change the write guard's captured flag. The patch captures the required permission before this intentional transition.

## Independent cases and boundaries

- Original collaboration missing, invalid and revoked sessions; read/write permission removal; inactive membership; another actor; wrong branch. Both mounted API aliases.
- Shared queued-job 409 control (not a success case; no manufactured approval).
- Legacy plain canvas write-only compatibility; association still requires source read.
- Approved original job with request incarnation/version/digest, job, asset and confirmation tampering; another target canvas; another project.
- Approved provenance and one-history-step persistence through service reopen.
- Original authority mutations after route admission: read/write permission, membership, session, actor binding and retired/rebound project scope.
- Real original project delete/recreate after admission, preserving distinct incarnation and preventing old-result adoption into the new owner.

Late authority hooks run after mounted-route admission at service entry. They prove guard composition and revalidation, not cross-process atomicity or a full approved-model collaboration pipeline. Shared production execution remains unavailable under the original unpackaged Host policy. No bypass was introduced to manufacture a collaboration positive. Real external models, browser E2E, Windows, PG and hosted CI were not run by this reviewer.

Canvas/queue business-owner negative assertions include file mtime and SHA-256, detecting byte-identical rewrites too. Approved-source tests use the main helper's strengthened filesystem snapshot. Existing lock facilities are not claimed to be globally write-free.

## Iterative test correction disclosure

1. First collection used default HOME, which attempted the read-only application identity path. No tests ran. Retried with XDG_DATA_HOME and NOVEL_DATA_PATH pointed to synthetic writable evidence runtime; no install or security change.
2. Initial missing-session test expected a route Cache-Control header on a middleware-level 401. Corrected the assertion to apply to route-level responses, preserving exact status and owner-integrity assertions.
3. Original baseline denial controls: 18 passed, 12 deselected, exit 0.
4. First complete patched run: 35 passed, 1 failed, then maxfail stopped. The scope-change fixture attempted to reassign a still-bound project directly and was correctly rejected by the original scope owner before exercising the intended guard. Corrected the hook to call original `retire_project` before linking a new workspace. No production change.
5. Final frozen independent candidate: 25b93c6fb22e1889ef179f9ee5317920e7543719. Final outcome recorded separately with process exit and log/JUnit hashes.
