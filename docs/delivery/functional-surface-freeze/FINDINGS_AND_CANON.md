# Original Findings and Canon review lifecycle

Status: `CONTRACT_VERIFIED` for implemented deterministic/File behavior. PostgreSQL execution and real browser execution require the hosted suites. This is a functional addition inside existing Write/Review surfaces, not a new workspace, second Canon owner, model-quality claim, or formal freeze.

## Ownership and entry

- Existing `ContinuityCheckPanel` contains `FindingReviewPanel` and `PendingCanonReviewPanel`; navigation remains Feature Navigation → 制作与分析 → 一致性检查.
- Continuity rows remain in the original continuity findings repository; narrative and foreshadowing findings remain in the original narrative findings repository. Versionless legacy lists/actions exclude source-bound rows.
- Pending Canon and approved facts remain in the original Canon repositories. No mirror table, replacement Canon authority, migration 001–020 change, or Research-to-Canon promotion was introduced.
- `experimental.finding_review_v1` is a default-off runtime flag. Both `/api` and `/api/v1` mount the same production routers; V1 acceptance mode and disabled flags fail closed. Branch manuscript access also needs the existing `branch_manuscript_v1` admission.

## Findings contract

Prefix: `/api[/v1]/projects/{project_id}/{kind}`, where kind is `continuity` or `narrative`.

| Route | Permission | Result/action |
| --- | --- | --- |
| `GET /review-findings` | `domain.read` | Scoped current finding projections, history, stale and suppression states |
| `POST /review-checks` | `domain.write` | Deterministic check tied to chapter ID and expected source version |
| `GET /review-findings/{id}` | `domain.read` | Exact finding owner, scope and review version |
| `GET /review-findings/{id}/history` | `domain.read` | Retained actor/reason/action/source history |
| `GET /review-findings/{id}/evidence` | `domain.read` | Exact original current or historical manuscript snapshot, verified digest and navigation |
| `POST /review-findings/{id}/review` | `domain.review` | `resolve`, `intentional`, `reopen`, or `feedback` |

Check input: `chapter_id`, `expected_source_version`, optional `facts`. Empty facts in local mode read original stored continuity facts or narrative expectations/events/mysteries/goals. Collaboration branches require explicit facts and read the actual branch chapter owner; no mainline source/fact fallback exists. Facts and results are bounded. Failures do not masquerade as a successful empty check.

Review input requires `expected_version`, `source_digest`, `finding_fingerprint`, `operation_id`, nonblank `reason`, action and `confirmed: true`. Stable identity is scope + kind + chapter + original rule finding ID. Fingerprints bind rule/subject/description/evidence, while source digest binds chapter identity/version/digest plus facts digest. Source-bound receipts live alongside the original finding.

`OPEN`, `RESOLVED`, and `INTENTIONAL` are durable decisions. `REVIEW_REQUIRED` is an effective read state when a chapter, stored fact set, or source availability changes. Intentional suppression is active only for the exact captured source and fingerprint. Rechecking an unchanged source preserves a decision; rechecking changed evidence increments review version, retains history, and reopens the finding. Stale rows permit feedback/reopen, but cannot resolve or suppress new evidence. Reusing an operation ID with different content conflicts; replaying the identical accepted request is idempotent.

Exact evidence never opens the newest text while labelling it as an old version. History snapshots are verified against the captured digest. Missing/deleted/archived sources withhold evidence; finding/history rows stay readable as stale. Evidence IDs remain explicit; absent paragraph coordinates are labelled chapter-level evidence rather than invented precise spans.

File mutations share existing cross-process repository coordination. PostgreSQL mutation uses advisory serialization and row locks in the existing owner. A synchronous check interrupted before its commit leaves no review change; repeated checks recover persisted partial checks without duplicating findings. Review history is bounded at 100; an exhausted history rejects new mutations and remains readable. No background model job or resumable model execution is claimed.

## Original pending Canon contract

Prefix: `/api[/v1]/projects/{project_id}/pending-canon`.

| Route | Permission | Result/action |
| --- | --- | --- |
| `GET /review` | Project `domain.read` | Pending and terminal candidates, recovery and source state |
| `POST /{id}/preview` | Project `domain.read` | Candidate digest, exact current source snapshot, lineage and retained history |
| `POST /{id}/review` | Project `domain.review` | Explicit approve/reject with version, preview digest, reason and operation ID |
| `POST /{id}/recover` | Project `domain.review` | Reconcile an already committed File receipt without duplicating facts |
| `POST /{id}/cancel-recovery` | Project `domain.review` | Cancel a prepared File operation only before any facts committed |

Canon is project/mainline authority. A valid branch-only actor never obtains project Canon permission by sending a branch header. The Canon client sends a trusted session token and no branch-authority header. Every response reauthorizes after loading; mutations recheck before owner commit and after work. Source-bound finding reads do the equivalent within their captured branch scope.

A legacy candidate with no source identity is `NOT_CONFIGURED`; rejection is available, approval is not. The author explicitly selects a current chapter and sees its exact snapshot. Legacy candidates without recorded generation-time source versions state `LEGACY_SOURCE_VERSION_NOT_RECORDED`; current human review does not fabricate historical provenance. Approval is fenced by candidate digest and current chapter version/content digest. A terminal receipt retains its original reviewed source identity when the active editor navigates elsewhere.

`PENDING` → `APPROVED` or `REJECTED` is terminal. Versioned review protects the original legacy approve/reject methods from bypass. Independently, original legacy repeated approval/rejection is idempotent; an opposite terminal action or changed approved proposals rejects. Re-saving identical terminal proposals cannot reopen a row. Canon approval retains the stricter existing privacy behavior.

File promotion is an original-row prepared journal plus atomic Canon replacement. Additions carry deterministic receipt identities. Restart after facts commit reconciles the receipt even if the source later changed, was archived or deleted; it never repeats facts. The deleted source snapshot is withheld, history remains, and one unavailable source does not crash the inbox. A different authorized project reviewer can recover a committed receipt. Before facts commit, source/permission fences still apply; cancellation removes the journal, increments version and records history. Cancellation after facts committed conflicts and directs recovery. PostgreSQL facts + pending receipt use one transaction; interrupted transactions roll back, so File-only prepared recovery is explicitly unavailable there.

## UI states and protected behavior

- Loading: flag, list, preview and mutation states use existing status primitives and disable duplicate submissions.
- Empty: separate no-findings/no-Canon-candidates states; no fabricated model success.
- Error: sanitized messages and codes; explicit retry, with review reasons retained for conflicts.
- Unauthorized/disabled: 401/403/404 and scope/session remounts withhold cached proposals/evidence; late responses from an earlier identity do not render.
- Missing configuration: no chapter or explicit source/facts prevents approval/check completion, with actionable explanation.
- Conflict: no overwrite; refresh/re-preview and explicit reconfirmation. Changing Canon source ID invalidates the preview even before a request.
- Review: reason + human checkbox + exact CAS tokens; repeated clicks are synchronously deduplicated.
- Cancel/close: closing an unsubmitted decision does not write. Durable File recovery has a separate versioned cancellation action. Already committed facts cannot be cancelled by dismissing UI.
- Recovery/restart: original durable receipts/history are reloaded; decisions are never auto-resubmitted. Terminal candidates stay accessible for history.
- Navigation: existing project/chapter/branch shell, exact captured finding snapshot, and original project Canon candidate. No second top-level module.

Opus may improve arrangement, token-based typography, controls and accessible presentation within these existing surfaces. It must preserve owner identity, scope and permission checks, source/version/fingerprint fences, human review, terminal/idempotent behavior, explicit recovery, retained reasons/history, and honest model/runtime labels. PoemSeed Local Interop 1.0 is untouched.

## Verification and limits

- Focused File/mounted production tests cover `/api` and `/api/v1`, flag-off/V1 acceptance, permission and late revoke, CAS competition, stale stored facts, source archive/deletion, exact history, idempotence, File interruption recovery and original Canon terminal behavior.
- Real PostgreSQL versions of the same tests are marked `postgres_backend_only`; local execution is `NOT_RUN` because the dedicated database profile is unavailable. Existing profile skips were not broadened.
- React tests cover human confirmation, close/cancel, duplicate clicks, preserved conflict reasons, exact source, source-ID invalidation, missing configuration, recovery, revoke withholding and late scope responses. Client tests cover branch findings versus project-only Canon headers.
- `surface-freeze-findings-canon.spec.ts` uses real `app.main`, File storage and React. It checks persisted intentional decisions, stale CAS rejection, exact historical evidence, the original Canon empty surface and three desktop geometry/screenshots. It is included by the existing hosted surface configuration. Full populated Canon decisions/recovery are covered by mounted API and React tests, not a fabricated generation fixture.
- Browser collection succeeds. Local Chromium execution remains `NOT_RUN` after the previously verified socket denial; it was not retried. Screenshots/geometry require hosted execution.
- No provider, GPU, paid API, private manuscript, production transport, merge/release/deploy, or independent final audit was executed. Historical independent-review `BLOCKED` remains unchanged.
- Exact worktree verification receipts are summarized in `FINDINGS_AND_CANON_VERIFICATION.json`. They are not evidence for a later final Git SHA until rerun there.

## Unified Review Inbox read-through integration

`register_finding_review_bindings` mounts `continuity_finding`, `narrative_finding`, and `pending_canon` in the existing Unified Review Inbox. It creates no data store, executor, review journal or alternate approval owner. Each item retains the original record ID, review revision, source revision/digest, stale state and original authority scope. Canon includes a separate current-source revision when an older human-reviewed source has since changed. The containing Inbox scope does not turn project Canon into branch data: `authority_scope` and the target contract remain explicitly project/mainline.

All three domains are read-only in the generic Inbox: `allowed_actions=[]`, no batch actions, and generic approve/reject/reopen returns the original-flow requirement. The original panels still require full preview, reason, exact CAS/source tokens and human confirmation. A branch role cannot authorize project Canon; before/after guards repeat both the Inbox-context and original project-authority checks. The Inbox GET also reauthorizes after aggregating all bindings, and the frontend withholds cached rows on loading or read failure.

Legacy Canon projection is suppressed only while `finding_review_v1` is enabled and the replacement `pending_canon` binding is mounted. Turning the flag off, or not mounting the binding, preserves the historical projection. New domains disappear/fail closed when disabled. Original flags-OFF tests remain unchanged.

The returned target metadata includes the original panel/surface, record ID, review revision and source-navigation identity. It is explicitly `FORMAL_TARGET_ONLY`. The generic Inbox renders that metadata and explains the manual route to the original panel; it does not currently render an exact-open button for these records. Existing finding panels do render verified exact-source snapshot controls. Canon panels render current source evidence and historical receipt metadata; a changed historical reviewed source is not labelled as an available exact snapshot in the Inbox.

`tests/test_surface_findings_canon_inbox.py` exercises actual `app.main` aliases with real File/PostgreSQL-parametrized owners: projection identity, no duplicates, branch isolation, project-only Canon, stale/current source revisions, late feature disable, late role revoke, generic/batch action denial, and flags-OFF/missing-binding legacy compatibility. React tests cover new filters, honest navigation-contract presentation and cached-row withholding.
