# A11 / U05 / U04 paragraph-lock checkpoint

Status: IMPLEMENTED / INTEGRATED for the bounded deterministic review path;
CONTRACT_VERIFIED with actual File persistence. PostgreSQL and browser cases are
authored, NOT_RUN in this executor. REAL_MODEL_VERIFIED and USER_ACCEPTED: NOT_RUN.
This is a scoped Experimental increment, not full A11 semantic-impact completion.

## Reused authorities and entry

- Original TipTap editor and its real ProseMirror selection; one editor remains.
- Original ChapterService, File/PostgreSQL chapter repositories and audited
  collaboration write port remain the only current document/history authority.
- Existing AuthorRequestPreviewPanel and AuthorPreparer generate the exact
  previewed Adapter request. No second executor, model router or prompt preview.
- Original immutable history and restore semantics remain. Accepted revisions
  create a new current chapter version; old history is not edited.
- Existing ExperimentalStore journals proposals, decisions, goals and milestone
  references only. It is not a second chapter/version repository.
- Experimental tab: “选区修订与保护”. The original editor inspector adds
  “修订选区与逐段接受”. Existing navigation and saved-state fencing are retained.

Runtime flags: revision_intelligence_v2; U05 generation additionally requires
selection_assistant_v2 and author_context_inspector_v2. Exact server allowlists
and V1_ACCEPTANCE_MODE apply. Pure enforcement of constraints already stored in
an original chapter remains active after feature OFF/V1; disabling a UI never
silently unlocks that chapter.

## Actual bounded user journey

1. Save the original chapter. Select text in TipTap, or choose a saved paragraph.
2. Verify the exact saved version and selection. Enter one candidate per selected
   text block, or explicitly choose polish/compress/expand/dialogue through the
   currently selected Provider/model and inspect the actual original request.
3. Authorize one generation only after that request preview. Read the original
   job status. Model output stays a draft; extra/ambiguous paragraph output cannot
   be automatically mapped back. A manually selected excerpt is clearly labeled
   manual/imported, not passed off as verified AI output.
4. Save candidate differences; choose accept/reject independently for each block.
   No choice means keep the candidate pending. Preview the entire chosen batch
   and original history checkpoint, then explicitly confirm the decisions.
5. Only approved inline spans change. Unapproved block JSON, marks, list nesting,
   headings and other original document structure remain intact. Mixed selected
   marks with no unambiguous plain-text replacement mapping are rejected.
6. Remaining untouched candidates can be explicitly re-reviewed in a new draft
   only against the exact result of this service's own previous partial accept.
   External edits, drift, changed privacy or ambiguous relocation reject that
   action; there is no fuzzy rebase and no last-write-wins fallback.
7. A milestone names the original chapter version and goal without copying its
   document. The original history remains the route for inspecting/restoring it.

## Source and Unicode contract

SelectionIn is strict, extra fields forbidden, and does not trim or normalize
text. ProseMirror node positions count UTF-16, including structure tokens. The
service maps them to exact Python codepoints inside supported text blocks,
verifies the exact quote and records the original document digest plus path,
block digest, local offsets and stable anchor digest. Duplicate text does not
select the first occurrence. Emoji surrogate splits, decomposed combining
characters, ZWJ sequences, variation/skin-tone/tag sequences, flag-emoji halves,
CRLF halves and uncertain Hangul/combining boundaries are conservatively rejected.
No unsupported selection is silently rounded or relocated.

HardBreak/newline mapping and leading/trailing whitespace are preserved. Up to
50 selected blocks and 100,000 chapter/candidate characters are supported.
Character diffs are calculable; long differences use an explicitly labeled
bounded whole-block replacement display instead of unbounded quadratic diff.

Semantic explanations are separately labeled author notes or imported model
assessments and require exact before/after quote evidence for a changed block.
They are not calculated truth or exhaustive world/relationship/motivation impact.
There is no standalone semantic-explanation model Adapter or A04 graph-impact
join in this checkpoint; imported explanation entry is API-only.

## AI paragraph locks

The original document stores aiRevisionLock attributes, including lock ID,
original node digest, source version and explicit unlock tombstones. Lock/unlock
is itself an original version-aware checkpoint. The small always-on persistence
helper has no model, network, experimental storage or configuration IO.

- File ChapterRepository.save validates inside the existing project/version lock.
- PostgreSQL ChapterRepository.save validates alongside original CAS.
- PostgresAtomicChapterAuditPort validates in its original transaction.
- FileAtomicChapterAuditPort delegates to the already guarded File repository.

AI_ACCEPT cannot alter, delete, move or remove the marker from a locked block.
Unknown or drifted locks fail closed. Ordinary manual edits preserve active lock
intent even when a legacy Markdown save omitted its attrs; a text/mark edit makes
the old lock visibly stale rather than unlocked. A structural change may require
explicit unlock first. Empty or corrupt locked paragraphs can be explicitly
unlocked by current chapter version, document digest and exact block path.

The TipTap extension preserves real markers/tombstones. A normalization helper
removes only default null-lock attributes from external editor JSON so ordinary
unlocked documents retain the original saved shape and controlled-edit behavior.
These are application authoring constraints, not OS/filesystem protection or a
security boundary against an authorized author making manual changes.

## Authorization, privacy and failure recovery

Every source/read/write uses existing project/actor permissions, current flags,
source version, rich-document digest and source privacy. Current branch-isolated
manuscript storage is not available, so distinct collaboration branch sources
are honestly unavailable. No main-branch manuscript is projected as another
branch. Reader-role access to these author surfaces is denied.

U05 jobs receive server-only partial_revision_only and exact selection binding
through the original shared preparer. The request receipt binds that selection;
final send revalidates it and current origin flags. Generic legacy acceptance
rejects these jobs with REVISION_REVIEW_REQUIRED. Only the reviewed A11 original-
CAS path can adopt them. Imported generated candidates require exact trusted job
binding and revalidate original job access/origin before reading, previewing and
applying. Revoked generated entries do not break unrelated manual draft listing.

A durable ACCEPTING claim precedes the original chapter side effect. Cross-store
journal/chapter atomicity is not claimed. Process interruption or ambiguous
failure leaves ACCEPTANCE_UNCERTAIN and cannot automatically replay. Check
original current chapter/history; do not repeat acceptance blindly. Competing
proposals can produce only one original chapter CAS winner.

Flag-off recovery for an already locked chapter: re-enable the authorized
revision feature to inspect and explicitly unlock. Ordinary supported manual
editing remains possible, but deleting lock metadata is not an implicit unlock.
Original JSON/history can preserve attrs; plain text/Markdown exports cannot
round-trip application lock metadata. Older builds do not implement these
constraints. Use isolated data/export-import rollback; never open Experimental
written data in frozen PR37 as if it supported this contract.

## Verification and limits

Focused tests:
- tests/test_r4_revision_intelligence.py: real File and parameterized real PG;
  precise Unicode/whitespace, duplicate anchors, marks/hardBreak/nesting,
  two-block adoption, reject/review, stale/privacy/branch guards, locks under
  OFF/V1, corrupt/empty-lock recovery, original history, competing CAS writers,
  replay prevention, generated-origin and evidence constraints.
- tests/test_r4_revision_intelligence_mounted.py: production /api and /api/v1
  routes, original File/PG repositories, real trusted role stack, legacy lock
  enforcement, fail-closed branch-source boundary.
- RevisionIntelligencePanel.test.tsx and revisionLocks.test.ts: mounted React,
  exact selection/request/approval payloads, conflict recovery, navigation,
  unavailable direct-entry state, output scope rejection and original TipTap
  JSON marker retention.
- frontend/tests/e2e/r4-revision-intelligence.spec.ts: authored real File + React
  J03 stale patch → reselect → accept first/third blocks → preserve bold middle
  block and history. No response mocks and no model request.

Actual local receipts for this checkpoint are reported in the commit handoff,
not cumulative historical counts. Required test markers separate PG from File;
a skip/deselection is not a PostgreSQL pass. No local PostgreSQL was started and
no Chromium retry was made after the known EPERM restriction. No paid API,
credential, user manuscript, model download or user-runtime modification was
used. Independent review remains platform-blocked and was not rerouted.

Remaining boundaries: branch-isolated chapter authority; cross-chapter batches;
automatic graph-linked semantic impact; dedicated explanation Adapter; real
model/GPU quality; actual PostgreSQL, browser geometry/screenshots and native
IME/Windows/user acceptance. Current UI reuses DS-v1.0 primitives and tokens,
adds no parallel shell or cosmetic lock-as-protection styling.

### Executed focused receipts (2026-10-05)

- Isolated harness pytest on test_r4_revision_intelligence.py and
  test_r4_revision_intelligence_mounted.py with `-m 'not postgres_backend_only'`:
  37 passed; 32 PostgreSQL parameter cases deselected, not passed.
- Original revision-context, branch-revision and writing-focus regression files
  with the same File-only marker: 27 passed; 15 PostgreSQL cases deselected.
- Pinned frontend `tsc -b`: passed after correcting a test-mock tuple type.
- RevisionIntelligencePanel, revisionLocks, Editor.anchor and Editor.recovery:
  14 tests passed across four files. UI token guard: passed.
- Shared trusted generation-selection seam was delivered separately in commit
  e2551c6. Its owner's actual test receipt covers real local Adapter serialization
  over a synthetic wire, generic-accept refusal, final-send revocation and the
  same reviewed original-CAS adoption. This is Adapter/protocol evidence, not
  real-model quality or independent review.

The initial focused run exposed the not-yet-registered feature flag; the initial
mounted test expected an old error-envelope shape and was corrected to assert
the actual centralized error code. Those intermediate failures are not claimed
as successful runs. No safety assertion was removed.
