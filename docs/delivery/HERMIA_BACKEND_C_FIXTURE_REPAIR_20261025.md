# Backend C: source-valid variants and verified-local memory fixtures

Date: 2026-10-25 (UTC). Base: `e99e91ed84763224638b80ffb83ae7880fa4f1a0`.

## Scope and result

Tests-only repair in:

- `tests/test_generation_variants_phase3.py`
- `tests/test_memory_agent_contract.py`

No production, frontend, schema, Asset/AudioAsset owner, B-owned `test_generation_idempotency_contracts.py`, dependency or baseline-registry changes were made by this slice. This delivery note is the only additional tracked file. No commit, push or release was performed by the implementing worker.

Final validation: both repaired files **21 passed**; original exact C40 plus ten added cases **50 passed**. These sets overlap and must not be added together as independent coverage. There were no setup/teardown errors, skips, xfails or external-side-effect guard events in either final run.

## Failure causes, established before editing

1. `test_variant_generation_creates_independent_jobs` supplied nonexistent project/chapter `n`/`c`, so intact `app/api.py::_generation_request_context` returned 404 before `jobs.create`. Current local admission reads the actual chapter and checks its project identity.
2. `test_variant_lifecycle_accepts_one_and_rejects_the_rest` had the same rejected admission, then indexed the nonexistent `variants` response field without first checking status.
3. `test_extract_creates_pending_proposal_with_evidence_and_is_idempotent` injected a router-only fake Runtime. `MemoryAgentRunner` now requires model/provider registries and an admissible verified local adapter, then calls `prepare_text_route` and the normalized TextModelNode. The old fake stopped at `MEMORY_LOCAL_PROVIDER_NOT_CONFIGURED`.
4. `test_invalid_json_marks_independent_job_failed` stopped at that same route check before it could exercise the intended JSON ValidationError.

A full pre-edit run of these two files additionally exposed their existing `test_generation_is_idempotent_under_concurrent_submission`: it used the same nonexistent source. That test was excluded from original C40 but was preserved and repaired within its already-owned file. The separate B file was not touched.

These were stale fixture contracts, not reasons to relax source admission, local-egress checks or output validation. No independent production defect was demonstrated by this slice.

## Variant fixture and preserved boundaries

The fixture creates a real run-scoped File repository bundle, project and allocated chapter, then resolves the chapter's actual canonical ID/version. API and JobManager use these same service owners. The idempotency store is independently rooted at tmp_path.

Only `JobManager.start_prepared` is replaced by a controlled software staging seam: it honors an optional authorization callback, records the exact prepared Job under its manager lock and persists it without launching a model worker. Real request admission, `prepare_job`, content gates, `accept`, `reject`, `retry`, `cancel`, source resolution and File persistence remain active.

Existing behavior is stronger than the former hand-written Job doubles:

- Concurrent same-key requests share one job and one dispatch, with a valid persisted source.
- Three variants have distinct jobs and instructions, one shared group, indices 1–3 and the real source version.
- Explicitly accepting candidate 2 uses the original JobManager to create the new chapter and pending canon. The source chapter is unchanged and siblings remain undecided until explicitly rejected.
- Real persisted statuses become REJECTED / ACCEPTED / REJECTED, and exactly one new chapter is created.
- Raw File create projection includes its title; durable read content is asserted via strict `document_to_markdown(markdown_to_document(expected_content))` and exact document equality. No content stripping or weakened status expectation was introduced.
- Failed retry creates a new independent job while preserving original source/instruction and sibling states; completed retry remains refused.
- The first two cancellation subjects are explicitly staged as GENERATING to preserve the old test's running-state case. Cancelling either does not cancel the other or the third queued job.
- Three new cases require 404 before dispatch/persistence for missing, wrong-project and deleted sources. The wrong-project code must remain `CHAPTER_OUTSIDE_PROJECT`.

Synthetic staging/completion does not claim model execution, live worker cancellation or outbound provider privacy acceptance.

## Memory fixture and preserved boundaries

The fixture uses real `ProviderRegistry`, `ModelRegistry`, `GenerationRuntime`, `LegacyTextProviderAdapter` and a `MockProvider` subclass. The subclass only supplies synthetic JSON text via `_text`; inherited generation retains genuine mock metadata. A recording adapter observes requests but delegates execution to the real adapter. The local verifier and dispatch guard are never replaced.

The memory module's frozen settings are narrowly replaced with explicit development-Mock settings for these fixture tests, then automatically restored. No host Runtime is constructed, no credentials are installed, and no unrelated provider routes or host identity stores are provisioned by this fixture. Legacy adapter structured-output capability remains false rather than claiming schema enforcement it does not supply.

Original assertions now additionally prove:

- Two extractions yield exactly one pending proposal and one evidence record with the accepted chapter/version/quote and `LOCAL_ONLY` privacy, with no approved memories.
- Two actual synthetic provider calls and two observed normalized requests prevent vacuous metadata assertions.
- Even a HYBRID caller produces a persisted LOCAL_ONLY request, guarded local route and `mock_standin` execution mode.
- Invalid JSON shape still reaches the real ValidationError, persists FAILED / MEMORY_EXTRACTION_FAILED, and leaves proposals/evidence/memories empty.

Seven new collected cases exercise the untouched fail-closed boundaries:

- Unconfigured provider.
- A remote-labelled provider, despite its harmless Mock implementation.
- A local-labelled non-Mock provider that must not execute.
- Mock mode disabled.
- Packaged runtime enabled.
- Local attempt fails and must not fall back to a registered remote provider.
- Adapter identity changes after selection and must be refused by the real dispatch guard before either adapter executes.

The first five persist NOT_CONFIGURED with zero dispatch/provider calls and no evidence/proposals; the latter two persist FAILED. All use synthetic local objects, never a real provider or network service.

## Verification, without mixing counts

Every phase used the existing `.venv`, sourced `.runtime/activate-backend.sh`, then ran with independent HOME/APPDATA/LOCALAPPDATA/XDG/data/TMP/basetemp. Environment started from `env -i`, File + Mock + LOCAL_ONLY, cloud/packaged mode off, credentials/database URLs absent and dotenv loading disabled. The runner blocks and records socket connections, DNS and process/shell launches; no guard events occurred. No test skip or assertion bypass was added.

| Phase | Actual result | Seconds | Exit |
| --- | --- | ---: | ---: |
| Original exact C40, before repair | 36 passed, 4 failed | 6.99 | 1 |
| Both owned files, before repair | 6 passed, 5 failed | 8.73 | 1 |
| Intermediate 1 | 20 passed, 1 failed: new real File title projection needed an exact expectation | 6.97 | 1 |
| Intermediate 2 | 20 passed, 1 failed: durable canonical Markdown includes trailing paragraph separators | 7.12 | 1 |
| Canonical projection corrected | 21 passed | 7.86 | 0 |
| Final reviewed two-file run | 21 passed | 7.60 | 0 |
| Final original C40 + ten new cases | 50 passed | 8.44 | 0 |

Each final phase had three existing warnings: Starlette TestClient/httpx deprecation and two Pydantic `schema` field-shadowing warnings. None prevented execution. The two final sets contain 51 distinct nodes in union: the original variant concurrency node is covered in the two-file run, not in C40. Do not report 21+50 as 71 distinct tests.

Final commands, from repository root:

```sh
timeout 180s env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
  bash .runtime/backend-c-fixture-repair-20261025/run.sh \
  after-focused-reviewed .runtime/backend-c-fixture-repair-20261025/focused-targets.txt

timeout 180s env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
  bash .runtime/backend-c-fixture-repair-20261025/run.sh \
  after-c-plus-new .runtime/backend-c-fixture-repair-20261025/c-plus-new-targets.txt
```

Evidence is retained under `.runtime/backend-c-fixture-repair-20261025/`, including original source copies, complete before/intermediate/after logs, JUnit XML, per-phase results and source hashes. `verification-summary.json` confirms all original 40 node IDs were included in the final 50. The original C40 failure evidence remains under `.runtime/backend-suite-inventory-20261025/group-c/`.

`git diff --check` for this slice passed, and `git diff --quiet -- app` was zero at validation time. Other workers' authorized B-file changes are not attributed to this slice. Subsequent production owner changes require combined revalidation against their exact source, not reuse of this result as evergreen acceptance.

## Frozen source hashes

| File | Before SHA256 | Final SHA256 |
| --- | --- | --- |
| test_generation_variants_phase3.py | e435c36c6ba5da6984a544a76ae97f12a9d7b0bf96d0a5856068862fca71f9a5 | c54bfb222839e8a73003a091ebed07ba0608147fab1df444c397c7ea35331755 |
| test_memory_agent_contract.py | c57045560a97d2c6188affde6b223fd1b425bb53465b0a20945104b96de813c7 | 140de9e8167b80bc21b28f601bf4bced759e357d0a40435b1fb8fcba2c81dd38 |

Two read-only implementation reviewers found no blocking authority/privacy issue. Their minor coverage suggestions were incorporated before the final reviewed and C50 runs. A separate parent-owned independent review remains distinct from these implementation checks.

The parent-owned review subsequently passed the frozen two-file focused set (21 tests), repeated the concurrency node 10 times in an independent archive of the fixed production baseline, and confirmed that seven in-process fault injections were rejected by the assertions. The probes covered duplicate dispatch, sibling cancellation, non-persisted rejection, changed retry instructions, remote-provider admission, a removed dispatch guard, and unstable memory idempotency identity. No blocking finding remained. These overlapping runs are not a summed unique test count, and are not validation of subsequent production changes.

Portable evidence: [verification summary and independent logs](evidence/backend-c-fixtures-20261025/). Checkout paths in the log copies are normalized; original local artifacts remain separate.

## Collection inventory correction and remaining limits

Earlier full collection, before this repair, observed 2251 items in 212 files with zero collection errors; it was not a full-suite execution and is not the post-edit count. No duplicate full collection was run here. The TaskCenter file's original 65 items consist of 32 with `file_backend_only` plus 33 without. An intermediate report mistakenly quoted that marker subset as its total; the original collection artifacts always contained all 65. No conditional collection filter was found: conftest adds opposite-backend skips but does not remove items. The correction and raw proof are retained in the inventory report.

No real PostgreSQL, GPU, provider inference, fee-bearing service, frontend/browser, DesktopHost or native media acceptance is claimed. A read-only review noted an analogous router-only fixture in the PostgreSQL-only lore test; that unexecuted and unowned test remains outside this slice. No automatic baseline update or unrelated repair was made.
