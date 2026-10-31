# Independent generation replay review

Date: 2026-10-25 UTC.
Requested baseline: e99e91ed84763224638b80ffb83ae7880fa4f1a0.
Review mode: read-only production/test inspection; controlled probes written only below this evidence directory. No network, real provider, PostgreSQL service, or production data access.

## Conclusion

No blocking finding remains in the reviewed three-file production patch for the bounded owner-replay defects. The two original controlled counterexamples now fail closed, and five additional independent File/Mock probes pass. This is not a claim of complete race freedom, cross-process exactly-once execution, or real PostgreSQL verification.

The reviewed production hashes are recorded in `final-source.sha256` and were verified before and after the final probes:

- app/api.py: d40588c7190472b778b41ad67bf4ea6bc69f8613d4858ca46b8c92471fb08ed7
- app/idempotency.py: 88b03eff20b10333645ae443169611adff1fe730c48453c2966f3a80d6e3214d
- app/services/generation_idempotency_authority.py: acdeb4d93a14103d4c7f0c0f50a3e57f57c3bad40ca7ba54bc2f681015941437

## Design checks

1. `api.py:1433-1435,1465-1474` retains the existing scoped key namespace. Retained legacy unscoped entries are also recognized; a missing new namespace is not used to adopt or silently replay an old claim.
2. `idempotency.py:13-29` adds a read-only retained lookup. Existing malformed JSON, a malformed record, and falsey values cannot become a successful cache miss. It does not change other callers' original `get()` TTL behavior.
3. `api.py:1475-1504` requires the bound schema and original four-field response shape, verifies the actual project incarnation, and rejects expired retained generation keys with an explicit conflict. Old unbound, corrupt, stale-owner, and expired records are not deleted or converted into new dispatches.
4. `generation_idempotency_authority.py:43-95` derives File ownership from the actual novel/chapter repositories and validates the registered branch repositories and store. It does not use `settings.data_path()` as a substitute owner. PostgreSQL requires the actual shared repository `Database` and a matching registered branch database configuration.
5. `generation_idempotency_authority.py:97-107` reuses `CreativeProjectStore`, including its File marker validation and lifecycle lease. Only a confirmed new request key may provision a marker. Replay uses `existing_owner_only()` and cannot repair or recreate a missing/corrupt identity.
6. `generation_idempotency_authority.py:21-34` adapts the original PostgreSQL owner query to the actual repository engine. The original `SELECT id FROM novels WHERE slug = %s FOR KEY SHARE` and UUID identity remain authoritative; no timestamps, filesystem inodes, or content hashes are substituted as incarnations.
7. `api.py:1513-1537` repeats current request/source/permission checks after cached job lookup, then compares the incarnation in a short lease before returning. Exact chapter ID, current project, archive/deletion state, current branch feature, trusted actor, and current scope are checked through the existing paths. It does not invoke an Audio/Asset owner or broaden content reads through `_generation_content_context`.
8. When `jobs.create` returns successfully, `api.py:1528-1535` retains the bound receipt before final revalidation. A later owner/source rejection therefore does not erase the successful dispatch receipt and silently permit the same key to dispatch again.
9. No-key generation, variants, and `_generate_once` retain their existing default context behavior. The active-source tightening and project-marker provisioning are keyed-generation behavior only.

## Lock-order review

- The original global generation idempotency lock remains outermost on the keyed route.
- The new owner lease does not span `jobs.create`, `jobs.get`, authorization checks, or branch/source reads.
- Existing JobManager startup holds `self.lock` while persisting. Source-bound persistence may acquire a project lease, so wrapping `jobs.create` in a project lease would introduce the reverse `project -> JobManager` ordering. The patch does not do that.
- Existing creative operations use source-scope-before-project ordering; project retirement uses authorization-before-project-before-collaboration-scope. The patch does not hold its project lease while entering these owners.
- This static review and the bounded concurrency tests are not a universal deadlock proof.

## Independent controlled probes

Final evidence: `final-probes.json`, `final-original-probes.json`, `final-assertions.json`, and `final-source-before.log` / `final-source-after.log`.

All seven checks passed, with denied responses containing no retained job ID:

1. Legal HTTP project delete/recreate and chapter-ID reuse: 409 `IDEMPOTENCY_OWNER_CHANGED`, dispatcher count remains one.
2. Real branch archive and source deletion inside cached `jobs.get`: current replay and the next replay both return 404 `CHAPTER_NOT_FOUND`, dispatcher count remains one.
3. Removing the original marker after an initial successful generation: 409, marker remains absent, cache bytes unchanged, dispatcher count one.
4. Replacing only the global settings data path with a decoy: successful first generation binds the actual repository marker, not the decoy path.
5. Replacing the project after the dispatcher has produced a job but before it returns: initial request and retry both return 409, receipt survives unchanged, dispatcher count one.
6. Only archiving the branch source during cached lookup: 404 without deleting the source or modifying cache bytes; dispatcher count one.
7. Copying readable branch source state to a different store root: 409 `IDEMPOTENCY_OWNER_UNVERIFIED`, zero dispatches, no cache created. This is a configuration-boundary probe, not a demonstrated remote exploit.

The baseline probe file `baseline-probes-rerun.json` records the original unsafe metadata responses. An earlier probe setup failed because Settings is frozen; its stderr and exit file remain. That harness error was corrected with `dataclasses.replace`; it is not a production failure.

## Verification and claim limits

- The implementation worker's final JUnit was independently inspected: 102 passed, zero failures/errors/skips, 16.725 seconds. This is 37 other B-group cases, 55 idempotency-file cases, and 10 canonical variants cases. The 12 offline PostgreSQL protocol/config cases are included, not additional tests. The reviewer did not rerun this batch or add its seven probes to that test count.
- The original counterexamples demonstrated stale job metadata, not generated-content disclosure. The independent checks retain that distinction.
- The final source observation and response are not an atomic transaction with every possible later source/feature/permission change. No new source-scope lease is introduced.
- No claim is made for cross-process idempotency, crashes between dispatch and receipt persistence, disk-write failure, or an uncertain `jobs.create` outcome.
- A keyed request's new transient authorization callback is used by the original branch worker path. Its mere presence does not prove that every local unscoped worker invokes it at every dispatch boundary.
- PostgreSQL adapter/config tests use controlled protocol doubles and offline configuration. A real PostgreSQL service, Windows locking, real model providers, UI behavior, and the complete repository suite were not run by this reviewer.
- The approved generation TTL contract is deliberately stricter: even an expired currently bound generation receipt requires an explicit new key, rather than automatic redispatch. Other operations retain the old TTL behavior.

## Release validation checklist

- Preserve the two original red-to-green regression nodes and the pre-repair evidence.
- Run the full updated idempotency contract file, the original B-group selection, and nearby no-key/variants/runtime boundary tests on the final frozen source.
- Keep legacy scoped/unscoped, malformed/falsey, expired, missing/corrupt marker, root mismatch, late source/feature/permission change, and post-dispatch owner/source failure cases.
- Keep the PostgreSQL original-query/parameter, transaction cleanup, and actual-owner configuration tests clearly labeled as protocol/config-only until a real PostgreSQL job verifies them.
- Recheck `git diff --check` and final production hashes after any later change. Do not claim the whole suite, PostgreSQL parity, or exactly-once execution from these bounded results.
