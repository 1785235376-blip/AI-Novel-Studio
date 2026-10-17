# Positioned insertion collection inventory

Source checkpoint: `6ea323c087ac88ad280852b614c7bb54f4170dd2`.
Predecessor checkpoint: `e1e66cedeb7a140b6894850bc21a1e5ac7e06c16`.

Collection inventory only. This packet does not execute test bodies or claim passing coverage, browser acceptance or product completion. The independently reviewed implementation remains in the unchanged `docs/CANVAS_POSITIONED_INSERT_HANDOFF.md`.

The predecessor canonical manifest has SHA-256 `733c4625f0ef4b69c47574672bcbc7d8bd7d62c7cf1de2d336c438b4797a4eee`, 2,647 sources and 16,924 Python rows. Source scope is six modified frontend runtime files and three new UI test modules. Python row changes are derived from actual original-generator collection, not UI test totals.

Stages are strictly separated: original no-write collection and parent audit; owned candidate generation after approval and parent exact-byte audit; explicit byte promotion followed by a separate third no-write collection and final parent audit. The collector itself cannot promote canonical bytes. No approval report is authored by the inventory worker.

Fresh natural startup and actual unchanged-runner child-origin proofs use only the approved reconciliation interpreter, sanitized environment and stdlib-only PathFinder probe. All prior full row dictionaries, ordering and classifications, protected source entries, 11 frontend script/E2E companions, PUBLIC packaging, both frozen golden fixtures, frozen V1, original generator/runner, and existing tracked documentation bytes are guarded. Exact logs and source/Git bindings are retained.

Read-only checks from repository root:

    node docs/delivery/v2-development/canvas-insert-inventory-20261017/check.mjs review
    node docs/delivery/v2-development/canvas-insert-inventory-20261017/check.mjs candidate .runtime/canvas-insert-inventory/candidate-manifest-v2.json.gz
    node docs/delivery/v2-development/canvas-insert-inventory-20261017/check.mjs final

## Preparation correction

The initial metadata-preparation command hit Node's default 1 MiB subprocess buffer while listing the full Git tree. The preparation did not reach writing the documentation preservation map. The subsequent collector stopped on the missing map before any Python provenance or collection invocation; its exact error is retained in `preflight-incomplete-docs.log`. The metadata command was rerun with a 40 MiB buffer. No source, tests, existing documentation or canonical manifest were changed by this correction.

## Derived gate results

Initial no-write collection and owned candidate generation both passed their parent independent gates. Actual inventory has 2,650 sources and 16,924 Python rows, with zero new Python rows. All 16,924 predecessor row dictionaries, order and classifications are exact. There are 1,324 unchanged protected predecessor sources, 11 unchanged companion files and 8,584 byte-preserved existing tracked documentation files.

The approved candidate is 627,061 bytes, SHA-256 `992aa33f830f8c6a4dc15438942d21c5bf834af69c2969562efd55a850411e0b`. Following explicit parent authorization and a fresh predecessor digest check, those exact bytes were copied to canonical without recompression. The independent approval and byte-promotion receipt are retained. The separate third original no-write collection passed; the parent independently audited all three gates and approved final closure. All three raw collections are byte-identical, SHA-256 `b8b55ea25ed271890add0b077cdce56fefe08f546edf9604f5c752fdc230d4a2`. The packet index includes all six parent-authored audit records/check logs and external evidence dependencies. This closes collection inventory only.

PUBLIC remains SHA-256 `57f657057a391fa9ebdd8586fba62262ea6f3bb5fb1e2fe71f0c5ff27ad573be`. Original Graph/SCREENPLAY golden remains `640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac`; frozen audio omission golden remains `1aa9100e0d3622b6d5a99019b5a7f33aa60e94173a9c962dce0a500c3a63c2d5`.
