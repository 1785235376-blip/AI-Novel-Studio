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
| R3-R read-contract fixes | **DONE (R3-R-08 PARTIAL)** | `ROUND3R_READ_CONTRACT_REPORT.md`; repro `round3r-repro-r1` **26 failed / 3 passed**; fix `round3r-read-contract-r2` **197 passed / 60 skipped / exit 0**; real PostgreSQL `round3r-read-contract-postgres` **100 passed / exit 0** |
| R3-W dedicated authoring entry | `NOT_RUN` | **next action** |
| R3-U Prompt Workspace | `NOT_RUN` | — |
| R3-I production application | `NOT_RUN` | — |
| R3-GATE | `NOT_RUN` | — |
| R4 asset relationship view | `NOT_RUN` | — |

## Round 3 status at baseline (honest)

Round 3 delivered the audit + a read-only library projection + three GET routes. It is **not** a
complete Prompt Studio: there is **no authoring route** (`ManualAssetImport.kind` is
`image|video|audio` only) and **no Prompt Workspace UI**. `ROUND3_PROMPT_REPORT.md` already records
both as `NOT_RUN`; this task book continues Round 3 rather than renaming that work as Round 4.

## Decisions in force (task book §0, incorporated)

1. Dedicated Prompt create/revision entry reusing `AssetLibraryService`; **do not** widen
   `ManualAssetImport`.
2. No `PromptDatabase`, no second asset/version/review/queue system.
3. **Forbidding AI auto-overwrite ≠ forbidding the user to edit/save/revise.** Read-only projections
   stay read-only; user-authorised writes get their own permission-bound routes.
4. "Prompt reads the latest authorised version" splits into: browse = latest readable; a saved
   revision/task records the **actually adopted** source version + digest and must not silently
   drift. Source change ⇒ STALE/needs review, never an automatic rebind.
5. Preserved: `main` untouched, PR #47 Draft, V1 frozen, QingJian untouched, Content Policy
   `RESERVED`, user's Strata untouched, no model download, no paid API, no final Windows/GPU
   acceptance.

## Next exact action (resume point)

**R3-W — dedicated authoring entry.** Nothing else is in flight; R3-R is committed and pushed.

1. Read `app/creative/workspace_models.py` (DTO conventions) and the existing
   `annotate_lineage` / `promote_owned` call sites.
2. Add a strict authoring DTO module (e.g. `app/creative/prompt_authoring_models.py`): create
   request (`family_id?`, text, negative_prompt, purpose, model preference, non-execution
   parameters, seed, selected character/scene/shot/reference ids, change note/reason, `request_id`
   idempotency key, optional expected previous revision) and a revision request. **No** client-supplied
   `approved_at`, reviewer, `_owner_actor_id`, `_project_binding`, receipts, `model_called` or
   output provenance.
3. Thin adapter service reusing `AssetLibraryService.create` + `update_metadata` +
   `annotate_lineage`, allocating `revision` under the existing project-binding mutation lease
   (no new lock, no new queue). Handle partial failure: `create` succeeded but metadata/lineage
   failed must not report success and must be recoverable by the same `request_id`.
4. Routes: `POST /projects/{nid}/studio/prompts` and
   `POST /projects/{nid}/studio/prompts/{family_id}/revisions`, added to the closed admission
   allow-list in `app/creative/workspace_api.py`. The three GETs stay read-only; the
   `/prompts/context` static route keeps priority over `{family_id}`.
5. Verification: File + real PostgreSQL + the T01–T07 cases in task book §8 (idempotency,
   concurrent next-revision, failure injection, immutability of old revisions, multibyte limits).
6. Then commit/push R3-W alone and continue to R3-U.

**Known constraint to design around (found in R3-R):** the asset owner's `update_metadata`
allow-list is `{source_job_id, provider_id, model_id, parameters, approved_at, character_id,
scene_id, source_asset_ids}`. Prompt payload/bindings already fit inside `parameters` +
`character_id`/`scene_id`/`source_asset_ids`, so **no owner change is currently required**; if one
proves necessary it must be a minimal, verified, type-specific immutability guard (task book §4)
rather than a new store.

## Stop reason (if the session ends here)

R3-R is complete and committed; R3-W onward is `NOT_RUN`. Stopping is a **session/tool budget**
limit, not a product blocker, and not a claim that work is running in the background.

