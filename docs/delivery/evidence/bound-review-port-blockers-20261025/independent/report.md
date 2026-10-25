# Independent bound File memory prerequisite review

## Opinion

PASS for the narrow reviewed prerequisite on the six final SHA-256 entries in source-before.sha256; all verified unchanged after execution in source-verified.txt. Base f4ed62a1d2d8c7cce876745d92e0ec95b4b15ec7. Final targeted run: **19 passed, 3 existing warnings, 6.70 seconds**. Not approval to enable bound ordinary accept or API capture, and not a claim of full acceptance atomicity.

## Confirmed defects and repair

Initial independent run found two actual failures: (1) successful proposal creation followed by a relation-write I/O failure left a FAILED operation; its same-owner retry became COMPLETED with zero evidence relations. (2) a prior legacy extraction with identical source/output was silently reused by bound completion, but the returned proposal retained the legacy generation_job_id. Exact failing assertions, stdout/XML, command and production hashes are retained under initial-defects. The original temporary path mistake ran no tests and is separately retained under initial-path-failure.

Revised bound-only code prefixes proposal/evidence seeds with the owner-inclusive bound job ID and verifies/reconciles existing proposal relations. Both unchanged independent regression assertions now pass. Final source files are copied under frozen-source, with frozen-production.diff for tracked changes. Initial red evidence includes exact probe source and production hashes, not a full copy of those historical production files.

## Independent targeted coverage

- Failed same-owner extraction → retry produces real original evidence/proposal/relation and bound COMPLETED receipt; enqueue reuses stable operation identity and terminal dedupe.
- Old FAILED owner's retry refuses after delete/recreate; replacement owner receives a distinct operation identity and completes separately.
- Missing relation after partial write is repaired; legacy proposal provenance is not adopted by a bound operation.
- Original lifecycle lease spans final source recheck, evidence/proposal/relation and COMPLETED persistence. A second thread attempting real File deletion cannot pass while paused at the source-recheck boundary; durable terminal completion occurs before deletion removes owner.
- FAILED error recording also holds the original lease, and stale inference cannot write an error into a replacement owner or modify its data.
- Real second-thread deletion completes while model inference is blocked: no lifecycle lease spans inference. Source/owner revalidation prevents final replacement writes.
- Queued delay and adapter-preparation replacement both yield zero provider calls and no replacement writes.
- Removed/null/mixed/boolean malformed binding updates reject without changing original durable bytes.
- Wrong File service object and generation-root rotation refuse before relevant writes; bound root rotation during inference leaves no Lore output.
- Runtime observers are called after lease exit: callbacks launch another thread that successfully acquires the same original lifecycle lock before the callback returns. This verifies transaction deferral rather than relying only on source nesting.
- Original PostgreSQL repository explicitly refuses bound memory before touching its database; this is offline refusal coverage, NOT a real PostgreSQL transaction/concurrency test.
- Bound local provider error never calls an available remote route.
- Delayed genuinely unbound legacy enqueue still adopts the replacement owner and completes. This positive legacy counterexample is intentionally retained; the old flow has NOT been repaired by the new opt-in seam.

## Method and limits

Exact command: bash .runtime/bound-memory-independent/run.sh. run.sh resets environment, uses isolated HOME/XDG/data/tmp and the existing dependency environment, hashes production before execution and verifies afterward. Probe fixtures block socket connect/create_connection. Tests use genuine original File repositories, LoreService, GenerationService, MemoryAgentRunner and original GenerationRuntime/LegacyTextProviderAdapter chain with the existing built-in Mock subclass emitting synthetic JSON. Only deterministic scheduling gates and one injected relation I/O failure are applied. No paid provider, model download, or external network is exercised. Imported fixture/helper source hashes are in probe-source.sha256.

This is owner fencing of cooperating original File paths, not a filesystem sandbox, protection from hostile direct filesystem mutation, chapter-incarnation guarantees, universal crash atomicity/rollback, or transactional delivery to observers. Partial multi-file Lore output can remain on failure; the reviewed retry repairs the tested deterministic same-output relation failure, not arbitrary crash recovery. Direct extract remains callable, while bound ordinary mutation and public admission/capture gates remain closed. No queue, registry, migration, or ordinary-binding reuse was introduced. The server-provided project incarnation is identity, not an execution authorization grant. Live PostgreSQL, real local model inference and full end-to-end ordinary accept activation remain NOT_RUN/not implemented here.
