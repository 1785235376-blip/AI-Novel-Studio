# R3 Prompt adoption binding implementation

Status: implementation and isolated File integration PASS; real PostgreSQL and independent-process/browser acceptance remain pending in this report. Production `PROMPT_ADOPTION_WRITE_ENABLED` remains `False`.

## Original-owner contract

`PromptAdoptionService.adopt_atomic` resolves every declared binding inside the existing `GraphAssetInputs.phase(writable=True)` boundary. The phase retains the original scope transaction, asset lease and project incarnation lease through the Creative document commit. It opens no Bible aggregate projection, nested asset scope or replacement owner.

- Character and scene bindings read the original `NovelService.data_set` records and reuse `BibleWorkspaceService._scoped`. Missing, ambiguous, foreign-branch or archived records refuse the adoption. File writers share `guard_project`; PostgreSQL `_upsert_story_record` takes the same novel `FOR UPDATE`, which conflicts with the phase's retained `FOR KEY SHARE`.
- Canonical shot bindings reuse the original pure `project_shot_cards` and `prompt.shot_index` document-number projection (`document_id:number`). Raw owner shot IDs remain compatible only inside the explicit target storyboard document. Another document's same-numbered shot and duplicate numbers cannot silently satisfy a binding.
- Reference and output assets use actor-aware original `AssetLibraryService.get` and verified content reads under the held lease. Deleted, private-other-actor, foreign-project/branch, invalid-version or damaged-content targets refuse with `PROMPT_ADOPTION_BINDING_UNAVAILABLE` without echoing target IDs or bodies.
- A committed proof records `source_binding_contract=prompt-adoption-bindings/1`, bounded identity/digest/version snapshots and `source_bindings_verified=True` only after all declared bindings pass. `WRITE_TIME_OWNER_LEASE` describes an observation at that commit; it is not approval, current-target liveness, model execution permission or a release-gate decision. A settled replay retains its historical proof without creating another write.

The existing Creative document version/digest CAS, source revision/body verification and final authority guard remain in their original owners. Production POST remains an authorized `503 PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED`; GET remains available.

## Verification retained

Pinned interpreter: `D:/PoemSeed/Cache/Tests/expansion-20261013-97da10e1/venv/Scripts/python.exe`, pytest 8.4.2. Base HEAD: `618affbca0aaf20d5bc669d697d8e2b1abb9b3fa`.

- `r3-bindings-file-r1`: 18 passed, 17 PostgreSQL parameter cases skipped; first additive binding suite.
- `r3-bindings-file-r2`: 39 passed, 22 PostgreSQL parameter cases skipped, one existing Starlette deprecation warning. Runs the additive binding suite and existing frozen adoption concurrency, HTTP and mounted-router suites. Receipt reports `sources_changed_during_check=false`.
- `r3-bindings-file-r3`: 41 passed, 2 failed, 26 skipped. Failure receipts retained: a deliberately corrupted duplicate-shot-number test setup attempted the normal document reader, which correctly refused `CREATIVE_DOCUMENT_CORRUPT` before the adoption assertion. The additive test now explicitly verifies that refusal and compares the retained original raw state after the adoption refusal.
- `r3-bindings-file-r4`: 43 passed, 26 PostgreSQL parameter cases skipped, one existing Starlette deprecation warning. The same focused selection now includes canonical document-number bindings, identical numbers across documents, and duplicate-number source refusal. Additive binding cases are 27 File cases (including the unparameterized closed-switch assertion) / 26 PostgreSQL parameter cases.

The additive module is `tests/test_round3_prompt_write_time_bindings.py`. Existing frozen tests were not modified. It exercises all four binding owner types, five binding fields, scoped and archived story records, imported output roles, unavailable/corrupt/private/foreign asset refusals, deletion after a read, late guard rollback, a participating story writer waiting for the retained phase, phase admission and the still-closed production switch.

The `.log` and `.json` files here are exact copies of original runner receipts retained under `docs/delivery/v2-development`; their embedded original log paths remain valid. No failed evidence was removed. This report does not turn service tests into browser acceptance or claim a production adoption write was enabled.
