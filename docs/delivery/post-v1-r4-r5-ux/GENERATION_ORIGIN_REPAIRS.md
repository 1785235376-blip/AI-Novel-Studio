# Generation origin and terminal-accounting repairs

This is the implementation repair of two already-reproduced defects from the `41723cd` checkpoint, not a new independent review.

## Disabled-origin behavior

Server coordinators stamp `experimental_origin` and `required_experimental_features` on author-preview, character-author and broker jobs. These fields are not copied from caller generation payloads. Existing persisted `expected_request_digest`, `character_viewpoint` and `dispatch_hooks_required` fields supply minimum required-feature inference for older receipts.

`require_generation_content(job)` enforces current feature flags and V1 acceptance mode across the legacy generation read, events, groups, diff, accept, retry and reject paths. Accept checks again after reading durable state under its existing write lock. Active event streams stop before emitting another disabled-content chunk. A normal V1 job with no experimental origin remains readable and acceptable with all experiments off.

Cancellation remains available through the existing ownership/session checks, with only ID/status and an explicit hidden-content marker when the required features are disabled. Existing authenticated broker accounting recovery can also read a stripped ledger receipt, cancel, or perform version-checked reconciliation. Recovery does not disclose prompt, output, source excerpts, provider/route details, price notes or history. Orphan reconciliation still requires both upstream-terminal and original-executor-stopped confirmations. Disabling features never automatically releases an ambiguous ledger hold.

Consumers of generated drafts must call the existing authorized generation reader or reapply `require_generation_content` after resolving the job's owner/scope. Derived acceptance must recheck the source job; a copied draft does not bypass a later origin revocation.

## Terminal accounting and acceptance

`execution_outcome` records the generation result independently of later `ACCEPTED`/`REJECTED` workflow states. Broker finalization consumes that stable outcome. Successful generation settles its accounting callback before publishing an acceptable COMPLETED state, under the same in-process transition lock used by acceptance. Late accounting/logging failure cannot rewrite an accepted or uncertain manuscript operation as a failed generation.

The only new public working status is `SETTLING`. It applies while accounting is pending; initial author/broker receipts and polling use the public status. `PREPARED` remains an internal nonstarted state. A persisted SETTLING job restores as FAILED with `GENERATION_SETTLEMENT_RECOVERY_REQUIRED`, retains its draft and execution outcome, drops transient guards, and leaves its ledger hold unchanged for explicit reconciliation. It never resumes model execution automatically.

## Regression evidence

- `tests/test_r4_generation_origin_regression.py` preserves the supplied regression file unchanged: OFF/V1 legacy acceptance denial and the paused-COMPLETED logging/acceptance race, each across `/api` and `/api/v1`.
- `tests/test_r4_generation_origin_guards.py` adds legacy endpoint, older persisted receipt, SSE cutoff, safe cancellation, stripped recovery, caller-metadata rejection, ordinary V1 compatibility, SETTLING restart, and paused-settlement acceptance coverage.
- The focused File/non-PostgreSQL run also includes author-context, exact character Adapter serialization, lifecycle hooks, mounted broker/character APIs, ordinary jobs, restart, idempotency, variants, creation-workbench and R2 egress/dispatch-authority tests.
- Local real PostgreSQL is unavailable; parametrized PG cases are explicitly deselected for the hosted-CI lane. No real model, paid provider, credential operation, deployment or independent-review retry was performed.

## Selection-only authoring extension (A11/U05)

The same `create_author_preparer` accepts `revision_selection_validator`, normally the existing revision service's `selection(nid, scope, value)`. Strict `revision_selection` (`SelectionIn`) and `revision_selection_digest` must be supplied together, only for rewrite without character mode. The coordinator validates exact project/chapter/version/source and the current deterministic selection receipt, then stamps `partial_revision_only`, the normalized `revision_selection_binding`, and trusted selection-assistant origin requirements. Caller payloads cannot stamp these job fields.

The binding is included in the shared request digest, preserved on authorized job JSON, and revalidated at final Adapter dispatch. Existing operation/source behavior is unchanged, including selected whitespace. Generic `Job.accept` refuses a partial marker, binding, or trusted selection-assistant origin even while all flags are enabled. Only A11's reviewed original-document CAS application may adopt that output. `tests/test_r4_selection_author_binding.py` exercises exact production Adapter serialization over a synthetic wire, generic-accept refusal, source/receipt/flag/permission changes and successful original-CAS partial application with untouched paragraphs preserved.
