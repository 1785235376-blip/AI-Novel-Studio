# Exact Director → original storyboard editor handoff

This is an explicit navigation slice in the existing independent IMAGE and VIDEO
workspaces. It reuses CreativeWorkspace and the same Creative document API. There
is one rendered AppShell and one active editor. The Graph controller is inactive
and its Director console is unmounted during the original storyboard session.
The module switcher stays on the originating module.

## User flow

1. Inspect a saved Director document and its source digest.
2. Explicitly derive a storyboard, or list related storyboards.
3. Inspect the exact storyboard export. A derive receipt alone has no digest and
   cannot enable Open. A board tied to a different Director pin cannot open.
4. Choose “在原分镜编辑器打开”. If there are unsaved inputs, the existing
   navigation confirmation requests consent first. Cancelling keeps inputs.
5. After consent, read capabilities and then export the exact target again.
   Verify target ID, mode, version, digest, document structure, and captured
   Director source ID/version/digest. There is no latest/sibling fallback.
6. Only a still-current successful preparation discards consented local inputs
   and mounts the original editor. The host commits an immutable cloned receipt;
   destination intake performs no second fallible admission read. This closes
   the gap where a second destination fetch could fail after discarding drafts.
7. Edit and explicitly Save. The original Creative.update request supplies the
   saved document's expected_version. Return uses the original dirty-exit consent.

## Authority and scope

Requests contain scalar pins and monotonic session tickets. They are not placed
in URLs, local storage, graph bindings, or a second document store. Retained
callbacks are fenced by source/client/selection/activity and host authority.
Destination intake bypasses ordinary first-document bootstrap and checks a fresh
request before replacing a clean target. Dirty, blocked, pending, stale, or
retired requests do not overwrite the current target. Session/store authority
loss is latched; an A→B→A identity transition does not revive old authority.

Reading an older sibling does not resolve an UNKNOWN derive. Opening never
creates another document, saves a graph, refreshes its pin, approves assets,
executes a job, or calls a model. The original graph pin can become stale after
an explicit storyboard edit and save; that is intentional.

## Verification boundary

Additive jsdom tests exercise real React navigation and controlled fetches,
including exact ID intake and original Save. They are not browser end-to-end
proof. The separate File-owner persistence test verifies re-opened data after an
explicit save, original source preservation, and stale old Graph evidence.
No live providers, credentials, PostgreSQL, browser sessions, or user computer
are involved in this slice. Existing protected tests and design tokens remain
unchanged.

## Latest bounded checkpoint — 2026-10-17

On source base `93bc8b49502cdc388688143c9d830449c62d75e6`, the primary final run
passed 258 UI checks in 24 suites, forced TypeScript, production build, and the
52-file token guard. Separate File-owner verification passed 10 tests with
7 PostgreSQL cases deselected. The final full-root 10,009-file snapshot remained
identical across execution. [Raw evidence and retained failures](delivery/v2-development/storyboard-editor-ui-20261017/README.md)
include the inherited SCREENPLAY label regression reproduced on the clean base,
its minimal label restoration, and the earlier new-fixture typecheck failure.
The first frontend-only snapshot setup diagnostic is explicitly qualified.
[Independent review](delivery/v2-development/storyboard-editor-independent-review.json)
approved the scoped source with 99 UI and 3 File passes (2 PostgreSQL
deselections), overlapping the primary selections. Its source/hash closure and
protected-file checks passed. No browser E2E or release gate is claimed.

## Raw evidence whitespace

The full staged whitespace check reports four trailing-whitespace lines in the original failed File-test traceback and six EOF blank lines in preserved Vitest/baseline logs. These raw bytes are retained. The separate source/test/documentation whitespace check excluding only `.log` evidence passes; the full staged check is not claimed as passing.
