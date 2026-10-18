# Loaded Prompt content → independent manual draft

2026-10-18. Additive UI capability, not an adoption gate release.

The existing Prompt workspace offers an explicit copy command for a fully loaded,
unmasked, complete saved/clean baseline. It reuses the original startNew/edit and
create/save owners. The copy itself does not issue a POST, invoke a model, change
source revisions, or persist prompt text to browser storage.

Copied: visible text, negative prompt, purpose, model reference, parameters, seed.
Cleared: all character/scene/shot/reference asset bindings and prior change notes.
Family/revision/request identity, origin, approval and server provenance are not
copied. An explicit subsequent save goes to the existing new-family route as MANUAL.
The loaded revision is not represented as a newly verified server head.

Dirty, pending, unknown, rejected/conflicted, masked, partial, stale-baseline,
read-only and loading states refuse the command. Scope changes retire old loaded
detail; stale/unmounted callbacks and duplicate synchronous clicks cannot copy.
Users must save current edits first; this command does not discard unsaved edits.

Verification: original runner receipts under docs/delivery/v2-development/
prompt-independent-draft-ui-20261018-r*. The fixture-driven workspace test uses
real response shapes but a mocked transport; it proves local UI behavior and route
selection, not an end-to-end server save. Existing workspace/scoping/P0 and AppShell
regressions, TypeScript and production build remain part of the focused check.
Actual browser geometry/visual and production model acceptance remain pending.
No shared shell, tokens, backend, authorization or Prompt adoption switch changed.
PROMPT_ADOPTION_WRITE_ENABLED remains False; R3-GATE remains HOLD.

Final r2 result: 53 passed (10 additive, 43 unchanged workspace/P0/scoping/shell).
TypeScript and Vite production build passed. Existing large-chunk warning remains.
The earlier r1 passed 52; r2 adds the scope round-trip/unmount regression, not a
second independent feature count. No existing baseline test was changed.
