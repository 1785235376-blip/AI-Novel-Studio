# ROUND3W_STATUS — dedicated Prompt authoring (R3-W)

**Status: `INCOMPLETE` — do not read this as a completed sub-phase.**

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform`
**Baseline SHA:** `bbb1d9e9c7b439d52f9c7d6ad55efcfcc187d89c` (exact HEAD at start)
**`main` `fed2404c` untouched · PR #47 Draft · no release**

> The directive requires `ROUND3W_AUTHORING_REPORT.md`, `ROUND3W_DECISIONS.md` and
> `ROUND3W_HANDOFF.md` **after the sub-phase completes** ("完成后独立：commit → push → 核对远端 →
> 生成…"). W6 is **not green**, so R3-W is not complete and those three documents are deliberately
> **not** produced. This status file records the real state instead.

---

## 1. What is implemented and verified

| Item | State |
| --- | --- |
| W1 call-site audit | **DONE** — see §3 |
| W2 strict request DTOs | **IMPLEMENTED** — `app/creative/prompt_authoring_models.py`, `extra="forbid"`, server-side facts absent |
| W2 routes | **IMPLEMENTED** — `POST /studio/prompts`, `POST /studio/prompts/{family_id}/revisions`, `POST …/revisions/{asset_id}/approve`; admission allow-list updated |
| W3 immutable revisions | **IMPLEMENTED** — a revision is a new asset; T02/T07 pass |
| W4 idempotency | **PARTIAL** — plain replay works (T04, T06b pass); **resume after a mid-write failure fails (T06)** |
| W4 concurrency | **IMPLEMENTED (conflict-detecting)** — stale-head refused (T03 status 409 correct, assertion pending); duplicate actives reported (T03b passes) |
| W5 privacy | **IMPLEMENTED** — drafts private to the resolved author (T08 passes); `SESSION_REQUIRED`/authority gates apply (T08b passes) |
| W6 Unicode | **IMPLEMENTED** — CJK/newline/emoji/byte-boundary (T09 passes) |

**Verified green:** 130 passed across the R3-W suite plus R3-S, R3-R, Round 3, bible and asset-library
regressions (`round3w-authoring-r7`). **With 3 R3-W tests failing.**

---

## 2. Open defects (the honest list)

| # | Defect | Evidence | Diagnosis |
| --- | --- | --- | --- |
| **D1** | The specific conflict reason never reaches the client. `PROMPT_REVISION_STALE` and `PROMPT_REQUEST_ID_REUSED` are replaced by an empty `current`. | T03, T05: body is `{"detail":{"code":"EXPERIMENTAL_VERSION_CONFLICT","current":{}}}` | The shared studio `invoke` wrapper normalises `CapabilityVersionConflict` and **drops `exc.current`**, so my payload (`exc.current` is set correctly — verified in `v1_capability_service.py`) is discarded on the way out. The service logic is right; the *transport* loses the reason. |
| **D2** | A retry after a mid-write failure (body created, payload not written) does not complete. | T06: retry raises instead of returning a receipt (`KeyError: 'asset_id'`) | The resume path exists and is entered (payload unreadable → `resume_asset`), but the retry still errors. Not yet isolated — the next concrete step is to capture the exact exception from the resume branch. |

Both are real integration defects, **not** test artefacts. Neither is fixed.

### Fixed during this sub-phase (real bugs found by the tests)

* **Replay content comparison was vacuous.** `content_digest(replay, body.text)` folded the
  *incoming* text into both sides, so any content compared equal and a reused `request_id` was
  silently accepted. The stored body bytes are now compared against the request body. This is why
  T05 originally returned `201` instead of `409`.
* **`include_deleted=True` on the owner's list** prevented the replay lookup from finding the
  just-created asset; the authoring path now uses the default listing.
* Replay detection now matches the owner's own recorded `idempotency_key` first, because that is the
  field the owner itself dedupes on.

---

## 3. W1 audit result — "the payload fits the allow-list" is not atomicity

Read from source, not assumed:

| Owner guarantee | Verified fact |
| --- | --- |
| `create(idempotency_key=…)` | **Native exactly-once.** A repeat returns the existing asset; the same key with **different content** raises `AssetIdempotencyConflict`; a deleted asset refuses the key rather than recreating it. |
| `update_metadata(expected_version=…)` | Compare-and-set, and a **no-op when the value is unchanged** — so replaying an identical payload does not bump a version. |
| Asset bytes | **Immutable** (written once in `create`), so a body revision *must* be a new asset and an old revision cannot be overwritten even by accident. |
| `owner_actor_id` | Keeps a new draft private to its author; reads require the actor. |
| `annotate_lineage` | Existing version-chain mechanism with a `history` that retains `asset_version`. |
| `promote_owned` | Existing review path; approval is never taken from client input. |

**Consequence for W4:** the owner supplies exactly-once for *create+payload*, but it does **not**
serialize "allocate the next revision of a family". R3-W therefore implements revision allocation as
**conflict-detecting, not lock-serialized**: the write path re-reads the family and the later racer
marks itself `CONFLICTED`; if both finish before either re-reads, two active revisions exist and the
read-side `DUPLICATE_REVISION` anomaly reports it. **No user content is discarded in either case** —
the loser keeps its asset, excluded from the chain and reported. This is documented in the module
docstring rather than presented as a lock.

---

## 4. Next concrete action (resume point)

1. **Fix D1 first** — it is a transport fix, not a service fix. In the studio `invoke` wrapper
   (`app/creative/workspace_api.py`), map `CapabilityVersionConflict` to a 409 that **preserves
   `exc.current`** instead of emptying it, then re-run T03/T05. Do not change the service to work
   around a lossy wrapper.
2. **Isolate D2** — run T06 and print the exception raised inside the resume branch, then complete
   the resume so a retry after a mid-write failure yields exactly one revision.
3. Then finish W6 on File **and** real PostgreSQL, commit/push R3-W alone, and only then produce
   `ROUND3W_AUTHORING_REPORT.md`, `ROUND3W_DECISIONS.md`, `ROUND3W_HANDOFF.md`.
4. R3-U → R3-I → R3-GATE → Round 4 remain `NOT_RUN`.

**Files added this sub-phase:** `app/creative/prompt_authoring_models.py`,
`app/creative/prompt_authoring.py`, `app/creative/prompt_authoring_api.py`,
`tests/test_round3w_authoring.py`.
**Modified:** `app/creative/prompt_asset.py` (request id/state in the payload contract, `CONTENT_KEYS`,
`conflicted` reporting), `app/creative/workspace_api.py` (admission + service wiring),
`app/experimental/api.py` (service construction), `tests/test_round3_prompt.py` (one admission
assertion updated because POST prompts is now deliberately admitted — recorded, not silent).

**No second asset/version/review/task system or database was created.** `AssetLibraryService` was
not modified. `prompts/**` untouched.

---

## 5. Stop reason

**Session/tool budget exhausted.** Not a product blocker, not a claim of background execution, and
**R3-W is not complete**. The work is committed as a durable checkpoint with the defects above named
explicitly rather than hidden.
