# Static coverage limits at the integrated candidate

This is a static M2/M3/M4 coverage review, not a new test result. Development
passes are in CORE_NOTES.md; final frozen-copy receipts remain the authority for
each exact command, environment and source hash.

| Requirement | Implemented / directly targeted | Remaining boundary |
| --- | --- | --- |
| M2 raw-byte snapshots and predecode admission | One optional raw JSON byte boundary in ExperimentalStore; identity/scope/grant/Export use the same active request budget; core probes cover size, depth, string, scalar, token limits and all five decoders | The budget belongs to the explicit paged usage HTTP chain. TaskCenter HTTP does not acquire a new default budget. Metadata syscalls, lock waits and unrelated routes are not bounded payload claims |
| M2 retries, final observations and amplification | Physical CAS rereads, committed captures and ordinary authority rereads cannot reset an active budget; byte-exact whitespace comparison and short-read/pre-open change probes are present | Final integrated mounted/TCP instrumentation must demonstrate actual read reconciliation; isolated reader tests alone do not prove every mounted authorization path |
| M2 syntax and metadata | Store/identity duplicate rejection retained; scope/grant/Export duplicate rejection added explicitly; corrupt lifecycle metadata remains refused | Export's old missing/syntactically malformed/non-object fallback remains `{}` for compatibility. This does not produce a reliable lifecycle observation. Full arbitrary corruption recovery is not implemented |
| M3 original writer / lock coexistence | A coordinator remains intact; B identity/audit, scope, grant, store and Export writer order and reentrancy retained; core/independent tests target cleanup, another-thread writers and cross-instance physical CAS | Strict existing-only mode requires prior original registration and lock facilities. A fresh process/path may refuse until an explicit compatible operation establishes them. No hard acquisition deadline or new worker-exclusivity protocol |
| M3 lifecycle ownership | Original same-file metadata, nonce/incarnation validation, legacy non-adoption and selected-row ABA evidence preserved; ordinary owner regression groups cover identity/member/session/scope/grant/row changes | No complete collection-membership ABA, invisible insert/remove history, external backup replay protection or cross-file rollback transaction |
| M3 process crash boundary | Windows harnesses now target before/after atomic replace for Export/local ExperimentalStore and identity/scope/grants/collaboration-team, then fresh-process writers; controlled owner contention and distinct/identical Export keys are separate probes | Historical POSIX suites still remain NOT_RUN on Windows; new Windows tests provide their own evidence. No harness establishes power-loss durability or cross-file crash atomicity |
| M4 query assembly | Both middleware additions retained; usage guard remains outermost; original TaskCenter authorizer, reader registry, safe projection and final revalidation retained | Supported cursors remain only File/local semantic_import, File/local exports, and File/collaboration agent_team with the validated no-source window. Mixed sources, collaboration exports, packaged and PG cursor support remain refused |
| M4 strict/no-store and authority precedence | Original strict success/refusal and authority-budget regressions passed in development; independent mounted refusal tests preserve each original route's public code | Successful frozen `/api` and `/api/v1`, session/member/role/scope revocation, invalid queries, continuation/replay and final denial evidence must come from the final HTTP groups; static middleware order is insufficient |
| Measurements | New measurement records initialized first/continuation/replay/repeat requests, actual bytes, Python allocation and Windows working set | OS caches are not cleared. 5 ms working-set samples can miss peaks; process-lifetime peak includes imports/setup. These are observations, not per-request RSS limits or speedup proofs |

The first Windows process development timeout was traced to test cleanup:
calling `Event.set()` after terminating its waiting child can block inside
multiprocessing notification. Removing the unnecessary notification is a
test-only correction; the timeout is retained and is not attributed to product
storage. The initial measurement setup omitted the nested `audio_history`/`rig`
fixture imports; that setup error is also retained separately from a corrected
run. Neither failed development run counts as acceptance.

Supplementary Windows owner development verification: the new
`test_file_backend_safety_windows_owners.py` ran **20 passed**, exit 0, no timeout,
in a separate clean detached copy of `43a0d43291148651caab2f89a27a9a3920a437fc`,
tree `9b78e4610e6c91a83ec9095d76654c1f2bc06c77`. Its eight TerminateProcess probes
cover before/after replace for identity/scope/grants/team; eight fsync/replace
failure probes verify unchanged exact bytes/metadata and fresh-process recovery;
four two-process probes hold the first at replace, observe the second's native
lock attempt, then release and verify both committed rows. Duplex Pipes provide
the barriers without sleep-based progress assumptions or abandoned Event waits.
The recorder reports source unchanged, no external parent app modules, and
`complete_pass=true`; raw log, module list and hash receipt are in
`windows-owner-development/`. This precursor receipt is separate from the later
unified final-freeze result.

No frontend/SDK/browser, real model/GPU, PostgreSQL, hosted Actions, POSIX-on-this-
machine, deployment, package install or system security change is claimed.
GraphFlow's legacy context/plan/index tools were unavailable; the later precise
gf_read refresh attempt returned `Transport closed`. No successful index refresh
or context-saving metric is asserted.
