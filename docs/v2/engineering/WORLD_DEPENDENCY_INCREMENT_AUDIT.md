# Story-world dependency increment — audit and current slice status (round 3)

SPEC phase P1 requires Story Kernel (DIF-01) and Impact Engine (DIF-02) before semantic
cross-media dependency tracking can be verified end to end. This page audits what already
exists, what was implemented in the comic slice, and why the full semantic increment is
BLOCKED rather than faked.

## 1. Existing reusable owners (audited)

- Source lineage primitives: app/experimental/production_lineage.py + asset_lineage_v2 flag;
  tests/test_r4_production_lineage.py, tests/test_r4_change_impact.py,
  tests/test_r4_change_impact_mounted.py.
- Change-impact preview: app/experimental/change_impact.py / change_impact_api.py (impact
  listing over pinned versions; no automatic mutation).
- Graph/typed ports: app/creative/ graph owners; GraphFlow external tooling is not part of
  the product runtime.
- Comic page export now records panel_sources + asset_bindings and the page identity
  (source_mode, page number, reading direction) in its manifest: real provenance for comic
  deliverables.

## 2. Implemented this round (verifiable increment)

- Provenance of comic pages: every exported page carries the bound asset versions and
  source mode in manifest.json (tests/test_v2_comic_blank_edit_loop.py).
- Text-only edits are proven to keep the underlying panel image asset bytes/version
  unchanged; this is the minimal edit-without-regenerating-unrelated-assets guarantee
  required by DIF-04/IMAGE-COMIC-17 at page level.

## 3. Blocked / not implemented, with dependencies

- A Story Kernel fact/claim/event-time model with author adjudication and branch isolation
  (DIF-01) does not exist as a product owner; without it, semantic dependencies would be
  text/RAG matches, which SPEC explicitly forbids as a substitute.
- Therefore the end-to-end Text→Screenplay→Comic/Storyboard→Image→Video/Audio→Timeline
  impact analysis with source evidence, unaffected-asset proof and author decision record
  (DIF-02) is PLANNED, not INTEGRATION_VERIFIED.
- Dependencies for a future slice: DIF-01 typed fact/relation storage bound to existing
  text/world owners; Impact Engine preview over recorded source versions; author decision
  audit; no auto-delete/rewrite of approved historical assets.

## 4. Status

- B slice (story-world semantic dependency) = BLOCKED on DIF-01/DIF-02 product owners.
- A slice (comic basic edit loop) = implemented and verified (see
  evidence/20261019-r3/comic-blank-edit-loop.md).
- C slice (public/internal isolation) = build invariant checks implemented; internal
  deployment isolation BLOCKED (see EDITIONS_AND_BUILD_BOUNDARIES.md).
