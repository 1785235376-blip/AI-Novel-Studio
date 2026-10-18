# Style navigation protection and no-write ORA inspection

2026-10-18 19:55 UTC. Product b02ef383287ea3f01ead4e50887caa1cfb172c48,
base 1d6a17f024dca193167b1eff30b73436b7c2ec5d.

## Style DNA navigation

The original App now coordinates save/discard/cancel before destructive module,
panel, project, search, task and interop navigation. It holds an editor ownership
ticket, not another copy of the draft. Verified saves and current revisions are
required; cancel suppresses late navigation without pretending to cancel remote
persistence. In-flight writes disable discard.

Context retirement and batched A→B→A changes quarantine/remount the original
editor. Original manuscript checks remain. CreativeWorkspace return and module
switch preserve its own guard, show the Style confirmation outside hidden NOVEL
content, and synchronously recheck the approved creative input/operation snapshot
at final exit. New creative edits while the Style prompt/save waits keep the
workspace open and require a fresh explicit request. No router/history/global
click interception was added.

Independent review identified and corrected unguarded Creative return, batched
identity retirement, and the nested-confirmation newer-edit race. Tests reproduce
these cases through the actual App. Browser/visual verification remains blocked.

## Pure ORA preview only

A new pure parser returns bounded canonical raster layers, a recomposed PNG and
explicit losses. It writes no files, Assets, receipts, projects or grants, and is
not mounted behind an upload route. Central-directory count is checked before ZIP
allocation; inflated bytes/member count/path/case collision/CRC and compression
bounds apply. XML is bounded and rejects DTD/entities/unsupported structure.
PNG headers/CRC/decompressed work are checked before Pillow, ancillary metadata
is removed and unsupported animation/color semantics rejected.

Order, integer opacity, visibility and offsets recompose from layer pixels.
Archived merged preview and sidecars cannot establish approval or provenance.
Report states sidecar_trust=NONE, approval_imported=false, origin_verified=false.
This profile supports a flat raster subset; unsupported semantics are rejected.
ZIP64 directory support is excluded; no broader per-entry ZIP64 claim is made.

Staging/review/page attachment/recovery and target-application re-edit roundtrip
remain absent. No current Comic layer or native text ownership is replaced.

## Evidence and boundaries

- Integrated navigation: 71 passing tests in five files plus 96 passing tests in
  seven separate original-regression files. TypeScript, Vite and token guard pass.
  The initial filter also named an absent author-task path; the actual original
  AppAuthorTaskNavigation suite was separately run and is included in the 96.
- Isolated final navigation suite: 133 passing tests, retained log; overlaps the
  integrated coverage and is not summed.
- Integrated parser/layer File checks: 78 pass, one existing verified-font skip,
  eight unrelated PG variants deselected.
- PUBLIC package and catalog: six pass; 2445 operations, none added or removed.
  Fingerprint 4490059fd55b50fb2e1c79f3f4272425bc971b42ae9010f23000d1763603186b.
- No database mutation exists in this parser/UI-only slice; no new PG run is
  claimed. Existing persisted Comic owners were not modified.
- Final source-path comparison is recorded in
  navigation-ora-committed-source-verification.json.
- Original large frontend chunk warnings remain. No live model, paid API, Windows
  or target-application acceptance occurred. Full DIF-09/IMAGE-COMIC-15 are open.
