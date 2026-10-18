# Opt-in model-led independent screenplay shot planning

Product checkpoint: 04cfb12fe24f451ddb341a0f29faee83e3a6d617. This is bounded development coverage for DIR-04 / SHOT-06, not full intelligent Director or V2 acceptance.

## Actual capability

An explicitly selected MULTI_SHOT_V1 option extends the existing independent screenplay model-v2 route with V3 preview/pending projections and INDEPENDENT_SCREENPLAY_SHOT_PLAN_V1 output. Existing omitted/null mode payload, legacy prompt/schema and V2 persisted preview/digest remain byte-compatible. Storyboard model-v1 and generic legacy human editing remain unchanged.

The first scope accepts a saved independent screenplay containing one or two scenes. The model can select one to three shots per scene, at most six total, from preview-frozen identity slots. Every scene must be covered; slot IDs are unique and ordered, selected note numbering is contiguous, and scene association/order cannot be invented or shifted. Allowed slots remain distinct from selected candidates. Required model rationale, sequence/duration reasoning and exact same-scene evidence or explicit speculation are validated. The model chooses the dramatic breakdown; deterministic code validates and binds it rather than pretending rule copying is model analysis.

The original configured LOCAL_ONLY, known-zero text route, Broker reservation, Job execution, durable terminal evidence, explicit pending publication, human review and Director DRAFT adoption remain the only owners. Actor/scope/incarnation, source version/digest, route fingerprints, reviewed digests, accounting and replay safeguards are retained. No new engine/provider/store is introduced. Existing DIRECTOR_NOTES derivation already turns the four adopted notes in the test into four associated Storyboard Shots, after which the existing explicit canvas return is available.

## Review and limits

Human review locks selected IDs, scene associations and order for V3 only, while preserving original content-edit semantics. Original sealed model candidates/provenance and candidate digest remain separately retained from the edited draft/reviewed-output digest. Human-cleared or defaulted fields are not automatically re-certified as grounded model analysis. Durations are estimates: the recorded model plan totals 26 seconds, while an explicit human edit changes it to 33 seconds.

Sources larger than two scenes fail with a smaller-source instruction; there is no silent splitting or truncation. The global 2048 output-token ceiling remains. Opt-in UI requests 2048; the old default remains 512. Six shots is a validation ceiling, not a guarantee every provider fits its output. Incomplete JSON/truncated output fails without publication or automatic retry. No live provider/model call, download, paid API, GPU or model-quality evaluation occurred during verification.

## Verified evidence

- Frozen original File lifecycle/parser/HTTP tests: 53 passed, 27 PG variants deselected. This includes one original Job/reservation, terminal, restart, pending reconciliation, human edit, one Director DRAFT, four real derived Shot associations, unchanged source and replay refusal.
- Real PostgreSQL 17.11, UTF8, OID 16384: 27 source/proposal/parser cases passed; exact row-hash multisets across 14 tables match, server stopped. This does not certify the full model Job lifecycle on PostgreSQL, which remains NOT_RUN.
- Root frontend: 150 tests in 9 suites, full TypeScript/Vite production build and token guard passed. Actual captured V3 HTTP fixtures decode through the real client; candidate/draft/derived-board links are checked. These are mounted synthetic client tests, not browser or live model acceptance.
- PUBLIC wheel/catalog: final 6 passed. Catalog remains 2521 operations, fingerprint 2cffd00d93b3d5e30677ee594086dcec21e0288b90175587a098fca316ba7cd1. Initial PUBLIC check caught the new contract Markdown missing from docker_files; only that exact standard contract path was added. Original closure checks were not weakened. Failure and final success are retained.
- All four frozen File, PG, final PUBLIC and frontend receipts match their 3190 recorded source paths. No runtime/source drift occurred during those final checks. Existing large-chunk warnings remain, not a performance acceptance.

The wider legacy File suite passed 125 but recorded overlapping edits; it is retained as diagnostic/overlapping evidence, not summed with the frozen final count. Earlier sparse-import/basetemp failures and an incorrect flattened-ancestry test expectation are preserved. Original derive correctly stores Board→Director→Screenplay direct-parent ancestry; implementation was not changed to satisfy the mistaken assertion. Independent frontend review passed 115; the author's final 116 adds one V2 generic-edit regression with identical runtime hashes. Counts overlap the root run.

## Remaining acceptance and delivery

Real model usefulness/token-fit, browser/geometry, native Windows, full PostgreSQL model lifecycle and the complete original-plus-extended V2 release gates remain open. A historical Storyboard rule-proposal document now explicitly labels its old model-support restrictions as historical; old test evidence remains intact.

Previous source 41a3c14d is verified at archive c7572d018c931d92f474e6bfe83d7f860811b25d, parent 8c789eae: 14 files / 4,305,772 bytes. Archives are prerequisite-bound Git bundles; main/PR source heads and releases are unchanged.
