# Shared repair backport candidates

Candidates only. No PR37/38 edit, backport, merge, release or deployment has occurred. Each needs separate user approval, scope reconciliation, and independent regression against its actual target tree.

1. R1: original `app/api.py` project/record/list authorization dependencies and `app/main.py` top-level alias boundaries. Reuse the target's original membership, scope and role services. Carry the route inventory and positive/negative File/PG/prefix/flag regression; do not cherry-pick by frontend feature name.
2. R2: `app/generation_stream.py`, `app/jobs.py::events` observer callback, and `app/api.py` admission/current-scope checks. Carry live HTTP/SSE revocation/disconnect/two-observer tests and origin-feature fences. Tokens remain request-local, never durable.
3. R3: shared `app/jobs.py` state-transition/review/accounting/recovery protocol, plus the API409 conflict mapping. Carry terminal matrix, provider/settlement/persistence race and unknown-budget tests. Preserve the older target's budget interfaces and human acceptance fences.

The baseline report statically identified similar inherited routes in R3. This repair does not establish exploitability of every frozen V1 deployment. Feature flags are not a shared-route fix and cannot roll back data migrations.
