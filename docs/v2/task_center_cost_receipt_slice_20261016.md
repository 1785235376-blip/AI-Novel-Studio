# Task Center original-job cost receipt slice

Date: 2026-10-16

## Delivered scope

Task Center now offers an explicitly selected, read-only original-job cost receipt beside a task. This is a consumer of the existing broker history endpoint and ledger, not a new billing service or an extension of the aggregate task projection.

- Reuses the shared broker history GET through the existing captured Studio session/branch transport. Existing server actor/project authorization and feature gates remain authoritative and unchanged.
- Only `author_generation` tasks are eligible for a broker history read. Attribution requires exactly one ledger row with the identical original job ID and matching project/scope. Provider/model display names are never matching keys.
- Missing, duplicate, malformed, unsupported and unreadable receipts remain UNKNOWN. The owner's latest-100 history limit is disclosed; absence is not evidence of zero cost. Media costs remain unknown.
- Displays original ledger state, provider/model, price source/version, USD and micro-USD units, reservation estimate, recorded actual amount, and explicit synthetic status. Six fractional USD digits retain one-micro-USD values. Zero is distinct from null.
- Usage-derived amounts are labeled as calculations from reported usage, not invoices. Synthetic zero and not-dispatched zero are distinct. User-reported reconciled amounts are labeled as not independently verified here. UNKNOWN_UPSTREAM cannot produce a retry action.
- Selection, close, queue changes, refreshed task records, project/session identity changes, inactive views and stale identity checks suppress obsolete receipts. Receipt read errors do not replace task data, expose upstream error text or cause a fallback access attempt.
- A pure recovery explanation repeats the original owner's preflight/recovery policy and actual completed/total counts. Counts are explicitly not proof of a durable checkpoint. No retry, resume or replay control was introduced.

No backend changes, ledger mutation, new prices, reconciliation operation, provider call, credential access, permission expansion or dispatch integration were added. Existing official packs and reserved graph cloud execution boundaries are unchanged.

## Verification

Focused frontend fixture/contract tests: 97 passed across seven files:

- `taskCostReceipt.test.ts` (24)
- `taskCenterClient.test.ts` (14)
- `taskCenterContract.test.ts` (17)
- `useTaskCostReceipt.test.ts` (9)
- `useTaskCenter.test.ts` (9)
- `TaskCenter.test.tsx` (15)
- `ModelBrokerPanel.test.tsx` (9)

These cover exact/missing/duplicate matches, scope mismatch, malformed amounts and state combinations, zero/null/units, synthetic and upstream-unknown presentation, unchanged captured GET transport, no media history read, failure isolation, explicit-only reading, and stale-result races. Broker panel regression tests use mocked transport, not real provider dispatch.

Also passed: TypeScript build check, Vite production build, UI design-token guard, test-discovery check, and `git diff --check`. Vite retained its large-chunk warning; this slice does not change bundle policy. Discovery is only discovery, not execution of the listed suites.

## Limits

No full test-suite run, browser visual/geometry acceptance, Windows/GPU test, real-provider output or payment acceptance was performed. Shared layout and styling were reused without token, shell, CSS or screenshot-baseline changes. Full product/local acceptance remains deferred. Hosted CI remains externally billing-blocked; it was not rerun and no settings were changed. This slice makes no release-readiness claim.
