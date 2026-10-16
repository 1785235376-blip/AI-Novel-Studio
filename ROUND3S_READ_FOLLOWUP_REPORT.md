# ROUND3S_READ_FOLLOWUP_REPORT — bounded read-contract follow-up (§3)

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform`
**Baseline SHA:** `f83cadbe8eb61ced886460a1c2e2fe5c36e4da21` (exact HEAD at start; no forward commits)
**`main` `fed2404c` untouched · PR #47 Draft · no release**

Directive: `DSH_AFTER_F83CADB_ROUND3_CONTINUATION.txt` §3. Four specific observations, each
**reproduced against the real module before being fixed**.

---

## 1. Reproduction

| Observation | Reproduction result at `f83cadb` |
| --- | --- |
| §3.1 decoder | `round3s-repro-r1` — **3 mismatches**: `b"OK\xff"` and `b"OK\xe4\xb8"` at full length → `COMPLETE "OK"` (required `UNDECODABLE`); `b"OK\xffX"` at limit 3 → `TRUNCATED "OK"`, the invalid `0xff` silently gone. Valid-boundary cases behaved correctly. |

The helper-only predictions in the directive were **accurate for all three failure cases** and for the
two control cases. Confirmed against the real module in an isolated runner, not from the text.

---

## 2. Fixes

### §3.1 — invalid UTF-8 reported as COMPLETE (real defect)

`_decode_chunk` tolerated **any** short trailing `UnicodeDecodeError`, whether or not the read was
actually truncated. It is now:

* `allow_partial_tail` is passed explicitly and is **only** true for a truncated read;
* the tolerance additionally requires `exc.reason == "unexpected end of data"` — a genuinely
  unfinished codepoint — so invalid start/continuation bytes are never treated as a boundary artefact.

New contract fields make the distinction explicit, as the directive requires:

| Field | Meaning |
| --- | --- |
| `decodable` | the returned `value` is valid UTF-8 |
| **`body_validated`** | the **whole original body** was decoded and validated (`COMPLETE` only) |
| **`tail_unverified`** | bytes exist that were neither returned nor validated |

A truncated read can therefore never promise that its unread tail is valid UTF-8, and the digest and
length still describe the **original bytes**.

Covered: zero / exact-limit / over-limit lengths, CJK, emoji cut at the boundary, invalid trailing
bytes, invalid interior bytes, whitespace and newline preservation. The original asset is never
rewritten to "repair" a body.

### §3.2 — library completeness not propagated per family

`project_prompt_library` computed outer `read_complete` but called `_entry_for` without it, so the
`read_complete=True` default survived **inside** each family entry. Completeness is now computed once
and passed to every entry, so an incomplete list cannot advertise an authoritative latest revision.
`scanned_assets` and `projected_families` are now separate, explicitly labelled quantities (plus the
existing `returned`) so a scanned count can never read as a family count or a total.

### §3.3 — deleted revisions never reached the detail projector

`_read_prompts` listed with `include_deleted=False` and filtered with `is_prompt_asset`, which also
rejects deleted rows — so the detail projector's `include_deleted=True` grouping was dead code.
`_read_prompts` gained an explicit `include_deleted` flag: the **library** still excludes deleted
rows, while **detail** accepts them as **metadata-only tombstones**. A deleted body is never read or
exposed (`fetch: TOMBSTONE`, `value: null`), and the revision is reported `available: false` with a
`REVISION_UNAVAILABLE` anomaly so `history_complete` becomes false rather than short.

### §3.4 — redaction of historical notes followed the head

`_entry_for` formatted **every** revision's change note/reason using the **head's** redacted flag, so
promoting an unmasked revision silently revealed a note an earlier revision had designated for
masking. Redaction is now resolved **per revision** in a dedicated `_version_row()` helper. Both
directions are asserted: masked-old under unmasked head stays masked, and cleartext-old under masked
head stays cleartext.

---

## 3. R3-R-08 decision (§4) — recorded, not silently relabelled

Kept as directed:

* the **authorised raw-asset download contract is unchanged**; an authorised user obtaining their own
  bytes is not treated as a defect;
* presentation masking is **not** called encryption, confidential sharing or permission enforcement,
  and no claim is made that "redacted means recipients cannot obtain the original";
* new Prompt drafts remain **private to the resolved author** — asserted again in this sub-phase;
* every list/detail/content/history path enforces the same project/branch/incarnation/actor
  boundary;
* commits, evidence and diagnostics contain **no user prompt text or credentials** (test bodies are
  synthetic).

**The residual cross-route security claim stays `PARTIAL`** until cross-route tests establish its
exact scope. No old redacted flag was changed and no permission was migrated. No new privacy promise
was invented, and the generic asset service was not rewritten for this presentation concern.

---

## 4. Verification

| Leg | Command | Result |
| --- | --- | --- |
| Reproduction | `round3s-repro-r1` (before fixes) | **3 mismatches**, kept as evidence |
| File backend | `round3s-read-followup-r1`: new follow-up suite + R3-R suite + Round 3 suite + bible + director + asset library | **154 passed, exit 0** |
| Real PostgreSQL | `round3s-read-followup-postgres`: fresh `v2_round3s`, 20 migrations, cluster stopped cleanly | **83 passed, exit 0** |
| New tests | `tests/test_round3s_read_followup.py` | 17 cases (§3.1 ×11, §3.2 ×3, §3.4 ×3), plus §3.3 rig cases included above |

---

## 5. Status

| Item | Status |
| --- | --- |
| §3.1 decoder defect | **IMPLEMENTED** — reproduced, fixed, verified |
| §3.2 per-family completeness | **IMPLEMENTED** |
| §3.3 deleted revisions in detail | **IMPLEMENTED** |
| §3.4 per-revision redaction | **IMPLEMENTED** |
| R3-R-08 cross-route security claim | **PARTIAL** (§3, unchanged by decision) |
| R3-W authoring | `NOT_RUN` — next sub-phase |
| R3-U / R3-I / R3-GATE / Round 4 | `NOT_RUN` |

**Files:** modified `app/creative/prompt_asset.py`, `app/creative/prompt_workspace.py`; added
`tests/test_round3s_read_followup.py`. No new store, no second asset/version/review system, no owner
rewrite. `prompts/**` untouched.
