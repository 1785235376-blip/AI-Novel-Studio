# DIF-02 partial: bounded Story fact downstream inspection

## Delivered scope

Frontend-only extension of the existing Story fact usage panel. An explicit,
read-only inspection selects one verified asset on the selected saved shot:

1. Re-read the original Creative document fact-use owner and compare the selected
   fact/use/current fact/document/scene/shot/asset pins and reason.
2. Read both original guarded production asset usage owners through the injected
   Studio transport and host read gate. No global transport or credential lookup.
3. Validate each response and require its exact asset ID/version/digest/kind to
   equal the selected fact-shot asset.
4. Re-read and revalidate the original fact-use path before publishing either
   consumer projection.

The path shows confirmed fact/use, document, scene, shot, formal image/video
asset, and saved Graph node or Timeline track/clip identities with versions and
64-character digests. Same-ID consumer pins from another asset snapshot are
explicitly separate from exact matching consumers. Existing stale fact blockers
remain visible; inspection does not approve or rebuild anything.

## Safety and bounds

- Shared asset usage validators and evidence renderer extracted without changing
  the existing asset-only interaction. Validation additionally rejects wrong
  owner-specific fields, non-asset-reference Graph definitions, conflicting pins
  for one consumer document, and more than 25 distinct documents.
- Existing owner bounds remain 25 documents and 200 usage rows per owner; no
  pagination, discovery expansion, recursive traversal, or inferred dependency.
- Fact impact response validation rejects duplicate use/asset identities,
  more than 200 uses, and more than two formal shot asset bindings.
- Any owner denial, malformed response, pin drift, or failed fact revalidation
  clears the whole assembled observation. A successful sibling cannot survive.
- Monotonic component generations and request identities fence transport,
  project, branch/session identity, selected target, admission, enabled state,
  single-asset selection A→B→A, late callbacks, and unmount.
- Reads are explicit, including reinspection; no mutations, model/run requests,
  owner writes, automatic refresh, or automatic regeneration are introduced.

## Evidence and validation

Worktree: `/workspace/shared/fact-downstream`, based on `01e84594`.
Raw evidence directory: `/workspace/shared/fact-downstream-evidence/`.

- `focused-tests.log`: 112 tests passed across new downstream tests (20),
  StoryFactUsagePanel (9), StoryboardWorkspacePanel (24), StudioUsagesPanel (53),
  and its existing integration suite (6).
- `types.log`: TypeScript check on the final slice (empty output on success).
- `tokens.log`: existing UI design-token guard.
- `build.log`: successful production TypeScript + Vite build, 2465 modules;
  existing large-chunk warning. The later defensive asset-ID type guard restores
  the original runtime check; the parent owns final combined-source build.
- `source-sha256.txt`: delivered frontend source and test SHA-256 hashes.
- `backend-sha256.txt` and `backend-diff.log`: original backend source hashes and
  zero backend changes relative to the baseline. No PostgreSQL/full backend run
  is needed or claimed for this frontend-only slice.

The sparse checkout includes frontend, app (read-only inspection), scripts,
existing test fixtures, and contracts. Shared node_modules is a non-staged
symlink; no dependencies or lockfiles were changed. No Comic, app/api,
workspace API, bootstrap, backend runtime, database, Release, paid API/model,
GPU, user computer, credential, push, main-branch, or reset operations occurred.

## Remaining limits

This is a bounded cross-owner read observation, not an atomic multi-owner
snapshot or semantic causation proof. A consumer may change after its owner read.
No semantic rebuild/execution or DIF-02 completion claim is made. Export,
resource cost, unrecorded dependencies, unsaved edits, inferred dependencies,
and recursive downstream impact remain unknown. Empty results never establish
that the fact has no impact. Owner limits can make coverage unavailable; row
truncation is displayed separately from empty and unavailable states.

## Recovery review (2026-10-19)

Recovered source commit `ab289bd0c0f45d172c8e241e7f9ef255bf2d4ffb` into
`/workspace/scratch/20a0022d2b33/fact-downstream-recovered`. The original
worktree was absent. Primary checkout remained at
`4816fcf863a38ab7f8060d5f2cfddc2106ffa0f1` during review; no primary edits,
reset, prune, backend changes, dependency installs, or external calls were made.

Review identified one concrete asynchronous dispatch gap: a host read gate can
hold its callback until after the chosen path has been retired. The original
publication guards prevented old results from appearing, but the deferred
callback could still dispatch an obsolete GET. All three inspection read stages
now check request lifetime inside the gated callback before dispatch. This adds
no endpoints, mutations, automatic reads, or UI changes.

Evidence: `/workspace/scratch/20a0022d2b33/fact-downstream-recovered-evidence/`.

- Original five focused suites: 112/112 passed (`baseline-tests.log`).
- Three new delayed-gate selection A→B→A regressions failed against original
  source, covering pre-fact, owner, and post-fact reads
  (`regression-before-fix.log`).
- Final same five suites: 115/115 passed (`final-tests.log`), including pure
  pin/validator coverage, mounted lifecycle coverage, original asset usage panel,
  its integration tests, Story fact panel, and Storyboard workspace.
- UI design-token guard passed (`tokens.log`); `git diff --check` passed.
- The first type check lacked fixture/contracts files in sparse checkout.
  Its diagnostics remain in `types-missing-sparse-inputs.log`; the existing
  repository inputs were then included without source edits. Final TypeScript
  `tsc -b` passed (`types.log`, empty successful output).
- Initial evidence directory creation under `/workspace/shared` failed because
  that mount is read-only; `setup-failure.log` preserves the failure.
- `source-sha256.txt` identifies reviewed source/test bytes; `backend-diff.log`
  confirms zero backend changes. No backend, browser/visual, or combined build
  success is claimed by this recovery review; parent owns combined build/archive.

The bounded cross-owner observation and UNKNOWN/empty/truncation limits above
remain unchanged. This is dispatch/publication lifecycle hardening, not an
atomic cross-owner snapshot or completion of DIF-02.
