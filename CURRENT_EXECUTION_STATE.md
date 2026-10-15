# CURRENT_EXECUTION_STATE — Round 3 completion (R3-R → R3-W → R3-U → R3-I → R3-GATE → R4)

**Updated:** 2026-10-15 (Round 3 completion task book `DSH_ROUND3_COMPLETION_AND_ROUND4_CONTINUATION.txt`)

## Repository / baseline

| Item | Value |
| --- | --- |
| Repository | `1785235376-blip/AI-Novel-Studio` |
| Development directory | `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` (**`D:\PoemSeed` is a container, not a repo**) |
| Branch | `feature/v2-narrative-platform` — in sync with `origin` |
| **HEAD (full)** | `1bce019f492a7e23b06f221f17ed49cf07d7f475` |
| Task-book baseline | `1bce019f492a7e23b06f221f17ed49cf07d7f475` → **exact match, no forward commits to integrate, no rebase needed** |
| `main` | `fed2404c8e30b44061b7139dced45b7f3301601c` — untouched |
| PR #47 | `OPEN`, `isDraft: true`, head `1bce019…` |
| Tracked dirty | **0** |
| Untracked | **51** = 49 under `docs/delivery/v2-development` (historical `phase6-*` receipts + this session's `round3-probe-*` diagnostics) + `.graphflow-cache/` + `graphflow-out/`. **Nothing cleaned.** |
| Protected | sibling clones, `D:\PoemSeed\AI-Novel-Studio` snapshot, QingJian, user's original project — observed only |

No `reset --hard`, `git clean`, force push, ref repair, ACL change or PATH rewrite was run.

## Environment (checked live, not assumed)

| Component | State |
| --- | --- |
| Python / Node / pnpm | `3.11.9` / `v22.14.0` / `12.4.2` (as declared by the repo) |
| **Port 8080** | **held by pid 15392 — the user's Strata server. NOT started by me; never stopped.** |
| **Port 8100** | held by pid 11804 (unrelated) — not mine |
| Ports 8110 / 5432 / 55433 / 5173 / 4173 | **free** (checked live) |
| PostgreSQL | portable cluster `D:\PoemSeed\Builds\studio-v2-host-5ed1cbee-20261011\Base\PostgreSQL` (16.15); checkout-owned cluster `.runtime/pgdata-v2-phase14a` **initialised and stopped**, ready for `run_v2_postgres_checks.py` |
| Isolated runner | `scripts/run_v2_checks.py` (needs explicit `--basetemp` under `.runtime`); `scripts/run_v2_postgres_checks.py` takes positional `label` |

## Sub-phase ledger

| Sub-phase | Status | Evidence |
| --- | --- | --- |
| Baseline verification | **DONE** | this file |
| R3-R read-contract fixes | **DONE (R3-R-08 PARTIAL)** | `ROUND3R_READ_CONTRACT_REPORT.md`; repro **26 failed / 3 passed**; fix **197 passed / 60 skipped / exit 0**; PG **100 passed / exit 0** |
| **§3 read follow-up** | **DONE** | `ROUND3S_READ_FOLLOWUP_REPORT.md`; repro `round3s-repro-r1` **3 mismatches**; fix `round3s-read-followup-r1` **154 passed / exit 0**; PG `round3s-read-followup-postgres` **83 passed / exit 0** |
| **R3-W dedicated authoring** | **DONE** | `ROUND3W_AUTHORING_REPORT.md` / `_DECISIONS.md` / `_HANDOFF.md`; File `round3w-authoring-r10` **202 passed / 60 skipped / exit 0**; real PostgreSQL `round3w-authoring-postgres` **79 passed / exit 0**. D1 fixed (prompt-specific whitelisted 409); D2 confirmed a test-contract error (`head_asset_id` vs `asset_id`). |
| R3-U Prompt Workspace | `NOT_RUN` | **next action** (see `ROUND3W_HANDOFF.md`) |
| R3-I production application | `NOT_RUN` | — |
| R3-GATE | `NOT_RUN` | — |
| R4 asset relationship view | `NOT_RUN` | — |

## Next exact action (resume point) — R3-U

Operable Prompt Workspace per `ROUND3W_HANDOFF.md`: create, edit a **local** draft, save a revision,
version history, version compare, bind characters/scenes/shots/reference assets, show unverified
references, handle `409` without discarding the draft, and recover after offline/refresh/reopen.
Save happens **only** on explicit user confirmation.

Constraints: `docs/ui/design_system.md` + `docs/ui/protected_ui_surfaces.md` + the
`ai-novel-studio-ui` skill (read from `.codex/skills/ai-novel-studio-ui/SKILL.md` if it is not in the
skill menu); reuse tokens/primitives/AppShell; no protected-surface change; no second system.
`check_ui_design_tokens.mjs` only walks `frontend/src/ui`, so new module CSS must be self-verified.
Then frontend tests + TypeScript + production build, then commit/push R3-U alone.

## Hash ledger (kept deliberately distinct — §2 of the directive)

| Role | Value |
| --- | --- |
| **baseline_sha** | `1bce019f492a7e23b06f221f17ed49cf07d7f475` (Round 3 data projection) |
| **last verified remote commit (before this sub-phase)** | `f83cadbe8eb61ced886460a1c2e2fe5c36e4da21` (R3-R) |
| **current sub-phase** | §3 bounded read-contract follow-up — committed locally, pushed to the dev branch |
| **source snapshot tested** | `app/creative/prompt_asset.py`, `app/creative/prompt_workspace.py` as modified in this sub-phase; digests are in the runner receipts (`round3s-read-followup-r1.json`) |
| **next concrete action** | R3-W (see below) |

A report cannot contain the hash of the commit that includes it; the commit record is the publication
identity and the runner receipts are the source pin.

## Round 3 status (honest)

Round 3 has delivered: the prompt-source audit, a read-only library/detail/context projection (3 GET
routes), the R3-R read-contract repairs, and the §3 follow-up. It is **still not a complete Prompt
Studio**: there is **no authoring route** (`ManualAssetImport.kind` is `image|video|audio` only) and
**no Prompt Workspace UI**. Those are `NOT_RUN`, not renamed into Round 4.

## Decisions in force (task book §0 + directive §4)

1. Dedicated Prompt create/revision entry reusing `AssetLibraryService`; **do not** widen
   `ManualAssetImport`.
2. No `PromptDatabase`, no second asset/version/review/queue system.
3. **Forbidding AI auto-overwrite ≠ forbidding the user to edit/save/revise.**
4. Browse = latest readable; a saved revision records the **actually adopted** source version +
   digest and must not silently drift. Source change ⇒ STALE, never an automatic rebind.
5. **R3-R-08 stands as PARTIAL by decision:** the authorised raw-asset download contract is
   unchanged; masking is never called confidentiality; the cross-route security claim stays PARTIAL
   until cross-route tests establish its scope.
6. Preserved: `main` untouched, PR #47 Draft, V1 frozen, QingJian untouched, Content Policy
   `RESERVED`, user's Strata untouched (pid 15392 on 8080 — not mine, never touched), no model
   download, no paid API, no final Windows/GPU acceptance.

## Next exact action (resume point)

**R3-W — dedicated Prompt authoring** (directive §5). Nothing is in flight; the follow-up sub-phase is
committed and pushed.

1. **Map the real call sites first** (directive §5 preamble): `AssetLibraryService.create` /
   `update_metadata` / `annotate_lineage` / `promote_owned`, the lock order and
   `workspace_mutation` boundary, `IndependentWorkspaceService._asset_scope` binding, and how
   `actor` reaches them. "The payload fits the allow-list" proves **shape compatibility only** — it
   does not prove atomicity, immutable revisions, provenance integrity or concurrency safety.
2. Add strict DTOs (e.g. `app/creative/prompt_authoring_models.py`): create + revision requests
   accepting only documented user-editable fields (text, negative prompt, purpose, provenance
   category, model preference, non-executing parameters, seed, selected bindings, change note/reason,
   `request_id`, expected head identity). **Reject** client-supplied `approved_at`, reviewer,
   authority fields, receipts, `model_called`, output provenance and internal owner/binding markers.
   Preserve whitespace/newlines/CJK/emoji — no generic `.strip()` on creative content; measure actual
   UTF-8 bytes against the existing limits.
3. Thin authoring adapter over the existing owner. Allocate `revision` inside the existing
   project-binding mutation lease; no process-local lock claimed as cross-process safety; never hold
   a storage lock across a model or external call.
4. Routes: `POST /projects/{nid}/studio/prompts` and
   `POST /projects/{nid}/studio/prompts/{family_id}/revisions`, added to the closed admission
   allow-list in `app/creative/workspace_api.py`; keep `/prompts/context` registered before the
   variable family route; the three GETs stay read-only.
5. Idempotency and failure: same actor/scope/`request_id` + same request ⇒ same result; same
   `request_id` + changed payload ⇒ conflict; injected failure after bytes / metadata / lineage /
   response must be recoverable exactly once via the original request identity, with no duplicate
   asset and no fabricated success.
6. Tests T01–T09 (directive §5.4) on File **and** real PostgreSQL; then commit/push R3-W alone.

**Known constraints found so far (design around them):**
the `update_metadata` allow-list is `{source_job_id, provider_id, model_id, parameters, approved_at,
character_id, scene_id, source_asset_ids}` — the prompt payload fits inside `parameters` plus
`character_id`/`scene_id`/`source_asset_ids`, so **no owner change is required yet**; and the asset
owner's reads require the **actor**, so a private draft is invisible to an anonymous read
(confirmed by test).

## Stop reason (if the session ends here)

The §3 follow-up is complete and committed; R3-W onward is `NOT_RUN`. Any stop is a **session/tool
budget** limit — not a product blocker, and not a claim that work is running in the background.


