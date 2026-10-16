# B09 bounded original branch comparison reading

Status: **PARTIAL**. Baseline `8ef05ff`; isolated branch `work/parallel-branch-review-20261016`. This slice adds a read-only view inside the already-mounted `BranchManuscriptPanel`, not a new branch/merge owner.

## Audit and implementation

Original `BranchManuscriptService.compare` already returns rich-block diff3 segments, exact source/target document references, preview digest, unresolved conflicts and desired document. Original proposals/manual confirmation/CAS/recovery and editor history were already implemented. The missing usability seam was that the differences were exposed only as raw JSON.

The new original-panel consumer displays:

- Exact current-branch and original-source chapter IDs, branch IDs (explicit null means mainline), versions, document digests and comparison digest. Missing identity/digest remains UNKNOWN.
- Original difference kinds, zero-based half-open baseline block ranges, baseline/source/fork text excerpts and full original rich-block JSON.
- Twenty-row pagination and an optional unchanged-block filter, preserving original segment indices and their manual choice identities.
- Per-side excerpts bounded to 600 Unicode codepoints and 512 visited nodes. Empty content, absent data, textless media and truncation remain distinct. No HTML/media is rendered from source text.
- Explicit limitations: this is a captured comparison, not proof of latest versions; plain text omits formatting, locks and embeds; the API does not separately provide the fork-base version. Root-attribute conflicts remain in the original manual-selection flow.

Changing an original manual conflict choice still clears the comparison; the next explicit original compare call supplies the next snapshot. The component adds no network calls or write controls. Chapter/editor navigation, unsaved inputs, proposals, review, apply, cancellation and UNKNOWN recovery retain their existing owners and semantics. No branch merge was performed outside existing mocked component tests.

## Verification

Commands and source hashes are recorded in the adjacent JSON. Focused mocked UI/pure tests cover original receipt display, original-index choices, filtering/pagination, root conflict guidance, malformed/prototype kind fallback, bounded Unicode/text-only extraction, original mounted compare flow, preservation of typed title and late identity-switch response rejection. Existing panel regressions and AppShell geometry are included: 32 passing tests. Forced TypeScript compilation and Vite build pass; Vite retains the existing large-chunk warning. Test discovery and the UI token guard pass. No CSS or protected shell/primitives changed.

Browser/visual screenshot/native IME/HTTP/File/PG/Windows/GPU/model/end-to-end/full RC were **NOT_RUN**. No claim of complete B09 or backend merge correctness is made. Public backend files and packaging are unchanged; PUBLIC package tests were not rerun for this display-only slice. P0 remains BLOCKED; release HOLD and Prompt Adoption disabled remain unchanged. No install, provider call, push, hosted CI, merge, tag, release, credentials or authority changes.

Tooling note: initial Vitest invocations used default caching against the existing dependency symlink and may have updated its shared cache. Subsequent/final tests use `--no-cache`; tracked changes and build outputs are isolated to this worktree.

## Remaining scope

Real rich-text visual review and browser accessibility acceptance, exact historical base-version receipt, larger full-project comparison, cross-owner historical navigation and complete branch recovery acceptance remain open. This view does not add a second history, acknowledgement store or merge engine. Parent review/cherry-pick is required before integration.
