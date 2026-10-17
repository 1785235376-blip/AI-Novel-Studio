# Storyboard Director proposal: bounded source evidence

Status: primary backend and final primary UI verification passed. Independent final source review approved the bounded slice; independent subset reruns passed against final combined source bytes. This is bounded source acceptance only, not full feature/model/browser acceptance.

Frontend: **88 unique cases across eight suites, including 19 new cases**, forced TypeScript, production build and token guard passed. [Byte-exact r1/r2 UI logs and source manifests](ui/README.md) retain the earlier overlapping 86-case checkpoint and its new-test TypeScript failure; it is not added to the unique total. Backend results below remain a separate evidence layer.

## Initial run

- Original runner receipt: [storyboard-director-backend-r1.json](../storyboard-director-backend-r1.json)
- Original runner log: [storyboard-director-backend-r1.log](../storyboard-director-backend-r1.log)
- Result: **45 passed, 33 deselected, 1 warning**, pytest duration 16.34 seconds; exit 0.
- Selection: `-m 'not postgres_backend_only'`. The 33 deselected cases require PostgreSQL. Selected tests include original File cases and backend-neutral checks; this does not claim 45 exclusively File-classified cases.
- Sources changed during check: **false**. Both before/after full source digests are retained by the original runner receipt.
- HEAD: `00b305c9c784bd316a8c23a70a28157d19366f09`.
- Receipt SHA256: `56998675811fa4003178be92ac9b3ceec72e1cb655980cf893d7bc1421486711`.
- Log SHA256: `04a2d7b168e5175be1ff065916898f5a1220983a78a370e2c15f037acd644a1a`.
- Warning: existing Starlette/httpx TestClient deprecation. No dependency modification was made.

Files selected:

1. `tests/test_v2_storyboard_director_proposal_loop.py` (new)
2. `tests/test_v2_graph_director_proposal_loop.py` (unchanged)
3. `tests/test_v2_director_proposal_reopen.py` (unchanged)
4. `tests/test_v2_director_model_planning.py` (unchanged)
5. `tests/test_v2_director_authority_reads.py` (unchanged)

## Scope and limitations

The new path exercises saved STORYBOARD creation, one note per authored shot, copied camera/duration values, complete shot provenance snapshots, explicit unmapped-field disclosure, human-edited review, separate DIRECTOR DRAFT, explicit original Graph snapshot pin and Creative/Graph restart with CURRENT references. It checks stale/archive, version CAS, exact review digest, actor/scope, association/order, cancellation/duplicate adoption and rich-field limits.

The original File-owner test includes a real imported tiny PNG, its formal image binding and original storyboard approval. It compares canonical source-row bytes read from the actual persisted File scope document, plus exact asset-file bytes before and after the loop. The whole scope file necessarily changes to add the proposal, Director and explicit Graph; unrelated collections remain equal. Source approvals and image bindings remain unchanged. No video was generated or bound: the test verifies the absent video binding stays absent, rather than claiming coverage of an existing generated-video result.

Storyboard model preview and dispatch use downstream-owner tripwires to prove rejection before broker, preparer or manager access, with persisted scope bytes unchanged. The new storyboard tests do not create model jobs or Graph runs. The unchanged screenplay regression suites do create synthetic mock-provider jobs through original owners, with the mock stream monkeypatched to deterministic text. Thus the overall 45-test run is not described as zero jobs; it made no live model/provider calls. No network service, real PostgreSQL, GPU, browser, paid provider or video rendering was used.

The implementation is rule-assisted copying and human-review scaffolding. It is not completion or quality validation of intelligent storyboard model analysis.

## Clean interpreter and current-root proof

The `origin/` files are byte-exact copies of the reviewer's `.runtime/storyboard-director-origin/` evidence. Each source/copy pair was checked with `cmp`; `origin-sha256.txt` records hashes. The probe is stdlib-only and reports normal startup plus parent/actual child PathFinder resolution. It does not import product or pytest modules. Original command records retain the actual runtime paths.

The authorized test run used the clean interpreter at `studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python`, with user-site, dotenv and pytest plugin autoload disabled. PYTHONHOME/PYTHONPATH/startup/userbase, pytest injection variables, database URLs, collaboration development sessions and packaged bootstrap settings were removed before the original `scripts/run_v2_checks.py` entrypoint. That runner owns the isolated File/mock/offline profile, source snapshot and basetemp under `.runtime/v2-checks/storyboard-director-backend-r1/`.

No source/test edits occurred during verification. No staging, commit, merge, push or release was performed.

## Independent final source approval

[Final source review](dot-storyboard-director-final-source-review-20261017.json) reports `APPROVE_SOURCE_SLICE`, binds all five runtime files and two additive test files, and records zero drift among 1,273 protected entries. The source base remains `00b305c9c784bd316a8c23a70a28157d19366f09`; no source changes followed the final verification. This README, feature report and ledger were finalized afterward, so the review's earlier documentation hash is a historical checkpoint rather than a hash of the final prose.

Independent frontend repetition passed **60 cases in three files**: 19 additive cases and 41 unchanged original panel/reopen cases. All 2,535 source-plus-companion entries were stable. [Exact independent UI artifacts](ui/independent/) retain original filenames and per-file hashes. Independent backend repetition passed **19 cases with 18 PostgreSQL cases deselected**, with 2,524 source entries stable: [receipt](../storyboard-director-independent-backend-20261017.json) and [raw log](../storyboard-director-independent-backend-20261017.log). These repeated subsets overlap the primary **88 UI / 45 backend** counts and are not summed.

The [initial checker diagnostic](dot-storyboard-director-final-source-review-20261017-initial-checker-diagnostic.json) is preserved unchanged. It records the reviewer's corrected interpretation of `git diff --no-index` exit 1 for a new/different file with empty stdout/stderr; it was not a source or test failure and required no source change. `final-review-sha256.json` binds both exact copies. Full feature, intelligent model analysis, browser, PostgreSQL, target-platform and release acceptance remain open.
