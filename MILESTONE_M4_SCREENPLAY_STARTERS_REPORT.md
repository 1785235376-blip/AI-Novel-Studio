# TEXT-11 — explicit independent screenplay starter guides

Baseline: `3a234ed242a2d15698560752d6ac3a982da7c350`, isolated worktree.
Status: **IMPLEMENTED / INTEGRATED FINAL VERIFICATION PENDING / PARTIAL**.

The original CreativeService exposes a bounded, read-only v1 catalog of four
original Chinese writing guides: feature film (8 scenes), short film (4),
animation (6), advertisement (5). These are editable linear prompts, not model
output, professional templates, complete films or a game branching engine.
Prototype scene identifiers are replaced with fresh local identifiers only after
explicit user action. No source chapters, references, director/shot/video data or
private Prompt are inserted.

The existing authenticated V2 route is `/screenplay-presets` under both original
Creative API aliases. Feature/default-off/V1 gates and before/after authority
checks remain authoritative. The catalog reads project existence and validates
scope; it does not read chapters, open a content mutation transaction or create
any document. Two authorized scopes receive the same immutable public guides;
actual project/branch membership remains enforced by the original authorizer.

The original workspace content area offers a collapsed, lazy-reading selector,
full scene-writing preview and explicit “new unsaved screenplay” command. Existing
saved documents remain intact. Dirty, blocked, busy or revoked state cannot be
replaced. Repeated clicks are synchronously fenced; authority/context changes or
closing the catalog abort and discard late reads. User edits persist only through
the original explicit POST/create and versioned PUT/save, with original history,
reopen and export. No additional owner, registry, model call, storage, schema or
protected AppShell change is introduced. JSON remains the complete structure.

## Source and development evidence

The pure catalog was implemented in private local commit
`0c0fd908825a39d8896db012527ba683f1791f1b`, only two new files. Its isolated original
runner passed **16 tests in 0.21s**; that receipt belongs to its own source.

First integration File invocation retained **16 passed / 9 profile skips / 9
setup errors**, caused by a missing parent directory for the new pytest basetemp.
No product assertion ran for those nine cases. Creating only that owned parent
and using a new label retained the failed evidence. Before the next run, the new
foreign-branch fixture expectation was corrected by inspecting its authorizer:
it explicitly permits any syntactically valid branch, so immutable public guides
are identical rather than a nonexistent private document returning 404. An
unauthorized project remains 404; runtime authority revocation remains tested.

The next focused File run passed **25 / 9 profile skips** in 5.89s. It covers all
four original create/edit/reopen/history/export paths, no chapter read or mutation
transaction on catalog access, original API gates and late authority rejection.
Two UI files passed **47 tests in 6.99s** (18 new plus 29 original workspace tests).
The isolated UI runner reused installed dependencies via a symlink, disabled test
cache and used a separate Vite cache directory; no package was installed. Original
main-tree full UI verification still must follow serial integration.

This is ordinary same-round implementation verification. Historical independent
security review remains BLOCKED. Hosted browser/geometry, PostgreSQL and combined
final-source acceptance are not claimed until their actual receipts exist.
Resource reserve takes precedence over starting more work. No later milestone is
being started in this slice.

The new nonempty starter-action accessibility contract first failed (1 test):
React initialized the textarea text node with the guide, but there was no explicit
action label. This is the same observed initial-text mechanism as the preceding
Script failure; the new hosted starter journey has not yet run. One additive
aria-label on the existing action textarea makes its label independent of guide
content. Original labels, user text, browser assertions and timeouts are unchanged.
The red receipt is retained; this local contract is not hosted visual acceptance.

After the narrow action-label correction, all **48** new/adjacent workspace UI
tests pass in 6.58 seconds and full TypeScript checking exits 0. The additive
real browser journey now includes explicit chapterless use, no save on preview,
fresh IDs, original v1/v2 saves, reopen, exact Markdown hash, no manuscript and
expanded-guide geometry at three canonical desktop sizes. It is not locally run.
