# ROUND3U_STATUS — Prompt Workspace (R3-U)

**Status: `PARTIAL`. The data/contract layer is implemented and verified; the React UI and
browser acceptance are `NOT_RUN`.**

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform`
**Baseline SHA:** `08dc0f2b96d6ac564c9ad62e465732cf55dd8ac9`
**`main` `fed2404c` untouched · PR #47 Draft · no release**

> The directive requires `ROUND3U_PROMPT_WORKSPACE_REPORT.md`, `ROUND3U_DECISIONS.md` and
> `ROUND3U_HANDOFF.md` **after R3-U completes**. It has not, so those are deliberately not
> produced. This file records the real state. Per the directive, a session/tool limit is a
> valid stop reason and must not be reported as background progress.

---

## 1. Implemented and verified

| File | Purpose | Verified |
| --- | --- | --- |
| `frontend/src/prompt/promptTypes.ts` | Contract constants, bounds, error codes, types | tsc |
| `frontend/src/prompt/promptContract.ts` | Strict decoders (unknown keys rejected) | 12 vitest cases |
| `frontend/src/prompt/promptClient.ts` | Read + author client over `StudioGraphTransport`; whitelist-only 409 decoding | tsc + cases |
| `frontend/src/prompt/promptDraft.ts` | Draft state machine + content-free reload marker | 12 vitest cases |
| `frontend/src/prompt/promptContract.test.ts`, `promptDraft.test.ts` | 24 cases | **24 passed** |

`npx tsc --noEmit` → **exit 0**. `vitest run src/prompt` → **24 passed**.

## 2. What the verified layer actually guarantees

* **The four states are distinct** — `DIRTY` (unsaved local), `SUBMITTING` (request in flight),
  `SAVED` (server receipt), `UNKNOWN` (timeout/offline/lost response), plus `CONFLICT`.
* **An unknown outcome never auto-retries.** `retryUnknown` requires an explicit user action and
  **reuses the same `request_id`**, which is the only safe option: R3-W's server-side exactly-once
  then recognises it as the same request. Minting a new id would genuinely create a second revision.
* **A 409 never loses the draft.** `markConflict` preserves the content and keeps the conflict code.
  Only `discardDraft`, an explicit user action, clears local content.
* **Typing while the outcome is unknown cannot mutate the pending submission** (asserted).
* **The whitelist conflict codes are the only ones treated as prompt conflicts** — a non-prompt 409
  (`{code, version}`) decodes to `null`, so other Studio/Graph semantics are unchanged.
* **`UNKNOWN` stays `UNKNOWN`.** A field that is not authored must carry `UNKNOWN`, never `''`;
  `COMPLETE` must carry the body, `TRUNCATED` a valid preview, and
  `REDACTED`/`UNDECODABLE`/`DELETED`/`UNAVAILABLE` must carry **no** text. Coercing a preview or a
  redaction into "normal complete content" fails the decode.
* **Counts and lists must agree** (`prompt_count === entries.length`), so a count can never
  contradict the list beside it.

## 3. Why prompt text is *not* persisted locally — and what that means on reload

The repo's existing resume store (`frontend/src/creative/studioWorkspaceResume.ts`) states in its own
docstring: *"No drafts, prompts, outputs, tokens, credentials or execution receipts are stored."*

R3-U therefore **does not write prompt cleartext to `localStorage`** and does not claim that doing so
would be safe. Instead it persists a **bounded, schema-versioned, content-free marker** (project,
family, base revision, request id — capped at 2048 bytes, unknown keys rejected) using the same
discipline as the existing resume record.

Consequence, stated plainly: **a full page reload cannot restore the text.** The marker exists so the
loss is *not silent* — `markerNotice()` tells the user a draft existed and that its content cannot be
recovered. In-app navigation, transient network failure, timeouts and 409 conflicts **do** preserve
the draft, because the draft lives in the client store for the session.

Tampering is rejected: a marker with a wrong `mode`, a foreign `project_id`, or an extra `text` key
decodes to `INVALID`, and unreadable storage reports `UNAVAILABLE` rather than "no draft".

## 4. `NOT_RUN` — the remaining R3-U work

1. **React UI**: `PromptWorkspace.tsx` — Library (search, filter by purpose/model, draft vs approved,
   reference view, error states), Editor (all fields, save only on explicit confirmation), Version
   Comparison (body / negative prompt / parameters / references / model), human vs professional mode
   in the existing AppShell, and conflict banners wired to the draft machine.
2. **Module CSS** following `docs/ui/design_system.md` tokens — and self-verified, because
   `scripts/check_ui_design_tokens.mjs` only walks `frontend/src/ui` and would not cover a new
   `src/prompt` directory.
3. **Component tests** (jsdom) — and **real browser acceptance**, which jsdom results must not be
   presented as.
4. **Human/professional mode**: the existing `StudioInterfaceMode` (`NOVICE`/`PROFESSIONAL`) should be
   reused rather than a second mode concept invented.

## 5. Defects the tests found and fixed in this layer

* A non-`COMPLETE` body was rejected even when it was a legitimate `TRUNCATED` preview — I had
  conflated `TRUNCATED` with `REDACTED`/`UNDECODABLE`, which would have discarded real preview text.
* Two `closed()` calls passed forward-compatible optional keys as **required**, so a valid projection
  missing an optional field failed to decode.
* `promptBody` read the value before checking the state, so every `null`-valued state threw.
* The problem payload field is `details`, not `detail` (found by `tsc`).

## 6. Stop reason

**Session/tool budget exhausted.** No background work is running. R3-U is **not** complete;
R3-I, R3-GATE and Round 4 are `NOT_RUN`.
