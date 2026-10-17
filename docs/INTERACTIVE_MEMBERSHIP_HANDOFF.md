# B07 existing-adaptation node membership handoff

Date: 2026-10-17 UTC

## Scope and result

The existing interactive editor can explicitly add one unused node from its original planning graph. The candidate selector displays the exact planning node ID, node version, and title. Existing current-node, entry-node, and choice-target selectors also display these identifiers so duplicate titles remain distinguishable; option values and selection semantics are unchanged.

Adding a node only changes the local draft. It appends the exact candidate ID/version/title with blank dialogue, ending, character, background, music, and choices. Existing nodes, dialogue, choices, variables, entry, graph references, and pins are retained. Authors manually connect the new node through the existing choice controls and use the existing explicit Save, optimistic-concurrency, history, review, and export flow.

No node removal, automatic edges, source repinning, new backend engine, parser change, client/API change, or export format change is included. A changed graph or member pin prevents addition and directs the author to the original current-version check and explicit source-rebinding flow. Backend authorization and source capture remain authoritative at Save.

## Changed code and tests

- `frontend/src/experimental/InteractiveStoryPanel.tsx`
- New `frontend/src/experimental/InteractiveStoryPanel.membership.test.tsx`
- New `tests/test_interactive_membership_handoff.py`

All existing tests, backend services, parser, client, export implementation, design tokens, and shared shell remain unchanged.

The UI fails closed for nonunique graph/node IDs, mismatched graph or member versions, unavailable catalog data, stale/withheld records, archived records, busy actions, IME composition, invalid candidate text/version, and the 100-member limit. Candidate text bounds count Unicode code points and reject unpaired surrogates or unsupported controls. Catalog refresh/error transitions and client/scope A→B→A transitions invalidate old selections and callbacks. Revert resets the editor index so an appended node cannot leave a dangling selection.

Static review identified same-batch retained-handler races: a stale add callback could overwrite newly entered text or use an earlier candidate before React rerendered. Draft changes, candidate/current-node selection, Save, and revert now synchronously invalidate the callback ticket; retained-callback tests cover this alongside Unicode and IME preservation. Static review also corrected only the new File test's export expectation to include the original exporter's existing `condition_tree` values from `parse_condition`; the export owner was not changed.

## Verification

All checks used the original `scripts/run_v2_checks.py`, isolated profiles, and frozen sources. File execution used only `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python`. Full natural-startup and actual runner-child PathFinder probes verified origins without importing product or pytest modules. Outer `PYTHONPATH` was unset.

- Primary File: **83 passed, 45 PostgreSQL cases deselected**
- Independent File rerun: **83 passed, 45 PostgreSQL cases deselected**
- Primary UI: **48 passed across 4 files**, including 25 new membership tests
- Independent UI rerun: **48 passed across the same 4 files**
- Forced TypeScript: **PASS**
- Production Vite build: **PASS**, with the existing large-chunk advisory
- UI token guard: **PASS**, 52 files
- Both natural/runner-child origin proofs: **PASS**
- All nine final runner receipts: identical 2,602-source maps, before/after equal, current hashes and log hashes verified, no source drift

File coverage includes subset→append original node→Save→service restart→history, manual new-ending branch, original review/export with exact source/node pins, unchanged planning/manuscript, CAS, explicit history restore, graph ABA and original explicit rebind, candidate drift/archive, malformed membership, owner/scope/archive restrictions, atomic reauthorization, mounted flags, and trusted branch permissions. UI coverage includes exact blank append, dirty Unicode, manual connections, conflict retention, repeated/batched/retained callbacks, catalog loading/errors/ABA, client/scope ABA, IME, withheld/archive gates, duplicate identities, text bounds, and the 100-node limit.

Primary and independent counts are repeat verification, not distinct capability counts. PostgreSQL cases were excluded, not passed.

## Evidence and limitations

The complete evidence inventory is `docs/delivery/v2-development/interactive-membership-evidence-index.json`. It records the nine runner receipts and logs, natural startup proofs, launchers/probes, independent audit artifacts when supplied, frozen source hashes, and this handoff.

This is a thin isolated checkout based on `39ba1c7`, branch `work/dot-interactive-membership-20261017`. Code and tests are present; historical `docs/delivery/` material was deliberately excluded by sparse checkout. This handoff does not claim validation of absent historical delivery records, and no old evidence index or ledger was edited.

Real browser visual/geometry/accessibility validation, native desktop/Windows execution, target-engine execution, PostgreSQL, paid providers, publication, and push are **NOT_RUN**. The export runtime status remains `NOT_RUN`. The build and unit tests are not a substitute for browser or target-engine validation. No stage or commit was performed by the implementation worker; the parent owns final review and the isolated branch commit.
