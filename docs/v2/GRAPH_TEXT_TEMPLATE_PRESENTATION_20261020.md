# GRAPH-09: portable text-template visual authoring slice

Base: `c40aec6d7ccf5162bef7a2a054ff45b6baf2b13b`, product tree
`d1e9a1da44cc6beca2fa8daf6fb0e0a719c5b704`. This slice is implemented
and locally verified; it does not mark the whole GRAPH-09 requirement accepted.
No remote push, main merge, Release, provider/model execution or live Host
acceptance is part of this slice.

## Requirement and observed gap

The source requirement is GRAPH-09 in
`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md` (line 141), indexed by
`docs/v2/V2_REQUIREMENTS_LEDGER_20261019_R2.json`. Its historical PARTIAL status
is not a current acceptance result. At the pinned base, the existing
`graphTextTemplates.ts` exporter deliberately discarded all presentation, and
the original tool told authors that groups and notes were excluded. A text
template round trip therefore lost author visual organization and notes.

## Result and compatibility

- Annotated text graphs export as `poemseed-text-graph-template/2`, carrying
  only original `presentation.groups` and `presentation.notes`. Parent/member
  links and Unicode multiline note text survive the round trip. The existing
  `/1` format remains accepted; unannotated graphs continue exporting `/1`.
  Earlier readers deliberately reject `/2` rather than silently losing its
  author content.
- Only graph schemas 1 and 2 are portable. The explicit schema guard prevents
  broader local recovery support for schemas 3–7 from widening this contract.
  Asset/source bindings, permissions, approvals, execution/cache receipts,
  graph comments and view preferences do not travel with a template.
- Original `graphSelectionCopy` owns node/edge planning, compatibility and
  placement. The template adapter maps visual group members and parents onto
  those copied nodes and offsets notes with the same delta. Every new visual
  identifier is fresh and checked against source, target and generated IDs.
  A collision or out-of-bounds note rejects the entire plan; no clamping or
  partial application changes the author's spatial relationship.
- Target content, including its existing groups, notes, graph comment and view
  settings, is preserved. The original text-graph node cap (16), catalog edge
  and byte limits, 24-group cap, 1,024-note cap, 256 Unicode characters per
  note, 12,000 total note characters and +/-100,000 coordinate bounds remain.
  The portable file cap remains 110,000 bytes and final graph cap 96,000 bytes.
- The original single-use consent, file ticket, current-owner/target/catalog
  fence, disabled/busy state, late-result and stale-callback behavior remain
  in `GraphTextTemplateTools`. One original controller `change()` records
  the whole addition; one original undo/redo removes/restores it, including
  visual identifiers. No automatic Save or run was added. Original Save is
  still the authoritative persist/permission check.

No graph engine, controller, shared copy helper, CSS, AppShell, DSH source or
`packaging/public-build.json` was changed. The existing same-graph
`graphVisualGroupCopy` remains its original owner; this adapter handles a whole
portable template and notes without changing that feature's selection rules.

## Verification and limits

Evidence is external to source control in the executor workspace:
`graph-template-presentation-evidence-20261020` (sibling of this worktree).
It contains raw command/exit records, logs, browser fixtures/screenshots,
the final patch and incremental bundle. The recovery evidence is separately
under `c40-independent-recovery-20261020`.

- Targeted Vitest: 4 files, **57 passed** (31 template, 8 UI consent/fence,
  1 real-controller integration, 17 unchanged copy-helper tests). This covers
  nested group remapping, notes-only/groups-only schema2 export, target
  preservation, extra authority fields, schema rejection, ID collision,
  note count/text/coordinate bounds and realistic final-byte overflow.
- The byte test uses the unchanged 96,000-byte catalog cap: node-only import
  fits, adding the template's visual content rejects atomically. It does not
  widen or cast a fixed catalog limit. The full final definition still passes
  through the original draft decoder when within the byte cap.
- `tsc -b`: PASS. Serial `vite build`: PASS, retaining its large-chunk warning.
  Original UI token guard: PASS (52 files). `git diff --check`: PASS.
- Controlled Playwright checks at 1366x768, 1440x900 and 1920x1080: PASS.
  Original AppShell, GraphCanvas, template tool and controller render against
  a static client. Font readiness and reduced motion are applied. Preview
  text fits without horizontal overflow; confirmation, hierarchy, note text,
  fresh node IDs and original undo/redo are checked. Browser Save/run calls
  and external requests are all zero. These are component checks, not live
  application or Windows packaged acceptance. Canonical NOVEL reference and
  representative real React renders were reviewed; no visual baseline updated.

Raw earlier failures were retained: the initial RED run had 9 failures / 18
passes; the first typecheck found two invalid test-only literal limits; a
real-limit fixture was initially rejected by the decoder's existing byte cap
before the adapter's clearer byte error. Fixtures now use valid source and
catalog limits, and the adapter reports its byte error before the unchanged
decoder. A runner invocation initially used a wrong relative path and did not
start TypeScript. A read-only SSR diagnosis also emitted Vite shutdown scan
warnings; it is not counted as a passing acceptance test.

Not run: real Host/PG persistence, live provider discovery/model execution,
packaged Windows E2E, full test suite, release build/install and GitHub Actions.
The separate zero-step Actions failure is unresolved. Browser and integration
clients are static/mocked; the integration Save assertion proves payload
plumbing only. DSH delivery review and Hermia packaging closure are separate
lanes and are not accepted by this evidence.
