# TaskCenter consistent query — M0 source checkpoint

Status: PARTIAL / EXECUTION_BLOCKED. This checkpoint is not a passing acceptance report.

## Exact origin

- Repository: 1785235376-blip/AI-Novel-Studio
- Requested base branch: work/hermia-backend-contracts-20261025
- Fixed commit: ffe1937911cff32d4ebd4770b350674627501d3a
- Git commit API tree: 447bfefcee8393b9b0907fe7daff2d5b044709da (exact match)
- New branch created from that exact commit: work/taskcenter-consistent-query-20261025
- Only root AGENTS.md exists in the fixed tree; read before implementation.
- No cloud checkout is available to inspect for local modifications. No reset, force push, main update, or alternate Codex task was performed.

GitHub GET /repos/1785235376-blip/AI-Novel-Studio/git/commits/ffe1937911cff32d4ebd4770b350674627501d3a supplied the original commit/tree identity. A repository/ref search confirmed the requested base branch exists. Its moving HEAD is not substituted for the fixed commit.

## Existing behavior (not new work)

GET /api/novels/{nid}/experimental/workspace/tasks and /api/v1 alias already provide q, failed_only and opt-in limit/offset. Original task readers are ordered:
author_generation, workflows, semantic_import, media, agent_team, audiobook, voice_direction, agents, exports, images, review_inbox, audio_tts, motion, subtitle_processing, adaptation, research_analysis, visual_identity.

Central inspection remains rows[:200] per original reader. Legacy response is capped at 500; offset limit is 1–100. observed_total is only the bounded authorized, safe, filtered projection. Coverage is BOUNDED_AUTHORIZED_PROJECTION / NOT_ASSERTED. There is no cross-owner atomic snapshot or source I/O pagination guarantee.

Existing tests explicitly require an isolated unknown cursor parameter to be ignored. A new explicit page_mode=cursor selector must avoid breaking that contract. The last four readers are registered after router construction; OpenAPI must not capture an incomplete early registry.

## Five actual work units

1. Contract/type parsing and compatibility — contract_review.
2. Standalone consistency cursor candidate and isolation — cursor_design.
3. Independent security counterexamples/review — security_review.
4. Real File/mounted HTTP, zero-write and measurement test preparation — file_http_validation.
5. Remote integration, staged commits, exact ref/CI checks — root.

Units own separate new files; only root changes ux.py/ux_api.py or updates the branch. No parallel writes to one checkout.

## Execution evidence and limits

The standard command entry point failed before running its command:
CreateProcess: exec-server rejected request (-32603): helper_unknown_error: setup refresh had errors.

An independent work unit reproduced the same initialization failure. The current tool catalog exposes no bound cloud_environment.environment_status / cloud command executor. A runtime inventory probe saw a Windows host; that is not evidence of a cloud executor and is not used for backend testing or project data access. No user old project directories or credentials were read.

The fixed tree contains no .github/workflows directory (complete tree response, truncated=false; contents request returns 404). Existing runs on other commits do not validate this task. Do not add or transplant a workflow silently. CI for this branch is expected NOT_CONFIGURED unless the remote reports otherwise.

Original focused tests: NOT_RUN.
Repair-before red tests: NOT_RUN; no invented failure count.
Real File/HTTP, synthetic performance, cold independent-process tests: NOT_RUN.
PostgreSQL, frontend, models: NOT_RUN.

## Reliable lifecycle findings / dependency pause

CreativeProjectStore.existing_owner_only() and incarnation(nid) can read original project identity without creating a missing marker. Never use capture_new() on a query, and never hold owner_lease around all readers.

TrustedSessionResolver.binding_generation(token) provides an original session generation for token revoke/register ABA. ReadContext string equality alone does not.

Original collaboration membership/permission/branch APIs do not expose a reliable common monotonic lifecycle observation. IdentityService.set_membership_status has a path without audit; timestamps or final-value hashes cannot prove absence of A→B→A. Some original task rows lack a reliable owner revision/incarnation.

The HTTP cursor dependency is therefore paused, not replaced by a parallel authority system. An explicit cursor request must fail safely with a fixed UNSUPPORTED response until a reliable original lifecycle observer is integrated. Independent type filtering, truthful capabilities, a non-wired cursor primitive and counterexample tests can proceed. The primitive must not be described as a usable frontend cursor.

## Red-test plan (not execution)

The new tests must expose ignored authority filters, malformed/duplicate/empty authority handling, explicit cursor silently falling back to old responses, and missing OpenAPI descriptions at this baseline. Further tests cover both prefixes, exact legacy envelopes, scope/revocation priority, source truncation without hidden counts, and complete business-file snapshots (only the exact original lock directory excluded). Synthetic engine tests cover mutation of full projection/order/revision, cross binding, TTL, capacity and process-local loss; they do not prove original owner wiring.
