# ROUND3W_AUTHORING_REPORT — dedicated Prompt authoring (R3-W)

**Status: `COMPLETE` for the write layer. R3-U / R3-I / R3-GATE / Round 4 remain `NOT_RUN`.**

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform`
**Baseline SHA:** `ac833e371cfe905218da1d1262f089726d8d9c73`
**`main` `fed2404c` untouched · PR #47 Draft · no release**

---

## 1. What now works

A user can create a Prompt, save it, edit it, save a new revision, view history, and reopen it —
through a dedicated, permission-bound write surface that reuses the existing asset owner.

| Capability | State |
| --- | --- |
| Create revision 1 | **IMPLEMENTED** (`POST /studio/prompts`) |
| Save the next revision | **IMPLEMENTED** (`POST /studio/prompts/{family_id}/revisions`) |
| Review a revision | **IMPLEMENTED** (reuses `promote_owned`) |
| Strict request DTOs | **IMPLEMENTED** — `extra="forbid"`; server-side facts absent from the schema |
| Exactly-once by `request_id` | **IMPLEMENTED** — replay returns the same revision; reuse with different content is refused |
| Interrupted-write resume | **IMPLEMENTED** — resumed only when the stored bytes still match the request |
| Concurrent next-revision | **IMPLEMENTED (conflict-detecting)** — see §3 |
| Immutability of a finished revision | **IMPLEMENTED** — prompt-scoped guard; other asset kinds unchanged |
| Private-by-default drafts | **IMPLEMENTED** — new drafts are private to the resolved author |
| Unicode fidelity | **IMPLEMENTED** — CJK / newline / emoji / byte boundary |

## 2. Verification

| Leg | Command | Result |
| --- | --- | --- |
| File backend | `round3w-authoring-r10`: R3-W authoring + concurrency + Round 3 + R3-S + R3-R + bible + asset library + creative workflows | **202 passed, 60 skipped, exit 0** |
| Real PostgreSQL | `round3w-authoring-postgres`: fresh `v2_round3w`, 20 migrations, disposable loopback cluster stopped cleanly | **79 passed, exit 0** |
| New tests | `tests/test_round3w_authoring.py` (16) · `tests/test_round3w_concurrency.py` (8) | 24 cases |

Covered: normal create + read-back, second revision, stale-editor refusal, **real two-thread
concurrency**, repeated request id, reused request id with different content, the same text with
different parameters, interrupted create with different text (refused), interrupted create with
identical text (resumed exactly once), old-revision immutability, self-approval blocked, review path
still works, non-prompt asset kinds unaffected, private-draft isolation, authority required, and
Unicode boundaries.

## 3. The two named defects, and how they resolved

**D1 — the conflict reason was silently emptied.** The shared studio invoker deliberately reduces
`CapabilityVersionConflict.current` to `{version, status}` so a conflict cannot smuggle internal
snapshots. That is a safety property for **every** existing API and was left untouched. A prompt
conflict now travels as `PromptAuthoringConflict`, rendered by the prompt routes from a strict
whitelist (`code`, `family_id`, `revision`, `expected_revision`, `current_revision`, `retryable`).
Asserted: the response carries no user text, no owner markers, no bindings, no other family's ids.
**Fixed.**

**D2 — was a test-contract error, confirmed.** The retry returned `201` all along; the failing line
was `library["entries"][0]["asset_id"]`. The Library entry field is **`head_asset_id`**; `asset_id`
belongs to the write receipt. The assertion was corrected to `head_asset_id` **and kept** — the
invariant it protects (the retry resolves to the revision the interrupted attempt had produced) is
unchanged. Recorded as a corrected assumption, not a weakened assertion. **No product change was
needed or made.**

## 4. Defects the new tests found and fixed

* **Request identity could be spent by one body and completed by another.** The resume path reused
  the existing asset's bytes while writing the new request's metadata — exactly the forbidden
  "old body ↔ new metadata" binding. Resume now requires the stored bytes to match the request.
* **Self-approval through the generic metadata path.** `approved_at` is in the owner's general
  allow-list, so an ordinary metadata write could approve a prompt revision without review. A
  `kind == "prompt"` guard now refuses changes to approval/provenance identity; the review path
  (`promote_owned`) does not use that method, so review still works, and other asset kinds are
  untouched.
* **A vacuous replay comparison** (earlier in this sub-phase): the request's own text was folded into
  both sides, so any content compared equal and a reused `request_id` was accepted.

## 5. Lock boundary — the earlier conclusion was checked, and stands

The directive asked me to re-verify that revision allocation is not serialized. Reading the chain
`_write → _asset_scope → project_scope → workspace_mutation("asset-library")` shows
`workspace_mutation` is acquired **inside each `AssetLibraryService` method**, and `project_scope` is
a scope adapter. A structural test asserts exactly that: the lock is present in `create` /
`update_metadata` and **absent** from `PromptAuthoringService._write`. So each owner operation is
atomic and cross-process safe, but the read-allocate-write sequence is not one critical section.
R3-W therefore implements a deterministic conflict rule and relies on the read-side
`DUPLICATE_REVISION` anomaly as the backstop. **No new lock was added**, per the directive's
"reuse the existing lock" instruction.

A real two-thread test asserts at most one racer is accepted for the same next revision, that a
losing racer is told why, and that **no user content is silently deleted**.

## 6. Honest limits

| Item | Status |
| --- | --- |
| Cross-*process* concurrency test | `NOT_RUN` — two-thread (in-process) and the structural lock analysis were done; a two-process run needs a second interpreter harness |
| `previous_asset_id` as full Asset Lineage | **Deliberately not claimed.** It is a reference in the prompt payload; the projection names it `previous_asset_id` and exposes no `lineage` record. Promoting it to a true lineage edge is Round 4 work |
| Reference/character/scene binding validity | Rendered as `KNOWN`/`UNKNOWN` by the read layer; **write-time validation of binding targets is `NOT_RUN`** |
| Browser acceptance | `NOT_RUN` |
| R3-U Prompt Workspace | `NOT_RUN` — next |

## 7. Files

**Added:** `app/creative/prompt_authoring_models.py`, `app/creative/prompt_authoring.py`,
`app/creative/prompt_authoring_api.py`, `tests/test_round3w_authoring.py`,
`tests/test_round3w_concurrency.py`.
**Modified:** `app/creative/prompt_asset.py` (request id/state in the payload contract,
`CONTENT_KEYS`, per-revision conflict reporting), `app/creative/workspace_api.py` (admission +
wiring), `app/experimental/api.py` (service construction),
**`app/services/asset_library_service.py`** (one prompt-scoped immutability guard — the only owner
change, minimal and tested), `tests/test_round3_prompt.py` (one admission assertion updated because
POST prompts is now deliberately admitted).

No second asset/version/review/task system or database was created. `prompts/**` untouched.
