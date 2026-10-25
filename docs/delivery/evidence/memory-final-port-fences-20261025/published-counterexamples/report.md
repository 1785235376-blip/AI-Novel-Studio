# Supplemental review: final-port reentry and rotation

## Blocking finding

The published memory prerequisite does NOT protect against same-thread original project lifecycle reentry or final-port repository/backend rotation. This supersedes the earlier narrow PASS wherever that opinion could be read as covering these boundaries. Ordinary/manual bound acceptance should remain unavailable until its dependent memory ports are fixed and reviewed.

Six deterministic positive counterexample assertions pass (6 passed, 3 existing warnings, 5.88 seconds). Passing here means defects reproduced, not guard correctness. Worktree dcfe91a production files match published 5eb983f exactly for all eight inspected source files. SHA-256s, a complete frozen copy of those files, original test source, command, stdout/XML and matching published-hash verification are preserved alongside this report. No production files were modified.

## Reproductions

1. Wrap original LoreService.create_evidence. On the extraction thread, after final source comparison but before original method executes, delete/recreate the same project via original NovelService and helper composition, then call the unchanged original evidence method. One evidence record is persisted in the replacement owner. Later terminal/failure owner validation raises MEMORY_PROJECT_OWNER_CHANGED, but cannot undo that contamination; original raw receipt remains GENERATING.
2. Same scheduling hook at original FileLoreRepository.create_evidence: same replacement evidence contamination and late refusal.
3. Same scheduling hook at original FileLoreRepository.create_proposal, after service evidence validation: replacement proposal is persisted. Later relation/error processing refuses because original evidence was deleted; original generation remains GENERATING. This is pending proposal contamination, not memory approval.
4. Wrap original LoreService.create_evidence and switch its repository to another original FileLoreRepository instance for the SAME root before invoking unchanged original method. Extraction completes with all evidence/proposal/relation rows. The promised pinned-object check is bypassed.
5. Same wrapper switches the original Lore repository's backend object to another original same-root backend. Extraction likewise completes, bypassing backend identity pinning.
6. Same wrapper switches LoreService.repository to an original FileLoreRepository for ANOTHER File root containing the same source IDs. Full evidence/proposal/relation data are persisted in that other root, while original GenerationRepository persists bound COMPLETED against the original owner. Original root has no Lore rows. This demonstrates actual cross-root contamination, beyond an object-identity-only discrepancy.

All cases invoke genuine original MemoryAgentRunner.extract with an explicit bound project incarnation. Original File repositories, Lore/Generation services, GenerationRuntime and LegacyTextProviderAdapter/Mock chain run unchanged apart from final-port scheduling wrappers. The wrapper does not change atomic_write, owner guards, source content, inference results, or binding validation. Network socket connects are disabled; environment is isolated and no real provider is used.

## Cause and minimum remediation direction

_bound_owner verifies object/root composition and incarnation only upon entry. Its lifecycle lock is reentrant on the same thread; legitimate original delete/recreate can therefore run inside an entered context. Lore evidence/proposal/relation methods receive no expected owner or pinned composition value, so their last write boundary cannot distinguish the stale context. The original generation terminal fence catches a replaced original owner too late to protect Lore. With only Lore facade/backend rotation, even terminal generation validation succeeds because it still writes to the untouched original generation owner.

A read immediately before calling a replaceable service/repository method is not sufficient. Expected original owner and object/root composition need enforcement at the original final mutation port, using its original lease/guard, with those expectations surviving the legitimate wrapper boundary. Consider all evidence/proposal/relation paths, partial-retry paths, terminal/error receipt behavior and callbacks. The prior cross-thread lock evidence remains valid for that tested schedule, but does not prove same-thread reentry safety, arbitrary callback safety or whole-flow atomicity. No proposed implementation is approved by this report; exact final guards require new testing.
