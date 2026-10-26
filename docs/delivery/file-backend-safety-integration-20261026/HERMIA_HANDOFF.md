# Contract for a later published mixed-source slice

No unpublished semantic_import + exports engine is included here. Current
TaskCenter cursor support is only these three independent combinations:

| Actual File runtime | Selected authority | Current window |
| --- | --- | --- |
| local | semantic_import | Existing committed semantic-import collection and original bounded safe projection |
| local | exports | Original Export owner list ordering, first 100 rows, exact six-key local permission context, original safe projection |
| collaboration | agent_team | Original validated window with no chapter/source references and current actor's relevant session/member/grant/scope evidence |

Mixed authorities, collaboration exports and other unsupported combinations
continue to refuse explicitly. A future published slice needs its own fixed
input SHA/tree, conflict analysis and independent combined acceptance. Current
single-source passes do not validate a mixed query or cross-owner atomicity.

Preserve these interfaces and boundaries when that slice is available:

1. ExperimentalStore's physical protocol remains `_file_bytes` →
   `_file_snapshot` → `_file_read`. Committed capture ignores active transaction
   buffers. Transactions compare exact committed bytes, including no-op leases,
   and keep project/scope/lifecycle validation and original lock ordering.
   Reads do not migrate legacy documents or mint project/lifecycle ownership.
2. Optional resource admission belongs at the original payload reader. An
   already active usage budget charges every physical attempt/chunk, capture,
   retry, final revalidation and CAS reread. It does not replace duplicate-key,
   schema/project/metadata validation or authorization. TaskCenter HTTP has no
   new default resource-budget promise in this integration.
3. `ExportJobService.local_task_observation(novel_id)` observes the original
   committed same-file job/metadata document. Its evidence is private and is not
   permission. Preserve the real owner instance/path, original list ordering,
   cap/filter/source_truncated semantics and hidden metadata. Never construct a
   service, run startup recovery or submit/cancel/retry work on a GET.
4. Keep original identity/session/member/scope/grant observations scoped to the
   current actor and selected resources. Do not bind whole workspace/file epochs
   or expose changes to unrelated users, filtered rows or unselected authorities.
   Reauthorize using the real registered readers and repeat the final checks;
   captured evidence never bypasses an original reader refusal.
5. Strict usage reads reuse original registered RLocks, reentrancy and populated
   OS lock files. They do not create a directory/file/byte/registry entry.
   Missing facilities retain the explicit 409 contract. Compatible mode may
   perform its original first-use lock initialization. ContextVars and lock
   depths must clear on failure before later ordinary requests or writer threads.
6. Cursor continuation/replay keeps query, owner, lifecycle, authorization,
   process lifetime and mode bindings, sanitized refusals and no-store policy.
   Preserve original legacy no-page envelopes, error precedence, UNKNOWN / NOT_ASSERTED
   coverage and original public Export job/idempotency structures.
7. Same-file writer serialization is not cross-owner snapshot atomicity, complete
   history ABA, backup replay protection or active worker exclusive execution.
   Input/parse admission and cooperative deadlines do not establish RSS, CPU or
   lock-wait hard limits. Process-local cursors remain process-local.

BOT owns frontend and SDK changes; neither is changed by this integration.
The existing Windows asset-list cursor fault remains separately documented.

For a shallow checkout, fetch enough remote history before calculating the
merge-base; never treat a shallow boundary as proof of unrelated histories and
never force an unrelated-history merge to bypass that check.
