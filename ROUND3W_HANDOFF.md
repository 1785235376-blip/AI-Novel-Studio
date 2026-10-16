# ROUND3W_HANDOFF — R3-W → R3-U

**R3-W is complete and verified. Next: R3-U (operable Prompt Workspace).**

## Frozen write contract (do not re-litigate)

| Route | Purpose |
| --- | --- |
| `POST /api/projects/{nid}/studio/prompts` | Create revision 1 → `201` + receipt |
| `POST /api/projects/{nid}/studio/prompts/{family_id}/revisions` | Save the next revision → `201` + receipt |
| `POST /api/projects/{nid}/studio/prompts/{family_id}/revisions/{asset_id}/approve?expected_version=N` | Review (reuses `promote_owned`) |
| `GET …/studio/prompts`, `GET …/studio/prompts/{family_id}`, `GET …/studio/prompts/context` | Read-only; unchanged |

**Receipt:** `family_id, asset_id, revision, asset_version, text_digest, idempotent_replay,
previous_asset_id, payload_digest`.
**Library entry head field:** `head_asset_id` (**not** `asset_id` — that is the receipt's field).

**Conflict body (409), strictly whitelisted:**
`{"code", "family_id", "revision", "expected_revision", "current_revision", "retryable"}`.
Codes: `PROMPT_REVISION_STALE`, `PROMPT_REQUEST_ID_REUSED`, `PROMPT_REVISION_CONFLICT`,
`PROMPT_ASSET_VERSION_CONFLICT`. Never contains user text, prompts, owner markers, bindings or
credentials. Other Studio/production/Graph APIs keep their existing `{version, status}` semantics.

## What R3-U must build

An **operable** Prompt Workspace — not a read-only detail page:

1. Create a Prompt; edit a **local** draft; save **only** on explicit user confirmation.
2. Save a new revision; browse version history; compare two versions (diff of text + changed
   metadata fields).
3. Bind characters / scenes / shots / reference assets; show which references are **unverified**
   (`UNKNOWN`), never invent one.
4. Handle `409` properly: keep the user's local draft, show which conflict occurred, offer reload of
   the authorised projection. **Never** discard the draft on conflict.
5. Recover after going offline, a refresh, or reopening — the local draft must survive; nothing is
   written before the user confirms.

## Hard constraints for R3-U

* Follow `docs/ui/design_system.md`; reuse design tokens, existing primitives, AppShell and the
  ModuleWorkspace contract. `docs/ui/protected_ui_surfaces.md` lists protected surfaces — feature
  agents are consumers by default. A system-level change needs a `DESIGN SYSTEM CHANGE REQUEST`.
* Do not modify the protected AppShell. Do not invent colours or spacing. Do not duplicate components.
* Reuse the existing UI and asset owner. **No second system.**
* `scripts/check_ui_design_tokens.mjs` only walks `frontend/src/ui`, so a new module's CSS must be
  self-verified.
* Run frontend tests, TypeScript, and a production build before committing.

## Known limits to carry forward (do not overstate in the UI)

* Revision allocation is conflict-detecting, **not** lock-serialized. The UI must therefore treat a
  `DUPLICATE_REVISION` anomaly as a real, displayable state rather than an impossible one.
* Write-time validation of binding targets is **`NOT_RUN`** — the UI may show bindings as unverified,
  but must not claim they were validated on save.
* `previous_asset_id` is a **reference**, not a verified lineage edge. Do not render it as a
  provenance graph; that is Round 4.
* Cross-**process** concurrency for the same asset root is `NOT_RUN` (two-thread and structural lock
  analysis were done).
* R3-R-08 remains **PARTIAL**: masking is presentation, not confidentiality.

## Evidence

`round3w-authoring-r10` (File, 202 passed / 60 skipped / exit 0) ·
`round3w-authoring-postgres` (real PostgreSQL, 79 passed / exit 0) ·
`round3w-authoring-r7`, `round3w-diag` (the failing runs that located D1/D2, kept).
