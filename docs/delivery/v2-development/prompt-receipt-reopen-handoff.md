# Prompt receipt-on-reopen handoff

Date: 2026-10-17. Baseline: `e1e66cedeb7a140b6894850bc21a1e5ac7e06c16`.
Branch: `work/dot-prompt-workspace-20261017`.
Status: bounded frontend fix implemented; primary and independent Prompt regression gates passed. Parent owns integration and commit.

## Actual gap and bounded behavior

While mounted, saving a revision in family A and selecting B before the POST settled previously discarded A's decoded result from the session draft store. Reopening A converted the stale SUBMITTING slot into UNKNOWN even after a known success, conflict or definite rejection. A restored conflict also lost its explicit rebase action because the controller reset conflictCode.

The existing session draft owner now settles only an existing slot with the same project/branch/actor, slot key, request ID, family, base asset/revision and exact frozen content. All twelve content fields, including ordered reference/binding lists, participate. SUBMITTING and matching reconciled UNKNOWN are eligible; missing, replaced, changed or settled slots are not resurrected. Creation promotion refuses an occupied destination family. The controller also checks a monotonic identity/client authority generation, including ABA changes and unmount, before routing outcomes. The existing host removes the component on access denial; this fix does not add an access mechanism.

A valid decoded POST receipt retains the exact saved asset/revision for reopening A without claiming B was saved. A definite 409 restores the conflict and explicit rebase button; rebase still reads the existing authorized current-head owner and retains local text. A definite 4xx remains REJECTED. Genuine ambiguous transport outcomes remain UNKNOWN with the original request ID and frozen content. There is no automatic POST/retry/rebase. The existing actual-unmount UNKNOWN behavior remains unchanged.

## Exact implementation scope

- `frontend/src/prompt/promptDraft.ts`: frozen-operation matcher and conditional session-slot settlement.
- `frontend/src/prompt/usePromptWorkspace.ts`: guarded routing, monotonic authority generation and restored conflict code.
- `frontend/src/prompt/promptDraft.settlement.test.ts`: 27 new unit cases.
- `frontend/src/prompt/PromptWorkspace.receiptReopen.test.tsx`: 11 new controlled-transport UI cases.

No old tests, backend owners, shared canvas/audio/B05 files, configuration, dependencies, frozen contracts or public-entry inventories changed. No new runtime file. `app/creative/prompt_adoption_api.py` still declares `PROMPT_ADOPTION_WRITE_ENABLED = False`; no R3-GATE/security relaxation, provider/model execution, credentials, paid APIs, GPU/Windows acceptance, push, merge or release.

## Verification and provenance

The original, unchanged `scripts/run_v2_checks.py` SHA256 is `64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5`.

Both workers used the approved clean Python at `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python`. Natural startup and original-runner child PathFinder proofs verify actual current-root origins without importing product or pytest modules. The outer environment does not set PYTHONPATH; the unmodified runner sets its own current-root child PYTHONPATH and owned profile.

Primary receipts:
- `prompt-receipt-reopen-origin-r1.json`: PASS, natural and runner-child startup/origin proof.
- `prompt-receipt-reopen-ui-r1.json`: PASS, all 21 Prompt test files /176 tests, including 38 new and 138 unchanged tests.
- `prompt-receipt-reopen-build-r1.json`: PASS, forced `tsc -b --force`, production Vite build and design-token guard (52 files). Vite reports its large-chunk warning; it is not a failed build.

Independent receipts:
- `prompt-receipt-review-origin-r1.json`: PASS, separate natural and runner-child origin proof.
- `prompt-receipt-review-ui-r1.json`: PASS, the same 21 files /176 tests independently repeated, with all 19 old Prompt test modules unchanged.

Each runner receipt records 2,587 source paths with equal before/after maps and `sources_changed_during_check: false`. UI gates use one worker, no file parallelism, no cache and unchanged configuration. Exact method/path routing ensures revision POSTs reach the decoder; successful reopen asserts asset A-3/revision 3 and SAVED rather than inferring success from GET counts. Tests assert unchanged B, all terminal/ambiguous outcomes, replaced slots, all content fields, scope/client ABA, unmount and explicit fresh-head rebase with no automatic POST.

## Qualifications and integration

This is frontend lifecycle verification using controlled transports; it does not claim a newly executed live backend/browser/end-to-end acceptance or completion of R3-I/R3-GATE. Existing backend contracts/owners are consumed unchanged.

This isolated worktree is code/test-complete but uses its pre-existing sparse checkout to omit historical `docs/delivery` material (approximately 1.3 GiB). Sparse configuration was not changed. The source maps establish code/test/runner preservation, not preservation of absent historical documentation. Only the uniquely named new Prompt proof documents belong to this delivery; historical documentation must remain untouched in the full integration tree.

Parent should integrate only the four listed source/test files and uniquely named Prompt evidence indexed alongside this handoff. Do not stage the shared `frontend/node_modules` symlink or build/profile output. Parent owns any commit and combined integration regression gate.
