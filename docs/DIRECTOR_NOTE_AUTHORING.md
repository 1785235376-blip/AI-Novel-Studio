# Director note order and duplication

The original CreativeCanvas Director section now offers earlier/later controls
within the selected scene, and explicit duplication of a direction note. These
operate only on the existing CreativeInput author draft and original onChange /
Save path. No backend owner, proposal approval, graph binding or execution changes.

Moving swaps two same-scene notes and their existing number slots; intervening
other-scene notes, IDs, evidence and author detail remain unchanged. Duplication
makes a detached copy with a fresh note ID in the same scene and retains its
planning/evidence/performance detail. It inserts after the source in global
numeric order and renumbers the author list consecutively; existing IDs remain.
The original 200-note bound stays. Source input is not mutated. Invalid/missing
identity or scene, duplicate generated ID, unsupported action and over-cap copy
are refused. No automatic source/chapter migration or evidence claim is made.

The UI retires old handlers across draft/selection/disabled changes and unmount;
original parent edit authority and dirty-state/save checks remain in force.
Saving still requires the existing explicit action. Removing notes, cross-scene
moves, automatic undo and changing derived Storyboard documents are not added.

Evidence: director-note-order-ui-r2 has 17 focused new/original UI checks and
TypeScript PASS. Tests cover same-scene ordering across interleaved other-scene
notes, detached copied performer detail, identity/cap rejection and actual
CreativeCanvas onChange→explicit Save callback. This is UI integration, not a new
backend save/reopen or product-browser run. r1 had 17 UI checks pass but TypeScript
failed because the injected ID generator inferred the UUID template type; its
explicit string-return type now matches the existing identifier contract. The
failed receipt/log is retained and no original test was changed.
