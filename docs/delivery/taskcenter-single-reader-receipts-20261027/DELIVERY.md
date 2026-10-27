# TaskCenter local single-reader completion receipts

## Scope and fixed baseline

This independent backend slice builds on the TaskCenter fixed-return-deadline repair. The local prior package is `28d17c9354f96c2f01f66a55b2f9ab381e4a9cd6`; its tree is identical to this branch's cherry-picked docs parent `a00222aa`. Source/tests are frozen at `c7282fdd5877b857de9d266489f01e47fa9163df`. Publication is not performed by this local package.

Only `app/experimental/taskcenter_cursor_http.py` changes in production. For the exact local `semantic_import` or `exports` single-source cursor, the adapter requires one actual selected aggregate reader receipt, the identical reader object before/after, the expected authority name, and `completed is True`. The existing request-local observer is reused. No separate probe is accepted as proof of the actual aggregate read.

The default aggregator's intentional 403/404 soft skip remains unchanged for legacy/offset requests. The separately guarded mixed adapter and existing collaboration route retain their original contracts. No new source, task action, permission domain, source store, budget, or frontend behavior is added.

## Demonstrated defect and correction

A temporary 403/404 from the actual aggregate reader could previously be misreported as a successful empty cursor response when the underlying source was empty or the query matched no rows. Both mounted and real loopback HTTP routes were exercised at `/api` and `/api/v1`, for both local sources. Baseline: 32 incorrect 200 responses and 32 correctly rejected nonempty/continuation controls. No private data disclosure or incorrectly minted token is claimed; this fixes denied reads being reported as successful empty results.

The repaired 88 focused cases pass. The independent 20 cases additionally verify transient refusal does not destroy or renew an already valid cursor, genuine empty recovery does not allocate state, and observer errors are not swallowed as availability. All are included in the final 108 focused group; groups overlap and must not be added.

## Frozen validation

See RESULTS.json and raw exit/JUnit/source receipts. Final groups on the same detached code/tests freeze: 675 TaskCenter, 143 export/adoption consumers, 108 focused. All exited 0. The runner hashes all application Python files and TaskCenter test files before/after, and records actual loaded application module origins. No source changed during those checks. Original source-free collaboration and mixed-reader regression tests are included in the TaskCenter group. Actual TCP tests retain original application routing and authorization, using only synthetic owners and deterministic denial hooks.

Development probes and their failures are retained separately from final-* evidence. The first 32-case mounted probe is superseded for acceptance by the immutable final group, not deleted. No production code was changed to make the test fixtures pass.

## Limits

Overall PARTIAL. This is not a full Studio integration or a main-merge approval. Browser, Windows, PostgreSQL, real models/GPU, and hosted CI are NOT_RUN for this slice. The known asset-query intermittent 409, older F37 observations and Windows asset-list 503 are unrelated and not claimed fixed. No cross-owner atomic snapshot, strong full-history ABA or resource hard-bound guarantee is added. No external upload, main change, force push or Release is performed here.

## Work handoff

Preserve the prior fixed-TTL repair and its evidence. Apply this one production diff and both new test files to the same chosen backend baseline; do not overwrite frontend or redo mixed-reader integration. Re-run the affected TaskCenter and original consumer groups on the actual combined source. Preserve legacy/offset soft-skip tests, original collaboration checks, and healthy-empty success. The private receipt is never returned as task data or used as an authorization substitute.
