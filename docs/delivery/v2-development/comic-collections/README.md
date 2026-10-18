# Manual Comic book collections

Partial IMAGE-COMIC-02 delivery. This is a manual collection workflow over the original Comic owner, not a full layer editor or whole-book publishing implementation.

## Product scope

- Image → Comic retains its original page editor and adds book/chapter/page structure.
- Create/rename books and chapters; order chapters and pages; move pages between chapters; explicitly attach an existing independent page.
- Create a blank page or duplicate a saved page atomically with its chapter membership. Duplicates receive fresh page/panel/bubble IDs and DRAFT status; source bindings and omission-sensitive crop/artwork fields remain intact.
- Removing a page/chapter removes membership only. Underlying Comic records and Assets remain. Explicit prior structure revision restore creates a new book revision and recovers membership/order, without reverting page text, layout, or approval.
- The same original page can appear in multiple books. Editing it affects all references; duplication creates an independent copy.
- Bounds: 20 books per current actor/project incarnation, 20 chapters and 100 unique pages per book, 100 history entries, 8 MB current-actor/current-incarnation book metadata. No model, generation, queue, paid API, or asset promotion path.

## Original ownership and compatibility

`ComicLayoutsService` remains the owner. Pages stay in `comic_layouts_v2`; subordinate `comic_page_collections_v1` metadata is stored in the same original raw experimental scope document. No second project/Asset master/store, no Creative collection registry widening, no database migration.

Collection membership accepts only existing current-incarnation INDEPENDENT pages of the same project, exact branch/scope and actor. Adapted screenplay layouts keep their existing ungrouped editing/rendering/review behavior. Their documents, omission-sensitive serialization and review digests are not migrated.

All original Comic/Asset/Director flags and `domain.read`/`domain.write`/`domain.review` authority boundaries remain. The known IMAGE-only-versus-NOVEL-domain authorization gap is not changed by navigation or this feature.

## Atomicity, revision and privacy

- Structure save requires current book CAS and current version pins for every referenced page. Copy additionally requires the source page version. No force-save or automatic conflict overwrite.
- Page insertion/copy and book update share one raw scope transaction; no public nested save transaction.
- Original lock order is scope → Asset Python/workspace lock → original project lease, held through raw commit. Coherent book read projections reuse those locks and raw state. Mutation response projections are assembled inside the already-held lease before the final guard.
- Empty book reads return before the write-capable raw transaction, avoiding PostgreSQL insertion of missing scope rows.
- Only valid explicit creation may initialize the original File epoch marker. Reads, existing mutation, duplication, restoration, and imported historical rows cannot initialize or adopt a new epoch.
- Old epoch rows remain intact and invisible. Quotas exclude archived epochs and other actors. Stale book projections omit titles, chapter/page references/counts and history versions.
- Private conflict errors retain the existing bounded envelope and no-store/nosniff headers.
- Structure snapshots contain membership only; per-page content history/review remains with the existing page owner. A missing, stale, or unauthorized page blocks restoration instead of being silently rebound.

## UI integration boundaries

The collection tree consumes shared UI primitives and existing tokens inside `ComicLayoutsPanel`; the independent Studio shell, Studio transport and StudioComicPanel are unchanged. Dirty tree navigation and collection page navigation require save/discard. Original standalone-page navigation semantics remain compatible with existing tests. Async actions and retained callbacks are fenced by owner/editor generations and synchronous pending guards.

## Verification and limits

- `comic-collections-file-3.json/.log`: 100 passed, 86 PostgreSQL deselected, including new collection contracts and existing independent/legacy mounted Comic regressions.
- `comic-collections-postgres-2.json/.log`: 76 passed, 10 File-only skips, 100 deselected on real PostgreSQL 17.11. Exact before/after full rows in `novels` and `experimental_scope_documents` match (one preexisting row in each table retained). `comic-collections-postgres-2-cleanup.json` contains that proof.
- Existing UTF8 database `v2_recovered_ocr_export_20261018`, OID 16384, reused without creation/migrations. Runner stopped it. `comic-collections-postgres-stop-proof.json` independently verifies pg_ctl exit 3, TCP connection refused (111), and no PID file.
- `verify_postgres.py` is the exact latest snapshot/test/cleanup wrapper, executed by the original PostgreSQL runner. No ownership-blind cleanup was performed.
- `comic-collection-ui-frozen.json/.log`: 94 passed (13 new collection tests, 50 existing Comic regressions, 31 AppShell tests). New tests include actual ComicLayoutsPanel integration, parent dirty/busy/generation callbacks, CAS pins, reference privacy and stale callbacks.
- `comic-collection-ui-types-frozen.json/.log`: TypeScript noEmit PASS. Both frozen UI/type receipts report `sources_changed_during_check=false`. `comic-collection-ui-tokens.json/.log`: token guard PASS (52 files).
- `comic-collection-ui-visual.json/.log`: 15 existing visual/geometry cases attempted; all blocked before browser assertions by the missing pinned chromium_headless_shell-1234 executable. No screenshots accepted, browser installed, or baselines changed.
- Earlier UI failures are retained: missing URL API mocks in the new integration fixture and a combined bounds test timeout, subsequently corrected in the fixtures/tests. Product code was not relaxed to bypass failed contracts. First File run retained two test failures from assuming the shared mounted fixture had no preseeded manuscript; the assertion was corrected to verify original source records stay unchanged.

Independent static review identified and verified fixes for cross-epoch quota accounting and unlocked multi-page projection. Dedicated regressions exercise retained old/other-owner bytes, a concurrent invalidation writer blocked by coherent projection, and epoch replacement before projection.

Not included: layer editing, split/merge, chapter/book duplication, aggregate content snapshots/approval, permanent deletion, right-to-left or whole-book export, automatic layout/generation, or full IMAGE-COMIC acceptance. Browser screenshots/geometry require the existing Chromium executable; no browser installation, production build, baseline update, commit or push is authorized in this slice.

## Frozen handoff

`source-sha256.json` binds the eight owned product/test files. `backend-sha256.json` additionally records the backend freeze before the final UI runs; those four hashes still match. No changes to the Studio shell, shared experimental composition, Style DNA, World, project store or Asset owner were made by this slice. Concurrent work in those files belongs to other lanes. No commits or pushes performed.
