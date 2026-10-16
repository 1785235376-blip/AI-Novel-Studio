# B02 authored-definition history

Baseline: `9b027fde2716ff34b37acdf1bd83eb803841ad3c` on
`work/dot-director-integration-20261016`. This slice extends the original
declarative-agents service, router and mounted authoring panel. It adds no store,
execution engine, transport, permission or automatic execution.

## Read and adoption boundary

- Both existing `/api` and `/api/v1` router mounts expose
  `GET /novels/{nid}/experimental/declarative-agents/definitions/{rid}/history`
  and the exact historical-version detail route `.../history/{version}`.
- The original feature, actor and scope checks run before and after each read.
  The original owner check and scoped store remain authoritative. Responses are
  `Cache-Control: no-store`.
- Metadata pages contain at most 20 historical versions, newest first, using
  exclusive `before_version` pagination. The response is capped at 65,536 UTF-8
  bytes. Items contain only version, title, definition digest and update time.
- Exact-version detail returns the authored definition and identity metadata
  only. It does not read or expand chapters, referenced resources, model routes,
  run snapshots, captured inputs or outputs. The existing 128,000-byte package
  constant bounds the entire detail response; this is a history-read limit, not
  a claim that existing saves enforced that total-byte limit.
- Unsupported or oversized historical definitions remain stored, but cannot be
  restored through this new editor path. No bytes are repaired or truncated.
  Canonical raw shapes must already satisfy the current editable projection;
  only the documented absent optional `capability_requirements` and
  `runtime_requirement` declarations are accepted without adding them to the
  response. Rejected detail does not remove metadata or change the current
  saved definition.
- Historical selection only fills the editable draft. Saving remains an
  explicit existing PUT with the current saved version as its CAS base. A
  restored v1 saved over v2 creates v3; old run approval/execution remains stale.
- Historical candidates and discard confirmations are retired on newer edits,
  selection/client changes or detected current-version/digest drift. Dirty
  current-definition reload offers explicit cancel/confirm; cancel retains the
  draft and its CAS base. Confirm only loads the selected saved definition.

## Verification receipts

- Initial environment attempt, before collection:
  `python -B -m pytest -q tests/test_declarative_definition_history.py -m file_backend_only --basetemp=.runtime/definition-history/red -o cache_dir=.runtime/definition-history/cache`.
  Exit 1, `No module named pytest`. This is the attested failure, not a product
  test result; no interpreter path is inferred from it.
- `definition-history-first.json` / `.log`: original runner with the verified
  Python 3.12.14 interpreter; 14 passed, 14 deselected, stable source snapshot.
- `definition-history-final.json` / `.log`: expanded ordinary File/API,
  template, SDK and comic selection; 102 passed, 93 PostgreSQL cases deselected,
  one existing Starlette/httpx deprecation warning, stable source snapshot.
  This run precedes the final compatibility-copy and metadata-preservation
  assertion addition; final acceptance is recorded separately.
- `definition-history-acceptance.json` / `.log`: final four-file backend
  selection, `-m 'not postgres_backend_only'`; 102 passed, 93 deselected, one
  existing Starlette/httpx deprecation warning. Both API mounts, real File
  persistence/reopen and actual scope/actor/feature checks are exercised.
- `definition-history-ui-final.json` / `.log`: 24 passed in two component files
  (16 history tests and 8 existing panel tests), no-cache, one worker. The
  independent reviewer also obtained 24/24 on these frozen sources.
- `workflow-history-shared-build.json` / `.log`: TypeScript `tsc -b --pretty
  false` and Vite production build passed. The existing large-chunk warning
  remains. This checks the combined B02/B10 frontend source set.
- `workflow-history-shared-tokens.json` / `.log`: token guard passed, 52 files.

All four final receipts report `sources_changed_during_check: false`. Their
complete 2,448-file source hash maps match each other and the final working
source set. Backend/UI receipts record HEAD `9b027fde2716ff34b37acdf1bd83eb803841ad3c`.
The B10 owner committed already-frozen B10 source and its evidence as
`a07f12ece793d5474995de5b7194240cae777441` while the shared build was running;
no source bytes changed during that run. The build receipt records the later
HEAD at completion, and the subsequent token receipt records that same HEAD.
The build did **not** start on the later SHA. Commit movement is not presented
as a clean-tree or stable-HEAD run; unchanged source hashes are the binding.

Raw-log formatting exception: unrestricted `git diff --cached --check` exited 2
with `docs/delivery/v2-development/definition-history-ui-final.log:15: new blank line at EOF.`
The exact runner log bytes and recorded hash were retained. The separate
source/documentation whitespace check, excluding raw `*.log` captures, passed.
The unrestricted check is not claimed as passing.

The interpreter is borrowed only as an installed executable from the adjacent
worktree. All selected tests and application sources are from this integration
worktree. The original runner creates an owned `.runtime/v2-checks/` profile,
uses explicit pytest temporary/cache paths, disables cloud/model access and
removes inherited provider credentials.

Browser/Playwright visual and shell-geometry checks are **NOT_RUN** because the
prior socket restriction remains unresolved. Component tests, real in-process
File/API checks, TypeScript/build and token validation are the scoped acceptance
path. No paid provider, user-machine operation, dependency installation or push
is part of this slice. PostgreSQL variants are deselected, not passed.
