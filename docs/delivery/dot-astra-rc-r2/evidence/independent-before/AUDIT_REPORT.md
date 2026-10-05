# Independent R2 integration audit

Snapshot: `eb16560988672bfbbf4a6c46431ddc4df6162f2d`
Git tree: `6a1b0081250eef7ae830ce584e7b5e1e48e68d0a`
Compared with: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`
Date: 2026-10-05 UTC

## Verdict

**REQUEST_CHANGES / ENGINEERING_IN_PROGRESS** for this fixed snapshot. Ordinary regression passes, but independent safety/data-integrity invariants below fail. These are findings against the frozen snapshot, not an assertion that concurrent later work still has the same issues. The separate Local AI Discovery supplement is outside this older snapshot and is not marked failed here.

No lead-tree source modifications, commits, pushes, merges, releases, deployment, real manuscripts, real credentials, paid API calls or real-model inference were performed. The audit used an independent `git archive`, scrubbed process environments, synthetic manuscripts, local media fixtures and recording transport doubles. All 1,236 tracked archive files still match the Git blobs after the tests (source-verification.json).

## Findings sent immediately to integration lead

### R2-IA-01 · P1 · Adaptation sends LOCAL_ONLY manuscript to remote models

- `app/services/adaptation_service.py:88-104`; API entry `app/api.py:1815-1816`
- The adaptation rewrite path copies full source text (including historical snapshots) into `TextGenerationRequest` and executes the selected provider without any source-privacy, hash-bound consent or project-policy gate.
- Reproduced with actual File repositories: create source chapter → create/approve/materialize adaptation → confirm `effective_source_privacy(source)==LOCAL_ONLY` → generate using recording remote node. Full source text reaches `node.execute`.
- No race is required. Blueprint approval is not source cloud authorization. Matrix C10's claim of inherited shared privacy boundaries is inaccurate for this path.
- Test: `test_adaptation_cloud_generation_cannot_send_unreviewed_manuscript`; `adaptation-egress.log`.

### R2-IA-02 · P1 · Agent context revocation is not checked at dispatch

- `app/services/agent_job_service.py:144-155`
- Context/hash validation precedes route preparation. No policy/authority revalidation occurs afterward before sending the already-built prompt.
- Actual File character starts CLOUD_ALLOWED. During the route-preparation boundary, its policy is persisted LOCAL_ONLY. Recording `node.execute` still receives `PRIVATE_FACT_CANARY`.
- Ordinary generation/planning have later checks; the Agent execution path lacks the equivalent. API authentication at entry is not a substitute for revalidation across slow preparation.
- Test: `test_agent_fact_revocation_during_route_preparation_must_block_send`.

### R2-IA-03 · P1 · Audio/image cancellation and audio privacy changes can lose the pre-dispatch race

- `app/services/audiobook_service.py:110-131`; `app/services/image_job_service.py:90-98`
- Both services claim an attempt and then perform preparation. A cancellation persisted during provider resolution is not checked before calling `generate`. Terminal-result fencing correctly prevents asset insertion afterward, but does not prevent the unwanted outbound/billable request.
- Audio also checks source privacy before the project-policy callback; a persisted source-policy revocation during that callback is ignored at dispatch.
- Three recording-provider tests confirm calls occur after persisted cancellation/revocation. No real provider or bill was involved.
- Tests: `test_audiobook_cancelled_during_provider_resolution_must_not_dispatch`, `test_image_cancelled_during_provider_resolution_must_not_dispatch`, `test_audiobook_rechecks_source_privacy_after_project_policy_check`.

### R2-IA-04 · P1 · Local stale Draft Accept silently overwrites newer saved text

- `app/jobs.py:233-240`; `app/api.py:1218-1226`
- `target_version` is computed from the job's captured generation base, but local-mode save uses current chapter version instead. The local API also omits `body.expected_version` when invoking accept.
- Actual File repro: generate/completed polish draft based on v1; user saves `NEWER USER EDIT` at v2; accept old draft. The operation succeeds and replaces the edit with `OLD AI DRAFT`, instead of returning conflict and preserving the newer manuscript.
- Inherited code retained by this R2 snapshot; relevant to mandatory D03 closure, not claimed newly introduced.
- Test: `test_local_stale_draft_accept_must_not_overwrite_newer_edit`.

### R2-IA-05 · P2 · Concurrent continuation acceptance produces duplicate side effects

- `app/jobs.py:195-242`
- No serialized/durable per-job acceptance claim protects the completed→accepted transition.
- Two accepts overlap while creating the next chapter. Both succeed and create two PendingCanon records for one job. Depending on File chapter-number allocation interleaving, the chapter count itself can stay unchanged because both create the same number; two successful results and two proposals are the definitive reproduced defect.
- Sequential repeated acceptance is blocked. The failure is concurrent acceptance, not a claim that every repeat duplicates.
- Test: `test_concurrent_continue_accept_must_create_only_one_pending_proposal`.

### R2-IA-06 · P2 · Project/outline restrictions are applied inconsistently

- `app/source_privacy.py:83-101`, called by `app/jobs.py:81-86` and audiobook; compare `app/services/ai_planning_service.py:117-123`
- The shared raw-manuscript guard checks seven knowledge collections but ignores explicit project/outline policies. Planning and import have extra checks for those policies.
- With a chapter separately approved CLOUD_ALLOWED and independent project or outline policy LOCAL_ONLY, generation still dispatches the raw chapter. Recording-request tests cover both cases.
- These tests use synthetic repository authority doubles. The finding is conditional on an existing persisted project/outline restriction; no claim is made that the current project UI exposes such a switch.
- Test: `test_generation_rejects_independent_project_or_outline_restriction[novel|outline]`.

### R2-IA-07 · P2 · Workflow UI applies stale cross-project responses

- `frontend/src/novel/WorkflowPanel.tsx:27-51`; mounting at `frontend/src/App.tsx:814`; related queue at `frontend/src/novel/AgentQueuePanel.tsx:22-39`
- Workflow requests do not use scope/epoch checks. The module subtree has no project/branch/session remount key; AgentQueuePanel observes project only.
- Independent Vitest repro: start project A list, rerender project B, let B's empty response finish, then resolve A's delayed response. `PRIVATE_PROJECT_A_WORKFLOW` is rendered in project B.
- This proves stale UI data display; it does not claim the backend accepted a cross-project mutation.
- Test and evidence: `WorkflowPanel.independent-audit.test.tsx`, `workflow-ui-scope.log`.

## Verified regression and former findings

- Full File backend suite: **1,845 passed, 36 skipped**, 1 warning; 102.62 seconds. `full-file.log`, `full-file.xml`.
- Frontend full default unit suite (excluding only the added independent failing audit test): **484 passed, 103 files**; TypeScript, design-token lint and Vite build passed. Large-bundle warning retained. `frontend-full.log/xml`, `typecheck.log`, `token-lint.log`, `frontend-build.log`. The earlier `src`-restricted run was 479 tests and overlaps this full suite.
- Independent adversarial Python invariants: **9 failed, 1 passed**, no harness errors; plus one failed independent frontend scope invariant. These fail results are the evidence for the findings, not a regression pass. `adversarial-final.log/xml`, `workflow-ui-scope.log`.
- Focused privacy, source egress, planning, media, import, backup, plugin, workflow, screenplay CAS/history, export recovery/resource suite: **245 passed, 4 skipped**, 1 warning. This overlaps the full suite, not additional unique coverage. `focused.log`, `focused.xml`.
- Former timeline/foreshadowing/Canon fixes have File and serializer contract coverage in the passing suite. Real PostgreSQL integration remains separately NOT_RUN by this auditor.
- Former Fountain cases: independent complete **fountain-js 1.2.4**, 8 synthetic mixed/numeric/case-preserved character, multiple-empty-dialogue-line and syntax-looking action cases pass. `fountain-parser.json`, `fountain-inputs.json`. This is parser compatibility, not a Windows screenplay application's acceptance.
- Former export rediscovery/same snapshot/download, owner/branch/revocation checks and frozen resource-package tests pass in the focused/full suites. No new concrete export-boundary defect was reproduced.
- Source privacy unknown/stale/explicit restriction, ordinary generation chapter-tail egress, cancellation and partial-stream no-fallback tests pass. The findings above are additional paths/windows, not a claim that the repaired ordinary tail path remains wholly unguarded.
- Existing screenplay File CAS/history, media download DNS pinning/private-address/redirect/limit checks, binary inspection, late-result fencing, backup exact inventory/traversal/symlink/corruption/secret JSON/no-overwrite contracts, plugin execution deny and workflow rejection/deadline tests pass.

## Scope/readiness review

Read complete adopted main R2 brief and embedded history, repository AGENTS, applicable UI skill/test guidance, matrix and relevant implementation. D00-D18 and all 143 original feature IDs are represented; matrix explicitly distinguishes PARTIAL, NOT_CONFIGURED, MOCK_ONLY, CONTRACT_VERIFIED and NOT_RUN. Three recipes are honestly disclosed as local rule review artifacts, visual memory as lexical metadata search, plugin execution as DENY_ALL, and video assembly as limited silent review output. These bounded features are not treated as real-model or complete-product validation.

The D03 implementation claim and C10 privacy statement need adjustment until the reproduced acceptance/adaptation defects are fixed. Actual final SHA/hosted CI/update of delivery receipts belongs to the integration lead. This audit is not an all-files line-by-line security certification.

## NOT_RUN / boundaries

Real PostgreSQL server/migration/restart/backup restoration; hosted GitHub CI; native Windows Host/WebView2/AppContainer/OS vault; Windows install/upgrade/uninstall; interactive browser/Chinese IME; real local GPU or paid/cloud provider inference; final screenplay/Word/EPUB-reader desktop compatibility; user acceptance. Existing authored test files or other workers' logs are not counted as this auditor's execution.

The initial independent Python harness had frozen-settings/create-return-shape errors, corrected before final invariant runs; they are not counted as product defects. All final findings are assertion-level repros. Frontend installed dependencies were copied to the isolated archive; no new frozen install is claimed.
