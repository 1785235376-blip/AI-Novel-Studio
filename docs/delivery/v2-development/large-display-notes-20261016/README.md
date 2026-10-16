# Persisted large display-note slice

## Scope and preserved budgets

The original graph definition now admits at most 1024 display-only notes in its existing `presentation.notes` field. Notes still contain only `id`, plain `text` and `position`. This establishes meaningful persisted text display items, not 1000 media/reference/execution nodes. No new store, collection, endpoint or workflow engine was added.

All existing budgets remain: 256 Unicode code points per note, 12000 combined note code points, 96000 canonical UTF-8 bytes per graph definition, 2000000 bytes per original record, 8000000 per graph/run scope, 20 ordinary history entries, 16/24 execution nodes, 40 edges and existing execution/review gates. Existing absent-field serialization, schema versions and graph/execution digests remain unchanged. Legacy 128-note tests remain; the obsolete 129-is-over-limit assertion is updated transparently to 1025, with new 1000/1024 positive cases.

## Byte-estimate reasoning

The UI previously reserved 32 extra bytes for every number, rejecting valid large boards mainly because of 2000+ ordinary integer coordinates. The new fast path applies only to exact safe integers with absolute value at most 100000. Their JSON decimal spelling matches Python's; Pydantic float normalization adds exactly `.0` (two bytes). JavaScript negative zero becomes JSON `0` before reaching Python, then `0.0`. Integer-typed configuration fields add no suffix, so this reserve remains conservative for them as well.

All other numbers retain the previous 32-byte reserve. No attempt is made to exactly predict arbitrary JS/Python float formatting. Shared wire fixtures exercise signed zero, integer bounds, positive/negative exponents, subnormals, long fractions, Chinese/emoji and JSON escapes. Frontend tests separately cover safe/unsafe integers outside the fast path. The original server canonical limit remains authoritative. Exact frontend admission-estimate and exact Python canonical tests cover 96000 accepted and the next byte rejected without trimming source text.

## Rendering and interaction

- A large board uses a 20-result searchable note directory instead of creating 1024 native select options. Keyboard arrows/page keys and explicit selection are supported; IME confirmation is not mistaken for selection.
- Card rendering is capped at 128 for measured overlap as well as unknown initial layout. A selected or dragged note is retained within that cap. The original saved note list is never truncated.
- The untransformed note editor reports exact candidate, drawn and omitted counts when the cap applies. Selecting a note exposes its original editor; search does not silently move the camera or mutate the graph.
- Search/page state does not replace the selected editor or its IME ownership guard. Existing note authoring, undo/save owner and graph recovery format are retained. The execution-node display projection was not changed.

## Evidence

Initial focused frontend selection: 243 passed in five files, including all 96 original GraphCanvas tests. This initial result preceded the final added exact frontend byte-boundary case; independent final verification is recorded below.

Initial ordinary File selection: 87 passed, 4 PostgreSQL cases deselected (`../large-notes-file.json`). It includes real original-owner create/save/get/reconstructed-store reopen for 1000 and 1024 distinct concise Chinese labels, exact prior snapshot history, CAS refusal, legacy graph digest restoration and unchanged execution digest/no execution collection. A separate 1000-note case fills the original 20-entry history budget and proves a further save fails atomically without modifying the saved row. Exact canonical-byte and number-fixture cases also pass. That initial receipt honestly reports concurrent source changes: only the other worker's `AIDirectorReopen.test.tsx` changed relative to its captured source hashes; note implementation stayed unchanged. The final stable-tree receipt is recorded separately.

The tests use synthetic authored text and the real File graph owner, with separate mocked-transport/component checks. Browser rendering, device heap/latency thresholds and PostgreSQL are not established by these results. Existing geometry-only 1000/1200-object tests remain separate evidence; they are not substituted for persistence. The prior own-cloud browser socket block was not retried. No models, dependency installation, lifecycle/security candidate, hosted CI or publication were run.

## Final stable-source verification

- Independent frontend: **244 passed / 5 files**, unchanged default test budgets. Exact selection: `graphCanvasLargeNotes.test.ts`, `GraphCanvasLargeNotes.test.tsx`, `graphCanvasNotes.test.ts`, `GraphCanvas.test.tsx`, `studioGraphClient.test.ts`, with `--no-cache --maxWorkers=1 --minWorkers=1`. See `independent-ui.log`. No blocking scoped review defect was found.
- Final ordinary File selection: **87 passed / 4 PostgreSQL cases deselected**, exit 0. Receipt `../large-notes-file-final.json` records base `ab1d0f63ac18d5fa67984b232d45af232dacb2d0` and `sources_changed_during_check=false`; exact command and source hashes are retained there. The earlier source-changing result remains historical, rather than being rewritten.
- Exact changed-source SHA256s are recorded in `source-sha256.json`. The adjacent panel-preservation commit is separate; no director panel or security-owner source is part of this slice.
- Final TypeScript `--noEmit`, Vite production build and UI token guard all pass on the same frozen sources; logs are retained here. The existing large-bundle advisory remains. No browser check was attempted.
