# B07 saved interactive-story issue navigation

Baseline: `72b43bffd137d60b6215b10f048f3eefe3b1981b`. The containing local commit identifies delivery. B07 remains **PARTIAL**.

## Audit and actual gap

The original `InteractiveStoryService`, mounted `InteractiveStoryPanel`, client, preview and history already provide manual bool/int variables, restricted typed conditions, choices and assignments, finite server replay, versioned save/reopen/history, source capture and explicit review/export. `analyze` distinguishes structural unreachable/cycle warnings from missing ending paths, invalid targets/variables/types/assignments and conditional dead ends. Its state/step limits remain authoritative; it is not an unbounded proof. No second branch engine or condition interpreter was needed.

Existing review and export use exact current versions/digest receipts. The ZIP contains neutral JSON, generated Ren'Py text/menu subset, typed Godot data, manifests, compatibility losses and checksums. Godot is a data adapter, not a playable project. Media bytes, target engines and arbitrary third-party scripts are not executed or packaged by this change. Original stale-source withholding, author/scope checks, history and import-safe contracts remain unchanged.

The concrete missing seam was that saved analysis rendered node IDs as plain text and discarded choice IDs. Authors had to find the corresponding original editor control manually, especially with duplicate node titles. This slice closes that seam only.

## Bounded flow

1. Open the original saved interactive adaptation. The original analysis now states its story and planning versions, and shows both node and choice IDs. Errors and warnings use twenty-row pages. Cycle warnings remain distinct from invalid/dead-end paths.
2. Explicitly locate a unique exact node/choice in the original editor. Node issues focus its title; choice issues focus its condition control so the existing choice fields can be reviewed. No path is guessed, no text is generated or replaced, and navigation makes no request.
3. Existing unsaved Unicode text, variable inputs and choices remain intact. Dirty drafts explicitly show that the analysis belongs to the saved version, not current input. Missing, ambiguous, wrong-parent, malformed or removed/replaced choices cannot be located. Removed choice identities remain invalid for saved issues even if the original add action reuses their IDs; explicit restore of original input or a new saved-version analysis resets this local guard.
4. Composition capture blocks navigation during IME input. Active save/version-check requests and archived records block issue navigation. Original identity/version remounts reset paging, focus and draft-local identity guards; late A→B→A reads cannot revive old editor issues.
5. The author manually corrects the original draft, explicitly saves through original CAS, then uses existing saved replay, review preview/approval and export preflight/acknowledgment. No autosave, automatic approval or export was added.

Catalog/list refresh continues to retain the owner's selected saved snapshot. Navigation only addresses that explicitly labelled local snapshot, without claiming a freshness reread or changing owner lifecycle. Server save/review/export checks remain authoritative. Existing broader UNKNOWN mutation/recovery UX and durable unsaved recovery are not closed by this navigation work.

## Verification

Exact commands, exit codes, source and log hashes are indexed in `interactive-issue-navigation-20261016.json`.

- 24 selected mock UI checks: 22 original-panel tests, history and PUBLIC placeholder; includes exact-ID navigation with duplicate titles, no navigation writes, Unicode draft/save preservation, saved-analysis labels, missing/removed/malformed/wrong-parent/duplicate IDs, twenty-row paging, archived/busy states, conflict preservation, IME guard, choice-ID reuse, revision/node-order reset and delayed client ABA isolation. Original playback, source rebind, review and acknowledged export regressions remain covered.
- Four nonsecurity File-fixture cases plus one pure bounded-state test: new exact issue → manual repair → original save/reopen/history → variable-aware ending replay → reviewed ZIP/neutral JSON export; existing undefined variable, cycle/unreachable/dead-end/cap and unavailable-choice cases. These are synthetic File-owner evidence, not HTTP or target-engine acceptance.
- 30 PUBLIC contracts, forced TypeScript/Vite, discovery, token/scoped color, diff and 487-file PUBLIC source closure checks.
- Independent review found composition, malformed-reference and reused-choice-ID gaps; these were corrected and independently rerun (27 combined panel/history/reviewer cases). Reviewer-only tests are preserved outside the repository and not shipped.

Initial File/PUBLIC setup failed before test bodies because the default runtime attempted a directory under read-only `/home/agent/.local/share/AI-Novel-Studio`. The failed receipt is retained. After parent direction, the established prior owned-temp profile was applied only to new `.runtime/v2-checks/interactive-navigation-final-file-public` paths; no escalation or permissions change. Final isolated checks passed. An early build that overlapped review edits is superseded by the unchanged-source final build.

## Remaining boundaries

Actual Ren'Py/Godot execution, browser/native IME/visual/accessibility/HTTP integration, Windows/GPU/provider/model quality and full RC are **NOT_RUN**. No browser workaround, external model call, user computer, new schema/backend/permission/lifecycle owner, paid service, push, hosted CI, merge, tag or release. P0 stays BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled; PUBLIC physical isolation and all existing cost/environment/denial boundaries remain intact. Parent final SHA review precedes the next tracked feature slice.
