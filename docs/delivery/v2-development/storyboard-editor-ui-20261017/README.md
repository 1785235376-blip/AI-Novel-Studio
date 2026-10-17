# Exact storyboard editor handoff: bounded verification

Source base: `93bc8b49502cdc388688143c9d830449c62d75e6`. These are local,
uncommitted implementation receipts, not a new commit or release claim.

## Latest primary result

R4 passed **24 suites / 258 tests**, with one worker, no cache, and default
Vitest timeouts. Forced `tsc -b --force`, `vite build`, and the existing UI token
guard (52 files) passed. Build emitted its chunk-size warning. `git diff --check`
also passed. All are bounded jsdom/mock-transport checks, not browser E2E.

Correct repository-root R4 manifests include 10,009 tracked/untracked regular
files, excluding ignored outputs and the dependency symlink. Before and after
are byte-identical. These bracket execution before this delivery documentation
was added; they do not claim the later documentation was in that run.
`evidence-index.json` records byte lengths and SHA256 for each byte-exact raw
copy. The empty R4 typecheck log reflects successful silent TypeScript output.

Separate [File-owner R2 evidence](../storyboard-editor-file-r2.json) passed
**10 tests, 7 PostgreSQL cases deselected**. It includes exact edited storyboard
persistence after a fresh File-owner restart, unchanged source documents, and
stale original Graph evidence. Do not combine UI and File checks into an E2E
claim or count repeated runs as additional unique coverage.

## Retained failures and corrections

- R1: 217 passed / 6 failed in 20 suites. New-test timing/scoping/error/UNKNOWN
  assertions were corrected. Original console selection-key semantics were
  restored; new handoff-only authority retirement remains separate.
- R1 setup emitted `sha256sum: node_modules: Is a directory` while operating
  from frontend. The retained `.sha256` and after-check log cover recorded
  frontend regular files only. That setup was not a successful full-root
  snapshot. The setup stderr was observed but was not captured in a separate
  raw log; this qualification preserves the diagnostic without fabricating it.
- R2: 222 passed / 1 failed in 20 suites. Correct full-root manifests are equal
  (10,008 regular files). The protected screenplay option-label test still
  failed, expecting `原剧本 · v2` rather than `原剧本 · 剧本 · v2`.
- The isolated original failing test was reproduced in the clean sibling
  `studio-storyboard-model` at the same base HEAD. Its raw baseline log is
  retained. HEAD/status were inspected before execution: only the preexisting
  untracked dependency symlink was present. This established the label failure
  as inherited. The original SCREENPLAY label was restored, retaining the mode
  cue only for STORYBOARD, with a new test covering both. No protected test was
  edited.
- R3: all 258 tests in 24 suites passed, and correct root manifests were equal
  (10,009 regular files). Forced TypeScript then failed on a new intentionally
  mocked controller/view test fixture's direct type assertion (TS2352). Build
  and token checks were not run in R3. The new fixture alone was corrected to
  assert through `unknown`; runtime assertions and product code were unchanged.
- R4: the full 24-suite selection and all subsequent checks passed as above.

[Independent review](../storyboard-editor-independent-review.json) approved the
scoped source: 99 UI tests in 8 suites (53 new + 46 original), and 3 File tests
with 2 PostgreSQL cases deselected. These are overlapping subsets, not additional
unique counts. Its 2,536-file source brackets/current closure match, with all
1,279 protected files unchanged. Raw independent receipts are beside that report.
Browser,
visual/file-picker acceptance, live HTTP/socket, PostgreSQL, target-platform,
provider/model quality, and full-release acceptance are NOT_RUN. Existing gates
remain open. No stage, commit, push, merge, or release is claimed.

Current-root startup/origin proof and probe script are retained byte-exact in
`origin/`, together with the initial static-review report and independent origin
proof. Their byte lengths and SHA256 values are indexed in `evidence-index.json`.
