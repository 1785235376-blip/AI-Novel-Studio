# A09 saved relationship reference inspection and original asset navigation

Baseline `08571f794c42c4ef5785d358968d8b89c330e78b`. The containing local commit identifies delivery. A09 remains **PARTIAL**.

## Audit before implementation

The original AssetLibrary/Studio relationship owner already persists the seven descriptive relationship types with exact target kind/ID/version/digest, source CAS, reason and removal tombstones. `AssetRelationshipsPanel` already edits those declarations and displays a lazy project graph. Rebuilding that graph or a second asset store would duplicate existing work. The concrete missing seam was inspecting a saved pin against the currently readable reference directory, then opening an exact original asset through the existing selection owner.

`ProductionLineageService._project_asset` already projects parent assets, source chapters, declaration history version numbers, inherited media task/brief/shot metadata, integrity and recorded impact. Its parent projection returns **current** version/digest; history version numbers are not historical bodies. `WorkspaceRelationshipService.graph` returns current parent targets without the original lineage expected pin. This slice deliberately does not relabel those current values as historical evidence or synthesize a complete production graph.

Prompt Workspace already owns family/version/diff/history; Storyboard has collapsed read-only Prompt Adoption provenance and original shot/document/version/digest contracts. Production Prompt Adoption writes remain disabled. Timeline clips already persist exact source snapshots and use original explicit handoff/history/save. The relationship graph does not inventory all these references. No adoption reference, stale-source bypass, backend schema, permission or lifecycle change is introduced.

## Bounded workflow

1. Open an existing asset's optional relationships. Each readable saved relationship now displays its exact original pin and an explicit metadata comparison action.
2. The action rereads the original authorized directory for its kind. Only one matching kind/ID is accepted. Current version and digest are compared independently against the saved pin. Missing, deleted, ambiguous or failed reads cannot open a source; mismatch does not upgrade the pin. Chapter/screenplay inspection remains explicitly metadata-only because this seam has no exact historical editor/body contract.
3. For a matching asset, a separate open action passes the saved pin to the original workspace navigation guard. Unsaved inputs remain until the author explicitly chooses the existing discard confirmation; busy/UNKNOWN behavior is unchanged.
4. After any discard, a fresh original asset GET checks exact ID, project/branch, version, digest and deletion state before changing the original selection. Original transport and owner denial behavior remain authoritative. A mismatch retains the original selection; no alternate/latest source is selected. An epoch-bound exact-review mode temporarily closes both live asset browsers; the original AssetInspector may load its ordinary preview. Returning to current asset browsing is a separate explicit action with a current-versus-historical version notice. This prevents the browser's existing ID-only follow-on GET from silently presenting a newer detail as the pinned source. There is no automatic file export or new media reader.
5. Current-reference results are invalidated on client, target-pin and busy changes, including A→B→A. Original selection increments the existing form revision as well as its epoch, so a batched A→B→A selection still remounts the original editors even when React sees the same final asset object. Old promises and retained click handlers cannot reuse an earlier successful inspection after failure. Unmount aborts reads; original workspace identity/selection generations fence navigation.
6. The existing project graph now includes a filtered view of recorded direct incoming relationships for the selected asset, with explicit partial-inventory and absent-history warnings. Zero recorded edges does not mean zero downstream impact. This is a read-only projection, not an exhaustive impact analysis or a replacement graph.

No new owner/store/queue/API, source mutation, automatic regeneration, latest-version substitution, declaration save, approval or export is added by these actions. Existing relationship editing is unchanged.

## Verification

Commands, timestamps, exits, source/log/receipt hashes are indexed in `asset-lineage-reference-navigation-20261016.json`.

- 62 selected mocked UI tests: inspection/pin mismatch/missing/deleted/ambiguous/read failure, target/client/busy ABA, retained handlers, original dirty navigation and explicit discard, exact second owner read, original scope-denial surface, recorded incoming impact, original relationship edits/redaction, existing lineage/replay panels and PUBLIC placeholder.
- Four original nonsecurity File-owner cases: exact asset/chapter/screenplay pins persist and reopen without copying/editing source text; existing graph distinguishes original lineage from declared relationships. No new backend persistence contract needed.
- 30 PUBLIC tests; forced TypeScript/Vite, discovery, shared and scoped token checks, diff check and 487-file PUBLIC source closure.
- Initial failures are retained: array-shaped parameterized test data incorrectly spread into arguments; integration fixture omitted required relationship timestamp; original controlled AssetBrowser's second detail read and scope-denial behavior were initially asserted incorrectly. File fixture first rejected an unowned pytest temp path before its body; rerun used the established owned `.runtime` basetemp, without changing permissions. Independent review identified follow-on current-browser drift and source-selection ABA; exact-review mode and monotonic original form revision close those seams. The first ABA regression failed before that correction and is retained. Final evidence does not use superseded failures as passes.

## Remaining boundaries

Exact old asset bytes/history bodies, chapter/screenplay historical editor navigation, comprehensive Shot→Prompt→result→Timeline impact and actual full-chain quality remain open/NOT_RUN. Native browser/visual/accessibility/HTTP, PostgreSQL/P0/security lifecycle, Windows/GPU/provider/model quality and full RC are NOT_RUN. P0 remains BLOCKED, R3-GATE HOLD, production Prompt Adoption disabled. No user computer, browser workaround, provider call, paid service, push or hosted CI; CI cost is unknown. No main/merge/tag/release. Parent independent review and final SHA verification precede the next tracked slice.
