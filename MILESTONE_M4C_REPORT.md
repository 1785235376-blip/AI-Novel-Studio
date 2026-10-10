# M4-C Real local text execution

**Bounded real CPU acceptance and final same-source selected File/PostgreSQL
regression passed. Broader M4 remains PARTIAL. New-SHA hosted CI is pending.**

This user-defined M4-C continues the AI Execution Layer from verified local and
remote `90e77c0aa559a8c0a52d9b42658ac8c756de3197`, on
`feature/v2-narrative-platform`, [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47).
It does not restart M4-B or rename the historical roadmap stages. QingJian is
independent; no other repository, Interop contract or Image/Video module changed.

## Actual implemented path

| User goal | Code / API / UI | Verified boundary |
|---|---|---|
| Real TextNode | Existing scoped graph create, preflight, run, preview and dispatch APIs; original TextModelNode and local transport | Official Qwen GGUF executed by owned llama.cpp CPU host; no Mock or cloud fallback |
| Provider adapter | Original Model Center LLAMA_CPP validation now records the missing local-source metadata agreement | Exact safe configured TEXT GGUF and running external numeric-loopback runtime alias required; invalid revalidation clears stale evidence |
| Actual Router scheduling | Original ModelRouter/ModelBroker match, exact reviewed route, price, reservation and original JobManager dispatch | One original Job; repeated admission returns that Job; existing 180-second deadline unchanged |
| Result → Asset → Version | Original actor-private AssetLibraryService archival and WorkflowRun human review | One DRAFT TextAsset v1; review metadata v2; no edited-content version or manuscript/Canon apply |
| Model / Prompt / parameters / Workflow receipt | Sealed optional execution snapshot within existing private asset metadata; existing scoped graph DTO and receipt UI | Exact prompt/hash, original request/route/model evidence, parameters, Workflow/source identity and settled terminal time; generic asset responses redact the snapshot |

Original Model Center, Creative Core, Creative Graph, provider/model registries,
JobManager, broker, generation repository and asset owner remain authoritative.
No queue, registry, storage owner, invocation reconstruction or recovery model
call was added. New opted-in dispatches bind receipt contract and admission
source version to the existing immutable Job request digest. Legacy bindings
omit both fields entirely and retain v1 recovery without automatic backfill.

UI uses the existing receipt panel, disclosure control, tokens and primitives.
Exact inputs are collapsed by default. It distinguishes `real`, `mock_standin`,
metadata fingerprints and full file hashes, with quality always `NOT_RUN`.
Current UI already authorizes draft archival in its original dispatch flow;
there is no extra archival confirmation or recovery step.

Designs: [execution receipts](docs/v2/text-execution-receipts.md),
[opt-in real CPU acceptance](docs/v2/real-text-acceptance.md),
[local environment evidence](docs/v2/local-ai-environment.md).

## Real acceptance, 2026-10-10 15:24 UTC

[Terminal receipt](docs/delivery/v2-development/m4c-real-cpu/attempt-4/acceptance.json)
and [complete local evidence index](docs/delivery/v2-development/m4c-real-cpu/manifest.json)
record an isolated dot-cloud CPU run. No user computer, GPU, private credential,
paid API or software auto-start on a user machine was involved.

- Official MIT llama.cpp archive b11429: 17,693,462 bytes; actual binary reports
  `0.6.0-dev (build 11429, commit d81235049)`.
- Official Apache-2.0 Qwen2.5-0.5B-Instruct Q4_K_M GGUF: 491,400,032 bytes;
  SHA256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
  Sources, immutable model revision, archive/hash and licenses are retained in
  [official input verification](docs/delivery/v2-development/m4c-real-cpu/official-inputs.json).
- Owned numeric-loopback server, CPU-only, two threads, 2,048 context, one slot,
  128-token batch, offline; no web UI, agent or UI MCP proxy. Narrow CORS.
- Original Model Center configuration → consented scan → validate → register →
  license confirmation → enable; explicit exact-route zero provider-fee receipt
  through original Broker API. This does not call hardware/electricity free.
- Original API match/preview/dispatch, `allow_synthetic: false`,
  `archive_result: true`; actual generation reported **89 input + 18 output =
  107 tokens**. Original Job latency **1,881 ms**; dispatch-to-draft **2.630 s**.
- Actual text: “A paper boat floats on a quiet pond, gently swaying in the gentle
  breeze.” This is execution evidence, not a prose-quality evaluation.
- Same Job after duplicate dispatch; stable single asset on repeated reads;
  same receipt across DRAFT v1 / APPROVED v2; no chapters created; host revocation
  blocks the graph read. Generic asset API correctly hides private proposals.
- Actual output bytes verified through the original asset owner's scope. The
  injected test host session and original File `local-author` project context
  remain distinct; this is not packaged-login/browser acceptance.
- Native runtime exited **0**, owned process stopped, whole check **14.387 s**.
  Source identity before/after is identical: **1,742 runner inputs**,
  `740b684c9cb2aae4369af061aa21f1051161950f743b36e4d25bf062d6cc2b8c`.

The runtime/weights are retained only in the owned ignored test workspace, not
committed, embedded in tests or added to ordinary CI. The explicit acceptance
script performs no downloads. It preserves all generated projects/evidence,
bounds its own process lifetime, and refuses normal PASS on abnormal runtime
shutdown, unconfirmed inference or changed source.

## Preserved diagnostic failures

All attempts remain in the evidence index; no failure was rewritten:

1. Attempt 1 stopped before inference because the new harness assumed the whole
   optional-runtime scan must be COMPLETE. It legitimately reported PARTIAL
   while the selected host was RUNNING. The harness now requires that exact
   host's complete evidence without promoting absent optional runtimes.
2. Attempt 2 stopped before inference at the unchanged TextNode locality gate.
   Real llama.cpp registration exposed the original missing explicit locality
   marker. Dedicated tests reproduced this before the narrow owner fix.
3. Attempt 3 completed real inference and created its private draft, then the
   new harness incorrectly read it using the host-session actor outside the
   original asset scope. Existing privacy protection rejected that read. The
   harness now uses the original scoped owner for byte verification and asserts
   the generic HTTP route remains hidden; production permissions were unchanged.
4. Attempt 4 passed the complete bounded check on the final stable source.

Two early new receipt-test fixture mistakes also remain in their original logs:
immutable stored-job mutation and an invalid nested asset lease. The fixtures
were corrected to exercise original persistence and the already-held lease;
their asserted corruption rejection was not relaxed. The interim 140-pass File
run had concurrent runner/test edits and is not final-tree acceptance.

## Verification inventory

- Final 27-file File regression: **914 passed / 390 opposite-profile skips**,
  325.37 s; unchanged 1,742-input source before/after. These are selected results,
  not a claim of complete backend CI.
- Final same 27-file PostgreSQL regression: **907 passed / 397 profile skips**,
  815.02 s; fresh PostgreSQL 17.11 database verified empty, all 20 unchanged
  migrations applied, real database identity recorded, exit 0 and normal shutdown.
  Database retained; final source map matches all checks below.
- Full frontend: **2,401 passed / 8 original skips**; TypeScript/Vite build and
  original **52-file** design-token guard passed on the same 1,742-input source.
- Original coverage/catalog/TCP infrastructure selection: **279 passed**.
- Two independent complete collections: **11,293 identical ordered node IDs
  and backend classifications**, +214 against M4-B. Collection is not execution.
- Frozen V1 manifest SHA256 remains
  `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
  Old test assertions, timeout budgets, skip policy and strict joins remain intact.
- Original API catalog regenerated from staged source: **2,123 operations**, no
  added/removed endpoint. Receipt is additive to the original graph DTO.
- Dedicated receipt, locality and isolated acceptance-runner tests cover legacy
  compatibility, corruption, source binding, revalidation, restart/no replay,
  private scope, cleanup, source drift and honest evidence labels. Their model
  fixtures are explicitly synthetic, separate from the real CPU check above.
- First frontend launch used an incompatible global pnpm 11.25.0 and failed the
  unchanged required 10.6.5 engine check. Retained FAIL receipt. The existing
  installed Vitest/TypeScript/Vite entrypoints then ran successfully, as in M4-B;
  no dependency requirement or engine assertion was changed.
- Local browser preflight could not find Playwright's expected pinned headless
  executable. Local visual/geometry execution remains **NOT_RUN**. Hosted browser
  suites on the published SHA are still required; no browser-security bypass.

Original raw logs retain pytest/native output whitespace. Source/document diff
checks pass; whole staged diff whitespace checking reports those raw-log trailing
spaces and blank lines. Evidence was not reformatted to manufacture a clean log.

## Remaining acceptance

Publication and full new-SHA CI are pending at this source checkpoint. The
[source-bound verification](docs/delivery/v2-development/stage-m4c-publish-verification.json)
binds the actual local results; the PR and post-CI delivery report record the
published SHA and its terminal workflows without fabricating a pre-commit CI result. Real CPU acceptance does not complete quality,
all models/prompts, Ollama/LM Studio inference, Windows/GPU, browser-real-model
flows, global hardware scheduling, API execution or Image/Video development.
Model Center locality is metadata agreement, not process/weight attestation;
the owned real test separately verifies official bytes and launched process.

M4-B `90e77c0a` retains its two successful 7,318-pass PostgreSQL profiles, hosted
browser passes, two File 20-minute platform cancellations and four failed strict
joins. Its **PARTIAL_HOSTED_CI_CAPACITY** is not erased by this local result.
Historical independent audit **BLOCKED** is separate and remains unchanged.
No merge, main/V1 baseline edit, release or deployment is authorized by this report.
