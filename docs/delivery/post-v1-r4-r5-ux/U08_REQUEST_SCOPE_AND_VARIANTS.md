# U08 request scope and exact local variants

This is feature implementation, not closure of the separately platform-blocked independent review.

## Actual author workflow

- The existing AI writing inspector exposes automatic source, exact saved selection only, and no-manuscript modes.
- Automatic context can be removed as one bundle. It is not resolved and does not enter either prompt or adapter context. No manuscript mode never falls back to the saved chapter tail.
- Selection-only and no-manuscript modes also remove automatic summaries, policy/context packs, memory, and all approved style/plan references. Current source metadata cannot prove substring-level independence; the UI explicitly explains this conservative removal.
- Existing selected approved STYLE / PLOT record IDs can be pinned or removed. Pins bind current approved versions through the existing creation service; this is not a new reference store, version freeze, or arbitrary-source picker. Changing an excluded reference ID still invalidates the input receipt.
- Explicit user-written instructions and freehand style remain author input; the controls do not promise to redact text the author explicitly writes into those fields.
- A05 character mode keeps its existing physically separate local-only knowledge path; generic manuscript controls are unsupported there. U05 partial-only selection receipts and generic-accept prohibition remain intact.

## One request authority

`AuthorPreparer` normalizes controls before resolving approved references. `JobManager.prepare_author_request` avoids omitted automatic context resolution; `build_author_request` applies the same boundary again. Scope options, exact author inputs, actor/scope, source/version/digest, route locality and approved records join the request digest. The transient current-authority closure and final adapter dispatch guard recheck them. Persisted jobs retain the review receipt, never the transient authorization closure.

The frontend carries the exact reviewed request body. App compares current source, model, instruction, options, session/scope and saved version against that receipt before submitting. Any change clears the review and requires another preflight. The broker's single-author path consumes the same request shape and remains on its original budget ledger.

## Bounded per-variant mapping

`POST .../author-context/preview-variants` and `generate-variants` accept 2–3 explicitly selected local candidates. Each variant has its original suffix instruction, exact payload/digest, stable original job ID, group ID/index and policy proof. All previews must validate before any job can start. UI shows each exact prompt, adapter options and request/job mapping.

All jobs are recorded as PREPARED in the existing generation persistence before the first start. Existing group/job history, usage, cancellation, Draft / Diff / Accept and version authority are reused. Repeated group submissions return original IDs; mismatched receipts, reordered/omitted members, altered count/scope/model/instruction and substituted group IDs fail closed. A partial start does not authorize remaining requests later. Missing persisted members or uncertain persistence are reported UNKNOWN; cancellations/start failures preserve the complete mapping. Restarts do not recover authorization closures or replay calls. Browser transport failures preserve reviewed job IDs for existing-task recovery.

## Budget boundary

The composition-injected `variant_policy_guard(nid, scope, actor, provider_id, model_id, count)` is mandatory. Its JSON receipt is included in each reviewed digest and rechecked before staging and immediately before adapter dispatch. Missing authority makes variants unavailable.

A06-enabled or persisted broker budget/ledger/price policy blocks this direct batch path, including after the broker flag is disabled. Cloud batches are also blocked. There is no claim that local means zero cost: local cost remains unknown. Budgeted/cloud groups require a real multi-reservation coordinator; authors can use existing individually budgeted broker jobs meanwhile. No paid call or provider retry is introduced by this feature.

## Validation and limits

- Deterministic synthetic capture covers excluded-source canaries, no derived re-entry, scope/permission/source drift, exact per-variant requests, incomplete/reordered receipts, cancellation, partial starts, restart/missing-member handling and policy receipt changes.
- Mounted tests use production routers and original File / explicitly opted-in real PostgreSQL repositories, including current approved pin revocation, saved scope receipts, group restart and A06 policy exclusion. PostgreSQL is not available locally; its marked cases remain NOT_RUN here until exact-commit hosted results return.
- React tests cover real controls, disabled dependencies, receipt invalidation, exact multi-preview mapping, incomplete preview rejection and late replies. Existing shared generation regressions are retained.
- `r4-author-scope-variants.spec.ts` is the real React/File hosted journey: remove manuscript, inspect each synthetic request, generate original jobs, compare drafts, repeat without extra calls, reload, and explicitly accept one original candidate. The dedicated 8023/5183 service uses shipped labeled `mock_standin`; this is not real model validation.
- Known local Chromium EPERM is respected: no local browser retry, screenshots or claimed browser PASS. Playwright discovery is checked without launching a browser. Hosted execution/geometry must be assessed on the published engineering commit.
- Per-source arbitrary removal and pinning unsupported records are not exposed. Only whole automatic-bundle removal and current approved style/plan IDs have authoritative support. U08 therefore retains these explicit granularity and budgeted-multi-request limits.

## Local execution receipts (2026-10-05)

Commands ran through the existing isolated `r2-run.sh` harness or the existing pinned pnpm toolchain. Results below are separate runs, not summed as a cumulative pass count.

- Composed author/scope/variant/U05/A05/hooks/broker focused run: 118 passed, 51 skipped. Skips are not PASS; real PG cases remain hosted-only here.
- Shared legacy generation/idempotency/restart/snapshot/variants/egress/origin/A05 regression: 107 passed, 66 skipped.
- Current scoped React suite (author controls, writing, character, broker, revision, generation scope and recovery): 70 passed. Subsequent author/broker receipt-map check: 18 passed; final writing/preview/timeline retry-state check: 30 passed.
- Final mounted-only rerun: 16 passed, 16 PostgreSQL skips.
- TypeScript build and production frontend build passed; Vite retained its existing large-chunk warning. Design-token guard passed. New hosted journey is discoverable by `playwright.r4.config.ts --list` (1 test); discovery is not browser execution.
- Logs remain in the disposable execution workspace; no raw runtime logs, user manuscripts, secrets or machine configuration are committed. Hosted results must name the published commit before any PASS claim.
