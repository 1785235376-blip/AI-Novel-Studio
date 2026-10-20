# Template review F2: synchronous draft generation guard

Origin: inherited from fixed c40 and reproduced unchanged at 3300636a. In one
React batch, original controller `change()` could synchronously change the draft
before React updated the template's props. Retained Apply then accepted an old
whole-definition plan and overwrote the intervening author's title. This is
separate from F1's newly introduced visual capacity path; F1's independent fix
is `faeb4d975c4fb44db39132538371f01658d2ff18`.

The original controller now exposes a template confirmation scope tied to its
existing insertion authority and synchronous `bindingMutationEpoch`. The
production view supplies that scope and its current predicate to the existing
template tool. Before the original `change()` can run, the predicate checks the
current controller draft/base refs, live authority/locks and mutation generation.
No new mutation engine, history, Save, backend contract or permission is added.

The generation also creates a fresh rendered scope token. Therefore changing
A→B→A in one batch cannot revive an old confirmation after React rerenders, even
when the original draft object returns. Ordinary status renders preserve the
scope. Existing single-use confirmation and file-request retirement remain.

New regression mounts the actual `studioGraphEditorView` with the original hook:

- Same-batch title change then old Apply preserves the new title, adds no nodes
  or selection, and retains only the author's one history record.
- Same-batch draft A→B→A then old Apply adds no import/history entry; repeating
  that callback after rerender still fails. One undo reaches the author's B.
- A late file read after same-batch target ABA cannot publish a candidate and
  does not add a history record.
- The updated original-controller positive integration still confirms once,
  imports full visual content, supports one undo/redo with stable new IDs, and
  forwards the exact payload only to an explicit mocked Save.

Evidence is in sibling `template-p2-evidence-20261020`: original RED 4 failed / 1
passed across both P2s; F2 first focused run 12 passed; final production-wiring
run 4 passed including the late-file case. Original UI consent/ABA tests and F1
capacity-history rejection passed in the focused run. Type checking and serial
build are recorded separately; an initial frontend-only sparse checkout missed
tracked root fixtures/types and failed type checking. Those original files were
materialized without changing compiler settings or declarations.

These are controlled React/jsdom checks and original Python type/byte validation,
not real Host/PG, native Windows E2E, model/GPU output, real Save, release or full
application acceptance. Original 330 evidence and independent review files were
not modified. Storyboard WIP remains frozen elsewhere; public-build policy and
DSH files are unchanged. Parent-coordinated independent revalidation remains a
separate acceptance step.
