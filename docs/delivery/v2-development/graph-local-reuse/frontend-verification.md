# Graph reviewed-local-dependency reuse: frontend verification

Verified on 2026-10-18 in the isolated `graph-local-cache` worktree. No service, paid/model/media call, commit, or push was performed. The frontend source was frozen after the independent review fixes.

## Results

- Focused regression corpus: **409 tests passed across 13 files**.
- Full frontend TypeScript check: **passed**.
- UI design-token guard: **passed, 52 files checked**.
- `git diff --check`: **passed**.
- Browser visual/geometry verification: **blocked; no pass claimed**.

The corpus covers default/false request-byte compatibility, strict optional boolean validation, whole-graph schema-1 eligibility (including disabled/unselected nonlocal nodes), opt-in request identity, explicit uncertain retry, authority/dirty/busy/preflight guards, independent human review, truthful receipt mode, and existing graph/model/media/text-asset transport and revocation behavior. Review fixes include consent invalidation on policy reset and retained-callback retirement across mode changes and ABA transitions.

## Exact verification commands

Working directory for all commands below: `frontend/` in this worktree. Existing dependencies were reused through an untracked `frontend/node_modules` symlink to the existing `studio-usability/frontend/node_modules`; that symlink is not a deliverable.

```sh
node node_modules/typescript/bin/tsc --noEmit
node ../scripts/check_ui_design_tokens.mjs
git diff --check
node node_modules/vitest/vitest.mjs run \
  src/creative/GraphRunPanel.test.tsx \
  src/creative/GraphReadRevocation.regression.test.tsx \
  src/creative/GraphModelExecutionPanel.test.tsx \
  src/creative/GraphTextAssetPanel.test.tsx \
  src/creative/studioGraphClient.test.ts \
  src/creative/studioGraphModelClient.test.ts \
  src/creative/studioGraphTextAssetClient.test.ts \
  src/creative/studioGraphTextExecutionReceiptClient.test.ts \
  src/creative/studioGraphTransportForwarding.test.ts \
  src/creative/studioGraphDirectorClient.test.ts \
  src/creative/studioGraphVideoContract.phase4.test.ts \
  src/creative/studioImageGraphClient.test.ts \
  src/creative/studioProductionGraphClient.test.ts
```

The final identical rerun captures stdout/stderr using `set -o pipefail` and `tee` into these sibling evidence files:

- `frontend-typecheck.log` (explicit process exit code; TypeScript is silent on success)
- `frontend-tokens.log`
- `frontend-diff-check.log` (explicit process exit code)
- `frontend-vitest.log` (per-file counts and aggregate results)

### Earlier failed checks and corrections

The initial typecheck failed with a new test callback returning `Promise<StudioGraphRun>` instead of `Awaitable<void>` (`TS2345`, `studioGraphClient.test.ts`). The callback was made `async` and now awaits the request without returning the run. The initial and next typechecks also reported the sparse checkout's missing `contracts/local-interop/v1/protocol.ts` (`TS2307`) and resulting implicit-any errors in the existing interop consumer. Restoring the tracked `contracts` directory from the repository root resolved that environment-only issue. No unrelated source fixes were made. Subsequent full typechecks passed.

Those earlier typecheck diagnostics were retained only in execution-tool output, not captured as raw files. The four sibling logs above are the actual captured final rerun; they are not reconstructed earlier logs.

## Visual/geometry blocker

The repository UI skill, design system, protected-surface rules, canonical novel reference, and visual-baseline rules were read. No CSS, token, primitive, or shared AppShell changes were made.

An offline in-memory React/AppShell fixture was prepared with esbuild and Playwright, intended to check 1366×768, 1440×900, and 1920×1080 geometry plus keyboard opt-in and explicit creation. It did not start a web server or make external requests. The attempted command was:

```sh
node /tmp/graph-local-reuse-visual.mjs
```

The bundled Playwright browser was absent. Retrying with the existing `/usr/bin/chromium` failed before page creation with `socket() failed: Operation not permitted (1)`. The permitted execution escalation failed in the sandbox wrapper before browser startup due to a read-only filesystem error. Consequently no screenshot, geometry assertion, or browser acceptance result is asserted. Re-run the normal repository visual/geometry checks in a browser-enabled validation environment before claiming visual acceptance.

The three failed browser-launch outputs are retained only in execution-tool output; no raw browser log file was captured. This paragraph records the observed blockers and does not substitute for a successful visual result.
