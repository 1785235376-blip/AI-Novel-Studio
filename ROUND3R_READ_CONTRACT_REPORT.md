# ROUND3R_READ_CONTRACT_REPORT — read-truthfulness, context contract and boundary fixes

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform`
**Baseline:** `1bce019f492a7e23b06f221f17ed49cf07d7f475` (exact match to the task book; no forward commits)
**`main` `fed2404c` untouched · PR #47 Draft · no release**

Task book: `DSH_ROUND3_COMPLETION_AND_ROUND4_CONTINUATION.txt` §3.
Sub-phase: **R3-R** (first of R3-R → R3-W → R3-U → R3-I → R3-GATE → R4).

> **Method:** every issue was **reproduced before it was fixed**. The task book's static
> findings were treated as hypotheses, not as passing evidence.

---

## 1. Reproduction (failing evidence first)

`tests/test_round3r_prompt_read_contract.py` was written against the **correct** contract and
run against the untouched baseline:

```
round3r-repro-r1  →  26 failed, 3 passed   (receipt: round3r-repro-r1.json, status FAIL)
```

All eight R3-R issues were confirmed present. **Every static finding in the task book was
accurate**; none was a false positive. The three passing cases were ones whose contract already
held (the declared limit constant, an absent-dimension passthrough, and error non-echo).

---

## 2. Fixes

| Item | Fix | Where |
| --- | --- | --- |
| **R3-R-01** read limit / 200th item | The body is now read for **every returned row before the cap is applied**; the previous order (`append` → `break` → read) silently stripped the boundary item's text. Truncation is now explicit: `returned`, `limit`, `truncated`, `has_more`, `total_known` (never invented). Detail uses its own larger scan bound (`MAX_PROMPT_SCAN`) so a family beyond the library page is no longer a spurious 404. The bound is resolved **at call time**, so it is live policy rather than a frozen default. | `prompt_workspace.py`, `prompt_asset.py` |
| **R3-R-02** `history_complete` | No longer a constant. It is `read_complete AND no blocking anomaly`. Anomalies are computed, not smoothed: `DUPLICATE_REVISION`, `BROKEN_PREDECESSOR`, `CROSS_FAMILY_LINK`, `REVISION_UNAVAILABLE`, `REVISION_GAP`. Detail groups with `include_deleted=True` so a deleted revision is reported as unavailable rather than vanishing into a shorter "complete" history. A family's revisions are never re-sorted into a fake linear chain. | `prompt_asset.py` |
| **R3-R-03** truncation & UTF-8 | New `read_prompt_body()` returns `state ∈ {COMPLETE, TRUNCATED, UNDECODABLE}`, the exact text or a **valid-UTF-8** preview, `original_length`, and a digest that **always describes the original bytes** (`digest_of: ORIGINAL_BYTES`). `errors='replace'` is gone. A cut mid-multibyte-character drops the partial bytes; genuinely invalid bytes are reported, not silently substituted. A preview's hash can never be presented as the asset hash. | `prompt_asset.py` |
| **R3-R-04** shot-context structure | `project_shot_cards()` returns top-level fields, but the context reader looked for `card['dimensions']` — so **every real shot produced an empty context**. Added `shot_card_dimensions()` which adapts the real producer output (lighting/action/emotion/lens/movement/composition/character/audio/duration/shot_size). Every adapted dimension is `PER_SHOT_MEASURED`; the director's own `kind` is passed through unchanged, so a measured aggregate is never relabelled as a document decision. Document and shot identity are carried. | `prompt_asset.py` |
| **R3-R-05** shot index | Was derived from character Bible `used_in`, so an empty establishing shot or a cast-less shot did not exist and two documents' shot number 1 could collide. Now `shot_index()` is built from the real shot/document owner, keyed `document_id:number` (`scope_aware: True`), and includes shots with no cast. | `prompt_asset.py`, `prompt_workspace.py` |
| **R3-R-06** actor passthrough | All three GET handlers now pass the **actor the authorisation path resolved** into the service, which passes it to the owner's `list`/`content`. The owner's private-owner filtering therefore applies **to the author too** rather than being bypassed. The actor is never taken from the client and never defaulted permissively. | `prompt_api.py`, `prompt_workspace.py` |
| **R3-R-07** strict payload | `validate_payload()` replaces the partial check: exact key set (unknown keys refused), exact `bool` (`'false'` is not `False`), exact business `int` (`True` is not a revision), enum membership, per-field length bounds, id-list shape, `seed` type, `previous_asset_id`/`adopted_from` shape. `revision_count`/`prompt_count` count **valid** families only and `malformed_count` is separate, so the two can never disagree; detail applies the same validity gate as the list. | `prompt_asset.py` |
| **R3-R-08** redaction | Redaction now covers the body **and** change note/reason, and grants **no** permission (asserted: a redacted private draft stays invisible to another author). Error paths and the projection are asserted not to echo prompt text. See §4 for the honest limits of this item. | `prompt_asset.py` |

---

## 3. Verification (this sub-phase, source-bound)

| Leg | Command | Result |
| --- | --- | --- |
| **Reproduction** | `round3r-repro-r1` (baseline, before fixes) | **26 failed / 3 passed** — kept as evidence |
| **File backend** | `round3r-read-contract-r2`: R3-R suite + Round 3 suite + bible + director + asset library + creative workflows | **197 passed, 60 skipped, exit 0** |
| **Real PostgreSQL** | `round3r-read-contract-postgres`: fresh `v2_round3r`, 20 migrations, disposable loopback cluster stopped cleanly | **100 passed, exit 0** |
| Regression | Round 3's own suite still passes; two assertions were **updated** (see §5) | included above |

---

## 4. Honest limits of this sub-phase

* **R3-R-08 is a partial fix.** The prompt projection and its error paths no longer leak body
  text, change notes or reasons. The **generic asset download route
  (`GET /studio/assets/{aid}/download`) still returns the raw bytes** to any caller the *asset
  owner* admits — by design of that owner, not a prompt-library leak. The correct treatment is a
  decision: either the download route consults a prompt-level intent, or redaction is documented as
  a projection-level presentation choice only. **Recorded, not silently fixed**, because changing
  the asset owner's long-standing read contract is out of this sub-phase's scope.
* Two distinct situations are recorded separately, as the task book requires:
  **(a) has permission but should be redacted** — the library projection case, fixed;
  **(b) has no permission** — the private-owner case, asserted.
* **`prompts/**` (system.md) is untouched and still excluded**, as required.
* No legacy prompt source was migrated, rewritten or deleted.

---

## 5. Contract refinements that changed two assertions

`validate_payload` now returns a **specific** reason instead of one generic code. Two Round 3
assertions were therefore updated:

| Test | Was | Now |
| --- | --- | --- |
| `test_a_prompt_asset_with_an_unreadable_payload_is_reported_not_guessed` | `PROMPT_PAYLOAD_UNREADABLE` | `PROMPT_PAYLOAD_CONTRACT_INVALID` |
| `test_a_payload_missing_its_required_family_id_is_reported_not_silently_accepted` | `PROMPT_PAYLOAD_UNREADABLE` | `PROMPT_PAYLOAD_FIELD_MISSING` |

This is a **strengthening, not a weakening**: the refusal is unchanged and the reason is now more
precise. Recorded here rather than changed silently.

The validator also checks `contract` before the key set, so an artefact that is not a prompt
payload at all reports the most actionable reason.

---

## 6. Status

| Item | Status |
| --- | --- |
| R3-R-01 … R3-R-07 | **IMPLEMENTED**, reproduced then fixed, verified on File + real PostgreSQL |
| R3-R-08 redaction | **PARTIAL** — projection/errors fixed; the owner's generic download route is a recorded decision (§4) |
| R3-W dedicated authoring entry | `NOT_RUN` — next sub-phase |
| R3-U Prompt Workspace | `NOT_RUN` |
| R3-I production application | `NOT_RUN` |
| R3-GATE | `NOT_RUN` |
| R4 asset relationship view | `NOT_RUN` |
| Release candidate | **`NOT ESTABLISHED`** (unchanged) |
| `CONTENT_POLICY_FRAMEWORK` | **`RESERVED`** (unchanged) |

**Preserved:** `main` untouched, PR #47 Draft, V1 frozen, QingJian not linked, user's Strata
(pid 15392 on 8080) never started or stopped, protected workspace untouched, no model download, no
paid API, no final Windows/GPU acceptance.

---

## 7. Files

**Modified (3)** `app/creative/prompt_asset.py` · `app/creative/prompt_workspace.py` ·
`app/creative/prompt_api.py`
**Added — tests (1)** `tests/test_round3r_prompt_read_contract.py`
**Modified — tests (1)** `tests/test_round3_prompt.py` (two reasons refined, §5)
**Added — docs (1)** `ROUND3R_READ_CONTRACT_REPORT.md` (+ `CURRENT_EXECUTION_STATE.md`)
**Evidence** `docs/delivery/v2-development/round3r-{repro-r1, read-contract-r1, read-contract-r2,
read-contract-postgres, actor-probe}.json|.log`
