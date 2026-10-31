# Delayed original memory extraction owner probe

Baseline: f4ed62a1d2d8c7cce876745d92e0ec95b4b15ec7. No production edits; git status clean. Relevant source hashes captured and verified unchanged in source-before.sha256 and source-verified.txt.

## Result

Two deterministic positive counterexample assertions passed (latest run 2 passed in 3.00s). Both start a genuine original JobManager.create('continue') worker with built-in MockProvider, await COMPLETED, call original accept, verify ACCEPTED and durable PENDING Canon, and let the original MemoryAgentRunner.enqueue start its real daemon extraction thread.

- before_extract: delay the original _quiet_extract call, delete original project and recreate same slug and chapter IDs, then release. The replacement chapter uses identical accepted prose. Original extraction reads replacement sources and writes one PENDING proposal, one evidence record and one relation under replacement project. MEMORY_EXTRACTION completes.
- before_evidence_write: delay immediately before original LoreService.create_evidence, after original extraction has performed source equality validation. Delete/recreate owner with entirely different chapter prose, then release. Original service/repository writes one PENDING proposal and evidence under replacement owner. The asserted persisted evidence quote is absent from replacement chapter. MEMORY_EXTRACTION completes.

Both assert original/replacement incarnation differ, records were empty before release, proposal points to actual memory job, record reaches COMPLETED, exactly one inference call occurs, and no approved character memory exists. No approvals are forged. These are contamination of pending evidence/proposal state, not automatic memory approval.

## Synthetic boundaries and hooks

Writer: original built-in MockProvider.stream through actual Runtime and JobManager worker. Memory: existing test_memory_agent_contract.Runtime and MemoryMockProvider, a MockProvider subclass overriding _text to fixed valid synthetic JSON. Original MemoryAgentRunner._local_generation, local route verifier, LegacyTextProviderAdapter and GenerationRuntime text node run unchanged. No real model or external network is involved.

Only scheduling hooks: instance _quiet_extract wrapper waits before original call (first case), signals final completion in both; instance LoreService.create_evidence wrapper waits then calls original service method (second case). No replacement source reads, owner checks, write methods, approval decisions or production guards. Isolated test composition supplies file root and enabled built-in Mock settings. Initial import attempt failed on default XDG read-only directory; exact failed stdout/XML retained. Rerun supplies XDG_DATA_HOME and NOVEL_DATA_PATH under this probe directory. Exact passing command in command.txt; stdout.txt/results.xml hold latest results, first-pass artifacts preserve earlier run.

## Original affected path and minimum future seam

JobManager._accept_claimed creates accepted chapter and pending Canon synchronously, persists ACCEPTED, then calls enqueue(novel_id, accepted_chapter_id, version, profile). Continuation uses newly created chapter, not source chapter. MemoryAgentRunner.enqueue uses uuid5(slug/chapter/version), writes unbound QUEUED, starts thread; extract writes unbound GENERATING, source reads, local inference, source equality check, evidence/proposal/relation writes, then unbound terminal generation row. Exceptions also write unbound FAILED/NOT_CONFIGURED.

FileLoreRepository addresses folders by slug and has no project incarnation check or lifecycle lease around this write batch. FileGenerationRepository receives no binding and cannot apply its bound-owner persistence fence. The original memory source equality check does not cover owner identity and is not atomic with writes.

For future bound acceptance support: capture/derive original existing owner provenance while acceptance owner is leased; pass explicitly to original memory enqueue/extract; verify all participating novel/chapter/lore/generation ports resolve the same File root. Carry strict memory identity in QUEUED, GENERATING, COMPLETED and failure records. Validate owner before initial source work/dispatch and reacquire existing owner lease for final source validation plus all evidence/proposal/relation/terminal writes. Do not hold lifecycle locks across model inference. A terminal binding alone does not protect Lore writes. Use existing project lifecycle and CreativeProjectStore.existing_owner_only/owner_lease, never provision a replacement marker on delayed work. Retain genuine legacy unbound behavior separately; never silently downgrade malformed bound input.

Current OrdinaryProjectBinding only supports ordinary operations and binds exact job ID/chapter; MEMORY_EXTRACTION is not a supported operation and has a separate deterministic job ID plus adopted chapter identity. Copying parent ordinary binding verbatim would be invalid. Future support needs a strict derived memory persistence identity contract using the existing owner fence, not fake Graph IDs, not a new owner/queue/migration. Existing deterministic memory job ID also aliases same slug/chapter/version across owners: bound rows must not be silently overwritten or adopted when old/replacement identities differ.

This demonstrates current unbound legacy behavior. It does not claim any bound-memory implementation already exists or has been tested, nor does it authorize promotion to a wider bound review path before this prerequisite is implemented and verified.
