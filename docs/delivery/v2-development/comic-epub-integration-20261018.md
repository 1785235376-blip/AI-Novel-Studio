# Fixed-layout EPUB reading-copy integration

Product checkpoint: 95a62f57d3a84ae7b74806bd850ac3022e309990. IMAGE-COMIC-18 and full V2 remain PARTIAL / NOT ACCEPTED.

## Actual implementation

Comic publication now creates an actual fixed-layout EPUB 3 raster reading copy, not a renamed generic ZIP. It contains the first exact uncompressed mimetype member, container, OPF manifest/spine, escaped XHTML navigation/pages, local original PNGs, per-page viewports, and fixed-layout metadata. Language must be explicitly selected as und (unspecified). No author, ISBN or language is inferred. Saved page order is preserved; declared LTR/RTL direction does not reorder panels.

Original book/page ownership, current approvals/source/privacy, scope/incarnation, renderer, cumulative budgets and the final post-serialization authorization check remain authoritative. There is no new engine, store, automatic approval or external resource/script. XML-invalid metadata and whitespace-only XHTML titles fail before serialization. Existing CBZ/PDF/JPEG/WebP bodies and identities remain compatible.

The UI explicitly discloses raster-only, unsearchable/uneditable text, limited accessibility and unverified readers. Its 64 MiB output cap uses a conservative reservation of aggregate pixels × 4 + 65,536 bytes per page + metadata + 65,536 bytes. This can reject a book whose eventual compressed output would be smaller. The 100-page structural limit does not promise 100 full-resolution pages. CBZ/PDF downloads also now opt into the existing per-call bounded streaming helper; unrelated media limits are unchanged.

## Verification and source reconciliation

- Builder backend: 326 passed, 309 PG parameters deselected, zero skips, including real pinned CJK and existing formats. The whole-source receipt changed only because a parallel frontend test changed. All 1,501 recorded non-frontend source hashes reconcile exactly to the frozen backend. An unnecessary repeat was stopped with exit 130 and recorded as canceled, not represented as a successful run.
- Frontend: 369 tests passed with unchanged source, plus full types/build/token evidence. All 1,639 recorded frontend inputs match integration. The exact production build was copied and hash-verified into an owned runtime snapshot rather than rebuilding unchanged source again.
- Root real PostgreSQL: 88 passed, 96 non-PG cases deselected, with new EPUB and focused unchanged reading-format compatibility. Existing UTF8 PostgreSQL 17.11 / OID16384 reused; exact hashes across 14 tables match; server stopped.
- PUBLIC wheel/catalog: 6 passed. Catalog 2513 operations, fingerprint 88ae1e6ed1b0417fc131b6edf632bbd49254ea56f78dacdf4d558738f52b68b4. Private backend exclusion remains enforced.
- Final PG/PUBLIC receipts match all 3,162 unchanged integrated source files.

Independent backend probes and review checked ZIP/XML references, escaping, invalid controls, metadata bounds, order, directions and unchanged legacy method structure. Its 85-pass focused run had one unavailable-font skip; that is distinct from the builder and root pinned-CJK execution. Independent frontend review passed 321 focused cases. Counts overlap and are not additive.

## Standards and acceptance boundary

The independent review cross-checked inspected packaging, metadata, navigation and fixed-layout structures against [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/), unspecified language against [RFC 5646](https://www.rfc-editor.org/rfc/rfc5646.html), and the fixed whitespace-only title defect against the [HTML title content model](https://html.spec.whatwg.org/multipage/semantics.html#the-title-element).

No installed EPUBCheck was located in the searched environment. These are structural/code/codec tests, not formal EPUBCheck, real reading-system, accessibility, browser, native Windows or print certification. Each exported artifact retains those limitations. Initial fixture and ZIP cleanup failures, final passes, source reconciliation and the canceled-repeat disclosure remain preserved.

## Original security priority and continuing work

A separate read-only reconciliation confirms the original same-public-ID permission inheritance fix has real retained File/PG execution evidence whose security-owner/test bytes match the inspected current source. See project-retirement-evidence-reconciliation-20261018.md for exact receipts and qualifications. It does not invent complete persisted snapshots or an exact-current whole-tree security rerun.

Storage approached exhaustion during verification. Only tracked historical documentation was removed from three completed sparse worktree checkouts; all Git objects, unique files and untracked evidence remained, and before/after worktree statuses matched. Approximately 7 GiB became available. No user project, source history or unique report was deleted.

Previous source 2997fda0 is independently archived as c4b15e8bced83e457419dfb68166f3c388f66e98, exact parent a946bafd: 14 artifacts / 5,247,349 bytes. Archive bundles do not update main/PR source heads and are not releases. A separately scoped assetless native-author archive roundtrip is now being implemented under original Comic owners; it is not yet integrated and will not claim asset-preserving or full native-project restoration.
